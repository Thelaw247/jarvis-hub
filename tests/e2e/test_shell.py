"""Shell smoke tests: the hub opens in demo mode, events arrive, tabs and Back work, scenes load cleanly."""
import pytest

SIZES = {"full": (1920, 1080), "laptop": (1280, 720), "phone": (390, 844), "strip": (360, 96), "ambient": (1920, 1080)}


def test_demo_mode_opens_and_events_reach_the_screen(hub):
    page = hub.open()
    assert hub.state("s => s.mode") == "demo"
    page.evaluate("fetch('/api/demo/play', {method: 'POST'})")
    page.wait_for_function("window.__jarvis.store.state.approvals.some(a => a.status === 'pending') && window.__jarvis.store.state.windows.length >= 3")
    assert hub.state("s => s.ui.log.length") > 5
    assert hub.problems == []


def test_router_paths_back_stack_and_deep_links(hub):
    page = hub.scene("shell")
    go = lambda path: page.evaluate(f"window.__jarvis.router.go('{path}')")
    current = lambda: page.evaluate("window.__jarvis.router.current.path")
    go("/life/ge-122")
    assert current() == "/life/ge-122" and page.evaluate("location.hash") == "#/life/ge-122"
    assert page.evaluate("window.__jarvis.router.current.tab") == "life"
    go("/activity")
    assert page.evaluate("window.__jarvis.router.back()") is True and current() == "/life/ge-122"
    page.evaluate("window.__jarvis.router.back()")
    page.evaluate("window.__jarvis.router.back()")
    assert current() == "/now"
    go("/nonsense")
    assert current() == "/now"
    assert hub.problems == []


def test_scene_mode_is_frozen_and_answers_actions_locally(hub):
    page = hub.scene("shell")
    assert hub.state("s => s.mode") == "scene"
    first = page.evaluate("window.__jarvis.store.now().toISOString()")
    page.wait_for_timeout(50)
    assert page.evaluate("window.__jarvis.store.now().toISOString()") == first
    assert page.evaluate("window.__jarvis.bridge.act('approve', 'ap-week').then(r => r.ok)") is True
    assert hub.state("s => [s.approvals[0].status, s.actions[0].what, s.actions[0].undo.label]") == ["approved", "Book this week's study plan", "24 h"]
    # receipt times are local (like the hub's), not UTC: the scene clock is frozen at the fixture's local time
    assert hub.state("s => [s.actions[0].ts, s.actions[0].undo.until]") == ["2026-11-16T15:40:00", "2026-11-17T15:40:00"]
    assert hub.state("s => s.now_card.ready_to_offer.some(o => o.id === 'o-week')") is False  # done, so no longer offered
    count = hub.state("s => s.actions.length")
    assert page.evaluate("window.__jarvis.bridge.act('approve', 'ap-week').then(r => r.ok)") is True  # same answer twice: once
    assert hub.state("s => s.actions.length") == count
    assert page.evaluate("window.__jarvis.bridge.act('decline', 'ap-week').then(r => r.ok)") is False  # a different answer
    receipt = hub.state("s => s.actions[0].id")
    assert page.evaluate(f"window.__jarvis.bridge.act('undo', '{receipt}').then(r => r.ok)") is True
    assert page.evaluate(f"window.__jarvis.bridge.act('undo', '{receipt}').then(r => r.ok)") is True  # already undone
    assert hub.problems == []


def test_scene_mode_mirrors_the_hub_rules_for_no_change_expiry_and_bigger(hub):
    page = hub.scene("shell")
    act = lambda call: page.evaluate(f"window.__jarvis.bridge.{call}")  # noqa: E731
    assert act("act('decline', 'ap-week').then(r => r.ok)") is True
    assert hub.state("s => { const a = s.actions.find(x => x.id === 'declined-ap-week'); return [a.why, a.undo]; }") == ["You said no. Nothing was changed.", None]
    page = hub.scene("shell")
    act("act('change', 'ap-week', {text: 'Not before 10 am'})")
    assert hub.state("s => [s.approvals[0].status, s.toasts.at(-1).text]") == ["changed", "It comes back with that change, for your yes."]
    page = hub.scene("shell")
    page.evaluate("window.__jarvis.store.state.approvals[0].expires = '2026-11-16T15:00:00'")
    assert act("act('approve', 'ap-week')") == {"ok": False, "message": "This offer ran out. Nothing was done."}
    assert hub.state("s => s.approvals[0].status") == "expired"
    page.evaluate("window.__jarvis.store.apply({v: 1, type: 'window.push', ts: '', data: {id: 'w-tall', type: 'notice', title: 'Tall', size: '1x2'}})")
    act("act('resize', 'w-tall')")
    assert hub.state("s => s.windows.find(w => w.id === 'w-tall').size") == "2x2"
    assert hub.problems == []


