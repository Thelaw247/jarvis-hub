"""N7: the demo on the real clock, the demo story, and Jarvis's lines (HUD v2 §9–§11)."""
import asyncio
import json
import random
import re
import threading
from datetime import datetime, timedelta

import pytest

from jarvis_hub.demo import lines as L
from jarvis_hub.demo.fixtures import FIXTURE_NOW, bare_state, load_state
from jarvis_hub.demo.rebase import (
    ISO,
    class_day,
    delta_for,
    next_class_day,
    rebase_state,
    shift_iso,
    shift_text,
)
from jarvis_hub.demo.scenario import DemoPlayer, due_this_week, steps
from jarvis_hub.events import Hub
from tests.test_contracts import problems

NOW = datetime(2026, 11, 16, 15, 40)


def isos(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from isos(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from isos(v, f"{path}.{i}")
    elif isinstance(value, str) and ISO.match(value):
        yield path, value


# ---- the clock ------------------------------------------------------------------------------------------------
def test_scenes_and_tests_stay_on_the_fixture_date(monkeypatch):
    monkeypatch.delenv("JARVIS_DEMO_CLOCK", raising=False)
    assert load_state()["now"] == "2026-11-16T15:40:00" and FIXTURE_NOW == NOW


def test_rebasing_to_the_fixture_time_changes_nothing_and_a_week_later_only_the_dates():
    fixture = load_state(real=False)
    assert rebase_state(fixture, NOW) == fixture  # the re-planned day is exactly the fixture's day
    week = rebase_state(fixture, NOW + timedelta(days=7))
    before, after = dict(isos(fixture)), dict(isos(week))
    assert before.keys() == after.keys() and len(before) > 40
    for path, value in before.items():
        assert after[path] == shift_iso(value, timedelta(days=7)), path
    plan = lambda s: [(i["id"], i["start"], i["end"], i.get("state")) for i in s["day"]["items"]]  # noqa: E731
    assert plan(week) == plan(fixture) and week["now_card"]["next_up"] == fixture["now_card"]["next_up"]


@pytest.mark.parametrize("now", [datetime(2026, 11, 14, 21, 13, 30), datetime(2026, 11, 20, 9, 2), datetime(2027, 1, 3, 0, 1)])
def test_calendar_things_move_by_whole_days_and_the_clock_is_exact(now):
    fixture = load_state(real=False)
    moved = rebase_state(fixture, now)
    assert moved["now"] == now.isoformat(timespec="seconds") and moved["day"]["date"] == now.date().isoformat()
    dues = lambda s: [(d["id"], d["due"]) for c in s["cards"].values() for d in c.get("due", [])]  # noqa: E731
    move = lambda day: class_day(NOW.date(), day, now.date())  # noqa: E731
    assert dues(moved) == [(ref, shift_iso(due, timedelta(0), move)) for ref, due in dues(fixture)]  # 8 pm stays 8 pm, 11:59 pm stays 11:59 pm
    for (_, before), (_, after) in zip(dues(fixture), dues(moved), strict=True):  # a later weekday deadline stays on a weekday
        if datetime.fromisoformat(before).date() > NOW.date():
            assert (datetime.fromisoformat(before).weekday() < 5) == (datetime.fromisoformat(after).weekday() < 5)
    assert moved["settings"]["quiet_hours"] == fixture["settings"]["quiet_hours"]
    classes = lambda s: [(i["id"], i["start"], i["end"]) for i in s["day"]["items"] if i["kind"] != "block"]  # noqa: E731
    if now.weekday() < 5:
        assert classes(moved) == classes(fixture)
    else:  # a weekend: his own things stay, there are no lectures or labs
        assert classes(moved) == [c for c in classes(fixture) if c[0] == "d-lunch"]
    # what happened minutes ago is still minutes ago
    delta = delta_for(NOW, now)
    assert moved["now_card"]["updated"] == shift_iso(fixture["now_card"]["updated"], delta)
    assert next(a for a in moved["actions"] if a["id"] == "a-sync")["ts"] == shift_iso(next(a for a in fixture["actions"] if a["id"] == "a-sync")["ts"], delta)
    assert problems("state", moved) == []
    assert fixture["now"] == "2026-11-16T15:40:00"  # the input isn't changed


def test_the_live_demo_moves_with_the_real_clock(monkeypatch):
    monkeypatch.setenv("JARVIS_DEMO_CLOCK", "real")
    before = datetime.now().replace(microsecond=0)
    now = datetime.fromisoformat(load_state()["now"])
    assert before <= now <= datetime.now()
    monkeypatch.setenv("JARVIS_DEMO_CLOCK", "fixture")
    assert load_state()["now"] == "2026-11-16T15:40:00"


def test_times_in_words_move_too():
    back = timedelta(hours=-42, minutes=-25)  # Monday 3:40 pm → Saturday 9:15 pm
    assert shift_text("PPS 7 is due Wednesday at 8 pm.", NOW, back) == "PPS 7 is due Tuesday at 1:35 am."
    assert shift_text("Tue 4 pm to Wed 10 am", NOW, back) == "Sun 9:35 pm to Mon 3:35 pm"
    assert shift_text("Tonight 7:00 to 8:30 pm", NOW, back) == "Tomorrow 12:35 to 2:05 am"
    assert shift_text("Today 7:00 am", NOW, back) == "Today 12:35 pm"
    assert shift_text("Monday · week 11 of 13", NOW, back) == "Saturday · week 11 of 13"
    assert shift_text("You · Nov 13", NOW, back) == "You · Nov 11"
    assert shift_text("due Wednesday evening", NOW, back) == "due Tuesday night"
    assert shift_text("Moved to 4 pm tomorrow.", NOW, timedelta(hours=6)) == "Moved to 10 pm tomorrow."
    assert shift_text("You'd rather not book study blocks before 9 am.", NOW, back) == "You'd rather not book study blocks before 9 am."  # a rule, not a moment
    assert shift_text("PPS 7 is due Wednesday at 8 pm.", NOW, timedelta(days=-2)) == "PPS 7 is due Monday at 8 pm."  # the live demo: whole days
    assert shift_text("Tonight 7:00 to 8:30 pm", NOW, timedelta(days=-2)) == "Tonight 7:00 to 8:30 pm"
    moved = rebase_state(load_state(real=False), NOW + back)
    assert next(f for f in moved["facts"] if f["id"] == "f-8am")["id"] == "f-8am"  # ids are never touched
    assert moved["now_card"]["greeting"] == "Good evening"
    assert moved["settings"]["quiet_hours"] == {"on": True, "from": "22:30", "to": "07:30"}
    assert moved["now_card"]["flag"]["text"] == "PPS 7 is due Tuesday 8 pm · half done"  # Wednesday is the third class day
    assert moved["cards"]["you"]["status"] == "Saturday · week 11 of 13"


def test_a_simulated_clock_for_trying_the_demo_at_any_time(monkeypatch):
    monkeypatch.setenv("JARVIS_DEMO_CLOCK", "2026-11-14T22:30")
    now = datetime.fromisoformat(load_state()["now"])
    assert datetime(2026, 11, 14, 22, 30) <= now < datetime(2026, 11, 14, 22, 31)
    monkeypatch.setenv("JARVIS_DEMO_CLOCK", "fixture")
    assert load_state()["now"] == "2026-11-16T15:40:00"


# ---- the live demo at any time of day ------------------------------------------------------------------------
CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))? (am|pm)\b")
WEEKDAY = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b")


