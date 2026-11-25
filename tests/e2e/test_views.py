"""Views and behaviour, exercised the way he would use them (scene mode unless the test says otherwise)."""
import pytest

STATE = "window.__jarvis.store.state"


def press(page, key):
    page.keyboard.press(key)
    page.wait_for_timeout(30)


def path(page):
    return page.evaluate("window.__jarvis.router.current.path")


# ---- Now -------------------------------------------------------------------------------------------
def test_now_ambient_is_huws_idle_screen_and_any_key_wakes_it(hub):
    page = hub.scene("now-ambient")
    assert page.is_visible(".jv-now__centre jv-orb[size=centre]") and page.is_visible("jv-clock.jv-amb__clock")
    assert page.locator("#rail jv-page-dots .jv-page-dots__dot").count() == 5  # HUD v3: the five views are page dots under the icon row
    assert page.locator("#chrome jv-tabs:visible").count() == 0  # no pills in the corner
    assert page.get_attribute(".jv-now__plant svg", "aria-label") == "Day plant: 4 of 6 done today"
    assert not page.is_visible("#orb")  # the corner orb steps aside while the big one is up
    press(page, "Enter")  # wakes it: the calm home keeps its layout (pushed windows go to the Stage, N9)
    assert hub.state("s => s.ui.ambient") is False
    assert page.is_visible(".jv-now__centre jv-orb[size=centre]") and not page.is_visible("jv-clock")  # awake: rings only, no clock
    assert not page.is_visible("#orb") and not page.is_visible("jv-now-card")
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'settings.updated', ts: '', data: {...window.__jarvis.store.state.settings, stage: 'hub'}})")  # "On the hub": awake is the canvas with the now card again
    page.wait_for_selector(".jv-amb__next:not([hidden])")  # v0.18.0: with nothing up it stays the orb, with one line for what's next
    assert page.is_visible(".jv-now__centre jv-orb[size=centre]") and not page.is_visible("#orb") and not page.is_visible(".jv-amb__clock")
    press(page, "Escape")  # nothing open, nothing behind: back to the calm screen
    assert page.is_visible("jv-clock.jv-amb__clock")


def test_the_return_offer_opens_the_thread_at_its_spot(hub):
    # walkthrough B8: "PPS 7 · Q7 · Today" did nothing when clicked, tapped or tabbed to. HUD v3: the permanent
    # line is gone; the offer is one small card under the orb while it is live (tests/e2e/test_offer.py has the rest)
    page = hub.scene("now-ambient-resume")
    assert page.locator(".jv-amb__lead").count() == 0
    link = page.locator(".jv-amb__offer a.jv-amb__offer-go")
    assert link.get_attribute("href") == "#/read/th-pps7"
    assert link.get_attribute("aria-label") == "Carry on: PPS 7 · Q7 · Today"
    link.focus()
    page.keyboard.press("Enter")
    page.wait_for_function("window.__jarvis.router.current.path === '/read/th-pps7'")


def test_now_shows_at_most_six_windows_and_marks_the_one_jarvis_means(hub):
    page = hub.scene("now-full")
    assert page.locator(".jv-now__canvas jv-window[window-id]").count() == 5  # plus the now card: six on screen
    assert page.locator("jv-window[active]").count() == 1
    page.evaluate("window.__jarvis.store.apply({v:1, type:'window.push', ts:'', data:{id:'w-7', type:'notice', title:'Seventh', data:{text:'One more'}}})")
    page.wait_for_selector("jv-window[window-id=w-7]")
    page.wait_for_timeout(250)
    ids = page.eval_on_selector_all(".jv-now__canvas jv-window[window-id]", "els => els.map(e => e.getAttribute('window-id'))")
    assert len(ids) == 5 and "w-due-pps7" not in ids and "w-chart" in ids  # oldest unpinned left; the pinned chart stayed
    page.click("jv-window[window-id=w-7] [data-tool=pin]")
    assert page.evaluate(f"{STATE}.windows.find(w => w.id === 'w-7').pinned") is True
    page.click("jv-window[window-id=w-7] [data-tool=close]")
    page.wait_for_selector("jv-window[window-id=w-7]", state="detached")


