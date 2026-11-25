"""v0.18.0: the live hub is filled from his class files, his calendar, memory and the voice log, and the talker
is handed the same day as its now card. Made-up courses only: his real files never go in git."""
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.core import hub_feed
from jarvis.core.hub_feed import HubFeed, day_items, now_context
from jarvis.reach.classes import ClassContent, find_root

NOW = datetime(2026, 11, 23, 10, 30)   # a Monday


def write(root: Path, name: str, data) -> None:
    (root / "_Week Planner").mkdir(parents=True, exist_ok=True)
    (root / "_Week Planner" / name).write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def cc(tmp_path):
    root = tmp_path / "Class Content"
    meet = {"title": "Statics", "section": "01", "start_date": "2026-09-02", "end_date": "2026-12-07", "only_dates": [], "skip_dates": []}
    write(root, "schedule.json", {
        "term_label": "Fall 2026", "fetched_at": "2026-10-26T11:37:56-06:00",
        "no_class_dates": ["2026-11-11"], "no_class_reasons": {"2026-11-11": "Remembrance Day"},
        "meetings": [
            {**meet, "course": "XX 101", "type": "Lecture", "days": ["Mon", "Wed"], "start": "08:30", "end": "09:20", "building": "ARTS", "room": "101"},
            {**meet, "course": "XX 202", "type": "Lecture", "days": ["Mon"], "start": "13:00", "end": "14:20", "building": "", "room": ""},
            {**meet, "course": "XX 202", "type": "Lab", "days": ["Tue"], "start": "14:30", "end": "17:20", "building": "ENGR", "room": "2A20"},
            {**meet, "course": "XX 303", "type": "Lab", "days": ["Fri"], "start": "08:30", "end": "11:20", "building": "THORV", "room": "120",
             "only_dates": ["2026-11-23"]},
            {**meet, "course": "XX 101", "type": "Lecture", "days": ["Mon"], "start": "15:00", "end": "15:50", "building": "X", "room": "1",
             "end_date": "2026-10-01"}]})
    write(root, "homework.json", {"generated_at": "2026-11-22T21:00:00-06:00", "items": [
        {"key": "XX-101-PS7", "course": "XX 101", "title": "Problem set 7", "due": "2026-11-24T20:00:00-06:00", "platform": "Crowdmark",
         "remaining_min": 90, "status": "open", "optional": False},
        {"key": "XX-202-Quiz", "course": "XX 202", "title": "Quiz 5", "due": "2026-11-27T23:59:00-06:00", "platform": "Canvas", "status": "open"},
        {"key": "XX-101-PS6", "course": "XX 101", "title": "Problem set 6", "due": "2026-11-23T20:00:00-06:00", "status": "done"},
        {"key": "XX-202-Far", "course": "XX 202", "title": "Report", "due": "2027-01-20T20:00:00-06:00", "status": "open"}]})
    write(root, "courses.json", {"updated_at": "2026-10-26T12:30:00-06:00", "courses": [
        {"course": "XX 101", "title": "Engineering Mechanics", "instructor": "Dr. Example",
         "assessments": [{"title": "Problem sets", "weight": 10}, {"title": "Practice", "weight": 0}],
         "exams": [{"title": "Midterm 2", "start": "2026-12-01T18:00:00-06:00", "location": "ARTS 101", "weight": 25}]},
        {"course": "XX 202", "title": "Circuits", "instructor": "Dr. Other", "assessments": [], "exams": []}]})
    return ClassContent(root)


class Bus:
    def __init__(self): self.sent = []
    def publish(self, kind, data=None): self.sent.append((kind, data or {}))
    def kinds(self): return [k for k, _ in self.sent]
    def last(self, kind): return [d for k, d in self.sent if k == kind][-1]


def event(title, start, end, where=""):
    return SimpleNamespace(title=title, start=datetime(2026, 11, 23, *start), end=datetime(2026, 11, 23, *end), day=date(2026, 11, 23), where=where)


