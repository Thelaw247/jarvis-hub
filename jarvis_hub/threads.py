"""Work threads and their resume points (HUD v2 §10), starting with practice-set PDFs (§10.1).

The hub's state holds each thread in the contract shape (contracts/thread.schema.json). This module adds:
  - file_path(file_id): where a file for the reader is (GET /api/file/<id> calls it). Demo files only; a live
    backend registers real files with register_file(). `<file id>.qindex.json` answers with the question index.
  - new_thread(...): a thread for a filed document, in the contract shape.
  - infer_resume / merge_session: what the reader saw becomes a resume point, done questions and time per
    question, by the rules below (§9 "the hidden trick": know more than needed, assume nothing).
  - on_act(action, thread, args, now): the hook for the resume_save / resume_accept actions (events.py).
Time per question, corrections and acceptances are kept beside the thread in Jarvis's cache folder (never git,
never in the state): dwell only ever picks resume points and is never shown or said (§9.3).

Inference (Horvitz: a less precise answer beats a wrong precise one):
  - clear: one question in view at the end, he stayed on it ≥ 60 s or the session was short (< 3 min), and he
    didn't jump back and forth → the question (page + y), `inferred`.
  - weak: two or more questions in view, back and forth, no index, or he corrected this document twice
    → the page only (no y, label "Page N"), `inferred`. The reader offers the page instead of a question.
  - a glance (< 15 s, nothing moved) keeps the saved spot.
  - his own choice wins (never downgraded by a later silent save): a question he picked or accepted in this
    session ("Carry on at Q8", "Another question → Q8") is saved `confirmed` while he stays on it.
  - a saved question he hasn't moved off (every question he was on is that one) is kept, `confirmed` if it
    was, however long he stayed: the view adds nothing new. Only moving on to another question re-decides.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import pdfindex

CLEAR_DWELL_S = 60  # stayed this long on the last question: it's where he is
SHORT_SESSION_S = 180  # a short session's last spot stands even without the dwell
GLANCE_S = 15  # opened and closed without moving: keep the saved spot
DONE_DWELL_S = 30  # worked this long on a question and moved on past it: done
VIEWED_DWELL_S = 10  # a solutions page on screen this long: viewed
CORRECTIONS_TO_PAGE = 2  # corrected twice → offers drop to page level (§10 item 7)
CORRECTION_MEMORY = timedelta(days=14)  # raised thresholds drift back over about two weeks
INDEX_SUFFIX = ".qindex.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")

_files: dict[str, Path] = {}  # file id -> path, registered by a live backend or a test
DEMO_FILES = {"file-pps7": "PPS 7.pdf"}  # made here on first use, never from his disk


def register_file(file_id: str, path: str | Path, index: bool = True) -> dict | None:
    """Make a file readable by the hub (a live backend does this when class-sync files it). Indexes it then."""
    if not SAFE_ID.match(file_id):
        raise ValueError("File ids follow the contract id pattern.")
    _files[file_id] = Path(path)
    return pdfindex.file_pdf(file_id, path) if index and Path(path).suffix.lower() == ".pdf" else None


def forget_file(file_id: str) -> None:
    _files.pop(file_id, None)


def file_path(file_id: str) -> Path | None:
    """GET /api/file/<id>: the file for the hub's reader, or its question index (`<id>.qindex.json`)."""
    if file_id.endswith(INDEX_SUFFIX):
        base = file_id[: -len(INDEX_SUFFIX)]
        pdf = file_path(base)
        if pdf is None or pdf.suffix.lower() != ".pdf":
            return None
        try:
            pdfindex.file_pdf(base, pdf)  # cached by content: normally already built at filing time
        except ImportError:
            return None
        return pdfindex.index_path(base)
    if file_id in _files:
        path = _files[file_id]
        return path if path.is_file() else None
    if file_id in DEMO_FILES:
        return _demo_file(file_id)
    return None


