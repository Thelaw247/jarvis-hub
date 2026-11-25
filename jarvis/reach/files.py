"""His files, with limits (v0.26.0, his ask and his boundaries on 22 Nov).

Jarvis may create a text file, make a folder, and move or rename things, in four places only: Class Content, Desktop,
Documents and Downloads on the laptop he is at. He never deletes, never overwrites, and never writes a file Windows
would run. Every change is written to an undo list and can be taken back. The tool that calls this asks him first
(jarvis.tools.files); this module only checks and does. T1.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path

from jarvis.reach.classes import find_root

PLACES = ("class_content", "desktop", "documents", "downloads")
NAMES = {"class_content": "Class Content", "desktop": "Desktop", "documents": "Documents", "downloads": "Downloads"}
WRITABLE = (".txt", ".md", ".csv", ".json", ".tex", ".html", ".py", ".c", ".cpp", ".h", ".ino", ".m")   # text he can read; nothing Windows runs
MAX_CHARS = 200_000
BAD = set('<>:"|?*')


class Refused(Exception):
    """A change this module will not make. The message is for Jarvis to put to him in plain words."""


def places(home: Path | None = None, env: dict | None = None) -> dict[str, Path]:
    """The four folders on this laptop (Desktop and Documents may live inside OneDrive)."""
    home, env = home or Path.home(), env if env is not None else os.environ
    first = lambda *c: next((p for p in c if p.is_dir()), None)  # noqa: E731
    table = {"class_content": find_root(env, home), "desktop": first(home / "OneDrive" / "Desktop", home / "Desktop"),
             "documents": first(home / "OneDrive" / "Documents", home / "Documents"), "downloads": first(home / "Downloads")}
    return {k: v.resolve() for k, v in table.items() if v is not None}


def spot(table: dict[str, Path], place: str, rel: str, *, allow_root: bool = False) -> Path:
    """A path inside one of the four folders, or Refused. `rel` is always relative: never a drive, never '..' out."""
    if place not in table:
        raise Refused(f"'{place}' isn't one of his folders here. The ones to use: {', '.join(table) or 'none found'}.")
    rel = str(rel or "").replace("\\", "/").strip().strip("/")
    if not rel and not allow_root:
        raise Refused("Say which file or folder, by its name inside that place.")
    if any(c in BAD for c in rel) or any(part in ("..", ".") or part.endswith((" ", ".")) for part in rel.split("/") if rel):
        raise Refused("That name has characters Windows doesn't allow, or tries to leave the folder.")
    base = table[place]
    target = (base / rel).resolve() if rel else base
    if target != base and base not in target.parents:
        raise Refused("That would be outside his folders. Nothing was changed.")
    return target


def label(table: dict[str, Path], path: Path) -> str:
    for place, base in table.items():
        if path == base or base in path.parents:
            inner = path.relative_to(base).as_posix()
            return f"{NAMES[place]} > {inner.replace('/', ' > ')}" if inner != "." else NAMES[place]
    return path.name


def plan(args: dict, table: dict[str, Path]) -> dict:
    """Check one change and describe it. → {"action", "src", "dst", "words"}; raises Refused. Changes nothing."""
    action = str(args.get("action") or "")
    if action == "create":
        dst = spot(table, str(args.get("place")), str(args.get("path")))
        if dst.suffix.lower() not in WRITABLE:
            raise Refused(f"I can write these kinds of file: {', '.join(WRITABLE)}. Not '{dst.suffix or 'no ending'}'.")
        if len(str(args.get("content") or "")) > MAX_CHARS:
            raise Refused("That is too long for one file.")
        if dst.exists():
            raise Refused(f"{label(table, dst)} already exists, and I don't overwrite. Pick another name.")
        return {"action": action, "src": None, "dst": dst, "words": f"Create {label(table, dst)}"}
    if action == "folder":
        dst = spot(table, str(args.get("place")), str(args.get("path")))
        if dst.exists():
            raise Refused(f"{label(table, dst)} is already there.")
        return {"action": action, "src": None, "dst": dst, "words": f"Make the folder {label(table, dst)}"}
    if action == "move":
        src = spot(table, str(args.get("place")), str(args.get("path")))
        if not src.exists():
            near = sorted(p.name for p in src.parent.iterdir())[:12] if src.parent.is_dir() else []
            raise Refused(f"There is no {label(table, src)}." + (f" In that folder: {', '.join(near)}." if near else ""))
        dst = spot(table, str(args.get("to_place") or args.get("place")), str(args.get("to_path") or ""), allow_root=True)
        if dst.is_dir():                       # "into that folder": it keeps its name
            dst = dst / src.name
        if dst.exists():
            raise Refused(f"{label(table, dst)} already exists, and I don't overwrite. Nothing was moved.")
        if src == dst or src in dst.parents:
            raise Refused("That would move it into itself.")
        if not dst.parent.is_dir():
            raise Refused(f"There is no folder {label(table, dst.parent)}. Make it first (action folder), then move.")
        verb = "Rename" if src.parent == dst.parent else "Move"
        return {"action": action, "src": src, "dst": dst, "words": f"{verb} {label(table, src)} to {label(table, dst)}"}
    raise Refused("Use action create, folder, move or undo.")


def undo_log(root: Path | None = None) -> Path:
    return (root or Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")) / "undo" / "files.jsonl"


def _note(log: Path, entry: dict) -> None:
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass   # the change still stands; it just can't be taken back from the list


def undo(table: dict[str, Path], log: Path) -> dict:
    """Take back the last change that hasn't been taken back. A created file or folder is set aside, not deleted."""
    try:
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError):
        entries = []
    done = {e.get("undoes") for e in entries if e.get("undoes")}
    last = next((e for e in reversed(entries) if e.get("id") and e["id"] not in done and not e.get("undoes")), None)
    if last is None:
        return {"ok": False, "why": "There is nothing of mine to take back."}
    dst, src = Path(last["dst"]), Path(last["src"]) if last.get("src") else None
    if not dst.exists():
        return {"ok": False, "why": f"{dst.name} isn't where I left it, so I left things alone."}
    if last["action"] == "move":
        if src.exists() or not src.parent.is_dir():
            return {"ok": False, "why": f"Its old place is taken or gone, so {dst.name} stays where it is."}
        shutil.move(str(dst), str(src))
        words = f"Put {dst.name} back in {label(table, src.parent)}"
    else:
        aside = log.parent / "set-aside" / f"{int(time.time())}-{dst.name}"
        aside.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(aside))
        words = f"Took {dst.name} back out (set aside, not deleted)"
    _note(log, {"id": uuid.uuid4().hex[:12], "undoes": last["id"], "action": "undo", "dst": str(dst)})
    return {"ok": True, "did": words}


