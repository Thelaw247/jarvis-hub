"""Claude's browser tools (``browser_toolset_20260801``) on Playwright, in the Jarvis browser profile.

Anthropic supplies the tool definitions Claude is trained on and the SDK's pipeline (URL policy, confirm hook, result
rendering); this class only performs each member on a Playwright page. JARVIS_DESIGN_TOOLS.md §6.

Rules held here in code, whatever the page or the model says:
- http(s) only; no local network, no browser-internal pages (``url_policy``);
- never types into a password field (his passwords are his, C26);
- read mode: no click or key that would submit a form that changes something; act mode: forms may be filled, but a
  consequential press (submit, send, pay, delete, post…) is left for him: the worker says so and opens the page in
  the visible browser for him to check and press;
- javascript_exec and file_upload stay off (Anthropic's advice for signed-in sessions).
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import ipaddress
import re
from typing import Any, Literal
from urllib.parse import urlparse

from anthropic.tools import ToolError
from anthropic.tools.browser import (
    BetaAsyncAbstractBrowserToolset20260801,
    BetaBrowserNavigateResult,
    BetaBrowserState,
    BetaConfirmContext,
    BetaScreenshotResult,
    BetaURLContext,
)

from .snapshot import PAGE_TEXT_JS, SNAPSHOT_JS

Mode = Literal["read", "act"]
CONSEQUENTIAL = re.compile(
    r"\b(submit|send|post|publish|pay|buy|purchase|order|checkout|check out|delete|remove|confirm|sign up|register|"
    r"enrol|enroll|apply|save changes|accept|agree|unsubscribe|transfer|withdraw|drop|cancel (?:my|the|this))\b", re.I)
VIEWPORT = {"width": 1280, "height": 800}
KEYS = {"return": "Enter", "enter": "Enter", "backspace": "Backspace", "esc": "Escape", "escape": "Escape",
        "tab": "Tab", "space": "Space", "delete": "Delete", "del": "Delete", "home": "Home", "end": "End",
        "page_down": "PageDown", "pagedown": "PageDown", "page_up": "PageUp", "pageup": "PageUp",
        "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
        "ctrl": "Control", "control": "Control", "alt": "Alt", "shift": "Shift", "cmd": "Meta", "super": "Meta",
        "meta": "Meta", "win": "Meta"}
BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


def _key(chord: str) -> str:
    parts = [KEYS.get(p.lower(), p if len(p) == 1 else p[:1].upper() + p[1:]) for p in chord.split("+")]
    return "+".join(parts)


def _mods(mods: str | None) -> list[str]:
    return [KEYS.get(m.strip().lower(), m.strip()) for m in (mods or "").split("+") if m.strip()]


async def _settle(page: Any) -> None:
    """After a click or key: give a navigation it started a moment to begin, then wait for the new page's DOM."""
    await asyncio.sleep(0.15)
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("domcontentloaded", timeout=8_000)


async def _eval(page: Any, js: str, arg: Any = None) -> Any:
    """Evaluate in the page; if a navigation replaced the document meanwhile, wait for it and try once more."""
    try:
        return await page.evaluate(js, arg)
    except Exception as e:
        if "context was destroyed" not in str(e) and "navigat" not in str(e):
            raise
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=8_000)
        return await page.evaluate(js, arg)


