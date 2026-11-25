"""The Stage (N9, HUD v2 §6.5): the hub's home stays calm and the windows Jarvis pulls up go to the Stage, a
separate window; "Stage · N" on the home; standby when the last one is put away; "On the hub" brings back the
old behaviour."""

STATE = "window.__jarvis.store.state"
PUSH = """(w) => window.__jarvis.store.apply({ v: 2, type: 'window.push', ts: '2026-11-16T15:42:00', data: w })"""
NOTE = {"id": "w-note", "type": "notice", "title": "Lab 4", "data": {"text": "Room changed to ENGR 2A30"}, "pushed": "2026-11-16T15:42:00"}


def home_windows(page):
    return page.locator("jv-view-now jv-window").count()


def test_the_home_never_shows_pushed_windows_with_the_stage_on(hub):
    page = hub.scene("now", theme="night")
    assert hub.state("s => s.settings.stage") == "window" and hub.state("s => s.windows.length") == 4
    assert home_windows(page) == 0
    assert page.get_attribute("html", "data-home") == "calm"
    assert page.is_visible(".jv-now__ambient jv-orb") and not page.is_visible(".jv-amb__clock")  # awake: the orb alone, no clock (HUD v3)
    assert not page.is_visible(".jv-dock #orb")  # one orb: the big one
    chip = page.locator("#rail [data-tool=stage]")  # the Stage chip is a glyph on the icon row now
    assert chip.is_visible() and chip.locator(".jv-rail__badge").inner_text() == "4"
    assert chip.get_attribute("aria-label") == "Show the Stage: 4 windows up"
    page.evaluate(PUSH, NOTE)  # another window arrives: still nothing on the home, the glyph counts it
    page.wait_for_function("document.querySelector('#rail [data-tool=stage] .jv-rail__badge')?.textContent === '5'", timeout=2_000)
    assert home_windows(page) == 0
    assert not hub.problems, hub.problems


def test_the_chip_hides_with_nothing_up_and_its_count_is_the_windows_up(hub):
    page = hub.scene("now-ambient", theme="night")
    assert not page.is_visible("#rail [data-tool=stage]")
    assert page.evaluate("import('/views/now/now.js').then(m => [m.stageCount({ windows: [{}, {}] }), m.stageCount({})])") == [2, 0]


def test_the_chip_opens_the_stage_window(hub):
    page = hub.scene("now", theme="night")
    with page.context.expect_page() as opened:
        page.click("#rail [data-tool=stage]")
    stage = opened.value
    stage.wait_for_selector("html[data-ready]")
    assert "window=stage" in stage.url and stage.evaluate("window.name") == "jarvis-stage"
    assert stage.evaluate("location.hash") == "#/stage"
    stage.close()


def test_the_stage_shows_the_windows_and_docks_them_on_close(hub):
    page = hub.scene("stage-active", theme="night")
    assert page.get_attribute("html", "data-window") == "stage" and page.get_attribute("html", "data-stage") == "active"
    assert not page.is_visible("jv-tabs") and not page.is_visible(".jv-chrome")  # no tabs or header on the Stage
    wins = page.locator(".jv-stage__canvas > jv-window:not([leaving])")
    assert wins.count() == 4 and page.locator("jv-now-card").count() == 0  # the now card stays on the hub
    first = page.eval_on_selector(".jv-stage__canvas > jv-window", "e => e.getAttribute('window-id')")
    assert first == hub.state("s => s.windows.at(-1).id")  # the newest one leads
    assert page.locator("jv-window[active]").count() == 1
    assert page.is_visible(".jv-dock #orb") and page.is_visible("jv-rail") and page.is_visible("jv-status-line")
    assert page.is_visible(".jv-stage__pills [data-do=hub]") and page.is_visible("[data-do=tidy]") and page.is_visible("[data-do=clear]")
    page.click("jv-window[window-id=w-due-pps7] [data-tool=close]")
    page.wait_for_selector("jv-window[window-id=w-due-pps7]", state="detached", timeout=2_000)
    assert hub.state("s => s.rail.slots.homework.items.filter(i => i.window).map(i => i.window.id)") == ["w-due-pps7"]  # docked
    assert not hub.problems, hub.problems


def test_the_stage_fades_to_standby_when_the_last_window_is_put_away(hub):
    page = hub.scene("stage-active", theme="night")
    assert not page.is_visible(".jv-stage__standby jv-orb")
    page.evaluate("window.__jarvis.store.apply({ v: 2, type: 'orb.state', ts: '2026-11-16T15:42:00', data: { state: 'idle' } })")  # he stopped talking
    page.click("[data-do=clear]")  # CLEAR VIEW: everything docks into the Rail
    page.wait_for_function("document.documentElement.dataset.stage === 'standby'", timeout=2_000)
    assert hub.state("s => s.windows.length") == 0
    assert hub.state("s => Object.values(s.rail.slots).flatMap(x => x.items).filter(i => i.window).length") >= 3
    page.wait_for_selector(".jv-stage__canvas > jv-window", state="detached")
    assert page.is_visible(".jv-stage__standby jv-orb") and page.is_visible(".jv-stage__clock")
    # the rings stay out a moment after Jarvis spoke (REST_LINGER_MS), then go back into the sphere
    page.wait_for_function("document.querySelector('.jv-stage__orb').getAttribute('state') === 'standby'", timeout=5_000)
    assert not page.is_visible(".jv-dock #orb") and not page.is_visible("[data-do=clear]") and page.is_visible("[data-do=hub]")
    page.evaluate(PUSH, NOTE)  # something new: back to the windows
    page.wait_for_selector("jv-window[window-id=w-note]")
    assert page.get_attribute("html", "data-stage") == "active"


