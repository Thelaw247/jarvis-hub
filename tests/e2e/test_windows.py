"""The window manager's rules (ui/core/windows.js, windows-core.js), run in the browser as plain functions.
Nothing gets away (HUD v2 §6.2): the 6th window, the 60 s lifetime and "close that" dock; they never delete."""
import json


def run(hub, body):
    hub.scene("shell")
    return hub.page.evaluate(f"import('/core/windows.js').then(m => {{ {body} }})")


def test_layout_fills_from_the_top_left_on_twelve_columns(hub):
    spots = run(hub, """return m.layout([{id:'a',size:'1x1'},{id:'b',size:'1x1'},{id:'c',size:'2x2'},{id:'d',size:'2x1'},{id:'e',size:'4x2'}]);""")
    assert spots[0] == {"id": "a", "col": 1, "row": 1, "w": 3, "h": 1}
    assert spots[1]["col"] == 4 and spots[2] == {"id": "c", "col": 7, "row": 1, "w": 6, "h": 2}
    assert spots[3] == {"id": "d", "col": 1, "row": 2, "w": 6, "h": 1}
    assert spots[4]["row"] == 3 and spots[4]["w"] == 12
    cells = set()
    for s in spots:  # nothing overlaps
        for r in range(s["row"], s["row"] + s["h"]):
            for c in range(s["col"], s["col"] + s["w"]):
                assert (r, c) not in cells
                cells.add((r, c))


def test_at_most_six_counting_the_now_card_and_pinned_windows_stay(hub):
    ids = run(hub, """let w = [{id:'p', pinned:true}]; for (let i = 1; i <= 8; i++) w = m.placeWindow(w, {id:'w'+i}); return w.map(x => x.id);""")
    assert len(ids) == 5 and ids[0] == "p" and ids[-1] == "w8" and "w1" not in ids


def test_a_sixth_window_docks_the_oldest_unpinned_one_and_never_drops_it(hub):
    out = run(hub, """return import('/core/windows-core.js').then(c => {
        const docked = []; let w = [{id:'p', pinned:true}];
        for (let i = 1; i <= 7; i++) w = c.placeWindow(w, {id:'w'+i}, (x) => docked.push(x));
        const again = c.placeAndDock(w, {id:'w4', title:'same id: updated in place'});
        return [w.map(x => x.id), docked.map(x => [x.id, x.docked]), again.docked.length, again.windows.find(x => x.id === 'w4').title]; });""")
    assert out[0] == ["p", "w4", "w5", "w6", "w7"]
    assert out[1] == [["w1", True], ["w2", True], ["w3", True]]  # every one that left the screen went to the Rail
    assert out[2] == 0 and out[3] == "same id: updated in place"
    hub.scene("now-awake")  # and the store folds them into their slots
    docked = hub.page.evaluate("""(() => { const {store} = window.__jarvis;
        for (let i = 1; i <= 6; i++) store.apply({v: 2, type: 'window.push', ts: '2026-11-16T15:41:00', data: {id: 'w-' + i, type: 'notice', title: 'Note ' + i, ref: 'note-' + i}});
        return [store.state.windows.length, store.slot('jarvis').filter(i => i.window).map(i => [i.ref, i.window.id, i.window.docked])]; })()""")
    assert docked == [5, [["note-1", "w-1", True]]]


def test_windows_leave_after_sixty_seconds_unless_pinned_or_used(hub):
    gone = run(hub, """const used = new Map([['b', 50000]]), pushed = new Map([['a', 0], ['b', 0], ['c', 0]]);
        return m.expired([{id:'a'}, {id:'b'}, {id:'c', pinned:true}], 61000, used, pushed);""")
    assert gone == ["a"]
    docked = run(hub, """let t = 0; const out = []; const clock = new m.WindowClock(id => out.push(id), () => t);
        const w = [{id:'a'}, {id:'b'}]; clock.tick(w); t = 30000; clock.touch('b'); t = 61000; clock.tick(w); return out;""")
    assert docked == ["a"]


