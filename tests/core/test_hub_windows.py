"""v0.15.3: the windows' own buttons work on the real core. On 2026-11-19 a page Jarvis pulled up could not be
closed or pinned: the hub said "Jarvis can't do that yet. Nothing was changed."."""
import pytest
from fastapi.testclient import TestClient

from jarvis.core.app import create_app
from jarvis.core.config import Config
from jarvis.core.sessions import HubSessions


@pytest.fixture
def hub(tmp_path):
    config = Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver",), keystore="memory",
                             voice_preload=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("laptop-a", can_write=True)
    app = create_app(config, log_to_stderr=False)
    with TestClient(app) as client:
        client.headers["X-Jarvis-Session"] = token
        yield app, client


def page(n, **more):
    return {"id": f"w-web-{n}", "type": "web", "title": f"Page {n}", "size": "2x2",
            "data": {"pages": [{"id": f"p-{n}", "url": f"https://example.com/{n}", "title": f"Page {n}"}], "active": f"p-{n}"},
            **more}


def act(client, action, target="", **args):
    return client.post("/api/act", json={"action": action, "target": target, "args": args}).json()


def state(client):
    return client.get("/api/state").json()


def test_a_window_jarvis_opened_can_be_closed_pinned_and_made_bigger(hub):
    app, c = hub
    app.state.core.bus.publish("window.push", page(1))
    app.state.core.bus.publish("window.push", page(2))
    assert act(c, "pin", "w-web-1") == {"ok": True}
    assert act(c, "resize", "w-web-1") == {"ok": True}
    one = next(w for w in state(c)["windows"] if w["id"] == "w-web-1")
    assert one["pinned"] is True and one["size"] == "3x2"
    assert act(c, "unpin", "w-web-1") == {"ok": True}
    assert act(c, "move", "w-web-2", to="left") == {"ok": True}
    assert [w["id"] for w in state(c)["windows"]] == ["w-web-2", "w-web-1"]
    assert act(c, "close", "w-web-2") == {"ok": True}
    assert [w["id"] for w in state(c)["windows"]] == ["w-web-1"]
    assert act(c, "close", "w-web-2") == {"ok": True}                # twice is not an error
    assert act(c, "resize", "w-web-1", size="9x9")["ok"] is False


def test_clear_view_docks_everything_and_a_docked_thing_comes_back_or_is_done(hub):
    app, c = hub
    task = {"id": "w-job-1", "type": "agent_task", "title": "Find the lab manual", "ref": "job-1", "size": "2x1"}
    app.state.core.bus.publish("window.push", task)
    app.state.core.bus.publish("window.push", page(3))
    assert act(c, "close_all") == {"ok": True}
    s = state(c)
    assert s["windows"] == []
    docked = [i for slot in s["rail"]["slots"].values() for i in slot["items"]]
    assert "job-1" in [i["ref"] for i in docked]                     # nothing is deleted: his task is on the Rail
    assert act(c, "recall", "job-1") == {"ok": True}
    assert [w["id"] for w in state(c)["windows"]] == ["w-job-1"]
    assert act(c, "archive", "job-1") == {"ok": True}                # done with it
    s = state(c)
    assert s["windows"] == [] and "job-1" not in [i["ref"] for slot in s["rail"]["slots"].values() for i in slot["items"]]
    assert act(c, "recall", "job-1")["ok"] is False


def test_what_still_needs_his_yes_stays_a_stub(hub):
    _app, c = hub
    for action in ("approve", "decline", "undo", "revoke"):
        assert act(c, action, "x") == {"ok": False, "message": "Jarvis can't do that yet. Nothing was changed."}
    # forget is real since v0.20.0 (the Memory page's Forget on a fact); a target that is no fact changes nothing
    assert act(c, "forget", "x") == {"ok": False, "message": "That isn't something Jarvis remembered. Nothing was changed."}
