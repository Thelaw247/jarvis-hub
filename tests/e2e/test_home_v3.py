"""P2, HUD v3 (§14 decisions 1, 2, 6, 7): the home screen as empty and calm as Huw's. Awake: the orb alone on the
grid. Resting: the small standby sphere with a small clock and a tiny date. The status word bottom-left, tiny.
Jarvis's line above the icon row only while he says it."""
import pytest

STATE = "window.__jarvis.store.state"
APPLY = "(e) => window.__jarvis.store.apply(e)"
CENTRE = ".jv-now__ambient"


def visible_in_centre(page):
    """What is drawn in the home's centre: elements that are seen and have a box (not their insides)."""
    return page.evaluate(f"""() => [...document.querySelector('{CENTRE}').querySelectorAll(':scope > *, .jv-amb > *')]
        .filter((e) => e.checkVisibility({{ visibilityProperty: true }}) && e.getBoundingClientRect().width > 0)
        .map((e) => e.localName + (e.classList[0] ? '.' + e.classList[0] : ''))""")


@pytest.mark.parametrize("theme", ["night", "day"])
def test_awake_the_home_is_the_orb_alone(hub, theme):
    page = hub.scene("now-calm", theme=theme)
    assert page.get_attribute("html", "data-home") == "calm"
    shown = [e for e in visible_in_centre(page) if e != "jv-plant.jv-now__plant"]  # Daylight keeps its small plant
    assert shown == ["div.jv-now__centre", "jv-orb.jv-amb__orb"], shown
    assert page.get_attribute(".jv-amb__orb", "state") == "idle"  # white rings, not the standby sphere
    assert page.locator("jv-clock:visible, jv-day-dial, .jv-amb__lead, .jv-amb__ask, .jv-now__stage").count() == 0
    assert page.locator("#chrome jv-tabs:visible, #chrome .jv-tabs__tab:visible").count() == 0  # no pills top-right
    assert hub.problems == []


def test_resting_is_the_small_sphere_with_a_small_clock_and_a_tiny_date(hub):
    for w, h in ((1920, 1080), (1440, 900)):
        hub.page.set_viewport_size({"width": w, "height": h})
        page = hub.scene("now-ambient", theme="night")
        assert page.get_attribute(".jv-amb__orb", "state") == "standby"
        assert visible_in_centre(page) == ["div.jv-now__centre", "jv-orb.jv-amb__orb", "div.jv-amb__time"]
        got = page.evaluate("""() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
            const orb = r('.jv-amb__orb'), time = r('.jv-amb__clock .jv-clock__time'), date = r('.jv-amb__clock .jv-clock__date');
            const fs = (s) => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
            return { orb: orb.width, cx: orb.left + orb.width / 2, cy: orb.top + orb.height / 2, timeTop: time.top, timeCx: time.left + time.width / 2,
                     timeW: time.width, dateTop: date.top, timeSize: fs('.jv-amb__clock .jv-clock__time'), dateSize: fs('.jv-amb__clock .jv-clock__date'),
                     dateText: document.querySelector('.jv-amb__clock .jv-clock__date').textContent }; }""")
        assert got["timeSize"] <= 64 and got["timeSize"] <= got["orb"] * 0.2, got  # the clock never dominates
        assert got["timeW"] < got["orb"], got  # narrower than the orb's box
        assert got["dateSize"] <= 12 and got["dateTop"] > got["timeTop"], got  # a tiny date, under the time
        assert got["timeTop"] > got["cy"] and abs(got["timeCx"] - got["cx"]) < 2, got  # under the sphere, centred on it
        assert got["dateText"] == "Monday, Nov 16"
    assert hub.problems == []


def test_the_orb_is_huws_size_and_never_moves_between_awake_and_resting(hub):
    for w, h in ((1920, 1080), (1440, 900), (1280, 720)):
        hub.page.set_viewport_size({"width": w, "height": h})
        boxes = []
        for scene in ("now-calm", "now-ambient"):
            page = hub.scene(scene, theme="night")
            boxes.append(page.locator(".jv-amb__orb").bounding_box())
        awake, resting = boxes
        assert all(abs(awake[k] - resting[k]) < 1 for k in ("x", "y", "width")), (w, h, boxes)
        # the box the v3 orb draws into: its outer ornaments (~0.76 of the box) come to about a sixth of the width
        assert 0.16 <= awake["width"] / w <= 0.24, (w, h, awake)
        assert abs(awake["x"] + awake["width"] / 2 - w / 2) < 2
        stage = page.evaluate("(() => { const s = document.getElementById('stage'); return [s.scrollHeight, s.clientHeight]; })()")
        assert stage[0] <= stage[1] + 1, (w, h, stage)  # nothing scrolls
        rail = page.locator("#rail").bounding_box()
        assert awake["y"] + awake["height"] < rail["y"], (w, h)


