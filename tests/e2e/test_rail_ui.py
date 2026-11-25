"""The Rail (<jv-rail>, N4; HUD v3 §14: Huw's icon row): six tiny icons that track things, their badges, the
keyboard path, the fan, recall, marks, focus, the search and Stage glyphs and the page dots under the row."""
import pytest

SLOT = "#rail .jv-rail__slot[data-slot={}]"


def marks(hub):
    return sorted(hub.state("s => Object.keys(s.marks)"))


def test_six_slots_are_buttons_with_a_summary_for_screen_readers(hub):
    page = hub.scene("now-rail")
    slots = page.eval_on_selector_all("#rail .jv-rail__slot", "n => n.map(b => [b.tagName, b.dataset.slot, b.getAttribute('aria-label')])")
    assert [s[1] for s in slots] == ["yes", "today", "homework", "messages", "jarvis", "parked"]
    assert all(tag == "BUTTON" for tag, _, _ in slots)
    labels = {name: text for _, name, text in slots}
    assert labels["homework"] == "Homework: 4 things, worst: In progress, 23% done"
    assert labels["today"].startswith("Today: 5 things, worst: Soon, 67% done")
    assert labels["messages"] == "Messages: 0 things"
    assert page.get_attribute("#rail .jv-rail__bar", "role") == "toolbar"
    assert page.inner_text(SLOT.format("homework") + " .jv-rail__count") == "4"
    assert page.inner_html(SLOT.format("messages") + " .jv-rail__badge") == ""  # an empty slot: no badge, no "0"
    assert page.locator(SLOT.format("homework") + " .jv-rail__notch").is_hidden()  # nothing new: no notch, and never a red badge
    # Huw's icon row: tiny line icons, the words only for screen readers (and the tooltip)
    sizes = page.eval_on_selector_all("#rail .jv-rail__slot", "n => n.map(b => [b.getBoundingClientRect().width, b.querySelector('.jv-icon').getBoundingClientRect().width, b.querySelector('.jv-rail__name').getBoundingClientRect().width, b.title])")
    assert all(w <= 44 and icon == 16 and name <= 1 and title for w, icon, name, title in sizes), sizes


def test_keyboard_path_alt_number_enter_arrows_and_escape(hub):
    page = hub.scene("now-rail")
    page.keyboard.press("Alt+3")
    assert page.evaluate("document.activeElement.dataset.slot") == "homework"
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.dataset.slot") == "messages"
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Enter")
    assert page.get_attribute(SLOT.format("homework"), "aria-expanded") == "true"
    assert page.is_visible("#jv-rail-fan")
    assert page.evaluate("document.activeElement.dataset.ref") == "due-pps7"  # the first thing, worst first
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.ref") == "due-lab4"
    page.keyboard.press("Escape")
    assert page.is_hidden("#jv-rail-fan") and page.evaluate("document.activeElement.dataset.slot") == "homework"
    assert hub.state("s => location.hash") in ("#/now", "")  # Esc closed the fan; it didn't also go back
    page.keyboard.press("Alt+6")
    assert page.evaluate("document.activeElement.dataset.slot") == "parked"
    tabbable = page.eval_on_selector_all("#rail .jv-rail__slot", "n => n.filter(b => b.tabIndex === 0).map(b => b.dataset.slot)")
    assert tabbable == ["parked"]  # one Tab stop for the whole Rail (roving)


def test_focus_ring_comes_back_after_a_click_and_escape(hub):
    # a11y review MUST 1: Esc after a click gave focus back to a slot that still had tabindex=-1, and
    # base.css's [tabindex="-1"]:focus rule hid the ring; the roving tab stop also stayed on slot 1
    page = hub.scene("now-rail")
    for slot in ("messages", "homework"):  # an empty slot (focus stays on it) and a filled one (focus goes to a card)
        page.click(SLOT.format(slot))
        assert page.get_attribute(SLOT.format(slot), "aria-expanded") == "true"
        page.keyboard.press("Escape")
        assert page.is_hidden("#jv-rail-fan")
        got = page.evaluate("() => { const a = document.activeElement; return [a.dataset.slot, a.tabIndex, getComputedStyle(a).outlineStyle]; }")
        assert got == [slot, 0, "solid"], got
        tabbable = page.eval_on_selector_all("#rail .jv-rail__slot", "n => n.filter(b => b.tabIndex === 0).map(b => b.dataset.slot)")
        assert tabbable == [slot]
    assert hub.problems == []


