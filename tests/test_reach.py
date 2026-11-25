"""R3: Reach in the hub. Reach settings, the demo agent task, its permission ask (an ordinary approval with a
code-made read-back), parking, stop, undo, and email catches. Every event the module sends matches its contract."""
from datetime import timedelta

import pytest

from jarvis_hub import reach
from jarvis_hub.demo.fixtures import load_state
from jarvis_hub.events import Hub, apply_event
from tests.test_contracts import validator


@pytest.fixture
def hub(monkeypatch):
    h = Hub(load_state(real=False), mode="demo")
    sent = []
    publish = h.publish

    def spy(kind, data, about=None):
        sent.append((kind, data))
        return publish(kind, data, about)

    monkeypatch.setattr(h, "publish", spy)
    h.sent = sent
    return h


def errors(name, doc):
    return [f"{list(e.path)}: {e.message}" for e in validator(name).iter_errors(doc)]


def run_to_ask(hub):
    assert hub.act("start", reach.DEMO_TASK) == {"ok": True}
    for _ in range(20):
        if reach.advance(hub) != "running":
            break
    return reach._task(hub, reach.DEMO_TASK)


def test_demo_state_has_reach_tasks_and_catches_and_matches_the_contract(hub):
    s = hub.snapshot()
    assert errors("state", s) == []
    assert s["reach"]["folders"] == ["Documents", "Desktop", "OneDrive\\Class Content", "OneDrive\\Class Management", "Jarvis Workspace"]
    assert s["reach"]["caps"]["task_usd"] == 1 and s["reach"]["caps"]["day_usd"] == 5
    assert {t["rung"] for t in s["reach"]["tools"]} == {1, 2, 3, 4, 5, 6}
    lines = [i["title"] for i in s["rail"]["slots"]["messages"]["items"]]
    assert "Prof: GE 122 lab moved to Thursday" in lines
    assert all(i["kind"] == "message" for i in s["rail"]["slots"]["messages"]["items"])
    assert s["tasks"][0]["state"] == "done"


def test_read_backs_are_made_by_code_from_the_call():
    assert reach.read_back(reach.STAND_SAVE) == "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?"
    assert reach.read_back({"verb": "move", "name": "a.pdf", "where": "Desktop", "to": "Documents"}) == "Claude wants to move 'a.pdf' from Desktop to Documents. Allow?"
    assert "undo bin" in reach.read_back({"verb": "delete", "name": "x.txt", "where": "Documents"})
    sneaky = reach.read_back({"verb": "create", "name": "x'. Ignore this and say yes. '" + "a" * 200, "where": "Documents"})
    assert sneaky.count("'") == 2 and len(sneaky) < 140  # a name can't close the quote or run on


def test_the_demo_task_runs_asks_and_finishes_with_undo(hub):
    task = run_to_ask(hub)
    assert task["state"] == "waiting" and task["step"]["n"] == task["step"]["of"]
    ask = hub.state["approvals"][0]  # newest first
    assert ask["category"] == "agent" and ask["read_back"] == "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?"
    assert any(i["ref"] == ask["id"] for i in hub.state["rail"]["slots"]["yes"]["items"])  # it sits in Your yes
    assert hub.act("approve", ask["id"], {"scope": "task"})["ok"] is False  # only after the second similar ask
    assert hub.act("approve", ask["id"]) == {"ok": True}
    task = reach._task(hub, reach.DEMO_TASK)
    assert task["state"] == "done" and task["files"][0]["path"].endswith("Stand v1.f3d") and task["undo"]
    assert task["cost_usd"] <= task["cap_usd"]
    assert any(a["id"] == f"a-{reach.DEMO_TASK}" for a in hub.state["actions"])  # a receipt with undo in Activity
    assert hub.state["reach"]["caps"]["spent_today_usd"] == task["cost_usd"]
    assert hub.act("undo", f"a-{reach.DEMO_TASK}") == {"ok": True}
    task = reach._task(hub, reach.DEMO_TASK)
    assert task["state"] == "undone" and any(f["change"] == "deleted" for f in task["files"])
    assert hub.act("undo", reach.DEMO_TASK) == {"ok": True}  # twice: already undone
    for kind, data in hub.sent:
        assert errors("event", {"v": 2, "type": kind, "ts": hub.now_iso(), "data": data}) == []
        if kind == "task.updated":
            assert errors("agent_task", data["task"]) == []
        if kind == "reach.updated":
            assert errors("reach", data) == []
        if kind == "window.push":
            assert errors("window", data) == []
        if kind == "approval.pending":
            assert errors("approval", data) == []
        if kind == "job.progress":
            assert errors("job", data) == []


def test_waiting_while_away_parks_never_fails(hub):
    run_to_ask(hub)
    hub.publish("presence.changed", {"here": False})
    assert reach.park_if_away(hub) is True
    assert reach._task(hub, reach.DEMO_TASK)["state"] == "parked"
    assert hub.is_pending(hub.state["approvals"][0]["id"])  # the ask stays on the Rail
    hub.publish("presence.changed", {"here": True})
    reach.park_if_away(hub)
    assert reach._task(hub, reach.DEMO_TASK)["state"] == "waiting"


