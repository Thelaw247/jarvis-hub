"""The Rail's own logic (jarvis_hub/rail.py, N4): things, not windows; one item per ref; gauges; nothing deleted."""
import copy
import json
from datetime import datetime, timedelta

from jarvis_hub.demo.fixtures import bare_state, load_state
from jarvis_hub.events import Hub, ensure_v2
from jarvis_hub.rail import refresh
from tests.test_contracts import validator

NOW = datetime(2026, 11, 16, 15, 40)  # the fixture's clock


def errors(name, doc):
    return [f"{list(e.path)}: {e.message}" for e in validator(name).iter_errors(doc)]


def fresh():
    return ensure_v2(bare_state())  # the Rail's rules start from a day with nothing tracked yet


def refs(state, slot):
    return [i["ref"] for i in state["rail"]["slots"][slot]["items"]]


def item(state, ref):
    return next(i for s in state["rail"]["slots"].values() for i in s["items"] if i["ref"] == ref)


def every_ref(state):
    return [i["ref"] for s in state["rail"]["slots"].values() for i in s["items"]]


def test_slots_are_built_from_what_the_hub_knows_and_match_the_contract():
    s = fresh()
    refresh(s, NOW)
    assert errors("rail", s["rail"]) == [] and errors("state", s) == []
    assert refs(s, "yes") == ["ap-week"] and item(s, "ap-week")["state"] == "yes"
    assert set(refs(s, "today")) == {i["id"] for i in s["day"]["items"]}
    assert set(refs(s, "homework")) == {"due-pps7", "due-lab4", "due-webwork", "due-memo", "due-prelab5"}  # deduped across cards
    assert item(s, "due-pps7")["title"] == "GE 122 · PPS 7"  # the fuller title of the copies
    assert item(s, "due-pps7")["detail"] == "Due Wed 8 pm · 50% done"
    assert refs(s, "messages") == [] and s["rail"]["slots"]["parked"]["count"] == 0


def test_gauges_count_done_and_the_worst_state():
    s = fresh()
    refresh(s, NOW)
    slots = s["rail"]["slots"]
    assert slots["today"]["done"] == 0.67  # 4 of the 6 that are still today (the moved block doesn't count)
    assert slots["homework"]["done"] == round((0.5 + 0.4 + 0 + 0 + 1) / 5, 2)
    assert slots["yes"]["worst"] == "yes"
    assert slots["today"]["worst"] == "soon"  # the 4 pm review starts within 30 minutes
    assert slots["today"]["items"][0]["ref"] == "d-review"  # the worst state comes first
    assert "worst" not in slots["messages"] and "done" not in slots["yes"]


def test_due_items_turn_soon_then_critical_and_done_as_time_and_progress_move():
    s = fresh()
    refresh(s, NOW + timedelta(days=1))  # Tue 15:40: PPS 7 due Wed 8 pm is now within 48 h
    assert item(s, "due-pps7")["state"] == "soon"
    refresh(s, NOW + timedelta(days=2, hours=5))  # Wed 20:40: past due
    assert item(s, "due-pps7")["state"] == "critical" and item(s, "due-pps7")["detail"].startswith("Overdue since Wed 8 pm")
    assert s["rail"]["slots"]["homework"]["worst"] == "critical"
    for card in s["cards"].values():
        for due in card.get("due", []):
            if due["id"] == "due-pps7":
                due["progress"] = 1
    refresh(s, NOW + timedelta(days=2, hours=5))
    assert item(s, "due-pps7")["state"] == "done"


def test_running_jobs_sit_under_jarvis_and_spoken_lines_are_capped_at_ten():
    s = fresh()
    s["jobs"] = [{"id": "j-canvas", "label": "Checking Canvas", "state": "running", "progress": 0.4}]
    s["rail"]["slots"]["jarvis"]["said"] = [{"text": f"Line {i}", "at": "2026-11-16T15:00:00", "kind": "caption"} for i in range(12)]
    refresh(s, NOW)
    assert item(s, "j-canvas")["slot"] == "jarvis" and item(s, "j-canvas")["state"] == "jarvis" and item(s, "j-canvas")["detail"] == "40%"
    assert len(s["rail"]["slots"]["jarvis"]["said"]) == 10 and s["rail"]["slots"]["jarvis"]["worst"] == "jarvis"