def _demo_file(file_id: str) -> Path | None:
    path = pdfindex.cache_dir("demo-files") / DEMO_FILES[file_id]
    if not path.is_file():
        try:
            make_demo_pps(path)
        except ImportError:  # PyMuPDF isn't installed: the reader says the file isn't here
            return None
    try:
        pdfindex.file_pdf(file_id, path)
    except ImportError:
        pass
    return path


# ---- threads in the contract shape -------------------------------------------------------------------------
def thread_id_for(file_id: str) -> str:
    return "th-" + re.sub(r"^file-", "", file_id)


def new_thread(file_id: str, title: str, branch: str, kind: str = "pdf", thumb: dict | None = None,
               now: str | None = None) -> dict:
    """A thread for a newly filed document: no resume point yet, so the reader opens it at the top."""
    thread = {"id": thread_id_for(file_id), "kind": kind, "ref": file_id, "branch": branch, "title": title,
              "resume": None, "done": [], "viewed": [], "state": "open"}
    if thumb:
        thread["thumb"] = thumb
    if now:
        thread["updated"] = now
    return thread


def page_thumb(file_id: str, title: str, page: int, label: str | None = None) -> dict:
    """thumb for a thread: its resume page, rendered at filing time (/api/thumb/<file id>-p<page>.webp)."""
    what = f"question {label[1:]}" if label and label.startswith("Q") else f"page {page}"
    return {"src": f"/api/thumb/{pdfindex.thumb_key(file_id, page)}", "kind": "page",
            "alt": f"Page {page} of {title}, {what}" if label else f"Page {page} of {title}"}


# ---- what he did, kept beside the thread (cache folder, never git) ----------------------------------------
def _side_path(thread_id: str) -> Path:
    return pdfindex.cache_dir("threads") / f"{thread_id}.json"


