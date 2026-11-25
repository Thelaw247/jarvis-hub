"""N3: the day dial (HUD v2 §6.1). HUD v3 (§14 decision 6): the dial leaves the home screen (Huw has nothing around
the orb); the component stays, shown here on its own scene around a standby orb."""
import pytest

DIAL = "import('/components/day-dial/day-dial.js')"
SAMPLES = "import('/components/day-dial/day-dial-scenes.js')"


def model(page, sample, private=False):
    return page.evaluate(f"""Promise.all([{DIAL}, {SAMPLES}]).then(([d, s]) => {{
        const x = s.DIAL_SAMPLES['{sample}'], m = d.dialModel(x.items, x.now, {{ private: {str(private).lower()} }});
        return {{ ...m, from: m.from.toISOString(), to: m.to.toISOString() }}; }})""")


def arc(m, ident):
    return next(a for a in m["arcs"] if a["id"] == ident)


def test_dial_geometry_and_labels_from_sample_data(hub):
    page = hub.scene("shell")
    assert page.evaluate(f"{DIAL}.then(d => [d.clockAngle('2026-11-16T15:00:00'), d.clockAngle('2026-11-16T03:00:00'), d.clockAngle('2026-11-16T00:00:00'), d.clockAngle('2026-11-16T16:45:00')])") == [90, 90, 0, 142.5]
    m = model(page, "afternoon")  # 3:40 pm: the face runs 2:40 pm → 2:40 am
    assert m["hand"] == 110
    review = arc(m, "dial-review")
    assert (review["look"], review["a0"], review["a1"]) == ("next", 120, 142.5)
    chem = arc(m, "dial-chem")  # done 1:30–3:20 pm, clipped to the face's start (2:40 pm)
    assert (chem["look"], chem["a0"], chem["a1"]) == ("done", 80, 100)
    assert arc(m, "dial-pps")["look"] == "upcoming"
    assert "dial-ge" not in [a["id"] for a in m["arcs"]]  # 10 am is off the face
    assert [(k["id"], k["shape"], k["look"]) for k in m["marks"]] == [("dial-webwork", "diamond", "due")]
    assert m["next"]["label"] == "4:00 · GE 122 review" and m["next"]["angle"] == 120
    assert m["summary"] == "Day dial, 2:40 pm to 2:40 am. Next: GE 122 review at 4:00 pm, Your desk. 1 done, 1 more later, 1 due."
    # others present: the same shapes, no words
    hidden = model(page, "afternoon", private=True)
    assert hidden["next"]["label"] is None and "GE 122" not in hidden["summary"] and hidden["arcs"] == m["arcs"]


def test_dial_crosses_midnight(hub):
    page = hub.scene("shell")
    m = model(page, "midnight")  # 10:30 pm: the face runs 9:30 pm → 9:30 am tomorrow
    read = arc(m, "dial-read")  # 11 pm → 12:15 am: one unbroken arc over 12 o'clock
    assert (read["look"], read["a0"], read["a1"]) == ("next", 330, 367.5)
    math = arc(m, "dial-math")  # tomorrow's 8:30 class is on tonight's face
    assert (math["look"], math["a0"], math["a1"]) == ("upcoming", 255, 280)
    assert arc(m, "dial-pps")["a0"] == 285  # done 9–10:15 pm, clipped to 9:30
    assert [k["id"] for k in m["marks"]] == ["dial-webwork"]
    assert m["next"]["label"] == "11:00 · Read lab 5 handout"
    assert m["summary"].startswith("Day dial, 9:30 pm to 9:30 am. Next: Read lab 5 handout at 11:00 pm")


def test_overdue_stays_on_the_face_and_all_done_says_so(hub):
    page = hub.scene("shell")
    m = model(page, "overdue")
    marks = {k["id"]: k for k in m["marks"]}
    assert marks["dial-quiz"]["shape"] == "triangle" and marks["dial-quiz"]["pinned"] and marks["dial-quiz"]["angle"] == 80
    assert marks["dial-memo"]["shape"] == "triangle" and not marks["dial-memo"]["pinned"] and marks["dial-memo"]["angle"] == 90
    assert marks["dial-lab4"]["shape"] == "diamond" and marks["dial-lab4"]["look"] == "due"
    assert "2 overdue" in m["summary"]
    done = model(page, "all-done")
    assert {a["look"] for a in done["arcs"]} == {"done"} and done["marks"][0]["look"] == "done" and done["next"] is None
    assert done["summary"] == "Day dial, 8:10 pm to 8:10 am. All done; nothing else booked."
    moved = model(page, "moved")
    assert {a["id"]: a["look"] for a in moved["arcs"]} == {"dial-chemrev": "off", "dial-math": "next", "dial-ge": "next", "dial-gym": "off"}
    assert moved["summary"] == "Day dial, 8:10 am to 8:10 pm. Now: MATH 133, until 9:20 am. Next: GE 122 at 10:00 am, ENGR 1A10. 2 moved or missed."


ORB = ".jv-day-dial-scene jv-orb"


def dial_scene(hub, **more):
    """The dial where it still lives: around a standby orb, with the orb's `dial` attribute on (HUD v3: off by
    default, so nothing is drawn round the home's orb). Setting it here keeps the test true before and after the
    scene sets it itself."""
    page = hub.scene("day-dial-orb", **more)
    page.evaluate(f"document.querySelector('{ORB}').setAttribute('dial', '')")
    return page


