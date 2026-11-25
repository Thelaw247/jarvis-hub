"""T0 approval grammar: answers to "Book it?" / "Send it?" with no LLM (RUNTIME: approvals).

Counted only while an approval is open and within the answer window (~10 s) of the ask. The whole utterance
must be the answer ("yes", "book it"); anything longer ("yes but at 3") goes to the T1 talker as an edit.
Outward actions (an email or post to other people) only go on "send it" / "post it": a bare "yes" gets a
reminder instead, so a stray "yeah" never sends anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from jarvis.voice.ports import PendingApproval

Answer = Literal["yes", "no", "later", "edit", "say_send_it"]

_YES = frozenset({
    "yes", "yeah", "yep", "yup", "sure", "do it", "go ahead", "book it", "sounds good", "ok do it",
    "okay do it", "yes please", "yes do it", "please do", "go for it",
})
_OUTWARD_YES = frozenset({"send it", "post it", "yes send it", "yes post it", "send", "post it now", "send it now"})
_NO = frozenset({"no", "nope", "nah", "dont", "do not", "cancel", "cancel that", "no thanks", "skip it"})
_LATER = frozenset({"later", "not now", "ask me later", "maybe later", "remind me later"})
_EDIT = frozenset({"edit", "change it", "edit it", "let me change it", "change something"})


@dataclass(frozen=True)
class ApprovalAnswer:
    approval_id: str
    answer: Answer


def classify(text: str, pending: PendingApproval | None, now: float, window_s: float) -> ApprovalAnswer | None:
    """T0. Map a normalized utterance to an approval answer, or None if it isn't one. < 0.1 ms."""
    if pending is None or now - pending.asked_at > window_s:
        return None
    if text in _OUTWARD_YES:
        return ApprovalAnswer(pending.id, "yes")
    if text in _YES:
        return ApprovalAnswer(pending.id, "say_send_it" if pending.outward else "yes")
    if text in _NO:
        return ApprovalAnswer(pending.id, "no")
    if text in _LATER:
        return ApprovalAnswer(pending.id, "later")
    if text in _EDIT:
        return ApprovalAnswer(pending.id, "edit")
    return None
