"""Glance codes, pictures and the Night window (N5a, HUD v2 §3, §5): every state is a shape + a colour + a word,
brackets mean only "wants you", pictures fall back to words, and the window keeps its old behaviour."""

SHAPES = """els => els.map(e => ({
  state: e.dataset.glance, name: e.getAttribute('aria-label'), role: e.getAttribute('role'),
  word: e.querySelector('.jv-glance__word')?.textContent || null,
  shape: [...e.querySelectorAll('svg > *')].map(n => n.getAttribute('class')).join(' '),
  colour: getComputedStyle(e).color, size: e.querySelector('svg').getBoundingClientRect().width }))"""


def test_every_glance_state_has_its_own_shape_colour_and_word(hub):
    for theme in ("night", "day"):
        page = hub.scene("component:glance", theme, state="every-state-inline")
        got = page.eval_on_selector_all(".jv-glance-demo .jv-glance", SHAPES)
        assert [g["state"] for g in got] == ["done", "progress", "jarvis", "soon", "yes", "critical", "parked"]
        assert all(g["role"] == "img" and g["name"] == g["word"] for g in got)  # the accessible name is the word
        names = {g["state"]: g["name"] for g in got}
        assert names["done"] == "Done" and names["yes"] == "Your yes" and names["parked"] == "Parked" and names["progress"] == "Q7 of 12"
        assert len({g["shape"] for g in got}) == 7, got  # never colour alone: no two states share a shape
        brackets = {g["state"] for g in got if "jv-glance__brackets" in g["shape"]}
        assert brackets == {"soon", "yes", "critical"}  # corner brackets mean only "wants you"
        colours = {g["state"]: g["colour"] for g in got}
        assert colours["soon"] == colours["yes"] != colours["critical"] and colours["jarvis"] != colours["done"]
    rail = hub.scene("component:glance", "night", state="every-state-rail-16-px").eval_on_selector_all(".jv-glance-demo .jv-glance", SHAPES)
    assert all(g["size"] >= 16 for g in rail)  # done is a filled disc of at least 16 px
    hub.page.goto(f"{hub.base}/?scene=component:glance&theme=night&state=shape-only-word-for-screen-readers")
    hub.page.wait_for_selector("html[data-ready]")
    shapes = hub.page.eval_on_selector_all(".jv-glance-demo .jv-glance", SHAPES)
    assert all(g["word"] is None and g["name"] for g in shapes)


def test_critical_brackets_hold_still_under_reduced_motion(hub):
    page = hub.scene("component:glance", "night", state="every-state-inline")  # the test browser asks for reduced motion
    crit = ".jv-glance--critical .jv-glance__brackets"
    assert page.eval_on_selector(crit, "e => getComputedStyle(e).animationName") == "none"
    assert page.eval_on_selector(crit, "e => getComputedStyle(e).strokeWidth") == "3px"  # a still, thicker frame
    assert page.locator(".jv-glance__scan").first.is_hidden()


def test_glance_helper_is_exported_for_other_components(hub):
    hub.scene("component:glance", "night")
    out = hub.page.evaluate("""import('/components/glance/glance.js').then(m => ({
        html: String(m.glance('yes', { word: 'Your yes · Week plan', size: 'rail' })),
        states: m.GLANCE_STATES, wants: [...m.WANTS_YOU] }))""")
    assert 'aria-label="Your yes · Week plan"' in out["html"] and "jv-glance--rail" in out["html"]
    assert out["states"] == ["done", "progress", "jarvis", "soon", "yes", "critical", "parked"]
    assert sorted(out["wants"]) == ["critical", "soon", "yes"]


def test_pictures_have_fixed_boxes_and_fall_back_to_words(hub):
    page = hub.scene("component:thumb", "night")
    page.wait_for_function("[...document.querySelectorAll('.jv-thumb__img')].every(i => i.complete && i.naturalWidth > 0)")
    imgs = page.eval_on_selector_all(".jv-thumb__img", "els => els.map(i => [i.getAttribute('loading'), i.alt, i.naturalWidth])")
    assert imgs and all(loading == "lazy" and alt and width == 320 for loading, alt, width in imgs)
    ratio = page.eval_on_selector("[data-state=slide-deck] .jv-thumb", "e => { const r = e.getBoundingClientRect(); return r.width / r.height; }")
    assert abs(ratio - 16 / 9) < 0.02  # the box is sized before the picture lands: no layout shift
    assert page.inner_text("[data-state=slide-deck] .jv-thumb__label").upper() == "GE 122 · L21"
    assert page.get_attribute("[data-state=room-code] .jv-thumb__mono", "aria-label") == "Room ENGR 1A10"
    assert page.inner_text("[data-state=person-initials] .jv-thumb__initials") == "ST"
    assert page.inner_text("[data-state=course-monogram-no-picture] .jv-thumb__mono").split() == ["GE", "122"]
    broken = page.locator("[data-state=picture-that-fails-to-load]")
    page.wait_for_function("!document.querySelector('[data-state=picture-that-fails-to-load] img')")
    assert broken.locator(".jv-thumb__mono").inner_text().split() == ["GE", "122"]
    assert hub.problems == []


