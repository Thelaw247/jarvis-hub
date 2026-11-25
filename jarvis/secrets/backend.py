"""Where the secrets themselves live: Windows Credential Manager (through keyring), or memory in tests.

One credential per provider and slot, named ``Jarvis/<provider>/<slot>`` (slots: live, next, previous, plus an
optional extra such as Google's refresh_token). Nothing else in the core ever holds a secret on disk.
"""
from __future__ import annotations

import sys
from typing import Protocol

SERVICE_PREFIX = "Jarvis"
USERNAME = "jarvis"
SLOTS = ("live", "next", "previous")

# Windows Credential Manager holds at most 2560 bytes per credential and keyring stores UTF-16 (2 bytes a char).
MAX_SECRET_CHARS = 1200


class StoreUnavailable(RuntimeError):
    """Credential Manager (or whatever backend) could not be read or written. Never carries secret text."""


def service_name(provider_id: str, slot: str) -> str:
    """The credential's name, e.g. ``Jarvis/anthropic/live``. T0."""
    return f"{SERVICE_PREFIX}/{provider_id}/{slot}"


class SecretBackend(Protocol):
    def get(self, service: str) -> str | None: ...
    def set(self, service: str, secret: str) -> None: ...
    def delete(self, service: str) -> None: ...


class MemoryBackend:
    """An in-memory backend for tests and the demo. Same interface as the keyring one."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}
        self.fail = False  # tests flip this to simulate Credential Manager being unavailable

    def _check(self) -> None:
        if self.fail:
            raise StoreUnavailable("backend unavailable")

    def get(self, service: str) -> str | None:
        self._check()
        return self.items.get(service)

    def set(self, service: str, secret: str) -> None:
        self._check()
        self.items[service] = secret

    def delete(self, service: str) -> None:
        self._check()
        self.items.pop(service, None)


class KeyringBackend:
    """keyring, pinned to the Windows Credential Manager backend on Windows (his account, C26).

    Calls take a few milliseconds and happen only on a change or at startup (T1), never per request.
    Errors are re-raised as ``StoreUnavailable`` with no cause attached (``from None``), so a backend's own
    message can never reach a log or a response.
    """

    def __init__(self, keyring_backend=None) -> None:
        try:
            import keyring  # noqa: PLC0415  (optional dependency, only needed on the real machine)
            import keyring.errors  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on the machine
            raise StoreUnavailable("keyring is not installed") from exc
        self._errors = keyring.errors
        if keyring_backend is None:
            if sys.platform == "win32":  # pragma: no cover - Windows only
                from keyring.backends.Windows import WinVaultKeyring  # noqa: PLC0415

                keyring_backend = WinVaultKeyring()
            else:
                keyring_backend = keyring.get_keyring()
        self._kr = keyring_backend

    def get(self, service: str) -> str | None:
        try:
            return self._kr.get_password(service, USERNAME)
        except Exception:  # noqa: BLE001
            raise StoreUnavailable("could not read the credential store") from None

    def set(self, service: str, secret: str) -> None:
        try:
            self._kr.set_password(service, USERNAME, secret)
        except Exception:  # noqa: BLE001
            raise StoreUnavailable("could not write the credential store") from None

    def delete(self, service: str) -> None:
        try:
            self._kr.delete_password(service, USERNAME)
        except self._errors.PasswordDeleteError:
            return  # already gone
        except Exception:  # noqa: BLE001
            raise StoreUnavailable("could not delete from the credential store") from None

