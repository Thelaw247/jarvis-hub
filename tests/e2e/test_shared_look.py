"""The shared look (F3): type rules, the page header, crumbs, big numbers, the status line, switches."""

FONT = "el => getComputedStyle(el).fontFamily"


def test_big_number_reads_in_sentence_case_with_one_due_soon_label(hub):
    page = hub.scene("component:big-number")
    soon = page.locator("[data-state=due-soon-within-72-h]")
    value = soon.locator(".jv-big-number__value")
    assert value.locator("[aria-hidden=true]").inner_text().split() == ["2", "d", "4", "h"]
    assert value.locator(".jv-sr").inner_text() == "2 days 4 hours left"
    # one label, in words, in the notice colours (terracotta is only for the main action)
    assert soon.locator(".jv-big-number__soon").inner_text().strip() == "Due soon"
    assert soon.locator(".jv-big-number__label").count() == 0 and "Due ·" not in soon.inner_text()
    colour = lambda sel: page.eval_on_selector(sel, "el => getComputedStyle(el).color")  # noqa: E731
    notice = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--notice-ink').trim()")
    probe = page.evaluate(f"(() => {{ const p = document.createElement('p'); p.style.color = '{notice}'; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; }})()")
    assert colour("[data-state=due-soon-within-72-h] .jv-big-number__soon") == probe
    # the number itself is never amber (HUD v2 §14.2): near-white in Night, the text ink in Daylight
    ink = page.evaluate("(() => { const p = document.createElement('p'); p.style.color = 'var(--text)'; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; })()")
    assert colour("[data-state=due-soon-within-72-h] .jv-big-number__value") == ink != probe
    later = page.locator("[data-state=due-later] .jv-big-number__label")
    assert later.inner_text() == "Due" and later.evaluate("el => getComputedStyle(el).textTransform") == "none"


def test_status_line_uses_words_not_mono_and_the_mic_follows_the_orb(hub):
    page = hub.scene("component:status-line")
    for state in ("listening", "offline-says-what-to-do"):
        line = page.locator(f"[data-state={state}] .jv-status-line")
        assert "Mono" not in line.evaluate(FONT) and "Atkinson" in line.evaluate(FONT)
    mic = page.locator("[data-state=offline-says-what-to-do] .jv-status-line__mic")
    assert "jv-status-line__mic--offline" in mic.get_attribute("class") and mic.get_attribute("data-act") is None
    assert mic.get_attribute("aria-disabled") == "true"
    on = page.eval_on_selector("[data-state=listening] .jv-status-line__mic", "el => getComputedStyle(el).borderTopColor")
    assert mic.evaluate("el => getComputedStyle(el).borderTopColor") != on


def test_page_header_is_crumb_then_h1_then_subtitle_on_one_left_edge(hub):
    for scene, crumbs in (("hood", True), ("today", False), ("today-free", False)):
        page = hub.scene(scene)
        head = page.locator(".jv-view__head").first
        order = head.evaluate("el => [...el.children].map(c => c.localName + (c.className ? '.' + c.className.split(' ')[0] : ''))")
        assert order == (["nav.jv-crumbs"] if crumbs else []) + ["h1", "p.jv-view__sub"], (scene, order)
        lefts = head.evaluate("el => [...el.children].map(c => Math.round(c.getBoundingClientRect().left))")
        assert len(set(lefts)) == 1, (scene, lefts)


def test_crumbs_are_sentence_case_lexend_14_and_not_underlined(hub):
    page = hub.scene("hood")
    crumbs = page.locator(".jv-crumbs")
    style = crumbs.evaluate("el => { const s = getComputedStyle(el); return [s.textTransform, s.fontSize, s.fontFamily]; }")
    assert style[0] == "none" and style[1] == "14px" and "Lexend" in style[2]
    assert page.eval_on_selector(".jv-crumbs a", "el => getComputedStyle(el).textDecorationLine") == "none"


def test_long_titles_are_never_small_caps(hub):
    page = hub.scene("hood")
    caps = page.eval_on_selector_all(
        "#stage *", "els => els.filter(e => e.children.length === 0 || e.matches('h2,h3,figcaption')).filter(e => getComputedStyle(e).textTransform === 'uppercase')"
        ".map(e => e.textContent.trim()).filter(t => t.split(/\\s+/).length > 2)")
    assert caps == []
    assert "Mono" not in page.eval_on_selector(".jv-mini-chart__caption", FONT)


def test_today_free_is_one_plain_card_with_one_action(hub):
    page = hub.scene("today-free")
    assert page.locator(".jv-today__free").count() == 1 and page.locator("#stage jv-notice").count() == 0
    assert page.locator(".jv-today__free button").count() == 1
    assert page.eval_on_selector(".jv-today__free", "el => getComputedStyle(el).borderTopStyle") == "solid"


def test_switches_use_the_pressed_look_not_leaf_green(hub):
    page = hub.scene("controls")
    on = page.locator(".jv-switch[aria-checked=true]").first
    border = on.evaluate("el => getComputedStyle(el).borderTopColor")
    probe = lambda token: page.evaluate(f"(() => {{ const p = document.createElement('p'); p.style.color = 'var({token})'; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; }})()")  # noqa: E731
    assert border == probe("--control") and border != probe("--leaf-ink")
    assert on.evaluate("el => getComputedStyle(el).backgroundColor") == page.evaluate("(() => { const p = document.createElement('p'); p.style.background = 'var(--card)'; document.body.append(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; })()")


def test_body_line_height_is_at_least_one_and_a_half(hub):
    page = hub.scene("today")
    size, line = page.evaluate("(() => { const s = getComputedStyle(document.body); return [parseFloat(s.fontSize), parseFloat(s.lineHeight)]; })()")
    assert line / size >= 1.5
