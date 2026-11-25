"""Hands on the laptop he is sitting at (v0.24.0).

Jarvis's core may run on the other laptop. The voice program on this one already carries his voice both ways, so it
also does three small things here when the core asks over that same paired connection (jarvis.voice.client):

  windows  the screens and the titles of his open windows. Asked only when he wants an arrangement; nothing is kept.
  place    move those windows. The core only asks after his yes (jarvis.tools.arrange_windows).
  open     a web page in his browser, a document inside his Class Content folder, or the Claude app.
  files    create a text file, make a folder, move or rename, in his four folders only (jarvis.reach.files: never
           deletes, never overwrites, every change can be taken back). The core asks him first.
  app      open an installed application by its name (jarvis.reach.apps: a Start Menu match or nothing).

Nothing else: no commands, no typing, no reading inside a window, no path outside those folders.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jarvis.reach.classes import find_root
from jarvis.reach.desktop import Desktop, Rect, Win
from jarvis.reach.workfiles import OPENABLE

CLAUDE_APP, CLAUDE_WEB = "claude://", "https://claude.ai/new"
MAX_MOVES = 4


def claude_running() -> bool:
    """Is the Claude app already open? (Windows task list; anywhere else: assume not.)"""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"], capture_output=True, text=True, timeout=4,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "claude.exe" in out.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def run(kind: str, args: dict | None = None, *, desktop: Any = None, opener: Callable[[str], Any] | None = None,
        root: Path | None = None, running: Callable[[], bool] = claude_running) -> dict:
    """Do one thing on this laptop. → {"ok": bool, ...}; never raises for a request it doesn't like. T1."""
    args = args if isinstance(args, dict) else {}
    if kind in ("windows", "place"):
        desk = desktop or Desktop()
        if not getattr(desk, "ok", False):
            return {"ok": False, "why": "not_windows"}
        if kind == "windows":
            return {"ok": True, "screens": [[r.x, r.y, r.w, r.h] for r in desk.screens()],
                    "windows": [{"handle": w.handle, "title": w.title, "screen": w.screen, "minimized": w.minimized} for w in desk.windows()]}
        moved = []
        for move in (args.get("moves") or [])[:MAX_MOVES]:
            try:
                handle, to = int(move["handle"]), [int(n) for n in move["to"]]
                if len(to) == 4 and desk.place(Win(handle, "", 0), Rect(*to)):
                    moved.append(handle)
            except (KeyError, TypeError, ValueError):
                continue
        return {"ok": True, "moved": moved}
    if kind == "files":
        from jarvis.reach import files  # noqa: PLC0415

        return files.run(args)
    if kind == "app":
        from jarvis.reach import apps  # noqa: PLC0415

        return apps.open_app(str(args.get("app") or ""), opener=opener)
    if kind == "open":
        opener = opener or getattr(os, "startfile", None)   # Windows: the thing's own app
        if opener is None:
            return {"ok": False, "why": "not_windows"}
        try:
            if args.get("app") == "claude":
                if running():
                    return {"ok": True, "was_open": True}
                try:
                    opener(CLAUDE_APP)
                except OSError:
                    opener(CLAUDE_WEB)
                return {"ok": True, "was_open": False}
            url = str(args.get("url") or "")
            if url:
                if not url.lower().startswith(("https://", "http://")) or any(c in url for c in "\r\n\t \"'"):
                    return {"ok": False, "why": "not_a_web_address"}
                opener(url)
                return {"ok": True}
            base = (root or find_root() or Path()).resolve()
            target = (base / str(args.get("file") or "")).resolve()
            if not args.get("file") or root is None and find_root() is None or base not in target.parents or not target.exists():
                return {"ok": False, "why": "not_in_class_content"}
            if target.is_file() and target.suffix.lower() not in OPENABLE:
                return {"ok": False, "why": "not_a_document"}   # documents and folders only, never a program
            opener(str(target))
            return {"ok": True}
        except OSError:
            return {"ok": False, "why": "would_not_open"}
    return {"ok": False, "why": "unknown"}
