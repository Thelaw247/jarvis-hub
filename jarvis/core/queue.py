"""The job queue: a durable SQLite table with at most 2 jobs running at once (RUNTIME §2, §4).

- **Durable.** Every job is a row in `<root>/data/jobs.db` (WAL, synchronous=FULL). A job that was running when
  the core stopped or crashed goes back to `queued` at the next start (or to `failed`, code `interrupted`, if it
  had no tries left).
- **De-duplicated.** Jobs with the same `dedupe_key` collapse while one is still queued: ten Canvas changes make
  one class-sync. A key whose job is already running queues one more run (the change came in after it started).
- **Retries.** A handler that raises is tried again after 1 s, 2 s, 4 s ... up to `max_attempts`.
- **Caps per job.** `Caps(seconds, usd, turns)`: the time cap is enforced here; spend and turns are counted by
  the handler through `ctx.spend(...)`, which stops the job when a cap is passed. A cap stop is never retried.
- **Screens see it.** Each job's progress goes out as `job.progress` (contracts/job.schema.json) and the end as
  the core event `job.done`.

All SQLite work happens on one private thread, so the event loop never waits on the disk.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bus import EventBus
from .logs import EventLog

log = EventLog("jarvis.core.queue")
STATES = ("queued", "running", "done", "failed", "cancelled")
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  dedupe_key TEXT,
  args TEXT NOT NULL DEFAULT '{}',
  state TEXT NOT NULL CHECK (state IN ('queued','running','done','failed','cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  cap_seconds REAL,
  cap_usd REAL,
  cap_turns INTEGER,
  spent_usd REAL NOT NULL DEFAULT 0,
  turns INTEGER NOT NULL DEFAULT 0,
  run_after REAL NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  error_code TEXT,
  result TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_dedupe_queued ON jobs(dedupe_key) WHERE dedupe_key IS NOT NULL AND state = 'queued';
CREATE INDEX IF NOT EXISTS jobs_next ON jobs(state, run_after, created_at);
"""


@dataclass(frozen=True)
class Caps:
    seconds: float | None = None
    usd: float | None = None
    turns: int | None = None


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    label: str
    dedupe_key: str | None
    args: dict
    state: str
    attempts: int
    max_attempts: int
    caps: Caps
    spent_usd: float
    turns: int
    run_after: float
    created_at: float
    updated_at: float
    error_code: str | None
    result: Any

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Job:
        return cls(row["id"], row["kind"], row["label"], row["dedupe_key"], json.loads(row["args"]), row["state"],
                   row["attempts"], row["max_attempts"], Caps(row["cap_seconds"], row["cap_usd"], row["cap_turns"]),
                   row["spent_usd"], row["turns"], row["run_after"], row["created_at"], row["updated_at"],
                   row["error_code"], json.loads(row["result"]) if row["result"] else None)


