"""remember: his own words into memory, on purpose (jarvis.core.learning.Learner.save)."""
from jarvis.tools.base import Result, ToolContext, ToolError


async def run(args: dict, ctx: ToolContext) -> Result:
    text = str(args.get("text") or "").strip()
    if not text:
        raise ToolError("Say what to remember in one sentence.")
    if args.get("confirmed") is not True:   # his rule (2026-11-22): always check with him before keeping something
        return Result("Not saved yet: he wants to be asked first. Ask him now, in your own words and in one short line, whether "
                      "to remember it for next time. If he says yes, call remember again with confirmed true; if no, drop it.")
    line = await ctx.learner.save(text, str(args.get("kind") or "preference"), his_words=str(args.get("his_words") or ""),
                                  about=args.get("about") or None, scope=args.get("scope") or None,
                                  replaces=args.get("replaces") or None, explicit=True)
    return Result(line, is_error=line.startswith("Not saved: say") or "refused it" in line)
