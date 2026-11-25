"""Jarvis's API keys, core side (JARVIS_CORE_BUILD_MAP §3, work package K1).

Write-only keys in Windows Credential Manager, a cheap check before any key goes live, two-slot rotation
with an atomic in-memory swap, a 15-minute fall-back to the previous key, and audit rows with no key material.

Wiring (K0): ``mgr = KeyManager(KeyringBackend(), default_registry(), MetaFile(default_meta_path(root)),
emit=bus.publish); mgr.load(); app.include_router(build_router(mgr, verifier)); start mgr.watchdog()``.
Other packages call ``mgr.client("anthropic").call(fn)``.
"""
from .api import build_router
from .backend import KeyringBackend, MemoryBackend, SecretBackend, StoreUnavailable, service_name
from .client import AuthFailed, KeyedClient, KeyMissing, Lease, is_auth_failure
from .guard import SESSION_HEADER, Session, ip_allowed
from .manager import KeyManager, KeysError
from .meta import MetaFile, default_meta_path
from .providers import CheckResult, Provider, Registry, ShapeError, default_providers, default_registry

__all__ = [
    "AuthFailed", "CheckResult", "KeyManager", "KeyMissing", "KeyedClient", "KeyringBackend", "KeysError", "Lease",
    "MemoryBackend", "MetaFile", "Provider", "Registry", "SESSION_HEADER", "SecretBackend", "Session", "ShapeError",
    "StoreUnavailable", "build_router", "default_meta_path", "default_providers", "default_registry", "ip_allowed",
    "is_auth_failure", "service_name",
]
