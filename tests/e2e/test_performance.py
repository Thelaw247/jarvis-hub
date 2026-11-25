"""Latency and motion budgets (plan §3 rules 6 and 17, §12; HUD v2 §4, §7). Run on whatever machine runs the
tests, so the limits here are the plan's targets with headroom for a busy CI runner; the measured numbers
are printed with `pytest -s`."""

# Every animation on the page, with what it animates. `props` are the keyframe properties (CSS animations)
# or the transitioned property (CSS transitions); `html` is false for animations on SVG elements.
ANIMATIONS = """(scope) => document.getAnimations()
  .filter((a) => !scope || a.effect?.target?.closest?.(scope))
  .map((a) => ({
    name: a.animationName || a.transitionProperty || '',
    state: a.playState,
    html: !(a.effect?.target instanceof SVGElement),
    props: a.transitionProperty ? [a.transitionProperty]
      : [...new Set(a.effect.getKeyframes().flatMap((k) => Object.keys(k)))].filter((k) => !['offset', 'computedOffset', 'easing', 'composite'].includes(k)),
  }))"""
COMPOSITED = {"transform", "opacity"}
ORB_ALLOWED = COMPOSITED | {"stroke-dashoffset", "strokeDashoffset"}


def running(page, scope=None):
    return [a for a in page.evaluate(ANIMATIONS, scope) if a["state"] == "running"]


def wait_frames(page, n=2):
    page.evaluate(f"new Promise((r) => {{ let i = {n}; const f = () => (--i ? requestAnimationFrame(f) : r()); requestAnimationFrame(f); }})")


def orb_state(page, state, **data):
    page.evaluate("(d) => window.__jarvis.store.apply({v: 2, type: 'orb.state', ts: '', data: d})", {"state": state, **data})
    wait_frames(page)


def test_first_paint_and_shell_ready(hub):
    page = hub.open()
    timing = page.evaluate("""() => { const p = performance.getEntriesByType('paint').find(e => e.name === 'first-contentful-paint');
        return { fcp: p ? p.startTime : null, ready: performance.now() }; }""")
    print("first contentful paint (ms):", timing["fcp"])
    assert timing["fcp"] is not None and timing["fcp"] < 1500  # plan target on his laptops: < 300 ms warm


def test_event_to_pixel_is_within_a_frame_or_two(hub):
    page = hub.scene("now-awake")
    took = page.evaluate("""async () => { const s = window.__jarvis.store, t0 = performance.now();
        s.apply({v:1, type:'window.push', ts:'', data:{id:'w-perf', type:'countdown', title:'Due', ref:'due-pps7'}});
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        const ok = !!document.querySelector('jv-window[window-id=w-perf] .jv-big-number__value');
        return { ms: performance.now() - t0, ok }; }""")
    print("window.push to pixel (ms):", took["ms"])
    assert took["ok"] and took["ms"] < 100
    orb = page.evaluate("""async () => { const s = window.__jarvis.store, t0 = performance.now();
        s.apply({v:1, type:'orb.state', ts:'', data:{state:'listening', level:0.8}});
        await new Promise(r => requestAnimationFrame(r));
        const o = document.getElementById('orb');
        return { ms: performance.now() - t0, state: o.getAttribute('state'), look: o.dataset.look }; }""")
    print("orb.state to pixel (ms):", orb["ms"])
    assert orb["state"] == "listening" and orb["look"] == "listening" and orb["ms"] < 100  # Listening from the first frame


def test_branch_page_and_life_map_open_fast(hub):
    page = hub.scene("today")
    took = page.evaluate("""async () => { const r = window.__jarvis.router, t0 = performance.now();
        r.go('/life/ge-122'); await new Promise(f => requestAnimationFrame(() => requestAnimationFrame(f)));
        const page = performance.now() - t0, ok = document.querySelector('#branch-title')?.textContent === 'GE 122' && document.querySelectorAll('.jv-map__node').length === 7;
        const t1 = performance.now(); r.go('/life/school'); await new Promise(f => requestAnimationFrame(f));
        return { page, ok, fly: performance.now() - t1, nodes: document.querySelectorAll('.jv-map__node, .jv-map__dot').length }; }""")
    print("Life Map + branch page (ms):", took["page"], "refocus (ms):", took["fly"])
    assert took["ok"] and took["page"] < 300 and took["fly"] < 100 and took["nodes"] <= 60


