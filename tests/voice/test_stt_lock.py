"""v0.12.3: the speech engine is used by one thing at a time. On Laptop B two turns ended 0.6 s apart, a turn was
finalized in a worker thread while new audio went into the same stream, and sherpa-onnx aborted the whole core
("GetFrames 56 + 65 > 69"). The fake recognizer below fails the same way if it's ever used concurrently."""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import numpy as np

from jarvis.voice.adapters_real import SherpaNemotronStt


class Stream:
    def __init__(self, n):
        self.n, self.samples, self.finished, self.busy = n, 0, False, threading.Lock()

    def accept_waveform(self, rate, samples):
        if not self.busy.acquire(blocking=False):
            raise RuntimeError("native abort: stream used from two places at once")
        try:
            assert not self.finished, "audio after input_finished"
            self.samples += len(samples)
        finally:
            self.busy.release()

    def input_finished(self):
        self.finished = True


class Recognizer:
    def __init__(self):
        self.made = 0

    def create_stream(self):
        self.made += 1
        return Stream(self.made)

    def is_ready(self, stream):
        return stream.samples > 0 and not getattr(stream, "_done", False)

    def decode_stream(self, stream):
        if not stream.busy.acquire(blocking=False):
            raise RuntimeError("native abort: stream used from two places at once")
        try:
            time.sleep(0.02)                     # decoding takes a while, in a worker thread
            stream._done = True
        finally:
            stream.busy.release()

    def get_result(self, stream):
        stream._done = False
        return f"stream {stream.n}: {stream.samples} samples"


def make_stt():
    stt = SherpaNemotronStt.__new__(SherpaNemotronStt)
    stt._np, stt._rec = np, Recognizer()
    stt._stream = stt._rec.create_stream()
    stt._lock = asyncio.Lock()
    return stt


def test_overlapping_turn_ends_never_touch_a_stream_at_once():
    frame = SimpleNamespace(audio=np.zeros(320, dtype=np.int16).tobytes())

    async def main():
        stt = make_stt()
        stt._lock = asyncio.Lock()
        jobs = []
        for _ in range(3):  # audio, a turn ends, more audio, the next turn ends, all overlapping
            jobs += [asyncio.create_task(stt.accept(frame)) for _ in range(4)]
            jobs.append(asyncio.create_task(stt.finalize()))
        return await asyncio.gather(*jobs)

    out = asyncio.run(main())
    # each turn: its own stream with its 4 frames (1,280 samples) plus the 0.3 s flush (4,800)
    assert [o for o in out if o.endswith("6080 samples")] == [f"stream {n}: 6080 samples" for n in (1, 2, 3)]


class NoLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_without_the_lock_this_is_the_crash():
    """Proves the fake catches the Laptop B failure: the same calls with the lock removed collide."""
    frame = SimpleNamespace(audio=np.zeros(320, dtype=np.int16).tobytes())

    async def main():
        stt = make_stt()
        stt._lock = NoLock()
        jobs = [asyncio.create_task(stt.accept(frame)) for _ in range(4)] + [asyncio.create_task(stt.finalize())]
        return await asyncio.gather(*jobs, return_exceptions=True)

    out = asyncio.run(main())
    assert any(isinstance(o, (RuntimeError, AssertionError)) for o in out)


def test_back_to_back_turns_keep_their_own_words_in_order():
    """Turn B ends while turn A is still finalizing: B gets exactly its own audio, A's and B's transcripts come out
    in order, and the audio after B goes into the next turn."""
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.frames import InputAudioRawFrame, TranscriptionFrame, UserStoppedSpeakingFrame
    from jarvis.voice.pipeline import SttProcessor
    from jarvis.voice.processor import FrameProcessor
    from jarvis.voice.session import VoiceSession

    class WordStt:
        def __init__(self):
            self.words: list[str] = []

        async def accept(self, frame):
            self.words.append(frame.meta["w"])
            return " ".join(self.words)

        async def finalize(self):
            await asyncio.sleep(0.05)               # slow enough for the next turn to end meanwhile
            text, self.words = " ".join(self.words), []
            return text

    class Capture(FrameProcessor):
        def __init__(self, s):
            super().__init__(s)
            self.finals: list[tuple[str, str]] = []

        async def process_frame(self, frame):
            if isinstance(frame, TranscriptionFrame):
                self.finals.append((frame.turn_id, frame.text))

    async def main():
        session = VoiceSession(VoiceConfig(voice_id="x"))
        stt = SttProcessor(session, WordStt())
        cap = Capture(session)
        stt.link(cap)

        def _frame(w, turn):
            fr = InputAudioRawFrame(audio=b"\0\0", meta={"w": w})
            fr.turn_id = turn
            return fr

        for w in ("what", "time"):
            await stt.process_frame(_frame(w, "A"))
        await stt.process_frame(UserStoppedSpeakingFrame(turn_id="A"))
        for w in ("is", "it"):                       # B's words arrive while A is finalizing
            await stt.process_frame(_frame(w, "B"))
        await stt.process_frame(UserStoppedSpeakingFrame(turn_id="B"))
        await stt.process_frame(_frame("next", "C"))  # after B: belongs to the next turn
        await asyncio.sleep(0.3)
        return cap.finals, stt.stt.words

    finals, left = asyncio.run(main())
    assert finals == [("A", "what time"), ("B", "is it")]
    assert left == ["next"]
