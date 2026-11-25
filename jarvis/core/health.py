"""Component health for `/healthz` (RUNTIME §8: heartbeats per component, each problem reported once).

Each component registers a check that returns `(status, info)`; status is `ok`, `starting`, `degraded` or `down`.
The overall light is **green** (all ok), **amber** (something starting or degraded) or **red** (something down).
A component's status change is logged once, when it changes, never on every poll.
"""
from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .logs import EventLog

Check = Callable[[], tuple[str, dict] | Awaitable[tuple[str, dict]]]
STATUSES = ("ok", "starting", "degraded", "down")
CHECK_TIMEOUT_S = 0.5
log = EventLog("jarvis.core.health")


class Health:
    def __init__(self, version: str) -> None:
        self.version = version
        self.started = time.monotonic()
        self._checks: dict[str, Check] = {}
        self._last: dict[str, str] = {}

    def register(self, name: str, check: Check) -> None:
        self._checks[name] = check

    async def _one(self, name: str, check: Check) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            out = check()
            if inspect.isawaitable(out):
                out = await asyncio.wait_for(out, CHECK_TIMEOUT_S)
            status, info = out
            status = status if status in STATUSES else "down"
        except Exception:  # noqa: BLE001 - a failing check means the component is down
            status, info = "down", {"code": "check_failed"}
        if self._last.get(name) != status:
            (log.info if status == "ok" else log.warning)("health.changed", component=name, status=status)
            self._last[name] = status
        return {"status": status, **info, "ms": round((time.perf_counter() - t0) * 1000, 2)}

    async def report(self) -> dict[str, Any]:
        """Run every check (concurrently, each capped at 0.5 s). T1 (a few ms)."""
        names = list(self._checks)
        results = await asyncio.gather(*(self._one(n, self._checks[n]) for n in names))
        components = dict(zip(names, results, strict=True))
        statuses = {c["status"] for c in components.values()}
        light = "red" if "down" in statuses else "amber" if statuses - {"ok"} else "green"
        return {"ok": light != "red", "status": light, "version": self.version,
                "uptime_ms": round((time.monotonic() - self.started) * 1000), "components": components}
