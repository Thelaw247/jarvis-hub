"""Audited row edits: every change to memory is a `changes` row plus one `audit` row per row touched,
with the exact before and after (MEMORY §9). Search indexes (FTS5, vec0) follow the rows in code.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from .db import vec_table
from .embeddings import Embedder, pack, zeros

# Columns never copied into audit snapshots (episodes are insert/forget only; their text stays in one place).
_SNAPSHOT_SKIP = {"episodes": {"content"}}
_INDEXED = {"facts", "episodes", "entities"}


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {k: row[k] for k in row.keys()}


class Indexer:
    """Keeps FTS5 and vec0 in step with facts, episodes and entities. Runs on the writer thread only."""

    def __init__(self, embedders: dict[str, Embedder]) -> None:
        self.embedders = embedders

    @staticmethod
    def fact_doc(row: dict[str, Any]) -> str:
        return row["text"] if not row.get("fact_keys") else f"{row['text']} {row['fact_keys']}"

    @staticmethod
    def _fts_values(tbl: str, row: dict[str, Any]) -> tuple[str, ...]:
        if tbl == "facts":
            return (row["text"], row["fact_keys"] or "", row["corrective_context"] or "")
        return (row["content"],)

    def index(self, conn: sqlite3.Connection, tbl: str, rowid: int) -> None:
        """Add a row to the indexes. Call unindex first if it was indexed before."""
        row = row_dict(conn.execute(f"SELECT * FROM {tbl} WHERE rowid=?", (rowid,)).fetchone())
        if row is None:
            return
        if tbl == "facts":
            conn.execute("INSERT INTO facts_fts(rowid, text, fact_keys, corrective) VALUES (?,?,?,?)",
                         (rowid, *self._fts_values(tbl, row)))
            self._embed(conn, "facts", rowid, self.fact_doc(row))
        elif tbl == "episodes":
            conn.execute("INSERT INTO episodes_fts(rowid, content) VALUES (?,?)", (rowid, *self._fts_values(tbl, row)))
        elif tbl == "entities":
            names = [row["canonical_name"], *json.loads(row["aliases"])]
            self._embed(conn, "entities", rowid, " / ".join(names))

    def _embed(self, conn: sqlite3.Connection, item: str, rowid: int, text: str) -> None:
        for space, emb in self.embedders.items():
            vec = emb.embed([text])[0]
            conn.execute(f"INSERT INTO {vec_table(space, item)}(rowid, embedding) VALUES (?,?)", (rowid, pack(vec)))

    def unindex(self, conn: sqlite3.Connection, tbl: str, rowid: int) -> None:
        """Remove a row from the indexes, using its current (still indexed) values. Call before changing it."""
        if tbl in ("facts", "episodes"):
            row = row_dict(conn.execute(f"SELECT * FROM {tbl} WHERE rowid=?", (rowid,)).fetchone())
            if row is not None:
                vals = self._fts_values(tbl, row)
                cols = "text, fact_keys, corrective" if tbl == "facts" else "content"
                conn.execute(f"INSERT INTO {tbl}_fts({tbl}_fts, rowid, {cols}) VALUES ('delete', ?, {', '.join('?' * len(vals))})",
                             (rowid, *vals))
        if tbl in ("facts", "entities"):
            for space, emb in self.embedders.items():
                vt = vec_table(space, tbl)
                if conn.execute(f"SELECT 1 FROM {vt} WHERE rowid=?", (rowid,)).fetchone():
                    # overwrite the stored vector before deleting it, so its bytes don't linger in a chunk
                    conn.execute(f"UPDATE {vt} SET embedding=? WHERE rowid=?", (zeros(emb.dim), rowid))
                    conn.execute(f"DELETE FROM {vt} WHERE rowid=?", (rowid,))


class Tx:
    """One logical change. Use through MemoryStore's writer only (single writer)."""

    def __init__(self, conn: sqlite3.Connection, indexer: Indexer, *, op: str, session_id: str | None,
                 now: str, undo_of: int | None = None) -> None:
        self.conn, self.indexer, self.now = conn, indexer, now
        self.change_id = conn.execute(
            "INSERT INTO changes(ts, session_id, op, undo_of) VALUES (?,?,?,?)", (now, session_id, op, undo_of)
        ).lastrowid
        self.seq = 0
        self.branches: set[str] = set()
        self.on_branch_change: list[Callable[[str], None]] = []

    # ---- reads ----
    def get(self, tbl: str, rowid: int) -> dict[str, Any] | None:
        return row_dict(self.conn.execute(f"SELECT rowid AS _rowid, * FROM {tbl} WHERE rowid=?", (rowid,)).fetchone())

    # ---- audited writes ----
    def _audit(self, tbl: str, rowid: int, before: dict | None, after: dict | None) -> None:
        self.seq += 1
        self.conn.execute(
            "INSERT INTO audit(change_id, seq, tbl, row_id, before, after) VALUES (?,?,?,?,?,?)",
            (self.change_id, self.seq, tbl, rowid, _snap(tbl, before), _snap(tbl, after)),
        )

    def insert(self, tbl: str, values: dict[str, Any], *, rowid: int | None = None) -> int:
        cols = list(values)
        args = [values[c] for c in cols]
        if rowid is not None:
            cols, args = ["rowid", *cols], [rowid, *args]
        new_id = self.conn.execute(
            f"INSERT INTO {tbl}({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", args
        ).lastrowid
        if tbl in _INDEXED:
            self.indexer.index(self.conn, tbl, new_id)
        self._audit(tbl, new_id, None, self.get(tbl, new_id))
        self._touch(tbl, new_id)
        return new_id

    def update(self, tbl: str, rowid: int, values: dict[str, Any]) -> dict[str, Any]:
        before = self.get(tbl, rowid)
        if before is None:
            raise KeyError(f"{tbl} {rowid} not found")
        if all(before.get(k) == v for k, v in values.items()):
            return before
        reindex = tbl in _INDEXED and bool(
            {"text", "fact_keys", "corrective_context", "canonical_name", "aliases"} & set(values))
        if reindex:
            self.indexer.unindex(self.conn, tbl, rowid)
        sets = ", ".join(f"{k}=?" for k in values)
        self.conn.execute(f"UPDATE {tbl} SET {sets} WHERE rowid=?", [*values.values(), rowid])
        if reindex:
            self.indexer.index(self.conn, tbl, rowid)
        self._audit(tbl, rowid, before, self.get(tbl, rowid))
        self._touch(tbl, rowid)
        return before

    def delete(self, tbl: str, rowid: int) -> dict[str, Any] | None:
        before = self.get(tbl, rowid)
        if before is None:
            return None
        self._touch(tbl, rowid)
        if tbl in _INDEXED:
            self.indexer.unindex(self.conn, tbl, rowid)
        self.conn.execute(f"DELETE FROM {tbl} WHERE rowid=?", (rowid,))
        self._audit(tbl, rowid, before, None)
        return before

    # ---- branch bookkeeping (for branch cards' "recent" and card rebuilds) ----
    def _touch(self, tbl: str, rowid: int) -> None:
        if tbl == "branch_links":
            row = self.conn.execute("SELECT branch_id FROM branch_links WHERE rowid=?", (rowid,)).fetchone()
            if row:
                self.branches.add(row[0])
        elif tbl == "branches":
            row = self.conn.execute("SELECT id FROM branches WHERE rowid=?", (rowid,)).fetchone()
            if row:
                self.branches.add(row[0])
        elif tbl in ("facts", "entities", "episodes", "open_loops", "patterns"):
            item = {"facts": "fact", "entities": "entity", "episodes": "episode", "open_loops": "open_loop",
                    "patterns": "pattern"}[tbl]
            self.branches.update(r[0] for r in self.conn.execute(
                "SELECT branch_id FROM branch_links WHERE item_type=? AND item_id=?", (item, rowid)))

    def finish(self, summary: str = "") -> int:
        """Record which branches this change touched. Returns the change id."""
        self.conn.execute("UPDATE changes SET summary=? WHERE id=?", (summary, self.change_id))
        self.conn.executemany("INSERT OR IGNORE INTO change_branches(change_id, branch_id) VALUES (?,?)",
                              [(self.change_id, b) for b in self.branches])
        return self.change_id


def _snap(tbl: str, row: dict[str, Any] | None) -> str | None:
    if row is None:
        return None
    skip = _SNAPSHOT_SKIP.get(tbl, set())
    return json.dumps({k: v for k, v in row.items() if k not in skip and not isinstance(v, bytes)}, sort_keys=True)


def chunks(ids: Iterable[int], size: int = 500) -> Iterable[list[int]]:
    buf: list[int] = []
    for i in ids:
        buf.append(i)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf
