"""K0: the SQLite job queue. Durable across a restart, at most 2 at once, de-duplication, retries and caps."""
import asyncio
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from jarvis.core.bus import EventBus
from jarvis.core.queue import Caps, JobQueue

JOB_SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "job.schema.json").read_text(encoding="utf-8"))


def run(coro):
    return asyncio.run(coro)


async def opened(path: Path, **kw) -> JobQueue:
    queue = JobQueue(path, retry_base_s=0.01, poll_s=0.02, **kw)
    await queue.open()
    return queue


def test_jobs_survive_a_restart(tmp_path):
    db = tmp_path / "data" / "jobs.db"

    async def first_run():
        queue = await opened(db)
        ids = [await queue.submit("sync", {"n": i}, label="Class sync") for i in range(3)]
        await queue.close()  # the core stops before any of them ran
        return ids

    async def second_run(ids):
        queue = await opened(db)
        assert [j.id for j in await queue.list("queued")] == ids
        seen = []

        async def handler(ctx):
            seen.append(ctx.args["n"])
            return {"n": ctx.args["n"]}

        queue.register("sync", handler)
        await queue.start()
        await queue.wait_idle()
        jobs = await queue.list()
        await queue.close()
        return seen, jobs

    ids = run(first_run())
    seen, jobs = run(second_run(ids))
    assert sorted(seen) == [0, 1, 2]
    assert {j.state for j in jobs} == {"done"} and [j.result for j in jobs] == [{"n": 0}, {"n": 1}, {"n": 2}]


def test_a_job_running_when_the_core_died_runs_again_after_restart(tmp_path):
    db = tmp_path / "jobs.db"

    async def crash():
        queue = await opened(db)
        job_id = await queue.submit("sync", label="Class sync", max_attempts=3)
        last = await queue.submit("sync", label="Class sync", max_attempts=1)
        await queue._call(queue._claim_sync, ("sync",))  # both claimed (running) ...
        await queue._call(queue._claim_sync, ("sync",))
        queue._exec.shutdown(wait=True)  # ... and the process dies without finishing them
        return job_id, last

    async def restart(job_id, last):
        queue = await opened(db)
        assert queue.recovered == 1
        retried, gave_up = await queue.get(job_id), await queue.get(last)
        await queue.close()
        return retried, gave_up

    job_id, last = run(crash())
    retried, gave_up = run(restart(job_id, last))
    assert retried.state == "queued" and retried.attempts == 1
    assert gave_up.state == "failed" and gave_up.error_code == "interrupted"


def test_never_more_than_two_jobs_at_once(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db", concurrency=2)
        now, peak = 0, 0

        async def handler(ctx):
            nonlocal now, peak
            now += 1
            peak = max(peak, now)
            await asyncio.sleep(0.05)
            now -= 1

        queue.register("work", handler)
        for _ in range(6):
            await queue.submit("work", label="Work")
        await queue.start()
        await queue.wait_idle()
        counts = await queue.counts()
        await queue.close()
        return peak, counts

    peak, counts = run(main())
    assert peak == 2 and counts["done"] == 6


def test_duplicates_collapse_while_queued_but_not_while_running(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db")
        ids = {await queue.submit("class-sync", label="Class sync", dedupe_key="class-sync") for _ in range(10)}
        assert len(ids) == 1  # ten Canvas changes, one class-sync
        await queue._call(queue._claim_sync, ("class-sync",))  # it starts running ...
        later = await queue.submit("class-sync", label="Class sync", dedupe_key="class-sync")  # ... a new change came in
        await queue.close()
        return ids, later

    ids, later = run(main())
    assert later not in ids


def test_failures_are_retried_then_given_up(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db")
        tries = {"flaky": 0, "broken": 0}

        async def flaky(ctx):
            tries["flaky"] += 1
            if tries["flaky"] < 3:
                raise ConnectionError("the network said something with a secret sk-123 in it")
            return "ok"

        async def broken(ctx):
            tries["broken"] += 1
            raise RuntimeError("always")

        queue.register("flaky", flaky)
        queue.register("broken", broken)
        a = await queue.submit("flaky", label="Flaky", max_attempts=3)
        b = await queue.submit("broken", label="Broken", max_attempts=2)
        await queue.start()
        await queue.wait_idle()
        jobs = await queue.get(a), await queue.get(b)
        await queue.close()
        return tries, jobs

    tries, (a, b) = run(main())
    assert tries == {"flaky": 3, "broken": 2}
    assert a.state == "done" and a.attempts == 3
    assert b.state == "failed" and b.error_code == "RuntimeError"  # the class name only, never the message


def test_caps_stop_a_job_and_are_never_retried(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db")
        calls = {"slow": 0, "spender": 0}

        async def slow(ctx):
            calls["slow"] += 1
            await asyncio.sleep(5)

        async def spender(ctx):
            calls["spender"] += 1
            for _ in range(10):
                ctx.spend(usd=0.10, turns=1)

        queue.register("slow", slow)
        queue.register("spender", spender)
        s = await queue.submit("slow", label="Slow", caps=Caps(seconds=0.05))
        p = await queue.submit("spender", label="Spender", caps=Caps(usd=0.25, turns=20))
        await queue.start()
        await queue.wait_idle()
        jobs = await queue.get(s), await queue.get(p)
        await queue.close()
        return calls, jobs

    calls, (s, p) = run(main())
    assert calls == {"slow": 1, "spender": 1}
    assert (s.state, s.error_code, s.caps.seconds) == ("failed", "cap_seconds", 0.05)
    assert (p.state, p.error_code) == ("failed", "cap_usd") and 0.25 < p.spent_usd < 0.35 and p.turns == 3


def test_stopping_puts_a_running_job_back_without_counting_the_try(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db")
        started = asyncio.Event()

        async def long(ctx):
            started.set()
            await asyncio.sleep(10)

        queue.register("long", long)
        job_id = await queue.submit("long", label="Long")
        await queue.start()
        await asyncio.wait_for(started.wait(), 2)
        await queue.close()
        queue = await opened(tmp_path / "jobs.db")
        job = await queue.get(job_id)
        await queue.close()
        return job

    job = run(main())
    assert job.state == "queued" and job.attempts == 0


def test_cancel_a_queued_job(tmp_path):
    async def main():
        queue = await opened(tmp_path / "jobs.db")
        job_id = await queue.submit("never", label="Never")
        assert await queue.cancel(job_id)
        job = await queue.get(job_id)
        await queue.close()
        return job

    assert run(main()).state == "cancelled"


def test_progress_goes_out_as_contract_job_events_and_the_end_as_job_done(tmp_path):
    async def main():
        bus = EventBus()
        sub = bus.subscribe(["job.progress", "job.done"])
        queue = await opened(tmp_path / "jobs.db", bus=bus)

        async def handler(ctx):
            ctx.progress(0.5)

        queue.register("sync", handler)
        await queue.submit("sync", label="Class sync")
        await queue.start()
        await queue.wait_idle()
        await queue.close()
        return [sub.queue.get_nowait() for _ in range(sub.queue.qsize())]

    events = run(main())
    progress = [e.data for e in events if e.type == "job.progress"]
    assert [p["state"] for p in progress] == ["running", "running", "done"]
    assert [p["progress"] for p in progress] == [None, 0.5, 1.0]
    validator = Draft202012Validator(JOB_SCHEMA)
    assert all(list(validator.iter_errors(p)) == [] for p in progress)
    assert events[-1].type == "job.done" and events[-1].data["state"] == "done"
