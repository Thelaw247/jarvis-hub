from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    path = str(args.get("path", "")).strip()
    if not path:
        raise ToolError("Give the file's path or link.")
    doc = await ctx.documents.read(path, pages=args.get("pages") or None, question=args.get("question") or None)
    return Result(doc.as_text(), note=f"pages={doc.pages_returned}/{doc.page_count}")
