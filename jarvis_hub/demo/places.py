"""The map window's demo data (R2, REACH §5.2): where today's classes and labs are, and the route between them.

`places.json` holds the campus places (approximate lat/long) and the day's order (the place the day starts from,
then day item ids; an entry may name the place of an item with no room). `map_window()` turns that and the day in the state into a `map` window
(contracts/map.schema.json is its `data`), so the window needs no extra call when it arrives.
`answer()` is the demo's reply to "show me where my lab is" and similar: it pushes the window and says one line.
"""
from __future__ import annotations

import json
import re
from functools import cache

from ..settings import resource_path

WINDOW_ID = "w-map-today"
# what he asks → which day item kind the map leads with (None: the next place)
_ASKS = [
    (re.compile(r"\bwhere(?:'s| is)? (?:my |the )?lab\b|\bmy lab\b.*\bwhere\b|\bwhere my lab is\b"), "lab"),
    (re.compile(r"\bwhere(?:'s| is)? (?:my |the )?(?:next )?class\b|\bwhere my (?:next )?class is\b"), "class"),
    (re.compile(r"\b(?:show|open|pull up)(?: me)? (?:the |my )?(?:campus )?map\b|\bwhere am i going\b|\bwhere(?:'s| is) (?:my )?next\b"), None),
]


@cache
def places_fixture() -> dict:
    """places.json (the installer bundles it next to this module: build.ps1 --add-data)."""
    return json.loads(resource_path("jarvis_hub", "demo", "places.json").read_text(encoding="utf-8"))


def place_for(where: str | None, places: dict) -> str | None:
    """The place id whose `match` words appear in a day item's `where`, or None."""
    text = (where or "").lower()
    return next((pid for pid, p in places.items() if any(word in text for word in p["match"])), None)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def map_window(state: dict, focus: str | None = None, pushed: str | None = None) -> dict:
    """The `map` window for the state's day. `focus`: the day item id the map leads with (its pin is the bright
    one and the only one labelled); left out, the window leads with the next stop by the clock."""
    fixture = places_fixture()
    places = fixture["places"]
    items = {i["id"]: i for i in state["day"]["items"] if "id" in i}
    stops = []
    for entry in fixture["order"]["items"]:
        ref, fixed = (entry, None) if isinstance(entry, str) else (entry["ref"], entry.get("place"))
        item = items.get(ref)
        place = (place_for(item.get("where"), places) or fixed) if item else None
        if not item or not place:
            continue  # not on today's list, or nowhere we know: not on the map
        stop = {"ref": ref, "place": place, "title": item["title"], "where": item.get("where") or places[place]["name"], "start": item["start"]}
        if item.get("end"):
            stop["end"] = item["end"]
        stops.append(stop)
    stops.sort(key=lambda s: _minutes(s["start"]))
    used = {fixture["order"]["start"], *(s["place"] for s in stops)}
    data: dict = {
        "day": str(state["now"])[:10],
        "start": fixture["order"]["start"],
        "places": [{"id": pid, "name": p["name"], "short": p["short"], "lat": p["lat"], "lon": p["lon"], **({"home": True} if p.get("home") else {})}
                   for pid, p in places.items() if pid in used],
        "stops": stops,
    }
    if focus and any(s["ref"] == focus for s in stops):
        data["focus"] = focus
    window = {"id": WINDOW_ID, "type": "map", "title": "Map", "data": data}
    if pushed:
        window["pushed"] = pushed
    return window


def wants_map(text: str) -> tuple[bool, str | None]:
    """Is this a map question? → (yes, the kind of day item to lead with, or None for the next stop)."""
    t = re.sub(r"[^a-z' ]+", " ", str(text or "").lower()).strip()
    for pattern, kind in _ASKS:
        if pattern.search(t):
            return True, kind
    return False, None


def _focus_for(state: dict, kind: str | None, now_min: int) -> str | None:
    """The day item to lead with: the next (or current) one of that kind, else the last one of it today."""
    if kind is None:
        return None
    ones = sorted((i for i in state["day"]["items"] if i.get("kind") == kind and i.get("id") and i.get("start")), key=lambda i: _minutes(i["start"]))
    upcoming = [i for i in ones if _minutes(i.get("end") or i["start"]) > now_min]
    pick = upcoming[0] if upcoming else (ones[-1] if ones else None)
    return pick["id"] if pick else None


def answer(hub, text: str) -> bool:
    """The demo's answer to a map question: push the map window and say one line. → False when it isn't one."""
    asked, kind = wants_map(text)
    if not asked:
        return False
    try:
        places_fixture()
    except OSError:
        return False  # a build without the demo places: the usual demo answer
    now = hub.now()
    focus = _focus_for(hub.state, kind, now.hour * 60 + now.minute)
    window = map_window(hub.state, focus=focus, pushed=hub.now_iso())
    stops = window["data"]["stops"]
    lead = next((s for s in stops if s["ref"] == focus), None) or next((s for s in stops if _minutes(s.get("end") or s["start"]) > now.hour * 60 + now.minute), None)
    hub.publish("window.push", window)
    if lead:
        line = f"{lead['title'].split(' · ')[0]} is in {lead['where']}."
    else:
        line = "Nothing else on campus today."
    hub.publish("caption.show", {"text": line, "source": {"kind": "jarvis", "label": "Jarvis"}, "ttl_ms": 5000})
    return True
