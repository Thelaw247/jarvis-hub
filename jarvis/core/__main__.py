"""Run jarvis-core: `python -m jarvis.core [--root DIR] [--host H] [--port N]`.

`python -m jarvis.core --check [--wait S]` asks a running core for /healthz and exits 0 when it is green within
S seconds (default 120, the M0.1 exit target), 1 otherwise. Servy runs it after start (ops/README.md).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

from .config import Config


def check(config: Config, wait_s: float) -> int:
    url = f"http://127.0.0.1:{config.port}/healthz"
    deadline = time.monotonic() + wait_s
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as reply:  # noqa: S310 - a fixed local URL
                if json.loads(reply.read()).get("status") == "green":
                    print("green")
                    return 0
        except Exception:  # noqa: BLE001 - not up yet, or red: keep asking until the deadline
            pass
        if time.monotonic() >= deadline:
            print("not green")
            return 1
        time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.core", description="Jarvis core (Laptop B)")
    parser.add_argument("--root", help="Jarvis folder (default: JARVIS_ROOT, else C:\\Jarvis on Windows)")
    parser.add_argument("--host", help="address to listen on (default 127.0.0.1; tailscale serve reaches it there)")
    parser.add_argument("--port", type=int, help="port (default 8770 or JARVIS_CORE_PORT)")
    parser.add_argument("--check", action="store_true", help="wait for a running core's /healthz to be green")
    parser.add_argument("--wait", type=float, default=120.0, help="seconds --check waits (default 120)")
    parser.add_argument("--pair", metavar="DEVICE", help="pair a hub device (laptop-a, laptop-b, phone); prints its token once")
    parser.add_argument("--view-only", action="store_true", help="with --pair: the device may look but not change (the phone)")
    parser.add_argument("--unpair", metavar="DEVICE", help="forget a paired hub device")
    args = parser.parse_args(argv)
    config = Config.from_env(root=args.root, host=args.host, port=args.port)
    if args.check:
        return check(config, args.wait)
    if args.pair or args.unpair:
        from .sessions import HubSessions

        sessions = HubSessions(config.data_dir / "hub_sessions.json")
        if args.unpair:
            print("forgotten" if sessions.unpair(args.unpair) else "no such device")
            return 0
        print(sessions.pair(args.pair, can_write=not args.view_only))  # shown once: put it in that device's hub settings
        return 0

    import uvicorn

    from .app import create_app

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, access_log=False, log_config=None, server_header=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