def test_saying_yes_leaves_a_receipt_that_can_be_undone(hub):
    page = hub.scene("now-waiting")
    assert page.get_attribute("#orb", "state") == "waiting"
    page.focus("jv-approval-card >> text=Yes, do it")  # keyboard focus opens the window's drawer (no buttons at rest)
    page.click("jv-approval-card >> text=Yes, do it")
    page.wait_for_selector("jv-window[window-id=w-ap-week]", state="detached")
    assert page.get_attribute("#orb", "state") == "idle"
    page.click("#rail .jv-page-dots__dot[data-key=activity]")  # the views are page dots now, not tabs
    assert "Nothing waiting for you" in page.inner_text("#stage")
    first = page.locator("jv-action-row").first
    assert "Book this week's study plan" in first.inner_text() and "You said yes" in first.inner_text()
    first.locator("text=/Undo · until .* tomorrow/").click()
    assert "Undone" in page.locator("jv-action-row").first.inner_text()
    assert page.locator("#rail [data-slot=yes] [data-glance]").count() == 0  # nothing waits for his yes any more


def test_nothing_private_is_pushed_to_a_screen_others_can_see(hub):
    page = hub.scene("now-active", size="ambient")
    page.evaluate("window.__jarvis.store.apply({v:1, type:'window.push', ts:'', data:{id:'w-money', type:'notice', title:'Money', tier:2, data:{text:'Private'}}})")
    page.wait_for_timeout(100)
    assert page.locator("jv-window[window-id=w-money]").count() == 0
    page.evaluate("window.__jarvis.store.apply({v:1, type:'presence.changed', ts:'', data:{others:true}})")
    page.wait_for_timeout(300)
    assert page.locator(".jv-now__canvas jv-window[window-id]").count() == 0


def test_window_commands_can_be_typed_like_they_are_spoken(hub):
    page = hub.scene("now-active")
    for words, check in (("keep that up", "s => s.windows.at(-1).pinned === true"), ("close due", "s => !s.windows.some(w => w.id === 'w-due-pps7')"), ("clear the screen", "s => s.windows.length === 0")):
        page.keyboard.press("Control+k")
        page.keyboard.type(words)
        page.keyboard.press("ArrowUp")  # the last row is "Ask Jarvis"
        page.keyboard.press("Enter")
        page.wait_for_function(f"({check})(window.__jarvis.store.state)")


# ---- Today -----------------------------------------------------------------------------------------
def test_today_progress_first_and_proposals_apply_tweak_skip(hub):
    page = hub.scene("today")
    assert "4 of 6" in page.inner_text(".jv-today__done")
    assert page.locator(".jv-today__proposal .jv-btn--primary").count() == 1
    assert "Moved to 4 pm tomorrow." in page.inner_text(".jv-today__moved")
    page.click(".jv-today__proposal >> text=Change it")
    page.fill("input[name=note]", "make it 10:00")
    press(page, "Enter")
    assert "Nothing to decide" in page.inner_text("#stage")
    page = hub.scene("today")
    page.click(".jv-today__proposal >> text=Yes, do it")
    assert page.evaluate(f"{STATE}.actions[0].what") == "Laundry tomorrow at 9:00 am"


# ---- Life ------------------------------------------------------------------------------------------
def test_life_map_seven_around_the_centre_and_two_steps_to_anything(hub):
    page = hub.scene("life")
    assert page.locator(".jv-map__node").count() == 6 and "Your life" in page.text_content(".jv-map__centre")
    assert "School, due in 2d, due soon, 1 waiting for your yes" == page.get_attribute(".jv-map__node[data-id=school]", "aria-label")
    page.click(".jv-map__node[data-id=school]")
    assert path(page) == "/life/school" and page.get_attribute(".jv-map", "data-focus") == "school"
    assert page.locator(".jv-map__node--proposed").count() == 1
    page.click(".jv-map__node[data-id=fall-2026]")
    nodes = page.locator(".jv-map__node")
    assert nodes.count() == 7 and "+2" in page.text_content(".jv-map__node--more")  # 8 courses: 6 shown + "more"
    page.click(".jv-map__node[data-id=ge-122]")
    assert path(page) == "/life/ge-122" and page.get_attribute(".jv-map", "data-focus") == "fall-2026"
    assert page.inner_text("#branch-title") == "GE 122" and "2 d 4 h" in page.inner_text("jv-branch-page")
    assert [t.strip() for t in page.inner_text(".jv-life__bar .jv-crumbs").replace("\n", "").upper().split("›")] == ["LIFE", "SCHOOL", "FALL 2026", "GE 122"]
    page.click(".jv-life__back")
    assert path(page) == "/life/school"


