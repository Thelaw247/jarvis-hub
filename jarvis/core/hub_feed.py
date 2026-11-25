"""What fills the live hub (v0.18.0). Until now the core's state started empty and stayed empty.

Three feeds, each one reducer event the hub already understands:

- Today and the Now card: his classes and due work from the files his study skills keep (jarvis.reach.classes:
  local, a millisecond, works offline), then his Google Calendar on top when it is connected (read-only, in the
  background, never in the way of a turn).
- The Life tree and Memory: branches, cards and facts straight from the memory store, plus his courses from the
  class files when memory has no branch for them yet (shown, never written: memory is only written by its own rules).
- Under the hood: real response times from the voice log, and which sources are working and how fresh they are.

The same day is handed to the talker as its now card text (`now_text`), so "what's my next class", "what room",
"what's due" are answered from the prompt with no tool round (about 0.5 to 1.5 s saved each time).

Everything here reads. Nothing is published unless it changed. A feed that fails says so in Under the hood and the
others carry on.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.reach import classes as cls
from jarvis.reach.classes import ClassContent, Due, clock, slug, when

log = logging.getLogger("jarvis.core.feed")

LOCAL_EVERY_S = 30.0        # the files and the clock: cheap, so the "next" line never lags a class ending
CALENDAR_EVERY_S = 300.0    # his Google Calendar, when connected
METRICS_EVERY_S = 60.0
LATENCY_TURNS = 200         # Under the hood looks at the most recent turns
COURSE = re.compile(r"\b([A-Za-z]{2,5})\s?-?(\d{3})\b")
BLOCK_WORDS = ("preview", "review", "homework", "study", "prep", "practice", "session")


def course_in(text: str) -> str | None:
    m = COURSE.search(text or "")
    return f"{m.group(1).upper()} {m.group(2)}" if m else None


def paws(cc: ClassContent) -> dict[str, str]:
    stamp = cc.as_of("schedule.json")
    return {"kind": "paws", "label": f"PAWS · {stamp}" if stamp else "PAWS"}


def day_items(cc: ClassContent | None, events: list[Any], now: datetime) -> list[dict[str, Any]]:
    """His day as contracts/day.schema.json items: classes and labs from the files, calendar events merged on top
    (a calendar copy of a class only adds its room; his own events and planner blocks are added)."""
    hhmm = f"{now:%H:%M}"
    items: list[dict[str, Any]] = []
    if cc is not None:
        source = paws(cc)
        for m in cc.meetings_on(now.date()):
            item = {"id": f"c-{slug(m.course)}-{m.start.replace(':', '')}", "start": m.start, "end": m.end,
                    "title": f"{m.course} {'lab' if m.kind == 'lab' else 'lecture'}", "kind": m.kind, "source": source,
                    "state": "done" if m.end <= hhmm else "planned", "branch_id": slug(m.course)}
            if m.where:
                item["where"] = m.where
            items.append(item)
    for e in events:
        if getattr(e, "start", None) is None or e.day != now.date():
            continue   # all-day events have no place on the day's timeline
        start, end = f"{e.start:%H:%M}", f"{e.end:%H:%M}" if e.end else f"{e.start + timedelta(minutes=30):%H:%M}"
        course, low = course_in(e.title), e.title.lower()
        same = next((i for i in items if i["start"] == start and course and i.get("branch_id") == slug(course)
                     and i["kind"] in ("class", "lab")), None)
        if same is not None:
            if e.where and not same.get("where"):
                same["where"] = e.where
            continue
        kind = "laundry" if "laundry" in low else "lab" if course and "lab" in low and "prep" not in low \
            else "block" if any(w in low for w in BLOCK_WORDS) else "class" if course and "lecture" in low else "own"
        item = {"id": f"g-{start.replace(':', '')}-{slug(e.title)[:24] or 'event'}", "start": start, "end": end,
                "title": e.title, "kind": kind, "source": {"kind": "calendar", "label": "Google Calendar"},
                "state": "done" if end <= hhmm else "planned"}
        if e.where:
            item["where"] = e.where
        if course:
            item["branch_id"] = slug(course)
        items.append(item)
    items.sort(key=lambda i: (i["start"], i["end"], i["id"]))
    seen: set[str] = set()
    for i in items:   # ids stay unique even with two events at one minute
        while i["id"] in seen:
            i["id"] += "x"
        seen.add(i["id"])
    return items


def due_source(d: Due) -> dict[str, str]:
    low = d.platform.lower()
    kind = "crowdmark" if "crowdmark" in low else "canvas" if "canvas" in low else "syllabus"
    return {"kind": kind, "label": d.platform.split("(")[0].strip() or "Homework list"}


def now_context(items: list[dict[str, Any]], due: list[Due], now: datetime, *, note: str | None = None) -> Any:
    """What the now card needs from outside memory (jarvis.memory.model.NowContext)."""
    from jarvis.memory.model import NowContext  # noqa: PLC0415

    hhmm = f"{now:%H:%M}"
    ahead = [i for i in items if i["end"] > hhmm]
    events = []
    for i in ahead[:3]:
        on = i["start"] <= hhmm
        event = {"title": i["title"], "when": f"now, until {clock(i['end'])}" if on else clock(i["start"]), "source": i["source"]}
        if i.get("where"):
            event["where"] = i["where"]
        events.append(event)
    today = [" · ".join(p for p in (f"{clock(i['start'])}–{clock(i['end'])}", i["title"], i.get("where", ""),
                                    "done" if i["end"] <= hhmm else "") if p) for i in items]
    soon = [d for d in due if not d.optional] or due
    flag = None
    if soon and soon[0].due <= now + timedelta(hours=72):
        d = soon[0]
        late = d.due < now
        flag = {"text": f"{d.course} {d.title} {'was' if late else 'is'} due {when(d.due, now)}",
                "why": "It's the closest deadline." + (f" About {d.remaining_min} minutes of work left." if d.remaining_min else ""),
                "source": due_source(d)}
        if d.course:
            flag["branch_id"] = slug(d.course)
    done = [i["title"] for i in items if i["end"] <= hhmm]
    return NowContext(events=events, done_today=done, day={"done": len(done), "total": len(items)} if items else None,
                      today=today, due=[d.line(now) for d in due[:6]], flag=flag, notes=[note] if note else [])


def plain_now_card(ctx: Any, now: datetime) -> tuple[dict[str, Any], str]:
    """The now card when the memory store isn't running: the same shape, from the feed alone."""
    part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
    card: dict[str, Any] = {"greeting": f"Good {part}", "updated": now.isoformat(timespec="seconds"),
                            "next_up": ctx.events[0] if ctx.events else None, "flag": ctx.flag}
    if ctx.done_today:
        card["done_today"] = ctx.done_today
    if ctx.day:
        card["day"] = ctx.day
    lines = [f"Next: {e['title']} · {e['when']}" + (f" · {e['where']}" if e.get("where") else "") for e in ctx.events[:3]]
    lines += [f"Today: {x}" for x in ctx.today[:12]] + [f"Due: {x}" for x in ctx.due[:6]] + [f"Note: {x}" for x in ctx.notes[:2]]
    lines += list(getattr(ctx, "names", [])[:2])
    lines += [f"Remember: {x}" for x in getattr(ctx, "prefs", [])[:8]]
    return card, "\n".join(lines)