def check_url(url: str) -> str:
    """The URL policy: returns the URL to load or raises ToolError. Scheme-less → https; http(s) only; no local or
    private network addresses; nothing browser-internal."""
    raw = url.strip()
    if raw.lower() in ("back", "forward", "reload"):
        return raw.lower()
    if "://" not in raw and not raw.lower().startswith(("about:", "javascript:", "data:", "file:")):
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ToolError(f"Only http and https pages can be opened, not {p.scheme or 'that'}.")
    host = p.hostname.lower()
    if host in BLOCKED_HOSTS or host.endswith(".local"):
        raise ToolError("Local network addresses are off limits.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ToolError("Local network addresses are off limits.")
    return raw


class JarvisBrowser(BetaAsyncAbstractBrowserToolset20260801):
    """One browsing session: its own tabs in the shared Jarvis browser context."""

    def __init__(self, context: Any, *, mode: Mode = "read", start_url: str | None = None,
                 url_check: Any = None) -> None:
        super().__init__(
            configs={"javascript_exec": {"enabled": False}, "file_upload": {"enabled": False},
                     "read_console": {"enabled": False}, "read_network": {"enabled": False},
                     "hold_key": {"enabled": False}, "left_mouse_down": {"enabled": False},
                     "left_mouse_up": {"enabled": False}},
            confirm=self._confirm, url_policy=self._url_policy)
        self.context = context
        self.url_check = url_check or check_url  # tests serve pages from 127.0.0.1; Jarvis never may
        self.mode = mode
        self.start_url = start_url
        self.tabs: dict[str, Any] = {}
        self.active: str | None = None
        self._n = 0
        self._opened: list[str] = []
        self.left_for_him: list[str] = []   # consequential steps it stopped before (act mode): he presses them
        self.visited: list[str] = []
        context.on("page", self._on_page)

    # ------------------------------------------------------------------ tabs
    def _on_page(self, page: Any) -> None:
        if any(p is page for p in self.tabs.values()):
            return
        tid = self._add(page)
        self._opened.append(tid)

    def _add(self, page: Any) -> str:
        self._n += 1
        tid = f"tab-{self._n}"
        self.tabs[tid] = page
        self.active = tid
        page.on("close", lambda *_: self._closed(tid))
        return tid

    def _closed(self, tid: str) -> None:
        self.tabs.pop(tid, None)
        if self.active == tid:
            self.active = next(reversed(self.tabs), None) if self.tabs else None

    async def _page(self, tab_id: str | None) -> Any:
        if tab_id:
            page = self.tabs.get(tab_id)
            if page is None:
                raise ToolError(f"There's no tab {tab_id}. Use list_tabs.")
            return page
        if self.active is None or self.active not in self.tabs:
            page = await self.context.new_page()
            await page.set_viewport_size(VIEWPORT)
            if page not in self.tabs.values():
                self._add(page)
        return self.tabs[self.active]

    async def _browser_state(self, context: Any) -> BetaBrowserState:
        tabs = []
        for tid, page in list(self.tabs.items()):
            try:
                title = await asyncio.wait_for(page.title(), 2)
            except Exception:
                title = ""
            tabs.append({"tab_id": tid, "title": title or "", "url": page.url or "", "active": tid == self.active})
        changes = [{"type": "tab_opened", "tab_id": t} for t in self._opened if t in self.tabs]
        self._opened = []
        return BetaBrowserState(tabs=tabs, state_changes=changes)

    async def close(self) -> None:
        for page in list(self.tabs.values()):
            try:
                await page.close()
            except Exception:
                pass
        self.tabs.clear()
        await super().close()

    # ------------------------------------------------------------------ policy and confirm
    def _url_policy(self, context: BetaURLContext, url: str) -> None:
        self.url_check(url)

    async def _target_info(self, tab_id: str | None, target: Any) -> dict:
        """What a click or form fill would hit: tag, type, text, and its form's method (for the read/act rules)."""
        page = await self._page(tab_id)
        js = """(el) => { const f = el.closest('form'); const b = el.closest('button, a, [role=button], input') || el;
          return { tag: b.tagName.toLowerCase(), type: (b.getAttribute('type') || '').toLowerCase(),
                   text: ((b.innerText || b.value || b.getAttribute('aria-label') || '') + '').slice(0, 120),
                   method: f ? (f.getAttribute('method') || 'get').toLowerCase() : null,
                   role: f ? (f.getAttribute('role') || '') : '', password: el.type === 'password' }; }"""
        try:
            if getattr(target, "type", None) == "ref":
                el = page.locator(f'[data-jv-ref="{target.ref}"]').first
                return await el.evaluate(js)
            if getattr(target, "type", None) == "coordinate":
                return await page.evaluate(
                    "([x, y, js]) => { const el = document.elementFromPoint(x, y); return el ? (eval(js))(el) : {}; }",
                    [target.x, target.y, js])
        except Exception:
            return {}
        return {}

    def _consequential(self, info: dict) -> bool:
        if not info:
            return False
        submits = info.get("type") == "submit" or (info.get("tag") == "button" and info.get("type") in ("", "submit")
                                                    and info.get("method") is not None)
        posts = info.get("method") == "post" and info.get("role") != "search"
        return bool(CONSEQUENTIAL.search(info.get("text") or "")) or (submits and posts)

    async def _confirm(self, ctx: BetaConfirmContext) -> bool:
        member, inp = ctx.member, ctx.input
        if member in ("type", "form_input", "key"):
            info = await self._target_info(ctx.tab_id, getattr(inp, "target", None)) if member == "form_input" else \
                await self._focused_info(ctx.tab_id)
            if info.get("password"):
                raise ToolError("That's a password field. Never type passwords: ask De Wet to sign in himself "
                                "(sign_in).")
            if member == "key" and "enter" in str(getattr(inp, "text", "")).lower() and info.get("method") == "post" \
                    and info.get("role") != "search":
                return self._leave("press Enter to send a form", ctx.tab_url)
            return True
        if member in ("left_click", "double_click", "triple_click"):
            info = await self._target_info(ctx.tab_id, getattr(inp, "target", None))
            if self._consequential(info):
                return self._leave(f"press “{(info.get('text') or 'the button').strip()[:60]}”", ctx.tab_url)
        return True

    async def _focused_info(self, tab_id: str | None) -> dict:
        page = await self._page(tab_id)
        try:
            return await page.evaluate("""() => { const el = document.activeElement; if (!el) return {};
              const f = el.closest('form'); return { password: el.type === 'password',
              method: f ? (f.getAttribute('method') || 'get').toLowerCase() : null,
              role: f ? (f.getAttribute('role') || '') : '' }; }""")
        except Exception:
            return {}

    def _leave(self, what: str, url: str | None) -> bool:
        """A step that would change something on a site: never done by Jarvis here. Read mode refuses it; act mode
        leaves it ready for him (the worker opens the page in the visible browser)."""
        self.left_for_him.append(f"{what} on {url or 'the page'}")
        raise ToolError(
            "Read mode: that would submit or change something. Don't do it; finish with what you found."
             if self.mode == "read" else
             "Stop here: this step changes something on the site, so De Wet presses it himself. Fill in what you "
             "can, then finish and say exactly what's ready for him to check and press.")

    # ------------------------------------------------------------------ members
    async def navigate(self, context: Any, input: Any) -> BetaBrowserNavigateResult:
        page = await self._page(input.tab_id)
        url = self.url_check(input.url)
        if url == "back":
            resp = await page.go_back(wait_until="domcontentloaded", timeout=20_000)
        elif url == "forward":
            resp = await page.go_forward(wait_until="domcontentloaded", timeout=20_000)
        elif url == "reload":
            resp = await page.reload(wait_until="domcontentloaded", timeout=20_000)
        else:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=3_000)
        except Exception:
            pass
        self.visited.append(page.url)
        return BetaBrowserNavigateResult(url=page.url, status=resp.status if resp else None, title=await page.title())

    async def screenshot(self, context: Any, input: Any) -> BetaScreenshotResult:
        page = await self._page(input.tab_id)
        data = await page.screenshot(type="jpeg", quality=70)
        return BetaScreenshotResult(data=base64.b64encode(data).decode(), media_type="image/jpeg")

    async def zoom(self, context: Any, input: Any) -> BetaScreenshotResult:
        page = await self._page(input.tab_id)
        x0, y0, x1, y1 = (int(v) for v in input.region)
        clip = {"x": max(0, x0), "y": max(0, y0), "width": max(1, x1 - x0), "height": max(1, y1 - y0)}
        data = await page.screenshot(type="jpeg", quality=80, clip=clip)
        return BetaScreenshotResult(data=base64.b64encode(data).decode(), media_type="image/jpeg")

    async def _point(self, page: Any, target: Any) -> tuple[float, float]:
        if target.type == "coordinate":
            return float(target.x), float(target.y)
        el = page.locator(f'[data-jv-ref="{target.ref}"]').first
        if await el.count() == 0:
            raise ToolError(f"{target.ref} isn't on the page any more (it went stale). Read the page again.")
        await el.scroll_into_view_if_needed(timeout=5_000)
        box = await el.bounding_box()
        if box is None:
            raise ToolError(f"{target.ref} isn't visible. Scroll or read the page again.")
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    async def _click(self, input: Any, *, button: str = "left", count: int = 1) -> None:
        page = await self._page(input.tab_id)
        x, y = await self._point(page, input.target)
        mods = _mods(getattr(input, "modifiers", None))
        for m in mods:
            await page.keyboard.down(m)
        try:
            await page.mouse.click(x, y, button=button, click_count=count)
        finally:
            for m in reversed(mods):
                await page.keyboard.up(m)
        await _settle(page)

    async def left_click(self, context: Any, input: Any) -> None:
        await self._click(input)

    async def right_click(self, context: Any, input: Any) -> None:
        await self._click(input, button="right")

    async def middle_click(self, context: Any, input: Any) -> None:
        await self._click(input, button="middle")

    async def double_click(self, context: Any, input: Any) -> None:
        await self._click(input, count=2)

    async def triple_click(self, context: Any, input: Any) -> None:
        await self._click(input, count=3)

    async def hover(self, context: Any, input: Any) -> None:
        page = await self._page(input.tab_id)
        x, y = await self._point(page, input.target)
        await page.mouse.move(x, y)

    async def mouse_move(self, context: Any, input: Any) -> None:
        await self.hover(context, input)

    async def scroll(self, context: Any, input: Any) -> None:
        page = await self._page(input.tab_id)
        await page.mouse.move(float(input.target.x), float(input.target.y))
        n = max(1, min(10, input.scroll_amount or 3)) * 100
        dx, dy = {"up": (0, -n), "down": (0, n), "left": (-n, 0), "right": (n, 0)}[input.scroll_direction]
        await page.mouse.wheel(dx, dy)
        await asyncio.sleep(0.2)

    async def scroll_to(self, context: Any, input: Any) -> None:
        page = await self._page(input.tab_id)
        await self._point(page, input.target)  # scrolls a ref into view

    async def type(self, context: Any, input: Any) -> None:
        page = await self._page(input.tab_id)
        await page.keyboard.type(input.text, delay=5)

    async def key(self, context: Any, input: Any) -> None:
        page = await self._page(input.tab_id)
        for _ in range(max(1, min(20, input.repeat or 1))):
            for chord in input.text.split():
                await page.keyboard.press(_key(chord))
        await _settle(page)

    async def wait(self, context: Any, input: Any) -> None:
        await asyncio.sleep(max(0.0, min(10.0, float(input.duration))))

    async def form_input(self, context: Any, input: Any) -> str:
        page = await self._page(input.tab_id)
        el = page.locator(f'[data-jv-ref="{input.target.ref}"]').first
        if await el.count() == 0:
            raise ToolError(f"{input.target.ref} went stale. Read the page again.")
        tag = await el.evaluate("(e) => e.tagName.toLowerCase() + ':' + (e.type || '')")
        value = input.value
        if tag.startswith("select"):
            try:
                await el.select_option(value=str(value), timeout=5_000)
            except Exception:
                await el.select_option(label=str(value), timeout=5_000)
        elif tag.endswith(("checkbox", "radio")):
            await el.set_checked(bool(value), timeout=5_000)
        else:
            await el.fill(str(value), timeout=5_000)
        return f"Set to {value!r}."

    async def read_page(self, context: Any, input: Any) -> str:
        page = await self._page(input.tab_id)
        out = await _eval(page, SNAPSHOT_JS, {"rootRef": input.ref, "depth": input.depth or 15,
                                              "filter": input.filter, "query": None})
        if out.get("error"):
            raise ToolError(out["error"])
        return out["text"]

    async def find(self, context: Any, input: Any) -> str:
        page = await self._page(input.tab_id)
        out = await _eval(page, SNAPSHOT_JS, {"rootRef": None, "depth": 40, "filter": "all", "query": input.query})
        return out.get("text") or "No matching elements."

    async def get_page_text(self, context: Any, input: Any) -> str:
        page = await self._page(input.tab_id)
        return await _eval(page, PAGE_TEXT_JS)

    async def new_tab(self, context: Any, input: Any) -> dict:
        page = await self.context.new_page()
        await page.set_viewport_size(VIEWPORT)
        tid = next((t for t, p in self.tabs.items() if p is page), None) or self._add(page)
        self.active = tid
        if tid in self._opened:
            self._opened.remove(tid)
        return {"tab_id": tid, "title": "", "url": page.url or "about:blank", "active": True}

    async def list_tabs(self, context: Any, input: Any) -> list[dict]:
        return (await self._browser_state(context)).tabs

    async def switch_tab(self, context: Any, input: Any) -> dict:
        if input.tab_id not in self.tabs:
            raise ToolError(f"There's no tab {input.tab_id}.")
        self.active = input.tab_id
        page = self.tabs[input.tab_id]
        await page.bring_to_front()
        return {"tab_id": input.tab_id, "title": await page.title(), "url": page.url, "active": True}

    async def close_tab(self, context: Any, input: Any) -> None:
        page = self.tabs.get(input.tab_id)
        if page is None:
            raise ToolError(f"There's no tab {input.tab_id}.")
        await page.close()
