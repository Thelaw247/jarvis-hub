"""Recall (MEMORY §7.3-§7.4): FTS5 BM25 + vector KNN, filtered to a branch subtree when one is given, fused
with reciprocal rank fusion, filtered by time and privacy, collapsed to each claim's winner, tagged.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from . import tree
from .db import vec_table
from .embeddings import Embedder, pack
from .model import Hit
from .reconcile import winner
from .util import norm
from .views import tag

TOP_N = 50
SMALL_SUBTREE = 2000
RRF_K = 60
_WORD = re.compile(r"\w+")
_STOP = frozenset("a an and are at be did do does for from i in is it me my of on or the to was what when where "
                  "which who why with you your".split())


def fts_query(text: str, *, partial: bool = False) -> str | None:
    """Words -> an OR query of quoted terms (safe from FTS5 syntax). A trailing partial word gets a prefix *."""
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
    if not words:
        return None
    terms = [f'"{w}"' for w in words]
    if partial and not text[-1:].isspace():
        terms[-1] += "*"
    return " OR ".join(dict.fromkeys(terms))


def _time_filter(at: str | None, as_of: str | None, now: str) -> tuple[str, list[Any]]:
    if as_of:   # what Jarvis believed at system time as_of
        return "recorded_at <= ? AND (retired_at IS NULL OR retired_at > ?)", [as_of, as_of]
    if at:      # what was true in the world at time `at`
        return ("status IN ('active','superseded') AND (valid_from IS NULL OR valid_from <= ?)"
                " AND (valid_to IS NULL OR valid_to > ?)"), [at, at]
    return "status = 'active' AND (valid_to IS NULL OR valid_to > ?)", [now]


def search(conn: sqlite3.Connection, embedders: dict[str, Embedder], query: str, *, now: str,
           branch: str | None = None, k: int = 10, at: str | None = None, as_of: str | None = None,
           widen: bool = True, space: str = "index", include_tier2: bool = False, partial: bool = False) -> list[Hit]:
    """Tier: T1 (deep recall, ~10-40 ms of SQL) or the hot path with space='fast', k=5, partial=True."""
    bounds = None
    if branch:
        slug = tree.resolve(conn, branch)
        row = tree.branch_row(conn, slug) if slug else None
        if row is None:
            raise KeyError(f"no branch {branch!r}")
        bounds = tree.subtree_bounds(row["path"])
        if tree.effective_tier(conn, slug) == 2:
            include_tier2 = True   # he asked about a tier-2 branch on purpose
    hits = _search(conn, embedders, query, now=now, bounds=bounds, k=k, at=at, as_of=as_of, space=space,
                   include_tier2=include_tier2, partial=partial)
    if not hits and bounds is not None and widen:
        hits = _search(conn, embedders, query, now=now, bounds=None, k=k, at=at, as_of=as_of, space=space,
                       include_tier2=False, partial=partial)
    return hits


def _search(conn: sqlite3.Connection, embedders: dict[str, Embedder], query: str, *, now: str,
            bounds: tuple[str, str] | None, k: int, at: str | None, as_of: str | None, space: str,
            include_tier2: bool, partial: bool) -> list[Hit]:
    # The subtree filter is one indexed range on branches.path. SQLite would push an IN(...) filter into
    # FTS5 and re-run the match per row (~0.7 s at 10k), so the match is materialised once and filtered after.
    sub_ids: set[int] | None = None
    if bounds:
        sub_ids = {r[0] for r in conn.execute(
            "SELECT l.item_id FROM branch_links l JOIN branches b ON b.id = l.branch_id"
            " WHERE l.item_type = 'fact' AND b.path >= ? AND b.path < ?", bounds)}
        if not sub_ids:
            return []
    scores: dict[int, float] = {}
    q = fts_query(query, partial=partial)
    if q:
        if bounds:
            rows = conn.execute(
                "WITH m AS MATERIALIZED (SELECT rowid AS id, rank AS r FROM facts_fts WHERE facts_fts MATCH ?)"
                " SELECT id FROM m WHERE id IN (SELECT l.item_id FROM branch_links l JOIN branches b"
                " ON b.id = l.branch_id WHERE l.item_type = 'fact' AND b.path >= ? AND b.path < ?)"
                f" ORDER BY r LIMIT {TOP_N}", [q, *bounds]).fetchall()
        else:
            rows = conn.execute(f"SELECT rowid FROM facts_fts WHERE facts_fts MATCH ? ORDER BY rank LIMIT {TOP_N}",
                                [q]).fetchall()
        for rank, r in enumerate(rows):
            scores[r[0]] = scores.get(r[0], 0.0) + 1.0 / (RRF_K + rank + 1)
    emb = embedders.get(space)
    if emb is not None and query.strip():
        vec = pack(emb.embed([query])[0])
        vt = vec_table(space, "facts")
        if sub_ids is None:
            rows = conn.execute(f"SELECT rowid FROM {vt} WHERE embedding MATCH ? AND k = {TOP_N}", [vec]).fetchall()
        elif len(sub_ids) <= SMALL_SUBTREE:
            rows = conn.execute(f"SELECT rowid FROM {vt} WHERE embedding MATCH ? AND k = {TOP_N}"
                                " AND rowid IN (SELECT value FROM json_each(?))",
                                [vec, json.dumps(sorted(sub_ids))]).fetchall()
        else:   # a big subtree: over-fetch the nearest and filter (cheaper than a huge IN list)
            total = conn.execute("SELECT count(*) FROM facts").fetchone()[0] or 1
            kk = min(4096, max(TOP_N, int(TOP_N * 3 * total / len(sub_ids))))
            rows = [r for r in conn.execute(f"SELECT rowid FROM {vt} WHERE embedding MATCH ? AND k = {kk}", [vec])
                    if r[0] in sub_ids][:TOP_N]
        for rank, r in enumerate(rows):
            scores[r[0]] = scores.get(r[0], 0.0) + 1.0 / (RRF_K + rank + 1)
    if not scores:
        return []
    tf_sql, tf_args = _time_filter(at, as_of, now)
    tier_sql = "" if include_tier2 else " AND privacy_tier < 2"
    ids = list(scores)
    rows = conn.execute(f"SELECT * FROM facts WHERE id IN ({','.join('?' * len(ids))}) AND {tf_sql}{tier_sql}",
                        [*ids, *tf_args]).fetchall()

    # authority collapse: each (subject, predicate, scope) -> its winner, with the loser kept for one line
    groups: dict[Any, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        key = (d["subject_id"], d["predicate"], d["scope"]) if d["subject_id"] and d["predicate"] else ("id", d["id"])
        g = groups.setdefault(key, {"score": 0.0, "rows": {}})
        g["score"] = max(g["score"], scores[d["id"]])
        g["rows"][d["id"]] = d
    hits: list[Hit] = []
    for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["score"])[:k]:
        members = list(g["rows"].values())
        if key[0] != "id":
            members = [dict(m) for m in conn.execute(
                f"SELECT * FROM facts WHERE subject_id=? AND predicate=? AND scope IS ? AND {tf_sql}{tier_sql}",
                [*key, *tf_args]).fetchall()] or members
        best = winner(members)
        others = [m for m in members if m["id"] != best["id"]]
        conflict = None
        if others:
            loser = next((m for m in others if m["conflicts_with"] == best["id"] or best["conflicts_with"] == m["id"]),
                         None)
            if loser is not None:
                conflict = _hit(conn, loser, 0.0)
        hits.append(_hit(conn, best, g["score"], conflict))
    hits.sort(key=lambda h: -h.score)
    return hits[:k]


def _hit(conn: sqlite3.Connection, d: dict[str, Any], score: float, conflict: Hit | None = None) -> Hit:
    link = conn.execute("SELECT branch_id FROM branch_links WHERE item_type='fact' AND item_id=? AND role='primary'",
                        (d["id"],)).fetchone()
    return Hit(fact_id=d["id"], text=d["text"], tag=tag(d), score=score, authority=d["authority"], kind=d["kind"],
               claim_type=d["claim_type"], status=d["status"], branch=link[0] if link else None,
               valid_from=d["valid_from"], valid_to=d["valid_to"], privacy_tier=d["privacy_tier"], conflict=conflict)


def branch_for_partial(conn: sqlite3.Connection, partial: str) -> str | None:
    """If a speech partial names exactly one branch (name or alias), return it: its card is attached instead."""
    text = f" {norm(partial)} "
    found = []
    for row in conn.execute("SELECT id, name, aliases FROM branches WHERE status='active' AND level >= 1"):
        names = [norm(row["name"]), *(norm(a) for a in json.loads(row["aliases"]))]
        if any(n and (len(n) >= 4 or any(ch.isdigit() for ch in n)) and f" {n} " in text for n in names):
            found.append(row["id"])
    return found[0] if len(found) == 1 else None
