"""N10 (v0.17.0), his ask of 2026-11-21: one window; the windows inside it can be moved and sized by hand; a
window pulled off the hub gets a plain window of its own (no orb, no voice) and can come back."""
import json

WIN = 'jv-window[window-id="{}"]'
DUE, FILE, NEXT = "w-due-pps7", "w-pps7", "w-next"


def box(page, wid):
    return page.evaluate("id => { const r = document.querySelector(`jv-window[window-id=\"${id}\"]`).getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }", wid)


def drag(page, x, y, dx, dy, steps=6):
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(x + dx * i / steps, y + dy * i / steps)
    page.mouse.up()


def near(a, b, tol=3):
    return abs(a - b) <= tol


def test_one_window_is_the_default_when_nothing_is_saved(hub):
    page = hub.scene("now-awake")
    assert page.evaluate("import('/views/stage/desktop.js').then(m => [m.stageSetting({ settings: {} }), m.stageSetting({ settings: { stage: 'window' } }), m.stageSetting({ settings: { stage: 'hub' } })])") == ["hub", "window", "hub"]
    report = page.evaluate("import('/views/stage/desktop.js').then(m => m.stageReport({ settings: {}, windows: [{ id: 'a' }], now_card: {} }))")
    assert report["settings"]["stage"] == "hub" and report["state"]["popped"] == 0
    assert hub.problems == []


def test_a_window_on_the_hub_can_be_dragged_and_stays_where_he_put_it(hub):
    page = hub.scene("now-active")
    page.wait_for_selector(WIN.format(DUE))
    before, other = box(page, DUE), box(page, NEXT)
    drag(page, before["x"] + 60, before["y"] + 14, 150, -70)
    after = box(page, DUE)
    assert near(after["x"], before["x"] + 150) and near(after["y"], before["y"] - 70)
    assert page.locator(WIN.format(DUE)).get_attribute("held") is not None
    assert page.evaluate("window.__jarvis.router.current.path") == "/now"         # the drag's click opened nothing
    assert page.locator(".jv-why, [role=dialog]").count() == 0
    page.evaluate("window.__jarvis.store.setUi({ nudge: Date.now() })")           # a redraw doesn't take it back
    page.wait_for_timeout(120)
    again = box(page, DUE)
    assert near(again["x"], after["x"]) and near(again["y"], after["y"])
    assert near(box(page, NEXT)["w"], other["w"])                                 # the others are not resized by it
    assert hub.problems == []


def test_a_plain_click_still_works_and_controls_do_not_start_a_drag(hub):
    page = hub.scene("now-active")
    page.wait_for_selector(WIN.format(DUE))
    win = page.locator(WIN.format(NEXT))
    win.hover()
    pin = win.locator('button[data-tool="pin"]')
    b = pin.bounding_box()
    drag(page, b["x"] + 8, b["y"] + 8, 90, 40)                                    # a press that starts on a button
    assert win.get_attribute("held") is None
    before = box(page, DUE)
    page.mouse.click(before["x"] + 60, before["y"] + 14)                          # no travel: not a drag
    assert page.locator(WIN.format(DUE)).get_attribute("held") is None
    after = box(page, DUE)
    assert near(after["x"], before["x"]) and near(after["y"], before["y"])


def test_the_corner_grip_sizes_a_window_by_mouse_and_by_keyboard(hub):
    page = hub.scene("now-active")
    win = page.locator(WIN.format(DUE))
    win.wait_for()
    before = box(page, DUE)
    grip = win.locator(".jv-window__grip")
    assert grip.get_attribute("aria-label").startswith("Size or move")
    g = grip.bounding_box()
    drag(page, g["x"] + g["width"] / 2, g["y"] + g["height"] / 2, 90, 60)
    sized = box(page, DUE)
    assert near(sized["w"], before["w"] + 90) and near(sized["h"], before["h"] + 60)
    assert near(sized["x"], before["x"]) and near(sized["y"], before["y"])        # its corner stays put
    grip.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")
    keyed = box(page, DUE)
    assert near(keyed["w"], sized["w"] + 24) and near(keyed["h"], sized["h"] + 24)
    page.keyboard.press("Shift+ArrowLeft")
    moved = box(page, DUE)
    assert near(moved["x"], keyed["x"] - 24) and near(moved["w"], keyed["w"])
    for _ in range(60):
        page.keyboard.press("ArrowLeft")                                          # never smaller than it can be read
    assert box(page, DUE)["w"] >= 220
    page.keyboard.press("Home")                                                   # lets go: back where Jarvis puts it
    assert win.get_attribute("held") is None
    home = box(page, DUE)
    assert near(home["w"], before["w"]) and near(home["h"], before["h"])
    assert hub.problems == []


def test_a_window_he_arranged_stays_up_past_its_minute(hub):
    page = hub.scene("now-awake")
    gone = page.evaluate("""import('/core/windows.js').then(m => {
      let t = 0; const docked = [];
      const clock = new m.WindowClock(id => docked.push(id), () => t);
      const wins = [{ id: 'a', type: 'fact' }, { id: 'b', type: 'fact' }];
      clock.tick(wins); clock.keep('a'); t = 10 * 60_000; clock.tick(wins);
      const first = [...docked];
      clock.keep('a', false); t += 10 * 60_000; clock.tick([wins[0]]);   // "b" is already in the Rail
      return [first, docked];
    })""")
    assert gone[0] == ["b"] and gone[1] == ["b", "a"]


