"""The Rail's own logic (HUD v2 §6.2, contracts v2 `rail`). The hub calls `refresh(state, now)` after every event.

The Rail tracks **things, not windows**. N0's reducers already dock windows into their slots, keep what Jarvis said
and put finished jobs under Jarvis; this module adds the things the hub knows about whether or not a window ever
showed them, and works out each slot's gauge:

    yes       approvals waiting for his yes (and ones that ran out, as Parked)
    today     today's classes, labs and blocks (the gauge arc is today's share done)
    homework  due items from the branch cards and open work threads (the arc is their average progress)
    messages  only what was docked there (no message contract yet)
    jarvis    running jobs; finished ones and the last 10 spoken lines are kept by the hub
    parked    things idle 7 days, folded here with `from` = their old slot; they come back when they want him

Rules: one item per ref in the whole Rail (a docked window and the thing it shows merge); nothing is removed here
except a window-less class or block of an earlier day that was done; the result is deterministic, so an event
that changes nothing on the Rail sends no `rail.updated`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .events import PARK_AFTER, SAID_MAX, SLOTS, parse_time

SEVERITY = {"done": 0, "parked": 1, "progress": 2, "jarvis": 3, "soon": 4, "yes": 5, "critical": 6}  # worst = highest
QUIET = 1.5  # an item with no state (upcoming, nothing needed) sorts after progress, before parked and done
WANTS_YOU = {"soon", "yes", "critical"}  # these come back out of Parked on their own
SOON = timedelta(hours=72)  # a due item this close is "Needs you soon" (the same 72 h the countdown window uses)
STARTING = timedelta(minutes=30)  # a class or block this close is "soon"
TIER_KEYS = ("tier",)


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


def _hour(when: datetime) -> str:
    """'Wed 8 pm', 'Thu 11:59 pm'."""
    clock = f"{when.hour % 12 or 12}{f':{when.minute:02d}' if when.minute else ''} {'am' if when.hour < 12 else 'pm'}"
    return f"{when:%a} {clock}"


def _clock(hhmm: str) -> str:
    """'16:00' -> '4 pm', '08:30' -> '8:30 am'."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    return f"{hour % 12 or 12}{f':{minute:02d}' if minute else ''} {'am' if hour < 12 else 'pm'}"


# ---- what the hub knows, as Rail items ------------------------------------------------------------------
def _approvals(state: dict) -> list[dict]:
    out = []
    for a in state.get("approvals", []):
        if a.get("status") == "pending":
            item = {"ref": a["id"], "slot": "yes", "kind": "approval", "title": a["title"], "at": a.get("asked") or state.get("now", ""),
                    "state": "yes", "detail": (a.get("consequences") or [""])[0]}
            if a.get("thumb"):
                item["thumb"] = a["thumb"]
            out.append(item)
    return out


def _today(state: dict, now: datetime) -> tuple[list[dict], float | None]:
    day = state.get("day") or {}
    items, counted, done = [], 0, 0
    for d in day.get("items", []):
        try:
            start = datetime.fromisoformat(f"{day['date']}T{d['start']}")
            end = datetime.fromisoformat(f"{day['date']}T{d['end']}")
        except (KeyError, ValueError):
            continue
        status = d.get("state", "planned")
        if status == "done":
            glance = "done"
        elif status in ("missed", "moved"):
            glance = "parked"  # dashed, like the dial's moved or missed arcs
        elif start <= now < end:
            glance = "progress"
        elif now < start <= now + STARTING:
            glance = "soon"
        else:
            glance = None
        if status != "moved":  # a moved block belongs to another day: it doesn't count against today
            counted += 1
            done += status == "done"
        detail = f"{_clock(d['start'])}" + (f" · {d['where']}" if d.get("where") else "")
        if status == "moved" and d.get("moved_to"):
            detail = d["moved_to"]
        item = {"ref": d["id"], "slot": "today", "kind": "event", "title": d["title"], "at": _iso(start), "detail": detail}
        if glance:
            item["state"] = glance
        if d.get("thumb"):
            item["thumb"] = d["thumb"]
        items.append(item)
    return items, (round(done / counted, 2) if counted else None)


def _homework(state: dict, now: datetime) -> tuple[list[dict], float | None]:
    tiers = {b["id"]: b.get("tier") for b in state.get("branches", [])}
    seen: dict[str, dict] = {}
    for card in (state.get("cards") or {}).values():
        for due in (card or {}).get("due", []):
            had = seen.get(due["id"])
            if had is None or len(due.get("title", "")) > len(had.get("title", "")):  # "GE 122 · PPS 7" over "PPS 7"
                seen[due["id"]] = due
    items, progress = [], []
    for due in sorted(seen.values(), key=lambda d: (d.get("due", ""), d["id"])):
        try:
            when = parse_time(due["due"])
        except (KeyError, ValueError):
            continue
        share = due.get("progress") or 0
        progress.append(min(max(share, 0), 1))
        if share >= 1:
            glance = "done"
        elif when <= now:
            glance = "critical"
        elif when - now <= SOON:
            glance = "soon"
        elif share > 0:
            glance = "progress"
        else:
            glance = None
        detail = ("Overdue since " if glance == "critical" else "Due ") + _hour(when) + (f" · {round(share * 100)}% done" if share else "")
        item = {"ref": due["id"], "slot": "homework", "kind": "due", "title": due["title"], "detail": detail}
        if glance:
            item["state"] = glance
        if due.get("thumb"):
            item["thumb"] = due["thumb"]
        if tiers.get(due.get("branch_id")) == 2:
            item["tier"] = 2
        items.append(item)
    for thread in state.get("threads", []):
        resume = thread.get("resume") or {}
        detail = " · ".join(x for x in (resume.get("label"), f"paused {_hour(parse_time(resume['at']))}" if resume.get("at") else None) if x)
        item = {"ref": thread.get("ref") or thread["id"], "slot": "homework", "kind": "thread", "title": thread["title"],
                "at": thread.get("updated") or resume.get("at") or state.get("now", ""), "state": "progress"}
        if detail:
            item["detail"] = detail
        if thread.get("thumb"):
            item["thumb"] = thread["thumb"]
        if tiers.get(thread.get("branch")) == 2:
            item["tier"] = 2
        items.append(item)
    return items, (round(sum(progress) / len(progress), 2) if progress else None)


