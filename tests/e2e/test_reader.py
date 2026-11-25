"""N6 in a real browser: the reader opens a work thread's PDF at its resume point behind the resume card,
answers to accept / scroll / leave, and lands warm on Q7 within the target. The PDF is generated here."""
import os
import socket
import threading
import time

import pytest

pymupdf = pytest.importorskip("pymupdf")

WARM_TARGET_MS = 400  # HUD v2 §10.1: warm open to Q7
SLACK = float(os.environ.get("JARVIS_PERF_SLACK", "1.5"))  # shared test machines are slower than his laptops
NOW = "2026-11-16T15:40:00"
TITLE = "Test set"


def _make_set(path, questions=12):
    doc = pymupdf.open()
    per_page, n = 3, 1
    while n <= questions:
        page = doc.new_page(width=612, height=792)
        for slot in range(per_page):
            if n > questions:
                break
            y = 90 + slot * 230
            page.insert_text((72, y), f"Question {n}", fontsize=12, fontname="hebo")
            page.insert_text((72, y + 22), "Find the reactions at the supports and draw the free-body diagram.", fontsize=11)
            n += 1
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def reader_hub(tmp_path_factory):
    """A hub of its own (the shared one can't be given threads): demo files and caches in a temp folder."""
    import uvicorn

    from jarvis_hub import threads
    from jarvis_hub.server import create_app

    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(tmp_path_factory.mktemp("appdata"))
    pdf = tmp_path_factory.mktemp("files") / "set.pdf"
    _make_set(pdf)
    threads.register_file("file-e2e-set", pdf)
    app = create_app(autoplay=False, speed=0)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.025)
    yield app, f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
    threads.forget_file("file-e2e-set")
    if old is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = old


def put_thread(app, thread_id, resume, done=()):
    from jarvis_hub import pdfindex

    q = {x["label"]: x for x in pdfindex.load_index("file-e2e-set")["questions"]}
    if resume in ("q7", "q8"):
        label = resume.upper()
        resume = {"page": q[label]["page"], "y": q[label]["y"], "label": label, "source": "inferred", "at": "2026-11-14T21:14:00"}
    thread = {"id": thread_id, "kind": "pdf", "ref": "file-e2e-set", "branch": "ge-122", "title": TITLE,
              "resume": resume, "done": list(done), "viewed": [], "state": "paused", "updated": NOW}
    app.state.hub.publish("thread.updated", {"thread": thread})
    return thread


def _with_reader(route):
    """ui/views/index.js is the overseer's: until it imports the reader, the test adds the one line."""
    response = route.fetch()
    text = response.text()
    if "reader/reader.js" not in text:
        text += '\nimport "./reader/reader.js";\n'
    route.fulfill(response=response, body=text)


class Page:
    def __init__(self, page, base):
        self.page, self.base, self.problems = page, base, []
        page.route("**/views/index.js", _with_reader)
        page.on("console", lambda m: self.problems.append(m.text) if m.type == "error" and "404" not in m.text else None)
        page.on("pageerror", lambda e: self.problems.append(str(e)))
        # thumbnails are N5a's route; until it lands they 404 and the card shows its monogram instead
        page.on("response", lambda r: self.problems.append(f"{r.status} {r.url}") if r.status >= 400 and "/api/thumb/" not in r.url else None)

    def open(self, hash_path="", **query):
        q = "&".join(f"{k}={v}" for k, v in query.items())
        self.page.goto(f"{self.base}/{'?' + q if q else ''}{'#' + hash_path if hash_path else ''}")
        self.page.wait_for_selector("html[data-ready]", timeout=10_000)
        return self.page

    def landed(self, timeout=10_000):
        self.page.wait_for_selector("jv-view-reader[data-landed-ms]", timeout=timeout)
        return int(self.page.get_attribute("jv-view-reader", "data-landed-ms"))

    def thread(self, thread_id):
        return self.page.evaluate(f"window.__jarvis.store.state.threads.find((t) => t.id === '{thread_id}')")


@pytest.fixture
def reader(browser, reader_hub):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(8_000)
    yield Page(page, reader_hub[1])
    context.close()


