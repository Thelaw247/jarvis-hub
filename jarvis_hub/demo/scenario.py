"""The scripted demo day (HUD v2 §11), so the demo finally feels like JARVIS:

  walk in → one line attached to what changed → "Status." walking across the HUD → "Study protocol." echoed back
  with its one write read back → his "Yes." inside the answer window → PPS 7 opens in the reader at question 7,
  behind the resume card, and the brackets lock on as Jarvis names it → "Plan the rest
  of my week." → its answer window closes when he says something else, so it waits under Your yes (the hub stays on
  the reader: a question never pulls him away from what he's doing) → "That's it for now." ("for tonight" from
  6 pm) → wind-down → standby.

The story follows his real day: with a lecture or lab on now or within 15 minutes it's the short rushed one ("Leave
now for MATH 133 in ARTS 101.", a one-line status, and he's off); in quiet hours every line is shown, not said (the
orb doesn't speak). "Play it again" keeps his Controls settings and Jarvis's memory of what he said, so a replay
doesn't repeat itself word for word.

Each step is (seconds to wait, event type, data). Every caption comes from `lines.py` and every time in it from the
(re-based) state, so weekdays and clock times are right in the live demo. Nothing here deletes anything: windows
step aside by docking, and only an answered approval's own window closes (the hub does that).

Steps whose type starts with "__" are run by the player instead of being sent as they are:
  __focus__              {ref, hold_ms}: ui.focus on what Jarvis is naming, until hold_ms from now (§9.1)
  __act__                {action, target, args?}: his answer by voice, through the hub's own action rules
  __while_pending__      a step that plays only while an approval still waits for his answer
  __close_yes_window__   {id}: he said something outside the answer grammar, so the yes window closes silently
  __wait_answer__        {id, max_s}: time for him to answer by tap before the story moves on
  __thread__             {thread}: thread.updated, stamped with the hub's time as it plays (his spot is saved now)
Nothing here pretends to be slow: the waits only pace the story so it can be followed.
"""
from __future__ import annotations

import asyncio
import copy
import random
from datetime import datetime, time, timedelta

from . import lines as L
from .fixtures import load_state, real_clock
from .rebase import SPOKEN, TOMORROW, busy_today, expiry, free_slot, in_quiet, latest, next_class_day

CALENDAR = {"kind": "calendar", "label": "Calendar"}
CANVAS = {"kind": "canvas", "label": "Canvas"}
JARVIS = {"kind": "jarvis", "label": "Jarvis"}
YOU = {"kind": "you", "label": "You · just now"}
PROTOCOL_MOVES_WITHIN = timedelta(hours=2)  # "Study protocol" moves the review only if it would come up while he studies
EVENING = 18  # from 6 pm (to 4 am) "that's it" means for the day ("for tonight"); before that it's "for now"
RUSHED_WITHIN = timedelta(minutes=15)  # a lecture or lab this close (or on now): the short, rushed story
WORDS_PER_S = 2.6  # roughly how fast the voice speaks: how long a focus cue and a caption stay
Step = tuple[float, str, dict]


def while_pending(approval_id: str, wait: float, kind: str, data: dict) -> Step:
    """A step that only plays while the approval still waits for his answer (and is skipped once he answers)."""
    return (wait, "__while_pending__", {"id": approval_id, "type": kind, "data": data})


def spoken_s(text: str) -> float:
    """How long a line takes to say, plus the 600 ms the focus cue holds after the sentence."""
    return round(len(text.split()) / WORDS_PER_S + 0.6, 2)


def after(seconds: float, group: list[Step]) -> list[Step]:
    """The same steps, starting `seconds` later."""
    (wait, kind, data), *rest = group
    return [(wait + seconds, kind, data), *rest]


def say(text: str, source: dict | None, ref: str | None = None, linger_s: float = 1.5) -> list[Step]:
    """A spoken line: its caption and, if it names something on screen, the focus cue timed to it."""
    out: list[Step] = [(0.0, "caption.show", {"text": text, "source": source, "ttl_ms": int((spoken_s(text) + linger_s) * 1000)})]
    if ref:
        out.append((0.0, "__focus__", {"ref": ref, "hold_ms": int(spoken_s(text) * 1000)}))
    return out


