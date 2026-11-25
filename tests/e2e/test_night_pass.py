"""N5b: the Night HUD pass on Today, Life, Activity, Memory, Controls and Under the hood."""


def test_timeline_ruler_and_next_hero(hub):
    page = hub.scene("today", "night")
    model = page.evaluate("""import('/components/timeline/timeline.js').then(m => m.rulerModel(
        [{id: 'a', start: '08:30', end: '09:20', state: 'done'}, {id: 'b', start: '16:00', end: '16:45', state: 'planned'}], 15 * 60 + 40))""")
    assert model["from"] == 8 and model["to"] == 17 and [b["state"] for b in model["blocks"]] == ["done", "next"]
    assert 0 < model["now"] < 1
    assert page.locator(".jv-timeline__block--done").count() == 4 and page.locator(".jv-timeline__hand").count() == 1
    assert "Review GE 122 lecture 21" in page.text_content(".jv-today__next") and page.locator(".jv-today__next .jv-hero").count() == 1
    assert page.locator(".jv-today__proposal jv-glance[state=yes]").count() == 1


def test_life_map_is_a_constellation_in_night_with_jarvis_in_cyan(hub):
    page = hub.scene("life-jarvis", "night")
    assert page.locator(".jv-map__node .jv-map__mark").count() == 6
    assert page.eval_on_selector(".jv-map__node .jv-map__leaf", "e => getComputedStyle(e).display") == "none"
    assert page.locator(".jv-map__node--jarvis").count() == 1 and page.locator(".jv-map__reticle").count() == 1
    assert page.get_attribute(".jv-map__node[data-id=school]", "aria-label").endswith("Jarvis is working here")
    cyan = page.evaluate("(() => { const p = document.createElement('p'); p.style.color = 'var(--cyan)'; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; })()")
    assert page.eval_on_selector(".jv-map__stem--jarvis", "e => getComputedStyle(e).stroke") == cyan
    day = hub.scene("life", "day")
    assert day.eval_on_selector(".jv-map__node .jv-map__mark", "e => getComputedStyle(e).display") == "none"


def test_controls_theme_segment_is_night_daylight_sunset(hub):
    page = hub.scene("controls", "night")
    radios = page.eval_on_selector_all("[role=radiogroup][aria-label=Theme] [role=radio]", "els => els.map(e => [e.textContent.trim(), e.getAttribute('aria-checked')])")
    assert radios == [["Night", "true"], ["Daylight", "false"], ["Sunset", "false"]]


def test_hood_latency_is_an_instrument_readout(hub):
    page = hub.scene("hood-over", "night")
    assert page.locator(".jv-hood__gauge").count() == 4 and page.locator(".jv-hood__gauge--over").count() == 1
    assert "Mono" in page.eval_on_selector(".jv-hood__num", "e => getComputedStyle(e).fontFamily")
    assert page.locator(".jv-hood__age").first.text_content().strip().endswith("2 min ago")
