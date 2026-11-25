"""Final fixes R3 (v0.3.0 reviews), updated for HUD v3: the dial's short label, Stage windows
that never cut anything silently, the chart's day labels, the hidden Stage orb at rest, small orb text and Esc
on the Stage."""
import pytest

STATE = "window.__jarvis.store.state"
SIZES = ((1920, 1080, "full"), (1440, 900, "full"), (1280, 720, "laptop"))

# The Stage's collage (HUD v3 §14): every window body fits (or says it doesn't); nothing is off-screen; nothing
# (frame, ghost edges or the metadata under it) is over the docked orb or the bottom row; no kicker is under
# another window; the window Jarvis means is fully visible, its metadata too (checked by hit-testing it).
FIT = """(() => {
  const wins = [...document.querySelectorAll('.jv-stage__canvas > jv-window:not([leaving])')];
  const rect = (e) => e.getBoundingClientRect();
  const hit = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const id = (w) => w.getAttribute('window-id');
  const z = (w) => Number(getComputedStyle(w).zIndex) || 0;
  const cut = wins.filter((w) => { const b = w.querySelector('.jv-window__body'); return b.scrollHeight - b.clientHeight > 2 && !w.hasAttribute('data-clipped'); }).map(id);
  // a window's whole footprint: the frame, its ghost edges and the metadata hanging under it
  const foot = (w) => { const parts = [w, ...w.querySelectorAll(':scope > .jv-window__ghost, :scope > .jv-window__meta')].map(rect);
    return { left: Math.min(...parts.map((r) => r.left)), top: Math.min(...parts.map((r) => r.top)), right: Math.max(...parts.map((r) => r.right)), bottom: Math.max(...parts.map((r) => r.bottom)) }; };
  const off = wins.filter((w) => { const r = foot(w); return r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight; }).map(id);
  const keep = ['dock', 'foot'].map((k) => document.getElementById(k)).filter((n) => n && n.getBoundingClientRect().height).map((n) => [n.id, rect(n)]);
  const under = []; for (const w of wins) for (const [k, r] of keep) if (hit(foot(w), r)) under.push([id(w), k]);
  const kicker = []; for (const w of wins) { const h = rect(w.querySelector('.jv-window__head'));
    for (const o of wins) if (o !== w && z(o) > z(w) && hit(h, rect(o))) kicker.push([id(w), id(o)]); }
  const active = wins.filter((w) => w.hasAttribute('active'));
  const hidden = [];
  for (const w of active) {
    const r = rect(w), pts = [];
    for (let i = 0; i <= 4; i++) for (let j = 0; j <= 4; j++) pts.push([r.left + 2 + (r.width - 4) * i / 4, r.top + 2 + (r.height - 4) * j / 4]);
    const m = w.querySelector(':scope > .jv-window__meta'); if (m) { const mr = rect(m); pts.push([mr.left + 4, mr.top + mr.height / 2]); }
    for (const [x, y] of pts) { const top = document.elementFromPoint(x, y)?.closest('jv-window'); if (top && top !== w) hidden.push([id(w), id(top), Math.round(x), Math.round(y)]); }
  }
  return { n: wins.length, active: active.length, cut, off, under, kicker, hidden };
})()"""


def test_the_state_word_clears_the_hash_marks(hub):
    for width, height, size in SIZES:
        hub.page.set_viewport_size({"width": width, "height": height})
        page = hub.scene("now", theme="night", size=size)  # reduced motion: the orb says "Speaking"
        # the hash groups' inner ends sit 51.6 units (of the orb's 220) out from the centre line on each side
        gap = page.evaluate("""(() => {
          const orb = document.querySelector('.jv-now__ambient jv-orb'), o = orb.getBoundingClientRect(), w = orb.querySelector('.jv-orb__word').getBoundingClientRect();
          const unit = o.width / 220, inner = (2.2 * 36 - 3 - 3.2) * Math.SQRT1_2 * unit, centre = o.left + o.width / 2;
          return w.width ? inner - Math.max(centre - w.left, w.right - centre) : null; })()""")
        assert gap is not None and gap >= 4, (width, height, gap)