def test_life_map_works_from_the_keyboard_and_l_switches_to_the_list(hub):
    page = hub.scene("life")
    page.focus(".jv-map__node[data-id=school]")
    press(page, "ArrowRight")
    assert page.evaluate("document.activeElement.classList.contains('jv-map__node')")
    page.focus(".jv-map__node[data-id=school]")
    press(page, "Enter")
    assert path(page) == "/life/school"
    press(page, "l")
    tree = page.locator("[role=tree]")
    assert tree.count() == 1 and page.locator(".jv-map").count() == 0
    row = page.locator("[role=treeitem][aria-current=page]")
    assert "School" in row.inner_text() and "needs your yes" in row.inner_text()
    row.focus()
    press(page, "ArrowDown")
    press(page, "ArrowRight")  # opens Fall 2026
    assert page.locator("[role=treeitem] >> text=GE 122").count() == 1
    press(page, "ArrowDown")
    first = page.evaluate("document.activeElement.dataset.nav")  # the busiest course (waiting counts come from the approvals)
    press(page, "Enter")
    assert first.startswith("/life/") and path(page) == first
    press(page, "l")
    assert page.locator(".jv-map").count() == 1


def test_private_branches_are_locked_where_others_can_see(hub):
    page = hub.scene("life-private")
    assert page.locator(".jv-map__node[data-id=money] .jv-map__lock").count() == 1
    assert "Money, private" == page.get_attribute(".jv-map__node[data-id=money]", "aria-label")
    page = hub.scene("life-private", size="ambient")
    assert page.get_attribute(".jv-map__node[data-id=money]", "aria-label") == "Private branch"
    assert "Money" not in page.text_content(".jv-map")
    page.evaluate("window.__jarvis.router.go('/life/money')")
    assert "is private" in page.inner_text("jv-branch-page") and page.locator("jv-branch-page jv-fact-card").count() == 0


def test_branch_page_shows_at_most_six_panels_and_the_rest_under_more(hub):
    page = hub.scene("branch-course")
    assert page.locator(".jv-branch > .jv-branch__panels > jv-window").count() <= 6
    assert not page.is_visible("text=Prof. Smith")
    page.click(".jv-branch__more > summary")
    assert page.is_visible("text=Prof. Smith") and page.is_visible("text=Summary, written by Jarvis")
    assert "Your call · Nov 13" in page.inner_text(".jv-branch__more")
    page = hub.scene("branch-empty")
    assert "nothing is needed from you" in page.inner_text("#stage")


# ---- Memory ----------------------------------------------------------------------------------------
def test_memory_guesses_are_reviewed_and_forget_previews_first(hub):
    page = hub.scene("memory")
    page.click("[data-tab=guesses]")
    assert page.locator("jv-fact-card").count() == 2
    page.locator("jv-fact-card >> text=Confirm").first.click()
    page.wait_for_function("document.querySelectorAll('jv-fact-card').length === 1")
    page.click("[data-tab=conflicts]")
    assert "Kept yours" in page.inner_text("jv-fact-card")
    page.click("[data-tab=all]")
    page.select_option("select[name=branch]", "residence")
    card = page.locator("jv-fact-card").first
    card.locator("[data-key=menu]").click()  # Edit · Pin · Move · Forget sit behind "…"
    card.locator("button:has-text('Forget')").click()
    assert "also forgets" in card.inner_text()
    card.locator("text=Forget it").click()
    assert page.evaluate(f"{STATE}.facts.some(f => f.id === 'f-res')") is False
    page.click("[role=switch][aria-label='Pause memory']")
    assert "Memory is paused" in page.inner_text("#stage")