def test_a_docked_thing_is_recalled_and_its_window_comes_back(hub):
    page = hub.scene("now-marks")
    assert hub.state("s => s.windows.some(w => w.id === 'w-ap-week')") is False
    page.click(SLOT.format("yes"))
    page.click("#jv-rail-fan .jv-rail__card[data-ref=ap-week]")
    page.wait_for_selector("jv-window[window-id=w-ap-week]")
    assert hub.state("s => s.rail.slots.yes.items.length") == 0 and page.is_hidden("#jv-rail-fan")


def test_a_thing_without_a_window_opens_where_it_lives(hub):
    page = hub.scene("now-rail")
    page.click(SLOT.format("homework"))
    page.click("#jv-rail-fan .jv-rail__card[data-ref=due-lab4]")
    page.wait_for_function("location.hash === '#/life/chem-142'")
    assert page.is_visible("#rail .jv-rail__bar")  # the Rail is on every tab


def test_marks_show_as_notches_and_clear_by_hover_or_mark_all_seen_never_by_being_shown(hub):
    page = hub.scene("now-marks")
    for name in ("homework", "jarvis"):
        assert page.is_visible(SLOT.format(name) + " .jv-rail__notch")
    assert page.is_hidden(SLOT.format("today") + " .jv-rail__notch")
    assert "1 new since you looked" in page.get_attribute(SLOT.format("homework"), "aria-label")
    page.click(SLOT.format("homework"))
    card = page.locator("#jv-rail-fan .jv-rail__card[data-ref=due-pps7]")
    assert "Due moved Wed 8 pm → Thu 11:59 pm" in card.inner_text()
    page.mouse.move(5, 300)
    page.wait_for_timeout(1_000)
    assert marks(hub) == ["due-pps7", "jarvis:said"]  # open and on screen for a second: still marked
    box = card.bounding_box()
    page.mouse.move(box["x"] + 60, box["y"] + 20)
    page.wait_for_function("!('due-pps7' in window.__jarvis.store.state.marks)", timeout=2_000)
    assert page.is_hidden(SLOT.format("homework") + " .jv-rail__notch")
    page.click("#jv-rail-fan [data-all-seen]")
    page.wait_for_function("Object.keys(window.__jarvis.store.state.marks).length === 0")
    assert page.is_hidden(SLOT.format("jarvis") + " .jv-rail__notch")


def test_keyboard_focus_on_what_jarvis_said_clears_its_mark(hub):
    page = hub.scene("now-marks")
    page.keyboard.press("Alt+5")
    page.keyboard.press("Enter")
    assert page.is_visible("#jv-rail-fan .jv-rail__said")
    assert "On track. PPS 7 is half done" in page.inner_text("#jv-rail-fan .jv-rail__said")
    page.focus("#jv-rail-fan .jv-rail__said")
    page.wait_for_function("!('jarvis:said' in window.__jarvis.store.state.marks)")


def test_ambient_shows_only_filled_slots_and_never_clears_by_hover(hub):
    page = hub.scene("now-ambient-rail")
    shown = page.eval_on_selector_all("#rail .jv-rail__slot", "n => n.filter(b => b.checkVisibility({ visibilityProperty: true })).map(b => b.dataset.slot)")
    assert shown == ["today", "homework", "jarvis", "parked"]
    # the empty ones keep their place (film review S7: the row never re-centres when a slot fills or he wakes it)
    vacant = page.evaluate("[...document.querySelectorAll('#rail .jv-rail__slot')].filter(b => b.hasAttribute('data-vacant')).map(b => [b.dataset.slot, b.getBoundingClientRect().width >= 32])")
    assert vacant == [["yes", True], ["messages", True]]
    page.hover(SLOT.format("homework"))
    page.wait_for_timeout(1_000)
    assert marks(hub) == ["due-pps7", "jarvis:said"]


def test_tier_two_things_hide_when_others_are_present(hub):
    page = hub.scene("component:rail", state="others-present-tier-2-hidden")
    assert page.inner_text(".jv-gallery jv-rail .jv-rail__slot[data-slot=jarvis] .jv-rail__count") == "1"
    page = hub.scene("component:rail", state="filled")
    assert page.inner_text(".jv-gallery jv-rail .jv-rail__slot[data-slot=jarvis] .jv-rail__count") == "2"


