"""R2: the map window on the Stage (REACH §5.2, HUD v2 §14.2 anatomy). Tests and screenshots always see the schematic."""
import pytest

IMPORT = 'import "./day-map/day-map.js";'


@pytest.fixture
def maphub(hub):
    """The hub, with the map component loaded even before the overseer adds its line to ui/components/index.js
    (once the line is there this changes nothing). Also records any request for map tiles."""
    hub.tiles = []

    def index(route):
        response = route.fetch()
        body = response.text()
        route.fulfill(response=response, body=body if "day-map/day-map.js" in body else f"{body}\n{IMPORT}\n")

    hub.page.route("**/components/index.js", index)
    hub.page.on("request", lambda r: hub.tiles.append(r.url) if "basemaps.cartocdn.com" in r.url else None)
    return hub


def window(hub):
    return hub.page.locator("jv-window[window-id=w-map-today]")


def test_the_map_window_has_one_anatomy(maphub):
    page = maphub.scene("stage-map", theme="night")
    win = window(maphub)
    win.wait_for()
    assert win.locator(".jv-window__name").inner_text().upper() == "MAP"
    assert win.locator(".jv-window__status").inner_text().upper() == "TODAY"
    assert win.locator(".jv-window__index").inner_text().replace(" ", "") == "3/4"
    # one hero (the map, edge to edge) and one supporting line
    assert win.locator("jv-day-map").count() == 1
    assert win.locator(".jv-day-map__line").inner_text() == "Next: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm"
    body, frame = win.locator(".jv-window__body").bounding_box(), win.bounding_box()
    assert abs(body["x"] - frame["x"]) <= 2 and abs(body["width"] - frame["width"]) <= 3
    # no buttons or links inside the window's content
    assert win.locator(".jv-window__body").locator("button, a, [role=button]").count() == 0
    # the label is only on the pin it leads with
    labels = win.locator(".jv-day-map__label")
    assert labels.count() == 1 and labels.inner_text().upper() == "THORVALDSON"
    assert win.locator(".jv-day-map__pin--lead").get_attribute("data-place") == "thorvaldson"
    assert maphub.problems == []
    assert page.evaluate("document.querySelector('jv-day-map .jv-day-map').getAttribute('role')") == "img"


def test_offline_it_is_a_labelled_schematic_and_asks_for_no_tiles(maphub):
    maphub.scene("stage-map", theme="night")
    win = window(maphub)
    win.wait_for()
    assert win.locator(".jv-day-map").get_attribute("data-mode") == "schematic"
    assert win.locator(".jv-day-map__credit").inner_text().lower() == "schematic · approximate"
    assert win.locator(".jv-day-map__tiles").count() == 0
    assert maphub.tiles == []


def test_it_draws_fast_and_never_moves(maphub):
    page = maphub.scene("component:day-map", theme="night")
    page.locator("jv-day-map").first.wait_for()
    draws = page.evaluate("[...document.querySelectorAll('jv-day-map')].map(m => Number(m.dataset.drawMs))")
    assert draws and max(draws) < 300
    assert page.evaluate("[...document.querySelectorAll('jv-day-map')].flatMap(m => m.getAnimations({ subtree: true })).length") == 0


def test_what_it_leads_with(maphub):
    page = maphub.scene("component:day-map", theme="night")
    page.locator("jv-day-map").first.wait_for()
    lines = page.locator(".jv-day-map__line").all_inner_texts()
    assert lines == [
        "Next: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm",
        "Earlier: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm",
        "Now: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm",
        "Next: Review GE 122 lecture 21 · Maple Hall · 4:00 pm",
        "Nothing else on campus today · Maple Hall",
    ]
    assert all(len(line) <= 90 for line in lines)


def test_the_tile_maths(maphub):
    maphub.scene("component:day-map", theme="night")
    out = maphub.page.evaluate("""import('/components/day-map/day-map.js').then(m => {
      const places = [{ lat: 52.1281, lon: -106.6405 }, { lat: 52.1326, lon: -106.6284 }, { lat: 52.1292, lon: -106.6334 }];
      const v = m.frame(places), tiles = m.tilesFor(v);
      const pts = places.map(p => v.at(p.lat, p.lon));
      return { z: v.z, scale: v.scale, n: tiles.length, inside: pts.every(([x, y]) => x >= 0 && x <= 600 && y >= 0 && y <= 360),
               covers: tiles.some(t => t.left <= 0 && t.top <= 0) && tiles.some(t => t.left + t.size >= 600 && t.top + t.size >= 360),
               same: m.tileUrl(tiles[0], v.z) === m.tileUrl(tiles[0], v.z), day: m.tileUrl({ x: 1, y: 2 }, 16, { theme: 'day', retina: true }),
               side: m.labelSide([300, 180], 10, [[300, 180], [500, 180]]) };
    })""")
    assert 15 <= out["z"] <= 17 and 0.5 < out["scale"] <= 1
    assert out["inside"] and out["covers"] and out["same"] and out["n"] <= 30
    assert out["day"] == "https://d.basemaps.cartocdn.com/light_nolabels/16/1/2@2x.png"
    assert out["side"] == "left"  # the route runs off to the right, so the label goes left


def test_asking_where_the_lab_is_opens_the_map_on_the_stage(maphub):
    page = maphub.open("#/stage", window="stage")
    page.evaluate("window.__jarvis.bridge.act('ask', 'jarvis', { text: 'Show me where my lab is' })")
    win = window(maphub)
    win.wait_for()
    assert "Thorvaldson 173" in win.locator(".jv-day-map__line").inner_text()
    assert maphub.tiles == []  # automation never asks for tiles
    page.evaluate("window.__jarvis.bridge.act('dock', 'w-map-today', { reason: 'closed' })")  # the shared hub: leave it as found
    win.wait_for(state="detached")
