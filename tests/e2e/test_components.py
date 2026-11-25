"""Component behaviour that the every-scene smoke test can't see: labels, events, keyboard paths."""


def events(page, name):
    page.evaluate(f"window.__got = []; document.addEventListener('{name}', e => window.__got.push(e.detail))")
    return lambda: page.evaluate("window.__got")


def test_orb_states_have_spoken_labels_and_no_countdown_number(hub):
    page = hub.scene("component:orb")
    labels = page.eval_on_selector_all("jv-orb[size=centre] .jv-orb__stage", "els => els.map(e => e.getAttribute('aria-label'))")
    assert "Jarvis: listening" in labels and "Jarvis: muted" in labels and "Jarvis: waiting for your yes" in labels
    # reduced motion (the test browser asks for it): nothing on the orb moves; the thinking ring is dashed instead
    assert page.evaluate("document.documentElement.hasAttribute('data-still')")
    assert page.evaluate("document.getAnimations().filter((a) => a.effect.target.closest('jv-orb')).length") == 0
    assert page.evaluate("getComputedStyle(document.querySelector('jv-orb[state=thinking] .jv-orb__en-ring')).strokeDasharray") != "none"


def test_window_pin_and_close_emit_actions(hub):
    page = hub.scene("component:window")
    got = events(page, "jv-act")
    page.click("jv-window[window-id=w-1] [data-tool=pin]")
    page.click("jv-window[window-id=w-1] [data-tool=close]")
    assert got() == [{"action": "pin", "target": "w-1"}, {"action": "close", "target": "w-1"}]
    assert page.get_attribute("jv-window[window-id=w-3] [data-tool=unpin]", "aria-pressed") == "true"
    # corner brackets mean only "wants you"; the window Jarvis means has the brighter frame and no glyph in its
    # kicker (HUD v2 §14.2: no icon glyphs; only a wants-you mark may lead it)
    assert page.locator("jv-window .jv-window__reticle").count() == 0 and page.locator("jv-window[active] .jv-window__title svg").count() == 0
    assert page.locator("jv-window[glance=soon] .jv-window__title .jv-glance--soon").count() >= 1
    assert not page.is_visible("jv-window[active] .jv-window__bracket--1") and page.is_visible("jv-window[glance=soon] .jv-window__bracket--1")


def test_source_chip_shows_evidence_and_flags_unexpected_sources(hub):
    page = hub.scene("component:source-chip", state="with-evidence-opens")
    page.focus("jv-source-chip summary")
    page.keyboard.press("Enter")
    assert "10% per day" in page.inner_text(".jv-source-chip__evidence")
    page = hub.scene("component:source-chip", state="unexpected-source")
    assert "a source you might not expect" in page.inner_text("jv-source-chip")


def test_tabs_are_links_with_one_meaningful_badge(hub):
    page = hub.scene("component:tabs")
    got = events(page, "jv-nav")
    page.click("#stage jv-tabs >> nth=1 >> text=Activity")
    assert got() == [{"path": "/activity"}]
    assert page.locator("#stage jv-tabs >> nth=1").locator(".jv-tabs__badge").count() == 1
    assert "1 waiting for your yes" in page.locator("#stage jv-tabs >> nth=1").inner_text()
    assert page.locator("#stage jv-tabs >> nth=0").locator("[aria-current=page]").inner_text() == "Now"


def test_now_card_why_ends_with_controls(hub):
    page = hub.scene("component:now-card", state="a-normal-afternoon")
    got = events(page, "jv-act")
    assert "4 of 6" in page.inner_text(".jv-now-card__done")
    page.click("text=Why?")
    assert "twice the estimate" in page.inner_text(".jv-now-card__why")
    page.click("text=Less of this")
    assert got()[0]["action"] == "less"
    assert page.locator(".jv-now-card .jv-btn--primary").count() <= 1


def test_toasts_leave_and_can_be_dismissed(hub):
    page = hub.scene("shell")
    page.evaluate("window.__jarvis.store.apply({v: 1, type: 'toast', ts: '', data: {id: 't-x', kind: 'info', text: 'Hello', ttl_ms: 400}})")
    page.wait_for_selector("jv-toast >> text=Hello")
    page.wait_for_selector("jv-toast", state="detached")
    page.evaluate("window.__jarvis.store.apply({v: 1, type: 'toast', ts: '', data: {id: 't-y', kind: 'error', text: 'Try again in a moment.'}})")
    assert page.get_attribute(".jv-toast--error", "role") == "alert"
    page.click("jv-toast button >> nth=-1")
    page.wait_for_selector("jv-toast", state="detached")