def test_the_class_files_give_his_day_rooms_and_due_work(cc):
    today = cc.meetings_on(NOW.date())
    assert [(m.course, m.kind, m.start, m.where) for m in today] == [
        ("XX 101", "class", "08:30", "ARTS 101"), ("XX 303", "lab", "08:30", "THORV 120"), ("XX 202", "class", "13:00", "")]
    assert cc.meetings_on(date(2026, 11, 11)) == [] and cc.no_class(date(2026, 11, 11)) == "Remembrance Day"
    assert [m.course for m in cc.meetings_on(date(2026, 11, 27))] == []            # the one-date lab is not every Friday
    due = cc.due(NOW)
    assert [d.title for d in due] == ["Problem set 7", "Quiz 5"]                   # done and far-off work stay out
    assert due[0].line(NOW) == "XX 101 Problem set 7 · due tomorrow 8:00 pm · Crowdmark · about 90 min left"
    assert cc.course("xx101")["instructor"] == "Dr. Example" and cc.course("circuits")["course"] == "XX 202"
    assert cc.course("nothing") is None and cc.as_of("schedule.json") == "Oct 26"
    assert [(code, e["title"]) for code, e, _ in cc.exams(NOW)] == [("XX 101", "Midterm 2")]


def test_a_missing_or_broken_file_is_an_empty_answer_never_a_crash(tmp_path):
    root = tmp_path / "Class Content"
    (root / "_Week Planner").mkdir(parents=True)
    (root / "_Week Planner" / "schedule.json").write_text("{not json", encoding="utf-8")
    cc = ClassContent(root)
    assert cc.meetings_on(NOW.date()) == [] and cc.due(NOW) == [] and cc.courses() == [] and cc.stamp("homework.json") is None
    assert find_root({"JARVIS_CLASS_CONTENT": str(root)}, tmp_path) == root
    assert find_root({}, tmp_path) is None
    (tmp_path / "OneDrive" / "Desktop" / "Class Content" / "_Week Planner").mkdir(parents=True)
    assert find_root({}, tmp_path) == tmp_path / "OneDrive" / "Desktop" / "Class Content"


def test_calendar_events_merge_onto_the_classes_without_doubling_them(cc):
    events = [event("XX 202 Lecture", (13, 0), (14, 20), "ENGR 1A10"),             # his planner's copy of a class: adds the room
              event("Review XX 101 lecture", (9, 30), (10, 0)), event("Laundry", (16, 0), (17, 30), "Basement"),
              event("Lunch with Sam", (12, 0), (12, 45)),
              SimpleNamespace(title="Reading week", start=None, end=None, day=date(2026, 11, 23), where="")]
    items = day_items(cc, events, NOW)
    assert [(i["start"], i["title"], i["kind"], i["state"]) for i in items] == [
        ("08:30", "XX 101 lecture", "class", "done"), ("08:30", "XX 303 lab", "lab", "planned"),
        ("09:30", "Review XX 101 lecture", "block", "done"), ("12:00", "Lunch with Sam", "own", "planned"),
        ("13:00", "XX 202 lecture", "class", "planned"), ("16:00", "Laundry", "laundry", "planned")]
    assert next(i for i in items if i["title"] == "XX 202 lecture")["where"] == "ENGR 1A10"
    assert len({i["id"] for i in items}) == len(items)
    assert items[0]["source"] == {"kind": "paws", "label": "PAWS · Oct 26"} and items[3]["source"]["kind"] == "calendar"


def test_the_now_card_names_what_is_next_and_the_closest_deadline(cc):
    ctx = now_context(day_items(cc, [], NOW), cc.due(NOW), NOW, note="the homework list is 9 days old")
    assert ctx.events[0] == {"title": "XX 303 lab", "when": "now, until 11:20 am", "where": "THORV 120", "source": {"kind": "paws", "label": "PAWS · Oct 26"}}
    assert ctx.events[1]["when"] == "1:00 pm" and "where" not in ctx.events[1]
    assert ctx.flag["text"] == "XX 101 Problem set 7 is due tomorrow 8:00 pm" and ctx.flag["branch_id"] == "xx-101"
    assert ctx.flag["source"] == {"kind": "crowdmark", "label": "Crowdmark"}
    assert ctx.done_today == ["XX 101 lecture"] and ctx.day == {"done": 1, "total": 3}
    card, text = hub_feed.plain_now_card(ctx, NOW)
    assert card["greeting"] == "Good morning" and card["next_up"]["title"] == "XX 303 lab"
    assert "Today: 8:30 am–9:20 am · XX 101 lecture · ARTS 101 · done" in text
    assert "Due: XX 101 Problem set 7 · due tomorrow 8:00 pm" in text and "Note: the homework list is 9 days old" in text


def test_the_feed_fills_the_hub_once_and_only_republishes_what_changed(cc, tmp_path):
    from jarvis.core.state import empty_state
    from jarvis_hub.events import apply_event

    bus = Bus()
    feed = HubFeed(bus, tmp_path, classes=cc, clock=lambda: NOW)
    asyncio.run(feed.refresh())
    state = empty_state(NOW.isoformat())
    for kind, data in bus.sent:
        apply_event(state, kind, data, NOW.isoformat())
    assert [i["title"] for i in state["day"]["items"]] == ["XX 101 lecture", "XX 303 lab", "XX 202 lecture"]
    assert state["now_card"]["next_up"]["title"] == "XX 303 lab" and state["now_card"]["flag"]["text"].startswith("XX 101 Problem set 7")
    ids = {b["id"]: b for b in state["branches"]}
    assert {"you", "school", "fall-2026", "xx-101", "xx-202", "xx-303"} <= set(ids)
    assert ids["xx-101"]["parent"] == "fall-2026" and ids["xx-101"]["due"]["label"] == "Problem set 7 · tomorrow 8:00 pm"
    card = state["cards"]["xx-101"]
    assert card["status"] == "Engineering Mechanics · Dr. Example" and card["next"][0] == {
        "title": "Lecture", "when": "Wed 8:30 am", "where": "ARTS 101", "source": {"kind": "paws", "label": "PAWS · Oct 26"}}
    assert card["due"][0]["title"] == "Problem set 7"
    names = {c["name"]: c for c in state["metrics"]["connectors"]}
    assert names["Class schedule (PAWS)"]["status"] == "ok" and names["Homework list"]["status"] == "ok"
    assert names["Google Calendar"]["status"] == "off" and names["Memory"]["status"] == "off"
    assert "Next: XX 303 lab · now, until 11:20 am · THORV 120" in feed.now_text()
    n = len(bus.sent)
    asyncio.run(feed.refresh())                                                    # nothing changed: nothing is sent
    assert len(bus.sent) == n
    feed.clock = lambda: NOW.replace(hour=11, minute=30)                           # the lab ended: the day and the card move on
    asyncio.run(feed.refresh_day())
    assert bus.kinds()[n:] == ["day.updated", "nowcard.updated"] and bus.last("nowcard.updated")["next_up"]["title"] == "XX 202 lecture"


def test_everything_the_feed_publishes_fits_the_contracts(cc, tmp_path):
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schemas = {p.name: json.loads(p.read_text()) for p in Path("contracts").glob("*.schema.json")}
    registry = Registry().with_resources((name, Resource.from_contents(s)) for name, s in schemas.items())
    check = lambda name, value: Draft202012Validator(schemas[name], registry=registry).validate(value)  # noqa: E731
    bus = Bus()
    feed = HubFeed(bus, tmp_path, classes=cc, clock=lambda: NOW)
    feed.events = [event("Lunch with Sam", (12, 0), (12, 45), "Marquis")]
    asyncio.run(feed.refresh())
    for kind, data in bus.sent:
        if kind == "day.updated": check("day.schema.json", data)
        elif kind == "nowcard.updated": check("now_card.schema.json", data)
        elif kind == "metrics.updated": check("metrics.schema.json", data)
        elif kind == "branch.updated":
            check("branch.schema.json", data["branch"])
            if data.get("card"): check("branch_card.schema.json", data["card"])
    assert {"day.updated", "nowcard.updated", "metrics.updated", "branch.updated"} <= set(bus.kinds())


def test_with_nothing_on_this_laptop_the_hub_says_so_instead_of_staying_blank(tmp_path):
    bus = Bus()
    asyncio.run(HubFeed(bus, tmp_path, clock=lambda: NOW).refresh())
    assert bus.last("day.updated") == {"date": "2026-11-23", "items": []}
    files = next(c for c in bus.last("metrics.updated")["connectors"] if c["name"] == "Class files")
    assert files == {"name": "Class files", "status": "off", "note": "Class Content folder not found on this laptop"}


