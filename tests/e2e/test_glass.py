"""HUD v3 glass collage windows on the Stage (HUD v2 §14 decision 3, P3): glass frames (v0.5.4: a soft shadow and a lit top edge, no ghost outlines), pin and
close only on hover or focus, the panel itself opens its thing, media edge to edge, the blue kicker, the title
plate only on the window Jarvis means, and a collage that keeps windows put until TIDY."""

STATE = "window.__jarvis.store.state"
PUSH = """(w) => window.__jarvis.store.apply({ v: 2, type: 'window.push', ts: '2026-11-16T15:42:00', data: w })"""
SPOTS = """[...document.querySelectorAll('.jv-stage__canvas > jv-window:not([leaving])')].map((w) => [w.getAttribute('window-id'), w.style.left, w.style.top])"""
TOKEN = """(name) => { const p = document.createElement('p'); p.style.color = `var(${name})`; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; }"""


def test_each_window_is_a_slab_of_glass(hub):
    for theme in ("night", "day"):
        page = hub.scene("stage-active", theme=theme)
        got = page.eval_on_selector("jv-window[window-id=w-pps7]", """(w) => {
            const cs = getComputedStyle(w), r = w.getBoundingClientRect();
            const ghosts = [...w.querySelectorAll(':scope > .jv-window__ghost')].map((g) => { const b = g.getBoundingClientRect(); return [b.right - r.right, b.bottom - r.bottom]; });
            const meta = w.querySelector(':scope > .jv-window__meta').getBoundingClientRect().top - r.bottom;
            const hidden = [...w.querySelectorAll(':scope > .jv-window__ghost')].every((g) => getComputedStyle(g).display === 'none');
            return { hidden, shadow: cs.boxShadow, radius: cs.borderTopLeftRadius, edge: cs.borderTopColor, attach: cs.backgroundAttachment, image: cs.backgroundImage, ghosts, meta,
                     blur: cs.backdropFilter, bodyBlur: getComputedStyle(document.body).backdropFilter }; }""")
        assert got["radius"] == "8px" and got["blur"] in ("none", "") and got["bodyBlur"] in ("none", ""), got
        # see-through: a tint over the page's own grid and vignette, fixed to the screen so they line up
        assert got["image"].count("gradient") >= 4 and "fixed" in got["attach"], got
        # v0.5.4: no stacked ghost outlines (they read as a cartoon): depth is a soft shadow and a lit top edge;
        # the metadata still hangs clear below the frame
        assert got["hidden"], got
        assert got["shadow"] not in ("none", "") and got["meta"] >= 6, got
    page = hub.scene("stage-active", theme="night")
    edge = page.evaluate(f"({TOKEN})('--glass-edge')")
    assert page.eval_on_selector("jv-window[active]", "w => getComputedStyle(w).borderTopColor") == edge  # the bright edge
    assert not hub.problems, hub.problems


def test_pin_and_close_show_only_on_hover_or_focus_and_stay_labelled(hub):
    page = hub.scene("stage-active", theme="night")
    tools = "jv-window[window-id=w-pps7] .jv-window__tools"
    opacity = lambda: page.eval_on_selector(tools, "t => getComputedStyle(t).opacity")  # noqa: E731
    page.mouse.move(5, 500)
    assert opacity() == "0"
    assert page.get_attribute("jv-window[window-id=w-pps7] [data-tool=close]", "title") == "Close PPS 7 (it waits on the Rail)"
    names = page.eval_on_selector_all("jv-window[window-id=w-pps7] .jv-window__tool", "bs => bs.map((b) => b.textContent.trim())")
    assert names == ["Pin PPS 7", "Close PPS 7"]
    page.hover("jv-window[window-id=w-pps7] .jv-window__body")
    assert opacity() == "1"
    page.mouse.move(5, 500)
    page.focus("jv-window[window-id=w-pps7] [data-tool=pin]")  # the keyboard finds them too
    assert opacity() == "1"
    # no buttons drawn on any card at rest: every tool is invisible, and the content's "Open it" isn't drawn
    page.evaluate("document.activeElement.blur()")
    shown = page.evaluate("""[...document.querySelectorAll('.jv-stage__canvas jv-window .jv-window__tools')].filter((t) => getComputedStyle(t).opacity !== '0').length""")
    assert shown == 0
    # the phone (touch) keeps them showing
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page = hub.scene("now", theme="night", size="phone")
    assert page.eval_on_selector(".jv-now__canvas jv-window[window-id] .jv-window__tools", "t => getComputedStyle(t).opacity") == "1"
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_the_panel_itself_opens_its_thing(hub):
    page = hub.scene("stage-active", theme="night")
    opener = "jv-window[window-id=w-pps7] [data-key=open]"
    box = page.locator(opener).bounding_box()
    assert box["width"] <= 1 and box["height"] <= 1  # not drawn ...
    assert page.locator(opener).inner_text().replace("\n", "") == "Open it: PPS 7.pdf"  # ... but a real, labelled button
    assert page.eval_on_selector("jv-window[window-id=w-pps7]", "w => getComputedStyle(w).cursor") == "pointer"
    page.click("jv-window[window-id=w-pps7] jv-thumb")  # a click on the panel: the reader opens at his place
    page.wait_for_function("location.hash === '#/read/th-pps7'")
    # the keyboard: Tab reaches the panel's "Open it", the whole panel shows the ring, Enter opens it
    page = hub.scene("stage-active", theme="night")
    page.focus("jv-window[window-id=w-ge122] [data-tool=close]")
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.dataset.key") == "open":
            break
    assert page.evaluate("document.activeElement.closest('jv-window')?.getAttribute('window-id')") == "w-ge122"
    page.evaluate("document.activeElement.blur(); document.querySelector('jv-window[window-id=w-ge122] [data-key=open]').focus({ focusVisible: true })")
    ring = page.eval_on_selector("jv-window[window-id=w-ge122]", "w => getComputedStyle(w).outlineStyle")
    assert ring == "solid"
    page.keyboard.press("Enter")
    page.wait_for_function("location.hash === '#/life/ge-122'")
    assert not hub.problems, hub.problems


