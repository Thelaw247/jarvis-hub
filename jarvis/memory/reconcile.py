"""Reconcile a new claim against what's already believed (MEMORY §4 step 5, §5). Pure code: the authority
order is applied here, never left to the language model.

- ADD: nothing on this (subject, predicate, scope) yet.
- REAFFIRM: the same value again; the episode joins the provenance set.
- SUPERSEDE: the same voice updated itself (his word replacing his word, Canvas replacing Canvas), or a
  Jarvis guess (authority 5) was replaced by something at least as good. The old fact gets valid_to /
  retired_at and superseded_by; history is kept.
- CONFLICT: two different voices disagree. Both stay; the winner is the better authority (then the newer),
  the other is linked with conflicts_with and flagged once. A pinned fact never loses to anything but him.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Candidate:
    authority: int
    source_key: str
    value_key: str
    his: bool


@dataclass(frozen=True)
class Decision:
    action: str               # add · reaffirm · supersede · conflict
    target: int | None = None
    new_wins: bool = True


def value_key(row: dict[str, Any]) -> str:
    if row.get("object_id") is not None:
        return f"e:{row['object_id']}"
    if row.get("object_value") is not None:
        return "v:" + " ".join(str(row["object_value"]).lower().split())
    return "t:" + row["text_hash"]


def winner(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Best authority first, then the newest in world time, then in system time."""
    newest_first = sorted(rows, key=lambda r: (r.get("valid_from") or "", r["recorded_at"]), reverse=True)
    return min(newest_first, key=lambda r: r["authority"])  # min keeps the first (newest) of the best


def decide(new: Candidate, existing: list[dict[str, Any]]) -> Decision:
    """Tier: T2. `existing` = active facts with the same subject + predicate + scope."""
    if not existing:
        return Decision("add")
    same_value = [r for r in existing if value_key(r) == new.value_key]
    if same_value:
        mine = [r for r in same_value if r["source_key"] == new.source_key]
        return Decision("reaffirm", (mine or same_value)[0]["id"])
    same_voice = [r for r in existing if r["source_key"] == new.source_key]
    if same_voice:
        target = winner(same_voice)
        if target["pinned"] and not new.his:
            return Decision("conflict", target["id"], new_wins=False)
        return Decision("supersede", target["id"])
    best = winner(existing)
    protected = bool(best["pinned"]) and not new.his
    if best["authority"] == 5 and not protected and new.authority <= 5:
        return Decision("supersede", best["id"])
    if new.authority < best["authority"] and not protected:
        return Decision("conflict", best["id"], new_wins=True)
    return Decision("conflict", best["id"], new_wins=False)
