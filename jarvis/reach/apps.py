"""Opening his applications (v0.26.0, his ask: "he could open any app he likes").

An app is opened by its name, found among the Start Menu shortcuts on the laptop he is at (what he has installed),
then among everything in his Start list (v0.27.0: Microsoft Store apps such as Netflix have no shortcut file;
Windows' own Get-StartApps lists them), plus a few that Windows keeps elsewhere. Jarvis never runs a path, a command or arguments of his own making: the
name either matches something installed or nothing opens. T1.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

BUILT_IN = {   # apps with no Start Menu shortcut to find: fixed targets, never built from what was asked
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "files": "explorer.exe", "notepad": "notepad.exe",
    "calculator": "calc.exe", "paint": "mspaint.exe", "settings": "ms-settings:", "spotify": "spotify:",
    "claude": "claude://", "snipping tool": "ms-screenclip:", "task manager": "taskmgr.exe",
}
ALIASES = {"vs code": "visual studio code", "vscode": "visual studio code", "code": "visual studio code", "chrome": "google chrome",
           "edge": "microsoft edge", "word": "word", "excel": "excel", "powerpoint": "powerpoint", "ppt": "powerpoint"}
SKIP = ("uninstall", "readme", "help", "license", "release notes", "website", "documentation")


def start_menus(env: dict | None = None) -> list[Path]:
    env = env if env is not None else os.environ
    found = [Path(env[k]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" for k in ("APPDATA", "PROGRAMDATA") if env.get(k)]
    return [p for p in found if p.is_dir()]


def installed(menus: list[Path]) -> dict[str, Path]:
    """name (lower case) → its shortcut. Uninstallers and read-me links are left out."""
    out: dict[str, Path] = {}
    for menu in menus:
        for link in menu.rglob("*.lnk"):
            name = link.stem.casefold()
            if not any(s in name for s in SKIP):
                out.setdefault(name, link)
    return out


_START = {"at": -1e9, "apps": {}}
START_TTL_S = 600.0
APP_ID = re.compile(r"^[\w.!\-{}\\ +]+$")


def start_apps(run: Callable[..., Any] = subprocess.run, clock: Callable[[], float] = time.monotonic) -> dict[str, tuple[str, str]]:
    """Everything in his Start list, Store apps included. name (lower case) → (name as shown, what to open).
    Asked of Windows itself (about a second the first time, then remembered for ten minutes). {} anywhere else."""
    if clock() - _START["at"] < START_TTL_S:
        return _START["apps"]
    apps: dict[str, tuple[str, str]] = {}
    try:
        out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                  capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rows = json.loads(out.stdout or "[]")
        for row in rows if isinstance(rows, list) else [rows]:
            name, app_id = str(row.get("Name") or "").strip(), str(row.get("AppID") or "").strip()
            if name and APP_ID.match(app_id) and not any(s in name.casefold() for s in SKIP):
                apps.setdefault(name.casefold(), (name, "shell:AppsFolder\\" + app_id))
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        apps = {}
    _START.update(at=clock(), apps=apps)
    return apps


def clean(ask: str) -> str:
    ask = re.sub(r"[^a-z0-9+# .-]", " ", str(ask or "").casefold())
    ask = re.sub(r"\b(the|app|application|program|please|open|launch|start|up)\b", " ", ask)
    return " ".join(ask.split())


def find(ask: str, shortcuts: dict[str, Any]) -> tuple[str, Any] | None:
    """The installed app he means: its exact name, else a name starting with it, else one holding every word."""
    want = ALIASES.get(clean(ask), clean(ask))
    if not want:
        return None
    words = want.split()
    ranked = sorted((0 if n == want else 1 if n.startswith(want) else 2, len(n), n) for n in shortcuts
                    if n == want or n.startswith(want) or all(w in n.split() or w in n for w in words))
    return (ranked[0][2], shortcuts[ranked[0][2]]) if ranked else None


def open_app(ask: str, *, opener: Callable[[str], Any] | None = None, menus: list[Path] | None = None,
             store: Callable[[], dict[str, tuple[str, str]]] = start_apps) -> dict:
    """→ {"ok": True, "opened": name} or {"ok": False, "why", "near": [names]}."""
    opener = opener or getattr(os, "startfile", None)
    if opener is None:
        return {"ok": False, "why": "not_windows", "near": []}
    shortcuts = installed(menus if menus is not None else start_menus())
    hit = find(ask, shortcuts)
    want = clean(ask)
    try:
        if hit is not None:
            opener(str(hit[1]))
            return {"ok": True, "opened": hit[1].stem}
        if want in BUILT_IN:
            opener(BUILT_IN[want])
            return {"ok": True, "opened": want}
        listed = store()                                   # Store apps and anything else with no shortcut file
        more = find(ask, listed)
        if more is not None:
            opener(more[1][1])
            return {"ok": True, "opened": more[1][0]}
    except OSError:
        return {"ok": False, "why": "would_not_open", "near": []}
    first = want.split()[0] if want else ""
    near = sorted({p.stem for n, p in shortcuts.items() if first and first[:3] in n}
                  | {shown for n, (shown, _) in listed.items() if first and first[:3] in n})[:6]
    return {"ok": False, "why": "not_found", "near": near}
