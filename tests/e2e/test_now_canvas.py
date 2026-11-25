"""The Now canvas (F2): the window frame, the window manager and the Now card working together on screen.
v0.3.0 (N4): nothing gets away (close, step-aside, a sixth, CLEAR VIEW and expiry dock into the Rail), one meaning
per mark, "since you looked" notches, and the voice's focus cue."""

STATE = "window.__jarvis.store.state"


def test_first_click_on_pin_or_close_works_on_a_window_that_is_not_active(hub):
    page = hub.scene("now-active")
    assert page.get_attribute("jv-window[window-id=w-next]", "active") is None
    page.click("jv-window[window-id=w-next] [data-tool=pin]")  # one click: pointerdown makes it active, click pins it
    page.wait_for_function(f"{STATE}.windows.find(w => w.id === 'w-next').pinned === true", timeout=2_000)
    assert page.get_attribute("jv-window[window-id=w-next] [data-tool=unpin]", "aria-pressed") == "true"
    assert page.get_attribute("jv-window[window-id=w-due-pps7]", "active") is None
    page.click("jv-window[window-id=w-due-pps7] [data-tool=close]")
    page.wait_for_selector("jv-window[window-id=w-due-pps7]", state="detached", timeout=2_000)
    assert hub.state("s => s.rail.slots.homework.items.filter(i => i.window).map(i => i.window.id)") == ["w-due-pps7"]  # docked, not deleted


def test_bigger_never_makes_a_window_shorter(hub):
    hub.scene("shell")
    out = hub.page.evaluate("import('/core/windows.js').then(m => ['1x1', '2x1', '1x2', '2x2', '3x2', '4x2', 'odd'].map(m.nextSize))")
    assert out == ["2x1", "2x2", "2x2", "3x2", "4x2", "4x2", "2x1"]


def test_the_window_jarvis_means_goes_first_and_the_oldest_unpinned_steps_aside(hub):
    hub.scene("shell")
    out = hub.page.evaluate("""import('/core/windows.js').then(m => {
        const w = [{id:'a'}, {id:'b', pinned:true}, {id:'ask', type:'approval', ref:'ap'}, {id:'c'}, {id:'d'}, {id:'e'}];
        const r = m.onScreen(w, {waiting: new Set(['ap'])});
        return [r.list.map(x => x.id), r.lead]; })""")
    assert out == [["e", "ask", "b", "c", "d"], "e"]  # newest first, then the question, then the rest in order; 'a' left


def test_rows_fit_the_screen_by_shrinking_older_windows_first(hub):
    hub.scene("shell")
    out = hub.page.evaluate("""import('/core/windows.js').then(m => {
        const panels = [{id:'lead', size:'2x2', level:2, rank:9}, {id:'__now', size:'1x2', level:1, rank:10},
          {id:'old', size:'2x1', rank:1}, {id:'mid', size:'2x2', rank:2}, {id:'new', size:'1x2', rank:3}];
        const roomy = m.arrange(panels), tight = m.arrange(panels, {maxRows: 3});
        const crowd = m.arrange([...panels, {id:'oldest', size:'1x1', rank:0}], {maxRows: 2});
        return { roomy: roomy.rows, tight: [tight.rows, Object.fromEntries(tight.sizes), tight.left, tight.spots[0]],
                 crowd: [crowd.rows, crowd.left, crowd.sizes.get('lead'), crowd.sizes.get('__now')] }; })""")
    assert out["roomy"] > 3
    rows, sizes, left, first = out["tight"]
    assert rows <= 3 and left == [] and sizes["lead"] == "2x2" and sizes["__now"] == "1x2"
    assert first["id"] == "lead" and first["col"] == 1 and first["row"] == 1
    assert sizes["old"] == "1x1"  # the oldest gave way first
    rows, left, lead, now = out["crowd"]
    assert rows <= 2 and left == ["oldest"] and lead == "2x2" and now == "1x1"  # the Now card gave way, then the oldest window


def test_now_canvas_never_scrolls_and_shows_at_most_six(hub):
    for w, h in ((1440, 900), (1920, 1080), (1280, 720)):
        hub.page.set_viewport_size({"width": w, "height": h})
        for scene in ("now-full", "now-crowded", "now-active"):
            page = hub.scene(scene)
            page.wait_for_timeout(50)
            stage = page.evaluate("(() => { const s = document.getElementById('stage'); return [s.scrollHeight, s.clientHeight]; })()")
            assert stage[0] <= stage[1] + 1, (scene, w, h, stage)
            n = page.locator(".jv-now__canvas > jv-window:not([leaving])").count()
            assert n <= 6, (scene, w, h, n)
            first = page.eval_on_selector(".jv-now__canvas > jv-window:not([leaving])", "e => e.getAttribute('window-id')")
            assert first == hub.state("s => s.windows.at(-1).id"), (scene, w, h, first)  # the newest one leads
            assert page.locator("jv-window[active]").count() == 1  # the window Jarvis means: one at most


