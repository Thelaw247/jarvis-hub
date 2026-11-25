"""Shared pytest setup.

The browser tests (tests/e2e) use Playwright's sync API, which keeps an event loop running in the test process
from the first browser test to the end of the session. Tests that start their own loop (`asyncio.run`: the
memory store, the voice pipeline) can't run after that. So the browser tests always run last, in a plain
`python -m pytest` and in each pytest-xdist worker alike.
"""
from __future__ import annotations

import os

os.environ.setdefault("JARVIS_HUB_MODE", "demo")  # the tests run the demo day; the app itself starts live (H5)


def pytest_collection_modifyitems(items):
    items.sort(key=lambda item: "/e2e/" in item.nodeid.replace("\\", "/") or item.nodeid.startswith("e2e/"))