def plausible(when: datetime) -> bool:
    """A deadline, class or block a USask student would really have: never between 1 and 6 am."""
    return not 1 <= when.hour < 6


def captions(script) -> list[str]:
    out = []
    for _, kind, data in script:
        if kind == "__while_pending__":
            kind, data = data["type"], data["data"]
        if kind == "caption.show":
            out.append(data["text"])
    return out


WEEKDAY_SHORT = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ")


def next_up_at(state: dict, now: datetime) -> datetime:
    when = state["now_card"]["next_up"]["when"]
    day, clock = now.date(), when
    if when.startswith("Tomorrow "):
        day, clock = now.date() + timedelta(days=1), when.removeprefix("Tomorrow ")
    elif WEEKDAY_SHORT.match(when):
        word = WEEKDAY_SHORT.match(when).group(1)
        day = next(now.date() + timedelta(days=n) for n in range(1, 8) if f"{now.date() + timedelta(days=n):%a}" == word)
        clock = when[4:]
    return datetime.combine(day, datetime.strptime(clock, "%I:%M %p").time())


def check_day(state: dict, now: datetime) -> None:
    """Everything on Now and Today makes sense at `now`."""
    day = state["day"]
    assert day["date"] == now.date().isoformat()
    at = lambda hhmm: datetime.fromisoformat(f"{day['date']}T{hhmm}")  # noqa: E731
    live = [i for i in day["items"] if i.get("state") != "moved"]
    for item in live:
        assert plausible(at(item["start"])) and at(item["start"]) < at(item["end"]), item
        if item["kind"] != "block":  # classes, labs and lunch: done once over, not before
            assert item["state"] == ("done" if at(item["end"]) <= now else "planned"), item
        else:
            assert at(item["end"]) <= at(state["settings"]["quiet_hours"]["from"]), item  # never into quiet hours
            assert item["state"] == "planned" and at(item["end"]) > now, item
    spans = sorted((at(i["start"]), at(i["end"])) for i in live)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False)), spans  # nothing double-booked
    for item in day["items"]:
        if item.get("state") == "moved":
            hour = CLOCK.search(item["moved_to"])
            assert hour and not 1 <= int(hour.group(1)) % 12 + (12 if hour.group(3) == "pm" else 0) < 6
    card = state["now_card"]
    assert card["greeting"] == ("Good morning" if 4 <= now.hour < 12 else "Good afternoon" if 12 <= now.hour < 17 else "Good evening")
    assert card["day"] == {"done": sum(i["state"] == "done" for i in live), "total": len(live)}
    nxt = next_up_at(state, now)
    assert nxt > now and plausible(nxt)  # the next thing is ahead of him, at a real hour
    nexts = [a for a in day["dial"] if a["state"] == "next"]
    assert len(nexts) <= 1 and all(a["title"] == card["next_up"]["title"] and datetime.fromisoformat(a["start"]) == nxt for a in nexts)
    for arc in day["dial"]:
        start = datetime.fromisoformat(arc["start"])
        end = datetime.fromisoformat(arc.get("end", arc["start"]))  # a due item is a point: its time
        assert plausible(start) and now - timedelta(hours=2) <= end and start <= now + timedelta(hours=11)
        assert arc["state"] != "done" or end <= now or arc["kind"] == "due"  # a deadline can be done before it's due
    if now.weekday() >= 5:  # no lectures or labs on a weekend
        assert not [i for i in day["items"] if i["kind"] in ("class", "lab")]
    for card_ in state["cards"].values():  # every lecture, lab, tutorial and quiz ahead is on a weekday
        for nxt_ in card_.get("next", []):
            assert WEEKDAY_SHORT.match(nxt_["when"]) and WEEKDAY_SHORT.match(nxt_["when"]).group(1) not in ("Sat", "Sun"), nxt_
    for card_ in state["cards"].values():
        for due in card_.get("due", []):
            assert plausible(datetime.fromisoformat(due["due"]))
    for approval in state["approvals"]:
        assert datetime.fromisoformat(approval["expires"]) > now and plausible(datetime.fromisoformat(approval["expires"]))
    # history is in the past; its undo is still ahead
    soon = now + timedelta(minutes=2)
    assert all(datetime.fromisoformat(a["ts"]) <= now for a in state["actions"])
    assert all(datetime.fromisoformat(a["undo"]["until"]) > now for a in state["actions"] if a.get("undo"))
    assert all(datetime.fromisoformat(f["learned"]) <= now for f in state["facts"])
    assert all(datetime.fromisoformat(t["resume"]["at"]) <= now for t in state["threads"])
    assert all(datetime.fromisoformat(m["at"]) <= soon for m in state["marks"].values())
    assert problems("state", state) == []


@pytest.mark.parametrize("now", [datetime(2026, 11, 14) + timedelta(minutes=30 * i) for i in range(48)]
                         + [datetime(2026, 11, 18, 7, 5), datetime(2027, 1, 3, 0, 1), datetime(2026, 11, 22, 23, 50)])
def test_the_live_day_makes_sense_at_every_half_hour(now):
    check_day(rebase_state(load_state(real=False), now), now)


@pytest.mark.parametrize("now", [datetime(2026, 11, 14, 8, 30), datetime(2026, 11, 19, 15, 40), datetime(2026, 11, 14, 22, 30),
                                 datetime(2026, 11, 19, 17, 10), datetime(2026, 11, 14, 0, 30)])
