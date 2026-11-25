from jarvis.canvas import CanvasError, SignInNeeded
from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ToolError("Say what to look for on Canvas.")
    try:
        hits = await ctx.canvas.find(query, course=args.get("course") or None, kinds=args.get("kinds") or None)
    except SignInNeeded as exc:
        # Laptop B, 2026-11-22: this surfaced as "Search Canvas failed (SignInNeeded)", which told Jarvis nothing.
        raise ToolError("Canvas needs De Wet to sign in first. Call sign_in with site canvas now (it opens the sign-in "
                        "window on the laptop Jarvis runs on), tell him in one line, and try again once he has closed it.") from exc
    except CanvasError as exc:
        raise ToolError(f"Canvas didn't answer ({str(exc)[:120]}). Say so in one line; don't retry the same call.") from exc
    if not hits:
        return Result(f"Nothing on Canvas matched {query!r}. Try other words, or a course.")
    return Result("\n".join(h.line() for h in hits[:10]))
