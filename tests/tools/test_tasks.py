"""The task brain (TOOLS §2): tasks start at once, show in the hub, report back by voice and on screen, respect caps,
and Agent SDK permissions allow reads only."""
from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.tasks import TaskRunner
from jarvis.tools import Registry, ToolContext


def runner(agent=None, browser=None):
    events, said = [], []

    async def publish(t, d):
        events.append((t, d))

    async def announce(text):
        said.append(text)
    r = TaskRunner(Path("/tmp/jarvis-test"), Registry(), lambda origin="task": ToolContext(root=Path("."),
                   browser=browser, origin=origin), keyed=None, publish=publish, announce=announce, agent=agent)
    return r, events, said


def test_research_starts_at_once_and_reports_back():
    async def agent(task, note, opts):
        assert "research" in note.lower() and opts["cap"] == 0.30
        await asyncio.sleep(0.05)
        return "Student Plus is cheapest at $9 a month.\n\nDetails…\n\nSources: https://example.com", 0.12

    async def main():
        r, events, said = runner(agent)
        t = await r.start("research", "cheapest phone plan for students")
        assert t.state == "running"
        await t.handle
        return r, t, events, said

    r, t, events, said = asyncio.run(main())
    assert t.state == "done" and t.cost_usd == 0.12
    assert said == ["Student Plus is cheapest at $9 a month."]                 # short, spoken
    kinds = [e[0] for e in events]
    assert kinds[0] == "task.updated" and "window.push" in kinds              # on screen too
    from tests.test_contracts import validator
    for typ, data in events:
        if typ == "task.updated":
            assert list(validator("agent_task").iter_errors(data["task"])) == []


def test_a_failed_or_slow_task_says_so_plainly():
    async def boom(task, note, opts):
        raise RuntimeError("secret detail")

    async def main():
        r, events, said = runner(boom)
        t = await r.start("task", "plan my week")
        await t.handle
        return t, said

    t, said = asyncio.run(main())
    assert t.state == "failed" and "RuntimeError" in t.why and "secret" not in said[0]


def test_browse_tasks_use_the_browser_worker():
    class Out:
        steps, failed = 4, False

        def report(self):
            return "PAWS shows GE 122 in ENGR 1A10.\n\nSources: PAWS"

    class Browser:
        needs_sign_in = False

        async def browse(self, task, start_url=None, mode="read"):
            assert mode == "read"
            return Out()

    async def main():
        r, events, said = runner(browser=Browser())
        t = await r.start("browse", "find my GE 122 room on PAWS")
        await t.handle
        return t, said

    t, said = asyncio.run(main())
    assert t.state == "done" and said[0].startswith("PAWS shows")


def test_task_permissions_allow_reading_only():
    import pytest
    sdk = pytest.importorskip("claude_agent_sdk")
    r, _, _ = runner()

    async def check(name):
        return await r._permission(name, {}, None)
    for ok in ("Read", "Grep", "WebSearch", "WebFetch", "mcp__jarvis__canvas_find", "Skill"):
        assert isinstance(asyncio.run(check(ok)), sdk.PermissionResultAllow), ok
    for no in ("Bash", "Write", "Edit", "NotebookEdit", "mcp__other__send_email"):
        res = asyncio.run(check(no))
        assert isinstance(res, sdk.PermissionResultDeny) and "proposal" in res.message, no
