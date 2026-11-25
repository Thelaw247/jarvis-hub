"""Wave 1 integration (hub v0.3.0): the pieces of N2, N4, N5a, N5b, N6 and N7 working as one screen."""
import re

STATE = "window.__jarvis.store.state"
APPLY = "(type, data) => window.__jarvis.store.apply({v: 2, type, ts: window.__jarvis.store.now().toISOString().slice(0, 19), data})"


def send(page, kind, data):
    page.evaluate(f"([t, d]) => ({APPLY})(t, d)", [kind, data])


def test_the_wave_one_parts_are_registered(hub):
    page = hub.scene("now-active")
    defined = page.evaluate("['jv-glance', 'jv-thumb', 'jv-rail', 'jv-resume-card', 'jv-view-reader'].filter((t) => !customElements.get(t))")
    assert defined == []
    assert "reader-resume" in page.evaluate("window.__jarvis.scenes()")
    sheets = page.eval_on_selector_all("link[rel=stylesheet]", "l => l.map(x => x.getAttribute('href'))")
    for css in ("components/glance/glance.css", "components/thumb/thumb.css", "components/rail/rail.css", "components/resume-card/resume-card.css", "views/reader/reader.css"):
        assert css in sheets
    assert hub.problems == []


def test_window_kickers_pictures_and_marks_come_from_real_data(hub):
    page = hub.scene("now-active")
    due, pps = "jv-window[window-id=w-due-pps7]", "jv-window[window-id=w-pps7]"
    assert [page.get_attribute(due, a) for a in ("heading", "status", "glance", "meta")] == ["GE 122", "PPS 7", "soon", "Added 3:40 pm"]  # SOURCE // TOPIC
    assert [page.get_attribute(pps, a) for a in ("heading", "status", "index")] == ["PPS 7", "Q7", "P. 3 / 5"]
    assert page.inner_text(f"{due} .jv-window__title").split() == ["GE", "122", "//", "PPS", "7"]
    # the file's picture is the thread's page thumbnail, served by the hub, and never stretched past its 320 px
    src = page.get_attribute(f"{pps} jv-thumb img", "src")
    assert src == "/api/thumb/file-pps7-p3.webp" and page.locator(f"{pps} jv-thumb").bounding_box()["width"] <= 452  # media: the large tier (450 at 1440)
    # no button on a resting window (§14.2): "Open it" stays a real, named control and the panel is what he clicks
    assert page.get_by_role("button", name=re.compile(r"Open it\s*: PPS 7\.pdf")).count() == 1
    page.click(f"{pps} jv-thumb")  # a practice set opens in the hub's reader, at his place
    page.wait_for_function("location.hash === '#/read/th-pps7'")
    page.wait_for_selector("jv-resume-card")
    assert hub.problems == []


def test_the_orb_stands_by_alerts_and_picks_the_wake_beat(hub):
    page = hub.scene("now-active")
    orb = "#orb"
    assert page.get_attribute(orb, "openable") is not None and page.get_attribute(orb, "alert") is None
    send(page, "orb.state", {"state": "idle"})
    send(page, "presence.changed", {"here": False})
    page.wait_for_function("document.getElementById('orb').getAttribute('state') === 'standby'")
    assert "Standby" in page.inner_text("#status") and page.evaluate("document.documentElement.dataset.orb") == "standby"
    send(page, "presence.changed", {"here": True})
    send(page, "orb.state", {"state": "listening", "last_wake": None})  # the first wake: the full beat
    page.wait_for_function("document.getElementById('orb').getAttribute('wake') === 'full'")
    send(page, "orb.state", {"state": "idle"})
    send(page, "orb.state", {"state": "listening", "last_wake": page.evaluate("window.__jarvis.store.now().toISOString()")})
    page.wait_for_function("document.getElementById('orb').getAttribute('wake') === 'tighten'")
    send(page, "orb.state", {"state": "thinking"})
    page.wait_for_function("!document.getElementById('orb').hasAttribute('wake')")
    # something critical on the Rail: the orb's ring turns red, with the word for screen readers
    page.evaluate(f"""(() => {{ const s = {STATE}, rail = structuredClone(s.rail);
        rail.slots.homework.items[0].state = 'critical'; ({APPLY})('rail.updated', rail); }})()""")
    page.wait_for_function("document.getElementById('orb').getAttribute('alert') === 'crit'")
    assert "critical" in page.get_attribute("#orb .jv-orb__stage", "aria-label")
    assert hub.problems == []