def _scene_names(hub):
    hub.scene("shell")
    return hub.page.evaluate("window.__jarvis.scenes()")


def test_every_scene_loads_in_both_themes_without_problems(hub):
    names = _scene_names(hub)
    assert "shell" in names
    failures = []
    for name in names:
        for theme in ("night", "day"):
            hub.problems.clear()
            page = hub.scene(name, theme)
            text = page.inner_text("#stage").strip()
            if hub.problems or not text:
                failures.append((name, theme, hub.problems[:3] or "nothing drawn"))
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            if overflow:
                failures.append((name, theme, "page is wider than the window"))
    assert failures == []


@pytest.mark.parametrize("size", ["laptop", "phone"])
def test_shell_fits_smaller_sizes(hub, size):
    hub.page.set_viewport_size(dict(zip(("width", "height"), SIZES[size], strict=True)))
    page = hub.scene("shell", size=size)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert hub.problems == []


# ---- contracts v2 (N0): the store's new reducers and the bottom band --------------------------------------------
APPLY = "(type, data) => window.__jarvis.store.apply({v: 2, type, ts: '2026-11-16T15:41:00', data})"


def test_the_store_docks_orders_and_never_deletes(hub):
    page = hub.scene("shell")
    out = page.evaluate(f"""() => {{
        const s = window.__jarvis.store, send = {APPLY};
        const note = (i, more = {{}}) => ({{id: `w-${{i}}`, type: 'notice', title: `Note ${{i}}`, ref: `thing-${{i}}`, ...more}});
        send('rail.updated', {{slots: Object.fromEntries(Object.keys(s.state.rail.slots).map((k) => [k, {{items: []}}]))}});  // start bare (N7's demo day has a realistic Rail)
        send('window.close', {{all: true}});
        for (let i = 0; i < 6; i++) send('window.push', note(i, i === 0 ? {{pinned: true}} : {{}}));
        const afterSixth = [s.state.windows.map((w) => w.id), s.slot('jarvis').map((i) => i.ref)];
        send('window.order', {{ids: ['w-5', 'w-0']}});
        const ordered = s.state.windows.map((w) => w.id);
        send('window.dock', {{id: 'w-5', slot: 'parked'}});
        send('window.push', {{id: 'w-chart', type: 'chart', title: 'Hours'}});
        send('window.dock', {{id: 'w-chart'}});
        send('window.close', {{all: true}});
        const cleared = [s.state.windows.length, s.slot('parked').map((i) => i.ref), s.slot('jarvis').map((i) => i.ref).sort(), s.railItem('w-5').window.docked];
        send('window.push', {{...s.railItem('thing-1').window, docked: false}});
        const recalled = [s.state.windows.map((w) => w.id), !!s.railItem('thing-1')];
        return {{afterSixth, ordered, cleared, recalled}};
    }}""")
    assert out["afterSixth"] == [["w-0", "w-2", "w-3", "w-4", "w-5"], ["thing-1"]]  # the sixth docks the oldest unpinned one
    assert out["ordered"] == ["w-5", "w-0", "w-2", "w-3", "w-4"]
    assert out["cleared"] == [0, ["thing-5"], ["thing-0", "thing-1", "thing-2", "thing-3", "thing-4"], True]  # the chart, a pure view, just closed
    assert out["recalled"] == [["w-1"], False]
    assert hub.problems == []


