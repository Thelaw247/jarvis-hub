import asyncio
import logging

from jarvis.tools.base import Result, ToolContext, ToolError

log = logging.getLogger("jarvis.tools")

# The site's ordinary front page, not its login address (his catch, 2026-11-22): the front page shows the dashboard when
# the sign-in is still good and only asks when it isn't, while the login address starts a new sign-in every time,
# even over one that would have lasted.
KNOWN = {
    "canvas": "https://canvas.usask.ca/",
    "paws": "https://paws.usask.ca/",
    "google": "https://accounts.google.com/",
    "crowdmark": "https://app.crowdmark.com/student",
    "github": "https://github.com/login",
}
QUICK_CLOSE_S = 4.0    # closed this fast: it never really opened (or handed its page to another window)
_watching: set = set()


async def run(args: dict, ctx: ToolContext) -> Result:
    site = str(args.get("site", "")).strip()
    url = KNOWN.get(site.lower(), site)
    if not url.startswith("https://"):
        raise ToolError("Give a known site (canvas, paws, google, crowdmark, github) or an https sign-in link.")
    await ctx.browser.open_visible(url, own_window=True)
    if ctx.resume is not None and hasattr(ctx.browser, "wait_closed"):
        # v0.14.0: watch the window. On 2026-11-18 he signed in, nothing noticed, and the question that needed the
        # sign-in was never answered. When the window closes, Jarvis carries on with it by himself.
        task = asyncio.ensure_future(_carry_on(ctx, site))
        _watching.add(task)
        task.add_done_callback(_watching.discard)
        return Result(f"The sign-in page for {site} is open in its own window on Laptop B. He signs in himself and "
                      "closes the window when he's done. You will be told when it closes, and then you carry on "
                      "with what he asked. For now say one short line: the sign-in is open, close it when done.")
    return Result(f"Opened the sign-in page for {site} in the Jarvis browser on Laptop B. He signs in himself.")


async def _carry_on(ctx: ToolContext, site: str) -> None:
    try:
        open_for = await ctx.browser.wait_closed()
        if open_for is None or open_for < QUICK_CLOSE_S:
            return      # not ours to judge: he'll say when he's done
        await asyncio.sleep(1.0)    # the browser lets go of its profile
        await ctx.resume(
            f"(A note from Jarvis's own tools, not something De Wet said: he has closed the sign-in window for "
            f"{site}, so he has most likely signed in. Carry on now with what he asked before the sign-in: use the "
            f"tool again and tell him the answer in a sentence. If it still asks for a sign-in, tell him it didn't "
            f"take and offer to open it again.)")
    except Exception as exc:  # noqa: BLE001 - a watcher must never take anything down
        log.warning("tool.failed", extra={"jv": {"tool": "sign_in", "error": type(exc).__name__}})
