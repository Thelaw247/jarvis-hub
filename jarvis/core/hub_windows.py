"""The hub's window buttons in live mode (v0.15.3): close, pin, bigger, move, clear view, bring back, done.

Until now only `set` was real on the core, so a window Jarvis opened (a page he pulled up) could not be closed or
pinned: the hub answered "Jarvis can't do that yet" (2026-11-19). These actions only change what is on his own
screen. Nothing outside Jarvis is touched, so none of them needs a yes. The rules are the demo hub's
(jarvis_hub/events.py act): closing a window docks its thing into the Rail and nothing is deleted; only "done"
(archive) takes a thing off the Rail. Every change is a hub event on the bus, folded in by the same reducer.
"""
from __future__ import annotations

import copy

from jarvis_hub.events import DOCK_REASONS, GROW, SIZES, SLOTS, rail_drop, rail_find

from .bus import now_iso
from .logs import EventLog

log = EventLog("jarvis.core.windows")
GONE = "That window isn't on screen any more."
ACTIONS = ("close", "dock", "close_all", "pin", "unpin", "resize", "move", "order", "recall", "seen", "archive")


def wire(core) -> None:
    def windows() -> list[dict]:
        return core.state.state["windows"]

    def find(target: str) -> dict | None:
        return next((w for w in windows() if w["id"] == target), None)

    def reorder(order: list[dict]) -> None:
        ids = [w["id"] for w in order]
        if ids != [w["id"] for w in windows()]:
            core.bus.publish("window.order", {"ids": ids})

    def seen(ref: str | None) -> None:
        marks = core.state.state.get("marks", {})
        left = {} if ref is None else {k: v for k, v in marks.items() if k != ref}
        if left != marks:
            core.bus.publish("marks.updated", {"marks": left})

    async def act(action: str, target: str, args: dict) -> dict:
        log.info("window.act", kind=action)
        if action in ("close", "dock"):
            if not find(target):
                return {"ok": True}                       # already gone: closing twice is not an error
            event = {"id": target, "reason": args["reason"] if args.get("reason") in DOCK_REASONS else "closed"}
            if args.get("slot") in SLOTS:
                event["slot"] = args["slot"]
            core.bus.publish("window.dock", event)
        elif action == "close_all":
            if windows():
                core.bus.publish("window.dock", {"all": True, "reason": "cleared"})
        elif action in ("pin", "unpin", "resize"):
            window = find(target)
            if not window:
                return {"ok": False, "message": GONE}
            if action == "resize":
                size = args.get("size") or GROW.get(window.get("size", "1x1"), "2x1")
                if size not in SIZES:
                    return {"ok": False, "message": "Windows come in 1x1, 2x1, 1x2, 2x2, 3x2 and 4x2."}
                window = {**window, "size": size}
            else:
                window = {**window, "pinned": action == "pin"}
            core.bus.publish("window.push", copy.deepcopy(window))
        elif action == "move":
            window = find(target)
            if not window:
                return {"ok": False, "message": GONE}
            rest = [w for w in windows() if w["id"] != target]
            reorder([window, *rest] if args.get("to") == "left" else [*rest, window])
        elif action == "order":
            ids = args.get("ids")
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                return {"ok": False, "message": "A new order needs the window ids. Nothing was moved."}
            on_screen = {w["id"]: w for w in windows()}
            reorder([on_screen[i] for i in ids if i in on_screen] + [w for w in windows() if w["id"] not in ids])
        elif action == "recall":
            item = rail_find(core.state.state["rail"], target)
            if not item or not item.get("window"):
                return {"ok": False, "message": "That isn't on the Rail any more."}
            window = {k: v for k, v in item["window"].items() if k != "docked"}
            core.bus.publish("window.push", {**copy.deepcopy(window), "pushed": now_iso()})
            seen(item["ref"])
        elif action == "seen":
            seen(None if target == "all" else target)
        elif action == "archive":
            rail = copy.deepcopy(core.state.state["rail"])
            item = rail_find(rail, target)
            ref = item["ref"] if item else target
            rail_drop(rail, lambda i: i["ref"] == ref)
            for window in [w for w in windows() if w["id"] == target or w.get("ref") == ref]:
                core.bus.publish("window.close", {"id": window["id"]})
            if rail != core.state.state["rail"]:
                core.bus.publish("rail.updated", rail)
            seen(ref)
        return {"ok": True}

    for name in ACTIONS:
        core.actions.handle(name, (lambda n: (lambda target, args: act(n, target, args)))(name))
