"""A minimal frame-processor graph in Pipecat's shape (FrameProcessor.process_frame / push_frame, Pipeline).

Frames go downstream from the mic side to the speaker side. Barge-in starts at the VAD (the first stage),
so an ``InterruptionFrame`` reaches every later stage in one pass; each stage handles it without awaiting
network I/O, which keeps "his voice stops TTS" well inside 150 ms.

Long work (STT finalize, the LLM stream, the TTS socket, playback) runs in tasks so one slow stage never holds
up the frames behind it.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine, Sequence
from typing import Any

from jarvis.voice.frames import EndFrame, Frame
from jarvis.voice.session import VoiceSession


class FrameProcessor:
    def __init__(self, session: VoiceSession) -> None:
        self.session = session
        self._next: FrameProcessor | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    def link(self, nxt: FrameProcessor) -> FrameProcessor:
        self._next = nxt
        return nxt

    async def process_frame(self, frame: Frame) -> None:
        if isinstance(frame, EndFrame):
            await self.cleanup()
        await self.push_frame(frame)

    async def push_frame(self, frame: Frame) -> None:
        if self._next is not None:
            await self._next.process_frame(frame)

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def cleanup(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        for t in list(self._tasks):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t


class Pipeline:
    """Processors linked in order. ``queue_frame`` feeds the first one (Pipecat: PipelineTask.queue_frame)."""

    def __init__(self, processors: Sequence[FrameProcessor]) -> None:
        if not processors:
            raise ValueError("empty pipeline")
        self.processors = list(processors)
        for a, b in zip(self.processors, self.processors[1:], strict=False):
            a.link(b)

    async def queue_frame(self, frame: Frame) -> None:
        await self.processors[0].process_frame(frame)

    async def stop(self) -> None:
        await self.queue_frame(EndFrame())

    def get(self, cls: type) -> Any:
        return next(p for p in self.processors if isinstance(p, cls))
