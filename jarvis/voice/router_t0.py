"""T0 router: rule-based, no LLM, runs on every STT partial. Target < 50 ms; it takes microseconds.

Handles the reflexes (FUNCTIONS T0): the time, timers, stop, mute/unmute, volume, "open X" (a stub until the
Life Tree resolver exists) and the approval grammar. Anything else returns ``None`` and goes to the T1 talker.

``safe_on_partial`` marks commands that may fire at the end of the turn on the last partial without waiting
for the STT final (saves 50-150 ms). Approval answers always wait for the final: a misheard partial must
never book or send anything.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from jarvis.voice import approvals_t0
from jarvis.voice.ports import ApprovalBox, Command

_PUNCT = re.compile(r"[^\w\s%]")
_SPACES = re.compile(r"\s+")
_LEAD = re.compile(r"^(?:(?:hey|ok|okay)\s+)?(?:jarvis\s+)?(?:(?:please|can you|could you|would you)\s+)?")
_TAIL = re.compile(r"\s+(?:please|jarvis|thanks|thank you)$")

_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "ninety": 90, "half": 0.5,
}
_UNIT_S = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600}

_TIME = re.compile(r"^(?:what time is it|whats the time|what is the time|time|the time|time check)(?: now)?$")
_STOP = re.compile(r"^(?:stop|stop talking|stop it|be quiet|quiet|shush|hush|enough|thats enough|never mind|nevermind"
                   r"|cancel|shut up)$")
_MUTE = re.compile(r"^(?:mute|mute yourself|stop listening|go quiet)$")
_UNMUTE = re.compile(r"^(?:unmute|start listening|you can listen)$")
_VOL_UP = re.compile(r"^(?:volume up|turn it up|louder|turn up the volume|turn the volume up|speak up)$")
_VOL_DOWN = re.compile(r"^(?:volume down|turn it down|quieter|softer|turn down the volume|turn the volume down)$")
_VOL_SET = re.compile(r"^(?:set (?:the )?)?volume (?:to )?(\d{1,3})(?: ?%| percent)?$")
_TIMER_CANCEL = re.compile(r"^(?:cancel|stop|clear) (?:the |my )?timer$")
_DUR = r"((?:\d+|[a-z]+)(?: and a half)?) (second|sec|minute|min|hour|hr)s?"
_TIMER_SET = [
    re.compile(rf"^(?:set )?(?:a |an )?timer (?:for )?{_DUR}$"),
    re.compile(rf"^(?:set )?(?:a |an )?{_DUR} timer$"),
    re.compile(rf"^(?:remind me in|wake me in) {_DUR}$"),
]
_OPEN = re.compile(r"^(?:open|pull up|bring up|show me|show|put up) (?:the |my )?(.+)$")
_NOT_A_THING = re.compile(r"\b(?:what|whats|how|why|when|who|where|which|if)\b")  # a question, not a thing


@dataclass(frozen=True)
class RouteResult:
    intent: str
    command: Command | None = None
    reply: str | None = None           # spoken line (None: the screen shows it); cached phrases play from disk
    safe_on_partial: bool = True


def normalize(text: str) -> str:
    """T0. Lowercase, drop punctuation and apostrophes, strip "hey jarvis"/"please"."""
    t = text.lower().replace("'", "").replace("’", "")
    t = _SPACES.sub(" ", _PUNCT.sub(" ", t)).strip()
    t = _LEAD.sub("", t, count=1)
    t = _TAIL.sub("", t)
    return t.strip()


def _number(word: str) -> float | None:
    if word.isdigit():
        return float(word)
    half = word.endswith(" and a half")
    if half:
        word = word[: -len(" and a half")]
    n = float(word) if word.isdigit() else _NUMBERS.get(word)
    if n is None:
        return None
    return n + 0.5 if half else n


def _say_duration(seconds: int) -> str:
    for unit, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds % size == 0 and seconds >= size:
            n = seconds // size
            return f"{n} {unit}{'' if n == 1 else 's'}"
    m, s = divmod(seconds, 60)
    return f"{m} minutes {s} seconds"


def say_time(now: datetime) -> str:
    hour = now.hour % 12 or 12
    return f"It's {hour}:{now.minute:02d}."


class RouterT0:
    """T0 router. ``route(text)`` is pure apart from reading the clock and the open approval."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] = datetime.now,
        clock: Callable[[], float] | None = None,
        approvals: ApprovalBox | None = None,
        approval_window_s: float = 10.0,
        resolve_open: Callable[[str], str | None] | None = None,
    ) -> None:
        import time

        self._now = now
        self._clock = clock or time.perf_counter
        self._approvals = approvals
        self._window = approval_window_s
        self._resolve_open = resolve_open

    def route(self, text: str) -> RouteResult | None:
        """T0, < 50 ms (measured ~10-30 us). Returns None for anything the talker should answer."""
        t = normalize(text)
        if not t:
            return None
        if self._approvals is not None:
            ans = approvals_t0.classify(t, self._approvals.pending(), self._clock(), self._window)
            if ans is not None:
                if ans.answer == "say_send_it":
                    return RouteResult("approval.hint", None, "Say send it to send it.", safe_on_partial=False)
                # "Don't confirm the obvious" (HUD v2 §9.3): the executor reports the result ("Booked.").
                reply = {"yes": None, "no": None, "later": None, "edit": "What should change?"}
                return RouteResult(
                    f"approval.{ans.answer}",
                    Command("approval.answer", {"id": ans.approval_id, "answer": ans.answer}),
                    reply[ans.answer],
                    safe_on_partial=False,
                )
        if _TIME.match(t):
            return RouteResult("time", None, say_time(self._now()))
        if _TIMER_CANCEL.match(t):
            return RouteResult("timer.cancel", Command("timer.cancel"), "Timer off.")
        for rx in _TIMER_SET:
            m = rx.match(t)
            if m:
                n = _number(m.group(1))
                if n is None or n <= 0:
                    return None
                seconds = int(n * _UNIT_S[m.group(2)])
                return RouteResult("timer.set", Command("timer.set", {"seconds": seconds}),
                                   f"{_say_duration(seconds).capitalize()}, starting now.")
        if _STOP.match(t):
            return RouteResult("stop", Command("stop"), None)
        if _MUTE.match(t):
            return RouteResult("mute", Command("mute"), None)       # the orb shows muted
        if _UNMUTE.match(t):
            return RouteResult("unmute", Command("unmute"), None)
        if _VOL_UP.match(t):
            return RouteResult("volume.up", Command("volume.step", {"delta": 10}), None)
        if _VOL_DOWN.match(t):
            return RouteResult("volume.down", Command("volume.step", {"delta": -10}), None)
        m = _VOL_SET.match(t)
        if m:
            level = max(0, min(100, int(m.group(1))))
            return RouteResult("volume.set", Command("volume.set", {"level": level}), None)
        m = _OPEN.match(t)
        if m and len(m.group(1).split()) <= 5 and not _NOT_A_THING.search(m.group(1)):
            query = m.group(1)
            # No resolver means nothing here can open it: leave it to the talker, who has work_on, show_page and
            # make_window. Until v0.24.0 this still answered "open" with a command nothing ran, so a clean
            # "pull up the physics assignment" got no reply and no window (seen twice on 22 Nov).
            target = self._resolve_open(query) if self._resolve_open else None
            if target is not None:
                return RouteResult("open", Command("open", {"query": query, "target": target}), None)
        return None
