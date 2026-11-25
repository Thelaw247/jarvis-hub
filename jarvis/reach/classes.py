"""His classes, due work and course facts, read from the files his study skills already keep.

The week-planner family of skills saves these in ``Class Content/_Week Planner`` (OneDrive Desktop, so the same files
are on both laptops): ``schedule.json`` (PAWS: every lecture and lab with days, times and rooms), ``homework.json``
(what is due, how long it takes) and ``courses.json`` (syllabi: assessments, exams, instructors). Reading them is
local and takes a millisecond, so the hub and the now card can show his day without a network call or a model round
trip (JARVIS_RESEARCH_CONTEXT_ARCHITECTURE.md: entity tools over local data; latency: about one tool round saved).

Read-only. The files are only as fresh as the last run of his skills, so every answer carries the date it is from.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("jarvis.reach")

FOLDER = "Class Content"
PLANNER = "_Week Planner"
DONE = "done.json"   # what he told Jarvis he has finished (v0.27.1). The homework list itself belongs to the skill that builds it.
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
STALE_HOMEWORK_DAYS = 4      # the homework list older than this says so
ENV = "JARVIS_CLASS_CONTENT"


def find_root(env: dict[str, str] | None = None, home: Path | None = None) -> Path | None:
    """Where Class Content lives on this laptop: the env var, else OneDrive's Desktop, else the plain Desktop."""
    env = os.environ if env is None else env
    home = home or Path.home()
    named = env.get(ENV)
    spots = [Path(named)] if named else []
    spots += [Path(env[k]) / "Desktop" / FOLDER for k in ("OneDrive", "OneDriveConsumer") if env.get(k)]
    spots += [home / "OneDrive" / "Desktop" / FOLDER, home / "Desktop" / FOLDER]
    for spot in spots:
        try:
            if (spot / PLANNER).is_dir():
                return spot
        except OSError:
            continue
    return None


def slug(course: str) -> str:
    """'GE 122' -> 'ge-122' (the branch id the hub and memory use for a course)."""
    return re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-")


def clock(t: datetime | str) -> str:
    """'4:00 pm' from a time or 'HH:MM'."""
    if isinstance(t, str):
        t = datetime.strptime(t, "%H:%M")
    return f"{t.hour % 12 or 12}:{t:%M} {'am' if t.hour < 12 else 'pm'}"


def when(due: datetime, now: datetime) -> str:
    """'today 10:00 pm', 'tomorrow 8:00 pm', 'Wed 8:00 pm', 'Dec 3 11:59 pm'."""
    days = (due.date() - now.date()).days
    day = "today" if days == 0 else "tomorrow" if days == 1 else "yesterday" if days == -1 \
        else f"{due:%a}" if 1 < days < 7 else f"{due:%b} {due.day}"
    return f"{day} {clock(due)}"


def parse(ts: Any) -> datetime | None:
    """An ISO time from the files as a naive local time (the files and the laptop are both on Saskatoon time)."""
    try:
        return datetime.fromisoformat(str(ts)).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Meeting:
    course: str
    title: str
    kind: str          # "class" | "lab"
    start: str         # "HH:MM"
    end: str
    where: str         # "ENGR 1A10", or "" when PAWS has no room

    def line(self) -> str:
        what = f"{self.course} {'lab' if self.kind == 'lab' else 'lecture'}"
        return " · ".join(p for p in (f"{clock(self.start)}–{clock(self.end)}", what, self.where) if p)


@dataclass(frozen=True)
class Due:
    key: str
    course: str
    title: str
    due: datetime
    platform: str = ""
    remaining_min: int | None = None
    optional: bool = False
    url: str = ""          # where it lives online (Canvas, WebAssign), when his homework list has it

    def line(self, now: datetime) -> str:
        left = f"about {self.remaining_min} min left" if self.remaining_min else ""
        return " · ".join(p for p in (f"{self.course} {self.title}", f"due {when(self.due, now)}", self.platform, left) if p)


