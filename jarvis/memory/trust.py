"""Trust, authority and the outside-content rules (MEMORY §4 step 4, §5; constraint C41).

Everything here is plain code on purpose: authority comes from *where* a claim came from, never from what
its text says, and the language model is never asked to decide it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import ClaimType, Kind, Trust

# Channels where De Wet himself speaks or types. Only these can carry trust "his".
HIS_CHANNELS = frozenset({"voice", "chat", "debrief", "hub"})
# Outside systems whose word is official for world facts (authority 4).
OFFICIAL_SOURCES = frozenset({"canvas", "paws", "syllabus", "crowdmark"})
# Kinds that speak for him. Outside content and Jarvis can never create these (C41).
HIS_ONLY_KINDS = frozenset({Kind.DECISION, Kind.PREFERENCE, Kind.COMMITMENT, Kind.PROCEDURE, Kind.CORRECTION})

_TRUST_RANK = {Trust.OUTSIDE: 0, Trust.JARVIS: 1, Trust.HIS: 2}


class TrustError(ValueError):
    """A caller tried to give content more trust than its channel allows."""


def source_of(channel: str) -> str:
    """'connector:canvas' -> 'canvas'; 'skill:homework.json' -> 'homework.json'; 'gmail' -> 'gmail'."""
    return channel.split(":", 1)[1] if ":" in channel else channel


def trust_for(channel: str, speaker: str, requested: Trust | str | None = None) -> Trust:
    """Work out an episode's trust from its channel and speaker. Tier: T2 (write path).

    A caller may *lower* trust (a paste of someone else's text in chat is outside) but never raise it.
    Unknown channels are outside (fail safe).
    """
    if speaker == "jarvis" or channel.startswith("observer:"):
        computed = Trust.JARVIS
    elif speaker == "user" and channel in HIS_CHANNELS:
        computed = Trust.HIS
    else:
        computed = Trust.OUTSIDE
    if requested is None:
        return computed
    req = Trust(requested)
    if _TRUST_RANK[req] > _TRUST_RANK[computed]:
        raise TrustError(f"channel {channel!r} cannot carry trust {req.value!r}")
    return req


def authority_for(trust: Trust, channel: str) -> int:
    """Authority 1-5 from trust (MEMORY §3, §4 step 4). Tier: T2.

    1 his word now · 2 his earlier word (set on supersede) · 3 observed behaviour · 4 official source ·
    5 Jarvis inference or any other outside source.
    """
    if trust is Trust.HIS:
        return 1
    if channel.startswith("observer:"):
        return 3
    if trust is Trust.OUTSIDE and source_of(channel) in OFFICIAL_SOURCES:
        return 4
    return 5


@dataclass(frozen=True)
class Guarded:
    """A claim after the C41 rules: what it may be stored as, and what was changed."""

    kind: Kind
    authority: int
    confirm_state: str
    pinned: bool
    notes: tuple[str, ...]


def guard_claim(trust: Trust, channel: str, kind: Kind, claim_type: ClaimType, *, explicit: bool,
                pinned: bool) -> Guarded:
    """Apply the outside-content rules in code (C41). Tier: T2.

    Outside content and Jarvis's own words can never create authority 1-2, a decision, preference,
    commitment, procedure, correction or pin: such claims are stored as observations ("from an email").
    """
    notes: list[str] = []
    authority = authority_for(trust, channel)
    if trust is Trust.HIS:
        state = "stated" if explicit else "proposed"
        if not explicit:  # an inference about him, even from his own episode, is not his word
            authority = 5
            if pinned:
                notes.append("pin dropped: inferred")
                pinned = False
        return Guarded(kind, authority, state, pinned, tuple(notes))
    if kind in HIS_ONLY_KINDS:
        notes.append(f"kind {kind.value} -> observation: not his word")
        kind = Kind.OBSERVATION
    if pinned:
        notes.append("pin dropped: not his word")
        pinned = False
    state = "observed" if authority in (3, 4) else "proposed"
    return Guarded(kind, max(authority, 3), state, False, tuple(notes))


# ---- privacy tiers (MEMORY §4 step 1, §9): simple rules; health, money -> tier 2 ----
_TIER2 = re.compile(
    r"\b(doctor|clinic|hospital|sick|illness|diagnos\w*|medication|prescription|therapy|therapist|"
    r"mental health|anxiety|depression|symptom\w*|injur\w*|bank account|banking|debt|overdraft|salary|"
    r"income|credit card|password|pin code|sin number|rent payment|student loan)\b",
    re.IGNORECASE,
)


def privacy_tier_for(text: str, default: int = 1) -> int:
    """Tier 2 when the text touches health or money; otherwise the default. Tier: T2."""
    return 2 if _TIER2.search(text) else default