def test_a_calendar_that_is_not_connected_is_a_quiet_row_not_an_error(cc, tmp_path):
    from jarvis.reach.calendar import NotConnected

    class Cal:
        async def events(self, first, days=1, query=None): raise NotConnected("not yet")

    feed = HubFeed(Bus(), tmp_path, classes=cc, calendar=Cal(), clock=lambda: NOW)
    asyncio.run(feed.refresh_calendar())
    assert feed.events == [] and feed.calendar_state[0] == "off" and "Not connected" in feed.calendar_state[1]


def test_the_school_tool_answers_a_whole_question_in_one_call(cc, monkeypatch):
    from jarvis.tools.school import handler

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None): return NOW

    monkeypatch.setattr(handler, "datetime", Fixed)
    ask = lambda **args: asyncio.run(handler.run(args, SimpleNamespace(classes=cc))).content  # noqa: E731
    assert ask(about="day", day="tuesday") == "His classes on Tuesday 24 November (schedule as of Oct 26):\n2:30 pm–5:20 pm · XX 202 lab · ENGR 2A20"
    assert "XX 101 Problem set 7 · due tomorrow 8:00 pm · Crowdmark · about 90 min left" in ask(about="due")
    assert ask(about="due", course="circuits").count("\n") == 1
    course = ask(about="course", course="XX 101")
    assert "XX 101 · Engineering Mechanics · Dr. Example" in course and "Next class: Wednesday 8:30 am–9:20 am · XX 101 lecture · ARTS 101" in course
    assert "Graded work: Problem sets 10%" in course and "Exam: Midterm 2 · Tue Dec 1 6:00 pm · ARTS 101 · 25%" in course
    assert ask(about="exams") .startswith("Tests in the next 30 days") and "Midterm 2" in ask(about="exams")
    with pytest.raises(Exception, match="No course matches"):
        ask(about="course", course="basket weaving")


