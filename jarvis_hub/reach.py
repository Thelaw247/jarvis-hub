"""Reach in the hub (REACH §5.3–§5.6, hub v0.5.0, demo-backed): what Jarvis can do, Claude agent tasks and their
permission asks, and the emails Jarvis flagged.

The hub calls `on_act(hub, action, target, args)` before its own rules (jarvis_hub/events.py Hub.act); it returns a
result for the actions it owns and None for everything else:

    set     reach:tool:<id> {value: bool}          a tool on or off
            reach:folders   {value: [paths]}       the allowed folders (nothing outside them, ever)
            reach:caps      {task_usd, day_usd}    the cost caps for agent tasks
    start   <task id>                              demo: play the "Design a phone stand in Fusion" task
    stop    <task id>                              "Stop that": the task ends (stopped, not failed); its ask goes
    approve <ask id> {scope?: "task"}              Allow (or Allow for this task) on an agent's permission ask
    decline <ask id> {text?}                       Deny; his reason goes to the agent
    undo    <task id> or a-<task id>               "Undo that": reverses what the task wrote, from its undo record

A permission ask is an ordinary approval (contracts/approval) with category "agent", so it sits in Your yes, uses the
same card and the same voice grammar. Its read-back is made here, by code, from the tool call itself: never from the
model's words (REACH §4). A task waiting on his answer while he is away is parked, never failed.

`seed(state)` adds the demo reach, one finished task and the flagged emails (Rail › Messages) in demo mode.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from datetime import datetime, timedelta

from . import settings
from .events import parse_time, rail_find, rail_put

AGENT = "agent"  # approval.category of an agent's permission ask
EXAMPLE_NOW = datetime.fromisoformat("2026-11-16T15:40:00")  # the day contracts/examples was written for
DEMO_TASK = "task-stand"
LIVE = {"running", "waiting", "parked"}
STEP_S = 2.4  # demo pacing between steps (divided by JARVIS_DEMO_SPEED)
AUTO_ALLOW_S = 9.0  # demo: his spoken "Allow." comes this long after the ask, if he is here and hasn't tapped
UNDO_FOR = timedelta(hours=24)
NEVER_ROOTS = re.compile(r"(^|\\|/)(appdata|windows|program files( \(x86\))?|programdata|\.ssh|\.gnupg|\$recycle\.bin)(\\|/|$)", re.I)
VERBS = {  # verb -> how the read-back says it
    "create": "create", "write": "write to", "move": "move", "rename": "rename", "delete": "move to the undo bin",
    "open": "open", "export": "export", "save": "save",
}

# The demo story: "Design a phone stand in Fusion" (REACH §3). Each step: (label, cost in USD, what Claude says).
STAND_GOAL = "Design a phone stand in Fusion"
STAND_STEPS = [
    ("Reading the brief", 0.02, "Brief: a stand for a phone, 65° back rest, fits the 3D printer bed. Fusion only."),
    ("Opening Fusion", 0.02, "Fusion is open with the MCP add-in running."),
    ("Sketching the base", 0.05, "Sketched a 90 × 70 mm base on the XY plane."),
    ("Extruding base", 0.06, "Extruded the base 6 mm."),
    ("Adding the back rest", 0.07, "Added a 65° back rest with a 12 mm lip for the phone."),
    ("Rounding the edges", 0.05, "Filleted the outside edges 2 mm."),
    ("Saving Stand v1.f3d", 0.04, "Saved Stand v1.f3d in Fusion Projects › Jarvis."),
]
STAND_SAVE = {"verb": "create", "name": "Stand v1.f3d", "where": "Fusion Projects", "app": "Fusion"}
STAND_THUMB = {"src": "/components/agent-task/demo/task-stand.webp", "kind": "design", "alt": "Fusion view: the phone stand, base and back rest"}


# ---- read-backs, made by code ------------------------------------------------------------------------------------
def _name(value: object, limit: int = 60) -> str:
    """A file or place name as it may be read out: one line, no quotes that could close the sentence, not too long."""
    text = " ".join(str(value or "").replace("'", "’").replace('"', "”").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_back(call: dict) -> str:
    """The plain question for an agent's tool call: "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?"
    `call` = {verb, name, where, to?}. Only these fields are read; whatever the model said about the call is not."""
    verb = str(call.get("verb") or "")
    name, where = _name(call.get("name")), _name(call.get("where"))
    if verb == "move" and call.get("to"):
        return f"Claude wants to move '{name}' from {where} to {_name(call['to'])}. Allow?"
    if verb == "rename" and call.get("to"):
        return f"Claude wants to rename '{name}' in {where} to '{_name(call['to'])}'. Allow?"
    if verb == "delete":
        return f"Claude wants to move '{name}' in {where} to the undo bin. Allow?"
    return f"Claude wants to {VERBS.get(verb, 'change')} '{name}' in {where}. Allow?"


def ask_kind(call: dict) -> str:
    """Asks of the same kind are "similar": the same verb in the same place."""
    return f"{call.get('verb', 'change')}:{_name(call.get('where'))}".lower()


def make_ask(task: dict, call: dict, now: str) -> dict:
    """An agent's permission request as an approval (contracts/approval): consequences first, the code read-back."""
    n = len(task.get("asks", [])) + 1
    verb = VERBS.get(str(call.get("verb")), "change")
    name, where = _name(call.get("name")), _name(call.get("where"))
    return {
        "id": f"ap-{task['id']}-{n}", "title": f"Claude: {verb} {name}", "status": "pending", "asked": now,
        "consequences": [f"{verb[:1].upper()}{verb[1:]}s '{name}' in {where}" if verb in ("create", "save", "export", "open")
                         else f"Claude will {verb} '{name}' in {where}",
                         f"Only for this task: {task['goal']}",
                         "Undo from the task puts it back"],
        "read_back": read_back(call), "category": AGENT, "reversible": True,
        "sources": [{"kind": "jarvis", "label": f"Claude task · {task['goal']}"}],
    }