def test_unsorted_items_file_in_one_tap(hub):
    page = hub.scene("unsorted")
    assert page.locator(".jv-unsorted li").count() == 2 and page.locator(".jv-unsorted .jv-btn--primary").count() == 1
    page.click("text=File under CMPT 141")
    assert page.locator(".jv-unsorted li").count() == 1
    assert page.evaluate(f"{STATE}.facts.find(f => f.id === 'u-1').branch_id") == "cmpt-141"


# ---- Controls, theme, motion --------------------------------------------------------------------
def test_controls_change_settings_theme_and_motion(hub):
    page = hub.open("#/controls", scene="controls-live")  # no forced theme, so Controls decides
    page.click("[role=radio][data-key=interruption-quiet]")
    assert page.evaluate(f"{STATE}.settings.interruption") == "quiet"
    assert page.get_attribute("[data-key=interruption-quiet]", "aria-checked") == "true"
    page.click("[data-key=theme-night]")
    assert page.evaluate("document.documentElement.dataset.theme") == "night"
    page.click("[data-key=theme-day]")
    page.click("[data-key=motion-full]")
    assert page.evaluate("document.documentElement.hasAttribute('data-still')")  # the browser asks for reduced motion
    page.click("[role=switch][aria-label=Plants]")
    assert page.evaluate("document.documentElement.dataset.plants") == "off"
    page.click("[role=switch][aria-label=Gmail]")
    assert page.evaluate(f"{STATE}.settings.sources.find(x => x.id === 'gmail').on") is False
    page.click("text=Revoke >> nth=0")
    assert page.evaluate(f"{STATE}.settings.standing_permissions.length") == 1
    assert "Submitting assignments · Payments" in page.inner_text("#stage")


def test_theme_rules(hub):
    hub.scene("shell")
    out = hub.page.evaluate("""import('/core/theme.js').then(m => [
        m.themeFor('sunset', new Date('2026-11-16T19:00:00-06:00'), false), m.themeFor('sunset', new Date('2026-11-16T12:00:00-06:00'), true),
        m.themeFor('system', new Date(), true), m.themeFor('day', new Date(), true),
        m.isStill('full', 'strip', false), m.isStill('', 'full', true), m.isStill('full', 'full', true), m.isStill('off', 'full', false)])""")
    assert out == ["night", "day", "night", "day", True, True, False, True]


def test_sunset_theme_follows_saskatoon_sun(hub):
    hub.scene("shell")
    # Saskatoon (CST, UTC-6): mid-November sunrise ~8:28 am, sunset ~5:14 pm; late June sunset ~9:31 pm
    out = hub.page.evaluate("""import('/core/theme.js').then(m => [
        '2026-11-16T08:00:00-06:00', '2026-11-16T09:00:00-06:00', '2026-11-16T17:00:00-06:00',
        '2026-11-16T17:30:00-06:00', '2026-11-17T01:00:00-06:00', '2026-06-21T21:00:00-06:00',
        '2026-06-21T22:00:00-06:00', '2026-06-21T05:15:00-06:00'].map(t => m.themeFor('sunset', new Date(t), false)))""")
    assert out == ["night", "day", "day", "night", "night", "day", "night", "day"]
    times = hub.page.evaluate("""import('/core/theme.js').then(m => { const t = m.sunTimes(new Date('2026-12-21T12:00:00-06:00'));
        return [t.rise.toISOString(), t.set.toISOString()]; })""")
    assert times[0].startswith("2026-12-21T15:1") and times[1].startswith("2026-12-21T22:5")  # 9:1x am, 4:5x pm CST


