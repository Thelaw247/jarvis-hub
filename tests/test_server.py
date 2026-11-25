"""Hub server and demo backend: state, events, actions and the scripted day all speak the contracts."""
import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient

from jarvis_hub.demo.fixtures import bare_state, load_state
from jarvis_hub.demo.scenario import DemoPlayer, steps
from jarvis_hub.events import MAX_WINDOWS, SLOTS, Hub, apply_event, ensure_v2
from jarvis_hub.server import create_app
from tests.test_contracts import validator


@pytest.fixture
def client():
    with TestClient(create_app(autoplay=False, speed=0), base_url="http://127.0.0.1") as c:
        hub = c.app.state.hub  # the Rail's and the marks' own rules start from a bare day (N7's fixture has a realistic Rail)
        hub._initial = bare_state()
        hub.reset()
        yield c


def errors(name, doc):
    return [f"{list(e.path)}: {e.message}" for e in validator(name).iter_errors(doc)]


def test_state_matches_the_contract(client):
    body = client.get("/api/state").json()
    body.pop("demo")
    assert errors("state", body) == []
    assert body["mode"] == "demo"


def test_health_and_static_contract_files(client):
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/contracts/examples/state.json").status_code == 200


def test_every_scripted_event_matches_its_contract():
    by_type = {"orb.state": "orb_state", "nowcard.updated": "now_card", "window.push": "window", "caption.show": "caption",
               "approval.pending": "approval", "job.progress": "job", "toast": "toast", "activity.added": "action"}
    for _wait, kind, data in steps(load_state()):
        if kind == "__while_pending__":  # a guarded step: check the event inside it
            kind, data = data["type"], data["data"]
        if kind.startswith("__"):
            continue
        assert errors("event", {"v": 2, "type": kind, "ts": "2026-11-16T15:40:00", "data": data}) == []
        if kind in by_type:
            assert errors(by_type[kind], data) == [], kind


def test_the_demo_day_plays_and_leaves_a_valid_state():
    hub = Hub(load_state())
    queue = hub.subscribe()
    # its own thread and loop: the browser tests leave a loop running in the main thread
    worker = threading.Thread(target=lambda: asyncio.run(DemoPlayer(hub, speed=0).play()))
    worker.start()
    worker.join(timeout=10)
    kinds = []
    while not queue.empty():
        kinds.append(queue.get_nowait()["type"])
    assert {"orb.state", "window.push", "caption.show", "approval.pending", "job.progress", "toast"} <= set(kinds)
    assert errors("state", hub.snapshot()) == []
    assert {a["id"]: a["status"] for a in hub.state["approvals"]} == {"ap-week": "pending", "ap-study": "approved"}  # his "Yes." inside the window
    assert hub.state["orb"]["state"] == "idle"  # nobody answered the week plan: calm, not nagging
    assert hub.state["jobs"] == []


def play_in_thread(player):
    # its own thread and loop: the browser tests leave a loop running in the main thread
    worker = threading.Thread(target=lambda: asyncio.run(player.play()))
    worker.start()
    worker.join(timeout=10)


def detail(name, data):
    """Check an event's data against its shape in event.schema.json ($defs)."""
    from jsonschema import Draft202012Validator

    from tests.test_contracts import REGISTRY, SCHEMAS
    schema = {"$ref": f"event.schema.json#/$defs/{name}"}
    return [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema, registry=REGISTRY).iter_errors(data)] if name in SCHEMAS["event.schema.json"]["$defs"] else ["no such shape"]


@pytest.fixture
def reducers_only(monkeypatch):
    """Hubs made in this test keep only what the reducers put on the Rail (no items derived by jarvis_hub/rail.py),
    so the dock, one-item-per-thing and fold rules can be checked on their own. tests/test_rail.py covers the rest."""
    import jarvis_hub.rail

    monkeypatch.setattr(jarvis_hub.rail, "refresh", lambda state, now: state["rail"])


def docked(state):
    """The ids of every window docked on the Rail."""
    return [item["window"]["id"] for slot in state["rail"]["slots"].values() for item in slot["items"] if item.get("window")]


def drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def test_answering_quickly_never_leaves_the_orb_waiting():
    """W1: he says yes right after the approval appears, before the script reaches its "waiting" step."""
    hub = Hub(load_state())
    publish = hub.publish

    def answer_at_once(kind, data, about=None):
        event = publish(kind, data, about=about)
        if kind == "approval.pending":
            assert hub.act("approve", data["id"])["ok"]
        return event

    hub.publish = answer_at_once
    queue = hub.subscribe()
    play_in_thread(DemoPlayer(hub, speed=0))
    events = drain(queue)
    answered = next(i for i, e in enumerate(events) if e["type"] == "approval.resolved" and e["data"]["id"] == "ap-week")
    after = events[answered:]
    assert not any(e["type"] == "orb.state" and e["data"]["state"] == "waiting" for e in after)  # (the wind-down still speaks)
    assert not any(e["type"] == "window.push" and e["data"]["id"] == "w-ap-week" for e in after)
    assert hub.snapshot()["orb"]["state"] == "idle"  # a reload shows a resting orb too
    assert {a["status"] for a in hub.state["approvals"]} == {"approved"}


def test_the_orb_never_waits_when_nothing_is_waiting():
    hub = Hub(load_state())
    hub.act("approve", "ap-week")
    hub.publish("orb.state", {"state": "waiting", "countdown_s": 10, "window_s": 10})
    assert hub.state["orb"]["state"] == "idle"
    hub.act("mute", "mic")
    hub.publish("orb.state", {"state": "waiting"})
    assert hub.state["orb"]["state"] == "muted"