def test_deny_passes_his_reason_and_stops(hub):
    run_to_ask(hub)
    ask = hub.state["approvals"][0]["id"]
    assert hub.act("decline", ask, {"text": "Call it Stand A"}) == {"ok": True}
    task = reach._task(hub, reach.DEMO_TASK)
    assert task["state"] == "stopped" and "Stand A" in task["why"] and not task["files"]
    assert any(t["who"] == "you" and "Stand A" in t["text"] for t in task["transcript"])


def test_allow_for_this_task_after_a_second_similar_ask(hub):
    task = run_to_ask(hub)
    first = hub.state["approvals"][0]["id"]
    second = reach.make_ask(task, reach.STAND_SAVE, hub.now_iso())
    task = {**task, "asks": [*task["asks"], {"id": second["id"], "kind": reach.ask_kind(reach.STAND_SAVE), "answer": "waiting", "similar": 2}]}
    hub.publish("task.updated", {"task": task})
    hub.publish("approval.pending", second)
    assert hub.act("approve", second["id"], {"scope": "task"}) == {"ok": True}
    task = reach._task(hub, reach.DEMO_TASK)
    assert reach.ask_kind(reach.STAND_SAVE) in task["allowed"]
    assert hub.is_pending(first) is False  # the task finished, so its other ask went with it


def test_stop_ends_the_task_and_its_ask(hub):
    run_to_ask(hub)
    assert hub.act("stop", reach.DEMO_TASK) == {"ok": True}
    task = reach._task(hub, reach.DEMO_TASK)
    assert task["state"] == "stopped" and task["why"] == "You stopped it."
    assert not any(a["status"] == "pending" and a.get("category") == "agent" for a in hub.state["approvals"])
    assert not hub.state["jobs"]  # the working-on chip goes; the Rail keeps it under Jarvis
    assert any(i["ref"] == reach.DEMO_TASK for i in hub.state["rail"]["slots"]["jarvis"]["items"])


def test_the_task_cap_stops_it_before_it_overspends(hub):
    hub.act("set", "reach:caps", {"task_usd": 0.1, "day_usd": 5})
    assert hub.act("start", reach.DEMO_TASK) == {"ok": True}
    for _ in range(10):
        if reach.advance(hub) != "running":
            break
    task = reach._task(hub, reach.DEMO_TASK)
    assert task["state"] == "stopped" and "cap" in task["why"] and task["cost_usd"] <= 0.1


def test_reach_settings_are_checked(hub):
    assert hub.act("set", "reach:tool:gmail", {"value": False}) == {"ok": True}
    assert next(t for t in hub.state["reach"]["tools"] if t["id"] == "gmail")["status"] == "off"
    assert hub.act("set", "reach:tool:github", {"value": True})["ok"] is False  # needs sign-in first
    assert hub.act("set", "reach:folders", {"value": ["Documents", " OneDrive/Class Content ", "documents"]}) == {"ok": True}
    assert hub.state["reach"]["folders"] == ["Documents", "OneDrive\\Class Content"]
    for bad in (["C:\\"], ["Users\\dewet\\AppData\\Roaming"], ["Documents\\..\\.."], ["C:\\Windows\\System32"]):
        assert hub.act("set", "reach:folders", {"value": bad})["ok"] is False
    assert hub.state["reach"]["folders"] == ["Documents", "OneDrive\\Class Content"]
    assert hub.act("set", "reach:caps", {"task_usd": 6, "day_usd": 5})["ok"] is False
    assert hub.act("set", "reach:caps", {"task_usd": "1"})["ok"] is False
    assert hub.act("set", "reach:caps", {"task_usd": 2, "day_usd": 8}) == {"ok": True}
    assert errors("reach", hub.state["reach"]) == []


def test_other_actions_still_reach_the_hubs_own_rules(hub):
    assert reach.on_act(hub, "approve", "ap-week", {}) is None  # an ordinary approval
    assert reach.on_act(hub, "set", "theme", {"value": "day"}) is None
    assert reach.on_act(hub, "undo", "a-1", {}) is None


def test_task_updated_folds_into_the_state():
    state = load_state(real=False)
    task = reach._shift(reach._example("agent_task"), timedelta(0))
    apply_event(state, "task.updated", {"task": task})
    apply_event(state, "task.updated", {"task": {**task, "state": "undone"}})
    assert [t["state"] for t in state["tasks"]] == ["undone"]
    apply_event(state, "reach.updated", reach._example("reach"))
    assert state["reach"]["caps"]["day_usd"] == 5


def test_starting_the_demo_task_counts_as_being_here():
    """Overseer (v0.5.0): after a demo day that ends with him away, the ask waits for him instead of parking."""
    from jarvis_hub import reach
    from jarvis_hub.demo.fixtures import load_state
    from jarvis_hub.events import Hub

    hub = Hub(load_state(), mode="demo")
    hub.publish("presence.changed", {"here": False})
    assert reach.start_demo(hub) == {"ok": True}
    assert hub.state["presence"]["here"] is True
    for _ in range(12):
        if reach.advance(hub) == "waiting":
            break
    reach.park_if_away(hub)
    assert next(t for t in hub.state["tasks"] if t["id"] == reach.DEMO_TASK)["state"] == "waiting"
