"""How memory is shown: source tags for the model (MEMORY §5) and the hub's contract shapes (contracts/)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .util import parse

OFFICIAL_LABELS = {"canvas": "Canvas", "paws": "PAWS", "syllabus": "Syllabus", "crowdmark": "Crowdmark"}
_CONTRACT_KIND = {"canvas": "canvas", "syllabus": "syllabus", "calendar": "calendar", "paws": "paws", "crowdmark": "crowdmark",
                  "gmail": "gmail", "file": "file", "web": "web"}


def local(ts: str | None) -> datetime | None:
    dt = parse(ts)
    return None if dt is None else dt.astimezone()


def short_date(ts: str | None) -> str:
    dt = local(ts)
    return "" if dt is None else f"{dt.strftime('%b')} {dt.day}"


def local_iso(ts: str | None) -> str | None:
    dt = local(ts)
    return None if dt is None else dt.isoformat(timespec="seconds")


def tag(row: dict[str, Any] | sqlite3.Row) -> str:
    """The source tag on every line given to the model: [you, Nov 3], [Canvas], [gmail, untrusted]..."""
    key, label = row["source_key"], row["source_label"]
    when = short_date(row["valid_from"] or row["recorded_at"]) if "valid_from" in row.keys() else ""
    if key == "his":
        return f"[you, {when}]" if when else "[you]"
    if key in OFFICIAL_LABELS:
        return f"[{OFFICIAL_LABELS[key]}]"
    if key == "observer":
        return "[observed]"
    if key == "jarvis" or label == "guess" or row["authority"] == 5 and row["origin_trust"] != "outside":
        return "[guess, unconfirmed]"
    return f"[{label}, untrusted]"


def contract_source(row: dict[str, Any] | sqlite3.Row) -> dict[str, str]:
    key = row["source_key"]
    if key == "his":
        return {"kind": "you", "label": f"You · {short_date(row['recorded_at'])}"}
    if key in ("jarvis", "observer"):
        return {"kind": "guess" if row["confirm_state"] == "proposed" else "jarvis",
                "label": "Observed" if key == "observer" else "Jarvis's guess"}
    kind = _CONTRACT_KIND.get(key, "web")
    return {"kind": kind, "label": OFFICIAL_LABELS.get(key, key.capitalize())}


def confidence_word(row: dict[str, Any] | sqlite3.Row) -> str:
    if row["confirm_state"] == "proposed" or row["confidence"] < 0.6:
        return "guess"
    return "sure" if row["confidence"] >= 0.85 else "likely"


def fact_id(n: int) -> str:
    return f"f-{n}"


def contract_fact(conn: sqlite3.Connection, n: int) -> dict[str, Any] | None:
    """One fact as the hub's fact.schema.json."""
    r = conn.execute("SELECT * FROM facts WHERE id=?", (n,)).fetchone()
    if r is None:
        return None
    link = conn.execute("SELECT branch_id, guess FROM branch_links WHERE item_type='fact' AND item_id=? AND role='primary'",
                        (n,)).fetchone()
    out: dict[str, Any] = {
        "id": fact_id(n), "branch_id": link["branch_id"] if link else "unsorted", "statement": r["text"],
        "source": contract_source(r), "confidence": confidence_word(r), "learned": local_iso(r["recorded_at"]),
        "pinned": bool(r["pinned"]), "tier": 2 if r["privacy_tier"] == 2 else 1,
    }
    if link and link["branch_id"] == "unsorted" and link["guess"]:
        out["guess_branch_id"] = link["guess"]
    history, cur = [], n
    for _ in range(20):
        old = conn.execute("SELECT text, valid_to FROM facts WHERE superseded_by=?", (cur,)).fetchone()
        if old is None:
            break
        history.append({"was": old["text"], "when": f"until {short_date(old['valid_to'])}"})
        cur = conn.execute("SELECT id FROM facts WHERE superseded_by=?", (cur,)).fetchone()[0]
    if history:
        out["history"] = history
    loser = conn.execute("SELECT * FROM facts WHERE conflicts_with=? AND status='active'", (n,)).fetchone()
    if loser is not None:
        out["conflict"] = {"other_source": contract_source(loser), "other_value": loser["object_value"] or loser["text"],
                           "kept": "mine" if r["origin_trust"] == "his" else "theirs"}
    return out


def hub_tree(conn: sqlite3.Connection, max_facts: int = 300) -> dict[str, Any]:
    """Everything the hub's Life tree and Memory page show, straight from the store: branches (branch.schema.json),
    the stored branch cards, and the active facts (fact.schema.json). Tier-2 branches are listed but their cards and
    facts stay out (they open only when he unlocks them). Read-only. Tier: T2 (a few ms at his scale)."""
    counts = {r[0]: r[1] for r in conn.execute(
        "SELECT l.branch_id, count(*) FROM branch_links l JOIN facts f ON f.id = l.item_id"
        " WHERE l.item_type='fact' AND l.role='primary' AND f.status='active' GROUP BY l.branch_id")}
    branches, locked = [], set()
    for r in conn.execute("SELECT * FROM branches WHERE status != 'archived' AND kind != 'detail' ORDER BY level, sort_hint, name"):
        tier = 2 if r["privacy_tier"] == 2 or r["parent_id"] in locked else 1
        if tier == 2:
            locked.add(r["id"])
        name = r["name"] or r["id"]
        branches.append({"id": r["id"], "parent": r["parent_id"], "name": name,
                         "glyph": r["glyph"] or "".join(w[0] for w in name.split()[:2]).upper() or "?",
                         "kind": r["kind"], "status": r["status"], "tier": tier, "counts": {"facts": counts.get(r["id"], 0)}})
    cards = {}
    for r in conn.execute("SELECT branch_id, card_json FROM branch_cards WHERE dirty=0"):
        if r[0] not in locked and r[1]:
            try:
                cards[r[0]] = json.loads(r[1])
            except ValueError:
                continue
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM facts WHERE status='active' AND privacy_tier < 2 ORDER BY pinned DESC, id DESC LIMIT ?", (max_facts,))]
    facts = [f for n in ids if (f := contract_fact(conn, n)) is not None and f["branch_id"] not in locked]
    stamp = conn.execute("SELECT coalesce(max(id), 0) FROM changes").fetchone()[0]
    return {"branches": branches, "cards": cards, "facts": facts, "stamp": stamp}


def standing_lines(conn: sqlite3.Connection, limit: int = 8) -> list[str]:
    """How he wants things done, for every prompt: his preferences, standing rules and corrections, pinned first,
    then the most important and newest. Tier-2 stays out. Read-only; a millisecond."""
    rows = conn.execute(
        "SELECT text, scope FROM facts WHERE status='active' AND privacy_tier < 2"
        " AND kind IN ('preference','procedure','correction') ORDER BY pinned DESC, importance DESC, id DESC LIMIT ?", (limit,))
    return [r["text"] + (f" ({r['scope']})" if r["scope"] else "") for r in rows]
