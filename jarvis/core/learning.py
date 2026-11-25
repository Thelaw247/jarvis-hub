"""The learning loop (v0.20.0): Jarvis remembers what De Wet tells him, uses it, and asks once when he lacks something.

His ask of 2026-11-22: "jarvis learns preferences but asks me if it needs context ... so it functions like actual
memory". The store itself (jarvis.memory) has been there since v0.5.0; nothing wrote his words into it or read them
back during a conversation. Three paths, as in the research (JARVIS_RESEARCH_CONTEXT_ARCHITECTURE.md "three ways to
write memory"; LangMem's hot path and background formation):

- On purpose, during the turn: the `remember` tool, when he states a preference, a rule, a correction or a name, or
  answers a question Jarvis asked. Pinned: his word is never overwritten by a guess.
- In the background, after the reply has been spoken: one small model call reads the exchange and notes the durable
  things he said that the talker did not pick up. They are not saved: Jarvis offers them once ("want me to remember
  that?") and he decides (his rule of 2026-11-22: always check with him first). Latency: none on the turn.
- Reading: before each answer the store's fast recall (MEMORY section 7.3) looks up what bears on his words and hands it
  to the talker, with at most 80 ms allowed; his standing preferences ride in the now card.

Rules that keep it honest: only what HE said is saved (never Jarvis's own reply, never a guess); a changed mind retires
the old fact and keeps its history; "Pause memory" and "Off the record" in Controls stop both writing paths; every save
shows on the hub so he can say "forget that"; logs carry ids and counts only (C21).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from typing import Any

log = logging.getLogger("jarvis.core.learning")

RECALL_BUDGET_S = 0.08       # the most a turn may wait for memory before answering without it
LEARN_TIMEOUT_S = 25.0
MIN_WORDS = 4                # "yes", "stop", "thanks": nothing to learn
MAX_PER_TURN = 2
KINDS = ("preference", "procedure", "correction", "decision", "commitment", "fact")
HIS = ("preference", "procedure", "correction", "decision", "commitment")   # his choices (claim_type intent)
EXTRACT = """You keep De Wet's long-term memory for his assistant Jarvis. You are given ONE exchange and the lines already known.
Decide what, if anything, is worth remembering for weeks.

Save only what De Wet himself said that is one of:
- preference: how he likes something done
- procedure: a standing rule for Jarvis ("always...", "never...", "from now on...")
- correction: he corrected something Jarvis got wrong
- decision or commitment: something he decided or promised
- fact: a lasting fact about his life, people, courses or things, including what he calls something

Do not save: one-off requests, questions, small talk, anything only Jarvis said, guesses, passing moods, or anything
already in Known. If he changed something in Known, return an update with that line's id. Most exchanges have nothing
to save: then return [].

