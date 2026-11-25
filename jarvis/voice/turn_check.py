"""Conversation check (Conversation check.bat, v0.12.5): does Jarvis catch each instruction, once, and ignore noise?

    python -m jarvis.voice.turn_check            # Laptop B, the core's Python (it has the speech model)

He follows on-screen prompts for about 45 seconds in one recording: five instructions (one with a pause in the
middle), a desk tap and a cough, and some quiet. The recording goes through his mic set-up (the Hearing check's
choice), then through the core's own voice detector, Smart Turn and speech model, once per candidate:

- ``old``      : the v0.9 settings (no smoothing, a loudness gate that let everything through)
- ``baseline`` : Pipecat's default set-up for these exact parts (confidence 0.7, 0.2 s start, 0.2 s stop, gate 0.6)
- ``fitted``   : the baseline with the loudness gate set between his room and his voice
- ``guarded``  : fitted, plus the echo guard (a stricter detector while Jarvis is speaking)

Two parts play Jarvis's own voice through the speakers (his cached phrases), recorded through the same echo
canceller and mic set-up as the voice window: one where he stays quiet (anything caught is Jarvis hearing himself)
and one where he talks over Jarvis (that should be caught once).

For each: instructions caught, instructions split in two, false starts (noise or quiet taken as speech), and words
right. The best is saved to <Jarvis>/voice/turns.json, which the core uses from its next start. Numbers only are
kept; the recording is gone when the window closes (the transcripts are shown on screen, they're the test lines).
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field

from jarvis.voice import mic_profile, turn_tuning
from jarvis.voice.hearing_check import FRAME, RATE, word_errors, words

SCRIPT: list[tuple[str, str, float, str]] = [   # (kind, what to say or "", seconds, prompt)
    ("quiet", "", 3.0, "Stay quiet..."),
    ("echo", "", 6.0, "Jarvis talks now. Stay quiet and let him finish."),
    ("barge", "Stop that's enough", 6.0, "Jarvis talks again. Talk over him and say:  Stop, that's enough."),
    ("say", "What's due this week", 5.0, "Say:  What's due this week?"),
    ("say", "Open my chemistry lab manual", 5.0, "Say:  Open my chemistry lab manual."),
    ("say", "Remind me to start the physics assignment tonight", 8.0,
     "Say, with a one-second pause at the dots:  Remind me to ... start the physics assignment tonight."),
    ("noise", "", 5.0, "Don't talk: tap your desk twice, then cough once."),
    ("say", "When is my next lecture", 5.0, "Say:  When is my next lecture?"),
    ("say", "Research the best budgeting apps for students", 6.0,
     "Say:  Research the best budgeting apps for students."),
    ("quiet", "", 3.0, "Stay quiet..."),
]


@dataclass
class Turn:
    start_s: float
    end_s: float | None = None
    text: str = ""


@dataclass
class Score:
    name: str
    settings: turn_tuning.TurnSettings
    caught: int = 0
    split: int = 0
    missed: int = 0
    false: int = 0
    echo: int = 0                 # false starts while Jarvis was talking and he wasn't (Jarvis hearing himself)
    errors: int = 0
    lines: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:  # what a person would feel: a missed or false turn is worse than a wrong word
        return self.errors + 4 * self.missed + 3 * self.false + 2 * self.split


def slots() -> list[tuple[str, str, float, float]]:
    out, t = [], 0.0
    for kind, line, secs, _ in SCRIPT:
        out.append((kind, line, t, t + secs))
        t += secs
    return out


async def run_turns(np, audio, settings, stt, speaking: list[tuple[float, float]] | None = None) -> list[Turn]:
    """The core's own processors over the recording: what turns they'd make, with their final transcripts."""
    import asyncio

    from jarvis.voice.adapters_real import SileroVad, SmartTurnV3
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.frames import (
        InputAudioRawFrame,
        TranscriptionFrame,
        UserStoppedSpeakingFrame,
        VADUserStartedSpeakingFrame,
    )
    from jarvis.voice.pipeline import SttProcessor, TurnProcessor, VadProcessor
    from jarvis.voice.processor import FrameProcessor
    from jarvis.voice.session import VoiceSession

    session = VoiceSession(VoiceConfig(voice_id="check", vad_stop_ms=settings.vad_stop_ms))
    now = {"s": 0.0}
    turns: dict[str, Turn] = {}

    class Capture(FrameProcessor):
        async def process_frame(self, frame):
            if isinstance(frame, VADUserStartedSpeakingFrame) and frame.turn_id not in turns:
                turns[frame.turn_id] = Turn(now["s"])
            elif isinstance(frame, UserStoppedSpeakingFrame) and frame.turn_id in turns:
                turns[frame.turn_id].end_s = now["s"]
            elif isinstance(frame, TranscriptionFrame) and frame.turn_id in turns:
                turns[frame.turn_id].text = frame.text
                session.responding = None   # nothing answers here: the next turn is a fresh one

    vad = VadProcessor(session, SileroVad.from_settings(settings))
    turn = TurnProcessor(session, SmartTurnV3(), incomplete_timeout_ms=settings.incomplete_ms)
    stt_p = SttProcessor(session, stt)
    vad.link(turn)
    turn.link(stt_p)
    stt_p.link(Capture(session))
    for i in range(0, len(audio) - FRAME + 1, FRAME):
        now["s"] = i / RATE
        session.bot_speaking = any(a <= now["s"] < b for a, b in speaking or [])  # Jarvis's voice was playing
        await vad.process_frame(InputAudioRawFrame(audio=audio[i:i + FRAME].tobytes()))
    session.bot_speaking = False
    silence = np.zeros(FRAME, dtype=np.int16).tobytes()
    for _ in range(int(2.0 * RATE / FRAME)):          # let the last turn close
        now["s"] += FRAME / RATE
        await vad.process_frame(InputAudioRawFrame(audio=silence))
    await asyncio.sleep(0.5)
    for _ in range(100):                              # finals are finishing in the background
        if not any(t.end_s is not None and not t.text for t in turns.values()) or not stt_p._finalizing \
                or stt_p._finalizing.done():
            break
        await asyncio.sleep(0.05)
    return list(turns.values())


def score(name, settings, turns: list[Turn]) -> Score:
    sc = Score(name, settings)
    plan = slots()
    used: set[int] = set()
    for kind, line, start, end in plan:
        # a turn belongs to the prompt it started in (it may end after the prompt's slot; that's fine)
        mine = [k for k, t in enumerate(turns) if k not in used and start - 0.3 <= t.start_s < end - 0.3]
        if kind in ("say", "barge"):
            spoken = [k for k in mine if words(turns[k].text)]
            used.update(mine)
            heard = " ".join(turns[k].text for k in spoken)
            sc.errors += word_errors(line, heard)
            sc.false += len(mine) - len(spoken)          # empty turns inside an instruction's slot
            if not spoken:
                sc.missed += 1
            else:
                sc.caught += 1
                sc.split += len(spoken) - 1
            sc.lines.append(f"{line!r} -> {heard or '(nothing)'}" + (f"  [{len(spoken)} turns]" if len(spoken) > 1
                                                                       else ""))
        else:
            sc.false += len(mine)
            if kind == "echo":
                sc.echo += len(mine)
            used.update(mine)
    sc.false += len([k for k in range(len(turns)) if k not in used])
    return sc


def jarvis_voice(np, root) -> object | None:
    """A few seconds of Jarvis's real voice: his cached phrases (24 kHz), or None if none are cached yet."""
    folder = root / "data" / "voice" / "phrases"
    clips = [np.fromfile(f, dtype=np.int16) for f in sorted(folder.glob("*.pcm"))] if folder.exists() else []
    if not clips:
        return None
    gap = np.zeros(int(0.15 * 24000), dtype=np.int16)
    out = np.concatenate([x for c in clips for x in (c, gap)])
    while len(out) < 5 * 24000:
        out = np.concatenate([out, out])
    return out[: int(5 * 24000)]


