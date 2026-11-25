from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    question = str(args.get("question", "")).strip()
    if not question:
        raise ToolError("Give the question.")
    qid = await ctx.questions.ask(question, options=list(args.get("options") or []), default=args.get("default"))
    return Result(f"Asked (#{qid}). Carry on with the default ({args.get('default') or 'none given'}) and say what's "
                  "waiting on his answer.")
