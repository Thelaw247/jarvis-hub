"""Audio in and out on a Windows laptop (sounddevice): the mic with an automatic boost, and the speakers.

Shared by the Laptop B talk test (talk.py) and the voice client (client.py) that streams to jarvis-core.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

FRAME_MS = 20
IN_RATE = 16_000
IN_BYTES = IN_RATE * 2 * FRAME_MS // 1000          # 640 bytes: 20 ms of 16 kHz mono int16


class MicBoost:
    """Automatic gain for a quiet laptop mic, so he can talk at a normal volume.

    Tracks the level of his speech (frames louder than the noise floor) and scales the audio so speech sits near
    -22 dBFS, by at most 8x (18 dB) and never below 1x. The gain moves slowly (it follows his voice over about a
    second) so it never pumps within a word, and the result is clipped to 16 bits. Silence and noise stay where
    they are relative to speech, so the voice detector and speech model just hear a louder, steadier voice."""

    TARGET = 32768 * 10 ** (-22 / 20)
    FLOOR = 32768 * 10 ** (-55 / 20)   # quieter than this is room noise, not him
    MAX_GAIN = 8.0

    def __init__(self) -> None:
        import numpy as np  # noqa: PLC0415

        self._np = np
        self.level = self.TARGET / 3.0   # a quiet laptop mic until it has heard him
        self.gain = 3.0

    def __call__(self, pcm: bytes) -> bytes:
        np = self._np
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
        if rms > self.FLOOR:
            self.level += 0.05 * (rms - self.level)          # ~1 s to follow his voice
        want = min(self.MAX_GAIN, max(1.0, self.TARGET / max(self.level, 1.0)))
        self.gain += 0.1 * (want - self.gain)
        return np.clip(x * self.gain, -32768, 32767).astype(np.int16).tobytes()


class EchoCanceller:
    """WebRTC AEC3 (pywebrtc-audio, the canceller in Chrome) on this laptop: removes Jarvis's own voice from the mic.

    The reference is exactly what the speaker played (Speaker hands it over), resampled 24 -> 16 kHz and queued;
    each 20 ms mic frame is processed as two 10 ms halves against the reference that was due then. AEC3 estimates
    the speaker-to-mic delay itself. Measured in the sandbox on a simulated laptop echo: ~57 dB of echo removed.
    While he and Jarvis talk at once it also suppresses part of his voice, so it's for noticing he's talking (to
    stop Jarvis); his words after Jarvis stops come through clean."""

    def __init__(self, out_rate: int = 24_000, **extra: object) -> None:
        """``extra``: AudioProcessor options from the mic profile (auto gain, noise suppression; mic_profile.py)."""
        import numpy as np  # noqa: PLC0415
        import pywebrtc_audio  # noqa: PLC0415

        self._np = np
        self._ap = pywebrtc_audio.AudioProcessor(sample_rate=IN_RATE, echo_cancellation=True, high_pass_filter=True,
                                                 **extra)
        self._out_rate = out_rate
        self._far = np.zeros(0, dtype=np.int16)

    @classmethod
    def available(cls) -> bool:
        try:
            import pywebrtc_audio  # noqa: F401, PLC0415
        except Exception:  # noqa: BLE001
            return False
        return True

    def played(self, pcm: bytes) -> None:
        np = self._np
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if not x.size:
            return
        n = int(x.size * IN_RATE / self._out_rate)
        y = np.interp(np.linspace(0, x.size - 1, n), np.arange(x.size), x).astype(np.int16)
        self._far = np.concatenate([self._far, y])[-IN_RATE:]  # at most a second queued

    def process(self, pcm: bytes) -> bytes:
        np = self._np
        near = np.frombuffer(pcm, dtype=np.int16)
        out = []
        for i in range(0, near.size - 159, 160):
            far = self._far[:160]
            self._far = self._far[160:]
            if far.size < 160:
                far = np.concatenate([far, np.zeros(160 - far.size, dtype=np.int16)])
            out.append(np.asarray(self._ap.process(near[i:i + 160].copy(), far), dtype=np.int16))
        return np.concatenate(out).tobytes() if out else pcm


class Speaker:
    """Jarvis's audio out: this laptop's speakers (sounddevice), through Playout (soft starts and stops, smooth
    ducking, an amplifier that stays awake; playout.py).

    v0.14.0: the sound card pulls audio from a callback instead of being written to, so a start, a stop or a gap is
    a short fade, never a click. What is actually played is handed to the echo canceller as its reference, so the
    mic can listen while he talks. ``level`` is how loud Jarvis is right now (the orb's glow)."""

    AHEAD_S = 0.3   # write() lets this much queue up before it waits (the standalone talk loop's pacing)

    def __init__(self, rate: int, device: Any = None, aec: Any = None,
                 loop: asyncio.AbstractEventLoop | None = None) -> None:
        import sounddevice as sd  # noqa: PLC0415

        from jarvis.voice.playout import Playout  # noqa: PLC0415

        self.rate = rate
        self.play = Playout(rate)
        self.last_write = 0.0
        self.aec = aec
        self._loop = loop
        if loop is None:
            with contextlib.suppress(RuntimeError):
                self._loop = asyncio.get_running_loop()

        self.trouble = 0    # times the sound card said it ran dry or overran (review recording reports the count)

        def want(outdata, frames, _time, _status) -> None:  # the audio thread
            if _status:
                self.trouble += 1
            block = self.play.pull(frames).tobytes()
            outdata[:] = block
            if self.aec is not None and self._loop is not None and self.play.active:
                # the canceller lives on the event loop (with the mic): hand it what was just played
                with contextlib.suppress(RuntimeError):
                    self._loop.call_soon_threadsafe(self.aec.played, block)

        self._stream = sd.RawOutputStream(samplerate=rate, channels=1, dtype="int16", device=device,
                                          blocksize=rate // 100, latency="low", callback=want)
        self._stream.start()

    @property
    def level(self) -> float:
        return self.play.level

    @property
    def playing(self) -> bool:
        return self.play.buffered_s > 0.0

    def duck(self, on: bool) -> None:
        self.play.duck(on)

    def feed(self, pcm: bytes) -> None:
        """Queue audio and return at once (the voice window: the core already paces what it sends)."""
        self.last_write = time.monotonic()
        self.play.feed(pcm)

    async def write(self, pcm: bytes) -> None:
        """Queue audio; wait only while more than AHEAD_S is already queued (the standalone loop plays in real
        time through this, so a barge-in stop lands before the whole answer is buffered)."""
        self.feed(pcm)
        ahead = self.play.buffered_s - self.AHEAD_S
        if ahead > 0:
            await asyncio.sleep(ahead)

    def remaining(self) -> float:
        """Seconds of his voice still to play."""
        return self.play.buffered_s + 0.05

    async def drain(self) -> None:
        """Wait until everything queued has been played."""
        while self.play.buffered_s > 0:
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.15)

    def stop(self) -> None:  # barge-in: a 15 ms fade, then what was still to come is dropped
        self.play.stop()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._stream.stop()
            self._stream.close()


class Mic:
    """This laptop's microphone as 20 ms frames of 16 kHz mono int16, delivered on the event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, device: Any = None, aec: Any = None,
                 boost: bool = True) -> None:
        import sounddevice as sd  # noqa: PLC0415

        self.aec = aec
        self.frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        self._loop = loop
        self.boost = MicBoost() if boost else (lambda pcm: pcm)

        self.trouble = 0    # times the sound card dropped mic input
        self.dropped = 0    # frames thrown away because this window fell behind

        def got(data, _frames, _time, _status) -> None:  # the audio thread
            if _status:
                self.trouble += 1
            self._loop.call_soon_threadsafe(self._put, bytes(data))

        self._stream = sd.RawInputStream(samplerate=IN_RATE, channels=1, dtype="int16", blocksize=IN_BYTES // 2,
                                         device=device, callback=got, latency="low")
        self._stream.start()

    def _put(self, data: bytes) -> None:
        if self.frames.full():
            self.frames.get_nowait()  # never fall behind: drop the oldest
            self.dropped += 1
        if self.aec is not None:
            data = self.aec.process(data)  # take Jarvis's own voice out before anything else hears it
        self.frames.put_nowait(self.boost(data))

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._stream.stop()
            self._stream.close()


class ConsoleFormat:
    """For the talk test and the client: the event name plus its codes, readable ("voice.tts_closed 1008: ...")."""

    FIELDS = ("code", "error", "status", "reason")

    def __init__(self) -> None:
        import logging  # noqa: PLC0415

        self._base = logging.Formatter("  [%(levelname)s] %(message)s")

    def format(self, record) -> str:  # noqa: ANN001
        extra = " ".join(str(getattr(record, f)) for f in self.FIELDS if getattr(record, f, ""))
        record.message = record.getMessage()
        return self._base.format(record) + (f" {extra}" if extra else "")


def setup_console_logging(log_file=None) -> None:  # noqa: ANN001
    """Warnings on the console with their reason (and to a file when given); Pipecat's debug chatter hidden."""
    import logging  # noqa: PLC0415
    import sys  # noqa: PLC0415

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ConsoleFormat())  # type: ignore[arg-type]
    handlers: list = [handler]
    if log_file is not None:
        with contextlib.suppress(Exception):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(ConsoleFormat())  # type: ignore[arg-type]
            handlers.append(fh)
    logging.basicConfig(level=logging.WARNING, handlers=handlers, force=True)
    with contextlib.suppress(Exception):
        from loguru import logger  # noqa: PLC0415

        logger.remove()
        logger.add(sys.stderr, level="WARNING")
