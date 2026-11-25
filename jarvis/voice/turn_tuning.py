"""How Jarvis decides he's talking (v0.12.5): the voice detector's settings, with Pipecat's defaults as the baseline.

The v0.9 settings were hand-tuned for a quiet laptop mic: start_secs 0 and stop_secs 0 (no smoothing at all), a
confidence of 0.5 and a loudness gate of 0.15 (about -95 LUFS, so it let everything through). Every stray 32 ms
window over the line started a turn and every tiny pause ended one: he went in and out of listening, a tap made him
duck, and noise turns came back empty (his first sessions on Laptop B: 6 of 11 turns empty). The Hearing check then
showed his mic is fine (voice about -20 dBFS, 30 dB over the room, 21 of 22 words right).

So the baseline is the configuration Pipecat ships for these exact parts (Silero VAD + Smart Turn v3): confidence 0.7,
0.2 s of speech to start, 0.2 s of silence before Smart Turn is asked, a loudness gate of 0.6. Conversation check.bat
replays one recording of him through the old settings, this baseline and a version fitted to his levels, and keeps
whichever catches the most instructions with the fewest false starts. Saved in <Jarvis>/voice/turns.json.
"""
from __future__ import annotations

import contextlib
import json
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from jarvis.voice import mic_profile


@dataclass(frozen=True)
class TurnSettings:
    confidence: float = 0.7      # Silero's speech probability needed (Pipecat default)
    min_volume: float = 0.6      # BS.1770 loudness gate, 0 = -110 LUFS .. 1 = -10 LUFS (Pipecat default)
    start_s: float = 0.2         # speech needed before a turn starts (Pipecat default)
    stop_s: float = 0.2          # silence before Smart Turn decides (Pipecat's recommendation with Smart Turn)
    vad_stop_ms: float = 0.0     # extra silence on top of stop_s (the analyzer already waited)
    incomplete_ms: float = 1500.0  # Smart Turn says "not finished": wait at most this for more speech
    echo_guard: bool = False     # while Jarvis speaks, ask more of the detector (his own echo isn't De Wet)

    @property
    def echo_confidence(self) -> float:
        return max(self.confidence, 0.85)

    @property
    def echo_min_volume(self) -> float:
        return min(0.9, self.min_volume + 0.1)

    def label(self) -> str:
        return (f"confidence {self.confidence:g}, loudness gate {self.min_volume:g}, start {self.start_s:g} s, "
                f"stop {self.stop_s:g} s" + (", echo guard" if self.echo_guard else ""))


BASELINE = TurnSettings()
OLD = TurnSettings(confidence=0.5, min_volume=0.15, start_s=0.0, stop_s=0.0, vad_stop_ms=200.0)
# Until he runs the Conversation check: the baseline plus the echo guard. In the sandbox (real speech clips, Jarvis's
# echo left at about -44 dBFS after the canceller) the old settings heard Jarvis as him 4 times in 6 s of talking,
# the baseline 3, the guard 0, and his "stop" over Jarvis was still caught every time.
DEFAULT = TurnSettings(echo_guard=True)


def path(base: Path | None = None) -> Path:
    return (base or mic_profile.root()) / "voice" / "turns.json"


def load(base: Path | None = None) -> TurnSettings:
    """The saved check's settings, or the default. Never raises; nonsense values fall back field by field."""
    out = DEFAULT
    with contextlib.suppress(Exception):
        saved = json.loads(path(base).read_text(encoding="utf-8"))
        fields = {}
        for k, lo, hi in (("confidence", 0.3, 0.95), ("min_volume", 0.0, 0.9), ("start_s", 0.0, 0.6),
                          ("stop_s", 0.0, 1.0), ("vad_stop_ms", 0.0, 800.0), ("incomplete_ms", 500.0, 4000.0)):
            v = saved.get(k)
            if isinstance(v, int | float) and not isinstance(v, bool) and lo <= v <= hi:
                fields[k] = float(v)
        if isinstance(saved.get("echo_guard"), bool):
            fields["echo_guard"] = saved["echo_guard"]
        out = replace(DEFAULT, **fields) if fields else DEFAULT
    return out


def save(settings: TurnSettings, name: str, base: Path | None = None) -> Path:
    p = path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({**asdict(settings), "chosen": name, "checked": time.strftime("%Y-%m-%d %H:%M")},
                            indent=2), encoding="utf-8")
    return p


def fitted(room_volume: float, voice_volume: float) -> TurnSettings:
    """The baseline with the loudness gate between his room and his voice (a third of the way up from the room),
    kept within 0.45-0.75 so it never opens to everything or shuts out a soft word."""
    gate = room_volume + (voice_volume - room_volume) / 3.0
    return replace(BASELINE, min_volume=round(min(0.75, max(0.45, gate)), 2))


def guarded(settings: TurnSettings) -> TurnSettings:
    return replace(settings, echo_guard=True)
