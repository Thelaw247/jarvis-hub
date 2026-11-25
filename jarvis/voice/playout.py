"""What the speaker plays next, with soft edges (v0.14.0).

Before, Jarvis's audio was written straight to the sound card: his voice started and stopped on whatever sample
came first or last (a tick at each end, a hard click when he was interrupted or the audio ran dry for a moment),
"quieter" was a jump to 30%, and between replies the output fell silent, so the laptop's amplifier switched off and
audibly back on with the next word.

Playout sits between the socket and the sound card's callback:
- his voice fades in over ~12 ms and out over ~30 ms: at the start, at the end, when it's stopped, and around any
  gap (the audio running dry fades instead of clicking);
- being talked over lowers him smoothly (~40 ms) instead of jumping;
- while the window is open the output never goes fully silent: a noise far below hearing (about -84 dBFS) keeps
  the amplifier awake, so there is no switch-on sound. JARVIS_KEEP_AWAKE=0 turns that off;
- it knows how loud what it is playing right now is (``level``), which is what the orb's glow follows while
  Jarvis speaks.

Pure numpy and thread-safe (feed from the event loop, pull from the audio callback); tested without a sound card.
"""
from __future__ import annotations

import math
import os
import threading
from collections import deque
from typing import Any

FADE_IN_MS = 12.0
FADE_OUT_MS = 30.0
STOP_MS = 15.0
DUCK_MS = 40.0
DUCKED = 0.3
KEEP_AWAKE_AMPLITUDE = 2          # +-2 of 32768: about -84 dBFS, far below hearing
QUIET_DB, LOUD_DB = -52.0, -16.0  # the meter's range for Jarvis's own voice (same as the core's)


class Playout:
    def __init__(self, rate: int = 24_000, *, keep_awake: bool | None = None) -> None:
        import numpy as np  # noqa: PLC0415

        self._np = np
        self.rate = rate
        self._lock = threading.Lock()
        self._chunks: deque[Any] = deque()
        self._queued = 0                 # samples waiting
        self._gain = 0.0                 # the edge gain now (0 = silent, 1 = full)
        self._duck = 1.0
        self._duck_to = 1.0
        self._stopping = False
        self._up = 1.0 / max(1.0, rate * FADE_IN_MS / 1000.0)
        self._down = 1.0 / max(1.0, rate * FADE_OUT_MS / 1000.0)
        self._stop_step = 1.0 / max(1.0, rate * STOP_MS / 1000.0)
        self._duck_step = (1.0 - DUCKED) / max(1.0, rate * DUCK_MS / 1000.0)
        self._tail = int(rate * FADE_OUT_MS / 1000.0)
        if keep_awake is None:
            keep_awake = os.environ.get("JARVIS_KEEP_AWAKE", "1").strip() not in ("0", "off", "no")
        self.keep_awake = keep_awake
        self._rng = np.random.default_rng(7)
        self.level = 0.0                 # 0-1: how loud what is playing right now is
        self.active = False              # the last block pulled had some of his voice in it
        self.underruns = 0               # times the audio ran dry in the middle of speech

    # ------------------------------------------------------------------ the event loop's side
    def feed(self, pcm: bytes) -> None:
        """More of his voice (16-bit mono at ``rate``)."""
        np = self._np
        x = np.frombuffer(pcm, dtype=np.int16)
        if not x.size:
            return
        with self._lock:
            if self._stopping:           # new speech right after a stop: the old audio is gone, this is fresh
                self._chunks.clear()
                self._queued = 0
                self._stopping = False
            self._chunks.append(x)
            self._queued += x.size

    def stop(self) -> None:
        """He talked over Jarvis: fade out fast, then drop what was still to come."""
        with self._lock:
            if self._queued:
                self._stopping = True
            self._duck_to = 1.0

    def duck(self, on: bool) -> None:
        with self._lock:
            self._duck_to = DUCKED if on else 1.0

    @property
    def buffered_s(self) -> float:
        return self._queued / self.rate

    # ------------------------------------------------------------------ the audio callback's side
    def pull(self, n: int) -> Any:
        """The next ``n`` samples for the sound card (int16). Never blocks, never raises."""
        np = self._np
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            take = min(n, self._queued)
            self.active = take > 0
            got = 0
            while got < take:
                head = self._chunks[0]
                k = min(head.size, take - got)
                out[got:got + k] = head[:k]
                if k == head.size:
                    self._chunks.popleft()
                else:
                    self._chunks[0] = head[k:]
                got += k
            self._queued -= take
            left = self._queued
            stopping = self._stopping
            duck_to = self._duck_to
        if take:
            # fade out as the audio runs out (or on a stop), fade in when it starts or comes back
            idx = np.arange(1, take + 1, dtype=np.float32)
            if stopping:
                g = np.maximum(0.0, self._gain - self._stop_step * idx)
            else:
                remaining = left + take - idx                  # samples still to play after each of these
                ceiling = np.minimum(1.0, remaining / max(1, self._tail))
                g = np.minimum(ceiling, self._gain + self._up * idx)
            if self._duck != duck_to:
                step = self._duck_step * idx
                d = np.maximum(duck_to, self._duck - step) if duck_to < self._duck else np.minimum(duck_to, self._duck + step)
                self._duck = float(d[-1])
            else:
                d = self._duck
            out[:take] *= g * d
            self._gain = float(g[-1])
            if stopping and self._gain <= 0.0:
                with self._lock:
                    if self._stopping:
                        self._chunks.clear()
                        self._queued = 0
                        self._stopping = False
            if take < n and not stopping and self._gain > 0.05:
                self.underruns += 1     # ran dry mid-word: the fade above was cut short
            if take < n:
                self._gain = 0.0
            rms = float(np.sqrt(np.mean(out[:take] * out[:take]))) / 32768.0
            db = 20.0 * math.log10(rms) if rms > 0 else -120.0
            self.level = min(1.0, max(0.0, (db - QUIET_DB) / (LOUD_DB - QUIET_DB)))
        else:
            self._gain = 0.0
            self._duck = duck_to
            self.level = 0.0
        if self.keep_awake:
            out += self._rng.integers(-KEEP_AWAKE_AMPLITUDE, KEEP_AWAKE_AMPLITUDE + 1, n)
        return np.clip(out, -32768, 32767).astype(np.int16)