def _jobs(state: dict) -> list[dict]:
    out = []
    for job in state.get("jobs", []):
        if job.get("state") == "running":
            item = {"ref": job["id"], "slot": "jarvis", "kind": "job", "title": job["label"], "state": "jarvis"}
            detail = job.get("detail") or (f"{round(job['progress'] * 100)}%" if isinstance(job.get("progress"), (int, float)) else None)
            if detail:
                item["detail"] = detail
            out.append(item)
    return out


# ---- putting it together -----------------------------------------------------------------------------------
def _index(rail: dict) -> dict[str, tuple[str, int]]:
    return {item["ref"]: (name, i) for name in SLOTS for i, item in enumerate(rail["slots"][name]["items"])}


def _fold(rail: dict, now: datetime) -> None:
    """Idle 7 days: into Parked, with `from` = its old slot (events.fold_idle's rule), except what wants him now."""
    parked = rail["slots"]["parked"]["items"]
    for name in SLOTS[:-1]:
        slot = rail["slots"][name]
        idle = [i for i in slot["items"] if i.get("state") not in WANTS_YOU and parse_time(i["at"]) + PARK_AFTER <= now]
        if idle:
            slot["items"] = [i for i in slot["items"] if i not in idle]
            parked += [{**i, "slot": "parked", "from": name, "state": "parked"} for i in idle]


def _worst(items: list[dict]) -> str | None:
    states = [item["state"] for item in items if item.get("state") in SEVERITY]
    return max(states, key=SEVERITY.__getitem__) if states else None


def refresh(state: dict, now: datetime) -> dict:
    """Bring the Rail up to date with what the hub knows, in place. Returns the Rail. Deterministic: run twice, same Rail."""
    rail = state.setdefault("rail", {"slots": {}})
    for name in SLOTS:
        rail.setdefault("slots", {}).setdefault(name, {"items": []}).setdefault("items", [])
    slots = rail["slots"]
    now_iso = _iso(now)

    today, today_done = _today(state, now)
    homework, homework_done = _homework(state, now)
    derived = [*_approvals(state), *today, *homework, *_jobs(state)]

    index = _index(rail)
    for fresh in derived:
        where = index.get(fresh["ref"])
        if where is None:  # new on the Rail
            fresh.setdefault("at", now_iso)
            slots[fresh["slot"]]["items"].append(fresh)
            index[fresh["ref"]] = (fresh["slot"], len(slots[fresh["slot"]]["items"]) - 1)
            continue
        name, i = where
        item = slots[name]["items"][i]
        if name == "parked":
            if fresh.get("state") in WANTS_YOU:  # it wants him again: out of Parked, back in its own slot, touched now
                slots[name]["items"][i] = None
                back = {**{k: v for k, v in item.items() if k not in ("from", "state")}, **fresh, "slot": item.get("from", fresh["slot"]), "at": now_iso}
                if back.get("window"):
                    back["window"] = {**back["window"], "slot": back["slot"]}
                slots[back["slot"]]["items"].append(back)
                index[fresh["ref"]] = (back["slot"], len(slots[back["slot"]]["items"]) - 1)
            else:  # still folded: only the words change
                for key in ("title", "detail"):
                    if key in fresh:
                        item[key] = fresh[key]
            continue
        # one item per ref: the docked window (if any) and the thing merge; the slot he docked it into stays
        for key in ("title", "detail", "state", "tier"):
            if key in fresh:
                item[key] = fresh[key]
            elif key in ("state", "tier"):
                item.pop(key, None)  # the thing's own state is the truth: one that has cleared clears here too
        if fresh.get("thumb") and not item.get("thumb"):
            item["thumb"] = fresh["thumb"]
    for slot in slots.values():
        slot["items"] = [item for item in slot["items"] if item is not None]

    # answered approvals have left (events.py); ones that ran out wait under Your yes as Parked
    expired = {a["id"] for a in state.get("approvals", []) if a.get("status") == "expired"}
    for item in slots["yes"]["items"]:
        if item["ref"] in expired:
            item["state"] = "parked"

    # yesterday's done classes and blocks leave Today (done is the one way off besides archive)
    todays = {item["ref"] for item in today}
    slots["today"]["items"] = [item for item in slots["today"]["items"]
                               if not (item.get("kind") == "event" and not item.get("window") and item["ref"] not in todays and item.get("state") == "done")]

    said = slots["jarvis"].get("said")
    if said is not None:
        slots["jarvis"]["said"] = said[:SAID_MAX]

    _fold(rail, now)

    for name in SLOTS:  # worst state first and done last, otherwise as they were (a stable sort, so nothing churns)
        slot = slots[name]
        slot["items"] = sorted(slot["items"], key=lambda item: -SEVERITY.get(item.get("state"), QUIET))
        worst = _worst(slot["items"])
        if worst:
            slot["worst"] = worst
        else:
            slot.pop("worst", None)
        slot.pop("done", None)
        if name != "parked":
            slot.pop("count", None)
    if today_done is not None:
        slots["today"]["done"] = today_done
    if homework_done is not None:
        slots["homework"]["done"] = homework_done
    slots["parked"]["count"] = len(slots["parked"]["items"])
    return rail