# ---- checks on what he sets --------------------------------------------------------------------------------------
def clean_folders(value: object) -> tuple[list[str] | None, str]:
    """The allowed folders he typed, cleaned, or (None, why not). System folders, AppData and credential stores are
    never reachable (REACH §2)."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None, "The folders need to be a list of names. Nothing was changed."
    out: list[str] = []
    for raw in value:
        path = " ".join(raw.replace("/", "\\").split()).strip("\\ ")
        if not path:
            continue
        if ".." in path.split("\\") or len(path) > 260:
            return None, f"{_name(raw)} isn't a folder Jarvis can use. Nothing was changed."
        if NEVER_ROOTS.search(path) or re.match(r"^[a-z]:\\?$", path, re.I):
            return None, f"{_name(path)} stays off limits: system folders, AppData and whole drives are never reachable."
        if path.lower() not in (p.lower() for p in out):
            out.append(path)
    if len(out) > 20:
        return None, "That's more than 20 folders. Nothing was changed."
    return out, ""


def clean_caps(args: dict, caps: dict) -> tuple[dict | None, str]:
    task, day = args.get("task_usd", caps["task_usd"]), args.get("day_usd", caps["day_usd"])
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (task, day)):
        return None, "Caps are amounts in dollars. Nothing was changed."
    task, day = round(float(task), 2), round(float(day), 2)
    if not (0.1 <= task <= 50 and 0.1 <= day <= 200):
        return None, "A task cap goes from $0.10 to $50, a day cap from $0.10 to $200. Nothing was changed."
    if task > day:
        return None, "One task can't cost more than the whole day's cap. Nothing was changed."
    return {**caps, "task_usd": task, "day_usd": day}, ""


def over_cap(task: dict, reach: dict | None, next_cost: float) -> str:
    """Why the next step may not run ("" when it may): the task's own cap or what's left of today's."""
    if task["cost_usd"] + next_cost > task["cap_usd"] + 1e-9:
        return f"Stopped at the ${task['cap_usd']:g} cap for one task."
    caps = (reach or {}).get("caps")
    if caps and caps["spent_today_usd"] + task["cost_usd"] + next_cost > caps["day_usd"] + 1e-9:
        return f"Stopped at today's ${caps['day_usd']:g} cap."
    return ""


