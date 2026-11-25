"""The voice client: this laptop's mic and speakers, connected to jarvis-core's voice loop (/ws/voice).

    python -m jarvis.voice.client               # half-duplex: the mic is muted while Jarvis speaks
    python -m jarvis.voice.client --barge-in    # with headphones: talk over him to stop him

Uses the hub's settings: JARVIS_CORE_URL (default http://127.0.0.1:8770, Laptop B itself) and JARVIS_CORE_SESSION
(this laptop's pairing token; setup-core.bat sets both on Laptop B). The thinking happens in the core, so the orb
and captions show on the hub. Reconnects by itself if the core restarts.

The mic goes through WebRTC's echo canceller (pywebrtc-audio) with what the speaker plays as the reference, so he
can talk over Jarvis: Jarvis ducks at once and stops when it's clearly him (the core decides). Without the canceller
it falls back to half-duplex. The mic clean-up (gain, noise suppression) comes from Hearing check.bat
(mic_profile.py). No wake word or push-to-talk yet. Nothing is recorded or stored.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from jarvis.voice import mic_profile, ptt, wake
from jarvis.voice.audio_io import IN_BYTES, EchoCanceller, Mic, Speaker, setup_console_logging
from jarvis.voice.gate import Gate

log = logging.getLogger("jarvis.voice.client")

ECHO_TAIL_S = 0.25
OUT_RATE = 24_000
SESSION_HEADER = "X-Jarvis-Session"


def voice_url(core_url: str) -> str:
    base = core_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):] + "/ws/voice"
    if base.startswith("http://"):
        return "ws://" + base[len("http://"):] + "/ws/voice"
    return base + "/ws/voice"


TAKEN_OVER = "taken_over"  # the core's error code when a newer client takes the voice
BUSY = "busy:"             # + the device that has the voice: this one asked politely and waits (hosted by a hub)


def tell_host(args: argparse.Namespace, state: str, detail: str = "") -> None:
    """Hosted by the hub (--hosted): one line it reads, e.g. "@@ live" or "@@ waiting laptop-b"."""
    if getattr(args, "hosted", False):
        print(f"@@ {state} {detail}".rstrip(), flush=True)


async def session(url: str, token: str, args: argparse.Namespace) -> str:
    """One connection. Returns why it ended."""
    import websockets  # noqa: PLC0415

    async with websockets.connect(url, additional_headers={SESSION_HEADER: token}, max_size=2**20,
                                  ping_interval=20, ping_timeout=60, open_timeout=10) as ws:
        cal = mic_profile.load()
        profile = mic_profile.PROFILES[cal["profile"]]
        hello = {"type": "hello", "device": os.environ.get("COMPUTERNAME", "laptop").lower()}
        if mic_profile.glow(cal):
            hello["glow"] = mic_profile.glow(cal)  # the orb's glow scaled to his voice and his room
        loop = asyncio.get_running_loop()
        gate, hotword, key = listen_setup(args, loop)
        hello["listen"] = gate.mode   # wake / ptt: everything sent is said to Jarvis; always: it may not be
        await ws.send(json.dumps(hello))
        first = json.loads(await ws.recv())
        if first.get("type") != "ready":
            if first.get("code") == "busy":
                return BUSY + str(first.get("device") or "")
            return first.get("message") or "Jarvis core turned the voice down."
        tell_host(args, "live")
        notes = Notes(bool(first.get("review")))
        aec = None
        if not args.half_duplex and EchoCanceller.available():
            with contextlib.suppress(Exception):
                aec = EchoCanceller(OUT_RATE, **profile["aec"])
        duplex = aec is not None or args.barge_in
        print("Connected. Talk to Jarvis (Ctrl+C to stop)."
              + (" You can talk over him to stop him." if duplex else " The mic is ignored while he speaks."),
              flush=True)
        speaker = Speaker(OUT_RATE, args.speaker, aec=aec, loop=loop)
        mic = Mic(loop, args.mic, aec=aec, boost=profile["boost"] or aec is None)
        print(f"  Mic: {cal['profile']}" + (f" (from the hearing check, {cal['checked']})" if cal["checked"] else
                                            " (run Hearing check.bat to tune it to your voice)"), flush=True)
        silence = bytes(IN_BYTES)
        ended: list[str] = []
        glow = mic_profile.glow(cal) or {}
        meter = Meter(glow.get("quiet_db"), glow.get("loud_db"))

        async def tell(msgs: list[dict]) -> None:
            for m in msgs:
                await ws.send(json.dumps(m))

        await tell(notes.start(listen=gate.mode, profile=cal["profile"], checked=cal["checked"], echo_cancel=aec is not None,
                               duplex=duplex, hosted=bool(getattr(args, "hosted", False)),
                               wake_word=hotword is not None, wake_threshold=getattr(hotword, "level", None),
                               talk_key=key is not None, **sound_devices(args)))

        def on_key(down: bool) -> None:
            if down:
                speaker.stop()   # he pressed to talk: Jarvis goes quiet at once, the core cancels the rest
            loop.create_task(tell(gate.key(down)))

        if key is not None:
            key._on_change = on_key
            key.start()

        async def send_mic() -> None:
            while True:
                frame = await mic.frames.get()
                if not duplex and (speaker.playing or time.monotonic() - speaker.last_write < ECHO_TAIL_S):
                    frame = silence  # half-duplex: he can't hear himself
                # The orb's glow: what this mic hears and what this speaker is playing right now, as two numbers,
                # ~12 times a second. Sent even while asleep: a loudness figure, never the sound itself.
                lv = meter.feed(frame, speaker.level)
                if lv is not None:
                    await ws.send(json.dumps({"type": "lv", "m": lv[0], "o": lv[1]}))
                await tell(notes.tick(mic, speaker, asleep=not gate.sending))
                if gate.listening_for_wake and hotword is not None:
                    fired = hotword.feed(frame)
                    notes.wake_score(hotword.score)
                    if fired:   # "hey Jarvis": heard here, on the laptop
                        await tell(notes.woke(hotword.score, hotword.level))
                        await tell(gate.wake())
                        speaker.feed(CHIME)
                        for early in hotword.preroll():
                            await ws.send(early)   # the words he said straight after it
                    continue
                if not gate.sending:
                    continue   # asleep: nothing leaves the laptop
                await ws.send(frame)
                await tell(gate.tick())

        heard = {"bytes": 0}
        jobs: list[Any] = []

        async def do(data: dict[str, Any]) -> None:
            """Hands on this laptop (v0.24.1): open a page or a class file, line his windows up (jarvis.reach.hands)."""
            from jarvis.reach import hands  # noqa: PLC0415

            try:
                result = await asyncio.to_thread(hands.run, str(data.get("kind")), data.get("args"))
            except Exception as exc:  # noqa: BLE001 - the core gets an answer either way
                result = {"ok": False, "why": type(exc).__name__}
            with contextlib.suppress(Exception):
                await ws.send(json.dumps({"type": "done", "id": data.get("id"), **result}))

        async def receive() -> None:
            async for msg in ws:
                if isinstance(msg, bytes):
                    if not heard["bytes"]:
                        print("  (Jarvis is speaking)", flush=True)
                        await tell(gate.jarvis_audio())   # so "yes" or "stop" works without the wake word
                    heard["bytes"] += len(msg)
                    notes.audio(len(msg))
                    try:
                        speaker.feed(msg)
                    except Exception as exc:  # noqa: BLE001 - say why the speaker failed, keep listening
                        log.warning("voice.speaker_failed", extra={"error": type(exc).__name__, "reason": str(exc)[:200]})
                    continue
                with contextlib.suppress(ValueError):
                    data: dict[str, Any] = json.loads(msg)
                    if data.get("type") == "orb":
                        gate.core(data.get("state"))
                        if data.get("state") == "idle":
                            heard["bytes"] = 0
                            await tell(notes.reply_done(speaker))
                    elif data.get("type") == "stop":
                        speaker.stop()
                    elif data.get("type") == "duck":
                        speaker.duck(bool(data.get("on")))
                    elif data.get("type") == "do":
                        jobs.append(asyncio.ensure_future(do(data)))  # kept so the task isn't collected mid-way
                        del jobs[:-8]
                    elif data.get("type") == "error":
                        if data.get("code") == TAKEN_OVER:
                            ended.append(TAKEN_OVER)
                            return
                        ended.append(data.get("message", ""))
                        print(f"  [core] {data.get('message', '')}", flush=True)

        tasks = [asyncio.create_task(send_mic()), asyncio.create_task(receive())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if not t.cancelled() and t.exception() is not None:
                    exc = t.exception()
                    log.warning("voice.client_failed", extra={"error": type(exc).__name__, "reason": str(exc)[:200]})
        finally:
            for t in tasks:
                t.cancel()
            if key is not None:
                key.stop()
            mic.close()
            speaker.close()
        return ended[-1] if ended else "The connection to Jarvis core closed."


class Notes:
    """The voice window's own numbers for a review (v0.16.0), sent only when the core says review recording is on:
    how close the wake word came, whether this window or its sound card fell behind, and how each reply's sound
    arrived. Numbers and device names only; never sound, never words (asleep included: C23)."""

    EVERY_S = 5.0
    QUIET_EVERY_S = 60.0

    def __init__(self, on: bool, clock: Any = time.monotonic) -> None:
        self.on, self.clock = on, clock
        self._at = self._said_at = clock()
        self._peak = 0.0
        self._last: dict = {}
        self._reply: dict | None = None

    def start(self, **facts: Any) -> list[dict]:
        return [{"type": "note", "what": "start", **facts}] if self.on else []

    def wake_score(self, score: float) -> None:
        self._peak = max(self._peak, score)

    def woke(self, score: float, level: float) -> list[dict]:
        return [{"type": "note", "what": "wake", "score": round(score, 3), "threshold": level}] if self.on else []

    def audio(self, n: int) -> None:
        """A piece of Jarvis's voice arrived."""
        if not self.on:
            return
        now = self.clock()
        r = self._reply
        if r is None:
            self._reply = {"bytes": n, "chunks": 1, "first": now, "last": now, "max_gap": 0.0}
            return
        r["max_gap"] = max(r["max_gap"], now - r["last"])
        r["bytes"], r["chunks"], r["last"] = r["bytes"] + n, r["chunks"] + 1, now

    def reply_done(self, speaker: Any) -> list[dict]:
        r, self._reply = self._reply, None
        if not self.on or r is None:
            return []
        return [{"type": "note", "what": "reply_audio", "bytes": r["bytes"], "chunks": r["chunks"],
                 "seconds": round(r["bytes"] / (2 * OUT_RATE), 2), "arrived_over_ms": round((r["last"] - r["first"]) * 1000),
                 "longest_wait_ms": round(r["max_gap"] * 1000), "ran_dry": getattr(speaker.play, "underruns", 0),
                 "card_trouble": getattr(speaker, "trouble", 0)}]

    def tick(self, mic: Any, speaker: Any, asleep: bool) -> list[dict]:
        """Every few seconds: one line if anything is worth saying, else one a minute to show the window is alive."""
        if not self.on:
            return []
        now = self.clock()
        if now - self._at < self.EVERY_S:
            return []
        self._at = now
        peak, self._peak = self._peak, 0.0
        facts = {"mic_behind": mic.frames.qsize(), "mic_dropped": getattr(mic, "dropped", 0),
                 "mic_trouble": getattr(mic, "trouble", 0), "ran_dry": getattr(speaker.play, "underruns", 0),
                 "card_trouble": getattr(speaker, "trouble", 0)}
        notable = peak >= 0.15 or facts["mic_behind"] > 5 or facts != {**self._last, "mic_behind": facts["mic_behind"]}
        if not notable and now - self._said_at < self.QUIET_EVERY_S:
            return []
        self._last, self._said_at = facts, now
        return [{"type": "note", "what": "window", "asleep": asleep, "wake_peak": round(peak, 3), **facts}]


