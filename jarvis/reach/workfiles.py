"""Find the work he means in his Class Content folder: "PPS 6", "the chem lab", "mechanics", "lecture 14".

Each course folder holds the same sections (the class-content skill keeps them): Assignments & Labs, Lectures,
Tests & Exams, Study Plans, 00 Class-Wide. This matches his words against those folder and file names and against his
homework list, all on this laptop, so "pull up PPS 6" costs no network call and no extra model round.

Read-only. Only ever returns paths inside the Class Content folder, and only document types (never a program).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jarvis.reach.classes import ClassContent, Due

SECTIONS = ("Assignments & Labs", "Lectures", "Tests & Exams", "Study Plans", "00 Class-Wide (all lectures)")
OPENABLE = (".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".html", ".htm", ".md", ".txt", ".m", ".py", ".png", ".jpg")
STOP = {"the", "my", "on", "for", "a", "an", "to", "up", "pull", "open", "work", "lets", "let", "s", "do", "start", "and", "of",
        "in", "with", "me", "show", "get", "please", "some", "that", "this", "it", "homework", "stuff", "i", "need", "want"}
NOT_FIRST = ("solution", "answer", "template", "rubric")   # he opens the questions first, not the answers


def tokens(text: str, *, section: str = "") -> list[str]:
    """Words and numbers, with his shorthand spelled out: PPS 6, P6, problem set 6 -> practice 6; L14 -> lecture 14."""
    t = text.lower()
    t = re.sub(r"\bpractice problem sets?\b|\bproblem sets?\b|\bpps\b|\bps(?=\s?\d)", " practice ", t)
    if section.startswith("Study"):
        t = re.sub(r"\bp0*(\d+)\b", r" plan \1 ", t)
    t = re.sub(r"\bp0*(\d+)\b", r" practice \1 ", t)
    t = re.sub(r"\bl0*(\d+)\b|\blec(?:ture)?\s?0*(\d+)\b", lambda m: f" lecture {m.group(1) or m.group(2)} ", t)
    t = re.sub(r"\bmid ?terms?\b|\bexams?\b|\btests?\b", " test ", t)
    t = re.sub(r"\blabs?\b", " lab ", t)
    out = []
    for w in re.findall(r"[a-z]+|\d+", t):
        w = w.lstrip("0") or "0" if w.isdigit() else w
        if w not in STOP:
            out.append(w)
    return out


def pick_course(cc: ClassContent, ask: str) -> dict | None:
    """The course in what he said: a code (GE 122), its letters (chem, phys, math) or a word of its title (mechanics)."""
    m = re.search(r"\b([A-Za-z]{2,5})\s?-?(\d{3})\b", ask)
    if m and (c := cc.course(f"{m.group(1)}{m.group(2)}")):
        return c
    found = cc.courses()
    for w in re.findall(r"[a-z]{3,}", ask.lower()):
        if w in STOP or w in ("practice", "lecture", "test", "lab", "plan", "problem", "set", "quiz", "assignment"):
            continue
        hits = [c for c in found if re.sub(r"[^a-z]", "", str(c["course"]).lower()).startswith(w[:4])
                or (len(w) >= 4 and w in re.sub(r"[^a-z ]", "", str(c.get("title") or "").lower()).split())
                or (len(w) >= 4 and any(t.startswith(w) or (len(t) >= 5 and w.startswith(t))   # "communications" ~ "communication"
                                        for t in re.sub(r"[^a-z ]", "", str(c.get("title") or "").lower()).split()))]
        if len(hits) == 1:
            return hits[0]
    return None


def course_folder(cc: ClassContent, code: str) -> Path | None:
    try:
        for d in sorted(cc.root.iterdir()):
            if d.is_dir() and (d.name == code or d.name.startswith(f"{code} - ")):
                return d
    except OSError:
        return None
    return None


@dataclass
class Work:
    course: str
    label: str                       # "Practice 6", "Lab 3 - Work and Energy", "GE 122"
    path: Path | None = None         # the folder or file it lives in
    files: list[Path] = field(default_factory=list)   # what to open, the questions first
    due: Due | None = None
    url: str = ""                    # the assignment's own page (Canvas, WebAssign), when his homework list has it
    why: str = ""                    # how it was chosen, when he didn't name it ("the next thing due")


def _entries(folder: Path) -> list[tuple[Path, str]]:
    out = []
    for section in SECTIONS:
        try:
            out += [(e, section) for e in sorted((folder / section).iterdir()) if not e.name.startswith(("_", "."))]
        except OSError:
            continue
    return out


def _score(want: list[str], have: list[str]) -> float:
    if not want:
        return 0.0
    nums_w, nums_h = [w for w in want if w.isdigit()], [h for h in have if h.isdigit()]
    if nums_w and nums_w[0] not in nums_h[:1]:     # "practice 6" is not "practice 5" (the name's first number decides)
        return 0.0
    words = [w for w in want if not w.isdigit()]
    hit = sum(1 for w in words if w in have or any(h.startswith(w) and len(w) >= 4 for h in have))
    if words and not hit:
        return 0.0
    return hit + (1.0 if nums_w else 0.0) - 0.01 * len(have)   # the tighter name wins a tie


def _openable(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in OPENABLE else []
    try:
        files = [f for f in sorted(path.iterdir()) if f.is_file() and f.suffix.lower() in OPENABLE and not f.name.startswith(("_", ".", "~"))]
    except OSError:
        return []
    order = {".pdf": 0, ".html": 1, ".htm": 1, ".docx": 2}
    return sorted(files, key=lambda f: (any(n in f.name.lower() for n in NOT_FIRST), order.get(f.suffix.lower(), 3), f.name.lower()))


def find(cc: ClassContent, ask: str, now: datetime) -> Work | None:
    """The piece of work he means, or None. With only a course ("let's work on mechanics") it is the next thing due
    there, else the latest lecture."""
    course = pick_course(cc, ask)
    due = cc.due(now, days=30)
    want = tokens(ask)
    if course:
        code_words = set(tokens(str(course["course"]))) | set(tokens(str(course.get("title") or "")))
        want = [w for w in want if w not in code_words or w.isdigit() and w not in tokens(str(course["course"]))]
        code = str(course["course"])
        want = [w for w in want if w != code.split()[-1]]   # the "122" of GE 122 is not "practice 122"
    best_due = None
    if want:
        scored = [(_score(want, tokens(d.title)), d) for d in due if course is None or d.course == course["course"]]
        scored = [s for s in scored if s[0] > 0]
        if scored:
            best_due = max(scored, key=lambda s: (s[0], -s[1].due.timestamp()))[1]
    if course is None and best_due is not None:
        course = cc.course(best_due.course)
    why = ""
    if course is None:
        return None
    code = str(course["course"])
    if not want:   # only the course: the next thing due there
        mine = [d for d in due if d.course == code]
        if mine:
            best_due, want, why = mine[0], tokens(mine[0].title), "the next thing due"
    folder = course_folder(cc, code)
    pick: Path | None = None
    if folder is not None:
        entries = _entries(folder)
        if want:
            scored = [(_score(want, tokens(e.name, section=sec)), e) for e, sec in entries]
            scored = [s for s in scored if s[0] > 0]
            if scored:
                pick = max(scored, key=lambda s: s[0])[1]
        if pick is None and (not want or why):   # nothing due matched a folder: the latest lecture
            lectures = [e for e, sec in entries if sec == "Lectures" and e.is_dir() and re.match(r"L\d+", e.name)]
            if lectures:
                pick, why = lectures[-1], why or "the latest lecture"
    if pick is None and best_due is None:
        if want:
            return None   # he named something and nothing matches: say so, don't open something else
        return Work(code, code, folder, _openable(folder / "index.html") if folder else [], None, "", "the course page")
    label = pick.stem if pick is not None and pick.is_file() else pick.name if pick is not None else best_due.title
    link = best_due.url if best_due is not None and best_due.url.startswith("https://") else ""
    return Work(code, label, pick, _openable(pick) if pick is not None else [], best_due, link, why)
