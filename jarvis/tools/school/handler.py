"""school: his classes, due work and course facts from the local class files (jarvis.reach.classes). Read-only."""
from datetime import datetime, timedelta

from jarvis.reach.calendar import which_day
from jarvis.reach.classes import clock, when
from jarvis.tools.base import Result, ToolContext, ToolError


def _stamp(cc, name: str, what: str) -> str:
    at = cc.as_of(name)
    return f"({what} as of {at})" if at else ""


def _day(cc, args: dict, now: datetime) -> str:
    try:
        day = which_day(str(args.get("day") or "today"), now.date())
    except Exception as exc:  # noqa: BLE001 - which_day explains what it could not read
        raise ToolError(f"I couldn't tell which day you mean by {args.get('day')!r}. Use today, tomorrow, a weekday or a date like 2026-11-24.") from exc
    label = f"{day:%A} {day.day} {day:%B}"
    off = cc.no_class(day)
    if off:
        return f"No classes on {label}: {off}."
    meetings = cc.meetings_on(day)
    if not meetings:
        return f"No classes on {label}. {_stamp(cc, 'schedule.json', 'schedule')}".strip()
    return f"His classes on {label} {_stamp(cc, 'schedule.json', 'schedule')}:\n" + "\n".join(m.line() for m in meetings)


def _due(cc, args: dict, now: datetime) -> str:
    days = max(1, min(60, int(args.get("days") or 14)))
    wanted = cc.course(str(args["course"])) if args.get("course") else None
    due = [d for d in cc.due(now, days) if wanted is None or d.course == wanted["course"]]
    age = cc.homework_age_days(now)
    old = f" The list is {age} days old, so newer work may be missing." if age is not None and age >= 4 else ""
    scope = f" for {wanted['course']}" if wanted else ""
    if not due:
        return f"Nothing left to do{scope} in the next {days} days on his homework list {_stamp(cc, 'homework.json', 'list')}.{old}"
    return (f"Still to do{scope}, soonest first {_stamp(cc, 'homework.json', 'list')}:\n" + "\n".join(d.line(now) for d in due[:15])
            + (f"\n{old.strip()}" if old else ""))


def _course(cc, args: dict, now: datetime) -> str:
    asked = str(args.get("course") or "").strip()
    if not asked:
        raise ToolError("Which course? Give the code or a word of its title, like GE 122 or mechanics.")
    c = cc.course(asked)
    if c is None:
        raise ToolError(f"No course matches {asked!r}. His courses: {', '.join(x['course'] for x in cc.courses()) or 'none on file'}.")
    code = c["course"]
    lines = [" · ".join(p for p in (code, str(c.get("title") or ""), str(c.get("instructor") or "")) if p)]
    nxt = cc.next_meeting(code, now)
    if nxt:
        day, m = nxt
        label = "today" if day == now.date() else "tomorrow" if day == now.date() + timedelta(days=1) else f"{day:%A}"
        lines.append(f"Next class: {label} {m.line()}")
    for d in [d for d in cc.due(now, 21) if d.course == code][:5]:
        lines.append(f"Due: {d.line(now)}")
    graded = [a for a in c.get("assessments") or [] if isinstance(a, dict) and a.get("weight")]
    if graded:
        lines.append("Graded work: " + "; ".join(f"{a.get('title')} {a.get('weight')}%" for a in graded[:12]))
    for e in [e for e in c.get("exams") or [] if isinstance(e, dict)][:6]:
        at = None
        try:
            at = datetime.fromisoformat(str(e.get("start"))).replace(tzinfo=None)
        except (TypeError, ValueError):
            pass
        bits = [str(e.get("title") or "Exam"), f"{at:%a %b} {at.day} {clock(at)}" if at else "date not set",
                str(e.get("location") or ""), f"{e.get('weight')}%" if e.get("weight") else ""]
        lines.append("Exam: " + " · ".join(b for b in bits if b))
    return "\n".join(lines) + f"\n{_stamp(cc, 'courses.json', 'syllabus facts')}"


def _exams(cc, args: dict, now: datetime) -> str:
    days = max(1, min(60, int(args.get("days") or 30)))
    wanted = cc.course(str(args["course"])) if args.get("course") else None
    rows = [(code, e, at) for code, e, at in cc.exams(now, days) if wanted is None or code == wanted["course"]]
    if not rows:
        return f"No tests in the next {days} days in his syllabi {_stamp(cc, 'courses.json', 'syllabi')}."
    return f"Tests in the next {days} days {_stamp(cc, 'courses.json', 'syllabi')}:\n" + "\n".join(
        " · ".join(b for b in (code, str(e.get("title") or "Exam"), when(at, now), str(e.get("location") or ""),
                               f"{e.get('weight')}%" if e.get("weight") else "") if b) for code, e, at in rows[:15])


async def run(args: dict, ctx: ToolContext) -> Result:
    cc = ctx.classes
    now = datetime.now()
    about = str(args.get("about") or "day").lower()
    pick = {"day": _day, "due": _due, "course": _course, "exams": _exams}.get(about)
    if pick is None:
        raise ToolError("about must be one of: day, due, course, exams.")
    return Result(pick(cc, args, now))