def test_the_whole_story_looks_real_morning_afternoon_and_late_night(now):
    state = load_state(real=True, now=now)
    check_day(state, now)
    script = steps(state)
    said = captions(script)
    text = " ".join(said)
    for match in CLOCK.finditer(text):  # every time Jarvis says is at a real hour
        hour = int(match.group(1)) % 12 + (12 if match.group(3) == "pm" else 0)
        assert not 1 <= hour < 6, match.group(0)
    dues = {datetime.fromisoformat(d["due"]) for c in state["cards"].values() for d in c.get("due", [])}
    days = {f"{d:%A}" for d in dues} | {f"{next_class_day(now.date()):%A}"}
    assert set(WEEKDAY.findall(text)) <= days  # every weekday he hears is a real due date's, or his next class day's
    pps = datetime.fromisoformat(next(d["due"] for d in state["cards"]["you"]["due"] if d["id"] == "due-pps7"))
    assert L.say_when(pps, now) in text  # "Monday at 8 pm", the same day the Rail and the countdown show
    greet = re.match(r"(Morning|Afternoon|Evening)\b", said[0])
    assert greet is None or greet.group(1) == L.greeting_word(now)
    review = next(i for i in state["day"]["items"] if i["id"] == "d-review")
    echo = next(t for t in said if t.startswith("Study protocol?"))
    if "moves your" in echo:  # the write reads back the review's real time, and the move lands on free time today
        assert f"your {L.clock(datetime.fromisoformat(state['day']['date'] + 'T' + review['start']))} review" in echo
    approvals = [d if k == "approval.pending" else d["data"] for _, k, d in script if k == "approval.pending"]
    assert {a["id"] for a in approvals} == {"ap-study", "ap-week"}
    assert all(now < datetime.fromisoformat(a["expires"]) and plausible(datetime.fromisoformat(a["expires"])) for a in approvals)
    stop = next(t for t in said if t.startswith("“That's it for"))
    evening = now.hour >= 18 or now.hour < 4
    assert stop == ("“That's it for tonight.”" if evening else "“That's it for now.”")
    assert "Good night" not in text or now.hour >= 20 or now.hour < 4
    last = said[-1]
    day = [d for _, k, d in script if k == "day.updated"][-1:] or [state["day"]]  # the day after his yes moved the review
    ahead = sorted(datetime.fromisoformat(f"{day[0]['date']}T{i['start']}") for i in day[0]["items"]
                   if i.get("state", "planned") == "planned" and datetime.fromisoformat(f"{day[0]['date']}T{i['start']}") > now)
    if ahead and not evening:  # stopping during the day: what's next today, at its real time (after his yes moved it)
        assert L.say_when(ahead[0], now) in last
    else:  # the first thing on his next day: tomorrow's first block, or the next lecture on a class day
        nxt = next_up_at(state, now)
        if state["now_card"]["next_up"]["when"].startswith("Tomorrow "):
            assert "tomorrow" in last and L.clock(nxt) in last
        else:
            first = next_class_day(now.date())
            assert "GE 122 at 10 am" in last and ("tomorrow" if first == now.date() + timedelta(days=1) else f"{first:%A}") in last
    hub, events = play(state)
    assert all(problems("event", e) == [] for e in events) and problems("state", hub.snapshot()) == []
    for e in events:  # every day the story sends still makes sense
        if e["type"] == "day.updated":
            moved_review = next(i for i in e["data"]["items"] if i["id"] == "d-review")
            start = datetime.fromisoformat(f"{e['data']['date']}T{moved_review['start']}")
            assert start > now and plausible(start)
        if e["type"] == "nowcard.updated" and e["data"].get("next_up"):
            assert e["data"]["next_up"]["when"]


# ---- the demo day's state ------------------------------------------------------------------------------------
def test_the_demo_day_is_rich_and_valid():
    s = load_state(real=False)
    assert problems("state", s) == []
    pps = next(t for t in s["threads"] if t["id"] == "th-pps7")
    assert (pps["resume"]["label"], pps["resume"]["page"], pps["branch"]) == ("Q7", 3, "ge-122") and pps["done"] == [f"Q{i}" for i in range(1, 7)]
    assert all(s["rail"]["slots"][k]["items"] for k in ("yes", "today", "homework", "messages", "jarvis", "parked"))
    refs = [i["ref"] for slot in s["rail"]["slots"].values() for i in slot["items"]]
    assert len(refs) == len(set(refs))  # one item per thing
    assert s["marks"] and s["now_card"]["moment"] in ("rushed", "between", "settled", "heads_down", "others", "game")
    dial = s["day"]["dial"]
    assert all(timedelta(hours=-1) <= datetime.fromisoformat(a["start"]) - NOW <= timedelta(hours=11) or a["state"] == "done" for a in dial)
    assert [a["state"] for a in dial].count("next") == 1
    thumbs = {t["src"] for _, t in thumbs_in(s)}
    from jarvis_hub.thumbs import thumb_path

    assert thumbs and all(re.fullmatch(r"/api/thumb/[a-z0-9-]+\.webp", src) for src in thumbs)
    assert all(thumb_path(src.rsplit("/", 1)[1]) for src in thumbs)  # every picture is one the hub can serve (N5a's keys)
    from jarvis_hub.rail import refresh

    before = json.dumps(s["rail"])
    assert json.dumps(refresh(s, NOW)) == before  # the fixture's Rail is what the hub derives: nothing doubles on load
    assert all(t["alt"] for _, t in thumbs_in(s))


def thumbs_in(value):
    if isinstance(value, dict):
        if "thumb" in value:
            yield value, value["thumb"]
        for v in value.values():
            yield from thumbs_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from thumbs_in(v)


def test_bare_state_has_nothing_tracked_yet():
    s = bare_state()
    assert all(slot["items"] == [] for slot in s["rail"]["slots"].values()) and s["marks"] == {} and s["threads"] == []
    assert problems("state", s) == []


# ---- the story ------------------------------------------------------------------------------------------------
def play(state):
    hub = Hub(state)
    queue = hub.subscribe()
    worker = threading.Thread(target=lambda: asyncio.run(DemoPlayer(hub, speed=0).play()))
    worker.start()
    worker.join(timeout=10)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return hub, events


