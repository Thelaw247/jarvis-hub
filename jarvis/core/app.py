"""The jarvis-core FastAPI app: health, the hub's state/event/action API, and the parts behind them.

  GET  /healthz            component statuses; 200 green or amber, 503 red (Servy's start check, ops/README.md)
  GET  /api/health         the hub's health shape: { ok, version, mode: "live", clients }
  GET  /api/state          the whole state (contracts/state.schema.json, mode "live")
  GET  /api/events         server-sent events, one envelope per message (contracts/event.schema.json)
  POST /api/act            a UI action (contracts/act.schema.json): `set` changes one of his settings (hub_settings.py);
                           every other action still answers safely, changing nothing
  POST /api/demo/{cmd}     404: there is no demo on the core
  GET  /api/thumb/{key}    404 until pictures are served from the core
  GET  /api/file/{id}      404 until files are served from the core

These are the routes `jarvis_hub/server.py` serves in demo mode, with the same shapes, so the hub's H5 live mode
only has to point at this address.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from jarvis import review

from . import hub_settings, hub_windows, review_wiring
from . import keys as keys_wiring
from .actions import Actions
from .bus import EventBus
from .config import Config
from .health import Health
from .logs import EventLog, setup_logging
from .queue import JobQueue
from .sessions import HubSessions
from .settings import CoreSettings
from .state import CoreState

SESSION_HEADER = "X-Jarvis-Session"

KEEPALIVE_S = 15
log = EventLog("jarvis.core.app")


@dataclass
class Core:
    """Everything the app holds, in one place (`app.state.core`)."""
    config: Config
    bus: EventBus
    state: CoreState
    queue: JobQueue
    health: Health
    actions: Actions
    keys: keys_wiring.Keys | None = None
    sse_clients: int = 0


class RequestLog:
    """One log line per request: method, route template, status and time. No query strings, bodies or addresses."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0, status, rid = time.perf_counter(), 500, uuid.uuid4().hex[:12]

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            log.info("http.request", request_id=rid, method=scope["method"], route=route, status=status,
                     ms=(time.perf_counter() - t0) * 1000)


def _same_origin(request: Request, config: Config) -> None:
    """Actions only from the core's own address or a listed hub page, never from another site in a browser."""
    origin = request.headers.get("origin")
    if origin and origin.split("://", 1)[-1] != request.headers.get("host") and origin.lower() not in config.extra_origins:
        raise HTTPException(403, "Actions are only accepted from the hub itself.")


def build_core(config: Config) -> Core:
    state = CoreState()
    bus = EventBus(reducer=state.apply)
    queue = JobQueue(config.queue_db, bus=bus, concurrency=config.max_jobs)
    core = Core(config, bus, state, queue, Health(config.version), Actions())

    core.health.register("config", lambda: ("ok", {}) if config.layout_ok() else ("down", {"code": "layout"}))
    core.health.register("bus", lambda: ("ok", {"count": bus.subscribers, "dropped_n": bus.dropped}))

    async def queue_check() -> tuple[str, dict]:
        if not queue.alive:
            return "starting", {}
        counts = await queue.counts()
        return "ok", {"running_n": counts["running"], "queued_n": counts["queued"], "failed_n": counts["failed"]}

    core.health.register("queue", queue_check)
    core.health.register("api", lambda: ("ok", {"clients_n": core.sse_clients}))
    return core


async def _start_memory(config: Config):
    """The memory store (MEMORY §3) in <root>/memory/jarvis.db, never in git. None if it can't start (logged)."""
    try:
        from jarvis.memory.store import MemoryStore  # noqa: PLC0415

        config.memory_dir.mkdir(parents=True, exist_ok=True)
        return await MemoryStore(config.memory_dir / "jarvis.db").start()
    except Exception as e:
        log.warning("memory.not_started", error=type(e).__name__)
        return None


