"""The event bus: in-process pub/sub with typed events (RUNTIME §2).

Every event has the hub's SSE envelope (contracts/event.schema.json): `{ v: 2, type, ts, data }`. Two families:
- **hub events** (`HUB_EVENTS`, read from the contract): what screens see; they are folded into the core's state
  and streamed to the hub over `/api/events`.
- **core events** (`CORE_EVENTS`, RUNTIME §2): what pollers, the queue and the action layer tell each other
  (`calendar.changed`, `job.done`, ...). They never leave the process.
A type in neither family is refused, so a typo can't become a silent event.

Publishing never waits: each subscriber has its own bounded queue. A screen that falls behind is dropped (it
reconnects and reloads the state); a core subscriber that falls behind loses its oldest events and the loss is
counted (and shows on /healthz).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from . import REPO
from .logs import EventLog

CONTRACT_V = 2
CORE_EVENTS = frozenset({
    "calendar.changed", "class.ended", "canvas.new_item", "canvas.login_needed", "email.important",
    "presence.arrived", "presence.left", "game.started", "game.stopped", "job.done", "action.proposed",
    "action.approved", "question.asked", "core.started", "core.stopping",
})
log = EventLog("jarvis.core.bus")


def _hub_events() -> frozenset[str]:
    schema = json.loads((REPO / "contracts" / "event.schema.json").read_text(encoding="utf-8"))
    return frozenset(schema["properties"]["type"]["enum"])


HUB_EVENTS = _hub_events()


def now_iso() -> str:
    """Contract times are local ISO date-times (the demo hub uses the same form)."""
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    data: dict[str, Any]
    ts: str = field(default_factory=now_iso)

    @property
    def for_hub(self) -> bool:
        return self.type in HUB_EVENTS

    def envelope(self) -> dict:
        return {"v": CONTRACT_V, "type": self.type, "ts": self.ts, "data": self.data}


class Subscription:
    """One subscriber's mailbox. Iterate it (`async for event in sub`) or `await sub.get()`."""

    def __init__(self, bus: EventBus, types: frozenset[str] | None, maxsize: int,
                 on_full: Literal["drop_oldest", "close"]) -> None:
        self._bus, self.types, self.on_full = bus, types, on_full
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize)
        self.dropped = 0
        self.closed = False

    def wants(self, event: Event) -> bool:
        return self.types is None or event.type in self.types

    def offer(self, event: Event) -> None:
        """T0: never blocks the publisher."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            if self.on_full == "close":
                self.close()
                return
            self.queue.get_nowait()
            self.queue.put_nowait(event)
            self.dropped += 1

    async def get(self, timeout: float | None = None) -> Event:
        if self.closed and self.queue.empty():
            raise StopAsyncIteration
        return await asyncio.wait_for(self.queue.get(), timeout) if timeout else await self.queue.get()

    def close(self) -> None:
        self.closed = True
        self._bus.unsubscribe(self)

    def __aiter__(self):
        return self

    async def __anext__(self) -> Event:
        return await self.get()


class EventBus:
    def __init__(self, reducer: Callable[[Event], None] | None = None, maxsize: int = 256) -> None:
        """`reducer` folds hub events into the core's state before anyone hears about them, so a screen that loads
        `/api/state` and then subscribes never misses or double-counts a change."""
        self._reducer = reducer
        self._maxsize = maxsize
        self._subs: set[Subscription] = set()
        self.taps: list[Callable[[Event], None]] = []   # hears every event as it is published (review recording)
        self.published = 0

    @property
    def subscribers(self) -> int:
        return len(self._subs)

    @property
    def dropped(self) -> int:
        return sum(s.dropped for s in self._subs)

    def publish(self, type: str, data: dict | None = None, ts: str | None = None) -> Event:
        """Publish one event to every interested subscriber. T0 (no awaits, no I/O; microseconds)."""
        if type not in HUB_EVENTS and type not in CORE_EVENTS:
            raise ValueError(f"unknown event type: {type}")
        event = Event(type, dict(data or {}), ts or now_iso())
        if event.for_hub and self._reducer is not None:
            self._reducer(event)
        for sub in list(self._subs):
            if sub.wants(event):
                sub.offer(event)
        for tap in self.taps:
            tap(event)
        self.published += 1
        return event

    def subscribe(self, types: Iterable[str] | None = None, *, hub_only: bool = False, maxsize: int | None = None,
                  on_full: Literal["drop_oldest", "close"] = "drop_oldest") -> Subscription:
        wanted = frozenset(types) if types is not None else (HUB_EVENTS if hub_only else None)
        if wanted is not None and (bad := wanted - HUB_EVENTS - CORE_EVENTS):
            raise ValueError(f"unknown event types: {sorted(bad)}")
        sub = Subscription(self, wanted, maxsize or self._maxsize, on_full)
        self._subs.add(sub)
        log.debug("bus.subscribed", count=len(self._subs))
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subs.discard(sub)
