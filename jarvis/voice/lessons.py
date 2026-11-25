"""Teach Jarvis your voice (Teach Jarvis your voice.bat, v0.14.0): what the speech model gets wrong for him, measured
on his own voice, and a note of it for Jarvis.

    python -m jarvis.voice.lessons               # read the sentences (about 4 minutes), then score
    python -m jarvis.voice.lessons --score       # score the recordings again (after a change), no reading

1. He reads 24 things he would really say to Jarvis (classes, Canvas, the calendar, short answers). For each: press
   Enter, say it, press Enter.
2. Each one goes through the same clean-up, voice detector and speech model the core uses. It shows what was heard.
3. The words it got wrong are lined up with the words he said, and the pairs that came out wrong are saved to
   <Jarvis>/voice/vocabulary.json. Jarvis reads that note with every question ("when you hear X he most likely
   said Y"), so he can work out what was meant.
4. The recordings stay in <Jarvis>/voice/lessons (on this laptop only, never in git, never logged): they are his
   voice saying our test sentences, and they are what other speech models get tried on to find the one that hears
   him best. Delete the folder to remove them.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

from jarvis.voice import mic_profile
from jarvis.voice.hearing_check import FRAME, RATE, hear, process, word_errors, words

SENTENCES = [
    "What's my first class tomorrow",
    "Check what I have due this week on Canvas",
    "Add a study block for chemistry after my lab on Thursday",
    "Open the lecture slides for GE one twenty two",
    "When is my next physics assignment due",
    "Remind me to do laundry tonight at eight",
    "What room is my math tutorial in",
    "Read me the latest announcement from my chemistry professor",
    "Move my study session to Saturday morning",
    "How much is the midterm worth",
    "Search the web for the weather in Saskatoon tomorrow",
    "Start a study plan for thermodynamics",
    "Show me my calendar for Friday",
    "Is anything new on Canvas",
    "Make flashcards for lecture twelve",
    "Sign me in to Crowdmark",
    "Did my professor post the lab report marks",
    "What do I have between two and five this afternoon",
    "Yes go ahead",
    "No never mind",
    "Stop",
    "Thanks that's all",
    "What time is it",
    "Hey Jarvis are you there",
]
MAX_S = 12.0
MAX_PAIRS = 40


def align(ref: list[str], hyp: list[str]) -> list[tuple[str, str]]:
    """Word-level alignment: (said, heard) pairs; "" on one side for a dropped or extra word."""
    n, m = len(ref), len(hyp)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        cost[i][0] = i
    for j in range(m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(cost[i - 1][j] + 1, cost[i][j - 1] + 1, cost[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    out: list[tuple[str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and cost[i][j] == cost[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            out.append((ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            out.append((ref[i - 1], ""))
            i -= 1
        else:
            out.append(("", hyp[j - 1]))
            j -= 1
    return out[::-1]


def misheard(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The (said, heard) phrases that came out wrong, with neighbouring wrong words joined into one phrase."""
    out: list[tuple[str, str]] = []
    said: list[str] = []
    heard: list[str] = []
    for a, b in [*pairs, ("=", "=")]:
        if a != b:
            said += [a] if a else []
            heard += [b] if b else []
            continue
        if said and heard:      # a substitution (something said came out as something else)
            out.append((" ".join(said), " ".join(heard)))
        said, heard = [], []
    return out


def vocabulary_note(root: Path | None = None) -> str:
    """What Jarvis is told about his speech-to-text, from the last lesson ("" when there hasn't been one)."""
    try:
        data = json.loads(((root or mic_profile.root()) / "voice" / "vocabulary.json").read_text(encoding="utf-8"))
        pairs = [(str(a), str(b)) for a, b in data.get("misheard", []) if a and b][:MAX_PAIRS]
    except (OSError, ValueError, TypeError):
        return ""
    if not pairs:
        return ""
    lines = "\n".join(f'- heard "{b}" → he most likely said "{a}"' for a, b in pairs)
    return ("Habits of the speech-to-text on his voice (measured on his own test recordings). When the words you get "
            "look like the left side, read them as the right side if that makes more sense:\n" + lines)


def record_until_enter(sd, np, device, prompt: str):
    chunks: list = []

    def got(data, _frames, _time, _status) -> None:
        chunks.append(bytes(data))

    input(prompt)
    with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME, device=device, callback=got):
        t0 = time.monotonic()
        print("     Listening... say it, then press Enter.", end="", flush=True)
        input()
        if time.monotonic() - t0 > MAX_S:
            chunks[:] = chunks[: int(MAX_S * RATE / FRAME)]
        time.sleep(0.25)
    return np.frombuffer(b"".join(chunks), dtype=np.int16)


