"""Paths and small settings for the hub app. Works from source and from the PyInstaller folder."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Jarvis Hub"
APP_ID = "JarvisHub.App"


def base_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller: data sits beside the exe (in _internal on newer versions)
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return base_dir().joinpath(*parts)


def data_dir() -> Path:
    """Where logs and window settings go (never in the repo)."""
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    path = root / "JarvisHub"
    path.mkdir(parents=True, exist_ok=True)
    return path


def version() -> str:
    try:
        return resource_path("VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def allowed_hosts() -> list[str]:
    """Host names the hub answers to. Anything else is refused, so a web page can't reach the hub through a
    look-alike name (DNS rebinding). Add the tailnet name (e.g. hub.tailnet-name.ts.net) with JARVIS_HUB_HOSTS,
    comma-separated."""
    extra = [h.strip().lower() for h in os.environ.get("JARVIS_HUB_HOSTS", "").split(",") if h.strip()]
    return ["127.0.0.1", "localhost", *extra]