def test_the_running_core_fills_the_hub_state_and_hands_the_talker_his_day(cc, tmp_path, monkeypatch):
    import time

    from fastapi.testclient import TestClient

    from jarvis.core.app import create_app
    from jarvis.core.config import Config
    from jarvis.core.sessions import HubSessions

    monkeypatch.setenv("JARVIS_CLASS_CONTENT", str(cc.root))
    config = Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver",), keystore="memory", voice_preload=False)
    app = create_app(config, log_to_stderr=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("test-hub")
    with TestClient(app, headers={"X-Jarvis-Session": token}) as client:
        state = {}
        for _ in range(100):                                    # the feed runs in the background: start-up never waits for it
            state = client.get("/api/state").json()
            if (state.get("metrics", {}).get("connectors") and any(b["id"] == "xx-101" for b in state["branches"])
                    and state["now_card"]["greeting"]):
                break
            time.sleep(0.05)
        assert {"xx-101", "xx-202", "school"} <= {b["id"] for b in state["branches"]}
        assert state["now_card"]["greeting"].startswith("Good ")
        assert any(c["name"] == "Homework list" for c in state["metrics"]["connectors"])
        assert state["day"]["date"] == time.strftime("%Y-%m-%d")
        voice = getattr(app.state, "voice", None)
        if voice is not None:                                   # the talker reads the same facts
            assert "# Now" in voice.now_card() and "Due: XX 202 Report" not in voice.now_card()


# -- v0.19.0: "pull up PPS 6", "let's work on mechanics" ----------------------------------------------------------

@pytest.fixture
def folders(cc):
    def make(course, *paths):
        for p in paths:
            f = cc.root / course / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("x", encoding="utf-8")
    make("XX 101 - Engineering Mechanics", "index.html", "Assignments & Labs/Practice 6/Practice 6 - Solutions.pdf",
         "Assignments & Labs/Practice 6/Practice 6.pdf", "Assignments & Labs/Practice 7/Practice 7.pdf", "Assignments & Labs/Practice 7/run.bat",
         "Assignments & Labs/Lab 3 - Work and Energy/Lab 3 - Instructions.pdf", "Lectures/L13 - Nov 05 - Work/notes.html",
         "Lectures/L14 - Nov 17 - Conservation of Energy/notes.html", "Lectures/_New Lecture Template/x.html",
         "Tests & Exams/Module 1 Test/Practice test.pdf", "Study Plans/P02 - Nov 28 - Module 2 Test/plan.html")
    make("XX 202 - Circuits", "index.html", "Assignments & Labs/Practice 6/P6.pdf", "Lectures/L09 - Nov 20 - Power/notes.html")
    return cc


def test_his_words_find_the_right_piece_of_work(folders):
    from jarvis.reach import workfiles as wf

    find = lambda ask: wf.find(folders, ask, NOW)  # noqa: E731
    assert wf.tokens("PPS 6") == wf.tokens("p6") == wf.tokens("problem set 6") == wf.tokens("Practice 06") == ["practice", "6"]
    assert wf.tokens("P02 - Nov 28", section="Study Plans")[:2] == ["plan", "2"] and wf.tokens("L14 - Nov 17")[:2] == ["lecture", "14"]
    w = find("pull up XX 101 pps 6")
    assert (w.course, w.label, [f.name for f in w.files]) == ("XX 101", "Practice 6", ["Practice 6.pdf", "Practice 6 - Solutions.pdf"])
    assert find("circuits practice 6").files[0].name == "P6.pdf"                    # the same number in another course
    w = find("problem set 7")                                                       # no course: his homework list knows which
    assert (w.course, w.label, w.due.title) == ("XX 101", "Practice 7", "Problem set 7") and [f.name for f in w.files] == ["Practice 7.pdf"]
    w = find("let's work on mechanics")                                             # only a course: the next thing due there
    assert (w.label, w.why, w.due.title) == ("Practice 7", "the next thing due", "Problem set 7")
    w = find("lets do circuits")                                                    # due, but no folder for a quiz: the latest lecture
    assert (w.course, w.due.title, w.label) == ("XX 202", "Quiz 5", "L09 - Nov 20 - Power")
    assert find("the mechanics lab 3").label == "Lab 3 - Work and Energy" and find("XX 101 lecture 14").label.startswith("L14")
    assert find("xx 101 module 1 test").label == "Module 1 Test" and find("mechanics practice 9") is None
    assert find("underwater basket weaving") is None


def test_work_on_opens_the_questions_shows_the_deadline_and_never_leaves_the_folder(folders, monkeypatch):
    from jarvis.tools.work_on import handler

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None): return NOW

    opened, shown = [], []
    monkeypatch.setattr(handler, "datetime", Fixed)
    monkeypatch.setattr(handler, "OPEN", opened.append)

    async def publish(kind, data): shown.append((kind, data))

    def ask(what, here=True):
        ctx = SimpleNamespace(classes=folders, here=here, publish=publish, show=publish)
        return asyncio.run(handler.run({"what": what}, ctx)).content

    said = ask("pps 7")
    assert [Path(p).name for p in opened] == ["Practice 7.pdf"]                    # the pdf, never the .bat beside it
    assert said == ("XX 101 · Practice 7 Opened on his laptop: Practice 7.pdf. "
                    "Due tomorrow 8:00 pm on Crowdmark, about 90 minutes of work left.")
    assert [(d["type"], d["ref"]) for _, d in shown] == [("countdown", "due-xx-101-ps7"), ("branch_card", "xx-101")]
    opened.clear()
    said = ask("xx 101 practice 6", here=False)                                    # he is at the other laptop
    assert opened == [] and "Not opened (he is talking from the other laptop" in said and "Practice 6" in said
    asked = []                                                                     # v0.24.1: the laptop he IS at opens it

    async def hands(kind, args):
        asked.append((kind, args))
        return {"ok": True}

    ctx = SimpleNamespace(classes=folders, here=False, hands=hands, publish=publish, show=publish)
    said = asyncio.run(handler.run({"what": "xx 101 practice 6"}, ctx)).content
    assert opened == [] and "Opened on his laptop: Practice 6" in said             # nothing opened on the core's laptop
    assert asked and all(k == "open" for k, _ in asked) and asked[0][1]["file"].endswith(".pdf")
    assert not any(a["file"].startswith(("/", "C:")) or ".." in a["file"] for _, a in asked)   # a path inside Class Content, never a full one
    with pytest.raises(Exception, match="Nothing in his Class Content folder matches"):
        ask("basket weaving")
    with pytest.raises(Exception, match="What should I pull up"):
        ask("")