def test_controls_inside_a_panel_never_open_it(hub):
    page = hub.scene("stage-active", theme="night")
    page.click("jv-window[window-id=w-due-pps7] [data-tool=pin]")
    page.wait_for_function(f"{STATE}.windows.find((w) => w.id === 'w-due-pps7').pinned")
    page.click("jv-window[window-id=w-ge122] .jv-window__head")  # the kicker of a panel with an opener does open it
    page.wait_for_function("location.hash === '#/life/ge-122'")
    # a question: clicking its window only OPENS it (in Activity); it never answers it (HUD v2 §14.2, v0.4.1)
    page = hub.scene("stage-waiting", theme="night")
    ask = "jv-window[window-id=w-ap-week]"
    assert page.locator(f"{ask} > .jv-window__body > jv-approval-card > article > .jv-approval-card__buttons").count() == 0  # no buttons at rest
    yes = page.locator(f"{ask} [data-key=yes]")
    assert yes.count() == 1 and yes.evaluate("b => b.closest('.jv-more') !== null")  # Yes / No wait in the drawer
    for part in (".jv-window__head", ".jv-approval-card__title", ".jv-pane__line"):
        page = hub.scene("stage-waiting", theme="night")
        page.evaluate("(() => { window.__acts = []; document.addEventListener('jv-act', (e) => window.__acts.push(e.detail.action)); })()")
        page.click(f"{ask} {part}")
        page.wait_for_function("location.hash === '#/activity'")
        assert page.evaluate("window.__acts") == [] and hub.state("s => s.approvals.find((a) => a.id === 'ap-week').status") == "pending"
    # keyboard focus opens the drawer at once: Yes is then one Enter away; the pointer resting on the window opens it too
    page = hub.scene("stage-waiting", theme="night")
    drawer = page.locator(f"{ask} .jv-more")
    assert drawer.bounding_box()["height"] <= 1
    page.focus(f"{ask} [data-key=yes]")
    assert drawer.bounding_box()["height"] > 60 and page.locator(f"{ask} [data-key=no]").is_visible()
    page.evaluate("document.activeElement.blur()")
    page.hover(f"{ask} .jv-approval-card__title")
    page.wait_for_function("document.querySelector('jv-window[window-id=w-ap-week] .jv-more').getBoundingClientRect().height > 60")


def test_media_fill_the_panel_edge_to_edge(hub):
    for width, height, size in ((1920, 1080, "full"), (1280, 720, "laptop")):
        hub.page.set_viewport_size({"width": width, "height": height})
        page = hub.scene("stage-active", theme="night", size=size)
        got = page.eval_on_selector("jv-window[window-id=w-pps7]", """(w) => {
            const r = w.getBoundingClientRect(), t = w.querySelector('jv-thumb').getBoundingClientRect(), head = w.querySelector('.jv-window__head').getBoundingClientRect();
            return { media: w.hasAttribute('media'), left: t.left - r.left, right: r.right - t.right, bottom: r.bottom - t.bottom, below: t.top - head.bottom, width: r.width,
                     labels: w.querySelectorAll('.jv-pane--media .jv-thumb__label, .jv-pane--media .jv-pane__line').length,
                     tint: getComputedStyle(w.querySelector('.jv-pane__media .jv-thumb'), '::after').backgroundColor }; }""")
        assert got["media"] and got["left"] <= 1.5 and got["right"] <= 1.5 and got["bottom"] <= 1.5, got  # inside the 1 px edge
        assert got["below"] >= 0 and got["width"] <= (602 if size == "full" else 452) and got["labels"] == 0, got  # under the kicker; media is the large tier; nothing over it
        assert got["tint"] not in ("rgba(0, 0, 0, 0)", "transparent"), got  # a bright page sits under the static dark tint (§14.2)
    hub.page.set_viewport_size({"width": 1440, "height": 900})


