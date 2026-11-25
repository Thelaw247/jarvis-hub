"""Forget (MEMORY §9): the content goes from the rows, the indexes, the audit trail and the cards; a tombstone
(hashes and (subject, predicate) keys only) stops it being learned again. The store then checkpoints the WAL
with TRUNCATE. secure_delete and FTS5 secure-delete overwrite the old bytes.

Forget is deliberately *not* undoable and its own audit entry holds counts only.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from . import cards
from .model import ForgetResult
from .tx import chunks
from .util import key_hash, norm, text_hash
from .writes import Ctx


def _q(conn: sqlite3.Connection, sql: str, ids: Iterable[int]) -> list[sqlite3.Row]:
    out: list[sqlite3.Row] = []
    for chunk in chunks(ids):
        out += conn.execute(sql.format(ids=",".join("?" * len(chunk))), chunk).fetchall()
    return out


def plan(conn: sqlite3.Connection, episode_ids: Iterable[int], fact_ids: Iterable[int],
         entity_ids: Iterable[int]) -> tuple[set[int], set[int], set[int]]:
    """What goes: the episodes, every fact whose only support was those episodes, and named entities."""
    E, F, N = set(episode_ids), set(fact_ids), set(entity_ids)
    if N:
        for chunk in chunks(N):
            marks = ",".join("?" * len(chunk))
            F |= {r[0] for r in conn.execute(
                f"SELECT id FROM facts WHERE subject_id IN ({marks}) OR object_id IN ({marks})", [*chunk, *chunk])}
        # episodes that name the entity hold the text too
        for eid in N:
            names = [r[0] for r in conn.execute("SELECT name_norm FROM entity_names WHERE entity_id=?", (eid,))]
            for name in names:
                if name:
                    phrase = '"' + name.replace('"', "") + '"'
                    E |= {r[0] for r in conn.execute("SELECT rowid FROM episodes_fts WHERE episodes_fts MATCH ?",
                                                     (phrase,))}
    E |= {r[0] for r in _q(conn, "SELECT episode_id FROM fact_sources WHERE fact_id IN ({ids})", F)}
    # facts with no support left
    candidates = {r[0] for r in _q(conn, "SELECT fact_id FROM fact_sources WHERE episode_id IN ({ids})", E)}
    for fid in candidates - F:
        others = conn.execute("SELECT episode_id FROM fact_sources WHERE fact_id=?", (fid,)).fetchall()
        if all(o[0] in E for o in others):
            F.add(fid)
    return E, F, N


def forget_op(ctx: Ctx, *, episode_ids: Iterable[int] = (), fact_ids: Iterable[int] = (),
              entity_ids: Iterable[int] = (), preview: bool = False, now_ctx=None) -> ForgetResult:
    conn = ctx.conn
    E, F, N = plan(conn, episode_ids, fact_ids, entity_ids)
    if preview:
        return ForgetResult(None, sorted(E), sorted(F), sorted(N), preview=True)
    if not (E or F or N):
        return ForgetResult(None)
    idx = ctx.indexer
    now = ctx.now

    # tombstones first (from the rows, before they go): hashes and keys, never text
    tombs: set[tuple[str, str]] = set()
    for r in _q(conn, "SELECT hash FROM episodes WHERE id IN ({ids})", E):
        tombs.add(("content", r[0]))
    for r in _q(conn, "SELECT f.text_hash, f.predicate, e.canonical_name FROM facts f"
                      " LEFT JOIN entities e ON e.id=f.subject_id WHERE f.id IN ({ids})", F):
        tombs.add(("content", r[0]))
        if r[1] and r[2]:
            tombs.add(("claim_key", key_hash(r[2], r[1])))
    for r in _q(conn, "SELECT name_norm FROM entity_names WHERE entity_id IN ({ids})", N):
        tombs.add(("entity", text_hash(r[0])))
    conn.executemany("INSERT INTO tombstones(kind, hash, ts) VALUES (?,?,?) ON CONFLICT(kind, hash)"
                     " DO UPDATE SET lifted_at=NULL, ts=excluded.ts", [(k, h, now) for k, h in tombs])

    # which branches show this content (their cards get rebuilt)
    touched: set[str] = set()
    for item, ids in (("fact", F), ("episode", E), ("entity", N)):
        touched |= {r[0] for r in _q(conn, f"SELECT branch_id FROM branch_links WHERE item_type='{item}'"
                                           " AND item_id IN ({ids})", ids)}
    loops = {r[0] for r in _q(conn, "SELECT id FROM open_loops WHERE origin_episode IN ({ids})", E)}
    touched |= {r[0] for r in _q(conn, "SELECT branch_id FROM branch_links WHERE item_type='open_loop'"
                                       " AND item_id IN ({ids})", loops)}

    # remove every row that holds or points at it; remember (table, rowid) to scrub the audit
    gone: list[tuple[str, int]] = []

    def drop(tbl: str, where: str, ids: Iterable[int]) -> None:
        rows = _q(conn, f"SELECT rowid FROM {tbl} WHERE {where}", ids)
        for r in rows:
            if tbl in ("facts", "episodes", "entities"):
                idx.unindex(conn, tbl, r[0])
            conn.execute(f"DELETE FROM {tbl} WHERE rowid=?", (r[0],))
            gone.append((tbl, r[0]))

    for item, ids in (("fact", F), ("episode", E), ("entity", N), ("open_loop", loops)):
        drop("branch_links", f"item_type='{item}' AND item_id IN ({{ids}})", ids)
    drop("fact_sources", "fact_id IN ({ids})", F)
    drop("fact_sources", "episode_id IN ({ids})", E)
    drop("procedures", "fact_id IN ({ids})", F)
    drop("corrections", "wrong_fact_id IN ({ids})", F)
    drop("corrections", "new_fact_id IN ({ids})", F)
    drop("pattern_cites", "fact_id IN ({ids})", F)
    drop("pattern_cites", "episode_id IN ({ids})", E)
    drop("open_loops", "id IN ({ids})", loops)
    for col in ("superseded_by", "conflicts_with"):
        for chunk in chunks(F):
            conn.execute(f"UPDATE facts SET {col}=NULL WHERE {col} IN ({','.join('?' * len(chunk))})", chunk)
    drop("facts", "id IN ({ids})", F)
    drop("episodes", "id IN ({ids})", E)
    drop("entity_names", "entity_id IN ({ids})", N)
    for chunk in chunks(N):
        conn.execute(f"UPDATE branches SET entity_id=NULL WHERE entity_id IN ({','.join('?' * len(chunk))})", chunk)
    drop("entities", "id IN ({ids})", N)

    # scrub the audit trail: those rows' before/after held the content; changes that touched them can't be undone
    for tbl, rowid in gone:
        conn.execute("UPDATE audit SET before=NULL, after=NULL, forgotten=1 WHERE tbl=? AND row_id=?", (tbl, rowid))
    conn.execute("UPDATE changes SET forgotten=1 WHERE id IN (SELECT change_id FROM audit WHERE forgotten=1)")

    # one content-free entry for the Memory view ("1 item forgotten")
    n_items = len(E) + len(F) + len(N)
    change_id = conn.execute("INSERT INTO changes(ts, session_id, op, summary, forgotten) VALUES (?,?,?,?,1)",
                             (now, ctx.session_id, "forget",
                              f"{n_items} item{'s' if n_items != 1 else ''} forgotten")).lastrowid
    # cards and centroids that may have held it
    for slug in touched:
        conn.execute("UPDATE branches SET centroid=NULL WHERE id=?", (slug,))
    cards.rebuild_with_ancestors(conn, touched, now)
    cards.store_now_card(conn, now, now_ctx)
    return ForgetResult(change_id, sorted(E), sorted(F), sorted(N), tombstones=len(tombs))


__all__ = ["forget_op", "plan", "norm"]