def create_app(config: Config | None = None, *, log_to_stderr: bool = True, key_backend=None) -> FastAPI:
    config = config or Config.from_env()
    t_start = time.perf_counter()
    config.ensure_layout()
    setup_logging(config.log_file, stream=log_to_stderr)
    core = build_core(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from .stallwatch import StallWatch  # noqa: PLC0415

        stallwatch = StallWatch(asyncio.get_running_loop())
        stallwatch.start()
        await core.queue.open()
        await core.queue.start()
        await keys_wiring.start(core.keys)
        core.bus.publish("core.started", {"version": config.version})
        toolkit = getattr(app.state, "toolkit", None)
        memory = None
        if toolkit is not None:
            if config.memory:
                memory = await _start_memory(config)
                toolkit.memory = memory
            await toolkit.start()
        voice = getattr(app.state, "voice", None)
        if voice is not None and config.voice_preload:
            voice.preload()  # models load in the background; the first client waits only if it's very quick
        log.info("core.started", version=config.version, port=config.port, ms=(time.perf_counter() - t_start) * 1000,
                 count=core.queue.recovered)
        learner = None
        if memory is not None and toolkit is not None:   # v0.20.0: he is remembered, and asked only once
            from .learning import Learner  # noqa: PLC0415

            learner = toolkit.learner = Learner(memory, toolkit.keyed, core.bus, settings)
            if voice is not None:
                voice.learner = learner

            async def forget_fact(target: str, args: dict) -> dict:   # the Memory page's Forget on one fact
                number = target.rsplit("-", 1)[-1]
                if not number.isdigit():
                    return {"ok": False, "message": "That isn't something Jarvis remembered. Nothing was changed."}
                await memory.forget(fact_ids=[int(number)])
                core.bus.publish("fact.updated", {"id": target, "forgotten": True})
                return {"ok": True}

            core.actions.handle("forget", forget_fact)
        feed = None
        if config.hub_feed and toolkit is not None:   # v0.18.0: the hub is no longer empty
            from .hub_feed import HubFeed  # noqa: PLC0415

            feed = app.state.feed = HubFeed(core.bus, config.root, classes=toolkit.classes, calendar=toolkit.calendar, memory=memory,
                                               rail=lambda: core.state.state["rail"])
            toolkit.refresh_hub = feed.refresh_day   # a tool that changes class data (mark_done) redraws the hub at once
            with contextlib.suppress(Exception):
                await feed.start()
            if voice is not None:
                voice.now_lines = feed.now_text
            if learner is not None:
                learner.after_save = feed.refresh   # a new memory shows on the hub and in the now card at once
        load_watch = asyncio.create_task(review_wiring.watch_load(app))   # review recording: idle unless it's on
        try:
            yield
        finally:
            load_watch.cancel()
            if feed is not None:
                await feed.stop()
            if learner is not None:
                await learner.aclose()
            core.bus.publish("core.stopping", {})
            if getattr(app.state, "voice", None) is not None:
                await app.state.voice.aclose()
            if toolkit is not None:
                with contextlib.suppress(Exception):
                    await toolkit.aclose()
            if memory is not None:
                with contextlib.suppress(Exception):
                    await memory.close()
            await keys_wiring.stop(core.keys)
            await core.queue.close()
            stallwatch.stop()
            log.info("core.stopped")

    app = FastAPI(title="Jarvis core", version=config.version, docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts, www_redirect=False)
    app.add_middleware(RequestLog)
    app.state.core = core
    # H5: the screen's doors (state, events, actions) answer only his paired devices (`--pair <name>`); the phone,
    # paired --view-only, can look but not act. Tailscale already keeps strangers off the network; this keeps
    # any other device on it out too.
    sessions = HubSessions(config.data_dir / "hub_sessions.json")

    def paired(request: Request, write: bool = False) -> None:
        device = sessions.device(request.headers.get(SESSION_HEADER, ""))
        if device is None:
            raise HTTPException(401, "Pair this screen with Jarvis core first (python -m jarvis.core --pair <name>).")
        if write and not device.can_write:
            raise HTTPException(403, "This device can look but not act.")

    core.keys = keys_wiring.mount(app, config, core.bus, key_backend)  # /api/keys (K1), when jarvis.secrets is there
    if core.keys is not None:
        core.health.register("keys", core.keys.check)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        report = await core.health.report()
        return JSONResponse(report, status_code=200 if report["ok"] else 503, headers={"Cache-Control": "no-store"})

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": config.version, "mode": "live", "clients": core.sse_clients}

    @app.get("/api/made/{made_id}")
    async def made_page(made_id: str, request: Request):
        """A page Jarvis wrote (make_window). Served with a sandbox policy: it has no origin, so it cannot touch the
        hub, his session or these doors, and it can load nothing from outside (jarvis/reach/made.py)."""
        from fastapi.responses import HTMLResponse  # noqa: PLC0415

        from jarvis.reach import made  # noqa: PLC0415

        paired(request)
        entry = made.load(config.root, made_id)
        if entry is None:
            raise HTTPException(404, "That window is gone.")
        return HTMLResponse(made.document(entry, request.query_params.get("theme", "night")), headers=made.HEADERS)

    @app.get("/api/state")
    async def state(request: Request) -> JSONResponse:
        paired(request)
        return JSONResponse(core.state.snapshot(), headers={"Cache-Control": "no-store"})

    @app.get("/api/events")
    async def events(request: Request, limit: int = 0) -> StreamingResponse:
        paired(request)
        sub = core.bus.subscribe(hub_only=True, on_full="close")  # a screen that falls behind reconnects and reloads
        core.sse_clients += 1

        async def stream():
            sent = 0
            try:
                yield ": connected\n\n"
                while not sub.closed:
                    try:
                        event = await sub.get(timeout=KEEPALIVE_S)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    except StopAsyncIteration:
                        return
                    yield f"data: {json.dumps(event.envelope(), ensure_ascii=False)}\n\n"
                    sent += 1
                    if (limit and sent >= limit) or await request.is_disconnected():
                        return
            finally:
                sub.close()
                core.sse_clients -= 1

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.post("/api/act")
    async def act(request: Request) -> dict:
        _same_origin(request, config)
        paired(request, write=True)
        try:
            body = await request.json()
            action, target, args = body["action"], str(body["target"]), body.get("args") or {}
        except Exception as err:
            raise HTTPException(400, "An action needs { action, target }.") from err
        if action not in core.actions.names or not isinstance(args, dict):
            raise HTTPException(400, "Unknown action.")
        t0 = time.perf_counter()
        result = await core.actions.act(action, target, args)
        review.note("act", action=action, target=target, args=args, result=result,
                    ms=round((time.perf_counter() - t0) * 1000, 1), device=request.headers.get("x-jarvis-device"))
        return result

    settings = CoreSettings(config.data_dir / "settings.json")
    hub_settings.restore(core, settings)   # his Controls choices, as he left them
    hub_settings.wire(core, settings)      # and Controls can change them (v0.12.4)
    hub_windows.wire(core)                 # and the windows' own buttons work: close, pin, bigger, move (v0.15.3)
    review_wiring.wire(app, core, config)  # review recording (v0.16.0): everything, only while he has it on
    from jarvis.voice.service import (
        BRAINS,
        VoiceService,  # noqa: PLC0415 (light: the voice packages load only when used)
    )

    voice = VoiceService(config.root, core.bus, core.keys, settings)
    app.state.voice = voice
    hub_settings.reflect(core, settings, "muted", False)   # a restart always starts with the mic on
    hub_settings.follow(core, settings, "muted", voice.set_muted)        # the hub's Microphone switch
    voice.on_muted = lambda muted: hub_settings.reflect(core, settings, "muted", muted)   # "mute the microphone"
    brain = settings.hub().get("voice_brain")
    if brain in BRAINS:
        voice.brain = brain                                                 # his choice, as he left it
    hub_settings.reflect(core, settings, "voice_brain", voice.brain)        # the hub always shows the one in use
    hub_settings.follow(core, settings, "voice_brain", voice.set_brain)     # quick (Haiku 5.5) or deep (Sonnet 5.5)
    voice.cloud_hearing = settings.hub().get("cloud_hearing") is True       # off unless he turned it on
    hub_settings.reflect(core, settings, "cloud_hearing", voice.cloud_hearing)
    hub_settings.follow(core, settings, "cloud_hearing", voice.set_cloud_hearing)   # ElevenLabs hears, or this laptop
    core.health.register("voice", voice.check)
    app.state.toolkit = None
    if config.tools:  # Jarvis's tools (JARVIS_DESIGN_TOOLS.md): the voice brain gets them; tasks report back
        from .toolkit import Toolkit  # noqa: PLC0415

        app.state.toolkit = Toolkit(config.root, core.bus, core.keys, voice=voice)
        voice.tools = app.state.toolkit.voice_tools()

    @app.websocket("/ws/voice")
    async def voice_socket(ws: WebSocket) -> None:
        """The mic in, Jarvis's voice out (jarvis/voice/service.py). Paired devices that may act only."""
        device = sessions.device(ws.headers.get(SESSION_HEADER, "") or ws.query_params.get("session", ""))
        if device is None or not device.can_write:
            await ws.close(code=4401 if device is None else 4403)
            return
        await ws.accept()
        log.info("voice.client", device=device.name)
        # ?polite=1: a hub starting the voice by itself; it doesn't take it from a laptop that has it
        await voice.attach(ws, device.name, polite=ws.query_params.get("polite") == "1")

    @app.get("/api/voice")
    async def voice_status(request: Request) -> JSONResponse:
        paired(request)
        return JSONResponse({"status": voice.status, "missing": voice.missing(), "device": voice.client_name},
                            headers={"Cache-Control": "no-store"})

    @app.post("/api/restart")
    async def restart(request: Request) -> JSONResponse:
        """Stop the core so ops/run-core.pyw starts the new code (restart-core.bat). From this laptop only."""
        paired(request, write=True)
        if (request.client.host if request.client else "") not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(403, "Restart only from Laptop B itself.")
        log.info("core.restart_requested")
        asyncio.get_running_loop().call_later(0.3, os._exit, 0)
        return JSONResponse({"ok": True, "message": "Restarting. Back in a few seconds."})

    @app.post("/api/browser/sign-in")
    async def browser_sign_in(request: Request) -> JSONResponse:
        """Open a site's sign-in page in the visible Jarvis browser on Laptop B (Sign in to a site.bat, the hub).
        He signs in himself; Jarvis never sees the password (TOOLS §6)."""
        paired(request, write=True)
        toolkit = getattr(app.state, "toolkit", None)
        if toolkit is None or toolkit.browser is None:
            raise HTTPException(409, "The Jarvis browser isn't installed yet: run setup-tools.bat.")
        try:
            site = str((await request.json()).get("site", "canvas"))
        except Exception:
            site = "canvas"
        out = await toolkit.registry.run("sign_in", {"site": site}, toolkit.make_ctx("hub"))
        if out.is_error:
            raise HTTPException(400, str(out.content))
        return JSONResponse({"ok": True, "message": str(out.content)})

    @app.get("/api/reach")
    async def get_reach(request: Request) -> JSONResponse:
        """What Jarvis can do right now (contracts/reach.schema.json), for the hub and the tools check."""
        paired(request)
        toolkit = getattr(app.state, "toolkit", None)
        if toolkit is None:
            raise HTTPException(409, "Tools are switched off (JARVIS_TOOLS=0).")
        return JSONResponse(toolkit.reach(), headers={"Cache-Control": "no-store"})

    @app.get("/api/settings")
    async def get_settings(request: Request) -> JSONResponse:
        paired(request)
        return JSONResponse(settings.public(), headers={"Cache-Control": "no-store"})

    @app.put("/api/settings/voice")
    async def put_voice(request: Request) -> JSONResponse:
        _same_origin(request, config)
        paired(request, write=True)
        try:
            body = await request.json()
            value = body.get("voice_id", "")
            if not isinstance(value, str):
                raise ValueError
        except Exception as err:
            raise HTTPException(400, "Send { voice_id }.") from err
        try:
            settings.set_voice_id(value)
        except ValueError as err:
            raise HTTPException(400, str(err)) from err
        log.info("settings.voice_id", count=1 if value else 0)
        return JSONResponse(settings.public(), headers={"Cache-Control": "no-store"})

    @app.post("/api/demo/{cmd}")
    async def demo(cmd: str, request: Request) -> dict:
        _same_origin(request, config)
        raise HTTPException(404, "There's no demo on Jarvis core.")

    @app.get("/api/thumb/{key}")
    async def thumb(key: str) -> None:
        raise HTTPException(404, "No picture for that yet.")

    @app.get("/api/file/{file_id}")
    async def file(file_id: str) -> None:
        raise HTTPException(404, "That file isn't here.", headers={"Accept-Ranges": "bytes"})

    return app