# ---- keyboard --------------------------------------------------------------------------------------
def test_keys_reach_everything_and_esc_always_goes_back(hub):
    page = hub.scene("activity")
    for key, where in (("3", "/life"), ("2", "/today"), ("5", "/controls"), ("1", "/now"), ("4", "/activity")):
        press(page, key)
        assert path(page) == where
    press(page, "Escape")
    assert path(page) == "/now"
    press(page, "?")
    assert page.is_visible("[role=dialog] >> text=Keyboard shortcuts")
    press(page, "3")  # keys don't leak through an open dialog
    assert path(page) == "/now"
    press(page, "Escape")
    assert page.locator(".jv-keys").count() == 0
    press(page, "/")
    assert page.evaluate("document.activeElement.getAttribute('role')") == "combobox"
    page.keyboard.type("2")  # typing in a field is typing, not a shortcut
    assert path(page) == "/now" and page.input_value("jv-command-bar input") == "2"
    press(page, "Escape")
    page.keyboard.press("Control+k")
    page.keyboard.type("under the hood")
    press(page, "Enter")
    assert path(page) == "/controls/hood"
    press(page, "m")
    assert page.evaluate(f"{STATE}.settings.muted") is True and "Muted" in page.inner_text("#status")


def test_screen_readers_hear_captions_approvals_and_notices(hub):
    page = hub.scene("shell")
    say = lambda t, d: page.evaluate(f"window.__jarvis.store.apply({{v:1, type:'{t}', ts:'', data:{d}}})")  # noqa: E731
    say("caption.show", "{text:'PPS 7 is due Wednesday at 8 pm.', source:{kind:'canvas', label:'Canvas'}}")
    page.wait_for_function("document.getElementById('jv-live-polite').textContent.includes('Source: Canvas')")
    assert page.get_attribute(".jv-caption", "aria-hidden") == "true"
    say("approval.pending", "{id:'ap-2', title:'Send lab report 3', consequences:['Sends an email'], read_back:'Shall I send it?', status:'pending', asked:'2026-11-16T15:45:00'}")
    page.wait_for_function("document.getElementById('jv-live-assertive').textContent.startsWith('Waiting for your yes: Send lab report 3')")
    say("toast", "{id:'t-9', kind:'info', text:'Jarvis learned 3 things today.'}")
    page.wait_for_function("document.getElementById('jv-live-polite').textContent.includes('learned 3 things')")


