"""The demo day. One fixture (contracts/examples/state.json) feeds the server, the scenes and the tests.

The fixture is written for Monday 2026-11-16 at 3:40 pm. In the live demo (app.py) it moves to the real clock
(`rebase.py`), so the hub shows the right time; the scenes and the tests keep the fixture date.

To see the live demo at another time of day, set JARVIS_DEMO_CLOCK to a local time instead of "real", e.g.
`JARVIS_DEMO_CLOCK=2026-11-14T22:30 python app.py`: the demo starts at that time and its clock runs from there.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime

from ..settings import resource_path
from .rebase import rebase_state

FIXTURE_NOW = datetime(2026, 11, 16, 15, 40)
CLOCK_ENV = "JARVIS_DEMO_CLOCK"  # "real": the demo follows the real clock (app.py sets it); a local ISO time: a
# simulated clock that starts there (for trying the demo at 8:30 am or 10:30 pm); anything else: the fixture date
_STARTED: dict[str, datetime] = {}  # when each simulated start time was first used: its clock runs from there


def _simulated() -> datetime | None:
    try:
        return datetime.fromisoformat(os.environ.get(CLOCK_ENV, ""))
    except ValueError:
        return None


def real_clock() -> bool:
    return os.environ.get(CLOCK_ENV, "fixture") == "real" or _simulated() is not None


def clock_now() -> datetime:
    """The live demo's time: the real local time, or the simulated one running on from where it was set."""
    start = _simulated()
    if start is None:
        return datetime.now()
    began = _STARTED.setdefault(os.environ[CLOCK_ENV], datetime.now())
    return start.replace(tzinfo=None) + (datetime.now() - began)


def load_state(real: bool | None = None, now: datetime | None = None) -> dict:
    """The demo day. `real` (default: the JARVIS_DEMO_CLOCK setting) moves it to `now` (default: the demo clock,
    `clock_now()`)."""
    state = json.loads(resource_path("contracts", "examples", "state.json").read_text(encoding="utf-8"))
    if real_clock() if real is None else real:
        state = rebase_state(state, now or clock_now())
    return state


def bare_state() -> dict:
    """The demo day with nothing tracked yet: no Rail items, no marks, no spoken lines, no work threads. Tests of the
    Rail's, the marks' and the threads' own rules start here, so the fixture's realistic Rail doesn't get in their way."""
    state = copy.deepcopy(load_state(real=False))
    for slot in state["rail"]["slots"].values():
        slot.clear()
        slot["items"] = []
    state["rail"]["slots"]["jarvis"]["said"] = []
    state["marks"] = {}
    state["threads"] = []
    return state
