"""Pace, step 1: how long Jarvis waits at a pause before he takes it as the end of his turn (v0.27.0).

Why (Jarvis/JARVIS_RESEARCH_CONVERSATION_PACE.md): on 22 Nov he talked over Jarvis in 48 of 221 turns, and in 59 of
107 hand-offs his "next turn" began under a second after Jarvis decided he had finished. Until now a "finished"
verdict from the turn model ended the turn at once, whatever the words were.

This step is rules, not learning: the wait depends on how his words end. It also records what happened at every
pause (did he carry on?), which is the teacher for the learner in step 2. `scale` is where that learner and his
pace will plug in. T0.
"""
from __future__ import annotations

import re

# words a sentence doesn't end on: a pause after one of these is him thinking, not him done
HOLDERS = frozenset("""
and or but so because if then than that which who when where while until unless although though as since
the a an my your his her our their this these those some any
to of for with in on at by from into about over under between through
is are was were am be been being do does did have has had will would can could should may might must
um uh er erm hmm like well
also plus minus times equals
""".split())
# short things that are complete by themselves: an answer or a command must never wait
QUICK = frozenset("""yes yeah yep yup no nope nah okay ok sure please thanks stop cancel wait go done correct right
fine continue next back pause resume quiet mute louder""".split())

# Giving way: when he starts again while Jarvis has only just begun, Jarvis began too soon. Then half the usual
# talking is enough to stop him (still enough that a cough or his own echo doesn't).
YIELD_WINDOW_MS, YIELD_AFTER_MS = 1500.0, 500.0
CLEAR_MS, SHORT_MS, UNHEARD_MS, HOLDER_MS, UNFINISHED_EXTRA_MS, MOST_MS = 250.0, 600.0, 450.0, 1600.0, 1000.0, 2500.0


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def patience_ms(text: str, *, smart_done: bool, unfinished_ms: float = 1500.0, scale: float = 1.0) -> tuple[float, str]:
    """→ (how much more silence to wait for, why). `text` is what has been heard of this turn so far (it can lag).
    `smart_done`: the turn model's verdict. `unfinished_ms`: the wait an "unfinished" verdict already had."""
    words = words_of(text)
    holder = bool(words) and words[-1] in HOLDERS
    if not smart_done:
        wait, why = unfinished_ms + (UNFINISHED_EXTRA_MS if holder else 0.0), "unfinished"
    elif 0 < len(words) <= 3 and any(w in QUICK for w in words):
        return 0.0, "quick"                       # "yes", "stop", "no thanks": at once, as before
    elif not words:
        wait, why = UNHEARD_MS, "unheard"         # the words haven't arrived yet: don't answer a guess
    elif holder:
        wait, why = HOLDER_MS, "holder"           # "...and", "...because", "...the": he is mid-sentence
    elif len(words) <= 2:
        wait, why = SHORT_MS, "short"             # two words and a pause is usually the start of something
    else:
        wait, why = CLEAR_MS, "clear"
    return max(0.0, min(MOST_MS, wait * scale)), why
