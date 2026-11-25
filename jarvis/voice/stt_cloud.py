"""Hearing through ElevenLabs instead of this laptop's processor (v0.25.0, his switch: Controls > Cloud hearing).

Why: on 22 Nov the laptop's own speech recognition ran up to three times slower than he spoke and fell 44 s behind,
and about 4 in 10 turns came out empty. ElevenLabs' live model (Scribe realtime, about 150 ms) writes his words down
on their side, so the laptop only has to pass the sound on.

What leaves the laptop when the switch is on: the sound of what he says to Jarvis (after the wake word or the talk
key; with neither set up, everything the mic hears as speech). Off, which is the default, nothing changes: his
voice is written down on the laptop and never leaves it.

Never a broken turn: `Hearing` keeps the sound of the turn in hand, and if ElevenLabs can't be reached, refuses the
key (it needs the Speech to Text permission) or stops answering, the same sound goes to the laptop's own model and
cloud hearing rests for a minute. Same three calls as the local model: accept, accept_many, finalize. T1.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import time
from collections.abc import Mapping
from typing import Any

log = logging.getLogger("jarvis.voice.stt")
URL = ("wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime&language_code=en"
       "&audio_format=pcm_16000&commit_strategy=manual")
SAMPLE_RATE = 16_000
FINAL_WAIT_S = 2.0     # how long finalize waits for the committed text before it settles for the last partial
REST_S = 60.0          # after a failure, the laptop's own hearing takes over for this long
ERRORS = ("error", "auth_error", "quota_exceeded", "transcriber_error", "input_error", "invalid_request",
          "unaccepted_terms", "rate_limited", "queue_overflow", "resource_exhausted")


async def _default_connect(url: str, headers: Mapping[str, str]) -> Any:
    import websockets  # noqa: PLC0415 - imported lazily: tests and the sandbox run without it

    return await websockets.connect(url, additional_headers=dict(headers), max_size=None, open_timeout=4)


class CloudStt:
    """One live transcription socket. Raises on any trouble; `Hearing` decides what happens then."""

    def __init__(self, keyed: Any, *, connect: Any = None, url: str = URL, final_wait_s: float = FINAL_WAIT_S) -> None:
        self.keyed, self._connect, self.url, self.final_wait_s = keyed, connect or _default_connect, url, final_wait_s
        self._ws: Any = None
        self._reader: asyncio.Task | None = None
        self._partial, self._final, self._problem = "", "", ""
        self._committed = asyncio.Event()
        self._sent = 0
        self.connects = 0

    async def _open(self) -> None:
        if self._ws is not None and (self._reader is None or not self._reader.done()):
            return
        await self.close()
        self._ws = await self.keyed.call(lambda key: self._connect(self.url, {"xi-api-key": key}))
        self.connects += 1
        self._problem = ""
        self._reader = asyncio.create_task(self._read(self._ws))

    async def _read(self, ws: Any) -> None:
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                kind = data.get("message_type")
                if kind == "partial_transcript":
                    self._partial = str(data.get("text") or "").strip()
                elif kind in ("committed_transcript", "committed_transcript_with_timestamps"):
                    self._final = str(data.get("text") or "").strip()
                    self._committed.set()
                elif kind in ERRORS:
                    self._problem = str(kind)
                    self._committed.set()
                    return
        except Exception as exc:  # noqa: BLE001 - a closed socket ends the reader; the next send notices
            self._problem = self._problem or type(exc).__name__
        finally:
            self._committed.set()

    async def send(self, pcm: bytes, commit: bool = False) -> str:
        """Pass sound on (16 kHz, 16-bit, mono). → the words so far in this turn."""
        await self._open()
        if self._problem:
            raise RuntimeError(self._problem)
        await self._ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(pcm).decode("ascii"),
                                        "commit": commit, "sample_rate": SAMPLE_RATE}))
        self._sent += len(pcm)
        return self._partial

    async def finalize(self) -> str:
        """End of his turn: ask for the settled text. Nothing sent means nothing asked."""
        if not self._sent:
            return ""
        self._committed.clear()
        await self.send(b"", commit=True)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._committed.wait(), self.final_wait_s)
        if self._problem:
            raise RuntimeError(self._problem)
        text = self._final or self._partial
        self._partial, self._final, self._sent = "", "", 0
        return text

    def forget(self) -> None:
        self._partial, self._final, self._sent = "", "", 0

    async def close(self) -> None:
        ws, reader, self._ws, self._reader = self._ws, self._reader, None, None
        if reader is not None:
            reader.cancel()
        if ws is not None:
            with contextlib.suppress(Exception):
                await ws.close()


class _Sound:
    """The turn's sound so far, shaped like the frames the local model takes."""

    def __init__(self, audio: bytes) -> None:
        self.audio = audio