def test_the_store_keeps_the_rail_marks_threads_and_focus(hub):
    page = hub.scene("shell")
    out = page.evaluate(f"""async () => {{
        const s = window.__jarvis.store, send = {APPLY};
        const seen = new Set(); s.subscribe((_, keys) => keys.forEach((k) => seen.add(k)));
        const rail = await (await fetch('/contracts/examples/rail.json')).json();
        const thread = await (await fetch('/contracts/examples/thread.json')).json();
        send('rail.updated', rail);
        send('marks.updated', {{marks: {{'due-pps7': {{what: 'Due moved Wed 8 pm → Thu 11:59 pm', at: '2026-11-16T15:12:00'}}}}}});
        send('thread.updated', {{thread}});
        send('thread.updated', {{thread: {{...thread, resume: {{...thread.resume, source: 'confirmed'}}}}}});
        send('ui.focus', {{ref: 'due-pps7', until: '2026-11-16T15:40:44'}});
        const focused = [s.focused('due-pps7'), s.focused('w-other')];
        send('ui.focus', {{ref: 'due-pps7', until: '2026-11-16T15:39:00'}});
        const lapsed = s.focused('due-pps7');
        send('ui.focus', {{ref: null}});
        send('window.push', {{id: 'w-ap-week', type: 'approval', title: 'Waiting for your yes', ref: 'ap-week'}});
        send('approval.resolved', {{id: 'ap-week', status: 'expired'}});
        const expired = [s.state.windows.some((w) => w.id === 'w-ap-week'), s.railItem('ap-week').slot, s.railItem('ap-week').window.id];
        send('approval.resolved', {{id: 'ap-week', status: 'approved'}});
        await Promise.resolve();
        return {{slots: Object.keys(s.state.rail.slots), said: s.state.rail.slots.jarvis.said.length, mark: s.mark('due-pps7').what, none: s.mark('nothing'),
                 threads: s.state.threads.filter((t) => t.id === 'th-pps7').length, source: s.thread('th-pps7').resume.source, focused, lapsed, focus: s.state.focus, expired,
                 answered: !!s.railItem('ap-week'), v: s.state.v, keys: ['rail', 'marks', 'threads', 'focus', 'windows'].filter((k) => seen.has(k))}};
    }}""")
    assert out["slots"] == ["yes", "today", "homework", "messages", "jarvis", "parked"] and out["said"] == 1
    assert out["mark"] == "Due moved Wed 8 pm → Thu 11:59 pm" and out["none"] is None
    assert (out["threads"], out["source"]) == (1, "confirmed")
    assert out["focused"] == [True, False] and out["lapsed"] is False and out["focus"] is None  # the scene clock is 15:40:00
    assert out["expired"] == [False, "yes", "w-ap-week"] and out["answered"] is False
    assert out["v"] == 2 and out["keys"] == ["rail", "marks", "threads", "focus", "windows"]
    assert hub.problems == []


def test_the_bottom_band_has_the_status_line_the_rail_the_caption_and_the_orb(hub):
    page = hub.scene("now-active")
    box = page.evaluate("""() => Object.fromEntries(['foot', 'status', 'rail', 'caption', 'orb', 'stage', 'ambient'].map((id) => {
        const r = document.getElementById(id).getBoundingClientRect(); return [id, {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}]; }))""")
    assert box["rail"]["h"] == 48 and abs((box["rail"]["l"] + box["rail"]["r"]) / 2 - 720) <= 1  # 48 px, in the true centre
    assert box["foot"]["t"] <= box["rail"]["t"] and box["rail"]["b"] <= box["foot"]["b"] and box["foot"]["b"] == 900
    assert box["status"]["l"] < box["status"]["r"] <= box["rail"]["l"] <= box["rail"]["r"] < box["orb"]["l"]  # status left · Rail centre · orb right
    assert box["caption"]["h"] > 0 and box["caption"]["b"] <= box["rail"]["t"]  # the caption floats above the Rail
    assert abs((box["caption"]["l"] + box["caption"]["r"]) / 2 - 720) <= 1
    assert box["stage"]["b"] <= box["foot"]["t"] and box["ambient"]["w"] == 0  # the ambient region shows only on the ambient screen
    for path in ("/today", "/life", "/activity", "/controls"):  # the band, and so the Rail, is on every tab
        page.evaluate(f"window.__jarvis.router.go('{path}')")
        assert page.evaluate("document.getElementById('rail').getBoundingClientRect().height") == 48
    page = hub.scene("now-ambient")
    assert page.evaluate("(() => { const r = document.getElementById('ambient').getBoundingClientRect(); return [r.width, r.height]; })()") == [1440, 900]
    assert page.evaluate("getComputedStyle(document.getElementById('ambient')).pointerEvents") == "none"
    assert page.evaluate("document.getElementById('rail').getBoundingClientRect().height") == 48  # the Rail's place stays on the ambient screen
    assert hub.problems == []
