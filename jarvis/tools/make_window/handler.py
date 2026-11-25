"""make_window: a page Jarvis wrote, shown as a hub window (jarvis.reach.made: kept locally, served sandboxed)."""
import re

from jarvis.reach import made
from jarvis.tools.base import Result, ToolContext, ToolError

OUTSIDE = re.compile(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""", re.I)


async def run(args: dict, ctx: ToolContext) -> Result:
    title = " ".join(str(args.get("title") or "").split())[:120]
    body = str(args.get("html") or "").strip()
    if not title or not body:
        raise ToolError("Give a title and the body of the page (html).")
    if len(body) > made.MAX_BODY:
        raise ToolError(f"That page is too big ({len(body):,} characters; the most is {made.MAX_BODY:,}). Make it shorter.")
    if re.search(r"<\s*(html|head|body)\b", body, re.I):
        raise ToolError("Write only the body's content: no <html>, <head> or <body> tags.")
    note = " Links to outside scripts, fonts or images in it will not load: the page can reach nothing outside itself." \
        if OUTSIDE.search(body) else ""
    page_id = made.save(ctx.root, title, body)
    size = args.get("size") if args.get("size") in ("2x1", "2x2", "3x2") else "2x2"
    window = {"id": f"w-made-{page_id}", "type": "web", "title": title, "size": size,
              "data": {"pages": [{"id": f"p-{page_id}", "url": made.url(page_id), "title": title}], "active": f"p-{page_id}"}}
    return Result(f"On screen: {title}.{note} Say one short line; don't read it out.", show=("window.push", window))
