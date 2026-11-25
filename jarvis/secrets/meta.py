"""The Keys page's non-secret bookkeeping: per slot, when a key was added and checked, its last 4 and its check.

A small JSON file under the core root (``<root>/data/keys.json``), written atomically. It never holds a
secret: only what the contract's rows may show, plus the audit trail (ids and fixed words).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

AUDIT_KEEP = 200


def default_meta_path(root: Path) -> Path:
    return Path(root) / "data" / "keys.json"


class MetaFile:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("providers", {})
        data.setdefault("audit", [])
        data.setdefault("seq", 0)
        return data

    def provider(self, provider_id: str) -> dict:
        """The provider's entry: {slots: {live|next|previous: info}, swapped_at, fell_back}. Created on first use."""
        entry = self.data["providers"].setdefault(provider_id, {})
        entry.setdefault("slots", {})
        entry.setdefault("swapped_at", None)
        entry.setdefault("fell_back", False)
        return entry

    def forget(self, provider_id: str) -> None:
        self.data["providers"].pop(provider_id, None)

    def add_audit(self, entry: dict) -> dict:
        self.data["seq"] += 1
        entry = {"id": f"keys-{self.data['seq']:04d}", **entry}
        self.data["audit"].insert(0, entry)
        del self.data["audit"][AUDIT_KEEP:]
        return entry

    def save(self) -> None:
        """Atomic write (temp file + replace). T1 (a few ms, only on a change)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
