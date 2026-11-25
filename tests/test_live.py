"""H5 live mode: the hub shows jarvis-core's state and nothing made up (jarvis_hub/live.py).

The app starts live; the demo day is only behind --demo (JARVIS_HUB_MODE=demo, which the test suite sets)."""
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis.core.app import create_app as create_core
from jarvis.core.config import Config
from jarvis.core.sessions import HubSessions
from jarvis_hub import live
from jarvis_hub.server import create_app as create_hub

HUB = "http://127.0.0.1"


def test_the_hub_starts_live_unless_asked_for_the_demo(monkeypatch):
    monkeypatch.delenv("JARVIS_HUB_MODE", raising=False)
    assert live.hub_mode() == "live"
    monkeypatch.setenv("JARVIS_HUB_MODE", "demo")
    assert live.hub_mode() == "demo"


def test_not_set_up_shows_an_honest_empty_screen(monkeypatch):
    monkeypatch.delenv("JARVIS_CORE_URL", raising=False)
    monkeypatch.delenv("JARVIS_CORE_SESSION", raising=False)
    with TestClient(create_hub(demo=False), base_url=HUB) as c:
        state = c.get("/api/state").json()
        assert state["mode"] == "live" and state["orb"]["state"] == "offline"
        assert state["windows"] == [] and state["approvals"] == [] and state["facts"] == []  # nothing made up
        assert "isn't set up" in state["now_card"]["greeting"]
        assert c.post("/api/act", json={"action": "approve", "target": "x"}).status_code == 503
        assert c.post("/api/demo/play").status_code == 404
        assert c.get("/api/health").json()["core"] == "not set up"


@pytest.fixture
def core(tmp_path):
    config = Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver", "core.test"), keystore="memory")
    app = create_core(config, log_to_stderr=False)
    app.state.token = HubSessions(config.data_dir / "hub_sessions.json").pair("laptop-a")
    with TestClient(app):  # runs the core's startup
        yield app
    logging.getLogger().handlers.clear()


def test_live_passes_the_cores_state_and_actions_through(core):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(live.build_router(("http://core.test", core.state.token), transport=httpx.ASGITransport(app=core)))
    with TestClient(app) as c:
        state = c.get("/api/state").json()
        assert state["mode"] == "live" and state["orb"]["state"] == "idle"  # the core's own state
        answer = c.post("/api/act", json={"action": "no-such-action", "target": "x"})
        assert answer.status_code == 400  # the core answered (unknown action), not the hub
        assert c.get("/api/health").json()["core"] == "connected"


def test_a_core_that_doesnt_answer_reads_as_offline(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("no route", request=request)

    router = live.build_router(("http://core.test", "token"), transport=httpx.MockTransport(refuse))
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        state = c.get("/api/state").json()
        assert state["orb"]["state"] == "offline" and "isn't answering" in state["now_card"]["greeting"]
        assert c.post("/api/act", json={"action": "x", "target": "y"}).status_code == 502


def test_an_unpaired_hub_is_turned_away(core):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(live.build_router(("http://core.test", "not-paired"), transport=httpx.ASGITransport(app=core)))
    with TestClient(app) as c:
        assert c.get("/api/state").json()["orb"]["state"] == "offline"  # shown as offline, nothing leaks


def test_the_voice_id_is_saved_on_the_core_through_the_hub(core):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(live.build_router(("http://core.test", core.state.token), transport=httpx.ASGITransport(app=core)))
    with TestClient(app) as c:
        assert c.get("/api/settings").json() == {"voice_id": ""}
        bad = c.put("/api/settings/voice", json={"voice_id": "not a voice id!"})
        assert bad.status_code == 400 and "voice ID" in bad.json()["detail"]
        ok = c.put("/api/settings/voice", json={"voice_id": "  JBFqnCBsd6RMkjVDRZzb "})
        assert ok.status_code == 200 and ok.json() == {"voice_id": "JBFqnCBsd6RMkjVDRZzb"}
        assert c.get("/api/settings").json() == {"voice_id": "JBFqnCBsd6RMkjVDRZzb"}
        assert c.put("/api/settings/voice", json={"voice_id": ""}).json() == {"voice_id": ""}  # cleared


def test_settings_need_a_core_and_a_paired_writer(core, monkeypatch):
    monkeypatch.delenv("JARVIS_CORE_URL", raising=False)
    monkeypatch.delenv("JARVIS_CORE_SESSION", raising=False)
    with TestClient(create_hub(demo=False), base_url=HUB) as c:
        answer = c.get("/api/settings")
        assert answer.headers["X-Jarvis-Settings"] == "example" and "isn't set up" in answer.json()["message"]
        assert c.put("/api/settings/voice", json={"voice_id": "JBFqnCBsd6RMkjVDRZzb"}).status_code == 503
    phone = HubSessions(core.state.core.config.data_dir / "hub_sessions.json").pair("phone", can_write=False)
    c = TestClient(core)  # the fixture already started the core
    assert c.get("/api/settings").status_code == 401
    assert c.put("/api/settings/voice", json={"voice_id": "JBFqnCBsd6RMkjVDRZzb"},
                 headers={"X-Jarvis-Session": phone}).status_code == 403
