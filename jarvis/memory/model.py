"""Plain data types of the memory interface (MEMORY §3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Trust(StrEnum):
    HIS = "his"          # he said or typed it
    JARVIS = "jarvis"    # Jarvis's own words or observations
    OUTSIDE = "outside"  # email, Canvas, invites, web, files from others


class Kind(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    COMMITMENT = "commitment"
    PROCEDURE = "procedure"
    POLICY = "policy"
    PATTERN = "pattern"
    OBSERVATION = "observation"
    CORRECTION = "correction"


class ClaimType(StrEnum):
    INTENT = "intent"  # his choices, preferences, decisions
    WORLD = "world"    # due dates, rooms, facts about reality


When = datetime | date | str | None


@dataclass(frozen=True)
class EpisodeIn:
    """One raw round (verbatim). Trust is worked out in code from channel + speaker."""

    content: str
    channel: str                 # voice, chat, debrief, hub, connector:canvas, calendar, gmail, skill:x, observer:x
    speaker: str = "user"        # user / jarvis / system
    session_id: str | None = None
    ts: When = None
    trust: Trust | str | None = None   # may only lower the computed trust
    privacy_tier: int | None = None
    retention: str = "keep"
    explicit: bool = False       # he said it again on purpose: lifts a tombstone


@dataclass(frozen=True)
class ClaimIn:
    """One candidate claim from the extractor (or a connector), tied to the episode it came from."""

    text: str
    kind: Kind | str = Kind.FACT
    claim_type: ClaimType | str = ClaimType.WORLD
    subject: str | None = None          # entity name; resolved by alias
    subject_type: str = "topic"
    predicate: str | None = None
    object: str | None = None           # entity name (or use value)
    object_type: str = "topic"
    value: str | None = None
    valid_from: When = None
    valid_to: When = None
    confidence: float = 0.8
    explicit: bool = True               # stated outright vs inferred
    scope: str | None = None
    domain_tags: tuple[str, ...] = ()
    branch: str | None = None           # a rule-level placement the caller knows (Canvas course id -> course)
    suggested_branch: str | None = None  # the extractor's guess (goes to Unsorted as a guess)
    importance: float = 0.5
    corrective_context: str | None = None
    pinned: bool = False                # honoured only for his word
    fact_keys: str | None = None
    privacy_tier: int | None = None


@dataclass
class ClaimOutcome:
    action: str                    # add · reaffirm · supersede · conflict · noop · blocked
    fact_id: int | None = None
    other_fact_id: int | None = None
    branch: str | None = None
    notes: tuple[str, ...] = ()


@dataclass
class AddResult:
    episode_id: int | None
    change_id: int | None
    outcomes: list[ClaimOutcome] = field(default_factory=list)
    blocked: bool = False


@dataclass
class ChangeResult:
    change_id: int
    ids: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hit:
    """One recalled fact, already collapsed to its winner and tagged with its source."""

    fact_id: int
    text: str
    tag: str
    score: float
    authority: int
    kind: str
    claim_type: str
    status: str
    branch: str | None
    valid_from: str | None
    valid_to: str | None
    privacy_tier: int
    conflict: Hit | None = None

    def line(self) -> str:
        """The line given to the model: text + source tag (MEMORY §5)."""
        out = f"{self.text} {self.tag}"
        if self.conflict is not None:
            out += f" (but {self.conflict.tag} says: {self.conflict.text})"
        return out


@dataclass
class UndoResult:
    change_id: int | None
    undone: list[int] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ForgetResult:
    change_id: int | None
    episodes: list[int] = field(default_factory=list)
    facts: list[int] = field(default_factory=list)
    entities: list[int] = field(default_factory=list)
    tombstones: int = 0
    scrubbed: bool = False
    preview: bool = False


@dataclass
class PlaceResult:
    branch: str
    assigned_by: str      # rule · entity · embedding · llm · him · unsorted
    confidence: float
    guess: str | None = None
    changed: bool = True


@dataclass
class NowContext:
    """What the now card needs from outside memory (calendar, homework, approvals, presence).

    Connectors fill this in later (P1); memory supplies flags, open loops and gaps itself.
    """

    events: list[dict[str, Any]] = field(default_factory=list)   # contract now_card.$defs.event, soonest first
    ready_to_offer: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    done_today: list[str] = field(default_factory=list)
    day: dict[str, int] | None = None
    moment: str | None = None
    active_branch: str | None = None
    waiting_for_yes: list[str] = field(default_factory=list)
    today: list[str] = field(default_factory=list)     # his whole day, one line each (prompt text only)
    due: list[str] = field(default_factory=list)       # due work from his homework list, soonest first (prompt text only)
    flag: dict[str, Any] | None = None                 # the closest deadline, shown when memory has no conflict to flag
    notes: list[str] = field(default_factory=list)     # how fresh the sources are, when that matters
    prefs: list[str] = field(default_factory=list)     # how he wants things done: his preferences, rules, corrections
    names: list[str] = field(default_factory=list)     # what building and course codes mean in plain words