def later(hub, **delta):
    """Move the demo clock forward."""
    from datetime import timedelta

    hub._clock_base += timedelta(**delta)


def test_undo_only_inside_its_window():
    """W3: the undo window is enforced by the server, not just hidden by the UI."""
    hub = Hub(load_state())
    later(hub, hours=18)  # about 09:40 the next day: a-quiz's window closed at 09:12; a-sync's is open until 15:38
    assert hub.act("undo", "a-quiz") == {"ok": False, "message": "The undo window has passed."}
    assert not next(a for a in hub.state["actions"] if a["id"] == "a-quiz").get("undone")
    assert hub.act("undo", "a-sync")["ok"] is True


def test_an_approval_that_ran_out_cannot_be_answered():
    """W3: after `expires` nothing is done, and the approval is resolved as expired."""
    hub = Hub(load_state())
    queue = hub.subscribe()
    later(hub, hours=6)  # ap-week expires at 21:00; the demo clock is now about 21:40
    assert hub.act("approve", "ap-week") == {"ok": False, "message": "This offer ran out. Nothing was done."}
    assert hub.state["approvals"][0]["status"] == "expired"
    assert not any(a["what"] == "Book this week's study plan" for a in hub.state["actions"])
    events = drain(queue)
    assert (events[0]["type"], events[0]["data"]) == ("approval.resolved", {"id": "ap-week", "status": "expired"})
    assert all(errors("event", e) == [] for e in events)
    assert errors("state", hub.snapshot()) == []


def test_an_approval_expires_on_time_without_anyone_asking():
    """W3: approval.resolved (expired) is published at the expiry time, with no request needed."""
    from datetime import timedelta

    hub = Hub(load_state())
    hub.state["approvals"] = []

    async def scenario():
        queue = hub.subscribe()
        approval = {**load_state()["approvals"][0], "expires": (hub.now() + timedelta(seconds=0.2)).isoformat()}
        hub.publish("approval.pending", approval)
        hub.publish("orb.state", {"state": "waiting", "countdown_s": 10, "window_s": 10})
        await asyncio.sleep(0.5)
        return drain(queue)

    result = {}
    worker = threading.Thread(target=lambda: result.update(events=asyncio.run(scenario())))
    worker.start()
    worker.join(timeout=10)
    resolved = [e["data"] for e in result["events"] if e["type"] == "approval.resolved"]
    assert resolved == [{"id": "ap-week", "status": "expired"}]
    assert hub.state["orb"]["state"] == "idle"  # it was waiting for this one, so it rests


def test_toasts_and_captions_leave_the_state_when_their_time_is_up():
    """W4: a reload doesn't replay old toasts and the last caption."""
    hub = Hub(load_state())
    hub.publish("toast", {"id": "t-short", "kind": "info", "text": "Undone.", "ttl_ms": 4000})
    hub.publish("toast", {"id": "t-stays", "kind": "error", "text": "Try again in a moment."})  # no ttl: stays until dismissed
    hub.publish("caption.show", {"text": "Here's PPS 7.", "source": None, "ttl_ms": 5000})
    assert [t["id"] for t in hub.snapshot()["toasts"]] == ["t-short", "t-stays"] and hub.snapshot()["caption"]
    later(hub, seconds=4.5)
    body = hub.snapshot()
    assert [t["id"] for t in body["toasts"]] == ["t-stays"] and body["caption"]["text"] == "Here's PPS 7."
    later(hub, seconds=1)
    assert hub.snapshot()["caption"] is None
    hub.publish("caption.show", {"text": "No time given, so the screen's default."})
    later(hub, seconds=5)
    assert hub.snapshot()["caption"] is not None
    later(hub, seconds=1.5)
    assert hub.snapshot()["caption"] is None
    assert errors("state", hub.snapshot()) == []


def test_the_read_back_caption_goes_when_its_approval_is_answered():
    hub = Hub(load_state())
    queue = hub.subscribe()
    hub.publish("caption.show", {"text": hub.state["approvals"][0]["read_back"], "ttl_ms": 7000}, about="ap-week")
    hub.act("approve", "ap-week")
    assert hub.state["caption"] is None
    cleared = [e for e in drain(queue) if e["type"] == "caption.show" and e["data"] == {"text": ""}]
    assert len(cleared) == 1 and errors("event", cleared[0]) == [] and errors("caption", cleared[0]["data"]) == []
    hub.publish("caption.show", {"text": "Something else.", "ttl_ms": 7000})
    hub.act("decline", "ap-week")  # refused: already answered, and the other caption stays
    assert hub.state["caption"]["text"] == "Something else."


def test_moving_a_window_is_one_real_reorder():
    """W6 + HUD v2 §6.2: "put it on the left/right" reaches every screen as one window.order, never close + push
    (which would look like a window leaving and a new one arriving)."""
    hub = Hub(bare_state())
    for i in range(4):
        hub.publish("window.push", {"id": f"w-{i}", "type": "notice", "title": str(i), "pinned": i == 2})
    queue = hub.subscribe()
    hub.act("move", "w-2", {"to": "left"})
    events = drain(queue)
    assert [(e["type"], e["data"]) for e in events] == [("window.order", {"ids": ["w-2", "w-0", "w-1", "w-3"]})]
    assert [w["id"] for w in hub.state["windows"]] == ["w-2", "w-0", "w-1", "w-3"]
    assert next(w for w in hub.state["windows"] if w["id"] == "w-2")["pinned"] is True
    hub.act("move", "w-0", {"to": "right"})
    events += drain(queue)
    assert [w["id"] for w in hub.state["windows"]] == ["w-2", "w-1", "w-3", "w-0"]
    hub.act("move", "w-0", {"to": "right"})
    assert drain(queue) == []  # already there
    assert hub.act("order", "windows", {"ids": ["w-3", "w-2"]}) == {"ok": True}  # named ones first, the rest keep their order
    assert [w["id"] for w in hub.state["windows"]] == ["w-3", "w-2", "w-1", "w-0"]
    assert hub.act("order", "windows", {"ids": "w-3"})["ok"] is False
    events += drain(queue)
    assert {e["type"] for e in events} == {"window.order"} and hub.state["marks"] == {}  # nothing closed, nothing marked new
    assert all(errors("event", e) == [] for e in events)
    assert all(detail("window_order", e["data"]) == [] for e in events)