def sound_devices(args: argparse.Namespace) -> dict:
    """Which microphone and speaker this window is using, by name."""
    out: dict = {}
    with contextlib.suppress(Exception):
        import sounddevice as sd  # noqa: PLC0415

        for name, kind, chosen in (("mic", "input", args.mic), ("speaker", "output", args.speaker)):
            info = sd.query_devices(chosen, kind)
            out[name] = {"name": info.get("name"), "rate": info.get("default_samplerate"),
                         "latency_ms": round(1000 * float(info.get(f"default_low_{kind}_latency") or 0), 1)}
    return out


class Meter:
    """The mic's loudness as 0-1 on his own range (the Hearing check's room noise to his voice), the loudest of
    the last ~80 ms, ready about 12 times a second."""

    EVERY_S = 0.08

    def __init__(self, quiet_db: object = None, loud_db: object = None) -> None:
        from jarvis.voice.session import LOUD_DB, QUIET_DB  # noqa: PLC0415

        try:
            q, top = float(quiet_db), float(loud_db)  # type: ignore[arg-type]
            self.range = (q, top) if -90.0 <= q < top <= 0.0 and top - q >= 10.0 else (QUIET_DB, LOUD_DB)
        except (TypeError, ValueError):
            self.range = (QUIET_DB, LOUD_DB)
        self._peak, self._out, self._at = 0.0, 0.0, 0.0

    def feed(self, frame: bytes, out_level: float, now: float | None = None) -> tuple[float, float] | None:
        from jarvis.voice.session import level_of  # noqa: PLC0415

        self._peak = max(self._peak, level_of(frame, *self.range))
        self._out = max(self._out, out_level)
        now = time.monotonic() if now is None else now
        if now - self._at < self.EVERY_S:
            return None
        self._at = now
        m, o, self._peak, self._out = self._peak, self._out, 0.0, 0.0
        return round(m, 2), round(o, 2)