def test_awake_with_nothing_pushed_is_the_orb_with_one_line_for_what_is_next(hub):
    """v0.18.0 (his word, 2026-11-22): with nothing up the hub is the orb, not a clock over the Now card."""
    page = hub.scene("now-awake")
    assert page.is_visible(".jv-now__ambient jv-orb") and not page.is_visible(".jv-now__clock") and not page.is_visible("jv-now-card")
    line = page.locator(".jv-amb__next")
    assert line.inner_text().upper() == "NEXT · REVIEW GE 122 LECTURE 21 · 4:00 PM · YOUR DESK"
    orb, box = page.locator(".jv-now__ambient jv-orb").bounding_box(), line.bounding_box()
    width = page.viewport_size["width"]
    assert abs((box["x"] + box["width"] / 2) - width / 2) < 4 and box["y"] > orb["y"] + orb["height"]
    page = hub.scene("now-active")
    assert not page.is_visible(".jv-now__clock") and not page.is_visible(".jv-amb__next")


def test_the_now_card_does_not_repeat_what_a_window_shows(hub):
    page = hub.scene("now-active")  # windows: next up, PPS 7 due, the file, GE 122
    card = page.inner_text("jv-now-card").upper()
    assert "REVIEW GE 122 LECTURE 21" not in card and "ONE THING" not in card and "READY WHEN YOU ARE" in card
    page = hub.scene("now-awake")  # nothing up: no card at all, the one line under the orb says what's next (v0.18.0)
    assert page.locator("jv-now-card:visible").count() == 0
    assert "REVIEW GE 122 LECTURE 21" in page.inner_text(".jv-amb__next").upper()


def test_closing_a_window_hands_focus_to_the_next_one(hub):
    page = hub.scene("now-active")
    page.focus("jv-window[window-id=w-due-pps7] [data-tool=close]")
    page.keyboard.press("Enter")
    page.wait_for_selector("jv-window[window-id=w-due-pps7]", state="detached")
    where = page.evaluate("(() => { const a = document.activeElement; return [a.tagName, a.closest('jv-window')?.getAttribute('window-id')]; })()")
    assert where == ["BUTTON", "w-pps7"], where  # the tools of the window that came after it
    page.keyboard.press("Tab")  # pin → close
    page.keyboard.press("Enter")  # close that one too
    page.wait_for_selector("jv-window[window-id=w-pps7]", state="detached")
    assert page.evaluate("document.activeElement.tagName") != "BODY"


def test_a_waiting_question_does_not_stop_the_hub_resting(hub):
    hub.scene("shell")
    out = hub.page.evaluate("""import('/core/presence.js').then(m => {
        const base = { ui: {ambient: false}, settings: {}, orb: {state: 'idle'}, approvals: [{id: 'ap', status: 'pending'}] };
        const ask = { id: 'w-ap', type: 'approval', ref: 'ap' }, note = { id: 'w-n', type: 'notice' };
        const at = (windows, path = '/now', extra = {}) => m.idleStep({ ...base, windows, ...extra }, { path, idle: m.IDLE_MS });
        return [at([ask]), at([ask, note]), at([ask, note], '/life'), at([], '/now', {orb: {state: 'speaking'}}),
                m.idleStep({ ...base, windows: [] }, { path: '/now', idle: 1000 })]; })""")
    assert out == ["rest", None, "now", None, None]


# ---- nothing gets away ------------------------------------------------------------------------------------
def all_windows(hub):
    """Every window the hub holds: on screen, plus docked on the Rail."""
    return hub.state("s => [...s.windows.map(w => w.id), ...Object.values(s.rail.slots).flatMap(x => x.items).filter(i => i.window).map(i => i.window.id)]")


def test_windows_that_step_aside_dock_into_the_rail(hub):
    hub.page.set_viewport_size({"width": 1000, "height": 430})  # too small for five windows and the Now card, even as a tight cluster
    page = hub.scene("now-full")
    page.wait_for_function("window.__jarvis.store.state.windows.length < 5")
    on_canvas = page.eval_on_selector_all(".jv-now__canvas > jv-window[window-id]:not([leaving])", "n => n.map(e => e.getAttribute('window-id'))")
    assert sorted(on_canvas) == sorted(hub.state("s => s.windows.map(w => w.id)"))  # nothing held off screen in secret
    assert sorted(all_windows(hub)) == sorted(["w-due-pps7", "w-chart", "w-pps7", "w-ge122", "w-ap-week"])  # nothing lost
    assert "w-chart" in on_canvas  # pinned: it never steps aside


