"""Shared state for one voice loop: the turn ids, who is speaking, the clock, the latency recorder, events."""

from __future__ import annotations

import array
import asyncio
import contextlib
import itertools
import logging
import math
import sys
import time
from collections.abc import Mapping
from typing import Any

from jarvis import review
from jarvis.health.latency import LatencyRecorder
from jarvis.health.spend import SpendMeter
from jarvis.voice.config import VoiceConfig
from jarvis.voice.ports import Clock, EventSink

log = logging.getLogger("jarvis.voice")

LEVEL_EVERY_S = 0.08
IDLE_HOLD_S = 0.4     # "idle" reaches the screen only if it's still true this much later (no close-and-reopen flicker)
QUIET_DB, LOUD_DB = -52.0, -16.0  # a voice level's range on the orb (dBFS after the mic boost)


def level_of(pcm: bytes, quiet_db: float = QUIET_DB, loud_db: float = LOUD_DB) -> float:
    """0-1 loudness of 16-bit PCM (RMS on a dB scale, so a soft voice still shows)."""
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    a = array.array("h", pcm[: n * 2])
    if sys.byteorder != "little":
        a.byteswap()
    rms = math.sqrt(sum(v * v for v in a) / n) / 32768.0
    if rms <= 0:
        return 0.0
    db = 20 * math.log10(rms)
    return min(1.0, max(0.0, (db - quiet_db) / (loud_db - quiet_db)))


