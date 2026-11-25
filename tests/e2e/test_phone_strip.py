"""N8: the phone (Rail row above the tabs, 320 px, toasts, the reader) and Laptop A's strip (still, silent,
worst state + new, game mode, the recap after a game)."""
import pytest

STATE = "window.__jarvis.store.state"
PHONE_SCENES = ("phone-now", "phone-said", "phone-rail-open", "phone-critical", "phone-standby", "phone-reader",
                "phone-life", "phone-branch", "phone-activity", "phone-controls")
STRIP_SCENES = ("strip", "strip-waiting", "strip-muted", "strip-standby", "strip-critical", "strip-game",
                "strip-game-critical", "strip-after-game")
RUNNING = """() => [...document.querySelectorAll('*')].filter((e) => { const s = getComputedStyle(e);
    return s.animationName !== 'none' || parseFloat(s.transitionDuration) > 0; }).length + document.getAnimations().length"""


def apply(page, kind, data):
    page.evaluate("([type, data]) => window.__jarvis.store.apply({v: 2, type, ts: '', data})", [kind, data])
    page.wait_for_timeout(60)


# ---- the strip -----------------------------------------------------------------------------------------------
def test_nothing_on_the_strip_ever_animates(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    hub.page.emulate_media(reduced_motion="no-preference")
    for scene in STRIP_SCENES:
        page = hub.scene(scene, theme="night", motion="full")
        assert page.evaluate(RUNNING) == 0, scene
        apply(page, "orb.state", {"state": "speaking", "level": 0.9})  # even when the state changes under it
        assert page.evaluate(RUNNING) == 0, scene
    assert hub.problems == []


def test_the_strip_reads_the_orb_through_orbview(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    page = hub.scene("strip-standby")
    assert page.inner_text(".jv-strip__state") == "Standby" and page.get_attribute(".jv-strip jv-orb", "state") == "standby"
    page = hub.scene("strip-critical")
    assert page.inner_text(".jv-strip__state") == "Critical" and page.get_attribute(".jv-strip jv-orb", "alert") == "crit"
    line = page.inner_text(".jv-strip__next")
    assert "GE 122 · PPS 7" in line and "Overdue since Wed 8 pm" in line and "Now" in line
    assert page.locator(".jv-strip__rail .jv-glance").count() == 0  # the critical thing is named once, not twice
    assert hub.problems == []


def test_the_strip_shows_the_rails_worst_state_and_whats_new(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    page = hub.scene("strip")
    rail = page.locator(".jv-strip__rail")
    assert rail.locator(".jv-glance").get_attribute("data-glance") == "soon"  # a shape, not colour alone
    assert rail.inner_text().split() == ["Soon", "3", "new"]
    assert rail.get_attribute("aria-label") == "Worst on the Rail: Soon (Today, Homework). 3 new since you looked"
    assert page.locator(".jv-strip__notch").count() == 1
    apply(page, "marks.updated", {"marks": {}})  # all seen: no "new" at all
    assert "new" not in page.inner_text(".jv-strip")
    assert hub.problems == []


def test_game_mode_shows_only_critical_and_leaves_a_recap(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    page = hub.scene("strip-game")
    assert page.locator(".jv-strip--hidden").count() == 1 and page.locator(".jv-strip jv-orb").count() == 0
    page = hub.scene("strip-game-critical")
    assert page.locator(".jv-strip--hidden").count() == 0 and page.get_attribute(".jv-strip jv-orb", "alert") == "crit"
    assert "GE 122 · PPS 7" in page.inner_text(".jv-strip") and page.locator(".jv-strip__rail").count() == 0

    # live: the strip notes when the game starts and ends, and counts what came in meanwhile by Rail slot
    page = hub.scene("strip")
    settings = page.evaluate(f"{STATE}.settings")
    apply(page, "settings.updated", {**settings, "game_mode": "on"})
    assert page.locator(".jv-strip--hidden").count() == 1
    now = page.evaluate(f"{STATE}.ui.gameSince")
    marks = page.evaluate(f"{STATE}.marks")
    apply(page, "marks.updated", {"marks": {**marks, "msg-maya-room": {"what": "New: room moved again", "at": now}, "f-sched": {"what": "Learned something", "at": now}}})
    assert page.locator(".jv-strip--hidden").count() == 1  # nothing shows while he plays
    apply(page, "settings.updated", {**settings, "game_mode": "auto"})
    assert page.inner_text(".jv-strip__recap") == "While you played: Messages 1, Jarvis 1"
    marks = page.evaluate(f"{STATE}.marks")
    marks.pop("msg-maya-room")
    apply(page, "marks.updated", {"marks": marks})  # seen on the hub: it drops out of the recap
    assert page.inner_text(".jv-strip__recap") == "While you played: Jarvis 1"

    page = hub.scene("strip-after-game")
    assert page.inner_text(".jv-strip__recap") == "While you played: Homework 1, Messages 2, Jarvis 1"
    assert page.evaluate("(() => { const r = document.querySelector('.jv-strip__recap'); return r.scrollWidth <= r.clientWidth; })()")
    assert hub.problems == []


def test_the_strip_never_makes_a_sound(hub):
    hub.page.add_init_script("""window.__sounds = 0;
        const A = window.AudioContext; window.AudioContext = function (...a) { window.__sounds++; return new A(...a); };
        const play = HTMLMediaElement.prototype.play; HTMLMediaElement.prototype.play = function () { window.__sounds++; return play.call(this); };""")
    hub.page.set_viewport_size({"width": 360, "height": 96})
    page = hub.scene("strip-critical", size="strip")  # as app.py opens it: ?size=strip from the first frame
    page.evaluate("import('/sounds/earcons.js').then((m) => { m.setEarconLevel('full'); return m.preload(); })")
    apply(page, "orb.state", {"state": "listening", "last_wake": None})  # a first wake: the full beat elsewhere
    apply(page, "orb.state", {"state": "idle", "alert": "crit"})
    page.wait_for_timeout(200)
    assert page.evaluate("window.__sounds") == 0
    assert hub.problems == []


# ---- the phone -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("width,height", [(390, 844), (320, 640)])
def test_the_phone_rail_row_sits_above_the_tabs_and_fits(hub, width, height):
    hub.page.set_viewport_size({"width": width, "height": height})
    page = hub.scene("phone-now", theme="night", size="phone")
    box = page.evaluate("""() => { const r = (e) => e.getBoundingClientRect();
        const bar = r(document.querySelector('#rail .jv-rail__bar')), tabs = r(document.getElementById('chrome')), stage = r(document.getElementById('stage'));
        const slots = [...document.querySelectorAll('#rail .jv-rail__slot')];
        return { h: Math.round(bar.height), above: bar.bottom <= tabs.top + 0.5, below: bar.top >= stage.bottom - 0.5, n: slots.length,
          apart: slots.every((s, i) => !i || r(slots[i - 1]).right <= r(s).left + 0.5),
          fit: slots.every((s) => s.scrollWidth <= s.clientWidth + 1 && r(s).height >= 44), inside: r(slots.at(-1)).right <= innerWidth,
          named: slots.every((s) => /^(Your yes|Today|Homework|Messages|Jarvis|Parked): \\d+ things?/.test(s.getAttribute('aria-label'))) }; }""")
    assert box == {"h": 44, "above": True, "below": True, "n": 6, "apart": True, "fit": True, "inside": True, "named": True}
    assert page.evaluate("[...document.querySelectorAll('#rail .jv-rail__name')].every((n) => n.getBoundingClientRect().width <= 1)")
    assert hub.problems == []


def test_the_phone_rail_shows_its_words_when_there_is_room(hub):
    hub.page.set_viewport_size({"width": 700, "height": 900})
    page = hub.scene("phone-now", size="phone")
    words = page.evaluate("[...document.querySelectorAll('#rail .jv-rail__name')].map((n) => n.getBoundingClientRect().width > 20 ? n.textContent : '')")
    assert words == ["Your yes", "Today", "Homework", "Messages", "Jarvis", "Parked"]
    assert page.evaluate("[...document.querySelectorAll('#rail .jv-rail__slot')].every((s) => s.scrollWidth <= s.clientWidth + 1)")
    assert hub.problems == []


def test_the_phone_rail_is_reachable_by_keyboard(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("phone-now", size="phone")
    page.evaluate("[...document.querySelectorAll('#tabs a')].at(0).focus()")
    page.keyboard.press("Shift+Tab")  # the Rail row comes before the tabs, as on the screen
    assert page.evaluate("document.activeElement.dataset.slot") == "yes"  # the Rail's one Tab stop
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.dataset.slot") == "homework"
    page.keyboard.press("Enter")
    page.wait_for_selector("#rail .jv-rail__fan:not([hidden]) .jv-rail__card")
    fan = page.evaluate("""() => { const f = document.querySelector('#rail .jv-rail__fan').getBoundingClientRect(), rail = document.querySelector('#rail .jv-rail__bar').getBoundingClientRect();
        return [f.left >= 0, f.right <= innerWidth, f.bottom <= rail.top, getComputedStyle(document.querySelector('#rail .jv-rail__fan')).backgroundColor.startsWith('rgb(')]; }""")
    assert fan == [True, True, True, True]  # the whole width, above the row, nothing showing through
    assert page.evaluate("document.activeElement.classList.contains('jv-rail__card')")
    page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement.dataset.slot") == "homework"
    page.keyboard.press("Alt+Digit5")
    assert page.evaluate("document.activeElement.dataset.slot") == "jarvis"
    assert hub.problems == []


@pytest.mark.parametrize("theme", ["night", "day"])
def test_nothing_scrolls_sideways_at_320(hub, theme):
    hub.page.set_viewport_size({"width": 320, "height": 640})
    wide = []
    for scene in PHONE_SCENES:
        page = hub.scene(scene, theme=theme, size="phone")
        over = page.evaluate("""() => [document.documentElement.scrollWidth - innerWidth,
            (() => { const s = document.getElementById('stage'); return s.scrollWidth - s.clientWidth; })()]""")
        if over != [0, 0]:
            wide.append((scene, over))
    assert wide == []
    assert hub.problems == []


@pytest.mark.parametrize("width,height", [(390, 844), (320, 640)])
def test_phone_toasts_and_captions_keep_clear(hub, width, height):
    hub.page.set_viewport_size({"width": width, "height": height})
    page = hub.scene("phone-said", size="phone")
    page.wait_for_selector("#toasts .jv-toast")
    page.wait_for_timeout(100)
    hits = page.evaluate("""() => { const r = (e) => e.getBoundingClientRect();
        const over = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
        const toast = r(document.querySelector('#toasts .jv-toast')), cap = r(document.querySelector('#caption .jv-caption'));
        const rail = r(document.querySelector('#rail .jv-rail__bar')), tabs = r(document.getElementById('chrome')), stage = r(document.getElementById('stage'));
        return { toast: [over(toast, cap), over(toast, rail), over(toast, tabs), toast.left >= 0 && toast.right <= innerWidth],
                 caption: [cap.top >= stage.bottom - 1, cap.bottom <= rail.top + 1] }; }""")
    assert hits == {"toast": [False, False, False, True], "caption": [True, True]}
    assert hub.problems == []


def test_the_phone_orb_says_standby_and_shows_the_critical_alert(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("phone-standby", size="phone")
    assert page.get_attribute("#orb", "state") == "standby"
    page = hub.scene("phone-critical", size="phone")
    assert page.get_attribute("#orb", "alert") == "crit"
    assert page.locator("#rail [data-slot=homework] [data-glance]").get_attribute("data-glance") == "critical"
    assert hub.problems == []


@pytest.mark.parametrize("width,height", [(390, 844), (320, 640)])
def test_pps7_opens_at_q7_on_the_phone_with_the_resume_card_in_reach(hub, width, height):
    hub.page.set_viewport_size({"width": width, "height": height})
    page = hub.scene("phone-reader", theme="night", size="phone")
    page.wait_for_selector("jv-resume-card .jv-btn--primary")
    page.wait_for_function("document.querySelector('.jv-reader__bar').innerText.toUpperCase().includes('Q7 OF')", timeout=15_000)
    box = page.evaluate("""() => { const r = (e) => e.getBoundingClientRect();
        const card = r(document.querySelector('.jv-reader__card')), sheet = r(document.querySelector('.jv-reader__sheet')), yes = r(document.querySelector('jv-resume-card .jv-btn--primary'));
        return [card.top > sheet.top + sheet.height / 2, card.bottom <= sheet.bottom + 1, yes.bottom <= innerHeight, yes.height >= 44,
                getComputedStyle(document.querySelector('.jv-resume-card')).backgroundColor.startsWith('rgb(')]; }""")
    assert box == [True, True, True, True, True]  # the lower half, within thumb reach, opaque
    page.click("jv-resume-card .jv-btn--primary")
    page.wait_for_function("!document.querySelector('jv-resume-card') || document.querySelector('jv-resume-card').hasAttribute('lifted')")
    assert hub.problems == []