def test_an_older_hub_sending_six_docks_the_extra_one(hub):
    page = hub.scene("now-crowded")
    page.wait_for_function("window.__jarvis.store.state.windows.length === 5")
    assert "w-next" not in all_windows(hub)  # "next up" is a pure view: it just closes
    page.evaluate("""(() => { const {store} = window.__jarvis;
        store.apply({v: 2, type: 'window.push', ts: '2026-11-16T15:42:00', data: {id: 'w-note', type: 'notice', title: 'Note', ref: 'note-1'}}); })()""")
    page.wait_for_function("window.__jarvis.store.state.windows.length === 5")
    assert sorted(all_windows(hub)) == sorted(["w-due-pps7", "w-chart", "w-pps7", "w-ge122", "w-ap-week", "w-note"])


def test_clear_view_docks_everything_and_recall_brings_it_back(hub):
    page = hub.scene("now-active")
    page.evaluate("window.__jarvis.bridge.act('close_all', 'all')")
    page.wait_for_function("window.__jarvis.store.state.windows.length === 0")
    assert sorted(all_windows(hub)) == ["w-due-pps7", "w-ge122", "w-pps7"]  # next up was a pure view
    assert hub.state("s => s.rail.slots.parked.items.filter(i => i.window).map(i => i.ref)") == ["ge-122"]
    assert page.evaluate("window.__jarvis.bridge.act('recall', 'due-pps7')") == {"ok": True}
    page.wait_for_selector("jv-window[window-id=w-due-pps7]")
    assert page.evaluate("window.__jarvis.bridge.act('recall', 'due-pps7')")["ok"] is False  # it's on screen, not on the Rail
    assert page.evaluate("window.__jarvis.bridge.act('archive', 'due-pps7')") == {"ok": True}  # done: the one way it goes
    page.wait_for_selector("jv-window[window-id=w-due-pps7]", state="detached")
    assert "w-due-pps7" not in all_windows(hub)


def test_a_question_that_runs_out_docks_under_your_yes(hub):
    page = hub.scene("now-waiting")
    page.evaluate("""(() => { const {store, bridge} = window.__jarvis;
        store.set({approvals: store.state.approvals.map(a => ({...a, expires: '2026-11-16T15:00:00'}))});
        return bridge.act('less', 'x'); })()""")  # any action first closes offers that ran out, as the hub does
    page.wait_for_selector("jv-window[window-id=w-ap-week]", state="detached")
    item = hub.state("s => s.rail.slots.yes.items[0]")
    assert item["ref"] == "ap-week" and item["window"]["id"] == "w-ap-week"


def test_moves_are_a_real_reorder_never_close_and_push(hub):
    page = hub.scene("now-active")
    page.evaluate("window.__jarvis.store.state.ui.log = []")
    page.evaluate("window.__jarvis.bridge.act('move', 'w-next', {to: 'right'})")
    assert hub.state("s => s.windows.map(w => w.id)") == ["w-due-pps7", "w-pps7", "w-ge122", "w-next"]
    assert hub.state("s => s.ui.log.map(e => e.type)") == ["window.order"]
    page.evaluate("window.__jarvis.bridge.act('order', 'windows', {ids: ['w-ge122']})")
    assert hub.state("s => s.windows.map(w => w.id)") == ["w-ge122", "w-due-pps7", "w-pps7", "w-next"]


def test_windows_stay_clear_of_the_bottom_band(hub):
    for w, h in ((1440, 900), (1280, 720), (1920, 1080)):
        hub.page.set_viewport_size({"width": w, "height": h})
        page = hub.scene("now-full")
        page.wait_for_timeout(50)
        box = page.evaluate("""(() => {
            const wins = [...document.querySelectorAll('.jv-now__canvas > jv-window:not([leaving])')].map(n => n.getBoundingClientRect());
            const foot = document.getElementById('foot').getBoundingClientRect(), orb = document.getElementById('dock').getBoundingClientRect();
            return { bottom: Math.max(...wins.map(r => r.bottom)), right: Math.max(...wins.map(r => r.right)), foot: foot.top, orb: orb.top, orbLeft: orb.left }; })()""")
        assert box["bottom"] <= box["foot"] - 48, (w, h, box)  # room for the caption's line above the Rail
        assert box["bottom"] <= box["orb"] or box["right"] <= box["orbLeft"], (w, h, box)  # never under the docked orb