def test_fact_card_guess_conflict_edit_and_forget(hub):
    page = hub.scene("component:fact-card")
    got = events(page, "jv-act")
    guess = page.locator("[data-state=a-guess-dotted-underline]")
    assert guess.locator(".jv-guess").count() == 1 and "guessed from" in guess.inner_text().lower()
    assert page.locator("[data-state=something-you-said-sure] .jv-guess").count() == 0
    guess.locator("text=Confirm").click()
    conflict = page.locator("[data-state=conflict-kept-yours]")
    assert "Canvas says Friday. Kept yours." in conflict.inner_text()
    conflict.locator("text=Use Canvas").click()
    forget = page.locator("[data-state=forget-preview]")
    assert "also forgets: Laundry room busy hours" in forget.inner_text()
    forget.locator("text=Forget it").click()
    card = page.locator("[data-state=from-a-syllabus-with-evidence]")
    card.locator("[data-key=menu]").click()
    card.locator("text=Edit").click()
    card.locator("textarea").fill("Late sets lose 10% a day.")
    card.locator("text=Save").click()
    assert [(g["action"], g["target"]) for g in got()] == [("confirm", "f-8am"), ("use_theirs", "f-ge-quiz"), ("forget", "f-res"), ("edit", "f-ge-late")]
    assert got()[3]["args"] == {"statement": "Late sets lose 10% a day."}


def test_approval_card_puts_consequences_first_with_one_accent(hub):
    page = hub.scene("component:approval-card")
    got = events(page, "jv-act")
    card = page.locator("[data-state=waiting-for-your-yes]")
    text = card.inner_text().lower()
    assert text.index("what will happen") < text.index("jarvis asks") < text.index("yes, do it")
    assert card.locator(".jv-btn--primary").count() == 1
    card.locator("text=Yes, do it").click()
    assert [(g["action"], g["target"]) for g in got()] == [("approve", "ap-week")]
    assert "can't be undone" in page.locator("[data-state=can-t-be-undone]").inner_text()
    assert page.locator("[data-state=ran-out] button").count() == 0


def test_approval_card_has_one_kicker_in_one_case(hub):
    # film review S4 mixed caps with sentence case; serious mode (v0.6.0) keeps the whole kicker in one normal case
    page = hub.scene("component:approval-card")
    kicker = page.locator("[data-state=waiting-for-your-yes] .jv-approval-card__kicker").inner_text()
    words = " ".join(kicker.split())
    assert words.startswith("Calendar // Your yes") and words.endswith("Until 9:00 pm"), words


def test_action_row_undo_window(hub):
    page = hub.scene("component:action-row")
    got = events(page, "jv-act")
    page.locator("[data-state=done-can-be-undone] >> text=Undo · until 3:38 pm tomorrow").click()
    assert [(g["action"], g["target"]) for g in got()] == [("undo", "a-sync")]
    assert page.locator("[data-state=undo-window-has-passed] button").count() == 0
    assert "Undo window has passed" in page.locator("[data-state=undo-window-has-passed]").inner_text()
    assert "held back" in page.locator("[data-state=held-back-and-why] article").inner_text().lower()


def test_command_bar_finds_his_work(hub):
    # walkthrough B11: "pps 7" found only a fact and "Ask"; "lab report" only facts
    page = hub.scene("now-awake")
    page.keyboard.press("Control+k")
    page.keyboard.type("pps 7")
    rows = page.eval_on_selector_all("[role=option]", "n => n.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")
    assert rows[0] == "PPS 7 · Q7 Open", rows
    assert any(r.startswith("GE 122 · PPS 7 · due Wed 8 pm") for r in rows), rows
    page.keyboard.press("Enter")  # opens the reader at his resume point
    page.wait_for_function("window.__jarvis.router.current.path === '/read/th-pps7'")
    page.keyboard.press("Control+k")
    page.keyboard.type("lab report")
    rows = page.eval_on_selector_all("[role=option]", "n => n.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")
    assert rows[0].startswith("Lab report 4 · Results"), rows
    assert hub.problems == []


def test_command_bar_keyboard_only(hub):
    page = hub.scene("shell")
    nav, act = events(page, "jv-nav"), None
    page.evaluate("document.addEventListener('jv-act', e => (window.__acts = window.__acts || []).push(e.detail))")
    page.evaluate("document.getElementById('command-bar').open()")
    page.keyboard.type("ge 122")
    assert page.inner_text("[role=option][aria-selected=true]").startswith("GE 122")
    page.keyboard.press("Enter")
    assert nav() == [{"path": "/life/ge-122"}] and page.locator("[role=dialog]").count() == 0
    page.evaluate("document.getElementById('command-bar').open()")
    page.keyboard.type("how long until my next lab?")
    assert page.locator("[role=option]").count() == 1  # nothing loose: only "Ask Jarvis"
    page.keyboard.press("Enter")
    assert page.evaluate("window.__acts.at(-1)") == {"action": "ask", "target": "jarvis", "args": {"text": "how long until my next lab?"}}
    page.evaluate("document.getElementById('command-bar').open()")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Escape")
    assert page.locator("[role=dialog]").count() == 0 and act is None


