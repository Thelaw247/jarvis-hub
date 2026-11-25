"""The hub's state, its event stream and the rules for applying events and UI actions.

Everything here speaks the contracts in contracts/ (v2). The demo backend and, later, jarvis-core
publish events through `Hub.publish`; every connected window gets them over SSE.

Nothing gets away (HUD v2 §6): a window that is closed, pushed out by a sixth, cleared, or whose approval ran
out is docked into its Rail slot, never deleted. Only done or archive removes a thing. Real changes, what
Jarvis said, finished jobs and expired approvals leave a "since you looked" mark until he has seen them.
"""
from __future__ import annotations

import asyncio
import copy
import importlib
import json
import time
from datetime import datetime, timedelta
from typing import Any

from .demo.keys import yes_flag
from .demo.places import answer as map_answer
from .schema import is_valid, setting_schema

CONTRACT_V = 2  # `v` in the state and in every event envelope
MAX_WINDOWS = 5  # pushed windows; the screen shows the Now card plus these (ui/core/windows-core.js MAX_PUSHED)
SLOTS = ("yes", "today", "homework", "messages", "jarvis", "parked")  # the Rail's six fixed slots (rail.schema.json)
PURE_VIEWS = {"chart", "next_up", "map"}  # views of nothing in particular: they just close, there is no thing to dock
SLOT_OF = {"approval": "yes", "timeline": "today", "timer": "today", "countdown": "homework", "file": "homework",
           "fact": "jarvis", "unsorted": "jarvis", "notice": "jarvis", "branch_card": "parked",
           "agent_task": "jarvis"}  # window type -> slot
KIND_OF = {"approval": "approval", "timeline": "event", "timer": "event", "countdown": "due", "file": "file",
           "fact": "fact", "unsorted": "fact", "notice": "notice", "branch_card": "branch",
           "agent_task": "job"}  # window type -> thing
DOCK_REASONS = {"closed", "lifetime", "evicted", "aside", "cleared", "expired"}
SAID_MAX = 10  # spoken lines kept under the Jarvis slot
PARK_AFTER = timedelta(days=7)  # idle this long, a Rail item folds into Parked
SAID_REF = "jarvis:said"  # the mark for "Jarvis said something since you looked"
RESUME_SCHEMA = {"type": "object", "required": ["label", "source", "at"], "additionalProperties": False,
                 "properties": {"page": {"type": "integer", "minimum": 1}, "y": {"type": "number"}, "seconds": {"type": "number", "minimum": 0},
                                "label": {"type": "string"},
                                "source": {"enum": ["inferred", "confirmed"]}, "at": {"type": "string"}}}  # thread.schema.json resume
REST_STATES = {"idle", "standby", "muted", "offline", "alert"}  # from one of these, listening is a wake
# What the hub shows in words follows Jarvis's register (HUD v2 §9.2): no "Got it", no "Okay", nothing that only
# confirms the obvious. A "no" gets no words at all: its window leaves and Activity keeps the quiet receipt.
ASK_AGAIN = "It comes back with that change, for your yes."
CAPTION_TTL_MS = 6000  # the caption's default time on screen (ui/components/caption)
SIZES = ["1x1", "2x1", "1x2", "2x2", "3x2", "4x2"]  # window.schema.json
GROW = {"1x1": "2x1", "2x1": "2x2", "1x2": "2x2", "2x2": "3x2", "3x2": "4x2", "4x2": "4x2"}  # "bigger": wider, never shorter


def parse_time(value: str) -> datetime:
    """Contract times are local unless they carry an offset; the hub clock is local and naive."""
    when = datetime.fromisoformat(value)
    return when.astimezone().replace(tzinfo=None) if when.tzinfo else when


def _upsert(items: list[dict], item: dict, front: bool = False) -> None:
    for i, old in enumerate(items):
        if old.get("id") == item.get("id"):
            items[i] = item
            return
    items.insert(0, item) if front else items.append(item)


def empty_rail() -> dict:
    rail = {"slots": {name: {"items": []} for name in SLOTS}}
    rail["slots"]["jarvis"]["said"] = []
    return rail


def ensure_v2(state: dict) -> dict:
    """Give a v1 state the v2 keys (Rail, marks, threads, focus), so older fixtures and backends still load."""
    state["v"] = CONTRACT_V
    rail = state.setdefault("rail", empty_rail())
    for name in SLOTS:
        rail.setdefault("slots", {}).setdefault(name, {"items": []})
    state.setdefault("marks", {})
    state.setdefault("threads", [])
    state.setdefault("focus", None)
    return state


def slot_for(window: dict) -> str | None:
    """The Rail slot a window docks into, or None for a pure view (which just closes)."""
    if window.get("slot") in SLOTS:
        return window["slot"]
    return None if window.get("type") in PURE_VIEWS else SLOT_OF.get(window.get("type"), "jarvis")