def test_the_story_plays_in_order_and_never_deletes_anything():
    hub, events = play(load_state(real=False))
    assert all(problems("event", e) == [] for e in events) and problems("state", hub.snapshot()) == []
    said = [e["data"]["text"] for e in events if e["type"] == "caption.show" and e["data"].get("text")]
    order = ["“Status.”", "“Study protocol.”", "“Yes.”", "Question seven.", "“Plan the rest of my week.”", "“That's it for now.”"]  # 3:40 pm
    assert [s for s in said if s in order] == order
    assert said[0].startswith("Afternoon.") and "Canvas posted hints for PPS 7" in said[0]  # greeting attached to what changed
    assert "Study protocol? That also moves your 4 pm review to 5 pm. Go ahead?" in said
    closes = [e["data"] for e in events if e["type"] == "window.close"]
    assert closes == [{"id": "w-ap-study"}]  # only the answered approval's own window (the hub's rule); everything else docks
    assert any(e["type"] == "window.dock" and e["data"] == {"all": True, "reason": "cleared"} for e in events)
    assert hub.state["windows"] == [] and {"w-pps7", "w-l21", "w-ge122", "w-ap-week"} <= {
        i["window"]["id"] for slot in hub.state["rail"]["slots"].values() for i in slot["items"] if i.get("window")}
    assert {a["id"]: a["status"] for a in hub.state["approvals"]} == {"ap-week": "pending", "ap-study": "approved"}
    assert hub.state["presence"]["here"] is False and hub.state["orb"]["state"] == "idle"  # standby
    thread = next(t for t in hub.state["threads"] if t["id"] == "th-pps7")
    assert thread["resume"]["label"] == "Q8" and "Q7" in thread["done"]
    # the set opens in the reader behind its card, then his yes confirms the spot as Jarvis names it
    kinds = [(e["type"], e["data"].get("path") or (e["data"].get("thread") or {}).get("resume", {}).get("source") or e["data"].get("ref")) for e in events]
    opened, confirmed, named = kinds.index(("nav.go", "/read/th-pps7")), kinds.index(("thread.updated", "confirmed")), kinds.index(("ui.focus", "w-pps7"))
    assert opened < confirmed < named
    # the week plan's question goes to the Stage and the Rail: the hub is never pulled off the reader he's in
    assert [k for k in kinds if k[0] == "nav.go"] == [("nav.go", "/read/th-pps7")]
    assert next(e for e in events if e["type"] == "window.push" and e["data"]["id"] == "w-ap-week")["data"]["title"] == "Study plan"
    # 3:40 pm: he's done for now, not for the night, and Jarvis names the review his yes just moved to 5 pm
    assert said[-1] == "PPS 7 to question eight. The review of lecture 21 is at 5 pm."
    assert not any("Good night" in t or "tonight" in t.lower() for t in said)


def test_each_status_item_lights_up_as_it_is_said():
    _, events = play(load_state(real=False))
    status = [i for i, e in enumerate(events) if e["type"] == "caption.show" and e["data"].get("text") == "“Status.”"][0]
    focus = [e["data"]["ref"] for e in events[status:] if e["type"] == "ui.focus"][:3]
    assert focus == ["due-pps7", "ge-122", "job-sync-am"]  # time-critical → progress → systems
    for e in events:
        if e["type"] == "ui.focus":
            assert datetime.fromisoformat(e["data"]["until"]) > datetime.fromisoformat(e["ts"])


def test_the_yes_window_closes_on_other_speech_and_books_nothing():
    _, events = play(load_state(real=False))
    door = next(i for i, e in enumerate(events) if e["type"] == "caption.show" and "door" in e["data"].get("text", ""))
    assert events[door + 1]["type"] == "orb.state" and events[door + 1]["data"]["state"] == "idle"
    assert not any(e["type"] == "approval.resolved" and e["data"]["id"] == "ap-week" for e in events)
    assert not any(e["type"] == "caption.show" and "No rush" in e["data"].get("text", "") for e in events)


def test_captions_follow_the_moved_clock():
    moved = load_state(real=True, now=datetime(2026, 11, 14, 21, 13))  # a Saturday evening
    said = " ".join(captions(steps(moved)))
    # Wednesday is the fixture's third class day: Tuesday from a Saturday; the next lecture is Monday, not Sunday
    assert said.startswith("Evening.") and "Tuesday at 8 pm" in said and "GE 122 at 10 am Monday" in said
    assert "Wednesday" not in said and "Sunday" not in said  # nothing left over from the fixture's Monday, no weekend class
    review = next(i for i in moved["day"]["items"] if i["id"] == "d-review")
    assert (review["start"], review["end"]) == ("21:30", "22:15")  # 4 pm has passed: the next free half hour, before quiet hours
    assert moved["now_card"]["next_up"]["when"] == "9:30 pm"
    assert "Study protocol?" in said and "moves your" not in said  # moving it an hour would run into quiet hours
    hub, events = play(moved)
    assert all(problems("event", e) == [] for e in events) and problems("state", hub.snapshot()) == []


def test_every_story_line_keeps_the_register():
    for state in (load_state(real=False), load_state(real=True, now=datetime(2026, 11, 18, 7, 5))):
        for _, kind, data in steps(state):
            if kind == "__while_pending__":
                kind, data = data["type"], data["data"]
            if kind == "caption.show" and (data.get("source") or {}).get("kind") != "you":
                assert L.register_problems(data["text"]) == [], data["text"]


# ---- the lines ------------------------------------------------------------------------------------------------
def test_every_pool_has_five_to_eight_original_wordings_in_register():
    for kind, groups in L.POOLS.items():
        for lead, pool in groups.items():
            if kind in ("leave_now", "protocol"):
                assert len(pool) == 1  # fixed wording, on purpose
                continue
            assert 5 <= len(pool) <= 8 and len(set(pool)) == len(pool), (kind, lead)
            for template in pool:
                values = {s: "PPS 7" for s in L._slots(template)} | {"name": "De Wet", "facts": "Minus fourteen."}
                assert L.register_problems(L.fill(template, values)) == [], template
    for line in ("Great job!", "Task resumed.", "Sure! Got it.", "Welcome back.", "As you said earlier, not now.", "Okay so it's open."):
        assert L.register_problems(line)
    assert L.register_problems("Morning, sir.") and L.register_problems("Morning, sir.", address="sir") == []
    assert L.register_problems("De Wet, morning, De Wet.")


