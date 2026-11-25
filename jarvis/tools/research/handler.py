from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    question = str(args.get("question", "")).strip()
    if not question:
        raise ToolError("Say what to research.")
    depth = args.get("depth") or "standard"
    t = await ctx.tasks.start("research", question, args={"depth": depth})
    return Result(f"Research started as task {t.id} ({depth}). Say a short 'On it'; the answer comes back when it's "
                  "done.", note="task")