def test_bigger_grows_every_window_size():
    """A tall 1x2 window (the GE 122 card) used to crash "bigger"; now it grows wider and keeps its height."""
    hub = Hub(load_state())
    hub.publish("window.push", {"id": "w-ge122", "type": "branch_card", "title": "GE 122", "ref": "ge-122", "size": "1x2"})
    assert hub.act("resize", "w-ge122") == {"ok": True}
    assert hub.state["windows"][-1]["size"] == "2x2"
    assert hub.act("resize", "w-ge122", {"size": "9x9"})["ok"] is False
    assert hub.state["windows"][-1]["size"] == "2x2"


@pytest.fixture
def live_server():
    """A real server on a free port (SSE needs true streaming, which the in-process test client buffers)."""
    import socket
    import threading
    import time

    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    app = create_app(autoplay=False, speed=0)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", app
    server.should_exit = True
    thread.join(timeout=5)


def test_events_stream_over_sse(live_server):
    import httpx

    url, _app = live_server
    events = []
    with httpx.Client(timeout=10, trust_env=False) as http, http.stream("GET", f"{url}/api/events?limit=2") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.iter_lines()
        assert next(lines).startswith(":")  # connected
        # actions arrive through the API, events come back on the stream
        httpx.post(f"{url}/api/act", json={"action": "mute", "target": "mic"}, trust_env=False)
        for line in lines:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert [e["type"] for e in events] == ["settings.updated", "orb.state"]
    assert all(errors("event", e) == [] for e in events)


def test_approve_leaves_a_receipt_with_undo(client):
    hub = client.app.state.hub
    assert client.post("/api/act", json={"action": "approve", "target": "ap-week"}).json()["ok"]
    assert hub.state["approvals"][0]["status"] == "approved"
    receipt = hub.state["actions"][0]
    assert receipt["what"] == "Book this week's study plan" and receipt["undo"]["label"] == "24 h"
    assert errors("action", receipt) == []
    assert client.post("/api/act", json={"action": "decline", "target": "ap-week"}).json()["ok"] is False
    assert client.post("/api/act", json={"action": "undo", "target": receipt["id"]}).json()["ok"]
    assert hub.state["actions"][0]["undone"] is True
    assert client.post("/api/act", json={"action": "undo", "target": "a-held"}).json()["ok"] is False  # no undo


def test_the_same_answer_twice_is_done_once(client):
    """W7: a double click on "Yes, do it" (or Undo) is not an error and has no second effect."""
    hub = client.app.state.hub
    queue = hub.subscribe()
    first = client.post("/api/act", json={"action": "approve", "target": "ap-week"}).json()
    count = len(drain(queue))
    receipts = len(hub.state["actions"])
    assert first == {"ok": True} and count > 0
    assert client.post("/api/act", json={"action": "approve", "target": "ap-week"}).json() == {"ok": True}
    assert drain(queue) == [] and len(hub.state["actions"]) == receipts
    receipt = hub.state["actions"][0]["id"]
    assert client.post("/api/act", json={"action": "undo", "target": receipt}).json()["ok"]
    drain(queue)
    assert client.post("/api/act", json={"action": "undo", "target": receipt}).json() == {"ok": True}
    assert drain(queue) == []


def test_fact_actions(client):
    hub = client.app.state.hub
    find = lambda fid: next((f for f in hub.state["facts"] if f["id"] == fid), None)
    client.post("/api/act", json={"action": "confirm", "target": "f-ge-pace"})
    assert find("f-ge-pace")["confidence"] == "sure"
    client.post("/api/act", json={"action": "use_theirs", "target": "f-ge-quiz"})
    assert find("f-ge-quiz")["conflict"]["kept"] == "theirs"
    client.post("/api/act", json={"action": "file", "target": "u-1"})
    assert find("u-1")["branch_id"] == "cmpt-141"
    client.post("/api/act", json={"action": "forget", "target": "f-hv"})
    assert find("f-hv") is None
    assert errors("state", hub.snapshot()) == []


def test_settings_mute_and_bad_actions(client):
    hub = client.app.state.hub
    client.post("/api/act", json={"action": "set", "target": "interruption", "args": {"value": "quiet"}})
    assert hub.state["settings"]["interruption"] == "quiet"
    client.post("/api/act", json={"action": "mute", "target": "mic"})
    assert hub.state["orb"]["state"] == "muted" and hub.state["settings"]["muted"] is True
    assert client.post("/api/act", json={"action": "explode", "target": "x"}).status_code == 400
    assert client.post("/api/act", json={"nope": 1}).status_code == 400


def test_at_most_five_windows_and_pinned_ones_stay():
    state = load_state()
    apply_event(state, "window.push", {"id": "w-0", "type": "notice", "title": "Pinned", "pinned": True})
    for i in range(1, 9):
        apply_event(state, "window.push", {"id": f"w-{i}", "type": "notice", "title": str(i)})
    ids = [w["id"] for w in state["windows"]]
    assert len(ids) == MAX_WINDOWS and "w-0" in ids and "w-8" in ids and "w-1" not in ids
    apply_event(state, "window.close", {"all": True})
    assert state["windows"] == []
    assert sorted(docked(state)) == sorted(f"w-{i}" for i in range(9))  # pushed out or cleared, all nine are on the Rail


