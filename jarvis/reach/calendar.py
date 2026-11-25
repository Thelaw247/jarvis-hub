"""His Google Calendar, read through Composio (v0.14.0).

On 2026-11-18 he asked "what's my first class tomorrow" and Jarvis went to Canvas, because nothing could read a
calendar. This is that missing piece: read-only (C12: reading needs no yes), one call per question after the first.

Composio's REST API v3.1 (docs.composio.dev, checked 2026-11-18):
  GET  /connected_accounts?toolkit_slugs=googlecalendar&statuses=ACTIVE   -> items[].id
  POST /tools/execute/GOOGLECALENDAR_EVENTS_LIST  {"connected_account_id", "arguments": {timeMin, timeMax, ...}}
       -> {"data": {"items": [...]}, "successful": true, "error": null}
Connecting Google Calendar (v0.15.3, docs.composio.dev checked 2026-11-19):
  GET  /auth_configs?toolkit_slug=googlecalendar            -> items[].id (the project's set-up for the toolkit)
  POST /auth_configs  {"toolkit": {"slug"}, "auth_config": {"type": "use_composio_managed_auth"}}  -> auth_config.id
  POST /connected_accounts/link  {"auth_config_id", "user_id"}  -> redirect_url (he opens it in his own browser)
The key is the Composio key from Controls › Keys (Credential Manager); it goes in the x-api-key header and is never
logged. Times are his local time (JARVIS_TZ, default America/Regina: Saskatchewan, UTC-6 all year).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any

log = logging.getLogger("jarvis.reach")
BASE = "https://backend.composio.dev/api/v3.1"
TOOLKIT = "googlecalendar"
LIST_EVENTS = "GOOGLECALENDAR_EVENTS_LIST"
CACHE_S = 60.0
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


USER_ID = "jarvis"      # one person, one user in his Composio project


def _toolkit_of(item: dict) -> str:
    """Which app a connected account belongs to ('googlecalendar'), however this API version spells it."""
    kit = item.get("toolkit")
    slug = kit.get("slug") if isinstance(kit, dict) else kit
    return str(slug or item.get("toolkit_slug") or item.get("app_name") or item.get("appName") or "").lower()


def _reason(response: Any) -> str:
    """Composio's own words for why it refused, short and on one line (an error text, never his data)."""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return ""
    err = body.get("error") if isinstance(body, dict) else None
    text = (err.get("message") if isinstance(err, dict) else err) or (body.get("message") if isinstance(body, dict) else "") or ""
    return " ".join(str(text).split())[:160]


class CalendarError(Exception):
    """Plain words for Jarvis to pass on: what's missing and what fixes it."""


class NotConnected(CalendarError):
    """The key works, but Google Calendar isn't connected in his Composio project yet."""


def local_zone(name: str | None = None) -> tzinfo:
    name = name or os.environ.get("JARVIS_TZ") or "America/Regina"
    try:
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - Windows without the tzdata package: Saskatchewan has no daylight saving
        return timezone(timedelta(hours=-6), "CST")


def which_day(text: str, today: date) -> date:
    """"today", "tomorrow", "friday" (the next one, today included), or a date like 2026-11-20."""
    t = (text or "today").strip().lower()
    if t in ("", "today", "now", "tonight"):
        return today
    if t == "tomorrow":
        return today + timedelta(days=1)
    if t == "yesterday":
        return today - timedelta(days=1)
    for i, name in enumerate(WEEKDAYS):
        if t in (name, name[:3], f"next {name}", f"this {name}"):
            ahead = (i - today.weekday()) % 7
            return today + timedelta(days=ahead + (7 if t.startswith("next ") and ahead == 0 else 0))
    try:
        return date.fromisoformat(t[:10])
    except ValueError as exc:
        raise CalendarError(f"I couldn't read {text!r} as a day. Use today, tomorrow, a weekday, or a date "
                            "like 2026-11-20.") from exc


