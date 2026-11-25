"""Shell, navigation and controls (F6): ARIA states, radio groups, live resizing, setting deep links, phone bar,
and the ambient chrome's contrast."""
import pytest

ARIA_STATES = ("aria-checked", "aria-pressed", "aria-expanded", "aria-selected")
EMPTY_STATES = f"""() => [...document.querySelectorAll('{", ".join(f"[{a}]" for a in ARIA_STATES)}')]
  .flatMap(e => {list(ARIA_STATES)}.filter(a => e.hasAttribute(a) && !['true', 'false', 'mixed'].includes(e.getAttribute(a)))
  .map(a => e.localName + ' ' + a + '=' + JSON.stringify(e.getAttribute(a))))"""


def _ratio(fg, bg):
    def lum(rgb):
        ch = [c / 255 for c in rgb]
        ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def test_aria_booleans_render_as_words(hub):
    page = hub.scene("shell")
    out = page.evaluate("""async () => { const { html } = await import('/core/dom.js');
      return [String(html`<b aria-pressed="${false}" aria-expanded='${true}' aria-checked=${false}>`),
              String(html`<b data-x="${false}" hidden-${false}>${false}</b>`)]; }""")
    assert out[0] == """<b aria-pressed="false" aria-expanded='true' aria-checked=false>"""
    assert out[1] == '<b data-x="" hidden->' + "</b>"  # outside aria-* attributes false still renders as nothing
    for scene, size in (("controls", None), ("phone-now", "phone"), ("activity", None), ("life", None), ("now-full", None),
                        ("component:command-bar", None)):
        page = hub.scene(scene, size=size)
        assert page.evaluate(EMPTY_STATES) == [], scene
    assert hub.problems == []


def test_radio_groups_have_one_tab_stop_and_arrow_keys(hub):
    page = hub.scene("controls")
    stops = page.evaluate("""() => [...document.querySelectorAll('[role=radiogroup]')]
      .map(g => [g.getAttribute('aria-label'), [...g.querySelectorAll('[role=radio]')].filter(r => r.tabIndex === 0).length])""")
    assert stops and all(n == 1 for _, n in stops) and "game_mode" not in dict(stops)
    page.focus("[role=radiogroup][aria-label=Theme] [role=radio][tabindex='0']")
    page.keyboard.press("ArrowRight")
    page.wait_for_function("window.__jarvis.store.state.settings.theme === 'day'")
    active = "[document.activeElement.textContent, document.activeElement.getAttribute('aria-checked')]"
    assert page.evaluate(active) == ["Daylight", "true"]
    page.keyboard.press("ArrowLeft")
    page.wait_for_function("window.__jarvis.store.state.settings.theme === 'night'")
    page.keyboard.press("End")
    assert page.evaluate(active) == ["Sunset", "true"]
    page.keyboard.press("Tab")  # leaves the group, landing on the next group's chosen option
    assert page.evaluate("document.activeElement.closest('[role=radiogroup]').getAttribute('aria-label')") == "Motion"
    assert page.evaluate("document.activeElement.getAttribute('aria-checked')") == "true"
    assert hub.problems == []