def heard(text: str, think: float = 0.6) -> list[Step]:
    """He speaks: the orb listens, his words show as a caption, then a short think."""
    return [(0.0, "orb.state", {"state": "listening", "level": 0.7}),
            (0.0, "caption.show", {"text": f"“{text}”", "source": YOU, "ttl_ms": 2500}),
            (think, "orb.state", {"state": "thinking"})]


def hm(when: datetime) -> str:
    """The hub's time style for a next-up line: '4:00 pm'."""
    return f"{when.hour % 12 or 12}:{when.minute:02d} {'am' if when.hour < 12 else 'pm'}"


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value)


def due_this_week(state: dict, now: datetime) -> list[tuple[str, datetime, str]]:
    """What the Rail's Homework slot shows as due in the next seven days and not done yet, soonest first, as
    (short title, when, ref). The status readout counts exactly these, so it never contradicts the slot it lights."""
    cards: dict[str, dict] = {}
    for card in (state.get("cards") or {}).values():
        for due in (card or {}).get("due", []):
            if due["id"] not in cards or len(due["title"]) > len(cards[due["id"]]["title"]):
                cards[due["id"]] = due
    slot = ((state.get("rail") or {}).get("slots") or {}).get("homework")
    refs = [i["ref"] for i in slot["items"] if i.get("kind") == "due"] if slot else list(cards)
    out = []
    for ref in refs:
        due = cards.get(ref)
        if not due or (due.get("progress") or 0) >= 1:
            continue
        when = _t(due["due"])
        if timedelta(0) <= when - now <= timedelta(days=7):
            out.append((due["title"].split(" · ")[-1], when, ref))
    return sorted(out, key=lambda d: d[1])


def class_on(state: dict, now: datetime) -> dict | None:
    """A lecture or lab on now, or starting within 15 minutes: he has somewhere to be."""
    for item in state["day"]["items"]:
        if item["kind"] in ("class", "lab") and item.get("state", "planned") != "moved":
            start, end = _t(f"{state['day']['date']}T{item['start']}"), _t(f"{state['day']['date']}T{item['end']}")
            if start - RUSHED_WITHIN <= now < end:
                return item
    return None


def spoken_name(title: str, state: dict) -> str:
    """What Jarvis calls a day item: "the review of lecture 21", "GE 122 lecture 22"."""
    ids = {i["title"]: i["id"] for i in [*state["day"]["items"], *TOMORROW] if i.get("title")}
    name = SPOKEN.get(ids.get(title, ""), title.split(" · ")[0])
    return name[:1].lower() + name[1:] if name.startswith(("The ", "Your ")) else name


def new_voice(state: dict) -> L.Voice:
    """A fresh voice for the demo day: the wording varies by day; the address term is the Controls setting."""
    now = _t(state["now"])
    return L.Voice(address=state.get("settings", {}).get("address", "name"), rng=random.Random(now.date().toordinal()))