def test_the_core_knows_when_he_is_at_its_own_laptop():
    from jarvis.voice.service import VoiceService

    src = Path("jarvis/voice/service.py").read_text(encoding="utf-8")
    assert 'not headers.get("x-forwarded-for")' in src and hasattr(VoiceService, "attach")


def test_the_setup_files_for_running_alone_are_plain_windows_files():
    for name in ("Run Jarvis on this laptop.bat", "Use the other laptop's Jarvis.bat", "setup-voice.bat", "setup-tools.bat"):
        raw = Path(name).read_bytes()
        raw.decode("ascii")
        assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), name
    alone = Path("Run Jarvis on this laptop.bat").read_text(encoding="ascii")
    assert "JARVIS_REMOTE_CORE_URL" in alone and "call setup-core.bat" in alone and "py -%%V" in alone
    assert alone.index("call setup-core.bat") < alone.index("call setup-voice.bat") < alone.index("call setup-tools.bat")


# -- v0.19.2: what Laptop B's own logs showed on 2026-11-22 --------------------------------------------------------

def test_facts_from_memory_reach_the_hub_and_the_card_is_rebuilt_only_when_the_day_changes(cc, tmp_path):
    from jarvis.core.state import empty_state
    from jarvis_hub.events import apply_event

    class Memory:
        builds = 0

        async def hub_tree(self):
            return {"branches": [{"id": "root", "parent": None, "name": "De Wet", "glyph": "DW", "kind": "root", "status": "active", "tier": 1}],
                    "cards": {}, "facts": [{"id": "f-1", "branch_id": "root", "statement": "Prefers mornings.", "source": {"kind": "you", "label": "You"},
                                            "confidence": "sure", "learned": "2026-11-20T09:00:00"}], "stamp": 1}

        async def rebuild_now_card(self, ctx):
            Memory.builds += 1
            return hub_feed.plain_now_card(ctx, NOW)[0]

        async def now_card_text(self): return "Next: XX 303 lab"

    bus = Bus()
    feed = HubFeed(bus, tmp_path, classes=cc, memory=Memory(), clock=lambda: NOW)
    asyncio.run(feed.refresh())
    state = empty_state(NOW.isoformat())
    for kind, data in bus.sent:
        apply_event(state, kind, data, NOW.isoformat())                             # a bare fact raised KeyError here
    assert [f["statement"] for f in state["facts"]] == ["Prefers mornings."]
    assert any(b["id"] == "school" and b["parent"] == "root" for b in state["branches"])
    asyncio.run(feed.refresh_day())
    asyncio.run(feed.refresh_day())
    assert Memory.builds == 1 and feed.now_text() == "Next: XX 303 lab"             # no database write every 30 s
    feed.clock = lambda: NOW.replace(hour=11, minute=30)                            # the lab ended: now it rebuilds
    asyncio.run(feed.refresh_day())
    assert Memory.builds == 2


# -- v0.20.1: his first real conversation with the learning loop (Laptop B, 2026-11-22 6:31 pm) ---------------------

def test_a_course_with_no_syllabus_on_file_and_work_that_lives_online_can_still_be_pulled_up(folders, monkeypatch):
    from jarvis.reach import workfiles as wf
    from jarvis.tools.work_on import handler

    cc = folders
    (cc.root / "XX 404 - Introduction to Atoms and Nuclei").mkdir()
    hw = json.loads((cc.root / "_Week Planner" / "homework.json").read_text())
    hw["items"].append({"key": "XX-303-A1", "course": "XX 303", "title": "Assignment 01 (WebAssign)", "due": "2026-11-23T23:59:00-06:00",
                        "platform": "WebAssign", "status": "open", "url": "https://canvas.example.edu/courses/1/assignments/2"})
    write(cc.root, "homework.json", hw)
    codes = [c["course"] for c in cc.courses()]
    assert codes[:2] == ["XX 101", "XX 202"] and {"XX 303", "XX 404"} <= set(codes)     # from his schedule and his folders
    assert wf.pick_course(cc, "pull up atoms")["course"] == "XX 404" and wf.pick_course(cc, "the engineering mechanic stuff")["course"] == "XX 101"
    w = wf.find(cc, "XX 303 assignment 01", NOW)
    assert (w.course, w.label, w.path, w.url) == ("XX 303", "Assignment 01 (WebAssign)", None, "https://canvas.example.edu/courses/1/assignments/2")

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None): return NOW

    opened = []
    monkeypatch.setattr(handler, "datetime", Fixed)
    monkeypatch.setattr(handler, "OPEN", opened.append)

    async def publish(kind, data): pass

    said = asyncio.run(handler.run({"what": "XX 303 assignment 1"}, SimpleNamespace(classes=cc, here=True, publish=publish, show=publish))).content
    assert opened == ["https://canvas.example.edu/courses/1/assignments/2"]
    assert "Opened on his laptop: its page in your browser." in said and "Due today 11:59 pm on WebAssign" in said
    said = asyncio.run(handler.run({"what": "XX 303 assignment 1"}, SimpleNamespace(classes=cc, here=False, publish=publish, show=publish))).content
    assert "It lives online and wasn't opened (the laptop he is at did not open it" in said and "https://canvas.example.edu" in said


