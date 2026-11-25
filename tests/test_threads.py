"""N6: work threads and resume points: the question index, the inference rules, files for the reader, and the
save / accept round trip. PDFs are generated here with PyMuPDF (never his files)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

pymupdf = pytest.importorskip("pymupdf")

from jarvis_hub import pdfindex, threads  # noqa: E402
from jarvis_hub.demo.fixtures import load_state  # noqa: E402
from jarvis_hub.events import Hub  # noqa: E402
from jarvis_hub.server import create_app  # noqa: E402
from tests.test_contracts import validator  # noqa: E402

NOW = "2026-11-16T15:40:00"


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    """Every test gets its own Jarvis data folder (index, thumbnails, side store, demo files)."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    yield tmp_path
    for file_id in list(threads._files):
        threads.forget_file(file_id)


def make_pdf(path, pages, size=(612, 792)):
    """pages: [[(x, y, text, fontsize, font), ...], ...]  (y = baseline, from the top)."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=size[0], height=size[1])
        for x, y, text, fontsize, font in lines:
            page.insert_text((x, y), text, fontsize=fontsize, fontname=font)
    doc.save(str(path))
    doc.close()
    return path


def body(x, y, text="Find the reactions at the supports and draw the free-body diagram."):
    return (x, y, text, 11, "helv")


def labels(index):
    return [(q["label"], q["page"]) for q in index["questions"]]


# ---- the question index ------------------------------------------------------------------------------------------
def test_numbered_set_with_parts_and_distractors(cache):
    pdf = make_pdf(cache / "numbered.pdf", [
        [(72, 60, "GE 122 Problem-Solving Set 7", 16, "hebo"),
         (72, 120, "1. A beam AB of length 4 m carries a point load.", 11, "helv"), body(90, 136),
         (72, 260, "2. Find the reactions at A and B.", 11, "helv"), body(90, 276),
         (180, 300, "3. an indented number inside the text is not a question", 11, "helv"),
         (72, 700, "3. A footnote in small type is not a question.", 7, "helv"),
         (300, 770, "1", 9, "helv")],
        [(72, 90, "3. Draw the free-body diagram for the truss.", 11, "helv"), body(90, 106),
         (96, 160, "(a) Find the support reactions.", 11, "helv"),
         (96, 200, "(b) Find the force in member BC.", 11, "helv"),
         (72, 260, "1. A list inside question 3 restarts its numbers", 11, "helv"),
         (72, 280, "2. and is not a new question.", 11, "helv"),
         (72, 420, "4. Locate the centroid of the plate.", 11, "helv"), body(90, 436)],
    ])
    index = pdfindex.build_index(pdf)
    assert labels(index) == [("Q1", 1), ("Q2", 1), ("Q3", 2), ("Q3a", 2), ("Q3b", 2), ("Q4", 2)]
    q3 = next(q for q in index["questions"] if q["label"] == "Q3")
    assert abs(q3["y"] - (90 - 11)) < 4  # the top of the heading line, in points from the top of the page
    assert index["pages"] == 2 and index["solutions"] is False


def test_keyword_headings_beat_bare_numbers_and_must_ascend(cache):
    pdf = make_pdf(cache / "keyword.pdf", [
        [(72, 100, "Question 1", 12, "hebo"), body(72, 120),
         (72, 140, "1. a numbered step inside question 1", 11, "helv"),
         (72, 160, "2. another step", 11, "helv"),
         (72, 260, "Question 2: Trusses", 12, "hebo"), body(72, 280),
         (72, 320, "Use the answer from Problem 1 here (a reference, mid-line).", 11, "helv")],
        [(72, 100, "Problem 3a", 12, "hebo"), body(72, 120),
         (72, 220, "Problem 3b", 12, "hebo"), body(72, 240),
         (72, 320, "Question 2 asked about trusses; this line looks back.", 11, "helv"),
         (72, 420, "Q4", 12, "hebo"), body(72, 440),
         (72, 520, "Problem 4.2 is a section number, not a question", 11, "helv")],
    ])
    index = pdfindex.build_index(pdf)
    assert labels(index) == [("Q1", 1), ("Q2", 1), ("Q3a", 2), ("Q3b", 2), ("Q4", 2)]


def test_q_style_and_solutions_sheet(cache):
    pdf = make_pdf(cache / "solutions.pdf", [
        [(72, 60, "PPS 7 Solutions", 16, "hebo"), (72, 120, "Q1", 11, "hebo"), body(72, 140),
         (72, 300, "Q2", 11, "hebo"), body(72, 320), (72, 500, "Q3", 11, "hebo"), body(72, 520)],
    ])
    index = pdfindex.build_index(pdf)
    assert labels(index) == [("Q1", 1), ("Q2", 1), ("Q3", 1)]
    assert index["solutions"] is True


def test_a_page_with_no_questions_gives_an_empty_index(cache):
    index = pdfindex.build_index(make_pdf(cache / "notes.pdf", [[body(72, 100), body(72, 120)]]))
    assert index["questions"] == []


def test_the_demo_set_is_indexed_fast_with_q7_on_page_3(cache):
    path = threads.file_path("file-pps7")
    assert path and path.suffix == ".pdf"
    started = time.perf_counter()
    index = pdfindex.build_index(path)
    assert (time.perf_counter() - started) * 1000 < 300  # ~1 ms a page; generous for a busy test machine
    tops = [q["label"] for q in index["questions"] if not q["part"]]
    assert tops == [f"Q{n}" for n in range(1, 13)]
    q7 = next(q for q in index["questions"] if q["label"] == "Q7")
    assert q7["page"] == 3
    assert [q["label"] for q in index["questions"] if q["n"] == 7] == ["Q7", "Q7a", "Q7b"]


# ---- files for the reader -----------------------------------------------------------------------------------------
def test_file_path_serves_demo_and_registered_files_only(cache):
    assert threads.file_path("nothing-here") is None
    assert threads.file_path("file-pps7").is_file()
    index_file = threads.file_path("file-pps7.qindex.json")
    assert json.loads(index_file.read_text())["questions"][0]["label"] == "Q1"
    pdf = make_pdf(cache / "mine.pdf", [[(72, 100, "Question 1", 12, "hebo"), (72, 300, "Question 2", 12, "hebo")]])
    threads.register_file("file-mine", pdf)
    assert threads.file_path("file-mine") == pdf
    assert labels(json.loads(threads.file_path("file-mine.qindex.json").read_text())) == [("Q1", 1), ("Q2", 1)]
    with pytest.raises(ValueError):
        threads.register_file("../etc", pdf)


def test_api_file_answers_ranges_and_the_index(cache):
    with TestClient(create_app(autoplay=False, speed=0), base_url="http://127.0.0.1") as client:
        whole = client.get("/api/file/file-pps7")
        assert whole.status_code == 200 and whole.content.startswith(b"%PDF")
        part = client.get("/api/file/file-pps7", headers={"Range": "bytes=0-99"})
        assert part.status_code == 206 and len(part.content) == 100
        index = client.get("/api/file/file-pps7.qindex.json")
        assert index.status_code == 200 and index.json()["pages"] == 5
        assert client.get("/api/file/file-nope").status_code == 404


def test_thumbnails_are_rendered_into_the_cache_not_the_repo(cache):
    pytest.importorskip("PIL")
    index = pdfindex.file_pdf("file-pps7", threads.file_path("file-pps7"))
    assert index["thumbs"]["3"] == "file-pps7-p3.webp"
    thumb = pdfindex.thumbs_dir() / "file-pps7-p3.webp"
    assert thumb.is_file() and thumb.read_bytes()[8:12] == b"WEBP"
    assert str(cache) in str(thumb)


# ---- inference ----------------------------------------------------------------------------------------------------
@pytest.fixture
def index(cache):
    return pdfindex.file_pdf("file-pps7", threads.file_path("file-pps7"), thumbs=False)


def session(**kw):
    base = {"seconds": 900, "dwell": {"Q6": 400, "Q7": 140}, "path": ["Q5", "Q6", "Q7"], "visible": ["Q7"],
            "page": 3, "y": 60, "current": "Q7"}
    return {**base, **kw}


def test_clear_case_is_the_question_inferred(index):
    r = threads.infer_resume(index, session(), NOW)
    q7 = next(q for q in index["questions"] if q["label"] == "Q7")
    assert r == {"page": 3, "y": q7["y"], "label": "Q7", "source": "inferred", "at": NOW}


def test_short_session_needs_no_dwell(index):
    assert threads.infer_resume(index, session(seconds=90, dwell={"Q7": 20}), NOW)["label"] == "Q7"


def test_weak_cases_fall_back_to_the_page(index):
    two_in_view = threads.infer_resume(index, session(visible=["Q7", "Q8"]), NOW)
    assert two_in_view == {"page": 3, "label": "Page 3", "source": "inferred", "at": NOW}
    no_dwell = threads.infer_resume(index, session(dwell={"Q7": 12}), NOW)
    assert no_dwell["label"] == "Page 3" and "y" not in no_dwell
    back_and_forth = threads.infer_resume(index, session(path=["Q7", "Q4", "Q7"]), NOW)
    assert back_and_forth["label"] == "Page 3"
    assert threads.infer_resume(None, session(), NOW)["label"] == "Page 3"  # no index: page only


def test_a_glance_keeps_the_saved_spot(index):
    saved = {"page": 3, "y": 71.2, "label": "Q7", "source": "confirmed", "at": NOW}
    assert threads.infer_resume(index, session(seconds=6, path=["Q7"]), NOW, saved=saved) is None


def _q(index, label):
    return next(q for q in index["questions"] if q["label"] == label)


def test_carry_on_at_q8_then_idle_keeps_q8_confirmed(index):
    """Walkthrough B1: he takes "Carry on at Q8", sits 20 s, closes. The space above Q8's heading used to count as
    Q7 (visible Q7 + Q8), so the save dropped to "Page 3". His choice is never downgraded by a silent save."""
    q8 = _q(index, "Q8")
    saved = {"page": 3, "y": q8["y"], "label": "Q8", "source": "confirmed", "at": "2026-11-14T21:14:00"}
    idle = {"seconds": 20, "dwell": {"Q8": 20}, "path": ["Q8"], "visible": ["Q7", "Q8"], "page": 3, "y": 140,
            "current": "Q8", "chosen": "Q8", "since": []}
    r = threads.infer_resume(index, idle, NOW, saved=saved)
    assert r == {"page": 3, "y": q8["y"], "label": "Q8", "source": "confirmed", "at": NOW}
    # the same without the session's choice (an older reader): a confirmed spot he hasn't moved off stays
    old_reader = {k: v for k, v in idle.items() if k not in ("chosen", "since")}
    assert threads.infer_resume(index, old_reader, NOW, saved=saved)["label"] == "Q8"
    # and after two corrections (offers at page level) his own choice still stands
    assert threads.infer_resume(index, idle, NOW, level="page", saved=saved)["label"] == "Q8"


def test_another_question_q8_is_confirmed_even_closed_3_s_later(index):
    q8 = _q(index, "Q8")
    saved = {"page": 3, "y": _q(index, "Q7")["y"], "label": "Q7", "source": "inferred", "at": "2026-11-14T21:14:00"}
    picked = {"seconds": 3, "dwell": {"Q7": 1, "Q8": 2}, "path": ["Q7", "Q8"], "visible": ["Q7", "Q8"], "page": 3,
              "y": 280, "current": "Q8", "corrected": True, "chosen": "Q8", "since": ["Q8"]}
    assert threads.infer_resume(index, picked, NOW, saved=saved) == {
        "page": 3, "y": q8["y"], "label": "Q8", "source": "confirmed", "at": NOW}


def test_moving_on_after_a_choice_re_decides(index):
    saved = {"page": 3, "y": _q(index, "Q8")["y"], "label": "Q8", "source": "confirmed", "at": "2026-11-14T21:14:00"}
    moved = {"seconds": 600, "dwell": {"Q8": 200, "Q9": 300}, "path": ["Q8", "Q9"], "visible": ["Q9"], "page": 4,
             "y": 60, "current": "Q9", "chosen": "Q8", "since": ["Q8", "Q9"]}
    r = threads.infer_resume(index, moved, NOW, saved=saved)
    assert (r["label"], r["source"]) == ("Q9", "inferred")
    unclear = {**moved, "visible": ["Q9", "Q10"]}  # two headings in view after he moved: the page, as before
    assert threads.infer_resume(index, unclear, NOW, saved=saved)["label"] == "Page 4"


def test_an_inferred_spot_he_never_moved_off_is_kept(index):
    """A big view (the phone shows Q8 and Q9's headings) adds nothing when he never moved off the saved question."""
    saved = {"page": 3, "y": _q(index, "Q8")["y"], "label": "Q8", "source": "inferred", "at": "2026-11-14T21:14:00"}
    sat = {"seconds": 400, "dwell": {"Q8": 400}, "path": ["Q8"], "visible": ["Q8", "Q9"], "page": 3, "y": 300,
           "current": "Q8"}
    r = threads.infer_resume(index, sat, NOW, saved=saved)
    assert (r["label"], r["source"], r["at"]) == ("Q8", "inferred", NOW)
    assert threads.infer_resume(index, sat, NOW, level="page", saved=saved)["label"] == "Page 3"  # corrected twice


def test_the_hub_keeps_his_pick_through_the_save(hub):
    """Through events.py: pick Q8 under "Another question", close 3 s later → the thread says Q8, confirmed."""
    hub.act("resume_save", "th-pps7", {"label": "Q7", "page": 3, "y": 71.2, "session": session()})
    picked = {"seconds": 3, "dwell": {}, "path": ["Q7", "Q8"], "visible": ["Q8"], "page": 3, "y": 280,
              "current": "Q8", "corrected": True, "chosen": "Q8", "since": ["Q8"]}
    assert hub.act("resume_save", "th-pps7", {"label": "Q8", "page": 3, "y": 309.6, "confirmed": True,
                                              "session": picked}) == {"ok": True}
    resume = hub.state["threads"][0]["resume"]
    assert (resume["label"], resume["source"]) == ("Q8", "confirmed")
    assert list(validator("thread").iter_errors(hub.state["threads"][0])) == []


def test_two_corrections_drop_offers_to_page_level_until_he_accepts(index):
    thread = threads.new_thread("file-pps7", "PPS 7", "ge-122")
    assert threads.offer_level(thread["id"], NOW) == "question"
    threads.on_act("resume_save", thread, {"label": "Q3", "confirmed": True, "corrected": True}, "2026-11-10T10:00:00")
    threads.merge_session(thread, session(corrected=True), "2026-11-12T10:00:00")
    assert threads.offer_level(thread["id"], NOW) == "page"
    assert threads.merge_session(thread, session(), NOW)["resume"]["label"] == "Page 3"
    threads.on_act("resume_accept", thread, {}, "2026-11-16T15:00:00")
    assert threads.offer_level(thread["id"], NOW) == "question"
    assert threads.offer_level(thread["id"], "2026-12-30T10:00:00") == "question"


def test_merge_marks_done_keeps_dwell_aside_and_stays_in_contract(index):
    thread = threads.new_thread("file-pps7", "PPS 7", "ge-122", now=NOW,
                                thumb=threads.page_thumb("file-pps7", "PPS 7", 1))
    path = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
    dwell = {"Q1": 200, "Q2": 45, "Q3": 10, "Q4": 300, "Q5": 90, "Q6": 400, "Q7": 70}
    merged = threads.merge_session(thread, session(path=path, dwell=dwell), NOW, index)
    assert merged["resume"]["label"] == "Q7" and merged["resume"]["source"] == "inferred"
    assert merged["done"] == ["Q1", "Q2", "Q4", "Q5", "Q6"]  # Q3 got 10 s: skimmed, not done
    assert merged["viewed"] == []  # not a solutions sheet
    assert merged["thumb"]["src"] == "/api/thumb/file-pps7-p3.webp"
    assert merged["state"] == "paused"
    assert list(validator("thread").iter_errors(merged)) == []
    assert threads.time_per_question(thread["id"])["Q6"] == 400
    threads.merge_session(merged, session(dwell={"Q7": 30}), NOW, index)
    assert threads.time_per_question(thread["id"])["Q7"] == 100
    assert "dwell" not in json.dumps(merged)  # time per question never goes into the thread or the state


def test_done_needs_moving_on_without_coming_back():
    idx = {"questions": [{"label": f"Q{n}"} for n in range(1, 6)]}
    assert threads.done_from(idx, {"path": ["Q1", "Q2", "Q3"], "dwell": {"Q1": 60, "Q2": 60}}, "Q3") == ["Q1", "Q2"]
    back = {"path": ["Q1", "Q2", "Q3", "Q2"], "dwell": {"Q1": 60, "Q2": 60, "Q3": 60}}
    assert threads.done_from(idx, back, "Q2") == ["Q1"]  # he went back from Q3: Q3 isn't done yet


# ---- the save / accept round trip through the hub ------------------------------------------------------------------
@pytest.fixture
def hub(index):
    state = load_state()
    state["threads"] = [threads.new_thread("file-pps7", "PPS 7", "ge-122", now=NOW)]
    return Hub(state)


def test_save_then_accept_round_trip(hub):
    thread_id = "th-pps7"
    saved = hub.act("resume_save", thread_id, {"label": "Q7", "page": 3, "y": 71.2, "session": session()})
    assert saved == {"ok": True}
    thread = hub.state["threads"][0]
    assert thread["resume"]["label"] == "Q7" and thread["resume"]["source"] == "inferred"
    assert list(validator("thread").iter_errors(thread)) == []
    assert hub.act("resume_accept", thread_id) == {"ok": True}
    assert hub.state["threads"][0]["resume"]["source"] == "confirmed"
    assert hub.state["threads"][0]["resume"]["page"] == 3


def test_the_hook_merges_the_session_when_the_hub_calls_it(hub):
    """What events.py does once N0 wires threads.on_act into resume_save (see the N6 report)."""
    thread = hub.state["threads"][0]
    merged = threads.on_act("resume_save", thread, {"label": "Page 1", "page": 1, "session": session()}, NOW)
    assert merged["resume"]["label"] == "Q7"  # the server re-decides from the session
    hub.publish("thread.updated", {"thread": merged})
    assert hub.state["threads"][0]["resume"]["label"] == "Q7"
    assert threads.on_act("resume_save", thread, {"label": "Q2", "page": 1}, NOW) is None  # explicit spot: the hub's own


def test_reopen_after_save_still_points_at_q7(hub):
    hub.act("resume_save", "th-pps7", {"label": "Q7", "page": 3, "y": 71.2, "session": session()})
    snap = hub.snapshot()
    thread = next(t for t in snap["threads"] if t["id"] == "th-pps7")
    q7 = next(q for q in pdfindex.load_index("file-pps7")["questions"] if q["label"] == "Q7")
    assert (thread["resume"]["page"], thread["resume"]["y"]) == (q7["page"], q7["y"])