def test_context_comes_first_then_rotation():
    v = L.Voice(rng=random.Random(3))
    base = {"thread": "PPS 7", "label": "question seven"}
    assert v.say("offer_resume", L.Context(now=NOW, changed="New hints arrived", away=timedelta(days=2), words="you'd finish it", values=base)).lead == "changed"
    assert v.say("offer_resume", L.Context(now=NOW, away=timedelta(days=2), words="you'd finish it", values=base)).lead == "away"
    assert v.say("offer_resume", L.Context(now=NOW, away=timedelta(hours=3), words="you'd finish it", values=base)).lead == "words"
    assert v.say("offer_resume", L.Context(now=NOW, values=base)).lead == "plain"
    picks = [v.say("mistake", L.Context(now=NOW, values={"what": "I filed that under the wrong course"})).template for _ in range(40)]
    for i in range(len(picks)):
        assert picks[i] not in picks[max(0, i - 5):i]  # never one of the last 5 wordings of that type


def test_shall_i_in_at_most_one_offer_in_five_and_the_name_once_per_exchange():
    v = L.Voice(rng=random.Random(7))
    shall = []
    for i in range(60):
        line = v.say("offer_resume", L.Context(now=NOW + timedelta(hours=i), by_voice=True, values={"thread": "PPS 7", "label": "question seven"}))
        shall.append("Shall I" in line.text)
    assert all(sum(shall[i:i + 5]) <= 1 for i in range(len(shall)))
    assert sum(shall) >= 3  # it's allowed, just rare
    v = L.Voice(rng=random.Random(1))
    names = [v.say("arrival", L.Context(now=NOW.replace(hour=h), changed="Lab four's draft is where you left it")).text.count("De Wet") for h in (8, 13, 19)]
    assert sum(names) <= 1  # one exchange
    sir = L.Voice(address="sir", rng=random.Random(2))
    assert "De Wet" not in " ".join(sir.say("arrival", L.Context(now=NOW.replace(hour=h))).text or "" for h in (8, 13, 19))
    quiet = L.Voice(address="none", rng=random.Random(2))
    assert all("{name}" not in (quiet.say("morning", L.Context(now=NOW.replace(day=d, hour=8), values={"facts": "Nothing due today."})).template or "") for d in range(1, 20))


def test_no_greeting_repeats_on_the_same_day():
    v = L.Voice(rng=random.Random(5))
    greetings = []
    for minute in range(0, 600, 30):
        line = v.say("arrival", L.Context(now=NOW.replace(hour=17) + timedelta(minutes=minute)))
        if line.text:
            match = L.GREETINGS.match(line.text)
            greetings.append((line.text and (NOW.replace(hour=17) + timedelta(minutes=minute)).date(), match and match.group(0).lower()))
    words = [g for g in greetings if g[1]]
    assert len(words) == len(set(words))
    # nothing changed and it's already been said today: a word or silence, never a ritual
    assert v.say("arrival", L.Context(now=NOW.replace(hour=20))).text is None


def test_moments_decide_how_much_is_said():
    v = L.Voice(rng=random.Random(4))
    ctx = lambda m, **k: L.Context(now=NOW, moment=m, changed="Assignment five is out", values={"thread": "PPS 7", "label": "question seven"}, **k)  # noqa: E731
    for moment, cap in (("rushed", 1), ("between", 1), ("settled", 2)):
        line = v.say("offer_resume", ctx(moment))
        if moment == "rushed":
            assert line.spoken is False  # no spoken offers when rushed
        else:
            assert line.spoken and len(L.sentences(line.text)) <= cap
    for moment in ("heads_down", "others", "game"):
        assert v.say("offer_resume", ctx(moment)).spoken is False
        assert v.say("arrival", L.Context(now=NOW, moment=moment, changed="X changed")).spoken is False
    leave = v.say("leave_now", L.Context(now=NOW, moment="game", values={"event": "the GE 122 midterm"}))
    assert (leave.text, leave.spoken) == ("Leave now for the GE 122 midterm.", True)  # critical: exempt, same words every time
    assert [v.say("leave_now", L.Context(now=NOW, values={"event": "x"})).text for _ in range(3)] == ["Leave now for x."] * 3
    status = v.status(L.Context(now=NOW, moment="rushed"), due=[("PPS 7", NOW + timedelta(days=2), "due-pps7")],
                      progress={"thread": "PPS 7", "label": "question seven", "done": 6, "total": 12, "ref": "th"},
                      systems={"source": "Canvas", "at": NOW, "ref": "j"})
    assert len(status.parts) == 1 and status.focus == ("due-pps7",)
    assert L.Voice.max_sentences(L.Context(now=NOW, moment="heads_down", asked=True, by_voice=True)) is None  # he spoke to it
    assert L.Voice.max_sentences(L.Context(now=NOW, moment="others", asked=True, by_voice=True)) == 0


def test_when_offers_are_spoken():
    v = L.Voice(rng=random.Random(6))
    values = {"thread": "PPS 7", "label": "question seven"}
    assert v.say("offer_resume", L.Context(now=NOW, values=values)).spoken is False  # nothing new: a card
    assert v.say("offer_resume", L.Context(now=NOW, by_voice=True, values=values)).spoken is True
    assert v.say("offer_resume", L.Context(now=NOW, away=timedelta(days=1), values=values)).spoken is True
    assert v.say("offer_resume", L.Context(now=NOW, changed="Hints arrived", values=values)).spoken is True
    assert v.say("offer_resume", L.Context(now=NOW, tapped=True, by_voice=True, changed="x", values=values)).spoken is False  # a tap never speaks
    assert L.new_work_spoken(timedelta(hours=48), True) and not L.new_work_spoken(timedelta(hours=80), True) and not L.new_work_spoken(timedelta(hours=1), False)
    assert L.wind_down_spoken(True, False) and L.wind_down_spoken(False, True) and not L.wind_down_spoken(False, False)
    assert L.debrief_ok(True, 0, "between") and not L.debrief_ok(False, 0, "between") and not L.debrief_ok(True, 1, "settled") and not L.debrief_ok(True, 0, "rushed")


