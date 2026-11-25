"""Write operations. They run only on the writer thread, inside one transaction each (MEMORY §4).

Steps per claim: guard (C41) -> tombstones -> resolve entities -> place -> reconcile -> store + index + audit.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import tree
from .model import (
    AddResult,
    ChangeResult,
    ClaimIn,
    ClaimOutcome,
    ClaimType,
    EpisodeIn,
    Kind,
    PlaceResult,
    Trust,
)
from .reconcile import Candidate, decide, value_key
from .trust import guard_claim, privacy_tier_for, source_of, trust_for
from .tx import Indexer, Tx
from .util import iso, key_hash, norm, text_hash


@dataclass
class Ctx:
    conn: sqlite3.Connection
    indexer: Indexer
    now: str
    session_id: str | None = None

    def tx(self, op: str, undo_of: int | None = None) -> Tx:
        return Tx(self.conn, self.indexer, op=op, session_id=self.session_id, now=self.now, undo_of=undo_of)


# ---------------------------------------------------------------- tombstones

def tombstoned(conn: sqlite3.Connection, kind: str, h: str) -> int | None:
    row = conn.execute("SELECT rowid FROM tombstones WHERE kind=? AND hash=? AND lifted_at IS NULL", (kind, h)).fetchone()
    return None if row is None else row[0]


def lift(tx: Tx, rowid: int) -> None:
    """He said it again on purpose: the tombstone is lifted (audited, undoable)."""
    tx.update("tombstones", rowid, {"lifted_at": tx.now})


# ---------------------------------------------------------------- entities

def resolve_entity(tx: Tx, name: str | None, etype: str) -> int | None:
    """Exact alias match, else a new entity. (Embedding > 0.85 and the LLM judge come with the M1.2 pipeline.)"""
    if not name:
        return None
    key = norm(name)
    row = tx.conn.execute(
        "SELECT e.id FROM entity_names n JOIN entities e ON e.id = n.entity_id WHERE n.name_norm=?"
        " ORDER BY e.status = 'active' DESC, e.importance DESC LIMIT 1", (key,)).fetchone()
    if row:
        # bookkeeping only (not a change to what he's told Jarvis), so not audited
        tx.conn.execute("UPDATE entities SET last_seen=? WHERE id=?", (tx.now, row[0]))
        return int(row[0])
    eid = tx.insert("entities", {"type": etype, "canonical_name": name, "aliases": "[]", "first_seen": tx.now,
                                 "last_seen": tx.now})
    tx.insert("entity_names", {"entity_id": eid, "name_norm": key})
    return eid


# ---------------------------------------------------------------- placement (LIFE_TREE §5)

def decide_place(conn: sqlite3.Connection, text: str, *, branch: str | None = None, suggested: str | None = None,
                 entity_ids: tuple[int | None, ...] = ()) -> PlaceResult:
    """Rules first, then the entity's branch, else Unsorted with a guess. Tier: T2.

    Steps 3 (embedding match to branch centroids, >= 0.80 and >= 0.10 ahead) and 4 (LLM judge on the top 5)
    are stubs until the nightly centroids and the extractor exist (M1.2); they never place anything yet.
    """
    # 1a. a placement the caller knows by rule (Canvas course id -> course, Class Content path -> lecture)
    if branch:
        slug = tree.resolve(conn, branch)
        if slug:
            return PlaceResult(slug, "rule", 1.0)
    # 1b. course codes in the text or path
    for code in tree.course_codes(text):
        hits = tree.names_matching(conn, code)
        if len(hits) == 1:
            return PlaceResult(hits[0], "rule", 0.95)
    # 1c. a branch named in the text (whole words, distinctive names only)
    padded = f" {norm(text)} "
    named = []
    for row in conn.execute("SELECT id, name, aliases, level FROM branches WHERE status='active' AND level >= 2"):
        names = [norm(row["name"]), *(norm(a) for a in json.loads(row["aliases"]))]
        if any(len(n) >= 4 and f" {n} " in padded for n in names):
            named.append(row["id"])
    if len(named) == 1:
        return PlaceResult(named[0], "rule", 0.9)
    # 2. the subject or object entity already lives on a branch
    for eid in entity_ids:
        if eid is None:
            continue
        row = conn.execute("SELECT id FROM branches WHERE entity_id=? AND status='active'", (eid,)).fetchone() or \
            conn.execute("SELECT branch_id FROM branch_links WHERE item_type='entity' AND item_id=? AND role='primary'",
                         (eid,)).fetchone()
        if row:
            return PlaceResult(row[0], "entity", 0.85)
    # 3-4. embedding centroids and the LLM judge: not yet (see docstring)
    # 5. Unsorted, with the best guess we have
    guess = tree.resolve(conn, suggested) if suggested else None
    if guess is None and len(named) > 1:
        guess = named[0]
    return PlaceResult(tree.UNSORTED, "unsorted", 0.0, guess=guess)


def link(tx: Tx, item_type: str, item_id: int, placed: PlaceResult, role: str = "primary") -> int:
    return tx.insert("branch_links", {"item_type": item_type, "item_id": item_id, "branch_id": placed.branch,
                                      "role": role, "assigned_by": placed.assigned_by,
                                      "confidence": placed.confidence, "guess": placed.guess, "ts": tx.now})


def item_text(conn: sqlite3.Connection, item_type: str, item_id: int) -> tuple[str, tuple[int | None, ...]]:
    if item_type == "fact":
        r = conn.execute("SELECT text, fact_keys, subject_id, object_id FROM facts WHERE id=?", (item_id,)).fetchone()
        return (f"{r['text']} {r['fact_keys'] or ''}", (r["subject_id"], r["object_id"])) if r else ("", ())
    if item_type == "entity":
        r = conn.execute("SELECT canonical_name, aliases FROM entities WHERE id=?", (item_id,)).fetchone()
        return (" ".join([r[0], *json.loads(r[1])]), (item_id,)) if r else ("", ())
    if item_type == "episode":
        r = conn.execute("SELECT content FROM episodes WHERE id=?", (item_id,)).fetchone()
        return (r[0], ()) if r else ("", ())
    if item_type == "open_loop":
        r = conn.execute("SELECT text FROM open_loops WHERE id=?", (item_id,)).fetchone()
        return (r[0], ()) if r else ("", ())
    return ("", ())


def place_op(ctx: Ctx, item_type: str, item_id: int, *, text: str | None = None, branch: str | None = None,
             suggested: str | None = None) -> tuple[PlaceResult, int | None]:
    """(Re)place an item. A link he set himself is never changed by inference."""
    conn = ctx.conn
    links = conn.execute("SELECT rowid, branch_id, assigned_by FROM branch_links WHERE item_type=? AND item_id=?"
                         " AND role='primary'", (item_type, item_id)).fetchall()
    mine = [r for r in links if r["assigned_by"] == "him"]
    if mine:
        return PlaceResult(mine[0]["branch_id"], "him", 1.0, changed=False), None
    body, entity_ids = item_text(conn, item_type, item_id)
    placed = decide_place(conn, text or body, branch=branch, suggested=suggested, entity_ids=entity_ids)
    if links and links[0]["branch_id"] == placed.branch:
        placed.changed = False
        return placed, None
    tx = ctx.tx("place")
    for r in links:
        tx.delete("branch_links", r["rowid"])
    link(tx, item_type, item_id, placed)
    return placed, tx.finish(f"placed {item_type} {item_id} on {placed.branch}")


def file_under_op(ctx: Ctx, item_type: str, item_id: int, branch: str) -> ChangeResult:
    """He moved it ("put that under Pen Reader"): pinned, never re-placed by inference."""
    slug = tree.resolve(ctx.conn, branch)
    if slug is None:
        raise KeyError(f"no branch called {branch!r}")
    tx = ctx.tx("move")
    for r in ctx.conn.execute("SELECT rowid FROM branch_links WHERE item_type=? AND item_id=? AND role='primary'",
                              (item_type, item_id)).fetchall():
        tx.delete("branch_links", r[0])
    link(tx, item_type, item_id, PlaceResult(slug, "him", 1.0))
    return ChangeResult(tx.finish(f"moved {item_type} {item_id} to {slug}"), {"branch": slug})


# ---------------------------------------------------------------- branches

_KIND_BY_LEVEL = {1: "area", 2: "branch", 3: "leaf", 4: "detail"}


def create_branch_op(ctx: Ctx, name: str, parent: str, *, aliases: tuple[str, ...] = (), tier: int | None = None,
                     created_by: str = "his", status: str = "active", glyph: str | None = None,
                     entity_id: int | None = None) -> ChangeResult:
    conn = ctx.conn
    pslug = tree.resolve(conn, parent)
    prow = tree.branch_row(conn, pslug) if pslug else None
    if prow is None:
        raise KeyError(f"no parent branch {parent!r}")
    level = prow["level"] + 1
    if level > 4:
        raise ValueError("the Life Tree is at most 4 levels below the root")
    base = tree.slugify(name)
    slug = base if not tree.branch_row(conn, base) else f"{pslug}.{base}"
    if tree.branch_row(conn, slug):
        raise ValueError(f"branch {slug!r} exists")
    tx = ctx.tx("create_branch")
    tx.insert("branches", {"id": slug, "parent_id": pslug, "path": f"{prow['path']}{base}/", "name": name,
                           "aliases": json.dumps(list(aliases)), "level": level, "kind": _KIND_BY_LEVEL[level],
                           "status": status, "privacy_tier": tier, "created_by": created_by,
                           "glyph": glyph or "".join(w[0] for w in name.split()[:3]).upper(),
                           "entity_id": entity_id})
    return ChangeResult(tx.finish(f"created branch {slug}"), {"branch": slug})


# ---------------------------------------------------------------- episodes and claims

def add_episode_op(ctx: Ctx, ep: EpisodeIn, claims: list[ClaimIn]) -> AddResult:
    conn = ctx.conn
    trust = trust_for(ep.channel, ep.speaker, ep.trust)
    h = text_hash(ep.content)
    tomb = tombstoned(conn, "content", h)
    lift_ok = trust is Trust.HIS and ep.explicit
    if tomb and not lift_ok:
        return AddResult(None, None, [ClaimOutcome("blocked", notes=("forgotten",)) for _ in claims], blocked=True)
    tx = ctx.tx("add_episode")
    if tomb:
        lift(tx, tomb)
    tier = ep.privacy_tier if ep.privacy_tier is not None else privacy_tier_for(ep.content)
    ep_id = tx.insert("episodes", {"ts": iso(ep.ts) or ctx.now, "channel": ep.channel, "speaker": ep.speaker,
                                   "trust": trust.value, "content": ep.content, "session_id": ep.session_id,
                                   "privacy_tier": tier, "hash": h, "retention": ep.retention})
    outcomes = [add_claim(ctx, tx, ep_id, trust, ep.channel, c, lift_ok=lift_ok, episode_tier=tier) for c in claims]
    summary = ", ".join(f"{o.action} fact {o.fact_id}" for o in outcomes if o.fact_id) or f"episode {ep_id}"
    return AddResult(ep_id, tx.finish(summary), outcomes)


def add_claim(ctx: Ctx, tx: Tx, ep_id: int, trust: Trust, channel: str, c: ClaimIn, *, lift_ok: bool,
              episode_tier: int) -> ClaimOutcome:
    conn = tx.conn
    kind, ctype = Kind(c.kind), ClaimType(c.claim_type)
    g = guard_claim(trust, channel, kind, ctype, explicit=c.explicit, pinned=c.pinned or kind is Kind.CORRECTION)
    # tombstones: the same text, or the same (subject, predicate) said another way
    blocks = [t for t in (tombstoned(conn, "content", text_hash(c.text)),
                          tombstoned(conn, "claim_key", key_hash(c.subject, c.predicate))
                          if c.subject and c.predicate else None) if t]
    if blocks:
        if not lift_ok:
            return ClaimOutcome("blocked", notes=("forgotten",))
        for t in blocks:
            lift(tx, t)
    for name in (c.subject, c.object):
        if name and tombstoned(conn, "entity", text_hash(name)):
            if not lift_ok:
                return ClaimOutcome("blocked", notes=("forgotten",))
            lift(tx, tombstoned(conn, "entity", text_hash(name)))
    subject_id = resolve_entity(tx, c.subject, c.subject_type)
    object_id = resolve_entity(tx, c.object, c.object_type)
    his_word = trust is Trust.HIS and c.explicit
    if his_word:
        source_key, label = "his", ("user-relayed" if ctype is ClaimType.WORLD else "you")
    elif trust is Trust.HIS:
        source_key, label = "jarvis", "guess"
    elif trust is Trust.JARVIS:
        source_key = "observer" if channel.startswith("observer:") else "jarvis"
        label = "observed" if source_key == "observer" else "jarvis"
    else:
        source_key = label = source_of(channel)
    placed = decide_place(conn, f"{c.text} {c.fact_keys or ''}", branch=c.branch, suggested=c.suggested_branch,
                          entity_ids=(subject_id, object_id))
    tier = max(episode_tier, c.privacy_tier or privacy_tier_for(c.text), tree.effective_tier(conn, placed.branch))
    row: dict[str, Any] = {
        "text": c.text, "subject_id": subject_id, "predicate": c.predicate, "object_id": object_id,
        "object_value": c.value, "kind": g.kind.value, "claim_type": ctype.value, "authority": g.authority,
        "origin_trust": trust.value, "source_key": source_key, "source_label": label,
        "confirm_state": g.confirm_state, "confidence": max(0.0, min(1.0, c.confidence)),
        "valid_from": iso(c.valid_from), "valid_to": iso(c.valid_to), "recorded_at": tx.now,
        "pinned": int(g.pinned), "scope": c.scope, "domain_tags": json.dumps(list(c.domain_tags)),
        "privacy_tier": tier, "importance": c.importance, "corrective_context": c.corrective_context,
        "fact_keys": c.fact_keys, "text_hash": text_hash(c.text),
    }
    if subject_id is not None and c.predicate:
        existing = conn.execute("SELECT * FROM facts WHERE subject_id=? AND predicate=? AND status='active'"
                                " AND scope IS ?", (subject_id, c.predicate, c.scope)).fetchall()
    else:
        existing = conn.execute("SELECT * FROM facts WHERE text_hash=? AND status='active'", (row["text_hash"],)).fetchall()
    existing_d = [dict(r) for r in existing]
    d = decide(Candidate(g.authority, source_key, value_key(row), his_word), existing_d)
    notes = g.notes

    if d.action == "reaffirm":
        target = tx.get("facts", d.target)
        if conn.execute("SELECT 1 FROM fact_sources WHERE fact_id=? AND episode_id=?", (d.target, ep_id)).fetchone():
            return ClaimOutcome("noop", d.target, notes=notes)
        tx.insert("fact_sources", {"fact_id": d.target, "episode_id": ep_id})
        upd: dict[str, Any] = {"confidence": round(target["confidence"] + (1 - target["confidence"]) * 0.3, 4),
                               "strength": target["strength"] + 1.0}
        if his_word and target["origin_trust"] != "his":   # he confirmed what another source said
            upd.update(origin_trust="his", authority=1, confirm_state="confirmed", source_key="his", source_label=label)
        tx.update("facts", d.target, upd)
        return ClaimOutcome("reaffirm", d.target, branch=_primary(conn, "fact", d.target), notes=notes)

    if d.action == "conflict" and not d.new_wins and not his_word:
        row.update(kind=Kind.OBSERVATION.value, conflicts_with=d.target, pinned=0)
        if g.confirm_state not in ("observed", "proposed"):
            row["confirm_state"] = "observed"
    fid = tx.insert("facts", row)
    tx.insert("fact_sources", {"fact_id": fid, "episode_id": ep_id})
    link(tx, "fact", fid, placed)
    if g.kind is Kind.PROCEDURE and trust is Trust.HIS:
        tx.insert("procedures", {"fact_id": fid, "rule_text": c.text, "scope": c.scope, "pinned": 1})
    other = d.target
    if d.action == "supersede":
        old = tx.get("facts", d.target)
        upd = {"valid_to": row["valid_from"] or tx.now, "retired_at": tx.now, "status": "superseded",
               "superseded_by": fid}
        if old["origin_trust"] == "his" and old["authority"] == 1:
            upd["authority"] = 2   # his earlier word
        tx.update("facts", d.target, upd)
        if g.kind is Kind.CORRECTION:
            tx.insert("corrections", {"wrong_fact_id": d.target, "new_fact_id": fid, "ts": tx.now})
    elif d.action == "conflict" and d.new_wins:
        tx.update("facts", d.target, {"conflicts_with": fid, "flagged_at": None})
    return ClaimOutcome(d.action, fid, other, placed.branch, notes)


def _primary(conn: sqlite3.Connection, item_type: str, item_id: int) -> str | None:
    row = conn.execute("SELECT branch_id FROM branch_links WHERE item_type=? AND item_id=? AND role='primary'",
                       (item_type, item_id)).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- invalidate, pin, open loops, flags

def invalidate_op(ctx: Ctx, fact_id: int, *, valid_to: Any = None, retract: bool = False) -> ChangeResult:
    """Stop believing a fact. retract=True: it was never true (wrong). Otherwise it ended at `valid_to`."""
    tx = ctx.tx("retract" if retract else "invalidate")
    row = tx.get("facts", fact_id)
    if row is None:
        raise KeyError(f"fact {fact_id} not found")
    upd: dict[str, Any] = {"retired_at": ctx.now}
    if retract:
        upd["status"] = "retracted"
    else:
        upd.update(status="superseded", valid_to=iso(valid_to) or ctx.now)
    tx.update("facts", fact_id, upd)
    return ChangeResult(tx.finish(f"{'retracted' if retract else 'ended'} fact {fact_id}"), {"fact": fact_id})


def pin_op(ctx: Ctx, fact_id: int, pinned: bool = True) -> ChangeResult:
    tx = ctx.tx("pin" if pinned else "unpin")
    tx.update("facts", fact_id, {"pinned": int(pinned)})   # the CHECK refuses pins on anything not his word
    return ChangeResult(tx.finish(f"{'pinned' if pinned else 'unpinned'} fact {fact_id}"), {"fact": fact_id})


def add_open_loop_op(ctx: Ctx, text: str, *, due: Any = None, slot: str | None = None, branch: str | None = None,
                     origin_episode: int | None = None) -> ChangeResult:
    tx = ctx.tx("add_open_loop")
    lid = tx.insert("open_loops", {"text": text, "origin_episode": origin_episode, "due": iso(due),
                                   "planned_slot": slot, "created_at": ctx.now})
    link(tx, "open_loop", lid, decide_place(ctx.conn, text, branch=branch))
    return ChangeResult(tx.finish(f"open loop {lid}"), {"open_loop": lid})


def mark_flagged_op(ctx: Ctx, fact_id: int) -> ChangeResult:
    """A conflict was said once; don't say it again (C15)."""
    tx = ctx.tx("flagged")
    tx.update("facts", fact_id, {"flagged_at": ctx.now})
    return ChangeResult(tx.finish(f"flagged fact {fact_id}"), {"fact": fact_id})