def side(thread_id: str) -> dict:
    try:
        data = json.loads(_side_path(thread_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("dwell", {})
    data.setdefault("corrections", [])
    data.setdefault("accepts", [])
    return data


def _save_side(thread_id: str, data: dict) -> None:
    _side_path(thread_id).write_text(json.dumps(data), encoding="utf-8")


def time_per_question(thread_id: str) -> dict[str, float]:
    return dict(side(thread_id)["dwell"])


def offer_level(thread_id: str, now: str) -> str:
    """'question', or 'page' once he has corrected this document's spot twice (since his last acceptance,
    within two weeks)."""
    data, at = side(thread_id), datetime.fromisoformat(now)
    last_accept = max(data["accepts"], default="")
    recent = [c for c in data["corrections"] if c > last_accept and at - datetime.fromisoformat(c) <= CORRECTION_MEMORY]
    return "page" if len(recent) >= CORRECTIONS_TO_PAGE else "question"


# ---- inference -------------------------------------------------------------------------------------------
def _top(label: str) -> str:
    return re.sub(r"^(Q\d+)[a-h]$", r"\1", label)


def _order(index: dict) -> dict[str, int]:
    return {q["label"]: i for i, q in enumerate(index.get("questions", []))}


def _back_and_forth(path: list[str], order: dict[str, int]) -> bool:
    steps = [order[label] for label in path if label in order]
    return any(b < a for a, b in zip(steps, steps[1:], strict=False))


def page_resume(page: int, now: str) -> dict:
    return {"page": max(1, int(page)), "label": f"Page {max(1, int(page))}", "source": "inferred", "at": now}


def infer_resume(index: dict | None, session: dict, now: str, level: str = "question",
                 saved: dict | None = None) -> dict | None:
    """A resume point from one reading session (see the module doc). None means: keep the saved one.

    session: { seconds, dwell, path, visible, page, y, current, corrected, chosen?, since? }. `chosen` is the
    question he picked or accepted on the card in this session; `since` the questions he was on after that."""
    seconds = float(session.get("seconds") or 0)
    path = [str(label) for label in session.get("path") or []]
    questions = (index or {}).get("questions") or []
    by_label = {q["label"]: q for q in questions}
    chosen = by_label.get(str(session.get("chosen") or ""))
    if chosen is not None and _stayed(session.get("since"), chosen["label"]):
        return {"page": chosen["page"], "y": chosen["y"], "label": chosen["label"], "source": "confirmed", "at": now}
    if saved and seconds < GLANCE_S and len(path) <= 1:
        return None
    page = int(session.get("page") or 1)
    if not questions:
        return page_resume(page, now)
    current = by_label.get(str(session.get("current") or ""))
    if current is None and session.get("y") is not None:
        current = pdfindex.question_at(index, page, float(session["y"]))
    if (saved and str(saved.get("label")) in by_label and (saved.get("source") == "confirmed" or level == "question")
            and _stayed(path + ([current["label"]] if current else []), str(saved["label"]))):
        kept = by_label[str(saved["label"])]  # he hasn't moved off the saved question: the view adds nothing new,
        return {"page": kept["page"], "y": kept["y"], "label": kept["label"],  # and a choice of his stands
                "source": "confirmed" if saved.get("source") == "confirmed" else "inferred", "at": now}
    if level == "page":
        return page_resume(page, now)
    in_view = {_top(str(label)) for label in session.get("visible") or [] if str(label) in by_label}
    dwell = float((session.get("dwell") or {}).get(current["label"], 0)) if current else 0
    clear = (current is not None and len(in_view - {_top(current["label"])}) == 0
             and (dwell >= CLEAR_DWELL_S or seconds < SHORT_SESSION_S)
             and not _back_and_forth(path[-4:], _order(index)))
    if not clear:
        return page_resume(page, now)
    return {"page": current["page"], "y": current["y"], "label": current["label"], "source": "inferred", "at": now}


def _stayed(labels, label: str) -> bool:
    """True when every question in `labels` is `label` (or one of its parts): he never moved off it."""
    return all(_top(str(x)) == _top(label) for x in labels or [])


def done_from(index: dict | None, session: dict, current: str | None) -> list[str]:
    """Questions he worked on (≥ 30 s) and then moved on past, without coming back to them."""
    order = _order(index or {})
    path = [str(label) for label in session.get("path") or [] if str(label) in order]
    dwell = session.get("dwell") or {}
    done = []
    for i, label in enumerate(path):
        later = path[i + 1:]
        if (label != current and float(dwell.get(label, 0)) >= DONE_DWELL_S and later
                and all(order[x] > order[label] for x in later) and label not in done):
            done.append(label)
    return done


def _sorted_labels(labels: set[str], index: dict | None) -> list[str]:
    order = _order(index or {})
    return sorted(labels, key=lambda label: (order.get(label, 10**6), label))


def merge_session(thread: dict, session: dict, now: str, index: dict | None = None) -> dict:
    """The thread after one reading session: resume point, done, viewed, state. Dwell goes to the side store."""
    thread = json.loads(json.dumps(thread))
    index = index if index is not None else pdfindex.load_index(thread["ref"])
    data = side(thread["id"])
    for label, seconds in (session.get("dwell") or {}).items():
        data["dwell"][str(label)] = round(data["dwell"].get(str(label), 0) + max(0.0, float(seconds)), 1)
    if session.get("corrected"):
        data["corrections"].append(now)
    _save_side(thread["id"], data)
    resume = infer_resume(index, session, now, offer_level(thread["id"], now), thread.get("resume"))
    if resume is not None:
        thread["resume"] = resume
    current = (thread.get("resume") or {}).get("label")
    thread["done"] = _sorted_labels(set(thread.get("done") or []) | set(done_from(index, session, current)), index)
    viewed = {str(label) for label in session.get("viewed") or []}
    if index and index.get("solutions"):
        viewed |= {str(label) for label, s in (session.get("dwell") or {}).items() if float(s) >= VIEWED_DWELL_S}
    thread["viewed"] = _sorted_labels(set(thread.get("viewed") or []) | viewed, index)
    if thread.get("resume") and thread["resume"].get("page") and thread["ref"] and thread.get("thumb", {}).get("kind") == "page":
        thread["thumb"] = page_thumb(thread["ref"], thread["title"], thread["resume"]["page"], thread["resume"]["label"])
    thread["state"] = "paused" if thread.get("state") != "done" else "done"
    thread["updated"] = now
    return thread


def on_act(action: str, thread: dict, args: dict, now: str) -> dict | None:
    """Hook for resume_save / resume_accept (events.py). Returns the whole new thread, or None to let the
    hub's own handling stand (an explicit spot: { label, page?, y?, confirmed? })."""
    if action == "resume_accept":
        data = side(thread["id"])
        data["accepts"].append(now)
        _save_side(thread["id"], data)
        return None
    if action != "resume_save":
        return None
    session = args.get("session")
    if isinstance(session, dict):
        return merge_session(thread, session, now)
    if args.get("corrected"):
        data = side(thread["id"])
        data["corrections"].append(now)
        _save_side(thread["id"], data)
    return None


# ---- the demo practice set: made up, drawn here, never one of his files ------------------------------------
DEMO_QUESTIONS = [
    "A 4 m beam AB is simply supported at A and B and carries a 6 kN point load 1.5 m from A. Find the "
    "reactions at A and B.",
    "A 2 m cantilever carries a uniform load of 3 kN/m along its whole length. Find the reaction force and the "
    "moment at the fixed support.",
    "Draw the free-body diagram of the 40 kg crate resting on a 25° slope, with friction acting up the slope.",
    "Two cables hold a 120 N sign. Cable AC makes 30° and cable BC makes 45° with the horizontal. Find the "
    "tension in each cable.",
    "Find the resultant of the three forces acting on the bracket and the angle it makes with the x axis.",
    "A ladder 5 m long leans against a smooth wall with its foot 1.4 m from the wall. Find the least "
    "coefficient of friction at the floor that keeps it from slipping.",
    "The truss shown is pinned at A and on a roller at E, with a 10 kN load at C.",
    "Use the method of sections to find the force in members CD, CH and GH. State whether each is in tension "
    "or compression.",
    "A 3 m shaft carries two pulleys. Find the bearing reactions when the belt tensions are as shown.",
    "Locate the centroid of the composite plate made of a 200 × 100 mm rectangle with a 40 mm hole.",
    "Find the moment of inertia of the T-section about its centroidal x axis.",
    "A 15 kg drum rests between two smooth inclines of 30° and 60°. Find the normal force on each incline.",
]
DEMO_PARTS = {7: ["Find the support reactions at A and E.", "Find the force in member BC and say whether it is "
                  "in tension or compression."]}
DEMO_LAYOUT = [[1, 2, 3], [4, 5, 6], [7, 8], [9, 10], [11, 12]]  # questions per page: Q7 opens page 3


def make_demo_pps(path: str | Path) -> Path:
    """Write the demo 'PPS 7' (GE 122, five pages, twelve questions, Q7 with parts (a) and (b))."""
    import pymupdf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    for number, questions in enumerate(DEMO_LAYOUT, 1):
        page = doc.new_page(width=612, height=792)
        y = 72
        if number == 1:
            page.insert_text((72, y + 14), "GE 122  ·  Problem-Solving Set 7", fontsize=16, fontname="hebo")
            page.insert_text((72, y + 36), "Statics: equilibrium, trusses and centroids. Due Wednesday at 8 pm.",
                             fontsize=10, fontname="helv")
            y += 72
        for n in questions:
            page.insert_text((72, y + 11), f"{n}.", fontsize=11, fontname="hebo")
            rect = pymupdf.Rect(100, y, 540, y + 80)
            spare = page.insert_textbox(rect, DEMO_QUESTIONS[n - 1], fontsize=11, fontname="helv", lineheight=1.35)
            y += 80 - spare + 14
            for i, part in enumerate(DEMO_PARTS.get(n, [])):
                page.insert_text((100, y + 11), f"({'ab'[i]})", fontsize=11, fontname="helv")
                spare = page.insert_textbox(pymupdf.Rect(128, y, 540, y + 60), part, fontsize=11, fontname="helv",
                                            lineheight=1.35)
                y += 60 - spare + 10
            y += 150  # working space
        page.insert_text((300, 760), str(number), fontsize=9, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path
