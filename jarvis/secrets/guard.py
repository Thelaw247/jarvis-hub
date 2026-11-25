"""Who may touch /api/keys: requests from this machine or the tailnet, with a valid hub session token.

The IP is the socket's peer address only (``request.client.host``); forwarded-for headers are never trusted.
Behind ``tailscale serve`` requests arrive from loopback, which is why the session token is always required too.
"""
from __future__ import annotations

import inspect
import ipaddress
from collections.abc import Callable
from dataclasses import dataclass

SESSION_HEADER = "X-Jarvis-Session"
TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")  # Tailscale's CGNAT range
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")  # Tailscale's IPv6 range


@dataclass(frozen=True)
class Session:
    """What a verified hub session may do. The phone's session is view-only (``can_write=False``)."""

    can_write: bool = True
    device: str | None = None


# verifier(token) -> Session (or True for a full session), or None/False to refuse. May be async.
Verifier = Callable[[str], object]


def ip_allowed(host: str | None) -> bool:
    """Loopback or tailnet. T0."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return True
    return ip in (TAILNET_V4 if ip.version == 4 else TAILNET_V6)


async def verify(verifier: Verifier, host: str | None, token: str | None) -> Session | None:
    """The request's Session, or None when it is refused. T0 (plus whatever the verifier costs)."""
    if not ip_allowed(host) or not token:
        return None
    try:
        out = verifier(token)
        if inspect.isawaitable(out):
            out = await out
    except Exception:  # noqa: BLE001 - a broken verifier refuses
        return None
    if out is True:
        return Session()
    return out if isinstance(out, Session) else None