def test_click_feedback_is_immediate(hub):
    page = hub.scene("controls")
    took = page.evaluate("""async () => { const b = document.querySelector('[data-key=interruption-chatty]'), t0 = performance.now();
        b.click(); await new Promise(r => requestAnimationFrame(r));
        return { ms: performance.now() - t0, on: document.querySelector('[data-key=interruption-chatty]').getAttribute('aria-checked') }; }""")
    assert took["on"] == "true" and took["ms"] < 100


# ---- motion budgets ------------------------------------------------------------------------------------

def test_ambient_screen_runs_at_most_eight_html_animations_and_stops_when_hidden(hub):
    """Plan §3 rule 6: on ambient, ≤ 8 running animations, all on HTML elements, transform/opacity only."""
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("now-ambient", motion="full")
    for state in ("idle", "listening", "thinking", "speaking"):
        orb_state(page, state, level=0.6)
        page.wait_for_timeout(650)  # the state change's own transitions and beat (≤ 500 ms, v0.11) are over: what keeps running?
        now = running(page)
        print(f"ambient, {state}: {len(now)} running", sorted(a["name"] for a in now))
        assert 1 <= len(now) <= 8, (state, now)
        assert all(a["html"] for a in now), [a for a in now if not a["html"]]
        assert all(set(a["props"]) <= COMPOSITED for a in now), [a for a in now if not set(a["props"]) <= COMPOSITED]
    page.evaluate("document.documentElement.setAttribute('data-hidden', '')")  # main.js sets it on visibilitychange
    assert running(page) == []


def test_the_orb_animates_only_transform_opacity_and_dash_offset(hub):
    """Every animation and transition the orb ever runs, through every state and beat."""
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-idle", motion="full")
    seen = {}

    def collect():
        for a in page.evaluate(ANIMATIONS, "jv-orb"):
            seen.setdefault(a["name"], set()).update(a["props"])
    steps = [
        "o.setAttribute('state', 'standby')", "o.setAttribute('wake', 'full'); o.setAttribute('state', 'listening')",
        "o.setAttribute('state', 'thinking')", "o.orb = {state: 'speaking', level: 0.9}; o.setAttribute('state', 'speaking')",
        "o.orb = {state: 'waiting', countdown_s: 8, window_s: 10}; o.setAttribute('state', 'waiting')",
        "o.setAttribute('alert', 'crit')", "o.removeAttribute('alert'); o.setAttribute('state', 'muted')",
        "o.setAttribute('state', 'idle'); o.removeAttribute('wake'); o.setAttribute('state', 'listening')",
        "o.setAttribute('docked', '')",
    ]
    for js in steps:
        # sample at once (after the element's microtask render), so a short beat is seen even on a slow machine
        got = page.evaluate(f"""async () => {{ const o = document.querySelector('jv-orb'); {js};
            await new Promise((r) => queueMicrotask(r)); await new Promise((r) => queueMicrotask(r));
            getComputedStyle(o).opacity; return ({ANIMATIONS})('jv-orb'); }}""")
        for a in got:
            seen.setdefault(a["name"], set()).update(a["props"])
        for _ in range(3):
            wait_frames(page, 3)
            collect()
    page.wait_for_timeout(260)  # the dock's slide starts after the 200 ms retract
    collect()
    print("orb animations:", {k: sorted(v) for k, v in seen.items()})
    assert {"jv-orb-wake", "jv-orb-turn", "jv-orb-drain", "jv-orb-pulse", "transform"} <= set(seen)  # the beats really ran
    bad = {k: v for k, v in seen.items() if not v <= ORB_ALLOWED}
    assert not bad, bad


def test_orb_decoration_and_the_whole_page_fit_their_node_budgets(hub):
    page = hub.scene("orb-idle")
    centre = page.evaluate("document.querySelectorAll('.jv-orb-scene jv-orb *').length")
    corner = page.evaluate("(() => { const o = document.createElement('jv-orb'); o.setAttribute('size', 'corner'); document.body.append(o); return o.querySelectorAll('*').length; })()")
    print("orb nodes: centre", centre, "corner", corner)
    assert centre <= 250 and corner <= 250
    for scene in ("now-crowded", "now-ambient"):
        page = hub.scene(scene, theme="night")
        total = page.evaluate("document.querySelectorAll('*').length")
        print(scene, "page nodes:", total)
        assert total <= 1200