def rail_put(rail: dict, item: dict) -> None:
    """Put a thing on the Rail: one item per ref in the whole Rail, newest first in its slot."""
    rail_drop(rail, lambda old: old["ref"] == item["ref"])
    rail["slots"][item["slot"]]["items"].insert(0, item)


def rail_drop(rail: dict, gone) -> None:
    for slot in rail["slots"].values():
        slot["items"] = [item for item in slot["items"] if not gone(item)]


def rail_find(rail: dict, target: str) -> dict | None:
    """A Rail item by its ref, or by the id of its docked window."""
    items = [item for slot in rail["slots"].values() for item in slot["items"]]
    return next((i for i in items if i["ref"] == target), None) or next((i for i in items if i.get("window", {}).get("id") == target), None)


def dock_window(state: dict, window: dict, at: str, slot: str | None = None) -> None:
    """Take a window off the screen and fold it into its Rail slot. The window is kept whole for recall."""
    state["windows"] = [w for w in state["windows"] if w["id"] != window["id"]]
    slot = slot if slot in SLOTS else slot_for(window)
    if slot is None:
        return
    item = {"ref": window.get("ref") or window["id"], "slot": slot, "kind": KIND_OF.get(window.get("type"), "notice"),
            "title": window["title"], "at": at, "window": {**window, "docked": True, "slot": slot}}
    for key in ("thumb", "tier"):
        if key in window:
            item[key] = window[key]
    rail_put(state["rail"], item)


def fold_idle(rail: dict, now: datetime) -> bool:
    """Things idle for 7 days fold into Parked's count, so the Rail never becomes a pile. True if anything moved."""
    parked, moved = rail["slots"]["parked"], False
    for name in SLOTS[:-1]:
        slot = rail["slots"][name]
        idle = [item for item in slot["items"] if parse_time(item["at"]) + PARK_AFTER <= now]
        if idle:
            slot["items"] = [item for item in slot["items"] if item not in idle]
            parked["items"] += [{**item, "slot": "parked", "from": name, "state": "parked"} for item in idle]
            moved = True
    if moved or parked.get("count", len(parked["items"])) != len(parked["items"]):
        parked["count"] = len(parked["items"])
    return moved


def apply_event(state: dict, kind: str, data: dict, at: str | None = None) -> None:
    """Fold one event into the state (the UI's store.js does the same in JavaScript). `at` is the event's time."""
    at = at or state.get("now", "")
    if "rail" not in state or "marks" not in state:
        ensure_v2(state)
    if kind == "orb.state":
        state["orb"] = data
    elif kind == "nowcard.updated":
        state["now_card"] = data
    elif kind == "branch.updated":
        _upsert(state["branches"], data["branch"])
        if data.get("card"):
            state["cards"][data["branch"]["id"]] = data["card"]
    elif kind == "window.push":
        rail_drop(state["rail"], lambda item: item.get("window", {}).get("id") == data["id"])  # recalled: back on screen
        if data.get("docked"):  # pushed straight into its slot, without ever taking the screen
            dock_window(state, data, at)
            return
        old = next((i for i, w in enumerate(state["windows"]) if w["id"] == data["id"]), None)
        if old is None:
            state["windows"] = [*state["windows"], data]
        else:  # the same window again (pin, resize, new data) keeps its place
            state["windows"][old] = data
        while len(state["windows"]) > MAX_WINDOWS:  # when a 6th arrives the oldest unpinned window docks; it is never deleted
            windows = state["windows"]
            dock_window(state, next((w for w in windows if not w.get("pinned")), windows[0]), at)
    elif kind == "window.dock":
        for window in [w for w in state["windows"] if data.get("all") or w["id"] == data.get("id")]:
            dock_window(state, window, at, data.get("slot"))
    elif kind == "window.order":
        rank = {window_id: i for i, window_id in enumerate(data["ids"])}
        state["windows"] = sorted(state["windows"], key=lambda w: rank.get(w["id"], len(rank)))  # stable: unnamed ones keep their order, after
    elif kind == "window.close":  # only for done, archive and pure views; a v1 "close everything" docks instead
        if data.get("all"):
            apply_event(state, "window.dock", {"all": True}, at)
        else:
            state["windows"] = [w for w in state["windows"] if w["id"] != data.get("id")]
    elif kind == "rail.updated":
        state["rail"] = data
    elif kind == "marks.updated":
        state["marks"] = data["marks"]
    elif kind == "thread.updated":
        if data.get("archived"):
            state["threads"] = [t for t in state["threads"] if t["id"] != data["id"]]
        else:
            _upsert(state["threads"], data["thread"], front=True)
    elif kind == "ui.focus":
        state["focus"] = data if data.get("ref") else None
    elif kind == "caption.show":  # an empty line clears the caption
        state["caption"] = data if data.get("text") else None
    elif kind == "approval.pending":
        _upsert(state["approvals"], data, front=True)
    elif kind == "approval.resolved":
        for approval in state["approvals"]:
            if approval["id"] == data["id"]:
                approval["status"] = data["status"]
                if data["status"] == "expired":  # it ran out unanswered: it docks under Your yes instead of vanishing
                    for window in [w for w in state["windows"] if w.get("type") == "approval" and w.get("ref") == data["id"]]:
                        dock_window(state, window, at, "yes")
                    if not rail_find(state["rail"], data["id"]):
                        rail_put(state["rail"], {"ref": data["id"], "slot": "yes", "kind": "approval", "title": approval["title"], "at": at})
        if data["status"] != "expired":  # answered: done, so it leaves the Rail
            rail_drop(state["rail"], lambda item: item["ref"] == data["id"])
    elif kind == "activity.added":
        _upsert(state["actions"], data, front=True)
    elif kind == "job.progress":
        _upsert(state["jobs"], data)
        state["jobs"] = [j for j in state["jobs"] if j["state"] == "running"]
    elif kind == "toast":
        _upsert(state["toasts"], data)
    elif kind == "presence.changed":
        state["presence"] = {**state["presence"], **data}
    elif kind == "fact.updated":
        if data.get("forgotten"):
            state["facts"] = [f for f in state["facts"] if f["id"] != data["id"]]
        else:
            _upsert(state["facts"], data["fact"], front=True)
    elif kind == "day.updated":
        state["day"] = data
    elif kind == "settings.updated":
        state["settings"] = data
    elif kind == "metrics.updated":  # v0.18.0: Under the hood, from the core's own numbers
        state["metrics"] = data
    elif kind == "reach.updated":  # R3: what Jarvis can do (contracts/reach)
        state["reach"] = data
    elif kind == "task.updated":  # R3: a Claude agent task (contracts/agent_task), newest first
        _upsert(state.setdefault("tasks", []), data["task"], front=True)
    elif kind == "keys.updated":  # K2: a key that fell back raises a Your-yes item; it goes when the row recovers
        row = data["row"]
        flag = yes_flag(row, at)
        if flag:
            rail_put(state["rail"], flag)
        else:
            rail_drop(state["rail"], lambda item: item["ref"] == f"keys:{row['id']}")


