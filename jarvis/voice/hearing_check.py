"""Hearing check (Hearing check.bat, v0.12.3): how well Jarvis hears him on this laptop's mic, and the best mic set-up.

    python -m jarvis.voice.hearing_check            # Laptop B, the core's Python (it has the speech model)
    python -m jarvis.voice.hearing_check --mic 3    # a particular mic

1. Three seconds of quiet: the room's noise level.
2. He reads three short sentences.
3. Every mic profile (mic_profile.py) is run over the same recording, exactly as the voice window would, then through
   the same voice detector and speech model the core uses. For each: how much of his speech the detector caught, how
   loud his voice ends up, and how many words came out right.
4. The profile with the most words right wins (ties keep the simpler one) and is saved to <Jarvis>/voice/mic.json
   with the levels, which also scale the orb's glow to his voice.

Nothing is saved but numbers: the recording stays in memory and is gone when the window closes. The transcripts are
shown on screen only (they're the test sentences). Close the core's Talk to Jarvis window first, so the mic is free.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from types import SimpleNamespace

from jarvis.voice import mic_profile

RATE = 16_000
FRAME = 320                     # 20 ms
SENTENCES = [
    "When is my next chemistry lab due",
    "Open my lecture notes for engineering design",
    "Remind me to start the physics assignment tonight",
]
QUIET_S, READ_S = 3.0, 6.0


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def word_errors(ref: str, hyp: str) -> int:
    """Word-level edit distance (substitutions + deletions + insertions)."""
    r, h = words(ref), words(hyp)
    row = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, row[0] = row[0], i
        for j, hw in enumerate(h, 1):
            cur = min(row[j] + 1, row[j - 1] + 1, prev + (rw != hw))
            prev, row[j] = row[j], cur
    return row[-1]


def frame_db(np, x) -> list[float]:
    out = []
    for i in range(0, len(x) - FRAME + 1, FRAME):
        f = x[i:i + FRAME].astype(np.float32)
        rms = float(np.sqrt(np.mean(f * f))) / 32768.0
        out.append(20 * np.log10(rms) if rms > 0 else -120.0)
    return out


def process(np, raw, profile: dict):
    """The voice window's clean-up, offline: echo canceller (+ gain / suppression), then the boost if the profile
    has it. The whole recording goes through one processor, so the gain has settled by the sentences."""
    from jarvis.voice.audio_io import MicBoost

    out = raw
    try:
        import pywebrtc_audio
        ap = pywebrtc_audio.AudioProcessor(sample_rate=RATE, echo_cancellation=True, high_pass_filter=True,
                                           **profile["aec"])
        far = np.zeros(160, dtype=np.int16)
        out = np.concatenate([np.asarray(ap.process(raw[i:i + 160].copy(), far), dtype=np.int16)
                              for i in range(0, len(raw) - 159, 160)])
    except ImportError:
        if profile["aec"]:
            return None
    if profile["boost"]:
        boost = MicBoost()
        out = np.concatenate([np.frombuffer(boost(out[i:i + FRAME].tobytes()), dtype=np.int16)
                              for i in range(0, len(out) - FRAME + 1, FRAME)])
    return out


async def hear(np, stt, vad, x) -> tuple[str, float]:
    """The core's detector and speech model on one sentence: (transcript, seconds of speech detected)."""
    speech_frames = 0
    for i in range(0, len(x) - FRAME + 1, FRAME):
        frame = SimpleNamespace(audio=x[i:i + FRAME].tobytes())
        if await vad.is_speech(frame):
            speech_frames += 1
        await stt.accept(frame)
    return await stt.finalize(), speech_frames * FRAME / RATE


