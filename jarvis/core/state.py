"""The hub-facing state the core keeps (contracts/state.schema.json, v2, mode "live").

It starts empty (nothing is connected yet) and changes only through hub events on the bus. The events are folded
in with `jarvis_hub.events.apply_event`, the same reducer the demo hub and the UI's store.js mirror, so the core
and the hub can never disagree about what an event means.
"""
from __future__ import annotations

import copy
from datetime import datetime

from jarvis_hub.events import apply_event, empty_rail

from .bus import CONTRACT_V, Event, now_iso


def empty_state(now: str | None = None) -> dict:
    """A valid live state with nothing in it yet."""
    now = now or now_iso()
    return {
        "v": CONTRACT_V, "mode": "live", "now": now,
        "orb": {"state": "idle"},
        "now_card": {"greeting": "", "updated": now},
        "branches": [], "cards": {}, "facts": [], "actions": [], "approvals": [], "windows": [], "jobs": [],
        "day": {"date": now[:10], "items": []},
        "settings": {"interruption": "balanced", "theme": "night", "motion": "full"},
        "metrics": {"latency": []},
        "presence": {"here": False},
        "toasts": [],
        "rail": empty_rail(), "marks": {}, "threads": [], "focus": None,
    }


class CoreState:
    def __init__(self, state: dict | None = None) -> None:
        self.state = state or empty_state()

    def apply(self, event: Event) -> None:
        """Fold one hub event in. T0 (in memory)."""
        apply_event(self.state, event.type, copy.deepcopy(event.data), event.ts)

    def snapshot(self) -> dict:
        """What `GET /api/state` returns. T0."""
        return {**copy.deepcopy(self.state), "now": datetime.now().isoformat(timespec="seconds")}
