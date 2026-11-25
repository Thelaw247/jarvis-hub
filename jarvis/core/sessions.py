"""Hub sessions: which of his devices may talk to the core's guarded routes (the Keys page first).

A device is paired once with `python -m jarvis.core --pair <name> [--view-only]`, which prints a token one time;
the hub keeps it and sends it as the `X-Jarvis-Session` header. The core keeps only a SHA-256 of each token, in
`<root>/data/hub_sessions.json` (runtime data, never in git). The phone is paired `--view-only`, so it can look
at keys but never change them (JARVIS_CORE_BUILD_MAP §3).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

DEVICE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")


@dataclass(frozen=True)
class Device:
    name: str
    can_write: bool


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class HubSessions:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._devices: dict[str, Device] = {}
        self._mtime: float | None = None
        self.reload()

    def _stamp(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return None

    def reload(self) -> None:
        self._mtime = self._stamp()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            raw = {}
        self._devices = {h: Device(d["name"], bool(d.get("can_write"))) for h, d in raw.get("devices", {}).items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"devices": {h: {"name": d.name, "can_write": d.can_write} for h, d in self._devices.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
        self._mtime = self._stamp()

    def pair(self, name: str, can_write: bool = True) -> str:
        """Make a new token for a device (replacing that device's old one) and return it. Shown once, never stored."""
        if not DEVICE.match(name):
            raise ValueError("a device name is lowercase letters, digits, dots, dashes or underscores")
        token = secrets.token_urlsafe(32)
        self._devices = {h: d for h, d in self._devices.items() if d.name != name}
        self._devices[_digest(token)] = Device(name, can_write)
        self._save()
        return token

    def unpair(self, name: str) -> bool:
        before = len(self._devices)
        self._devices = {h: d for h, d in self._devices.items() if d.name != name}
        self._save()
        return len(self._devices) < before

    def device(self, token: str) -> Device | None:
        """The paired device for a token, or None. T0 (one stat, one hash, a dict lookup). A device paired from the
        command line while the core runs counts at once: the file is read again when it has changed."""
        if self._stamp() != self._mtime:
            self.reload()
        return self._devices.get(_digest(token)) if token else None

    @property
    def count(self) -> int:
        return len(self._devices)