def test_voice_focus_snaps_brackets_onto_the_slot(hub):
    page = hub.scene("now-focus")
    assert page.get_attribute(SLOT.format("homework"), "data-focus") == ""
    assert page.is_visible(SLOT.format("homework") + " .jv-rail__brackets")
    assert page.locator("#rail .jv-rail__slot[data-focus]").count() == 1
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'ui.focus', ts: '2026-11-16T15:40:30', data: {ref: 'rail:jarvis', until: '2026-11-16T15:41:00'}})")
    page.wait_for_selector(SLOT.format("jarvis") + "[data-focus]")
    assert page.locator("#rail .jv-rail__slot[data-focus]").count() == 1


def test_new_marks_are_announced_politely_at_most_once_a_minute(hub):
    page = hub.scene("now-rail")
    page.evaluate("""(() => { window.__said = [];
        new MutationObserver(() => { const t = document.getElementById('jv-live-polite').textContent; if (t) window.__said.push(t); })
          .observe(document.getElementById('jv-live-polite'), {childList: true, characterData: true, subtree: true});
        const {store} = window.__jarvis, at = '2026-11-16T15:41:00';
        store.apply({v: 2, type: 'marks.updated', ts: at, data: {marks: {'due-lab4': {what: 'Due moved Thu 5 pm → Fri 5 pm', at}}}}); })()""")
    page.wait_for_function("window.__said.length === 1", timeout=3_000)
    page.evaluate("""(() => { const {store} = window.__jarvis, at = '2026-11-16T15:41:10';
        store.apply({v: 2, type: 'marks.updated', ts: at, data: {marks: {'due-lab4': {what: 'x', at}, 'd-review': {what: 'Review GE 122 lecture 21 moved 4 pm → 5 pm', at}}}}); })()""")
    page.wait_for_timeout(2_000)
    said = page.evaluate("window.__said")
    assert said == ["New since you looked: Homework 1."]  # the second waits for the minute to pass


def test_the_fan_rises_once_with_no_card_stagger_when_motion_is_on(browser, hub_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="no-preference")
    page = context.new_page()
    page.goto(f"{hub_url}/?scene=now-rail&theme=night&motion=full")
    page.wait_for_selector("html[data-ready]")
    page.click(SLOT.format("homework"))
    delays = page.eval_on_selector_all("#jv-rail-fan .jv-rail__cards > li", "n => n.map(li => getComputedStyle(li).animationDelay)")
    context.close()
    assert delays == ["0s", "0s", "0s", "0s"]  # serious mode (v0.6.0): the fan rises once; no card stagger


@pytest.mark.parametrize("theme", ["night", "day"])
def test_the_gallery_draws_every_state_without_errors(hub, theme):
    page = hub.scene("component:rail", theme=theme)
    assert page.locator(".jv-gallery jv-rail").count() == 10
    assert page.locator(".jv-rail__legend .jv-glance").count() == 7
    assert hub.problems == []


def test_the_live_hub_makes_a_mark_when_jarvis_speaks_and_keeps_the_line(hub):
    page = hub.open()
    page.evaluate("window.__jarvis.bridge.act('less', 'rail-test')")  # Jarvis toasts "Less of this from now on."
    page.wait_for_function("'jarvis:said' in window.__jarvis.store.state.marks")
    page.wait_for_selector(SLOT.format("jarvis") + " .jv-rail__notch:not([hidden])")
    assert hub.state("s => s.rail.slots.jarvis.said[0].text") == "Less of this from now on."
    assert "due-pps7" in hub.state("s => s.rail.slots.homework.items.map(i => i.ref)")  # the server built the Rail from what it knows
    page.evaluate("window.__jarvis.bridge.act('seen', 'all')")
    page.wait_for_selector(SLOT.format("jarvis") + " .jv-rail__notch", state="hidden")


@pytest.mark.parametrize("theme", ["night", "day"])
def test_the_open_fan_is_solid(hub, theme):
    # walkthrough B9: the clock and the resume line showed through the open fan
    page = hub.scene("now-rail-open", theme=theme)
    colour = page.evaluate("getComputedStyle(document.getElementById('jv-rail-fan')).backgroundColor")
    assert colour.startswith("rgb(") or colour.endswith(", 1)"), colour  # opaque under the panel's tint
    assert hub.problems == []


