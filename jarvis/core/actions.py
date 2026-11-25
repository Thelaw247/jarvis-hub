"""UI actions from the hub (`POST /api/act`, contracts/act.schema.json).

M0.1 has no action layer yet (approvals, executor and undo come in P1, RUNTIME §9), so every action answers
safely: nothing is changed and the hub is told so in words. Later packages replace one stub at a time with
`Actions.handle(name, handler)`; the action names come from the contract, so nothing outside it is accepted.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from . import REPO
from .logs import EventLog

NOT_YET = "Jarvis can't do that yet. Nothing was changed."
NO_DEMO = "There's no demo on Jarvis core. Nothing was changed."
log = EventLog("jarvis.core.actions")
Handler = Callable[[str, dict], Awaitable[dict]]


def contract_actions() -> frozenset[str]:
    schema = json.loads((REPO / "contracts" / "act.schema.json").read_text(encoding="utf-8"))
    return frozenset(schema["properties"]["action"]["enum"])


class Actions:
    def __init__(self) -> None:
        self.names = contract_actions()
        self._handlers: dict[str, Handler] = {}

    def handle(self, action: str, handler: Handler) -> None:
        if action not in self.names:
            raise ValueError(f"not a contract action: {action}")
        self._handlers[action] = handler

    async def act(self, action: str, target: str, args: dict) -> dict:
        """Answer one action. Stubs change nothing. T0 for stubs."""
        handler = self._handlers.get(action)
        if handler is None:
            log.info("act.not_implemented", kind=action)
            return {"ok": False, "message": NO_DEMO if action == "demo" else NOT_YET}
        return await handler(target, args)
