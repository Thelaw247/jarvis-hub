"""Demo answers for the hub's Keys page (Controls › Keys, K2; JARVIS_CORE_BUILD_MAP §3; contracts/keys.schema.json).

The real keys live only in Windows Credential Manager on Laptop B, behind jarvis-core's `/api/keys` (K1). The
hub on its own never holds a key, so the demo backend here:

- answers `GET /api/keys` with a contract-shaped document of **example rows** (made-up last-4s, `can_write:
  false`) and the response header `X-Jarvis-Keys: example`, so the page says "Jarvis core isn't connected yet",
  marks every row as an example and accepts nothing;
- can simulate each row state for the scenes (`?scene=live|next_waiting|checking|failed_check|fell_back|
  old_kept|missing|expiring|not_connected`), always as examples;
- answers every write (`POST /api/keys/{id}/next|promote`, `DELETE /api/keys/{id}[/previous]`) with a refusal
  **without reading the request body**: nothing sent to it is parsed, logged, kept or echoed.

Nothing in this module is a secret: the last-4s are made up and never derived from anything typed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

EXAMPLE_HEADER = "X-Jarvis-Keys"  # "example": answered by the hub's demo, not by jarvis-core
NOT_CONNECTED = "Jarvis core isn't connected yet. Nothing was sent or kept."
FALLBACK_MIN = 15  # the old key stays as `previous` this long after "Make live" (build map §3, step 3)

# One row per service the page always shows, in this order. Composio handles Gmail, Calendar and Drive, so the
# Google OAuth client is an optional service in the "Add a service" list (his change, 2026-11-15).
SERVICES: list[dict[str, Any]] = [
    {"id": "anthropic", "label": "Claude (Anthropic API)", "kind": "token", "checkable": True,
     "console_url": "https://console.anthropic.com/settings/keys"},
    {"id": "elevenlabs", "label": "ElevenLabs (voice)", "kind": "token", "checkable": True,
     "console_url": "https://elevenlabs.io/app/settings/api-keys"},
    {"id": "composio", "label": "Composio (Gmail, Calendar, Drive)", "kind": "token", "checkable": True,
     "console_url": "https://platform.composio.dev"},
    {"id": "restic", "label": "Backup password (restic)", "kind": "password", "checkable": False},
]
# More services he can add from a list, without code changes to the page ("Add a service").
CATALOG: list[dict[str, Any]] = [
    {"id": "google-oauth", "label": "Google OAuth client", "kind": "client_json", "checkable": True,
     "console_url": "https://console.cloud.google.com/apis/credentials"},
    {"id": "openweather", "label": "OpenWeather", "kind": "token", "checkable": True,
     "console_url": "https://home.openweathermap.org/api_keys"},
]
# Made-up last-4s, marked as examples on the page. Never taken from anything typed.
FAKE_LAST4 = {"anthropic": "EX01", "elevenlabs": "EX02", "composio": "EX03", "google-oauth": "EX04"}
FAKE_NEXT = "EX09"
SCENES = ("not_connected", "live", "next_waiting", "checking", "failed_check", "fell_back", "old_kept", "missing",
          "expiring")


def _iso(d: datetime) -> str:
    return d.replace(microsecond=0).isoformat()


def _now(value: str | None) -> datetime:
    """The scene's clock (the page passes its own `now`, so times read right against a frozen fixture day)."""
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None) if value else datetime.now()
    except ValueError:
        return datetime.now()


def _slot(service: dict[str, Any], added: datetime, checked: datetime | None, check: str = "ok", **more: Any) -> dict[str, Any]:
    password = service["kind"] == "password"
    slot = {"last4": None if password else FAKE_LAST4.get(service["id"], "EX00"), "added": _iso(added),
            "checked": _iso(checked) if checked else None, "check": "shape_only" if password and check == "ok" else check}
    slot.update(more)
    return slot


def _row(service: dict[str, Any], now: datetime) -> dict[str, Any]:
    row = {**service, "status": "live", "live": _slot(service, now - timedelta(days=3, hours=2), now - timedelta(minutes=4)),
           "next": None, "previous": None, "used": _iso(now - timedelta(seconds=12))}
    if service["kind"] == "password":  # the backup password is read once a night, not per turn
        row["used"] = _iso((now - timedelta(days=1)).replace(hour=3, minute=0, second=0))
    return row


def _missing(row: dict[str, Any]) -> None:
    row.update(status="missing", live=None, used=None)


