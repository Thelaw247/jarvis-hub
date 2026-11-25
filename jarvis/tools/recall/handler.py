from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ToolError("Say what to look for.")
    hits = await ctx.memory.search(query, branch=args.get("branch") or None, k=8)
    if not hits:
        return Result("Nothing in memory about that.")
    # Hit.line(): the text with its source tag (MEMORY §5), so the answer can say how sure it is
    return Result("\n".join(f"- {h.line()}" for h in hits))