def test_the_dial_label_is_short_and_never_cut(hub):
    page = hub.scene("shell")
    words = page.evaluate("""import('/components/day-dial/day-dial.js').then((d) => [
        ['Review GE 122 lecture 21', 'block', 'Your desk'], ['GE 122 lecture 21 · Frames', 'class', 'ENGR 1A10'],
        ['CHEM 142 lab 4', 'lab', 'Thorvaldson 173'], ['PPS 7 · questions 7 to 12', 'block', 'Your desk'],
        ['Lunch with Sam and the whole study squad', 'own']]
      .map(([title, kind, where]) => d.dialModel([{ id: 'x', kind, title, where, state: 'next', start: '2026-11-16T16:00:00', end: '2026-11-16T17:00:00' }], '2026-11-16T15:40:00').next.label))""")
    assert words == ["4:00 · GE 122 review", "4:00 · GE 122 · ENGR 1A10", "4:00 · CHEM 142 lab", "4:00 · PPS 7", "4:00 · Lunch with Sam"]
    # HUD v3: the dial left the home screen (§14 decision 6) and the orb draws it only with `dial` (P1), so the
    # label is checked on the dial's own orb scene, at the three sizes, with `dial` set
    for size, w, h in (("ambient", 1920, 1080), ("laptop", 1280, 720), ("full", 1440, 900)):
        hub.page.set_viewport_size({"width": w, "height": h})
        page = hub.scene("day-dial-orb", theme="night", size=size, state="moved")
        page.evaluate("document.querySelectorAll('jv-orb').forEach((o) => o.setAttribute('dial', ''))")
        page.wait_for_selector(".jv-day-dial__label")
        scene = f"day-dial-orb@{size}"
        got = page.eval_on_selector(".jv-day-dial__label", """e => { const cs = getComputedStyle(e), lh = parseFloat(cs.lineHeight);
            return { text: e.textContent, ellipsis: cs.textOverflow, lines: Math.round(e.getBoundingClientRect().height / lh), wide: e.scrollWidth - e.clientWidth }; }""")
        assert "…" not in got["text"] and got["ellipsis"] != "ellipsis" and got["lines"] <= 2 and got["wide"] <= 1, (scene, got)
        assert "Your desk" not in got["text"], (scene, got)


@pytest.mark.parametrize("scene", ["stage-active", "stage-crowded", "stage-waiting", "stage-focus", "stage-board"])
def test_the_stage_collage_fits_the_screen(hub, scene):
    for width, height, size in SIZES:
        for theme in ("night", "day"):
            hub.page.set_viewport_size({"width": width, "height": height})
            page = hub.scene(scene, theme=theme, size=size)
            page.wait_for_timeout(120)  # the second measuring pass (late fonts) and any step aside
            got = page.evaluate(FIT)
            assert got["n"] >= 1 and got["active"] == 1, (scene, width, height, theme, got)
            assert got["cut"] == [] and got["off"] == [] and got["under"] == [], (scene, width, height, theme, got)
            assert got["kicker"] == [] and got["hidden"] == [], (scene, width, height, theme, got)
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_the_window_jarvis_names_comes_to_the_front_whole(hub):
    # stage-focus: Jarvis names PPS 7's countdown, wherever the collage put it: it is drawn on top, whole
    for width, height, size in SIZES:
        hub.page.set_viewport_size({"width": width, "height": height})
        page = hub.scene("stage-focus", theme="night", size=size)
        page.wait_for_timeout(120)
        got = page.evaluate(FIT)
        assert page.get_attribute("jv-window[window-id=w-due-pps7]", "active") == "" and got["hidden"] == [], (width, got)
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_a_window_that_cannot_fit_says_so(hub):
    hub.page.set_viewport_size({"width": 1280, "height": 720})
    page = hub.scene("stage-waiting", theme="night", size="laptop")
    # make the question's window far too short: nothing can step aside (the other one is pinned), so it says so
    page.evaluate("Promise.all(window.__jarvis.store.state.windows.map((w) => window.__jarvis.bridge.act('pin', w.id)))")
    page.add_style_tag(content=".jv-stage__canvas > jv-window { max-height: 60px !important; }")
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_selector("jv-window[window-id=w-ap-week][data-clipped]")
    after = page.eval_on_selector("jv-window[window-id=w-ap-week]", "e => getComputedStyle(e, '::before').content")
    assert "More" in after
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_the_week_chart_keeps_every_bar_and_labels_the_days(hub):
    for width, height, size in SIZES:
        hub.page.set_viewport_size({"width": width, "height": height})
        page = hub.scene("stage-crowded", theme="night", size=size)
        page.wait_for_selector("jv-window[window-id=w-chart] .jv-mini-chart__bar")
        got = page.evaluate("""(() => {
          const w = document.querySelector('jv-window[window-id=w-chart]'), body = w.querySelector('.jv-window__body').getBoundingClientRect();
          const bars = [...w.querySelectorAll('.jv-mini-chart__bar')].map((b) => b.getBoundingClientRect());
          const labels = [...w.querySelectorAll('.jv-mini-chart__label')].map((l) => [l.textContent, getComputedStyle(l).fontSize, l.getBoundingClientRect().bottom <= body.bottom + 1]);
          return { bars: bars.map((b) => [Math.round(b.height), b.top >= body.top - 1 && b.bottom <= body.bottom + 1]), labels }; })()""")
        assert len(got["bars"]) == 5 and all(h >= 2 and inside for h, inside in got["bars"]), (width, got)
        assert [t for t, _, _ in got["labels"]] == ["Mon", "Tue", "Wed", "Thu", "Fri"], got
        assert all(px == "12px" and inside for _, px, inside in got["labels"]), got
    hub.page.set_viewport_size({"width": 1440, "height": 900})
    page = hub.scene("shell")
    assert page.evaluate("import('/components/mini-chart/mini-chart.js').then((m) => ['Monday', 'Tuesday', 'Wed', 'Hear'].map(m.shortLabel))") == ["Mon", "Tue", "Wed", "Hear"]