def steps(state: dict, voice: L.Voice | None = None) -> list[Step]:
    """The story for this state. `voice` carries Jarvis's memory of what he has said (a replay passes the last one,
    so it doesn't repeat itself); left out, a fresh one for the day."""
    now = _t(state["now"])
    voice = voice or new_voice(state)
    voice.address = state.get("settings", {}).get("address", voice.address)  # "sir" is opt-in, in Controls
    voice.new_session()
    quiet = in_quiet(state, now)  # quiet hours: every line is shown, none is said (the orb doesn't speak)
    talk = (lambda level: {"state": "idle"}) if quiet else (lambda level: {"state": "speaking", "level": level})  # noqa: E731
    find = lambda items, key: next(x for x in items if x["id"] == key)  # noqa: E731
    thread = copy.deepcopy(find(state["threads"], "th-pps7"))
    review = find(state["day"]["items"], "d-review")
    approval = copy.deepcopy(find(state["approvals"], "ap-week"))
    synced = _t(find(state["actions"], "a-sync")["ts"])
    dues = due_this_week(state, now)
    label = f"question {L.number(int(thread['resume']['label'].lstrip('Q')))}"
    card = {**copy.deepcopy(state["now_card"]), "moment": "between"}
    script: list[Step] = []
    lecture = class_on(state, now)
    if lecture:
        return rushed(state, voice, lecture, dues, card)

    # 1. walking in: standby lifts; one line, attached to the one thing that changed
    arrival = voice.say("arrival", L.Context(now=now, moment="between", changed="Canvas posted hints for PPS 7, filed under GE 122",
                                             quiet_hours=quiet))
    script += [(1.0, "presence.changed", {"here": True, "others": False, "idle_s": 0}),
               (0.2, "nowcard.updated", card),
               (0.4, "orb.state", talk(0.6) if arrival.spoken else {"state": "idle"}),
               *say(arrival.text, CANVAS, "due-pps7"),
               (spoken_s(arrival.text), "orb.state", {"state": "idle"})]

    # 2. "Status.": time-critical → progress → systems, each lighting up as it's said
    voice.new_exchange()
    status = voice.status(L.Context(now=now, moment="between", by_voice=True, quiet_hours=quiet), due=dues,
                          progress={"thread": "PPS 7", "label": label, "done": len(thread["done"]), "total": 12, "ref": "ge-122"},
                          systems={"source": "Canvas", "at": synced, "ref": "job-sync-am"})
    script += after(2.0, heard("Status."))
    script += [(0.3, "window.push", {"id": "w-due-pps7", "type": "countdown", "title": "Due", "ref": "due-pps7", "size": "1x1",
                                     "thumb": thread["thumb"]}),
               (0.1, "window.push", {"id": "w-ge122", "type": "branch_card", "title": "GE 122", "ref": "ge-122", "size": "1x2"}),
               (0.1, "orb.state", talk(0.6))]
    for i, (part, ref) in enumerate(zip(status.parts, status.focus, strict=True)):
        script += after(spoken_s(status.parts[i - 1]) if i else 0.0, say(part, JARVIS, ref, 0.6))
    script += [(spoken_s(status.parts[-1]), "orb.state", {"state": "idle"})]

    # 3. "Study protocol.": echoed back as a question with its one write read back; his "Yes." inside the window.
    # The write is moving the review he'd otherwise be studying through: only when it's today, within two hours.
    voice.new_exchange()
    moved_from = _t(f"{state['day']['date']}T{review['start']}")
    moved_to = None
    if review.get("state", "planned") == "planned" and timedelta(0) <= moved_from - now <= PROTOCOL_MOVES_WITHIN:
        length = _t(f"{state['day']['date']}T{review['end']}") - moved_from
        moved_to = free_slot(busy_today(state, ignore="d-review"), moved_from + timedelta(hours=1), length,
                             latest(state, moved_from.date()))
    write = f"That also moves your {L.clock(moved_from)} review to {L.clock(moved_to)}." if moved_to else None
    echo = voice.protocol(L.Context(now=now, quiet_hours=quiet), "Study", write)
    consequences = ["Opens PPS 7 at question 7, with the Lecture 21 pack beside it"]
    if moved_to:
        consequences = [f"Moves your GE 122 review from {L.clock(moved_from)} to {L.clock(moved_to)}", *consequences,
                        "Keeps your phone quiet until the review", "Can be undone for 24 hours"]
    else:
        consequences.append("Keeps your phone quiet while you work")
    study = {"id": "ap-study", "title": "Study protocol", "status": "pending", "asked": state["now"],
             "consequences": consequences,
             "read_back": echo.text, "branch_id": "ge-122", "sources": [CALENDAR], "answer_window_s": 10,
             "expires": expiry(state, now, timedelta(hours=1)).isoformat(timespec="seconds"), "reversible": bool(moved_to),
             "category": "calendar"}
    day = copy.deepcopy(state["day"])
    moved_card = copy.deepcopy(card)
    if moved_to:
        for item in day["items"]:
            if item["id"] == "d-review":
                item.update(start=f"{moved_to:%H:%M}", end=f"{moved_to + length:%H:%M}")
        for arc in day.get("dial", []):
            if arc.get("ref") == "d-review":
                arc.update(start=moved_to.isoformat(timespec="seconds"), end=(moved_to + length).isoformat(timespec="seconds"))
        if (moved_card.get("next_up") or {}).get("title") == review["title"]:
            moved_card["next_up"]["when"] = hm(moved_to)
    script += after(2.5, heard("Study protocol.", 0.5))
    script += [(0.2, "approval.pending", study),
               while_pending("ap-study", 0.0, "orb.state", talk(0.6)),
               while_pending("ap-study", 0.0, "caption.show", {"text": echo.text, "source": CALENDAR, "ttl_ms": int((spoken_s(echo.text) + 3) * 1000)}),
               while_pending("ap-study", 0.0, "__focus__", {"ref": "d-review", "hold_ms": int(spoken_s(echo.text) * 1000)}),
               while_pending("ap-study", spoken_s(echo.text), "orb.state", {"state": "waiting", "countdown_s": 10, "window_s": 10}),
               while_pending("ap-study", 1.6, "caption.show", {"text": "“Yes.”", "source": YOU, "ttl_ms": 2000}),
               (0.1, "__act__", {"action": "approve", "target": "ap-study"}),  # inside the answer window, so the yes counts
               *([(0.2, "day.updated", day)] if moved_to else []),
               (0.0 if moved_to else 0.2, "nowcard.updated", {**moved_card, "moment": "heads_down"}),
               (0.2, "window.dock", {"id": "w-due-pps7", "reason": "aside"}),  # the study layout: the countdown steps aside
               (0.1, "window.push", {"id": "w-pps7", "type": "file", "title": "PPS 7", "ref": "file-pps7", "size": "2x2", "thumb": thread["thumb"]}),
               (0.1, "window.push", {"id": "w-l21", "type": "file", "title": "Lecture 21 study pack", "ref": "file-l21", "size": "1x2",
                                     "thumb": find(state["threads"], "th-l21")["thumb"]}),
               (0.0, "window.order", {"ids": ["w-pps7", "w-l21", "w-ge122"]}),
               # the practice set opens in the hub's reader, already at question 7, behind the small card (§10.1) …
               (0.5, "nav.go", {"path": "/read/th-pps7"}),
               # … and his yes covered it: the spot is confirmed, and as Jarvis names it the card lifts and the
               # brackets lock onto the question's heading
               (1.8, "__act__", {"action": "resume_accept", "target": "th-pps7"}),
               (0.1, "orb.state", talk(0.5)),
               *say(f"{L.fill('{Label}', {'label': label})}.", {"kind": "file", "label": "PPS 7.pdf"}, "w-pps7", 1.0),
               (1.6, "orb.state", {"state": "idle"})]

    # 4. "Plan the rest of my week.": something else he says closes the yes window; it waits under Your yes
    voice.new_exchange()
    ack = voice.say("acknowledge", L.Context(now=now, moment="heads_down", asked=True, by_voice=True, quiet_hours=quiet,
                                             values={"target": "your calendar"}))
    job = {"id": "job-plan", "label": "Planning your week", "state": "running"}
    script += after(4.0, heard("Plan the rest of my week.", 0.4))
    script += [(0.0, "caption.show", {"text": ack.text, "source": None, "ttl_ms": 2500}) if ack.text else (0.0, "orb.state", {"state": "thinking"}),
               (0.1, "job.progress", {**job, "progress": 0.2, "detail": "Reading Canvas due dates"}),
               (1.0, "job.progress", {**job, "progress": 0.6, "detail": "Finding free time in your calendar"}),
               (1.0, "job.progress", {**job, "progress": 0.9, "detail": "Sizing blocks generously"}),
               (0.6, "job.progress", {**job, "state": "done", "progress": 1}),
               (0.1, "approval.pending", {**approval, "status": "pending"}),
               # the question goes to the Stage, the Rail's Your yes and the hub's pill; the hub stays on the reader he's
               # working in (nothing he didn't ask for moves)
               while_pending("ap-week", 0.0, "window.push", {"id": "w-ap-week", "type": "approval", "title": "Study plan",
                                                              "ref": "ap-week", "size": "2x2"}),
               while_pending("ap-week", 0.1, "orb.state", talk(0.6)),
               while_pending("ap-week", 0.0, "caption.show", {"text": approval["read_back"], "source": CALENDAR,
                                                               "ttl_ms": int((spoken_s(approval["read_back"]) + 1.5) * 1000)}),
               while_pending("ap-week", 0.0, "__focus__", {"ref": "w-ap-week", "hold_ms": int(spoken_s(approval["read_back"]) * 1000)}),
               while_pending("ap-week", spoken_s(approval["read_back"]), "orb.state", {"state": "waiting", "countdown_s": 10, "window_s": 10}),
               # his own words, and not an answer: the window closes and nothing is booked. A yes now needs a tap or a fresh wake.
               while_pending("ap-week", 3.0, "caption.show", {"text": "“Hang on, someone's at the door.”", "source": YOU, "ttl_ms": 2500}),
               (0.0, "__close_yes_window__", {"id": "ap-week"}),
               (0.0, "__wait_answer__", {"id": "ap-week", "max_s": 30})]

    # 5. "That's it for now." ("for tonight" from 6 pm): wind-down, spoken because question 7 is finished; then
    # standby, everything docked. During the day it names what's next today (the review his yes just moved).
    voice.new_exchange()
    finished = {**thread, "resume": {"page": 3, "y": 309.6, "label": "Q8", "source": "inferred", "at": state["now"]},  # Q8's heading in the demo PDF
                "done": [*thread["done"], "Q7"], "state": "paused", "updated": state["now"]}
    evening = now.hour >= EVENING or now.hour < 4
    ahead = sorted((_t(f"{day['date']}T{i['start']}"), i) for i in day["items"]
                   if i.get("state", "planned") == "planned" and _t(f"{day['date']}T{i['start']}") > now)
    if ahead and not evening:  # stopping during the day: say what's next today instead of tomorrow
        start, item = ahead[0]
        name = spoken_name(item["title"], state)
        words = f"PPS 7 to question eight. {name[:1].upper()}{name[1:]} is {L.say_when(start, now)}."
    else:
        words = wind_down(state, voice, now, quiet)
    done_for = "That's it for tonight." if evening else "That's it for now."
    script += after(2.5, heard(done_for, 0.3))
    script += [(0.0, "__thread__", {"thread": finished}),
               (0.2, "orb.state", talk(0.5)),
               *say(words, JARVIS, "w-pps7", 1.5),
               (spoken_s(words), "orb.state", {"state": "idle"}),
               *leave(1.5)]
    return script