def test_the_stage_chip_is_now_a_glyph_on_the_icon_row(hub):
    page = hub.scene("now", theme="night")  # four windows up on the Stage
    assert page.locator(".jv-now__stage, .jv-now__stagebar").count() == 0
    assert page.get_attribute("#rail [data-tool=stage]", "aria-label") == "Show the Stage: 4 windows up"
    page.evaluate(APPLY, {"v": 2, "type": "window.push", "ts": "2026-11-16T15:42:00",
                          "data": {"id": "w-note", "type": "notice", "title": "Lab 4", "data": {"text": "Room changed"}}})
    page.wait_for_function("document.querySelector('#rail [data-tool=stage]').getAttribute('aria-label') === 'Show the Stage: 5 windows up'")
    assert page.locator("jv-view-now jv-window").count() == 0  # still nothing pops up on the home
    page = hub.scene("now-calm", theme="night")
    assert page.locator("#rail [data-tool=stage]").is_hidden()
    assert page.evaluate("import('/views/now/now.js').then(m => [m.stageCount({ windows: [{}, {}] }), m.stageCount({})])") == [2, 0]


def test_jarvis_line_shows_above_the_icon_row_only_while_he_speaks(hub):
    page = hub.scene("now", theme="night")  # speaking, with his line
    cap = page.locator("#caption .jv-caption")
    assert cap.is_visible()
    box, row = cap.bounding_box(), page.locator("#rail .jv-rail__bar").bounding_box()
    assert box["y"] + box["height"] <= row["y"] and abs(box["x"] + box["width"] / 2 - (row["x"] + row["width"] / 2)) < 40
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "idle"}})
    page.wait_for_selector("#caption .jv-caption", state="detached")  # he stopped: the line folds into the Jarvis slot
    assert page.evaluate(f"{STATE}.rail.slots.jarvis.said.length") > 0  # what he said stays under the Jarvis icon (the hub keeps it)
    # a line shown but not said (quiet hours: the orb doesn't speak) still shows, for its time
    page.evaluate(APPLY, {"v": 1, "type": "caption.show", "ts": "", "data": {"text": "Canvas is up to date.", "source": None, "ttl_ms": 600000}})
    page.wait_for_selector("#caption .jv-caption")
    # his own words show while Jarvis hears and thinks, and go when Jarvis answers
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "listening"}})
    page.evaluate(APPLY, {"v": 1, "type": "caption.show", "ts": "", "data": {"text": "Status.", "source": {"kind": "you", "label": "You"}, "ttl_ms": 600000}})
    page.wait_for_selector("#caption .jv-caption--you")
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "thinking"}})
    page.wait_for_timeout(50)
    assert page.locator("#caption .jv-caption--you").is_visible()
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "idle"}})
    page.wait_for_selector("#caption .jv-caption", state="detached")
    assert hub.problems == []


def test_resting_jarvis_speaks_and_his_line_shows_above_the_row(hub):
    page = hub.scene("now-ambient-caption", theme="night")
    assert page.get_attribute(".jv-amb__orb", "state") == "speaking" and page.is_hidden(".jv-amb__time")
    cap, row = page.locator("#caption .jv-caption").bounding_box(), page.locator("#rail .jv-rail__bar").bounding_box()
    assert cap["y"] + cap["height"] <= row["y"]
    assert hub.problems == []


@pytest.mark.parametrize("theme", ["night", "day"])
def test_the_status_word_is_tiny_and_bottom_left(hub, theme):
    page = hub.scene("now-ambient", theme=theme)
    got = page.evaluate("""() => { const t = document.querySelector('#status .jv-status-line__text'), b = t.getBoundingClientRect();
        return [parseFloat(getComputedStyle(t).fontSize), b.left < 120, b.bottom > innerHeight - 60, t.textContent.replace(/\\s+/g, ' ').trim()]; }""")
    assert got[0] <= 12 and got[1] and got[2], got
    assert got[3].lower() == "standby · mic on"
    # the word follows the orb: it says Speaking only while Jarvis speaks, then goes back
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "speaking", "level": 0.5}})
    page.wait_for_function("document.querySelector('#status .jv-status-line__state').textContent === 'Speaking'")
    page.evaluate(APPLY, {"v": 1, "type": "orb.state", "ts": "", "data": {"state": "thinking"}})
    page.wait_for_function("document.querySelector('#status .jv-status-line__state').textContent === 'Thinking'")
    assert page.locator("#status .jv-status-line__mic").is_visible()  # the mic is always shown (trust: listening is visible)
    assert hub.problems == []


def test_awake_the_status_word_matches_the_rings(hub):
    page = hub.scene("now-calm", theme="night")
    assert page.inner_text("#status .jv-status-line__state").lower() == "listening"


def test_the_home_fits_its_node_budget_and_others_see_nothing_personal(hub):
    page = hub.scene("now-ambient-others", theme="night")
    text = page.inner_text(CENTRE)
    assert "PPS" not in text and "GE 122" not in text
    assert page.locator("jv-plant:visible").count() == 0
    for scene in ("now-calm", "now-ambient"):
        page = hub.scene(scene, theme="night")
        centre = page.evaluate(f"document.querySelectorAll('{CENTRE} *').length")
        total = page.evaluate("document.querySelectorAll('*').length")
        row = page.evaluate("document.querySelectorAll('#rail *').length")
        print(scene, "centre", centre, "row", row, "page", total)
        assert total <= 1200 and row <= 200
    assert hub.problems == []