class Hearing:
    """The pipeline's recognizer: the laptop's own model, or ElevenLabs when his switch is on and it is working."""

    def __init__(self, local: Any, cloud: CloudStt | None, *, on: bool = False, clock: Any = time.monotonic, rest_s: float = REST_S) -> None:
        self.local, self.cloud, self.on, self.clock, self.rest_s = local, cloud, bool(on), clock, rest_s
        self._turn: list[bytes] = []      # this turn's sound, kept until the turn ends so a failure loses nothing
        self._via_cloud = False           # how this turn is being heard
        self._in_turn = False             # sound has come in since the last finalize
        self._rest_until = 0.0
        self._lock = asyncio.Lock()       # sound and "that was the turn" keep their order
        self.fell_back = 0

    def _use_cloud(self) -> bool:
        if self._in_turn:                 # mid-turn: stay with whoever has the sound so far
            return self._via_cloud
        return bool(self.on and self.cloud is not None and self.clock() >= self._rest_until)

    async def _fall_back(self, why: Exception) -> str:
        """ElevenLabs let go mid-turn: the laptop hears the whole turn so far, and takes the next minute too."""
        self.fell_back += 1
        self._via_cloud, self._rest_until = False, self.clock() + self.rest_s
        log.warning("voice.cloud_hearing_failed", extra={"error": type(why).__name__, "reason": str(why)[:80]})
        if self.cloud is not None:
            self.cloud.forget()
            await self.cloud.close()
        sound, many = _Sound(b"".join(self._turn)), getattr(self.local, "accept_many", None)
        return await (many([sound]) if many is not None else self.local.accept(sound))

    async def accept_many(self, frames: list) -> str:
        async with self._lock:
            return await self._take(frames)

    async def _take(self, frames: list) -> str:
        pcm = b"".join(f.audio for f in frames)
        cloud = self._via_cloud = self._use_cloud()
        self._in_turn = True
        if not cloud:
            many = getattr(self.local, "accept_many", None)
            if many is not None:
                return await many(frames)
            text = ""
            for f in frames:
                text = await self.local.accept(f)
            return text
        self._turn.append(pcm)
        try:
            return await self.cloud.send(pcm)
        except Exception as exc:  # noqa: BLE001 - any trouble there: the laptop takes the turn
            return await self._fall_back(exc)

    async def accept(self, frame: Any) -> str:
        return await self.accept_many([frame])

    async def finalize(self) -> str:
        async with self._lock:
            return await self._end()

    async def _end(self) -> str:
        cloud = self._via_cloud and self._in_turn
        try:
            if cloud:
                try:
                    return await self.cloud.finalize()
                except Exception as exc:  # noqa: BLE001
                    await self._fall_back(exc)
            return await self.local.finalize()
        finally:
            self._turn, self._via_cloud, self._in_turn = [], False, False

    async def set_on(self, on: bool) -> None:
        self.on, self._rest_until = bool(on), 0.0
        if not on and self.cloud is not None and not (self._in_turn and self._via_cloud):
            await self.cloud.close()
