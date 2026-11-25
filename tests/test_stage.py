"""The Stage (N9, HUD v2 §6.5): the second window's decision logic in app.py, its JS API with stand-in windows
(pywebview isn't installed here; the real window only runs on Windows), and the `stage` setting's round trip."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app
from jarvis_hub.schema import contract, is_valid

UP = {"windows": [{"id": "w-pps7"}], "now_card": {"moment": "between"}}
EMPTY = {"windows": [], "now_card": {"moment": "between"}}
ON = {"stage": "window", "game_mode": "auto"}


def test_the_stage_shows_while_windows_are_up():
    assert app.should_show_stage(UP, ON, "B") is True
    assert app.should_show_stage(UP, ON, "A") is True
    assert app.should_show_stage(UP, {}, "B") is False  # left out = one window (the default since v0.17.0)


def test_one_window_is_the_default_and_the_holder_shows_only_what_he_pulled_out():
    """2026-11-21: "when I open the hub it pulls up two hubs both with the Jarvis orb"."""
    hub = {"game_mode": "auto"}                                    # nothing saved: one window
    for device in ("A", "B"):
        assert app.should_show_stage(UP, hub, device) is False          # windows are up, but on the hub itself
        assert app.should_show_stage(UP, hub, device, showing=True) is False
        assert app.should_show_stage({"windows": []}, hub, device, showing=True) is False   # no standby orb window
        assert app.should_show_stage({**UP, "popped": 1}, hub, device) is True          # he pulled one out
        assert app.should_show_stage({**UP, "popped": 0}, {**hub, "stage": "hub"}, device, showing=True) is False
    assert app.should_show_stage({**UP, "popped": 2}, {**hub, "game_mode": "on"}, "B") is False   # never over a game
    api, hub_win, holder = app.StageApi("A"), FakeWindow(), FakeWindow()
    api._attach(hub_win, holder)
    assert api.sync_stage({"state": UP, "settings": hub}) is False and holder.calls == []
    assert api.show_stage() is False                                # nothing out: nothing to bring forward
    assert api.sync_stage({"state": {**UP, "popped": 1}, "settings": hub}) is True
    assert holder.calls[:1] == [("show",)] and holder.on_top is False   # shown, brought to the front, not kept on top
    assert api.sync_stage({"state": {**UP, "popped": 0}, "settings": hub}) is False and holder.calls[-1] == ("hide",)
    assert api._holder_closed() is True and "popped.clear()" in hub_win.calls[-1][1]   # closing it sends them back


def test_the_second_window_is_an_ordinary_one_for_one_window_and_borderless_for_the_stage():
    made = []

    class Webview:
        screens = [type("S", (), {"x": 0, "y": 0, "width": 1920, "height": 1080})()]

        @staticmethod
        def create_window(**options):
            made.append(options)
            return object()

    app.create_stage(Webview, "http://127.0.0.1:9", app.StageApi("A"), None, holder=True)
    app.create_stage(Webview, "http://127.0.0.1:9", app.StageApi("B"), None)
    holder, stage = made
    assert holder["frameless"] is False and holder["hidden"] is True and holder["title"] == "Jarvis Windows"
    assert (holder["width"], holder["height"]) == app.HOLDER_SIZE and "x" not in holder and "screen" not in holder
    assert stage["frameless"] is True and stage["width"] == 1920 and stage["title"].endswith("Stage")
    assert holder["url"] == stage["url"]                             # the same page: it draws what it is given


def test_where_jarvis_shows_things_is_read_once_at_start(monkeypatch):
    import io
    import urllib.request

    def reply(settings):
        return lambda url, timeout=0: io.BytesIO(json.dumps({"settings": settings}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", reply({"stage": "window"}))
    assert app.saved_stage("http://127.0.0.1:9") == "window"
    monkeypatch.setattr(urllib.request, "urlopen", reply({"theme": "night"}))
    assert app.saved_stage("http://127.0.0.1:9") == "hub"            # nothing saved: one window

    def down(url, timeout=0):
        raise OSError("not answering")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    assert app.saved_stage("http://127.0.0.1:9") == "hub"            # the core is off: still one window


def test_never_with_on_the_hub_or_in_game_mode():
    assert app.should_show_stage(UP, {**ON, "stage": "hub"}, "B", showing=True) is False
    assert app.should_show_stage(UP, {**ON, "game_mode": "on"}, "B") is False
    assert app.should_show_stage({**UP, "now_card": {"moment": "game"}}, ON, "A") is False  # Auto, a game running
    assert app.should_show_stage({**UP, "now_card": {"moment": "game"}}, {**ON, "game_mode": "off"}, "B") is False
    assert app.should_show_stage(UP, {**ON, "game_mode": "off"}, "A") is True


def test_empty_laptop_b_stays_on_standby_and_laptop_a_hides():
    assert app.should_show_stage(EMPTY, ON, "B", showing=True) is True   # fades back to standby
    assert app.should_show_stage(EMPTY, ON, "B", showing=False) is False  # not shown until something is pushed
    assert app.should_show_stage(EMPTY, ON, "A", showing=True) is False  # Laptop A hides it
    assert app.should_show_stage(EMPTY, ON, "a", showing=True) is False
    assert app.should_show_stage(None, None, "B") is False  # nothing reported yet


def test_the_stage_page_url():
    assert app.page_url("http://127.0.0.1:1", "stage") == "http://127.0.0.1:1/?window=stage#/stage"
    assert app.page_url("https://hub.example.ts.net/", "stage").startswith("https://hub.example.ts.net/?window=stage")


def test_the_stage_fills_the_chosen_or_the_primary_monitor():
    left = SimpleNamespace(x=-1920, y=0, width=1920, height=1080)
    primary = SimpleNamespace(x=0, y=0, width=2560, height=1440)
    assert app.stage_screen([left, primary]) is primary
    assert app.stage_screen([left, primary], 0) is left
    assert app.stage_screen([left, primary], 7) is primary  # no such monitor: the primary one
    assert app.stage_screen([SimpleNamespace(x=5, y=5, width=1, height=1)]).x == 5
    assert app.stage_screen([]) is None


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.on_top = False

    def __getattr__(self, name):  # show, hide, restore, run_js: record them
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a: self.calls.append((name, *a))


def test_the_api_shows_and_hides_on_change_only():
    api = app.StageApi("A")
    hub, stage = FakeWindow(), FakeWindow()
    api._attach(hub, stage)
    report = {"state": UP, "settings": ON}
    assert api.sync_stage(report) is True and api.sync_stage(report) is True
    assert [c[0] for c in stage.calls] == ["show"]  # once
    assert api.sync_stage({"state": EMPTY, "settings": ON}) is False
    assert [c[0] for c in stage.calls] == ["show", "hide"]  # Laptop A hides an empty Stage
    api.sync_stage({"state": UP, "settings": {**ON, "game_mode": "on"}})
    assert [c[0] for c in stage.calls] == ["show", "hide"]  # never in game mode
    assert api.show_stage() is False  # the chip doesn't cover a game either
    api.sync_stage({"state": UP, "settings": ON})
    assert api.show_stage() is True
    assert [c[0] for c in stage.calls] == ["show", "hide", "show", "show"]  # the chip brings it to the front


def test_the_api_brings_the_hub_back_at_a_page():
    api = app.StageApi("B")
    hub, stage = FakeWindow(), FakeWindow()
    api._attach(hub, stage)
    assert api.focus_hub("/life/ge-122") is True
    assert hub.calls[0][0] == "run_js" and 'router.go("/life/ge-122")' in hub.calls[0][1]
    assert [c[0] for c in hub.calls[1:]] == ["restore", "show"]
    hub.calls.clear()
    api.focus_hub("javascript:alert(1)")  # only hub paths are followed
    assert [c[0] for c in hub.calls] == ["restore", "show"]


def test_the_api_exposes_only_its_four_calls():
    """pywebview exposes every public attribute of the js_api object to the page."""
    public = {name for name in dir(app.StageApi("B")) if not name.startswith("_")}
    assert public == {"sync_stage", "show_stage", "hide_stage", "focus_hub"}


def test_no_stage_window_is_a_quiet_no():
    api = app.StageApi("B")
    assert api.sync_stage({"state": UP, "settings": ON}) is False and api.show_stage() is False and api.focus_hub() is False


def test_the_stage_options_on_the_command_line(monkeypatch):
    seen = {}
    monkeypatch.setattr(app, "run_native", lambda url, mode, stage=None: seen.update(url=url, mode=mode, stage=stage) or True)
    monkeypatch.setattr(app, "LocalHub", lambda port: SimpleNamespace(url="http://127.0.0.1:9", start=lambda: None, stop=lambda: None))
    app.main(["--strip", "--stage-screen", "1"])
    assert seen["stage"] == {"base": "http://127.0.0.1:9", "device": "A", "screen": 1}
    app.main(["--device", "a"])
    assert seen["stage"]["device"] == "A" and seen["stage"]["screen"] is None
    monkeypatch.setenv("JARVIS_STAGE_SCREEN", "2")
    app.main(["--ambient"])
    assert seen["stage"] == {"base": "http://127.0.0.1:9", "device": "B", "screen": 2} and seen["mode"] == "ambient"
    app.main(["--no-stage"])
    assert seen["stage"] is None


# ---- the setting ----------------------------------------------------------------------------------------
def test_the_stage_setting_is_in_the_contract_and_the_fixture():
    schema = contract("settings")
    assert schema["properties"]["stage"]["enum"] == ["window", "hub"]
    assert "stage" not in schema["required"]  # left out = the Stage window
    for name in ("settings.json", "state.json"):
        data = json.loads((ROOT / "contracts" / "examples" / name).read_text(encoding="utf-8"))
        settings = data.get("settings", data)
        assert settings["stage"] == "window", name
        assert is_valid(settings, schema), name


@pytest.fixture
def client():
    httpx = pytest.importorskip("httpx")  # noqa: F841 - TestClient needs it
    from fastapi.testclient import TestClient

    from jarvis_hub.server import create_app

    with TestClient(create_app(autoplay=False, speed=0), base_url="http://127.0.0.1") as c:
        yield c


def test_the_stage_setting_round_trips(client):
    assert client.get("/api/state").json()["settings"]["stage"] == "window"
    r = client.post("/api/act", json={"action": "set", "target": "stage", "args": {"value": "hub"}})
    assert r.json()["ok"] is True
    assert client.get("/api/state").json()["settings"]["stage"] == "hub"
    bad = client.post("/api/act", json={"action": "set", "target": "stage", "args": {"value": "monitor"}}).json()
    assert bad["ok"] is False and client.get("/api/state").json()["settings"]["stage"] == "hub"
    client.post("/api/act", json={"action": "set", "target": "stage", "args": {"value": "window"}})
    assert client.get("/api/state").json()["settings"]["stage"] == "window"
