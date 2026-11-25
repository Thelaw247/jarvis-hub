"""Screenshots of every scene × theme × size, for looking at (and for the reviews).

  python tools/screenshots.py                      every scene, both themes, each scene's own sizes
  python tools/screenshots.py --only orb,now       only scenes whose name contains one of these words
  python tools/screenshots.py --sizes full,phone   force sizes
  python tools/screenshots.py --list               just print the scene names

Writes PNGs to screenshots/out/<scene>__<theme>__<size>.png (ignored by git) and prints any console
errors it saw. Starts its own hub server; needs Playwright (python -m playwright install chromium).
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SIZES = {"full": (1920, 1080), "laptop": (1280, 720), "phone": (390, 844), "strip": (360, 96), "ambient": (1920, 1080)}
THEMES = ("night", "day")


def start_server() -> tuple[str, object]:
    import uvicorn

    from jarvis_hub.server import create_app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(create_app(autoplay=False), host="127.0.0.1", port=port, log_level="warning", access_log=False))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.025)
    return f"http://127.0.0.1:{port}", server


def sizes_for(name: str, forced: list[str] | None) -> list[str]:
    if forced:
        return forced
    if name.startswith("component:"):
        return ["laptop"]
    if name.startswith("strip"):
        return ["strip"]
    if name.startswith("phone"):
        return ["phone"]
    if "ambient" in name:
        return ["ambient", "laptop"]
    return ["full", "laptop"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default="", help="comma-separated words; keep scenes containing any of them")
    parser.add_argument("--sizes", default="", help=f"comma-separated: {', '.join(SIZES)}")
    parser.add_argument("--themes", default=",".join(THEMES))
    parser.add_argument("--out", default=str(ROOT / "screenshots" / "out"))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--motion", default="reduce", choices=["reduce", "no-preference"])
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    base, server = start_server()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base}/?scene=shell")
        page.wait_for_selector("html[data-ready]")
        names = page.evaluate("window.__jarvis.scenes()")
        words = [w for w in args.only.split(",") if w]
        names = [n for n in names if not words or any(w in n for w in words)]
        if args.list:
            print("\n".join(names))
            return 0
        forced = [s for s in args.sizes.split(",") if s] or None
        for name in names:
            for size in sizes_for(name, forced):
                width, height = SIZES[size]
                context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion=args.motion)
                shot = context.new_page()
                seen: list[str] = []
                shot.on("console", lambda m, seen=seen: seen.append(m.text) if m.type == "error" else None)
                shot.on("pageerror", lambda e, seen=seen: seen.append(str(e)))
                for theme in [t for t in args.themes.split(",") if t]:
                    shot.goto(f"{base}/?scene={name}&theme={theme}&size={size}")
                    shot.wait_for_selector("html[data-ready]")
                    shot.evaluate("document.fonts.ready")
                    shot.wait_for_timeout(150)
                    file = out / f"{re.sub(r'[^a-z0-9]+', '-', name)}__{theme}__{size}.png"
                    shot.screenshot(path=str(file), full_page=name.startswith("component:"))
                    count += 1
                    problems += [f"{name} ({theme}, {size}): {text}" for text in seen]
                    seen.clear()
                context.close()
        browser.close()
    server.should_exit = True
    for line in problems:
        print(line)
    print(f"screenshots: {count} written to {out}" + (f", {len(problems)} problem(s)" if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