def test_the_sixty_second_lifetime_docks_with_reason_lifetime(hub):
    hub.scene("now-active")
    sent = hub.page.evaluate("""import('/core/presence.js').then(p => { const {bridge} = window.__jarvis, calls = [], act = bridge.act;
        bridge.act = (...a) => { calls.push(a); return act(...a); };
        p.windowClock.dock('w-due-pps7'); bridge.act = act; return calls; })""")
    assert sent == [["dock", "w-due-pps7", {"reason": "lifetime"}]]
    hub.page.wait_for_function("!window.__jarvis.store.state.windows.some(w => w.id === 'w-due-pps7')")
    item = hub.state("s => s.rail.slots.homework.items.find(i => i.ref === 'due-pps7')")
    assert item["window"]["id"] == "w-due-pps7" and item["window"]["docked"] is True  # on the Rail, whole


def test_private_items_never_reach_a_shared_screen(hub):
    shown = run(hub, """const w = [{id:'a'}, {id:'money', tier:2}];
        return [m.visible(w, {size:'full'}).length, m.visible(w, {size:'ambient'}).map(x => x.id), m.visible(w, {size:'ambient', presence:{others:true}}).length, m.visible(w, {size:'full', presence:{others:true}}).map(x => x.id)];""")
    assert shown == [2, ["a"], 0, ["a"]]


def test_voice_and_keyboard_commands_map_to_actions(hub):
    out = run(hub, """const w = [{id:'w1', title:'Due', size:'1x1', ref:'due-pps7'}, {id:'w2', title:'PPS 7', size:'2x2'}];
        return ['close that', 'Clear the screen.', 'keep that up', 'bigger', 'put the PPS 7 on the left', 'close due', 'what time is it',
                'clear view', 'Mark all seen.', 'archive due', 'done with that'].map(t => m.command(t, w));""")
    assert out[0] == {"action": "dock", "target": "w2", "args": {"reason": "closed"}}  # "close" docks: it waits on the Rail
    assert out[1] == {"action": "close_all", "target": "all"}
    assert out[2] == {"action": "pin", "target": "w2"}
    assert out[3] == {"action": "resize", "target": "w2", "args": {"size": "3x2"}}
    assert out[4] == {"action": "move", "target": "w2", "args": {"to": "left"}}
    assert out[5] == {"action": "dock", "target": "w1", "args": {"reason": "closed"}}
    assert out[6] is None
    assert out[7] == {"action": "close_all", "target": "all"} and out[8] == {"action": "seen", "target": "all"}
    assert out[9] == {"action": "archive", "target": "due-pps7"} and out[10] == {"action": "archive", "target": "w2"}  # only these remove


def test_layouts_are_saved_as_data_and_restored_pinned(hub):
    out = run(hub, """const store = {d: {}, getItem(k) { return this.d[k] ?? null; }, setItem(k, v) { this.d[k] = v; }};
        const n = m.saveLayout('praelecta', [{id:'a', type:'chart', title:'Costs', size:'2x1', pushed:'x'}, {id:'b', type:'fact', title:'Private', tier:2}], store);
        return [n, m.restoreLayout('praelecta', store), m.restoreLayout('nothing', store)];""")
    assert out[0] == 1 and out[2] == []
    assert json.dumps(out[1]) == json.dumps([{"id": "a", "type": "chart", "title": "Costs", "size": "2x1", "pinned": True}])


# ---- HUD v3 §14.2: the aligned cluster (core/windows.js cluster, panelWidth, tierOf, roleOf) -----------------
BOARD = """const area = {left: 20, top: 12, right: 1900, bottom: 960}, keepOut = [{left: 1760, top: 900, right: 1920, bottom: 1080}];
    const FOOT = 28, G = m.GUTTER;
    const hit = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
    const box = (s, foot = FOOT) => ({left: s.x, top: s.y, right: s.x + s.w, bottom: s.y + s.h + foot});
    const colsOf = (spots) => { const cols = new Map(); for (const s of spots) cols.set(s.col, [...(cols.get(s.col) || []), s]);
      return [...cols.entries()].sort((a, b) => a[0] - b[0]).map(([, c]) => c.sort((a, b) => a.y - b.y)); };
    const check = (spots, room = area, keep = keepOut) => {
      const cols = colsOf(spots), right = Math.min(room.right, ...keep.map((k) => k.left));
      const l = Math.min(...spots.map((s) => s.x)), r = Math.max(...spots.map((s) => s.x + s.w));
      const edges = cols.map((c) => [Math.min(...c.map((s) => s.x)), Math.max(...c.map((s) => s.x + s.w))]);
      return {
        inside: spots.every((s) => s.x >= room.left && s.y >= room.top && s.x + s.w <= room.right && s.y + s.h + FOOT <= room.bottom + 0.5),
        orb: spots.some((s) => keep.some((k) => hit(box(s), k))),
        leftOfOrb: spots.every((s) => s.x + s.w <= right),
        baseline: cols.every((c) => c[0].y === cols[0][0].y),                                    // the columns share one top edge
        stacked: cols.every((c) => c.every((s, i) => !i || s.y - (c[i - 1].y + c[i - 1].h) === FOOT + G)),  // a footer and a gutter under the one above: no holes
        gutter: edges.every((e, i) => !i || e[0] - edges[i - 1][1] === G),                         // 16 px between columns
        edge: cols.every((c) => c.every((s) => s.x === c[0].x) || c.every((s) => s.x + s.w === c[0].x + c[0].w)),  // a column shares one side
        centred: Math.abs((l + r) / 2 - (room.left + right) / 2) <= 1,                             // the cluster sits in the middle of its room
        cols: cols.map((c) => c.map((s) => s.id)),
        overlaps: spots.some((s) => spots.some((o) => o !== s && hit(box(s), box(o)))) };
    };"""


