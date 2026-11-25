"""mark_done: he says a piece of coursework is finished; it leaves his list and the hub's warnings (done.json)."""
from datetime import datetime

from jarvis.reach import workfiles
from jarvis.tools.base import Result, ToolContext, ToolError

LOOK_BACK_DAYS, LOOK_AHEAD_DAYS = 30, 60


def _score(ask: list[str], course: dict | None, item) -> int:
    words = set(workfiles.tokens(f"{item.title} {item.platform}"))
    hit = sum(2 if w.isdigit() else 1 for w in ask if w in words or (w.isdigit() and w.zfill(2) in words))
    return hit + (3 if course is not None and course.get("course") == item.course else 0)


async def run(args: dict, ctx: ToolContext) -> Result:
    cc, what = ctx.classes, " ".join(str(args.get("what") or "").split())
    if not what:
        raise ToolError("Say which piece of work.")
    if args.get("confirmed") is not True:
        return Result("Nothing has changed. Ask him in a few words whether it is finished, then call mark_done again with confirmed true.")
    now = ctx.now() if callable(getattr(ctx, "now", None)) else datetime.now()
    ask, course = workfiles.tokens(what), workfiles.pick_course(cc, what)
    if args.get("done") is False:
        marks = cc.done()
        back = [k for k, m in marks.items() if any(w in workfiles.tokens(f"{m.get('title', '')} {m.get('course', '')} {k}") for w in ask)
                or (course is not None and m.get("course") == course.get("course"))]
        if not back:
            raise ToolError("Nothing he marked as done matches that. Say so in a few words.")
        for key in back:
            cc.mark_done(key, done=False)
        names = ", ".join(f"{marks[k].get('course', '')} {marks[k].get('title', k)}".strip() for k in back)
    else:
        open_now = cc.due(now, LOOK_AHEAD_DAYS, overdue_days=LOOK_BACK_DAYS)
        scored = sorted(((_score(ask, course, d), d) for d in open_now), key=lambda p: -p[0])
        best = [d for s, d in scored if s > 0 and s == scored[0][0]]
        if not best:
            listed = "; ".join(f"{d.course} {d.title}" for d in open_now[:8]) or "nothing"
            raise ToolError(f"Nothing on his list matches \"{what}\". Still on it: {listed}. Ask which he means.")
        if len(best) > 1 and args.get("all") is not True:
            raise ToolError("More than one matches: " + "; ".join(f"{d.course} {d.title}" for d in best) + ". Ask which, or all of them.")
        for d in best:
            cc.mark_done(d.key, title=d.title, course=d.course, now=now)
        names = ", ".join(f"{d.course} {d.title}" for d in best)
    refresh = getattr(ctx, "refresh", None)
    if refresh is not None:
        try:
            await refresh()
        except Exception:  # noqa: BLE001 - the hub catches up by itself within half a minute
            pass
    verb = "Back on his list" if args.get("done") is False else "Marked as done on his list"
    return Result(f"{verb}: {names}. One short line; this changes his own list only, nothing was submitted anywhere.")
