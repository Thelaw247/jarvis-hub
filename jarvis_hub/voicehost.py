"""The hub starts the voice by itself (v0.15.0): one icon, no second window.

Until now talking to Jarvis took two things on screen: the hub, and a black "Talk to Jarvis" window that carried
this laptop's mic and speakers to the core. The voice part is still its own small program (jarvis.voice.client:
sound cards, echo cancelling and the wake word are better off in a process of their own, and it can be restarted
without touching the hub), but the hub now runs it: hidden, started with the hub, stopped with the hub.

Only one laptop has Jarvis's voice at a time. A hub asks politely: if another laptop already has it, this one waits
(state "waiting") and gets it when the other closes, or at once when he presses "Talk here" (take()). It never
takes the voice just because a hub was opened.

The hub and the voice program talk over the program's stdin and stdout, nothing else:
  hub -> voice   "take"                       take the voice now
  voice -> hub   "@@ live" | "@@ waiting laptop-b" | "@@ down core" | "@@ off not_paired"
When the hub goes away the pipe closes and the voice program stops itself, so none is ever left running.

JARVIS_HUB_VOICE=0 keeps the old way (the hub doesn't start it; Talk to Jarvis.bat still works).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

STATES = ("starting", "live", "waiting", "down", "off")
WHY = {   # the voice program's reasons, as words for the hub
    "not_paired": "This laptop isn't paired with Jarvis core yet.",
    "view_only": "This laptop is paired view-only, so it can't talk to Jarvis.",
    "core": "Jarvis core isn't answering. It tries again by itself.",
    "error": "The voice part hit a problem. It tries again by itself.",
    "missing": "The voice part isn't installed on this laptop. Run Set up Laptop A.bat (or setup-voice.bat on Laptop B).",
    "disabled": "The hub isn't starting the voice (JARVIS_HUB_VOICE=0).",
    "stopped": "The voice part stopped. It starts again in a moment.",
    "demo": "The demo has no voice.",
}
RESTART_S = (5.0, 15.0, 60.0)
RETRY_MARK = " Trying again in "   # how jarvis.voice.client ends the line that says why it isn't connected
NEEDS = ("sounddevice", "websockets", "numpy")


def voice_python(root: Path) -> str | None:
    """The Python that can run the voice program: this hub's own if it has the audio packages (Laptop A's hub is
    installed with them), else the core's (Laptop B, where setup-voice.bat put them)."""
    if not getattr(sys, "frozen", False) and all(importlib.util.find_spec(m) is not None for m in NEEDS):
        exe = Path(sys.executable)
        plain = exe.with_name("python.exe")          # pythonw has no stdout to talk through
        return str(plain if exe.name.lower() == "pythonw.exe" and plain.exists() else exe)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        core = Path(local) / "JarvisCore" / "venv" / "Scripts" / "python.exe"
        if core.exists():
            return str(core)
    return None


LOG_MAX = 300_000


def note(text: str) -> None:
    """One line in <Jarvis folder>\\logs\\voice-host.log: what the hidden voice program did and said (it used to
    say it in its own window). States, reasons and errors only; it never prints what he or Jarvis said."""
    folder = Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis") / "logs"
    try:
        if not folder.is_dir():
            return
        path = folder / "voice-host.log"
        mode = "w" if path.exists() and path.stat().st_size > LOG_MAX else "a"
        with path.open(mode, encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text[:400]}\n")
    except OSError:
        pass