def test_layout_follows_the_window_live(hub):
    page = hub.open("#/controls")
    seen = []
    for width, height in ((1440, 900), (1000, 800), (700, 800), (390, 844), (320, 640), (1440, 900)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(120)
        seen.append(page.evaluate("""() => { const c = document.getElementById('chrome');
          return [document.documentElement.dataset.size, c.previousElementSibling?.id || '', c.nextElementSibling.id,
          document.documentElement.scrollWidth <= innerWidth]; }"""))
    assert [s[0] for s in seen] == ["full", "laptop", "phone", "phone", "phone", "full"]
    # on the phone the tabs follow the view and the Rail row (which sits above them); elsewhere they lead
    assert all((before == "foot") == (size == "phone") for size, before, _, _ in seen)
    assert all((after == "stage") == (size != "phone") for size, _, after, _ in seen)
    assert all(fits for *_, fits in seen)  # no sideways scroll, down to 320 px


def test_phone_tab_order_matches_the_screen(hub):
    # a11y review: on the phone the Rail row sits above the tabs but came after them in Tab order
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("phone-now", size="phone")
    order = page.evaluate("""() => { const stops = [...document.querySelectorAll('#rail .jv-rail__slot[tabindex="0"], #tabs a, #tabs button')]
        .filter((e) => e.checkVisibility());
      const rail = stops.find((e) => e.closest('#rail')), tab = stops.find((e) => e.closest('#tabs'));
      return [!!(rail.compareDocumentPosition(tab) & Node.DOCUMENT_POSITION_FOLLOWING), rail.getBoundingClientRect().bottom <= tab.getBoundingClientRect().top + 1]; }""")
    assert order == [True, True]
    assert hub.problems == []
    assert hub.problems == []


def test_command_bar_setting_focuses_its_row(hub):
    page = hub.scene("now-awake")
    page.keyboard.press("Control+k")
    page.keyboard.type("pause memory")
    assert page.inner_text("#jv-cmd-0").startswith("Pause memory")
    page.wait_for_function("document.getElementById('jv-live-polite').textContent.includes('result')")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement?.closest('[data-setting]')?.dataset.setting === 'memory_paused'")
    assert page.evaluate("location.hash") == "#/controls/memory_paused"
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Pause memory"
    top = page.evaluate("document.activeElement.getBoundingClientRect().top")
    assert 0 < top < 900
    assert "Pause memory" in page.text_content(".jv-crumbs")
    assert hub.problems == []


def test_every_controls_group_has_at_most_four_rows(hub):
    page = hub.scene("controls")
    groups = page.evaluate("[...document.querySelectorAll('.jv-controls__grid > section')].map((g) => [g.querySelector('h2').textContent.trim(), g.querySelectorAll(':scope > .jv-row').length])")
    assert [name for name, _ in groups] == ["Interruptions", "Voice // Sound", "Approvals", "Look", "Screens", "Data // Privacy"]
    assert all(1 <= rows <= 4 for _, rows in groups), groups
    assert dict(groups)["Look"] == 3 and dict(groups)["Screens"] == 2  # theme, motion, plants · ambient screen, where Jarvis shows things


def test_controls_show_four_sources_and_the_rest_behind_more(hub):
    page = hub.scene("controls")
    sources = page.locator("[data-setting=sources] .jv-switch")
    shown = page.evaluate("[...document.querySelectorAll('[data-setting=sources] .jv-switch')].filter(e => e.checkVisibility()).length")
    assert shown <= 4 < sources.count()
    page.click(".jv-controls__more > summary")
    hidden = page.locator(".jv-controls__more .jv-switch").first
    hidden.click()  # a change re-draws Controls; "More" stays open
    page.wait_for_timeout(100)
    assert page.evaluate("document.querySelector('.jv-controls__more').open") is True
    assert hub.problems == []


def test_phone_orb_sits_in_the_tab_bar(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    for scene in ("phone-now", "phone-activity", "phone-controls"):
        page = hub.scene(scene, size="phone")
        box = page.evaluate("""() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
          const orb = r('#orb'), bar = r('#chrome'), stage = r('#stage'), tabs = r('#chrome .jv-tabs__list');
          return [orb.top >= bar.top - 0.5 && orb.bottom <= bar.bottom + 0.5, orb.top >= stage.bottom - 0.5, tabs.right <= orb.left]; }""")
        assert box == [True, True, True], scene
    assert page.evaluate("document.querySelector('#tabs nav').getAttribute('aria-label')") == "Views"
    assert hub.problems == []


ROW_COLOURS = """() => {
  const rgb = (s) => s.match(/[\\d.]+/g).map(Number);
  const probe = document.createElement('i'); probe.style.color = 'var(--canvas)'; document.body.append(probe);
  const canvas = rgb(getComputedStyle(probe).color); probe.remove();
  const opacity = (e) => { let op = 1; for (let n = e; n; n = n.parentElement) op *= +getComputedStyle(n).opacity; return op; };
  const shown = (e) => e.checkVisibility({ visibilityProperty: true });
  const one = (e, kind, colour) => [kind, e.closest('[data-slot]')?.dataset.slot || e.closest('[data-key]')?.dataset.key || 'status', opacity(e), rgb(colour), canvas];
  return [...[...document.querySelectorAll('#rail .jv-rail__slot .jv-icon')].filter(shown).map(e => one(e, 'icon', getComputedStyle(e).color)),
          ...[...document.querySelectorAll('#rail .jv-rail__count')].filter(shown).map(e => one(e, 'word', getComputedStyle(e).color)),
          ...[...document.querySelectorAll('#status .jv-status-line__state')].map(e => one(e, 'word', getComputedStyle(e).color)),
          ...[...document.querySelectorAll('#rail .jv-page-dots__dot')].map(e => one(e, 'icon', getComputedStyle(e, '::before').backgroundColor))]; }"""


def _over(fg, bg):
    """A colour with alpha, composited over the backdrop."""
    if len(fg) < 4:
        return fg[:3]
    a = fg[3]
    return [fg[i] * a + bg[i] * (1 - a) for i in range(3)]


def test_the_bottom_row_is_quiet_but_readable(hub):
    # HUD v3: no pills in the corner; the icon row, the page dots and the status word are tiny but never faint:
    # words ≥ 4.5:1, icons and dots ≥ 3:1 on the backdrop, at full opacity, awake and resting, in both themes
    for theme in ("night", "day"):
        for scene in ("now-calm", "now-ambient"):
            page = hub.scene(scene, theme=theme)
            assert page.locator("#chrome .jv-tabs__tab:visible").count() == 0, (theme, scene)
            items = page.evaluate(ROW_COLOURS)
            assert len(items) >= 15, (theme, scene, items)
            for kind, name, opacity, fg, bg in items:
                assert opacity == 1, (theme, scene, name)
                assert _ratio(_over(fg, bg[:3]), bg[:3]) >= (4.5 if kind == "word" else 3), (theme, scene, kind, name, fg, bg)
    assert hub.problems == []


@pytest.mark.parametrize("theme", ["night", "day"])
def test_demo_chip_is_neutral_not_amber(hub, theme):
    # film review S6: amber means only "needs you"; the DEMO chip is a quiet label
    page = hub.scene("now-awake", theme=theme)
    got = page.evaluate("""() => { const chip = document.getElementById('demo-chip'); chip.hidden = false;
      const probe = document.createElement('span'); probe.style.color = 'var(--text-3)'; probe.style.borderColor = 'var(--warn)';
      document.body.append(probe); const want = getComputedStyle(probe).color, warn = getComputedStyle(probe).borderColor; probe.remove();
      const cs = getComputedStyle(chip); return [cs.color === want, cs.color !== warn && cs.borderTopColor !== warn, cs.backgroundColor]; }""")
    assert got == [True, True, "rgba(0, 0, 0, 0)"], got


def test_the_stage_window_names_itself_and_keeps_the_orb_in_a_landmark(hub):
    # a11y review NICE 13: the Stage's main said "Jarvis hub" and its docked orb sat outside every landmark
    page = hub.open("#/stage", window="stage")
    assert page.get_attribute("#stage", "aria-label") == "Jarvis Stage"
    assert page.evaluate("!!document.querySelector('footer#foot #orb')")
    page = hub.open("#/now")  # the hub keeps its own name and order
    assert page.get_attribute("#stage", "aria-label") == "Jarvis hub"
    assert page.evaluate("document.getElementById('dock').parentElement === document.body")
    assert hub.problems == []
