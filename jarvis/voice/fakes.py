"""Fakes for every outside service, so the pipeline runs end to end in tests and in the scripted latency run.

Fake latencies are in milliseconds (defaults from the VOICE latency table) and multiplied by ``scale``, so a
50-utterance run takes seconds. Audio frames carry their script in ``meta``: ``speech``, ``partial``,
``incomplete`` (Smart Turn says still talking), ``final`` (the STT final differs from the last partial),
``ptt_release``.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from jarvis.voice.frames import InputAudioRawFrame
from jarvis.voice.ports import Command, PendingApproval

FAKE_KEY = "fake-key-for-tests"  # not a real key


@dataclass
class FakeLatencies:
    smart_turn_ms: float = 12.0
    stt_final_ms: float = 80.0
    llm_first_token_ms: float = 450.0
    llm_token_gap_ms: float = 12.0
    tts_first_byte_ms: float = 180.0
    tts_chunk_ms: float = 30.0
    scale: float = 1.0

    async def sleep(self, ms: float) -> None:
        await asyncio.sleep(ms * self.scale / 1000.0)


# -- script helpers ------------------------------------------------------------------------------------------
def utterance(text: str, *, frames_per_word: int = 3, quiet_frames: int = 14, final: str | None = None,
              pause_after_word: int | None = None, pause_frames: int = 12, ptt: bool = False,
              ) -> list[InputAudioRawFrame]:
    """Frames for one spoken utterance: speech with growing partials, then silence (or a PTT release)."""
    words = text.split()
    out: list[InputAudioRawFrame] = []
    for i in range(len(words)):
        partial = " ".join(words[: i + 1])
        for _ in range(frames_per_word):
            out.append(InputAudioRawFrame(meta={"speech": True, "partial": partial}, ptt=ptt))
        if pause_after_word is not None and i == pause_after_word and i < len(words) - 1:
            out += [InputAudioRawFrame(meta={"speech": False, "incomplete": True}, ptt=ptt) for _ in range(pause_frames)]
    if ptt:
        out.append(InputAudioRawFrame(meta={"speech": False, "ptt_release": True, "final": final}, ptt=True))
        return out
    for _ in range(quiet_frames):
        out.append(InputAudioRawFrame(meta={"speech": False, "final": final}))
    return out


def silence(n: int) -> list[InputAudioRawFrame]:
    return [InputAudioRawFrame(meta={"speech": False}) for _ in range(n)]


# -- audio in side ---------------------------------------------------------------------------------------------
class FakeVad:
    async def is_speech(self, frame: Any) -> bool:
        return bool(frame.meta.get("speech"))


class FakeTurn:
    def __init__(self, lat: FakeLatencies | None = None) -> None:
        self.lat = lat or FakeLatencies()
        self._last: Mapping[str, Any] = {}
        self.asked = 0

    def append(self, frame: Any, is_speech: bool) -> None:
        self._last = frame.meta

    async def is_complete(self) -> bool:
        self.asked += 1
        await self.lat.sleep(self.lat.smart_turn_ms)
        return not self._last.get("incomplete")

    def clear(self) -> None:
        self._last = {}


class FakeStt:
    def __init__(self, lat: FakeLatencies | None = None) -> None:
        self.lat = lat or FakeLatencies()
        self._partial = ""
        self._final: str | None = None

    async def accept(self, frame: Any) -> str:
        if "partial" in frame.meta:
            self._partial = frame.meta["partial"]
        if frame.meta.get("final"):
            self._final = frame.meta["final"]
        return self._partial

    async def finalize(self) -> str:
        await self.lat.sleep(self.lat.stt_final_ms)
        text = self._final or self._partial
        self._partial, self._final = "", None
        return text


# -- keys and the LLM ----------------------------------------------------------------------------------------------
class FakeKeyed:
    """Matches K1's KeyedClient.call: runs fn(key)."""

    def __init__(self, key: str = FAKE_KEY) -> None:
        self.key = key
        self.calls = 0

    async def call(self, fn: Callable[[str], Awaitable[Any]]) -> Any:
        self.calls += 1
        return await fn(self.key)


