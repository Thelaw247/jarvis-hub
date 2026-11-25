"""Review recording: everything about every interaction, kept for a review, when De Wet has switched it on.

He asked for this on 2026-11-19: "map all the data from every interaction ... absolutely everything ... then you
can review it all on Sunday". Jarvis's ordinary logs hold ids and timings only (C21), which is why a bad
conversation leaves nothing to study. While review recording is on, and only then, this keeps the lot:

  <Jarvis>/logs/review/<date>/events.jsonl    one line per thing that happened, in order (see KINDS below)
  <Jarvis>/logs/review/<date>/audio/*.wav     his side of each turn, exactly as the speech model got it

What a line can hold: what the speech model heard, what Claude was sent and what it answered (text and tool calls),
every tool's input and result, every event the hub was sent, every button he pressed, every log line with its full
error, every request's timing, the voice window's own notes (wake-word scores, sound running dry), and the
machine's load. What it never holds: keys, passwords, session tokens or sign-in cookies (redacted by name and by
shape), and no sound from before he woke Jarvis (C23 stands: asleep, only numbers leave the voice window).

It stays on this laptop, never goes in git, and switches itself off at the time written in the flag file.
    python -m jarvis.review on [days]   |   off   |   status
Deleting <Jarvis>/logs/review removes everything.

Cost on a turn: note() puts one object on a queue (about a microsecond); a writer thread does the disk work, so the
voice loop never waits on a file. Off, note() is one comparison.
"""
from __future__ import annotations

import atexit
import contextlib
import itertools
import json
import os
import queue
import re
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Any

DAYS = 4.0
MAX_TEXT = 60_000            # one string: a whole tool result fits, a runaway page doesn't
MAX_AUDIO_BYTES = 3_000_000_000   # sound stops being kept past this; the events go on
PREROLL_FRAMES = 30          # 0.6 s before the voice detector called it speech
CHECK_S = 2.0
KINDS = ("review", "env", "load", "log", "bus", "http", "act", "voice.session", "voice.client", "voice.sent", "client.note",
         "turn.heard", "turn.said", "turn.ended", "turn.timing", "llm.request", "llm.response", "llm.error",
         "tool", "task")

SECRET_NAME = re.compile(r"(api[_-]?key|apikey|authorization|passw|secret|cookie|bearer|credential|x-jarvis-session|"
                         r"(access|refresh|id|session)[_-]?token)", re.IGNORECASE)
SECRET_SHAPE = re.compile(r"(\b(?:sk|ck|ak|pk|xi|lk|rk)[-_][A-Za-z0-9_\-]{16,}|Bearer\s+[A-Za-z0-9._\-]{12,}|"
                          r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,})")
REDACTED = "[redacted]"


