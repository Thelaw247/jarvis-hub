"""The memory interface (MEMORY §1): small on purpose, so Graphiti or Mem0 could be swapped in later (C33)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from .model import (
    AddResult,
    ChangeResult,
    ClaimIn,
    EpisodeIn,
    ForgetResult,
    Hit,
    NowContext,
    PlaceResult,
    UndoResult,
    When,
)


@runtime_checkable
class Memory(Protocol):
    async def add_episode(self, episode: EpisodeIn, claims: Sequence[ClaimIn] = ()) -> AddResult:
        """Store one raw round and the claims extracted from it. T2 (writer queue)."""
        ...

    async def search(self, query: str, *, branch: str | None = None, k: int = 10, at: When = None,
                     as_of: When = None, widen: bool = True, space: str = "index",
                     include_tier2: bool = False, partial: bool = False) -> list[Hit]:
        """Recall tagged, collapsed facts. T1; hot path with space='fast', partial=True (≤ 50 ms p95)."""
        ...

    async def invalidate(self, fact_id: int, *, valid_to: When = None, retract: bool = False,
                         session_id: str | None = None) -> ChangeResult:
        """Stop believing a fact (ended at valid_to, or retracted as never true). T2."""
        ...

    async def forget(self, *, episode_ids: Sequence[int] = (), fact_ids: Sequence[int] = (),
                     entity_ids: Sequence[int] = (), preview: bool = False,
                     session_id: str | None = None) -> ForgetResult:
        """Forget for real: rows, indexes, audit content, cards; tombstone; WAL truncated. T2."""
        ...

    async def undo(self, change_id: int | None = None, *, session_id: str | None = None) -> UndoResult:
        """Undo exactly one change (default: the latest), or every change of one session. T2."""
        ...

    async def now_card(self) -> dict[str, Any]:
        """The stored now card (contracts/now_card.schema.json). T0: one row read."""
        ...

    async def rebuild_now_card(self, context: NowContext | None = None) -> dict[str, Any]:
        """Rebuild the now card from memory + context. T2 (< 100 ms)."""
        ...

    async def branch_card(self, branch: str) -> dict[str, Any] | None:
        """A branch's stored card (contracts/branch_card.schema.json). T0: one row read (< 5 ms)."""
        ...

    async def place(self, item_type: str, item_id: int, *, text: str | None = None, branch: str | None = None,
                    suggested: str | None = None) -> PlaceResult:
        """File an item on the Life Tree (rules step; centroid and LLM steps come in M1.2). T2."""
        ...
