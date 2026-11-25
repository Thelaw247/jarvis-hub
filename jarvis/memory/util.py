"""Small helpers: time stamps, hashes and name normalising."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, time

from .model import When

_ISO = "%Y-%m-%dT%H:%M:%S.%fZ"


def iso(value: When) -> str | None:
    """Any time-ish value -> fixed-format UTC string (sorts correctly as text). Naive = local time."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time())
    if value.tzinfo is None:
        value = value.astimezone()
    return value.astimezone(UTC).strftime(_ISO)


def parse(value: str | None) -> datetime | None:
    return None if value is None else datetime.strptime(value, _ISO).replace(tzinfo=UTC)


def norm(text: str) -> str:
    """Lowercase, single spaces, no punctuation: 'GE 122' -> 'ge 122'."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def text_hash(text: str) -> str:
    return hashlib.sha256(norm(text).encode()).hexdigest()


def key_hash(subject: str, predicate: str) -> str:
    return hashlib.sha256(f"{norm(subject)}|{norm(predicate)}".encode()).hexdigest()