def test_the_kicker_is_the_accent_and_the_window_jarvis_means_has_the_accent_edge(hub):
    # serious mode (v0.6.0, HUD_V2 §14.12): no title plate; the window Jarvis means gets the accent edge
    page = hub.scene("stage-crowded", theme="night")
    page.wait_for_selector("jv-window[active]")
    cyan, edge = page.evaluate(f"[({TOKEN})('--cyan'), ({TOKEN})('--glass-edge')]")
    assert page.eval_on_selector("jv-window[window-id=w-due-pps7] .jv-window__name", "n => getComputedStyle(n).color") == cyan
    plates = page.evaluate("""() => [...document.querySelectorAll('.jv-stage__canvas jv-window :is(.jv-pane__title, .jv-approval-card__title) > span')]
        .filter((n) => getComputedStyle(n).backgroundColor !== 'rgba(0, 0, 0, 0)').length""")
    assert plates == 0
    assert page.eval_on_selector("jv-window[active]", "w => getComputedStyle(w).borderTopColor") == edge
    # titles are sentence case in the clean sans, not condensed caps
    font = page.eval_on_selector("jv-window[window-id=w-ge122] .jv-pane__title", "n => [getComputedStyle(n).textTransform, getComputedStyle(n).fontFamily]")
    assert font[0] == "none" and "Lexend" in font[1] and "Barlow" not in font[1]
    # big numbers stay big
    assert page.eval_on_selector("jv-window[window-id=w-due-pps7] .jv-big-number__value", "n => parseFloat(getComputedStyle(n).fontSize)") >= 48


def test_windows_keep_their_spots_when_another_arrives_and_tidy_lays_them_out_again(hub):
    page = hub.scene("stage-active", theme="night")
    before = dict((i, (x, y)) for i, x, y in page.evaluate(SPOTS))
    page.evaluate(PUSH, {"id": "w-note", "type": "notice", "title": "Lab 4", "data": {"text": "Room changed to ENGR 2A30"}, "pushed": "2026-11-16T15:42:00"})
    page.wait_for_selector("jv-window[window-id=w-note]")
    page.wait_for_timeout(100)
    after = dict((i, (x, y)) for i, x, y in page.evaluate(SPOTS))
    assert {i: after[i] for i in before} == before  # nothing jumped
    assert page.get_attribute("jv-window[window-id=w-note]", "active") == ""  # the newcomer is the one he means
    page.evaluate("window.__jarvis.bridge.act('move', 'w-ge122', { to: 'left' })")
    page.wait_for_function(f"{STATE}.windows[0].id === 'w-ge122'")
    page.click("[data-do=tidy]")
    page.wait_for_function(f"{STATE}.windows.map(w => w.id).join() === 'w-next,w-due-pps7,w-pps7,w-ge122,w-note'", timeout=2_000)
    assert page.locator(".jv-stage__canvas > jv-window:not([leaving])").count() == 5
    assert not hub.problems, hub.problems


def test_the_stage_words_are_small_and_quiet(hub):
    page = hub.scene("stage-active", theme="night")
    got = page.evaluate("""[...document.querySelectorAll('.jv-stage__pills button')].map((b) => {
        const cs = getComputedStyle(b); return [b.textContent.trim(), cs.fontFamily.includes('JetBrains Mono'), cs.fontSize, cs.borderTopColor, b.getAttribute('aria-label')]; })""")
    assert [g[0] for g in got] == ["Hub", "Tidy", "Clear view"]
    assert all(g[1] and g[2] == "12px" and g[3] == "rgba(0, 0, 0, 0)" for g in got), got
    assert got[2][4] == "Clear view: send everything to the Rail"
    # nothing on the board under them
    under = page.evaluate("""(() => { const bar = document.querySelector('.jv-stage__bar').getBoundingClientRect();
        return [...document.querySelectorAll('.jv-stage__canvas > jv-window')].filter((w) => { const r = w.getBoundingClientRect();
          return r.left < bar.right && bar.left < r.right && r.top < bar.bottom && bar.top < r.bottom; }).length; })()""")
    assert under == 0


def test_a_pushed_window_lands_on_the_board_within_a_frame_or_two(hub):
    # the median of three pushes (other test runs share this machine), each placed within two frames
    page = hub.scene("stage-waiting", theme="night")
    took = page.evaluate("""async () => { const s = window.__jarvis.store, out = [];
        const push = (id) => s.apply({v: 2, type: 'window.push', ts: '', data: {id, type: 'countdown', title: 'Due', ref: 'due-pps7'}});
        const two = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const rest = () => new Promise((r) => setTimeout(r, 150));
        push('w-warm'); await two(); await rest();  // (the first push also loads fonts)
        for (const id of ['w-p1', 'w-p2', 'w-p3']) {
          const t0 = performance.now(); push(id); await two();
          const w = document.querySelector(`jv-window[window-id=${id}]`);
          out.push([performance.now() - t0, !!w && !!w.style.left && !!w.querySelector('.jv-big-number__value')]);
          await rest();
        }
        return out; }""")
    print("window.push to a placed glass panel (ms):", [round(ms) for ms, _ in took])
    assert all(placed for _, placed in took)
    assert sorted(ms for ms, _ in took)[1] < 100