def test_demo_restart(client):
    client.post("/api/act", json={"action": "approve", "target": "ap-week"})
    assert client.post("/api/demo/restart").json()["ok"]
    assert client.post("/api/demo/nope").status_code == 404


def test_actions_from_another_site_are_refused(client):
    other = client.post("/api/act", json={"action": "approve", "target": "ap-week"}, headers={"Origin": "https://example.com"})
    assert other.status_code == 403 and client.app.state.hub.state["approvals"][0]["status"] == "pending"
    assert client.post("/api/demo/restart", headers={"Origin": "https://example.com"}).status_code == 403
    own = client.post("/api/act", json={"action": "approve", "target": "ap-week"}, headers={"Origin": "http://127.0.0.1"})
    assert own.status_code == 200 and own.json()["ok"]


def test_proposal_tweak_source_switch_and_branch_settings(client):
    hub = client.app.state.hub
    client.post("/api/act", json={"action": "change", "target": "p-laundry", "args": {"note": "make it 10"}})
    assert hub.state["day"]["proposals"] == []
    client.post("/api/act", json={"action": "set", "target": "source:gmail", "args": {"value": False}})
    assert next(s for s in hub.state["settings"]["sources"] if s["id"] == "gmail")["on"] is False
    before = [b["name"] for b in hub.state["branches"]]
    client.post("/api/act", json={"action": "edit", "target": "branch:ge-122", "args": {"name": "X"}})
    assert [b["name"] for b in hub.state["branches"]] == before and "demo mode" in hub.state["toasts"][-1]["text"]
    assert errors("state", hub.snapshot()) == []


def test_a_fresh_demo_starts_at_the_beginning_of_the_day():
    with TestClient(create_app(autoplay=True, speed=0), base_url="http://127.0.0.1") as c:
        body = c.get("/api/state").json()
        assert body["approvals"] == [] and body["windows"] == [] and body["demo"]["played"] is False


def test_only_our_own_host_names_are_answered(client, monkeypatch):
    """W13: a page on another site can't reach the hub through a name that points at 127.0.0.1 (DNS rebinding)."""
    hub = client.app.state.hub
    for host in ("evil.example.com", "127.0.0.1.nip.io"):
        assert client.get("/api/state", headers={"Host": host}).status_code == 400
        assert client.post("/api/act", json={"action": "approve", "target": "ap-week"}, headers={"Host": host}).status_code == 400
    assert hub.state["approvals"][0]["status"] == "pending"
    assert client.get("/api/health", headers={"Host": "localhost:8765"}).status_code == 200
    monkeypatch.setenv("JARVIS_HUB_HOSTS", "hub.tailnet-name.ts.net, hub")
    with TestClient(create_app(autoplay=False, speed=0), base_url="http://hub.tailnet-name.ts.net") as tailnet:
        assert tailnet.get("/api/health").status_code == 200
        assert tailnet.get("/api/health", headers={"Host": "hub"}).status_code == 200
        assert tailnet.get("/api/health", headers={"Host": "other.ts.net"}).status_code == 400


def test_settings_only_take_values_the_contract_allows(client):
    """W13: `set` is checked against settings.schema.json; anything else changes nothing."""
    hub = client.app.state.hub
    act = lambda target, value: client.post("/api/act", json={"action": "set", "target": target, "args": {"value": value}}).json()
    before = json.loads(json.dumps(hub.state["settings"]))
    for target, value in [("interruption", "loud"), ("theme", "<script>"), ("focus", "yes"), ("plants", 1),
                          ("quiet_hours", {"on": True}), ("quiet_hours", {"on": True, "from": "22:00", "to": "07:00", "x": 1}),
                          ("sources", []), ("standing_permissions", []), ("nonsense", True), ("__class__", "x"),
                          ("source:gmail", "off"), ("source:nope", True)]:
        assert act(target, value)["ok"] is False, (target, value)
    assert client.post("/api/act", json={"action": "set", "target": "focus", "args": {}}).json()["ok"] is False
    assert hub.state["settings"] == before
    assert act("interruption", "chatty")["ok"] and act("focus", True)["ok"] and act("source:gmail", False)["ok"]
    assert act("quiet_hours", {"on": False, "from": "22:00", "to": "07:00"})["ok"]
    assert hub.state["settings"]["interruption"] == "chatty" and hub.state["settings"]["quiet_hours"]["on"] is False
    assert errors("settings", hub.state["settings"]) == []


def test_a_booked_plan_is_no_longer_offered(client):
    hub = client.app.state.hub
    offers = lambda: [o["id"] for o in hub.state["now_card"]["ready_to_offer"]]
    assert offers() == ["o-week", "o-hints"]
    client.post("/api/act", json={"action": "approve", "target": "ap-week"})
    assert offers() == ["o-hints"]
    assert errors("now_card", hub.state["now_card"]) == []


def test_a_no_is_logged_as_a_quiet_receipt_with_nothing_to_undo():
    hub = Hub(load_state())
    title = hub.state["approvals"][0]["title"]
    assert hub.act("decline", "ap-week") == {"ok": True}
    row = next(a for a in hub.state["actions"] if a["id"] == "declined-ap-week")
    assert row["what"] == title and row["why"].startswith("You said no") and row["undo"] is None
    assert errors("action", row) == [] and errors("state", hub.snapshot()) == []
    assert hub.act("decline", "ap-week") == {"ok": True}  # again: still one row
    assert sum(a["id"] == "declined-ap-week" for a in hub.state["actions"]) == 1
    assert hub.act("undo", "declined-ap-week")["ok"] is False