class CapExceeded(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JobContext:
    """What a handler gets: its job, the caps, a way to count spend and to report real progress."""

    def __init__(self, queue: JobQueue, job: Job) -> None:
        self._queue, self.job = queue, job
        self.spent_usd, self.turns = job.spent_usd, job.turns

    @property
    def id(self) -> str: return self.job.id
    @property
    def args(self) -> dict: return self.job.args
    @property
    def caps(self) -> Caps: return self.job.caps
    @property
    def attempt(self) -> int: return self.job.attempts

    def spend(self, usd: float = 0.0, turns: int = 0) -> None:
        """Count what a step cost. Raises CapExceeded once a cap is passed (the job stops, no retry)."""
        self.spent_usd += usd
        self.turns += turns
        if self.caps.usd is not None and self.spent_usd > self.caps.usd:
            raise CapExceeded("cap_usd")
        if self.caps.turns is not None and self.turns > self.caps.turns:
            raise CapExceeded("cap_turns")

    def progress(self, fraction: float | None, detail: str | None = None) -> None:
        """Real progress only (0..1), or None when it can't be measured (job contract)."""
        self._queue._announce(self.job, "running", fraction, detail)


Handler = Callable[[JobContext], Awaitable[Any]]


class JobQueue:
    def __init__(self, path: Path, bus: EventBus | None = None, concurrency: int = 2, retry_base_s: float = 1.0,
                 poll_s: float = 0.5, clock: Callable[[], float] = time.time) -> None:
        self.path, self.bus, self.concurrency = Path(path), bus, concurrency
        self.retry_base_s, self.poll_s, self._clock = retry_base_s, poll_s, clock
        self._handlers: dict[str, Handler] = {}
        self._exec: ThreadPoolExecutor | None = None
        self._db: sqlite3.Connection | None = None
        self._wake = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._running: dict[str, asyncio.Task] = {}
        self.recovered = 0

    # -- the private SQLite thread --
    async def _call(self, fn: Callable, *args):
        if self._exec is None:
            raise RuntimeError("the job queue is not open")
        return await asyncio.get_running_loop().run_in_executor(self._exec, fn, *args)

    def _open_sync(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        db.executescript(SCHEMA)
        self._db = db
        now = self._clock()
        with db:  # a job that was running when the core stopped: try it again, or give up if it had no tries left
            db.execute("UPDATE jobs SET state='failed', error_code='interrupted', updated_at=? "
                       "WHERE state='running' AND attempts >= max_attempts", (now,))
            cur = db.execute("UPDATE jobs SET state='queued', run_after=?, updated_at=? WHERE state='running'", (now, now))
        return cur.rowcount

    def _close_sync(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    async def open(self) -> None:
        """Open (or create) the table and recover interrupted jobs. T1 (once at start)."""
        if self._exec is None:
            self._exec = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-jobs-db")
        self.recovered = await self._call(self._open_sync)
        log.info("queue.opened", count=self.recovered)

    async def close(self) -> None:
        await self.stop()
        if self._exec is not None:
            await self._call(self._close_sync)
            self._exec.shutdown(wait=True)
            self._exec = None

    # -- jobs --
    def register(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler
        self._wake.set()

    def _submit_sync(self, kind: str, label: str, args: dict, dedupe_key: str | None, caps: Caps,
                     max_attempts: int, delay_s: float) -> tuple[str, bool]:
        assert self._db is not None
        now = self._clock()
        if dedupe_key is not None:
            row = self._db.execute("SELECT id FROM jobs WHERE dedupe_key=? AND state='queued'", (dedupe_key,)).fetchone()
            if row:
                return row["id"], False
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        with self._db:
            self._db.execute(
                "INSERT INTO jobs (id, kind, label, dedupe_key, args, state, max_attempts, cap_seconds, cap_usd, cap_turns,"
                " run_after, created_at, updated_at) VALUES (?,?,?,?,?,'queued',?,?,?,?,?,?,?)",
                (job_id, kind, label, dedupe_key, json.dumps(args), max_attempts, caps.seconds, caps.usd, caps.turns,
                 now + delay_s, now, now))
        return job_id, True

    async def submit(self, kind: str, args: dict | None = None, *, label: str, dedupe_key: str | None = None,
                     caps: Caps | None = None, max_attempts: int = 3, delay_s: float = 0.0) -> str:
        """Queue a job and return its id (the existing job's id when `dedupe_key` matches a queued one). T1."""
        job_id, new = await self._call(self._submit_sync, kind, label, dict(args or {}), dedupe_key, caps or Caps(),
                                       max(1, max_attempts), delay_s)
        log.info("job.queued" if new else "job.deduped", job_id=job_id, kind=kind)
        self._wake.set()
        return job_id

    def _get_sync(self, job_id: str) -> Job | None:
        assert self._db is not None
        row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return Job.from_row(row) if row else None

    async def get(self, job_id: str) -> Job | None:
        return await self._call(self._get_sync, job_id)

    def _list_sync(self, state: str | None) -> list[Job]:
        assert self._db is not None
        sql, args = ("SELECT * FROM jobs WHERE state=? ORDER BY created_at", (state,)) if state else (
            "SELECT * FROM jobs ORDER BY created_at", ())
        return [Job.from_row(r) for r in self._db.execute(sql, args)]

    async def list(self, state: str | None = None) -> list[Job]:
        return await self._call(self._list_sync, state)

    def _counts_sync(self) -> dict[str, int]:
        assert self._db is not None
        counts = dict.fromkeys(STATES, 0)
        counts.update({r["state"]: r["n"] for r in self._db.execute("SELECT state, count(*) AS n FROM jobs GROUP BY state")})
        return counts

    async def counts(self) -> dict[str, int]:
        return await self._call(self._counts_sync)

    def _cancel_sync(self, job_id: str) -> bool:
        assert self._db is not None
        with self._db:
            cur = self._db.execute("UPDATE jobs SET state='cancelled', updated_at=? WHERE id=? AND state='queued'",
                                   (self._clock(), job_id))
        return cur.rowcount == 1

    async def cancel(self, job_id: str) -> bool:
        """Cancel a queued job (a running one finishes or hits its cap)."""
        task = self._running.get(job_id)
        if task is not None:
            task.cancel()
            return True
        return await self._call(self._cancel_sync, job_id)

    def _claim_sync(self, kinds: tuple[str, ...]) -> Job | None:
        """Take the next due job of a kind we can run, atomically."""
        assert self._db is not None
        if not kinds:
            return None
        now = self._clock()
        marks = ",".join("?" * len(kinds))
        with self._db:
            row = self._db.execute(
                f"SELECT id FROM jobs WHERE state='queued' AND run_after<=? AND kind IN ({marks}) "
                "ORDER BY run_after, created_at LIMIT 1", (now, *kinds)).fetchone()
            if row is None:
                return None
            self._db.execute("UPDATE jobs SET state='running', attempts=attempts+1, updated_at=? WHERE id=?",
                             (now, row["id"]))
        return self._get_sync(row["id"])

    def _finish_sync(self, job_id: str, state: str, error_code: str | None, result: Any, spent_usd: float, turns: int,
                     run_after: float | None = None, refund: bool = False) -> None:
        assert self._db is not None
        now = self._clock()
        with self._db:
            self._db.execute(
                "UPDATE jobs SET state=?, error_code=?, result=?, spent_usd=?, turns=?, updated_at=?, run_after=COALESCE(?, run_after),"
                " attempts=attempts-? WHERE id=?",
                (state, error_code, json.dumps(result) if result is not None else None, spent_usd, turns, now, run_after,
                 1 if refund else 0, job_id))

    # -- workers --
    async def start(self) -> None:
        """Start running jobs (at most `concurrency` at once)."""
        if self._loop_task is None or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._dispatch(), name="jarvis-jobs")

    async def stop(self) -> None:
        """Stop taking jobs; running ones are put back in the queue for next time (their try is not counted)."""
        if self._loop_task is not None:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None
        tasks = list(self._running.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def alive(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    @property
    def active(self) -> int:
        return len(self._running)

    async def _dispatch(self) -> None:
        while True:
            self._wake.clear()
            while len(self._running) < self.concurrency:
                job = await self._call(self._claim_sync, tuple(self._handlers))
                if job is None:
                    break
                task = asyncio.create_task(self._run(job), name=f"jarvis-job-{job.id}")
                self._running[job.id] = task
                task.add_done_callback(lambda _t, jid=job.id: (self._running.pop(jid, None), self._wake.set()))
            try:
                await asyncio.wait_for(self._wake.wait(), self.poll_s)
            except TimeoutError:
                pass

    async def wait_idle(self, timeout: float = 5.0) -> None:
        """Tests: wait until nothing is queued-and-due or running."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            counts = await self.counts()
            if counts["running"] == 0 and counts["queued"] == 0 and not self._running:
                return
            await asyncio.sleep(0.01)
        raise TimeoutError("the job queue did not go idle")

    async def _run(self, job: Job) -> None:
        ctx = JobContext(self, job)
        started = time.monotonic()
        self._announce(job, "running", None)
        log.info("job.started", job_id=job.id, kind=job.kind, attempt=job.attempts)
        state, code, result, run_after = "done", None, None, None
        try:
            coro = self._handlers[job.kind](ctx)
            result = await (asyncio.wait_for(coro, job.caps.seconds) if job.caps.seconds else coro)
        except asyncio.CancelledError:  # stopping: back in the queue, this try doesn't count
            await self._call(self._finish_sync, job.id, "queued", None, None, ctx.spent_usd, ctx.turns, None, True)
            log.info("job.requeued", job_id=job.id, reason="stopping")
            raise
        except CapExceeded as cap:
            state, code = "failed", cap.code
        except TimeoutError:
            state, code = "failed", "cap_seconds"
        except Exception as err:  # noqa: BLE001 - any handler failure is retried, then reported by class name only
            code = type(err).__name__
            if job.attempts < job.max_attempts:
                state, run_after = "queued", self._clock() + self.retry_base_s * 2 ** (job.attempts - 1)
            else:
                state = "failed"
        ms = (time.monotonic() - started) * 1000
        await self._call(self._finish_sync, job.id, state, code, result if state == "done" else None, ctx.spent_usd,
                         ctx.turns, run_after)
        log.info(f"job.{'retry' if state == 'queued' else state}", job_id=job.id, kind=job.kind, ms=ms,
                 attempt=job.attempts, code=code)
        if state != "queued":
            self._announce(job, state, 1.0 if state == "done" else None)
            if self.bus is not None:
                self.bus.publish("job.done", {"id": job.id, "kind": job.kind, "state": state, "ms": round(ms),
                                              **({"code": code} if code else {})})
        self._wake.set()

    def _announce(self, job: Job, state: str, progress: float | None, detail: str | None = None) -> None:
        if self.bus is None:
            return
        data: dict = {"id": job.id, "label": job.label, "state": state, "progress": progress}
        if detail:
            data["detail"] = detail
        self.bus.publish("job.progress", data)
