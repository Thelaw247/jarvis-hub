"""The hub server: serves the UI, the state, the live event stream and UI actions.

  GET  /api/state          the whole state (contracts/state.schema.json)
  GET  /api/events         server-sent events, one envelope per message (contracts/event.schema.json)
  POST /api/act            a UI action (contracts/act.schema.json)
  POST /api/demo/{cmd}     demo only: play | restart | stop
  GET  /api/health         version and mode
  GET  /api/thumb/{key}    a thing's small picture (contracts: thumb.src); 404 until jarvis_hub/thumbs.py exists (N5a)
  GET  /api/file/{id}      a file for the hub's reader, with HTTP Range; 404 until jarvis_hub/threads.py exists (N6)
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import keys_proxy, live, settings, voicehost
from .demo import keys as demo_keys
from .demo.fixtures import load_state
from .demo.scenario import DemoPlayer
from .events import Hub

KEEPALIVE_S = 15
SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")  # contract ids: no slashes, so a key can never walk the disk
ACTIONS = None  # filled from the contract on first use


def _allowed_actions() -> set[str]:
    global ACTIONS
    if ACTIONS is None:
        schema = json.loads(settings.resource_path("contracts", "act.schema.json").read_text(encoding="utf-8"))
        ACTIONS = set(schema["properties"]["action"]["enum"])
    return ACTIONS


def _same_origin(request: Request) -> None:
    """Actions may only come from the hub's own pages, not from another site open in a browser."""
    origin = request.headers.get("origin")
    if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
        raise HTTPException(403, "Actions are only accepted from the hub itself.")


def _lookup(module: str, function: str, key: str) -> Path | None:
    """Ask the package that owns thumbnails or files where one is. Until that package is merged there is none.
    The owner only adds `jarvis_hub/<module>.py` with `<function>(key) -> Path | None`; this file doesn't change."""
    if not SAFE_KEY.match(key) or ".." in key:
        return None
    try:
        find = getattr(importlib.import_module(f"jarvis_hub.{module}"), function, None)
    except ImportError:
        return None
    path = find(key) if find else None
    return Path(path) if path and Path(path).is_file() else None


class NoCacheStatic(StaticFiles):
    """The UI is tiny and local: always revalidate, so an update shows at once."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def _local_files(app: FastAPI) -> None:
    """Pictures and files the hub keeps on this laptop (both modes)."""
    @app.get("/api/thumb/{key}")
    async def thumb(key: str) -> FileResponse:
        path = _lookup("thumbs", "thumb_path", key)  # N5a: jarvis_hub/thumbs.py thumb_path("<key>.webp")
        if path is None:
            raise HTTPException(404, "No picture for that yet.")
        return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/api/file/{file_id}")
    async def file(file_id: str) -> FileResponse:
        path = _lookup("threads", "file_path", file_id)  # N6: jarvis_hub/threads.py file_path("<file id>")
        if path is None:
            raise HTTPException(404, "That file isn't here.", headers={"Accept-Ranges": "bytes"})
        return FileResponse(path, headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"})  # FileResponse answers Range requests (206)



def create_app(autoplay: bool | None = None, speed: float | None = None, hosts: list[str] | None = None,
               demo: bool | None = None) -> FastAPI:
    app = FastAPI(title="Jarvis Hub", version=settings.version(), docs_url=None, redoc_url=None, openapi_url=None)
    # only answer to our own names: 127.0.0.1, localhost and the tailnet name (JARVIS_HUB_HOSTS)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts or settings.allowed_hosts(), www_redirect=False)
    demo = live.hub_mode() == "demo" if demo is None else demo
    if not demo:
        # H5 live mode: the screen shows jarvis-core's state and nothing made up (jarvis_hub/live.py)
        core = keys_proxy.core_target()
        app.include_router(live.build_router(core))
        app.include_router(keys_proxy.build_router(*core) if core else demo_keys.router)
        app.include_router(voicehost.router(app.state))   # this laptop's voice, run by the hub (v0.15.0)
        _local_files(app)
        app.mount("/contracts", NoCacheStatic(directory=settings.resource_path("contracts")), name="contracts")
        app.mount("/", NoCacheStatic(directory=settings.resource_path("ui"), html=True), name="ui")
        return app
    app.include_router(voicehost.router(app.state, demo=True))
    hub = Hub(load_state(), mode="demo")
    player = DemoPlayer(hub, speed=float(os.environ.get("JARVIS_DEMO_SPEED", "1")) if speed is None else speed)
    autoplay = os.environ.get("JARVIS_DEMO_AUTOPLAY", "1") != "0" if autoplay is None else autoplay
    app.state.hub, app.state.player = hub, player
    if autoplay:
        player.prepare()  # the first window opens on the start of the day, not on its end state

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": settings.version(), "mode": hub.mode, "clients": hub.clients}

    @app.get("/api/state")
    async def state() -> JSONResponse:
        body = {**hub.snapshot(), "demo": {"running": player.running, "played": player.played, "step": player.step, "total": player.total}}
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @app.get("/api/events")
    async def events(request: Request, limit: int = 0) -> StreamingResponse:
        queue = hub.subscribe()
        if autoplay and not player.played and not player.running:
            player.start()  # the tour starts when the first window connects

        async def stream():
            sent = 0
            try:
                yield ": connected\n\n"
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    sent += 1
                    if limit and sent >= limit:
                        return
                    if await request.is_disconnected():
                        return
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    _local_files(app)

    @app.post("/api/act")
    async def act(request: Request) -> dict:
        _same_origin(request)
        try:
            body = await request.json()
            action, target, args = body["action"], str(body["target"]), body.get("args") or {}
        except Exception as err:
            raise HTTPException(400, "An action needs { action, target }.") from err
        if action not in _allowed_actions() or not isinstance(args, dict):
            raise HTTPException(400, f"Unknown action: {action}")
        if action == "demo":
            return await _demo(target)
        return hub.act(action, target, args)

    @app.post("/api/demo/{cmd}")
    async def demo(cmd: str, request: Request) -> dict:
        _same_origin(request)
        return await _demo(cmd)

    async def _demo(cmd: str) -> dict:
        if cmd in ("play", "restart"):
            player.start()
            await asyncio.sleep(0)
            hub.publish("nav.go", {"path": "/now", "reload": True})
        elif cmd == "stop":
            player.stop()
        else:
            raise HTTPException(404, "Use play, restart or stop.")
        return {"ok": True, "running": player.running}

    # K2: /api/keys. Live (JARVIS_CORE_URL + JARVIS_CORE_SESSION): straight through to jarvis-core with
    # X-Jarvis-Session. Otherwise the demo backend: example rows, never connected, writes refused unread.
    core = keys_proxy.core_target()
    app.include_router(keys_proxy.build_router(*core) if core else demo_keys.router)

    @app.get("/api/settings")
    async def demo_settings() -> JSONResponse:  # the demo has no core: the voice field says so and accepts nothing
        return JSONResponse({"voice_id": ""}, headers={"Cache-Control": "no-store", live.EXAMPLE_HEADER: "example"})

    app.mount("/contracts", NoCacheStatic(directory=settings.resource_path("contracts")), name="contracts")
    app.mount("/", NoCacheStatic(directory=settings.resource_path("ui"), html=True), name="ui")
    return app


app = create_app