def test_change_it_keeps_his_words_and_stops_asking_what_to_change():
    hub = Hub(load_state())
    queue = hub.subscribe()
    assert hub.act("change", "ap-week", {"text": "  Not before 10 am,\n please "}) == {"ok": True}
    assert hub.tweaks == {"ap-week": "Not before 10 am, please"}
    toasts = [e["data"]["text"] for e in drain(queue) if e["type"] == "toast"]
    assert toasts == ["It comes back with that change, for your yes."]
    hub.reset()
    assert hub.tweaks == {}
    assert hub.act("change", "ap-week") == {"ok": True}  # no words given: Jarvis still has to ask
    assert hub.state["toasts"][-1]["text"].startswith("Tell me what to change") and hub.tweaks == {}


# ---- contracts v2 (hub v0.3.0): nothing gets away -------------------------------------------------------------
def note(i, **more):
    return {"id": f"w-{i}", "type": "notice", "title": f"Note {i}", **more}


def test_a_sixth_window_docks_the_oldest_instead_of_deleting_it(reducers_only):
    hub = Hub(bare_state())
    queue = hub.subscribe()
    hub.publish("window.push", note(0, pinned=True))
    hub.publish("window.push", {"id": "w-chart", "type": "chart", "title": "Hours this week"})
    for i in range(1, 6):
        hub.publish("window.push", note(i, ref=f"thing-{i}"))
    assert [w["id"] for w in hub.state["windows"]] == ["w-0", "w-2", "w-3", "w-4", "w-5"]  # the pinned one stays
    assert docked(hub.state) == ["w-1"]  # the chart was a pure view: it just closed; the note is a thing: it docked
    item = hub.state["rail"]["slots"]["jarvis"]["items"][0]
    assert (item["ref"], item["kind"], item["window"]["docked"], item["window"]["slot"]) == ("thing-1", "notice", True, "jarvis")
    events = drain(queue)
    assert "window.close" not in {e["type"] for e in events}
    assert [e["data"]["slots"]["jarvis"]["items"][0]["ref"] for e in events if e["type"] == "rail.updated"] == ["thing-1"]  # every screen is told
    assert all(errors("event", e) == [] for e in events) and errors("state", hub.snapshot()) == []


def test_closing_and_clear_view_dock_and_recall_brings_the_window_back(reducers_only):
    hub = Hub(bare_state())
    hub.publish("window.push", {"id": "w-due-pps7", "type": "countdown", "title": "Due", "ref": "due-pps7", "size": "1x1", "pinned": True})
    hub.publish("window.push", {"id": "w-ge122", "type": "branch_card", "title": "GE 122", "ref": "ge-122", "size": "1x2"})
    hub.publish("window.push", {"id": "w-next", "type": "next_up", "title": "Next"})
    queue = hub.subscribe()
    assert hub.act("close", "w-due-pps7") == {"ok": True}  # the close button, "close that" and the 60 s lifetime all send this
    assert [w["id"] for w in hub.state["windows"]] == ["w-ge122", "w-next"]
    assert [i["ref"] for i in hub.state["rail"]["slots"]["homework"]["items"]] == ["due-pps7"]
    assert hub.act("close_all", "all") == {"ok": True}  # CLEAR VIEW
    assert hub.state["windows"] == [] and sorted(docked(hub.state)) == ["w-due-pps7", "w-ge122"]
    assert [i["ref"] for i in hub.state["rail"]["slots"]["parked"]["items"]] == ["ge-122"]
    events = drain(queue)
    assert [e["type"] for e in events] == ["window.dock", "rail.updated", "window.dock", "rail.updated"]
    assert [e["data"] for e in events if e["type"] == "window.dock"] == [{"id": "w-due-pps7", "reason": "closed"}, {"all": True, "reason": "cleared"}]
    assert all(detail("window_dock", e["data"]) == [] for e in events if e["type"] == "window.dock")
    assert errors("state", hub.snapshot()) == []
    assert hub.act("recall", "due-pps7") == {"ok": True}
    back = hub.state["windows"][0]
    assert (back["id"], back["pinned"], back["size"]) == ("w-due-pps7", True, "1x1") and "docked" not in back and errors("window", back) == []
    assert hub.state["rail"]["slots"]["homework"]["items"] == []
    assert hub.act("recall", "due-pps7") == {"ok": False, "message": "That isn't on the Rail any more."}
    assert hub.act("dock", "w-due-pps7", {"reason": "lifetime", "slot": "today"}) == {"ok": True}
    assert [i["ref"] for i in hub.state["rail"]["slots"]["today"]["items"]] == ["due-pps7"]


def test_the_rail_has_one_item_per_thing(reducers_only):
    hub = Hub(bare_state())
    hub.publish("window.push", {"id": "w-a", "type": "file", "title": "PPS 7", "ref": "file-pps7"})
    hub.act("close", "w-a")
    hub.publish("window.push", {"id": "w-b", "type": "file", "title": "PPS 7 again", "ref": "file-pps7", "slot": "parked"})
    hub.act("close", "w-b")
    items = [i for slot in hub.state["rail"]["slots"].values() for i in slot["items"]]
    assert [(i["ref"], i["slot"], i["window"]["id"]) for i in items] == [("file-pps7", "parked", "w-b")]
    hub.publish("window.push", {"id": "w-c", "type": "fact", "title": "Straight to its slot", "ref": "f-1", "docked": True})
    assert hub.state["windows"] == [] and docked(hub.state) == ["w-c", "w-b"]
    assert hub.act("archive", "file-pps7") == {"ok": True}  # done with it: the only way off the Rail
    assert docked(hub.state) == ["w-c"]


