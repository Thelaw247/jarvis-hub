"""The /api/keys routes (contracts/keys.schema.json), as an APIRouter for the core app (K0) to mount.

Bodies are parsed by hand, never by a pydantic model: FastAPI's 422 answers echo the input, which here
would be the key. Every answer is built from rows (at most a key's last 4 characters).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .guard import SESSION_HEADER, Session, Verifier, verify
from .manager import KeyManager, KeysError

MAX_BODY_BYTES = 64 * 1024
NO_STORE = {"Cache-Control": "no-store"}


def _answer(body: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=NO_STORE)


def _refuse(code: str, message: str, status: int) -> JSONResponse:
    return _answer({"error": code, "message": message}, status)


async def _session(request: Request, verifier: Verifier) -> Session | None:
    host = request.client.host if request.client else None
    return await verify(verifier, host, request.headers.get(SESSION_HEADER))


async def _body(request: Request) -> dict | None:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return None
    try:
        doc = json.loads(raw or b"{}")
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def build_router(manager: KeyManager, verifier: Verifier, prefix: str = "/api/keys") -> APIRouter:
    router = APIRouter(prefix=prefix)

    async def guarded(request: Request, write: bool, fn):
        session = await _session(request, verifier)
        if session is None:
            return _refuse("not_allowed", "Keys can only be changed from your own devices.", 403)
        if write and not session.can_write:
            return _refuse("view_only", "Keys are view-only on this device.", 403)
        try:
            return await fn(session)
        except KeysError as exc:
            return _answer(exc.body(), exc.status)

    @router.get("")
    async def list_keys(request: Request):
        """T0: rows from memory."""
        async def run(session: Session):
            return _answer(manager.listing(can_write=session.can_write))
        return await guarded(request, False, run)

    @router.post("/{provider_id}/next")
    async def add_next(provider_id: str, request: Request):
        """T2: stores the key, then a provider check (≤ 6 s)."""
        async def run(session: Session):
            manager.row(provider_id)  # 404 before reading the body for an unknown service
            body = await _body(request)
            secret = body.get("secret") if body else None
            if set(body or {}) != {"secret"} or not isinstance(secret, str) or not secret or len(secret) > 20000:
                return _refuse("bad_request", "Send the key as {\"secret\": \"…\"}.", 400)
            return _answer(await manager.add_next(provider_id, secret))
        return await guarded(request, True, run)

    @router.post("/{provider_id}/promote")
    async def promote(provider_id: str, request: Request):
        """T1: an atomic swap plus Credential Manager writes."""
        async def run(session: Session):
            return _answer(await manager.promote(provider_id))
        return await guarded(request, True, run)

    @router.delete("/{provider_id}/previous")
    async def drop_previous(provider_id: str, request: Request):
        async def run(session: Session):
            return _answer(await manager.drop_previous(provider_id))
        return await guarded(request, True, run)

    @router.delete("/{provider_id}")
    async def remove(provider_id: str, request: Request):
        async def run(session: Session):
            manager.row(provider_id)
            body = await _body(request)
            return _answer(await manager.remove(provider_id, (body or {}).get("confirm")))
        return await guarded(request, True, run)

    return router
