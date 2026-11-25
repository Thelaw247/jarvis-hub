"""The services Jarvis holds keys for, and the cheap check each one runs before a key may go live.

A check result is a fixed reason code, never the provider's own error text (some providers echo part of the
key back). Every HTTP call goes to a fixed URL of the provider; nothing in a pasted key or client file can
point a check somewhere else.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import httpx

from .backend import MAX_SECRET_CHARS

CHECK_TIMEOUT_S = 6.0


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    reason: str | None = None  # keys.schema.json $defs/reason
    expires: float | None = None  # epoch seconds, when the provider says the credential runs out
    shape_only: bool = False


class ShapeError(ValueError):
    """The pasted text isn't what this service's key looks like. ``reason`` is a contract reason code."""

    def __init__(self, reason: str = "bad_shape") -> None:
        super().__init__(reason)
        self.reason = reason


Aux = Mapping[str, str]
HttpGetter = Callable[[], httpx.AsyncClient]


@dataclass
class Provider:
    """One service. Subclasses fill ``validate``, ``last4`` and ``_check``."""

    id: str
    label: str
    noun: str  # used in Activity lines: "Claude key replaced"
    kind: str = "token"  # token | client_json | password
    checkable: bool = True
    console_url: str | None = None
    default: bool = True  # always has a row on the Keys page
    http: HttpGetter | None = field(default=None, repr=False)

    def validate(self, secret: str) -> str:
        """The key as it will be stored (trimmed), or ``ShapeError``. T0."""
        token = secret.strip()
        if len(token) > MAX_SECRET_CHARS:
            raise ShapeError("too_long")
        if len(token) < 8 or any(c.isspace() for c in token):
            raise ShapeError()
        return token

    def last4(self, secret: str) -> str | None:
        return secret[-4:]

    def public(self) -> dict:
        out = {"id": self.id, "label": self.label, "kind": self.kind, "checkable": self.checkable}
        if self.console_url:
            out["console_url"] = self.console_url
        return out

    async def check(self, secret: str, aux: Aux | None = None) -> CheckResult:
        """Validate the shape, then one cheap call to the provider. T2 (network, ≤ CHECK_TIMEOUT_S)."""
        try:
            secret = self.validate(secret)
        except ShapeError as exc:
            return CheckResult(False, exc.reason)
        if not self.checkable:
            return CheckResult(True, shape_only=True)
        try:
            return await self._check(secret, aux or {})
        except httpx.TransportError:
            return CheckResult(False, "unreachable")
        except Exception:  # noqa: BLE001 - never let a check's error text out
            return CheckResult(False, "provider_error")

    async def _check(self, secret: str, aux: Aux) -> CheckResult:  # pragma: no cover - overridden
        raise NotImplementedError

    def _client(self) -> httpx.AsyncClient:
        if self.http is None:
            raise RuntimeError("no http client")
        return self.http()


def from_status(code: int) -> CheckResult:
    if 200 <= code < 300:
        return CheckResult(True)
    return CheckResult(False, {401: "rejected", 403: "forbidden", 429: "rate_limited"}.get(code, "provider_error"))


@dataclass
class Anthropic(Provider):
    async def _check(self, secret: str, aux: Aux) -> CheckResult:
        r = await self._client().get("https://api.anthropic.com/v1/models", params={"limit": 1},
                                     headers={"x-api-key": secret, "anthropic-version": "2023-06-01"})
        return from_status(r.status_code)

    def validate(self, secret: str) -> str:
        token = super().validate(secret)
        if not token.startswith("sk-ant-"):
            raise ShapeError()
        return token


@dataclass
class ElevenLabs(Provider):
    async def _check(self, secret: str, aux: Aux) -> CheckResult:
        r = await self._client().get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": secret})
        return from_status(r.status_code)


@dataclass
class Composio(Provider):
    async def _check(self, secret: str, aux: Aux) -> CheckResult:
        r = await self._client().get("https://backend.composio.dev/api/v3.1/connected_accounts", params={"limit": 1},
                                     headers={"x-api-key": secret})
        return from_status(r.status_code)


@dataclass
class OpenWeather(Provider):
    async def _check(self, secret: str, aux: Aux) -> CheckResult:
        # OpenWeather only takes the key in the query string; the log filter below strips queries from httpx logs.
        r = await self._client().get("https://api.openweathermap.org/data/2.5/weather",
                                     params={"lat": 0, "lon": 0, "appid": secret})
        return from_status(r.status_code)


@dataclass
class Password(Provider):
    """A password with no remote check (restic). Nothing of it is ever shown, not even the last 4."""

    def validate(self, secret: str) -> str:
        pw = secret.rstrip("\r\n")
        if len(pw) > MAX_SECRET_CHARS:
            raise ShapeError("too_long")
        if len(pw) < 8:
            raise ShapeError()
        return pw

    def last4(self, secret: str) -> str | None:
        return None


GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class GoogleClient(Provider):
    """Google's OAuth client file. Shape check always; a token refresh when a refresh token is stored (aux)."""

    def _parse(self, secret: str) -> dict:
        try:
            doc = json.loads(secret)
        except ValueError:
            raise ShapeError() from None
        inner = doc.get("installed") or doc.get("web") if isinstance(doc, dict) else None
        if not isinstance(inner, dict):
            raise ShapeError()
        cid, csec = inner.get("client_id"), inner.get("client_secret")
        if not (isinstance(cid, str) and cid.endswith(".apps.googleusercontent.com")
                and isinstance(csec, str) and len(csec) >= 8):
            raise ShapeError()
        return inner

    def validate(self, secret: str) -> str:
        if len(secret) > 20000:
            raise ShapeError("too_long")
        inner = self._parse(secret.strip())
        kind = "installed" if "installed" in json.loads(secret) else "web"
        compact = json.dumps({kind: inner}, separators=(",", ":"), sort_keys=True)
        if len(compact) > MAX_SECRET_CHARS:
            raise ShapeError("too_long")
        return compact

    def last4(self, secret: str) -> str | None:
        return self._parse(secret)["client_secret"][-4:]

    async def _check(self, secret: str, aux: Aux) -> CheckResult:
        refresh = aux.get("refresh_token")
        if not refresh:
            return CheckResult(True, shape_only=True)
        inner = self._parse(secret)
        r = await self._client().post(GOOGLE_TOKEN_URL, data={
            "client_id": inner["client_id"], "client_secret": inner["client_secret"],
            "refresh_token": refresh, "grant_type": "refresh_token"})
        if r.status_code == 200:
            try:
                left = r.json().get("refresh_token_expires_in")
            except ValueError:
                left = None
            return CheckResult(True, expires=time.time() + float(left) if left else None)
        if r.status_code == 400:
            return CheckResult(False, "refresh_failed")
        return CheckResult(False, "rejected" if r.status_code == 401 else from_status(r.status_code).reason)