def test_its_own_window_button_moves_a_window_to_the_holder_and_back(hub):
    page = hub.scene("now-active")
    page.wait_for_selector(WIN.format(FILE))
    holder = page.context.new_page()
    holder.goto(f"{hub.base}/?scene=stage-holder-live&theme=day&window=stage")
    holder.wait_for_selector("html[data-ready]")
    assert holder.locator("jv-window[window-id]").count() == 0                    # nothing pulled out yet
    assert holder.locator(".jv-stage__empty").is_visible()
    assert holder.evaluate("document.documentElement.dataset.stage") == "holder"
    for hidden in ("#dock", "#foot"):
        assert holder.locator(hidden).is_hidden()                                 # no orb, no voice, no bottom row
    win = page.locator(WIN.format(FILE))
    win.hover()
    with page.context.expect_page() as opened:                                    # in a browser the holder is a named window
        win.get_by_role("button", name="Move PPS 7 to its own window").click()
    opened.value.close()
    page.wait_for_selector(WIN.format(FILE), state="detached")
    assert page.locator("jv-window[window-id]").count() == 3                      # the hub keeps the rest
    assert json.loads(page.evaluate("localStorage.getItem('jv-popped')")) == [FILE]
    holder.wait_for_selector(WIN.format(FILE))                                    # the other window heard at once
    assert holder.locator("jv-window[window-id]").count() == 1
    assert holder.locator(".jv-stage__empty").is_hidden()
    report = page.evaluate("import('/views/stage/desktop.js').then(m => m.stageReport())")
    assert report["state"]["popped"] == 1                                         # what app.py shows the holder on
    out = holder.locator(WIN.format(FILE))
    out.hover()
    out.get_by_role("button", name="Move PPS 7 back to the hub").click()
    holder.wait_for_selector(WIN.format(FILE), state="detached")
    page.wait_for_selector(WIN.format(FILE))
    assert page.evaluate("localStorage.getItem('jv-popped')") is None
    assert hub.problems == []


def test_dragged_off_the_edge_it_leaves_and_back_to_the_hub_returns_everything(hub):
    page = hub.scene("now-active")
    page.wait_for_selector(WIN.format(DUE))
    b = box(page, DUE)
    page.mouse.move(b["x"] + 60, b["y"] + 14)
    page.mouse.down()
    page.mouse.move(b["x"] + 20, b["y"] + 14)
    page.mouse.move(-40, b["y"] + 14)                                             # past the hub's left edge
    assert page.locator(WIN.format(DUE)).get_attribute("leaving-screen") is not None
    with page.context.expect_page() as opened:
        page.mouse.up()
    opened.value.close()
    page.wait_for_selector(WIN.format(DUE), state="detached")
    assert json.loads(page.evaluate("localStorage.getItem('jv-popped')")) == [DUE]
    holder = page.context.new_page()
    holder.goto(f"{hub.base}/?scene=stage-holder-live&theme=day&window=stage")
    holder.wait_for_selector(WIN.format(DUE))
    hb = box(holder, DUE)                                                         # and it can be arranged there too
    drag(holder, hb["x"] + 60, hb["y"] + 14, 80, 50)
    assert near(box(holder, DUE)["x"], hb["x"] + 80)
    holder.get_by_role("button", name="Move every window here back to the hub").click()
    holder.wait_for_selector(WIN.format(DUE), state="detached")
    page.wait_for_selector(WIN.format(DUE))
    assert page.locator("jv-window[window-id]").count() == 4


def test_the_stage_setting_keeps_the_old_way_with_no_grips_for_sending(hub):
    page = hub.scene("stage-active")                                              # "Stage window": every window on the Stage
    page.wait_for_selector("jv-window[window-id]")
    assert page.locator('button[data-tool^="pop"]').count() == 0                  # nowhere to send them
    assert page.locator(".jv-window__grip").count() >= 1                          # but they can still be moved and sized
    assert page.evaluate("document.documentElement.dataset.stage") == "active"


def test_resting_with_one_window_shows_the_orb_alone_not_the_board_under_it(hub):
    """His screenshot of 2026-11-22: the resting orb drawn over the awake clock and the Now card."""
    page = hub.scene("now-awake")
    page.evaluate("(() => { const s = window.__jarvis.store; s.set({ settings: { theme: 'night', motion: 'full' }, windows: [] }); s.setUi({ ambient: true }); })()")
    page.wait_for_selector(".jv-now--ambient")
    assert page.locator(".jv-now__canvas").is_hidden()
    assert page.locator(".jv-now__ambient jv-orb").is_visible()


def test_with_nothing_up_the_hub_is_the_orb_and_windows_send_it_to_the_corner(hub):
    """His second screenshot of 2026-11-22: awake with no windows showed a clock and the Now card, not the orb."""
    page = hub.scene("now-awake")
    page.evaluate("(() => { const s = window.__jarvis.store; s.set({ settings: { theme: 'night', motion: 'full' }, windows: [], approvals: [] }); })()")
    page.wait_for_selector(".jv-now--ambient")
    assert page.locator(".jv-now__ambient jv-orb").is_visible() and page.locator(".jv-now__canvas").is_hidden()
    page.evaluate("window.__jarvis.store.apply({ type: 'window.push', ts: window.__jarvis.store.state.now, data: { id: 'w-x', type: 'fact', title: 'A fact', ref: 'f-ge-late' } })")
    page.wait_for_selector('jv-window[window-id="w-x"]')
    assert page.locator(".jv-now__canvas").is_visible() and page.locator(".jv-now__ambient jv-orb").is_hidden()
    assert hub.problems == []
