"""R2: the map window's demo data and its "show me where my lab is" answer (REACH §5.2)."""
import json
from pathlib import Path

import pytest

from jarvis_hub.demo.fixtures import load_state
from jarvis_hub.demo.places import WINDOW_ID, map_window, places_fixture, wants_map
from jarvis_hub.events import Hub
from tests.test_contracts import problems

ROOT = Path(__file__).resolve().parent.parent


def test_the_map_window_matches_its_contracts():
    window = map_window(load_state(real=False), focus="d-chem", pushed="2026-11-16T15:40:20")
    assert problems("window", window) == []
    assert problems("map", window["data"]) == []
    assert window["data"]["focus"] == "d-chem"


def test_the_contract_example_is_the_demo_day():
    # the scenes draw contracts/examples/map.json: it must be what the demo builds from the fixture
    example = json.loads((ROOT / "contracts" / "examples" / "map.json").read_text(encoding="utf-8"))
    assert map_window(load_state(real=False))["data"] == example


def test_the_day_runs_from_home_through_his_rooms_in_time_order():
    data = map_window(load_state(real=False))["data"]
    assert data["start"] == "maple"
    assert [(s["ref"], s["place"]) for s in data["stops"]] == [
        ("d-math", "arts"), ("d-ge", "engineering"), ("d-chem", "thorvaldson"), ("d-review", "maple")]
    lab = next(s for s in data["stops"] if s["ref"] == "d-chem")
    assert (lab["where"], lab["start"]) == ("Thorvaldson 173", "13:30")
    # a stop with no room (the review at his desk) takes the place the fixture names
    assert next(s for s in data["stops"] if s["ref"] == "d-review")["where"] == "Maple Hall"


def test_places_are_on_the_usask_campus():
    for place in places_fixture()["places"].values():
        assert 52.125 < place["lat"] < 52.137 and -106.645 < place["lon"] < -106.620, place["name"]


def test_an_unknown_focus_is_left_out():
    assert "focus" not in map_window(load_state(real=False), focus="d-nowhere")["data"]


@pytest.mark.parametrize("text, kind", [
    ("Show me where my lab is", "lab"), ("where's my lab?", "lab"), ("Where is the lab", "lab"),
    ("where is my next class", "class"), ("show me the map", None), ("Pull up the campus map", None),
])
def test_map_questions_are_recognised(text, kind):
    assert wants_map(text) == (True, kind)


@pytest.mark.parametrize("text", ["what's due this week", "open GE 122", "close that", ""])
def test_other_questions_are_not_map_questions(text):
    assert wants_map(text)[0] is False


def test_asking_where_the_lab_is_opens_the_map_and_says_where():
    hub = Hub(load_state(real=False))
    assert hub.act("ask", "jarvis", {"text": "Show me where my lab is"}) == {"ok": True}
    window = next(w for w in hub.state["windows"] if w["id"] == WINDOW_ID)
    assert window["type"] == "map" and window["data"]["focus"] == "d-chem" and window.get("pushed")
    assert hub.state["caption"]["text"] == "CHEM 142 lab 4 is in Thorvaldson 173."


def test_other_asks_still_get_the_demo_answer():
    hub = Hub(load_state(real=False))
    hub.act("ask", "jarvis", {"text": "what's the weather"})
    assert not any(w["type"] == "map" for w in hub.state["windows"])
    assert "demo mode" in hub.state["caption"]["text"]


def test_the_map_is_a_pure_view_closing_it_leaves_nothing_on_the_rail():
    hub = Hub(load_state(real=False))
    hub.act("ask", "jarvis", {"text": "show me the map"})
    hub.act("dock", WINDOW_ID, {"reason": "closed"})
    assert not any(w["id"] == WINDOW_ID for w in hub.state["windows"])
    items = [i for slot in hub.state["rail"]["slots"].values() for i in slot["items"]]
    assert not any((i.get("window") or {}).get("id") == WINDOW_ID for i in items)