def test_declines():
    v = L.Voice(rng=random.Random(8))
    ctx = L.Context(now=NOW, by_voice=True, values={"thread": "PPS 7", "label": "question seven"})
    offer = lambda **k: v.offer("offer_resume", ctx, context="evening", ref="th-pps7", **k)  # noqa: E731
    assert offer().spoken
    # he answers by acting: that's the answer, nothing is said
    assert v.decline("offer_resume", "acted", ctx, context="evening", ref="th-pps7").text is None
    # ignored: not spoken again this session; two in a row → card-only until he accepts one by voice
    v.decline("offer_resume", "ignored", ctx, context="evening", ref="th-pps7")
    assert offer().spoken is False
    v.new_session()
    assert offer().spoken
    v.decline("offer_resume", "ignored", ctx, context="evening", ref="th-pps7")
    v.new_session()
    assert offer().spoken is False and ("offer_resume", "evening") in v.declines.card_only
    v.decline("offer_resume", "accepted", ctx, context="evening", ref="th-pps7")
    assert offer().spoken
    # "not now": a soft tick at most; unspoken until the context changes
    assert v.decline("offer_resume", "not_now", ctx, context="evening", ref="th-pps7", fingerprint="due wed").text is None
    assert offer(fingerprint="due wed").spoken is False
    assert offer(fingerprint="due tomorrow").spoken is True
    # "stop offering that": off, one receipt with the undo
    receipt = v.decline("offer_resume", "stop", ctx, what="resume")
    assert receipt.text and "Jarvis learned" in receipt.text and L.register_problems(receipt.text) == []
    assert offer().text is None
    v.declines.undo_stop("offer_resume")
    assert offer().text
    # thresholds drift back over about two weeks
    d = L.Declines()
    d.record("break", "ignored", now=NOW)
    d.record("break", "not_now", now=NOW)
    assert d.threshold("break", NOW) == pytest.approx(0.8)
    assert d.threshold("break", NOW + timedelta(days=7)) == pytest.approx(0.65)
    assert d.threshold("break", NOW + timedelta(days=14)) == pytest.approx(0.5)
    # and no line, anywhere, mentions a past decline
    assert not any(L.DECLINE_MENTIONS.search(t.lower()) for groups in L.POOLS.values() for pool in groups.values() for t in pool)


def test_the_humour_budget():
    v = L.Voice(rng=random.Random(9))
    ctx = L.Context(now=NOW)
    assert v.aside(ctx, where="chat", target="lab manual", thing="The lab manual").text
    assert v.aside(ctx, where="chat", target="syllabus", thing="The syllabus").text is None  # one per session
    v.new_session()
    assert v.aside(ctx, where="chat", target="lab manual", thing="The lab manual").text is None  # same target within a week
    assert v.aside(ctx, where="chat", target="syllabus", thing="The syllabus").text  # two today
    v.new_session()
    assert v.aside(ctx, where="chat", target="quiz", thing="The quiz").text is None  # about two a day
    tomorrow = L.Context(now=NOW + timedelta(days=1))
    for where in ("alert", "approval", "error", "readout"):
        v.new_session()
        assert v.aside(tomorrow, where=where, target=f"t-{where}").text is None
    for moment in ("rushed", "others", "heads_down", "game"):
        v.new_session()
        assert v.aside(L.Context(now=NOW + timedelta(days=1), moment=moment), where="chat", target=f"m-{moment}").text is None
    v.new_session()
    assert v.aside(L.Context(now=NOW + timedelta(days=1), alone=False), where="chat", target="x").text is None
    assert v.aside(tomorrow, where="chat", target="y", behind=True).text is None


def test_timed_lines_fire_at_a_breakpoint_inside_their_window():
    start, end = L.break_window(NOW)
    assert (start - NOW, end - NOW) == (timedelta(hours=2.5), timedelta(hours=3.5))
    breaks = [NOW + timedelta(hours=2, minutes=50), NOW + timedelta(hours=3, minutes=5)]
    assert L.fire_at(start, end, breaks) == breaks[0]
    assert L.fire_at(start, end, []) == end
    assert L.fire_at(start, end, breaks, hard=NOW + timedelta(hours=1)) == NOW + timedelta(hours=1)  # critical keeps its hard time
    assert L.is_arrival(timedelta(minutes=31), timedelta(minutes=40)) and L.is_arrival(timedelta(minutes=5), timedelta(hours=3))
    assert not L.is_arrival(timedelta(minutes=5), timedelta(minutes=20))
    assert L.full_wake_beat(True, timedelta(0)) and L.full_wake_beat(False, timedelta(hours=4)) and not L.full_wake_beat(False, timedelta(hours=1))
    assert L.moment_for(minutes_to_fixed=10) == "rushed" and L.moment_for(minutes_to_fixed=None, said_quick=True) == "rushed"
    assert L.moment_for(minutes_to_fixed=40, minutes_since_arrival=3) == "between"
    assert L.moment_for(minutes_to_fixed=None, session_started=True, free_minutes=90) == "settled"
    assert L.moment_for(minutes_to_fixed=5, others=True) == "others" and L.moment_for(minutes_to_fixed=5, game=True) == "game"


def test_times_are_said_like_a_person_would():
    assert L.say_when(datetime(2026, 11, 18, 20), NOW) == "Wednesday at 8 pm"
    assert L.say_when(datetime(2026, 11, 17, 9, 30), NOW) == "tomorrow at 9:30 am"
    assert L.say_when(datetime(2026, 11, 16, 16), NOW) == "at 4 pm"
    assert L.say_when(datetime(2026, 11, 16, 19), NOW) == "tonight at 7 pm"
    assert L.say_when(datetime(2026, 11, 25, 23, 59), NOW) == "Nov 25"
    assert L.clock(datetime(2026, 1, 1, 12)) == "noon" and L.clock(datetime(2026, 1, 1, 23, 59)) == "11:59 pm"
    assert L.ago(NOW - timedelta(minutes=4), NOW) == "four minutes ago"


