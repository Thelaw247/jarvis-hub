"""The tools folder, loaded once: every ``jarvis/tools/<id>/TOOL.md`` becomes a ToolSpec (and its handler).

One registry feeds everything from the same files (JARVIS_DESIGN_TOOLS.md §3):
- the voice brain's tool list: loaded tools in full, the rest ``defer_loading`` behind tool search, plus Anthropic's
  server tools (web search, web fetch);
- the task brain's in-process MCP server (``mcp__jarvis__<id>``, jarvis.tasks.runner);
- the Controls › Reach rows (contracts/reach.schema.json) and the abilities card in memory (jarvis.tools.abilities).

Tiers are enforced here, not in prompts: a ``never`` tool is never offered; an ``ask`` tool's handler can only file a
proposal (its code has no write path). Every call is timed and its failure returned to Claude as words.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import logging
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from jarvis import review

from .base import SPEEDS, TIERS, VOICE, WHERE, Result, ToolContext, ToolError, ToolSpec

log = logging.getLogger("jarvis.tools")
TOOLS_DIR = Path(__file__).resolve().parent
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
TIMEOUT_S = {"instant": 3.0, "fast": 20.0, "slow": 90.0, "task": 15.0}  # a task tool only *starts* the task
TOOL_SEARCH = {"type": "tool_search_tool_bm25_20251119", "name": "tool_search_tool_bm25"}
MAX_RESULT_CHARS = 40_000  # what one tool result may put in the prompt (a long document returns an outline instead)


class SpecError(ValueError):
    pass


def _split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise SpecError("TOOL.md must start with --- front matter")
    _, fm, body = text.split("---", 2)
    data = yaml.safe_load(fm) or {}
    if not isinstance(data, dict):
        raise SpecError("front matter must be a mapping")
    return data, body.strip()


def parse_tool_md(folder: Path) -> ToolSpec:
    try:
        data, body = _split_front_matter((folder / "TOOL.md").read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SpecError(f"{folder.name}: TOOL.md front matter isn't valid YAML ({e})") from e
    tid = data.get("id") or folder.name
    if tid != folder.name or not NAME_RE.match(tid):
        raise SpecError(f"{folder.name}: id must match the folder and be snake_case")
    for key, allowed in (("tier", TIERS), ("speed", SPEEDS), ("voice", VOICE), ("where", WHERE)):
        if key in data and data[key] not in allowed:
            raise SpecError(f"{tid}: {key} must be one of {allowed}")
    server = data.get("server")
    schema = data.get("input") or {"type": "object", "properties": {}}
    if server is None:
        if schema.get("type") != "object":
            raise SpecError(f"{tid}: input must be a JSON Schema object")
        lowered = body.lower()
        if "when to use" not in lowered or "when not to use" not in lowered:
            raise SpecError(f"{tid}: the description must say 'When to use' and 'When not to use'")
    return ToolSpec(
        id=tid, name=str(data.get("name", tid)), description=body, input_schema=schema,
        rung=int(data.get("rung", 1)), tier=data.get("tier", "read"), speed=data.get("speed", "fast"),
        voice=data.get("voice", "deferred"), task=bool(data.get("task", True)), where=data.get("where", "Laptop B"),
        reads=str(data.get("reads", "")), writes=str(data.get("writes", "nothing")), server=server,
        needs=tuple(data.get("needs") or ()), folder=folder)


def _load_handler(spec: ToolSpec) -> Any:
    path = spec.folder / "handler.py" if spec.folder else None
    if spec.server is not None:
        return None
    if path is None or not path.exists():
        raise SpecError(f"{spec.id}: handler.py is missing")
    mod_name = f"jarvis.tools._h_{spec.id}"
    loader = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(loader)
    assert loader.loader is not None
    loader.loader.exec_module(module)
    run = getattr(module, "run", None)
    if not asyncio.iscoroutinefunction(run):
        raise SpecError(f"{spec.id}: handler.py needs `async def run(args, ctx)`")
    return run


class Registry:
    def __init__(self, folders: Iterable[Path] | None = None) -> None:
        folders = folders if folders is not None else sorted(
            p for p in TOOLS_DIR.iterdir() if p.is_dir() and (p / "TOOL.md").exists())
        self.specs: dict[str, ToolSpec] = {}
        self.handlers: dict[str, Any] = {}
        self.last_used: dict[str, str] = {}
        self.use: dict[str, dict] = {}  # per tool: runs, fails, last_used, last_error (kept on disk, see `remember`)
        self.store: Path | None = None
        self.off: set[str] = set()      # switched off in Controls › Reach
        for folder in folders:
            spec = parse_tool_md(folder)
            if spec.tier == "never":
                continue  # never offered to a model, whatever it asks
            self.specs[spec.id] = spec
            self.handlers[spec.id] = _load_handler(spec)

    # ------------------------------------------------------------------ what ran (v0.19.1)
    def remember(self, store: Path) -> None:
        """Keep each tool's history in a small file. Before this, "last used" lived in memory only, so after every
        restart the hub said no tool had ever run (his report of 2026-11-22), and a refusal left no trace at all."""
        self.store = Path(store)
        try:
            data = json.loads(self.store.read_text(encoding="utf-8"))
            self.use = {k: v for k, v in data.items() if isinstance(v, dict)}
            self.last_used.update({k: v["last_used"] for k, v in self.use.items() if v.get("last_used")})
        except (OSError, ValueError):
            self.use = {}

    def _note(self, tid: str, problem: str | None, *, ran: bool = True) -> None:
        """One call's outcome: ids, counts, a time and a short reason. Never his words or a result (C21)."""
        rec = self.use.setdefault(tid, {"runs": 0, "fails": 0})
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        if ran:
            rec["runs"] = int(rec.get("runs", 0)) + 1
            rec["last_used"] = self.last_used[tid] = now
        if problem:
            rec["fails"] = int(rec.get("fails", 0)) + 1
            rec["last_error"] = f"{now} {problem}"[:160]
        elif ran:
            rec.pop("last_error", None)
        if self.store is not None:
            with contextlib.suppress(OSError):
                self.store.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.store.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.use, indent=1), encoding="utf-8")
                tmp.replace(self.store)

    # ------------------------------------------------------------------ what is usable
    def get(self, tid: str) -> ToolSpec | None:
        return self.specs.get(tid)

    def status(self, spec: ToolSpec, ctx: ToolContext) -> str:
        """contracts/reach: connected · needs_sign_in · paused · off."""
        if spec.id in self.off:
            return "off"
        missing = [n for n in spec.needs if not ctx.has(n)]
        if missing:
            return "off"
        for need in spec.needs:  # a service that is present but signed out (the browser, Canvas)
            svc = getattr(ctx, need, None)
            if getattr(svc, "needs_sign_in", False):
                return "needs_sign_in"
        return "connected"

    def usable(self, ctx: ToolContext, *, origin: str = "voice") -> list[ToolSpec]:
        out = []
        for spec in self.specs.values():
            if self.status(spec, ctx) == "off":
                continue
            if origin == "voice" and spec.voice == "off":
                continue
            if origin == "task" and not spec.task:
                continue
            out.append(spec)
        return out

    # ------------------------------------------------------------------ the voice brain's tool list
    # v0.14.0: every tool is loaded in a spoken turn. With deferral a "deferred" tool cost a tool-search round trip
    # before each use (the sign-in on 2026-11-18 took 6.5 s to its first word), and the whole list is cached anyway
    # (~4k tokens read from cache). Deferral comes back when there are more tools than this.
    DEFER_ABOVE = 30

    @property
    def defer(self) -> bool:
        return len(self.specs) > self.DEFER_ABOVE

    def voice_tools(self, ctx: ToolContext) -> list[dict]:
        """Server tools as Anthropic defines them; our tools loaded (deferred only past DEFER_ABOVE tools, with tool
        search first then). The last loaded tool carries cache_control so the list is cached."""
        server, loaded, deferred = [], [], []
        for spec in self.usable(ctx, origin="voice"):
            if spec.server is not None:
                server.append(dict(spec.server))
                continue
            param = {"name": spec.id, "description": spec.description, "input_schema": spec.input_schema}
            if spec.voice == "loaded" or not self.defer:
                loaded.append(param)
            else:
                deferred.append({**param, "defer_loading": True})
        tools: list[dict] = []
        if deferred:
            tools.append(dict(TOOL_SEARCH))
        tools += server + loaded
        if tools:
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
        return tools + deferred

    def index_text(self, ctx: ToolContext | None = None) -> str:
        """One line per ability, for the cached persona prefix (~600 tokens): the voice brain always knows the
        whole set exists, and searches for a deferred tool's details only when it needs them."""
        specs = self.usable(ctx) if ctx is not None else list(self.specs.values())
        lines = ["What you can do (tools; search for any you don't see loaded):" if self.defer
                 else "What you can do (your tools):"]
        for s in specs:
            lines.append(f"- {s.id}: {s.summary}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ running a call
    async def run(self, tid: str, args: dict | None, ctx: ToolContext) -> Result:
        """Run one call. Never raises: a refusal or failure comes back as an is_error Result in plain words."""
        spec = self.specs.get(tid)
        if spec is None or spec.server is not None:
            return Result(f"There is no tool called {tid!r}.", is_error=True)
        status = self.status(spec, ctx)
        if status == "off":
            missing = [n for n in spec.needs if not ctx.has(n)]
            self._note(tid, "switched off" if spec.id in self.off else f"not set up here (missing: {', '.join(missing) or '?'})", ran=False)
            return Result(f"{spec.name} is switched off or not set up on this laptop.", is_error=True)
        if status == "needs_sign_in":
            # Laptop B, 2026-11-22: "he still maintains Canvas isn't signed in when it really is". The sign-in flag was
            # only ever cleared by a successful call, and a raised flag stopped every call before it ran: once Canvas
            # had asked for a sign-in, Jarvis could never find out that he had signed in. Now the flag is lowered and
            # the tool runs: it finds out for itself, and raises the flag again only if Canvas really still asks.
            for need in spec.needs:
                svc = getattr(ctx, need, None)
                if getattr(svc, "needs_sign_in", False):
                    with contextlib.suppress(Exception):
                        svc.needs_sign_in = False
        t0 = time.perf_counter()
        try:
            out = await asyncio.wait_for(self.handlers[tid](dict(args or {}), ctx), TIMEOUT_S[spec.speed])
        except ToolError as e:
            out = Result(str(e), is_error=True)
        except TimeoutError:
            out = Result(f"{spec.name} took too long and was stopped. Say so briefly, or start a task for it.",
                         is_error=True)
        except Exception as e:  # a bug: Claude hears that it failed, the log has the type
            log.warning("tool.failed", extra={"tool": tid, "error": type(e).__name__}, exc_info=True)
            out = Result(f"{spec.name} failed ({type(e).__name__}). Don't retry the same call.", is_error=True)
        result = out if isinstance(out, Result) else Result(str(out))
        if isinstance(result.content, str) and len(result.content) > MAX_RESULT_CHARS:
            result.content = result.content[:MAX_RESULT_CHARS] + "\n[…cut: ask for specific pages or a narrower search]"
        # the reason in the tool's own first words: a refusal he can act on, never content (C21)
        self._note(tid, (str(result.content).split(".")[0][:100] if isinstance(result.content, str) else "failed") if result.is_error else None)
        if review.on():
            review.note("tool", tool=tid, tier=spec.tier, input=dict(args or {}), is_error=result.is_error,
                        ms=round((time.perf_counter() - t0) * 1000, 1), result=result.content,
                        show=result.show[0] if result.show else None, shown=result.show[1] if result.show else None,
                        note=getattr(result, "note", None))
        log.info("tool.ran", extra={"tool": tid, "ms": round((time.perf_counter() - t0) * 1000, 1),
                                    "error": result.is_error})
        if result.show is not None:
            await ctx.show(*result.show)
        return result

    # ------------------------------------------------------------------ the hub's Controls › Reach
    def reach_rows(self, ctx: ToolContext) -> list[dict]:
        rows = []
        for s in self.specs.values():
            rows.append({"id": s.id.replace("_", "-"), "name": s.name, "rung": max(1, min(6, s.rung)),
                         "reads": s.reads or "—", "writes": s.writes or "nothing",
                         "status": self.status(s, ctx), "on": s.id not in self.off, "where": s.where,
                         "last_used": self.last_used.get(s.id)})
        return rows


_default: Registry | None = None


def default_registry() -> Registry:
    global _default
    if _default is None:
        _default = Registry()
    return _default