def save_wav(path: Path, x) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(x.tobytes())


def load_wav(np, path: Path):
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def score(np, folder: Path, items: list[dict], stt, vad_factory) -> dict:
    cal = mic_profile.load()
    profile = mic_profile.PROFILES[cal["profile"]]
    loop = asyncio.new_event_loop()
    total = wrong = 0
    pairs: list[tuple[str, str]] = []
    rows = []
    for item in items:
        raw = load_wav(np, folder / item["file"])
        x = process(np, np.concatenate([np.zeros(RATE // 2, dtype=np.int16), raw]), profile)
        if x is None:
            x = raw
        text, _ = loop.run_until_complete(hear(np, stt, vad_factory(), x))
        errors = word_errors(item["text"], text)
        total += len(words(item["text"]))
        wrong += errors
        pairs += misheard(align(words(item["text"]), words(text)))
        rows.append({"file": item["file"], "errors": errors, "words": len(words(item["text"]))})
        mark = "ok " if errors == 0 else f"{errors} off"
        print(f"  [{mark}] said:  {item['text']}\n         heard: {text or '(nothing)'}", flush=True)
    loop.close()
    return {"total": total, "wrong": wrong, "pairs": pairs, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.lessons")
    parser.add_argument("--mic", type=int, help="microphone number (python -m jarvis.voice.talk --devices)")
    parser.add_argument("--score", action="store_true", help="score the saved recordings again, no reading")
    args = parser.parse_args(argv)

    import numpy as np

    from jarvis.voice import turn_tuning
    from jarvis.voice.adapters_real import SherpaNemotronStt, SileroVad
    from jarvis.voice.talk import stt_dir

    root = mic_profile.root()
    folder = root / "voice" / "lessons"
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / "lessons.json"
    models = stt_dir(root)
    if not (models / "encoder.int8.onnx").exists():
        print(f"The speech model isn't here ({models}). Run setup-voice.bat first.")
        return 1

    if not args.score:
        import sounddevice as sd

        print("Teach Jarvis your voice. Close the Talk to Jarvis window first, so the mic is free.")
        print(f"{len(SENTENCES)} short things to say, the way you'd really say them (fast is fine). About 4 minutes.")
        print(f"The recordings stay on this laptop, in {folder}.\n")
        items = []
        for n, sentence in enumerate(SENTENCES, 1):
            x = record_until_enter(sd, np, args.mic, f"\n  {n}/{len(SENTENCES)}  \"{sentence}\"\n     Press Enter to start. ")
            name = f"{n:02d}.wav"
            save_wav(folder / name, x)
            items.append({"file": name, "text": sentence})
        index.write_text(json.dumps(items, indent=1), encoding="utf-8")
    elif not index.exists():
        print("No recordings yet: run this without --score first.")
        return 1
    items = json.loads(index.read_text(encoding="utf-8"))

    print("\nLoading the speech model...", flush=True)
    stt = SherpaNemotronStt(models, num_threads=4)
    print("What Jarvis hears:\n")
    got = score(np, folder, items, stt, lambda: SileroVad.from_settings(turn_tuning.load()))
    right = got["total"] - got["wrong"]
    pct = round(100 * right / max(1, got["total"]))
    counts: dict[tuple[str, str], int] = {}
    for pair in got["pairs"]:
        counts[pair] = counts.get(pair, 0) + 1
    ranked = sorted(counts, key=lambda p: (-counts[p], p))[:MAX_PAIRS]
    (root / "voice" / "vocabulary.json").write_text(json.dumps(
        {"checked": time.strftime("%Y-%m-%d"), "words_right": right, "words": got["total"],
         "misheard": [list(p) for p in ranked]}, indent=1), encoding="utf-8")
    print(f"\n{right} of {got['total']} words right ({pct}%).")
    if ranked:
        print("Jarvis now knows these habits of his hearing (he said → it heard):")
        for a, b in ranked[:12]:
            print(f"   {a}  →  {b}")
    else:
        print("Nothing to correct: every sentence came out right.")
    print("\nSaved. Run restart-core.bat so Jarvis picks it up.")
    with (root / "logs").joinpath("hearing-check.txt").open("a", encoding="utf-8") as log:  # numbers only
        log.write(f"{time.strftime('%Y-%m-%d %H:%M')} lessons words_right={right}/{got['total']} "
                  f"pairs={len(ranked)}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
