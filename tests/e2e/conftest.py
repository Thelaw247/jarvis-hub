"""Browser tests: a real hub server on a free port and one Chromium for the whole run.
Skipped (not failed) when Playwright or its browser isn't installed."""
import os
import socket
import threading
import time

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="session")
def hub_url():
    import uvicorn

    from jarvis_hub.server import create_app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    app = create_app(autoplay=False, speed=float(os.environ.get("JARVIS_E2E_SPEED", "25")))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.025)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except Exception as err:  # noqa: BLE001
            pytest.skip(f"Chromium isn't installed for Playwright ({err}). Run: python -m playwright install chromium")
        yield chromium
        chromium.close()


class Hub:
    """A page plus the problems it reported (console errors, failed requests, uncaught exceptions)."""

    def __init__(self, page, base):
        self.page, self.base, self.problems = page, base, []
        page.on("console", lambda m: self.problems.append(f"console: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: self.problems.append(f"error: {e}"))
        # a request the browser cancels on leaving is not a problem: the event stream, a PDF still streaming into
        # the reader, or a sound or the PDF worker still loading when the page moves on to the next scene
        # (net::ERR_ABORTED; seen on GitHub's runners, v0.3.0). A missing file is caught below, by its 404, and a
        # hub that stops answering fails with another error, which still counts.
        page.on("requestfailed", lambda r: self.problems.append(f"failed: {r.url}")
                if "/api/events" not in r.url and "/api/file/" not in r.url and "ERR_ABORTED" not in (r.failure or "") else None)
        page.on("response", lambda r: self.problems.append(f"{r.status}: {r.url}") if r.status >= 400 else None)

    def open(self, path="", **query):
        params = "&".join(f"{k}={v}" for k, v in query.items())
        self.page.goto(f"{self.base}/{'?' + params if params else ''}{path}")
        self.page.wait_for_selector("html[data-ready]", timeout=10_000)
        return self.page

    def scene(self, name, theme="day", size=None, **more):
        query = {"scene": name, "theme": theme, **({"size": size} if size else {}), **more}
        return self.open(**query)

    def state(self, expr="s => s"):
        return self.page.evaluate(f"(({expr}))(window.__jarvis.store.state)")


@pytest.fixture
def hub(browser, hub_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(8_000)
    yield Hub(page, hub_url)
    context.close()
