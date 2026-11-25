"""The abilities branch (TOOLS §4): Jarvis knows what it can do from its own memory, refreshed at start."""
from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.memory.store import MemoryStore
from jarvis.tools import Registry, ToolContext
from jarvis.tools.abilities import ability_lines, sync_abilities


def test_abilities_are_filed_in_memory_and_recalled(tmp_path):
    async def main():
        store = await MemoryStore(tmp_path / "jarvis.db").start()
        try:
            reg = Registry()
            c = ToolContext(root=Path("."), documents=object(), memory=store)
            n = await sync_abilities(store, reg, c, skills=[("week-planner", "Plans his week and books it")])
            again = await sync_abilities(store, reg, c)          # a restart: refreshed, not duplicated
            hits = await store.search("read PDFs Word documents", k=5)
            recalled = await reg.run("recall", {"query": "Canvas search"}, c)
            card = await store.branch_card("abilities")
            return n, again, hits, recalled, card
        finally:
            await store.close()

    n, again, hits, recalled, card = asyncio.run(main())
    assert n == len(Registry().specs) + 1 and again == n - 1
    assert any("read_document" in h.text for h in hits)
    assert not recalled.is_error and "canvas_find" in recalled.content
    assert card is not None


def test_ability_lines_say_how_each_one_behaves():
    reg = Registry()
    lines = dict(ability_lines(reg, ToolContext(root=Path("."))))
    assert lines["tool:browse"].startswith("Jarvis can use a real browser")
    assert "background task" in lines["tool:browse"] and "(now: off)" in lines["tool:browse"]
    assert "free to use" in lines["tool:web_search"]