def test_an_approval_that_runs_out_docks_under_your_yes_with_a_mark():
    hub = Hub(bare_state())
    hub.publish("window.push", {"id": "w-ap-week", "type": "approval", "title": "Waiting for your yes", "ref": "ap-week", "size": "2x2"})
    queue = hub.subscribe()
    later(hub, hours=6)
    body = hub.snapshot()
    assert body["approvals"][0]["status"] == "expired" and body["windows"] == []
    item = body["rail"]["slots"]["yes"]["items"][0]
    assert (item["ref"], item["kind"], item["window"]["id"]) == ("ap-week", "approval", "w-ap-week")
    assert body["marks"]["ap-week"]["what"] == "Ran out unanswered: Book this week's study plan. Nothing was done."
    events = drain(queue)
    assert [e["type"] for e in events] == ["approval.resolved", "rail.updated", "marks.updated"]  # no window.close
    assert errors("state", body) == [] and all(errors("event", e) == [] for e in events)


def test_an_expired_approval_without_a_window_still_reaches_the_rail_and_an_answered_one_leaves():
    hub = Hub(bare_state())
    later(hub, hours=6)
    hub.expire_due()
    assert [(i["ref"], i["title"]) for i in hub.state["rail"]["slots"]["yes"]["items"]] == [("ap-week", "Book this week's study plan")]
    hub = Hub(bare_state())
    hub.publish("window.push", {"id": "w-ap-week", "type": "approval", "title": "Waiting for your yes", "ref": "ap-week"})
    hub.act("close", "w-ap-week")  # set aside unanswered: it waits under Your yes
    assert docked(hub.state) == ["w-ap-week"] and hub.is_pending("ap-week")
    hub.act("approve", "ap-week")
    assert hub.state["rail"]["slots"]["yes"]["items"] == []  # answered is done


def test_changes_leave_marks_that_say_what_changed():
    hub = Hub(bare_state())
    queue = hub.subscribe()
    ge = next(b for b in hub.state["branches"] if b["id"] == "ge-122")
    card = json.loads(json.dumps(hub.state["cards"]["ge-122"]))
    card["due"][0]["due"] = "2026-11-19T23:59:00"
    hub.publish("branch.updated", {"branch": ge, "card": card})
    assert hub.state["marks"]["due-pps7"]["what"] == "Due moved Wed 8 pm → Thu 11:59 pm"
    day = json.loads(json.dumps(hub.state["day"]))
    review = next(i for i in day["items"] if i["id"] == "d-review")
    review.update(start="17:30", end="18:15")
    day["items"] = [i for i in day["items"] if i["id"] != "d-pps"]
    hub.publish("day.updated", day)
    assert hub.state["marks"]["d-review"]["what"] == "Review GE 122 lecture 21 moved 4 pm → 5:30 pm"
    assert hub.state["marks"]["d-pps"]["what"].startswith("Removed: PPS 7")
    now_card = json.loads(json.dumps(hub.state["now_card"]))
    now_card["next_up"]["when"] = "5:30 pm"
    now_card["flag"]["text"] = "PPS 7 is due Thursday 11:59 pm · half done"
    hub.publish("nowcard.updated", now_card)
    assert hub.state["marks"]["now_card"]["what"] == "Review GE 122 lecture 21 moved 4:00 pm → 5:30 pm"
    assert "Thursday 11:59 pm" in hub.state["marks"]["now_card:flag"]["what"]
    before = dict(hub.state["marks"])
    hub.publish("nowcard.updated", now_card)  # the same card again changes nothing, so it marks nothing
    hub.publish("day.updated", day)
    assert hub.state["marks"] == before
    events = drain(queue)
    assert [e["type"] for e in events].count("marks.updated") == 3
    assert all(detail("marks_updated", e["data"]) == [] for e in events if e["type"] == "marks.updated")
    assert errors("marks", hub.state["marks"]) == [] and errors("state", hub.snapshot()) == []


def test_what_jarvis_said_and_finished_jobs_stay_on_the_rail():
    hub = Hub(bare_state())
    for i in range(12):
        hub.publish("caption.show", {"text": f"Line {i}.", "source": {"kind": "canvas", "label": "Canvas"}, "ttl_ms": 1000})
    hub.publish("caption.show", {"text": "“Plan my week.”", "source": {"kind": "you", "label": "You · just now"}})  # his words, not Jarvis's
    hub.publish("caption.show", {"text": ""})
    hub.publish("toast", {"id": "t-1", "kind": "info", "text": "Less of this from now on.", "ttl_ms": 1000})
    later(hub, seconds=30)  # the caption and the toast have left the screen
    body = hub.snapshot()
    assert body["caption"] is None and body["toasts"] == []
    said = body["rail"]["slots"]["jarvis"]["said"]
    assert len(said) == 10 and [said[0]["text"], said[0]["kind"], said[1]["text"], said[-1]["text"]] == ["Less of this from now on.", "toast", "Line 11.", "Line 3."]
    assert body["marks"]["jarvis:said"]["what"] == "Jarvis said: Less of this from now on."
    hub.publish("job.progress", {"id": "job-sync", "label": "Syncing Canvas", "state": "running", "progress": 0.5})
    assert "job-sync" not in hub.state["marks"]
    hub.publish("job.progress", {"id": "job-sync", "label": "Syncing Canvas", "state": "done", "progress": 1})
    hub.publish("job.progress", {"id": "job-plan", "label": "Planning your week", "state": "failed"})
    assert hub.state["jobs"] == []
    jobs = [(i["ref"], i.get("state")) for i in hub.state["rail"]["slots"]["jarvis"]["items"]]
    assert jobs == [("job-plan", None), ("job-sync", "done")]
    assert hub.state["marks"]["job-sync"]["what"] == "Finished: Syncing Canvas" and hub.state["marks"]["job-plan"]["what"] == "Did not finish: Planning your week"
    assert errors("state", hub.snapshot()) == []