async def record(np, device, profile, voice) -> tuple[object, list[tuple[float, float]]]:
    """Exactly what the voice window would send the core: the mic through the echo canceller (with what the
    speaker plays as its reference) and the mic profile. Jarvis's voice plays in the echo and barge parts."""
    import asyncio

    from jarvis.voice.audio_io import EchoCanceller, Mic, Speaker

    aec = None
    if EchoCanceller.available():
        aec = EchoCanceller(24_000, **profile["aec"])
    speaker = Speaker(24_000, None, aec=aec)
    mic = Mic(asyncio.get_running_loop(), device, aec=aec, boost=profile["boost"] or aec is None)
    frames: list[bytes] = []
    speaking: list[tuple[float, float]] = []

    async def collect():
        while True:
            frames.append(await mic.frames.get())

    async def play(start_s: float):
        chunk = int(0.1 * 24000)
        for i in range(0, len(voice), chunk):
            await speaker.write(voice[i:i + chunk].tobytes())
            await asyncio.sleep(0.095)
        speaking.append((start_s, start_s + len(voice) / 24000 + 0.25))

    task = asyncio.create_task(collect())
    t0, until = time.monotonic(), 0.0
    try:
        for kind, _line, secs, prompt in SCRIPT:
            print(f"\n  {prompt}", flush=True)
            if kind in ("echo", "barge"):
                await asyncio.sleep(0.5)
                await play(len(frames) * FRAME / RATE)
            until += secs
            while time.monotonic() - t0 < until:
                await asyncio.sleep(0.05)
    finally:
        task.cancel()
        mic.close()
        speaker.close()
    return np.frombuffer(b"".join(frames), dtype=np.int16), speaking