# ---- one meaning per mark ------------------------------------------------------------------------------
def test_jarvis_means_one_window_and_brackets_only_mean_wants_you(hub):
    page = hub.scene("now-wants")
    means = page.eval_on_selector_all("jv-window[active]", "n => n.map(e => e.getAttribute('window-id'))")
    assert len(means) == 1 and page.locator("jv-window .jv-window__reticle").count() == 0  # no glyph: the bright frame says it
    wants = dict(page.eval_on_selector_all("jv-window[data-wants]", "n => n.map(e => [e.getAttribute('window-id'), e.getAttribute('glance')])"))
    assert wants == {"w-ap-week": "yes", "w-due-pps7": "critical", "w-pps7": "soon"}
    assert page.locator(".jv-now__canvas jv-window:not([data-wants]) .jv-window__bracket:visible").count() == 0  # brackets only on the three that want him
    assert page.locator(".jv-now__canvas jv-window[data-wants] > .jv-window__bracket:visible").count() == 12
    assert page.locator(".jv-now__canvas jv-window > [class^='jv-now__']").count() == 0  # one implementation: nothing is hung on a window
    page = hub.scene("now-active")  # only PPS 7 (due within 72 h) wants him: brackets there alone, still one reticle
    assert page.eval_on_selector_all("jv-window[data-wants]", "n => n.map(e => e.getAttribute('window-id'))") == ["w-due-pps7"]
    assert page.locator("jv-window[active]").count() == 1


def test_since_you_looked_notch_shows_on_the_window_and_clears_on_keyboard_focus(hub):
    page = hub.scene("now-marks")
    assert page.locator("jv-window[window-id=w-due-pps7] > .jv-window__notch").is_visible()
    assert "Due moved Wed 8 pm" in page.inner_text("jv-window[window-id=w-due-pps7] > .jv-window__notch .jv-sr")
    assert page.locator("jv-window[window-id=w-pps7] > .jv-window__notch").count() == 0
    page.wait_for_timeout(1_000)  # being shown never clears a mark
    assert "due-pps7" in hub.state("s => Object.keys(s.marks)")
    page.focus("jv-window[window-id=w-due-pps7] [data-tool=pin]")
    page.wait_for_selector("jv-window[window-id=w-due-pps7] > .jv-window__notch", state="detached")
    assert hub.state("s => Object.keys(s.marks)") == ["jarvis:said"]


def test_a_deliberate_hover_clears_a_mark_and_a_pass_over_does_not(hub):
    page = hub.scene("now-marks")
    box = page.locator("jv-window[window-id=w-due-pps7]").bounding_box()
    page.mouse.move(box["x"] + 30, box["y"] + 60)
    page.wait_for_timeout(300)
    page.mouse.move(5, 500)  # moved on before 800 ms
    page.wait_for_timeout(700)
    assert "due-pps7" in hub.state("s => Object.keys(s.marks)")
    page.mouse.move(box["x"] + 30, box["y"] + 60)
    page.wait_for_function("!('due-pps7' in window.__jarvis.store.state.marks)", timeout=2_000)


def test_the_voice_focus_snaps_onto_the_window_and_lets_go(hub):
    page = hub.scene("now-focus")
    assert page.get_attribute("jv-window[window-id=w-due-pps7]", "named") == ""
    assert page.locator("jv-window[window-id=w-due-pps7] > .jv-window__bracket:visible").count() == 4  # the brackets snap on
    assert page.locator("jv-window[named]").count() == 1
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'ui.focus', ts: '2026-11-16T15:40:30', data: {ref: null}})")  # let go at once
    page.wait_for_selector("jv-window[named]", state="detached")
    assert page.locator(".jv-now__canvas .jv-window__bracket:visible").count() == 0


def test_the_voice_focus_lets_go_when_until_passes(hub):
    page = hub.open()  # the live demo: the hub clock runs
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'settings.updated', ts: '', data: {...window.__jarvis.store.state.settings, stage: 'hub'}})")  # windows on the home page (N9: "On the hub")
    page.evaluate("""(() => { const {store} = window.__jarvis, iso = (ms) => { const d = new Date(store.now().getTime() + ms); return new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 19); };
        store.apply({v: 2, type: 'window.push', ts: iso(0), data: {id: 'w-focus-test', type: 'notice', title: 'Focus test', ref: 'focus-test'}});
        store.setUi({ambient: false});
        store.apply({v: 2, type: 'ui.focus', ts: iso(0), data: {ref: 'focus-test', until: iso(1500)}}); })()""")
    page.wait_for_selector("jv-window[window-id=w-focus-test][named]")
    page.wait_for_selector("jv-window[window-id=w-focus-test][named]", state="detached", timeout=4_000)
