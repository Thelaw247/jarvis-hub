from jarvis.canvas import CanvasError, SignInNeeded
from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    link = str(args.get("link", "")).strip()
    if not link:
        raise ToolError("Give the Canvas link or path from canvas_find.")
    try:
        item = await ctx.canvas.read(link)
    except SignInNeeded as exc:
        # Laptop B, 2026-11-22: this surfaced as "Search Canvas failed (SignInNeeded)", which told Jarvis nothing.
        raise ToolError("Canvas needs De Wet to sign in first. Call sign_in with site canvas now (it opens the sign-in "
                        "window on the laptop Jarvis runs on), tell him in one line, and try again once he has closed it.") from exc
    except CanvasError as exc:
        raise ToolError(f"Canvas didn't answer ({str(exc)[:120]}). Say so in one line; don't retry the same call.") from exc
    if item.file_path is not None and ctx.documents is not None:
        doc = await ctx.documents.read(str(item.file_path))
        return Result(item.header() + "\n\n" + doc.as_text())
    return Result(item.text())