def volumes(np, audio) -> tuple[float, float]:
    """Pipecat's own loudness measure (BS.1770, 0-1) for his room and his voice."""
    from pipecat.audio.utils import calculate_audio_volume

    win = int(0.4 * RATE)
    room, voice = [], []
    for kind, _line, start, end in slots():
        seg = audio[int(start * RATE): int(end * RATE)]
        vals = [calculate_audio_volume(seg[i:i + win].tobytes(), RATE) for i in range(0, len(seg) - win + 1, win // 2)]
        (room if kind == "quiet" else voice if kind == "say" else []).extend(vals)
    return float(np.median(room)) if room else 0.5, float(np.percentile(voice, 75)) if voice else 0.8


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.turn_check")
    parser.add_argument("--mic", type=int, help="microphone number (python -m jarvis.voice.talk --devices)")
    args = parser.parse_args(argv)

    import asyncio

    import numpy as np

    from jarvis.voice.adapters_real import SherpaNemotronStt
    from jarvis.voice.talk import stt_dir

    root = mic_profile.root()
    models = stt_dir(root)
    if not (models / "encoder.int8.onnx").exists():
        print(f"The speech model isn't here ({models}). Run setup-voice.bat first.")
        return 1
    print("Conversation check: does Jarvis catch each instruction once, and ignore noise?")
    print("Close the Talk to Jarvis window first. Sit where you usually sit and talk normally.\n")
    print("Loading the speech model...", flush=True)
    stt = SherpaNemotronStt(models, num_threads=4)
    cal = mic_profile.load()
    profile = mic_profile.PROFILES[cal["profile"]]
    voice = jarvis_voice(np, root)
    if voice is None:  # no cached phrases yet: skip the parts with Jarvis's voice rather than fake them
        SCRIPT[:] = [x for x in SCRIPT if x[0] not in ("echo", "barge")]
        print("(Jarvis hasn't cached any phrases yet, so the parts with his voice are skipped.)")
    total = sum(x[2] for x in SCRIPT)
    input(f"When you press Enter, follow the prompts as they appear (about {total:.0f} seconds). ")
    loop = asyncio.new_event_loop()
    audio, speaking = loop.run_until_complete(record(np, args.mic, profile, voice))
    audio = audio[: int(total * RATE)]
    print("\nGot it. Trying each setting (a minute or so)...", flush=True)

    room, voice_level = volumes(np, audio)
    fitted = turn_tuning.fitted(room, voice_level)
    candidates = [("old", turn_tuning.OLD), ("baseline", turn_tuning.BASELINE), ("fitted", fitted),
                  ("guarded", turn_tuning.guarded(fitted))]
    results = []
    for name, settings in candidates:
        turns = loop.run_until_complete(run_turns(np, audio, settings, stt, speaking))
        sc = score(name, settings, turns)
        results.append(sc)
        print(f"\n  {name} ({settings.label()})")
        print(f"     caught {sc.caught}/{sum(1 for k, *_ in SCRIPT if k in ('say', 'barge'))}, split {sc.split}, "
              f"missed {sc.missed}, false starts {sc.false} (hearing himself {sc.echo}), word errors {sc.errors}")
        for line in sc.lines:
            print(f"     {line}")
    loop.close()
    order = {"baseline": 0, "fitted": 1, "guarded": 2, "old": 3}
    best = min(results, key=lambda s: (s.total, order[s.name]))
    saved = turn_tuning.save(best.settings, best.name)
    print(f"\nYour room {room:.2f}, your voice {voice_level:.2f} on Pipecat's loudness scale.")
    print(f"Best: {best.name}. Saved to {saved}. Restart the core (restart-core.bat) to use it.")
    with (root / "logs").joinpath("conversation-check.txt").open("a", encoding="utf-8") as log:  # numbers only
        log.write(f"{time.strftime('%Y-%m-%d %H:%M')} room={room:.2f} voice={voice_level:.2f} " + " ".join(
            f"{s.name}:caught={s.caught},split={s.split},missed={s.missed},false={s.false},echo={s.echo},"
            f"errors={s.errors}"
            for s in results) + f" chose={best.name}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
