"""Move the demo day to the real clock (HUD v2 §11), so it looks real at any time of day.

The demo fixture is written for Monday 2026-11-16 at 3:40 pm. In the live demo it moves to `now` in three ways:

- **Calendar things move by whole days**, so they keep their real clock times: deadlines (8 pm, 11:59 pm),
  classes and labs, quiet hours, events on other days, and every day word written in text.
- **Later days move by class days** (`class_day`): the fixture's Tuesday is the next weekday after today, its
  Wednesday the one after that, and so on, so lectures, labs, tutorials and quizzes never land on a weekend, and
  everything planned around them (and every deadline) keeps its order and its weekday-ness. On a Saturday "Tue
  10:00 am · Lecture 22" becomes "Mon 10:00 am", "Wed 8 pm" becomes "Tue 8 pm"; the fixture's Sunday deadline
  stays on a weekend. Today and the past move by whole days, and **on a weekend there are no classes today.**
- **Things relative to now keep their offset from now** (the shift rounded to 5 minutes): what was added or
  synced minutes ago, spoken lines, the approval asked a minute ago. Older history (receipts, facts learned,
  paused threads) moves by whole days too, and back one more day if that would put it after now.
- **Today is planned again at the real time:** earlier classes are done, Jarvis's own study blocks keep their
  time if it's still ahead, otherwise move to the next free slot today (never into quiet hours), otherwise to
  tomorrow ("Moved to 11:30 am tomorrow."). Next up, the day dial, the day count and the Rail follow.

Used only in the live demo (app.py). Screenshot scenes and tests stay frozen at the fixture date.
Times are local, naive ISO (the hub follows Windows' time zone; Saskatoon is UTC−6 all year).
"""
from __future__ import annotations

import copy
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from ..rail import refresh

ISO = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")
HHMM = re.compile(r"^\d{2}:\d{2}$")
STEP = timedelta(minutes=5)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SHORT = {"Mon": 0, "Tue": 1, "Tues": 1, "Wed": 2, "Thu": 3, "Thurs": 3, "Fri": 4, "Sat": 5, "Sun": 6}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
RELATIVE = {"today": 0, "tonight": 0, "tomorrow": 1, "yesterday": -1}
PERIODS = {"morning": 9, "afternoon": 15, "evening": 19, "night": 21}


def _period(when: datetime) -> str:
    if when.hour < 5 or when.hour >= 21:
        return "night"
    return "morning" if when.hour < 12 else "afternoon" if when.hour < 17 else "evening"

_DAY = (r"(?P<day>\b(?:" + "|".join(WEEKDAYS) + "|" + "|".join(sorted(SHORT, key=len, reverse=True))
        + r"|[Tt]oday|[Tt]onight|[Tt]omorrow|[Yy]esterday)\b|\b(?:" + "|".join(MONTHS) + r") \d{1,2}\b)")
_T = r"\d{1,2}(?::\d{2})?\s?(?:am|pm)\b|\d{1,2}:\d{2}\b|noon\b|midnight\b"
PHRASE = re.compile(
    rf"{_DAY}(?:(?P<sep>,? (?:at )?)(?P<t1>{_T})(?P<rng> to (?P<t2>{_T}))?| (?P<per>morning|afternoon|evening|night)\b)?"
    rf"|(?P<lt1>\b\d{{1,2}}(?::\d{{2}})?\s?(?:am|pm)\b|\b\d{{1,2}}:\d{{2}}(?= to ))(?P<lrng> to (?P<lt2>{_T}))?(?P<lday> (?:today|tonight|tomorrow|yesterday)\b)?"
)

# Text that states a rule or a preference, not a moment: never moved.
KEEP_PATHS = (re.compile(r"^facts\.\d+\.basis$"), re.compile(r"^metrics\.self_report\."), re.compile(r"^settings\.quiet_hours\."))
SKIP_KEYS = frozenset({"id", "ref", "branch_id", "branch", "src", "path", "kind", "target", "action", "glyph", "parent",
                       "state", "category", "type", "slot", "from", "mode", "v"})
KEEP_TEXT = re.compile(r"\b(?:before|after|until) \d{1,2}(?::\d{2})? ?(?:am|pm)\b(?! (?:today|tonight|tomorrow))")


def round_delta(delta: timedelta, step: timedelta = STEP) -> timedelta:
    return step * round(delta / step) if step else delta