# ---- demo data ---------------------------------------------------------------------------------------------------
def _example(name: str) -> dict:
    return json.loads(settings.resource_path("contracts", "examples", f"{name}.json").read_text(encoding="utf-8"))


def _shift(value: object, by: timedelta) -> object:
    """Move every date-time in an example by `by`, so the demo's times sit on the demo day (which may be rebased)."""
    if isinstance(value, dict):
        return {k: _shift(v, by) for k, v in value.items()}
    if isinstance(value, list):
        return [_shift(v, by) for v in value]
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
        return (parse_time(value) + by).isoformat(timespec="seconds")
    return value


def catch_item(catch: dict) -> dict:
    """An email catch as a Rail item in Messages: one line with the reason. Reading only (no reply)."""
    return {"ref": f"mail-{catch['id']}", "slot": "messages", "kind": "message", "title": catch["line"], "at": catch["at"],
            "detail": f"{catch['from']} · {catch['source']['label'].split(' · ')[0]}"}


def seed(state: dict) -> None:
    """Demo only: the reach, one finished task and the flagged emails, unless the state already has them."""
    by = parse_time(state["now"]) - EXAMPLE_NOW
    if "reach" not in state:
        state["reach"] = _shift(_example("reach"), by)
    if "tasks" not in state:
        state["tasks"] = [_shift(_example("agent_task"), by)]
    rail = state.get("rail")
    if not rail or not any(slot.get("items") for slot in rail["slots"].values()):
        return  # a bare day (tests of the Rail's own rules) tracks nothing yet: the catches stay off its Rail
    for catch in (state["reach"].get("catches") or [])[::-1]:
        if not rail_find(rail, f"mail-{catch['id']}"):
            rail_put(rail, catch_item(catch))


# ---- tasks -------------------------------------------------------------------------------------------------------
def _task(hub, task_id: str) -> dict | None:
    return next((t for t in hub.state.get("tasks", []) if t["id"] == task_id), None)


def _say(task: dict, who: str, text: str, at: str) -> None:
    task.setdefault("transcript", []).append({"at": at, "who": who, "text": text})
    task["transcript"] = task["transcript"][-200:]


def _publish(hub, task: dict) -> None:
    """task.updated, and the working-on chip (a job) while it is live, so the Rail's Jarvis slot follows it too."""
    hub.publish("task.updated", {"task": copy.deepcopy(task)})
    step = task.get("step") or {"n": 0, "of": 1, "label": ""}
    job = {"id": task["id"], "label": f"Claude: {_name(task['goal'], 26)}"}  # short: the working-on chip sits beside the Rail
    if task["state"] in LIVE:
        detail = {"waiting": "Waiting for your yes", "parked": "Parked: waiting for your yes"}.get(task["state"], f"{step['label']} · {step['n']} of {step['of']}")
        hub.publish("job.progress", {**job, "state": "running", "progress": round(max(step["n"] - 1, 0) / step["of"], 2), "detail": detail})
    elif task["state"] in ("done", "stopped", "failed") and any(j["id"] == task["id"] for j in hub.state.get("jobs", [])):
        hub.publish("job.progress", {**job, "state": "done" if task["state"] == "done" else "failed", "progress": 1 if task["state"] == "done" else None,
                                     "detail": task.get("why") or "Finished"})