def test_stage_empty_is_standby(hub):
    page = hub.scene("stage-empty", theme="night")
    assert page.get_attribute("html", "data-stage") == "standby"
    assert page.locator(".jv-stage__canvas > jv-window").count() == 0
    assert page.is_visible(".jv-stage__orb") and page.is_visible(".jv-stage__clock")


def test_the_stage_never_scrolls_and_shows_at_most_five(hub):
    for w, h in ((1920, 1080), (1440, 900), (1280, 720)):
        hub.page.set_viewport_size({"width": w, "height": h})
        for scene in ("stage-active", "stage-crowded", "stage-waiting", "stage-focus"):
            page = hub.scene(scene, theme="night")
            page.wait_for_timeout(50)
            box = page.evaluate("(() => { const s = document.getElementById('stage'); return [s.scrollHeight, s.clientHeight]; })()")
            assert box[0] <= box[1] + 1, (scene, w, h, box)
            n = page.locator(".jv-stage__canvas > jv-window:not([leaving])").count()
            assert 1 <= n <= 5, (scene, w, h, n)
            # nothing runs into the bottom band (the caption's line and the docked orb)
            bottom = page.evaluate("Math.max(...[...document.querySelectorAll('.jv-stage__canvas > jv-window:not([leaving])')].map(e => e.getBoundingClientRect().bottom))")
            band = page.evaluate("document.getElementById('foot').getBoundingClientRect().top")
            assert bottom <= band, (scene, w, h, bottom, band)
    hub.page.set_viewport_size({"width": 1920, "height": 1080})  # (smaller screens step more aside: test_stage_fit.py)
    page = hub.scene("stage-crowded", theme="night")
    page.wait_for_function(f"{STATE}.windows.length === 5", timeout=2_000)  # the sixth docked, never dropped


def test_the_voice_focus_lights_up_on_the_stage(hub):
    page = hub.scene("stage-focus", theme="night")
    assert page.get_attribute("jv-window[window-id=w-due-pps7]", "named") == ""
    assert page.get_attribute("jv-window[window-id=w-due-pps7]", "active") == ""


def test_tidy_puts_the_windows_back_in_the_order_they_came(hub):
    page = hub.scene("stage-active", theme="night")
    out = page.evaluate("""import('/views/stage/stage.js').then(m => [
        m.tidyOrder([{id: 'a', pushed: '2026-11-16T10:00'}, {id: 'b', pushed: '2026-11-16T09:00'}, {id: 'c'}]),
        m.tidyOrder([{id: 'a', pushed: '1'}, {id: 'b', pushed: '2'}])])""")
    assert out == [["c", "b", "a"], None]
    page.evaluate("window.__jarvis.bridge.act('move', 'w-ge122', { to: 'left' })")
    page.wait_for_function(f"{STATE}.windows[0].id === 'w-ge122'")
    page.click("[data-do=tidy]")
    page.wait_for_function(f"{STATE}.windows.map(w => w.id).join() === 'w-next,w-due-pps7,w-pps7,w-ge122'", timeout=2_000)


def test_on_the_hub_brings_the_windows_back_to_the_home_page(hub):
    page = hub.scene("now", theme="night")
    assert home_windows(page) == 0
    page.evaluate("window.__jarvis.bridge.act('set', 'stage', { value: 'hub' })")
    page.wait_for_selector(".jv-now__canvas > jv-window[window-id=w-pps7]", timeout=2_000)
    assert page.get_attribute("html", "data-home") is None and not page.is_visible(".jv-now__stage")
    assert page.locator(".jv-now__canvas > jv-window[window-id]").count() == 4 and page.is_visible("jv-now-card")
    page.evaluate("window.__jarvis.bridge.act('set', 'stage', { value: 'window' })")
    page.wait_for_function("document.documentElement.dataset.home === 'calm'", timeout=2_000)
    assert not page.is_visible(".jv-now__canvas")


def test_controls_has_where_jarvis_shows_things(hub):
    page = hub.scene("controls", theme="night")
    row = page.locator("[data-setting=stage]")
    assert "Where Jarvis shows things" in row.inner_text()
    assert row.locator("[role=radio][aria-checked=true]").text_content().strip() == "Stage window"
    row.locator("[role=radio]", has_text="On the hub").click()
    page.wait_for_function(f"{STATE}.settings.stage === 'hub'", timeout=2_000)
    assert page.locator("[data-setting=stage] [role=radio][aria-checked=true]").text_content().strip() == "On the hub"
    page = hub.scene("controls-stage-hub", theme="night")
    assert page.locator("[data-setting=stage] [role=radio][aria-checked=true]").text_content().strip() == "On the hub"