def delta_for(fixture_now: datetime, now: datetime, step: timedelta = STEP) -> timedelta:
    return round_delta(now - fixture_now, step)


Move = Callable[[date], date]


def _moved(when: datetime, delta: timedelta, move: Move | None) -> datetime:
    """`when` + `delta`, or, with `move`, on the day `move` gives and the part of `delta` under a day."""
    if move is None:
        return when + delta
    return datetime.combine(move(when.date()), when.time()) + (delta - timedelta(days=delta.days))


def class_day(fixture_day: date, day: date, today: date) -> date:
    """Where a day of the fixture lands when the fixture's `fixture_day` becomes `today`. Today and the past move by
    whole days. A later weekday becomes the same number of weekdays after today, so classes stay on weekdays and
    everything keeps its order; a later Saturday or Sunday stays that many days after its (moved) Friday."""
    if day <= fixture_day:
        return today + (day - fixture_day)
    if day.weekday() >= 5:
        friday = day - timedelta(days=day.weekday() - 4)
        return (class_day(fixture_day, friday, today) if friday > fixture_day else today + (friday - fixture_day)) + (day - friday)
    weekdays = sum(1 for n in range(1, (day - fixture_day).days + 1) if (fixture_day + timedelta(days=n)).weekday() < 5)
    out = today
    while weekdays:
        out += timedelta(days=1)
        weekdays -= out.weekday() < 5
    return out


def next_class_day(today: date) -> date:
    """The first weekday after `today`: where the fixture's tomorrow (Tuesday) lands."""
    out = today + timedelta(days=1)
    while out.weekday() >= 5:
        out += timedelta(days=1)
    return out


def shift_iso(value: str, delta: timedelta, move: Move | None = None) -> str:
    """Shift one ISO date-time, keeping its precision and any offset."""
    match = ISO.match(value)
    if not match:
        return value
    seconds, offset = match.group(4), match.group(6) or ""
    when = _moved(datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}:{match.group(3)}:{seconds or '00'}"), delta, move)
    return when.isoformat(timespec="seconds" if seconds is not None else "minutes") + offset


# --- times in words --------------------------------------------------------------------------------------------
def _parse_time(text: str, meridiem: str | None = None) -> tuple[int, int, bool, str | None]:
    """'8 pm' → (20, 0, False, 'pm'); '7:00' with meridiem 'pm' → (19, 0, True, 'pm'); 'noon' → (12, 0, False, None)."""
    text = text.strip()
    if text == "noon":
        return 12, 0, False, None
    if text == "midnight":
        return 0, 0, False, None
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s?(am|pm)?", text)
    hour, minute, ap = int(match.group(1)), int(match.group(2) or 0), match.group(3) or meridiem
    if ap is None:  # a bare "9:00" with nothing to go by: daytime hours
        ap = "am" if 7 <= hour <= 11 else "pm"
    hour = hour % 12 + (12 if ap == "pm" else 0)
    return hour, minute, match.group(2) is not None, match.group(3)


def _say_time(when: datetime, with_minutes: bool, meridiem: bool = True) -> str:
    hour = when.hour % 12 or 12
    minutes = f":{when.minute:02d}" if (with_minutes or when.minute) else ""
    return f"{hour}{minutes}" + (f" {'am' if when.hour < 12 else 'pm'}" if meridiem else "")


def _anchor(day_word: str, fixture: datetime) -> date:
    """The fixture date a day word means: weekdays fall from two days before to four days after the fixture day."""
    word = day_word.strip()
    if word.lower() in RELATIVE:
        return fixture.date() + timedelta(days=RELATIVE[word.lower()])
    if word[:3] in MONTHS and " " in word:
        return date(fixture.year, MONTHS.index(word[:3]) + 1, int(word.split()[1]))
    weekday = WEEKDAYS.index(word) if word in WEEKDAYS else SHORT[word]
    return fixture.date() + timedelta(days=(weekday - fixture.weekday() + 2) % 7 - 2)


