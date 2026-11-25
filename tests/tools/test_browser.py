"""Claude's browser tools on Playwright (TOOLS §6): read with refs, find, click, fill, tabs; and the lines held in
code: no passwords typed, read mode never submits, act mode leaves the submit for him, http(s) only."""
from __future__ import annotations

import asyncio
import functools
import http.server
import threading

import pytest

pytest.importorskip("playwright")
from anthropic.tools import ToolError  # noqa: E402
from anthropic.tools.browser import BetaToolsetCallContext  # noqa: E402

from jarvis.browser.driver import JarvisBrowser, check_url  # noqa: E402

PAGES = {
    "index.html": """<html><head><title>GE 122 course site</title></head><body><main>
      <h1>GE 122</h1><nav><a href="labs.html">Labs</a> <a href="news.html" target="_blank">News</a></nav>
      <form role="search" action="search.html" method="get"><input type="search" name="q" placeholder="Search the course">
      <button type="submit">Search</button></form>
      <p>Lab 5 is in Engineering 1B71.</p></main></body></html>""",
    "labs.html": "<html><head><title>Labs</title></head><body><h1>Labs</h1><p>Lab 5: Trusses, Thursday 2 pm.</p></body></html>",
    "news.html": "<html><head><title>News</title></head><body><p>Midterm moved.</p></body></html>",
    "search.html": "<html><head><title>Results</title></head><body><p>1 result for your search</p></body></html>",
    "form.html": """<html><head><title>Account</title></head><body><form method="post" action="done.html">
      <label for="u">Email</label><input id="u" name="u"><label for="p">Password</label><input id="p" type="password">
      <label for="m">Message</label><textarea id="m"></textarea>
      <button type="submit">Send message</button></form></body></html>""",
    "done.html": "<html><body>Sent</body></html>",
}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    for name, html in PAGES.items():
        (root / name).write_text(html)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def local_ok(url: str) -> str:
    return url if url in ("back", "forward", "reload") or url.startswith("http://127.0.0.1") else check_url(url)


async def session(mode="read"):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
    return pw, browser, JarvisBrowser(ctx, mode=mode, url_check=local_ok)


async def call(drv, name, **inp):
    out = await drv.call(BetaToolsetCallContext(), name, inp)
    if isinstance(out, list):
        return "\n".join(b.get("text", "") for b in out if isinstance(b, dict))
    return str(out)


def run(coro):
    return asyncio.run(coro)


def test_read_find_click_and_tabs(site):
    async def go():
        pw, browser, drv = await session()
        try:
            nav = await call(drv, "navigate", url=f"{site}/index.html")
            tree = await call(drv, "read_page")
            found = await call(drv, "find", query="labs link")
            ref = found.split("[")[1].split("]")[0]
            await call(drv, "left_click", target={"type": "ref", "ref": ref})
            text = await call(drv, "get_page_text")
            await call(drv, "navigate", url="back")
            news = (await call(drv, "find", query="news")).split("[")[1].split("]")[0]
            await call(drv, "left_click", target={"type": "ref", "ref": news})  # opens a new tab
            await asyncio.sleep(0.3)
            tabs = await drv.list_tabs(None, None)
            return nav, tree, text, tabs
        finally:
            await browser.close(); await pw.stop()
    nav, tree, text, tabs = run(go())
    assert "GE 122 course site" in nav
    assert '- link "Labs" [ref_' in tree and "searchbox" in tree and "[ref_" in tree
    assert "Thursday 2 pm" in text
    assert len(tabs) == 2 and sum(t["active"] for t in tabs) == 1


def test_search_forms_work_in_read_mode(site):
    async def go():
        pw, browser, drv = await session()
        try:
            await call(drv, "navigate", url=f"{site}/index.html")
            box = (await call(drv, "find", query="search the course")).split("[")[1].split("]")[0]
            await call(drv, "form_input", target={"type": "ref", "ref": box}, value="trusses")
            btn = (await call(drv, "find", query="search button")).split("[")[1].split("]")[0]
            await call(drv, "left_click", target={"type": "ref", "ref": btn})
            return await call(drv, "get_page_text")
        finally:
            await browser.close(); await pw.stop()
    assert "1 result" in run(go())


def test_passwords_are_never_typed_and_read_mode_never_submits(site):
    async def go():
        pw, browser, drv = await session("read")
        out = {}
        try:
            await call(drv, "navigate", url=f"{site}/form.html")
            tree = await call(drv, "read_page", filter="interactive")
            out["tree"] = tree
            pwd = [ln for ln in tree.splitlines() if "password" in ln][0].split("[")[1].split("]")[0]
            try:
                await call(drv, "form_input", target={"type": "ref", "ref": pwd}, value="hunter2")
            except ToolError as e:
                out["pwd"] = str(e.content if hasattr(e, "content") else e)
            send = [ln for ln in tree.splitlines() if "Send message" in ln][0].split("[")[1].split("]")[0]
            try:
                await call(drv, "left_click", target={"type": "ref", "ref": send})
            except ToolError as e:
                out["send"] = str(e.content if hasattr(e, "content") else e)
            out["url"] = drv.tabs[drv.active].url
            out["value"] = await drv.tabs[drv.active].evaluate("document.getElementById('p').value")
            return out
        finally:
            await browser.close(); await pw.stop()
    out = run(go())
    assert "(password: never type here)" in out["tree"]
    assert "password" in out["pwd"].lower() and out["value"] == ""
    assert "read mode" in out["send"].lower() and out["url"].endswith("form.html")


def test_act_mode_fills_the_form_but_leaves_the_send_for_him(site):
    async def go():
        pw, browser, drv = await session("act")
        try:
            await call(drv, "navigate", url=f"{site}/form.html")
            tree = await call(drv, "read_page", filter="interactive")
            msg = [ln for ln in tree.splitlines() if "Message" in ln][0].split("[")[1].split("]")[0]
            await call(drv, "form_input", target={"type": "ref", "ref": msg}, value="Hi prof")
            send = [ln for ln in tree.splitlines() if "Send message" in ln][0].split("[")[1].split("]")[0]
            refused = ""
            try:
                await call(drv, "left_click", target={"type": "ref", "ref": send})
            except ToolError as e:
                refused = str(e.content if hasattr(e, "content") else e)
            return refused, drv.left_for_him, drv.tabs[drv.active].url, \
                await drv.tabs[drv.active].evaluate("document.getElementById('m').value")
        finally:
            await browser.close(); await pw.stop()
    refused, left, url, value = run(go())
    assert "presses it himself" in refused and left and "Send message" in left[0]
    assert url.endswith("form.html") and value == "Hi prof"


def test_only_web_pages():
    for bad in ("file:///C:/Users/dewet/secrets.txt", "http://127.0.0.1:8770/api/keys", "http://localhost:8765",
                "http://192.168.1.4/router", "chrome://settings", "javascript:alert(1)"):
        with pytest.raises(ToolError):
            check_url(bad)
    assert check_url("canvas.usask.ca/courses") == "https://canvas.usask.ca/courses"