def _chime() -> bytes:
    """A soft two-note "I'm listening" (~140 ms, quiet) at 24 kHz, played through the echo canceller."""
    import numpy as np  # noqa: PLC0415

    def note(hz: float, ms: int) -> np.ndarray:
        t = np.arange(int(OUT_RATE * ms / 1000)) / OUT_RATE
        env = np.minimum(1.0, np.minimum(t / 0.008, (t[-1] - t) / 0.03 + 1e-9))
        return np.sin(2 * np.pi * hz * t) * env

    wave = np.concatenate([note(660, 60), note(880, 80)]) * 0.12 * 32767
    return wave.astype(np.int16).tobytes()


CHIME = _chime()


def listen_setup(args: argparse.Namespace, loop: asyncio.AbstractEventLoop) -> tuple[Gate, Any, Any]:
    """The listen mode, the wake word and the talk key, falling back gracefully if a part isn't installed."""
    mode = args.listen
    hotword = key = None
    if mode == "wake":
        if wake.available():
            try:
                hotword = wake.WakeWord()
            except Exception as exc:  # noqa: BLE001 - say why, keep talking
                log.warning("voice.wake_failed", extra={"error": type(exc).__name__})
        if hotword is None:
            print("  The wake word isn't set up (run setup-voice.bat), so Jarvis listens all the time for now.",
                  flush=True)
            mode = "always"
    if ptt.available():
        try:
            key = ptt.PushToTalk(loop, lambda _down: None)
        except Exception as exc:  # noqa: BLE001 - no keyboard hook: carry on without the key
            log.warning("voice.ptt_failed", extra={"error": type(exc).__name__})
    if mode == "ptt" and key is None:
        print("  Push-to-talk isn't set up (run setup-voice.bat), so Jarvis listens all the time for now.", flush=True)
        mode = "always"
    hold = f" Hold {ptt.label(key.name)} to talk any time." if key is not None else ""
    print({"wake": "  Say \"hey Jarvis\" to talk." + hold,
           "ptt": "  Hold " + (ptt.label(key.name) if key else "the key") + " while you talk, let go when you're done.",
           "always": "  Listening all the time." + hold}[mode], flush=True)
    return Gate(mode), hotword, key