def test_nothing_moves_on_the_strip(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    hub.page.add_init_script("""window.__raf = 0; const raf = window.requestAnimationFrame.bind(window);
        window.requestAnimationFrame = (f) => { window.__raf++; return raf(f); };""")
    for scene in ("strip", "strip-waiting", "orb-strip"):
        page = hub.scene(scene, size="strip", motion="full")
        orb_state(page, "speaking", level=0.9)
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelectorAll('jv-orb').length") >= 1
        assert page.evaluate(ANIMATIONS, None) == [], scene  # not even a paused one
        before = page.evaluate("window.__raf")
        page.wait_for_timeout(300)
        loop = page.evaluate("import('/components/orb/orb.js').then((m) => m.orbLoop.running)")
        assert not loop and page.evaluate("window.__raf") - before <= 2, scene


def test_reduced_motion_holds_a_still_orb_with_its_word(hub):
    for scene, word in (("orb-speaking", "Speaking"), ("orb-thinking", "Thinking"), ("orb-muted", "Muted"), ("orb-alert-crit", "Critical")):
        page = hub.scene(scene, theme="night")
        assert page.evaluate("document.documentElement.hasAttribute('data-still')")
        assert running(page, "jv-orb") == [], scene
        assert page.evaluate("import('/components/orb/orb.js').then((m) => m.orbLoop.running)") is False
        shown = page.evaluate("(() => { const w = document.querySelector('.jv-orb-scene .jv-orb__word'); return getComputedStyle(w).display !== 'none' && w.textContent; })()")
        assert shown == word, (scene, shown)
    # waiting: the drained dots are held where they are (7 s of 10 left = 14 of 48 gone); no countdown number
    page = hub.scene("orb-waiting", theme="night")
    assert page.evaluate("getComputedStyle(document.querySelector('.jv-orb-scene .jv-orb__drain-mask')).strokeDashoffset") in ("-14", "-14px")
    words = page.evaluate("[...document.querySelectorAll('.jv-orb-scene jv-orb text, .jv-orb-scene .jv-orb__word')].map((t) => t.textContent).join(' ')")
    assert "AWAITING" in words and not any(ch.isdigit() for ch in words)


def test_the_level_loop_runs_at_30_fps_and_pauses_when_hidden_off_screen_or_in_a_game(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-speaking", motion="full")
    measure = """async (ms) => { const m = await import('/components/orb/orb.js'), o = document.querySelector('.jv-orb-scene jv-orb');
        const hash = [...o.querySelectorAll('.jv-orb__hash')]; let steps = 0;
        const mo = new MutationObserver(() => steps++); hash.forEach((p) => mo.observe(p, { attributes: true, attributeFilter: ['style'] }));
        const f0 = m.orbLoop.frames, t0 = performance.now(); let i = 0;
        const feed = setInterval(() => { o.level = (Math.sin(i++ / 2) + 1) / 2; }, 8);  // a fast-changing voice level
        await new Promise((r) => setTimeout(r, ms)); clearInterval(feed); mo.disconnect();
        const s = (performance.now() - t0) / 1000;
        return { fps: (m.orbLoop.frames - f0) / s, hashPerSecond: steps / s, running: m.orbLoop.running }; }"""
    live = page.evaluate(measure, 1500)
    print("level loop:", live)
    # ≤ 30 fps; the floor only proves it runs (busy CI). The hash marks step 3 times a second: a 1.5 s window can
    # catch a fifth step at its edge (5 / 1.5 = 3.33, seen on GitHub's runner), never a sixth (4.0)
    assert 2 <= live["fps"] <= 31 and live["hashPerSecond"] <= 3.4
    # hidden page
    page.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
    hidden = page.evaluate(measure, 400)
    assert hidden["fps"] == 0 and not hidden["running"]
    page.evaluate("delete document.hidden; document.dispatchEvent(new Event('visibilitychange'))")
    assert page.evaluate(measure, 400)["fps"] > 0
    # off screen (IntersectionObserver)
    page.evaluate("document.querySelector('.jv-orb-scene jv-orb').style.cssText = 'position: fixed; top: -5000px'")
    page.wait_for_timeout(150)
    assert page.evaluate(measure, 400)["fps"] == 0
    assert running(page, ".jv-orb-scene jv-orb") == []  # its CSS motion pauses too
    page.evaluate("document.querySelector('.jv-orb-scene jv-orb').style.cssText = ''")
    page.wait_for_timeout(150)
    # game mode
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'settings.updated', ts: '', data: {...window.__jarvis.store.state.settings, game_mode: 'on'}})")
    wait_frames(page)
    assert page.evaluate(measure, 400)["fps"] == 0