def test_marks_clear_only_when_he_has_seen_them(client):
    hub = client.app.state.hub
    hub.mark("due-pps7", "Due moved Wed 8 pm → Thu 11:59 pm")
    hub.mark("d-review", "Review GE 122 lecture 21 moved 4 pm → 5:30 pm")
    hub.mark("ap-week", "Ran out unanswered")
    assert set(client.get("/api/state").json()["marks"]) == {"due-pps7", "d-review", "ap-week"}  # being shown isn't being seen
    queue = hub.subscribe()
    assert client.post("/api/act", json={"action": "seen", "target": "due-pps7"}).json() == {"ok": True}
    assert set(hub.state["marks"]) == {"d-review", "ap-week"}
    assert client.post("/api/act", json={"action": "seen", "target": "due-pps7"}).json() == {"ok": True}  # twice: nothing more
    assert [e["type"] for e in drain(queue)] == ["marks.updated"]
    assert client.post("/api/act", json={"action": "seen", "target": "all"}).json() == {"ok": True}  # "mark all seen"
    assert client.get("/api/state").json()["marks"] == {}


def test_things_idle_for_a_week_fold_into_parked(reducers_only):
    hub = Hub(bare_state())
    hub.publish("window.push", {"id": "w-a", "type": "file", "title": "PPS 6", "ref": "file-pps6"})
    hub.act("close", "w-a")
    later(hub, days=6)
    hub.publish("window.push", {"id": "w-b", "type": "file", "title": "PPS 7", "ref": "file-pps7"})
    hub.act("close", "w-b")
    later(hub, days=1, minutes=1)
    slots = hub.snapshot()["rail"]["slots"]
    assert [i["ref"] for i in slots["homework"]["items"]] == ["file-pps7"]
    assert [(i["ref"], i["from"], i["state"]) for i in slots["parked"]["items"]] == [("file-pps6", "homework", "parked")] and slots["parked"]["count"] == 1
    assert docked(hub.state) == ["w-b", "w-a"]  # folded, not lost: it can still be recalled
    assert errors("state", hub.snapshot()) == []


def test_work_threads_keep_a_resume_point(client):
    hub = client.app.state.hub
    thread = {"id": "th-pps7", "kind": "pdf", "ref": "file-pps7", "branch": "ge-122", "title": "PPS 7", "done": ["Q1"], "viewed": []}
    hub.publish("thread.updated", {"thread": thread})
    act = lambda action, args=None: client.post("/api/act", json={"action": action, "target": "th-pps7", "args": args or {}}).json()  # noqa: E731
    assert act("resume_accept") == {"ok": False, "message": "There's no saved spot for that yet."}
    assert act("resume_save", {"page": 3, "y": 412.5, "label": "Q7"}) == {"ok": True}  # a local note: no approval involved
    saved = client.get("/api/state").json()["threads"][0]
    assert saved["resume"] == {"page": 3, "y": 412.5, "label": "Q7", "source": "inferred", "at": saved["updated"]}
    assert act("resume_save", {"page": "three", "label": "Q7"})["ok"] is False and act("resume_save", {"page": 4})["ok"] is False
    assert act("resume_accept") == {"ok": True}
    body = client.get("/api/state").json()
    assert body["threads"][0]["resume"]["source"] == "confirmed" and body["threads"][0]["resume"]["page"] == 3
    body.pop("demo")
    assert errors("state", body) == [] and errors("thread", body["threads"][0]) == []
    assert client.post("/api/act", json={"action": "resume_save", "target": "th-none", "args": {"label": "Q1"}}).json()["ok"] is False
    assert detail("thread_updated", {"thread": body["threads"][0]}) == [] and detail("thread_updated", {"id": "th-pps7", "archived": True}) == []
    hub.publish("thread.updated", {"id": "th-pps7", "archived": True})
    assert hub.state["threads"] == []


def test_the_focus_cue_lights_a_thing_and_lets_go():
    from datetime import timedelta

    hub = Hub(load_state())
    until = (hub.now() + timedelta(seconds=2)).isoformat(timespec="seconds")
    event = hub.publish("ui.focus", {"ref": "due-pps7", "until": until})
    assert errors("event", event) == [] and errors("focus", event["data"]) == []
    assert hub.snapshot()["focus"] == {"ref": "due-pps7", "until": until}
    later(hub, seconds=3)
    hub.publish("orb.state", {"state": "idle"})
    assert hub.state["focus"] is None
    hub.publish("ui.focus", {"ref": "w-a", "until": (hub.now() + timedelta(seconds=2)).isoformat(timespec="seconds")})
    hub.publish("ui.focus", {"ref": None})
    assert hub.state["focus"] is None


def test_a_v1_state_still_loads():
    state = load_state()
    for key in ("rail", "marks", "threads", "focus"):
        state.pop(key)
    state["v"] = 1
    hub = Hub(state)
    assert hub.state["v"] == 2 and set(hub.state["rail"]["slots"]) == set(SLOTS) and errors("state", hub.snapshot()) == []
    bare = {"windows": [note(0)], "approvals": []}
    apply_event(bare, "window.dock", {"id": "w-0"})  # the reducer alone copes with a state that has no Rail yet
    assert bare["windows"] == [] and docked(ensure_v2(bare)) == ["w-0"]


