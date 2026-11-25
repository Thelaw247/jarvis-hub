"""v0.24.1: he talks from one laptop while Jarvis runs on the other. The voice program on the laptop he is at opens
things and moves windows there (jarvis.reach.hands), and only a few fixed things: never a program, never outside Class
Content, and windows only after his yes."""
import asyncio
from types import SimpleNamespace

import pytest

from jarvis.reach import hands
from jarvis.reach.desktop import Rect, Win
from jarvis.tools.arrange_windows import handler
from jarvis.tools.base import ToolError


class Desk:
    ok = True

    def __init__(self): self.moved = []
    def screens(self): return [Rect(0, 0, 1920, 1152)]
    def windows(self): return [Win(2, "Assignment 01 - PHYS 152 - Canvas - Google Chrome", 0), Win(3, "Claude", 0, minimized=True)]

    def place(self, win, rect):
        self.moved.append((win.handle, rect))
        return True


def test_it_looks_at_and_moves_windows_only_in_the_shapes_it_knows():
    desk = Desk()
    seen = hands.run("windows", {}, desktop=desk)
    assert seen["ok"] and seen["screens"] == [[0, 0, 1920, 1152]] and [w["title"] for w in seen["windows"]][1] == "Claude"
    done = hands.run("place", {"moves": [{"handle": 2, "to": [0, 0, 960, 1152]}, {"handle": "x"}, {"handle": 3, "to": [960, 0, 960]}]}, desktop=desk)
    assert done == {"ok": True, "moved": [2]} and desk.moved == [(2, Rect(0, 0, 960, 1152))]
    assert hands.run("windows", {}, desktop=SimpleNamespace(ok=False)) == {"ok": False, "why": "not_windows"}
    assert hands.run("type", {"text": "hello"}) == {"ok": False, "why": "unknown"}  # nothing but the three kinds


def test_it_opens_web_pages_and_class_documents_and_nothing_else(tmp_path):
    root = tmp_path / "Class Content"
    (root / "XX 101 - Things" / "Assignments & Labs").mkdir(parents=True)
    (root / "XX 101 - Things" / "Assignments & Labs" / "Practice 6.pdf").write_text("x")
    (root / "XX 101 - Things" / "run.bat").write_text("x")
    (tmp_path / "secret.pdf").write_text("x")
    opened = []

    def go(args, **kw):
        return hands.run("open", args, opener=opened.append, root=root, **kw)

    assert go({"url": "https://canvas.example.edu/courses/1"}) == {"ok": True}
    assert go({"file": "XX 101 - Things/Assignments & Labs/Practice 6.pdf"}) == {"ok": True}
    assert go({"file": "XX 101 - Things"}) == {"ok": True}  # a folder inside Class Content
    assert len(opened) == 3 and opened[1].endswith("Practice 6.pdf")
    for bad, why in [({"url": "file:///C:/Windows/System32/cmd.exe"}, "not_a_web_address"), ({"url": "calc.exe"}, "not_a_web_address"),
                     ({"url": "https://x.example/ a"}, "not_a_web_address"), ({"file": "XX 101 - Things/run.bat"}, "not_a_document"),
                     ({"file": "../secret.pdf"}, "not_in_class_content"), ({"file": "nope.pdf"}, "not_in_class_content"), ({}, "not_in_class_content")]:
        assert go(bad) == {"ok": False, "why": why}
    assert len(opened) == 3
    assert go({"app": "claude"}, running=lambda: True) == {"ok": True, "was_open": True} and len(opened) == 3
    assert go({"app": "claude"}, running=lambda: False) == {"ok": True, "was_open": False} and opened[-1] == "claude://"


def far_ctx(desk, log, fail=None):
    async def ask(kind, args):
        log.append((kind, args))
        if fail:
            raise fail
        return hands.run(kind, args, desktop=desk)
    return SimpleNamespace(here=False, hands=ask, desktop=None)


def test_arranging_from_the_other_laptop_plans_first_and_moves_after_his_yes():
    desk, log = Desk(), []
    ctx = far_ctx(desk, log)
    plan = asyncio.run(handler.run({"windows": ["canvas", "claude"]}, ctx))
    assert "Nothing has moved yet" in plan.content and desk.moved == [] and [k for k, _ in log] == ["windows"]
    done = asyncio.run(handler.run({"windows": ["canvas", "claude"], "confirmed": True}, ctx))
    assert done.content.startswith("Done on his laptop screen") and [h for h, _ in desk.moved] == [2, 3]
    assert desk.moved[0][1] == Rect(0, 0, 960, 1152) and log[-1][0] == "place"


def test_it_says_plainly_when_the_other_laptop_cannot_be_reached():
    with pytest.raises(ToolError, match="close Jarvis Hub on that laptop and open it again"):
        asyncio.run(handler.run({"windows": ["canvas"]}, far_ctx(Desk(), [], fail=TimeoutError())))
    with pytest.raises(ToolError, match="can't reach the laptop he is at"):
        asyncio.run(handler.run({"windows": ["canvas"]}, SimpleNamespace(here=False, hands=None, desktop=None)))


def test_the_core_asks_over_the_voice_connection_and_gives_up_politely():
    from jarvis.voice.service import VoiceService

    sent = []

    class Ws:
        async def send_text(self, text): sent.append(text)

    async def scene():
        service = VoiceService.__new__(VoiceService)
        service.client, service._asks = None, {}
        with pytest.raises(RuntimeError):
            await service.ask_client("windows")
        service.client = Ws()
        asking = asyncio.ensure_future(service.ask_client("open", {"url": "https://a.example"}))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        (ask_id, waiting), = service._asks.items()
        waiting.set_result({"type": "done", "id": ask_id, "ok": True})
        assert (await asking)["ok"] is True and service._asks == {}
        with pytest.raises(TimeoutError):
            await service.ask_client("windows", timeout_s=0.01)   # an older voice program never answers
        assert service._asks == {}

    asyncio.run(scene())
    assert '"type": "do"' in sent[0] and '"kind": "open"' in sent[0]
