"""F5: Activity, approvals, receipts, toasts and announcements, driven with the keyboard only.
After every answer, focus must land somewhere sensible (never <body>)."""
import re

FOCUS = """() => { const e = document.activeElement;
  if (!e || e === document.body) return {tag: 'BODY'};
  return {tag: e.tagName, key: e.dataset.key || '', cls: String(e.className || ''), label: e.getAttribute('aria-label') || '',
          text: (e.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120), toast: !!e.closest('jv-toast'), id: (e.closest('[data-id]') || {dataset: {}}).dataset.id || ''}; }"""


def focus(page):
    return page.evaluate(FOCUS)


def tab_to(page, test, limit=80, back=False):
    for _ in range(limit):
        page.keyboard.press("Shift+Tab" if back else "Tab")
        if page.evaluate(f"(() => {{ const e = document.activeElement; return !!e && ({test}); }})()"):
            return focus(page)
    raise AssertionError(f"never reached {test}; focus is {focus(page)}")


def toast(page, data):
    page.evaluate(f"window.__jarvis.store.apply({{v: 1, type: 'toast', ts: '', data: {data}}})")


def acts(page):
    page.evaluate("window.__acts = []; document.addEventListener('jv-act', e => window.__acts.push(e.detail), true)")
    return lambda: page.evaluate("window.__acts")


# ---- answering in Activity -------------------------------------------------------------------------
def test_keyboard_yes_lands_on_the_new_receipt_and_says_booked_with_undo(hub):
    page = hub.scene("activity")
    got = acts(page)
    tab_to(page, "e.dataset.key === 'yes'")
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")  # a second press must not answer twice
    page.wait_for_function("document.activeElement.classList.contains('jv-action-row')")
    f = focus(page)
    assert "Book this week's study plan" in f["text"] and not f["toast"]
    assert [g["action"] for g in got()].count("approve") == 1
    page.wait_for_selector("jv-toast >> text=Added 9 study blocks to your Google Calendar this week")  # a plain receipt, never "Booked." or "· Done"
    assert "Undo (24 h)" in page.inner_text("jv-toast")
    assert page.locator(".jv-toast--error").count() == 0
    # Tab goes on to that receipt's own Undo, which says how long it still works
    page.keyboard.press("Tab")
    f = focus(page)
    assert f["key"] == "undo" and re.search(r"^Undo · until \d{1,2}:\d\d [ap]m tomorrow", f["text"])
    assert hub.problems == []


def test_keyboard_undo_keeps_focus_on_the_row_it_undid(hub):
    page = hub.scene("activity-clear")
    tab_to(page, "e.dataset.key === 'undo'")
    target = focus(page)["id"]
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.classList.contains('jv-action-row')")
    f = focus(page)
    assert f["id"] == target and "(undone)" in f["text"]
    assert page.evaluate(f"window.__jarvis.store.state.actions.find(a => a.id === '{target}').undone") is True


def test_keyboard_no_becomes_a_quiet_row_and_focus_follows_it(hub):
    page = hub.scene("activity")
    tab_to(page, "e.dataset.key === 'no'")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.classList.contains('jv-action-row')")
    f = focus(page)
    assert f["id"] == "declined-ap-week" and "You said no" in f["text"]
    assert "Nothing waiting for you" in page.inner_text("section[aria-labelledby=act-wait]")


def test_change_it_opens_a_field_sends_his_words_and_keeps_the_item(hub):
    page = hub.scene("activity")
    got = acts(page)
    tab_to(page, "e.dataset.key === 'change'")
    page.keyboard.press("Enter")
    assert focus(page)["tag"] == "TEXTAREA"
    page.keyboard.press("Escape")  # Esc cancels and goes back to the button
    assert focus(page)["key"] == "change" and page.locator("jv-approval-card textarea").count() == 0
    page.keyboard.press("Enter")
    page.keyboard.type("Not before 10 am, please")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.classList.contains('jv-approval-card')")
    f = focus(page)
    assert f["label"] == "Changing: Book this week's study plan"
    assert [(g["action"], g["target"], g.get("args")) for g in got() if g["action"] == "change"] == [("change", "ap-week", {"text": "Not before 10 am, please"})]
    card = page.inner_text("section[aria-labelledby=act-wait]")
    assert "Changing…" in card and "Not before 10 am, please" in card and "Yes, do it" not in card


