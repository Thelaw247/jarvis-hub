from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from jarvis.memory import ClaimIn, EpisodeIn

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
_SCHEMAS = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in CONTRACTS.glob("*.schema.json")}
_REGISTRY = Registry().with_resources((n, Resource.from_contents(d)) for n, d in _SCHEMAS.items())


def contract_errors(name: str, doc: object) -> list[str]:
    v = Draft202012Validator(_SCHEMAS[f"{name}.schema.json"], registry=_REGISTRY)
    return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(doc)]


def said(text: str, *claims: ClaimIn, channel: str = "chat", session: str | None = None, **kw) -> tuple:
    """He said it (chat)."""
    return EpisodeIn(text, channel, "user", session_id=session, **kw), list(claims)


def from_(channel: str, text: str, *claims: ClaimIn, speaker: str = "system", **kw) -> tuple:
    return EpisodeIn(text, channel, speaker, **kw), list(claims)


def row(store, sql: str, *args):
    """Read straight from the database (test only)."""
    return store._run_read(lambda c: c.execute(sql, args).fetchone(), (), {})


def rows(store, sql: str, *args):
    return store._run_read(lambda c: c.execute(sql, args).fetchall(), (), {})
