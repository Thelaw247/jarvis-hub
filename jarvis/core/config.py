"""Where Jarvis lives on disk and the few settings the core reads at start (RUNTIME §10).

One setting matters: the root folder, `JARVIS_ROOT` (default `C:\\Jarvis` on Windows, `~/Jarvis` elsewhere; tests
use a temp folder). The repo itself sits in that root; the runtime folders below are made at start and are never
committed (.gitignore lists them):

    <root>/memory/    jarvis.db (MEMORY §3), never in git
    <root>/undo/      undo records for file changes (30 days)
    <root>/data/      jobs.db (the job queue) and other runtime state
    <root>/browser/   browser profiles (browser/usask for the Canvas session)
    <root>/logs/      core.jsonl (ids and timings only, C21)
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import version

RUNTIME_DIRS = ("memory", "undo", "data", "browser", "logs")
DEFAULT_PORT = 8770  # the hub picks a free port on Laptop A; the core has a fixed one for tailscale serve and Servy
MAX_JOBS = 2  # RUNTIME §4: at most 2 jobs at once (~1 GiB RAM each)


def default_root() -> Path:
    return Path(r"C:\Jarvis") if sys.platform == "win32" else Path.home() / "Jarvis"


def _hosts(raw: str) -> tuple[str, ...]:
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


@dataclass(frozen=True)
class Config:
    root: Path
    host: str = "127.0.0.1"  # tailscale serve proxies the tailnet name to this; nothing else on the network reaches it
    port: int = DEFAULT_PORT
    max_jobs: int = MAX_JOBS
    extra_hosts: tuple[str, ...] = ()  # e.g. the tailnet name laptop-b.<tailnet>.ts.net (JARVIS_CORE_HOSTS)
    extra_origins: tuple[str, ...] = ()  # pages allowed to send actions besides the core's own (JARVIS_CORE_ORIGINS)
    keystore: str = "keyring"  # where API keys live: keyring (Credential Manager) or memory (tests only)
    voice_preload: bool = True  # load the voice models at start-up when everything is there (JARVIS_VOICE_PRELOAD=0 to skip)
    tools: bool = True    # Jarvis's tools (TOOLS): browser, Canvas, documents, tasks (JARVIS_TOOLS=0 to switch off)
    memory: bool = True   # the memory store in the core (recall, the abilities branch) (JARVIS_MEMORY=0 to skip)
    hub_feed: bool = True  # fill the hub from his class files, calendar, memory and the voice log (JARVIS_HUB_FEED=0 to skip)
    version: str = field(default_factory=version)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **overrides) -> Config:
        env = os.environ if env is None else env
        values: dict = {
            "root": Path(env["JARVIS_ROOT"]) if env.get("JARVIS_ROOT") else default_root(),
            "host": env.get("JARVIS_CORE_HOST", "127.0.0.1"),
            "port": int(env.get("JARVIS_CORE_PORT", DEFAULT_PORT)),
            "extra_hosts": _hosts(env.get("JARVIS_CORE_HOSTS", "")),
            "extra_origins": _hosts(env.get("JARVIS_CORE_ORIGINS", "")),
            "keystore": env.get("JARVIS_CORE_KEYSTORE", "keyring"),
            "voice_preload": env.get("JARVIS_VOICE_PRELOAD", "1") != "0",
            "hub_feed": env.get("JARVIS_HUB_FEED", "1") != "0",
            "tools": env.get("JARVIS_TOOLS", "1") != "0",
            "memory": env.get("JARVIS_MEMORY", "1") != "0",
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        values["root"] = Path(values["root"])
        if values["keystore"] not in ("keyring", "memory"):
            raise ValueError("JARVIS_CORE_KEYSTORE is keyring or memory")
        return cls(**values)

    # the runtime folders (RUNTIME §10)
    @property
    def memory_dir(self) -> Path: return self.root / "memory"
    @property
    def undo_dir(self) -> Path: return self.root / "undo"
    @property
    def data_dir(self) -> Path: return self.root / "data"
    @property
    def browser_dir(self) -> Path: return self.root / "browser"
    @property
    def logs_dir(self) -> Path: return self.root / "logs"
    @property
    def queue_db(self) -> Path: return self.data_dir / "jobs.db"
    @property
    def log_file(self) -> Path: return self.logs_dir / "core.jsonl"

    @property
    def allowed_hosts(self) -> list[str]:
        """Host names the core answers to; anything else is refused (DNS rebinding)."""
        return ["127.0.0.1", "localhost", *self.extra_hosts]

    def ensure_layout(self) -> list[Path]:
        """Make the root and its runtime folders. Safe to run every start. T1 (disk, once at start)."""
        made = []
        for name in RUNTIME_DIRS:
            path = self.root / name
            if not path.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                made.append(path)
        return made

    def layout_ok(self) -> bool:
        return all((self.root / name).is_dir() and os.access(self.root / name, os.W_OK) for name in RUNTIME_DIRS)
