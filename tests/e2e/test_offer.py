"""The hidden trick on the HUD v3 home (HUD v2 §6.4, §9.5, §10; v3 §14): the return offer is never a permanent
line. It is Jarvis's caption while he says it, and otherwise one small glass card under the orb, only while the
offer is live: gone once answered, declined, ignored or answered by doing something else. PPS 7 still opens at
question 7 from the offer and from the icon row."""
STATE = "window.__jarvis.store.state"
CARD = ".jv-now__ambient .jv-amb__offer"
OFFER = "import('/views/now/offer.js')"


def at_q7(page):
    page.wait_for_function("window.__jarvis.router.current.path === '/read/th-pps7'")
    page.wait_for_function("document.querySelector('.jv-reader__bar')?.innerText.toUpperCase().includes('Q7 OF')", timeout=15_000)


def test_no_offer_no_card_and_a_live_offer_is_one_small_glass_card_under_the_orb(hub):
    page = hub.scene("now-calm", theme="night")  # PPS 7 was last touched two days ago: the icon row has it, the home is empty
    assert page.locator(CARD).count() == 0 and page.locator(".jv-amb__lead, .jv-amb__resume").count() == 0
    for w, h in ((1920, 1080), (1440, 900), (1280, 720)):
        hub.page.set_viewport_size({"width": w, "height": h})
        for scene in ("now-offer", "now-ambient-resume"):
            page = hub.scene(scene, theme="night")
            assert page.locator(CARD).count() == 1
            got = page.evaluate("""() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
                const card = r('.jv-amb__offer'), orb = r('.jv-amb__orb'), foot = r('#foot'), where = document.querySelector('.jv-amb__offer-where');
                const time = document.querySelector('.jv-amb__time:not([hidden])')?.getBoundingClientRect();
                const cs = getComputedStyle(document.querySelector('.jv-amb__offer'));
                return { top: card.top, bottom: card.bottom, w: card.width, h: card.height, cx: card.left + card.width / 2, orbCx: orb.left + orb.width / 2,
                         orbCy: orb.top + orb.height / 2, foot: foot.top, timeBottom: time ? time.bottom : 0, cut: where.scrollWidth > where.clientWidth + 1,
                         alpha: cs.backgroundColor, blur: cs.backdropFilter, radius: cs.borderTopLeftRadius,
                         scroll: document.getElementById('stage').scrollHeight - document.getElementById('stage').clientHeight }; }""")
            assert got["top"] > got["orbCy"] and got["top"] >= got["timeBottom"] and abs(got["cx"] - got["orbCx"]) < 2, (w, h, scene, got)
            assert got["bottom"] < got["foot"] and got["scroll"] <= 1, (w, h, scene, got)  # clear of the icon row, nothing scrolls
            assert got["w"] <= 440 and got["h"] <= 64 and not got["cut"], (w, h, scene, got)  # small, and the words are whole
            assert got["alpha"].startswith("rgba(") and got["blur"] in ("none", "") and got["radius"] == "0px", got  # glass: see-through, square, no blur
            assert page.inner_text(".jv-amb__offer-where") == "PPS 7 · Q7 · Today"
    assert hub.problems == []


def test_a_tap_on_the_offer_opens_pps7_at_q7_with_no_second_card(hub):
    page = hub.scene("now-offer", theme="night")
    page.click(f"{CARD} .jv-amb__offer-go")
    at_q7(page)
    page.wait_for_function("document.querySelector('jv-view-reader')?.dataset.locked === 'Q7'", timeout=15_000)  # the brackets lock onto Q7
    assert page.locator("jv-resume-card:not([lifted])").count() == 0  # his tap was the yes
    assert hub.state("s => s.threads.find((t) => t.id === 'th-pps7').resume.source") == "confirmed"
    assert hub.state("s => s.ui.offers['th-pps7'].how") == "accept"
    page.evaluate("window.__jarvis.router.go('/now')")
    page.wait_for_selector(".jv-now__ambient jv-orb")
    assert page.locator(CARD).count() == 0  # answered: it does not come back for the same spot
    page.evaluate("window.__jarvis.store.setUi({ ambient: true }); window.__jarvis.store.setUi({ ambient: false })")
    page.wait_for_timeout(100)
    assert page.locator(CARD).count() == 0  # not even after he leaves and comes back
    assert hub.problems == []


def test_pps7_opens_at_q7_from_the_icon_row(hub):
    page = hub.scene("now-offer", theme="night")
    page.click("#rail [data-slot=homework]")  # he opens an icon instead: that's his answer, the card goes
    page.wait_for_selector(".jv-rail__fan")
    page.wait_for_function(f"!document.querySelector('{CARD}')")
    assert hub.state("s => s.ui.offers['th-pps7'].how") == "acted"
    page.click(".jv-rail__fan [data-ref=file-pps7]")
    at_q7(page)
    page.click("jv-resume-card .jv-btn--primary")  # "Carry on at Q7"
    page.wait_for_function("document.querySelector('jv-view-reader')?.dataset.locked === 'Q7'", timeout=15_000)
    assert hub.state("s => s.threads.find((t) => t.id === 'th-pps7').resume.source") == "confirmed"
    assert hub.problems == []


