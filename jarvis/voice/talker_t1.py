"""T1 talker: Claude (Haiku 5.5) over the Messages API, streaming, with the persona as a cached prefix.

- The persona + code of conduct is the first system block with ``cache_control`` (prompt caching), so every
  turn after the first reads it from cache. The now card follows uncached (it changes every minute).
- **Speculative start:** once he goes quiet and the STT partial has been stable for ``stable_ms``, the call
  starts on the partial. Its text is held, not spoken. If the final transcript matches, the held text is
  released at once (saves ~150-250 ms); if the partial changes, Smart Turn says he is still talking, or T0
  takes the turn, the speculative call is cancelled. Hits and misses are logged per turn.
- The first chunk goes to TTS the moment the chunker says it is complete (VOICE speaking rules).
- Every call goes through K1's ``KeyedClient.call`` (``mgr.client("anthropic")``); the key is handed to the
  SDK client and never logged.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis import review
from jarvis.voice.chunker import Chunker
from jarvis.voice.config import VoiceConfig
from jarvis.voice.frames import (
    FillerFrame,
    Frame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    T0RoutedFrame,
    TTSSpeakFrame,
    TurnIncompleteFrame,
    UserPausedFrame,
    UserTextFrame,
    VADUserStartedSpeakingFrame,
)
from jarvis.voice.persona import PERSONA
from jarvis.voice.ports import KeyedClient
from jarvis.voice.processor import FrameProcessor
from jarvis.voice.router_t0 import normalize
from jarvis.voice.session import VoiceSession

log = logging.getLogger("jarvis.voice.t1")

PERSONA_V0 = PERSONA  # the researched persona (persona.py); the name stays for callers and tests


def _anthropic_client(key: str) -> Any:
    import anthropic  # imported lazily: the sandbox and tests run without it

    # a stalled connection must not hold a turn for the SDK's default 10 minutes (v0.14.0)
    return anthropic.AsyncAnthropic(api_key=key, max_retries=0, timeout=45.0)


class TalkerT1:
    """Builds the request and streams text. T1 hot path: first token is the provider's latency."""

    def __init__(
        self,
        config: VoiceConfig,
        keyed: KeyedClient,
        *,
        persona: str = PERSONA_V0,
        now_card: Callable[[], str] | None = None,
        client_factory: Callable[[str], Any] = _anthropic_client,
        tools: Any = None,
    ) -> None:
        self.config = config
        self.keyed = keyed
        self.persona = persona
        self.now_card = now_card
        self.tools = tools  # jarvis.tools.voice.VoiceTools (TOOLS §2): None = talk only
        self.hearing_note = ""  # what his speech-to-text gets wrong for him (lessons.py); read with every question
        self.tool_level = "full"  # steps down if the API refuses part of the tool list (see stream)
        self.history: list[dict[str, str]] = []
        # What he checked to give each answer (tool calls and results), kept beside the history (v0.27.2). Until now
        # only the words were kept, so one turn later his own answer looked unchecked to him: on 23 Nov he re-read
        # the timetable five turns running and "corrected" an answer that had been right the whole time.
        self._work: list[tuple[str, str, list[dict]]] = []
        self._pending_work: tuple[str, list[dict]] | None = None
        self.recall = None      # async (his words) -> prompt lines from memory, within its own time limit (v0.20.0)
        self.on_learn = None    # (his words, the reply) once a turn is answered: the background learning pass
        self._recalled = ""
        self._factory = client_factory
        # One SDK client per key, so its HTTP connection pool stays warm across turns (no TLS handshake per
        # turn). Two at most: the live key and, for 15 minutes after a swap, the previous one.
        self._clients: dict[str, Any] = {}

    def _client(self, key: str) -> Any:
        client = self._clients.get(key)
        if client is None:
            while len(self._clients) >= 2:
                self._clients.pop(next(iter(self._clients)))
            client = self._clients[key] = self._factory(key)
        return client

    def build_request(self, text: str) -> dict[str, Any]:
        system: list[dict[str, Any]] = [
            {"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}},
        ]
        request: dict[str, Any] = {"model": self.config.llm_model, "max_tokens": self.config.llm_max_tokens}
        quiet = next((v for k, v in SPEAK_FIRST if str(self.config.llm_model).startswith(k)), None)
        if quiet is not None:
            request["thinking"] = dict(quiet)
        if self.tools is not None:
            # the routing policy + ability index: stable, so cached with the persona (TOOLS §5)
            guide = self.tools.guide() + (f"\n\n{self.hearing_note}" if self.hearing_note else "")
            system.append({"type": "text", "text": guide, "cache_control": {"type": "ephemeral"}})
            tools = self.tools.params(self.tool_level)
            if tools:
                request["tools"] = tools
        elif self.hearing_note:
            system.append({"type": "text", "text": self.hearing_note, "cache_control": {"type": "ephemeral"}})
        card = self.now_card() if self.now_card else ""
        if card:
            system.append({"type": "text", "text": card})
        if self._recalled:   # what memory holds about what he just said (never cached: it changes every turn)
            system.append({"type": "text", "text": self._recalled})
        return {**request, "system": system, "messages": [*self._with_work(), {"role": "user", "content": text}]}

    def _with_work(self) -> list[dict]:
        """The conversation so far, with each answer's checks put back in front of it."""
        work = {(u, r): w for u, r, w in self._work}
        out: list[dict] = []
        h = self.history
        for i, msg in enumerate(h):
            if msg.get("role") == "assistant" and i > 0 and h[i - 1].get("role") == "user":
                out.extend(work.get((h[i - 1].get("content"), msg.get("content")), []))
            out.append(msg)
        return out

    async def stream(self, text: str, on_delta: Callable[[str], Awaitable[None]], *,
                     gate: Callable[[], Awaitable[bool]] | None = None,
                     on_tools: Callable[[list[str]], Awaitable[None]] | None = None,
                     turn_id: str | None = None) -> Any:
        """T1. Stream the reply through ``on_delta``; return the summed ``usage``.

        With tools (TOOLS §2): when Claude stops for tool use, ``gate`` is awaited first (a speculative answer runs
        no tool until his final transcript confirms it; False = abandon), ``on_tools`` hears the names (fillers,
        the latency log), the calls run in parallel, and the reply carries on streaming. Server tools (web
        search) run inside the API call; ``pause_turn`` just continues. At most ``MAX_TOOL_ROUNDS`` rounds.

        Runs inside ``keyed.call`` so K1 leases the key for this request (and retries once on the previous
        key after a refused swap: that happens at the request start, before any text has been spoken).
        """
        self._recalled = ""
        if self.recall is not None:
            with contextlib.suppress(Exception):
                self._recalled = await self.recall(text) or ""
        request = self.build_request(text)
        said = {"n": 0}
        inner_delta = on_delta
        clock = {"t0": time.perf_counter(), "first": None}

        async def on_delta(delta: str) -> None:  # noqa: F811 - counts what was actually said this turn
            if delta:
                said["n"] += len(delta)
                if clock["first"] is None:
                    clock["first"] = time.perf_counter()
            await inner_delta(delta)

        def sent(req: dict, messages: list, round_: int) -> None:
            """Review recording (off: one comparison): exactly what Claude is sent this round."""
            if not review.on():
                return
            clock["t0"], clock["first"] = time.perf_counter(), None
            system = "\n\n".join(b.get("text", "") for b in req.get("system", []) if isinstance(b, dict))
            fresh = hash(system) != getattr(self, "_review_system", None)
            self._review_system = hash(system)
            tools = req.get("tools", [])
            review.note("llm.request", turn=turn_id, round=round_, model=req.get("model"),
                        max_tokens=req.get("max_tokens"), system_chars=len(system),
                        system=system if fresh else "(same as the last request)",
                        tools=[t.get("name") or t.get("type") for t in tools if isinstance(t, dict)],
                        tool_defs=tools if fresh else "(same as the last request)",
                        history=len(messages) - 1 if round_ == 0 else None,
                        messages=messages if round_ == 0 else messages[-2:])

        def got(final: Any, round_: int) -> None:
            if not review.on():
                return
            now = time.perf_counter()
            review.note("llm.response", turn=turn_id, round=round_, stop=getattr(final, "stop_reason", None),
                        first_text_ms=None if clock["first"] is None else round((clock["first"] - clock["t0"]) * 1000, 1),
                        total_ms=round((now - clock["t0"]) * 1000, 1), usage=getattr(final, "usage", None),
                        content=[_block(b) for b in getattr(final, "content", []) or []])

        async def first_round(client: Any, messages: list) -> Any:
            """The first call, stepping the tool list down if the API refuses it (400) before any text: a feature
            that isn't on for his account must not break every spoken turn. The level sticks for later turns."""
            nonlocal request
            while True:
                try:
                    sent(request, messages, 0)
                    async with client.messages.stream(**{**request, "messages": messages}) as stream:
                        async for delta in stream.text_stream:
                            await on_delta(delta)
                        return await stream.get_final_message()
                except Exception as exc:
                    review.note("llm.error", turn=turn_id, round=0, error=type(exc).__name__, detail=str(exc)[:2000],
                                status=getattr(exc, "status_code", None))
                    levels = self.tools.LEVELS if self.tools is not None else ()
                    if (getattr(exc, "status_code", None) != 400 or "tools" not in request
                            or self.tool_level not in levels or self.tool_level == levels[-1]):
                        raise
                    self.tool_level = levels[levels.index(self.tool_level) + 1]
                    log.warning("voice.tools_refused", extra={"status": "400", "code": self.tool_level})
                    request = self.build_request(text)

        async def run(key: str) -> Any:
            nonlocal request
            client = self._clients.get(key)
            if client is None:
                # Laptop B, 2026-11-22: the first turn after a restart loaded the Anthropic library on the event loop
                # and the whole core froze for 63 s. Made in a thread, the turn waits for it and nothing else does.
                client = await asyncio.to_thread(self._client, key)
            messages = list(request["messages"])
            total = _Usage()
            retried = False
            round_ = 0
            while round_ < MAX_TOOL_ROUNDS:
                if round_ == 0 and not retried:
                    final = await first_round(client, messages)
                else:
                    sent(request, messages, round_)
                    try:
                        async with client.messages.stream(**{**request, "messages": messages}) as stream:
                            async for delta in stream.text_stream:
                                await on_delta(delta)
                            final = await stream.get_final_message()
                    except Exception as exc:
                        review.note("llm.error", turn=turn_id, round=round_, error=type(exc).__name__,
                                    detail=str(exc)[:2000], status=getattr(exc, "status_code", None))
                        raise
                got(final, round_)
                round_ += 1
                total.add(getattr(final, "usage", None))
                stop = getattr(final, "stop_reason", None)
                total.stop, total.rounds = str(stop or ""), round_
                content = [_block(b) for b in getattr(final, "content", []) or []]
                if stop == "pause_turn":
                    messages = [*messages, {"role": "assistant", "content": content}]
                    continue
                calls = [b for b in getattr(final, "content", []) or [] if getattr(b, "type", "") == "tool_use"]
                if stop != "tool_use" or not calls or self.tools is None:
                    if said["n"] == 0 and not retried:
                        # Nothing to say at all (7 of 23 turns on 2026-11-18: he heard "Mm." and then silence).
                        # Once more, with room to finish a cut-off tool call and a plain instruction to answer.
                        retried = True
                        total.empty_first = str(stop or "none")
                        request = {**request, "max_tokens": max(int(request.get("max_tokens", 0)), 1200),
                                   "system": [*request["system"], {"type": "text", "text": EMPTY_NUDGE}]}
                        continue
                    break
                if gate is not None and not await gate():
                    break
                names = [c.name for c in calls]
                if on_tools is not None:
                    await on_tools(names)
                results = await asyncio.gather(*(self.tools.run(c.name, c.input, turn_id=turn_id) for c in calls))
                messages = [*messages, {"role": "assistant", "content": content},
                            {"role": "user", "content": [
                                {"type": "tool_result", "tool_use_id": c.id, "content": r.content,
                                 **({"is_error": True} if r.is_error else {})} for c, r in zip(calls, results, strict=True)]}]
            self._pending_work = (str(request["messages"][-1].get("content")), messages[len(request["messages"]):])
            return total if total.any else None

        return await self.keyed.call(run)

    def remember(self, user: str, reply: str) -> None:
        self.history += [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
        pending, self._pending_work = self._pending_work, None
        if pending is not None and pending[0] == user and reply and _checks(pending[1]):
            self._work.append((user, reply, _short(pending[1])))
        if self.on_learn is not None:
            with contextlib.suppress(Exception):
                self.on_learn(user, reply)
        keep = self.config.history_turns * 2
        self.history = self.history[-keep:]
        said = {(self.history[i - 1].get("content"), m.get("content")) for i, m in enumerate(self.history) if i and m.get("role") == "assistant"}
        self._work = [w for w in self._work if (w[0], w[1]) in said][-keep:]


# Thinking before speaking (v0.27.3). The 5.5 models think by default when the request says nothing about it, and
# that thinking counts toward max_tokens. Measured on Laptop A, 23 Nov: 294 to 429 hidden thinking tokens before a
# two-sentence reply, about 3 s before his first word, and replies cut off at the 600-token limit. The voice design
# always said "no extended thinking" for the spoken turn; these are the documented ways to say so per model
# (platform.claude.com/docs/en/build-with-claude/thinking): Haiku 5.5 takes "disabled"; Sonnet 5.5 refuses that
# and takes "between_tools" (no thinking up front, thinking between tool calls).
# Only the quick brain for now: the deep one is left as it was until its setting has been tried against the real API.
SPEAK_FIRST = (("claude-haiku-5-5", {"type": "disabled"}),)

WORK_RESULT_CHARS = 700   # enough of a tool's answer for him to see what he had read; the rest was already said


def _checks(work: list[dict]) -> bool:
    """Is this a clean run of tool calls and their results (assistant, user, assistant, user ...)?"""
    if not work or len(work) % 2:
        return False
    for i, msg in enumerate(work):
        blocks = msg.get("content")
        want = ("assistant", "tool_use") if i % 2 == 0 else ("user", "tool_result")
        if msg.get("role") != want[0] or not isinstance(blocks, list) or not any(isinstance(b, dict) and b.get("type") == want[1] for b in blocks):
            return False
    return True


def _short(work: list[dict]) -> list[dict]:
    out = []
    for msg in work:
        blocks = []
        for b in msg["content"]:
            if isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"):
                continue   # an earlier turn's thinking is never sent back: after the now card changes the API refuses it
            if isinstance(b, dict) and b.get("type") == "tool_result" and isinstance(b.get("content"), str) and len(b["content"]) > WORK_RESULT_CHARS:
                b = {**b, "content": b["content"][:WORK_RESULT_CHARS] + " …"}
            blocks.append(b)
        out.append({"role": msg["role"], "content": blocks})
    return out


CARRY_WITHIN_S = 2.0   # cut off this soon after Jarvis started answering: he was still mid-thought
CARRY_FOR_S = 20.0     # ...and the rest of the thought comes within this long
STUCK_AFTER_S = 8.0    # a finished answer with no sound for this long: the turn is closed by force
NO_REPLY = "Sorry, I didn't catch that. Say it again?"
MAX_TOOL_ROUNDS = 4  # tool rounds in one spoken turn; anything longer is a task (start_task)
EMPTY_NUDGE = ("Your last reply to this came back empty, and he is waiting. Answer now: one short spoken sentence, or "
               "the tool call it needs. If what he said doesn't make sense as heard, ask him to say it again in a "
               "few words.")


class _Usage:
    """Token counts summed over a turn's rounds (spend meter, cache check)."""

    FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

    def __init__(self) -> None:
        for f in self.FIELDS:
            setattr(self, f, 0)
        self.any = False
        self.stop = ""           # the last round's stop reason (end_turn, tool_use, max_tokens, refusal...)
        self.rounds = 0
        self.empty_first = ""    # set when the first try came back with no words: its stop reason

    def add(self, usage: Any) -> None:
        if usage is None:
            return
        self.any = True
        for f in self.FIELDS:
            setattr(self, f, getattr(self, f) + int(getattr(usage, f, 0) or 0))


def _block(b: Any) -> Any:
    """An assistant content block as request params (SDK models → dicts; dicts pass through)."""
    if isinstance(b, dict):
        return b
    dump = getattr(b, "model_dump", None)
    return dump(exclude_none=True) if dump else b


@dataclass
class _Response:
    text: str                   # the user text it answers
    turn_id: str
    speculative: bool
    task: asyncio.Task[Any] | None = None
    confirmed: bool = False
    held: list[str] = field(default_factory=list)
    first_token_at: float | None = None
    done: bool = False
    finished: bool = False
    failed: bool = False
    reply: str = ""
    spoken_at: float | None = None   # when its first words went to the voice


class TalkerProcessor(FrameProcessor):
    def __init__(self, session: VoiceSession, talker: TalkerT1) -> None:
        super().__init__(session)
        self.talker = talker
        self._partial = ""
        self._partial_t0 = False
        self._partial_audio_ms = 0.0
        self._spec: _Response | None = None
        self._live: _Response | None = None
        self._spec_count: dict[str, int] = {}
        self.stats = {"spec_started": 0, "spec_hit": 0, "spec_cancelled": 0}
        # What he said in a turn he then talked over before Jarvis had really answered: the next turn is the rest of
        # the same thought, so it's answered together (v0.14.0). (text, when)
        self._carry: tuple[str, float] | None = None
        self._last: _Response | None = None   # the answer that finished most recently (its voice may still be playing)

    async def process_frame(self, frame: Frame) -> None:
        s = self.session
        if isinstance(frame, InterimTranscriptionFrame):
            if self._spec and normalize(frame.text) != normalize(self._spec.text):
                self._cancel_spec("partial_changed")
            if frame.text != self._partial:
                self._partial, self._partial_t0, self._partial_audio_ms = frame.text, frame.t0_match, s.audio_ms
            return
        if isinstance(frame, UserPausedFrame):
            self._maybe_speculate(frame.turn_id)
            return
        if isinstance(frame, VADUserStartedSpeakingFrame):
            await self.push_frame(frame)
            return
        if isinstance(frame, TurnIncompleteFrame):
            self._cancel_spec("still_talking")
            return
        if isinstance(frame, T0RoutedFrame):
            self._cancel_spec("t0")
            self._reset_partial()
            return
        if isinstance(frame, UserTextFrame):
            await self._answer(frame)
            self._reset_partial()
            return
        if isinstance(frame, InterruptionFrame):
            self._cancel_spec(frame.reason)
            live = self._live
            if live is not None:
                if live.task:
                    live.task.cancel()
                heard = live.spoken_at is not None and s.clock() - live.spoken_at >= CARRY_WITHIN_S
                if frame.reason == "stuck":
                    pass
                elif heard:
                    # he heard a good part of the answer, then cut in: keep the exchange, so "no, the other one"
                    # makes sense. (Before, an interrupted answer was forgotten completely.)
                    self.talker.remember(live.text, (live.reply.strip() + " …").strip() + " (De Wet cut in here.)")
                    self._carry = None
                else:
                    # he went on talking before Jarvis had really answered: one thought, said in two parts
                    self._carry = (live.text, s.clock())
            elif (frame.reason != "stuck" and self._last is not None and self._last.turn_id == frame.turn_id
                  and self._last.spoken_at is not None and s.clock() - self._last.spoken_at < CARRY_WITHIN_S):
                # the whole answer was already written, but he'd heard under two seconds of it when he went on:
                # still one thought. Take the half-answered exchange back out of the conversation and join the parts.
                last = self._last
                h = self.talker.history
                if len(h) >= 2 and h[-2].get("content") == last.text and h[-1].get("content") == last.reply:
                    del h[-2:]
                self._carry = (last.text, s.clock())
            self._live = None
            s.live_turn = None
            await self.push_frame(frame)
            return
        await super().process_frame(frame)

    def _reset_partial(self) -> None:
        self._partial, self._partial_t0 = "", False

    # -- speculation ---------------------------------------------------------------------------------
    def _maybe_speculate(self, turn_id: str | None) -> None:
        rules = self.session.config.speculation
        if (not rules.enabled or turn_id is None or self._spec is not None or self._partial_t0
                or self.session.barge is not None  # talking over Jarvis: not a question (yet)
                or len(self._partial.split()) < rules.min_words
                or self.session.audio_ms - self._partial_audio_ms < rules.stable_ms
                or self._spec_count.get(turn_id, 0) >= rules.max_per_turn):
            return
        self._spec_count[turn_id] = self._spec_count.get(turn_id, 0) + 1
        self.stats["spec_started"] += 1
        self._spec = self._start(self._whole(self._partial), turn_id, speculative=True)

    def _whole(self, text: str) -> str:
        """What he said, with the part he'd already said in the turn he talked over (if that was just now)."""
        if self._carry is None:
            return text
        earlier, when = self._carry
        if self.session.clock() - when > CARRY_FOR_S or normalize(text).startswith(normalize(earlier)):
            return text
        return f"{earlier} {text}".strip()

    def _cancel_spec(self, why: str) -> None:
        spec, self._spec = self._spec, None
        if spec is None:
            return
        if spec.task:
            spec.task.cancel()
        self.stats["spec_cancelled"] += 1
        self.session.recorder.note(spec.turn_id, "speculation", "cancelled")
        log.debug("speculation cancelled", extra={"turn": spec.turn_id, "why": why})

    # -- answering -----------------------------------------------------------------------------------
    async def _answer(self, frame: UserTextFrame) -> None:
        s = self.session
        turn = frame.turn_id or ""
        text = self._whole(frame.text)
        if text != frame.text:
            s.recorder.note(turn, "joined", True)   # answered together with the part he said just before
        spec = self._spec
        if (spec is not None and spec.turn_id == turn and not spec.failed
                and normalize(spec.text) == normalize(text)):
            self._spec = None
            self.stats["spec_hit"] += 1
            s.recorder.note(turn, "speculation", "hit")
            self._live = spec
            s.live_turn = turn
            await self._confirm(spec)
            return
        if spec is not None:
            self._cancel_spec("final_differs")
            s.recorder.note(turn, "speculation", "miss")
        self._live = self._start(text, turn, speculative=False)
        s.live_turn = turn
        await self._confirm(self._live)

    def _start(self, text: str, turn_id: str, *, speculative: bool) -> _Response:
        resp = _Response(text=text, turn_id=turn_id, speculative=speculative)
        resp.task = self.spawn(self._run(resp))
        return resp

    async def _confirm(self, resp: _Response) -> None:
        self.session.speaking_text = ""
        if resp.first_token_at is None and self.session.config.filler_after_ms > 0:
            self.spawn(self._filler(resp))
        if resp.first_token_at is not None:
            self.session.recorder.mark(resp.turn_id, "llm_first_token")  # effective first token: now
        while resp.held:  # chunks that arrive while flushing join the queue, so order is kept
            await self._say(resp, resp.held.pop(0))
        resp.confirmed = True
        if resp.done:
            await self._finish(resp)

    async def _say(self, resp: _Response, chunk: str) -> None:
        if resp.spoken_at is None:
            resp.spoken_at = self.session.clock()
        self.session.speaking_text += " " + chunk
        await self.push_frame(TTSSpeakFrame(text=chunk, turn_id=resp.turn_id))

    async def _emit_chunk(self, resp: _Response, chunk: str) -> None:
        if resp.confirmed:
            await self._say(resp, chunk)
        else:
            resp.held.append(chunk)

    async def _filler(self, resp: _Response, *, wait: bool = True) -> None:
        """Claude is slow to start (or a slow tool runs): one short cached filler so Jarvis doesn't go silent."""
        s = self.session
        if wait:
            await asyncio.sleep(s.config.filler_after_ms / 1000.0)
        now = time.monotonic()
        if (resp.first_token_at is not None or resp.failed or s.responding != resp.turn_id or s.bot_speaking
                or now - s.last_filler_at < s.config.filler_gap_s or not s.config.fillers):
            return
        s.last_filler_at = now
        self._filler_i = (getattr(self, "_filler_i", -1) + 1) % len(s.config.fillers)
        await self.push_frame(FillerFrame(text=s.config.fillers[self._filler_i], turn_id=resp.turn_id))

    async def _run(self, resp: _Response) -> None:
        s = self.session
        chunker = Chunker(s.config.speaking)
        usage: Any = None

        async def on_delta(delta: str) -> None:
            if not delta:
                return
            if resp.first_token_at is None:
                resp.first_token_at = s.clock()
                if resp.confirmed:
                    s.recorder.mark(resp.turn_id, "llm_first_token", resp.first_token_at)
            resp.reply += delta
            for chunk in chunker.feed(delta):
                await self._emit_chunk(resp, chunk)

        async def gate() -> bool:
            """A speculative answer runs no tool until his final words confirm it (no fetching for a guess)."""
            while not resp.confirmed:
                if resp.task is not None and resp.task.cancelled():
                    return False
                await asyncio.sleep(0.02)
            return True

        async def on_tools(names: list[str]) -> None:
            s.recorder.note(resp.turn_id, "tools", ",".join(names))
            tools = self.talker.tools
            if tools is not None and tools.slow(names) and resp.first_token_at is None:
                await self._filler(resp, wait=False)

        try:
            usage = await self.talker.stream(resp.text, on_delta, gate=gate, on_tools=on_tools,
                                             turn_id=resp.turn_id)
            for chunk in chunker.flush():
                await self._emit_chunk(resp, chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # the error's type and HTTP status only (never the text of what he said)
            log.warning("voice.talker_failed", extra={"turn": resp.turn_id, "error": type(exc).__name__,
                                                      "status": str(getattr(exc, "status_code", "") or "")})
            resp.reply = ""
            resp.failed = True
            await self._emit_chunk(resp, "Sorry, I can't answer that right now.")  # held if speculative
        if usage is not None:
            # is the persona being served from Anthropic's prompt cache? (it should: ~1,250 tokens, cached)
            s.recorder.note(resp.turn_id, "cache_read", int(getattr(usage, "cache_read_input_tokens", 0) or 0))
            # why the reply ended and how long it was: counts and flags, never the words (C21)
            stop = str(getattr(usage, "stop", "") or "")
            if stop and stop != "end_turn":
                s.recorder.note(resp.turn_id, "stop", stop)
            if getattr(usage, "empty_first", ""):
                s.recorder.note(resp.turn_id, "empty_first", usage.empty_first)
            s.recorder.note(resp.turn_id, "out_tokens", int(getattr(usage, "output_tokens", 0) or 0))
            with contextlib.suppress(KeyError):
                s.spend.record_llm(self.talker.config.llm_model, usage)
        if not resp.reply.strip() and not resp.failed:
            # Still nothing after the second try. Silence is right only when it wasn't meant for him; if he was
            # addressed (wake word, talk key), a filler already promised an answer, or it was a real sentence, say so.
            s.recorder.note(resp.turn_id, "no_reply", True)
            promised = s.recorder.get_note(resp.turn_id, "filler") is not None
            if s.addressed or promised or len(resp.text.split()) >= 4:
                resp.reply = NO_REPLY
                await self._emit_chunk(resp, NO_REPLY)
        resp.done = True
        if resp.confirmed:
            await self._finish(resp)

    async def prompt(self, text: str, *, wait_s: float = 60.0) -> bool:
        """Jarvis picks a thread back up by himself (he signed in; a tool is ready): one more spoken answer with no
        new words from De Wet. ``text`` is Jarvis's own note about what just happened; the conversation so far tells
        him what to do with it. Waits for a quiet moment, like announce."""
        s = self.session
        deadline = time.monotonic() + wait_s
        while (s.user_turn is not None or s.responding is not None or s.bot_speaking or s.barge is not None
               or self._live is not None):
            if time.monotonic() > deadline:
                return False
            await asyncio.sleep(0.1)
        turn = s.new_turn()
        s.user_turn = None
        s.responding = turn
        await s.show_orb()
        self._live = self._start(text, turn, speculative=False)
        s.live_turn = turn
        await self._confirm(self._live)
        return True

    async def announce(self, text: str, *, wait_s: float = 90.0) -> bool:
        """A task finished (or a task asks him something): say it at the next quiet moment, never over him or over
        another answer. It joins the conversation history, so "and the second one?" makes sense afterwards."""
        s = self.session
        text = text.strip()
        if not text:
            return False
        deadline = time.monotonic() + wait_s
        while (s.user_turn is not None or s.responding is not None or s.bot_speaking or s.barge is not None
               or self._live is not None):
            if time.monotonic() > deadline:
                return False
            await asyncio.sleep(0.1)
        turn = s.new_turn()
        s.user_turn = None
        s.responding = turn
        self.talker.remember("(Jarvis reports back on a task he was working on.)", text)
        s.speaking_text = text
        await self.push_frame(TTSSpeakFrame(text=text, turn_id=turn))
        await s.emit("caption.show", {"text": text, "ttl_ms": 8000})
        await self.push_frame(LLMFullResponseEndFrame(text="", turn_id=turn))
        self.spawn(self._watch(turn))
        return True

    async def _finish(self, resp: _Response) -> None:
        if resp.finished:
            return
        resp.finished = True
        s = self.session
        if self._live is resp:
            self._live = None
        self._last = resp
        if s.live_turn == resp.turn_id:
            s.live_turn = None
        self._carry = None   # answered: the thought is closed
        if resp.reply:
            self.talker.remember(resp.text, resp.reply)
            await s.emit("caption.show", {"text": resp.reply.strip(), "ttl_ms": 6000})
            if s.debug is not None:
                s.debug.said(resp.turn_id, resp.text, resp.reply)
        await self.push_frame(LLMFullResponseEndFrame(text="", turn_id=resp.turn_id))
        self.spawn(self._watch(resp.turn_id))

    async def _watch(self, turn_id: str) -> None:
        """The words are done; the voice must follow. If this turn is still "answering" long after the last sound
        (the voice service never closed it), end it, so Jarvis doesn't sit there deaf to everything said after.
        On 2026-11-18 he went quiet for good after a sign-in: every later sentence was "talking over" a turn that
        had never ended."""
        s = self.session
        quiet = 0.0
        while s.responding == turn_id:
            await asyncio.sleep(0.5 * s.orb_time_scale)
            quiet = quiet + 0.5 if s.clock() - s.audio_at > 1.0 * s.orb_time_scale else 0.0
            if quiet >= STUCK_AFTER_S:
                log.warning("voice.turn_stuck", extra={"turn": turn_id})
                s.recorder.note(turn_id, "stuck", True)
                await self.push_frame(InterruptionFrame(turn_id=turn_id, reason="stuck"))
                return
