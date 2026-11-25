"""Contracts v2: every schema is valid, every example passes its schema, and the demo state hangs together."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent / "contracts"
SCHEMAS = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(ROOT.glob("*.schema.json"))}
REGISTRY = Registry().with_resources((name, Resource.from_contents(doc)) for name, doc in SCHEMAS.items())
NAMES = [n.removesuffix(".schema.json") for n in SCHEMAS if n != "common.schema.json"]


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(SCHEMAS[f"{name}.schema.json"], registry=REGISTRY)


def example(name: str):
    return json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))


def test_the_plan_contracts_all_exist():
    planned = {"now_card", "branch", "branch_card", "fact", "action", "approval", "window", "orb_state", "job", "caption",
               "toast", "settings", "metrics"}
    assert planned <= set(NAMES)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_schema_is_valid(name):
    Draft202012Validator.check_schema(SCHEMAS[name])


@pytest.mark.parametrize("name", NAMES)
def test_example_matches_schema(name):
    errors = [f"{list(e.path)}: {e.message}" for e in validator(name).iter_errors(example(name))]
    assert errors == []


def test_invented_fields_are_rejected():
    bad = {**example("fact"), "mood": "happy"}
    assert list(validator("fact").iter_errors(bad))


def test_event_types_cover_the_plan():
    planned = {"orb.state", "nowcard.updated", "branch.updated", "window.push", "window.close", "caption.show",
               "approval.pending", "approval.resolved", "activity.added", "job.progress", "toast", "presence.changed"}
    assert planned <= set(SCHEMAS["event.schema.json"]["properties"]["type"]["enum"])


def test_demo_state_references_resolve():
    state = example("state")
    branches = {b["id"] for b in state["branches"]}
    facts = {f["id"] for f in state["facts"]}
    actions = {a["id"] for a in state["actions"]}
    assert all(b["parent"] is None or b["parent"] in branches for b in state["branches"])
    assert all(f["branch_id"] in branches for f in state["facts"])
    for branch_id, card in state["cards"].items():
        assert branch_id in branches and card["branch_id"] == branch_id
        assert set(card.get("key_facts", [])) <= facts and set(card.get("recent", [])) <= actions


def test_psychology_limits_in_the_demo_data():
    state = example("state")
    assert all(len(a["consequences"]) <= 4 for a in state["approvals"])
    assert len(state["now_card"].get("gaps", [])) <= 3


# ---- contracts v2 (hub v0.3.0, Night HUD) ---------------------------------------------------------------------
SLOTS = ["yes", "today", "homework", "messages", "jarvis", "parked"]
THUMB = {"src": "/api/thumb/file-pps7-p3.webp", "kind": "page", "alt": "Page 3 of PPS 7, question 7"}


def problems(name, doc, part=None):
    schema = {"$ref": f"{name}.schema.json{'#/$defs/' + part if part else ''}"}
    return [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema, registry=REGISTRY).iter_errors(doc)]


def test_the_v2_contracts_all_exist():
    assert {"rail", "marks", "thread", "focus"} <= set(NAMES)
    assert {"thumb", "glance", "slot"} <= set(SCHEMAS["common.schema.json"]["$defs"])


def test_the_version_is_2_in_the_state_and_the_envelope():
    assert example("state")["v"] == 2 and example("event")["v"] == 2
    assert problems("state", {**example("state"), "v": 1}) and problems("event", {**example("event"), "v": 1})


def test_v2_event_types_and_actions():
    types = set(SCHEMAS["event.schema.json"]["properties"]["type"]["enum"])
    assert {"window.dock", "window.order", "rail.updated", "marks.updated", "thread.updated", "ui.focus"} <= types
    actions = set(SCHEMAS["act.schema.json"]["properties"]["action"]["enum"])
    assert {"dock", "recall", "order", "seen", "archive", "resume_save", "resume_accept"} <= actions
    assert {"close", "close_all", "move"} <= actions  # v1 names stay; the hub docks or reorders when it gets them


@pytest.mark.parametrize(("shape", "good", "bad"), [
    ("window_dock", [{"id": "w-pps7"}, {"all": True, "reason": "cleared"}, {"id": "w-pps7", "slot": "homework", "reason": "lifetime"}],
     [{}, {"id": "w-pps7", "slot": "inbox"}, {"id": "w-pps7", "reason": "deleted"}, {"all": False}]),
    ("window_order", [{"ids": ["w-b", "w-a"]}, {"ids": []}], [{}, {"ids": "w-a"}, {"ids": ["w-a"], "close": True}]),
    ("marks_updated", [{"marks": {}}, {"marks": {"due-pps7": {"what": "Due moved Wed 8 pm → Thu 11:59 pm", "at": "2026-11-16T15:12:00"}}}],
     [{}, {"marks": {"due-pps7": {"what": "Moved"}}}, {"marks": {"due-pps7": {"what": "Moved", "at": "2026-11-16T15:12:00", "count": 3}}}]),
    ("thread_updated", [{"id": "th-pps7", "archived": True}], [{}, {"id": "th-pps7"}, {"thread": {"id": "th-pps7"}}]),
])
def test_v2_event_data_shapes(shape, good, bad):
    assert [problems("event", doc, shape) for doc in good] == [[] for _ in good]
    assert all(problems("event", doc, shape) for doc in bad)
    assert problems("event", {"thread": example("thread")}, "thread_updated") == []


def test_windows_can_dock_into_a_rail_slot():
    window = {**example("window"), "docked": True, "slot": "homework", "thumb": THUMB}
    assert problems("window", window) == []
    assert problems("window", {**window, "slot": "inbox"}) and problems("window", {**window, "docked": "yes"})
    assert problems("window", example("window")) == []  # a v1 window, with neither, is still a window


def test_the_rail_has_six_fixed_slots_and_items_by_ref():
    rail = example("rail")
    assert list(rail["slots"]) == SLOTS == SCHEMAS["common.schema.json"]["$defs"]["slot"]["enum"]
    for name in SLOTS:
        assert problems("rail", {"slots": {k: v for k, v in rail["slots"].items() if k != name}})  # all six, always
    assert problems("rail", {"slots": {**rail["slots"], "inbox": {"items": []}}})
    item = rail["slots"]["homework"]["items"][0]
    assert problems("rail", item, "item") == []
    assert problems("rail", {k: v for k, v in item.items() if k != "ref"}, "item") and problems("rail", {**item, "state": "new"}, "item")
    assert all(i["slot"] == name for name in SLOTS for i in rail["slots"][name]["items"])
    assert rail["slots"]["yes"]["items"][0]["window"]["docked"] is True  # a docked window is kept whole, so it can be recalled
    line = rail["slots"]["jarvis"]["said"][0]
    assert problems("rail", {**rail["slots"]["jarvis"], "said": [line] * 10}, "slot") == []
    assert problems("rail", {**rail["slots"]["jarvis"], "said": [line] * 11}, "slot")  # the last 10 lines, no more


def test_marks_are_what_and_at_by_ref():
    assert problems("marks", {"due-pps7": {"what": "Due moved Wed 8 pm → Thu 11:59 pm", "at": "2026-11-16T15:12:00"}}) == []
    assert problems("marks", {"due-pps7": {"what": "Due moved"}}) and problems("marks", {"due-pps7": {"at": "2026-11-16T15:12:00"}})
    assert problems("marks", {"due-pps7": {"what": "x", "at": "3 pm"}}) and problems("marks", {"due-pps7": {"what": "x", "at": "2026-11-16T15:12:00", "badge": 3}})


def test_threads_carry_a_resume_point():
    thread = example("thread")
    assert set(SCHEMAS["thread.schema.json"]["required"]) == {"id", "kind", "ref", "branch", "title", "done", "viewed"}
    assert set(thread["resume"]) == {"page", "y", "label", "source", "at"}
    assert problems("thread", {**thread, "resume": {**thread["resume"], "source": "confirmed"}}) == []
    assert problems("thread", {**thread, "resume": None}) == []  # a fresh thread has no spot yet
    assert problems("thread", {**thread, "resume": {**thread["resume"], "source": "sure"}})
    assert problems("thread", {**thread, "resume": {"page": 3}}) and problems("thread", {**thread, "kind": "homework"})
    assert problems("thread", {k: v for k, v in thread.items() if k != "done"}) and problems("thread", {**thread, "time_per_question": [40]})


def test_things_carry_a_thumb_with_alt_text():
    assert problems("common", THUMB, "thumb") == []
    for missing in ("src", "kind", "alt"):
        assert problems("common", {k: v for k, v in THUMB.items() if k != missing}, "thumb")
    assert problems("common", {**THUMB, "kind": "photo"}, "thumb")
    state = example("state")
    assert problems("branch", {**state["branches"][0], "thumb": THUMB}) == []
    assert problems("approval", {**example("approval"), "thumb": THUMB}) == []
    assert problems("now_card", {**state["files"][0], "thumb": THUMB}, "file") == []
    assert problems("now_card", {**example("now_card"), "next_up": {**example("now_card")["next_up"], "thumb": THUMB}}) == []
    day = example("day")
    assert problems("day", {**day, "items": [{**day["items"][0], "thumb": THUMB}]}) == []
    assert example("thread")["thumb"]["alt"] and example("rail")["slots"]["homework"]["items"][0]["thumb"]["alt"]


def test_the_day_dial_uses_full_iso_times():
    day = example("day")
    assert day["dial"] and all("T" in arc["start"] for arc in day["dial"])
    overnight = {"id": "dial-late", "kind": "block", "start": "2026-11-16T23:30:00", "end": "2026-11-17T00:30:00", "title": "Late review", "state": "upcoming"}
    assert problems("day", {**day, "dial": [overnight]}) == []  # it crosses midnight, which HH:MM could not say
    assert problems("day", {**day, "dial": [{**overnight, "start": "23:30"}]}) and problems("day", {**day, "dial": [{**overnight, "end": "00:30"}]})
    assert problems("day", {**day, "dial": [{**overnight, "state": "late"}]})
    assert problems("day", {k: v for k, v in day.items() if k != "dial"}) == []  # v1 days, without a dial, still pass


def test_the_now_card_reads_the_moment():
    card = example("now_card")
    for moment in ("rushed", "between", "settled", "heads_down", "others", "game"):
        assert problems("now_card", {**card, "moment": moment}) == []
    assert problems("now_card", {**card, "moment": "busy"})
    assert problems("now_card", {k: v for k, v in card.items() if k != "moment"}) == []


def test_the_focus_cue():
    assert problems("focus", {"ref": "due-pps7", "until": "2026-11-16T15:40:44"}) == [] and problems("focus", {"ref": None}) == []
    assert problems("focus", {"until": "2026-11-16T15:40:44"}) and problems("focus", {"ref": "due-pps7", "until": "soon"})


def test_the_state_carries_the_rail_marks_threads_and_focus():
    state = example("state")
    assert set(state["rail"]["slots"]) == set(SLOTS) and state["focus"] is None
    assert state["marks"] and any(t["resume"] and t["resume"]["label"] == "Q7" for t in state["threads"])  # N7's demo day
    for key in ("rail", "marks", "threads"):
        assert problems("state", {k: v for k, v in state.items() if k != key})
    full = {**state, "rail": example("rail"), "marks": example("marks"), "threads": [example("thread")], "focus": example("focus")}
    assert problems("state", full) == []
    assert all(not w.get("docked") for w in state["windows"])  # windows on screen are never docked; docked ones live on the Rail