def record(sd, np, seconds: float, device):
    rec = sd.rec(int(seconds * RATE), samplerate=RATE, channels=1, dtype="int16", device=device)
    sd.wait()
    return np.asarray(rec[:, 0], dtype=np.int16)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.hearing_check")
    parser.add_argument("--mic", type=int, help="microphone number (python -m jarvis.voice.talk --devices)")
    args = parser.parse_args(argv)

    import numpy as np
    import sounddevice as sd

    from jarvis.voice import turn_tuning
    from jarvis.voice.adapters_real import SherpaNemotronStt, SileroVad
    from jarvis.voice.talk import stt_dir

    root = mic_profile.root()
    models = stt_dir(root)
    if not (models / "encoder.int8.onnx").exists():
        print(f"The speech model isn't here ({models}). Run setup-voice.bat first.")
        return 1
    print("Hearing check: how well Jarvis hears you on this mic. Close the Talk to Jarvis window first.\n")
    print("Loading the speech model...", flush=True)
    stt = SherpaNemotronStt(models, num_threads=4)

    input("Step 1 of 2: stay quiet for 3 seconds. Press Enter, then don't talk. ")
    quiet = record(sd, np, QUIET_S, args.mic)
    takes = []
    print("\nStep 2 of 2: read each sentence in your normal voice, from where you usually sit.")
    for n, sentence in enumerate(SENTENCES, 1):
        input(f"\n  {n}. \"{sentence}\"\n     Press Enter, then read it (you have {READ_S:.0f} seconds). ")
        takes.append(record(sd, np, READ_S, args.mic))
        print("     Got it.", flush=True)

    raw = np.concatenate([quiet, *takes])
    raw_floor = float(np.percentile(frame_db(np, quiet), 20))
    raw_speech = float(np.percentile(np.concatenate([frame_db(np, t) for t in takes]), 90))
    total_words = sum(len(words(s)) for s in SENTENCES)
    print(f"\nYour mic as it comes in: room {raw_floor:.0f} dBFS, your voice {raw_speech:.0f} dBFS "
          f"({raw_speech - raw_floor:.0f} dB above the room).\n\nTrying each mic set-up...", flush=True)

    results = []
    loop = asyncio.new_event_loop()  # one loop for every run: the speech model's lock belongs to it
    for name, profile in mic_profile.PROFILES.items():
        out = process(np, raw, profile)
        if out is None:
            print(f"  {name}: not available on this laptop")
            continue
        q, rest = out[:len(quiet)], out[len(quiet):]
        parts = np.array_split(rest, len(takes))
        vad = SileroVad.from_settings(turn_tuning.load())
        errors, heard_s, lines = 0, 0.0, []
        for sentence, part in zip(SENTENCES, parts, strict=True):
            text, speech_s = loop.run_until_complete(hear(np, stt, vad, part))
            errors += word_errors(sentence, text)
            heard_s += speech_s
            lines.append(text or "(nothing)")
        floor = float(np.percentile(frame_db(np, q), 20))
        speech = float(np.percentile(np.concatenate([frame_db(np, p) for p in parts]), 90))
        results.append((errors, list(mic_profile.PROFILES).index(name), name, floor, speech, heard_s, lines))
        print(f"\n  {name}: {total_words - errors}/{total_words} words right, voice {speech:.0f} dBFS, room "
              f"{floor:.0f} dBFS, speech detected {heard_s:.1f} s")
        for line in lines:
            print(f"     heard: {line}")

    loop.close()
    if not results:
        print("No mic set-up could run here.")
        return 1
    best = min(results)
    _, _, name, floor, speech, _, _ = best
    saved = mic_profile.save(name, floor, speech)
    print(f"\nBest: {name} ({total_words - best[0]}/{total_words} words). Saved to {saved}.")
    if raw_speech < -45:
        print("Your mic is quiet. Windows can help: Settings > System > Sound > your microphone > Input volume, "
              "set it to 80-100%, then run this check again.")
    if best[0] > total_words // 4:
        print("He still misses a lot of words. Try sitting closer, a quieter room, or a headset mic, then run "
              "the check again.")
    print("Restart the Talk to Jarvis window to use it.")
    with (root / "logs").joinpath("hearing-check.txt").open("a", encoding="utf-8") as log:  # numbers only
        log.write(f"{time.strftime('%Y-%m-%d %H:%M')} raw_floor={raw_floor:.1f} raw_speech={raw_speech:.1f} "
                  + " ".join(f"{r[2]}:errors={r[0]}/{total_words},speech_s={r[5]:.1f},voice={r[4]:.1f},"
                             f"room={r[3]:.1f}" for r in results) + f" chose={name}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