def _steps(labels: list[str], current: int) -> list[dict]:
    return [{"n": i + 1, "label": label, "state": "done" if i + 1 < current else "now" if i + 1 == current else "todo"} for i, label in enumerate(labels)]


def start_demo(hub) -> dict:
    """Start (or restart) the demo task: "Design a phone stand in Fusion"."""
    if hub.mode != "demo":
        return {"ok": False, "message": "Starting tasks arrives with jarvis-core. Nothing was started."}
    old = _task(hub, DEMO_TASK)
    if old and old["state"] in LIVE:
        return {"ok": True}  # already running
    if not hub.state["presence"].get("here", True):
        # he just pressed the button, so he is here: without this a demo day that ended with him away parks the ask
        hub.publish("presence.changed", {**hub.state["presence"], "here": True})
    now = hub.now_iso()
    caps = (hub.state.get("reach") or {}).get("caps") or {"task_usd": 1}
    task = {
        "id": DEMO_TASK, "goal": STAND_GOAL, "app": "Fusion", "state": "running", "started": now,
        "step": {"n": 1, "of": len(STAND_STEPS), "label": STAND_STEPS[0][0]},
        "steps": _steps([s[0] for s in STAND_STEPS], 1), "files": [], "cost_usd": STAND_STEPS[0][1], "cap_usd": caps["task_usd"],
        "asks": [], "allowed": [], "transcript": [], "undo": None,
        "brief": {"folders": ["Jarvis Workspace"], "apps": ["Fusion"], "done_when": "Stand v1.f3d is saved in Fusion Projects"},
    }
    _say(task, "you", "Design a phone stand in Fusion.", now)
    _say(task, "jarvis", "On it. Claude has Fusion and Jarvis Workspace, nothing else.", now)
    _say(task, "claude", STAND_STEPS[0][2], now)
    _publish(hub, task)
    hub.publish("caption.show", {"text": "On it.", "source": {"kind": "jarvis", "label": "Jarvis"}, "ttl_ms": 2500})
    hub.publish("window.push", {"id": f"w-{DEMO_TASK}", "type": "agent_task", "title": STAND_GOAL, "ref": DEMO_TASK, "size": "2x1",
                                "pushed": now, "slot": "jarvis"})
    _run_later(hub)
    return {"ok": True}


def advance(hub, task_id: str = DEMO_TASK) -> str:
    """One beat of the demo task. Returns its state afterwards. Runs the next step, asks before the save, and
    finishes once he has allowed it. Waiting or parked tasks don't move here: his answer moves them."""
    task = copy.deepcopy(_task(hub, task_id))
    if not task or task["state"] not in ("running",):
        return task["state"] if task else "gone"
    now, n = hub.now_iso(), task["step"]["n"]
    labels = [s[0] for s in STAND_STEPS]
    if n < len(STAND_STEPS) - 1:  # the next ordinary step
        label, cost, said = STAND_STEPS[n]
        why = over_cap(task, hub.state.get("reach"), cost)
        if why:
            return _end(hub, task, "stopped", why)
        task.update(step={"n": n + 1, "of": len(labels), "label": label}, steps=_steps(labels, n + 1), cost_usd=round(task["cost_usd"] + cost, 2))
        if n + 1 >= 4:
            task["thumb"] = STAND_THUMB  # once there's a body, the window shows the app's view
        _say(task, "claude", said, now)
        _publish(hub, task)
        return task["state"]
    save = next((a for a in task["asks"] if a["kind"] == ask_kind(STAND_SAVE)), None)
    if save is None or save["answer"] == "waiting":  # the save is a write outside the brief's allow list: ask him
        if ask_kind(STAND_SAVE) in task.get("allowed", []):
            return _finish_save(hub, task)
        return _ask(hub, task, STAND_SAVE)
    if save["answer"] in ("allowed", "allowed_for_task"):
        return _finish_save(hub, task)
    return task["state"]