def run(args: dict | None, *, table: dict[str, Path] | None = None, log: Path | None = None) -> dict:
    """One request, start to finish. args: action, place, path, [content], [to_place], [to_path], [dry].
    → {"ok": True, "plan": words} for dry, {"ok": True, "did": words} when done, {"ok": False, "why": words}."""
    args = args if isinstance(args, dict) else {}
    table = table if table is not None else places()
    log = log or undo_log()
    try:
        if args.get("action") == "undo":
            return undo(table, log) if not args.get("dry") else {"ok": True, "plan": "Take back my last file change"}
        step = plan(args, table)
        if args.get("dry"):
            return {"ok": True, "plan": step["words"]}
        dst, src = step["dst"], step["src"]
        if step["action"] == "create":
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open("x", encoding="utf-8", newline="\n") as f:   # "x": never over something that appeared meanwhile
                f.write(str(args.get("content") or ""))
        elif step["action"] == "folder":
            dst.mkdir(parents=True)
        else:
            shutil.move(str(src), str(dst))
        _note(log, {"id": uuid.uuid4().hex[:12], "action": step["action"], "src": str(src) if src else None, "dst": str(dst)})
        return {"ok": True, "did": step["words"].replace("Create", "Created").replace("Make the", "Made the").replace("Rename", "Renamed").replace("Move", "Moved", 1)}
    except Refused as no:
        return {"ok": False, "why": str(no)}
    except OSError as exc:
        return {"ok": False, "why": f"Windows wouldn't let me ({type(exc).__name__}). Nothing else was changed."}
