"""Browser check (Browser check.bat): runs Jarvis's own browser code the way the core does, in a throwaway folder,
and prints every step with timings: a hidden browser for a Canvas lookup, then the sign-in window. Never touches
the Jarvis browser's real profile or sign-ins, and prints no personal data."""
import asyncio
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def watch_loop():
    """Prints when something freezes the event loop (which would freeze the core)."""
    last = time.perf_counter()
    while True:
        await asyncio.sleep(0.25)
        now = time.perf_counter()
        if now - last > 1.0:
            print(f"   !! the event loop was frozen for {now - last - 0.25:.1f} s", flush=True)
        last = now


async def step(name, coro):
    t = time.perf_counter()
    try:
        out = await asyncio.wait_for(coro, 70)
        print(f"OK   {name}: {time.perf_counter() - t:.1f} s", flush=True)
        return out
    except Exception as e:  # noqa: BLE001 - this is a diagnostic: show everything
        print(f"FAIL {name} after {time.perf_counter() - t:.1f} s: {type(e).__name__}: {str(e)[:700]}", flush=True)
        traceback.print_exc(limit=4)
        return None


async def main():
    print("event loop:", type(asyncio.get_running_loop()).__name__, flush=True)
    asyncio.create_task(watch_loop())  # noqa: RUF006
    from jarvis.browser import BrowserService
    from jarvis.canvas import CanvasClient, playwright_fetch

    root = Path(tempfile.mkdtemp())
    svc = BrowserService(root)
    print("browser:", svc.channel or "chromium", flush=True)
    canvas = CanvasClient(playwright_fetch(svc), downloads=root / "dl")
    await step("hidden browser + a Canvas lookup (expect 'sign in again')", canvas.courses())
    await step("sign-in window (a plain browser window)", svc.open_visible("https://canvas.usask.ca/login"))
    print("     Close the browser window that opened to finish.", flush=True)
    for _ in range(240):
        if not svc.his_window_open():
            break
        await asyncio.sleep(0.5)
    await step("Jarvis takes the profile back", canvas.courses())
    await step("close", svc.aclose())


asyncio.run(main())
