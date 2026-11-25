"""K0: the event bus. Typed events in the hub's envelope, filters, the state reducer, slow subscribers, speed."""
import asyncio
import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from jarvis.core.bus import CORE_EVENTS, HUB_EVENTS, EventBus
from jarvis.core.state import CoreState, empty_state

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMAS = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in CONTRACTS.glob("*.schema.json")}
REGISTRY = Registry().with_resources((n, Resource.from_contents(d)) for n, d in SCHEMAS.items())


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(SCHEMAS[f"{name}.schema.json"], registry=REGISTRY)


def run(coro):
    return asyncio.run(coro)


def test_hub_event_types_come_from_the_contract_and_core_events_dont_clash():
    assert HUB_EVENTS == set(SCHEMAS["event.schema.json"]["properties"]["type"]["enum"])
    assert not HUB_EVENTS & CORE_EVENTS
    assert {"job.done", "calendar.changed", "presence.arrived"} <= CORE_EVENTS


def test_publish_reaches_every_subscriber_in_the_contract_envelope():
    async def main():
        bus = EventBus()
        a, b = bus.subscribe(), bus.subscribe()
        bus.publish("toast", {"id": "t1", "kind": "info", "text": "Booked."})
        for sub in (a, b):
            event = await sub.get(timeout=1)
            envelope = event.envelope()
            assert envelope["v"] == 2 and envelope["type"] == "toast" and envelope["data"]["id"] == "t1"
            assert list(validator("event").iter_errors(envelope)) == []
    run(main())


def test_subscribers_only_get_the_types_they_asked_for():
    async def main():
        bus = EventBus()
        jobs = bus.subscribe(["job.done"])
        hub = bus.subscribe(hub_only=True)
        bus.publish("calendar.changed", {"id": "cal-1"})
        bus.publish("job.done", {"id": "job-1", "kind": "x", "state": "done"})
        bus.publish("orb.state", {"state": "thinking"})
        assert (await jobs.get(timeout=1)).type == "job.done" and jobs.queue.empty()
        assert (await hub.get(timeout=1)).type == "orb.state" and hub.queue.empty()  # core events never reach screens
    run(main())


def test_unknown_types_are_refused():
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.publish("orb.sate", {})
    with pytest.raises(ValueError):
        bus.subscribe(["nope.never"])


def test_hub_events_are_folded_into_the_state_before_anyone_hears_them():
    async def main():
        state = CoreState()
        bus = EventBus(reducer=state.apply)
        sub = bus.subscribe()
        bus.publish("orb.state", {"state": "listening"})
        bus.publish("job.progress", {"id": "job-a", "label": "Class sync", "state": "running", "progress": None})
        bus.publish("calendar.changed", {"id": "cal-1"})  # a core event: not part of the hub's state
        assert state.state["orb"]["state"] == "listening"
        assert [j["id"] for j in state.state["jobs"]] == ["job-a"]
        assert (await sub.get(timeout=1)).type == "orb.state"
        assert list(validator("state").iter_errors(state.snapshot())) == []
    run(main())


def test_the_empty_live_state_matches_the_contract():
    state = empty_state()
    assert state["mode"] == "live"
    assert list(validator("state").iter_errors(state)) == []


def test_a_slow_core_subscriber_loses_its_oldest_events_and_the_loss_is_counted():
    async def main():
        bus = EventBus(maxsize=3)
        sub = bus.subscribe(["calendar.changed"])
        for i in range(5):
            bus.publish("calendar.changed", {"n": i})
        assert sub.dropped == 2 and bus.dropped == 2
        assert [(await sub.get(timeout=1)).data["n"] for _ in range(3)] == [2, 3, 4]
    run(main())


def test_a_screen_that_falls_behind_is_dropped_and_the_others_carry_on():
    async def main():
        bus = EventBus()
        stuck = bus.subscribe(hub_only=True, maxsize=2, on_full="close")
        fine = bus.subscribe(hub_only=True)
        for _ in range(3):
            bus.publish("orb.state", {"state": "idle"})
        assert stuck.closed and bus.subscribers == 1
        assert fine.queue.qsize() == 3
    run(main())


def test_publish_is_t0_fast():
    """T0: publishing never waits. 10,000 events to 3 subscribers well under a second (~µs each)."""
    async def main():
        bus = EventBus(reducer=CoreState().apply, maxsize=20_000)
        subs = [bus.subscribe() for _ in range(3)]
        t0 = time.perf_counter()
        for i in range(10_000):
            bus.publish("calendar.changed", {"n": i})
        per_event_us = (time.perf_counter() - t0) / 10_000 * 1e6
        assert per_event_us < 100, per_event_us
        assert all(s.queue.qsize() == 10_000 for s in subs)
    run(main())
