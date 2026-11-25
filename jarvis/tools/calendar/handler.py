import asyncio
import logging

from jarvis.reach.calendar import CalendarError, NotConnected, which_day
from jarvis.tools.base import Result, ToolContext, ToolError

log = logging.getLogger("jarvis.tools")
WATCH_EVERY_S = 4.0
WATCH_FOR_S = 600.0
_watching: set = set()


async def run(args: dict, ctx: ToolContext) -> Result:
    cal = ctx.calendar
    try:
        first = which_day(str(args.get("day") or "today"), cal.today())
        days = int(args.get("days") or 1)
        events = await cal.events(first, days, args.get("query") or None)
    except NotConnected:
        return await connect(ctx)
    except CalendarError as exc:
        raise ToolError(str(exc)) from exc
    span = f"{first:%A} {first.day} {first:%B}" if days <= 1 else f"the {days} days from {first:%A} {first.day} {first:%B}"
    if not events:
        return Result(f"Nothing in his calendar for {span}.")
    return Result(f"His calendar for {span} (today is {cal.today():%A} {cal.today().day} {cal.today():%B}):\n"
                  + "\n".join(e.line() for e in events[:40]))


async def connect(ctx: ToolContext) -> Result:
    """Google Calendar isn't connected yet (v0.15.3). On 2026-11-19 Jarvis pulled Composio's site up inside the hub,
    where Google refuses to sign anyone in (403). Now: a card on his screen that opens the connect page in his own
    browser, on whichever laptop he is at, and Jarvis carries on by himself once the connection is there."""
    try:
        url = await ctx.calendar.connect_link()
    except CalendarError as exc:
        raise ToolError(str(exc)) from exc
    window = {"id": "w-web-connect-calendar", "type": "web", "title": "Connect Google Calendar", "size": "2x1",
              "data": {"pages": [{"id": "p-connect-calendar", "url": url, "title": "Connect Google Calendar",
                                  "site": "composio.dev", "frame": "no"}], "active": "p-connect-calendar"}}
    carry = ""
    if ctx.resume is not None:
        task = asyncio.ensure_future(_carry_on(ctx))
        _watching.add(task)
        task.add_done_callback(_watching.discard)
        carry = " You will be told when it is connected, and then you answer what he asked."
    return Result("His Google Calendar isn't connected yet, so you can't read it this time. A card called Connect "
                  "Google Calendar is on his screen now: he clicks it, it opens in his own browser, he picks his "
                  "Google account and allows it. He does that himself; nothing is typed for him." + carry +
                  " For now say one short line: click the Connect Google Calendar card and allow it. Don't open "
                  "any other page and don't use sign_in for this.", show=("window.push", window), note="connect")


async def _carry_on(ctx: ToolContext) -> None:
    try:
        waited = 0.0
        while waited < WATCH_FOR_S:
            await asyncio.sleep(WATCH_EVERY_S)
            waited += WATCH_EVERY_S
            try:
                if await ctx.calendar.connected():
                    break
            except CalendarError:
                continue
        else:
            return          # he didn't connect it this time; asking again starts over
        await ctx.resume(
            "(A note from Jarvis's own tools, not something De Wet said: Google Calendar is connected now. Carry on "
            "with what he asked before: use the calendar tool again and tell him the answer in a sentence.)")
    except Exception as exc:  # noqa: BLE001 - a watcher must never take anything down
        log.warning("tool.failed", extra={"jv": {"tool": "calendar", "error": type(exc).__name__}})