class VoiceSession:
    def __init__(
        self,
        config: VoiceConfig | None = None,
        *,
        clock: Clock = time.perf_counter,
        recorder: LatencyRecorder | None = None,
        spend: SpendMeter | None = None,
        events: EventSink | None = None,
    ) -> None:
        self.config = config or VoiceConfig()
        self.clock = clock
        self.recorder = recorder or LatencyRecorder(clock)
        self.spend = spend or SpendMeter()
        self.events = events
        self._ids = itertools.count(1)
        self.user_turn: str | None = None       # the turn he is speaking now
        self.responding: str | None = None      # the turn Jarvis is answering now
        self.bot_speaking = False
        self.muted = False
        self.audio_ms = 0.0                      # input audio time (VAD/turn/speculation timing runs on this)
        self.heard_so_far = ""                   # this turn's words as they arrive (pace: how do they end?)
        self.speaking_since = -1e12              # input-audio time at which Jarvis last began to speak
        self.pace_scale = 1.0                    # his pace, as a factor on every wait (the learner sets it, step 2)
        self.barge_ins: list[float] = []         # ms from his first speech frame to audio stopped
        self.barge: dict | None = None           # a barge-in waiting to be confirmed ("confirm" mode)
        self.dropped_turns: set[str] = set()     # turns that were only noise/backchannel over Jarvis: never answered
        self.speaking_text = ""                  # what Jarvis is saying now (to tell his own echo from De Wet)
        self.duck: Any = None                    # audio out's duck(on) when it has one
        self.last_filler_at = -1e9
        self._level_at = -1e9
        self._level_peak = 0.0
        self.level_range = (QUIET_DB, LOUD_DB)   # the glow's dB range; the Hearing check tunes it to his voice
        self._done: dict[str, asyncio.Event] = {}
        self.interrupted: set[str] = set()       # turns he cut off (their late words are never spoken)
        self.live_turn: str | None = None        # the talker is still producing this turn's answer (tools running)
        self.audio_at = -1e9                     # when Jarvis's voice last went out
        self.shown = ""                          # the orb state on the screens now (see show_orb)
        self._idle_task: asyncio.Task[Any] | None = None
        self.client_levels_at = -1e9             # when the voice window last sent its own meter (set_levels)
        self.addressed = False                   # this turn came after "hey Jarvis" or the talk key: meant for him
        self.attentive = False                   # the voice window is awake and waiting for him to speak
        self.lag_ms = 0.0                        # how far behind real time the input side is running
        self.debug: Any = None                   # an opt-in conversation recorder (voice/diagnose.py); None = off

    def set_duck(self, on: bool) -> None:
        if self.duck is not None:
            try:
                self.duck(on)
            except Exception:  # noqa: BLE001 - ducking is cosmetic
                pass

    async def show_level(self, state: str, pcm: bytes) -> None:
        """The orb's glow follows the sound: the room and his voice, or Jarvis's voice while he speaks. The loudest
        of the last ~80 ms, about 12 times a second (contracts/orb_state: level 0-1).

        v0.14.0: this is the fallback for a voice window that doesn't send its own meter. A current one measures
        what its mic hears and what its speaker is playing right now and sends that (set_levels), because audio is
        sent to it up to 0.3 s ahead: measured here, Jarvis's glow ran ahead of his voice."""
        if self.clock() - self.client_levels_at < 1.0:
            return
        speaking = state == "speaking"
        await self._level(level_of(pcm) if speaking else level_of(pcm, *self.level_range), speaking=speaking,
                          state=state)

    async def set_levels(self, mic: object, out: object) -> None:
        """The voice window's own meter (0-1 each): its mic and what its speaker is playing this instant."""
        try:
            mic_l, out_l = min(1.0, max(0.0, float(mic))), min(1.0, max(0.0, float(out)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        self.client_levels_at = self.clock()
        speaking = self.shown == "speaking"
        self._level_peak, self._level_at = 0.0, -1e9   # the window already paces and peaks its meter
        await self._level(out_l if speaking else mic_l, speaking=speaking)

    async def _level(self, lvl: float, *, speaking: bool, state: str = "") -> None:
        if lvl > self._level_peak:
            self._level_peak = lvl
        now = self.clock()
        if now - self._level_at < LEVEL_EVERY_S:
            return
        self._level_at, peak, self._level_peak = now, self._level_peak, 0.0
        shown = self.shown or state
        if not shown or speaking != (shown == "speaking"):
            return   # between states: the next tick lands on the right one
        # always with the state the screens already show, so a meter tick can never change the orb's state
        await self.emit("orb.state", {"state": shown, "level": round(peak, 2)})

    def set_level_range(self, quiet_db: object, loud_db: object) -> None:
        """His voice's glow range (Hearing check): ignored unless it's a sane range."""
        try:
            q, top = float(quiet_db), float(loud_db)
        except (TypeError, ValueError):
            return
        if -90.0 <= q < top <= 0.0 and top - q >= 10.0:
            self.level_range = (q, top)

    def orb_state(self) -> str:
        """What the orb should show now, from what is actually going on. One rule for every caller.

        v0.14.0: he is talking -> listening comes before thinking and idle. Before, a bit of sound that turned out
        to be nothing sent "idle" while he was already talking again: the orb closed and reopened under his voice."""
        if self.muted:
            return "muted"
        if self.bot_speaking:
            return "speaking"
        if self.user_turn is not None:
            return "listening"
        if self.responding is not None:
            return "thinking"
        return "listening" if self.attentive else "idle"   # awake after "hey Jarvis" or with the talk key held

    async def show_orb(self, state: str | None = None) -> None:
        """Put the orb in ``state`` (default: whatever orb_state() says). Sent only when it changes.

        Idle (and muted) wait IDLE_HOLD_S and are sent only if still true: a turn that ends and another that starts
        a moment later never shows as close-then-open. Everything else shows at once (feedback <= 100 ms)."""
        state = state or self.orb_state()
        if state in ("idle", "muted"):
            if self.shown == state or (self._idle_task is not None and not self._idle_task.done()):
                return
            self._idle_task = asyncio.ensure_future(self._settle())
            return
        if self._idle_task is not None:
            self._idle_task.cancel()
            self._idle_task = None
        if state != self.shown:
            self.shown = state
            await self.emit("orb.state", {"state": state})

    async def _settle(self) -> None:
        try:
            await asyncio.sleep(IDLE_HOLD_S * self.orb_time_scale)
        except asyncio.CancelledError:
            return
        self._idle_task = None
        state = self.orb_state()
        if state != self.shown:
            self.shown = state
            await self.emit("orb.state", {"state": state})

    async def settled(self) -> None:
        """Wait for a pending "idle" to reach the screens (tests, shutdown)."""
        task = self._idle_task
        if task is not None and not task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await task

    orb_time_scale = 1.0   # tests shrink the idle hold with their other latencies

    def take_barge(self) -> str | None:
        """Confirm the waiting barge-in: returns the turn to interrupt (once)."""
        barge, self.barge = self.barge, None
        if barge is None or self.responding != barge["turn"]:
            return None
        self.barge_ins.append((self.clock() - barge["t0"]) * 1000.0)
        return barge["turn"]

    def new_turn(self) -> str:
        tid = f"turn-{next(self._ids)}"
        self.user_turn = tid
        self._done[tid] = asyncio.Event()
        return tid

    def end_user_turn(self, turn_id: str) -> None:
        if self.user_turn == turn_id:
            self.user_turn = None
        if self.barge is None:  # talking over Jarvis: he keeps the floor until it's confirmed as a barge-in
            self.responding = turn_id

    def finish_turn(self, turn_id: str | None, **notes: Any) -> None:
        """The turn is fully answered (or interrupted). Closes its latency trace."""
        if turn_id is None:
            return
        for k, v in notes.items():
            self.recorder.note(turn_id, k, v)
        if notes.get("interrupted"):
            self.interrupted.add(turn_id)
            if len(self.interrupted) > 50:
                self.interrupted.pop()
        if self.debug is not None:
            self.debug.ended(turn_id, self.recorder.notes(turn_id), notes)
        trace = self.recorder.finish(turn_id)
        if trace is not None:
            log.info("turn", extra={"turn": turn_id, "kind": trace.kind, "ms": trace.ms})
            review.note("turn.timing", turn=turn_id, kind=trace.kind, ms=trace.ms, notes=trace.notes)
        if self.responding == turn_id:
            self.responding = None
        ev = self._done.get(turn_id)
        if ev is not None:
            ev.set()

    async def wait_turn(self, turn_id: str, timeout: float = 10.0) -> None:
        ev = self._done.setdefault(turn_id, asyncio.Event())
        await asyncio.wait_for(ev.wait(), timeout)

    async def emit(self, type: str, data: Mapping[str, Any]) -> None:
        """Publish a hub event (orb.state, caption.show). Never blocks the voice loop on a slow bus."""
        if self.events is None:
            return
        try:
            await self.events.publish(type, data)
        except Exception:  # the hub being down must never stop Jarvis talking
            log.warning("event publish failed", extra={"type": type})