# ---- HUD v3: the badges, the tools and the page dots ------------------------------------------------------------
def test_a_slot_that_wants_him_shows_its_glance_shape_as_the_badge(hub):
    page = hub.scene("now-wants", theme="night")  # your yes waiting, Today soon, Homework critical
    shapes = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#rail .jv-rail__slot')].map(b => {
        const mark = b.querySelector('.jv-rail__shape path');
        return [b.dataset.slot, mark ? [mark.getAttribute('d').split(' ').length, getComputedStyle(b.querySelector('.jv-rail__badge')).color] : null]; }))""")
    warn, crit = page.evaluate("""() => { const p = document.createElement('i'); document.body.append(p);
        p.style.color = 'var(--warn)'; const w = getComputedStyle(p).color; p.style.color = 'var(--crit)'; const c = getComputedStyle(p).color;
        p.remove(); return [w, c]; }""")
    assert shapes["yes"][1] == warn and shapes["today"][1] == warn and shapes["homework"][1] == crit
    assert shapes["messages"] is None and shapes["jarvis"] is None and shapes["parked"] is None  # nothing wants him there: a plain count
    # shape, not colour alone: the square, the diamond and the triangle are different paths, and the words are in the label
    kinds = page.evaluate("[...document.querySelectorAll('#rail .jv-rail__shape path')].map(p => p.closest('.jv-rail__slot').dataset.slot + ':' + p.getAttribute('d'))")
    assert len(set(k.split(":")[1] for k in kinds)) == 3
    assert "worst: Now" in page.get_attribute(SLOT.format("homework"), "aria-label")
    assert "worst: Your yes" in page.get_attribute(SLOT.format("yes"), "aria-label")


def test_the_search_glyph_opens_the_command_bar_and_is_on_the_row(hub):
    page = hub.scene("now-calm", theme="night")
    tool = page.locator("#rail .jv-rail__tool[data-tool=search]")
    assert tool.is_visible() and tool.get_attribute("aria-label") == "Go anywhere or ask Jarvis"
    tool.click()
    page.wait_for_function("document.getElementById('command-bar').isOpen")
    page.keyboard.press("Escape")
    # one Tab stop for the row: the arrows reach the tools after the slots
    page.keyboard.press("Alt+6")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.dataset.tool") == "search"
    page.keyboard.press("ArrowRight")  # the Stage glyph is hidden with nothing up: round to the first slot
    assert page.evaluate("document.activeElement.dataset.slot") == "yes"
    assert hub.problems == []


def test_the_stage_glyph_counts_the_windows_up_and_brings_the_stage_forward(hub):
    page = hub.scene("now", theme="night")  # four windows on the Stage
    tool = page.locator("#rail .jv-rail__tool[data-tool=stage]")
    assert tool.is_visible() and tool.get_attribute("aria-label") == "Show the Stage: 4 windows up"
    assert tool.locator(".jv-rail__count").inner_text() == "4"
    with page.context.expect_page() as opened:
        tool.click()
    stage = opened.value
    stage.wait_for_selector("html[data-ready]")
    assert stage.evaluate("location.hash") == "#/stage"
    assert stage.locator("#rail .jv-rail__tool[data-tool=stage]").is_hidden()  # the Stage doesn't point at itself
    stage.close()
    page.click(".jv-page-dots__dot[data-key=today]")  # away from the calm home the glyph steps aside
    page.wait_for_function("location.hash === '#/today'")
    assert tool.is_hidden()


def test_page_dots_replace_the_tabs_and_work_with_the_keyboard(hub):
    page = hub.scene("now-calm-waiting", theme="night")
    assert page.locator("#chrome jv-tabs").is_hidden()  # no pills in the top-right corner
    dots = page.locator("#rail jv-page-dots .jv-page-dots__dot")
    assert dots.count() == 5
    assert page.get_attribute("#rail jv-page-dots nav", "aria-label") == "Views"
    names = page.eval_on_selector_all("#rail .jv-page-dots__dot", "n => n.map(a => [a.textContent.trim(), a.getAttribute('aria-current'), a.getAttribute('aria-keyshortcuts')])")
    assert names == [["Now", "page", "1"], ["Today", None, "2"], ["Life", None, "3"], ["Activity, 1 waiting for your yes", None, "4"], ["Controls", None, "5"]]
    # under the icon row, centred with it
    row, dot = page.locator("#rail .jv-rail__bar").bounding_box(), page.locator("#rail jv-page-dots").bounding_box()
    assert dot["y"] >= row["y"] + row["height"] - 1 and abs((dot["x"] + dot["width"] / 2) - (row["x"] + row["width"] / 2)) < 30
    page.focus(".jv-page-dots__dot[data-key=now]")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.dataset.key") == "life"
    page.keyboard.press("Enter")
    page.wait_for_function("location.hash === '#/life'")
    assert page.get_attribute("#rail .jv-page-dots__dot[data-key=life]", "aria-current") == "page"
    page.keyboard.press("2")  # the number keys still work
    page.wait_for_function("location.hash === '#/today'")
    assert page.get_attribute("#rail .jv-page-dots__dot[data-key=today]", "aria-current") == "page"
    assert hub.problems == []


def test_the_row_is_the_same_on_the_hub_ambient_and_the_stage(hub):
    hub.page.set_viewport_size({"width": 1920, "height": 1080})
    seen = {}
    for name, (scene, extra) in {"hub": ("now-calm", {}), "ambient": ("now-ambient", {"size": "ambient"}),
                                 "stage": ("stage-active", {"window": "stage"})}.items():
        page = hub.scene(scene, theme="night", **extra) if name != "stage" else hub.open("#/stage", scene=scene, theme="night", window="stage")
        seen[name] = page.evaluate("""() => { const bar = document.querySelector('#rail .jv-rail__bar').getBoundingClientRect();
            return [document.querySelectorAll('#rail .jv-rail__slot').length, !!document.querySelector('#rail jv-page-dots'),
                    Math.round(bar.height), Math.abs(bar.left + bar.width / 2 - innerWidth / 2) < 40, bar.bottom > innerHeight - 80]; }""")
    assert all(v == [6, True, 28, True, True] for v in seen.values()), seen
    assert hub.problems == []


# ---- F1 (his v0.4.1 report): what opens from the bottom row is always on top -------------------------------------
CROWD = """() => { const fan = document.getElementById('jv-rail-fan').getBoundingClientRect();
    const wins = [...document.querySelectorAll('.jv-stage__canvas > jv-window:not([leaving])')];
    const box = wins[0].offsetParent.getBoundingClientRect();
    // every window dragged under the fan's cards, with each kind of raised window: the one Jarvis means (40), named
    // (40), what he works in (41) and the hovered or "Why?" one (45)
    wins.forEach((w, i) => { w.style.left = `${fan.left - box.left + i * 60}px`; w.style.top = `${fan.top - box.top + 20 + i * 30}px`; });
    wins[0].setAttribute('active', ''); wins[1].setAttribute('named', ''); wins[2].setAttribute('data-show-why', '');
    return wins.length; }"""
HITS = """() => [...document.querySelectorAll('#jv-rail-fan .jv-rail__card')].map((c) => {
    const r = c.getBoundingClientRect(), hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return [c.dataset.ref, !!hit?.closest('#jv-rail-fan')]; })"""


@pytest.mark.parametrize("width,height", [(1920, 1080), (1440, 900)])
def test_the_open_fan_sits_above_every_stage_window(hub, width, height):
    hub.page.set_viewport_size({"width": width, "height": height})
    page = hub.scene("stage-crowded", theme="night", window="stage")
    page.click(SLOT.format("homework"))
    assert page.is_visible("#jv-rail-fan")
    assert page.evaluate(CROWD) >= 3
    hits = page.evaluate(HITS)
    assert len(hits) >= 4 and all(ok for _, ok in hits), hits
    # the windows step back one level while it is open: dimmer, and they don't take the pointer
    look = page.eval_on_selector(".jv-stage__canvas > jv-window[active]", "w => [getComputedStyle(w).pointerEvents, Number(getComputedStyle(w).opacity)]")
    assert look[0] == "none" and look[1] < 0.8, look
    page.keyboard.press("Escape")  # Esc closes it, and the windows come back
    assert page.is_hidden("#jv-rail-fan")
    assert page.eval_on_selector(".jv-stage__canvas > jv-window[active]", "w => getComputedStyle(w).pointerEvents") == "auto"
    page.click(SLOT.format("homework"))
    page.mouse.click(width - 40, 200)  # a click outside closes it too
    assert page.is_hidden("#jv-rail-fan")
    assert hub.problems == []
