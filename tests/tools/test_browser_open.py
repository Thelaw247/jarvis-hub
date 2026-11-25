"""The sign-in window (v0.12.1): the profile opens as a plain browser with no automation attached, started off the
core's event loop, and Jarvis waits for it to close before using the profile again."""
from __future__ import annotations

import asyncio
import subprocess

import pytest

from jarvis.browser import service as svc_mod
from jarvis.browser.service import BrowserBusy, BrowserService, pick_channel
from jarvis.tools import Registry, ToolContext


class FakeProc:
    def __init__(self, args, **kw):
        self.args, self.alive = args, True
        FakeProc.made.append(self)

    def poll(self):
        return None if self.alive else 0


FakeProc.made = []


def test_sign_in_opens_a_plain_window_and_jarvis_waits_for_it(tmp_path, monkeypatch):
    FakeProc.made = []
    monkeypatch.setattr(svc_mod, "browser_exe", lambda ch: r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    svc = BrowserService(tmp_path, channel="chrome")
    assert svc.profile.name == "profile-chrome"

    async def main():
        out = await Registry().run("sign_in", {"site": "google"}, ToolContext(root=tmp_path, browser=svc))
        assert svc.his_window_open()                         # starting (or started): Jarvis keeps off the profile
        await svc._launching
        await svc.open_visible("canvas.usask.ca")          # a second page: same window, the first stays tracked
        await svc._launching
        with pytest.raises(BrowserBusy):
            await svc.context()
        FakeProc.made[0].alive = False                       # he closed the window
        return out

    out = asyncio.run(main())
    assert not out.is_error and "sign-in" in out.content.lower()
    first = FakeProc.made[0].args
    assert first[0].endswith("chrome.exe") and f"--user-data-dir={svc.profile}" in first
    # v0.14.0: a window of its own with only the page (Chrome's app window), not a tab in a browser window
    assert "--app=https://accounts.google.com/" in first and not any("remote-debugging" in a for a in first)
    assert FakeProc.made[1].args[-1] == "https://canvas.usask.ca"       # other pages still open as normal tabs
    assert svc._his_window is FakeProc.made[0] and not svc.his_window_open()


def test_busy_reaches_the_voice_brain_as_words(tmp_path, monkeypatch):
    svc = BrowserService(tmp_path, channel="chrome")
    svc._his_window = type("P", (), {"poll": lambda self: None})()

    async def find(args, ctx):
        await ctx.browser.context()

    reg = Registry()
    reg.handlers["canvas_find"] = find
    out = asyncio.run(reg.run("canvas_find", {"query": "lab"}, ToolContext(root=tmp_path, browser=svc, canvas=object())))
    assert out.is_error and "closes that window" in out.content


def test_the_browser_choice(monkeypatch):
    monkeypatch.setenv("JARVIS_BROWSER", "msedge")
    assert pick_channel() == "msedge"
    monkeypatch.setenv("JARVIS_BROWSER", "chromium")
    assert pick_channel() is None


def test_when_he_closes_the_sign_in_window_jarvis_carries_on_with_what_he_asked(tmp_path, monkeypatch):
    """v0.14.0. On 2026-11-18 he signed in, nothing noticed, and the question was never answered."""
    from jarvis.tools.sign_in import handler

    FakeProc.made = []
    monkeypatch.setattr(svc_mod, "browser_exe", lambda ch: "chrome.exe")
    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    reg = Registry()
    monkeypatch.setitem(reg.handlers["sign_in"].__globals__, "QUICK_CLOSE_S", 0.05)
    assert handler.QUICK_CLOSE_S >= 2
    svc = BrowserService(tmp_path, channel="chrome")
    notes = []

    async def resume(note):
        notes.append(note)
        return True

    real_sleep = asyncio.sleep

    async def fast(seconds):
        await real_sleep(min(seconds, 0.02))

    async def main():
        monkeypatch.setattr(asyncio, "sleep", fast)
        out = await reg.run("sign_in", {"site": "canvas"}, ToolContext(root=tmp_path, browser=svc, resume=resume))
        await svc._launching
        await real_sleep(0.15)
        assert notes == []                                   # still signing in: nothing said
        FakeProc.made[0].alive = False                       # he closes the window
        for _ in range(100):
            if notes:
                break
            await real_sleep(0.02)
        return out

    out = asyncio.run(main())
    assert "carry on" in out.content                         # Claude is told it will be picked back up
    assert len(notes) == 1 and "closed the sign-in window for canvas" in notes[0]
    assert "not something De Wet said" in notes[0]


def test_a_window_that_never_really_opened_does_not_trigger_a_follow_up(tmp_path, monkeypatch):
    from jarvis.tools.sign_in import handler

    FakeProc.made = []
    monkeypatch.setattr(svc_mod, "browser_exe", lambda ch: "chrome.exe")
    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    svc = BrowserService(tmp_path, channel="chrome")
    notes = []

    async def resume(note):
        notes.append(note)
        return True

    async def main():
        await Registry().run("sign_in", {"site": "canvas"}, ToolContext(root=tmp_path, browser=svc, resume=resume))
        await svc._launching
        FakeProc.made[0].alive = False                       # gone at once: it handed its page to another window
        await asyncio.sleep(1.2)

    asyncio.run(main())
    assert notes == [] and handler.QUICK_CLOSE_S >= 2
