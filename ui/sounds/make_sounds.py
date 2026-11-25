"""Make Jarvis's three earcons (HUD v2 §7): original sounds synthesised from sine waves, nothing sampled.

    python ui/sounds/make_sounds.py        writes wake.wav, tick.wav and critical.wav next to this file

Gentle by design (F1, his v0.4.1 report: the old glass tones were unpleasant): pure sines with at most a faint
second harmonic, a gentle low-pass, a raised-cosine attack of at least 15 ms (no click), a smooth decay to exact
zero, and peaks about 6 dB under the old ones.

- wake:     a soft two-note rise (D5 then A5, a fifth), 520 ms. Only the first wake of the day.
- tick:     a short, round "heard you" (A5, 55 ms) when listening turns into thinking.
- critical: one low tone (G3 with a soft octave), 600 ms, alongside a critical alert (Full only).

Mono, 16-bit, 22.05 kHz (nothing here is above 2 kHz, so the files stay small). The player (earcons.js) sets the
level (~18 dB under the voice). Standard library only, and deterministic: running it again gives the same bytes.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 22_050
HERE = Path(__file__).resolve().parent
ATTACK = 0.018   # every sound fades in over at least 15 ms: no click
LOWPASS = 1_800  # Hz: a gentle one-pole low-pass rounds off any edge
PEAKS = {"wake": -7.0, "tick": -9.0, "critical": -8.0}  # dBFS; the old files peaked at -1, -3 and -2


def silence(seconds: float) -> list[float]:
    return [0.0] * int(round(seconds * RATE))


def add(buf: list[float], start: float, samples: list[float]) -> None:
    at = int(round(start * RATE))
    for i, v in enumerate(samples):
        if at + i < len(buf):
            buf[at + i] += v


def rise(t: float, attack: float) -> float:
    """Raised-cosine fade-in: starts at exact zero with zero slope."""
    return 0.5 * (1 - math.cos(math.pi * t / attack)) if t < attack else 1.0


def tone(freq: float, seconds: float, decay: float, harmonic: float = 0.08, attack: float = ATTACK) -> list[float]:
    """A soft sine note: a slow fade-in, an exponential decay and a faint second harmonic for roundness."""
    out = []
    for i in range(int(seconds * RATE)):
        t = i / RATE
        v = math.sin(2 * math.pi * freq * t) + harmonic * math.sin(2 * math.pi * 2 * freq * t)
        out.append(rise(t, attack) * math.exp(-t / decay) * v)
    return out


def lowpass(buf: list[float], cutoff: float = LOWPASS) -> list[float]:
    a = 1 - math.exp(-2 * math.pi * cutoff / RATE)
    out, y = [], 0.0
    for v in buf:
        y += a * (v - y)
        out.append(y)
    return out


def fade_tail(buf: list[float], seconds: float) -> None:
    n = int(seconds * RATE)
    for i in range(n):
        buf[len(buf) - n + i] *= 0.5 * (1 + math.cos(math.pi * i / n))  # raised cosine to exact zero


def normalise(buf: list[float], peak_db: float) -> list[float]:
    peak = max(abs(v) for v in buf) or 1.0
    gain = 10 ** (peak_db / 20) / peak
    return [v * gain for v in buf]


def finish(name: str, buf: list[float], tail: float) -> list[float]:
    buf = lowpass(buf)
    fade_tail(buf, tail)
    return normalise(buf, PEAKS[name])


def wake() -> list[float]:
    buf = silence(0.52)
    add(buf, 0.000, tone(587.33, 0.30, 0.12, attack=0.025))   # D5
    add(buf, 0.120, tone(880.00, 0.40, 0.14, attack=0.030))   # A5, a fifth up: the rise
    return finish("wake", buf, 0.12)


def tick() -> list[float]:
    buf = silence(0.055)
    add(buf, 0.0, tone(880.0, 0.055, 0.020, harmonic=0.05, attack=0.015))  # A5, round and short
    return finish("tick", buf, 0.025)


def critical() -> list[float]:
    seconds = 0.6
    out = []
    for i in range(int(seconds * RATE)):
        t = i / RATE
        release = 1.0 if t < 0.32 else 0.5 * (1 + math.cos(math.pi * (t - 0.32) / (seconds - 0.32)))
        f = 196.0  # G3
        v = math.sin(2 * math.pi * f * t) + 0.18 * math.sin(2 * math.pi * f * 2 * t) * math.exp(-t / 0.2)
        out.append(rise(t, 0.04) * release * v)
    return finish("critical", out, 0.02)


def write(name: str, samples: list[float]) -> Path:
    path = HERE / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(round(v * 32767))))) for v in samples))
    return path


def main() -> None:
    for name, make in (("wake", wake), ("tick", tick), ("critical", critical)):
        path = write(name, make())
        with wave.open(str(path)) as w:
            print(f"{path.name}: {w.getnframes() / w.getframerate() * 1000:.0f} ms, {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
