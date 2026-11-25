"""Spots the core freezing and logs where (v0.12.2).

On Laptop B the core twice stopped answering for seconds while a browser opened (53 s the first time), and the
watchdog then started duplicate cores. A daemon thread pings the event loop every 0.5 s; when a ping isn't answered
within 1.5 s it captures the loop thread's stack, waits for the loop to come back, and logs `core.loop_stalled` with
how long it took and where it was stuck (file:line:function only, so C21 holds: no text, no data). Costs nothing
while the loop is healthy (one callback every half second).
"""
from __future__ import annotations

import asyncio
import sys
import threading
import time
import traceback

from .logs import EventLog

log = EventLog("jarvis.core.stall")


def where(frame) -> list[str]:
    """The innermost frames as short code locations, outermost first."""
    out = []
    for f in traceback.extract_stack(frame)[-12:]:
        path = f.filename.replace("\\", "/")
        for cut in ("/site-packages/", "/Lib/", "/Jarvis/", "/jarvis/"):
            if cut in path:
                path = path.split(cut, 1)[1]
                break
        loc = f"{path.rsplit('/', 3)[-1] if path.count('/') > 3 else path}:{f.lineno}:{f.name}"
        # "<frozen importlib._bootstrap>" and "<module>" become log-safe tokens instead of being dropped (the first
        # stall on Laptop B logged an empty list: it was all import frames)
        out.append(loc.replace("<", "").replace(">", "").replace(" ", "_").lstrip("_.-")[:80])
    return out


class StallWatch:
    def __init__(self, loop: asyncio.AbstractEventLoop, *, threshold: float = 1.5, every: float = 0.5) -> None:
        self.loop = loop
        self.threshold = threshold
        self.every = every
        self.loop_thread = threading.get_ident()  # created on the loop's thread
        self.stalls: list[tuple[float, list[str]]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="jarvis-stallwatch", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            answered = threading.Event()
            t0 = time.monotonic()
            try:
                self.loop.call_soon_threadsafe(answered.set)
            except RuntimeError:  # the loop is closed
                return
            if not answered.wait(self.threshold):
                frame = sys._current_frames().get(self.loop_thread)
                stack = where(frame) if frame is not None else []
                answered.wait(300)
                ms = (time.monotonic() - t0) * 1000
                self.stalls.append((ms, stack))
                log.warning("core.loop_stalled", ms=ms, ids=stack)
            self._stop.wait(self.every)
