"""The core logs where it froze (v0.12.2): a blocked event loop is reported with its code location, not text."""
from __future__ import annotations

import asyncio
import time

from jarvis.core.stallwatch import StallWatch


def blocking_launch():
    time.sleep(2.0)  # stands in for a process start that blocks the loop


def test_a_frozen_loop_is_reported_with_where_it_was_stuck():
    async def main():
        watch = StallWatch(asyncio.get_running_loop(), threshold=0.5, every=0.1)
        watch.start()
        await asyncio.sleep(0.3)
        blocking_launch()
        await asyncio.sleep(0.5)
        watch.stop()
        return watch.stalls

    stalls = asyncio.run(main())
    assert len(stalls) == 1
    ms, stack = stalls[0]
    assert 1400 <= ms <= 3000
    assert any(s.endswith(":blocking_launch") for s in stack) and all(" " not in s for s in stack)


def test_every_location_survives_the_log_filter():
    """The first stall on Laptop B logged an empty list: its frames (imports, "<module>") were dropped by C21's
    filter. Locations are now made log-safe, so all of them reach the log."""
    import sys

    from jarvis.core.logs import clean
    from jarvis.core.stallwatch import where

    ids = where(sys._getframe())
    assert ids and clean({"ids": ids})["ids"] == ids


def test_plain_extra_fields_keep_their_ids_and_error_names_but_never_words():
    """v0.14.0: the voice loop logs the plain way (extra={"turn": ...}); those lines used to arrive bare, so the log
    said "tool.failed" and nothing else."""
    import json
    import logging

    from jarvis.core.logs import JsonFormatter

    rec = logging.LogRecord("jarvis.tools", logging.WARNING, __file__, 1, "tool.failed", None, None)
    rec.__dict__.update({"tool": "canvas_find", "error": "TimeoutError", "turn": "turn-6",
                         "text": "what is my first class tomorrow", "reason": "he said something private"})
    line = json.loads(JsonFormatter().format(rec))
    assert line["event"] == "tool.failed" and line["tool"] == "canvas_find"
    assert line["error"] == "TimeoutError" and line["turn"] == "turn-6"
    assert "text" not in line and "reason" not in line          # words never get in: not a token, not an allowed name
