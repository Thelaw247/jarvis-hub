"""K2: the hub's demo answers for the Keys page (jarvis_hub/demo/keys.py). Examples only, never accepts anything."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jarvis_hub.demo import keys
from jarvis_hub.server import create_app

ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-ant-api03-DEMO-should-never-be-kept-zz9Z"
NOW = "2026-11-16T15:40:00"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(autoplay=False, speed=0), base_url="http://127.0.0.1") as c:
        yield c


def test_default_rows_and_the_optional_list():
    doc = keys.snapshot(now=NOW)
    assert [r["id"] for r in doc["rows"]] == ["anthropic", "elevenlabs", "composio", "restic"]
    assert [a["id"] for a in doc["addable"]] == ["google-oauth", "openweather"]
    assert doc["can_write"] is False and doc["audit"] == []


@pytest.mark.parametrize("scene", keys.SCENES)
def test_every_scene_is_examples_only(scene):
    doc = keys.snapshot(scene, NOW)
    for r in doc["rows"]:
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", r["id"])
        for slot in (r["live"], r["next"], r["previous"]):
            if slot:
                assert slot["last4"] is None or slot["last4"].startswith("EX")  # made up, and looks it
    have = {r["id"] for r in doc["rows"]}
    assert not have & {a["id"] for a in doc["addable"]}


def test_scene_states():
    status = lambda scene, sid="anthropic": next(r for r in keys.rows_for(scene, NOW) if r["id"] == sid)  # noqa: E731
    assert status("next_waiting")["status"] == "next_waiting"
    assert status("checking")["next"]["check"] == "checking"
    assert status("failed_check")["next"]["reason"] == "rejected"
    assert status("fell_back")["status"] == "fell_back"
    assert status("old_kept")["previous"]["until"] == "2026-11-16T15:54:00"
    assert status("missing", "composio")["live"] is None
    assert status("expiring", "google-oauth")["status"] == "expiring"
    assert status("live", "restic")["live"]["last4"] is None  # nothing of a password is shown


def test_snapshots_match_the_contract_when_it_is_present():
    path = ROOT / "contracts" / "keys.schema.json"
    if not path.exists():
        pytest.skip("contracts/keys.schema.json arrives with K1")
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    docs = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "contracts").glob("*.schema.json")}
    registry = Registry().with_resources((n, Resource.from_contents(d)) for n, d in docs.items())
    validator = Draft202012Validator(docs["keys.schema.json"], registry=registry)
    for scene in keys.SCENES:
        assert not list(validator.iter_errors(keys.snapshot(scene, NOW))), scene


def test_get_is_marked_as_example(client):
    r = client.get("/api/keys", params={"scene": "live", "now": NOW})
    assert r.status_code == 200 and r.headers[keys.EXAMPLE_HEADER] == "example"
    assert r.json()["rows"][0]["live"]["last4"] == "EX01"


@pytest.mark.parametrize(("method", "path"), [("post", "/api/keys/anthropic/next"), ("post", "/api/keys/anthropic/promote"),
                                              ("delete", "/api/keys/anthropic/previous"), ("delete", "/api/keys/anthropic")])
def test_writes_are_refused_and_nothing_is_kept(client, method, path):
    before = json.dumps(keys.snapshot(None, NOW))
    r = client.request(method.upper(), path, json={"secret": SECRET, "confirm": "anthropic"})
    assert r.status_code == 200 and r.headers[keys.EXAMPLE_HEADER] == "example"
    assert r.json() == {"error": "not_allowed", "message": keys.NOT_CONNECTED}
    assert SECRET not in r.text
    assert json.dumps(keys.snapshot(None, NOW)) == before  # nothing changed
    assert SECRET not in json.dumps(client.get("/api/keys").json())


def test_the_refusal_never_reads_the_body(client, monkeypatch):
    from starlette.requests import Request

    async def boom(self):  # noqa: ARG001
        raise AssertionError("the demo read a request body")
    monkeypatch.setattr(Request, "body", boom)
    monkeypatch.setattr(Request, "json", boom)
    assert client.post("/api/keys/anthropic/next", content=SECRET).json()["error"] == "not_allowed"


def test_yes_flag_for_a_fell_back_row_fits_the_rail_contract():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    docs = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "contracts").glob("*.schema.json")}
    registry = Registry().with_resources((n, Resource.from_contents(d)) for n, d in docs.items())
    item = {"$ref": "rail.schema.json#/$defs/item"}
    fell = next(r for r in keys.rows_for("fell_back", NOW) if r["id"] == "anthropic")
    flag = keys.yes_flag(fell, NOW)
    assert flag["slot"] == "yes" and flag["state"] == "yes" and flag["title"] == "Claude key fell back"
    assert not list(Draft202012Validator(item, registry=registry).iter_errors(flag))
    assert keys.yes_flag(keys.rows_for("live", NOW)[0], NOW) is None


# ---- overseer (v0.5.0): the fell-back flag on the Rail, and the live pass-through -----------------------------
def test_keys_updated_puts_and_drops_the_your_yes_item():
    from jarvis_hub.events import apply_event, empty_rail

    state = {"rail": empty_rail(), "marks": {}, "now": "2026-11-16T15:40:00"}
    row = {"id": "anthropic", "label": "Claude (Anthropic API)", "status": "fell_back"}
    apply_event(state, "keys.updated", {"row": row})
    assert [i["ref"] for i in state["rail"]["slots"]["yes"]["items"]] == ["keys:anthropic"]
    apply_event(state, "keys.updated", {"row": row})  # again: still one item
    assert len(state["rail"]["slots"]["yes"]["items"]) == 1
    apply_event(state, "keys.updated", {"row": {**row, "status": "live"}})
    assert state["rail"]["slots"]["yes"]["items"] == []


def test_live_keys_pass_through_with_the_session_header_and_an_unread_body(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from jarvis_hub import keys_proxy

    assert keys_proxy.core_target() is None  # nothing configured: the demo backend
    monkeypatch.setenv("JARVIS_CORE_URL", "https://core.example")
    monkeypatch.setenv("JARVIS_CORE_SESSION", "device-token")
    assert keys_proxy.core_target() == ("https://core.example", "device-token")
    seen = []

    def core(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers.get("x-jarvis-session"), request.content))
        return httpx.Response(200, json={"id": "anthropic", "status": "checking"})

    app = FastAPI()
    app.include_router(keys_proxy.build_router("https://core.example", "device-token", transport=httpx.MockTransport(core)))
    client = TestClient(app)
    assert client.get("/api/keys").status_code == 200
    answer = client.post("/api/keys/anthropic/next", content=b'{"secret":"not-a-real-key"}', headers={"Content-Type": "application/json"})
    assert answer.json() == {"id": "anthropic", "status": "checking"} and "x-jarvis-keys" not in answer.headers
    assert seen[1] == ("POST", "https://core.example/api/keys/anthropic/next", "device-token", b'{"secret":"not-a-real-key"}')
    assert client.post("/api/keys/anthropic/promote", headers={"Origin": "https://evil.example"}).status_code == 403

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    app = FastAPI()
    app.include_router(keys_proxy.build_router("https://core.example", "device-token", transport=httpx.MockTransport(down)))
    answer = TestClient(app).get("/api/keys")
    assert answer.status_code == 502 and answer.json()["error"] == "unreachable"