def test_the_hidden_stage_orb_runs_nothing(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    try:
        page = hub.scene("stage-active", theme="night", motion="full")
        page.wait_for_selector(".jv-stage__orb[data-offstage]", state="attached")
        # (a wait, not a fixed pause: on a busy machine the last transition can still be finishing after 300 ms)
        page.wait_for_function("document.querySelector('.jv-stage__orb').getAnimations({ subtree: true }).filter((a) => a.playState === 'running').length === 0", timeout=3_000)
        page = hub.scene("stage-empty", theme="night", motion="full")  # standby: the centre orb is the face again
        page.wait_for_timeout(300)
        assert not page.evaluate("document.querySelector('.jv-stage__orb').hasAttribute('data-offstage')")
        assert page.evaluate("document.querySelector('.jv-stage__orb').getAnimations({ subtree: true }).filter((a) => a.playState === 'running').length") > 0
    finally:
        hub.page.emulate_media(reduced_motion="reduce")


def test_no_text_under_12px_in_a_small_or_docked_orb(hub):
    for width, height, size in ((1920, 1080, "full"), (1280, 720, "laptop")):
        hub.page.set_viewport_size({"width": width, "height": height})
        page = hub.scene("stage-waiting", theme="night", size=size)
        tiny = page.evaluate("""[...document.querySelectorAll('jv-orb text')].filter((t) => {
            const r = t.getBoundingClientRect(); return r.height > 0 && getComputedStyle(t).display !== 'none' && r.height < 12; }).map((t) => t.textContent)""")
        assert tiny == [], (width, height, tiny)
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_esc_on_the_stage_closes_the_focused_window(hub):
    page = hub.scene("stage-active", theme="night")
    page.focus("jv-window[window-id=w-pps7] .jv-window__tool")
    page.keyboard.press("Escape")
    page.wait_for_function(f"!{STATE}.windows.some((w) => w.id === 'w-pps7')")
    page.wait_for_selector("jv-window[window-id=w-pps7]", state="detached")
    focused = page.evaluate("document.activeElement.closest('jv-window')?.getAttribute('window-id') || document.activeElement.tagName")
    assert focused in ("w-next", "w-due-pps7", "w-ge122")  # focus went to the next window, never the body


def test_the_close_button_names_its_window(hub):
    page = hub.scene("stage-active", theme="night")
    assert page.get_attribute("jv-window[window-id=w-pps7] [data-tool=close]", "title") == "Close PPS 7 (it waits on the Rail)"