def test_the_stage_window_stays_on_the_stage_and_sends_links_to_the_hub(hub):
    hub.page.add_init_script("window.open = (url, name) => { (window.__opened = window.__opened || []).push([url, name]); return null; }")
    page = hub.open("#/stage", window="stage")
    page.wait_for_selector("jv-view-stage")
    assert page.get_attribute("html", "data-window") == "stage"
    page.evaluate("window.__jarvis.router.go('/life/ge-122')")  # a link inside a Stage window
    assert page.evaluate("location.hash") == "#/stage" and page.locator("jv-view-stage").count() == 1
    assert page.evaluate("window.__opened") == [["", "jarvis-hub"]]  # it went to the hub
    page.evaluate("window.__jarvis.store.apply({ v: 2, type: 'nav.go', ts: '2026-11-16T15:42:00', data: { path: '/today' } })")
    page.wait_for_timeout(50)
    assert page.evaluate("location.hash") == "#/stage"  # the hub follows the conversation; the Stage doesn't
    assert page.evaluate("window.__jarvis.router.back()") is False


def test_the_hub_reports_what_decides_the_stage(hub):
    page = hub.scene("now", theme="night")
    out = page.evaluate("""import('/views/stage/desktop.js').then(m => [
        m.stageReport(window.__jarvis.store.state),
        m.windowsHere({ settings: {} }, { size: 'full' }), m.windowsHere({ settings: { stage: 'window' } }, { size: 'full' }),  // unset = on the hub since v0.17.0
        m.windowsHere({ settings: {} }, { size: 'phone' }), m.windowsHere({ settings: {} }, { stageWindow: true, size: 'full' })])""")
    report, *here = out
    assert report == {"state": {"windows": [{"id": "w-next"}, {"id": "w-due-pps7"}, {"id": "w-pps7"}, {"id": "w-ge122"}], "now_card": {"moment": "between"}, "popped": 0},
                      "settings": {"stage": "window", "game_mode": "auto"}}
    assert here == [True, False, True, True]


def test_the_phone_keeps_its_own_column(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("now", theme="night", size="phone")
    assert page.get_attribute("html", "data-home") is None
    assert page.locator(".jv-now__canvas > jv-window[window-id]").count() == 4


def test_windows_on_the_stage_sit_back_when_jarvis_means_one(hub):
    # depth in the aligned cluster (HUD v2 §14.2): the rest dim, but never scale (a scale would break the shared
    # top baseline and the 16 px gutter)
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("stage-active", theme="night")
    page.wait_for_selector(".jv-stage__canvas > jv-window[window-id]")
    page.evaluate("document.querySelector('.jv-stage__canvas > jv-window[window-id]').setAttribute('active', '')")
    page.wait_for_timeout(500)
    got = page.evaluate("""[...document.querySelectorAll('.jv-stage__canvas > jv-window[window-id]')].map((w) => {
        const c = getComputedStyle(w); return [w.hasAttribute('active'), c.transform, c.opacity]; })""")
    assert len(got) >= 2
    for active, transform, opacity in got:
        assert (transform, opacity) == ("none", "1" if active else "0.88"), got


def test_windows_arrive_out_of_the_orb_once_the_stage_is_on_screen(hub):
    # v0.5.2: "the orb just disappears, reappears at the corner and then the windows pop open". On Laptop A the
    # Stage is hidden until the push, so the beat waits until it is on screen; then the orb slides to the corner
    # while the windows fly out of it.
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("stage-empty", theme="night")
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); }""")
    page.evaluate("""() => import('/views/stage/stage.js').then(({ STAGE_WINDOWS: W }) =>
        window.__jarvis.store.set({ orb: { state: 'speaking', level: 0.6 }, windows: [W.next, W.due] }))""")
    page.wait_for_timeout(100)
    sec = ".jv-stage"
    assert page.evaluate(f"document.querySelector('{sec}').classList.contains('jv-stage--arriving')")  # waiting, orb in the middle
    assert not page.evaluate(f"document.querySelector('{sec}').classList.contains('jv-stage--docking')")
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
        document.dispatchEvent(new Event('visibilitychange')); }""")
    page.wait_for_function(f"document.querySelector('{sec}').classList.contains('jv-stage--docking')", timeout=2000)
    flying = page.evaluate("document.querySelectorAll('.jv-stage__canvas jv-window[window-id]')[0].getAnimations().length")
    assert flying >= 1  # the windows come out of the orb
    page.wait_for_function(f"!document.querySelector('{sec}').classList.contains('jv-stage--docking')", timeout=3000)
    hub.page.emulate_media(reduced_motion="reduce")
