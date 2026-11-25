"""KeyedClient: the live key in memory, swapped atomically, with a 15-minute fall-back to the previous key.

The keys sit in one immutable ``_Keys`` object; ``swap`` replaces that object in a single assignment, so a
request reads either the old pair or the new one, never a mix. A request takes its key once, at its start
(a ``Lease``), and finishes on it: in-flight requests keep the old key, new requests get the new one.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

AUTH_FAILURE_CODES = (401, 403)


class KeyMissing(RuntimeError):
    """There is no live key for this service (the Keys page shows it as Missing)."""


class AuthFailed(RuntimeError):
    """Raise from a request function when the provider answered 401/403 (when not using httpx's raise)."""

    def __init__(self, status_code: int = 401) -> None:
        super().__init__(f"auth failed ({status_code})")
        self.status_code = status_code


def is_auth_failure(exc: BaseException) -> bool:
    """True for a 401/403 from httpx (``HTTPStatusError``), an SDK error with ``status_code``, or ``AuthFailed``. T0."""
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code in AUTH_FAILURE_CODES


@dataclass(frozen=True)
class _Keys:
    live: str | None
    previous: str | None
    generation: int
    swapped_at: float | None


@dataclass(frozen=True)
class Lease:
    """The key one request uses from its start to its end."""

    secret: str
    generation: int


# on_auth_failure(provider_id, lease) -> True when the caller should retry with a fresh lease
AuthHook = Callable[[str, Lease], Awaitable[bool]]


class KeyedClient:
    def __init__(self, provider_id: str, *, on_auth_failure: AuthHook | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.provider_id = provider_id
        self._keys = _Keys(None, None, 0, None)
        self._on_auth_failure = on_auth_failure
        self._clock = clock
        self.used: float | None = None

    # ---- reads (T0: one attribute read, no lock, no I/O) -------------------------------------------------------
    def lease(self) -> Lease:
        """The live key for one request. T0."""
        keys = self._keys
        if keys.live is None:
            raise KeyMissing(self.provider_id)
        return Lease(keys.live, keys.generation)

    @property
    def generation(self) -> int:
        return self._keys.generation

    @property
    def has_previous(self) -> bool:
        return self._keys.previous is not None

    @property
    def swapped_at(self) -> float | None:
        return self._keys.swapped_at

    # ---- changes (T0: build a new _Keys, one assignment) -------------------------------------------------------
    def load(self, live: str | None, previous: str | None = None, swapped_at: float | None = None) -> None:
        """Set the keys at startup from the store. T0."""
        self._keys = _Keys(live, previous, self._keys.generation + 1, swapped_at)

    def swap(self, new_live: str | None, *, keep_previous: bool = True) -> None:
        """Make ``new_live`` the live key; the old one becomes previous (or is dropped). Atomic. T0 (< 1 ms)."""
        old = self._keys
        self._keys = _Keys(new_live, old.live if keep_previous else None, old.generation + 1, self._clock())

    def fall_back(self) -> bool:
        """Go back to the previous key (the new one was refused). Atomic. T0."""
        old = self._keys
        if old.previous is None:
            return False
        self._keys = _Keys(old.previous, None, old.generation + 1, old.swapped_at)
        return True

    def drop_previous(self) -> None:
        old = self._keys
        self._keys = _Keys(old.live, None, old.generation, old.swapped_at)

    # ---- the request wrapper -----------------------------------------------------------------------------------
    async def call(self, fn: Callable[[str], Awaitable[T]]) -> T:
        """Run ``fn(key)``; on a 401/403 from a just-swapped key, fall back (via the hook) and retry once.

        Overhead T0 (a lease and a try); the request itself is whatever tier ``fn`` is.
        """
        lease = self.lease()
        try:
            result = await fn(lease.secret)
        except Exception as exc:
            if not is_auth_failure(exc) or self._on_auth_failure is None:
                raise
            if not await self._on_auth_failure(self.provider_id, lease):
                raise
            retry = self.lease()
            if retry.secret == lease.secret:
                raise
            result = await fn(retry.secret)
        self.used = self._clock()
        return result
