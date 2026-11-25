"""Talk to Jarvis on Laptop B: the real voice loop with this laptop's own mic and speakers (M0.2 / M0.4 first run).

    python -m jarvis.voice.talk                 # half-duplex: the mic is muted while Jarvis speaks (no echo loop)
    python -m jarvis.voice.talk --barge-in      # with headphones: talk over Jarvis to stop him
    python -m jarvis.voice.talk --devices       # list microphones and speakers
    python -m jarvis.voice.talk --check         # load everything, say one line, exit (no mic)

Same pipeline as the design (VAD -> Smart Turn v3 -> Nemotron STT -> T0 router -> Haiku -> ElevenLabs), with
the keys read from Windows Credential Manager the way the core reads them (never printed) and the voice ID from
the hub (Controls > Keys > Voice, kept in <Jarvis folder>/data/settings.json). Prints what it heard, what it
answered and each turn's latency, and writes every turn to <Jarvis folder>/logs/voice-latency.jsonl.

The laptop has no echo cancellation, so by default the mic is ignored while Jarvis speaks and for a moment
after. The real setup takes the mic on Laptop A (thin client with echo cancellation, push-to-talk, wake word).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ECHO_TAIL_S = 0.25

STT_DIR_NAME = "sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25"

from jarvis.voice.audio_io import IN_BYTES, IN_RATE, Mic, MicBoost, Speaker  # noqa: E402,F401


def stt_dir(root: Path) -> Path:
    return root / "models" / "stt" / STT_DIR_NAME


class Printer:
    """Stands in for the hub's event bus: prints what Jarvis heard and said."""

    async def publish(self, type: str, data: Any) -> None:
        if type == "caption.show" and data.get("text"):
            print(f"  Jarvis: {data['text']}", flush=True)


class HeardStt:
    """The real STT, printing what it heard at the end of each turn."""

    def __init__(self, stt: Any) -> None:
        self.stt = stt

    async def accept(self, frame: Any) -> str:
        return await self.stt.accept(frame)

    async def finalize(self) -> str:
        text = await self.stt.finalize()
        if text:
            print(f"  You: {text}", flush=True)
        return text


class Commands:
    async def run(self, command: Any) -> None:
        print(f"  [command] {command.name} {dict(command.args)}", flush=True)


class NoApprovals:
    def pending(self) -> None:
        return None


def keyed_clients(root: Path) -> tuple[Any, Any]:
    """The live Claude and ElevenLabs keys, as the core holds them (Credential Manager), wrapped in K1's clients."""
    from jarvis.secrets import KeyManager, KeyringBackend, MetaFile, default_registry  # noqa: PLC0415

    mgr = KeyManager(KeyringBackend(), default_registry(), MetaFile(root / "data" / "keys.json"))
    mgr.load()
    return mgr.client("anthropic"), mgr.client("elevenlabs")


def build(root: Path, *, out_device: Any = None, model: str | None = None) -> dict[str, Any]:
    from jarvis.core.settings import CoreSettings  # noqa: PLC0415
    from jarvis.health.latency import LatencyRecorder  # noqa: PLC0415
    from jarvis.voice import turn_tuning  # noqa: PLC0415
    from jarvis.voice.adapters_real import SherpaNemotronStt, SileroVad, SmartTurnV3  # noqa: PLC0415
    from jarvis.voice.config import VoiceConfig  # noqa: PLC0415
    from jarvis.voice.pipeline import build_pipeline  # noqa: PLC0415
    from jarvis.voice.router_t0 import RouterT0  # noqa: PLC0415
    from jarvis.voice.session import VoiceSession  # noqa: PLC0415
    from jarvis.voice.talker_t1 import TalkerT1  # noqa: PLC0415
    from jarvis.voice.tts_elevenlabs import ElevenLabsTTS  # noqa: PLC0415

    voice_id = CoreSettings(root / "data" / "settings.json").voice_id()
    if not voice_id:
        raise SystemExit("No voice yet: paste your ElevenLabs voice ID in the hub (Controls > Keys > Voice).")
    models = stt_dir(root)
    if not (models / "encoder.int8.onnx").exists():
        raise SystemExit(f"The speech model isn't downloaded yet: run setup-voice.bat ({models}).")
    config = VoiceConfig.from_mapping({"core_root": str(root), "voice_id": voice_id, **({"tts_model": model} if model else {})})
    print(f"Voice model: {config.tts_model}.", flush=True)
    anthropic, elevenlabs = keyed_clients(root)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    recorder = LatencyRecorder(sink=root / "logs" / "voice-latency.jsonl")
    session = VoiceSession(config, recorder=recorder, events=Printer())
    t = time.perf_counter()
    stt = HeardStt(SherpaNemotronStt(models, num_threads=min(4, os.cpu_count() or 2)))
    print(f"Speech model loaded in {time.perf_counter() - t:.1f} s.", flush=True)
    tts = ElevenLabsTTS(config, elevenlabs)
    speaker = Speaker(config.tts_sample_rate, out_device)
    router = RouterT0(now=datetime.now, clock=session.clock, approvals=NoApprovals(),
                      approval_window_s=config.approval_window_s)
    talker = TalkerT1(config, anthropic, now_card=now_card)
    pipeline = build_pipeline(session, vad=SileroVad.from_settings(turn_tuning.load(root)), turn=SmartTurnV3(), stt=stt, router=router, talker=talker,
                              tts=tts, audio_out=speaker, commands=Commands())
    return {"session": session, "pipeline": pipeline, "tts": tts, "speaker": speaker, "recorder": recorder}


def now_card() -> str:
    """The date and time for the persona's "Now" block (not cached: it changes every turn)."""
    now = datetime.now()
    hour = now.strftime("%I").lstrip("0")
    return f"# Now\n{now:%A %d %B %Y}, {hour}:{now:%M} {now:%p}".replace(" 0", " ", 1) + ", Saskatoon."


