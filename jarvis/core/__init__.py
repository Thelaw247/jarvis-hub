"""jarvis-core (M0.1): config, event bus, durable job queue, health, private JSON logs and the hub's API.

Start it with `python -m jarvis.core`. See ops/README.md for running it under Servy and `tailscale serve`.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def version() -> str:
    """The repo's VERSION file is the one version number (jarvis-release skill)."""
    try:
        return (REPO / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
