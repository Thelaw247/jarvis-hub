"""Check Jarvis's tools on this laptop (setup-tools.bat runs it): what's installed, and the Jarvis browser opens.

    python -m jarvis.tools.check            # list every tool and whether it can run here
    python -m jarvis.tools.check --browser  # also start the Jarvis browser headless and read a public page

Prints plain lines; exits 1 if something needed is missing. Never touches his signed-in sessions.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys

NEEDS = {"anthropic": "Claude's tools (browser, vision)", "playwright": "the Jarvis browser (browse, Canvas)",
         "pymupdf": "PDF reading", "markitdown": "Word, Excel and PowerPoint reading",
         "claude_agent_sdk": "tasks and research (Claude agents with his skills)", "yaml": "the tools folder"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args(argv)
    ok = True
    for mod, what in NEEDS.items():
        have = importlib.util.find_spec(mod) is not None
        ok &= have
        print(f"  {'ok ' if have else 'MISSING'}  {what} ({mod})")
    from jarvis.tools import Registry  # noqa: PLC0415

    reg = Registry()
    print(f"\n  {len(reg.specs)} tools in the tools folder: {', '.join(sorted(reg.specs))}")
    if args.browser and importlib.util.find_spec("playwright") is not None:
        ok &= asyncio.run(_browser())
    print("\nAll set." if ok else "\nSomething is missing: run setup-tools.bat again and read the messages above.")
    return 0 if ok else 1


async def _browser() -> bool:
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from playwright.async_api import async_playwright  # noqa: PLC0415

    from jarvis.browser.service import pick_channel  # noqa: PLC0415

    channel = pick_channel()
    try:
        async with async_playwright() as pw:
            with tempfile.TemporaryDirectory() as tmp:  # a throwaway profile: his signed-in one isn't touched
                ctx = await pw.chromium.launch_persistent_context(str(Path(tmp)), headless=True,
                                                                  **({"channel": channel} if channel else {}))
                page = await ctx.new_page()
                await page.goto("https://example.com", timeout=20_000)
                title = await page.title()
                await ctx.close()
        print(f"  ok   the Jarvis browser opened a page ({title}) with {({'chrome': 'Google Chrome', 'msedge': 'Microsoft Edge'}).get(channel or '', 'Chromium')}")
        return True
    except Exception as e:
        print(f"  MISSING  the Jarvis browser couldn't start ({type(e).__name__}). On Windows it uses Microsoft Edge.")
        return False


if __name__ == "__main__":
    sys.exit(main())