def leave(wait: float) -> list[Step]:
    """Standby: every window docks (nothing is lost), he's gone; then the end of the tour, once, with how to replay."""
    return [(wait, "window.dock", {"all": True, "reason": "cleared"}),
            (0.6, "presence.changed", {"here": False, "others": False, "idle_s": 0}),
            (3.0, "toast", {"id": "t-demo-end", "kind": "info", "text": "That was the demo day. Everything still works: look around.",
                            "ttl_ms": 8000, "action": {"label": "Play it again", "action": "demo", "target": "restart"}})]


def wind_down(state: dict, voice: L.Voice, now: datetime, quiet: bool) -> str:
    """The wind-down line: progress, then the first thing on his next day (what's next tomorrow on the Now card, or the
    first lecture on the next class day, "Monday" after a Friday or on a weekend)."""
    upcoming = state["now_card"].get("next_up") or {}
    if upcoming.get("when", "").startswith("Tomorrow "):
        when = datetime.combine(now.date() + timedelta(days=1), datetime.strptime(upcoming["when"].removeprefix("Tomorrow "), "%I:%M %p").time())
        first, day = f"{spoken_name(upcoming['title'], state)} at {L.clock(when)}", "tomorrow"
    else:
        lecture = next(t for t in TOMORROW if not t.get("busy"))  # GE 122 lecture 22
        when = datetime.combine(next_class_day(now.date()), time.fromisoformat(lecture["start"]))
        first = f"GE 122 at {L.clock(when)}"
        day = "tomorrow" if when.date() == now.date() + timedelta(days=1) else f"{when:%A}"
    line = voice.say("wind_down", L.Context(now=now, quiet_hours=quiet, values={"progress": "PPS 7 to question eight", "tomorrow": first, "day": day}))
    return line.text or f"PPS 7 to question eight. {first[:1].upper()}{first[1:]} {day}."