async def run(args: argparse.Namespace) -> int:
    core = os.environ.get("JARVIS_CORE_URL", "http://127.0.0.1:8770")
    token = os.environ.get("JARVIS_CORE_SESSION", "")
    if not token:
        print("This laptop isn't paired with Jarvis core yet (JARVIS_CORE_SESSION is empty). See LAPTOP_B_SETUP.md.")
        tell_host(args, "off", "not_paired")
        return 1
    url = voice_url(core)
    hosted = bool(getattr(args, "hosted", False))
    take = asyncio.Event()      # "Talk here" in the hub: take the voice even though another laptop has it
    if getattr(args, "take", False):
        take.set()
    if hosted:
        watch_host(asyncio.get_running_loop(), take)
    delay = 2.0
    while True:
        polite = hosted and not take.is_set()
        take.clear()
        try:
            why = await session(url + ("?polite=1" if polite else ""), token, args)
            delay = 2.0
            if why.startswith(BUSY) or (hosted and why == TAKEN_OVER):
                # another laptop has the voice. Started by a hub, this one waits its turn: it asks again every few
                # seconds (and gets the voice when the other closes), or at once when he presses "Talk here".
                who = why[len(BUSY):] if why.startswith(BUSY) else ""
                tell_host(args, "waiting", who)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(take.wait(), WAIT_TURN_S)
                continue
            if why == TAKEN_OVER:  # a newer window has the voice: stop here, or the two would take turns forever
                print("  Another Talk to Jarvis window has the voice now, so this one has stopped. You can close it.",
                      flush=True)
                return 0
        except OSError:
            why = "Jarvis core isn't answering."
        except Exception as exc:  # noqa: BLE001 - say why, then try again
            code = getattr(getattr(exc, "rcvd", None), "code", None)
            why = {4401: "This laptop isn't paired with Jarvis core.",
                   4403: "This laptop is paired view-only; it can't talk to Jarvis."}.get(code, f"{type(exc).__name__}")
            if code in (4401, 4403):
                print(why)
                tell_host(args, "off", "not_paired" if code == 4401 else "view_only")
                return 1
        tell_host(args, "down", "core" if "core" in why else "error")
        print(f"  {why} Trying again in {delay:.0f} s.", flush=True)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30.0)