Write each memory as one short sentence about him in the third person ("Prefers ...", "Calls GE 122 mechanics").
Answer with JSON only, at most two items:
[{"op": "add" or "update", "id": <the Known id, only for update>, "kind": "...", "text": "...", "about": "<course code or topic, optional>", "scope": "<when it applies, optional>"}]"""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _same(a: str, b: str) -> bool:
    """The same memory said twice (so it is not stored twice)."""
    wa, wb = set(_norm(a).split()), set(_norm(b).split())
    return bool(wa) and (wa == wb or len(wa & wb) / max(len(wa | wb), 1) >= 0.85)


class Learner:
    def __init__(self, memory: Any, keyed: Any, bus: Any, settings: Any = None, *, model: str = "claude-haiku-5-5",
                 client_factory: Any = None, after_save: Any = None) -> None:
        self.memory, self.keyed, self.bus, self.settings, self.model = memory, keyed, bus, settings, model
        self._factory = client_factory
        self._clients: dict[str, Any] = {}
        self.after_save = after_save          # the hub feed's refresh, so the Memory page and now card follow at once
        self.saved_this_turn = False          # the talker used `remember`: the background pass has nothing to add
        self.offers: list[str] = []           # what the background pass noticed: Jarvis offers once, he decides
        self._tasks: set[asyncio.Task] = set()
        self.session = time.strftime("voice-%Y%m%d")

    # -- Controls -------------------------------------------------------------------------------------------------
    def paused(self) -> str | None:
        """Why nothing is being saved right now, or None. Controls: Pause memory, Off the record."""
        hub: dict = {}
        with contextlib.suppress(Exception):
            hub = self.settings.hub() if self.settings is not None else {}
        if hub.get("off_record"):
            return "this conversation is off the record"
        if hub.get("memory_paused"):
            return "memory is paused in Controls"
        return None

    # -- reading (hot path) ---------------------------------------------------------------------------------------
    async def recall(self, text: str) -> str:
        """What memory holds that bears on his words, as prompt lines ('' when nothing or not in time)."""
        if self.memory is None or len(text.split()) < 2:
            return ""
        try:
            got = await asyncio.wait_for(self.memory.hot_recall(text), RECALL_BUDGET_S)
        except Exception:  # noqa: BLE001 - too slow or unavailable: answer without it, never wait
            return self._offer().strip()
        lines = []
        card = got.get("branch_card") if isinstance(got, dict) else None
        if card:
            lines.append(f"About {card.get('branch_id')}: {card.get('status')}")
            lines += [f"- {f.get('statement')}" for f in (card.get("key_facts") or [])[:4] if isinstance(f, dict) and f.get("statement")]
        for hit in (got.get("facts") or [])[:5] if isinstance(got, dict) else []:
            line = getattr(hit, "line", None)
            lines.append(f"- {line() if callable(line) else getattr(hit, 'text', hit)}")
        out = ("# From memory (it may bear on this; use it without saying you looked it up)\n" + "\n".join(lines))[:1200] if lines else ""
        return out + self._offer()

    def _offer(self) -> str:
        """What he said earlier that may be worth keeping: handed to the talker once, to ask him about."""
        offers, self.offers = self.offers[:2], []
        if not offers:
            return ""
        return ("\n\n# Worth offering to remember (ask him once, in a few words, when it fits this turn; save only if he "
                "says yes; if it doesn't fit now, let it go)\n" + "\n".join(f"- {o}" for o in offers))

    # -- writing ---------------------------------------------------------------------------------------------------
    async def save(self, text: str, kind: str = "preference", *, his_words: str = "", about: str | None = None,
                   scope: str | None = None, replaces: str | int | None = None, explicit: bool = True) -> str:
        """Store one thing he said. Returns one plain line for Jarvis (saved, already known, or why not)."""
        from jarvis.memory.model import ClaimIn, EpisodeIn  # noqa: PLC0415

        text = " ".join(str(text).split())
        if self.memory is None:
            return "Not saved: the memory store isn't running on this laptop."
        why = self.paused()
        if why:
            return f"Not saved: {why}."
        if len(text) < 6:
            return "Not saved: say what to remember in one sentence."
        kind = kind if kind in KINDS else "preference"
        hits = []
        with contextlib.suppress(Exception):
            hits = await self.memory.search(text, k=4)
        if any(_same(text, h.text) for h in hits):
            return "Already in memory: nothing to add."
        old = None
        if replaces not in (None, ""):
            if isinstance(replaces, int) or str(replaces).isdigit():
                old = int(replaces)
            else:
                with contextlib.suppress(Exception):
                    found = [h for h in await self.memory.search(str(replaces), k=3) if h.claim_type == "intent" or h.kind in KINDS]
                    old = found[0].fact_id if found else None
        branch = suggested = None
        if about:
            with contextlib.suppress(Exception):
                branch = about if await self.memory.branch_card(about) is not None else None
            suggested = None if branch else about
        claim = ClaimIn(text=text, kind=kind, claim_type="intent" if kind in HIS else "world", scope=scope or None,
                        confidence=0.95 if explicit else 0.7, explicit=True, branch=branch, suggested_branch=suggested,
                        importance=0.7 if explicit else 0.5, pinned=explicit)
        episode = EpisodeIn(content=(his_words or text)[:2000], channel="voice", speaker="user", session_id=self.session, explicit=explicit)
        try:
            if old is not None:
                await self.memory.invalidate(old, session_id=self.session)
            result = await self.memory.add_episode(episode, [claim])
        except Exception as exc:  # noqa: BLE001
            log.warning("learning.save_failed", extra={"error": type(exc).__name__})
            return f"Not saved: memory refused it ({type(exc).__name__})."
        if getattr(result, "blocked", False):
            return "Not saved: this is something he asked Jarvis to forget, or it is marked private."
        log.info("learning.saved", extra={"kind": kind, "count": 1, "status": "updated" if old is not None else "added"})
        self.saved_this_turn = self.saved_this_turn or explicit
        with contextlib.suppress(Exception):
            self.bus.publish("toast", {"id": f"learned-{int(time.time() * 1000)}", "kind": "notice", "ttl_ms": 6000,
                                       "text": f"{'Updated' if old is not None else 'Remembered'}: {text[:140]}"})
        if self.after_save is not None:
            with contextlib.suppress(Exception):
                await self.after_save()
        return f"{'Updated' if old is not None else 'Saved'} in memory: {text}"

    async def forget(self, what: str) -> str:
        """Retire the memory that best matches his words. He asked, so it happens whatever Controls say."""
        if self.memory is None:
            return "The memory store isn't running on this laptop."
        hits = []
        with contextlib.suppress(Exception):
            hits = await self.memory.search(what, k=3)
        if not hits:
            return "Nothing in memory matches that, so nothing was forgotten."
        hit = hits[0]
        try:
            await self.memory.forget(fact_ids=[hit.fact_id], session_id=self.session)
        except Exception as exc:  # noqa: BLE001
            return f"I couldn't forget it ({type(exc).__name__})."
        log.info("learning.forgot", extra={"count": 1})
        with contextlib.suppress(Exception):
            self.bus.publish("fact.updated", {"id": f"f-{hit.fact_id}", "forgotten": True})
        if self.after_save is not None:
            with contextlib.suppress(Exception):
                await self.after_save()
        return f"Forgotten: {hit.text}"

    # -- the background pass ---------------------------------------------------------------------------------------
    def heard(self, user: str, reply: str) -> None:
        """A turn has been answered. Look at it afterwards; the turn itself never waits. Never raises."""
        explicit, self.saved_this_turn = self.saved_this_turn, False
        if explicit or self.memory is None or self.paused() or len(user.split()) < MIN_WORDS:
            return
        try:
            task = asyncio.get_running_loop().create_task(self._learn_quietly(user, reply), name="jarvis-learn")
        except RuntimeError:
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _learn_quietly(self, user: str, reply: str) -> None:
        try:
            await asyncio.wait_for(self.learn(user, reply), LEARN_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - learning is never allowed to disturb the conversation
            log.info("learning.skipped", extra={"error": type(exc).__name__})

    async def _client(self, key: str) -> Any:
        if key not in self._clients:
            if self._factory is None:
                from jarvis.voice.talker_t1 import _anthropic_client  # noqa: PLC0415

                self._factory = _anthropic_client
            self._clients = {key: await asyncio.to_thread(self._factory, key)}
        return self._clients[key]

    async def learn(self, user: str, reply: str) -> list[str]:
        """One small model call over one exchange -> at most two things worth offering to remember. Nothing is saved
        here: they wait in `offers` for Jarvis to ask him about, once. Returns what was noticed."""
        known = []
        with contextlib.suppress(Exception):
            known = await self.memory.search(user, k=5)
        listing = "\n".join(f"[{h.fact_id}] {h.text}" for h in known) or "(nothing related)"

        async def run(key: str) -> str:
            client = await self._client(key)
            msg = await client.messages.create(
                model=self.model, max_tokens=300, system=EXTRACT,
                messages=[{"role": "user", "content": f"Known:\n{listing}\n\nDe Wet said: {user}\n\nJarvis replied: {reply[:600]}"}])
            return "".join(getattr(b, "text", "") for b in getattr(msg, "content", []) or [])

        raw = await self.keyed.call(run)
        found = re.search(r"\[.*\]", raw or "", re.S)
        try:
            items = json.loads(found.group(0)) if found else []
        except ValueError:
            items = []
        ids = {h.fact_id for h in known}
        saved = []
        for item in [i for i in items if isinstance(i, dict) and str(i.get("text") or "").strip()][:MAX_PER_TURN]:
            replaces = item.get("id") if item.get("op") == "update" and item.get("id") in ids else None
            text = " ".join(str(item["text"]).split())
            if replaces is None and any(_same(text, h.text) for h in known):
                continue
            if text not in self.offers:      # nothing is saved here: Jarvis asks him, and he decides (his rule)
                self.offers.append(text)
                saved.append(text)
        self.offers = self.offers[-4:]
        log.info("learning.noticed", extra={"count": len(saved)})
        return saved

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