def test_repeat_rate_over_a_simulated_week_is_under_ten_percent():
    """A week of ordinary use: mornings, arrivals, acknowledgements, offers, status, wind-downs, breaks, leave-nows."""
    rng = random.Random(11)
    v = L.Voice(rng=random.Random(12))
    changes = ["Canvas posted hints for PPS {n}", "Lab {n}'s mark is in", "CHEM moved to Thorvaldson 271 for lecture {n}",
               "Maya replied about tutorial {n}", "WeBWorK {n} opened", "The GE 122 quiz {n} grades are up"]
    targets = ["Canvas", "your calendar", "PAWS", "Crowdmark", "the syllabus", "Gmail", "the Class Content folder", "WeBWorK"]
    threads = [("PPS 7", "question {n}"), ("Lab report 4", "the Results section"), ("Lecture 21 pack", "step {n}"), ("Thermo deck", "card {n}")]
    for day in range(7):
        start = datetime(2026, 11, 16 + day, 8, 0)
        v.new_session()
        v.new_exchange()
        v.say("morning", L.Context(now=start, moment="between", changed=rng.choice([None, rng.choice(changes).format(n=day + 3)]),
                                   values={"facts": f"Minus {L.number(rng.randint(2, 12))}. CHEM at {rng.choice(['8:30', '9:30', '10'])}. "
                                                    f"{L.number(rng.randint(0, 3)).capitalize()} due today."}))
        for k in range(rng.randint(2, 3)):
            v.new_exchange()
            at = start + timedelta(hours=3 + 3 * k)
            change = rng.choice(changes).format(n=rng.randint(1, 30)) if rng.random() < 0.8 else None
            v.say("arrival", L.Context(now=at, moment="between", changed=change))
        for k in range(6):
            v.say("acknowledge", L.Context(now=start + timedelta(hours=1, minutes=40 * k), asked=True, by_voice=True,
                                           values={"target": rng.choice(targets)}))
        for k in range(3):
            thread, label = rng.choice(threads)
            v.new_exchange()
            v.say("offer_resume", L.Context(now=start + timedelta(hours=4 + 2 * k), by_voice=True,
                                            changed=rng.choice([None, rng.choice(changes).format(n=rng.randint(1, 30))]),
                                            values={"thread": thread, "label": label.format(n=rng.randint(2, 12))}))
        v.status(L.Context(now=start + timedelta(hours=9), by_voice=True),
                 due=[("PPS 7", start + timedelta(days=rng.randint(1, 4), hours=rng.randint(0, 12)), "d")] * rng.randint(1, 4),
                 progress={"thread": "PPS 7", "label": f"question {L.number(rng.randint(2, 12))}", "done": rng.randint(1, 11), "total": 12, "ref": "t"},
                 systems={"source": rng.choice(["Canvas", "PAWS", "Calendar"]), "at": start + timedelta(hours=9, minutes=-rng.randint(1, 50)), "ref": "j"})
        if day % 2:
            v.say("break", L.Context(now=start + timedelta(hours=12), values={"span": rng.choice(["three hours", "two and a half hours"]),
                                                                              "thread": rng.choice(threads)[0]}))
        v.say("leave_now", L.Context(now=start + timedelta(hours=1), values={"event": "CHEM 142"}))
        v.say("wind_down", L.Context(now=start + timedelta(hours=14), values={"progress": f"PPS 7 to question {L.number(rng.randint(3, 12))}",
                                                                               "tomorrow": f"{rng.choice(['GE 122', 'CHEM 142', 'MATH 133'])} at {rng.choice(['8:30 am', '9:30 am', '10 am', '1:30 pm'])}"}))
    spoken = [line for line in v.log if line[1] not in L.SAFETY]
    assert len(spoken) > 80
    assert L.repeat_rate(v.log) < 0.10, L.repeat_rate(v.log)
    # the safety line is excluded: it is the same every day on purpose
    same = [(datetime(2026, 11, 16 + d, 9), "leave_now", "Leave now for CHEM 142.") for d in range(7)]
    assert L.repeat_rate(same) == 0.0
    assert L.repeat_rate([(NOW, "arrival", "Evening."), (NOW + timedelta(days=1), "arrival", "Evening.")]) == 0.5
    # acknowledgements never repeat within a week: once every wording is used, the orb's Thinking state is the ack
    ack = L.Voice(rng=random.Random(1))
    said = [ack.say("acknowledge", L.Context(now=NOW + timedelta(hours=i), values={"target": "Canvas"})).text for i in range(12)]
    heard = [t for t in said if t]
    assert len(heard) == len(set(heard)) == len(L.POOLS["acknowledge"]["plain"]) == 7 and said[-1] is None


# ---- final-fix regressions (v0.3.0 reviews) -------------------------------------------------------------------
def run(hub, player, times=1):
    """Play the story `times` times on one hub (like "Play it again"); the captions of each run."""
    queue = hub.subscribe()
    runs = []

    async def go():
        for _ in range(times):
            await player.play()
            said = []
            while not queue.empty():
                e = queue.get_nowait()
                if e["type"] == "caption.show" and e["data"].get("text"):
                    said.append(e["data"]["text"])
            runs.append(said)

    worker = threading.Thread(target=lambda: asyncio.run(go()))
    worker.start()
    worker.join(timeout=20)
    return runs


def test_status_counts_exactly_what_the_homework_slot_shows():
    state = load_state(real=False)
    slot = [i["ref"] for i in state["rail"]["slots"]["homework"]["items"] if i["kind"] == "due"]
    cards = {d["id"]: d for c in state["cards"].values() for d in c.get("due", [])}
    week = [r for r in slot if (cards[r].get("progress") or 0) < 1 and timedelta(0) <= datetime.fromisoformat(cards[r]["due"]) - NOW <= timedelta(days=7)]
    assert [ref for _, _, ref in due_this_week(state, NOW)] == sorted(week, key=lambda r: cards[r]["due"]) == ["due-pps7", "due-lab4", "due-webwork"]
    first = next(t for t in captions(steps(state)) if "due" in t and "“" not in t)
    assert re.search(r"\bthree\b", first, re.I), first  # "Three due this week…", not "Two": the slot it lights lists three
    for now in (datetime(2026, 11, 14, 15, 40), datetime(2026, 11, 19, 15, 40)):  # and on any day of the week
        moved = load_state(real=True, now=now)
        count = L.number(len(due_this_week(moved, now)))
        assert re.search(rf"\b{count}\b", next(t for t in captions(steps(moved)) if " due" in t and "“" not in t), re.I)


def test_good_night_and_tonight_only_at_night():
    for hour, ok in ((15, False), (17, False), (19, False), (20, True), (23, True), (2, True)):
        assert L.fits_time("Good night. {Progress}.", NOW.replace(hour=hour)) is ok
    assert not L.fits_time("That's it for tonight.", NOW.replace(hour=15, minute=41)) and L.fits_time("x tonight", NOW.replace(hour=18))
    v = L.Voice(rng=random.Random(0))
    afternoon = {v.say("wind_down", L.Context(now=NOW + timedelta(minutes=i), values={"progress": "PPS 7 to question eight", "tomorrow": "GE 122 at 10 am"})).template
                 for i in range(40)}
    assert not any("Good night" in (t or "") for t in afternoon)
    late = L.Voice(rng=random.Random(0))
    assert any("Good night" in (late.say("wind_down", L.Context(now=NOW.replace(hour=22) + timedelta(days=d), values={"progress": "x", "tomorrow": "y"})).text or "")
               for d in range(30))