def rows_for(scene: str | None = None, now: str | None = None) -> list[dict[str, Any]]:
    """The example rows for one simulated state. Unknown scenes fall back to the calm not-connected set. T0."""
    at = _now(now)
    scene = scene if scene in SCENES else "not_connected"
    rows = {s["id"]: _row(s, at) for s in SERVICES}
    claude, svc = rows["anthropic"], SERVICES[0]
    fresh = at - timedelta(seconds=20)
    if scene == "not_connected":
        _missing(rows["restic"])
    elif scene == "next_waiting":
        claude.update(status="next_waiting", detail="A new key passed its check. Make it live when you're ready.",
                      next={**_slot(svc, fresh, fresh), "last4": FAKE_NEXT})
    elif scene == "checking":
        claude.update(status="checking", next={**_slot(svc, fresh, None, "checking"), "last4": FAKE_NEXT})
    elif scene == "failed_check":
        claude.update(status="failed_check", detail="Anthropic refused the new key. The live key is still in use.",
                      next={**_slot(svc, fresh, fresh, "failed", reason="rejected"), "last4": FAKE_NEXT})
    elif scene == "fell_back":  # the new key was refused once live, inside the 15 minutes: back to the old one
        claude.update(status="fell_back",
                      detail="The new key was refused after it went live, so Jarvis went back to the old one.",
                      next={**_slot(svc, at - timedelta(minutes=4), fresh, "failed", reason="refused_after_swap"),
                            "last4": FAKE_NEXT})
    elif scene == "old_kept":  # just made live: the old key is kept for 15 minutes in case the new one fails
        swap = at - timedelta(minutes=1)
        claude.update(live={**_slot(svc, swap, swap), "last4": FAKE_NEXT}, used=_iso(at - timedelta(seconds=3)),
                      previous=_slot(svc, at - timedelta(days=44), swap, until=_iso(swap + timedelta(minutes=FALLBACK_MIN))))
    elif scene == "missing":
        _missing(rows["composio"])
        _missing(rows["restic"])
    elif scene == "expiring":  # an optional service added from the list, whose Google sign-in runs out soon
        google = _row(CATALOG[0], at)
        google["live"]["expires"] = _iso(at + timedelta(days=3))
        google.update(status="expiring", detail="The Google sign-in runs out in 3 days. Sign in again before then.",
                      used=_iso(at - timedelta(minutes=6)))
        rows[google["id"]] = google
    return list(rows.values())


def snapshot(scene: str | None = None, now: str | None = None) -> dict[str, Any]:
    """What `GET /api/keys` answers in demo mode: examples only, nothing can be written. T0."""
    rows = rows_for(scene, now)
    have = {r["id"] for r in rows}
    return {"v": 2, "can_write": False, "rows": rows, "addable": [dict(c) for c in CATALOG if c["id"] not in have],
            "audit": []}


def yes_flag(row: dict[str, Any], at: str) -> dict[str, Any] | None:
    """The "Your yes" Rail item a fell-back row raises (contracts/rail.schema.json $defs/item), or None.
    For the hub (or the core) to put in `rail.slots.yes` on `keys.updated`, and drop when the row leaves fell_back.
    Mirrors ui/views/keys/keys.js keysYesFlag. T0."""
    if row.get("status") != "fell_back":
        return None
    name = str(row.get("label", row.get("id", ""))).split(" (")[0]
    return {"ref": f"keys:{row['id']}", "slot": "yes", "kind": "notice", "title": f"{name} key fell back", "at": at,
            "state": "yes", "detail": "The new key was refused once live · Controls › Keys"}


router = APIRouter()
_EXAMPLE = {EXAMPLE_HEADER: "example", "Cache-Control": "no-store"}
_REFUSAL = {"error": "not_allowed", "message": NOT_CONNECTED}


@router.get("/api/keys")
async def get_keys(scene: str | None = None, now: str | None = None) -> JSONResponse:
    return JSONResponse(snapshot(scene, now), headers=_EXAMPLE)


# Writes: refused, and the body is never read, so a pasted key can't be parsed, logged or kept here.
# 200 with the contract's error shape (not 403), so the page's "not connected" path is the only one it takes.
@router.post("/api/keys/{key_id}/{action}")
@router.delete("/api/keys/{key_id}/{action}")
@router.delete("/api/keys/{key_id}")
async def refuse(key_id: str, action: str = "") -> JSONResponse:  # noqa: ARG001
    return JSONResponse(_REFUSAL, headers=_EXAMPLE)