def test_not_now_takes_it_away_quietly_until_he_leaves_and_comes_back(hub):
    page = hub.scene("now-offer", theme="night")
    said = hub.state("s => (s.rail.slots.jarvis.said || []).length")
    page.click(f"{CARD} .jv-amb__offer-no")
    page.wait_for_function(f"!document.querySelector('{CARD}')")
    assert hub.state("s => s.ui.offers['th-pps7'].how") == "notnow"
    assert hub.state("s => (s.rail.slots.jarvis.said || []).length") == said and page.locator("jv-toast, .jv-toast").count() == 0  # not a word
    assert page.locator("#rail [data-slot=homework]").is_visible()  # it stays on the Homework icon
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'orb.state', ts: '', data: {state: 'thinking'}})")
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'orb.state', ts: '', data: {state: 'idle'}})")
    page.wait_for_timeout(100)
    assert page.locator(CARD).count() == 0  # still declined while he stays
    page.evaluate("window.__jarvis.store.setUi({ ambient: true })")
    page.wait_for_timeout(50)
    assert page.locator(CARD).count() == 0
    page.evaluate("window.__jarvis.store.setUi({ ambient: false })")  # he left and came back: something changed
    page.wait_for_selector(CARD)
    assert hub.problems == []


def test_ignored_it_folds_into_the_icon_row_and_going_elsewhere_is_an_answer(hub):
    hub.page.clock.install()
    page = hub.scene("now-offer", theme="night")
    page.wait_for_selector(CARD)
    ignore_ms = page.evaluate(f"{OFFER}.then((m) => m.IGNORE_MS)")
    page.clock.fast_forward(ignore_ms - 2_000)
    assert page.locator(CARD).count() == 1
    page.clock.fast_forward(3_000)
    page.wait_for_function(f"!document.querySelector('{CARD}')")
    assert hub.state("s => s.ui.offers['th-pps7'].how") == "ignored"
    page = hub.scene("now-offer", theme="night")  # a fresh one; he goes to Today instead
    page.wait_for_selector(CARD)
    page.click("#rail .jv-page-dots__dot[data-key=today]")
    page.wait_for_function("location.hash === '#/today'")
    assert hub.state("s => s.ui.offers['th-pps7'].how") == "acted"
    page.click("#rail .jv-page-dots__dot[data-key=now]")
    page.wait_for_selector(".jv-now__ambient jv-orb")
    assert page.locator(CARD).count() == 0


def test_spoken_it_is_the_caption_and_the_card_waits_until_he_stops(hub):
    page = hub.scene("now-offer-spoken", theme="night")
    assert page.is_visible("#caption .jv-caption") and "PPS 7" in page.inner_text("#caption .jv-caption")
    assert page.locator(CARD).count() == 0  # one thing at a time: his line has the floor
    box = page.locator("#caption .jv-caption").bounding_box(), page.locator("#rail").bounding_box()
    assert box[0]["y"] + box[0]["height"] <= box[1]["y"] + 1  # above the icon row
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'orb.state', ts: '', data: {state: 'idle'}})")
    page.wait_for_selector(CARD)  # he stopped: the offer can still be taken with a tap
    page.wait_for_function("!document.querySelector('#caption .jv-caption')")
    assert hub.problems == []


def test_others_present_mornings_and_private_branches_get_no_offer(hub):
    page = hub.scene("now-offer", theme="night")
    got = page.evaluate(f"""{OFFER}.then((m) => {{ const s = structuredClone({STATE}), now = '2026-11-16T15:40:00';
        const live = m.resumeOffer(s, now);
        const others = m.resumeOffer({{ ...s, presence: {{ here: true, others: true }} }}, now);
        const old = m.resumeOffer(s, '2026-11-16T19:40:00');  // four hours on: the icon row keeps it
        const justLeft = m.resumeOffer(s, '2026-11-16T15:06:00');  // not the moment he puts it down
        const morning = m.resumeOffer({{ ...s, threads: s.threads.map((t) => t.id === 'th-pps7' ? {{ ...t, resume: {{ ...t.resume, at: '2026-11-16T03:30:00' }} }} : t) }}, '2026-11-16T05:00:00');
        const tier2 = m.resumeOffer({{ ...s, branches: s.branches.map((b) => b.id === s.threads.find((t) => t.id === 'th-pps7').branch ? {{ ...b, tier: 2 }} : b) }}, now);
        const done = m.resumeOffer({{ ...s, threads: s.threads.map((t) => t.id === 'th-pps7' ? {{ ...t, state: 'done' }} : t) }}, now);
        return {{ live: live && [live.thread.id, live.words, live.to], others, old, justLeft, morning, tier2, done }}; }})""")
    assert got["live"] == ["th-pps7", "PPS 7 · Q7 · Today", "/read/th-pps7"]
    assert [got[k] for k in ("others", "old", "justLeft", "morning", "tier2", "done")] == [None] * 6, got
    page.evaluate("window.__jarvis.store.apply({v: 2, type: 'presence.changed', ts: '', data: {here: true, others: true}})")
    page.wait_for_function(f"!document.querySelector('{CARD}')")  # someone walks in: nothing personal stays up