@dataclass(frozen=True)
class Event:
    start: datetime | None      # None = an all-day event
    end: datetime | None
    day: date
    title: str
    where: str = ""

    def line(self) -> str:
        day = f"{self.day:%a} {self.day.day} {self.day:%b}"
        if self.start is None:
            when = "all day"
        else:
            end = f"–{_clock(self.end)}" if self.end is not None else ""
            when = f"{_clock(self.start)}{end}"
        return " · ".join(p for p in (day, when, self.title, self.where) if p)


def _clock(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def parse_events(items: list[dict], zone: tzinfo) -> list[Event]:
    out: list[Event] = []
    for it in items or []:
        if not isinstance(it, dict) or it.get("status") == "cancelled":
            continue
        start, end = it.get("start") or {}, it.get("end") or {}
        title = str(it.get("summary") or "(no title)").strip()
        where = str(it.get("location") or "").strip().splitlines()[0][:80] if it.get("location") else ""
        try:
            if start.get("dateTime"):
                s = datetime.fromisoformat(str(start["dateTime"]).replace("Z", "+00:00")).astimezone(zone)
                e = (datetime.fromisoformat(str(end["dateTime"]).replace("Z", "+00:00")).astimezone(zone)
                     if end.get("dateTime") else None)
                out.append(Event(s, e, s.date(), title, where))
            elif start.get("date"):
                out.append(Event(None, None, date.fromisoformat(str(start["date"])[:10]), title, where))
        except ValueError:
            continue
    out.sort(key=lambda e: (e.day, e.start.timetz().replace(tzinfo=None) if e.start else datetime.min.time()))
    return out


class CalendarClient:
    def __init__(self, keys: Any, *, zone: tzinfo | None = None, transport: Any = None,
                 clock: Any = time.monotonic) -> None:
        self.keys = keys
        self.zone = zone or local_zone()
        self._transport = transport
        self._clock = clock
        self._account: str | None = None
        self._user: str | None = None
        self._client: Any = None
        self._cache: dict[tuple, tuple[float, list[Event]]] = {}

    def today(self) -> date:
        return datetime.now(self.zone).date()

    def _keyed(self) -> Any:
        manager = getattr(self.keys, "manager", None)
        if manager is None:
            raise CalendarError("The keys aren't available yet.")
        try:
            client = manager.client("composio")
            client.lease()
        except Exception as exc:  # noqa: BLE001 - no key saved
            raise CalendarError("There's no Composio key yet. He adds it himself in the hub under Controls › Keys "
                                "(he copies it from platform.composio.dev in his own browser, not in a hub window). "
                                "Tell him that; don't open any page for it.") from exc
        return client

    async def _http(self) -> Any:
        """One HTTPS client for the whole run. Laptop B's logs of 2026-11-22: making a new one for every call froze
        the core for 2.4 to 4.8 s each time (Windows loads its certificate store on the event loop), which is a
        frozen voice. It is made once, in a thread, and kept."""
        if self._client is None:
            import asyncio  # noqa: PLC0415

            import httpx  # noqa: PLC0415

            self._client = await asyncio.to_thread(lambda: httpx.AsyncClient(timeout=10.0, transport=self._transport))
        return self._client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        client = await self._http()

        async def run(key: str) -> dict:
            r = await client.request(method, BASE + path, headers={"x-api-key": key}, **kwargs)
            if r.status_code in (401, 403):
                raise CalendarError("Composio turned the key down: check it in Controls › Keys.")
            if r.status_code >= 400:
                why = _reason(r)
                log.warning("calendar.refused", extra={"status": r.status_code, "reason": why, "step": path.split("/")[1]})
                err = CalendarError(f"Composio answered with an error ({r.status_code}{': ' + why if why else ''}).")
                err.status = r.status_code
                raise err
            return r.json() if r.content else {}

        try:
            return await self._keyed().call(run)
        except CalendarError:
            raise
        except Exception as exc:  # noqa: BLE001 - network, timeout: say so in words
            raise CalendarError(f"I couldn't reach Composio ({type(exc).__name__}).") from exc

    async def account(self) -> str:
        if self._account is None:
            got = await self._request("GET", "/connected_accounts",
                                      params={"toolkit_slugs": TOOLKIT, "statuses": "ACTIVE", "limit": 5})
            items = [i for i in got.get("items") or [] if str(i.get("status", "ACTIVE")).upper() == "ACTIVE"]
            # Laptop B, 2026-11-22: the list came back 200 and the very next call was refused (400) every time. If
            # Composio ignores the toolkit filter, the first account in the list is some other app's, and a calendar
            # call on it is a bad request. So the account is picked by its own toolkit, not by its place in the list.
            named = [i for i in items if _toolkit_of(i)]
            mine = [i for i in named if _toolkit_of(i) == TOOLKIT] if named else items
            if not mine:
                raise NotConnected("Google Calendar isn't connected in Composio yet.")
            self._account = str(mine[0]["id"])
            self._user = str(mine[0].get("user_id") or "") or USER_ID   # the id the connect link was made for
        return self._account

    async def connected(self) -> bool:
        """Is Google Calendar connected now? Asks Composio afresh. T2."""
        self._account = None
        try:
            await self.account()
        except NotConnected:
            return False
        return True

    async def connect_link(self) -> str:
        """A link he opens in his own browser to connect Google Calendar: he picks his Google account and allows
        it, on Google's and Composio's own pages. Jarvis never sees a password (C26). Nothing is connected until
        he does. T2."""
        got = await self._request("GET", "/auth_configs", params={"toolkit_slug": TOOLKIT, "limit": 5})
        configs = [c for c in got.get("items") or [] if str(c.get("status", "ENABLED")).upper() != "DISABLED"]
        if configs:
            config = str(configs[0]["id"])
        else:
            made = await self._request("POST", "/auth_configs", json={
                "toolkit": {"slug": TOOLKIT}, "auth_config": {"type": "use_composio_managed_auth"}})
            config = str((made.get("auth_config") or {}).get("id") or "")
        if not config:
            raise CalendarError("Composio didn't give a way to connect Google Calendar. Try again in a moment.")
        link = await self._request("POST", "/connected_accounts/link",
                                   json={"auth_config_id": config, "user_id": USER_ID})
        url = str(link.get("redirect_url") or "")
        if not url.startswith("https://"):
            raise CalendarError("Composio didn't give a link to connect Google Calendar. Try again in a moment.")
        return url

    async def events(self, first: date, days: int = 1, query: str | None = None) -> list[Event]:
        days = max(1, min(int(days or 1), 31))
        key = (first, days, (query or "").strip().lower())
        hit = self._cache.get(key)
        if hit is not None and self._clock() - hit[0] < CACHE_S:
            return hit[1]
        start = datetime.combine(first, datetime.min.time(), self.zone)
        end = start + timedelta(days=days)
        args: dict[str, Any] = {"calendarId": "primary", "timeMin": start.isoformat(), "timeMax": end.isoformat(),
                                "singleEvents": True, "orderBy": "startTime", "maxResults": 100,
                                "fields": "items(status,summary,location,start,end)"}
        if query and query.strip():
            args["query"] = query.strip()
        account = await self.account()
        # Composio's answer on Laptop B (2026-11-22, every call): "User ID is required with connected account".
        body = {"connected_account_id": account, "arguments": args, **({"user_id": self._user} if self._user else {})}
        try:
            got = await self._request("POST", f"/tools/execute/{LIST_EVENTS}", json=body)
        except CalendarError:
            self._account = None   # look the connection up afresh next time
            raise
        if got.get("successful") is False:
            self._account = None    # the connection may have been removed: look it up again next time
            raise CalendarError("Google Calendar didn't answer through Composio. If it keeps happening, reconnect "
                                "Google Calendar at platform.composio.dev.")
        data = got.get("data") or {}
        for nest in ("response_data", "data"):      # older responses wrapped the calendar's answer once more
            if "items" not in data and isinstance(data.get(nest), dict):
                data = data[nest]
        events = [e for e in parse_events(data.get("items") or [], self.zone) if first <= e.day < first + timedelta(days=days)]
        self._cache[key] = (self._clock(), events)
        while len(self._cache) > 30:
            self._cache.pop(next(iter(self._cache)))
        return events