def test_the_story_never_pulls_the_hub_away_from_his_work_even_on_the_hub_setting():
    for where in ("window", "hub"):
        state = load_state(real=False)
        state["settings"]["stage"] = where
        _, events = play(state)
        assert [e["data"]["path"] for e in events if e["type"] == "nav.go"] == ["/read/th-pps7"]  # only what his yes asked for


@pytest.mark.parametrize("now", [datetime(2026, 11, 16, 8, 30), datetime(2026, 11, 18, 8, 20), datetime(2026, 11, 19, 13, 40)])
def test_with_a_class_on_now_the_story_is_the_short_rushed_one(now):
    state = load_state(real=True, now=now)
    check_day(state, now)
    script = steps(state)
    said = captions(script)
    assert said[0].startswith("Leave now for ") and (" in ARTS 101." in said[0] or " in Thorvaldson 173." in said[0])
    kinds = [k if k != "__while_pending__" else d["type"] for _, k, d in script]
    assert "approval.pending" not in kinds and "nav.go" not in kinds and "day.updated" not in kinds  # nothing booked over his class
    assert any(k == "nowcard.updated" and d["moment"] == "rushed" for _, k, d in script)
    status = next(t for t in said if " due" in t and "“" not in t)
    assert len(L.sentences(status)) == 1  # rushed: one sentence
    hub, events = play(state)
    assert all(problems("event", e) == [] for e in events) and hub.state["presence"]["here"] is False


def test_weekends_have_no_classes_and_lectures_stay_on_weekdays():
    for now in (datetime(2026, 11, 14, 15, 40), datetime(2026, 11, 15, 21, 0), datetime(2026, 11, 13, 21, 0)):  # Sat, Sun, Fri
        state = load_state(real=True, now=now)
        text = json.dumps(state, ensure_ascii=False)
        assert not re.search(r"\b(?:Sat|Sun)\w* 10:00 am · Lecture|\b(?:Sat|Sun)\w* 1:30 pm", text)
        lecture = state["cards"]["ge-122"]["next"][0]
        assert lecture["when"] == f"{next_class_day(now.date()):%a} 10:00 am"
        said = captions(steps(state))
        if now.hour >= 18:  # done for the night: Friday and Saturday say "Monday", Sunday "tomorrow"
            first = next_class_day(now.date())
            word = "tomorrow" if first == now.date() + timedelta(days=1) else f"{first:%A}"
            assert "GE 122 at 10 am" in said[-1] and word in said[-1] and (word == "tomorrow") == (now.weekday() == 6)
        assert not [i for i in state["day"]["items"] if i["kind"] in ("class", "lab")] or now.weekday() < 5
        approval = state["approvals"][0]
        assert not re.search(r"\b(?:Sat|Sun)\b", " ".join(approval["consequences"])) and "Saturday" not in approval["read_back"] and "Sunday" not in approval["read_back"]
        assert "weekday mornings" not in " ".join(p["why"] for p in state["day"]["proposals"])


def test_quiet_hours_show_lines_but_jarvis_does_not_speak():
    now = datetime(2026, 11, 16, 22, 30)  # quiet hours are 10:30 pm to 7:30 am
    state = load_state(real=True, now=now)
    script = steps(state)
    orbs = [(d if k == "orb.state" else d["data"])["state"] for _, k, d in script
            if k == "orb.state" or (k == "__while_pending__" and d["type"] == "orb.state")]
    assert "speaking" not in orbs and "waiting" in orbs  # shown, not said; the yes window still opens
    assert len(captions(script)) > 8  # every line is still there to read
    loud = steps(load_state(real=True, now=datetime(2026, 11, 16, 21, 30)))
    assert any(k == "orb.state" and d["state"] == "speaking" for _, k, d in loud)


def test_play_it_again_keeps_his_settings_and_does_not_repeat_itself():
    hub = Hub(load_state(real=False))
    player = DemoPlayer(hub, speed=0)
    player.prepare()  # the hub's first window shows the start of the day: it doesn't use up any wording
    hub.state["settings"].update(address="sir", theme="day", earcons="full")
    first, second = run(hub, player, times=2)
    assert hub.state["settings"]["address"] == "sir" and hub.state["settings"]["theme"] == "day" and hub.state["settings"]["earcons"] == "full"
    assert first[0].startswith("Afternoon.")  # the first play is the day's own (the start-up prepare didn't use it)
    assert first != second and first[0] != second[0]  # a replay is told in other words
    assert not any("De Wet" in t for t in first + second)  # he chose "sir"
    assert [t for t in first if t.startswith("“")] == [t for t in second if t.startswith("“")]  # the same story


def test_copy_and_the_dial_diamond():
    s = load_state(real=False)
    text = json.dumps(s, ensure_ascii=False)
    assert "No problem" not in text and "Free?" not in text and "Thursday afternoon is still open." in s["now_card"]["gaps"]
    assert any(a["kind"] == "due" and "end" not in a for a in s["day"]["dial"])  # a deadline on the dial: a diamond
    for now in (datetime(2026, 11, 18, 14, 0), datetime(2026, 11, 14, 21, 0)):
        assert any(a["kind"] == "due" for a in rebase_state(s, now)["day"]["dial"])


def test_his_saved_spot_is_stamped_when_he_stopped_never_in_the_future():
    hub, events = play(load_state(real=False))
    saved = [e["data"]["thread"] for e in events if e["type"] == "thread.updated" and e["data"]["thread"]["resume"]["label"] == "Q8"]
    assert saved and all(datetime.fromisoformat(t["resume"]["at"]) <= datetime.fromisoformat(e_ts) for t, e_ts in
                         zip(saved, [e["ts"] for e in events if e["type"] == "thread.updated" and e["data"]["thread"]["resume"]["label"] == "Q8"], strict=True))
    assert datetime.fromisoformat(next(t for t in hub.state["threads"] if t["id"] == "th-pps7")["resume"]["at"]) <= hub.now()
    assert not any(k == "thread.updated" for _, k, _ in steps(load_state(real=False)))  # stamped as it plays, not ahead of time