def test_window_marks_mean_one_thing_each(hub):
    page = hub.scene("component:window", "night")
    shown = lambda cell: page.eval_on_selector(f"[data-state={cell}] jv-window", "w => [...w.querySelectorAll(':scope > .jv-window__bracket')].map(b => getComputedStyle(b).visibility)")  # noqa: E731
    assert shown("resting") == ["hidden"] * 4
    assert shown("active-jarvis-means-it") == ["hidden"] * 4  # the window Jarvis means: a brighter frame, no glyph (§14.2)
    assert page.locator("[data-state=active-jarvis-means-it] .jv-window__title svg").count() == 0
    # only a wants-you mark may lead a kicker; a working window's state is a word for screen readers, not a glyph
    assert page.locator("[data-state=wants-you-soon] .jv-window__title svg").count() == 1
    assert page.locator("[data-state=working-60] .jv-window__title svg").count() == 0
    for cell in ("wants-you-soon", "wants-you-your-yes", "wants-you-critical", "named-as-jarvis-speaks"):
        assert shown(cell) == ["visible"] * 4, cell
    kicker = page.inner_text("[data-state=kicker-index-and-metadata] .jv-window__title")
    assert "".join(kicker.split()) == "MATH133//Exam" and page.inner_text("[data-state=kicker-index-and-metadata] .jv-window__index") == "EXAM"
    meta = page.locator("[data-state=kicker-index-and-metadata] .jv-window__meta")
    frame = page.locator("[data-state=kicker-index-and-metadata] jv-window").bounding_box()
    assert meta.bounding_box()["y"] >= frame["y"] + frame["height"]  # metadata hangs outside the frame
    # the window it isn't about sits back; under reduced motion it keeps the dimming but not the scale
    other = page.locator("[data-state=focused-and-unfocused] jv-window[window-id=w-12]")
    assert other.evaluate("e => getComputedStyle(e).transform") == "none"
    assert page.locator("[data-state=docked-not-drawn] jv-window").is_hidden()


def test_working_shows_words_when_nothing_may_move_and_assembly_leaves_nothing_behind(hub):
    page = hub.scene("component:window", "night")
    work = page.locator("[data-state=working-60] jv-window")
    assert work.locator(".jv-window__scan").is_hidden() and work.locator(".jv-window__scan-words").inner_text().upper() == "WORKING · 60%"
    assert work.locator("[role=progressbar]").get_attribute("aria-valuetext") == "Working · 60%"
    assert work.locator(".jv-window__scan > *").count() == 1  # the ~30 blocks are 2 elements: track and chunk
    # nothing may move: no overlay is ever added, and the content is there from the start
    assert page.locator("jv-window[assembling], .jv-window__draw, .jv-window__cover").count() == 0


def test_assembly_is_an_overlay_that_ends_within_300_ms(browser, hub_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="no-preference")
    page = context.new_page()
    page.goto(f"{hub_url}/?scene=component:window&theme=night&state=resting")
    page.wait_for_selector("html[data-ready]")
    out = page.evaluate("""() => new Promise((done) => {
        const w = document.createElement('jv-window');
        w.setAttribute('heading', 'PPS 7'); w.setAttribute('window-id', 'w-new');
        const b = document.createElement('button'); b.textContent = 'Open it'; w.append(b);
        document.querySelector('#stage').append(w);
        const at0 = { assembling: w.hasAttribute('assembling'), overlays: w.querySelectorAll('.jv-window__draw, .jv-window__cover').length,
                      usable: getComputedStyle(b).visibility === 'visible' && getComputedStyle(w.querySelector('.jv-window__body')).opacity === '1' };
        setTimeout(() => done({ at0, after: w.hasAttribute('assembling') || w.querySelectorAll('.jv-window__draw, .jv-window__cover').length > 0 }), 400);
    })""")
    context.close()
    assert out["at0"] == {"assembling": True, "overlays": 2, "usable": True}
    assert out["after"] is False