def _say_day(word: str, when: datetime, now: datetime) -> str:
    """Say the shifted day in the same style as the original word."""
    capital = word[:1].isupper()
    if word.lower() in RELATIVE:
        days = (when.date() - now.date()).days
        out = {0: "tonight" if (word.lower() == "tonight" and when.hour >= 17) else "today", 1: "tomorrow", -1: "yesterday"}.get(days)
        out = out or when.strftime("%A")
    elif word[:3] in MONTHS and " " in word:
        out = f"{when:%b} {when.day}"
    elif word in WEEKDAYS:
        out = when.strftime("%A")
    else:
        out = when.strftime("%a")
    return out[:1].upper() + out[1:] if capital else out


def shift_text(text: str, fixture: datetime, delta: timedelta, move: Move | None = None) -> str:
    """Move every time and day written in words in `text` by `delta` (days by `move`, if given)."""
    if KEEP_TEXT.search(text):
        return text
    now = fixture + delta

    def at(day: date, hour: int = 0, minute: int = 0) -> datetime:
        return _moved(datetime.combine(day, time(hour, minute)), delta, move)

    def one(m: re.Match) -> str:
        if m.group("day"):
            day = _anchor(m.group("day"), fixture)
            if m.group("per"):  # "Wednesday evening": the day and the part of it both move
                when = at(day, PERIODS[m.group("per")])
                return f"{_say_day(m.group('day'), when, now)} {_period(when)}"
            if not m.group("t1"):  # a day on its own moves with the clock's own time of day
                return _say_day(m.group("day"), at(day, fixture.hour, fixture.minute), now)
            t2 = _parse_time(m.group("t2")) if m.group("t2") else None
            h, mi, mins, _ = _parse_time(m.group("t1"), t2[3] if t2 else None)
            start = at(day, h, mi)
            out = _say_day(m.group("day"), start, now) + m.group("sep") + _range(start, mins, t2, at(day, *t2[:2]) if t2 else None)
            return out
        t2 = _parse_time(m.group("lt2")) if m.group("lt2") else None
        h, mi, mins, _ = _parse_time(m.group("lt1"), t2[3] if t2 else None)
        day = _anchor(m.group("lday").strip(), fixture) if m.group("lday") else fixture.date()
        start = at(day, h, mi)
        out = _range(start, mins, t2, at(day, *t2[:2]) if t2 else None)
        if m.group("lday"):
            out += " " + _say_day(m.group("lday").strip(), start, now)
        return out

    return PHRASE.sub(one, text)


def _range(start: datetime, with_minutes: bool, t2: tuple | None, end: datetime | None) -> str:
    if not t2 or end is None:
        return _say_time(start, with_minutes)
    same = (start.hour < 12) == (end.hour < 12)
    return f"{_say_time(start, with_minutes, meridiem=not same)} to {_say_time(end, t2[2])}"


# --- the whole state -------------------------------------------------------------------------------------------
def _walk(value, path: str, fn):
    if isinstance(value, dict):
        return {k: _walk(v, f"{path}.{k}" if path else k, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, f"{path}.{i}", fn) for i, v in enumerate(value)]
    if isinstance(value, str):
        return fn(value, path)
    return value


def shift(value, delta: timedelta, fixture: datetime | None = None, move: Move | None = None):
    """Shift every ISO time in any JSON-like value (a state, a script step). With `fixture`, words too. With `move`,
    days move by it (`class_day`) instead of by `delta`'s whole days."""
    def one(text: str, path: str) -> str:
        if ISO.match(text):
            return shift_iso(text, delta, move)
        key = path.rsplit(".", 1)[-1]
        if fixture is None or HHMM.match(text) or key in SKIP_KEYS or any(k.search(path) for k in KEEP_PATHS):
            return text
        return shift_text(text, fixture, delta, move)
    return _walk(value, "", one)


def greeting(now: datetime) -> str:
    return "Good morning" if 4 <= now.hour < 12 else "Good afternoon" if 12 <= now.hour < 17 else "Good evening"


def day_shift(fixture: datetime, now: datetime) -> timedelta:
    """Whole days from the fixture's day to today: what calendar things move by."""
    return timedelta(days=(now.date() - fixture.date()).days)