def test_the_dial_sits_inside_the_motes_and_is_drawn_to_spec(hub):
    page = dial_scene(hub, theme="night")
    page.wait_for_selector(f"{ORB} .jv-orb__dial > jv-day-dial svg")
    got = page.evaluate("""() => {
        const orb = document.querySelector('.jv-day-dial-scene jv-orb'), dial = orb.querySelector('jv-day-dial');
        const o = orb.getBoundingClientRect(), d = dial.getBoundingClientRect(), R = o.width * 36 / 220;
        const sw = (sel) => parseFloat(getComputedStyle(dial.querySelector(sel)).strokeWidth);
        const label = dial.querySelector('.jv-day-dial__label');
        return { ring: d.width / 2 / R, centred: Math.abs((d.left + d.width / 2) - (o.left + o.width / 2)) < 1,
                 arc: sw('.jv-day-dial__arc--next'), hand: sw('.jv-day-dial__hand'), label: label.textContent,
                 size: getComputedStyle(label).fontSize, ticks: dial.querySelector('.jv-day-dial__ticks').getAttribute('d').split('M').length - 1,
                 nodes: dial.querySelectorAll('*').length }; }""")
    assert abs(got["ring"] - 2.5) < 0.01 and got["centred"]
    # the furthest a mark reaches (a 4 px arc or a 9 px diamond on the ring) stays inside the motes at 2.75 R
    width = page.evaluate("document.querySelector('.jv-day-dial-scene jv-orb').getBoundingClientRect().width")
    r_px = 2.5 * width * 36 / 220
    assert (r_px + 5) / (width * 36 / 220) < 2.75
    assert got["arc"] == 4 and got["hand"] == 2 and got["ticks"] == 12
    assert got["label"] == "4:00 · GE 122 review" and got["size"] == "12px"
    assert got["nodes"] < 30


def test_the_dial_is_static(hub):
    """HUD v2 §7: the orb owns the ambient screen's 8 animations; the dial runs none and doesn't redraw between minutes."""
    hub.page.emulate_media(reduced_motion="no-preference")
    page = dial_scene(hub, theme="night", motion="full")
    page.wait_for_selector("jv-day-dial svg")
    page.evaluate("""() => { window.__dialMuts = 0; new MutationObserver((m) => { window.__dialMuts += m.length; })
        .observe(document.querySelector('jv-day-dial'), { subtree: true, childList: true, attributes: true, characterData: true }); }""")
    page.wait_for_timeout(1500)
    assert page.evaluate("window.__dialMuts") == 0
    assert page.evaluate("document.getAnimations().filter(a => a.effect?.target?.closest?.('jv-day-dial')).length") == 0
    assert page.evaluate("[...document.querySelectorAll('jv-day-dial, jv-day-dial *')].every(e => getComputedStyle(e).animationName === 'none' && ['0s', ''].includes(getComputedStyle(e).transitionDuration.split(',')[0]))")
    running = page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length")
    assert 1 <= running <= 8


def test_the_dial_redraws_with_the_minute_and_new_data(hub):
    page = hub.scene("shell")
    out = page.evaluate("""async () => {
        await import('/components/day-dial/day-dial.js');
        const d = document.createElement('jv-day-dial'); d.style.cssText = 'width:300px;height:300px';
        d.now = '2026-11-16T15:40:00';
        d.items = [{ id: 'a', kind: 'class', start: '2026-11-16T16:00:00', end: '2026-11-16T17:00:00', title: 'GE 122', where: 'ENGR 1A10' }];
        document.body.append(d); await new Promise(r => setTimeout(r, 50));
        const first = d.querySelector('.jv-day-dial__label').textContent;
        d.now = '2026-11-16T16:10:00'; await new Promise(r => setTimeout(r, 50));
        return [first, d.querySelector('.jv-day-dial__label'), d.querySelector('.jv-day-dial__arc--next') !== null, d.getAttribute('aria-label')]; }""")
    assert out[0] == "4:00 · GE 122 · ENGR 1A10"
    assert out[1] is None and out[2]  # under way now: still cyan, but nothing is labelled "next" any more
    assert out[3] == "Day dial, 3:10 pm to 3:10 am. Now: GE 122, until 5:00 pm."


def test_screen_readers_get_the_dial_in_one_line(hub):
    page = dial_scene(hub, theme="night")
    page.wait_for_selector("jv-day-dial svg")
    dial = page.locator("jv-day-dial")
    assert dial.get_attribute("role") == "img"
    summary = dial.get_attribute("aria-label")
    assert summary == "Day dial, 2:40 pm to 2:40 am. Next: GE 122 review at 4:00 pm, Your desk. 1 done, 1 more later, 1 due."
    assert page.get_attribute(".jv-day-dial__svg", "aria-hidden") == "true"


def test_the_dial_has_left_the_home_screen(hub):
    """HUD v3 §14 decision 6: nothing around the orb on the home, awake or resting; what's next is in Today and on
    the Today icon's badge."""
    for scene in ("now-calm", "now-ambient", "now", "now-ambient-others"):
        page = hub.scene(scene, theme="night")
        assert page.locator("jv-day-dial").count() == 0, scene  # not mounted at all, so no dial timers run
        assert page.locator(".jv-orb__dial *").count() == 0, scene
        assert page.get_attribute(".jv-amb__orb", "dial") is None, scene
    assert hub.problems == []


def test_others_present_hides_the_dial_words(hub):
    page = hub.scene("component:day-dial", state="others-present-shapes-no-words", theme="night")
    page.wait_for_selector("jv-day-dial svg")
    assert page.locator(".jv-day-dial__label").count() == 0 and page.locator(".jv-day-dial__arc").count() > 0
    assert "Review" not in page.get_attribute("jv-day-dial", "aria-label")


@pytest.mark.parametrize("theme", ["night", "day"])
def test_dial_scenes_load_cleanly(hub, theme):
    for scene in ("day-dial-orb", "component:day-dial"):
        hub.scene(scene, theme=theme)
    assert hub.problems == []