class Registry:
    """The services, in display order. Default ones always have a row; the others can be added from a list."""

    def __init__(self, providers: list[Provider]) -> None:
        self._by_id = {p.id: p for p in providers}

    def get(self, provider_id: str) -> Provider | None:
        return self._by_id.get(provider_id)

    def __iter__(self):
        return iter(self._by_id.values())


def default_providers(http: HttpGetter | None = None) -> list[Provider]:
    return [
        Anthropic("anthropic", "Claude (Anthropic API)", "Claude key", http=http,
                  console_url="https://console.anthropic.com/settings/keys"),
        ElevenLabs("elevenlabs", "ElevenLabs (voice)", "ElevenLabs key", http=http,
                   console_url="https://elevenlabs.io/app/settings/api-keys"),
        Composio("composio", "Composio (app connections)", "Composio key", http=http,
                 console_url="https://platform.composio.dev"),
        Password("restic", "Backup password (restic)", "backup password", kind="password", checkable=False),
        # Optional: added from the "Add a service" list (Composio handles Gmail, Calendar and Drive now).
        GoogleClient("google-oauth", "Google OAuth client", "Google OAuth client", kind="client_json",
                     default=False, http=http, console_url="https://console.cloud.google.com/apis/credentials"),
        OpenWeather("openweather", "OpenWeather", "OpenWeather key", default=False, http=http,
                    console_url="https://home.openweathermap.org/api_keys"),
    ]


class _SharedHttp:
    """One lazily made AsyncClient for every check (keeps TLS connections warm)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def __call__(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=CHECK_TIMEOUT_S, follow_redirects=False)
        return self._client


def default_registry(http: HttpGetter | None = None) -> Registry:
    install_log_redaction()
    return Registry(default_providers(http or _SharedHttp()))


class _StripQueries(logging.Filter):
    """httpx logs every request URL at INFO; drop the query so a key passed as a parameter never lands in a log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(a.copy_with(query=None) if isinstance(a, httpx.URL) else a for a in record.args)
        return True


_FILTER = _StripQueries()


def install_log_redaction() -> None:
    for name in ("httpx", "httpcore"):
        lg = logging.getLogger(name)
        if _FILTER not in lg.filters:
            lg.addFilter(_FILTER)