def test_reopen_lands_on_q7_behind_the_card_and_warm_open_is_fast(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-warm", "q7", done=[f"Q{n}" for n in range(1, 7)])
    page = reader.open("/read/th-e2e-warm")
    cold = reader.landed()
    card = page.locator("jv-resume-card")
    assert card.is_visible()
    assert "1–6" in card.locator("[data-line]").inner_text() or "6" in card.locator("[data-line]").inner_text()
    assert "Q7" in card.inner_text()
    assert "Q7 of 12" in page.locator("#rd-where").text_content()
    # Q7's heading is on the sheet, below the card, not hidden under it
    heading_top = page.evaluate("""() => { const v = document.querySelector('jv-view-reader');
        const sheet = v.querySelector('.jv-reader__sheet').getBoundingClientRect();
        const card = v.querySelector('jv-resume-card').getBoundingClientRect();
        const q = v.index.questions.find((x) => x.label === 'Q7'), pv = v._viewer.getPageView(q.page - 1);
        const [, y] = pv.viewport.convertToViewportPoint(0, pv.viewport.viewBox[3] - q.y);
        const top = pv.div.getBoundingClientRect().top + y;
        return { top, cardBottom: card.bottom, sheetBottom: sheet.bottom }; }""")
    assert heading_top["cardBottom"] <= heading_top["top"] < heading_top["sheetBottom"]
    # leave without doing anything (a glance keeps the spot), come back: warm
    page.evaluate("location.hash = '#/now'")
    page.wait_for_selector("jv-view-now")
    page.evaluate("location.hash = '#/read/th-e2e-warm'")
    page.wait_for_function("document.querySelector('jv-view-reader')?.dataset.landedMs")
    warm = int(page.get_attribute("jv-view-reader", "data-landed-ms"))
    print(f"\nreader: cold open {cold} ms, warm open to Q7 {warm} ms (target {WARM_TARGET_MS} ms)")
    assert warm <= WARM_TARGET_MS * SLACK
    assert reader.thread("th-e2e-warm")["resume"]["label"] == "Q7"
    assert reader.problems == []


def test_accept_confirms_and_locks_the_brackets_on_q7(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-accept", "q7")
    page = reader.open("/read/th-e2e-accept")
    reader.landed()
    page.keyboard.press("Enter")  # the card's main answer has focus
    page.wait_for_selector("jv-resume-card[lifted]", state="attached")
    page.wait_for_function("window.__jarvis.store.state.threads.find((t) => t.id === 'th-e2e-accept').resume.source === 'confirmed'")
    assert page.get_attribute("jv-view-reader", "data-locked") == "Q7"
    assert page.locator(".jv-reader__lock").count() == 1
    assert reader.problems == []


def test_scrolling_is_the_answer_card_lifts_silently(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-ignore", "q7")
    page = reader.open("/read/th-e2e-ignore")
    reader.landed()
    page.mouse.move(700, 600)
    page.mouse.wheel(0, 300)
    page.wait_for_selector("jv-resume-card", state="detached")
    assert reader.thread("th-e2e-ignore")["resume"]["source"] == "inferred"  # no accept was sent
    assert reader.problems == []


def test_leaving_saves_the_spot_silently(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-save", "q7")
    page = reader.open("/read/th-e2e-save")
    reader.landed()
    page.mouse.move(700, 600)
    page.mouse.wheel(0, 200)  # he moves on: the card goes
    page.wait_for_selector("jv-resume-card", state="detached")
    page.wait_for_timeout(300)  # the wheel's own scroll settles
    page.evaluate("""() => { const v = document.querySelector('jv-view-reader');
        const q = v.index.questions.find((x) => x.label === 'Q11'); v.jumpTo(q.page, q.y); }""")
    page.wait_for_function("document.querySelector('#rd-where').textContent.includes('Q11')")
    page.evaluate("location.hash = '#/now'")
    page.wait_for_function("window.__jarvis.store.state.threads.find((t) => t.id === 'th-e2e-save').resume.label !== 'Q7'")
    resume = reader.thread("th-e2e-save")["resume"]
    assert resume["page"] == 4 and resume["source"] == "inferred"
    assert resume["label"] in ("Q11", "Page 4")
    assert reader.problems == []


def test_a_fresh_pdf_opens_at_the_top_with_no_card(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-fresh", None)
    page = reader.open("/read/th-e2e-fresh")
    reader.landed()
    assert page.locator("jv-resume-card").count() == 0
    assert page.locator("#rd-page").text_content().startswith("P. 1 /")
    assert page.evaluate("document.querySelector('#rd-scroll').scrollTop") < 40  # the first page's top edge


def test_a_weak_spot_offers_the_page(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-weak", {"page": 3, "label": "Page 3", "source": "inferred", "at": "2026-11-14T21:14:00"})
    page = reader.open("/read/th-e2e-weak")
    reader.landed()
    card = page.locator("jv-resume-card")
    assert "page 3" in card.locator("[data-choice=accept]").inner_text()
    assert "PAGE 3" in card.inner_text().upper()


def test_why_shows_solutions_viewed_only_when_alone(reader, reader_hub):
    thread = put_thread(reader_hub[0], "th-e2e-why", "q7")
    reader_hub[0].state.hub.publish("thread.updated", {"thread": {**thread, "viewed": ["Q4"]}})
    page = reader.open("/read/th-e2e-why")
    reader.landed()
    card = page.locator("jv-resume-card")
    assert "Solutions" not in card.inner_text()  # never on the face of the card
    card.locator("[data-key=why]").click()
    assert "Solutions you looked at: 4." in card.inner_text()
    page.evaluate("(c => { c.private = true; })(document.querySelector('jv-resume-card'))")
    page.wait_for_timeout(50)
    assert "Solutions" not in card.inner_text()


@pytest.mark.parametrize("theme", ["night", "day"])
@pytest.mark.parametrize("scene", ["reader-fresh", "reader-resume", "reader-weak", "reader-accepted"])
def test_reader_scenes_draw_cleanly(reader, scene, theme):
    page = reader.open(scene=scene, theme=theme)
    reader.landed()
    assert (page.locator("jv-resume-card").count() == 1) == (scene in ("reader-resume", "reader-weak"))
    if scene == "reader-accepted":
        assert page.get_attribute("jv-view-reader", "data-locked") == "Q7"
    assert reader.problems == []


def test_resume_card_gallery_and_no_repeats_in_a_row(reader):
    page = reader.open(scene="component:resume-card", theme="night")
    lines = page.locator("jv-resume-card [data-line]").all_inner_texts()
    assert len(lines) == 9
    assert all(a != b for a, b in zip(lines, lines[1:], strict=False))  # the card never shows the same line twice running
    assert not any(word in " ".join(lines) for word in ("Resumed", "Bookmark", "!", "Welcome back"))


# ---- final-fix R1: his question is never lost, the card's focus, words and timing ----------------------------------
SINCE = "(id) => window.__jarvis.store.state.threads.find((t) => t.id === id).resume"


def _leave(page, thread_id, seconds):
    """He sat `seconds` on the sheet (the session clock, without the wait), then leaves: the spot is saved."""
    page.evaluate(f"document.querySelector('jv-view-reader').session.seconds = {seconds}")
    before = page.evaluate(f"({SINCE})('{thread_id}').at")
    page.evaluate("location.hash = '#/now'")
    page.wait_for_function(f"({SINCE})('{thread_id}').at !== '{before}'")
    return page.evaluate(f"({SINCE})('{thread_id}')")


def test_carry_on_at_q8_then_idle_keeps_q8(reader, reader_hub):
    """Walkthrough B1: "Carry on at Q8", 20 s idle, close. It used to save "Page 3" and reopen at Q7."""
    put_thread(reader_hub[0], "th-e2e-q8", "q8")
    page = reader.open("/read/th-e2e-q8")
    reader.landed()
    assert "Q8 of 12" in page.locator("#rd-where").text_content()
    # the empty space above Q8's heading is Q8's, not Q7's: only Q8 is in view
    assert page.evaluate("document.querySelector('jv-view-reader').where().visible") == ["Q8"]
    page.keyboard.press("Enter")
    page.wait_for_function(f"({SINCE})('th-e2e-q8').source === 'confirmed'")
    resume = _leave(page, "th-e2e-q8", 20)
    assert (resume["label"], resume["source"]) == ("Q8", "confirmed")
    page.evaluate("location.hash = '#/read/th-e2e-q8'")
    page.wait_for_function("document.querySelector('jv-view-reader')?.dataset.landedMs")
    assert "Q8 of 12" in page.locator("#rd-where").text_content()
    assert page.locator("jv-resume-card").count() == 0  # answered minutes ago: just the spot, no card again
    assert reader.problems == []


def test_another_question_q8_closed_3_s_later_keeps_q8(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-pick", "q7")
    page = reader.open("/read/th-e2e-pick")
    reader.landed()
    card = page.locator("jv-resume-card")
    card.locator("[data-key=pick]").click()
    card.locator("[data-label=Q8]").click()
    page.wait_for_function("document.querySelector('#rd-where').textContent.includes('Q8')")
    assert page.evaluate("document.activeElement.id") == "rd-scroll"
    resume = _leave(page, "th-e2e-pick", 3)
    assert (resume["label"], resume["source"]) == ("Q8", "confirmed")
    assert reader.problems == []


def test_esc_on_the_card_gives_focus_to_the_sheet(reader, reader_hub):
    """a11y MUST 2: Esc on the card used to drop focus to <body>; Tab then skipped the sheet."""
    put_thread(reader_hub[0], "th-e2e-esc", "q7")
    page = reader.open("/read/th-e2e-esc")
    reader.landed()
    page.locator("jv-resume-card [data-choice=accept]").focus()
    page.keyboard.press("Escape")
    page.wait_for_selector("jv-resume-card", state="detached")
    assert page.evaluate("document.activeElement.id") == "rd-scroll"
    assert reader.thread("th-e2e-esc")["resume"]["source"] == "inferred"  # Esc is not a yes
    # the text layers are not tab stops of their own
    assert page.evaluate("[...document.querySelectorAll('#rd-scroll .textLayer')].every((t) => t.tabIndex === -1)")


def test_the_card_stays_away_once_answered(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-once", "q7")
    page = reader.open("/read/th-e2e-once")
    reader.landed()
    page.keyboard.press("Enter")
    page.wait_for_selector("jv-resume-card", state="detached")
    page.wait_for_timeout(4500)  # the walkthrough saw it come back about 4 s after the yes
    assert page.locator("jv-resume-card").count() == 0
    page.evaluate("location.hash = '#/now'")
    page.wait_for_selector("jv-view-now")
    page.evaluate("location.hash = '#/read/th-e2e-once'")
    page.wait_for_function("document.querySelector('jv-view-reader')?.dataset.landedMs")
    assert page.locator("jv-resume-card").count() == 0


def test_a_weak_spot_on_page_1_offers_one_way_in(reader, reader_hub):
    """Never "Carry on at page 1" next to "From the top": they're the same answer."""
    put_thread(reader_hub[0], "th-e2e-p1", {"page": 1, "label": "Page 1", "source": "inferred", "at": "2026-11-14T21:14:00"})
    page = reader.open("/read/th-e2e-p1")
    reader.landed()
    card = page.locator("jv-resume-card")
    assert "page 1" in card.locator("[data-choice=accept]").inner_text()
    assert card.locator("[data-choice=top]").count() == 0
    assert "Somewhere" not in card.inner_text()


def test_the_card_makes_room_only_where_it_covers_the_page(browser, reader_hub):
    """N8's note: room above the heading only when the card really lies over the top of the page (not on phone)."""
    put_thread(reader_hub[0], "th-e2e-room", "q7")
    for viewport, covers in (({"width": 1280, "height": 720}, True), ({"width": 390, "height": 844}, False)):
        context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        r = Page(context.new_page(), reader_hub[1])
        page = r.open("/read/th-e2e-room")
        r.landed()
        got = page.evaluate("""() => { const v = document.querySelector('jv-view-reader');
            const card = v.querySelector('jv-resume-card').getBoundingClientRect();
            const q = v.index.questions.find((x) => x.label === 'Q7'), pv = v._viewer.getPageView(q.page - 1);
            const [, y] = pv.viewport.convertToViewportPoint(0, pv.viewport.viewBox[3] - q.y);
            return { covered: v.covered(), top: pv.div.getBoundingClientRect().top + y, cardTop: card.top, cardBottom: card.bottom }; }""")
        assert (got["covered"] > 0) == covers, (viewport, got)
        assert got["top"] >= got["cardBottom"] or got["top"] < got["cardTop"]  # the heading is never under the card
        context.close()


def test_double_click_on_close_goes_back_once(reader, reader_hub):
    put_thread(reader_hub[0], "th-e2e-close", "q7")
    page = reader.open("/today")
    page.evaluate("location.hash = '#/read/th-e2e-close'")
    reader.landed()
    page.locator("#rd-close").dblclick()
    page.wait_for_selector("jv-view-today")
    page.wait_for_timeout(300)
    assert page.evaluate("location.hash") == "#/today"
