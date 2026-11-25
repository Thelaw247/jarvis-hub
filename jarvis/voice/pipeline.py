"""The voice pipeline graph (M0.4), in Pipecat's order:

    audio in -> VAD (Silero) -> Smart Turn v3 -> streaming STT (Nemotron) -> T0 router (on partials)
             -> T1 talker (Haiku 5.5, speculative start) -> TTS (ElevenLabs Flash v2.5, phrase cache) -> audio out

Every stage stamps the latency recorder: VAD end -> STT final -> route -> LLM first token -> TTS first byte
-> audio out. Barge-in: speech while Jarvis is answering sends an InterruptionFrame down the graph; audio out
goes silent at once, the LLM stream is cancelled and the TTS context closed.

All outside services are ports (jarvis.voice.ports); ``build_pipeline`` takes fakes in tests and the real
adapters on Laptop B.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from jarvis.voice import pace
from jarvis.voice.frames import (
    EndFrame,
    FillerFrame,
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    PhraseFrame,
    T0RoutedFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
    TTSStoppedFrame,
    TurnIncompleteFrame,
    UserPausedFrame,
    UserStoppedSpeakingFrame,
    UserTextFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from jarvis.voice.phrases import PhraseBook, PhraseCache
from jarvis.voice.ports import AudioOut, Command, CommandSink, StreamingStt, TtsPort, TurnDetector, Vad
from jarvis.voice.processor import FrameProcessor, Pipeline
from jarvis.voice.router_t0 import RouteResult, RouterT0, normalize
from jarvis.voice.session import VoiceSession
from jarvis.voice.talker_t1 import TalkerProcessor, TalkerT1

log = logging.getLogger("jarvis.voice")


class VadProcessor(FrameProcessor):
    """Silero VAD. Starts turns, detects barge-in, and says when silence starts and when it counts as a stop.

    Silence is counted in audio time (frames x frame_ms), as Silero does, so tests can feed frames fast.
    """

    def __init__(self, session: VoiceSession, vad: Vad) -> None:
        super().__init__(session)
        self.vad = vad
        self._speaking = False
        self._quiet_ms = 0.0
        self._stopped = True
        self._t0: float | None = None     # real time when this run of frames began (the lag meter)
        self._debug_at = -1e9
        self._fed_ms = 0.0
        self._last_at = -1e9

    async def process_frame(self, frame: Frame) -> None:
        if not isinstance(frame, InputAudioRawFrame):
            await super().process_frame(frame)
            return
        s = self.session
        # How far behind real time is the input side? (frames arrive 20 ms apart; if they're handled slower than
        # that, everything he says is heard late.) A gap in the frames (asleep, no talk key) starts the count again.
        now = s.clock()
        if self._t0 is None or now - self._last_at > 2.0:
            self._t0, self._fed_ms = now, 0.0
        self._last_at = now
        self._fed_ms += s.config.frame_ms
        s.lag_ms = max(0.0, (now - self._t0) * 1000.0 - self._fed_ms)
        if now - self._debug_at > 2.0:    # review recording, or the 20-minute test recording: only when he switched it on
            self._debug_at = now
            root = getattr(s.config, "core_root", "")
            if root:
                from jarvis import review  # noqa: PLC0415

                s.debug = review.tap(root, s.debug)
        if frame.meta.get("end_turn"):
            # the voice window stopped sending (went back to sleep, or closed): whatever turn is open ends here,
            # instead of hanging until the next frame arrives minutes later
            if s.user_turn is not None:
                self._speaking, self._stopped = False, True
                s.recorder.mark(s.user_turn, "vad_end")
                await self.push_frame(VADUserStoppedSpeakingFrame(turn_id=s.user_turn, forced=True))
            return
        if s.muted and not frame.ptt:
            return
        s.audio_ms += s.config.frame_ms
        if hasattr(self.vad, "strict"):
            self.vad.strict = s.bot_speaking   # the echo guard (turn_tuning.py), when it's on
        if frame.meta.get("ptt_down") and s.responding is not None:
            # push-to-talk pressed while Jarvis answers: that's him meaning to interrupt, no confirming needed
            turn, s.barge = s.responding, None
            s.set_duck(False)
            await self.push_frame(InterruptionFrame(turn_id=turn, reason="push_to_talk"))
        speech = await self.vad.is_speech(frame)
        if frame.ptt and not frame.meta.get("ptt_release"):
            speech = True  # key held: everything until release is one turn (v0.13.0)
        frame.meta["is_speech"] = speech
        if speech:
            self._quiet_ms = 0.0
            if not self._speaking:
                self._speaking, self._stopped = True, False
                if s.responding is not None and s.barge is None:  # barge-in: he talks while Jarvis answers
                    if s.config.barge_in_mode == "confirm":
                        # Not yet: a fan, a cough or "mm-hmm" must not throw away the answer. Duck at once if he's
                        # speaking; stop when it's clearly him (real words, or long speech over Jarvis's voice).
                        # While Jarvis is still thinking, only real words count; noise turns are dropped.
                        # v0.12.5: no duck on the first frame any more (a tap or his own echo made Jarvis go
                        # quiet): only once it has been speech for duck_after_ms (below)
                        s.barge = {"turn": s.responding, "t0": s.clock(), "speech_ms": 0.0, "quiet_ms": 0.0,
                                   "early": bool(s.config.patience and s.bot_speaking
                                                 and s.audio_ms - s.speaking_since <= pace.YIELD_WINDOW_MS)}
                    else:
                        started = s.clock()
                        await self.push_frame(InterruptionFrame(turn_id=s.responding))
                        s.barge_ins.append((s.clock() - started) * 1000.0)
                tid = s.user_turn or s.new_turn()
                s.recorder.clear(tid, "vad_end")  # he went on after a pause: the end of speech is later
                await s.show_orb()
                await self.push_frame(VADUserStartedSpeakingFrame(turn_id=tid))
        frame.turn_id = s.user_turn
        if s.debug is not None and frame.audio:
            s.debug.audio(frame.turn_id, frame.audio)
        if not s.bot_speaking and frame.audio:
            # the glow follows the room and his voice all the time, not only inside a turn (v0.14.0); a current
            # voice window sends its own meter instead and this does nothing (session.show_level)
            await s.show_level(s.shown, frame.audio)
        if s.barge is not None:
            b = s.barge
            if speech:
                b["speech_ms"] += s.config.frame_ms
                b["quiet_ms"] = 0.0
                if b["speech_ms"] >= s.config.duck_after_ms and s.bot_speaking and not b.get("ducked"):
                    b["ducked"] = True
                    s.set_duck(True)  # clearly talking: quieter at once (and again after a pause)
                    s.recorder.note(b["turn"], "ducks", int(s.recorder.get_note(b["turn"], "ducks", 0)) + 1)
                enough = pace.YIELD_AFTER_MS if b.get("early") else s.config.barge_confirm_ms
                if s.bot_speaking and b["speech_ms"] >= enough:
                    turn = s.take_barge()
                    if turn is not None and b.get("early"):
                        s.recorder.note(turn, "gave_way", True)   # he had more to say: Jarvis started too soon
                    if turn is not None:
                        await self.push_frame(InterruptionFrame(turn_id=turn))
            else:
                b["quiet_ms"] += s.config.frame_ms
                if b["quiet_ms"] >= s.config.barge_quiet_ms:  # a cough, an "mm-hmm", an echo: back to full volume
                    b["speech_ms"] = 0.0  # it has to be continuous talking to stop him (v0.11.2: some push-back)
                    b["ducked"] = False
                    s.set_duck(False)  # the final transcript decides whether it was a question (router)
        await self.push_frame(frame)
        if s.user_turn is None:
            return
        if frame.meta.get("ptt_release"):
            self._speaking, self._stopped = False, True     # push-to-talk: release is the end of turn
            s.recorder.mark(s.user_turn, "vad_end")
            await self.push_frame(VADUserStoppedSpeakingFrame(turn_id=s.user_turn, forced=True))
            return
        if not speech and not self._stopped:
            self._speaking = False
            self._quiet_ms += s.config.frame_ms
            await self.push_frame(UserPausedFrame(turn_id=s.user_turn))
            if self._quiet_ms >= s.config.vad_stop_ms:
                self._stopped = True
                s.recorder.mark(s.user_turn, "vad_end")
                await self.push_frame(VADUserStoppedSpeakingFrame(turn_id=s.user_turn))


class TurnProcessor(FrameProcessor):
    """Smart Turn v3: once the VAD stops, is the turn really over? If not, wait for more speech (with a cap)."""

    def __init__(self, session: VoiceSession, turn: TurnDetector, incomplete_timeout_ms: float = 1500.0) -> None:
        super().__init__(session)
        self.turn = turn
        self._waiting_ms: float | None = None
        self._timeout = incomplete_timeout_ms
        self._limit = incomplete_timeout_ms   # how long this pause may last (pace.patience_ms decides, v0.27.0)
        self._held: tuple[str, str] | None = None   # (turn, why): waiting after a "finished" verdict

    async def process_frame(self, frame: Frame) -> None:
        if isinstance(frame, InputAudioRawFrame):
            speech = bool(frame.meta.get("is_speech"))
            self.turn.append(frame, speech)
            await self.push_frame(frame)
            if self._waiting_ms is not None and frame.turn_id:
                self._waiting_ms = 0.0 if speech else self._waiting_ms + self.session.config.frame_ms
                if self._waiting_ms >= self._limit:
                    await self._complete(frame.turn_id)
            return
        if isinstance(frame, VADUserStartedSpeakingFrame):
            if self._waiting_ms is not None and self._held is not None:
                # he carried on after a pause the turn model called the end: before v0.27.0 Jarvis had answered here
                rec, turn = self.session.recorder, self._held[0]
                rec.note(turn, "carried_on", int(rec.get_note(turn, "carried_on", 0)) + 1)
            self._waiting_ms, self._held = None, None
            await self.push_frame(frame)
            return
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            await self.push_frame(frame)
            if frame.turn_id and frame.forced:   # push-to-talk release: over, at once (~250 ms saved)
                await self._complete(frame.turn_id)
            elif frame.turn_id:
                done = await self.turn.is_complete()
                wait, why = (0.0, "") if done else (self._timeout, "unfinished")
                if self.session.config.patience:
                    wait, why = pace.patience_ms(getattr(self.session, "heard_so_far", ""), smart_done=done,
                                                 unfinished_ms=self._timeout, scale=getattr(self.session, "pace_scale", 1.0))
                    rec = self.session.recorder
                    rec.note(frame.turn_id, "pauses", int(rec.get_note(frame.turn_id, "pauses", 0)) + 1)
                    rec.note(frame.turn_id, "end_why", why)
                    rec.note(frame.turn_id, "end_wait_ms", int(wait))
                if done and wait <= 0:
                    await self._complete(frame.turn_id)
                else:
                    self._waiting_ms, self._limit = 0.0, wait
                    self._held = (frame.turn_id, why) if done else None
                    if not done:
                        await self.push_frame(TurnIncompleteFrame(turn_id=frame.turn_id))
            return
        await super().process_frame(frame)

    async def _complete(self, turn_id: str) -> None:
        self._waiting_ms, self._held = None, None
        self.turn.clear()
        self.session.end_user_turn(turn_id)
        await self.session.show_orb()
        await self.push_frame(UserStoppedSpeakingFrame(turn_id=turn_id))


BACKCHANNELS = frozenset({
    "mm", "mhm", "mmhm", "mmhmm", "hmm", "hm", "uh", "uhhuh", "huh", "um", "umm", "er", "erm", "ah", "oh",
    "yeah", "yep", "yup", "okay", "ok", "right", "alright", "sure", "cool", "nice", "wow", "jarvis", "hey",
})


def meant_words(heard: str, speaking: str) -> int:
    """How many words in what the mic heard are really him: not listener noises, not Jarvis's own words leaking
    back through the speakers (echo the canceller missed)."""
    own = set(normalize(speaking).split())
    return sum(1 for w in normalize(heard).split() if w not in BACKCHANNELS and w not in own)


ANSWERS = frozenset({"yes", "yeah", "yep", "yup", "sure", "okay", "ok", "no", "nope", "nah", "please", "go", "do",
                     "cancel", "stop", "done", "correct", "right", "alright", "fine", "thanks", "not"})


def answers_him(heard: str, speaking: str) -> bool:
    """Jarvis just asked something and this is a short reply to it ("yeah", "no thanks", "go ahead"). One word is
    enough then: it isn't a listener noise, it's the answer. (v0.14.0: these were dropped as "mm-hmm" when they
    landed on the last word of his question.)"""
    if not speaking.rstrip().endswith("?"):
        return False
    words = normalize(heard).split()
    return 0 < len(words) <= 5 and any(w in ANSWERS for w in words)


PREROLL_MS = 600.0


class SttProcessor(FrameProcessor):
    """Streaming STT: partials while he talks; at the end of the turn, the last partial at once, then the final.

    v0.14.0: one worker reads a queue. Audio and "the turn ended" go in, in order, and only the worker touches the
    speech model. Before, every 20 ms frame waited on the model inside the same call that reads the microphone
    socket, so when the model ran slower than real time everything behind it (the voice detector, barge-in, the
    end of the turn) ran late too; a turn's final words once took 19 s. Now the mic side never waits: when the
    model falls behind, the worker takes all the audio that is waiting in one go and catches up.
    """

    def __init__(self, session: VoiceSession, stt: StreamingStt) -> None:
        super().__init__(session)
        self.stt = stt
        self._partial = ""
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._worker: asyncio.Task[Any] | None = None
        self._work_s = 0.0      # time the model spent on this turn's audio...
        self._audio_s = 0.0     # ...and how much audio that was: work/audio > 1 means slower than he talks
        # Pre-roll: the VAD needs a moment to call speech, so the first word starts before the turn does. The last
        # PREROLL_MS of audio before a turn is fed to the STT when the turn starts ("After early nightfall…").
        self._preroll: deque[InputAudioRawFrame] = deque(maxlen=max(1, int(PREROLL_MS // session.config.frame_ms)))

    def _put(self, item: Any) -> None:
        self._queue.put_nowait(item)
        if self._worker is None or self._worker.done():
            self._worker = self.spawn(self._work())

    async def process_frame(self, frame: Frame) -> None:
        if isinstance(frame, InputAudioRawFrame):
            if frame.turn_id is None:
                self._preroll.append(frame)
                return
            while self._preroll:  # the turn just started: what came just before it first
                self._put(self._preroll.popleft())
            self._put(frame)
            return
        if isinstance(frame, UserStoppedSpeakingFrame):
            self._put((frame, self.session.clock()))
            return
        await super().process_frame(frame)

    async def _work(self) -> None:
        many = getattr(self.stt, "accept_many", None)
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if isinstance(item, tuple):
                await self._finalize(*item)
                continue
            batch = [item]
            while not self._queue.empty() and isinstance(self._queue._queue[0], InputAudioRawFrame):  # noqa: SLF001
                batch.append(self._queue.get_nowait())
            t0 = time.perf_counter()
            try:
                if many is not None:
                    text = await many(batch)
                else:
                    text = self._partial
                    for f in batch:
                        text = await self.stt.accept(f)
            except Exception as exc:  # noqa: BLE001 - one bad chunk must not end the worker (and with it, hearing)
                log.warning("voice.stt_failed", extra={"error": type(exc).__name__})
                continue
            self._work_s += time.perf_counter() - t0
            self._audio_s += len(batch) * self.session.config.frame_ms / 1000.0
            if text != self._partial:
                self._partial = text
                self.session.heard_so_far = text   # the turn logic reads how his words end (jarvis.voice.pace)
                await self.push_frame(InterimTranscriptionFrame(text=text, turn_id=batch[-1].turn_id))

    async def _finalize(self, frame: UserStoppedSpeakingFrame, asked_at: float) -> None:
        s = self.session
        frame.partial = self._partial
        await self.push_frame(frame)
        waited = (s.clock() - asked_at) * 1000.0
        if waited > 50.0:
            s.recorder.note(frame.turn_id, "stt_behind_ms", round(waited))  # the model was still catching up
        try:
            final = await self.stt.finalize()
        except Exception as exc:  # noqa: BLE001
            log.warning("voice.stt_failed", extra={"error": type(exc).__name__})
            final = self._partial
        s.recorder.mark(frame.turn_id, "stt_final")
        self._partial = ""
        s.heard_so_far = ""
        if self._audio_s >= 1.0:
            # how fast the model ran against his speech, as a percentage: 40 = comfortable, 100+ = it can't keep up
            pct = round(100.0 * self._work_s / self._audio_s)
            s.recorder.note(frame.turn_id, "stt_pct", pct)
            if pct >= 90:
                from jarvis.health.memory import memory  # noqa: PLC0415

                mem = memory() or (0, 0)
                log.warning("voice.hearing_slow", extra={"turn": frame.turn_id, "pct": pct, "free_mb": mem[0],
                                                          "mem_pct": mem[1]})
        self._work_s = self._audio_s = 0.0
        await self.push_frame(TranscriptionFrame(text=final, turn_id=frame.turn_id))


class RouterProcessor(FrameProcessor):
    """T0 router on partials. Safe commands fire at the end of the turn on the last partial; everything else
    waits for the final. Non-commands go to the talker."""

    def __init__(self, session: VoiceSession, router: RouterT0, commands: CommandSink | None,
                 phrases: PhraseBook | None = None) -> None:
        super().__init__(session)
        self.router = router
        self.commands = commands
        self.phrases = phrases or PhraseBook()
        self._last: tuple[str, RouteResult | None] = ("", None)
        self._fired: dict[str, str] = {}      # turn -> intent fired on the partial

    async def process_frame(self, frame: Frame) -> None:
        if isinstance(frame, InterimTranscriptionFrame):
            s = self.session
            # while Jarvis is still thinking, real words mean a new question at once; while he speaks it takes
            # ~1 s of continuous talking (VAD), so he doesn't stop for every word (his ask, v0.11.2)
            if (s.barge is not None and not s.bot_speaking
                    and meant_words(frame.text, s.speaking_text) >= s.config.barge_min_words):
                turn = s.take_barge()
                if turn is not None:
                    await self.push_frame(InterruptionFrame(turn_id=turn))
            res = self.router.route(frame.text)
            self._last = (frame.text, res)
            frame.t0_match = res is not None
            await self.push_frame(frame)
            return
        if isinstance(frame, UserStoppedSpeakingFrame):
            await self.push_frame(frame)
            text, res = self._last
            if res is not None and res.safe_on_partial and text == frame.partial and frame.turn_id:
                await self._fire(res, frame.turn_id, on_partial=True)
            return
        if isinstance(frame, TranscriptionFrame):
            turn = frame.turn_id
            self._last = ("", None)
            if turn is None:
                return
            if turn in self._fired:
                intent = self._fired.pop(turn)
                again = self.router.route(frame.text)
                if again is None or again.intent != intent:
                    self.session.recorder.note(turn, "partial_mismatch", True)
                return
            sess = self.session
            sess.recorder.note(turn, "words", len(frame.text.split()))
            if sess.lag_ms > 100.0:
                sess.recorder.note(turn, "lag_ms", round(sess.lag_ms))
            if sess.debug is not None:
                sess.debug.heard(turn, frame.text)
            if sess.barge is not None:  # he finished talking over Jarvis before it counted as a barge-in
                over_his_voice = sess.bot_speaking and sess.responding == sess.barge["turn"]
                real = not over_his_voice and meant_words(frame.text, sess.speaking_text) >= sess.config.barge_min_words
                if real or answers_him(frame.text, sess.speaking_text):
                    old = sess.take_barge()  # the words came late: it was a real question (or his answer) after all
                    if old is not None:
                        await self.push_frame(InterruptionFrame(turn_id=old))
                    sess.responding = turn
                else:  # noise, "mm-hmm", or his own echo: the answer carries on
                    sess.barge = None
                    sess.set_duck(False)
                    sess.dropped_turns.add(turn)
            if turn in self.session.dropped_turns:  # only noise or "mm-hmm" over Jarvis: not a question
                self.session.dropped_turns.discard(turn)
                self.session.finish_turn(turn, dropped=True)
                await self.session.show_orb()
                return
            if not frame.text.strip():  # heard sound but no words (a cough, a door): nothing to answer
                self.session.recorder.note(turn, "empty", True)
                self.session.finish_turn(turn)
                await self.session.show_orb()
                return
            res = self.router.route(frame.text)
            if res is not None:
                await self._fire(res, turn, on_partial=False)
            else:
                self.session.recorder.mark(turn, "route")
                self.session.recorder.kind(turn, "t1")
                await self.push_frame(UserTextFrame(text=frame.text, turn_id=turn))
            return
        await super().process_frame(frame)

    async def _fire(self, res: RouteResult, turn: str, *, on_partial: bool) -> None:
        s = self.session
        s.recorder.mark(turn, "route")
        s.recorder.kind(turn, "t0")
        s.recorder.note(turn, "intent", res.intent)
        s.recorder.note(turn, "routed_on_partial", on_partial)
        if on_partial:
            self._fired[turn] = res.intent
        await self.push_frame(T0RoutedFrame(intent=res.intent, turn_id=turn))
        if res.command is not None:
            await self._run(res.command)
        if res.reply:
            if self.phrases.is_phrase(res.reply):
                await self.push_frame(PhraseFrame(text=res.reply, turn_id=turn))
            else:
                await self.push_frame(TTSSpeakFrame(text=res.reply, turn_id=turn))
                await self.push_frame(LLMFullResponseEndFrame(turn_id=turn))
        else:
            s.finish_turn(turn)
            await s.show_orb()

    async def _run(self, cmd: Command) -> None:
        s = self.session
        if cmd.name == "mute":
            s.muted = True
        elif cmd.name == "unmute":
            s.muted = False
        if self.commands is not None:
            self.spawn(self.commands.run(cmd))  # the executor never holds up the voice loop


@dataclass
class _Ctx:
    turn_id: str
    cid: str = ""               # the TTS context's own id: the turn id, or turn.2, turn.3 when a turn needs another
    reader: asyncio.Task[Any] | None = None


class TtsProcessor(FrameProcessor):
    """Text to speech: one context per turn on the warm socket; cached phrases are read from disk instead."""

    def __init__(self, session: VoiceSession, tts: TtsPort, cache: PhraseCache | None = None) -> None:
        super().__init__(session)
        self.tts = tts
        self.cache = cache
        self._ctx: _Ctx | None = None
        self._opened: dict[str, int] = {}   # turn -> how many TTS contexts it has had

    async def process_frame(self, frame: Frame) -> None:
        s = self.session
        if isinstance(frame, VADUserStartedSpeakingFrame):
            # He started talking: make sure the TTS socket is open while he speaks, so a socket ElevenLabs closed
            # while idle costs nothing on the answer.
            self.spawn(self._warm())
            await self.push_frame(frame)
            return
        if isinstance(frame, TTSSpeakFrame):
            if frame.turn_id != s.responding:
                if (s.responding is None and s.user_turn is None and frame.turn_id == s.live_turn
                        and frame.turn_id not in s.interrupted):
                    # his voice ran out before the words did (a tool took a while): it's still this turn's answer.
                    # Before v0.14.0 these words were shown as a caption and never spoken.
                    s.responding = frame.turn_id
                else:
                    s.recorder.note(frame.turn_id, "unspoken", True)
                    return  # an interrupted turn's leftovers
            try:
                ctx = await self._context(frame.turn_id)
                await self.tts.send(ctx.cid, frame.text)
            except Exception:  # the voice service is down: show the answer instead of hanging on "thinking"
                self._ctx = None
                log.warning("voice.tts_unavailable", extra={"turn": frame.turn_id})
                await s.emit("caption.show", {"text": frame.text.strip(), "ttl_ms": 8000})
                s.finish_turn(frame.turn_id, tts_failed=True)
                await s.show_orb()
                return
            s.spend.record_tts(s.config.tts_model, len(frame.text))
            return
        if isinstance(frame, LLMFullResponseEndFrame):
            if self._ctx is not None and self._ctx.turn_id == frame.turn_id:
                await self.tts.flush(self._ctx.cid)
                self._ctx = None
            elif frame.turn_id == s.responding:
                await self.push_frame(TTSStoppedFrame(turn_id=frame.turn_id))
            return
        if isinstance(frame, PhraseFrame):
            await self._phrase(frame)
            return
        if isinstance(frame, FillerFrame):
            audio = self.cache.get(frame.text) if self.cache is not None else None
            if audio is not None and frame.turn_id == s.responding:
                s.recorder.note(frame.turn_id, "filler", frame.text)
                await self.push_frame(TTSAudioRawFrame(audio=audio, cached=True, turn_id=frame.turn_id))
            return
        if isinstance(frame, InterruptionFrame):
            ctx, self._ctx = self._ctx, None
            if ctx is not None:
                if ctx.reader:
                    ctx.reader.cancel()
                self.spawn(self.tts.cancel(ctx.cid))  # the socket write happens after audio is stopped
            await self.push_frame(frame)
            return
        await super().process_frame(frame)

    async def _warm(self) -> None:
        with contextlib.suppress(Exception):
            await self.tts.start()

    async def _context(self, turn_id: str) -> _Ctx:
        if self._ctx is not None and self._ctx.turn_id == turn_id:
            return self._ctx
        n = self._opened[turn_id] = self._opened.get(turn_id, 0) + 1
        while len(self._opened) > 20:
            self._opened.pop(next(iter(self._opened)))
        ctx = self._ctx = _Ctx(turn_id, cid=turn_id if n == 1 else f"{turn_id}.{n}")
        await self.tts.open(ctx.cid)
        ctx.reader = self.spawn(self._read(ctx))
        return ctx

    async def _read(self, ctx: _Ctx) -> None:
        first = True
        async for chunk in self.tts.audio(ctx.cid):
            if first:
                self.session.recorder.mark(ctx.turn_id, "tts_first_byte")
                first = False
            await self.push_frame(TTSAudioRawFrame(audio=chunk, turn_id=ctx.turn_id))
        if self._ctx is ctx:
            self._ctx = None   # the voice service closed this one (it went quiet too long): more words get a new one
        await self.push_frame(TTSStoppedFrame(turn_id=ctx.turn_id))

    async def _phrase(self, frame: PhraseFrame) -> None:
        s = self.session
        if frame.turn_id != s.responding:
            return
        audio = self.cache.get(frame.text) if self.cache is not None else None
        if audio is not None:
            s.recorder.mark(frame.turn_id, "tts_first_byte")
            s.spend.record_cached_phrase()
            await self.push_frame(TTSAudioRawFrame(audio=audio, cached=True, turn_id=frame.turn_id))
            await self.push_frame(TTSStoppedFrame(turn_id=frame.turn_id))
            return
        # miss: speak it live now, render it for next time in the background
        await self.process_frame(TTSSpeakFrame(text=frame.text, turn_id=frame.turn_id))
        await self.process_frame(LLMFullResponseEndFrame(turn_id=frame.turn_id))
        if self.cache is not None:
            self.spawn(self.cache.ensure(frame.text))


class AudioOutProcessor(FrameProcessor):
    """Plays audio in ``frame_ms`` slices so a barge-in lands between slices (<= 20 ms of extra sound)."""

    def __init__(self, session: VoiceSession, out: AudioOut) -> None:
        super().__init__(session)
        self.out = out
        if hasattr(out, "duck"):
            session.duck = out.duck
        self._queue: asyncio.Queue[Frame] = asyncio.Queue()
        self._epoch = 0
        self._player: asyncio.Task[Any] | None = None
        self.stopped_at: float | None = None

    def _bytes_per_slice(self) -> int:
        c = self.session.config
        return max(2, int(c.tts_sample_rate * 2 * c.frame_ms / 1000))

    async def process_frame(self, frame: Frame) -> None:
        if isinstance(frame, TTSAudioRawFrame | TTSStoppedFrame):
            if frame.turn_id != self.session.responding:
                return
            if self._player is None or self._player.done():
                self._player = self.spawn(self._play())
            self._queue.put_nowait(frame)
            return
        if isinstance(frame, InterruptionFrame):
            self._epoch += 1
            while not self._queue.empty():
                self._queue.get_nowait()
            self.out.stop()
            self.stopped_at = self.session.clock()
            s = self.session
            s.bot_speaking = False
            s.finish_turn(frame.turn_id, interrupted=True)
            await s.show_orb()
            return
        if isinstance(frame, EndFrame):
            await self.cleanup()
            return
        await super().process_frame(frame)

    async def _play(self) -> None:
        s = self.session
        step = self._bytes_per_slice()
        while True:
            frame = await self._queue.get()
            epoch = self._epoch
            if isinstance(frame, TTSStoppedFrame):
                # the client is still playing what was sent ahead: stay "speaking" until his voice has really ended
                remaining = getattr(self.out, "remaining", None)
                left = remaining() if callable(remaining) else 0.0
                if left > 0:
                    await asyncio.sleep(left)
                    if epoch != self._epoch:  # talked over during the tail: the interruption already ended the turn
                        continue
                if s.bot_speaking:
                    s.bot_speaking = False
                if s.live_turn == frame.turn_id:
                    # the talker isn't done (a tool is running): he's thinking again, the turn stays open
                    await s.show_orb()
                    continue
                s.finish_turn(frame.turn_id)
                await s.show_orb()
                continue
            data = frame.audio
            # Did his voice run dry before this piece arrived? (gaps = "broken up" speech; counted per turn)
            ends = getattr(self.out, "playing_until", None)
            if s.bot_speaking and isinstance(ends, float) and ends > 0 and not frame.cached:
                gap = (time.monotonic() - ends) * 1000.0
                if gap > 60.0:
                    s.recorder.note(frame.turn_id, "gaps", int(s.recorder.get_note(frame.turn_id, "gaps", 0)) + 1)
                    s.recorder.note(frame.turn_id, "gap_ms", max(round(gap), int(s.recorder.get_note(frame.turn_id, "gap_ms", 0))))
            for i in range(0, len(data), step):
                if epoch != self._epoch:
                    break
                if not s.bot_speaking:
                    s.bot_speaking = True
                    s.speaking_since = s.audio_ms   # pace: was he cut in on right at the start?
                    s.recorder.mark(frame.turn_id, "audio_out")
                    await s.show_orb()
                    if epoch != self._epoch:
                        break
                await s.show_level("speaking", data[i:i + step])  # fallback meter; a current window sends its own
                await self.out.write(data[i:i + step])
                s.audio_at = s.clock()


def build_pipeline(
    session: VoiceSession,
    *,
    vad: Vad,
    turn: TurnDetector,
    stt: StreamingStt,
    router: RouterT0,
    talker: TalkerT1,
    tts: TtsPort,
    audio_out: AudioOut,
    commands: CommandSink | None = None,
    phrases: PhraseCache | None = None,
    book: PhraseBook | None = None,
    incomplete_ms: float = 1500.0,
) -> Pipeline:
    return Pipeline([
        VadProcessor(session, vad),
        TurnProcessor(session, turn, incomplete_timeout_ms=incomplete_ms),
        SttProcessor(session, stt),
        RouterProcessor(session, router, commands, book),
        TalkerProcessor(session, talker),
        TtsProcessor(session, tts, phrases),
        AudioOutProcessor(session, audio_out),
    ])


async def close_pipeline(pipeline: Pipeline) -> None:
    with contextlib.suppress(Exception):
        await pipeline.stop()
