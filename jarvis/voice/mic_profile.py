"""How the voice window cleans up the mic (v0.12.3): which profile, and how loud his voice and the room are.

Hearing check.bat measures his real mic and writes ``<Jarvis folder>/voice/mic.json``; the voice window reads it at
start. Numbers only: no audio is ever kept.

Profiles (all keep WebRTC's echo canceller, so Jarvis's own voice is removed first):
- ``boost``  : the v0.9 mic boost (speech toward -22 dBFS, at most 18 dB). The default until he runs the check.
- ``agc``    : WebRTC AGC2 (the adaptive gain in Chrome and Meet), up to 30 dB, no boost.
- ``agc_ns`` : AGC2 plus light noise suppression (level 1, about 12 dB). Suppression can cost words on clean
  speech (Deepgram: preprocessing hurt accuracy in a 2025 study), so it only wins if his words say so.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path

PROFILES: dict[str, dict] = {
    "boost": {"aec": {}, "boost": True},
    "agc": {"aec": {"auto_gain_control": True, "agc_max_gain_db": 30.0}, "boost": False},
    "agc_ns": {"aec": {"auto_gain_control": True, "noise_suppression": True, "ns_level": 1, "agc_max_gain_db": 30.0},
               "boost": False},
}
DEFAULT = "boost"


def root() -> Path:
    return Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")


def path(base: Path | None = None) -> Path:
    return (base or root()) / "voice" / "mic.json"


def load(base: Path | None = None) -> dict:
    """The saved check, or the defaults. Never raises."""
    out = {"profile": DEFAULT, "floor_db": None, "speech_db": None, "checked": None}
    with contextlib.suppress(Exception):
        saved = json.loads(path(base).read_text(encoding="utf-8"))
        if saved.get("profile") in PROFILES:
            out.update({k: saved.get(k) for k in out})
    return out


def save(profile: str, floor_db: float, speech_db: float, base: Path | None = None) -> Path:
    p = path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"profile": profile, "floor_db": round(floor_db, 1), "speech_db": round(speech_db, 1),
                             "checked": time.strftime("%Y-%m-%d %H:%M")}, indent=2), encoding="utf-8")
    return p


def glow(cal: dict) -> dict | None:
    """The glow's range for the core: silence at the room's noise + 6 dB, full at his normal voice + 3 dB."""
    floor, speech = cal.get("floor_db"), cal.get("speech_db")
    if floor is None or speech is None or speech - floor < 10:
        return None
    return {"quiet_db": round(floor + 6.0, 1), "loud_db": round(speech + 3.0, 1)}
