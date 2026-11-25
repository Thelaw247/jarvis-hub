"""Undo from audit rows (MEMORY §9): "undo that" reverses only that change.

Field by field: a field goes back to its before-value only if it still holds the value this change wrote.
If a later change has moved it on, the later change wins and the clash is reported, so later corrections
are never wiped. Undo is itself a change, so it can be undone too. There is no time limit.
Raw episodes are kept by undo (it reverses what was learned, not what was said); only forget removes them.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .model import UndoResult
from .tx import Tx
from .writes import Ctx

# Rows that point at a fact; while any exist (from other changes) the fact can't simply vanish.
_FACT_REFS = (
    ("fact_sources", "fact_id"), ("branch_links", "item_id"), ("procedures", "fact_id"),
    ("facts", "superseded_by"), ("facts", "conflicts_with"), ("corrections", "new_fact_id"),
    ("corrections", "wrong_fact_id"),
)


class UndoError(RuntimeError):
    pass


def _refs(conn: sqlite3.Connection, tbl: str, rowid: int) -> int:
    if tbl == "facts":
        n = 0
        for t, col in _FACT_REFS:
            extra = " AND item_type='fact'" if t == "branch_links" else ""
            n += conn.execute(f"SELECT count(*) FROM {t} WHERE {col}=?{extra}", (rowid,)).fetchone()[0]
        return n
    if tbl == "entities":
        return conn.execute("SELECT (SELECT count(*) FROM facts WHERE subject_id=:i OR object_id=:i)"
                            " + (SELECT count(*) FROM entity_names WHERE entity_id=:i)", {"i": rowid}).fetchone()[0]
    if tbl == "episodes":
        return conn.execute("SELECT count(*) FROM fact_sources WHERE episode_id=?", (rowid,)).fetchone()[0]
    if tbl == "branches":
        slug = conn.execute("SELECT id FROM branches WHERE rowid=?", (rowid,)).fetchone()[0]
        return conn.execute("SELECT (SELECT count(*) FROM branch_links WHERE branch_id=:s)"
                            " + (SELECT count(*) FROM branches WHERE parent_id=:s)", {"s": slug}).fetchone()[0]
    return 0


def undo_change(ctx: Ctx, change_id: int) -> UndoResult:
    conn = ctx.conn
    ch = conn.execute("SELECT * FROM changes WHERE id=?", (change_id,)).fetchone()
    if ch is None:
        raise UndoError(f"no change {change_id}")
    if ch["undone_by"] is not None:
        raise UndoError(f"change {change_id} was already undone")
    if ch["forgotten"] or ch["op"] == "forget":
        raise UndoError("a forget can't be undone, and neither can changes to forgotten items")
    tx = ctx.tx("undo", undo_of=change_id)
    conflicts: list[str] = []
    rows = conn.execute("SELECT * FROM audit WHERE change_id=? ORDER BY seq DESC", (change_id,)).fetchall()
    for a in rows:
        tbl, rowid = a["tbl"], a["row_id"]
        before = json.loads(a["before"]) if a["before"] else None
        after = json.loads(a["after"]) if a["after"] else None
        current = tx.get(tbl, rowid)
        if before is None:                      # it was inserted: remove it, unless later work depends on it
            if current is None or tbl == "episodes":   # raw episodes stay; only "forget" removes them
                continue
            if _refs(conn, tbl, rowid):
                conflicts.append(f"{tbl} {rowid}: kept, later changes depend on it")
                continue
            tx.delete(tbl, rowid)
        elif after is None:                     # it was deleted: put it back
            if current is not None:
                conflicts.append(f"{tbl} {rowid}: exists again, left as is")
                continue
            if tbl == "episodes":
                conflicts.append(f"episodes {rowid}: raw text isn't kept in the audit, can't restore")
                continue
            tx.insert(tbl, _cols(before), rowid=rowid)
        else:                                   # it was edited: revert the fields still as this change left them
            if current is None:
                conflicts.append(f"{tbl} {rowid}: gone since, nothing to revert")
                continue
            revert: dict[str, Any] = {}
            for f, old in before.items():
                if f == "_rowid" or after.get(f) == old:
                    continue
                if current.get(f) == after.get(f):
                    revert[f] = old
                else:
                    conflicts.append(f"{tbl} {rowid}.{f}: changed again later, kept the later value")
            if revert:
                tx.update(tbl, rowid, revert)
    conn.execute("UPDATE changes SET undone_by=? WHERE id=?", (tx.change_id, change_id))
    uid = tx.finish(f"undid change {change_id}")
    return UndoResult(uid, [change_id], conflicts)


def undo_session(ctx: Ctx, session_id: str) -> UndoResult:
    """"Undo everything you learned from that conversation": every change carrying that session id, newest first."""
    ids = [r[0] for r in ctx.conn.execute(
        "SELECT id FROM changes WHERE session_id=? AND undone_by IS NULL AND op NOT IN ('undo','forget')"
        " AND forgotten=0 ORDER BY id DESC", (session_id,))]
    out = UndoResult(None)
    for cid in ids:
        r = undo_change(ctx, cid)
        out.undone.append(cid)
        out.conflicts.extend(r.conflicts)
        out.change_id = r.change_id
    return out


def _cols(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in snapshot.items() if k != "_rowid"}


__all__ = ["UndoError", "undo_change", "undo_session", "Tx"]
