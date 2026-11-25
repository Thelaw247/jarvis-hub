"""Live mode (H5): the hub shows what jarvis-core knows, and nothing made up.

The hub on Laptop A is told where the core is (`JARVIS_CORE_URL`, e.g. https://laptop-b.<tailnet>.ts.net) and which
paired device it is (`JARVIS_CORE_SESSION`, the token `python -m jarvis.core --pair laptop-a` printed). It then passes
the screen's three doors straight through to the core with the X-Jarvis-Session header:

  GET  /api/state    the core's state (contracts/state.schema.json, mode "live")
  GET  /api/events   the core's event stream (SSE), relayed as it comes
  POST /api/act      a UI action, answered by the core

When the core isn't configured or isn't answering, the hub shows an honest empty screen: the orb "offline", one
line saying so, nothing invented. The event stream closes after a short wait so the screen reconnects (and reloads)
by itself once the core is back. The demo day lives only behind `--demo` (jarvis_hub/demo/).

Latency: one extra local hop on the tailnet (~1-5 ms); events are relayed line by line, never buffered.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import settings as hub_settings
from .keys_proxy import (
    ALSO_HEADER,
    OTHER_HEADER,
    SESSION_HEADER,
    core_target,
    other_target,
    send_also,
    where_headers,
)

TIMEOUT_S = 5.0
RETRY_S = 10.0  # an offline stream closes after this, so the screen reconnects and reloads by itself
NOT_SET_UP = "Jarvis core isn't set up on this laptop yet."
NOT_ANSWERING = "Jarvis core isn't answering. It'll reconnect by itself."


def hub_mode() -> str:
    """"demo" only when asked for (`--demo` or JARVIS_HUB_MODE=demo); everything else is live. T0."""
    return "demo" if os.environ.get("JARVIS_HUB_MODE", "").strip().lower() == "demo" else "live"


def offline_state(message: str) -> dict:
    """A valid live state with nothing in it, the orb offline and one honest line."""
    from jarvis.core.state import empty_state  # noqa: PLC0415 - the core's own empty state, so both agree

    state = empty_state()
    state["orb"] = {"state": "offline"}
    state["now_card"]["greeting"] = message
    state["presence"] = {"here": True}
    return state

EXAMPLE_HEADER = "X-Jarvis-Settings"  # "example": no core behind this answer


def build_router(target: tuple[str, str] | None = None, transport=None, other: tuple[str, str] | None = None,
                 other_transport=None) -> APIRouter:
    """The live doors. `target`: (core url, session) or None (not set up). `transport`: an httpx transport (tests)."""
    router = APIRouter()
    target = target if target is not None else core_target()
    other = other if other is not None else other_target(target)  # the other laptop's Jarvis, when this one runs alone

    def headers(extra: dict | None = None) -> dict:
        return {SESSION_HEADER: target[1], "Accept": "application/json", **(extra or {})} if target else {}

    async def client():
        import httpx  # noqa: PLC0415

        return httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport)

    @router.get("/api/health")
    async def health() -> dict:
        if not target:
            return {"ok": True, "version": hub_settings.version(), "mode": "live", "core": "not set up", "clients": 0}
        try:
            async with await client() as c:
                answer = await c.get(f"{target[0]}/api/health", headers=headers())
            core = "connected" if answer.status_code == 200 else f"answered {answer.status_code}"
        except Exception:
            core = "not answering"
        # version: the code on this laptop (read from disk each time), so an open page notices a new one
        return {"ok": True, "version": hub_settings.version(), "mode": "live", "core": core, "clients": 0}

    @router.get("/api/made/{made_id}")
    async def made_page(made_id: str, theme: str = "night"):
        """A page Jarvis wrote, fetched from the core for a hub window. The sandbox policy is set here again, whatever
        the core sent: a made page never runs with the hub's own origin."""
        from fastapi.responses import HTMLResponse  # noqa: PLC0415

        from jarvis.reach.made import HEADERS, ID  # noqa: PLC0415

        if not target or not ID.match(made_id):
            return HTMLResponse("<p>That window is gone.</p>", status_code=404, headers=HEADERS)
        try:
            async with await client() as c:
                answer = await c.get(f"{target[0]}/api/made/{made_id}", params={"theme": theme}, headers=headers({"Accept": "text/html"}))
        except Exception:
            return HTMLResponse("<p>Jarvis core isn't answering.</p>", status_code=502, headers=HEADERS)
        if answer.status_code != 200:
            return HTMLResponse("<p>That window is gone.</p>", status_code=404, headers=HEADERS)
        return HTMLResponse(answer.text, headers=HEADERS)

    @router.get("/api/state")
    async def state() -> JSONResponse:
        if not target:
            return JSONResponse(offline_state(NOT_SET_UP), headers={"Cache-Control": "no-store"})
        try:
            async with await client() as c:
                answer = await c.get(f"{target[0]}/api/state", headers=headers())
            if answer.status_code == 200:
                return JSONResponse(answer.json(), headers={"Cache-Control": "no-store"})
        except Exception:
            pass
        return JSONResponse(offline_state(NOT_ANSWERING), headers={"Cache-Control": "no-store"})

    @router.get("/api/events")
    async def events(request: Request) -> StreamingResponse:
        async def offline():
            yield ": connected\n\n"
            await asyncio.sleep(RETRY_S)  # then close: the screen reconnects and reloads the state

        async def relay():
            import httpx  # noqa: PLC0415

            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_S, read=None), transport=transport) as c:
                    async with c.stream("GET", f"{target[0]}/api/events", headers=headers({"Accept": "text/event-stream"})) as answer:
                        if answer.status_code != 200:
                            async for line in offline():
                                yield line
                            return
                        async for chunk in answer.aiter_text():
                            yield chunk
                            if await request.is_disconnected():
                                return
            except Exception:
                async for line in offline():
                    yield line

        return StreamingResponse(relay() if target else offline(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @router.post("/api/act")
    async def act(request: Request) -> JSONResponse:
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
            raise HTTPException(403, "Actions are only accepted from the hub itself.")
        if not target:
            return JSONResponse({"ok": False, "message": NOT_SET_UP}, status_code=503)
        try:
            async with await client() as c:
                answer = await c.post(f"{target[0]}/api/act", content=await request.body(),
                                      headers=headers({"Content-Type": "application/json"}))
            return JSONResponse(answer.json(), status_code=answer.status_code)
        except Exception:
            return JSONResponse({"ok": False, "message": NOT_ANSWERING}, status_code=502)

    @router.get("/api/settings")
    async def get_settings() -> JSONResponse:
        if not target:  # answered, not failed: the voice field just says the core isn't set up
            return JSONResponse({"voice_id": "", "message": NOT_SET_UP},
                                headers={"Cache-Control": "no-store", EXAMPLE_HEADER: "example"})
        try:
            async with await client() as c:
                answer = await c.get(f"{target[0]}/api/settings", headers=headers())
            return JSONResponse(answer.json(), status_code=answer.status_code,
                                headers={"Cache-Control": "no-store", **where_headers(target[0], other)})
        except Exception:
            return JSONResponse({"error": "unreachable", "message": NOT_ANSWERING}, status_code=502)

    @router.put("/api/settings/voice")
    async def put_voice(request: Request) -> JSONResponse:
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
            raise HTTPException(403, "Settings are only accepted from the hub itself.")
        if not target:
            return JSONResponse({"error": "not_set_up", "message": NOT_SET_UP}, status_code=503)
        body, out = await request.body(), {"Cache-Control": "no-store", **where_headers(target[0], other)}
        try:
            async with await client() as c:
                answer = await c.put(f"{target[0]}/api/settings/voice", content=body,
                                     headers=headers({"Content-Type": "application/json"}))
            if other and answer.status_code < 400 and request.headers.get(ALSO_HEADER) == "1":  # the same voice on both
                out[OTHER_HEADER] = await send_also(other, "PUT", "/api/settings/voice", body, "application/json", other_transport)
            return JSONResponse(answer.json(), status_code=answer.status_code, headers=out)
        except Exception:
            return JSONResponse({"error": "unreachable", "message": NOT_ANSWERING}, status_code=502)

    @router.post("/api/demo/{cmd}")
    async def demo(cmd: str) -> None:
        raise HTTPException(404, "There's no demo in live mode. Start the hub with --demo for the demo day.")

    return router