def rushed(state: dict, voice: L.Voice, lecture: dict, dues: list, card: dict) -> list[Step]:
    """A lecture or lab is on now or about to start: the safety line, a one-line status if he asks, and he's off.
    No study protocol and nothing booked over his class."""
    now = _t(state["now"])
    where = f" in {lecture['where']}" if lecture.get("where") else ""
    go = voice.say("leave_now", L.Context(now=now, moment="rushed", critical=True,
                                          values={"event": f"{SPOKEN.get(lecture['id'], lecture['title'].split(' · ')[0])}{where}"}))
    script: list[Step] = [(1.0, "presence.changed", {"here": True, "others": False, "idle_s": 0}),
                          (0.2, "nowcard.updated", {**card, "moment": "rushed"}),
                          (0.4, "orb.state", {"state": "speaking", "level": 0.7}),  # critical: said even in quiet hours
                          *say(go.text, {"kind": "paws", "label": "PAWS"}, lecture["id"]),
                          (spoken_s(go.text), "orb.state", {"state": "idle"})]
    voice.new_exchange()
    quiet = in_quiet(state, now)
    status = voice.status(L.Context(now=now, moment="rushed", by_voice=True, quiet_hours=quiet), due=dues, progress=None, systems=None)
    script += after(1.5, heard("Status.", 0.4))
    script += [(0.1, "orb.state", {"state": "idle"} if quiet else {"state": "speaking", "level": 0.6}),
               *say(status.text, JARVIS, status.focus[0] if status.focus else None, 0.6),
               (spoken_s(status.text), "orb.state", {"state": "idle"}),
               *leave(2.0)]
    return script


