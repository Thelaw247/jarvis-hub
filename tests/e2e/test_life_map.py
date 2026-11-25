"""Life Map, branch pages and Memory after the v0.2.1 fixes (F4): the plant, waiting counts from the
approvals, labels that never shrink, focus that stays in the map, and named facts."""

STATE = "window.__jarvis.store"


def press(page, key):
    page.keyboard.press(key)
    page.wait_for_timeout(30)


def path(page):
    return page.evaluate("window.__jarvis.router.current.path")


def waiting(page, selector):
    """The "n waiting" tag on a node (or the pot), or "" when there is none."""
    tag = page.locator(f"{selector} .jv-map__pill--yes")
    return tag.text_content().strip() if tag.count() else ""


def approval(id_, branch, status="pending"):
    return (f"{{v: 1, type: 'approval.pending', ts: '', data: {{id: '{id_}', title: 'Test', consequences: ['x'], "
            f"read_back: 'x', status: '{status}', asked: '2026-11-16T09:00', branch_id: '{branch}'}}}}")


def test_waiting_dots_follow_state_approvals_not_the_stored_count(hub):
    page = hub.scene("life-fall")
    # the fixture says ge-122 has pending: 1, but the only approval (ap-week) is on Fall 2026
    assert waiting(page, ".jv-map__node[data-id=ge-122]") == ""
    assert "waiting" not in page.get_attribute(".jv-map__node[data-id=ge-122]", "aria-label")
    assert waiting(page, ".jv-map__centre") == "1 waiting"
    page.evaluate(f"{STATE}.apply({approval('ap-ge', 'ge-122')})")
    page.wait_for_function("document.querySelector('.jv-map__node[data-id=ge-122] .jv-map__pill--yes')")
    assert waiting(page, ".jv-map__node[data-id=ge-122]") == "1 waiting"
    assert page.get_attribute(".jv-map__node[data-id=ge-122]", "aria-label").endswith("1 waiting for your yes")
    assert waiting(page, ".jv-map__centre") == "2 waiting"  # counted on the branch and everything above it
    page.evaluate(f"{STATE}.apply({{v: 1, type: 'approval.resolved', ts: '', data: {{id: 'ap-week', status: 'approved'}}}})")
    page.wait_for_function("document.querySelector('.jv-map__centre .jv-map__pill--yes')?.textContent.trim() === '1 waiting'")
    page.evaluate("window.__jarvis.router.go('/life')")
    page.wait_for_selector(".jv-map[data-focus=you]")
    assert waiting(page, ".jv-map__node[data-id=school]") == "1 waiting"
    page.evaluate(f"{STATE}.apply({{v: 1, type: 'approval.resolved', ts: '', data: {{id: 'ap-ge', status: 'declined'}}}})")
    page.wait_for_function("!document.querySelector('.jv-map__node[data-id=school] .jv-map__pill--yes')")
    page.click("[data-key=mode-list]")
    assert "needs your yes" not in page.inner_text("[role=tree]")


def test_the_map_is_a_plant_with_readable_leaf_labels(hub):
    page = hub.scene("life")
    assert page.locator(".jv-map__centre .jv-map__pot").count() == 1 and page.locator(".jv-map__stem").count() == 6
    assert page.locator(".jv-map__node .jv-map__leaf").count() == 6 and page.locator(".jv-map__glyph").count() == 0
    fonts = page.eval_on_selector_all(".jv-map__name", "els => els.map(e => getComputedStyle(e).fontFamily)")
    assert fonts and all(f.startswith('"Lexend"') or f.startswith("Lexend") for f in fonts)
    # tags are words (never colour alone), in the notice colours rather than terracotta, and at least 12 px
    tags = page.eval_on_selector_all(".jv-map__node[data-id=school] .jv-map__pill text", "els => els.map(e => e.textContent)")
    assert tags == ["Due 2d", "1 waiting"]
    accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
    fills = page.eval_on_selector_all(".jv-map__pill rect, .jv-map__due", "els => els.map(e => getComputedStyle(e).fill + getComputedStyle(e).stroke)")
    assert accent and not any(accent in f for f in fills)
    sizes = page.eval_on_selector_all(".jv-map__pill text", "els => els.map(e => e.getBoundingClientRect().height)")
    assert sizes and min(sizes) >= 12
    names = page.eval_on_selector_all(".jv-map__name", "els => els.map(e => e.getBoundingClientRect().height)")
    assert min(names) >= 13
    page = hub.scene("life-fall")
    assert "Lexend" in page.evaluate("getComputedStyle(document.querySelector('.jv-life__also')).fontFamily")


def test_labels_never_shrink_and_a_narrow_window_gets_the_list(hub):
    page = hub.page
    page.set_viewport_size({"width": 1100, "height": 760})
    hub.scene("life")
    assert page.locator(".jv-map").count() == 1
    heights = page.eval_on_selector_all(".jv-map__name", "els => els.map(e => e.getBoundingClientRect().height)")
    assert min(heights) >= 13  # the map is drawn at ~0.6 px per unit; labels are scaled back up
    page.set_viewport_size({"width": 720, "height": 450})  # 1440 x 900 at 200% zoom
    page.wait_for_selector("[role=tree]")
    assert page.locator(".jv-map").count() == 0 and "too narrow for the map" in page.inner_text(".jv-life__bar")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_selector(".jv-map")


def test_keyboard_focus_stays_in_the_map_flying_in_and_out(hub):
    page = hub.scene("life")
    page.focus(".jv-map__node[data-id=school]")
    press(page, "Enter")
    assert path(page) == "/life/school"
    assert page.evaluate("document.activeElement.classList.contains('jv-map__node')")
    press(page, "Backspace")
    assert path(page) in ("/life", "/life/you")
    assert page.evaluate("document.activeElement.dataset.id") == "school"
    assert page.get_attribute(".jv-map", "aria-label") == "Life Map of your life, with 6 branches growing from it."


def test_header_and_inside_chips(hub):
    page = hub.scene("life-school")
    head = page.locator("jv-view-life header.jv-view__head")
    assert head.locator("nav.jv-crumbs + h1 + p.jv-view__sub").count() == 1 and head.locator("h1").inner_text() == "Life Map"
    assert page.locator(".jv-branch__kids").count() == 0  # the map already shows them
    press(page, "l")
    assert page.locator(".jv-branch__kids").count() == 1
    for scene in ("memory", "unsorted"):
        page = hub.scene(scene)
        assert page.locator("header.jv-view__head > nav.jv-crumbs + h1 + p.jv-view__sub").count() == 1


def test_memory_filters_are_toggles_and_facts_are_named(hub):
    page = hub.scene("memory")
    assert page.locator("[role=tab], [role=tablist]").count() == 0
    assert page.get_attribute("[data-tab=all]", "aria-pressed") == "true"
    card = page.locator("jv-fact-card article").first
    statement = card.locator(".jv-fact-card__statement").inner_text()
    assert page.evaluate("el => document.getElementById(el.getAttribute('aria-labelledby')).textContent.trim()", card.element_handle()) == statement
    assert card.locator("button:visible").count() == 1  # only "…" until opened (Confirm shows on guesses)
    card.locator("[data-key=menu]").click()
    assert card.locator("[data-key=menu]").get_attribute("aria-expanded") == "true"
    assert card.locator("[data-key=edit]").get_attribute("aria-label") == f"Edit: {statement}"
    press(page, "Escape")
    assert card.locator("[data-key=edit]").count() == 0
    page.click("[data-tab=guesses]")
    assert page.locator("jv-fact-card >> text=Confirm").count() == 2