def say_time(value: str) -> str:
    """A time the way he'd say it: 'Wed 8 pm', 'Thu 11:59 pm'; a bare HH:MM gives '4 pm'."""
    when = parse_time(value if "T" in value else f"2000-01-01T{value}")
    hour = f"{when.hour % 12 or 12}{f':{when.minute:02d}' if when.minute else ''} {'am' if when.hour < 12 else 'pm'}"
    return f"{when:%a} {hour}" if "T" in value else hour


def changes(kind: str, old: dict | None, data: dict) -> dict[str, str]:
    """What an update really changed, as {ref: the change in words}. An edit in place must never be silent."""
    found: dict[str, str] = {}
    if kind == "nowcard.updated" and old:
        was, now = old.get("next_up") or {}, data.get("next_up") or {}
        if now and was and (was.get("title"), was.get("when"), was.get("where")) != (now.get("title"), now.get("when"), now.get("where")):
            if was.get("title") == now.get("title"):
                moved = [f"{a} → {b}" for a, b in ((was.get("when"), now.get("when")), (was.get("where"), now.get("where"))) if a != b and a and b]
                found["now_card"] = f"{now['title']} moved {', '.join(moved)}" if moved else f"Next up changed: {now['title']}"
            else:
                found["now_card"] = f"Next up changed: {was['title']} → {now['title']}, {now['when']}"
        flag, flag_was = (data.get("flag") or {}).get("text"), (old.get("flag") or {}).get("text")
        if flag and flag != flag_was:
            found["now_card:flag"] = f"{flag_was} → {flag}" if flag_was else flag
    elif kind == "day.updated" and old:
        before = {item["id"]: item for item in old.get("items", [])}
        for item in data.get("items", []):
            was = before.pop(item["id"], None)
            if was is None:
                found[item["id"]] = f"Added: {item['title']}, {say_time(item['start'])}"
            elif (was["start"], was["end"]) != (item["start"], item["end"]):
                found[item["id"]] = f"{item['title']} moved {say_time(was['start'])} → {say_time(item['start'])}"
            elif was.get("where") != item.get("where") and item.get("where"):
                found[item["id"]] = f"{item['title']} room changed {was.get('where') or 'none'} → {item['where']}"
            elif was.get("state") != item.get("state") and item.get("state") in ("moved", "missed"):
                found[item["id"]] = f"{item['title']} was {item['state']}" + (f" to {item['moved_to']}" if item.get("moved_to") else "")
        for item in before.values():
            found[item["id"]] = f"Removed: {item['title']}, {say_time(item['start'])}"
    elif kind == "branch.updated" and old:
        branch, was, card = data["branch"], old.get("branch"), data.get("card")
        if was and was.get("status") != branch.get("status"):
            found[branch["id"]] = f"{branch['name']}: {was.get('status')} → {branch['status']}"
        elif was and (was.get("counts") or {}).get("due") != (branch.get("counts") or {}).get("due") and "due" in (branch.get("counts") or {}):
            found[branch["id"]] = f"{branch['name']}: things due {(was.get('counts') or {}).get('due', 0)} → {branch['counts']['due']}"
        if card and old.get("card"):
            before = {due["id"]: due for due in old["card"].get("due", [])}
            for due in card.get("due", []):
                due_was = before.get(due["id"])
                if due_was is None:
                    found[due["id"]] = f"New: {due['title']}, due {say_time(due['due'])}"
                elif due_was["due"] != due["due"]:
                    found[due["id"]] = f"Due moved {say_time(due_was['due'])} → {say_time(due['due'])}"
    return found


