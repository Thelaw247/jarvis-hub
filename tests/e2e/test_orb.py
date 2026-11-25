"""The Core orb (N2, HUD v2 §4, §7): states and words, the wake beats, docking, readouts, the dial slot and the
earcons. Motion budgets are in test_performance.py."""
import pytest


def frames(page, n=2):
    page.evaluate(f"new Promise((r) => {{ let i = {n}; const f = () => (--i ? requestAnimationFrame(f) : r()); requestAnimationFrame(f); }})")


def make_orb(page, **attrs):
    page.evaluate("""(attrs) => { document.querySelector('#__t')?.remove(); const o = document.createElement('jv-orb'); o.id = '__t';
        for (const [k, v] of Object.entries(attrs)) o.setAttribute(k, v); document.querySelector('#stage').append(o); }""", attrs)
    frames(page)


def test_every_state_has_a_label_and_a_look(hub):
    page = hub.scene("component:orb", theme="night")
    labels = page.eval_on_selector_all("jv-orb[size=centre] .jv-orb__stage", "els => els.map(e => e.getAttribute('aria-label'))")
    assert {"Jarvis: standby", "Jarvis: listening", "Jarvis: hearing you", "Jarvis: thinking", "Jarvis: speaking", "Jarvis: waiting for your yes",
            "Jarvis: listening, needs you", "Jarvis: listening, critical", "Jarvis: muted", "Jarvis: offline"} <= set(labels)
    looks = page.eval_on_selector_all("jv-orb[size=centre]", "els => els.map(e => e.dataset.look + (e.dataset.alert ? ':' + e.dataset.alert : ''))")
    assert looks == ["standby", "idle", "listening", "thinking", "speaking", "waiting", "idle:warn", "idle:crit", "muted", "offline"]
    # unknown or retired names still draw (as idle); "alert" alone is an amber alert
    make_orb(page, state="gyroscope")
    assert page.evaluate("document.querySelector('#__t').dataset.look") == "idle"
    make_orb(page, state="alert")
    assert page.evaluate("[document.querySelector('#__t').dataset.look, document.querySelector('#__t').dataset.alert]") == ["idle", "warn"]
    assert hub.problems == []