def test_the_cluster_is_aligned_packed_and_centred_left_of_the_orb(hub):
    out = run(hub, BOARD + """
        const panels = [{id: 'lead', w: 440, h: 110}, {id: 'pic', w: 600, h: 370, centre: true}, {id: 'due', w: 300, h: 150},
                        {id: 'fact', w: 440, h: 100}, {id: 'chart', w: 440, h: 210}];
        const spots = m.cluster(panels, {area, keepOut, foot: FOOT});
        return {spots, gutter16: G, ...check(spots)};""")
    spots = {s["id"]: s for s in out["spots"]}
    assert out["gutter16"] == 16
    assert out["inside"] and not out["orb"] and out["leftOfOrb"]
    assert out["baseline"] and out["stacked"] and out["gutter"] and out["edge"] and out["centred"], out
    assert not out["overlaps"]  # room enough: nobody overlaps
    assert all(s["covered"] == 0 for s in out["spots"])
    assert spots["lead"]["z"] == max(s["z"] for s in out["spots"])  # the window Jarvis means is on top
    # media leads the centre column, the smaller windows packed in the columns either side (no stragglers)
    assert len(out["cols"]) == 3 and out["cols"][1][0] == "pic", out["cols"]
    assert all(len(c) >= 1 for c in out["cols"]) and sorted(sum(out["cols"], [])) == ["chart", "due", "fact", "lead", "pic"]
    # the left column hugs the media (shared right edge), the right column starts a gutter after it
    left = [spots[i] for i in out["cols"][0]]
    assert all(s["x"] + s["w"] == spots["pic"]["x"] - 16 for s in left)
    assert all(spots[i]["x"] == spots["pic"]["x"] + 600 + 16 for i in out["cols"][2])


def test_one_window_sits_in_the_middle_of_its_room(hub):
    out = run(hub, BOARD + """const spots = m.cluster([{id: 'a', w: 440, h: 200}], {area, keepOut, foot: FOOT}); return {spots, ...check(spots)};""")
    s = out["spots"][0]
    assert out["centred"] and out["inside"] and abs((s["y"] + (s["h"] + 28) / 2) - (12 + 960) / 2) <= 1


def test_a_crowded_cluster_closes_its_columns_up_and_stays_clear_of_the_orb(hub):
    out = run(hub, BOARD + """
        const small = {...area, right: 1240, bottom: 560}, orb = [{left: 1150, top: 470, right: 1280, bottom: 720}];
        const panels = [{id: 'a', w: 380, h: 300}, {id: 'b', w: 300, h: 300}, {id: 'c', w: 300, h: 260},
                        {id: 'd', w: 300, h: 230}, {id: 'e', w: 330, h: 230}, {id: 'f', w: 330, h: 280}, {id: 'g', w: 300, h: 250}];
        const spots = m.cluster(panels, {area: small, keepOut: orb, foot: FOOT});
        const roomy = m.cluster(panels.slice(0, 3), {area: small, keepOut: orb, foot: FOOT});
        return {spots, roomy, ...check(spots, small, orb), roomyOverlaps: check(roomy, small, orb).overlaps};""")
    assert out["inside"] and not out["orb"] and out["leftOfOrb"] and out["baseline"] and out["gutter"], out
    covered = {s["id"]: s["covered"] for s in out["spots"]}
    assert covered["a"] == 0 and any(c > 0 for c in covered.values())  # crowded: a column closes up, never over the one on top
    assert all(0 <= c < 1 for c in covered.values()), covered  # (the canvas steps the oldest aside past one half)
    assert not out["roomyOverlaps"] and all(s["covered"] == 0 for s in out["roomy"])  # overlap only when crowded


