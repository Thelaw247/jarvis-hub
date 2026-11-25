"""ask_dewet: a task's question, asked out loud at the next quiet moment (RUNTIME §4, ASK_OR_ACT §2)."""
from __future__ import annotations

import itertools
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class Question:
    id: int
    text: str
    options: list[str] = field(default_factory=list)
    default: str | None = None
    asked: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


class Questions:
    MAX_PER_HOUR = 6  # a task can't turn Jarvis into an interviewer

    def __init__(self, announce: Callable[[str], Awaitable[object]] | None = None) -> None:
        self.announce = announce
        self.items: list[Question] = []
        self._ids = itertools.count(1)
        self._times: list[float] = []

    async def ask(self, text: str, *, options: list[str] | None = None, default: str | None = None) -> int:
        now = time.monotonic()
        self._times = [t for t in self._times if now - t < 3600]
        q = Question(next(self._ids), text.strip(), list(options or []), default)
        self.items.append(q)
        if self.announce is not None and len(self._times) < self.MAX_PER_HOUR:
            self._times.append(now)
            await self.announce(q.text)
        return q.id