def show_latency(trace: Any) -> None:
    ms = trace.ms
    parts = [f"{k} {v:.0f}" for k, v in sorted(ms.items(), key=lambda kv: kv[1])]
    first = ms.get("audio_out") or ms.get("tts_first_byte")
    head = f"first sound {first:.0f} ms after you stopped" if first is not None else "no sound"
    print(f"  [{trace.kind}] {head}  ({', '.join(parts)} ms)", flush=True)


async def run(args: argparse.Namespace) -> int:
    from jarvis.core.config import Config  # noqa: PLC0415
    from jarvis.voice.frames import InputAudioRawFrame  # noqa: PLC0415

    root = Config.from_env().root
    parts = build(root, out_device=args.speaker, model="eleven_flash_v2_5" if args.flash else None)
    session, pipeline, tts, speaker = parts["session"], parts["pipeline"], parts["tts"], parts["speaker"]
    await tts.start()  # warm socket before the first turn
    if args.check:
        pcm = await tts.synthesize("Jarvis online. The voice is working.")
        for i in range(0, len(pcm), 960):
            await speaker.write(pcm[i:i + 960])
        await speaker.drain()
        print("Check passed: keys, voice ID, speech model and speaker all work.")
        await tts.aclose()
        speaker.close()
        return 0

    mic = Mic(asyncio.get_running_loop(), args.mic)
    silence = bytes(IN_BYTES)
    seen = 0
    print("\nListening. Talk to Jarvis (Ctrl+C to stop)."
          + ("" if args.barge_in else " The mic is ignored while he speaks; use --barge-in with headphones."), flush=True)
    try:
        while True:
            frame = await mic.frames.get()
            if not args.barge_in and (session.bot_speaking or time.monotonic() - speaker.last_write < ECHO_TAIL_S):
                frame = silence  # half-duplex: he can't hear himself
            await pipeline.queue_frame(InputAudioRawFrame(audio=frame))
            traces = session.recorder.traces
            for trace in traces[seen:]:
                show_latency(trace)
            seen = len(traces)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        mic.close()
        with contextlib.suppress(Exception):
            await pipeline.stop()
        with contextlib.suppress(Exception):
            await tts.aclose()
        speaker.close()
        firsts = sorted(t.ms["audio_out"] for t in session.recorder.traces if "audio_out" in t.ms)
        if firsts:
            print(f"{len(firsts)} answers. First sound after you stopped talking: median {firsts[len(firsts) // 2]:.0f} ms, "
                  f"worst {firsts[-1]:.0f} ms. Every turn is in logs\\voice-latency.jsonl.", flush=True)
    return 0


async def mic_test(args: argparse.Namespace, seconds: float = 10.0) -> int:
    """Show the mic level and whether the voice detector hears speech, for a few seconds."""
    import math  # noqa: PLC0415

    from jarvis.voice import turn_tuning  # noqa: PLC0415
    from jarvis.voice.adapters_real import SileroVad  # noqa: PLC0415
    from jarvis.voice.frames import InputAudioRawFrame  # noqa: PLC0415

    vad = SileroVad.from_settings(turn_tuning.load())
    mic = Mic(asyncio.get_running_loop(), args.mic)
    print(f"Mic test for {seconds:.0f} s: talk normally, then stay quiet. # = level, SPEECH = the detector hears you.")
    end, n, speech_db = time.monotonic() + seconds, 0, []
    try:
        while time.monotonic() < end:
            pcm = await mic.frames.get()   # already boosted (MicBoost)
            speech = await vad.is_speech(InputAudioRawFrame(audio=pcm))
            samples = memoryview(pcm).cast("h")
            rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))
            db = 20 * math.log10(max(rms, 1.0) / 32768.0)
            if speech:
                speech_db.append(db)
            n += 1
            if n % 5 == 0:  # every 100 ms
                bar = "#" * max(0, int((db + 70) / 2))
                print(f"{db:6.1f} dB {'SPEECH' if speech else '      '} {bar}   boost x{mic.boost.gain:.1f}", flush=True)
    finally:
        mic.close()
    if not speech_db:
        print("It didn't hear any speech. Check the mic isn't muted and is the Windows default input.")
        return 0
    typical = sorted(speech_db)[len(speech_db) // 2]
    hint = ("Still quiet: move a little closer or raise the mic level in Windows Sound settings."
            if typical < -35 else "Your voice level looks good.")
    print(f"Your speech (after the boost): about {typical:.0f} dB. {hint}")
    return 0


def setup_logging() -> None:
    from jarvis.voice.audio_io import setup_console_logging  # noqa: PLC0415

    setup_console_logging()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.talk", description="Talk to Jarvis on this laptop")
    parser.add_argument("--barge-in", action="store_true", help="keep listening while Jarvis speaks (headphones)")
    parser.add_argument("--devices", action="store_true", help="list microphones and speakers, then exit")
    parser.add_argument("--mic", type=int, help="microphone number from --devices (default: Windows default)")
    parser.add_argument("--speaker", type=int, help="speaker number from --devices (default: Windows default)")
    parser.add_argument("--check", action="store_true", help="load everything and say one line, then exit")
    parser.add_argument("--flash", action="store_true", help="use Flash v2.5 (plainer, the old voice model)")
    parser.add_argument("--mic-test", action="store_true", help="show the mic level and what the voice detector hears")
    args = parser.parse_args(argv)
    setup_logging()
    if args.mic_test:
        return asyncio.run(mic_test(args))
    if args.devices:
        import sounddevice as sd  # noqa: PLC0415

        print(sd.query_devices())
        return 0
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
