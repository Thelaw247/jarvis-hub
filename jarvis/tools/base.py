"""What every tool shares: its spec (read from TOOL.md), the context it runs in, and its result.

A tool is a folder in ``jarvis/tools/<id>/``: ``TOOL.md`` (front matter + the description Claude reads) and, unless it
is an Anthropic server tool, ``handler.py`` with ``async def run(args: dict, ctx: ToolContext) -> Result | str``.
JARVIS_DESIGN_TOOLS.md §3.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Tier = Literal["read", "ask", "never"]
Speed = Literal["instant", "fast", "slow", "task"]
Voice = Literal["loaded", "deferred", "off"]

TIERS = ("read", "ask", "never")
SPEEDS = ("instant", "fast", "slow", "task")
VOICE = ("loaded", "deferred", "off")
WHERE = ("Laptop A", "Laptop B", "Cloud")
# Fillers and the spoken turn: tools at these speeds are worth "Let me see." while they run (VOICE §fillers)
FILLER_SPEEDS = ("fast", "slow")


class ToolError(Exception):
    """A tool refused or failed in a way Claude should read (returned as an is_error tool result, never raised
    past the registry). The message is plain words: what went wrong and what to do instead."""


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    description: str           # the TOOL.md body: purpose, When to use, When not to use, Prefer, Cost and speed
    input_schema: dict
    rung: int = 1
    tier: Tier = "read"
    speed: Speed = "fast"
    voice: Voice = "deferred"
    task: bool = True          # offered to the task brain (Agent SDK) too
    where: str = "Laptop B"
    reads: str = ""
    writes: str = "nothing"
    server: dict | None = None  # an Anthropic server tool: the exact tool param (web_search, web_fetch)
    needs: tuple[str, ...] = ()  # context services it can't run without ("browser", "canvas", "memory", "tasks")
    folder: Path | None = None

    @property
    def summary(self) -> str:
        """The first line of the description: the one-line index entry (abilities card, prompt index)."""
        para = " ".join(self.description.strip().split("\n\n")[0].split())
        if not para:
            return self.name
        cut = para.find(". ")
        first = para if cut < 0 else para[:cut + 1]
        return first if len(first) <= 160 else first[:157].rsplit(" ", 1)[0] + "…"


@dataclass
class Result:
    """What a handler returns. ``content`` goes back to Claude (text or content blocks); ``show`` is an optional
    hub event to publish (a window, a card) so voice and screen move together; ``note`` goes to the latency log."""

    content: str | list[dict]
    is_error: bool = False
    show: tuple[str, dict] | None = None
    note: str | None = None


@dataclass
class ToolContext:
    """The services a tool may use. Each is optional: a tool whose ``needs`` aren't present reports itself as
    off (or needs_sign_in) instead of failing mid-turn."""

    root: Path
    publish: Callable[[str, dict], Awaitable[None]] | None = None   # hub events (window.push, task.updated…)
    memory: Any = None
    browser: Any = None        # jarvis.browser.service.BrowserService
    canvas: Any = None         # jarvis.canvas.client.CanvasClient
    tasks: Any = None          # jarvis.tasks.runner.TaskRunner
    documents: Any = None      # jarvis.documents.reader.DocumentReader
    questions: Any = None      # jarvis.tools.questions.Questions (ask_dewet)
    calendar: Any = None       # jarvis.reach.calendar.CalendarClient (his Google Calendar, read-only)
    classes: Any = None        # jarvis.reach.classes.ClassContent (his schedule, due work and courses, local files)
    resume: Callable[[str], Awaitable[bool]] | None = None   # Jarvis picks the conversation back up (voice.prompt)
    allowed_roots: tuple[Path, ...] = ()
    session_id: str | None = None
    turn_id: str | None = None
    origin: str = "voice"      # voice · task · hub
    desktop: Any = None        # jarvis.reach.desktop.Desktop (his open windows on this laptop; Windows only)
    learner: Any = None        # jarvis.core.learning.Learner (remember, forget; what he says into memory)
    here: bool = False         # he is at the laptop this core runs on (so a file opened here opens in front of him)
    refresh: Any = None        # async (): redraw the hub's day, due work and warnings now (after class data changed)
    hands: Any = None          # async (kind, args) -> dict: the voice program on the laptop he IS at, when that is another one
    extra: dict[str, Any] = field(default_factory=dict)

    def has(self, need: str) -> bool:
        return getattr(self, need, None) is not None

    async def show(self, type: str, data: dict) -> None:
        if self.publish is not None:
            await self.publish(type, data)


Handler = Callable[[dict, ToolContext], Awaitable["Result | str"]]


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
