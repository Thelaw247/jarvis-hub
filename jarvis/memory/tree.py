"""Life Tree helpers (LIFE_TREE §3-§5): subtrees as one indexed range, tiers by inheritance, name lookup."""
from __future__ import annotations

import json
import re
import sqlite3

from .util import norm

UNSORTED = "unsorted"
ROOT = "root"


def subtree_bounds(path: str) -> tuple[str, str] | None:
    """'school/' -> ('school/', 'school0'): every path in the subtree sorts between them. Root -> None."""
    if not path:
        return None
    return path, path[:-1] + "0"   # '0' sorts right after '/'


def branch_row(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT rowid AS _rowid, * FROM branches WHERE id=?", (slug,)).fetchone()


def ancestors(conn: sqlite3.Connection, slug: str) -> list[str]:
    """The branch itself first, then its parents up to the root."""
    out: list[str] = []
    cur: str | None = slug
    while cur is not None:
        out.append(cur)
        row = conn.execute("SELECT parent_id FROM branches WHERE id=?", (cur,)).fetchone()
        cur = row[0] if row else None
    return out


def effective_tier(conn: sqlite3.Connection, slug: str) -> int:
    """A branch inherits its parent's privacy tier unless set (LIFE_TREE §10)."""
    for bid in ancestors(conn, slug):
        row = conn.execute("SELECT privacy_tier FROM branches WHERE id=?", (bid,)).fetchone()
        if row is not None and row[0] is not None:
            return int(row[0])
    return 1


def tier2_prefixes(conn: sqlite3.Connection) -> list[str]:
    """Paths of branches explicitly set to tier 2 (their whole subtree is tier 2)."""
    return [r[0] for r in conn.execute("SELECT path FROM branches WHERE privacy_tier=2")]


def resolve(conn: sqlite3.Connection, name: str) -> str | None:
    """A slug, a path or a spoken name/alias -> the branch slug (active first). None if unknown or ambiguous."""
    if conn.execute("SELECT 1 FROM branches WHERE id=?", (name,)).fetchone():
        return name
    path = name.strip("/") + "/"
    row = conn.execute("SELECT id FROM branches WHERE path=?", (path,)).fetchone()
    if row:
        return row[0]
    hits = names_matching(conn, norm(name))
    return hits[0] if len(hits) == 1 else None


def names_matching(conn: sqlite3.Connection, wanted: str) -> list[str]:
    hits = []
    for row in conn.execute("SELECT id, name, aliases FROM branches WHERE status != 'archived'"):
        names = {norm(row["name"]), *(norm(a) for a in json.loads(row["aliases"]))}
        if wanted in names or wanted.replace(" ", "") in {n.replace(" ", "") for n in names}:
            hits.append(row["id"])
    return hits


_COURSE = re.compile(r"\b([A-Za-z]{2,4})[ _-]?(\d{3})\b")


def course_codes(text: str) -> list[str]:
    """'GE 122', 'chem142', 'Class Content/GEOL 121/...' -> ['ge 122', 'chem 142', ...]."""
    return [f"{a.lower()} {b}" for a, b in _COURSE.findall(text)]


def slugify(name: str) -> str:
    return norm(name).replace(" ", "-") or "branch"
