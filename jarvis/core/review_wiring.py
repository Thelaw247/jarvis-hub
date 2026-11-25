"""Review recording, wired into the core (jarvis/review): every log line in full, every event on the bus, every
button, the machine's load and what Jarvis was running on. All of it only while he has review recording switched
on; off, each hook is one comparison."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import sys
import time
import traceback
from typing import Any

from jarvis import review
from jarvis.health.memory import memory

HANDLER_NAME = "jarvis-review"
STANDARD = frozenset(logging.LogRecord("x", 0, "x", 0, "", None, None).__dict__) | {"message", "asctime", "taskName"}
FAST = ("orb.state",)      # sent many times a second while the glow follows the room: thinned to changes + 4 a second
LOAD_EVERY_S = 10.0
PROBE_S = 0.5


class ReviewHandler(logging.Handler):
    """Every log record, unfiltered: its fields as given and the whole traceback (the ordinary log keeps only the
    error's class name, which is why a failure could be seen but not explained)."""

    def emit(self, record: logging.LogRecord) -> None:
        if not review.on() or record.name.startswith("jarvis.review"):
            return
        try:
            fields = {k: v for k, v in record.__dict__.items() if k not in STANDARD and k != "jv"}
            fields.update(getattr(record, "jv", None) or {})
            # the error being handled when this line was logged, even where the code logged only its name
            exc = record.exc_info if record.exc_info and record.exc_info[0] else sys.exc_info()
            trace = "".join(traceback.format_exception(*exc)) if exc and exc[0] is not None else None
            review.note("log", logger=record.name, level=record.levelname.lower(), event=record.getMessage(),
                        fields=fields, trace=trace)
        except Exception:  # noqa: BLE001 - a logging handler must never raise
            pass


def cpu_times() -> tuple[float, float] | None:
    """(busy, total) seconds for the whole machine so far, or None."""
    try:
        if sys.platform == "win32":
            import ctypes  # noqa: PLC0415

            class FT(ctypes.Structure):
                _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]

            idle, kernel, user = FT(), FT(), FT()
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):  # type: ignore[attr-defined]
                return None
            def sec(t: FT) -> float:
                return ((t.hi << 32) | t.lo) / 1e7
            total = sec(kernel) + sec(user)          # kernel time includes idle time
            return total - sec(idle), total
        with open("/proc/stat", encoding="ascii") as f:
            parts = [float(x) for x in f.readline().split()[1:]]
        return sum(parts) - parts[3] - parts[4], sum(parts)
    except Exception:  # noqa: BLE001
        return None


def environment(config: Any, app: Any) -> dict:
    """What Jarvis is running on and how it is set, once per start. No keys: only which ones are set."""
    def version(name: str) -> str | None:
        with contextlib.suppress(Exception):
            from importlib.metadata import version as v  # noqa: PLC0415

            return v(name)
        return None

    voice = getattr(app.state, "voice", None)
    settings = {}
    with contextlib.suppress(Exception):
        settings = dict(app.state.core.state.state.get("settings") or {})
    return {
        "version": config.version, "python": sys.version.split()[0], "platform": platform.platform(),
        "machine": platform.node(), "cpu": platform.processor(), "cores": os.cpu_count(), "memory": memory(),
        "root": str(config.root), "pid": os.getpid(),
        "packages": {n: version(n) for n in ("anthropic", "fastapi", "uvicorn", "websockets", "httpx", "numpy",
                                             "onnxruntime", "sherpa-onnx", "elevenlabs", "sounddevice")},
        "voice": {"status": getattr(voice, "status", None), "reason": getattr(voice, "reason", None),
                  "brain": getattr(voice, "brain", None)},
        "settings": settings,
    }


def detail(on: bool) -> None:
    """While recording, Jarvis's own debug lines are kept too (in the review only: the ordinary log stays as it is)."""
    for h in logging.getLogger().handlers:
        if h.get_name() != HANDLER_NAME and h.level < logging.INFO:
            h.setLevel(logging.INFO)
    logging.getLogger("jarvis").setLevel(logging.DEBUG if on else logging.NOTSET)


def wire(app: Any, core: Any, config: Any) -> None:
    review.use(config.root)
    root = logging.getLogger()
    for old in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(old)
    handler = ReviewHandler(level=logging.DEBUG)
    handler.set_name(HANDLER_NAME)
    root.addHandler(handler)
    detail(review.on())

    def tap(event: Any) -> None:
        if not review.on():
            return
        if event.type in FAST:
            review.sampled("bus", f"{event.type}:{event.data.get('state')}", 0.25, type=event.type, data=event.data)
        else:
            review.note("bus", type=event.type, data=event.data)

    core.bus.taps.append(tap)
    app.state.review_environment = lambda: environment(config, app)


async def watch_load(app: Any) -> None:
    """Every 10 s while recording: memory, how busy the machine and this process are, and how late the event loop
    ran (a late loop is heard as broken-up speech). Also says what Jarvis is running on, each time recording starts."""
    was_on = False
    last_cpu, last_proc, last_wall = cpu_times(), time.process_time(), time.perf_counter()
    while True:
        worst, waited = 0.0, 0.0
        while waited < LOAD_EVERY_S:
            t0 = time.perf_counter()
            await asyncio.sleep(PROBE_S)
            worst = max(worst, time.perf_counter() - t0 - PROBE_S)
            waited += PROBE_S
        now_on = review.on()
        if now_on != was_on:
            detail(now_on)
        if now_on and not was_on:
            with contextlib.suppress(Exception):
                review.note("env", **app.state.review_environment())
        was_on = now_on
        cpu, proc, wall = cpu_times(), time.process_time(), time.perf_counter()
        if now_on:
            machine = None
            if cpu and last_cpu and cpu[1] > last_cpu[1]:
                machine = round(100 * (cpu[0] - last_cpu[0]) / (cpu[1] - last_cpu[1]), 1)
            voice = getattr(app.state, "voice", None)
            review.note("load", memory=memory(), machine_cpu_pct=machine,
                        core_cpu_pct=round(100 * (proc - last_proc) / max(1e-6, wall - last_wall), 1),
                        loop_late_ms=round(worst * 1000, 1), tasks=len(asyncio.all_tasks()),
                        voice_client=getattr(voice, "client_name", "") or None)
        last_cpu, last_proc, last_wall = cpu, proc, wall