class ClassContent:
    """The three files, re-read only when they change on disk."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._cache: dict[str, tuple[float, Any]] = {}

    def _path(self, name: str) -> Path:
        return self.root / PLANNER / name

    def load(self, name: str) -> Any:
        """The parsed file, or None when it is missing or broken (logged once per change)."""
        path = self._path(name)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            self._cache.pop(name, None)
            return None
        hit = self._cache.get(name)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            log.warning("classes.unreadable name=%s error=%s", name, type(exc).__name__)
            data = None
        self._cache[name] = (mtime, data)
        return data

    def stamp(self, name: str) -> datetime | None:
        """When the file's content is from (its own fetched/generated/updated time)."""
        data = self.load(name)
        if not isinstance(data, dict):
            return None
        return next((t for k in ("fetched_at", "generated_at", "updated_at") if (t := parse(data.get(k)))), None)

    def as_of(self, name: str) -> str:
        """'Oct 26' for a source label."""
        t = self.stamp(name)
        return f"{t:%b} {t.day}" if t else ""

    # -- classes -------------------------------------------------------------------------------------------------
    def no_class(self, day: date) -> str | None:
        """Why there are no classes that day (a holiday, reading week), else None."""
        sched = self.load("schedule.json") or {}
        if day.isoformat() in (sched.get("no_class_dates") or []):
            return (sched.get("no_class_reasons") or {}).get(day.isoformat()) or "No classes"
        return None

    def meetings_on(self, day: date) -> list[Meeting]:
        sched = self.load("schedule.json")
        if not isinstance(sched, dict) or self.no_class(day):
            return []
        iso, name = day.isoformat(), DAYS[day.weekday()]
        out: dict[tuple, Meeting] = {}
        for m in sched.get("meetings") or []:
            try:
                only = m.get("only_dates") or []
                if only:
                    if iso not in only:
                        continue
                elif name not in (m.get("days") or []) or not (str(m.get("start_date") or "0") <= iso <= str(m.get("end_date") or "9")):
                    continue
                if iso in (m.get("skip_dates") or []):
                    continue
                where = " ".join(p for p in (str(m.get("building") or ""), str(m.get("room") or "")) if p)
                kind = "lab" if str(m.get("type", "")).lower() == "lab" else "class"
                meeting = Meeting(str(m["course"]), str(m.get("title") or ""), kind, str(m["start"]), str(m["end"]), where)
                key = (meeting.course, meeting.kind, meeting.start)
                if key not in out or (where and not out[key].where):
                    out[key] = meeting
            except (KeyError, TypeError, AttributeError):
                continue
        return sorted(out.values(), key=lambda x: (x.start, x.course))

    def names(self) -> list[str]:
        """What the codes mean in plain words, so Jarvis can say "the Engineering Building" and "mechanics" instead of
        reading "ENGR 1A10" and "GE 122" off a record. From PAWS (building names) and the course titles."""
        sched = self.load("schedule.json")
        places: dict[str, str] = {}
        for m in (sched.get("meetings") or []) if isinstance(sched, dict) else []:
            if isinstance(m, dict) and m.get("building") and m.get("building_name"):
                places.setdefault(str(m["building"]), str(m["building_name"]))
        out = []
        if places:
            out.append("Buildings: " + "; ".join(f"{code} is the {name}" if not name.lower().startswith("the ") else f"{code} is {name}"
                                               for code, name in sorted(places.items())))
        titles = [f"{c['course']} is {c['title']}" for c in self.courses() if c.get("title")]
        if titles:
            out.append("Courses: " + "; ".join(titles))
        return out

    def next_meeting(self, course: str, now: datetime, days: int = 14) -> tuple[date, Meeting] | None:
        for n in range(days):
            day = now.date() + timedelta(days=n)
            for m in self.meetings_on(day):
                if m.course.lower() == course.lower() and (n or m.end > f"{now:%H:%M}"):
                    return day, m
        return None

    # -- due work ------------------------------------------------------------------------------------------------
    def due(self, now: datetime, days: int = 14, *, overdue_days: int = 2) -> list[Due]:
        """What is still to do, soonest first: not done, due within `days`, or up to `overdue_days` late."""
        work = self.load("homework.json")
        if not isinstance(work, dict):
            return []
        out, finished = [], self.done()
        for item in work.get("items") or []:
            try:
                at = parse(item.get("due"))
                if at is None or str(item.get("status") or "").lower() in ("done", "submitted", "dropped"):
                    continue
                if str(item.get("key") or item.get("title")) in finished:
                    continue   # he said it is done; the list catches up when it is next rebuilt
                if not (now - timedelta(days=overdue_days) <= at <= now + timedelta(days=days)):
                    continue
                left = item.get("remaining_min")
                out.append(Due(str(item.get("key") or item["title"]), str(item.get("course") or ""), str(item["title"]), at,
                               str(item.get("platform") or ""), int(left) if isinstance(left, (int, float)) and left > 0 else None,
                               bool(item.get("optional")), str(item.get("url") or "")))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(out, key=lambda d: d.due)

    def done(self) -> dict[str, dict]:
        """key → {title, course, at}: work he told Jarvis is finished (done.json beside the homework list)."""
        data = self.load(DONE)
        marks = data.get("done") if isinstance(data, dict) else None
        return marks if isinstance(marks, dict) else {}

    def mark_done(self, key: str, *, title: str = "", course: str = "", done: bool = True, now: datetime | None = None) -> None:
        """Mark one piece of work finished, or take the mark off. Only done.json is written, never the homework list."""
        marks = dict(self.done())
        if done:
            marks[key] = {"title": title, "course": course, "at": (now or datetime.now()).isoformat(timespec="minutes")}
        else:
            marks.pop(key, None)
        path = self._path(DONE)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"done": marks}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        self._cache.pop(DONE, None)

    def homework_age_days(self, now: datetime) -> int | None:
        t = self.stamp("homework.json")
        return None if t is None else max(0, (now.date() - t.date()).days)

    # -- courses -------------------------------------------------------------------------------------------------
    def courses(self) -> list[dict]:
        """Every course he has: the ones with a syllabus on file (full detail), then any other that is on his PAWS
        schedule or has a folder in Class Content (code and title only). PHYS 152 started mid-term and had no
        syllabus entry, so "pull up physics" found nothing (Laptop B, 2026-11-22)."""
        data = self.load("courses.json")
        out = [c for c in (data.get("courses") or []) if isinstance(c, dict) and c.get("course")] if isinstance(data, dict) else []
        have = {str(c["course"]) for c in out}
        sched = self.load("schedule.json")
        for m in (sched.get("meetings") or []) if isinstance(sched, dict) else []:
            code = str(m.get("course") or "") if isinstance(m, dict) else ""
            if code and code not in have:
                have.add(code)
                out.append({"course": code, "title": str(m.get("title") or "")})
        try:
            for d in sorted(self.root.iterdir()):
                m = re.match(r"^([A-Z]{2,5} \d{3}) - (.+)$", d.name) if d.is_dir() else None
                if m and m.group(1) not in have:
                    have.add(m.group(1))
                    out.append({"course": m.group(1), "title": m.group(2)})
        except OSError:
            pass
        return out

    def course(self, wanted: str) -> dict | None:
        """A course by code ('GE 122', 'ge122') or by a word of its title ('mechanics')."""
        want = re.sub(r"[^a-z0-9]", "", wanted.lower())
        if not want:
            return None
        found = self.courses()
        for c in found:
            if re.sub(r"[^a-z0-9]", "", str(c["course"]).lower()) == want:
                return c
        return next((c for c in found if want in re.sub(r"[^a-z0-9]", "", str(c.get("title") or "").lower())), None)

    def exams(self, now: datetime, days: int = 30) -> list[tuple[str, dict, datetime]]:
        out = []
        for c in self.courses():
            for exam in c.get("exams") or []:
                at = parse(exam.get("start")) if isinstance(exam, dict) else None
                if at and now <= at <= now + timedelta(days=days):
                    out.append((str(c["course"]), exam, at))
        return sorted(out, key=lambda x: x[2])