# ---- strip, phone, presence -----------------------------------------------------------------------
def test_the_strip_never_animates_and_hides_in_game_mode(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("strip-waiting", motion="full")
    moving = page.evaluate("[...document.querySelectorAll('*')].filter(e => { const s = getComputedStyle(e); return s.animationName !== 'none' || parseFloat(s.transitionDuration) > 0; }).length")
    assert moving == 0
    assert "Waiting for your yes" in page.inner_text(".jv-strip") and page.is_visible("jv-orb[size=strip]")
    assert page.locator(".jv-chrome").is_hidden()
    page = hub.scene("strip-game")
    assert page.locator(".jv-strip--hidden").count() == 1 and not page.is_visible("jv-orb")


def test_phone_shows_now_waiting_and_quick_controls(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("phone-now")
    assert page.is_visible("jv-now-card") and page.is_visible("jv-approval-card") and page.is_visible("jv-quick-controls")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    small = page.evaluate("[...document.querySelectorAll('#chrome a, #stage button')].filter(e => e.offsetParent && e.getBoundingClientRect().height < 40).map(e => e.textContent.trim().slice(0, 20))")
    assert small == []
    page.click("jv-quick-controls [aria-label='Focus mode']")
    assert page.evaluate(f"{STATE}.settings.focus") is True
    page = hub.scene("phone-life")
    assert page.locator("[role=tree]").count() == 1 and page.locator(".jv-map").count() == 0


def test_idle_goes_ambient_and_a_pushed_window_wakes(hub):
    page = hub.scene("activity")
    out = page.evaluate("""import('/core/presence.js').then(async m => {
        const s = window.__jarvis.store, r = window.__jarvis.router, seen = [];
        m.rest(); await new Promise(f => setTimeout(f, 30)); seen.push([r.current.path, s.state.ui.ambient]);
        s.apply({v:1, type:'window.push', ts:'', data:{id:'w-x', type:'notice', title:'Hello', data:{text:'x'}}});
        await new Promise(f => setTimeout(f, 30)); seen.push(s.state.ui.ambient);
        return [seen, m.IDLE_MS]; })""")
    assert out == [[["/now", True], False], 120000]


# ---- the demo day, live over SSE -----------------------------------------------------------------
def test_the_demo_day_can_be_clicked_through(hub):
    page = hub.open()
    assert hub.state("s => s.approvals.length") == 0 or hub.state("s => s.mode") == "demo"
    page.evaluate("fetch('/api/demo/restart', {method: 'POST'})")
    # the windows go to the Stage (N9): the calm home only counts them, and the chip opens the Stage window
    page.wait_for_function(f"{STATE}.windows.some(w => w.id === 'w-ap-week') && {STATE}.approvals.some(a => a.status === 'pending')", timeout=15_000)
    page.evaluate("location.hash = '#/now'")  # the story may have opened the reader on PPS 7 by now
    page.wait_for_selector("#rail [data-slot=yes] [data-glance=yes]")  # the amber square on the Your yes icon
    assert page.locator(".jv-amb__yes").count() == 0  # no "1 waiting for your yes" pill on the home (HUD v3)
    assert page.locator("jv-view-now jv-window").count() == 0
    assert "1 waiting for your yes" in page.inner_text("#rail .jv-page-dots__dot[data-key=activity]")
    with page.context.expect_page() as opened:
        page.click("#rail [data-tool=stage]")
    stage = opened.value
    stage.set_default_timeout(8_000)
    stage.wait_for_selector("jv-window[window-id=w-pps7] jv-thumb", timeout=15_000)  # the page fills the glass panel
    stage.wait_for_selector("jv-window[window-id=w-ge122] >> text=Week 11 of 13")
    stage.wait_for_selector("jv-approval-card >> text=Yes, do it")
    box = stage.locator("jv-window[window-id=w-ap-week]").bounding_box()
    assert box["y"] < 400  # the question sits at the top of the canvas, not below the fold
    stage.focus("jv-approval-card >> text=Yes, do it")  # no buttons on a resting window: focus (or hover) opens its drawer
    stage.click("jv-approval-card >> text=Yes, do it")
    stage.wait_for_selector("jv-window[window-id=w-ap-week]", state="detached")
    stage.close()
    page.bring_to_front()
    page.wait_for_function(f"!{STATE}.approvals.some(a => a.status === 'pending')")
    press(page, "4")
    page.wait_for_selector("jv-action-row >> text=Book this week's study plan")
    assert page.is_visible("#demo-chip")
    assert hub.problems == []


# ---- every view, checked against the plan's rules ------------------------------------------------
AUDIT = """() => {
  const visible = (e) => e.offsetParent !== null || getComputedStyle(e).position === 'fixed';
  const out = { unnamed: [], tiny: [], accents: [], faint: [] };
  for (const e of document.querySelectorAll('button, a[href], [role=switch], [role=radio], [role=tab], summary, select, input, textarea')) {
    if (!visible(e)) continue;
    const name = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || (e.labels && e.labels[0] && e.labels[0].textContent) || e.getAttribute('placeholder') || '').trim();
    if (!name) out.unnamed.push(e.outerHTML.slice(0, 90));
  }
  const lum = (c) => { const v = c.map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const rgb = (s) => { const m = s.match(/[\\d.]+/g).map(Number); return { c: m.slice(0, 3), a: m.length > 3 ? m[3] : 1 }; };
  const bg = (e) => { for (let n = e; n; n = n.parentElement) { const b = rgb(getComputedStyle(n).backgroundColor); if (b.a >= 0.99) return b.c; if (b.a > 0.05) return null; } return rgb(getComputedStyle(document.body).backgroundColor).c; };
  const walker = document.createTreeWalker(document.getElementById('stage').parentElement, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    const e = t.parentElement;
    if (!t.textContent.trim() || seen.has(e) || !visible(e) || e.closest('.jv-sr, svg, [hidden], title, .textLayer')) continue;  // .textLayer: PDF.js's invisible selection layer
    seen.add(e);
    const s = getComputedStyle(e), size = parseFloat(s.fontSize);
    if (size < 12) out.tiny.push(`${size}px: ${t.textContent.trim().slice(0, 30)}`);
    let faded = false; for (let n = e; n; n = n.parentElement) if (parseFloat(getComputedStyle(n).opacity) < 1) faded = true;
    const back = bg(e), fg = rgb(s.color);
    if (!back || faded || fg.a < 0.99) continue;
    const a = lum(fg.c), b = lum(back), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const large = size >= 24 || (size >= 18.66 && parseInt(s.fontWeight) >= 600);
    if (ratio < (large ? 3 : 4.5)) out.faint.push(`${ratio.toFixed(2)} ${t.textContent.trim().slice(0, 30)} (${s.color} on ${back})`);
  }
  for (const panel of document.querySelectorAll('jv-window, .jv-card, .jv-sheet, jv-fact-card, .jv-approval-card')) {
    const n = [...panel.querySelectorAll('.jv-btn--primary')].filter(b => visible(b) && b.closest('jv-window, .jv-card, .jv-sheet, jv-fact-card, .jv-approval-card') === panel).length;
    if (n > 1) out.accents.push(`${n} accent buttons in ${panel.localName}.${panel.className}`);
  }
  return out;
}"""


def test_every_scene_passes_the_accessibility_and_calm_audit(hub):
    hub.scene("shell")
    names = hub.page.evaluate("window.__jarvis.scenes()")
    failures = []
    for name in names:
        for theme in ("night", "day"):
            size = "phone" if name.startswith("phone") else "strip" if name.startswith("strip") else None
            w, h = {"phone": (390, 844), "strip": (360, 96)}.get(size, (1440, 900))
            hub.page.set_viewport_size({"width": w, "height": h})
            page = hub.scene(name, theme, size)
            found = page.evaluate(AUDIT)
            if page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
                failures.append((name, theme, "wider than the screen", f"{w}px"))
            for kind, items in found.items():
                if items:
                    failures.append((name, theme, kind, items[:3]))
    assert failures == []


@pytest.mark.parametrize("scene,limit", [("now-full", 6), ("activity", 6), ("controls", 6), ("hood", 9)])
def test_panels_stay_few(hub, scene, limit):
    page = hub.scene(scene)
    assert page.locator("#stage jv-window:visible, #stage .jv-sheet:visible").count() <= limit


def test_the_home_column_clears_the_caption_and_the_page_dots(hub):
    # the orb (and the offer card under it) never reach Jarvis's caption, the icon row or the page dots
    page = hub.scene("now-ambient-caption", theme="night")
    assert page.locator("#rail jv-page-dots").count() == 1
    for w, h in ((1920, 1080), (1440, 900), (1280, 720)):
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(100)
        bottom = page.evaluate("Math.max(...[...document.querySelectorAll('.jv-now__centre > :not([hidden])')].map(e => e.getBoundingClientRect().bottom))")
        cap, rail = (page.locator(s).bounding_box() for s in ("#caption .jv-caption", "#rail"))
        assert bottom <= cap["y"] and cap["y"] + cap["height"] <= rail["y"], (w, h)
        assert page.evaluate("(() => { const s = document.getElementById('stage'); return s.scrollHeight <= s.clientHeight; })()"), (w, h)


def test_night_life_map_nodes_are_never_empty_and_grow_no_leaflets(hub):
    # film review S8: every Night node was the same empty disc, and the stems still carried leaflets
    page = hub.scene("life", theme="night")
    words = page.eval_on_selector_all(".jv-map__node .jv-map__mark-word", "n => n.map(e => e.textContent)")
    assert len(words) == page.locator(".jv-map__node").count() and all(words), words
    assert "4" in words  # School: the four things due under it, as one big number
    assert page.eval_on_selector_all(".jv-map__dot", "n => n.filter(e => getComputedStyle(e).display !== 'none').length") == 0
    page = hub.scene("life", theme="day")  # Daylight keeps its plant: leaflets, no ring words
    assert page.eval_on_selector_all(".jv-map__dot", "n => n.filter(e => getComputedStyle(e).display !== 'none').length") > 0
    assert page.eval_on_selector_all(".jv-map__mark", "n => n.filter(e => getComputedStyle(e).display !== 'none').length") == 0
    assert hub.problems == []
