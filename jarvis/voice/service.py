"""The voice loop inside jarvis-core (M0.4 in the core): one client streams the mic in, Jarvis's voice streams out.

    client (Laptop A or B)  --binary 20 ms 16 kHz PCM-->  /ws/voice  -->  VAD > Smart Turn > STT > T0 > T1 > TTS
                            <--binary 24 kHz PCM, JSON control--

Why in the core: the orb, captions and latency become hub events on the core's bus (the hub on both laptops shows
them), the keys come from the core's KeyManager (key swaps follow at once), and Laptop A's client stays thin (C37).

Protocol (text frames are JSON):
- client -> core: binary audio; {"type": "hello", "device": "laptop-a"}; {"type": "playing", "on": bool} so the
  pipeline knows when the client is still playing Jarvis's voice.
- core -> client: binary audio; {"type": "ready"}; {"type": "stop"} (barge-in: drop what's buffered);
  {"type": "error", "message": ...}.
One client at a time: a new connection replaces the old one (the newest laptop is where he is).

Nothing loads unless the voice packages, the speech model, the voice ID and the keys are all there; the core runs
fine without voice, and /healthz says what's missing.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
import time
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis import review

log = logging.getLogger("jarvis.voice.service")

STT_DIR_NAME = "sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25"
CLIENT_OUT_DELAY_S = 0.1  # the client's speaker buffer
BRAINS = {"quick": "claude-haiku-5-5", "deep": "claude-sonnet-5-5"}   # the hub setting voice_brain -> the model
FILLER_AFTER_MS = 800.0  # no first word from Claude this long after he finished -> one short filler


def _warm() -> None:
    with contextlib.suppress(Exception):
        __import__("anthropic")


def now_card() -> str:
    now = datetime.now()
    hour = now.strftime("%I").lstrip("0")
    return f"# Now\n{now:%A %d %B %Y}, {hour}:{now:%M} {now:%p}".replace(" 0", " ", 1) + ", Saskatoon."


class BusEvents:
    """The voice session's event sink -> the core's bus (orb.state, caption.show). Never raises.

    v0.13.0: orb states (not the level ticks) also go to the connected voice window, so it knows when a
    conversation is still going (stay awake after the wake word) and when it's over (go back to sleep)."""

    def __init__(self, bus: Any) -> None:
        self.bus = bus
        self.client: Any = None
        self.on_muted: Any = None      # called with True/False when the mic's muted state changes (the hub's switch)
        self._muted = False

    async def publish(self, type: str, data: Any) -> None:
        with contextlib.suppress(Exception):
            self.bus.publish(type, dict(data))
        if type == "orb.state" and "level" not in data:
            muted = data.get("state") == "muted"
            if muted != self._muted:
                self._muted = muted
                if self.on_muted is not None:
                    with contextlib.suppress(Exception):
                        self.on_muted(muted)
        if type == "orb.state" and self.client is not None and "level" not in data:
            with contextlib.suppress(Exception):
                await _send_json(self.client, {"type": "orb", "state": data.get("state")})


class ClientAudio:
    """Audio out = the connected client. Writes 20 ms slices; stop() tells the client to drop its buffer."""

    def __init__(self) -> None:
        self.ws: Any = None
        self.playing_until = 0.0

    async def write(self, pcm: bytes) -> None:
        ws = self.ws
        if ws is None:
            return
        with contextlib.suppress(Exception):
            await ws.send_bytes(pcm)
            # The client plays in real time: 24 kHz mono int16 = 48 bytes per ms. Pace roughly so a barge-in stop
            # lands before the client has buffered the whole answer.
            self.playing_until = max(self.playing_until, time.monotonic()) + len(pcm) / 48_000
            ahead = self.playing_until - time.monotonic()
            if ahead > 0.3:
                await asyncio.sleep(ahead - 0.3)

    def remaining(self) -> float:
        """Seconds of sent audio the client hasn't played yet (+ its sound card's own delay)."""
        return max(0.0, self.playing_until - time.monotonic()) + CLIENT_OUT_DELAY_S if self.playing_until else 0.0

    def stop(self) -> None:
        self.playing_until = 0.0
        ws = self.ws
        if ws is not None:
            asyncio.ensure_future(_send_json(ws, {"type": "stop"}))

    def duck(self, on: bool) -> None:
        """He's talking over Jarvis: quieter at once (the client applies it); stop() follows if it's a barge-in."""
        ws = self.ws
        if ws is not None:
            asyncio.ensure_future(_send_json(ws, {"type": "duck", "on": bool(on)}))


ASK_TIMEOUT_S = 8.0