WAIT_TURN_S = 4.0


def watch_host(loop: asyncio.AbstractEventLoop, take: asyncio.Event) -> None:
    """Hosted by the hub: it talks to this process through stdin. "take" = take the voice now. When the hub goes
    away (stdin closes), so does this, so no voice window is ever left running without its hub."""
    import threading  # noqa: PLC0415

    def read() -> None:
        try:
            for line in sys.stdin:
                if line.strip() == "take":
                    loop.call_soon_threadsafe(take.set)
        except Exception:  # noqa: BLE001, S110 - a broken pipe is the hub leaving
            pass
        os._exit(0)

    threading.Thread(target=read, name="jarvis-voice-host", daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.client", description="Talk to Jarvis core")
    parser.add_argument("--barge-in", action="store_true", help="keep listening while Jarvis speaks (headphones)")
    parser.add_argument("--half-duplex", action="store_true", help="ignore the mic while Jarvis speaks (no echo canceller)")
    parser.add_argument("--mic", type=int, help="microphone number (see: python -m jarvis.voice.talk --devices)")
    parser.add_argument("--speaker", type=int, help="speaker number")
    parser.add_argument("--hosted", action="store_true",
                        help="started by the hub: wait politely if another laptop has the voice, obey the hub")
    parser.add_argument("--take", action="store_true", help="with --hosted: take the voice on the first connect")
    parser.add_argument("--listen", choices=("wake", "ptt", "always"),
                        default=(os.environ.get("JARVIS_LISTEN") or "wake").lower(),
                        help='wake: after "hey Jarvis" (default); ptt: only while the talk key is held; always: always')
    args = parser.parse_args(argv)
    logs = Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis") / "logs"
    setup_console_logging(logs / "voice-client.log" if logs.is_dir() else None)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