def test_thumb_and_file_routes_answer_404_for_unknown_keys_and_serve_ranges(client, tmp_path, monkeypatch):
    import sys
    import types

    assert client.get("/api/thumb/not-made.webp").status_code == 404  # an unknown key (N5a serves the known ones)
    missing = client.get("/api/file/file-nope", headers={"Range": "bytes=0-9"})
    assert missing.status_code == 404 and missing.headers["accept-ranges"] == "bytes"
    assert client.get("/api/file/..%2F..%2Fpyproject.toml").status_code == 404 and client.get("/api/thumb/a..b").status_code == 404
    # the owning packages only add a module with one function; the routes then serve it, with HTTP Range for the reader
    (tmp_path / "pps7.pdf").write_bytes(b"0123456789")
    threads = types.ModuleType("jarvis_hub.threads")
    threads.file_path = lambda file_id: tmp_path / "pps7.pdf" if file_id == "file-pps7" else None
    monkeypatch.setitem(sys.modules, "jarvis_hub.threads", threads)
    part = client.get("/api/file/file-pps7", headers={"Range": "bytes=2-5"})
    assert (part.status_code, part.content, part.headers["content-range"]) == (206, b"2345", "bytes 2-5/10")
    assert client.get("/api/file/file-other").status_code == 404


def test_a_wake_carries_when_the_last_wake_was(client):
    hub = client.app.state.hub
    first = hub.publish("orb.state", {"state": "listening", "level": 0.7})["data"]
    assert first["last_wake"] is None and errors("orb_state", first) == []  # the first wake: the full beat
    hub.publish("orb.state", {"state": "thinking"})
    assert "last_wake" not in hub.publish("orb.state", {"state": "listening"})["data"]  # still the same exchange: no wake
    hub.publish("orb.state", {"state": "idle"})
    again = hub.publish("orb.state", {"state": "listening"})["data"]
    assert again["last_wake"] and errors("orb_state", again) == []
    hub.reset()
    assert hub.publish("orb.state", {"state": "listening"})["data"]["last_wake"] is None


def test_sounds_and_address_are_settings(client):
    assert client.get("/api/state").json()["settings"]["earcons"] == "minimal"
    assert client.post("/api/act", json={"action": "set", "target": "earcons", "args": {"value": "full"}}).json() == {"ok": True}
    assert client.post("/api/act", json={"action": "set", "target": "address", "args": {"value": "sir"}}).json() == {"ok": True}
    settings = client.get("/api/state").json()["settings"]
    assert (settings["earcons"], settings["address"]) == ("full", "sir") and errors("settings", settings) == []
    assert client.post("/api/act", json={"action": "set", "target": "earcons", "args": {"value": "loud"}}).json()["ok"] is False
    for orb in ({"state": "standby"}, {"state": "alert", "alert": "crit"}, {"state": "idle", "alert": "warn"}):
        assert errors("orb_state", orb) == []
    assert errors("orb_state", {"state": "wake"})  # a wake is never a state


def test_what_the_hub_says_in_toasts_follows_the_register(client):
    """HUD v2 §9.2: no "Got it", no "Okay", no jingles; a "no" is answered by the window leaving, with no words."""
    from jarvis_hub.demo.lines import register_problems

    hub = client.app.state.hub
    queue = hub.subscribe()
    hub.publish("approval.pending", {**hub._initial["approvals"][0], "id": "ap-x", "status": "pending"})
    client.post("/api/act", json={"action": "decline", "target": "ap-x"})
    hub.publish("approval.pending", {**hub._initial["approvals"][0], "id": "ap-y", "status": "pending"})
    client.post("/api/act", json={"action": "change", "target": "ap-y", "args": {"text": "after 7 pm"}})
    client.post("/api/act", json={"action": "less", "target": "f-1"})
    client.post("/api/act", json={"action": "wrong", "target": "f-1"})
    toasts = [e["data"]["text"] for e in drain(queue) if e["type"] == "toast"]
    assert len(toasts) == 3  # nothing for the "no"
    for text in toasts:
        low = text.lower()
        assert not any(bad in low for bad in ("got it", "okay", "booked", "thanks", "!")), text
        assert [p for p in register_problems(text) if "decline" not in p] == [], text


def test_a_reading_session_goes_through_the_threads_rules(client, tmp_path, monkeypatch):
    """resume_save with a session: jarvis_hub/threads.py decides the spot (N6); an explicit spot is saved as given."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    hub = client.app.state.hub
    thread = {"id": "th-x", "kind": "pdf", "ref": "file-x", "branch": "ge-122", "title": "Set X", "resume": None, "done": [], "viewed": [], "state": "open"}
    hub.publish("thread.updated", {"thread": thread})
    act = lambda args: client.post("/api/act", json={"action": "resume_save", "target": "th-x", "args": args}).json()
    session = {"file": "file-x", "seconds": 240, "dwell": {"Q3": 200}, "path": ["Q2", "Q3"], "visible": ["Q3", "Q4"], "page": 2, "y": 10, "current": "Q3"}
    assert act({"label": "Q3", "page": 2, "y": 10.0, "session": session}) == {"ok": True}
    saved = next(t for t in hub.state["threads"] if t["id"] == "th-x")
    assert saved["resume"]["source"] == "inferred" and saved["resume"]["page"] == 2 and saved["state"] == "paused"
    assert errors("thread", saved) == []
    assert act({"label": "12:40", "seconds": 760}) == {"ok": True}  # a video's place
    assert next(t for t in hub.state["threads"] if t["id"] == "th-x")["resume"]["seconds"] == 760
    assert act({"label": "Q3", "session": "nonsense"}) == {"ok": True}  # an odd session never loses the spot
