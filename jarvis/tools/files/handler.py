"""files: create, move and rename in his four folders, after his yes (jarvis.reach.files does the checking)."""
import asyncio

from jarvis.reach import files
from jarvis.tools.base import Result, ToolContext, ToolError

ASK = ("Nothing has changed yet. Put this to him in a few words and wait for his yes: {plan}? "
       "Then call files again with the same arguments and confirmed true.")


async def _do(ctx: ToolContext, args: dict) -> dict:
    """On the laptop he is at: here, or through its voice program when he talks from the other one."""
    if getattr(ctx, "here", False):
        return await asyncio.to_thread(files.run, args)
    hands = getattr(ctx, "hands", None)
    if hands is None:
        raise ToolError("I can\'t reach the laptop he is at right now, so nothing was changed. Say so in a few words.")
    try:
        return await hands("files", args)
    except Exception:  # noqa: BLE001 - an older voice program there, or it went away
        raise ToolError("The laptop he is at didn\'t answer, so nothing was changed. Closing and reopening Jarvis Hub "
                        "there fixes it. Say so in a few words.") from None


async def run(args: dict, ctx: ToolContext) -> Result:
    ask = {k: args[k] for k in ("action", "place", "path", "content", "to_place", "to_path") if args.get(k) is not None}
    if ask.get("action") not in ("create", "folder", "move", "undo"):
        raise ToolError("Use action create, folder, move or undo.")
    looked = await _do(ctx, {**ask, "dry": True})
    if not looked.get("ok"):
        raise ToolError(f"{looked.get('why') or 'That can\'t be done.'} Nothing was changed.")
    if args.get("confirmed") is not True:
        return Result(ASK.format(plan=looked.get("plan", "Make that change")))
    done = await _do(ctx, ask)
    if not done.get("ok"):
        raise ToolError(f"{done.get('why') or 'That didn\'t work.'} Nothing else was changed.")
    return Result(f"{done.get('did')}. Tell him in one short line. He can say \"undo that\" to take it back.")