def test_an_empty_change_is_not_sent(hub):
    page = hub.scene("activity")
    got = acts(page)
    tab_to(page, "e.dataset.key === 'change'")
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    assert focus(page)["tag"] == "TEXTAREA" and "Type what to change first" in page.inner_text("jv-approval-card")
    assert [g for g in got() if g["action"] == "change"] == []


def test_keyboard_yes_over_the_live_demo(hub):
    page = hub.open()
    page.evaluate("fetch('/api/demo/restart', {method: 'POST'})")
    # the question goes to the Stage (N9); the calm home only says "1 waiting for your yes"
    page.wait_for_function("window.__jarvis.store.state.windows.some(w => w.type === 'approval')", timeout=15_000)
    page.keyboard.press("4")
    page.wait_for_selector("jv-view-activity jv-approval-card >> text=Yes, do it")
    tab_to(page, "e.dataset.key === 'yes' && !!e.closest('jv-view-activity')")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.classList.contains('jv-action-row')", timeout=5_000)
    assert "Book this week's study plan" in focus(page)["text"]
    page.wait_for_selector("jv-toast >> text=Added 9 study blocks to your Google Calendar this week")
    assert page.locator(".jv-toast--error").count() == 0


# ---- toasts ----------------------------------------------------------------------------------------
def test_a_focused_toast_waits_and_focus_comes_back_when_it_goes(hub):
    page = hub.scene("activity-clear")
    # remember the last thing focused outside the toasts, to check focus goes back there
    page.evaluate("document.addEventListener('focusin', e => { if (!e.target.closest('jv-toasts')) window.__before = e.target; })")
    back = lambda: page.evaluate("document.activeElement === window.__before && document.activeElement !== document.body")  # noqa: E731
    tab_to(page, "e.dataset.key === 'f-files'")
    toast(page, "{id: 't-a', kind: 'info', text: 'Jarvis learned 3 things today.', ttl_ms: 600, action: {label: 'See them', action: 'open', target: '/life/memory'}}")
    page.wait_for_selector("jv-toast[data-id=t-a]")
    assert tab_to(page, "!!e.closest('jv-toast')")["toast"]
    page.wait_for_timeout(1200)  # well past its time: it waits while it has focus
    assert page.locator("jv-toast[data-id=t-a]").count() == 1
    page.keyboard.press("Escape")  # Esc sends it away; focus goes back where it was
    page.wait_for_selector("jv-toast[data-id=t-a]", state="detached")
    assert back() and focus(page)["tag"] != "BODY"
    # a focused toast that leaves for another reason (the hub dropped it) also hands focus back
    toast(page, "{id: 't-b', kind: 'success', text: 'Undone.', ttl_ms: 600}")
    assert tab_to(page, "!!e.closest('jv-toast')")["toast"]
    page.evaluate("window.__jarvis.store.set({toasts: []})")
    page.wait_for_selector("jv-toast[data-id=t-b]", state="detached")
    assert back()
    # once focus leaves, the timer runs again and the toast goes by itself
    toast(page, "{id: 't-c', kind: 'info', text: 'Saved.', ttl_ms: 500}")
    assert tab_to(page, "!!e.closest('jv-toast')")["toast"]
    page.wait_for_timeout(800)
    assert page.locator("jv-toast[data-id=t-c]").count() == 1
    page.keyboard.press("Shift+Tab")
    assert not focus(page)["toast"]
    page.wait_for_selector("jv-toast[data-id=t-c]", state="detached", timeout=3_000)
    assert focus(page)["tag"] != "BODY"
    # the toast's action works from the keyboard and sends the toast away, handing focus back
    toast(page, "{id: 't-d', kind: 'success', text: 'Moved your GE 122 review to 5:00 pm', ttl_ms: 5000, action: {label: 'Undo (24 h)', action: 'undo', target: 'a-sync'}}")
    tab_to(page, "e.closest('jv-toast') && e.dataset.key === 'act'")
    page.keyboard.press("Enter")
    page.wait_for_selector("jv-toast[data-id=t-d]", state="detached")
    assert page.evaluate("window.__jarvis.store.state.actions.find(a => a.id === 'a-sync').undone") is True
    assert not focus(page)["toast"] and focus(page)["tag"] != "BODY"