async def _send_json(ws: Any, msg: dict) -> None:
    if review.on():       # what the voice window is told: every change of state, the level stream thinned out
        review.sampled("voice.sent", f"{msg.get('type')}:{msg.get('state')}:{msg.get('on')}:{msg.get('code')}", 0.5, msg=msg)
    with contextlib.suppress(Exception):
        await ws.send_text(json.dumps(msg))


class VoiceService:
    async def _recall(self, text: str) -> str:
        return await self.learner.recall(text) if self.learner is not None else ""

    def _heard(self, user: str, reply: str) -> None:
        if self.learner is not None:
            self.learner.heard(user, reply)

    async def ask_client(self, kind: str, args: dict | None = None, timeout_s: float = ASK_TIMEOUT_S) -> dict:
        """Ask the voice program on the laptop he is at to do one small thing there (jarvis.reach.hands: windows,
        place, open). Raises RuntimeError with no voice program connected, TimeoutError when it doesn't answer (an
        older voice program doesn't know the question). T1-T2."""
        ws = self.client
        if ws is None:
            raise RuntimeError("no voice program is connected")
        ask_id = uuid.uuid4().hex[:12]
        asked = self._asks[ask_id] = asyncio.get_running_loop().create_future()
        try:
            await _send_json(ws, {"type": "do", "id": ask_id, "kind": kind, "args": args or {}})
            return await asyncio.wait_for(asked, timeout_s)
        finally:
            self._asks.pop(ask_id, None)

    def now_card(self) -> str:
        """The time, then his day and due work when the hub feed has them (v0.18.0). The feed's lines are facts he can
        be answered from directly: no tool round for "what's next", "what room", "what's due". Never raises."""
        lines = ""
        if self.now_lines is not None:
            with contextlib.suppress(Exception):
                lines = self.now_lines() or ""
        if not lines:
            return now_card()
        return (f"{now_card()}\n{lines}\n(Today, Next and Due above are current: answer from them directly. "
                "Use a tool only for other days or details that aren't there.)")

    def __init__(self, root: Path, bus: Any, keys: Any, settings: Any) -> None:
        self.root, self.bus, self.keys, self.settings = Path(root), bus, keys, settings
        self.status, self.reason = "off", "not started"
        self.client: Any = None
        self.client_name = ""
        self.on_muted: Any = None   # the core keeps the Microphone switch in step with "mute the microphone"
        self.brain = "quick"        # which model answers him (BRAINS); the core restores his choice at start
        self.cloud_hearing = False  # his switch: ElevenLabs writes his words down (jarvis.voice.stt_cloud), else this laptop
        self._hearing: Any = None
        self.learner = None         # jarvis.core.learning.Learner, set by the core when memory is up
        self.client_here = False    # the voice window is on this laptop (work_on opens files only then)
        self._asks: dict[str, asyncio.Future] = {}   # things asked of the laptop he is at, waiting for its answer
        self.now_lines = None       # the hub feed's now card text (jarvis.core.hub_feed.HubFeed.now_text), set by the core
        self._parts: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._load: asyncio.Task | None = None
        self.tools: Any = None  # jarvis.tools.voice.VoiceTools, set by the core when tools are on (TOOLS §2)

    # ---- readiness -------------------------------------------------------------------------------------------
    def missing(self) -> str:
        """What stops the voice loop from running, in his words, or "" when everything is there."""
        try:
            import pipecat  # noqa: F401, PLC0415
            import sherpa_onnx  # noqa: F401, PLC0415
        except Exception:
            return "Voice isn't installed: run setup-voice.bat."
        if not (self.root / "models" / "stt" / STT_DIR_NAME / "encoder.int8.onnx").exists():
            return "The speech model isn't downloaded: run setup-voice.bat."
        if not self.settings.voice_id():
            return "No voice yet: paste the ElevenLabs voice ID in Controls › Keys › Voice."
        manager = getattr(self.keys, "manager", None)
        if manager is None:
            return "The keys aren't available."
        for provider in ("anthropic", "elevenlabs"):
            try:
                manager.client(provider)
            except Exception:
                return f"No live {'Claude' if provider == 'anthropic' else 'ElevenLabs'} key: add it in Controls › Keys."
        return ""

    def check(self) -> tuple[str, dict]:
        """For /healthz: voice is optional, so it never turns the light amber or red; the info says its state."""
        info: dict = {"code": self.status}
        if self.client is not None:
            info["device"] = self.client_name
        return "ok", info

    # ---- loading ---------------------------------------------------------------------------------------------
    def preload(self) -> None:
        """Start loading the models in the background (core start-up must not wait for them)."""
        if self._load is None and not self.missing():
            self._load = asyncio.create_task(self._ensure(), name="jarvis-voice-load")
            # and the Anthropic library, off the event loop, so his first question doesn't wait for a cold import
            threading.Thread(target=_warm, name="jarvis-warm", daemon=True).start()

    async def _ensure(self) -> dict[str, Any]:
        async with self._lock:
            reason = self.missing()
            if reason:
                self.status, self.reason = "off", reason
                raise RuntimeError(reason)
            voice_id = self.settings.voice_id()
            if self._parts is not None and self._parts["voice_id"] == voice_id:
                return self._parts
            if self._parts is not None:  # the voice changed in the hub: rebuild with the new one
                with contextlib.suppress(Exception):
                    await self._parts["tts"].aclose()
            self.status, self.reason = "loading", ""
            t = time.perf_counter()
            self._parts = await self._build(voice_id)
            self.status = "ready"
            from jarvis.health.memory import memory  # noqa: PLC0415

            mem = memory() or (0, 0)
            log.info("voice.loaded", extra={"ms": (time.perf_counter() - t) * 1000, "free_mb": mem[0],
                                            "mem_pct": mem[1]})
            return self._parts

    async def _build(self, voice_id: str) -> dict[str, Any]:
        from jarvis.health.latency import LatencyRecorder  # noqa: PLC0415
        from jarvis.voice import turn_tuning  # noqa: PLC0415
        from jarvis.voice.adapters_real import SherpaNemotronStt, SileroVad, SmartTurnV3  # noqa: PLC0415
        from jarvis.voice.config import VoiceConfig  # noqa: PLC0415
        from jarvis.voice.pipeline import build_pipeline  # noqa: PLC0415
        from jarvis.voice.router_t0 import RouterT0  # noqa: PLC0415
        from jarvis.voice.session import VoiceSession  # noqa: PLC0415
        from jarvis.voice.talker_t1 import TalkerT1  # noqa: PLC0415
        from jarvis.voice.tts_elevenlabs import ElevenLabsTTS  # noqa: PLC0415

        turns = turn_tuning.load(self.root)  # Pipecat's baseline, or what Conversation check.bat chose (v0.12.5)
        config = VoiceConfig.from_mapping({"core_root": str(self.root), "voice_id": voice_id,
                                           "barge_in_mode": "confirm", "filler_after_ms": FILLER_AFTER_MS, "patience": True,
                                           "vad_stop_ms": turns.vad_stop_ms, "llm_model": BRAINS[self.brain]})
        manager = self.keys.manager
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        recorder = LatencyRecorder(sink=self.root / "logs" / "voice-latency.jsonl")
        events = BusEvents(self.bus)
        events.on_muted = lambda muted: self.on_muted(muted) if self.on_muted is not None else None
        session = VoiceSession(config, recorder=recorder, events=events)
        stt = await asyncio.to_thread(SherpaNemotronStt, self.root / "models" / "stt" / STT_DIR_NAME, num_threads=4)
        from jarvis.voice.stt_cloud import CloudStt, Hearing  # noqa: PLC0415

        stt = self._hearing = Hearing(stt, CloudStt(manager.client("elevenlabs")), on=self.cloud_hearing)
        tts = ElevenLabsTTS(config, manager.client("elevenlabs"))
        out = ClientAudio()
        from jarvis.voice.phrases import PhraseCache  # noqa: PLC0415

        phrases = PhraseCache(config.phrase_dir, voice_id=voice_id, model=config.tts_model,
                              settings=config.voice_settings, output_format=config.tts_output_format,
                              render=tts.synthesize)

        class NoApprovals:
            def pending(self) -> None:
                return None

        class Commands:
            async def run(self, command: Any) -> None:
                log.info("voice.command", extra={"command": command.name})  # not "name": logging owns that word and raised

        router = RouterT0(now=datetime.now, clock=session.clock, approvals=NoApprovals(),
                          approval_window_s=config.approval_window_s)
        talker = TalkerT1(config, manager.client("anthropic"), now_card=self.now_card, tools=self.tools)
        talker.recall, talker.on_learn = self._recall, self._heard   # memory in and out of every turn (v0.20.0)
        with contextlib.suppress(Exception):
            from jarvis.voice.lessons import vocabulary_note  # noqa: PLC0415

            talker.hearing_note = vocabulary_note(self.root)   # from "Teach Jarvis your voice.bat", if he's run it
        pipeline = build_pipeline(session, vad=SileroVad.from_settings(turns), turn=SmartTurnV3(), stt=stt,
                                  router=router, talker=talker, tts=tts, audio_out=out, commands=Commands(),
                                  phrases=phrases, incomplete_ms=turns.incomplete_ms)
        with contextlib.suppress(Exception):
            await tts.start()  # warm socket; it re-opens by itself when he starts talking

        async def render_fillers() -> None:  # once per voice; after that they play from disk in ~1 ms
            for text in config.fillers:
                with contextlib.suppress(Exception):
                    await phrases.ensure(text)

        self._fillers = asyncio.create_task(render_fillers())
        return {"events": events, "voice_id": voice_id, "session": session, "pipeline": pipeline, "tts": tts, "out": out}

    async def announce(self, text: str) -> bool:
        """Say a task's result (or a task's question) at the next quiet moment. False when no one is listening (the
        caller then shows it as a caption only)."""
        parts = self._parts
        if parts is None or self.client is None:
            return False
        from jarvis.voice.talker_t1 import TalkerProcessor  # noqa: PLC0415

        talker = next((p for p in parts["pipeline"].processors if isinstance(p, TalkerProcessor)), None)
        return bool(talker is not None and await talker.announce(text))

    # ---- a client --------------------------------------------------------------------------------------------
    async def attach(self, ws: Any, device: str, *, polite: bool = False) -> None:
        """Serve one client until it goes away. A newer client replaces this one, unless it asked politely
        (v0.15.0: a hub starts the voice by itself, and must not take it from the laptop he's talking on): then it
        is told who has the voice and waits its turn."""
        from jarvis.voice.frames import InputAudioRawFrame  # noqa: PLC0415

        if polite and self.client is not None:
            await _send_json(ws, {"type": "error", "code": "busy", "device": self.client_name,
                                  "message": f"{self.client_name or 'Another laptop'} has the voice."})
            return
        try:
            parts = await self._ensure()
        except Exception as exc:
            await _send_json(ws, {"type": "error", "message": str(exc) or "Voice isn't ready."})
            return
        if polite and self.client is not None:   # someone connected while the models loaded
            await _send_json(ws, {"type": "error", "code": "busy", "device": self.client_name,
                                  "message": f"{self.client_name or 'Another laptop'} has the voice."})
            return
        if self.client is not None:
            await _send_json(self.client, {"type": "error", "code": "taken_over",
                                                "message": "Another Talk to Jarvis window took over the voice."})
            with contextlib.suppress(Exception):
                await self.client.close()
        self.client, self.client_name = ws, device
        # is he at this laptop? A window on this machine connects from loopback with nothing in between; the other
        # laptop arrives through tailscale serve, which also looks like loopback but says who it forwarded for.
        peer = getattr(getattr(ws, "client", None), "host", "") or ""
        headers = getattr(ws, "headers", None) or {}
        self.client_here = peer in ("127.0.0.1", "::1", "localhost") and not headers.get("x-forwarded-for")
        out: ClientAudio = parts["out"]
        out.ws = ws
        pipeline = parts["pipeline"]
        events = parts.get("events")
        session = parts.get("session")
        if events is not None:
            events.client = ws
        # "review": the voice window may send its own notes (wake-word scores, sound running dry) while he has
        # review recording on; numbers only, as with the loudness meter
        await _send_json(ws, {"type": "ready", **({"review": True} if review.on() else {})})
        review.note("voice.session", what="connected", device=device, polite=polite, brain=self.brain)
        if session is not None:
            session.attentive, session.addressed, session.shown = False, False, "idle"
        self.bus_publish("orb.state", {"state": "idle"})
        ptt = {"down": False, "first": False}
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                data = msg.get("bytes")
                if data:
                    frame = InputAudioRawFrame(audio=data, ptt=ptt["down"])
                    if ptt["first"]:
                        frame.meta["ptt_down"], ptt["first"] = True, False
                    await pipeline.queue_frame(frame)
                    continue
                text = msg.get("text")
                if text:
                    with contextlib.suppress(ValueError, TypeError, AttributeError):
                        info = json.loads(text)
                        kind = info.get("type")
                        if kind == "done":   # an answer from the laptop he is at; never recorded (it can hold window titles)
                            asked = self._asks.get(str(info.get("id")))
                            if asked is not None and not asked.done():
                                asked.set_result(info)
                            continue
                        if kind == "lv":
                            review.sampled("voice.client", "lv", 1.0, device=device, msg=info)
                        elif kind == "note":
                            review.note("client.note", device=device, **{k: v for k, v in info.items() if k != "type"})
                        else:
                            review.note("voice.client", device=device, msg=info)
                        if kind == "lv" and session is not None:
                            # the window's own meter: what its mic hears and its speaker plays, right now
                            await session.set_levels(info.get("m"), info.get("o"))
                        elif kind == "hello" and session is not None:
                            if isinstance(info.get("glow"), dict):
                                # the glow's range from the Hearing check: his room's noise to his normal voice
                                session.set_level_range(info["glow"].get("quiet_db"), info["glow"].get("loud_db"))
                            # after a wake word or with a talk key, everything that arrives is said to Jarvis
                            session.addressed = info.get("listen") in ("wake", "ptt")
                        elif kind == "ptt":
                            await self._ptt(pipeline, session, ptt, bool(info.get("down")), InputAudioRawFrame)
                        elif kind == "listen" and session is not None:
                            # the voice window woke (wake word) or went back to sleep: show it at once
                            session.attentive = bool(info.get("on"))
                            if not session.attentive:   # asleep: no more audio is coming, so an open turn ends now
                                await pipeline.queue_frame(InputAudioRawFrame(audio=b"", meta={"end_turn": True}))
                            await session.show_orb()
        finally:
            review.note("voice.session", what="disconnected", device=device, taken_over=self.client is not ws)
            if events is not None and events.client is ws:
                events.client = None
            if self.client is ws:
                self.client, self.client_name = None, ""
                out.ws = None
                out.stop()
                if session is not None:
                    session.attentive = False
                    with contextlib.suppress(Exception):   # the window went away mid-sentence: close the turn
                        await pipeline.queue_frame(InputAudioRawFrame(audio=b"", meta={"end_turn": True}))
                    session.shown = "idle"
                self.bus_publish("orb.state", {"state": "idle"})

    async def _ptt(self, pipeline: Any, session: Any, ptt: dict, down: bool, frame_cls: Any) -> None:
        """Push-to-talk (v0.13.0): frames while the key is held are his turn; release ends it at once."""
        if down and not ptt["down"]:
            ptt["down"], ptt["first"] = True, True
            if session is not None:
                session.attentive = True   # feedback before he says a word
                await session.show_orb()
        elif not down and ptt["down"]:
            ptt["down"], ptt["first"] = False, False
            await pipeline.queue_frame(frame_cls(audio=bytes(640), ptt=True, meta={"ptt_release": True}))
            if session is not None:
                session.attentive = False
                await session.show_orb()   # pressed, said nothing: back to rest

    def _talker(self) -> Any:
        parts = self._parts
        if parts is None:
            return None
        from jarvis.voice.talker_t1 import TalkerProcessor  # noqa: PLC0415

        return next((p for p in parts["pipeline"].processors if isinstance(p, TalkerProcessor)), None)

    async def set_brain(self, brain: str) -> None:
        """Which Claude model answers him (the hub setting voice_brain, v0.15.0). Changes from his next sentence on:
        no restart, and the conversation so far carries over."""
        if brain not in BRAINS:
            return
        self.brain = brain
        proc = self._talker()
        if proc is not None:
            proc.talker.config = replace(proc.talker.config, llm_model=BRAINS[brain])
        log.info("voice.brain", extra={"kind": brain})

    async def set_cloud_hearing(self, on: bool) -> None:
        """His Cloud hearing switch (v0.25.0). From his next sentence on; the laptop's model stays loaded as the net."""
        self.cloud_hearing = bool(on)
        if self._hearing is not None:
            await self._hearing.set_on(self.cloud_hearing)
        log.info("voice.cloud_hearing", extra={"kind": "on" if self.cloud_hearing else "off"})

    async def set_muted(self, muted: bool) -> None:
        """The hub's Microphone switch (v0.15.0). While muted nothing he says is taken in, so only the hub (or the
        talk key) can turn it back on."""
        session = (self._parts or {}).get("session")
        if session is None:
            return
        session.muted = bool(muted)
        if muted and session.user_turn is not None:
            session.finish_turn(session.user_turn)
            session.user_turn = None
        await session.show_orb()

    async def prompt(self, note: str) -> bool:
        """Jarvis carries on by himself with something he was waiting for (v0.14.0: he signed in, so the question
        that needed it gets answered). False when no one is listening."""
        talker = self._talker()
        if talker is None or self.client is None:
            return False
        return bool(await talker.prompt(note))

    def bus_publish(self, type: str, data: dict) -> None:
        with contextlib.suppress(Exception):
            self.bus.publish(type, data)

    async def aclose(self) -> None:
        if getattr(self, "_fillers", None) is not None:
            self._fillers.cancel()
        if self._load is not None:
            self._load.cancel()
            with contextlib.suppress(BaseException):
                await self._load
        if self._parts is not None:
            with contextlib.suppress(Exception):
                await self._parts["pipeline"].stop()
            with contextlib.suppress(Exception):
                await self._parts["tts"].aclose()