# --- planning today again at the real time ---------------------------------------------------------------------
RECENT = timedelta(minutes=30)     # history this close to the fixture's now keeps its age ("two minutes ago")
STUDY_FROM = time(9, 0)            # his own rule (fact f-8am): no study blocks before 9 am
LEAD = timedelta(minutes=15)       # a block that has to move starts at least this long after now, on the half hour
STEP_SLOT = timedelta(minutes=30)
FIXED = frozenset({"class", "lab", "own", "laundry"})  # what Jarvis plans around and never moves
AFTER = {"d-review": "d-ge"}       # a review comes after the lecture it reviews
DIAL_BEFORE, DIAL_AHEAD = timedelta(hours=1), timedelta(hours=11)  # the dial: an hour ago to 11 hours ahead
PAWS = {"kind": "paws", "label": "PAWS"}
# Tomorrow in the fixture (Tue Nov 17), from the GE 122 and CHEM 142 cards, the CHEM pre-lab review that moved to
# 4 pm tomorrow and the laundry proposal (9 to 10 am). `busy` ones are only planned around.
TOMORROW = (
    {"id": "d-ge22", "start": "10:00", "end": "11:20", "title": "GE 122 lecture 22 · Trusses", "kind": "class",
     "where": "ENGR 1A10", "source": PAWS},
    {"id": "d-chem5", "start": "13:30", "end": "15:20", "title": "CHEM 142 lab 5", "kind": "lab",
     "where": "Thorvaldson 173", "source": PAWS},
    {"id": "d-chemrev", "start": "16:00", "end": "16:30", "busy": True},
    {"id": "p-laundry", "start": "09:00", "end": "10:00", "busy": True},
)
SPOKEN = {"d-review": "The review of lecture 21", "d-pps": "Your PPS 7 block", "d-math": "MATH 133",
          "d-ge": "GE 122 lecture 21", "d-lunch": "Lunch with Sam", "d-chem": "Lab four", "d-ge22": "GE 122 lecture 22",
          "d-chem5": "Lab five"}


def _at(day: date, hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hour, minute))


