"""v0.22.0: his windows side by side on the laptop screen, and never moved before he has said he is ready."""
import asyncio
from types import SimpleNamespace

import pytest

from jarvis.reach.desktop import Desktop, Rect, Win, match, pick_screen, tile
from jarvis.tools.arrange_windows import handler
from jarvis.tools.base import ToolError

LAPTOP, MONITOR = Rect(0, 0, 1920, 1152), Rect(1920, 0, 2560, 1392)


class FakeDesk:
    ok = True

    def __init__(self, windows, screens=(LAPTOP, MONITOR)):
        self._w, self._s, self.moved = list(windows), list(screens), []

    def screens(self): return self._s
    def windows(self): return self._w

    def place(self, win, rect):
        self.moved.append((win.title, rect))
        return "Admin" not in win.title


WINDOWS = [Win(1, "Jarvis Hub", 1), Win(2, "Assignment 01 (WebAssign) - PHYS 152 - Canvas - Google Chrome", 0),
           Win(3, "Claude", 0, minimized=True), Win(4, "Practice 6.pdf - Adobe Acrobat", 0), Win(5, "notes about claude and canvas.txt - Notepad", 0)]


def ask(desk, here=True, **args):
    return asyncio.run(handler.run(args, SimpleNamespace(desktop=desk, here=here)))


def test_the_layouts_fill_the_screen_with_no_gaps_and_no_overlap():
    assert tile(1, LAPTOP) == [LAPTOP]
    assert tile(2, LAPTOP) == [Rect(0, 0, 960, 1152), Rect(960, 0, 960, 1152)]
    assert tile(3, MONITOR) == [Rect(1920, 0, 1280, 1392), Rect(3200, 0, 1280, 696), Rect(3200, 696, 1280, 696)]
    for n in (2, 3, 4):
        for area in (LAPTOP, Rect(0, 0, 1367, 729)):           # an odd-sized screen loses no pixel
            spots = tile(n, area)
            assert sum(r.w * r.h for r in spots) == area.w * area.h
            assert all(area.x <= r.x and r.x + r.w <= area.x + area.w and area.y <= r.y and r.y + r.h <= area.y + area.h for r in spots)
    assert len(tile(9, LAPTOP)) == 4


def test_a_word_or_two_finds_the_window_he_means():
    found, missing = match(["canvas", "claude", "spotify"], WINDOWS)
    assert [w.handle for w in found] == [2, 3] and missing == ["spotify"]          # the Claude app, not the note that mentions it
    assert match(["practice 6"], WINDOWS)[0][0].handle == 4
    assert [w.handle for w in match(["claude", "claude"], WINDOWS)[0]] == [3, 5]    # one window each, never the same twice
    assert pick_screen([LAPTOP, MONITOR], WINDOWS, "laptop") == 0 and pick_screen([LAPTOP, MONITOR], WINDOWS, "monitor") == 1
    assert pick_screen([LAPTOP], WINDOWS, "laptop") == 0 and pick_screen([LAPTOP, MONITOR], WINDOWS[1:], "laptop") == 0


def test_nothing_moves_until_he_says_he_is_ready():
    desk = FakeDesk(WINDOWS)
    first = ask(desk, windows=["canvas", "claude"])
    assert desk.moved == [] and first.is_error is False
    assert first.content.startswith("Nothing has moved yet. The plan for his laptop screen: Google Chrome on the left half, Claude on the right half.")
    assert "Ask him in a few words if he is ready" in first.content
    done = ask(desk, windows=["canvas", "claude"], confirmed=True)
    assert desk.moved == [(WINDOWS[1].title, Rect(0, 0, 960, 1152)), ("Claude", Rect(960, 0, 960, 1152))]
    assert done.content == "Done on his laptop screen: Google Chrome on the left half, Claude on the right half."
    desk.moved.clear()
    ask(desk, windows=["claude"], screen="monitor", confirmed=True)
    assert desk.moved == [("Claude", MONITOR)]                                      # the hub's own screen, when he asks for it


def test_it_says_what_is_open_when_it_cannot_find_one_and_refuses_from_the_other_laptop():
    desk = FakeDesk(WINDOWS)
    with pytest.raises(ToolError, match=r"No open window matches 'spotify'. Open right now: Google Chrome; Claude; Practice 6.pdf - Adobe Acrobat"):
        ask(desk, windows=["canvas", "spotify"], confirmed=True)
    assert desk.moved == []                                                         # all or nothing: half a layout is worse than none
    with pytest.raises(ToolError, match="can't reach the laptop he is at"):   # no voice program to ask (tests/core/test_hands.py)
        ask(desk, here=False, windows=["canvas"], confirmed=True)
    front = ask(desk, windows=[])                                                   # v0.27.1: no names means the windows in front
    assert front.content.startswith("Nothing has moved yet") and desk.moved == []
    assert len(ask(desk, count=3, confirmed=True).content.split(" on ")) >= 3 and len(desk.moved) == 3
    desk.moved.clear()
    with pytest.raises(ToolError, match="Windows laptop only"):
        ask(FakeDesk(WINDOWS, screens=()), windows=["canvas"])
    stuck = ask(FakeDesk([Win(7, "Admin console", 0), Win(8, "Claude", 0)], screens=(LAPTOP,)), windows=["admin", "claude"], confirmed=True)
    assert "Windows would not let me move: Admin console" in stuck.content and stuck.is_error is False


def test_off_windows_it_reports_nothing_and_moves_nothing_and_the_tool_is_simply_off():
    desk = Desktop()
    if not desk.ok:
        assert desk.screens() == [] and desk.windows() == [] and desk.place(Win(1, "x", 0), LAPTOP) is False
    from jarvis.tools import Registry

    reg = Registry()
    ctx = SimpleNamespace(has=lambda need: False)
    assert reg.status(reg.specs["arrange_windows"], ctx) == "off"
    from jarvis.tools.voice import ROUTING

    assert "Ready for me to move them?" in ROUTING
