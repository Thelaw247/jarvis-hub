from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    task = str(args.get("task", "")).strip()
    if not task:
        raise ToolError("Say what to find or do, and when it's done.")
    mode = args.get("mode") or "read"
    start = args.get("start_url") or None
    if ctx.origin == "task":  # inside a task: run here and give the findings back to the task's model
        out = await ctx.browser.browse(task, start_url=start, mode=mode)
        return Result(out.report(), is_error=out.failed)
    t = await ctx.tasks.start("browse", task, args={"start_url": start, "mode": mode})
    return Result(f"Started browsing as task {t.id}. Say a short 'On it' (no details); Jarvis reports back when it's "
                  "done.", note="task")
