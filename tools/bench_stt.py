"""Benchmark the Nemotron streaming STT exports on this laptop (Laptop B): which chunk size is fastest here?

    python tools/bench_stt.py            # every model under <Jarvis folder>\\models\\stt; results to logs\\stt-bench.txt

For each model: real-time factor (decode time / audio time; must stay well under 1), the slowest single frame, and
the final-transcript time after the speech ends (the number that adds to every answer). Uses the models' own test
recordings, so no microphone is needed.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jarvis.voice.adapters_real import SherpaNemotronStt  # noqa: E402
from jarvis.voice.frames import InputAudioRawFrame  # noqa: E402


async def bench(model: Path, wavs: list[Path], threads: int) -> str:
    stt = SherpaNemotronStt(model, num_threads=threads)
    rows = []
    for wav in wavs:
        with wave.open(str(wav)) as w:
            pcm = w.readframes(w.getnframes())
        t0, worst = time.perf_counter(), 0.0
        for i in range(0, len(pcm) - 639, 640):
            t = time.perf_counter()
            await stt.accept(InputAudioRawFrame(audio=pcm[i:i + 640]))
            worst = max(worst, (time.perf_counter() - t) * 1000)
        rtf = (time.perf_counter() - t0) / (len(pcm) / 32000)
        t = time.perf_counter()
        text = await stt.finalize()
        rows.append((rtf, worst, (time.perf_counter() - t) * 1000, text))
    rtf = sum(r[0] for r in rows) / len(rows)
    fin = sum(r[2] for r in rows) / len(rows)
    worst = max(r[1] for r in rows)
    sample = rows[0][3][:60]
    return f"{model.name[-38:]:40} RTF {rtf:4.2f}  worst frame {worst:5.0f} ms  final {fin:5.0f} ms  | {sample}"


async def main() -> int:
    root = Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")
    models = sorted(p for p in (root / "models" / "stt").iterdir() if (p / "encoder.int8.onnx").exists())
    if not models:
        print("No speech models found. Run setup-voice.bat first.")
        return 1
    wavs = sorted((models[0] / "test_wavs").glob("*.wav"))[:2]
    threads = min(4, os.cpu_count() or 2)
    lines = [f"STT benchmark, {threads} threads, {len(wavs)} recordings, {time.strftime('%Y-%m-%d %H:%M')}"]
    for m in models:
        line = await bench(m, wavs, threads)
        print(line, flush=True)
        lines.append(line)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "stt-bench.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSaved to {root / 'logs' / 'stt-bench.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
