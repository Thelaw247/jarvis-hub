"""forget: retire one remembered thing at his word (jarvis.core.learning.Learner.forget)."""
from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    what = str(args.get("what") or "").strip()
    if not what:
        raise ToolError("Say which memory to forget, in a few of its words.")
    return Result(await ctx.learner.forget(what))
