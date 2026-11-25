"""work_on: find the work he means (jarvis.reach.workfiles), open it on his laptop, put its deadline on the hub."""
import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path

from jarvis.reach import workfiles
from jarvis.reach.classes import slug, when
from jarvis.tools.base import Result, ToolContext, ToolError

CLAUDE_APP, CLAUDE_WEB = "claude://", "https://claude.ai/new"


def claude_running() -> bool:
    """Is the Claude app already open? (Windows task list; anywhere else: assume not.)"""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"], capture_output=True, text=True, timeout=4,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "claude.exe" in out.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


OPEN = getattr(os, "startfile", None)   # Windows: the file's own app. None elsewhere (then nothing is opened)
MAX_OPEN = 2


def due_id(key: str) -> str:
    return f"due-{slug(key)[:40]}"


async def run(args: dict, ctx: ToolContext) -> Result:
    cc = ctx.classes
    ask = str(args.get("what") or "").strip()
    if not ask:
        raise ToolError("What should I pull up? Give the course or the piece of work, like 'GE 122 practice 6'.")
    now = datetime.now()
    work = workfiles.find(cc, ask, now)
    if work is None:
        codes = ", ".join(str(c["course"]) for c in cc.courses()) or "none on file"
        raise ToolError(f"Nothing in his Class Content folder matches {ask!r}. His courses: {codes}. Ask him which course or which number.")
    root = cc.root.resolve()
    files = [f for f in work.files if root in f.resolve().parents][:MAX_OPEN]   # never anything outside Class Content
    opened: list[str] = []
    here = bool(getattr(ctx, "here", False))
    hands = getattr(ctx, "hands", None) if not here else None   # he is at the other laptop: its voice program opens it there
    can = (here and OPEN is not None) or hands is not None

    async def put(what) -> bool:
        """Open a file or folder inside Class Content, or a web page, on the laptop he is at."""
        try:
            if here:
                OPEN(str(what))
                return True
            if isinstance(what, Path):
                answer = await hands("open", {"file": what.resolve().relative_to(root).as_posix()})
            else:
                answer = await hands("open", {"url": str(what)})
            return bool(answer.get("ok"))
        except Exception:  # noqa: BLE001 - it didn't open; the reply says where it is instead
            return False

    extra = [str(a) for a in (args.get("also") or []) if a in ("claude", "lecture_notes", "course_page")]
    if can:
        for f in files or ([work.path] if work.path is not None and work.path.is_dir() else []):
            if await put(f):
                opened.append(f.name)
        if work.url and not files and await put(work.url):   # it lives online (WebAssign, a Canvas quiz): its own page
            opened.append("its page in your browser")
        folder = workfiles.course_folder(cc, work.course)
        if "lecture_notes" in extra and folder is not None:
            lectures = sorted((p for p in (folder / "Lectures").glob("L[0-9]*") if p.is_dir()), key=lambda p: p.name) if (folder / "Lectures").is_dir() else []
            for f in (workfiles._openable(lectures[-1])[:1] if lectures else []):
                if await put(f):
                    opened.append(f"the notes for {lectures[-1].name.split(' - ')[-1]}")
        if "course_page" in extra and folder is not None and (folder / "index.html").is_file() and await put(folder / "index.html"):
            opened.append("the course page")
        if "claude" in extra:
            if here:
                if await asyncio.to_thread(claude_running):
                    opened.append("Claude (it was open already)")
                elif await put(CLAUDE_APP):
                    opened.append("Claude")
                elif await put(CLAUDE_WEB):
                    opened.append("Claude in your browser")
            else:
                try:
                    answer = await hands("open", {"app": "claude"})
                    if answer.get("ok"):
                        opened.append("Claude (it was open already)" if answer.get("was_open") else "Claude")
                except Exception:  # noqa: BLE001
                    pass
    if ctx.publish is not None and work.url:   # Canvas can't be framed in the hub: a card that opens it in his browser
        await ctx.show("window.push", {"id": f"w-web-{slug(work.course)}-{slug(work.label)[:24]}", "type": "web", "size": "2x1",
                                       "title": f"{work.course} {work.label}"[:120],
                                       "data": {"pages": [{"id": "p-work", "url": work.url, "title": work.label[:120], "frame": "no"}], "active": "p-work"}})
    if ctx.publish is not None:   # the hub: the deadline, then the course (its next classes and what else is due)
        if work.due is not None:
            await ctx.show("window.push", {"id": f"w-{due_id(work.due.key)}", "type": "countdown", "title": f"{work.course} {work.due.title}",
                                           "ref": due_id(work.due.key)})
        await ctx.show("window.push", {"id": f"w-{slug(work.course)}", "type": "branch_card", "title": work.course, "ref": slug(work.course)})
    said = [f"{work.course} · {work.label}" + (f" ({work.why})" if work.why else "")]
    if opened:
        said.append("Opened on his laptop: " + ", ".join(opened) + ".")
    elif work.path is not None:
        where = str(work.path.relative_to(cc.root)) if root in work.path.resolve().parents else work.path.name
        reason = ("there is no file in it to open, or it would not open on the laptop he is at" if can else
                  "he is talking from the other laptop and its voice program isn't reachable" if not here else
                  "this isn't a Windows laptop")
        said.append(f"Not opened ({reason}). It is in Class Content: {where}.")
    elif work.url:
        said.append(f"It lives online and wasn't opened ({'the laptop he is at did not open it; if that keeps happening, closing and reopening Jarvis Hub there fixes it' if not here else 'this is not a Windows laptop'}): {work.url}")
    else:
        said.append("There is no folder for it in Class Content yet, so nothing was opened.")
    if work.due is not None:
        said.append(f"Due {when(work.due.due, now)}" + (f" on {work.due.platform}" if work.due.platform else "")
                    + (f", about {work.due.remaining_min} minutes of work left." if work.due.remaining_min else "."))
    return Result(" ".join(said))