class Hub:
    """Holds the state and fans events out to every connected client."""

    def __init__(self, state: dict, mode: str = "demo") -> None:
        ensure_v2(state)
        self._initial = copy.deepcopy(state)
        self.state = copy.deepcopy(state)
        self.state["mode"] = mode
        self.mode = mode
        self._clients: set[asyncio.Queue] = set()
        self._clock_base = datetime.fromisoformat(state["now"])
        self._started = time.monotonic()
        self._seq = 0
        self._timers: list[asyncio.TimerHandle] = []
        self._until: dict[str, datetime] = {}  # when each toast ("toast:<id>") and the caption leave the screen
        self._caption_about: str | None = None  # the approval the current caption is about, if any
        self.tweaks: dict[str, str] = {}  # approval id -> what he asked to change ("Change it"), in his words
        self._last_wake: str | None = None  # when he last woke Jarvis (orb_state.last_wake picks the wake beat)
        self._rail_ext = None  # jarvis_hub/rail.py (N4), if it exists: refresh(state, now) derives the Rail's own items
        try:
            self._rail_ext = getattr(importlib.import_module("jarvis_hub.rail"), "refresh", None)
        except ImportError:
            pass
        self._threads_ext = None  # jarvis_hub/threads.py (N6), if it exists: on_act(action, thread, args, now)
        try:
            self._threads_ext = getattr(importlib.import_module("jarvis_hub.threads"), "on_act", None)
        except ImportError:
            pass
        self._reach_ext = None  # jarvis_hub/reach.py (R3), if it exists: on_act(hub, action, target, args) -> dict | None
        try:
            reach = importlib.import_module("jarvis_hub.reach")
            self._reach_ext = getattr(reach, "on_act", None)
            if mode == "demo":
                reach.seed(self.state)  # demo reach, tasks and email catches (not in the shared fixture)
                self._initial = copy.deepcopy(self.state)
        except ImportError:
            pass
        self._refresh_rail()

    def _refresh_rail(self) -> None:
        """Fold idle things and let jarvis_hub/rail.py derive the Rail's own items, so the first state a screen loads
        already has the whole Rail and the first event doesn't look like a Rail change."""
        fold_idle(self.state["rail"], self.now())
        if self._rail_ext:
            self._rail_ext(self.state, self.now())

    # -- clock: the demo day has its own clock that starts at the fixture's time and runs forward --
    def now(self) -> datetime:
        if self.mode == "live":
            return datetime.now()
        return self._clock_base + timedelta(seconds=time.monotonic() - self._started)

    def now_iso(self) -> str:
        return self.now().isoformat(timespec="seconds")

    def snapshot(self) -> dict:
        self.expire_due()
        self.prune()
        self._refresh_rail()
        return {**self.state, "now": self.now_iso()}

    def prune(self) -> None:
        """Drop toasts and the caption once their time is up, so a reload doesn't show them again."""
        now = self.now()
        gone = {key for key, until in self._until.items() if until <= now}
        if not gone:
            return
        self.state["toasts"] = [t for t in self.state["toasts"] if f"toast:{t['id']}" not in gone]
        if "caption" in gone:
            self.state["caption"] = None
            self._caption_about = None
        for key in gone:
            del self._until[key]

    def _drop_focus(self) -> None:
        """The focus cue lets go on its own once `until` has passed (screens time it out themselves too)."""
        focus = self.state.get("focus")
        if focus and focus.get("until") and parse_time(focus["until"]) <= self.now():
            self.state["focus"] = None

    def reset(self) -> None:
        mode = self.mode
        self.state = copy.deepcopy(self._initial)
        self.state["mode"] = mode
        self._started = time.monotonic()
        for timer in self._timers:
            timer.cancel()
        self._timers = []
        self._until = {}
        self._caption_about = None
        self.tweaks = {}
        self._last_wake = None
        self._refresh_rail()

    # -- time limits: an approval that runs out is resolved as expired at its expiry time --
    def expire_due(self) -> None:
        now = self.now()
        for approval in list(self.state["approvals"]):
            if approval["status"] == "pending" and approval.get("expires") and parse_time(approval["expires"]) <= now:
                self._resolve(approval["id"], "expired", calm=False)

    def _schedule_expiry(self, approval: dict) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no event loop (scripts, tests): expiry is still checked whenever the state is read or an action arrives
        delay = (parse_time(approval["expires"]) - self.now()).total_seconds()
        self._timers = [t for t in self._timers if not t.cancelled() and t.when() > loop.time()]
        self._timers.append(loop.call_later(max(delay, 0) + 0.05, self.expire_due))

    def _resolve(self, approval_id: str, status: str, calm: bool = True) -> None:
        """Close an approval. After his answer the orb always rests; on expiry only if it was waiting for this one."""
        self.publish("approval.resolved", {"id": approval_id, "status": status})  # expired: its window docks under Your yes
        if status != "expired":
            self.publish("window.close", {"id": f"w-{approval_id}"})  # answered, so done: the one case a thing's window closes
        if self._caption_about == approval_id and self.state.get("caption"):
            self.publish("caption.show", {"text": ""})  # its read-back no longer applies
        nothing_waiting = not any(a["status"] == "pending" for a in self.state["approvals"])
        if calm or (self.state["orb"].get("state") == "waiting" and nothing_waiting):
            self.publish("orb.state", self.calm_orb())

    # -- events --
    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._clients.discard(queue)

    @property
    def clients(self) -> int:
        return len(self._clients)

    def is_pending(self, approval_id: str) -> bool:
        return any(a["id"] == approval_id and a["status"] == "pending" for a in self.state["approvals"])

    def calm_orb(self) -> dict:
        """The orb at rest: idle, or muted while the mic is off."""
        return {"state": "muted" if self.state["settings"].get("muted") else "idle"}

    def publish(self, kind: str, data: dict, about: str | None = None) -> dict:
        """Apply an event and send it to every client. `about` names the approval a step belongs to, if any."""
        if kind == "orb.state" and data.get("state") == "waiting" and not any(a["status"] == "pending" for a in self.state["approvals"]):
            data = self.calm_orb()  # "waiting for your yes" with nothing waiting would hold the orb (and presence) forever
        if kind == "orb.state" and data.get("state") == "listening" and self.state["orb"].get("state") in REST_STATES:
            # a wake: say when the wake before it was, so every screen picks the same beat (full or short)
            data = {"last_wake": self._last_wake, **data}
            self._last_wake = self.now_iso()
        self.prune()
        self._drop_focus()
        derived = kind in ("rail.updated", "marks.updated")
        before = None if derived else (json.dumps(self.state["rail"]), json.dumps(self.state["marks"]))
        old = self._before(kind, data)
        ts = self.now_iso()
        apply_event(self.state, kind, copy.deepcopy(data), ts)
        self._track_time_on_screen(kind, data, about)
        if kind == "approval.pending" and data.get("status") == "pending" and data.get("expires"):
            self._schedule_expiry(data)
        event = {"v": CONTRACT_V, "type": kind, "ts": ts, "data": data}
        self._send(event)
        if not derived:  # the Rail and the marks live here, so every screen is told when this event changed them
            self._notice(kind, data, old, ts)
            self._refresh_rail()
            if json.dumps(self.state["rail"]) != before[0]:
                self._send({"v": CONTRACT_V, "type": "rail.updated", "ts": ts, "data": copy.deepcopy(self.state["rail"])})
            if json.dumps(self.state["marks"]) != before[1]:
                self._send({"v": CONTRACT_V, "type": "marks.updated", "ts": ts, "data": {"marks": copy.deepcopy(self.state["marks"])}})
        return event

    def _send(self, event: dict) -> None:
        for queue in list(self._clients):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # a stuck client must never slow the others down
                self._clients.discard(queue)

    # -- nothing gets away: marks, spoken lines and finished jobs (HUD v2 §6.2–6.4) --
    def _before(self, kind: str, data: dict) -> dict | None:
        """The part of the state an update is about to overwrite, kept so the change can be shown as a change."""
        s = self.state
        if kind == "nowcard.updated":
            return s.get("now_card")
        if kind == "day.updated":
            return s.get("day")
        if kind == "branch.updated":
            branch_id = data["branch"]["id"]
            return {"branch": next((b for b in s["branches"] if b["id"] == branch_id), None), "card": s["cards"].get(branch_id)}
        return None

    def mark(self, ref: str, what: str, at: str | None = None) -> None:
        """Leave a "since you looked" mark on a thing. One per ref; a newer change replaces the older one."""
        self.state["marks"][ref] = {"what": what, "at": at or self.now_iso()}

    def _said(self, text: str, kind: str, at: str, source: dict | None = None) -> None:
        """Keep what Jarvis said: captions and toasts leave the screen, but the last 10 lines stay under the Jarvis slot."""
        slot = self.state["rail"]["slots"]["jarvis"]
        lines = slot.get("said", [])
        if lines and lines[0]["text"] == text:
            return
        line = {"text": text, "at": at, "kind": kind}
        if source:
            line["source"] = source
        slot["said"] = [line, *lines][:SAID_MAX]
        self.mark(SAID_REF, f"Jarvis said: {text}", at)

    def _notice(self, kind: str, data: dict, old: dict | None, at: str) -> None:
        for ref, what in changes(kind, old, data).items():
            self.mark(ref, what, at)
        if kind == "caption.show" and data.get("text") and (data.get("source") or {}).get("kind") != "you":  # his own words aren't Jarvis's
            self._said(data["text"], "caption", at, data.get("source"))
        elif kind == "toast":
            self._said(data["text"], "toast", at)
        elif kind == "job.progress" and data["state"] != "running":  # a finished job drops out of `jobs`; it stays on the Rail
            item = {"ref": data["id"], "slot": "jarvis", "kind": "job", "title": data["label"], "at": at}
            if data["state"] == "done":
                item["state"] = "done"
            rail_put(self.state["rail"], item)
            self.mark(data["id"], f"{'Finished' if data['state'] == 'done' else 'Did not finish'}: {data['label']}", at)
        elif kind == "approval.resolved" and data["status"] == "expired":
            title = next((a["title"] for a in self.state["approvals"] if a["id"] == data["id"]), "An offer")
            self.mark(data["id"], f"Ran out unanswered: {title}. Nothing was done.", at)

    def _track_time_on_screen(self, kind: str, data: dict, about: str | None) -> None:
        if kind == "toast":
            if data.get("ttl_ms"):
                self._until[f"toast:{data['id']}"] = self.now() + timedelta(milliseconds=data["ttl_ms"])
            else:  # a toast without a time stays until it is dismissed
                self._until.pop(f"toast:{data['id']}", None)
        elif kind == "caption.show":
            self._caption_about = about if data.get("text") else None
            if data.get("text"):
                self._until["caption"] = self.now() + timedelta(milliseconds=data.get("ttl_ms") or CAPTION_TTL_MS)
            else:
                self._until.pop("caption", None)

    def _reorder(self, order: list[dict]) -> None:
        """Put the windows in a new order: one real reorder, never close + push (that would look like new arrivals)."""
        ids = [w["id"] for w in order]
        if ids != [w["id"] for w in self.state["windows"]]:
            self.publish("window.order", {"ids": ids})

    def _drop_offer(self, approval_id: str) -> None:
        """Once it's done, the now card stops offering it. Offer `o-<x>` is the same piece of work as approval `ap-<x>`."""
        card = self.state.get("now_card")
        offer_id = "o-" + approval_id.removeprefix("ap-")
        if card and any(o["id"] == offer_id for o in card.get("ready_to_offer", [])):
            card = copy.deepcopy(card)
            card["ready_to_offer"] = [o for o in card["ready_to_offer"] if o["id"] != offer_id]
            self.publish("nowcard.updated", card)

    def _seen(self, ref: str | None) -> None:
        """Clear the mark on one thing, or every mark. Shown on the ambient screen is not seen: only this clears."""
        marks = {} if ref is None else {k: v for k, v in self.state["marks"].items() if k != ref}
        if marks != self.state["marks"]:
            self.publish("marks.updated", {"marks": marks})

    # -- UI actions (demo rules; live mode forwards these to jarvis-core instead) --
    def _find(self, key: str, target: str) -> dict | None:
        return next((x for x in self.state[key] if x["id"] == target), None)

    def _receipt(self, what: str, why: str, category: str, **extra: Any) -> None:
        self._seq += 1
        now = self.now()
        self.publish("activity.added", {
            "id": f"a-ui-{self._seq}", "ts": now.isoformat(timespec="seconds"), "kind": "done", "what": what, "why": why,
            "category": category, "sources": [{"kind": "you", "label": "You · just now"}],
            "undo": {"until": (now + timedelta(hours=24)).isoformat(timespec="seconds"), "label": "24 h"}, **extra})

    def act(self, action: str, target: str, args: dict | None = None) -> dict:
        args = args or {}
        self.expire_due()
        if self._reach_ext:  # R3: reach settings, agent tasks and their permission asks go to jarvis_hub/reach.py first
            handled = self._reach_ext(self, action, target, args)
            if handled is not None:
                return handled
        s = self.state
        if target.startswith("branch:"):  # renaming, moving and archiving branches needs jarvis-core
            self.publish("toast", {"id": f"t-{target}", "kind": "info", "text": "Branches can't be changed in demo mode yet. Nothing was changed.", "ttl_ms": 6000})
        elif action == "set" and target.startswith("source:"):
            source = next((x for x in s["settings"].get("sources", []) if x["id"] == target[7:]), None)
            if not source or not isinstance(args.get("value"), bool):
                return {"ok": False, "message": "That setting can't be changed like that. Nothing was changed."}
            source["on"] = args["value"]
            source["status"] = "ok" if source["on"] else "off"
            self.publish("settings.updated", s["settings"])
        elif action == "change" and any(p["id"] == target for p in s["day"].get("proposals", [])):
            day = copy.deepcopy(s["day"])  # Tweak on a proposed change: it goes away and comes back changed
            day["proposals"] = [p for p in day["proposals"] if p["id"] != target]
            self.publish("day.updated", day)
            self.publish("toast", {"id": f"t-{target}", "kind": "info", "text": ASK_AGAIN, "ttl_ms": 5000})
        elif action in ("approve", "decline", "change"):
            approval = self._find("approvals", target)
            status = {"approve": "approved", "decline": "declined", "change": "changed"}[action]
            if approval and approval["status"] == status:
                return {"ok": True}  # the same answer twice (a double click): already done, nothing more happens
            if approval and approval["status"] == "expired":
                return {"ok": False, "message": "This offer ran out. Nothing was done."}
            if not approval or approval["status"] != "pending":
                return {"ok": False, "message": "That one has already been answered."}
            self._resolve(target, status)  # answered: the orb always comes to rest, never stays "waiting"
            if status == "approved":
                self._drop_offer(target)
                self._receipt(approval["title"], "You said yes.", approval.get("category", "calendar"),
                              result="Done. " + approval["consequences"][0], branch_id=approval.get("branch_id", "you"))
            elif status == "declined":  # a "no" is a receipt too: a quiet row with nothing to undo
                self._receipt(approval["title"], "You said no. Nothing was changed.", approval.get("category", "calendar"),
                              id=f"declined-{target}", undo=None, branch_id=approval.get("branch_id", "you"))
            else:
                text = " ".join(str(args.get("text") or "").split())[:400]
                if text:  # his tweak, in his words, kept for when Jarvis asks again (live mode hands it to jarvis-core)
                    self.tweaks[target] = text
                said = ASK_AGAIN if text else "Tell me what to change and it comes back for your yes."
                self.publish("toast", {"id": f"t-{target}", "kind": "info", "text": said, "ttl_ms": 6000})
        elif action == "undo":
            receipt = self._find("actions", target)
            if receipt and receipt.get("undone"):
                return {"ok": True}  # undo pressed twice: it is already undone
            if not receipt or not receipt.get("undo"):
                return {"ok": False, "message": "That can't be undone any more."}
            if parse_time(receipt["undo"]["until"]) <= self.now():
                return {"ok": False, "message": "The undo window has passed."}
            self.publish("activity.added", {**receipt, "undone": True})
            self.publish("toast", {"id": f"t-undo-{target}", "kind": "success", "text": "Undone.", "ttl_ms": 4000})
        elif action == "move":
            window = self._find("windows", target)
            if window:
                rest = [w for w in s["windows"] if w["id"] != target]
                self._reorder([window, *rest] if args.get("to") == "left" else [*rest, window])
        elif action in ("pin", "unpin", "resize"):
            window = self._find("windows", target)
            if window:
                if action in ("pin", "unpin"):
                    window = {**window, "pinned": action == "pin"}
                elif action == "resize":
                    size = args.get("size") or GROW.get(window.get("size", "1x1"), "2x1")
                    if size not in SIZES:
                        return {"ok": False, "message": "Windows come in 1x1, 2x1, 1x2, 2x2, 3x2 and 4x2."}
                    window = {**window, "size": size}
                self.publish("window.push", window)
        elif action in ("close", "dock"):  # closing a window docks its thing into the Rail; only a pure view really closes
            if self._find("windows", target):
                event = {"id": target, "reason": args["reason"] if args.get("reason") in DOCK_REASONS else "closed"}
                if args.get("slot") in SLOTS:
                    event["slot"] = args["slot"]
                self.publish("window.dock", event)
        elif action == "close_all":  # CLEAR VIEW: everything docks, nothing is deleted
            if s["windows"]:
                self.publish("window.dock", {"all": True, "reason": "cleared"})
        elif action == "order":
            ids = args.get("ids")
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                return {"ok": False, "message": "A new order needs the window ids. Nothing was moved."}
            on_screen = {w["id"]: w for w in s["windows"]}
            self._reorder([on_screen[i] for i in ids if i in on_screen] + [w for w in s["windows"] if w["id"] not in ids])
        elif action == "recall":  # bring a docked thing back as the window it was
            item = rail_find(s["rail"], target)
            if not item or not item.get("window"):
                return {"ok": False, "message": "That isn't on the Rail any more."}
            window = {k: v for k, v in item["window"].items() if k != "docked"}
            self.publish("window.push", {**window, "pushed": self.now_iso()})
            self._seen(item["ref"])
        elif action == "seen":  # he looked: clear one mark, or all of them ("mark all seen")
            self._seen(None if target == "all" else target)
        elif action == "archive":  # done with it: the only way a thing leaves the Rail
            rail = copy.deepcopy(s["rail"])
            item = rail_find(rail, target)
            ref = item["ref"] if item else target
            rail_drop(rail, lambda i: i["ref"] == ref)
            for window in [w for w in s["windows"] if w["id"] == target or w.get("ref") == ref]:
                self.publish("window.close", {"id": window["id"]})
            if rail != s["rail"]:
                self.publish("rail.updated", rail)
            self._seen(ref)
        elif action in ("resume_save", "resume_accept"):
            thread = copy.deepcopy(self._find("threads", target))
            if not thread:
                return {"ok": False, "message": "I can't find that piece of work any more."}
            merged = None
            if self._threads_ext:  # threads.py first: it keeps the dwell beside the thread and re-decides the spot
                try:               # from the reading session (a less precise spot beats a wrong precise one)
                    merged = self._threads_ext(action, copy.deepcopy(thread), args, self.now_iso())
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    merged = None  # an odd session never loses the spot: the plain rules below still save it
            if merged is not None and (merged.get("resume") is None or is_valid(merged["resume"], RESUME_SCHEMA)):
                self.publish("thread.updated", {"thread": merged})
                return {"ok": True}
            if action == "resume_accept":  # he took the offer, so the spot is no longer a guess
                if not thread.get("resume"):
                    return {"ok": False, "message": "There's no saved spot for that yet."}
                thread["resume"] = {**thread["resume"], "source": "confirmed"}
            else:  # a local note, not an outward write: it needs no yes
                resume = {"label": str(args.get("label") or "")[:80], "at": self.now_iso(),
                          "source": "confirmed" if args.get("confirmed") is True else "inferred",
                          **{key: args[key] for key in ("page", "y", "seconds") if key in args}}
                if not resume["label"] or not is_valid(resume, RESUME_SCHEMA):
                    return {"ok": False, "message": "A saved spot needs a label and, if given, a page number or seconds. Nothing was saved."}
                thread["resume"] = resume
            thread["updated"] = self.now_iso()
            self.publish("thread.updated", {"thread": thread})
        elif action in ("confirm", "edit", "pin_rule", "keep_mine", "use_theirs", "file"):
            fact = self._find("facts", target)
            if not fact:
                return {"ok": False, "message": "I can't find that any more."}
            fact = copy.deepcopy(fact)
            if action == "confirm":
                fact.update(confidence="sure", last_confirmed=self.now_iso(), source={"kind": "you", "label": "You · today"})
                fact.pop("basis", None)
            elif action == "edit":
                fact.setdefault("history", []).insert(0, {"was": fact["statement"], "when": "until today"})
                fact.update(statement=str(args.get("statement", fact["statement"]))[:400], confidence="sure",
                            source={"kind": "you", "label": "You · today"}, last_confirmed=self.now_iso())
            elif action == "pin_rule":
                fact["pinned"] = not fact.get("pinned", False)
            elif action in ("keep_mine", "use_theirs") and fact.get("conflict"):
                fact["conflict"]["kept"] = "mine" if action == "keep_mine" else "theirs"
            elif action == "file":
                fact["branch_id"] = args.get("branch_id") or fact.get("guess_branch_id", fact["branch_id"])
                fact.pop("guess_branch_id", None)
            self.publish("fact.updated", {"fact": fact})
        elif action == "forget":
            if self._find("facts", target):
                self.publish("fact.updated", {"id": target, "forgotten": True})
                self.publish("toast", {"id": f"t-forget-{target}", "kind": "info", "text": "Forgotten.", "ttl_ms": 4000})
        elif action in ("mute", "unmute"):
            s["settings"]["muted"] = action == "mute"
            self.publish("settings.updated", s["settings"])
            self.publish("orb.state", {"state": "muted" if action == "mute" else "idle"})
        elif action == "set":  # only known settings, and only values settings.schema.json allows
            schema = setting_schema(target)
            if schema is None or "value" not in args or not is_valid(args["value"], schema):
                return {"ok": False, "message": "That setting can't be changed like that. Nothing was changed."}
            s["settings"][target] = copy.deepcopy(args["value"])
            self.publish("settings.updated", s["settings"])
        elif action == "revoke":
            s["settings"]["standing_permissions"] = [p for p in s["settings"].get("standing_permissions", []) if p["id"] != target]
            self.publish("settings.updated", s["settings"])
        elif action in ("apply", "skip"):
            day = copy.deepcopy(s["day"])
            proposal = next((p for p in day.get("proposals", []) if p["id"] == target), None)
            if proposal:
                day["proposals"].remove(proposal)
                self.publish("day.updated", day)
                if action == "apply":
                    self._receipt(proposal["text"], "You applied a proposed change.", "calendar", result=proposal["changes"][0])
        elif action == "open":
            self.publish("nav.go", {"path": target})
        elif action == "less":  # "less of this": every explanation comes with a control
            self.publish("toast", {"id": f"t-less-{target}", "kind": "info", "text": "Less of this from now on.", "ttl_ms": 4000})
        elif action == "wrong":
            self.publish("toast", {"id": f"t-wrong-{target}", "kind": "info", "text": "I'll check that and stop relying on it.", "ttl_ms": 5000})
        elif action == "ask":
            if not map_answer(self, str(args.get("text", ""))):  # R2: "show me where my lab is" opens the map window
                self.publish("caption.show", {"text": "In demo mode I can't answer new questions yet.", "source": None, "ttl_ms": 5000})
        return {"ok": True}