def _ask(hub, task: dict, call: dict) -> str:
    now = hub.now_iso()
    label, _cost, _said = STAND_STEPS[-1]
    approval = make_ask(task, call, now)
    kind = ask_kind(call)
    similar = sum(1 for a in task["asks"] if a["kind"] == kind) + 1
    task["asks"].append({"id": approval["id"], "kind": kind, "answer": "waiting", "similar": similar})
    task.update(state="waiting" if hub.state["presence"].get("here", True) else "parked",
                step={"n": len(STAND_STEPS), "of": len(STAND_STEPS), "label": label}, steps=_steps([s[0] for s in STAND_STEPS], len(STAND_STEPS)))
    _say(task, "jarvis", approval["read_back"], now)
    _publish(hub, task)
    hub.publish("approval.pending", approval)
    hub.publish("window.push", {"id": f"w-{approval['id']}", "type": "approval", "title": "Waiting for your yes", "ref": approval["id"], "size": "2x2", "pushed": now})
    hub.publish("caption.show", {"text": approval["read_back"], "source": {"kind": "jarvis", "label": "Jarvis"}, "ttl_ms": 8000}, about=approval["id"])
    hub.publish("orb.state", {"state": "waiting", "countdown_s": 8, "window_s": 8})
    return task["state"]


def _finish_save(hub, task: dict) -> str:
    now = hub.now_iso()
    label, cost, said = STAND_STEPS[-1]
    why = over_cap(task, hub.state.get("reach"), cost)
    if why:
        return _end(hub, task, "stopped", why)
    task["cost_usd"] = round(task["cost_usd"] + cost, 2)
    task["files"].append({"path": "Fusion Projects\\Jarvis\\Stand v1.f3d", "change": "created", "where": "Fusion"})
    _say(task, "claude", said, now)
    return _end(hub, task, "done", "")


def _end(hub, task: dict, state: str, why: str) -> str:
    now = hub.now_iso()
    task.update(state=state, ended=now)
    if why:
        task["why"] = why
    task["steps"] = [{**s, "state": "done" if state == "done" or s["state"] == "done" else "skipped"} for s in task["steps"]]
    if state == "done":
        task["step"] = {**task["step"], "label": f"Saved {task['files'][-1]['path'].split(chr(92))[-1]}" if task["files"] else "Finished"}
    task["undo"] = {"until": (hub.now() + UNDO_FOR).isoformat(timespec="seconds"), "label": "24 h"} if task["files"] else None
    for ask in task["asks"]:  # an ask nobody answered goes with the task
        if ask["answer"] == "waiting" and hub.is_pending(ask["id"]):
            ask["answer"] = "denied"
            hub._resolve(ask["id"], "declined")
    reach = hub.state.get("reach")
    if reach:  # what it cost counts against today's cap
        reach = copy.deepcopy(reach)
        reach["caps"]["spent_today_usd"] = round(reach["caps"]["spent_today_usd"] + task["cost_usd"], 2)
        for tool in reach["tools"]:
            if tool["id"] in ("claude-agent", "fusion-mcp"):
                tool["last_used"] = now
        hub.publish("reach.updated", reach)
    _publish(hub, task)
    if state == "done":
        hub._receipt(f"Claude: {task['goal']}", "You asked for it.", "files", id=f"a-{task['id']}", branch_id="you",
                     result=f"Done. Created {', '.join(f['path'].split(chr(92))[-1] for f in task['files'])} in Fusion Projects",
                     undo=task["undo"])
        hub.publish("toast", {"id": f"t-{task['id']}", "kind": "success", "text": f"Claude finished: {task['files'][-1]['path'].split(chr(92))[-1]} is in Fusion Projects." if task["files"] else "Claude finished.", "ttl_ms": 6000})
    return state