def test_status_line_always_shows_the_mic_and_mutes_in_one_tap(hub):
    page = hub.scene("component:status-line")
    got = events(page, "jv-act")
    assert page.locator("#stage .jv-status-line__mic").count() == page.locator("#stage jv-status-line").count()
    page.locator("[data-state=listening] button").click()
    page.locator("[data-state=muted] button").click()
    assert [g["action"] for g in got()] == ["mute", "unmute"]
    assert "It will reconnect on its own" in page.locator("[data-state=offline-says-what-to-do]").inner_text()


def test_day_plant_grows_with_done_items_and_never_scolds(hub):
    page = hub.scene("component:plant")
    leaves = lambda state: page.locator(f"[data-state={state}] .jv-leaf").count()  # noqa: E731
    assert leaves("morning-0-of-6") < leaves("afternoon-4-of-6") < leaves("all-done-blooms")
    assert page.locator("[data-state=all-done-blooms] .jv-plant__petal").count() == 5
    assert page.locator("[data-state=afternoon-4-of-6] svg").get_attribute("aria-label") == "Day plant: 4 of 6 done today"


def test_chart_has_a_real_table_and_timeline_marks_now(hub):
    page = hub.scene("component:mini-chart")
    assert page.locator("[data-state=bars-with-a-target] table tbody tr").count() == 4
    page = hub.scene("component:timeline")
    day = page.locator("[data-state=a-normal-day]")
    assert day.locator(".jv-timeline__item--done").count() == 4 and day.locator(".jv-timeline__now").count() == 1
    assert "twice the estimate" in day.inner_html()


def test_big_number_and_branch_card(hub):
    page = hub.scene("component:big-number")
    soon = page.locator("[data-state=due-soon-within-72-h]").inner_text()
    assert "2 d 4 h" in soon and "due soon" in soon.lower() and "50%" in soon
    assert "due soon" not in page.locator("[data-state=due-later]").inner_text().lower()
    page = hub.scene("component:branch-card")
    course = page.locator("[data-state=a-course]")
    assert course.locator("article > section").count() <= 3 and course.locator("details").count() == 0
    assert [h.strip() for h in course.locator("h4").all_text_contents()] == ["Due soon", "Next", "Key fact"] and course.locator("button").count() == 1
    assert "hasn't learned anything" in page.locator("[data-state=nothing-learned-yet]").inner_text()


def test_status_line_follows_the_orb_he_sees(hub):
    # film review S2: "LISTENING · BALANCED" showed under a standby sphere, and "Balanced" is a setting, not a state
    page = hub.scene("now-ambient")
    page.wait_for_function("document.querySelector('.jv-amb__orb')?.getAttribute('state') === 'standby'")
    words = " ".join(page.inner_text("#status .jv-status-line__text").split()).lower()
    assert words.startswith("standby · mic on") and "balanced" not in words and "listening" not in words, words
    page = hub.scene("now-awake")  # "On the hub", awake: the corner orb is idle, so the line says Listening
    assert " ".join(page.inner_text("#status .jv-status-line__text").split()).lower() == "listening"
    page = hub.scene("component:status-line")
    assert "quiet" in page.inner_text("[data-state=thinking-quiet-dial]").lower()
    assert hub.problems == []


def test_now_card_leads_with_content_not_a_greeting(hub):
    # walkthrough: "GOOD AFTERNOON" as the now card's heading felt mechanical
    page = hub.scene("component:now-card")
    text = page.locator("[data-state=a-normal-afternoon] jv-now-card").inner_text().lower()
    assert "good afternoon" not in text and page.locator("[data-state=a-normal-afternoon] jv-now-card h2").count() == 0
    assert text.split("\n")[0].strip() == "4 of 6 done today" and "review ge 122 lecture 21" in text
    assert hub.problems == []


def test_approval_footer_follows_the_yes_window(hub):
    # walkthrough: "Say yes or no, or tap" stayed after the yes window closed (voice then needs a fresh wake)
    page = hub.scene("now-waiting")
    wait = "jv-approval-card .jv-approval-card__wait"
    assert page.inner_text(wait).startswith("Say yes or no, or tap.")
    page.evaluate("window.__jarvis.store.apply({v: 1, type: 'orb.state', ts: '', data: {state: 'idle'}})")
    page.wait_for_function(f"document.querySelector('{wait}').textContent.startsWith('Tap to answer, or wake Jarvis and say it.')")
    assert "It waits until 9:00 pm" in page.inner_text(wait)
    assert hub.problems == []