def test_both_browser_launches_keep_the_session_so_a_sign_in_survives_the_window_closing():
    src = Path("jarvis/browser/service.py").read_text(encoding="utf-8")
    assert src.count("KEEP_SESSION") >= 3 and 'KEEP_SESSION = "--restore-last-session"' in src


# -- v0.21.0: more human, the icon row, and everything he needs beside the work ----------------------------------

def test_the_prompt_carries_plain_names_and_the_icon_row_holds_his_day_and_due_work(cc, tmp_path):
    from jarvis.core.state import empty_state
    from jarvis_hub.events import apply_event

    sched = json.loads((cc.root / "_Week Planner" / "schedule.json").read_text())
    for m in sched["meetings"]:
        m["building_name"] = {"ARTS": "Arts Building", "ENGR": "Engineering Building", "THORV": "Thorvaldson Building"}.get(m["building"], "")
    write(cc.root, "schedule.json", sched)
    names = cc.names()
    assert names[0] == "Buildings: ARTS is the Arts Building; ENGR is the Engineering Building; THORV is the Thorvaldson Building"
    assert "XX 101 is Engineering Mechanics" in names[1] and "XX 303 is Statics" in names[1]
    state = empty_state(NOW.isoformat())
    docked = {"ref": "file-x", "slot": "homework", "kind": "file", "title": "Something he docked", "at": NOW.isoformat(),
              "window": {"id": "w-x", "type": "file", "title": "x", "docked": True}}
    state["rail"]["slots"]["homework"]["items"] = [docked, {"ref": "old", "slot": "homework", "kind": "due", "title": "stale", "at": NOW.isoformat()}]
    bus = Bus()
    feed = HubFeed(bus, tmp_path, classes=cc, clock=lambda: NOW, rail=lambda: state["rail"])
    asyncio.run(feed.refresh())
    assert "Buildings: ARTS is the Arts Building" in feed.now_text()
    for kind, data in bus.sent:
        apply_event(state, kind, data, NOW.isoformat())
    slots = state["rail"]["slots"]
    assert [(i["title"], i["state"], i["detail"]) for i in slots["today"]["items"]] == [
        ("XX 303 lab", "soon", "8:30 am · THORV 120"), ("XX 202 lecture", "progress", "1:00 pm")]
    hw = slots["homework"]["items"]
    assert [(i["title"], i.get("state")) for i in hw] == [("XX 101 · Problem set 7", "soon"), ("XX 202 · Quiz 5", "progress"),
                                                          ("Something he docked", None)]     # his own stays; the stale one goes
    assert hw[0]["detail"] == "Due tomorrow 8:00 pm · about 90 min left" and hw[0]["window"] == {
        "id": "w-due-xx-101-ps7", "type": "countdown", "title": "XX 101 Problem set 7", "ref": "due-xx-101-ps7"}
    assert slots["today"]["done"] == 0.33 and slots["homework"]["worst"] == "soon"
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schemas = {p.name: json.loads(p.read_text()) for p in Path("contracts").glob("*.schema.json")}
    registry = Registry().with_resources((name, Resource.from_contents(sc)) for name, sc in schemas.items())
    Draft202012Validator(schemas["rail.schema.json"], registry=registry).validate(state["rail"])