def test_one_item_per_ref_a_docked_window_merges_with_its_thing():
    s = fresh()
    window = {"id": "w-due-pps7", "type": "countdown", "title": "Due", "ref": "due-pps7", "docked": True, "slot": "homework"}
    s["rail"]["slots"]["homework"]["items"] = [{"ref": "due-pps7", "slot": "homework", "kind": "due", "title": "Due", "at": "2026-11-16T15:30:00", "window": window}]
    refresh(s, NOW)
    assert every_ref(s).count("due-pps7") == 1
    merged = item(s, "due-pps7")
    assert merged["window"] == window and merged["at"] == "2026-11-16T15:30:00" and merged["title"] == "GE 122 · PPS 7"
    # docked by hand into another slot: it stays where he put it
    s = fresh()
    s["rail"]["slots"]["today"]["items"] = [{"ref": "due-pps7", "slot": "today", "kind": "due", "title": "Due", "at": "2026-11-16T15:30:00", "window": window}]
    refresh(s, NOW)
    assert "due-pps7" in refs(s, "today") and "due-pps7" not in refs(s, "homework")


def test_threads_join_homework_with_their_resume_point():
    s = fresh()
    s["threads"] = [json.load(open("contracts/examples/thread.json", encoding="utf-8"))]
    refresh(s, NOW)
    t = item(s, "file-pps7")
    assert (t["slot"], t["kind"], t["state"], t["detail"]) == ("homework", "thread", "progress", "Q7 · paused Sun 9:14 pm")
    assert t["thumb"]["alt"].startswith("Page 3")


def test_refresh_is_deterministic_and_never_removes_a_thing():
    s = fresh()
    refresh(s, NOW)
    once = json.dumps(s["rail"])
    refresh(s, NOW)
    assert json.dumps(s["rail"]) == once  # an event that changes nothing on the Rail sends no rail.updated
    before = set(every_ref(s))
    s["approvals"][0]["status"] = "expired"  # ran out: it stays, parked under Your yes
    s["cards"] = {}  # the cards are gone for a moment: the homework stays on the Rail
    refresh(s, NOW)
    assert before <= set(every_ref(s))
    assert item(s, "ap-week")["slot"] == "yes" and item(s, "ap-week")["state"] == "parked"


def test_idle_for_seven_days_folds_into_parked_and_comes_back_when_it_wants_him():
    s = fresh()
    refresh(s, NOW)
    later = NOW + timedelta(days=8)
    s["day"]["items"] = []  # a new day: no classes yet
    s["cards"] = {"school": {"due": [{"id": "due-memo", "title": "GE 122 · Design memo 3", "due": "2026-11-25T23:59:00", "progress": 0}]}}
    refresh(s, later)
    parked = s["rail"]["slots"]["parked"]
    assert "due-webwork" in refs(s, "parked") and parked["count"] == len(parked["items"])
    assert item(s, "due-webwork")["from"] == "homework" and item(s, "due-webwork")["state"] == "parked"
    assert "d-math" not in every_ref(s)  # last week's finished class has left Today (done)
    assert "d-pps" in refs(s, "parked")  # last week's block that never got done is folded, not lost
    assert item(s, "due-memo")["slot"] == "homework" and item(s, "due-memo")["state"] == "soon"  # due in 48 h: it wants him, so it's back
    assert errors("rail", s["rail"]) == []


def test_tier_two_branches_mark_their_items():
    s = fresh()
    s["branches"].append({**copy.deepcopy(s["branches"][0]), "id": "money", "name": "Money", "tier": 2})
    s["cards"]["money"] = {"due": [{"id": "due-rent", "title": "Rent", "due": "2026-11-30T12:00:00", "progress": 0, "branch_id": "money",
                                    "source": {"kind": "you", "label": "You"}}]}
    refresh(s, NOW)
    assert item(s, "due-rent")["tier"] == 2 and "tier" not in item(s, "due-pps7")


def test_the_hub_refreshes_the_rail_from_the_start_and_tells_every_screen_only_about_changes():
    hub = Hub(load_state())
    assert "ap-week" in [i["ref"] for i in hub.state["rail"]["slots"]["yes"]["items"]]  # the first state already has the whole Rail
    queue = hub.subscribe()
    hub.publish("orb.state", {"state": "listening"})  # nothing on the Rail changed: no rail.updated
    assert all(queue.get_nowait()["type"] != "rail.updated" for _ in range(queue.qsize()))
    hub.publish("job.progress", {"id": "job-x", "label": "Checking Canvas", "state": "running"})
    rails = [e["data"] for e in (queue.get_nowait() for _ in range(queue.qsize())) if e["type"] == "rail.updated"]
    assert len(rails) == 1 and "job-x" in [i["ref"] for i in rails[0]["slots"]["jarvis"]["items"]]
    hub.reset()
    assert "ap-week" in [i["ref"] for i in hub.state["rail"]["slots"]["yes"]["items"]]
    assert errors("state", hub.snapshot()) == []
