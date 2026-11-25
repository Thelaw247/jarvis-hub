"""Live-mode door for the hub's Keys page: /api/keys passes straight through to jarvis-core (K1, K2).

Used only when the hub is told where the core is (`JARVIS_CORE_URL`, e.g. https://laptop-b.<tailnet>.ts.net) and
which paired device it is (`JARVIS_CORE_SESSION`, the token `jarvis.core --pair` printed, sent as X-Jarvis-Session).
Without both the hub mounts the demo backend (jarvis_hub/demo/keys.py: example rows, writes refused unread).

A pasted key crosses this module as opaque bytes: the body is never parsed, logged, kept or echoed, and the core's
answer (which never holds a key) is returned as it came. If the core doesn't answer, the reply is the keys
contract's error shape, so the page says so and nothing is changed.

Two laptops (v0.24.0). A laptop that runs its own Jarvis still remembers the other laptop's (`JARVIS_REMOTE_CORE_URL`
and `JARVIS_REMOTE_CORE_SESSION`, saved by "Run Jarvis on this laptop.bat"). When the page sends `X-Jarvis-Also-Other: 1`
a new key's steps (next, promote, previous) are repeated on that Jarvis, so both laptops end up with the same key.
The answer says how that went in `X-Jarvis-Other` (saved | refused | unreachable). The key still is never parsed,
logged or kept here, and it only goes to the other laptop over https (the tailnet) or to this laptop itself.
Removing a service is never repeated: that is done on each laptop by itself.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

SESSION_HEADER = "X-Jarvis-Session"
ALSO_HEADER = "X-Jarvis-Also-Other"        # the page asks: make this change on the other laptop's Jarvis too
OTHER_HEADER = "X-Jarvis-Other"            # how that went: saved | refused | unreachable
KEPT_HEADER = "X-Jarvis-Kept"              # where the keys on the page are kept: "here" or the other laptop's name
OTHER_NAME_HEADER = "X-Jarvis-Other-Name"  # the second Jarvis this hub can also update (only when it runs its own)
MIRRORED = ("next", "promote", "previous")
TIMEOUT_S = 10.0
_UNREACHABLE = {"error": "unreachable", "message": "Jarvis core isn't answering. Nothing was changed."}


def core_target() -> tuple[str, str] | None:
    """(core url, session token) when live keys are configured, else None (demo). T0."""
    url, token = os.environ.get("JARVIS_CORE_URL", "").strip().rstrip("/"), os.environ.get("JARVIS_CORE_SESSION", "").strip()
    return (url, token) if url.startswith(("http://", "https://")) and token else None


def is_local(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in ("127.0.0.1", "localhost", "::1")


def laptop_name(url: str) -> str:
    """"here" for this laptop's own Jarvis, else the other laptop's short name (laptop-b.<tailnet>.ts.net → laptop-b)."""
    return "here" if is_local(url) else (urlsplit(url).hostname or "the other laptop").split(".")[0].lower()


def other_target(core: tuple[str, str] | None = None) -> tuple[str, str] | None:
    """(url, session) of the other laptop's Jarvis, only when this hub uses its own and knows another one. T0."""
    core = core if core is not None else core_target()
    url = os.environ.get("JARVIS_REMOTE_CORE_URL", "").strip().rstrip("/")
    token = os.environ.get("JARVIS_REMOTE_CORE_SESSION", "").strip()
    safe = url.startswith("https://") or (url.startswith("http://") and is_local(url))  # a key never crosses in the clear
    if not core or not is_local(core[0]) or not token or not safe or url.lower() == core[0].lower():
        return None
    return url, token


def where_headers(core_url: str, other: tuple[str, str] | None) -> dict:
    return {KEPT_HEADER: laptop_name(core_url), **({OTHER_NAME_HEADER: laptop_name(other[0])} if other else {})}


async def send_also(other: tuple[str, str], method: str, path: str, body: bytes, content_type: str | None, transport=None) -> str:
    """Repeat one change on the other laptop's Jarvis. → saved | refused | unreachable. Nothing is kept or logged."""
    import httpx  # noqa: PLC0415

    headers = {SESSION_HEADER: other[1], "Accept": "application/json", **({"Content-Type": content_type} if content_type else {})}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as client:
            answer = await client.request(method, f"{other[0]}{path}", content=body, headers=headers)
    except httpx.HTTPError:
        return "unreachable"
    return "saved" if answer.status_code < 400 and not failed_check(answer) else "refused"


def failed_check(answer) -> bool:
    """A key that was stored but didn't pass its check (the row never holds the key itself)."""
    try:
        return ((answer.json() or {}).get("next") or {}).get("check") == "failed"
    except Exception:  # noqa: BLE001 - not a row: nothing to read
        return False


def build_router(core_url: str, session: str, transport=None, other: tuple[str, str] | None = None,
                 other_transport=None) -> APIRouter:
    """Routes that forward /api/keys to the core with the session header. `transport`: an httpx transport (tests).
    `other`: the other laptop's Jarvis (default: from the environment, see other_target)."""
    import httpx  # noqa: PLC0415 - only needed in live mode (the `core` extra)

    router = APIRouter()
    other = other if other is not None else other_target((core_url, session))

    async def forward(request: Request, path: str) -> Response:
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
            raise HTTPException(403, "Keys are only accepted from the hub itself.")
        headers = {SESSION_HEADER: session, "Accept": "application/json"}
        if request.headers.get("content-type"):
            headers["Content-Type"] = request.headers["content-type"]
        body, out = await request.body(), {"Cache-Control": "no-store", **where_headers(core_url, other)}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as client:
                answer = await client.request(request.method, f"{core_url}/api/keys{path}", params=dict(request.query_params),
                                              content=body, headers=headers)
        except httpx.HTTPError:
            return JSONResponse(_UNREACHABLE, status_code=502, headers=out)
        step = path.rsplit("/", 1)[-1]
        if (other and request.method != "GET" and step in MIRRORED and request.headers.get(ALSO_HEADER) == "1"
                and answer.status_code < 400 and not failed_check(answer)):
            out[OTHER_HEADER] = await send_also(other, request.method, f"/api/keys{path}", body,
                                                request.headers.get("content-type"), other_transport)
        return Response(answer.content, status_code=answer.status_code, media_type="application/json", headers=out)

    @router.get("/api/keys")
    async def get_keys(request: Request) -> Response:
        return await forward(request, "")

    @router.post("/api/keys/{key_id}/{action}")
    @router.delete("/api/keys/{key_id}/{action}")
    async def change(request: Request, key_id: str, action: str) -> Response:
        return await forward(request, f"/{key_id}/{action}")

    @router.delete("/api/keys/{key_id}")
    async def remove(request: Request, key_id: str) -> Response:
        return await forward(request, f"/{key_id}")

    return router