def test_a_wake_shows_listening_at_once_and_plays_the_full_beat_only_when_told(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-idle", theme="night", motion="full")
    make_orb(page, state="idle")
    got = page.evaluate("""() => { const o = document.querySelector('#__t'); o.setAttribute('state', 'listening');
        return new Promise((r) => queueMicrotask(() => r([o.dataset.look, o.dataset.wake]))); }""")
    assert got == ["listening", "tighten"]  # Listening is drawn in the same frame; an ordinary wake only tightens
    page.wait_for_timeout(320)
    assert page.evaluate("document.querySelector('#__t').dataset.wake") is None
    make_orb(page, state="standby", wake="full")
    page.evaluate("document.querySelector('#__t').setAttribute('state', 'listening')")
    frames(page)
    assert page.evaluate("document.querySelector('#__t').dataset.wake") == "full"
    assert page.evaluate("document.getAnimations().some((a) => a.animationName === 'jv-orb-wake')")
    # v0.5.1: the full wake is flat. A 3D tilt played while the orb slid to the corner looked like the rings
    # spinning on the wrong axis; every ring only ever turns and scales about the centre, in the screen's plane.
    assert page.evaluate("""() => [...document.querySelectorAll('#__t .jv-orb__tilt, #__t .jv-orb__stage')]
        .every((el) => !getComputedStyle(el).transform.startsWith('matrix3d') && getComputedStyle(el).perspective === 'none')""")
    # not a wake: thinking → listening plays no beat
    make_orb(page, state="thinking")
    page.evaluate("document.querySelector('#__t').setAttribute('state', 'listening')")
    frames(page)
    assert page.evaluate("document.querySelector('#__t').dataset.wake") is None
    kinds = page.evaluate("""import('/components/orb/orb.js').then(({ wakeKind }) => [wakeKind(null),
        wakeKind('2026-11-16T09:00:00', new Date('2026-11-16T10:00:00')), wakeKind('2026-11-16T05:00:00', new Date('2026-11-16T10:00:00')),
        wakeKind('2026-11-15T23:30:00', new Date('2026-11-16T00:30:00'))])""")
    assert kinds == ["full", "tighten", "full", "full"]


def test_reduced_motion_wakes_and_docks_instantly(hub):
    page = hub.scene("orb-idle", theme="night")
    make_orb(page, state="idle", wake="full")
    page.evaluate("document.querySelector('#__t').setAttribute('state', 'listening')")
    frames(page)
    assert page.evaluate("document.querySelector('#__t').dataset.wake") is None
    page.evaluate("window.__docked = 0; document.addEventListener('jv-orb-docked', () => window.__docked++)")
    page.evaluate("document.querySelector('#__t').setAttribute('docked', '')")
    frames(page)
    assert page.evaluate("[document.querySelector('#__t').dataset.dock, window.__docked]") == ["docked", 1]


def test_docking_retracts_slides_to_the_corner_and_skips_the_slide_within_a_minute(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-speaking", theme="night", motion="full")
    page.evaluate("""() => { window.__ev = []; for (const n of ['jv-orb-docked', 'jv-orb-undocked']) document.addEventListener(n, () => window.__ev.push(n));
        import('/components/orb/orb.js').then((m) => m.resetDock()); }""")
    orb = ".jv-orb-scene jv-orb"
    page.evaluate(f"document.querySelector('{orb}').setAttribute('docked', '')")
    frames(page)
    # v0.5.3: the slide starts 120 ms in, while the outer rings are still pulling in (one motion, not two)
    assert page.evaluate(f"document.querySelector('{orb}').dataset.dock") in ("retract", "slide")
    page.wait_for_timeout(260)
    assert page.evaluate(f"document.querySelector('{orb}').dataset.dock") in ("slide", "docked")  # v0.6.0: a 450 ms slide
    page.wait_for_function("window.__ev.includes('jv-orb-docked')", timeout=2000)
    box = page.evaluate(f"""(() => {{ const r = document.querySelector('{orb} .jv-orb__L--dots').getBoundingClientRect();
        return {{ cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, vw: innerWidth, vh: innerHeight }}; }})()""")
    assert box["cx"] > box["vw"] - 140 and box["cy"] > box["vh"] - 140 and 100 < box["w"] < 135  # 120 px mini rings, bottom-right
    assert page.evaluate(f"getComputedStyle(document.querySelector('{orb} .jv-orb__L--ticks')).opacity") == "0"  # outer layers retracted
    page.evaluate(f"document.querySelector('{orb}').removeAttribute('docked')")
    page.wait_for_function("window.__ev.includes('jv-orb-undocked')", timeout=2000)
    page.evaluate(f"document.querySelector('{orb}').setAttribute('docked', '')")  # content again within 60 s: no slide
    frames(page)
    assert page.evaluate(f"document.querySelector('{orb}').dataset.dock") == "docked"


def test_the_ticks_are_bare_and_the_numbers_live_under_the_hood(hub):
    page = hub.scene("orb-idle", theme="night")
    assert page.locator("jv-orb .jv-orb__readout, jv-orb .jv-orb__L--read").count() == 0  # Huw's ticks are bare (v0.4.1)
    assert page.locator(".jv-orb-scene jv-orb .jv-orb__ticks").count() == 1  # the four plain dashes stay
    assert "MS" not in page.inner_text(".jv-orb-scene jv-orb") and "MIN" not in page.inner_text(".jv-orb-scene jv-orb")
    assert page.get_attribute(".jv-orb-scene jv-orb .jv-orb__stage", "aria-label") == "Jarvis: listening"  # the screen-reader status stays
    page = hub.scene("hood", theme="night")  # the same numbers, where they are useful
    text = page.inner_text("jv-view-hood").lower()
    assert "think" in text and "420" in text and "hear" in text and "180" in text


CENTRES = """async ({ ms, still }) => {
  const o = document.querySelector('.jv-orb-scene jv-orb') || document.querySelector('jv-view-now jv-orb') || document.querySelector('jv-orb');
  const c = (el) => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.width]; };
  const layers = [...o.querySelectorAll('.jv-orb__L:not(.jv-orb__dial), .jv-orb__spin, .jv-orb__spin2, .jv-orb__lvl, .jv-orb__svg')].filter((el) => el.getBoundingClientRect().width > 0);
  const seq = ['listening', 'thinking', 'speaking'], t0 = performance.now(), worst = {}; let i = 0, scaled = 0;
  const lvl = [...o.querySelectorAll('.jv-orb__lvl, .jv-orb__L--energy, .jv-orb__L--halo')];  // v0.5.6: the glow layer grows by state (speaking), never with the voice level: checked on its own
  while (performance.now() - t0 < ms) {
    const st = seq[Math.min(2, Math.floor(((performance.now() - t0) / ms) * 3))];
    if (o.getAttribute('state') !== st) o.setAttribute('state', st);
    o.orb = { state: st, level: (i++ % 5) / 4 };  // the voice level swings from silence to full
    await new Promise((r) => setTimeout(r, 50));
    const [ox, oy] = c(o);
    for (const el of layers) { const [x, y] = c(el), d = Math.hypot(x - ox, y - oy), k = (el.closest('.jv-orb__L')?.classList[1] || '') + ' ' + (el.classList?.[0] || el.tagName);
      worst[k] = Math.max(worst[k] || 0, d); }
    for (const el of lvl) { const t = getComputedStyle(el).transform; if (t !== 'none' && t !== 'matrix(1, 0, 0, 1, 0, 0)') scaled++; }
  }
  // v0.11.2: the extra spin is turned by orb.js (eased; the outer rings follow Jarvis's voice, the other way)
  const angle = (el) => { const m = new DOMMatrix(getComputedStyle(el).transform); return Math.atan2(m.b, m.a) * 180 / Math.PI; };
  const wheels = ['arcs-a', 'outer', 'dots'].map((n) => o.querySelector(`.jv-orb__L--${n} .jv-orb__spin2`));
  const a0 = wheels.map(angle); await new Promise((r) => setTimeout(r, 300)); const a1 = wheels.map(angle);
  const spinning = a0.map((a, k) => { const d = ((a1[k] - a + 540) % 360) - 180; return d > 0.5 ? 'cw' : d < -0.5 ? 'ccw' : 'still'; });
  return { worst: Math.max(...Object.values(worst)), layers: layers.length, scaled, spinning, look: o.dataset.look }; }"""


@pytest.mark.parametrize("size", [(1920, 1080), (1440, 900)])
def test_every_ring_stays_centred_from_listening_to_speaking(hub, size):
    # v0.4.1: "when Jarvis talks and the rings speed up, they spin off centre". A 3D tilt under the stage's
    # perspective threw the arcs up to 6 px off; now every ring only ever rotates about the centre.
    hub.page.set_viewport_size({"width": size[0], "height": size[1]})
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("now", theme="night")  # the home while Jarvis speaks: the big orb, motion on
    assert page.evaluate("!document.documentElement.hasAttribute('data-still')")
    got = page.evaluate(CENTRES, {"ms": 3000, "still": False})
    assert got["layers"] >= 20 and got["look"] == "speaking"
    assert got["worst"] <= 1, got  # every layer's centre within 1 px of the orb's, the whole way
    assert got["scaled"] == 0, got  # no pulsing: nothing scales with the voice
    assert got["spinning"] == ["cw", "ccw", "ccw"]  # speaking: the inner arcs one way, the outer wheels the other
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_reduced_motion_and_the_docked_orb_stay_centred_too(hub):
    page = hub.scene("now", theme="night")  # the fixture asks for reduced motion
    got = page.evaluate(CENTRES, {"ms": 900, "still": True})
    assert got["worst"] <= 1 and got["scaled"] == 0, got
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("stage-active", theme="night")  # the docked mini rings beside the windows
    got = page.evaluate(CENTRES.replace("document.querySelector('.jv-orb-scene jv-orb') || document.querySelector('jv-view-now jv-orb') || document.querySelector('jv-orb')", "document.getElementById('orb')"), {"ms": 1500, "still": False})
    assert got["layers"] >= 10 and got["worst"] <= 1 and got["scaled"] == 0, got


def test_the_glow_is_always_there_and_brightens_when_jarvis_speaks(hub):
    sizes = {}
    for state in ("idle", "speaking"):
        page = hub.scene(f"orb-{state}", theme="night")
        sizes[state] = page.evaluate("(() => { const o = document.querySelector('.jv-orb-scene jv-orb'); const g = o.querySelector('.jv-orb__L--glow');"
                                     " return [Number(getComputedStyle(g).opacity), o.querySelector('.jv-orb__en-bloom').getBoundingClientRect().width / o.querySelector('.jv-orb__core').getBoundingClientRect().width]; })()")
    assert sizes["idle"][0] >= 0.5 and sizes["speaking"][0] > sizes["idle"][0], sizes  # on at rest, brighter while Jarvis speaks
    assert abs(sizes["speaking"][1] - sizes["idle"][1]) < 0.05, sizes  # v0.6.1: brighter, never bigger


def test_the_glow_is_light_that_fades_far_and_only_its_opacity_follows_the_voice(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("now", theme="night")
    got = page.evaluate("""async () => {
        const o = document.querySelector('jv-view-now jv-orb'), glow = o.querySelector('.jv-orb__L--glow'), lvl = glow.querySelector('.jv-orb__lvl');
        const R = o.querySelector('.jv-orb__core').getBoundingClientRect().width / 2, bloom = glow.querySelector('.jv-orb__en-bloom').getBoundingClientRect().width / 2;
        const seen = new Set();
        for (const level of [0, 1, 0.5, 1, 0]) { o.orb = { state: 'speaking', level }; await new Promise((r) => setTimeout(r, 220)); seen.add(lvl.style.opacity); }
        return { reach: bloom / R, opacities: [...seen].map(Number), transform: lvl.style.transform, halo: getComputedStyle(o.querySelector('.jv-orb__L--halo')).opacity,
                 stops: [...glow.querySelectorAll('stop')].map((s) => Number(s.getAttribute('stop-opacity'))) }; }""")
    # v0.5.2 (his reference): light, not a ring. It reaches far (about 4.6 R) and fades smoothly to nothing there,
    # its peak stays dim, and it never steps up by much from one stop to the next going outward (no edge)
    stops = got["stops"]
    # v0.5.6: a hidden light at the centre (the peak is behind the core), always on, small at rest and grown
    # (scaled ×1.4, one static layer) while Jarvis speaks: it reaches about 6.4 R then, smooth to nothing
    assert 3.5 <= got["reach"] <= 7, got  # between rest (×0.85) and grown (×1.4), whichever it has reached
    assert stops[-1] == 0 and max(stops) <= 1, stops
    peak = stops.index(max(stops))
    assert all(a >= b for a, b in zip(stops[peak:], stops[peak + 1:], strict=False)), stops  # only ever fades outward
    assert len(got["opacities"]) >= 2 and max(got["opacities"]) <= 1 and min(got["opacities"]) >= 0.3 and got["transform"] == ""  # v0.11.2: 0.3-1, so the voice reads
    assert got["halo"] == "0"  # no wide haze out to the dotted ring while he or Jarvis speaks


def test_the_day_dial_is_off_by_default_and_mounts_at_two_and_a_half_r_when_asked(hub):
    page = hub.scene("orb-idle", theme="night")
    got = page.evaluate("""async () => { const o = document.querySelector('.jv-orb-scene jv-orb');
        const dial = document.createElement('div'); dial.id = 'dial'; dial.setAttribute('slot', 'dial'); o.append(dial);
        await new Promise((r) => setTimeout(r));
        const inSlot = dial.parentElement === o.dialSlot, hidden = getComputedStyle(o.dialSlot).display === 'none';
        o.setAttribute('dial', ''); await new Promise((r) => setTimeout(r));
        const s = o.dialSlot.getBoundingClientRect(), b = o.getBoundingClientRect();
        o.setAttribute('state', 'thinking'); await new Promise((r) => setTimeout(r));
        return { inSlot, hidden, still: dial.parentElement === o.dialSlot, ratio: s.width / b.width }; }""")
    assert got["inSlot"] and got["hidden"]  # HUD v3: nothing is drawn round the orb unless the host asks
    assert got["still"] and abs(got["ratio"] - 180 / 220) < 0.01  # with `dial`: the 2.5 R ring is the slot's inscribed circle
    page = hub.scene("orb-dial", theme="night")
    assert page.is_visible(".jv-orb-scene jv-orb[dial] jv-day-dial")
    assert page.locator(".jv-orb-scene .jv-orb__readout").count() == 0  # the ticks are bare
    assert hub.problems == []


def test_the_docked_orb_can_bring_back_the_full_view(hub):
    page = hub.scene("orb-idle", theme="night")
    make_orb(page, state="idle", size="corner", openable="")
    page.evaluate("window.__open = 0; document.addEventListener('jv-orb-open', () => window.__open++)")
    page.focus("#__t .jv-orb__open")
    page.keyboard.press("Enter")
    assert page.evaluate("window.__open") == 1
    assert page.get_attribute("#__t .jv-orb__open", "aria-label") == "Show the full view"


def test_earcons_follow_the_rules_and_start_fast(hub):
    page = hub.scene("orb-idle", theme="night")
    rules = page.evaluate("""import('/sounds/earcons.js').then((m) => ({
        minimal: m.NAMES.filter((n) => m.shouldPlay(n, { level: 'minimal' })),
        full: m.NAMES.filter((n) => m.shouldPlay(n, { level: 'full' })),
        off: m.NAMES.filter((n) => m.shouldPlay(n, { level: 'off' })),
        quiet: m.shouldPlay('tick', { level: 'full', quiet: true }), game: m.shouldPlay('wake', { level: 'full', game: true }),
        strip: m.shouldPlay('tick', { level: 'full', strip: true }), default: m.earconLevel(),
        night: m.inQuietHours({ on: true, from: '22:30', to: '07:30' }, new Date(2026, 10, 16, 23, 5)),
        early: m.inQuietHours({ on: true, from: '22:30', to: '07:30' }, new Date(2026, 10, 16, 6, 0)),
        noon: m.inQuietHours({ on: true, from: '22:30', to: '07:30' }, new Date(2026, 10, 16, 12, 0)),
        off_hours: m.inQuietHours({ on: false, from: '22:30', to: '07:30' }, new Date(2026, 10, 16, 23, 5)),
        gameState: m.inGame({ now_card: { moment: 'game' } }) && m.inGame({ settings: { game_mode: 'on' } }) && !m.inGame({ settings: { game_mode: 'auto' } }),
        pushed: m.NAMES.filter((n) => m.shouldPlay(n, { level: 'full', pushed: true })),
        woke: m.NAMES.filter((n) => m.shouldPlay(n, { level: 'full', wokeToday: true })),
        day: m.dayKey(new Date(2026, 10, 16, 23, 59)) === m.dayKey(new Date(2026, 10, 16, 0, 1)) && m.dayKey(new Date(2026, 10, 17, 0, 1)) !== m.dayKey(new Date(2026, 10, 16, 23, 59)),
    }))""")
    assert rules == {"minimal": ["wake", "tick"], "full": ["wake", "tick", "critical"], "off": [], "quiet": False, "game": False,
                     "strip": False, "default": "minimal", "night": True, "early": True, "noon": False, "off_hours": False, "gameState": True,
                     "pushed": ["tick"], "woke": ["tick", "critical"], "day": True}
    took = page.evaluate("""import('/sounds/earcons.js').then(async (m) => { const ready = await m.preload();
        const runs = ['tick', 'wake', 'critical'].map((n) => m.play(n, { force: true }));
        return { ready, played: runs.every((r) => r.played), ms: Math.max(...runs.map((r) => r.ms)) }; })""")
    print("earcon start (ms):", took["ms"])
    assert took["ready"] and took["played"] and took["ms"] < 10
    assert hub.problems == []


# ---- F1 (his v0.4.1 report): windows open in silence, and one window sounds ------------------------------------
SOUNDS = """window.__sounds = [];
    const start = AudioBufferSourceNode.prototype.start;
    AudioBufferSourceNode.prototype.start = function (...a) { window.__sounds.push(Math.round(this.buffer.duration * 1000)); return start.apply(this, a); };"""
PUSHES = [{"id": f"w-f1-{i}", "type": "notice", "title": f"Note {i}", "data": {"text": "Room changed"}, "pushed": "2026-11-16T15:42:00"} for i in range(3)]


def apply(page, kind, data):
    page.evaluate("([type, data]) => window.__jarvis.store.apply({v: 2, type, ts: '2026-11-16T15:42:00', data})", [kind, data])
    page.wait_for_timeout(40)


def ready_to_sound(page, level="full"):
    page.evaluate(f"import('/sounds/earcons.js').then(async (m) => {{ m.setEarconLevel('{level}'); await m.preload(); }})")
    page.wait_for_function("import('/sounds/earcons.js').then((m) => m.soundOwner())", timeout=3_000)


def test_pushing_windows_plays_no_sound(hub):
    hub.page.add_init_script(SOUNDS)
    page = hub.scene("stage-active", theme="night", window="stage")
    ready_to_sound(page)  # Full: the most that may ever sound
    for w in PUSHES:
        apply(page, "window.push", w)
    # the server's Rail follows the push; even a thing on it turning critical makes no sound as windows land
    apply(page, "rail.updated", {"slots": {**hub.state("s => s.rail.slots"), "messages": {"items": [
        {"ref": "w-f1-0", "slot": "messages", "kind": "notice", "title": "Note 0", "at": "2026-11-16T15:42:00", "state": "critical"}], "worst": "critical"}}})
    page.wait_for_timeout(300)
    assert page.locator(".jv-stage__canvas > jv-window[window-id^=w-f1]").count() >= 1
    assert page.evaluate("window.__sounds") == []
    assert hub.problems == []


def test_only_the_heard_you_tick_and_the_first_wake_of_the_day_sound_and_only_once(hub):
    hub.page.add_init_script(SOUNDS)
    home = hub.scene("now", theme="night")
    stage = hub.page.context.new_page()
    stage.add_init_script(SOUNDS)
    stage.goto(f"{hub.base}/?scene=stage-active&theme=night&window=stage")
    stage.wait_for_selector("html[data-ready]")
    for page in (home, stage):
        page.evaluate("import('/sounds/earcons.js').then((m) => { m.setEarconLevel('minimal'); return m.preload(); })")
    stage.wait_for_function("import('/sounds/earcons.js').then((m) => m.soundOwner())", timeout=3_000)
    assert home.evaluate("import('/sounds/earcons.js').then((m) => m.soundOwner())") is False  # the Stage sounds, not both

    def ask(last_wake):  # "Jarvis, show me…": the wake, the think, the windows, the answer
        for page in (home, stage):
            apply(page, "orb.state", {"state": "idle"})
            apply(page, "orb.state", {"state": "listening", "level": 0.7, "last_wake": last_wake})
            apply(page, "orb.state", {"state": "thinking"})
            for w in PUSHES:
                apply(page, "window.push", w)
            apply(page, "orb.state", {"state": "speaking", "level": 0.6})
        stage.wait_for_timeout(250)

    ask(None)  # the first wake of the day: the soft rise, then the tick
    assert stage.evaluate("window.__sounds") == [520, 55] and home.evaluate("window.__sounds") == []
    stage.wait_for_timeout(2600)  # v0.14.0: one tick per thought, so the next ask comes a moment later
    ask(None)  # another full wake the same day (a reload, or ≥ 4 h away): the beat still plays, the rise doesn't
    assert stage.evaluate("window.__sounds") == [520, 55, 55] and home.evaluate("window.__sounds") == []
    stage.close()  # the Stage goes away: the hub sounds again
    home.wait_for_function("import('/sounds/earcons.js').then((m) => m.soundOwner())", timeout=3_000)
    assert hub.problems == []


# ---- HUD v3 (§14): white rings, blue only while he or Jarvis speaks, smaller, standby sphere + small clock ----

LOOK = """(sel) => { const o = document.querySelector(sel), q = (s) => o.querySelector(s), cs = (s) => getComputedStyle(q(s));
    const css = (n) => { const p = document.createElement('i'); p.style.color = getComputedStyle(o).getPropertyValue(n); o.append(p);
        const c = getComputedStyle(p).color; p.remove(); return c; };
    return { energy: +cs('.jv-orb__L--energy').opacity, ring: cs('.jv-orb__en-ring').stroke, halo: +cs('.jv-orb__L--halo').opacity,
             core: cs('.jv-orb__core').stroke, arc: cs('.jv-orb__arc--hi').stroke, dots: cs('.jv-orb__dots').stroke,
             orb: css('--orb-band'), line: css('--orb-line'), w: o.getBoundingClientRect().width }; }"""


def look(page, sel):
    return page.evaluate(LOOK, sel)


def test_rings_are_white_and_the_blue_ring_shows_only_while_listening_or_speaking(hub):
    for theme in ("night", "day"):
        seen = {}
        for state in ("idle", "thinking", "listening", "speaking"):
            page = hub.scene(f"orb-{state}", theme=theme)
            seen[state] = got = look(page, ".jv-orb-scene jv-orb")
            assert got["core"] == got["line"] and got["arc"] == got["line"] and got["dots"] == got["line"], (theme, state)
        for state in ("idle", "thinking"):  # white rings, a faint halo, no energy ring (reduced motion: thinking adds a dashed white one)
            assert seen[state]["halo"] <= 0.65 and (seen[state]["energy"] == 0 or seen[state]["ring"] == seen[state]["line"]), (theme, state)
        for state in ("listening", "speaking"):  # the deep blue fills the energy ring
            assert seen[state]["energy"] > 0.5 and seen[state]["ring"] == seen[state]["orb"], (theme, state)
    assert seen["idle"]["orb"] != seen["idle"]["line"]
    assert hub.problems == []


def test_the_default_size_puts_the_ornaments_at_a_sixth_of_the_screen_and_the_host_can_set_it(hub):
    hub.page.set_viewport_size({"width": 1920, "height": 1080})
    page = hub.scene("orb-idle", theme="night")
    got = page.evaluate("""() => { const o = document.querySelector('.jv-orb-scene jv-orb'), r = (s) => o.querySelector(s).getBoundingClientRect();
        return { box: o.getBoundingClientRect().width, hash: r('.jv-orb__L--hash').width, core: r('.jv-orb__L--core').width, vw: innerWidth }; }""")
    ornaments = got["hash"] * 84 / 88   # the hash marks' outer reach (84 units) in their 88-unit layer
    core_r = got["core"] / 2 * 36 / 41  # the core's radius (36 units) in its 41-unit layer
    assert 1 / 7 < ornaments / got["vw"] < 1 / 5, got
    assert 1 / 32 < core_r / got["vw"] < 1 / 20, got
    page.evaluate("document.querySelector('.jv-orb-scene').style.setProperty('--jv-orb-size', '260px')")
    assert page.evaluate("document.querySelector('.jv-orb-scene jv-orb').getBoundingClientRect().width") == 260
    # the docked mini sizes stay: 120 px on the big screen, 64 px on a laptop
    make_orb(page, size="corner")
    assert page.evaluate("document.querySelector('#__t').getBoundingClientRect().width") == 120
    page = hub.scene("orb-idle", theme="night", size="laptop")
    make_orb(page, size="corner")
    assert page.evaluate("document.querySelector('#__t').getBoundingClientRect().width") == 64


def test_docked_orbs_are_white_rings_only(hub):
    page = hub.scene("orb-idle", theme="night")
    for state in ("idle", "listening", "speaking", "thinking"):
        make_orb(page, state=state, size="corner")
        got = look(page, "#__t")
        assert got["halo"] == 0 and got["ring"] == got["line"], state  # never the blue, even while he speaks
    make_orb(page, state="waiting", size="corner")
    got = page.evaluate("[getComputedStyle(document.querySelector('#__t .jv-orb__en-ring')).stroke, getComputedStyle(document.body).getPropertyValue('--warn')]")
    assert got[0] != look(page, "#__t")["line"]  # amber, red and grey states keep their colours
    page = hub.scene("orb-docked-listening", theme="night")
    page.wait_for_function("document.querySelector('.jv-orb-scene jv-orb').dataset.dock === 'docked'", timeout=3000)
    got = look(page, ".jv-orb-scene jv-orb")
    assert got["halo"] == 0 and got["ring"] == got["line"]
    assert hub.problems == []


def test_standby_is_the_sphere_with_the_wordmark_and_never_a_big_clock(hub):
    page = hub.scene("orb-standby", theme="night")
    got = page.evaluate("""() => { const o = document.querySelector('.jv-orb-scene jv-orb'), op = (s) => +getComputedStyle(o.querySelector(s)).opacity;
        return { sphere: op('.jv-orb__L--sphere'), mark: op('.jv-orb__mark') * op('.jv-orb__L--core'), ring: op('.jv-orb__core'),
                 arcs: op('.jv-orb__L--arcs-b'), clocks: o.querySelectorAll('jv-clock, .jv-clock').length,
                 sphereW: o.querySelector('.jv-orb__L--sphere').getBoundingClientRect().width, hashW: o.querySelector('.jv-orb__L--hash').getBoundingClientRect().width }; }""")
    assert got["sphere"] == 1 and got["mark"] == 1 and got["ring"] == 0 and got["arcs"] == 0 and got["clocks"] == 0
    assert 0.75 < got["sphereW"] / got["hashW"] < 1.05  # about as wide as the awake orb's hash ring (hashW: the layer at its 0.86 standby scale)
    # the small clock the host puts under it: small mono digits and a tiny tracked date
    clock = page.evaluate("""() => { const c = document.querySelector('.jv-orb-scene jv-clock[small]'), t = getComputedStyle(c.querySelector('.jv-clock__time')),
        d = getComputedStyle(c.querySelector('.jv-clock__date'));
        return { small: c.querySelector('.jv-clock--small') !== null, size: parseFloat(t.fontSize), mono: t.fontFamily.includes('JetBrains Mono'),
                 date: parseFloat(d.fontSize), caps: d.textTransform, track: parseFloat(d.letterSpacing), next: c.querySelector('.jv-clock__next') === null }; }""")
    assert clock["small"] and clock["mono"] and clock["next"] and clock["caps"] == "uppercase" and clock["date"] == 12 and clock["track"] > 2
    assert 36 <= clock["size"] <= 64
    page.evaluate("document.querySelector('.jv-orb-scene jv-clock').style.setProperty('--jv-clock-size', '40px')")
    assert page.evaluate("parseFloat(getComputedStyle(document.querySelector('.jv-orb-scene .jv-clock__time')).fontSize)") == 40
    assert hub.problems == []


def test_voice_level_ticks_move_the_glow_and_leave_the_caption_alone(hub):
    """His clip (v0.11.1): Jarvis's caption flickered while he spoke, because every level tick re-rendered it."""
    page = hub.scene("now", theme="night")
    got = page.evaluate("""async () => {
      const s = window.__jarvis.store, ev = (data) => s.apply({ v: 2, type: 'orb.state', ts: '2026-11-16T15:42:00', data });
      ev({ state: 'speaking' });
      s.apply({ v: 2, type: 'caption.show', ts: '2026-11-16T15:42:00', data: { text: 'Yes, sir.', ttl_ms: 60000 } });
      await new Promise((r) => setTimeout(r, 100));
      const line = document.querySelector('#caption .jv-caption');
      const glow = document.querySelector('jv-orb .jv-orb__L--glow .jv-orb__lvl');
      const seen = new Set();
      for (const level of [0, 1, 0, 1, 0.5, 1, 0]) { ev({ state: 'speaking', level }); await new Promise((r) => setTimeout(r, 120)); seen.add(glow?.style.opacity); }
      return { same: !!line && document.querySelector('#caption .jv-caption') === line, glows: seen.size };
    }""")
    assert got["same"], got        # the caption's line is the very same element: nothing re-drew it
    assert got["glows"] >= 3, got  # the glow followed the level


def test_always_motion_keeps_the_orb_moving_when_windows_asks_for_less(hub):
    """v0.12.3: with Windows' animations off (this harness emulates prefers-reduced-motion: reduce), "Full" goes
    still as before, but Controls › Motion › Always keeps the orb's transitions and spin."""
    page = hub.scene("orb-idle", theme="night")
    look = """() => { const r = document.documentElement, o = document.querySelector('.jv-orb-scene jv-orb');
      const layer = o.querySelector('.jv-orb__L--arcs-a');
      return { still: r.hasAttribute('data-still'), motion: r.dataset.motion || '',
               fade: getComputedStyle(layer).transitionDuration }; }"""
    before = page.evaluate(look)
    assert before["still"] and before["fade"].startswith("0s"), before
    page.evaluate("""() => { const s = window.__jarvis.store; s.set({ settings: { ...s.state.settings, motion: 'always' } }); }""")
    frames(page)
    after = page.evaluate(look)
    assert not after["still"] and after["motion"] == "full" and not after["fade"].startswith("0s"), after


def test_at_rest_the_light_follows_the_room_and_a_meter_tick_never_changes_the_state(hub):
    """v0.14.0 (his ask): the light gets brighter and dimmer with the sound around us, also when nobody is talking;
    a meter tick only ever moves the light."""
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-idle", theme="night", motion="full")
    make_orb(page, state="idle")
    got = page.evaluate("""async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const orb = document.querySelector('#__t'), glow = orb.querySelector('.jv-orb__L--glow .jv-orb__lvl');
      await wait(150);
      const steady = glow.style.opacity;                 // no meter yet: the full, steady resting light
      const seen = [];
      for (const level of [0, 1, 0, 0.6]) { orb.level = level; await wait(1100); seen.push(parseFloat(glow.style.opacity)); }
      return { steady, seen, look: orb.dataset.look };
    }""")
    assert got["look"] == "idle" and (got["steady"] == "" or float(got["steady"]) > 0.95), got
    quiet, loud, quiet2, mid = got["seen"]
    assert quiet < 0.5 and loud > 0.95 and quiet2 < 0.5 and quiet < mid < loud, got   # dim, bright, dim, in between
    # through the store: a tick for the state on screen moves the light; a tick for another state does nothing
    page = hub.scene("now", theme="night", motion="full")
    out = page.evaluate("""async () => {
      const s = window.__jarvis.store, ev = (data) => s.apply({ v: 2, type: 'orb.state', ts: '2026-11-18T23:42:00', data });
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const orb = document.querySelector('jv-orb');
      ev({ state: 'idle' }); await wait(80);
      ev({ state: 'idle', level: 0.9 }); await wait(80);
      return { level: orb.level, state: s.state.orb.state, look: orb.dataset.look };
    }""")
    assert out["state"] == "idle" and out["level"] == 0.9, out


def test_the_resting_sphere_breathes_with_the_room_too(hub):
    hub.page.emulate_media(reduced_motion="no-preference")
    page = hub.scene("orb-idle", theme="night", motion="full")
    make_orb(page, state="standby")
    got = page.evaluate("""async () => {
      const o = document.querySelector('#__t'), halo = o.querySelector('.jv-orb__L--halo');
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const out = [];
      for (const level of [0, 1, 0]) { o.level = level; await wait(1300); out.push(parseFloat(halo.style.opacity)); }
      o.setAttribute('state', 'listening'); await wait(150);
      return { out, after: halo.style.opacity };
    }""")
    quiet, loud, quiet2 = got["out"]
    assert quiet < 0.2 and loud > 0.55 and quiet2 < 0.2, got
    assert got["after"] == "", got                         # leaving the sphere gives the halo back to the stylesheet


def test_heard_you_ticks_once_for_a_thought_said_in_two_parts(hub):
    hub.page.add_init_script(SOUNDS)
    page = hub.scene("orb-idle", theme="night")
    ready_to_sound(page, "minimal")
    make_orb(page, state="idle")
    page.evaluate("""async () => {
      const o = document.querySelector('#__t'), wait = (ms) => new Promise((r) => setTimeout(r, ms));
      for (const s of ['listening', 'thinking', 'listening', 'thinking']) { o.setAttribute('state', s); await wait(80); }
    }""")
    page.wait_for_timeout(200)
    assert page.evaluate("window.__sounds") == [55]         # one "heard you", not two 160 ms apart
