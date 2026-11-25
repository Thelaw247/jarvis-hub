"""Wiring the API keys (`jarvis.secrets`, work package K1) into the core app.

At start: `KeyManager(backend, default_registry(), MetaFile(<root>/data/keys.json), emit=...)`, `.load()` (keys
are read once into memory), `/api/keys` mounted with a verifier that knows his paired devices (`sessions.py`;
the phone is view-only), and `mgr.watchdog()` running as a task.

`JARVIS_CORE_KEYSTORE`: `keyring` (default: Windows Credential Manager, his account, C26) or `memory` (tests and
sandboxes only: keys live in RAM and are gone at restart). If `jarvis.secrets` isn't merged yet, this does
nothing and /healthz has no `keys` component.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI

from .bus import CORE_EVENTS, HUB_EVENTS, EventBus
from .config import Config
from .logs import EventLog
from .sessions import HubSessions

log = EventLog("jarvis.core.keys")
AVAILABLE = importlib.util.find_spec("jarvis.secrets") is not None


@dataclass
class Keys:
    manager: Any = None  # jarvis.secrets.KeyManager, once the store could be opened
    sessions: HubSessions | None = None
    status: str = "starting"
    code: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)

    def check(self) -> tuple[str, dict]:
        info: dict = {"devices_n": self.sessions.count if self.sessions else 0}
        if self.code:
            info["code"] = self.code
        return self.status, info


def _emit(bus: EventBus):
    """K1's events go on the bus when the bus knows their type. `keys.updated` waits for the contract (see report)."""
    def emit(kind: str, data: dict) -> None:
        if kind in HUB_EVENTS or kind in CORE_EVENTS:
            bus.publish(kind, data)
        else:
            log.debug("keys.event_skipped", kind=kind)
    return emit


def mount(app: FastAPI, config: Config, bus: EventBus, backend: Any = None) -> Keys | None:
    """Mount /api/keys if jarvis.secrets is present. The store is opened in `start` (lifespan), not here."""
    if not AVAILABLE:
        return None
    from jarvis.secrets import (  # noqa: PLC0415 - optional until K1 is merged
        KeyManager,
        MemoryBackend,
        MetaFile,
        Session,
        StoreUnavailable,
        build_router,
        default_registry,
    )

    keys = Keys(sessions=HubSessions(config.data_dir / "hub_sessions.json"))
    if backend is None:
        try:
            if config.keystore == "memory":
                backend = MemoryBackend()
            else:
                from jarvis.secrets import KeyringBackend  # noqa: PLC0415

                backend = KeyringBackend()
        except StoreUnavailable:
            backend, keys.status, keys.code = None, "degraded", "store_unavailable"
    if backend is not None:
        keys.manager = KeyManager(backend, default_registry(), MetaFile(config.data_dir / "keys.json"), emit=_emit(bus))

    def verifier(token: str):
        device = keys.sessions.device(token) if keys.sessions else None
        return None if device is None else Session(can_write=device.can_write, device=device.name)

    if keys.manager is not None:
        app.include_router(build_router(keys.manager, verifier))
    return keys


async def start(keys: Keys | None) -> None:
    """Load the stored keys once (T1, a few ms per key, off the event loop) and start the watchdog."""
    if keys is None or keys.manager is None:
        return
    from jarvis.secrets import StoreUnavailable  # noqa: PLC0415

    try:
        await asyncio.to_thread(keys.manager.load)
    except StoreUnavailable:
        keys.status, keys.code = "degraded", "store_unavailable"
        log.warning("keys.load_failed", code="store_unavailable")
        return
    keys.status = "ok"
    keys.task = asyncio.create_task(keys.manager.watchdog(), name="jarvis-keys-watchdog")


async def stop(keys: Keys | None) -> None:
    if keys is not None and keys.task is not None:
        keys.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keys.task