def park_if_away(hub, task_id: str = DEMO_TASK) -> bool:
    """A task waiting on his answer while he's away is parked (not failed); it comes back to waiting when he's here."""
    task = _task(hub, task_id)
    if not task or task["state"] not in ("waiting", "parked"):
        return False
    here = hub.state["presence"].get("here", True)
    want = "waiting" if here else "parked"
    if task["state"] == want:
        return False
    task = copy.deepcopy(task)
    task["state"] = want
    _say(task, "jarvis", "Parked until you answer." if want == "parked" else "You're back: it still waits for your yes.", hub.now_iso())
    _publish(hub, task)
    return True


def _run_later(hub) -> None:
    """Pace the demo task on the event loop (none in scripts and tests: they call advance() themselves)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    speed = float(os.environ.get("JARVIS_DEMO_SPEED", "1") or 1) or 1
    state = hub.state  # a demo reset replaces the state: then this run stops

    async def run() -> None:
        waited = 0.0
        while hub.state is state:
            await asyncio.sleep(STEP_S / speed)
            task = _task(hub, DEMO_TASK)
            if hub.state is not state or not task or task["state"] not in LIVE:
                return
            if task["state"] == "running":
                waited = 0.0
                advance(hub)
                continue
            park_if_away(hub)
            waited += STEP_S / speed
            ask = next((a for a in task["asks"] if a["answer"] == "waiting"), None)
            if ask and task["state"] == "waiting" and waited * speed >= AUTO_ALLOW_S:  # his spoken "Allow." (T0 grammar)
                hub.publish("caption.show", {"text": "Allow.", "source": {"kind": "you", "label": "You"}, "ttl_ms": 2000})
                answer(hub, ask["id"], "approve", {})

    loop.create_task(run())


def answer(hub, approval_id: str, action: str, args: dict) -> dict:
    """Allow, Allow for this task, or Deny on an agent's permission ask."""
    task = next((t for t in hub.state.get("tasks", []) if any(a["id"] == approval_id for a in t["asks"])), None)
    approval = next((a for a in hub.state["approvals"] if a["id"] == approval_id), None)
    if not approval or not task:
        return {"ok": False, "message": "That ask isn't here any more."}
    if approval["status"] != "pending":
        same = {"approve": "approved", "decline": "declined"}.get(action) == approval["status"]
        return {"ok": True} if same else {"ok": False, "message": "That one has already been answered."}
    task = copy.deepcopy(task)
    ask = next(a for a in task["asks"] if a["id"] == approval_id)
    now = hub.now_iso()
    if action == "approve":
        for_task = args.get("scope") == "task"
        if for_task and ask.get("similar", 1) < 2:
            return {"ok": False, "message": "Allow for this task comes after the second ask like this one. Nothing was allowed."}
        ask["answer"] = "allowed_for_task" if for_task else "allowed"
        if for_task and ask["kind"] not in task.setdefault("allowed", []):
            task["allowed"].append(ask["kind"])
        _say(task, "you", "Allow for the rest of this task." if for_task else "Allow.", now)
        hub._resolve(approval_id, "approved")
        task["state"] = "running"
        _publish(hub, task)
        if task["id"] == DEMO_TASK:
            advance(hub)
        return {"ok": True}
    reason = " ".join(str(args.get("text") or "").split())[:200]
    ask["answer"] = "denied"
    _say(task, "you", f"No. {reason}" if reason else "No.", now)
    hub._resolve(approval_id, "declined")
    _say(task, "claude", "Understood. I won't save it; the design stays open in Fusion, unsaved.", now)
    _end(hub, task, "stopped", f"You said no{': ' + reason if reason else ''}.")
    return {"ok": True}


def stop(hub, task_id: str) -> dict:
    task = _task(hub, task_id)
    if not task:
        return {"ok": False, "message": "I can't find that task any more."}
    if task["state"] not in LIVE:
        return {"ok": True}  # already finished or stopped
    task = copy.deepcopy(task)
    _say(task, "you", "Stop that.", hub.now_iso())
    _end(hub, task, "stopped", "You stopped it.")
    return {"ok": True}


