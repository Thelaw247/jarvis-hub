"""The earcon files (HUD v2 §7; F1, his v0.4.1 report): gentle, short, quiet, small, and exactly what
ui/sounds/make_sounds.py makes."""
import importlib.util
import math
import struct
import wave
from pathlib import Path

import pytest

SOUNDS = Path(__file__).resolve().parent.parent / "ui" / "sounds"
LONGEST_MS = {"tick": 60, "wake": 600, "critical": 600}
OLD_PEAK_DB = {"tick": -3.0, "wake": -1.0, "critical": -2.0}  # v0.4.1's files


def read(name):
    with wave.open(str(SOUNDS / f"{name}.wav")) as w:
        rate, n = w.getframerate(), w.getnframes()
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2)
        frames = struct.unpack(f"<{n}h", w.readframes(n))
    return rate, [v / 32767 for v in frames]


@pytest.mark.parametrize("name", ["wake", "tick", "critical"])
def test_each_sound_is_soft_short_quiet_and_small(name):
    rate, s = read(name)
    peak = max(abs(v) for v in s)
    assert len(s) / rate * 1000 <= LONGEST_MS[name]
    assert 20 * math.log10(peak) <= OLD_PEAK_DB[name] - 5.5  # about 6 dB quieter than before
    # a soft attack (≥ 15 ms): nothing near full level in the first 5 ms, and it starts and ends at silence
    assert s[0] == 0 and abs(s[-1]) < 0.002
    assert max(abs(v) for v in s[: int(rate * 0.002)]) < 0.1 * peak
    assert max(abs(v) for v in s[: int(rate * 0.005)]) < 0.5 * peak
    # round, no click and no square or saw edge: no sample jumps more than a low sine can
    assert max(abs(b - a) for a, b in zip(s, s[1:], strict=False)) < 0.3 * peak
    assert (SOUNDS / f"{name}.wav").stat().st_size < 32_000


def test_the_files_are_what_make_sounds_makes():
    spec = importlib.util.spec_from_file_location("make_sounds", SOUNDS / "make_sounds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("wake", "tick", "critical"):
        made = [max(-32767, min(32767, int(round(v * 32767)))) for v in getattr(mod, name)()]
        rate, s = read(name)
        assert rate == mod.RATE and [round(v * 32767) for v in s] == made, name
