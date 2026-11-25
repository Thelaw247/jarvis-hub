"""KeyManager: the two-slot rotation (JARVIS_CORE_BUILD_MAP §3).

add next (stored + checked, nothing changes) → promote (atomic swap; old key kept as previous for 15 min)
→ previous removed (by him, or by the watchdog after 15 min). A 401/403 on the new key inside that window
falls back to the previous key at once. A key that failed its check is never made live.

Secrets live only in the backend (Credential Manager) and in the KeyedClients' memory. Rows, events, audit
entries and logs carry ids, times, statuses, fixed reason codes and at most a key's last 4 characters.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Callable
from datetime import datetime

from .backend import SecretBackend, StoreUnavailable, service_name
from .client import KeyedClient, Lease
from .meta import MetaFile
from .providers import CheckResult, Provider, Registry, ShapeError

log = logging.getLogger("jarvis.secrets")

WINDOW_S = 15 * 60  # previous key kept, and fall-back armed, for 15 minutes after a swap
RECHECK_S = 10 * 60  # promote re-checks a next key whose check is older than this
EXPIRING_S = 72 * 3600  # a credential that runs out within 3 days shows as Expiring
AUX_NAMES = ("refresh_token",)  # extra secrets a provider may keep (Google's refresh token)
AUDIT_SHOWN = 20

Emit = Callable[[str, dict], object]


class KeysError(Exception):
    """An API-level refusal: ``code`` is a contract error code, ``status`` the HTTP status."""

    def __init__(self, code: str, message: str, status: int, row: dict | None = None) -> None:
        super().__init__(code)
        self.code, self.message, self.status, self.row = code, message, status, row

    def body(self) -> dict:
        out = {"error": self.code, "message": self.message}
        if self.row is not None:
            out["row"] = self.row
        return out


def iso(t: float | None) -> str | None:
    return None if t is None else datetime.fromtimestamp(t).isoformat(timespec="seconds")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


WHY = {
    "added": "You added it on the Keys page and it passed its check. Make it live when you're ready.",
    "failed_check": "It failed its check, so it was not made live. The live key is unchanged.",
    "made_live": "You made it live on the Keys page.",
    "replaced": "You made the new key live on the Keys page. The old one is kept for 15 minutes in case.",
    "fell_back": "The new key was refused within 15 minutes of going live, so Jarvis went back to the old one.",
    "previous_removed": "The old key was removed. Also revoke it in the provider's console.",
    "removed": "You removed it on the Keys page.",
}


class KeyManager:
    def __init__(self, backend: SecretBackend, registry: Registry, meta: MetaFile, *,
                 clock: Callable[[], float] = time.time, emit: Emit | None = None,
                 window_s: float = WINDOW_S, recheck_s: float = RECHECK_S) -> None:
        self.backend, self.registry, self.meta = backend, registry, meta
        self.clock, self._emit_fn = clock, emit
        self.window_s, self.recheck_s = window_s, recheck_s
        self._clients: dict[str, KeyedClient] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ---- startup and clients ---------------------------------------------------------------------------------
    def load(self) -> None:
        """Read every stored live/previous key into memory once, at startup. T1 (a few ms per key)."""
        for p in self.registry:
            if p.default or p.id in self.meta.data["providers"]:
                self._load_client(p.id)

    def _load_client(self, provider_id: str) -> KeyedClient:
        client = self._clients.get(provider_id)
        if client is None:
            client = KeyedClient(provider_id, on_auth_failure=self.on_auth_failure, clock=self.clock)
            self._clients[provider_id] = client
        entry = self.meta.provider(provider_id) if provider_id in self.meta.data["providers"] else None
        swapped = entry["swapped_at"] if entry else None
        client.load(self.backend.get(service_name(provider_id, "live")),
                    self.backend.get(service_name(provider_id, "previous")), swapped)
        return client

    def client(self, provider_id: str) -> KeyedClient:
        """The KeyedClient other parts of the core use (voice: anthropic, elevenlabs; Reach: composio). T0 once loaded."""
        self._provider(provider_id)
        return self._clients.get(provider_id) or self._load_client(provider_id)

    def set_aux(self, provider_id: str, name: str, secret: str | None) -> None:
        """Store or clear an extra secret (Google's refresh token, written by the sign-in flow). T1."""
        if name not in AUX_NAMES:
            raise ValueError("unknown aux name")
        svc = service_name(provider_id, name)
        self.backend.set(svc, secret) if secret else self.backend.delete(svc)

    # ---- reading rows (no secrets) ---------------------------------------------------------------------------
    def listing(self, can_write: bool = True) -> dict:
        """GET /api/keys. T0 (memory only, no Credential Manager reads)."""
        rows, addable = [], []
        for p in self.registry:
            if p.default or self._has_any(p.id):
                rows.append(self.row(p.id))
            else:
                addable.append(p.public())
        return {"v": 2, "can_write": can_write, "rows": rows, "addable": addable,
                "audit": self.meta.data["audit"][:AUDIT_SHOWN]}

    def _has_any(self, provider_id: str) -> bool:
        entry = self.meta.data["providers"].get(provider_id)
        return bool(entry and entry.get("slots"))

    def row(self, provider_id: str) -> dict:
        p = self._provider(provider_id)
        entry = self.meta.data["providers"].get(provider_id) or {"slots": {}, "swapped_at": None, "fell_back": False}
        slots = entry["slots"]
        status, detail = self._status(p, entry)
        client = self._clients.get(provider_id)
        out = {**p.public(), "status": status}
        if detail:
            out["detail"] = detail
        for name in ("live", "next", "previous"):
            out[name] = self._slot_out(slots.get(name), entry if name == "previous" else None)
        out["used"] = iso(client.used) if client else None
        return out

    def _slot_out(self, info: dict | None, entry: dict | None) -> dict | None:
        if not info:
            return None
        out = {"last4": info.get("last4"), "added": iso(info["added"]), "checked": iso(info.get("checked")),
               "check": info["check"]}
        if info.get("reason"):
            out["reason"] = info["reason"]
        if info.get("expires"):
            out["expires"] = iso(info["expires"])
        if entry is not None and entry.get("swapped_at"):
            out["until"] = iso(entry["swapped_at"] + self.window_s)
        return out

    def _status(self, p: Provider, entry: dict) -> tuple[str, str | None]:
        slots = entry["slots"]
        live, nxt = slots.get("live"), slots.get("next")
        if nxt and nxt["check"] == "checking":
            return "checking", None
        if entry.get("fell_back"):
            return "fell_back", (f"The new {p.noun} was refused after it went live, so Jarvis went back to the "
                                 f"previous one. Check the new key in the provider's console.")
        if nxt and nxt["check"] == "failed":
            keep = " The live key is still in use." if live else ""
            return "failed_check", f"The new {p.noun} failed its check, so it wasn't made live.{keep}"
        if nxt:
            return "next_waiting", f"A new {p.noun} passed its check. Make it live when you're ready."
        if not live:
            return "missing", None
        if live.get("expires") and live["expires"] - self.clock() < EXPIRING_S:
            return "expiring", f"The {p.noun} runs out soon. Renew it before then."
        return "live", None

    # ---- changes ---------------------------------------------------------------------------------------------
    async def add_next(self, provider_id: str, secret: str) -> dict:
        """Store a pasted key as next and check it. Never makes it live. T2 (the check is a network call)."""
        p = self._provider(provider_id)
        t0 = time.perf_counter()
        async with self._lock(provider_id):
            entry = self.meta.provider(provider_id)
            entry["fell_back"] = False
            now = self.clock()
            try:
                value = p.validate(secret)
            except ShapeError as exc:
                entry["slots"]["next"] = {"last4": None, "added": now, "checked": now, "check": "failed",
                                          "reason": exc.reason}
                self._store(lambda: self.backend.delete(service_name(provider_id, "next")))
                return await self._changed(p, "failed_check", f"New {p.noun} failed its check", t0)
            self._store(lambda: self.backend.set(service_name(provider_id, "next"), value))
            entry["slots"]["next"] = {"last4": p.last4(value), "added": now, "checked": None, "check": "checking"}
            self.meta.save()
            await self._emit("keys.updated", {"row": self.row(provider_id)})
            result = await p.check(value, self._aux(provider_id))
            self._record_check(provider_id, entry["slots"]["next"], result)
            if not result.ok:
                return await self._changed(p, "failed_check", f"New {p.noun} failed its check", t0)
            return await self._changed(p, "added", f"New {p.noun} added and checked", t0)

    async def promote(self, provider_id: str) -> dict:
        """Make the checked next key live: an atomic swap in memory; the old key stays as previous. T1
        (Credential Manager writes; T2 only when the check is older than ``recheck_s`` and runs again)."""
        p = self._provider(provider_id)
        t0 = time.perf_counter()
        async with self._lock(provider_id):
            entry = self.meta.provider(provider_id)
            slots = entry["slots"]
            nxt = slots.get("next")
            secret = self._store(lambda: self.backend.get(service_name(provider_id, "next"))) if nxt else None
            if not nxt or secret is None:
                raise KeysError("no_next", f"There's no new {p.noun} to make live. Add one first.", 409,
                                self.row(provider_id))
            if nxt["check"] not in ("ok", "shape_only"):
                raise KeysError("next_not_checked", f"The new {p.noun} hasn't passed its check, so it can't go live.",
                                409, self.row(provider_id))
            if p.checkable and self.clock() - (nxt.get("checked") or 0) > self.recheck_s:
                result = await p.check(secret, self._aux(provider_id))
                self._record_check(provider_id, nxt, result)
                if not result.ok:
                    row = await self._changed(p, "failed_check", f"New {p.noun} failed its check", t0)
                    raise KeysError("next_not_checked", f"The new {p.noun} failed its check again, so it stays out.",
                                    409, row)
            old = self._store(lambda: self.backend.get(service_name(provider_id, "live")))

            def write() -> None:
                if old is not None:
                    self.backend.set(service_name(provider_id, "previous"), old)
                else:
                    self.backend.delete(service_name(provider_id, "previous"))
                self.backend.set(service_name(provider_id, "live"), secret)
                self.backend.delete(service_name(provider_id, "next"))

            self._store(write)
            client = self.client(provider_id)
            client.swap(secret, keep_previous=old is not None)  # the swap itself: one assignment, < 1 ms
            slots.pop("previous", None)
            if old is not None and slots.get("live"):
                slots["previous"] = slots["live"]
            slots["live"] = slots.pop("next")
            entry["swapped_at"] = client.swapped_at if old is not None else None
            entry["fell_back"] = False
            if old is not None:
                return await self._changed(p, "replaced", f"{_cap(p.noun)} replaced", t0)
            return await self._changed(p, "made_live", f"{_cap(p.noun)} made live", t0)

    async def drop_previous(self, provider_id: str, *, auto: bool = False) -> dict:
        """Delete the previous key from Credential Manager (by him, or by the watchdog). T1."""
        p = self._provider(provider_id)
        t0 = time.perf_counter()
        async with self._lock(provider_id):
            entry = self.meta.provider(provider_id)
            if not entry["slots"].get("previous"):
                if auto:
                    return self.row(provider_id)
                raise KeysError("no_previous", f"There's no old {p.noun} to remove.", 409, self.row(provider_id))
            self._store(lambda: self.backend.delete(service_name(provider_id, "previous")))
            self.client(provider_id).drop_previous()
            entry["slots"].pop("previous", None)
            entry["swapped_at"] = None
            return await self._changed(p, "previous_removed", f"Old {p.noun} removed", t0, auto=auto)

    async def remove(self, provider_id: str, confirm: object) -> dict:
        """Remove every slot of a service (and its extras). Needs ``confirm`` equal to the id. T1."""
        p = self._provider(provider_id)
        if confirm != provider_id:
            raise KeysError("confirm_required", f"To remove the {p.noun}, confirm with the service's id.", 400)
        t0 = time.perf_counter()
        async with self._lock(provider_id):
            def wipe() -> None:
                for name in ("live", "next", "previous", *AUX_NAMES):
                    self.backend.delete(service_name(provider_id, name))

            self._store(wipe)
            self.client(provider_id).load(None, None, None)
            self.meta.forget(provider_id)
            return await self._changed(p, "removed", f"{_cap(p.noun)} removed", t0)

    # ---- fall-back and the watchdog --------------------------------------------------------------------------
    async def on_auth_failure(self, provider_id: str, lease: Lease) -> bool:
        """A request got 401/403. Within 15 min of a swap, go back to the previous key. Returns True when the
        caller should retry with a fresh lease. The in-memory switch is T0; persisting it is T1, after."""
        client = self._clients[provider_id]
        if lease.generation != client.generation:
            return True  # the key changed since this request started: retry on the current one
        swapped = client.swapped_at
        if not client.has_previous or swapped is None or self.clock() - swapped > self.window_s:
            return False
        client.fall_back()
        p = self._provider(provider_id)
        t0 = time.perf_counter()
        async with self._lock(provider_id):
            entry = self.meta.provider(provider_id)
            slots = entry["slots"]

            def write() -> None:
                prev = self.backend.get(service_name(provider_id, "previous"))
                if prev is not None:
                    self.backend.set(service_name(provider_id, "live"), prev)
                self.backend.delete(service_name(provider_id, "previous"))
                self.backend.delete(service_name(provider_id, "next"))

            try:
                self._store(write)
            except KeysError:
                log.error("keys.fallback.persist_failed", extra={"provider": provider_id})
            refused = slots.get("live") or {"last4": None, "added": self.clock()}
            slots["next"] = {**refused, "checked": self.clock(), "check": "failed", "reason": "refused_after_swap"}
            if slots.get("previous"):
                slots["live"] = slots.pop("previous")
            entry["swapped_at"] = None
            entry["fell_back"] = True
            await self._changed(p, "fell_back", f"Went back to the previous {p.noun}: the new one was refused", t0,
                                level=logging.WARNING)
        return True

    async def sweep(self, now: float | None = None) -> list[str]:
        """Remove every previous key older than the window. T1. Returns the provider ids it cleaned."""
        now = self.clock() if now is None else now
        done = []
        for provider_id, entry in list(self.meta.data["providers"].items()):
            swapped = entry.get("swapped_at")
            if entry.get("slots", {}).get("previous") and swapped is not None and now - swapped >= self.window_s:
                await self.drop_previous(provider_id, auto=True)
                done.append(provider_id)
        return done

    async def watchdog(self, interval_s: float = 15.0, sleep=asyncio.sleep) -> None:
        """Run forever (K0 starts it as a task): sweep, then wait. Never raises on a store error."""
        while True:
            try:
                await self.sweep()
            except KeysError:
                log.error("keys.watchdog.store_unavailable")
            await sleep(interval_s)

    # ---- helpers ---------------------------------------------------------------------------------------------
    def _provider(self, provider_id: str) -> Provider:
        p = self.registry.get(provider_id)
        if p is None:
            raise KeysError("unknown_provider", "Jarvis doesn't know that service.", 404)
        return p

    def _lock(self, provider_id: str) -> asyncio.Lock:
        return self._locks.setdefault(provider_id, asyncio.Lock())

    def _store(self, fn):
        try:
            return fn()
        except StoreUnavailable:
            raise KeysError("store_unavailable", "Windows Credential Manager can't be reached right now.",
                            503) from None

    def _aux(self, provider_id: str) -> dict[str, str]:
        out = {}
        for name in AUX_NAMES:
            value = self._store(lambda n=name: self.backend.get(service_name(provider_id, n)))
            if value:
                out[name] = value
        return out

    def _record_check(self, provider_id: str, info: dict, result: CheckResult) -> None:
        info["checked"] = self.clock()
        info["check"] = ("shape_only" if result.shape_only else "ok") if result.ok else "failed"
        info.pop("reason", None)
        if not result.ok:
            info["reason"] = result.reason or "provider_error"
            self._store(lambda: self.backend.delete(service_name(provider_id, "next")))
        if result.expires:
            info["expires"] = result.expires

    async def _changed(self, p: Provider, what: str, text: str, t0: float, *, auto: bool = False,
                       level: int = logging.INFO) -> dict:
        audit = self.meta.add_audit({"ts": iso(self.clock()), "provider": p.id, "what": what, "text": text})
        self.meta.save()
        row = self.row(p.id)
        log.log(level, "keys.%s", what, extra={"provider": p.id, "audit": audit["id"],
                                                "ms": round((time.perf_counter() - t0) * 1000, 2)})
        await self._emit("keys.updated", {"row": row, "audit": audit})
        why = WHY[what]
        if what == "previous_removed" and not auto:
            why = "You removed it on the Keys page. Also revoke it in the provider's console."
        await self._emit("activity.added", {"id": audit["id"], "ts": audit["ts"], "kind": "done", "what": text,
                                            "why": why, "category": "keys"})
        return row

    async def _emit(self, kind: str, data: dict) -> None:
        if self._emit_fn is None:
            return
        try:
            out = self._emit_fn(kind, data)
            if inspect.isawaitable(out):
                await out
        except Exception:  # noqa: BLE001 - an event that can't be sent never breaks a key change
            log.error("keys.emit_failed", extra={"event": kind})