START_OVERRIDES = {"approvals": [], "windows": [], "jobs": [], "toasts": [], "caption": None, "focus": None}


class DemoPlayer:
    """Plays the scripted day into a Hub. `speed` 0 plays it instantly (used by the tests)."""

    def __init__(self, hub, speed: float = 1.0) -> None:
        self.hub = hub
        self.speed = speed
        self.task: asyncio.Task | None = None
        self.played = False
        self.step = 0
        self.total = 0
        self.voice: L.Voice | None = None  # Jarvis's memory of what he said, kept across replays
        self._next_voice: L.Voice | None = None

    def prepare(self) -> list[Step]:
        settings = copy.deepcopy(self.hub.state.get("settings"))  # his Controls choices survive "Play it again"
        if real_clock():  # a restart later on starts the day again from the real time, so the clock stays right
            fresh = load_state(real=True)
            self.hub._initial, self.hub._clock_base = fresh, datetime.fromisoformat(fresh["now"])
        if settings:
            self.hub._initial["settings"] = settings
        # the story is written with a copy of the voice: only a play that starts commits it (prepare also runs once
        # when the hub starts, to show the start of the day)
        self._next_voice = copy.deepcopy(self.voice) if self.voice else new_voice(self.hub._initial)
        script = steps(self.hub._initial, self._next_voice)
        self.hub.reset()
        self.hub.state.update(copy.deepcopy(START_OVERRIDES))
        asked = {a["id"] for a in self.hub._initial.get("approvals", [])}  # the story asks its own questions
        for slot in self.hub.state["rail"]["slots"].values():
            slot["items"] = [i for i in slot["items"] if i["ref"] not in asked]
        self.total = len(script)
        return script

    async def _pause(self, seconds: float) -> None:
        if self.speed and seconds:
            await asyncio.sleep(seconds / self.speed)

    async def play(self) -> None:
        script = self.prepare()
        self.voice = self._next_voice
        self.played = True
        hub = self.hub
        for self.step, (wait, kind, data) in enumerate(script, 1):
            await self._pause(wait)
            about = None
            if kind == "__while_pending__":
                if not hub.is_pending(data["id"]):
                    continue
                kind, data, about = data["type"], data["data"], data["id"]
            if kind == "__focus__":
                until = hub.now() + timedelta(milliseconds=data["hold_ms"])
                hub.publish("ui.focus", {"ref": data["ref"], "until": until.isoformat(timespec="milliseconds")}, about=about)
            elif kind == "__act__":
                hub.act(data["action"], data["target"], data.get("args"))
            elif kind == "__close_yes_window__":
                if hub.is_pending(data["id"]) and hub.state["orb"].get("state") == "waiting":
                    hub.publish("orb.state", hub.calm_orb())  # silently: no "No rush", no words at all
            elif kind == "__wait_answer__":
                waited = 0.0
                while self.speed and hub.is_pending(data["id"]) and waited < data["max_s"]:
                    await self._pause(0.25)
                    waited += 0.25
            elif kind == "__thread__":  # his spot is saved as it happens
                stamp = hub.now_iso()
                thread = {**data["thread"], "updated": stamp, "resume": {**data["thread"]["resume"], "at": stamp}}
                hub.publish("thread.updated", {"thread": thread}, about=about)
            elif kind == "window.push" and "pushed" not in data:
                hub.publish(kind, {**data, "pushed": hub.now_iso()}, about=about)
            else:
                hub.publish(kind, data, about=about)

    def start(self) -> None:
        self.stop()
        self.task = asyncio.get_running_loop().create_task(self.play())

    def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    @property
    def running(self) -> bool:
        return bool(self.task and not self.task.done())