def test_windows_keep_their_spots_when_another_arrives(hub):
    out = run(hub, BOARD + """
        const first = m.cluster([{id: 'a', w: 440, h: 130}, {id: 'b', w: 600, h: 370, centre: true}], {area, keepOut, foot: FOOT});
        const prev = (s) => ({x: s.x, y: s.y});
        const again = m.cluster([{id: 'new', w: 300, h: 150}, ...first.map((s) => ({id: s.id, w: s.w, h: s.h, centre: s.id === 'b', prev: prev(s)}))], {area, keepOut, foot: FOOT});
        // TIDY (nobody has a spot) lays the three out afresh, centred again
        const tidy = m.cluster([{id: 'new', w: 300, h: 150}, ...first.map((s) => ({id: s.id, w: s.w, h: s.h, centre: s.id === 'b'}))], {area, keepOut, foot: FOOT});
        return {first, again, ...check(again), tidy: check(tidy)};""")
    before = {s["id"]: (s["x"], s["y"]) for s in out["first"]}
    after = {s["id"]: s for s in out["again"]}
    assert (after["a"]["x"], after["a"]["y"]) == before["a"] and (after["b"]["x"], after["b"]["y"]) == before["b"]  # nothing jumps
    assert not out["overlaps"] and out["inside"] and out["leftOfOrb"]
    new, others = after["new"], [after["a"], after["b"]]
    # the new one is aligned to the cluster: a footer and a gutter under a window (sharing an edge), or a new column a gutter away on the top baseline
    under = any(new["y"] == o["y"] + o["h"] + 28 + 16 and (new["x"] == o["x"] or new["x"] + new["w"] == o["x"] + o["w"]) for o in others)
    beside = new["y"] == min(o["y"] for o in others) and (new["x"] == max(o["x"] + o["w"] for o in others) + 16 or new["x"] + new["w"] == min(o["x"] for o in others) - 16)
    assert under or beside, out["again"]
    assert out["tidy"]["centred"] and out["tidy"]["baseline"] and out["tidy"]["gutter"] and out["tidy"]["stacked"]


def test_panel_widths_tiers_and_roles(hub):
    out = run(hub, """return [m.panelWidth({type: 'countdown'}, 1840), m.panelWidth({type: 'fact'}, 1840), m.panelWidth({type: 'file'}, 1840, {picture: true}),
        m.panelWidth({type: 'notice'}, 1840, {short: true}), [m.panelWidth({type: 'countdown'}, 1360), m.panelWidth({type: 'approval'}, 1360), m.panelWidth({type: 'file'}, 1360, {picture: true})],
        m.panelWidth({type: 'notice'}, 200), m.TIER,
        m.roleOf({type: 'file'}), m.roleOf({type: 'file'}, {picture: false}), m.roleOf({type: 'chart'}), m.roleOf({type: 'countdown'}), m.roleOf({type: 'approval'}),
        ['countdown', 'timer', 'next_up', 'file', 'chart', 'branch_card', 'approval', 'timeline', 'fact', 'unsorted', 'notice'].map((type) => m.tierOf({type})),
        [m.tierOf({type: 'branch_card'}, {short: true}), m.tierOf({type: 'chart'}, {short: true}), m.tierOf({type: 'approval'}, {short: true}), m.tierOf({type: 'file'}, {picture: true})]];""")
    assert out[6] == {"S": 300, "M": 440, "L": 600}
    assert out[0:4] == [300, 440, 600, 300]  # S, M and L at 1920; a few words are small
    assert out[4] == [225, 330, 450]  # the same tiers at 1440 (× 0.75)
    assert out[5] == 200  # never wider than the room
    assert out[7:12] == ["media", "title", "chart", "number", "title"]
    assert out[12] == ["S", "S", "M", "M", "M", "M", "M", "M", "M", "M", "M"]  # by kind, before the content is known
    assert out[13] == ["S", "M", "M", "L"]  # by content: short titles small, charts and questions medium, media large