@dataclass
class FakeUsage:
    input_tokens: int = 40
    output_tokens: int = 20
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class _Block:
    """A content block like the SDK's (type, text / id, name, input) with ``model_dump``."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)

    def model_dump(self, exclude_none: bool = False) -> dict:
        return {k: v for k, v in self.__dict__.items() if not (exclude_none and v is None)}


class _FakeStream:
    def __init__(self, owner: FakeAnthropic, reply: str, tool: tuple[str, dict] | None = None) -> None:
        self.owner, self.reply, self.tool = owner, reply, tool

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[str]:
        lat = self.owner.lat
        self.owner.started += 1
        try:
            await lat.sleep(lat.llm_first_token_ms)
            tokens = self.reply.split(" ") if self.reply else []  # a tool call alone streams no text
            for i, tok in enumerate(tokens):
                if i:
                    await lat.sleep(lat.llm_token_gap_ms)
                yield tok if i == len(tokens) - 1 else tok + " "
            self.owner.completed += 1
        except asyncio.CancelledError:
            self.owner.cancelled += 1
            raise

    async def get_final_message(self) -> Any:
        first = self.owner.completed <= 1
        content: list[Any] = [_Block(type="text", text=self.reply)] if self.reply else []
        if self.tool is not None:
            self.owner.tool_ids += 1
            content.append(_Block(type="tool_use", id=f"toolu_{self.owner.tool_ids}", name=self.tool[0],
                                  input=self.tool[1]))
        return type("Msg", (), {"usage": FakeUsage(
            input_tokens=60, output_tokens=len(self.reply.split()),
            cache_creation_input_tokens=1200 if first else 0, cache_read_input_tokens=0 if first else 1200),
            "content": content, "stop_reason": "tool_use" if self.tool is not None else "end_turn"})()


class FakeAnthropic:
    """Stands in for ``anthropic.AsyncAnthropic``: ``client.messages.stream(**request)``."""

    def __init__(self, lat: FakeLatencies | None = None, reply: Callable[[str], str] | None = None,
                 script: Callable[[dict[str, Any]], Any] | None = None) -> None:
        self.lat = lat or FakeLatencies()
        self._reply = reply or (lambda text: "Thursday at noon, in Engineering 1B71. You have two left.")
        # script(request) -> "text" or ("text", (tool_name, tool_input)): a tool call ends the round (tool_use)
        self._script = script
        self.tool_ids = 0
        self.requests: list[dict[str, Any]] = []
        self.started = self.completed = self.cancelled = 0
        self.messages = self
        self.keys_seen: list[str] = []

    def factory(self, key: str) -> FakeAnthropic:
        self.keys_seen.append(key)
        return self

    def stream(self, **request: Any) -> _FakeStream:
        self.requests.append(request)
        if self._script is not None:
            out = self._script(request)
            if isinstance(out, tuple):
                return _FakeStream(self, out[0], out[1])
            return _FakeStream(self, out)
        return _FakeStream(self, self._reply(request["messages"][-1]["content"]))


# -- TTS and audio out ---------------------------------------------------------------------------------------------
class FakeTts:
    """Implements the TtsPort: audio for each text chunk after a first-byte delay; 240 bytes per character."""

    BYTES_PER_CHAR = 240

    def __init__(self, lat: FakeLatencies | None = None) -> None:
        self.lat = lat or FakeLatencies()
        self._queues: dict[str, asyncio.Queue[Any]] = {}
        self._work: dict[str, asyncio.Queue[Any]] = {}
        self._workers: dict[str, asyncio.Task[Any]] = {}
        self.sent: list[tuple[str, str]] = []
        self.cancelled: list[tuple[str, float]] = []
        self.synthesized: list[str] = []
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def open(self, context_id: str) -> None:
        self._queues[context_id] = asyncio.Queue()
        self._work[context_id] = asyncio.Queue()
        self._workers[context_id] = asyncio.create_task(self._worker(context_id))

    async def _worker(self, ctx: str) -> None:
        first = True
        work, out = self._work[ctx], self._queues[ctx]
        while True:
            item = await work.get()
            if item is None:
                out.put_nowait(None)
                return
            await self.lat.sleep(self.lat.tts_first_byte_ms if first else self.lat.tts_chunk_ms)
            first = False
            out.put_nowait(b"\x00" * (len(item) * self.BYTES_PER_CHAR))

    async def send(self, context_id: str, text: str) -> None:
        self.sent.append((context_id, text))
        if context_id in self._work:
            self._work[context_id].put_nowait(text)

    async def flush(self, context_id: str) -> None:
        if context_id in self._work:
            self._work[context_id].put_nowait(None)

    async def cancel(self, context_id: str) -> None:
        self.cancelled.append((context_id, time.perf_counter()))
        w = self._workers.pop(context_id, None)
        if w:
            w.cancel()
        q = self._queues.pop(context_id, None)
        self._work.pop(context_id, None)
        if q is not None:
            q.put_nowait(None)

    async def audio(self, context_id: str) -> AsyncIterator[bytes]:
        q = self._queues.get(context_id)
        if q is None:
            return
        while True:
            item = await q.get()
            if item is None:
                return
            yield item

    async def synthesize(self, text: str) -> bytes:
        self.synthesized.append(text)
        await self.lat.sleep(self.lat.tts_first_byte_ms)
        return b"\x01" * (len(text) * self.BYTES_PER_CHAR)

    async def aclose(self) -> None:
        for w in self._workers.values():
            w.cancel()


class FakeAudioOut:
    """Plays in real time (scaled): each 20 ms slice takes 20 ms x scale."""

    def __init__(self, frame_ms: float = 20.0, scale: float = 1.0) -> None:
        self.frame_ms, self.scale = frame_ms, scale
        self.writes: list[tuple[float, int]] = []
        self.stops: list[float] = []

    async def write(self, pcm: bytes) -> None:
        self.writes.append((time.perf_counter(), len(pcm)))
        await asyncio.sleep(self.frame_ms * self.scale / 1000.0)

    def stop(self) -> None:
        self.stops.append(time.perf_counter())


# -- the rest of the core ------------------------------------------------------------------------------------------
@dataclass
class FakeEvents:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def publish(self, type: str, data: Mapping[str, Any]) -> None:
        self.events.append((type, dict(data)))

    def of(self, type: str) -> list[dict[str, Any]]:
        return [d for t, d in self.events if t == type]


@dataclass
class FakeCommands:
    ran: list[Command] = field(default_factory=list)

    async def run(self, command: Command) -> None:
        self.ran.append(command)


@dataclass
class FakeApprovals:
    current: PendingApproval | None = None

    def pending(self) -> PendingApproval | None:
        return self.current


async def say(pipeline: Any, frames: list[InputAudioRawFrame], *, frame_ms: float = 20.0,
              scale: float = 1.0) -> None:
    """Feed frames at (scaled) real-time pace."""
    for f in frames:
        await pipeline.queue_frame(f)
        await asyncio.sleep(frame_ms * scale / 1000.0)


async def drain(seconds: float = 0.0) -> None:
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.sleep(seconds)


@dataclass
class Rig:
    """A whole pipeline wired to fakes (tests and the scripted latency run)."""

    session: Any
    pipeline: Any
    lat: FakeLatencies
    llm: FakeAnthropic
    tts: FakeTts
    out: FakeAudioOut
    events: FakeEvents
    commands: FakeCommands
    approvals: FakeApprovals
    keyed: FakeKeyed
    talker: Any
    phrases: Any

    async def say(self, frames: list[InputAudioRawFrame]) -> str | None:
        """Speak an utterance; return its turn id."""
        before = self.session.user_turn
        tid = None
        for f in frames:
            await self.pipeline.queue_frame(f)
            if tid is None and self.session.user_turn not in (None, before):
                tid = self.session.user_turn
            await asyncio.sleep(self.session.config.frame_ms * self.lat.scale / 1000.0)
        return tid or self.session.user_turn or self.session.responding

    async def turn(self, frames: list[InputAudioRawFrame], timeout: float = 10.0) -> str:
        """Speak and wait until the answer has finished playing."""
        tid = await self.say(frames)
        assert tid is not None
        await self.session.wait_turn(tid, timeout)
        return tid

    async def close(self) -> None:
        await self.session.settled()
        await self.pipeline.stop()
        await self.tts.aclose()


def make_rig(*, scale: float = 0.02, lat: FakeLatencies | None = None, config: Any = None,
             reply: Callable[[str], str] | None = None, phrase_dir: Any = None, now: Any = None,
             spend: Any = None, script: Callable[[dict], Any] | None = None, tools: Any = None) -> Rig:
    from datetime import datetime

    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.phrases import PhraseCache
    from jarvis.voice.pipeline import build_pipeline
    from jarvis.voice.router_t0 import RouterT0
    from jarvis.voice.session import VoiceSession
    from jarvis.voice.talker_t1 import TalkerT1

    lat = lat or FakeLatencies(scale=scale)
    cfg = config or VoiceConfig(voice_id="fake-voice")
    events, commands, approvals, keyed = FakeEvents(), FakeCommands(), FakeApprovals(), FakeKeyed()
    session = VoiceSession(cfg, events=events, spend=spend)
    session.orb_time_scale = lat.scale
    llm = FakeAnthropic(lat, reply, script=script)
    tts = FakeTts(lat)
    out = FakeAudioOut(cfg.frame_ms, lat.scale)
    talker = TalkerT1(cfg, keyed, client_factory=llm.factory, tools=tools)
    router = RouterT0(now=now or (lambda: datetime(2026, 11, 15, 16, 12)), clock=session.clock,
                      approvals=approvals, approval_window_s=cfg.approval_window_s)
    phrases = None
    if phrase_dir is not None:
        phrases = PhraseCache(phrase_dir, voice_id=cfg.voice_id, model=cfg.tts_model, settings=cfg.voice_settings,
                              output_format=cfg.tts_output_format, render=tts.synthesize)
    pipeline = build_pipeline(session, vad=FakeVad(), turn=FakeTurn(lat), stt=FakeStt(lat), router=router,
                              talker=talker, tts=tts, audio_out=out, commands=commands, phrases=phrases)
    return Rig(session, pipeline, lat, llm, tts, out, events, commands, approvals, keyed, talker, phrases)