class VoiceHost:
    def __init__(self, root: Path, *, command: list[str] | None = None, restart_s: tuple[float, ...] = RESTART_S) -> None:
        self.root = Path(root)
        self._command = command
        self._restart_s = restart_s
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._stopping = False
        self._tries = 0
        self.state, self.device, self.reason = "off", "", ""
        self.said = ""   # the voice program's own reason for "down" ("No voice yet: paste the ElevenLabs voice ID ...")

    # ------------------------------------------------------------------ what the hub asks
    def status(self) -> dict[str, str]:
        """contracts/voice_host.schema.json"""
        why = WHY.get(self.reason, "") if self.state in ("down", "off") else ""
        if self.state == "down" and self.reason == "error" and self.said:
            why = self.said   # v0.24.2: its own words, not "hit a problem" (a missing voice ID read as "Not connected")
        return {"state": self.state, "device": self.device, "message": why}

    def start(self) -> bool:
        if os.environ.get("JARVIS_HUB_VOICE", "1").strip().lower() in ("0", "off", "no"):
            self._set("off", reason="disabled")
            return False
        if not os.environ.get("JARVIS_CORE_SESSION"):
            self._set("off", reason="not_paired")
            return False
        command = self._command
        if command is None:
            exe = voice_python(self.root)
            if exe is None:
                self._set("off", reason="missing")
                return False
            command = [exe, "-u", "-m", "jarvis.voice.client", "--hosted"]
        return self._spawn(command)

    def take(self) -> bool:
        """"Talk here": take the voice from the laptop that has it."""
        proc = self._proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            return self.start()
        note("hub: Talk here")
        try:
            proc.stdin.write("take\n")
            proc.stdin.flush()
            return True
        except OSError:
            return False

    def stop(self) -> None:
        self._stopping = True
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()          # the voice program stops itself when its hub goes
            proc.wait(timeout=2.0)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except OSError:
                pass
        self._set("off", reason="stopped")

    # ------------------------------------------------------------------ inside
    def _set(self, state: str, device: str = "", reason: str = "") -> None:
        if (state, device, reason) != (self.state, self.device, self.reason):
            note(f"hub: voice is {state} {device or reason}".rstrip())
        self.state, self.device, self.reason = state, device, reason

    def _spawn(self, command: list[str]) -> bool:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        try:
            with self._lock:
                self._proc = subprocess.Popen(command, cwd=str(self.root), stdin=subprocess.PIPE,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                              encoding="utf-8", errors="replace", bufsize=1, creationflags=flags,
                                              env=env)
        except OSError:
            self._set("off", reason="missing")
            return False
        note(f"hub: started the voice program with {Path(command[0]).name}")
        self._set("starting")
        threading.Thread(target=self._read, args=(self._proc, command), name="jarvis-voice-host", daemon=True).start()
        return True

    def _read(self, proc: subprocess.Popen, command: list[str]) -> None:
        final = ""
        try:
            for line in proc.stdout or ():
                if line.strip():
                    note(line.rstrip())      # what the black window used to show, kept where it can be read
                if RETRY_MARK in line:       # "  <why> Trying again in 2 s.": the reason it just reported "down" for
                    self.said = line.split(RETRY_MARK)[0].strip()[:200]
                if not line.startswith("@@ "):
                    continue
                parts = line[3:].split()
                state = parts[0] if parts else ""
                detail = parts[1] if len(parts) > 1 else ""
                if state == "live":
                    self._tries, self.said = 0, ""
                    self._set("live")
                elif state == "waiting":
                    self._set("waiting", device=detail)
                elif state == "down":
                    self._set("down", reason=detail or "error")
                elif state == "off":
                    final = detail or "error"
                    self._set("off", reason=final)
        except Exception:  # noqa: BLE001, S110 - a closed pipe ends the read
            pass
        code = proc.wait()
        note(f"hub: the voice program ended (code {code})")
        if self._stopping or self._proc is not proc:
            return
        if final in ("not_paired", "view_only"):
            return                           # nothing a restart would fix
        self._set("down", reason="stopped")
        wait = self._restart_s[min(self._tries, len(self._restart_s) - 1)]
        self._tries += 1
        time.sleep(wait)
        if not self._stopping and self._proc is proc:
            self._spawn(command)


def router(app_state: Any, *, demo: bool = False):
    """GET /api/voicehost (this laptop's voice: live, waiting for its turn, down, off) and POST /api/voicehost/take
    ("Talk here"). The host is attached to the app's state by app.py when the hub starts it."""
    api = APIRouter()

    def host() -> VoiceHost | None:
        return getattr(app_state, "voicehost", None)

    @api.get("/api/voicehost")
    async def voice_host() -> JSONResponse:
        h = host()
        body = h.status() if h is not None else {"state": "off", "device": "",
                                                 "message": WHY["demo" if demo else "disabled"]}
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @api.post("/api/voicehost/take")
    async def take(request: Request) -> JSONResponse:
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
            raise HTTPException(403, "Only the hub itself can move the voice.")
        h = host()
        return JSONResponse({"ok": bool(h is not None and h.take())})

    return api