def _ceil(when: datetime, step: timedelta = STEP_SLOT) -> datetime:
    base = datetime.combine(when.date(), time())
    return base + step * -(-(when - base) // step)


def _hm(when: datetime) -> str:
    """The now card's time style: '4:00 pm'."""
    return f"{when.hour % 12 or 12}:{when.minute:02d} {'am' if when.hour < 12 else 'pm'}"


def _quiet(state: dict) -> tuple[time, time] | None:
    q = (state.get("settings") or {}).get("quiet_hours") or {}
    if not q.get("on") or not q.get("from") or not q.get("to"):
        return None
    return time.fromisoformat(q["from"]), time.fromisoformat(q["to"])


def in_quiet(state: dict, when: datetime) -> bool:
    q = _quiet(state)
    if not q:
        return False
    start, end = q
    return (when.time() >= start or when.time() < end) if start > end else start <= when.time() < end


def latest(state: dict, day: date) -> datetime:
    """Study blocks end before quiet hours start (11 pm without them)."""
    q = _quiet(state)
    return datetime.combine(day, q[0] if q and q[0] > q[1] else time(23))


def free_slot(busy: list[tuple[datetime, datetime]], start: datetime, length: timedelta, until: datetime) -> datetime | None:
    """The first half-hour start at or after `start` where a block of `length` fits before `until`."""
    when = _ceil(start)
    while when + length <= until:
        clashes = [end for s, end in busy if s < when + length and when < end]
        if not clashes:
            return when
        when = _ceil(max(clashes))
    return None


def busy_today(state: dict, ignore: str = "") -> list[tuple[datetime, datetime]]:
    """Today's taken time: everything on the day that hasn't moved to another day."""
    day = date.fromisoformat(state["day"]["date"])
    return [(_at(day, i["start"]), _at(day, i["end"])) for i in state["day"]["items"] if i.get("state") != "moved" and i["id"] != ignore]


def expiry(state: dict, asked: datetime, window: timedelta) -> datetime:
    """An approval keeps its window from when it was asked; one that would run out in quiet hours waits for 9 am."""
    when = asked + window
    if not in_quiet(state, when):
        return when
    morning = datetime.combine(when.date(), STUDY_FROM)
    return morning if when < morning else morning + timedelta(days=1)


def _plan(state: dict, now: datetime) -> list[dict]:
    """Plan today again at `now` (in place). Returns the next days' items, each with a `when` and `until`: the
    fixture's tomorrow (lecture 22, lab 5 and what's planned around them) on the next class day, and any block that
    had to roll over, tomorrow."""
    day = state["day"]
    today, tomorrow, class_next = now.date(), now.date() + timedelta(days=1), next_class_day(now.date())
    if today.weekday() >= 5:  # a weekend: no lectures or labs today; his own things and Jarvis's blocks stay
        day["items"] = [i for i in day["items"] if i["kind"] not in ("class", "lab")]
        for item in day["items"]:
            if item["id"] == "d-review":
                item["why"] = "While lecture 21 is still fresh."
    items = day["items"]
    by_id = {i["id"]: i for i in items}
    for item in items:  # classes, labs and his own things keep their time: done once they're over
        if item["kind"] in FIXED and item.get("state", "planned") in ("planned", "done"):
            item["state"] = "done" if _at(today, item["end"]) <= now else "planned"
    later = [{**t, "when": _at(class_next, t["start"]), "until": _at(class_next, t["end"])} for t in TOMORROW]
    blocks = sorted((i for i in items if i["kind"] not in FIXED and i.get("state", "planned") == "planned"), key=lambda i: i["start"])
    keep = [b for b in blocks if _at(today, b["end"]) > now]
    busy = [(_at(today, i["start"]), _at(today, i["end"])) for i in items if i.get("state") != "moved" and (i["kind"] in FIXED or i in keep)]
    after = now + LEAD
    for block in [b for b in blocks if b not in keep]:  # their time has passed: the next free slot today, or tomorrow
        length = _at(today, block["end"]) - _at(today, block["start"])
        start = max(after, datetime.combine(today, STUDY_FROM))
        if block["id"] in AFTER and AFTER[block["id"]] in by_id:
            start = max(start, _at(today, by_id[AFTER[block["id"]]]["end"]))
        when = free_slot(busy, start, length, latest(state, today))
        if when:
            block.update(start=f"{when:%H:%M}", end=f"{when + length:%H:%M}")
            busy.append((when, when + length))
            after = when + length
            continue
        taken = [(t["when"], t["until"]) for t in later]
        when = free_slot(taken, datetime.combine(tomorrow, STUDY_FROM), length, latest(state, tomorrow))
        if when is None:  # tomorrow is full too (never in the fixture): it stays where it was, missed
            block["state"] = "missed"
            continue
        block["state"], block["moved_to"] = "moved", f"Moved to {_say_time(when, False)} tomorrow."
        later.append({**block, "busy": False, "when": when, "until": when + length, "rolled": True})
    return sorted(later, key=lambda t: t["when"])


def _next(state: dict, now: datetime, later: list[dict]) -> tuple[dict, datetime, bool] | None:
    """The next thing on his day: (item, start, is it tomorrow)."""
    today = date.fromisoformat(state["day"]["date"])
    ahead = [(_at(today, i["start"]), i) for i in state["day"]["items"] if i.get("state", "planned") == "planned" and _at(today, i["start"]) > now]
    if ahead:
        start, item = min(ahead, key=lambda a: a[0])
        return item, start, False
    nxt = next((t for t in later if not t.get("busy")), None)
    return (nxt, nxt["when"], True) if nxt else None


def _dial(state: dict, now: datetime, later: list[dict], nxt: tuple | None) -> list[dict]:
    today = date.fromisoformat(state["day"]["date"])
    arcs, ours = [], {i["id"] for i in state["day"]["items"]}
    spans = [(i, _at(today, i["start"]), _at(today, i["end"]), i.get("state") == "moved") for i in state["day"]["items"]]
    spans += [(t, t["when"], t["until"], False) for t in later if not t.get("busy")]
    for item, start, end, moved in sorted(spans, key=lambda s: s[1]):
        if end < now - DIAL_BEFORE or start > now + DIAL_AHEAD:
            continue
        if moved:
            status = "moved"
        elif item.get("state") == "done" or end <= now:
            status = "done"
        elif start <= now:
            status = "now"
        elif nxt and nxt[0]["id"] == item["id"]:
            status = "next"
        else:
            status = "upcoming"
        arc = {"id": f"dial-{item['id'].removeprefix('d-')}{'-was' if moved else ''}", "kind": item["kind"],
               "start": start.isoformat(timespec="seconds"), "end": end.isoformat(timespec="seconds"), "title": item["title"],
               "where": item.get("where") or "Your desk", "state": status}
        if item["id"] in ours:  # tomorrow's classes aren't day items yet: no ref
            arc["ref"] = item["id"]
        arcs.append(arc)
    for due in _dues(state):  # deadlines on the face: a diamond at the time it's due (a triangle once overdue)
        when = datetime.fromisoformat(due["due"])
        if not now - DIAL_BEFORE <= when <= now + DIAL_AHEAD:
            continue
        status = "done" if (due.get("progress") or 0) >= 1 else "overdue" if when <= now else "upcoming"
        arcs.append({"id": f"dial-{due['id']}", "kind": "due", "start": when.isoformat(timespec="seconds"), "title": due["title"],
                     "state": status, "ref": due["id"]})
    return sorted(arcs, key=lambda a: a["start"])


def _dues(state: dict) -> list[dict]:
    """Every due item on the branch cards, once (the longest title: "GE 122 · PPS 7" over "PPS 7"), as the Rail's
    Homework slot lists them."""
    seen: dict[str, dict] = {}
    for card in (state.get("cards") or {}).values():
        for due in (card or {}).get("due", []):
            if due["id"] not in seen or len(due.get("title", "")) > len(seen[due["id"]].get("title", "")):
                seen[due["id"]] = due
    return sorted(seen.values(), key=lambda d: (d.get("due", ""), d["id"]))


def _loop_slot(start: datetime, end: datetime, now: datetime) -> str:
    """'Tonight 7:00 to 8:30 pm', 'Tomorrow 4:30 to 6:00 pm', 'Today 9:30 to 11:00 am'."""
    word = "Tomorrow" if start.date() > now.date() else "Tonight" if start.hour >= 17 else "Today"
    same = (start.hour < 12) == (end.hour < 12)
    return f"{word} {_say_time(start, True, meridiem=not same)} to {_say_time(end, True)}"


def _said(item: dict, start: datetime, at: datetime, lab_done: bool) -> str:
    """Jarvis's last spoken line about the day, true at the moment he said it."""
    days = (start.date() - at.date()).days
    when = (f"tonight at {_say_time(start, False)}" if start.hour >= 18 else f"at {_say_time(start, False)}") if days == 0 \
        else f"tomorrow at {_say_time(start, False)}"
    head = "Lab four's done. " if lab_done else ""
    return f"{head}{SPOKEN.get(item['id'], item['title'].split(' · ')[0])} is {when}."


def rebase_state(state: dict, now: datetime | None = None, step: timedelta = STEP) -> dict:
    """The demo state moved to `now` (default: the real local time). The input is not changed."""
    fixture = datetime.fromisoformat(state["now"])
    now = (now or datetime.now()).replace(microsecond=0)
    days, rel = day_shift(fixture, now), delta_for(fixture, now, step)
    move = (lambda day: class_day(fixture.date(), day, now.date())) if days else None  # noqa: E731
    out = shift(copy.deepcopy(state), days, fixture, move)  # calendar things: whole (class) days, so clock times stay real
    out["now"] = now.isoformat(timespec="seconds")

    def past(value: str) -> tuple[str, timedelta]:
        """History: recent things keep their age; older ones move by whole days, and never land after now."""
        when = datetime.fromisoformat(value)
        if fixture - when <= RECENT:
            return shift_iso(value, rel), rel
        if when + days > now - timedelta(minutes=5):
            return shift_iso(value, days - timedelta(days=1)), days - timedelta(days=1)
        return shift_iso(value, days), days

    def labels(old: dict, new: dict, moved: timedelta) -> None:
        """'You · today' follows its own time when that moved back a day."""
        if moved == days:
            return
        for src_old, src_new in zip([old.get("source"), *(old.get("sources") or [])], [new.get("source"), *(new.get("sources") or [])], strict=True):
            if src_old and src_new and src_old.get("label"):
                src_new["label"] = shift_text(src_old["label"], fixture, moved)

    if state.get("now_card", {}).get("updated"):
        out["now_card"]["updated"] = shift_iso(state["now_card"]["updated"], rel)
    for old, new in zip(state.get("facts", []), out.get("facts", []), strict=True):
        moved = days
        if old.get("learned"):
            new["learned"], moved = past(old["learned"])
        if old.get("last_confirmed"):
            new["last_confirmed"] = past(old["last_confirmed"])[0]
        labels(old, new, moved)
    for old, new in zip(state.get("actions", []), out.get("actions", []), strict=True):
        new["ts"], moved = past(old["ts"])
        if (old.get("undo") or {}).get("until"):
            new["undo"]["until"] = shift_iso(old["undo"]["until"], moved)  # still "undo for 24 hours" from the receipt
        labels(old, new, moved)
    for old, new in zip(state.get("approvals", []), out.get("approvals", []), strict=True):
        if old.get("asked"):
            new["asked"] = shift_iso(old["asked"], rel)
            if old.get("expires"):
                window = datetime.fromisoformat(old["expires"]) - datetime.fromisoformat(old["asked"])
                new["expires"] = expiry(out, datetime.fromisoformat(new["asked"]), window).isoformat(timespec="seconds")
    for old, new in zip(state.get("threads", []), out.get("threads", []), strict=True):
        for key in ("updated",):
            if old.get(key):
                new[key] = past(old[key])[0]
        if (old.get("resume") or {}).get("at"):
            new["resume"]["at"] = past(old["resume"]["at"])[0]
    for ref, mark in (state.get("marks") or {}).items():
        if mark.get("at"):
            out["marks"][ref]["at"] = past(mark["at"])[0]
    for name, slot in ((state.get("rail") or {}).get("slots") or {}).items():
        for old, new in zip(slot.get("items", []), out["rail"]["slots"][name]["items"], strict=True):
            if old.get("at") and (name != "today" or fixture - datetime.fromisoformat(old["at"]) <= RECENT):
                new["at"] = past(old["at"])[0]
        for old, new in zip(slot.get("said", []), out["rail"]["slots"][name].get("said", []), strict=True):
            new["at"] = past(old["at"])[0]

    for name, card in (state.get("cards") or {}).items():  # an open loop's slot ("Wed 10:00 to 11:30 am") is a time too
        for old, new in zip(card.get("open_loops", []), out["cards"][name].get("open_loops", []), strict=True):
            if old.get("slot"):
                new["slot"] = shift_text(old["slot"], fixture, days, move)
    if out.get("day"):
        _replan(out, now)
    if out.get("now_card", {}).get("greeting"):
        out["now_card"]["greeting"] = greeting(now)
    if "rail" in out:
        refresh(out, now)  # the hub's own Rail rules, so the Rail matches the moved day
    return out


def _replan(out: dict, now: datetime) -> None:
    out["day"]["date"] = now.date().isoformat()
    later = _plan(out, now)
    nxt = _next(out, now, later)
    today = now.date()
    items = out["day"]["items"]
    if "dial" in out["day"]:
        out["day"]["dial"] = _dial(out, now, later, nxt)
    card = out.get("now_card")
    if card:
        counted = [i for i in items if i.get("state") != "moved"]
        done = [i for i in counted if i.get("state") == "done"]
        card["day"] = {"done": len(done), "total": len(counted)}
        card["done_today"] = [i["title"].split(" · ")[0] for i in done]
        if nxt:
            item, start, tomorrow = nxt
            word = "Tomorrow" if start.date() == today + timedelta(days=1) else f"{start:%a}"
            up = {"title": item["title"], "when": f"{word} {_hm(start)}" if tomorrow else _hm(start),
                  "where": item.get("where") or "Your desk", "source": item["source"]}
            if item.get("thumb"):
                up["thumb"] = item["thumb"]
            card["next_up"] = up
        else:
            card.pop("next_up", None)
    pps = next((i for i in items if i["id"] == "d-pps"), None)
    if pps:  # the GE 122 open loop names the PPS 7 block's time
        rolled = next((t for t in later if t["id"] == "d-pps"), None)
        start, end = (rolled["when"], rolled["until"]) if rolled else (_at(today, pps["start"]), _at(today, pps["end"]))
        for loop in ((out.get("cards") or {}).get("ge-122") or {}).get("open_loops", []):
            if loop.get("text", "").startswith("Finish PPS 7"):
                loop["slot"] = _loop_slot(start, end, now)
    said = ((out.get("rail") or {}).get("slots") or {}).get("jarvis", {}).get("said") or []
    if said and said[0].get("text", "").startswith("Lab four's done"):  # what Jarvis last said about the day
        at = datetime.fromisoformat(said[0]["at"])
        upcoming = _next(out, at, later)
        lab = next((i for i in items if i["id"] == "d-chem"), None)
        if upcoming:
            said[0]["text"] = _said(upcoming[0], upcoming[1], at, bool(lab) and _at(today, lab["end"]) <= at)
