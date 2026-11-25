"""open_app: any installed application, by name (jarvis.reach.apps: a Start Menu match or nothing opens)."""
import asyncio

from jarvis.reach import apps
from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    name = " ".join(str(args.get("app") or "").split())[:80]
    if not name:
        raise ToolError("Say which application.")
    if getattr(ctx, "here", False):
        answer = await asyncio.to_thread(apps.open_app, name)
    elif getattr(ctx, "hands", None) is not None:
        try:
            answer = await ctx.hands("app", {"app": name})
        except Exception:  # noqa: BLE001
            raise ToolError("The laptop he is at didn\'t answer, so nothing was opened. Closing and reopening Jarvis Hub "
                            "there fixes it. Say so in a few words.") from None
    else:
        raise ToolError("I can\'t reach the laptop he is at right now. Say so in a few words.")
    if answer.get("ok"):
        return Result(f"Opened {answer.get('opened') or name} on his laptop. One short line.")
    if answer.get("why") == "not_found":
        near = ", ".join(answer.get("near") or [])
        raise ToolError(f"No application called \"{name}\" is installed on that laptop." + (f" Close matches: {near}." if near else "") + " Ask which he means.")
    raise ToolError("That application wouldn\'t open on that laptop. Say so in a few words.")
