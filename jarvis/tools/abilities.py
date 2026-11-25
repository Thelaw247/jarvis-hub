"""The abilities branch: what Jarvis can do, filed in his own memory (TOOLS §4).

One leaf-level branch, Projects › Jarvis › Abilities, holds one fact per tool (and per skill, when skills are
listed), refreshed at start-up. Recall and branch cards then answer "can you read PDFs?" from memory like anything
else, and the Life Map shows it. Jarvis's own notes: observer channel, never his word.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from .base import ToolContext
from .registry import Registry

log = logging.getLogger("jarvis.tools")
BRANCH = "Abilities"
PARENT = "jarvis"


def ability_lines(registry: Registry, ctx: ToolContext, skills: Iterable[tuple[str, str]] = ()) -> list[tuple[str, str]]:
    """(key, sentence) per ability: the tool's one line plus how it behaves (free or asks, quick or a task)."""
    out = []
    for spec in registry.specs.values():
        status = registry.status(spec, ctx)
        how = {"read": "free to use", "ask": "proposes; runs after his yes"}.get(spec.tier, spec.tier)
        speed = {"instant": "instant", "fast": "about a second", "slow": "a few seconds",
                 "task": "a background task"}[spec.speed]
        state = "" if status == "connected" else f" (now: {status.replace('_', ' ')})"
        out.append((f"tool:{spec.id}", f"Jarvis can {spec.summary[0].lower()}{spec.summary[1:]} "
                                       f"[{spec.id}: {how}, {speed}]{state}"))
    for name, description in skills:
        out.append((f"skill:{name}", f"Jarvis has the skill {name}: {description}"))
    return out


async def sync_abilities(memory: Any, registry: Registry, ctx: ToolContext,
                         skills: Iterable[tuple[str, str]] = ()) -> int:
    from jarvis.memory.model import ClaimIn, EpisodeIn  # noqa: PLC0415

    try:
        await memory.create_branch(BRANCH, PARENT)
    except Exception:  # it exists already
        pass
    lines = ability_lines(registry, ctx, skills)
    claims = [ClaimIn(text=text, subject="Jarvis", predicate=key, value=text, branch="abilities",
                      confidence=1.0, importance=0.3) for key, text in lines]
    episode = EpisodeIn(content="Jarvis's abilities (from the tools folder).", channel="observer:tools",
                        speaker="jarvis")
    await memory.add_episode(episode, claims)
    log.info("abilities.synced", extra={"count": len(claims)})
    return len(claims)
