"""Shared fixtures for the memory tests: a fresh jarvis.db per test, fake embedders, a clock we control."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.memory import FakeEmbedder, MemoryStore


class Clock:
    def __init__(self) -> None:
        self.t = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kw: float) -> datetime:
        self.t += timedelta(**kw)
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def run():
    """Run a coroutine on a fresh loop (no pytest-asyncio needed)."""
    loop = asyncio.new_event_loop()
    yield loop.run_until_complete
    loop.close()


@pytest.fixture
def store(tmp_path, clock, run):
    s = MemoryStore(tmp_path / "jarvis.db", {"fast": FakeEmbedder(32, "fake-fast-32"),
                                             "index": FakeEmbedder(64, "fake-index-64")},
                    clock=clock, card_debounce=0)
    run(s.start())
    yield s
    run(s.close())