def undo(hub, task_id: str) -> dict:
    task = _task(hub, task_id)
    if not task:
        return {"ok": False, "message": "I can't find that task any more."}
    if task["state"] == "undone":
        return {"ok": True}  # pressed twice: already undone
    if task["state"] in LIVE:
        return {"ok": False, "message": "Stop the task first, then undo it."}
    if not task.get("undo") or not task["files"]:
        return {"ok": False, "message": "That task didn't change anything, so there's nothing to undo."}
    if parse_time(task["undo"]["until"]) <= hub.now():
        return {"ok": False, "message": "The undo window has passed."}
    task = copy.deepcopy(task)
    now = hub.now_iso()
    restored = []
    for f in reversed(task["files"]):  # undo in reverse: what it made goes to the undo bin, what it moved goes back
        name = f["path"].split("\\")[-1]
        restored.append({"path": f["path"], "change": "deleted" if f["change"] == "created" else "restored",
                         "where": "undo bin, 30 days" if f["change"] == "created" else "back where it was"})
        _say(task, "jarvis", f"Put {name} {'in the undo bin' if f['change'] == 'created' else 'back'}.", now)
    task.update(state="undone", undo=None, files=task["files"] + restored)
    hub.publish("task.updated", {"task": task})
    receipt = next((a for a in hub.state["actions"] if a["id"] == f"a-{task_id}"), None)
    if receipt and not receipt.get("undone"):
        hub.publish("activity.added", {**receipt, "undone": True})
    hub.publish("toast", {"id": f"t-undo-{task_id}", "kind": "success", "text": "Undone. What it made is in the undo bin for 30 days.", "ttl_ms": 5000})
    return {"ok": True}


def set_reach(hub, target: str, args: dict) -> dict:
    reach = copy.deepcopy(hub.state.get("reach"))
    if not reach:
        return {"ok": False, "message": "Reach settings aren't loaded yet. Nothing was changed."}
    if target.startswith("reach:tool:"):
        tool = next((t for t in reach["tools"] if t["id"] == target[11:]), None)
        if not tool or not isinstance(args.get("value"), bool):
            return {"ok": False, "message": "That tool can't be changed like that. Nothing was changed."}
        if args["value"] and tool["status"] == "needs_sign_in":
            return {"ok": False, "message": f"{tool['name']} needs you to sign in first. Nothing was changed."}
        tool["on"] = args["value"]
        if tool["status"] in ("connected", "off"):
            tool["status"] = "connected" if tool["on"] else "off"
    elif target == "reach:folders":
        folders, why = clean_folders(args.get("value"))
        if folders is None:
            return {"ok": False, "message": why}
        reach["folders"] = folders
    elif target == "reach:caps":
        caps, why = clean_caps(args, reach["caps"])
        if caps is None:
            return {"ok": False, "message": why}
        reach["caps"] = caps
    else:
        return {"ok": False, "message": "That setting isn't here. Nothing was changed."}
    if reach != hub.state.get("reach"):
        hub.publish("reach.updated", reach)
    return {"ok": True}


def on_act(hub, action: str, target: str, args: dict) -> dict | None:
    """The actions this module owns (see the top of the file); None lets the hub's own rules run."""
    if action == "set" and target.startswith("reach:"):
        return set_reach(hub, target, args)
    if action == "start":
        if target != DEMO_TASK:
            return {"ok": False, "message": "Starting tasks arrives with jarvis-core. Nothing was started."}
        return start_demo(hub)
    if action == "stop":
        return stop(hub, target)
    if action in ("approve", "decline"):
        approval = next((a for a in hub.state["approvals"] if a["id"] == target), None)
        if approval and approval.get("category") == AGENT:
            return answer(hub, target, action, args)
        return None
    if action == "undo":
        task_id = target[2:] if target.startswith("a-task-") else target
        if _task(hub, task_id):
            return undo(hub, task_id)
    return None