def course_branches(cc: ClassContent, now: datetime, have: set[str], root: str) -> list[tuple[dict, dict | None]]:
    """His term and courses as branches with cards (next classes, due work), for the ones memory doesn't hold yet."""
    sched = cc.load("schedule.json") or {}
    codes = sorted({str(m.get("course")) for m in sched.get("meetings") or [] if m.get("course")}
                   | {str(c["course"]) for c in cc.courses()})
    if not codes:
        return []
    due = cc.due(now, days=21)
    term_name = str(sched.get("term_label") or "This term")
    term = slug(term_name) or "term"
    out: list[tuple[dict, dict | None]] = []

    def add(branch: dict, card: dict | None = None) -> None:
        if branch["id"] not in have:
            out.append((branch, card))

    add({"id": "school", "parent": root, "name": "School", "glyph": "SC", "kind": "area", "status": "active", "tier": 1,
         "counts": {"due": len(due)}, "summary": f"{len(codes)} courses · {len(due)} due in the next three weeks"})
    add({"id": term, "parent": "school", "name": term_name, "glyph": "".join(w[0] for w in term_name.split()[:2]).upper() or "T",
         "kind": "branch", "status": "active", "tier": 1, "counts": {"due": len(due)}})
    for code in codes:
        sid, info = slug(code), cc.course(code) or {}
        mine = [d for d in due if d.course == code]
        branch: dict[str, Any] = {"id": sid, "parent": term, "name": code, "glyph": code.split()[0][:2].upper(), "kind": "leaf",
                                  "status": "active", "tier": 1, "counts": {"due": len(mine)},
                                  "activity": 2 if mine and mine[0].due <= now + timedelta(hours=72) else 1 if mine else 0,
                                  "summary": str(info.get("title") or "")}
        if mine:
            hours = max(0, int((mine[0].due - now).total_seconds() // 3600))
            branch["due"] = {"label": f"{mine[0].title} · {when(mine[0].due, now)}", "hours": hours}
        nxt, day = [], now.date()
        for n in range(8):
            for m in cc.meetings_on(day + timedelta(days=n)):
                if m.course == code and (n or m.end > f"{now:%H:%M}") and len(nxt) < 3:
                    label = "Today" if n == 0 else "Tomorrow" if n == 1 else f"{day + timedelta(days=n):%a}"
                    event = {"title": "Lab" if m.kind == "lab" else "Lecture", "when": f"{label} {clock(m.start)}", "source": paws(cc)}
                    if m.where:
                        event["where"] = m.where
                    nxt.append(event)
        status = " · ".join(p for p in (str(info.get("title") or ""), str(info.get("instructor") or "")) if p) or code
        card: dict[str, Any] = {"branch_id": sid, "status": status}
        if nxt:
            card["next"] = nxt
        if mine:
            card["due"] = [{"id": f"due-{slug(d.key)[:40]}", "title": d.title, "due": d.due.isoformat(timespec="seconds"),
                            "source": due_source(d), "branch_id": sid} for d in mine[:6]]
        add(branch, card)
    return out


def latency_rows(path: Path, turns: int = LATENCY_TURNS) -> list[dict]:
    """Under the hood's response times from the tail of logs/voice-latency.jsonl ([] before any turn)."""
    from jarvis.health.latency import TurnTrace, build_report, to_metrics_latency  # noqa: PLC0415

    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - turns * 1200))
            lines = f.read().decode("utf-8", "replace").splitlines()[-turns:]
    except OSError:
        return []
    traces = []
    for line in lines:
        with contextlib.suppress(Exception):
            traces.append(TurnTrace.from_json(line))
    try:
        return to_metrics_latency(build_report(traces)) if traces else []
    except Exception:  # noqa: BLE001 - a half-written line must never take the hub's numbers down
        return []


