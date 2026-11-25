"""Jarvis's tools in the core: the registry plus the services behind it (JARVIS_DESIGN_TOOLS.md §2).

Each service is optional: when its packages aren't installed yet (setup-tools.bat), its tools show as off in
Controls › Reach and the voice brain simply doesn't get them. Nothing here blocks start-up: the browser starts on its
first use, the memory store and the abilities sync run in the background.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

from jarvis.tools.base import ToolContext
from jarvis.tools.questions import Questions
from jarvis.tools.registry import Registry, default_registry
from jarvis.tools.voice import VoiceTools

log = logging.getLogger("jarvis.core.toolkit")


def installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


WARM = ("playwright.async_api", "jarvis.browser.driver", "jarvis.canvas.client", "anthropic")


def warm_imports() -> None:
    """Import the slow modules off the event loop (v0.12.3)."""
    import importlib  # noqa: PLC0415

    for name in WARM:
        with contextlib.suppress(Exception):
            importlib.import_module(name)


def default_roots(root: Path) -> tuple[Path, ...]:
    """The folders documents may be read from (REACH §2 defaults), those that exist."""
    home = Path.home()
    onedrive = Path(os.environ.get("OneDrive", home / "OneDrive"))
    wanted = [home / "Documents", home / "Desktop", home / "Downloads", onedrive / "Documents",
              onedrive / "Desktop", onedrive / "Desktop" / "Class Content", onedrive / "Class Content",
              onedrive / "Class Management", root / "workspace"]
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    return tuple(p for p in wanted if p.exists())


class LazyKeyed:
    """The Claude key, looked up at call time (it may be added or rotated in the hub while the core runs)."""

    def __init__(self, keys: Any) -> None:
        self.keys = keys

    async def call(self, run: Any) -> Any:
        manager = getattr(self.keys, "manager", None)
        if manager is None:
            raise RuntimeError("keys not available")
        return await manager.client("anthropic").call(run)


class Toolkit:
    def __init__(self, root: Path, bus: Any, keys: Any, *, registry: Registry | None = None,
                 memory: Any = None, voice: Any = None) -> None:
        self.root = Path(root)
        self.bus = bus
        self.keys = keys
        self.registry = registry or default_registry()
        from jarvis.reach.desktop import Desktop  # noqa: PLC0415

        desk = Desktop()
        self.desktop = desk if desk.ok else None   # arranging his windows: only on his Windows laptop
        self.learner = None   # jarvis.core.learning.Learner, set by the core once memory is up
        self.registry.remember(self.root / "data" / "tool_use.json")   # what ran and what was refused survives a restart
        self.memory = memory
        self.voice = voice
        self.keyed = LazyKeyed(keys)
        self.downloads = self.root / "browser" / "downloads"
        self.roots = default_roots(self.root)
        self.browser = self.canvas = self.documents = self.tasks = None
        if installed("playwright") and installed("anthropic"):
            from jarvis.browser import BrowserService  # noqa: PLC0415
            from jarvis.canvas import CanvasClient, playwright_fetch  # noqa: PLC0415

            self.browser = BrowserService(self.root, keyed=self.keyed)
            self.canvas = CanvasClient(playwright_fetch(self.browser), downloads=self.downloads)
        if installed("pymupdf") or installed("fitz"):
            from jarvis.documents import DocumentReader  # noqa: PLC0415
            from jarvis.documents.vision import make_vision  # noqa: PLC0415

            self.documents = DocumentReader(self.roots, self.downloads,
                                            vision=make_vision(self.keyed) if installed("anthropic") else None)
        from jarvis.reach.classes import ClassContent, find_root  # noqa: PLC0415

        found = find_root()
        self.classes = ClassContent(found) if found is not None else None   # his schedule, due work and courses (local files)
        self.calendar = None
        if installed("httpx"):
            from jarvis.reach.calendar import CalendarClient  # noqa: PLC0415

            self.calendar = CalendarClient(keys)   # needs the Composio key (Controls › Keys); says so if it's missing
        from jarvis.tasks import TaskRunner  # noqa: PLC0415

        self.tasks = TaskRunner(self.root, self.registry, self.make_ctx, self.keyed, publish=self.publish,
                                announce=self.announce)
        self.questions = Questions(self.announce)

    def _hands(self):
        """The laptop he is talking from, when it isn't this one: its voice program opens things and moves windows there."""
        voice = self.voice
        far = getattr(voice, "client", None) is not None and not getattr(voice, "client_here", False)
        return getattr(voice, "ask_client", None) if far else None

    # ------------------------------------------------------------------ context
    def make_ctx(self, origin: str = "voice") -> ToolContext:
        return ToolContext(root=self.root, publish=self.publish, memory=self.memory, browser=self.browser,
                           canvas=self.canvas, tasks=self.tasks, documents=self.documents, questions=self.questions,
                           calendar=self.calendar, classes=self.classes, here=bool(getattr(self.voice, "client_here", False)), hands=self._hands(), refresh=getattr(self, "refresh_hub", None), learner=self.learner, desktop=self.desktop, resume=self.resume, allowed_roots=self.roots, origin=origin)

    def voice_tools(self) -> VoiceTools:
        return VoiceTools(self.registry, lambda: self.make_ctx("voice"))

    # ------------------------------------------------------------------ events
    async def publish(self, type: str, data: dict) -> None:
        with contextlib.suppress(Exception):
            self.bus.publish(type, dict(data))

    async def announce(self, text: str) -> None:
        """Say it when he's free (voice), and always show it (caption)."""
        spoken = False
        if self.voice is not None:
            with contextlib.suppress(Exception):
                spoken = await self.voice.announce(text)
        if not spoken:
            await self.publish("caption.show", {"text": text, "ttl_ms": 12000})

    async def resume(self, note: str) -> bool:
        """Something Jarvis was waiting for has happened (he signed in): carry on aloud with what he asked."""
        if self.voice is None:
            return False
        with contextlib.suppress(Exception):
            return bool(await self.voice.prompt(note))
        return False

    def reach(self) -> dict:
        """contracts/reach.schema.json for Controls › Reach."""
        return {"tools": self.registry.reach_rows(self.make_ctx()), "folders": [str(p) for p in self.roots][:20],
                "apps": [], "caps": {"task_usd": 1.0, "day_usd": 5.0, "spent_today_usd": round(self.spent_today(), 2)}}

    def spent_today(self) -> float:
        today = __import__("time").strftime("%Y-%m-%d")
        return sum(t.cost_usd for t in (self.tasks.tasks.values() if self.tasks else []) if t.started.startswith(today))

    async def start(self) -> None:
        self.bus.publish("reach.updated", self.reach())
        if self.memory is not None:
            asyncio.create_task(self._sync_abilities())
        if self.browser is not None:
            # Load the browser's code now, in a worker thread: done on first use it froze the core for ~6 s on
            # Laptop B (Windows checks every new file), and the first sign-in or Canvas question paid for it.
            self._warm = asyncio.create_task(asyncio.to_thread(warm_imports))

    async def _sync_abilities(self) -> None:
        from jarvis.tools.abilities import sync_abilities  # noqa: PLC0415

        try:
            await sync_abilities(self.memory, self.registry, self.make_ctx(), skills=list_skills(self.root))
        except Exception as e:
            log.warning("abilities.failed", extra={"error": type(e).__name__})

    async def aclose(self) -> None:
        if self.tasks is not None:
            await self.tasks.aclose()
        if self.browser is not None:
            await self.browser.aclose()


def list_skills(root: Path) -> list[tuple[str, str]]:
    """His skills available to tasks (SKILL.md name + description) in <root>/.claude/skills, the folder the Agent SDK
    loads them from (tasks run with cwd=<root>). The repo's own build skills are not Jarvis's."""
    out: dict[str, str] = {}
    for base in (Path(root) / ".claude" / "skills",):
        if not base.exists():
            continue
        for md in sorted(base.glob("*/SKILL.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            name, desc = md.parent.name, ""
            if text.startswith("---"):
                import yaml  # noqa: PLC0415

                with contextlib.suppress(Exception):
                    fm = yaml.safe_load(text.split("---", 2)[1]) or {}
                    name, desc = fm.get("name", name), " ".join(str(fm.get("description", "")).split())[:200]
            out[name] = desc
    return sorted(out.items())
