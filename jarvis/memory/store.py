"""MemoryStore: the SQLite implementation of the Memory interface.

One writer task: every change goes through an asyncio queue and runs, one at a time, on a single writer
thread with its own connection, in a short BEGIN IMMEDIATE transaction. Reads are concurrent: a small pool of
read-only connections (WAL lets them read while the writer writes). Logs carry ids and timings only (C21).
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import sqlite3
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import cards, recall, writes
from .db import connect, open_writer
from .embeddings import Embedder, FakeEmbedder
from .forget import forget_op
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
from .tx import Indexer
from .undo import UndoError, undo_change, undo_session
from .util import iso
from .views import contract_fact

log = logging.getLogger("jarvis.memory")


def default_embedders() -> dict[str, Embedder]:
    """Fakes, sized like the real models (REAL_MODELS). Laptop B swaps in the real ones."""
    return {"fast": FakeEmbedder(256, "fake-fast-256"), "index": FakeEmbedder(384, "fake-index-384")}


class MemoryStore:
    def __init__(self, path: str | Path, embedders: dict[str, Embedder] | None = None, *, readers: int = 4,
                 clock: Callable[[], datetime] | None = None, card_debounce: float = 2.0) -> None:
        self.path = Path(path)
        self.embedders = embedders if embedders is not None else default_embedders()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._indexer = Indexer(self.embedders)
        self._n_readers = readers
        self._debounce = card_debounce
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._wexec = ThreadPoolExecutor(1, thread_name_prefix="memory-writer")
        self._rexec = ThreadPoolExecutor(readers, thread_name_prefix="memory-reader")
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue()
        self._wconn: sqlite3.Connection | None = None
        self._task: asyncio.Task[None] | None = None
        self._dirty: set[str] = set()
        self._timer: asyncio.TimerHandle | None = None
        self._now_ctx: NowContext | None = None

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> MemoryStore:
        loop = asyncio.get_running_loop()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wconn = await loop.run_in_executor(self._wexec, open_writer, self.path, self.embedders)
        for _ in range(self._n_readers):
            self._pool.put(await loop.run_in_executor(self._rexec, lambda: connect(self.path, readonly=True)))
        self._task = asyncio.create_task(self._writer_loop(), name="memory-writer")
        return self

    async def close(self) -> None:
        if self._timer:
            self._timer.cancel()
        if self._task:
            await self._queue.put(None)
            await self._task
        loop = asyncio.get_running_loop()
        while not self._pool.empty():
            self._pool.get().close()
        if self._wconn is not None:
            await loop.run_in_executor(self._wexec, self._wconn.close)
        self._wexec.shutdown()
        self._rexec.shutdown()

    async def __aenter__(self) -> MemoryStore:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def now(self) -> str:
        return iso(self._clock())

    # ------------------------------------------------------------ the one writer
    async def _writer_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            job = await self._queue.get()
            if job is None:
                return
            fn, args, kw, sid, fut = job
            try:
                result, touched = await loop.run_in_executor(self._wexec, self._run_write, fn, args, kw, sid)
            except BaseException as exc:  # noqa: BLE001 - handed to the caller
                if not fut.cancelled():
                    fut.set_exception(exc)
                continue
            if touched:
                self._dirty |= touched
                self._schedule_cards()
            if not fut.cancelled():
                fut.set_result(result)

    def _run_write(self, fn: Callable[..., Any], args: tuple, kw: dict, sid: str | None) -> tuple[Any, set[str]]:
        conn = self._wconn
        assert conn is not None
        t0 = time.perf_counter()
        ctx = writes.Ctx(conn, self._indexer, self.now(), sid)
        last = conn.execute("SELECT coalesce(max(id), 0) FROM changes").fetchone()[0]
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = fn(ctx, *args, **kw)
            touched = {r[0] for r in conn.execute("SELECT branch_id FROM change_branches WHERE change_id > ?", (last,))}
            if touched and self._debounce <= 0:
                cards.rebuild_with_ancestors(conn, touched, ctx.now)
                cards.store_now_card(conn, ctx.now, self._now_ctx)
                touched = set()
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        if fn is forget_op and isinstance(result, ForgetResult) and result.change_id is not None:
            result.scrubbed = self._checkpoint_truncate()
        log.info("memory write op=%s ms=%.1f", getattr(fn, "__name__", "op"), (time.perf_counter() - t0) * 1000)
        return result, touched

    def _checkpoint_truncate(self) -> bool:
        """Copy the WAL into the main file and cut the WAL to zero bytes (forget step 4)."""
        assert self._wconn is not None
        for _ in range(40):
            busy, _log, _done = self._wconn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if busy == 0:
                return True
            time.sleep(0.025)
        return False

    async def _write(self, fn: Callable[..., Any], *args: Any, session_id: str | None = None, **kw: Any) -> Any:
        if self._task is None:
            raise RuntimeError("MemoryStore not started")
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await self._queue.put((fn, args, kw, session_id, fut))
        return await fut

    # ------------------------------------------------------------ card rebuilds (debounced, MEMORY §7.1)
    def _schedule_cards(self) -> None:
        if self._timer is None:
            loop = asyncio.get_running_loop()
            self._timer = loop.call_later(self._debounce, lambda: asyncio.ensure_future(self.flush_cards()))

    async def flush_cards(self) -> set[str]:
        """Rebuild every card marked dirty now (normally 2-5 s after the last change)."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        dirty, self._dirty = self._dirty, set()
        ctx_now = self._now_ctx

        def op(ctx: writes.Ctx) -> set[str]:
            changed = cards.rebuild_with_ancestors(ctx.conn, dirty, ctx.now)
            cards.store_now_card(ctx.conn, ctx.now, ctx_now)
            return changed

        return await self._write(op)

    # ------------------------------------------------------------ concurrent reads
    def _run_read(self, fn: Callable[..., Any], args: tuple, kw: dict) -> Any:
        conn = self._pool.get()
        try:
            return fn(conn, *args, **kw)
        finally:
            self._pool.put(conn)

    async def _read(self, fn: Callable[..., Any], *args: Any, **kw: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(self._rexec, self._run_read, fn, args, kw)

    # ------------------------------------------------------------ the Memory interface
    async def add_episode(self, episode: EpisodeIn, claims: Sequence[ClaimIn] = ()) -> AddResult:
        return await self._write(writes.add_episode_op, episode, list(claims), session_id=episode.session_id)

    def search_sync(self, query: str, **kw: Any) -> list[Hit]:
        """Same as search, on the calling thread (the voice loop's T0/T1 code and the benchmark)."""
        return self._run_read(self._search, (query,), kw)

    def _search(self, conn: sqlite3.Connection, query: str, *, at: When = None, as_of: When = None,
                **kw: Any) -> list[Hit]:
        return recall.search(conn, self.embedders, query, now=self.now(), at=iso(at), as_of=iso(as_of), **kw)

    async def search(self, query: str, *, branch: str | None = None, k: int = 10, at: When = None,
                     as_of: When = None, widen: bool = True, space: str = "index", include_tier2: bool = False,
                     partial: bool = False) -> list[Hit]:
        return await self._read(self._search, query, branch=branch, k=k, at=at, as_of=as_of, widen=widen,
                                space=space, include_tier2=include_tier2, partial=partial)

    async def hot_recall(self, partial: str) -> dict[str, Any]:
        """Speculative recall on an STT partial (MEMORY §7.3): a branch card if it names a branch, else ≤ 5 facts.
        Tier: T0/T1, ≤ 50 ms p95."""
        def op(conn: sqlite3.Connection) -> dict[str, Any]:
            slug = recall.branch_for_partial(conn, partial)
            if slug:
                row = conn.execute("SELECT card_json FROM branch_cards WHERE branch_id=?", (slug,)).fetchone()
                if row:
                    return {"branch_card": json.loads(row[0])}
            return {"facts": self._search(conn, partial, k=5, space="fast", partial=True)}
        return await self._read(op)

    async def invalidate(self, fact_id: int, *, valid_to: When = None, retract: bool = False,
                         session_id: str | None = None) -> ChangeResult:
        return await self._write(writes.invalidate_op, fact_id, valid_to=valid_to, retract=retract,
                                 session_id=session_id)

    async def forget(self, *, episode_ids: Sequence[int] = (), fact_ids: Sequence[int] = (),
                     entity_ids: Sequence[int] = (), preview: bool = False,
                     session_id: str | None = None) -> ForgetResult:
        return await self._write(forget_op, episode_ids=list(episode_ids), fact_ids=list(fact_ids),
                                 entity_ids=list(entity_ids), preview=preview, now_ctx=self._now_ctx,
                                 session_id=session_id)

    async def undo(self, change_id: int | None = None, *, session_id: str | None = None) -> UndoResult:
        def op(ctx: writes.Ctx) -> UndoResult:
            if session_id is not None and change_id is None:
                return undo_session(ctx, session_id)
            cid = change_id
            if cid is None:
                row = ctx.conn.execute("SELECT max(id) FROM changes WHERE undone_by IS NULL AND forgotten=0"
                                       " AND op NOT IN ('undo','forget','flagged')").fetchone()
                if row[0] is None:
                    raise UndoError("nothing to undo")
                cid = row[0]
            return undo_change(ctx, cid)
        return await self._write(op, session_id=session_id)

    async def now_card(self) -> dict[str, Any]:
        row = await self._read(lambda c: c.execute("SELECT card_json FROM now_card WHERE id=1").fetchone())
        if row is None:
            return await self.rebuild_now_card(self._now_ctx)
        return json.loads(row[0])

    async def now_card_text(self) -> str:
        row = await self._read(lambda c: c.execute("SELECT card_text FROM now_card WHERE id=1").fetchone())
        if row is None:
            await self.rebuild_now_card(self._now_ctx)
            return await self.now_card_text()
        return row[0]

    async def rebuild_now_card(self, context: NowContext | None = None) -> dict[str, Any]:
        if context is not None:
            self._now_ctx = context
        ctx_now = self._now_ctx
        return await self._write(lambda ctx: cards.store_now_card(ctx.conn, ctx.now, ctx_now))

    async def standing(self, limit: int = 8) -> list[str]:
        """His preferences, rules and corrections as prompt lines (views.standing_lines). Read-only."""
        from . import views  # noqa: PLC0415
        return await self._read(views.standing_lines, limit)

    async def hub_tree(self) -> dict[str, Any]:
        """The tree, cards and facts for the hub (views.hub_tree). Read-only."""
        from . import views  # noqa: PLC0415
        return await self._read(views.hub_tree)

    async def branch_card(self, branch: str) -> dict[str, Any] | None:
        def read(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
            from . import tree
            slug = tree.resolve(conn, branch)
            if slug is None:
                return None, None
            row = conn.execute("SELECT card_json FROM branch_cards WHERE branch_id=? AND dirty=0", (slug,)).fetchone()
            return slug, (row[0] if row else None)
        slug, body = await self._read(read)
        if slug is None:
            return None
        if body is None:
            await self._write(lambda ctx: cards.store_branch_card(ctx.conn, slug, ctx.now))
            slug, body = await self._read(read)
        return json.loads(body) if body else None

    async def place(self, item_type: str, item_id: int, *, text: str | None = None, branch: str | None = None,
                    suggested: str | None = None) -> PlaceResult:
        placed, _cid = await self._write(writes.place_op, item_type, item_id, text=text, branch=branch,
                                         suggested=suggested)
        return placed

    # ------------------------------------------------------------ more of his commands (all audited, undoable)
    async def create_branch(self, name: str, parent: str, **kw: Any) -> ChangeResult:
        return await self._write(writes.create_branch_op, name, parent, **kw)

    async def file_under(self, item_type: str, item_id: int, branch: str) -> ChangeResult:
        return await self._write(writes.file_under_op, item_type, item_id, branch)

    async def pin(self, fact_id: int, pinned: bool = True) -> ChangeResult:
        return await self._write(writes.pin_op, fact_id, pinned)

    async def add_open_loop(self, text: str, **kw: Any) -> ChangeResult:
        return await self._write(writes.add_open_loop_op, text, **kw)

    async def mark_flagged(self, fact_id: int) -> ChangeResult:
        return await self._write(writes.mark_flagged_op, fact_id)

    async def fact(self, fact_id: int) -> dict[str, Any] | None:
        """One fact in the hub's contract shape (contracts/fact.schema.json)."""
        return await self._read(contract_fact, fact_id)
