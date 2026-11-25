"""Controls in live mode (v0.12.4): the hub's `set` action changes one of his settings on the core.

Until now every action on the core answered "Jarvis can't do that yet" (actions.py stubs), so no switch in Controls
worked against the real core. `set` is the first real one: only settings that settings.schema.json lets `set`
change, only values it allows (the same check the demo hub uses), saved to data\\settings.json so they survive a
restart, and published as settings.updated so every screen follows at once. Lists (standing permissions, sources)
keep their own actions, still stubs.
"""
from __future__ import annotations

import copy

from jarvis_hub.schema import is_valid, setting_schema

from .logs import EventLog

log = EventLog("jarvis.core.settings")
REFUSED = "That setting can't be changed like that. Nothing was changed."


def restore(core, settings) -> None:
    """Put his saved Controls choices back into the state the hub reads (at start)."""
    saved = {k: v for k, v in settings.hub().items()
             if setting_schema(k) is not None and is_valid(v, setting_schema(k))}
    if saved:
        core.state.state["settings"] = {**core.state.state.get("settings", {}), **copy.deepcopy(saved)}


def wire(core, settings) -> None:
    async def set_setting(target: str, args: dict) -> dict:
        schema = setting_schema(target)
        if schema is None or "value" not in args or not is_valid(args["value"], schema):
            return {"ok": False, "message": REFUSED}
        value = copy.deepcopy(args["value"])
        settings.set_hub(target, value)
        current = copy.deepcopy(core.state.state.get("settings", {}))
        current[target] = value
        core.bus.publish("settings.updated", current)
        log.info("settings.set", kind=target)
        for act in FOLLOWERS.get(target, ()):      # a setting something acts on at once (the mic's mute)
            try:
                await act(value)
            except Exception as exc:  # noqa: BLE001 - the setting is saved either way
                log.warning("settings.follow_failed", kind=target, error=type(exc).__name__)
        return {"ok": True}

    core.actions.handle("set", set_setting)


FOLLOWERS: dict[str, list] = {}


def follow(core, settings, target: str, act) -> None:
    """Call ``await act(value)`` whenever this setting is changed from the hub."""
    FOLLOWERS.setdefault(target, []).clear()
    FOLLOWERS[target].append(act)


def reflect(core, settings, target: str, value) -> None:
    """Something other than the hub changed what a setting describes (he said "mute the microphone"): show it."""
    current = copy.deepcopy(core.state.state.get("settings", {}))
    if current.get(target) == value:
        return
    settings.set_hub(target, value)
    current[target] = value
    core.bus.publish("settings.updated", current)
