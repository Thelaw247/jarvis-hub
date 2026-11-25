"""Checks for the v0.2.1 integration follow-ups that cross work packages (I-fix)."""


def test_life_redraws_when_the_window_crosses_a_size_and_fits_320px(hub):
    page = hub.open("#/life/ge-122")
    page.wait_for_selector("jv-view-life .jv-map")
    page.set_viewport_size({"width": 320, "height": 700})
    page.wait_for_function("document.documentElement.dataset.size === 'phone'")
    page.wait_for_selector("jv-view-life jv-life-outline")  # the map gives way to the list without a reload
    assert page.locator("jv-view-life .jv-map").count() == 0
    assert page.evaluate("(() => { const s = document.getElementById('stage'); return s.scrollWidth - s.clientWidth; })()") == 0
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_selector("jv-view-life .jv-map")
    assert hub.problems == []


def test_toasts_sit_in_the_header_clear_of_windows_and_the_caption(hub):
    page = hub.scene("now-full")
    page.evaluate("""() => { const s = window.__jarvis.store;
        s.apply({v: 1, type: 'toast', ts: '', data: {id: 't-a', kind: 'success', text: 'Moved your review to 5 pm', action: {label: 'Undo (24 h)', action: 'undo', target: 'x'}}});
        s.apply({v: 1, type: 'toast', ts: '', data: {id: 't-b', kind: 'info', text: "Less of this from now on."}});
        s.apply({v: 1, type: 'caption.show', ts: '', data: {text: 'PPS 7 is due Wednesday at 4 pm.'}}); }""")
    page.wait_for_selector("#toasts .jv-toast >> nth=1")
    hits = page.evaluate("""() => {
        const box = (e) => e.getBoundingClientRect();
        const over = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
        const others = [...document.querySelectorAll('#stage jv-window, #caption, #search, jv-tabs')].map(box);
        return [...document.querySelectorAll('#toasts .jv-toast')].map(box).filter((t) => others.some((o) => over(t, o))).length; }""")
    assert hits == 0
    assert hub.problems == []


def test_the_orb_and_the_status_line_use_the_same_word_at_rest(hub):
    page = hub.scene("shell")
    words = page.evaluate("import('/components/orb/orb.js').then((m) => [m.ORB_WORDS.idle, m.ORB_WORDS.listening])")
    assert words == ["Listening", "Hearing you"]
    assert hub.state("s => s.orb.state") == "idle" and "Listening" in page.locator("jv-status-line").inner_text()


def test_phone_now_windows_fill_the_column(hub):
    page = hub.scene("phone-now")
    page.set_viewport_size({"width": 390, "height": 844})
    widths = page.evaluate("[...document.querySelectorAll('.jv-now__canvas > jv-window')].map((w) => w.getBoundingClientRect().width)")
    assert widths and min(widths) > 340
