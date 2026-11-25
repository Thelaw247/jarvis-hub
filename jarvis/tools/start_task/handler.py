from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    goal = str(args.get("goal", "")).strip()
    if not goal:
        raise ToolError("Say what the task should do, and when it's done.")
    t = await ctx.tasks.start("task", goal, args={"skills": list(args.get("skills") or [])})
    return Result(f"Task {t.id} started. Say a short 'On it'; it reports back when done.", note="task")
