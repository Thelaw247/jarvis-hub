"""An opt-in recording of a test conversation, for fixing what Jarvis mishears (v0.14.0).

Jarvis's logs hold ids and timings only (C21), which is right, and it means that when a conversation goes wrong
nobody can see what he heard. This is the one exception, and only when De Wet switches it on himself
("Record a test conversation.bat"), for 20 minutes at a time:

  <Jarvis>/voice/diagnose/conversation.txt   per turn: what the speech model heard, what Claude was asked, what
                                             Jarvis said, and how the turn ended
  <Jarvis>/voice/diagnose/turn-N.wav         his side of each turn (what the mic sent), so other speech models can be
                                             tried on his own voice

It stays on this laptop, is never logged, never goes in git, keeps the last 80 turns, and switches itself off.
"Record a test conversation.bat off" stops it early; deleting the folder removes everything.

    python -m jarvis.voice.diagnose on [minutes]    |    off    |    status
"""
from __future__ import annotations

import contextlib
import os
import sys
import time
import wave
from collections import deque
from pathlib import Path
from typing import Any

MINUTES = 20
KEEP_TURNS = 80
PREROLL_FRAMES = 30     # 0.6 s before the voice detector called it speech


def _root(root: Any = None) -> Path:
    return Path(root or os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")


def flag(root: Any = None) -> Path:
    return _root(root) / "voice" / "diagnose.on"


def switch(on: bool, minutes: float = MINUTES, root: Any = None) -> float:
    f = flag(root)
    if not on:
        with contextlib.suppress(OSError):
            f.unlink()
        return 0.0
    until = time.time() + minutes * 60
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(int(until)), encoding="ascii")
    return until


def until(root: Any = None) -> float:
    try:
        t = float(flag(root).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 0.0
    return t if t > time.time() else 0.0


class Diagnose:
    def __init__(self, root: Any, until_s: float) -> None:
        self.dir = _root(root) / "voice" / "diagnose"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.until = until_s
        self._pre: deque[bytes] = deque(maxlen=PREROLL_FRAMES)
        self._audio: dict[str, list[bytes]] = {}
        self._n = 0

    @classmethod
    def current(cls, root: Any, now: Diagnose | None) -> Diagnose | None:
        """The recorder to use right now: the same one while it's on, a new one when it was just switched on, None
        when it's off or its time is up."""
        t = until(root)
        if not t:
            return None
        if now is not None and abs(now.until - t) < 1.0:
            return now
        return cls(root, t)

    def _write(self, line: str) -> None:
        with contextlib.suppress(OSError), open(self.dir / "conversation.txt", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {line}\n")

    # ---- what the pipeline tells it ---------------------------------------------------------------------------
    def audio(self, turn: str | None, pcm: bytes) -> None:
        if turn is None:
            self._pre.append(pcm)
            return
        frames = self._audio.get(turn)
        if frames is None:
            frames = self._audio[turn] = list(self._pre)
            self._pre.clear()
        if len(frames) < 3000:      # a minute at most
            frames.append(pcm)

    def heard(self, turn: str, text: str) -> None:
        self._write(f"{turn}  heard: {text!r}")

    def said(self, turn: str, asked: str, reply: str) -> None:
        self._write(f"{turn}  asked Claude: {asked!r}")
        self._write(f"{turn}  Jarvis said: {reply!r}")

    def ended(self, turn: str, notes: dict, extra: dict) -> None:
        flags = {**notes, **extra}
        self._write(f"{turn}  ended: " + (", ".join(f"{k}={v}" for k, v in flags.items()) or "answered"))
        frames = self._audio.pop(turn, None)
        if frames:
            self._n += 1
            with contextlib.suppress(OSError), wave.open(str(self.dir / f"{turn}-{int(time.time())}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16_000)
                w.writeframes(b"".join(frames))
            if self._n % 10 == 0:
                self._trim()

    def _trim(self) -> None:
        with contextlib.suppress(OSError):
            wavs = sorted(self.dir.glob("turn-*.wav"), key=lambda p: p.stat().st_mtime)
            for old in wavs[:-KEEP_TURNS]:
                old.unlink()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = (args[0] if args else "status").lower()
    if cmd == "on":
        minutes = float(args[1]) if len(args) > 1 else MINUTES
        t = switch(True, minutes)
        print(f"Recording test conversations until {time.strftime('%H:%M', time.localtime(t))} "
              f"({minutes:.0f} minutes).")
        print(f"Kept on this laptop only, in {_root() / 'voice' / 'diagnose'}:")
        print("  what Jarvis heard, what he said, and your side of each turn as sound.")
        print("Now talk to Jarvis as usual. It switches itself off; run this again with 'off' to stop sooner.")
    elif cmd == "off":
        switch(False)
        print("Recording is off.")
    else:
        t = until()
        print(f"Recording until {time.strftime('%H:%M', time.localtime(t))}." if t else "Recording is off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