def scrub(value: Any, depth: int = 0) -> Any:
    """Anything -> something JSON can hold, with secrets taken out by name and by shape. T0 for small values."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, str):
        text = value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + f"[…{len(value) - MAX_TEXT} more characters]"
        return SECRET_SHAPE.sub(REDACTED, text)
    if isinstance(value, bytes | bytearray | memoryview):
        return f"[{len(value)} bytes]"
    if depth > 8:
        return "[…]"
    if isinstance(value, dict):
        return {str(k): (REDACTED if SECRET_NAME.search(str(k)) else scrub(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset | deque):
        return [scrub(v, depth + 1) for v in itertools.islice(value, 400)]
    for dump in ("model_dump", "to_dict"):           # the Anthropic SDK's objects
        if callable(getattr(value, dump, None)):
            with contextlib.suppress(Exception):
                return scrub(getattr(value, dump)(), depth + 1)
    if hasattr(value, "__dict__") and depth < 4:
        return scrub({k: v for k, v in vars(value).items() if not k.startswith("_")}, depth + 1)
    return scrub(repr(value)[:500], depth + 1)


def root_dir(root: Any = None) -> Path:
    return Path(root or os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")


def flag(root: Any = None) -> Path:
    return root_dir(root) / "logs" / "review" / "review.on"


def until(root: Any = None) -> float:
    try:
        t = float(flag(root).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 0.0
    return t if t > time.time() else 0.0


def switch(on: bool, days: float = DAYS, root: Any = None) -> float:
    f = flag(root)
    if not on:
        with contextlib.suppress(OSError):
            f.unlink()
        return 0.0
    t = time.time() + days * 86400
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(int(t)), encoding="ascii")
    return t


class Recorder:
    def __init__(self, root: Any = None) -> None:
        self.root = root_dir(root)
        self.dir = self.root / "logs" / "review"
        self._checked, self._until = -1e9, 0.0
        self._q: queue.SimpleQueue = queue.SimpleQueue()
        self._wake = threading.Event()
        self._writing = threading.Lock()      # one writer at a time, so lines land in the order they happened
        self._seq = itertools.count(1)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._quiet: dict[str, tuple[float, int]] = {}
        self._audio_bytes: int | None = None
        self._was_on = False
        self.written = 0

    # ---- on or off ------------------------------------------------------------------------------------------
    def on(self) -> bool:
        now = time.monotonic()
        if now - self._checked > CHECK_S:
            self._checked = now
            self._until = until(self.root)
        on = self._until > time.time()
        if on != self._was_on:
            self._was_on = on
            if on:
                self._put("review", {"what": "on", "until": time.strftime("%Y-%m-%d %H:%M", time.localtime(self._until))})
        return on

    # ---- writing ----------------------------------------------------------------------------------------------
    def note(self, kind: str, /, **data: Any) -> None:
        """One thing that happened. Never raises, never waits on a disk. T0."""
        with contextlib.suppress(Exception):
            if self.on():
                self._put(kind, data)

    def sampled(self, kind: str, key: str, every_s: float, /, **data: Any) -> None:
        """For things that repeat many times a second: at most one line per `every_s`, with how many were left out."""
        with contextlib.suppress(Exception):
            if not self.on():
                return
            now = time.monotonic()
            last, skipped = self._quiet.get(key, (-1e9, 0))
            if now - last < every_s:
                self._quiet[key] = (last, skipped + 1)
                return
            self._quiet[key] = (now, 0)
            self._put(kind, {**data, **({"left_out": skipped} if skipped else {})})

    def _put(self, kind: str, data: dict) -> None:
        self._q.put((time.time(), time.perf_counter(), kind, data))
        self._wake.set()
        if self._thread is None:
            with self._lock:
                if self._thread is None:
                    self._thread = threading.Thread(target=self._drain, name="jarvis-review", daemon=True)
                    self._thread.start()
                    atexit.register(self.flush)

    def _line(self, wall: float, mono: float, kind: str, data: dict) -> tuple[str, str]:
        day = time.strftime("%Y-%m-%d", time.localtime(wall))
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(wall)) + f".{int(wall % 1 * 1000):03d}"
        try:
            body = {(f"{k}_" if k in ("t", "mono", "n", "k") else k): v for k, v in scrub(data).items()}
            text = json.dumps({"t": stamp, "mono": round(mono, 4), "n": next(self._seq), "k": kind, **body},
                              ensure_ascii=False, separators=(",", ":"), default=str)
        except Exception as exc:  # noqa: BLE001 - one odd value must not lose the line, or stop the recorder
            text = json.dumps({"t": stamp, "k": kind, "unwritable": type(exc).__name__})
        return day, text

    def _write(self, items: list) -> None:
        by_day: dict[str, list[str]] = {}
        for wall, mono, kind, data in items:
            day, text = self._line(wall, mono, kind, data)
            by_day.setdefault(day, []).append(text)
        for day, lines in by_day.items():
            with contextlib.suppress(OSError):
                folder = self.dir / day
                folder.mkdir(parents=True, exist_ok=True)
                with open(folder / "events.jsonl", "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                self.written += len(lines)

    def _drain(self) -> None:
        while True:
            self._wake.wait()
            time.sleep(0.2)                       # gather what else arrives: one file write for a burst
            self._wake.clear()
            self.flush()

    def flush(self) -> None:
        """Write what is waiting, now (the writer thread, tests, and the core stopping)."""
        with self._writing:
            items = []
            with contextlib.suppress(queue.Empty):
                while len(items) < 5000:
                    items.append(self._q.get_nowait())
            if items:
                self._write(items)

    # ---- sound --------------------------------------------------------------------------------------------------
    def save_audio(self, turn: str, frames: list[bytes], rate: int = 16_000) -> str | None:
        """His side of one turn as a .wav. Returns the file's name, or None once the sound budget is used up."""
        if not frames or not self.on():
            return None
        if self._audio_bytes is None:
            self._audio_bytes = sum(p.stat().st_size for p in self.dir.glob("*/audio/*.wav")) if self.dir.is_dir() else 0
        if self._audio_bytes > MAX_AUDIO_BYTES:
            return None
        now = time.time()
        folder = self.dir / time.strftime("%Y-%m-%d", time.localtime(now)) / "audio"
        name = f"{time.strftime('%H%M%S', time.localtime(now))}-{re.sub(r'[^A-Za-z0-9_.-]', '_', turn)[:40]}.wav"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            data = b"".join(frames)
            with wave.open(str(folder / name), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(data)
            self._audio_bytes += len(data)
        except OSError:
            return None
        return name


class TurnTap:
    """What the voice loop hands a recorder (the same four calls as voice/diagnose.py): the sound of his turn, what
    was heard, what was asked and said, and how it ended."""

    def __init__(self, rec: Recorder) -> None:
        self.rec = rec
        self._pre: deque[bytes] = deque(maxlen=PREROLL_FRAMES)
        self._audio: dict[str, list[bytes]] = {}

    def audio(self, turn: str | None, pcm: bytes) -> None:
        if turn is None:
            self._pre.append(pcm)
            return
        frames = self._audio.get(turn)
        if frames is None:
            frames = self._audio[turn] = list(self._pre)
            self._pre.clear()
        if len(frames) < 6000:      # two minutes at most
            frames.append(pcm)

    def heard(self, turn: str, text: str) -> None:
        self.rec.note("turn.heard", turn=turn, text=text)

    def said(self, turn: str, asked: str, reply: str) -> None:
        self.rec.note("turn.said", turn=turn, asked=asked, reply=reply)

    def ended(self, turn: str, notes: dict, extra: dict) -> None:
        frames = self._audio.pop(turn, None)
        wav = self.rec.save_audio(turn, frames) if frames else None
        seconds = round(sum(len(f) for f in frames) / 32_000, 2) if frames else 0.0
        self.rec.note("turn.ended", turn=turn, notes=notes, extra=extra, wav=wav, heard_s=seconds)
        for stale in list(self._audio)[:-4]:      # turns that never ended: don't hold their sound for ever
            self._audio.pop(stale, None)


# ---- the one recorder this process uses ---------------------------------------------------------------------
_rec = Recorder()


def use(root: Any) -> Recorder:
    """Point the recorder at this Jarvis folder (the core does this once at start; tests use their own)."""
    global _rec
    if _rec.root != root_dir(root):
        _rec.flush()
        _rec = Recorder(root)
    return _rec


def recorder() -> Recorder:
    return _rec


def on() -> bool:
    return _rec.on()


def note(kind: str, /, **data: Any) -> None:
    _rec.note(kind, **data)


def sampled(kind: str, key: str, every_s: float, /, **data: Any) -> None:
    _rec.sampled(kind, key, every_s, **data)


def tap(root: Any, now: Any) -> Any:
    """The voice loop's recorder right now: this one while review recording is on (it keeps everything the 20-minute
    test recording does, and more), else the test recording if he switched that on, else None."""
    rec = _rec if _rec.root == root_dir(root) else use(root)
    if rec.on():
        return now if isinstance(now, TurnTap) and now.rec is rec else TurnTap(rec)
    from jarvis.voice.diagnose import Diagnose  # noqa: PLC0415

    return Diagnose.current(root, now if isinstance(now, Diagnose) else None)