class HubFeed:
    def __init__(self, bus: Any, root: Path, *, classes: ClassContent | None = None, calendar: Any = None,
                 memory: Any = None, clock: Any = datetime.now, rail: Any = None) -> None:
        self.rail = rail            # () -> the core's current rail (the icon row), so what he docked there is kept
        self.bus, self.root, self.classes, self.calendar, self.memory, self.clock = bus, Path(root), classes, calendar, memory, clock
        self.events: list[Any] = []
        self.calendar_state = ("off", "No Composio key or not connected yet") if calendar is not None else ("off", "Not installed")
        self.calendar_at: datetime | None = None
        self._sent: dict[str, str] = {}
        self._text = ""
        self._ctx_sig: str | None = None
        self._card: dict | None = None
        self._tasks: list[asyncio.Task] = []

    # -- what the talker reads -------------------------------------------------------------------------------------
    def now_text(self) -> str:
        """The now card lines for the prompt (today, next, due). '' until the first refresh."""
        return self._text

    # -- publishing --------------------------------------------------------------------------------------------------
    def _send(self, key: str, kind: str, data: dict, *, ignore: tuple[str, ...] = ()) -> bool:
        """Publish only what changed (so the hub doesn't redraw every 30 s for nothing)."""
        sig = json.dumps({k: v for k, v in data.items() if k not in ignore}, sort_keys=True, default=str)
        if self._sent.get(key) == sig:
            return False
        self._sent[key] = sig
        self.bus.publish(kind, data)
        return True

    async def refresh_day(self) -> None:
        now = self.clock()
        cc = self.classes
        items = day_items(cc, self.events, now)
        due = cc.due(now) if cc is not None else []
        age = cc.homework_age_days(now) if cc is not None else None
        note = f"the homework list is {age} days old, so newer work may be missing" if age is not None and age >= cls.STALE_HOMEWORK_DAYS else None
        ctx = now_context(items, due, now, note=note)
        if cc is not None:
            ctx.names = cc.names()        # "the Engineering Building", "mechanics": plain words for the codes (v0.21.0)
        if self.memory is not None:   # how he wants things done rides in every prompt (v0.20.0)
            with contextlib.suppress(Exception):
                ctx.prefs = list(await self.memory.standing())
        # memory rebuilds the card (a database write) only when his day actually changed, not every 30 seconds
        sig = json.dumps([ctx.events, ctx.today, ctx.due, ctx.flag, ctx.notes, ctx.prefs, ctx.names, now.hour // 6], sort_keys=True, default=str)
        if sig != self._ctx_sig or self._card is None:
            card = text = None
            if self.memory is not None:
                with contextlib.suppress(Exception):
                    card = await self.memory.rebuild_now_card(ctx)
                    text = await self.memory.now_card_text()
            if card is None:
                card, text = plain_now_card(ctx, now)
            self._ctx_sig, self._card, self._text = sig, card, text or ""
        card = self._card
        self._send("day", "day.updated", {"date": now.date().isoformat(), "items": items})
        self._rail(items, due, now)
        self._send("now", "nowcard.updated", card, ignore=("updated",))

    def _rail(self, items: list[dict], due: list[Due], now: datetime) -> None:
        """The icon row under the hub (v0.21.0): Today holds what is left of his day, Homework what is due, each one
        click from its window. Before this the live icons opened onto "Nothing here right now". Whatever he docked
        there himself stays."""
        if self.rail is None:
            return
        try:
            rail = json.loads(json.dumps(self.rail()))
        except Exception:  # noqa: BLE001
            return
        hhmm, today = f"{now:%H:%M}", now.date().isoformat()
        ahead = [i for i in items if i["end"] > hhmm]
        mine = {"today": [], "homework": []}
        for n, i in enumerate(ahead[:6]):
            item = {"ref": i["id"], "slot": "today", "kind": "event", "title": i["title"], "at": f"{today}T{i['start']}:00",
                    "state": "soon" if n == 0 else "progress", "detail": " · ".join(p for p in (clock(i["start"]), i.get("where", "")) if p)}
            if i.get("branch_id"):
                item["window"] = {"id": f"w-{i['branch_id']}", "type": "branch_card", "title": i["title"], "ref": i["branch_id"]}
            mine["today"].append(item)
        for d in due[:8]:
            ref = f"due-{slug(d.key)[:40]}"
            hours = (d.due - now).total_seconds() / 3600
            mine["homework"].append({
                "ref": ref, "slot": "homework", "kind": "due", "title": " · ".join(p for p in (d.course, d.title) if p),
                "at": d.due.isoformat(timespec="seconds"), "state": "critical" if hours < 24 else "soon" if hours < 72 else "progress",
                "detail": f"Due {when(d.due, now)}" + (f" · about {d.remaining_min} min left" if d.remaining_min else ""),
                "window": {"id": f"w-{ref}", "type": "countdown", "title": f"{d.course} {d.title}".strip(), "ref": ref}})
        slots = rail.setdefault("slots", {})
        for name, fresh in mine.items():
            slot = slots.setdefault(name, {"items": []})
            kept = [x for x in slot.get("items") or [] if isinstance(x.get("window"), dict) and x["window"].get("docked")
                    and x["ref"] not in {f["ref"] for f in fresh}]
            slot["items"] = fresh + kept
            if name == "today" and items:
                slot["done"] = round(sum(1 for i in items if i["end"] <= hhmm) / len(items), 2)
            if fresh:
                slot["worst"] = "critical" if any(f["state"] == "critical" for f in fresh) else "soon" if any(f["state"] == "soon" for f in fresh) else "progress"
        self._send("rail", "rail.updated", rail)

    async def refresh_tree(self) -> None:
        now = self.clock()
        tree = {"branches": [], "cards": {}, "facts": []}
        if self.memory is not None:
            with contextlib.suppress(Exception):
                tree = await self.memory.hub_tree()
        have = {b["id"] for b in tree["branches"]}
        root = next((b["id"] for b in tree["branches"] if b["kind"] == "root"), None)
        extra: list[tuple[dict, dict | None]] = []
        if root is None:
            root = "you"
            extra.append(({"id": root, "parent": None, "name": "You", "glyph": "DW", "kind": "root", "status": "active", "tier": 1}, None))
        if self.classes is not None:
            extra += course_branches(self.classes, now, have, root)
        for b in tree["branches"]:
            self._send(f"b:{b['id']}", "branch.updated", {"branch": b, **({"card": tree["cards"][b["id"]]} if b["id"] in tree["cards"] else {})})
        for b, card in extra:
            self._send(f"b:{b['id']}", "branch.updated", {"branch": b, **({"card": card} if card else {})})
        for f in tree["facts"]:
            self._send(f"f:{f['id']}", "fact.updated", {"fact": f})   # the reducer's shape (a bare fact raised KeyError every minute on Laptop B)

    def connectors(self, now: datetime) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        cc = self.classes
        if cc is None:
            rows.append({"name": "Class files", "status": "off", "note": "Class Content folder not found on this laptop"})
        else:
            for name, file, stale in (("Class schedule (PAWS)", "schedule.json", 60), ("Homework list", "homework.json", cls.STALE_HOMEWORK_DAYS),
                                      ("Courses (syllabi)", "courses.json", 120)):
                t = cc.stamp(file)
                if t is None:
                    rows.append({"name": name, "status": "error", "note": f"{file} is missing or unreadable"})
                else:
                    old = (now.date() - t.date()).days >= stale
                    rows.append({"name": name, "status": "stale" if old else "ok", "last_sync": f"{t:%b} {t.day}",
                                 **({"note": "Run your week planner to refresh it"} if old else {})})
        status, note = self.calendar_state
        row = {"name": "Google Calendar", "status": status}
        if self.calendar_at is not None and status == "ok":
            row["last_sync"] = clock(self.calendar_at)
        elif note:
            row["note"] = note
        rows.append(row)
        rows.append({"name": "Memory", "status": "ok"} if self.memory is not None else {"name": "Memory", "status": "off", "note": "The memory store isn't running"})
        return rows

    async def refresh_metrics(self) -> None:
        rows = await asyncio.to_thread(latency_rows, self.root / "logs" / "voice-latency.jsonl")
        self._send("metrics", "metrics.updated", {"latency": rows, "connectors": self.connectors(self.clock())})

    async def refresh_calendar(self) -> None:
        """Today's events from his Google Calendar. Quiet when it isn't connected: the calendar tool offers that."""
        from jarvis.reach.calendar import CalendarError, NotConnected  # noqa: PLC0415

        if self.calendar is None:
            return
        try:
            self.events = await self.calendar.events(self.clock().date(), 1)
            self.calendar_state, self.calendar_at = ("ok", ""), self.clock()
        except NotConnected:
            self.events, self.calendar_state = [], ("off", "Not connected yet: ask Jarvis about your calendar to connect it")
        except CalendarError as exc:
            self.calendar_state = ("off" if "key" in str(exc).lower() else "error", str(exc)[:120])
        except Exception as exc:  # noqa: BLE001 - a network hiccup is a stale row, never a crash
            self.calendar_state = ("error", type(exc).__name__)

    async def refresh(self) -> None:
        """Everything once, local first (so the hub fills at once), then the calendar on top."""
        for step in (self.refresh_day, self.refresh_tree, self.refresh_metrics):
            try:
                await step()
            except Exception:  # noqa: BLE001
                log.exception("feed.failed step=%s", step.__name__)

    # -- running -----------------------------------------------------------------------------------------------------
    async def _every(self, seconds: float, *steps: Any) -> None:
        while True:   # at once, then every `seconds`
            for step in steps:
                try:
                    await step()
                except Exception:  # noqa: BLE001
                    log.exception("feed.failed step=%s", step.__name__)
            await asyncio.sleep(seconds)

    async def _calendar_loop(self) -> None:
        while True:
            await self.refresh_calendar()
            with contextlib.suppress(Exception):
                await self.refresh_day()
            await asyncio.sleep(CALENDAR_EVERY_S)

    async def start(self) -> None:
        """Start filling the hub in the background: the core's start-up never waits for a file or the network."""
        self._tasks = [asyncio.create_task(self._every(LOCAL_EVERY_S, self.refresh_day)),
                       asyncio.create_task(self._every(METRICS_EVERY_S, self.refresh_metrics, self.refresh_tree)),
                       asyncio.create_task(self._calendar_loop())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks = []
