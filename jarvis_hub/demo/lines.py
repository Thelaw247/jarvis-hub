"""What Jarvis says, when he says it, and how much (HUD v2 §9). The demo uses it for its captions; jarvis-core can
lift this file as it is: plain Python, no hub imports, the clock and the randomness passed in.

Three layers (§9.4), so the words never form a pattern he can predict but what Jarvis *does* never changes:
1. **Never varies:** the safety line (`leave_now`), the register, the grammar of answers.
2. **Varies by context** (deterministic, so "Why?" can explain it): whether he speaks at all, how much, and what
   the line leads with: what changed first, then time away from the thread, then his own last words.
3. **Varies by rotation** (surface only): every line type has 5–8 wordings plus silence; the picker never reuses
   one of the last 5 wordings of that type, and never repeats a greeting on the same day.

Everything here is our own wording; nothing is quoted from the films.
"""
from __future__ import annotations

import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# --- the pools -------------------------------------------------------------------------------------------------
# Each line type has groups by what the line leads with: "changed", "away" (continuity across days, never a remark
# on the time away), "words" (his own last words) and "plain". Slots: {changed} {words} {thread} {label} {item}
# {due} {estimate} {beside} {target} {greet} {name} {facts} {progress} {tomorrow} {count} {nearest} {when}
# {done} {total} {source} {ago} {span} {what} {event} {thing}. A slot at the start of a sentence is capitalised.
POOLS: dict[str, dict[str, tuple[str, ...]]] = {
    # jobs over ~1 s get an instant short acknowledgement; under ~0.7 s, nothing but the result
    "acknowledge": {"plain": (
        "Checking {target}.",
        "Looking at {target}.",
        "Reading {target} now.",
        "Pulling up {target}.",
        "Going through {target}.",
        "One moment.",
        "A moment, please.",
    )},
    "offer_resume": {
        "plain": (
            "{Label} is where you stopped. Shall I take you there?",
            "You stopped at {label}. Would you like it open there?",
            "{Thread} is ready at {label}.",
            "{Label} is next in {thread}. Do you want to pick it up there?",
            "{Thread} opens at {label}, where you left it.",
            "{Label} is waiting in {thread}.",
            "{Thread} is set at {label}. Say the word and it's up.",
        ),
        "away": (
            "{Label}'s where we left it.",
            "We left {thread} at {label}. It's ready when you are.",
            "{Thread} picks up at {label}.",
            "{Thread} is set at {label}, as we left it.",
            "{Label} in {thread} is where we stopped. Would you like it?",
            "{Thread} is where we left it, at {label}. Shall I open it?",
        ),
        "changed": (
            "{Changed}. {Label} is where you stopped.",
            "{Changed}. {Thread} is ready at {label}.",
            "{Changed}, and {label} is still next.",
            "{Changed}. You were on {label}; it's ready.",
            "{Changed}. {Thread} is open at {label} whenever you are.",
        ),
        "words": (
            "You said {words}. {Thread} is ready at {label}.",
            "As you said, {words}. {Label} is ready.",
            "You wanted {words}. It's open at {label}.",
            "{Thread} is at {label}; you said {words}.",
            "You planned {words}. {Label} is up when you are.",
        ),
    },
    "offer_new_work": {"plain": (
        "{Item} is out, {due}. {Estimate}. Shall I open it with {beside} beside it?",
        "{Item} just arrived, {due}. {Estimate}.",
        "There's a new one: {item}, {due}. {Estimate}.",
        "{Item} came in, {due}. {Estimate}. It can open with {beside} beside it.",
        "{Item} is on Canvas now, {due}. {Estimate}.",
        "{Item} is out and {due}. {Estimate}. Would you like it set up with {beside}?",
        "One new item: {item}, {due}. {Estimate}.",
    )},
    # walking in: at most a short greeting attached to the one thing that changed; never a standalone ritual
    "arrival": {
        "changed": (
            "{Greet}. {Changed}.",
            "{Greet}. {Changed}. Nothing else is new.",
            "{Changed}. Everything else is as you left it.",
            "{Greet}. One thing changed: {changed}.",
            "{Changed}. That's the only change.",
            "{Greet}, {name}. {Changed}.",
            "{Changed}. Nothing else needs you.",
        ),
        "words": (
            "{Greet}. You said {words}; it's ready.",
            "{Greet}. It's set up for {words}, as you said.",
            "You said {words}. It's ready.",
            "{Greet}. Ready for {words}.",
            "Ready for {words}, as you said.",
        ),
        "plain": (
            "{Greet}.",
            "{Greet}, {name}.",
            "{Greet}. Nothing new since you left.",
            "{Greet}. All as you left it.",
            "{Greet}. Nothing's changed.",
        ),
    },
    # first wake of the day: up to three facts, numbers first
    "morning": {
        "changed": (
            "{Changed}. {facts}",
            "Morning. {Changed}. {facts}",
            "Good morning. {Changed}. {facts}",
            "Morning, {name}. {Changed}. {facts}",
            "One change overnight: {changed}. {facts}",
        ),
        "plain": (
            "Morning. {facts}",
            "Good morning. {facts}",
            "Morning, {name}. {facts}",
            "{facts}",
            "Good morning, {name}. {facts}",
            "Morning. Here's today. {facts}",
        ),
    },
    # wind-down: spoken only when a whole item finished or tomorrow changed; otherwise shown
    # {tomorrow} is the first thing on his next day ("GE 122 at 10 am"), {day} the word for that day ("tomorrow",
    # "Monday" after a Friday or on a weekend); "Good night" only late at night (see TIME_WORDS)
    "wind_down": {"plain": (
        "{Progress}. {Day} starts with {tomorrow}.",
        "{Progress}. {Tomorrow} first thing {day}.",
        "Saved where you stopped: {progress}. {Tomorrow} {day}.",
        "That's {progress}. First up {day}: {tomorrow}.",
        "{Progress}. All saved. {Tomorrow} is first {day}.",
        "Good night. {Progress}. {Tomorrow} {day}.",
    )},
    # "status" / "how are we doing?": three items in a fixed order, time-critical → progress → systems
    "status": {"plain": (
        "{Count} due this week, the nearest {when}.",
        "{Count} due this week; {nearest} comes first, {when}.",
        "{Nearest} is due {when}, the first of {count} this week.",
        "{Count} things due this week. {Nearest} is first, {when}.",
        "First due is {nearest}, {when}. {Count} in all this week.",
        "This week: {count} due, starting with {nearest} {when}.",
    )},
    "status_none": {"plain": (
        "Nothing due this week.",
        "Nothing is due this week.",
        "The week is clear of deadlines.",
        "No deadlines this week.",
        "Nothing on the due list this week.",
    )},
    "status_progress": {"plain": (
        "You're {done} questions into {thread}.",
        "{Thread} is at {label}, {done} of {total} done.",
        "{Thread}: {done} of {total} done, {label} next.",
        "{Done} of {total} done on {thread}.",
        "{Thread} stands at {label}.",
        "{Label} is next on {thread}; {done} are done.",
    )},
    "status_systems": {"plain": (
        "{Source} synced {ago}.",
        "Last {source} sync was {ago}.",
        "Systems are fine. {Source} synced {ago}.",
        "{Source} last synced {ago}; nothing is waiting on it.",
        "Everything is current. {Source} checked in {ago}.",
        "All sources are up to date; {source} synced {ago}.",
    )},
    # safety line: the same words every time, on purpose (§9.4 layer 1)
    "leave_now": {"plain": ("Leave now for {event}.",)},
    # fires at the nearest breakpoint inside a 2.5–3.5 h window, once an evening
    "break": {"plain": (
        "That's {span} straight. Your call; a ten-minute break is on offer.",
        "{Span} in. A ten-minute break would fit here.",
        "A break would fit here, if you want one. {Thread} will keep.",
        "Good point for ten minutes away. {Thread} stays where it is.",
        "{Thread} is at a natural stop. A short break is on offer.",
        "Ten minutes off would fit now. Everything stays as it is.",
    )},
    # "stop offering that": one receipt, with the undo in "Jarvis learned"
    "decline_receipt": {"plain": (
        "Understood. No more {what} offers. The undo is in Jarvis learned.",
        "I'll stop offering {what}. You can undo that in Jarvis learned.",
        "{What} offers are off. The undo is in Jarvis learned.",
        "Noted: no {what} offers from now on. Undo is in Jarvis learned.",
        "Understood. {What} offers are off until you turn them back on in Jarvis learned.",
    )},
    # a bigger slip gets one line, once; small ones are fixed silently
    "mistake": {"plain": (
        "{What}. Fixed, and here's the undo.",
        "{What}. It's corrected; the undo is in Activity.",
        "{What}. That's put right, with an undo in Activity.",
        "{What}. Corrected now. The undo is in Activity if you need it.",
        "{What}. I've fixed it and kept an undo.",
        "{What}. It's fixed. Activity has the undo.",
    )},
    # he overrode a warning: warned once, now help with what he chose; never "I told you so"
    "carry_on": {"plain": (
        "Understood. Carrying on.",
        "Very well. Carrying on.",
        "Understood.",
        "As you like. Carrying on.",
        "Noted. Carrying on.",
    )},
    # a protocol he named: echoed back as a question; a write inside it is named in the read-back
    "protocol": {"plain": (
        "{Name} protocol?",
    )},
    # a dry aside: understatement about the situation, or polite literal agreement. Budgeted (see Humour).
    "aside": {"plain": (
        "{Thing} describes itself as short. It's open.",
        "{Thing} is, by its own account, a quick one. It's open.",
        "{Thing} promised to be brief. It's open regardless.",
        "Quite.",
        "So it would seem.",
        "{Thing} calls this optional. It's here anyway.",
    )},
}
SILENT = None  # every type's extra variant: say nothing
SAFETY = frozenset({"leave_now"})  # fixed wording, exempt from rotation, moments and the repeat rate
GREETING_TYPES = frozenset({"arrival", "morning", "wind_down"})
# Acknowledgements carry no news, so the same one is never heard twice in a week; when every wording has been
# used, the orb's Thinking state is the acknowledgement (silence). This is what keeps the repeat rate low.
NO_REPEAT = frozenset({"acknowledge", "carry_on"})
NO_REPEAT_FOR = timedelta(days=7)
OFFER_TYPES = frozenset({"offer_resume", "offer_new_work"})
LEADS = ("changed", "away", "words")  # context first, in this order; then "plain"

# How much Jarvis may say in each moment (§9.3). Critical items are exempt.
MAX_SENTENCES = {"rushed": 1, "between": 1, "settled": 2, "heads_down": 0, "others": 0, "game": 0}
NO_OFFERS = frozenset({"rushed", "heads_down", "others", "game"})

# Register (§9.2): what a line must never contain.
SYSTEM_SPEAK = ("task resumed", "bookmark saved", "processing", "your request", "sure!", "got it", "welcome back",
                "missed you", "streak", "no problem", "great job", "awesome", "as an ai", "error occurred")
FILLER = ("basically", "actually,", "just so you know", "um", "uh,", "okay so", "so,", "well,", "like,")
DECLINE_MENTIONS = re.compile(r"not now|declin|ignor|said no|turned (?:it|that) down|earlier|again|last time you")
SHALL = re.compile(r"\bShall I\b")
GREETINGS = re.compile(r"^(?:Good )?(?:[Mm]orning|[Aa]fternoon|[Ee]vening|[Nn]ight)\b")
GREETING_ONLY = re.compile(r"^(?:Good )?(?:Morning|Afternoon|Evening|night)(?:, [^.?]+)?\.$")  # "Evening." "Morning, De Wet."
ANSWER_TYPES = frozenset({"morning", "wind_down", "status", "status_none", "status_progress", "status_systems"})
# Time-of-day words written into a wording (not ones that come in with a slot, like "tonight at 8 pm" for a deadline)
# must fit the clock: no "Good night." at 3:41 pm, no "tonight" before 6 pm, no "Morning." after noon.
TIME_WORDS = (
    (re.compile(r"\bGood night\b|^Night\b"), lambda h: h >= 20 or h < 4),
    (re.compile(r"\b[Tt]onight\b"), lambda h: h >= 18 or h < 4),
    (re.compile(r"^(?:Good )?[Mm]orning\b"), lambda h: 4 <= h < 12),
    (re.compile(r"^(?:Good )?[Aa]fternoon\b"), lambda h: 12 <= h < 18),
    (re.compile(r"^(?:Good )?[Ee]vening\b"), lambda h: h >= 17 or h < 4),
)


def fits_time(template: str, now: datetime) -> bool:
    """Does this wording's own time-of-day word fit `now`?"""
    return all(ok(now.hour) for word, ok in TIME_WORDS if word.search(template))


# --- small helpers ---------------------------------------------------------------------------------------------
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def number(n: int) -> str:
    """Counts the way he'd say them: 'two', 'eleven', '14'."""
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def clock(when: datetime) -> str:
    """'8 pm', '9:30 am', 'noon', 'midnight'."""
    if (when.hour, when.minute) == (12, 0):
        return "noon"
    if (when.hour, when.minute) == (0, 0):
        return "midnight"
    hour = when.hour % 12 or 12
    return f"{hour}{f':{when.minute:02d}' if when.minute else ''} {'am' if when.hour < 12 else 'pm'}"


def say_when(when: datetime, now: datetime) -> str:
    """A time relative to now, the way a person says it: 'at 4 pm', 'tonight at 8 pm', 'tomorrow at 9:30 am',
    'Wednesday at 8 pm', 'Nov 25'. Built from real (or re-based) times, never hard-coded."""
    days = (when.date() - now.date()).days
    if days == 0:
        return f"tonight at {clock(when)}" if when.hour >= 18 else f"at {clock(when)}"
    if days == 1:
        return f"tomorrow at {clock(when)}"
    if days == -1:
        return f"yesterday at {clock(when)}"
    if 1 < days < 7:
        return f"{when:%A} at {clock(when)}"
    return f"{when:%b} {when.day}"


def greeting_word(now: datetime) -> str:
    return "Morning" if 4 <= now.hour < 12 else "Afternoon" if 12 <= now.hour < 17 else "Evening"  # 1 am is still evening


def ago(then: datetime, now: datetime) -> str:
    minutes = max(0, round((now - then).total_seconds() / 60))
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{number(minutes)} minute{'s' if minutes != 1 else ''} ago"
    hours = round(minutes / 60)
    return f"{number(hours)} hour{'s' if hours != 1 else ''} ago" if hours < 24 else f"{then:%A}"


def sentences(text: str) -> list[str]:
    """Split a line into sentences (a '?' or '.' followed by a space and a capital ends one)."""
    return [s for s in re.split(r"(?<=[.?])\s+(?=[A-Z0-9“\"'])", text.strip()) if s]


def trim(text: str, cap: int) -> str:
    """Keep the first `cap` sentences; a bare greeting ("Evening.") doesn't count as one."""
    parts = sentences(text)
    head = parts[:1] if parts and GREETING_ONLY.match(parts[0]) else []
    return " ".join(head + parts[len(head):len(head) + cap])


def _slots(template: str) -> set[str]:
    return {name.lower() for name in re.findall(r"\{(\w+)\}", template)}


def _cap(value: str) -> str:
    return value[:1].upper() + value[1:]


def fill(template: str, values: dict[str, str]) -> str:
    """Fill a template. `{Slot}` (capital first letter) capitalises the value; `{slot}` keeps it as given, so course
    codes and names are never lower-cased."""
    def one(match: re.Match) -> str:
        key = match.group(1)
        value = str(values[key.lower()])
        return _cap(value) if key[0].isupper() else value
    return re.sub(r"\{(\w+)\}", one, template)


def register_problems(text: str, *, address: str = "name", name: str = "De Wet") -> list[str]:
    """Check one line against the register (§9.2). Returns what's wrong; empty means it's fine."""
    found = []
    low = text.lower()
    if "!" in text:
        found.append("exclamation mark")
    found += [f"system-speak: {p}" for p in SYSTEM_SPEAK if p in low]
    found += [f"filler: {p}" for p in FILLER if re.search(rf"(?:^|\s){re.escape(p)}(?:\s|$)", low)]
    if re.search(r"\bsir\b", low) and address != "sir":
        found.append("'sir' without the setting")
    if low.count(name.lower()) + len(re.findall(r"\bsir\b", low)) > 1:
        found.append("address term more than once")
    if text and text[-1] not in ".?":
        found.append("not a complete sentence")
    if DECLINE_MENTIONS.search(low):
        found.append("mentions a past decline")
    return found


# --- what he says ----------------------------------------------------------------------------------------------
@dataclass
class Context:
    """What Jarvis knows at the moment of speaking. Only `now` is required."""
    now: datetime
    moment: str = "settled"            # now_card.moment
    changed: str | None = None         # what changed, as a sentence without its full stop ("Canvas posted hints for PPS 7")
    away: timedelta | None = None      # time away from this thread (only picks the continuity wording; never said)
    words: str | None = None           # his own last words about it, paraphrased ("you'd finish it after dinner")
    values: dict[str, str] = field(default_factory=dict)  # the other slots
    asked: bool = False                # he asked for this (an answer or a readout he requested)
    by_voice: bool = False             # ... and asked by voice
    tapped: bool = False               # he tapped (a tap never makes Jarvis speak)
    critical: bool = False             # time-critical: exempt from moments
    alone: bool = True
    quiet_hours: bool = False


@dataclass
class Line:
    kind: str
    text: str | None                   # None: silence (nothing shown either)
    spoken: bool                       # False: shown only (caption, card or receipt), not said aloud
    lead: str = "plain"
    why: str = ""                      # for "Why?": what decided the shape of this line
    template: str | None = None
    focus: tuple[str | None, ...] = ()  # per part: what lights up on the HUD as it's said (§9.1)
    parts: tuple[str, ...] = ()         # a readout's items, in the order they're said (text is them joined)


class Humour:
    """The aside budget (§9.2): at most one per session and about two a day, never the same target twice in a week;
    never in alerts, approvals, errors or readouts; never when he's rushed, behind, heads-down, gaming or not alone."""

    PER_SESSION, PER_DAY, SAME_TARGET = 1, 2, timedelta(days=7)
    NEVER_IN = frozenset({"alert", "approval", "error", "readout", "critical", "leave_now", "mistake"})

    def __init__(self) -> None:
        self.log: list[tuple[datetime, int, str]] = []  # (when, session, target)

    def allowed(self, now: datetime, session: int, *, where: str, moment: str, target: str,
                alone: bool = True, behind: bool = False) -> bool:
        if where in self.NEVER_IN or moment in ("rushed", "heads_down", "others", "game") or not alone or behind:
            return False
        if sum(1 for _, s, _ in self.log if s == session) >= self.PER_SESSION:
            return False
        if sum(1 for at, _, _ in self.log if at.date() == now.date()) >= self.PER_DAY:
            return False
        return not any(t == target and now - at < self.SAME_TARGET for at, _, t in self.log)

    def record(self, now: datetime, session: int, target: str) -> None:
        self.log.append((now, session, target))


class Declines:
    """How a decline changes what Jarvis does next (§9.5). Nothing here ever produces a line that mentions a past
    decline, and declines never show as misses.

    - acted:    he answered by doing something else. That's the answer; the resume point follows him, silently.
    - ignored:  the card shrinks into its Rail slot and isn't spoken again this session; two ignores in a row for the
                same kind of offer in the same context make it card-only until he next accepts one by voice.
    - not_now:  a soft tick at most; it stays on the Rail, unspoken until something changes (he leaves and comes back,
                a new day, or its state changes).
    - no:       do what he said.
    - stop:     off for that kind of offer, with one receipt and an undo.
    Raised thresholds drift back to normal over about two weeks.
    """

    RAISE, CAP, DRIFT = 0.15, 0.6, timedelta(days=14)

    def __init__(self) -> None:
        self.streak: dict[tuple[str, str], int] = defaultdict(int)
        self.card_only: set[tuple[str, str]] = set()
        self.quiet: set[tuple[str, str]] = set()          # (kind, ref) not spoken again this session
        self.held: dict[tuple[str, str], str] = {}        # (kind, ref) -> the context it was put off in
        self.off: set[str] = set()
        self.raised: dict[str, tuple[float, datetime]] = {}

    def new_session(self) -> None:
        self.quiet.clear()

    def threshold(self, kind: str, now: datetime, base: float = 0.5) -> float:
        """How sure Jarvis must be before offering this kind of thing. Raised by ignores and "not now"; drifts back."""
        amount, since = self.raised.get(kind, (0.0, now))
        left = max(0.0, 1 - (now - since) / self.DRIFT)
        return base + amount * left

    def _raise(self, kind: str, now: datetime) -> None:
        self.raised[kind] = (min(self.CAP, self.threshold(kind, now, 0.0) + self.RAISE), now)

    def record(self, kind: str, outcome: str, *, now: datetime, context: str = "", ref: str = "",
               fingerprint: str = "", by_voice: bool = False) -> str | None:
        """Note his answer. Returns "tick" for "not now" (an earcon at most), "receipt" for "stop offering that"."""
        key = (kind, context)
        if outcome == "acted":
            self.streak[key] = 0
        elif outcome == "ignored":
            self.quiet.add((kind, ref))
            self.streak[key] += 1
            if self.streak[key] >= 2:
                self.card_only.add(key)
            self._raise(kind, now)
        elif outcome == "not_now":
            self.held[(kind, ref)] = fingerprint
            self._raise(kind, now)
            return "tick"
        elif outcome == "stop":
            self.off.add(kind)
            return "receipt"
        elif outcome == "accepted":
            self.streak[key] = 0
            self.held.pop((kind, ref), None)
            if by_voice:
                self.card_only.discard(key)
        return None

    def undo_stop(self, kind: str) -> None:
        self.off.discard(kind)

    def gate(self, kind: str, *, context: str = "", ref: str = "", fingerprint: str = "") -> tuple[str, str]:
        """("off" | "card" | "speak", why). "card" means show it, don't say it."""
        if kind in self.off:
            return "off", "he turned this kind of offer off"
        if (kind, ref) in self.held:
            if self.held[(kind, ref)] == fingerprint:
                return "card", "put off until something changes"
            del self.held[(kind, ref)]
            return "speak", "something changed since he put it off"
        if (kind, ref) in self.quiet:
            return "card", "not spoken again this session"
        if (kind, context) in self.card_only:
            return "card", "card-only until he accepts one by voice"
        return "speak", ""


class Voice:
    """Picks Jarvis's lines. One per hub (or per jarvis-core); keeps the rotation, greeting, "Shall I", address,
    humour and decline state. `rng` and the times passed in make it deterministic for tests and "Why?"."""

    def __init__(self, *, name: str = "De Wet", address: str = "name", rng: random.Random | None = None) -> None:
        self.name, self.address = name, address  # address: "name" (default), "sir" (opt-in setting) or "none"
        self.rng = rng or random.Random(0)
        self.recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))   # last 5 wordings per type
        self.used_at: dict[tuple[str, str], int] = {}                            # (type, template) -> pick number
        self.greeted: dict[date, set[str]] = defaultdict(set)                    # greetings used per day
        self.heard: dict[str, datetime] = {}                                      # acknowledgement text -> last said
        self.offers: deque = deque(maxlen=4)                                     # did each recent offer use "Shall I"
        self.log: list[tuple[datetime, str, str]] = []                          # spoken lines: (when, type, text)
        self.humour = Humour()
        self.declines = Declines()
        self.session = 0
        self._addressed = False
        self._picks = 0

    # -- sessions and exchanges --
    def new_session(self) -> None:
        self.session += 1
        self.declines.new_session()

    def new_exchange(self) -> None:
        """An exchange is one back-and-forth; the address term is used at most once in it."""
        self._addressed = False

    # -- the rules --
    @staticmethod
    def max_sentences(ctx: Context, kind: str = "") -> int | None:
        """None means no cap (an answer he asked for, in a moment that allows speech). Morning facts and the
        wind-down are answers to something he did (woke Jarvis, said he's done), so they count as asked."""
        if ctx.critical:
            return None
        cap = MAX_SENTENCES.get(ctx.moment, 2)
        if ctx.asked and ctx.by_voice and ctx.moment == "heads_down":
            return None  # he spoke to Jarvis, so he's not heads-down any more (others present and games stay silent)
        if (ctx.asked or kind in ANSWER_TYPES) and cap:
            return 1 if ctx.moment == "rushed" else None
        return cap

    @staticmethod
    def offer_spoken(ctx: Context) -> tuple[bool, str]:
        """When an offer is spoken (§9.4): he asked by voice, he's been away from the thread a day or more, or
        something about it changed. Otherwise it's a card. A tap never triggers speech."""
        if ctx.tapped:
            return False, "a tap never makes Jarvis speak"
        if ctx.by_voice:
            return True, "he asked by voice"
        if ctx.away is not None and ctx.away >= timedelta(days=1):
            return True, "away from it a day or more"
        if ctx.changed:
            return True, "something about it changed"
        return False, "nothing new to say: a card is enough"

    def _lead(self, kind: str, ctx: Context) -> str:
        groups = POOLS[kind]
        if ctx.changed and "changed" in groups:
            return "changed"
        if ctx.away is not None and ctx.away >= timedelta(days=1) and "away" in groups:
            return "away"
        if ctx.words and "words" in groups:
            return "words"
        return "plain" if "plain" in groups else next(iter(groups))

    def _values(self, ctx: Context) -> dict[str, str]:
        values = {"greet": greeting_word(ctx.now), "name": self._address_term() or "", "day": "tomorrow", **ctx.values}
        if ctx.changed:
            values["changed"] = ctx.changed
        if ctx.words:
            values["words"] = ctx.words
        return values

    def _address_term(self) -> str | None:
        return {"name": self.name, "sir": "sir"}.get(self.address)

    def _candidates(self, kind: str, lead: str, ctx: Context, values: dict[str, str]) -> list[str]:
        today = self.greeted[ctx.now.date()]
        out = []
        for template in POOLS[kind][lead]:
            needs = _slots(template)
            if not needs <= set(values):
                continue
            if not fits_time(template, ctx.now):
                continue
            if "name" in needs and (self._addressed or not self._address_term()):
                continue
            if kind in OFFER_TYPES and SHALL.search(template) and any(self.offers):
                continue  # "Shall I" in at most 1 offer in 5
            if kind in NO_REPEAT and ctx.now - self.heard.get(fill(template, values), datetime.min) < NO_REPEAT_FOR:
                continue
            greeting = GREETINGS.match(fill(template, values)) if kind in GREETING_TYPES else None
            if greeting and greeting.group(0).lower() in today:
                continue  # no greeting repeated the same day
            out.append(template)
        return out

    def _choose(self, kind: str, candidates: list[str]) -> str:
        fresh = [t for t in candidates if t not in self.recent[kind]]
        if fresh:
            return self.rng.choice(fresh)
        return min(candidates, key=lambda t: self.used_at.get((kind, t), -1))  # all recent: the longest unused

    def say(self, kind: str, ctx: Context) -> Line:
        """The line for this moment, or silence. Never decides *what Jarvis does*, only what he says about it."""
        if kind in SAFETY:  # the same words every time, said even when others are here or he's heads-down
            text = fill(POOLS[kind]["plain"][0], ctx.values)
            return Line(kind, text, True, "plain", "safety line: fixed wording", POOLS[kind]["plain"][0])
        values = self._values(ctx)
        lead = self._lead(kind, ctx)
        candidates = self._candidates(kind, lead, ctx, values)
        if not candidates and lead != "plain" and "plain" in POOLS[kind]:
            lead, candidates = "plain", self._candidates(kind, "plain", ctx, values)
        if not candidates:  # for an acknowledgement, the orb's Thinking state is the acknowledgement
            return Line(kind, SILENT, False, lead, "nothing left to say that wouldn't repeat today")
        template = self._choose(kind, candidates)
        text = fill(template, values)
        spoken, why = True, {"changed": "led with what changed", "away": "picked up where you left it",
                             "words": "followed your own words", "plain": ""}[lead]
        if kind in OFFER_TYPES:
            spoken, reason = self.offer_spoken(ctx)
            why = "; ".join(w for w in (why, reason) if w)
            if ctx.moment in NO_OFFERS and not ctx.critical:
                spoken, why = False, f"{why}; no spoken offers when {ctx.moment.replace('_', ' ')}"
        if kind in GREETING_TYPES and not ctx.alone:
            spoken, why = False, f"{why}; shown, not said (not alone)"
        if ctx.quiet_hours and not ctx.critical:  # quiet hours: nothing is said aloud but what's critical
            spoken, why = False, f"{why}; shown, not said (quiet hours)"
        cap = self.max_sentences(ctx, kind)
        if cap == 0:
            spoken = False
        elif cap is not None and spoken:
            text = trim(text, cap)
        self._record(kind, template, text, ctx, spoken)
        return Line(kind, text, spoken, lead, why.strip("; "), template)

    def _record(self, kind: str, template: str, text: str, ctx: Context, spoken: bool) -> None:
        self._picks += 1
        self.recent[kind].append(template)
        self.used_at[(kind, template)] = self._picks
        if kind in NO_REPEAT:
            self.heard[text] = ctx.now
        greeting = GREETINGS.match(text) if kind in GREETING_TYPES else None
        if greeting:
            self.greeted[ctx.now.date()].add(greeting.group(0).lower())
        if kind in OFFER_TYPES:
            self.offers.append(bool(SHALL.search(template)))
        if "{name}" in template.lower():
            self._addressed = True
        if spoken:
            self.log.append((ctx.now, kind, text))

    # -- composite lines --
    def status(self, ctx: Context, *, due: list[tuple[str, datetime, str]], progress: dict | None,
               systems: dict | None) -> Line:
        """The status readout: time-critical → progress → systems, one sentence each, each with the ref that lights
        up on the HUD as it's said. `due` = [(title, when, ref)] sorted soonest first; `progress` = {thread, label,
        done, total, ref}; `systems` = {source, at, ref}. A readout he asked for: no asides, no offers."""
        parts: list[tuple[str, str | None]] = []
        ctx = Context(**{**ctx.__dict__, "asked": True, "changed": None, "words": None})
        if due:
            title, when, ref = due[0]
            values = {"count": number(len(due)), "nearest": title, "when": say_when(when, ctx.now)}
            parts.append((self._pick("status", ctx, values), ref))
        else:
            parts.append((self._pick("status_none", ctx, {}), None))
        if progress:
            values = {k: (number(v) if isinstance(v, int) else v) for k, v in progress.items() if k != "ref"}
            parts.append((self._pick("status_progress", ctx, values), progress.get("ref")))
        if systems:
            parts.append((self._pick("status_systems", ctx, {"source": systems["source"], "ago": ago(systems["at"], ctx.now)}),
                          systems.get("ref")))
        cap = self.max_sentences(ctx, "status")
        spoken = cap != 0 and not (ctx.quiet_hours and not ctx.critical)
        if cap:
            parts = parts[:cap]
            if cap == 1:  # rushed: one sentence in all
                parts = [(trim(p, 1), ref) for p, ref in parts]
        text = " ".join(p for p, _ in parts)
        if spoken:
            self.log.append((ctx.now, "status", text))
        return Line("status", text, spoken, "plain", "status: time-critical, progress, systems",
                    focus=tuple(ref for _, ref in parts), parts=tuple(p for p, _ in parts))

    def _pick(self, kind: str, ctx: Context, values: dict[str, str]) -> str:
        template = self._choose(kind, [t for t in POOLS[kind]["plain"] if _slots(t) <= set(values)])
        self._picks += 1
        self.recent[kind].append(template)
        self.used_at[(kind, template)] = self._picks
        return fill(template, values)

    def protocol(self, ctx: Context, name: str, write: str | None = None) -> Line:
        """He names a protocol; Jarvis echoes it as a question. If the bundle includes a write, the read-back names it
        and the yes covers only what was read back."""
        echo = fill(POOLS["protocol"]["plain"][0], {"name": name})
        text = f"{echo} {write} Go ahead?" if write else echo
        spoken = not (ctx.quiet_hours and not ctx.critical)
        return Line("protocol", text, spoken, "plain", "echoed back before acting" + ("; read back the write" if write else "")
                    + ("" if spoken else "; shown, not said (quiet hours)"))

    def aside(self, ctx: Context, *, where: str, target: str, thing: str = "", behind: bool = False) -> Line:
        if not self.humour.allowed(ctx.now, self.session, where=where, moment=ctx.moment, target=target,
                                   alone=ctx.alone, behind=behind):
            return Line("aside", SILENT, False, "plain", "no aside here")
        line = self.say("aside", Context(**{**ctx.__dict__, "values": {**ctx.values, "thing": thing or target}}))
        if line.text:
            self.humour.record(ctx.now, self.session, target)
        return line

    def decline(self, kind: str, outcome: str, ctx: Context, *, what: str = "", context: str = "", ref: str = "",
                fingerprint: str = "") -> Line:
        """Record his answer to an offer; returns the one line it earns (usually silence)."""
        result = self.declines.record(kind, outcome, now=ctx.now, context=context, ref=ref, fingerprint=fingerprint,
                                      by_voice=ctx.by_voice)
        if result == "receipt":
            return self.say("decline_receipt", Context(**{**ctx.__dict__, "values": {**ctx.values, "what": what}}))
        return Line("decline", SILENT, False, "plain", "a soft tick at most" if result == "tick" else "his action was the answer")

    def offer(self, kind: str, ctx: Context, *, context: str = "", ref: str = "", fingerprint: str = "") -> Line:
        """An offer, through the decline gate first: off → nothing; card → shown only; speak → the usual rules."""
        gate, why = self.declines.gate(kind, context=context, ref=ref, fingerprint=fingerprint)
        if gate == "off":
            return Line(kind, SILENT, False, "plain", why)
        line = self.say(kind, ctx)
        if gate == "card" and line.spoken:
            line.spoken, line.why = False, why
        return line