def test_work_on_sets_up_what_he_likes_beside_it_and_opens_claude_only_if_it_is_not_open(folders, monkeypatch):
    from jarvis.tools.work_on import handler

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None): return NOW

    opened, shown, running = [], [], [False]
    monkeypatch.setattr(handler, "datetime", Fixed)
    monkeypatch.setattr(handler, "OPEN", opened.append)
    monkeypatch.setattr(handler, "claude_running", lambda: running[0])

    async def publish(kind, data): shown.append(data)

    def ask(**args):
        return asyncio.run(handler.run(args, SimpleNamespace(classes=folders, here=True, publish=publish, show=publish))).content

    said = ask(what="mechanics problem set 7", also=["claude", "lecture_notes", "course_page", "delete_everything"])
    assert [Path(p).name for p in opened] == ["Practice 7.pdf", "notes.html", "index.html", "claude:"] or opened[-1] == "claude://"
    assert "Practice 7.pdf, the notes for Conservation of Energy, the course page, Claude." in said
    opened.clear()
    running[0] = True
    said = ask(what="mechanics problem set 7", also=["claude"])
    assert [Path(p).name for p in opened] == ["Practice 7.pdf"] and "Claude (it was open already)" in said
    assert "ask afterwards whether he wants it set up that way" in Path("jarvis/tools/work_on/TOOL.md").read_text()


def test_the_talkers_rules_say_talk_like_a_person_and_ask_before_remembering():
    from jarvis.tools.voice import ROUTING

    for line in ("Talk like a person who knows him", "assignment one for physics", "give the room number only if he asks",
                 "Remembering needs his yes", "Want me to remember that for next time?", "pass it in `also`"):
        assert line in ROUTING, line


# ---- v0.27.1: he says a piece of work is finished ----------------------------------------------------------------
def test_marking_work_done_takes_it_off_his_list_and_never_touches_the_list_file(cc):
    from jarvis.tools.mark_done import handler as mark

    redrawn = []

    async def refresh():
        redrawn.append(1)

    ctx = SimpleNamespace(classes=cc, now=lambda: NOW, refresh=refresh)
    before = (cc.root / "_Week Planner" / "homework.json").read_text(encoding="utf-8")
    assert [d.key for d in cc.due(NOW)] == ["XX-101-PS7", "XX-202-Quiz"]
    asked = asyncio.run(mark.run({"what": "the mechanics problem set", "confirmed": False}, ctx)).content
    assert asked.startswith("Nothing has changed") and len(cc.due(NOW)) == 2          # only his word marks it
    said = asyncio.run(mark.run({"what": "problem set 7 for mechanics", "confirmed": True}, ctx)).content
    assert said.startswith("Marked as done on his list: XX 101 Problem set 7") and "nothing was submitted" in said
    assert [d.key for d in cc.due(NOW)] == ["XX-202-Quiz"] and redrawn == [1]
    assert (cc.root / "_Week Planner" / "homework.json").read_text(encoding="utf-8") == before
    assert list(cc.done()) == ["XX-101-PS7"] and cc.done()["XX-101-PS7"]["title"] == "Problem set 7"
    with pytest.raises(Exception, match="Nothing on his list matches"):
        asyncio.run(mark.run({"what": "the chemistry lab", "confirmed": True}, ctx))
    back = asyncio.run(mark.run({"what": "problem set 7", "done": False, "confirmed": True}, ctx)).content
    assert back.startswith("Back on his list: XX 101 Problem set 7") and len(cc.due(NOW)) == 2


def test_two_matches_ask_which_unless_he_said_all(cc):
    from jarvis.tools.mark_done import handler as mark

    ctx = SimpleNamespace(classes=cc, now=lambda: NOW, refresh=None)
    with pytest.raises(Exception, match="More than one matches: XX 202 Quiz 5; XX 202 Report"):
        asyncio.run(mark.run({"what": "my circuits work", "confirmed": True}, ctx))
    asyncio.run(mark.run({"what": "my circuits work", "all": True, "confirmed": True}, ctx))
    assert [d.key for d in cc.due(NOW, 90)] == ["XX-101-PS7"]
