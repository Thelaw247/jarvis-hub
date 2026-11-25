"""Keep Jarvis core running on Laptop B without Servy (setup-core.bat starts this at sign-in).

Run with the core's own pythonw.exe from the repo folder. Every 15 s it asks the core's /healthz; when nothing
answers it starts `python -m jarvis.core` with no window, and starts it again if it stops. If a core is already
answering (Servy, or a terminal), it leaves it alone. Output goes to <Jarvis folder>\\logs\\core.console.log.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")
PORT = int(os.environ.get("JARVIS_CORE_PORT") or 8770)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def answering() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=3):  # noqa: S310 - fixed local URL
            return True
    except urllib.error.HTTPError:
        return True  # it answered (red is still a running core)
    except Exception:  # noqa: BLE001 - not running
        return False


def main() -> None:
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, JARVIS_ROOT=str(ROOT), JARVIS_CORE_PORT=str(PORT), PYTHONUNBUFFERED="1")
    while True:
        if answering():
            time.sleep(15)
            continue
        with open(ROOT / "logs" / "core.console.log", "ab") as log:
            subprocess.call([sys.executable, "-m", "jarvis.core"], cwd=REPO, env=env,
                            stdout=log, stderr=log, creationflags=NO_WINDOW)
        time.sleep(5)  # stopped or crashed: wait a moment, then start it again


if __name__ == "__main__":
    main()