# --- when to speak (deterministic rules other parts of Jarvis call) --------------------------------------------
def acknowledge_needed(expected_s: float) -> bool:
    """Jobs over ~1 s get an instant short acknowledgement; under that, nothing but the result."""
    return expected_s >= 1.0


def is_arrival(idle: timedelta, since_last_wake: timedelta | None) -> bool:
    """Walking in: Laptop B unlocked or used after ≥ 30 min idle, or the first wake in ≥ 2 h (no camera)."""
    return idle >= timedelta(minutes=30) or since_last_wake is None or since_last_wake >= timedelta(hours=2)


def full_wake_beat(first_today: bool, away: timedelta) -> bool:
    """The cinematic wake beat: first wake of the day or after ≥ 4 h away. Every other wake is the quick tighten."""
    return first_today or away >= timedelta(hours=4)


def wind_down_spoken(item_finished: bool, tomorrow_changed: bool) -> bool:
    """Wind-down is shown by default; spoken only when a whole item finished or tomorrow changed."""
    return item_finished or tomorrow_changed


def debrief_ok(had_outcome: bool, debriefs_today: int, moment: str) -> bool:
    """After-class debriefs only follow events with an outcome (quiz, lab, midterm), once a day, never when rushed."""
    return had_outcome and debriefs_today == 0 and moment != "rushed"


