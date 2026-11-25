"""Templated cards (MEMORY §7.1, §7.5; LIFE_TREE §7): built by code in T2 (< 100 ms), stored, read in T0.

Never written by a language model, so every line traces to a fact, a loop or a change.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import timedelta
from typing import Any

from . import tree
from .model import NowContext
from .util import parse
from .views import contract_source, fact_id, local, local_iso, short_date, tag

DUE_DAYS = 14


def _facts_on(conn: sqlite3.Connection, lo_hi: tuple[str, str] | None, slug: str, *, subtree: bool) -> list[sqlite3.Row]:
    if subtree and lo_hi:
        sql = ("SELECT DISTINCT f.* FROM facts f JOIN branch_links l ON l.item_type='fact' AND l.item_id=f.id"
               " JOIN branches b ON b.id=l.branch_id WHERE f.status='active' AND b.path >= ? AND b.path < ?")
        return conn.execute(sql, lo_hi).fetchall()
    return conn.execute("SELECT DISTINCT f.* FROM facts f JOIN branch_links l ON l.item_type='fact' AND l.item_id=f.id"
                        " WHERE f.status='active' AND l.branch_id=?", (slug,)).fetchall()


def _loops_on(conn: sqlite3.Connection, lo_hi: tuple[str, str] | None) -> list[sqlite3.Row]:
    sql = ("SELECT DISTINCT o.*, l.branch_id FROM open_loops o JOIN branch_links l ON l.item_type='open_loop'"
           " AND l.item_id=o.id JOIN branches b ON b.id=l.branch_id WHERE o.status='open'")
    if lo_hi:
        return conn.execute(sql + " AND b.path >= ? AND b.path < ?", lo_hi).fetchall()
    return conn.execute(sql).fetchall()


def build_branch_card(conn: sqlite3.Connection, slug: str, now: str) -> tuple[dict[str, Any], str]:
    """Build one branch card as contracts/branch_card.schema.json plus its spoken/LLM text. Tier: T2."""
    b = tree.branch_row(conn, slug)
    if b is None:
        raise KeyError(slug)
    bounds = tree.subtree_bounds(b["path"])
    now_dt = parse(now)
    tier2 = tree.tier2_prefixes(conn)
    in_tier2 = any(b["path"].startswith(p) for p in tier2)

    def hidden(path: str) -> bool:   # tier-2 children never show in a parent's roll-up
        return not in_tier2 and any(path.startswith(p) for p in tier2)

    facts = [f for f in _facts_on(conn, bounds, slug, subtree=False) if not f["conflicts_with"]]
    key = sorted(facts, key=lambda f: (-f["pinned"], -(f["importance"] * f["strength"]), f["id"]))[:6]
    decisions = [f for f in facts if f["kind"] == "decision" and f["origin_trust"] == "his"][:3]
    loops = [lp for lp in _loops_on(conn, bounds)
             if not hidden(conn.execute("SELECT path FROM branches WHERE id=?", (lp["branch_id"],)).fetchone()[0])]
    horizon = now_dt + timedelta(days=DUE_DAYS)
    due = sorted((lp for lp in loops if lp["due"] and parse(lp["due"]) <= horizon), key=lambda lp: lp["due"])
    people = conn.execute(
        "SELECT DISTINCT e.canonical_name, e.summary FROM entities e JOIN branch_links l ON l.item_type='entity'"
        " AND l.item_id=e.id WHERE l.branch_id=? AND e.type='person' LIMIT 5", (slug,)).fetchall()
    files = conn.execute(
        "SELECT DISTINCT e.id, e.canonical_name FROM entities e JOIN branch_links l ON l.item_type='entity'"
        " AND l.item_id=e.id WHERE l.branch_id=? AND e.type='file' LIMIT 3", (slug,)).fetchall()
    recent = [r[0] for r in conn.execute(
        "SELECT c.id FROM change_branches cb JOIN changes c ON c.id=cb.change_id WHERE cb.branch_id=?"
        " AND c.undone_by IS NULL AND c.op != 'undo' ORDER BY c.id DESC LIMIT 5", (slug,))]
    children = [c for c in conn.execute("SELECT id, name, path FROM branches WHERE parent_id=? AND status='active'",
                                        (slug,)) if not hidden(c["path"])]

    status = f"{b['name']} · {len(facts)} facts" + (f" · {len(due)} due in {DUE_DAYS} days" if due else "")
    card: dict[str, Any] = {"branch_id": slug, "status": status}
    if children:
        week = [lp for lp in due if parse(lp["due"]) <= now_dt + timedelta(days=7)]
        rollup = f"{len(children)} branches · {len(week)} due this week"
        if due:
            rollup += f" · closest: {due[0]['text']}"
        card["rollup"] = rollup
    if due:
        card["due"] = [{"id": f"loop-{lp['id']}", "title": lp["text"], "due": local_iso(lp["due"]),
                        "branch_id": lp["branch_id"]} for lp in due]
    if loops:
        card["open_loops"] = [{"text": lp["text"], **({"slot": lp["planned_slot"]} if lp["planned_slot"] else {})}
                              for lp in loops[:5]]
    if key:
        card["key_facts"] = [fact_id(f["id"]) for f in key]
    if decisions:
        card["decisions"] = [{"text": f"{d['text']} (your call)", "date": short_date(d["recorded_at"])}
                             for d in decisions]
    if people:
        card["people"] = [{"name": p[0], "role": p[1] or "person"} for p in people]
    if files:
        card["files"] = [{"id": f"file-{f[0]}", "name": f[1], "kind": _file_kind(f[1])} for f in files]
    if recent:
        # action ids (contracts/branch_card): a memory change's Activity receipt carries the same chg-<n> id
        card["recent"] = [f"chg-{c}" for c in recent]
    gaps = []
    if not facts and not loops:
        gaps.append(f"Nothing known about {b['name']} yet")
    guesses = sum(1 for f in facts if f["confirm_state"] == "proposed")
    if guesses:
        gaps.append(f"{guesses} guess{'es' if guesses > 1 else ''} not confirmed yet")
    if gaps:
        card["gaps"] = gaps
    story = conn.execute("SELECT story FROM branch_cards WHERE branch_id=?", (slug,)).fetchone()
    card["story"] = json.loads(story[0]) if story and story[0] else None

    lines = [f"Branch: {b['name']} ({b['path'] or 'root'})", f"Status: {status}"]
    if "rollup" in card:
        lines.append(f"Roll-up: {card['rollup']}")
    lines += [f"Due: {lp['text']} · {local(lp['due']):%a %b %d %H:%M}" for lp in due[:3]]
    lines += [f"Open: {lp['text']}" + (f" · planned {lp['planned_slot']}" if lp["planned_slot"] else "")
              for lp in loops[:3]]
    lines += [f"Fact: {f['text']} {tag(f)}" for f in key]
    lines += [f"Decision: {d['text']} [you, {short_date(d['recorded_at'])}]" for d in decisions]
    lines += [f"Gap: {g}" for g in gaps]
    return card, "\n".join(lines)


def _file_kind(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {"pdf": "pdf", "pptx": "slides", "ppt": "slides", "docx": "doc", "doc": "doc", "md": "doc",
            "xlsx": "sheet", "csv": "sheet", "py": "code", "js": "code", "png": "image", "jpg": "image"}.get(ext, "folder")


def store_branch_card(conn: sqlite3.Connection, slug: str, now: str) -> bool:
    """Rebuild and store one card if its inputs changed. Returns True when the stored card changed."""
    card, text = build_branch_card(conn, slug, now)
    h = hashlib.sha256((json.dumps(card, sort_keys=True) + text).encode()).hexdigest()
    old = conn.execute("SELECT inputs_hash FROM branch_cards WHERE branch_id=?", (slug,)).fetchone()
    if old and old[0] == h:
        conn.execute("UPDATE branch_cards SET dirty=0 WHERE branch_id=?", (slug,))
        return False
    conn.execute("INSERT INTO branch_cards(branch_id, card_json, card_text, built_at, inputs_hash, dirty)"
                 " VALUES (?,?,?,?,?,0) ON CONFLICT(branch_id) DO UPDATE SET card_json=excluded.card_json,"
                 " card_text=excluded.card_text, built_at=excluded.built_at, inputs_hash=excluded.inputs_hash, dirty=0",
                 (slug, json.dumps(card), text, now, h))
    due = card.get("due", [])
    conn.execute("UPDATE branches SET open_loop_count=?, next_due_at=? WHERE id=?",
                 (len(card.get("open_loops", [])), due[0]["due"] if due else None, slug))
    return True


def rebuild_with_ancestors(conn: sqlite3.Connection, slugs: set[str], now: str) -> set[str]:
    """A change rebuilds its branches and their ancestors (parents hold roll-ups)."""
    todo: set[str] = set()
    for s in slugs:
        if tree.branch_row(conn, s):
            todo.update(tree.ancestors(conn, s))
    return {s for s in sorted(todo) if store_branch_card(conn, s, now)}


# ---------------------------------------------------------------- the now card

def build_now_card(conn: sqlite3.Connection, now: str, ctx: NowContext | None = None) -> tuple[dict[str, Any], str]:
    """The now card as contracts/now_card.schema.json, plus the ~600-900 token text for the prompt. Tier: T2."""
    ctx = ctx or NowContext()
    dt = local(now)
    part = "morning" if dt.hour < 12 else "afternoon" if dt.hour < 18 else "evening"
    root = conn.execute("SELECT name FROM branches WHERE id='root'").fetchone()
    card: dict[str, Any] = {"greeting": f"Good {part}, {root[0] if root else 'there'}.", "updated": local_iso(now)}
    card["next_up"] = ctx.events[0] if ctx.events else None
    flag = conn.execute(
        "SELECT l.*, w.text AS w_text, w.source_key AS w_key, w.source_label AS w_label, w.recorded_at AS w_rec,"
        " w.valid_from AS w_from, w.authority AS w_auth, w.origin_trust AS w_trust, w.confirm_state AS w_state"
        " FROM facts l JOIN facts w ON w.id = l.conflicts_with WHERE l.status='active' AND w.status='active'"
        " AND l.flagged_at IS NULL AND l.importance >= 0.5 AND l.privacy_tier < 2 AND w.privacy_tier < 2"
        " ORDER BY l.importance DESC, l.id DESC LIMIT 1").fetchone()
    if flag is not None:
        winner_tag = tag({"source_key": flag["w_key"], "source_label": flag["w_label"], "valid_from": flag["w_from"],
                          "recorded_at": flag["w_rec"], "authority": flag["w_auth"], "origin_trust": flag["w_trust"]})
        link = conn.execute("SELECT branch_id FROM branch_links WHERE item_type='fact' AND item_id=? AND role='primary'",
                            (flag["conflicts_with"],)).fetchone()
        card["flag"] = {"text": f"{tag(flag)} says: {flag['text']}. Kept: {flag['w_text']} {winner_tag}.",
                        "why": "two sources disagree", "source": contract_source(flag),
                        **({"branch_id": link[0]} if link else {})}
    else:
        card["flag"] = ctx.flag
    if ctx.ready_to_offer:
        card["ready_to_offer"] = ctx.ready_to_offer[:3]
    unsorted = conn.execute("SELECT count(*) FROM branch_links WHERE branch_id='unsorted'").fetchone()[0]
    gaps = list(ctx.gaps) + ([f"{unsorted} item{'s' if unsorted != 1 else ''} waiting in Unsorted"] if unsorted else [])
    if gaps:
        card["gaps"] = gaps[:3]
    if ctx.done_today:
        card["done_today"] = ctx.done_today
    if ctx.day:
        card["day"] = ctx.day
    if ctx.moment:
        card["moment"] = ctx.moment

    due72 = [lp for lp in _loops_on(conn, None)
             if lp["due"] and parse(lp["due"]) <= parse(now) + timedelta(hours=72)
             and tree.effective_tier(conn, lp["branch_id"]) < 2]
    due72.sort(key=lambda lp: lp["due"])
    lines = [card["greeting"], f"Now: {dt:%a %b %d %H:%M}" + (f" · Context: {ctx.active_branch}" if ctx.active_branch else "")]
    lines += [f"Next: {e.get('title')} · {e.get('when')}" + (f" · {e['where']}" if e.get("where") else "")
              for e in ctx.events[:3]]
    lines += [f"Today: {line}" for line in ctx.today[:12]]
    lines += [f"Due: {lp['text']} · {local(lp['due']):%a %H:%M}" for lp in due72[:5]]
    lines += [f"Due: {line}" for line in ctx.due[:6]]
    lines += [f"Note: {line}" for line in ctx.notes[:2]]
    lines += list(ctx.names[:2])
    lines += [f"Remember: {line}" for line in ctx.prefs[:8]]
    lines += [f"Ready: {r['text']}" for r in ctx.ready_to_offer[:3]]
    if card["flag"]:
        lines.append(f"Flag: {card['flag']['text']}")
    lines += [f"Gap: {g}" for g in gaps[:3]]
    lines += [f"Waiting for your yes: {w}" for w in ctx.waiting_for_yes[:3]]
    return card, "\n".join(lines)


def store_now_card(conn: sqlite3.Connection, now: str, ctx: NowContext | None = None) -> dict[str, Any]:
    card, text = build_now_card(conn, now, ctx)
    body = dict(card)
    body.pop("updated", None)
    h = hashlib.sha256((json.dumps(body, sort_keys=True) + text.split("\n", 2)[-1]).encode()).hexdigest()
    conn.execute("INSERT INTO now_card(id, card_json, card_text, built_at, inputs_hash) VALUES (1,?,?,?,?)"
                 " ON CONFLICT(id) DO UPDATE SET card_json=excluded.card_json, card_text=excluded.card_text,"
                 " built_at=excluded.built_at, inputs_hash=excluded.inputs_hash", (json.dumps(card), text, now, h))
    return card