def test_hovered_toasts_wait_and_at_most_two_show(hub):
    page = hub.scene("activity-clear")
    toast(page, "{id: 't-1', kind: 'info', text: 'One', ttl_ms: 500}")
    page.wait_for_selector("jv-toast[data-id=t-1]")
    page.hover("jv-toast[data-id=t-1]")
    page.wait_for_timeout(900)
    assert page.locator("jv-toast[data-id=t-1]").count() == 1
    page.mouse.move(5, 5)
    page.wait_for_selector("jv-toast[data-id=t-1]", state="detached", timeout=3_000)
    for n in (2, 3, 4):
        toast(page, f"{{id: 't-{n}', kind: 'info', text: 'Note {n}', ttl_ms: 10000}}")
    page.wait_for_timeout(100)
    assert page.eval_on_selector_all("jv-toast", "els => els.map(e => e.dataset.id)") == ["t-3", "t-4"]


# ---- empty states, announcements, strip ------------------------------------------------------------
def test_activity_empty_is_one_plain_card_with_one_action_and_no_filters(hub):
    page = hub.scene("activity-empty")
    assert page.locator(".jv-chip").count() == 0
    assert page.locator("#stage .jv-notice--empty").count() == 1
    assert page.locator("#stage .jv-notice--empty button").count() == 1
    assert page.evaluate("getComputedStyle(document.querySelector('#stage .jv-notice--empty')).borderStyle") == "solid"
    assert page.inner_text("#stage h1") == "Activity" and page.locator("#stage .jv-view__head .jv-crumbs").count() == 1


def test_the_waiting_card_uses_the_width(hub):
    page = hub.scene("activity")
    card = page.locator(".jv-activity__approval").bounding_box()
    sheet = page.locator("section.jv-sheet").first.bounding_box()
    assert card["width"] > 0.9 * sheet["width"]


def test_announcements_are_merged_instead_of_cut_off(hub):
    page = hub.scene("shell")
    page.evaluate("""(() => { const s = window.__jarvis.store;
      s.apply({v:1, type:'window.push', ts:'', data:{id:'w-p', type:'notice', title:'PPS 7', data:{text:'x'}}});
      setTimeout(() => s.apply({v:1, type:'caption.show', ts:'', data:{text:'PPS 7 is due Wednesday at 8 pm.', source:{kind:'canvas', label:'Canvas'}}}), 95); })()""")
    page.wait_for_function("document.getElementById('jv-live-polite').textContent.includes('Source: Canvas')")
    said = page.evaluate("document.getElementById('jv-live-polite').textContent")
    assert said.startswith("Showing PPS 7.") and "Jarvis: PPS 7 is due" in said


def test_the_strip_says_listening_never_repeats_itself_and_never_says_showing(hub):
    hub.page.set_viewport_size({"width": 360, "height": 96})
    page = hub.scene("strip")
    assert page.inner_text(".jv-strip__state") == "Listening"
    page = hub.scene("strip-waiting")
    text = page.inner_text(".jv-strip")
    assert text.lower().count("waiting for your yes") == 1 and "Book this week's study plan" in text
    page.evaluate("window.__jarvis.store.apply({v:1, type:'window.push', ts:'', data:{id:'w-p', type:'notice', title:'PPS 7', data:{text:'x'}}})")
    page.wait_for_timeout(400)
    assert "Showing" not in page.evaluate("document.getElementById('jv-live-polite').textContent")