def new_work_spoken(due_in: timedelta, coarse_breakpoint: bool) -> bool:
    """A new Canvas item gets a Rail notch at once; it's spoken only at a coarse breakpoint and only if due ≤ 72 h."""
    return coarse_breakpoint and due_in <= timedelta(hours=72)


def fire_at(start: datetime, end: datetime, breakpoints: list[datetime], hard: datetime | None = None) -> datetime:
    """Timed lines (leave-for-class, break) fire at the nearest natural breakpoint inside their window, never at the
    same minute every day; a critical "leave now" keeps its hard time."""
    if hard is not None:
        return hard
    inside = sorted(b for b in breakpoints if start <= b <= end)
    return inside[0] if inside else end


def break_window(session_start: datetime) -> tuple[datetime, datetime]:
    """The break line's window: 2.5 to 3.5 hours into a session (once an evening)."""
    return session_start + timedelta(hours=2.5), session_start + timedelta(hours=3.5)


def moment_for(*, minutes_to_fixed: float | None, said_quick: bool = False, minutes_since_arrival: float | None = None,
               free_minutes: float | None = None, session_started: bool = False, heads_down: bool = False,
               others: bool = False, game: bool = False) -> str:
    """now_card.moment from plain signals (§9.3 / review S1)."""
    if game:
        return "game"
    if others:
        return "others"
    if heads_down:
        return "heads_down"
    if said_quick or (minutes_to_fixed is not None and minutes_to_fixed <= 15):
        return "rushed"
    if minutes_since_arrival is not None and minutes_since_arrival <= 10:
        return "between"
    if session_started and (free_minutes is None or free_minutes >= 60):
        return "settled"
    return "between"


def repeat_rate(log: list[tuple[datetime, str, str]], days: int = 7) -> float:
    """Share of spoken lines identical to one spoken in the previous `days` days (safety lines excluded). Shown in
    Under the hood; the target is under 10%."""
    lines = [(at, text) for at, kind, text in sorted(log) if kind not in SAFETY]
    if not lines:
        return 0.0
    seen: dict[str, list[datetime]] = defaultdict(list)
    repeats = 0
    for at, text in lines:
        if any(at - before <= timedelta(days=days) for before in seen[text]):
            repeats += 1
        seen[text].append(at)
    return repeats / len(lines)