def test_clicking_the_docked_orb_brings_back_the_full_view_and_windows_dock_it_again(hub):
    page = hub.open(motion="full")
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'settings.updated', ts: '', data: {...window.__jarvis.store.state.settings, stage: 'hub'}})")  # the windows on the home page (N9: "On the hub")
    page.evaluate("window.__jarvis.store.setUi({ambient: false})")
    page.wait_for_selector(".jv-now__ambient jv-orb")  # v0.18.0: nothing up, so the hub is the orb in the middle
    assert not page.is_visible("#orb")
    send(page, "window.push", {"id": "w-dock-test", "type": "notice", "title": "Dock test", "ref": "dock-test"})
    page.wait_for_selector("jv-window[window-id=w-dock-test]")  # the window is there at once; nothing waits for the orb
    moving = page.evaluate("[document.documentElement.hasAttribute('data-orb-docking'), !!document.querySelector('.jv-now--docking')]")
    page.wait_for_function("!document.documentElement.hasAttribute('data-orb-docking') && getComputedStyle(document.getElementById('orb')).visibility === 'visible'", timeout=3_000)
    assert page.locator(".jv-now--docking").count() == 0 and not page.is_visible(".jv-now__ambient")
    assert moving in ([True, True], [False, False])  # ([False, False] when this browser asks for reduced motion: an instant swap)
    page.click("#orb .jv-orb__open")  # the docked orb brings back the full view: the big orb and the clock
    page.wait_for_function(f"{STATE}.ui.ambient === true")
    assert page.is_visible(".jv-now__ambient jv-orb") and not page.is_visible("#orb")
    send(page, "window.dock", {"all": True, "reason": "cleared"})
    send(page, "presence.changed", {"here": False})  # he has left: the hub rests, the big orb stands by
    page.wait_for_function(f"{STATE}.ui.ambient === true")
    page.wait_for_function("document.querySelector('.jv-now__ambient jv-orb').getAttribute('state') === 'standby'")
    assert hub.problems == []


def test_the_reader_locks_onto_the_question_when_jarvis_names_it(hub):
    page = hub.scene("reader-resume", motion="full")  # a scene, so other tests' reading doesn't move the spot
    page.wait_for_selector("jv-resume-card")
    page.wait_for_function("document.querySelector('.jv-reader')?.dataset.state === 'ready'", timeout=10_000)
    until = page.evaluate("new Date(window.__jarvis.store.now().getTime() + 4000 - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 23)")
    send(page, "ui.focus", {"ref": "file-pps7", "until": until})  # named, but the spot is still a guess: the card stays
    page.wait_for_timeout(300)
    assert page.locator("jv-resume-card").count() == 1 and page.get_attribute("jv-view-reader", "data-locked") is None
    page.evaluate("window.__jarvis.bridge.act('resume_accept', 'th-pps7')")  # his yes: confirmed
    page.wait_for_function(f"{STATE}.threads.find(t => t.id === 'th-pps7').resume.source === 'confirmed'")
    page.wait_for_selector("jv-view-reader[data-locked=Q7]", timeout=3_000)  # the card lifts and the brackets lock onto Q7
    page.wait_for_selector("jv-resume-card", state="detached")
    assert hub.problems == []


def test_sounds_and_address_have_controls_and_the_sound_level_follows_them(hub):
    page = hub.scene("controls")
    assert page.get_attribute("[data-key=earcons-minimal]", "aria-checked") == "true"
    assert page.get_attribute("[data-key=address-name]", "aria-checked") == "true"
    page.click("[data-key=earcons-off]")
    page.click("[data-key=address-sir]")
    assert page.evaluate(f"[{STATE}.settings.earcons, {STATE}.settings.address]") == ["off", "sir"]
    rules = page.evaluate("import('/sounds/earcons.js').then((m) => [m.earconLevel(), m.shouldPlay('tick'), m.shouldPlay('tick', {level: 'minimal'})])")
    assert rules == ["off", False, True]
    assert hub.problems == []


def test_the_phone_caption_takes_its_own_row_and_clear_the_screen_says_where_things_go(hub):
    page = hub.scene("now-active", size="phone")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_selector("#caption .jv-caption")
    boxes = page.evaluate("""(() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
        return {stage: r('#stage').bottom, caption: r('#caption .jv-caption').top, rail: r('#rail').top, captionBottom: r('#caption .jv-caption').bottom}; })()""")
    assert boxes["stage"] <= boxes["caption"] + 1 and boxes["captionBottom"] <= boxes["rail"] + 1  # never over what he reads
    page.set_viewport_size({"width": 1440, "height": 900})
    source = page.evaluate("fetch('/components/command-bar/command-bar.js').then((r) => r.text())")
    assert re.search(r"Clear the screen \(everything goes to the Rail\)", source) and "close all windows" not in source
