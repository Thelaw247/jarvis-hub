"""The thin interfaces the voice pipeline talks to. Real adapters and fakes both implement these.

Nothing here imports Pipecat, sherpa-onnx, Anthropic or websockets, so the whole pipeline runs in tests with
no audio devices, no models and no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class KeyedClient(Protocol):
    """K1's ``jarvis.secrets.KeyedClient`` (``mgr.client("anthropic" | "elevenlabs")``), as voice code uses it.

    ``call(fn)`` leases the live key for one request, runs ``fn(key)``, and on a 401/403 from a just-swapped
    key falls back to the previous key and retries once. Requests already running finish on their key.
    Voice code passes the key straight into the SDK / socket headers and never logs or stores it.
    """

    async def call(self, fn: Callable[[str], Awaitable[T]]) -> T: ...


class EventSink(Protocol):
    """K0's event bus. ``type``/``data`` follow contracts/event.schema.json (orb.state, caption.show)."""

    async def publish(self, type: str, data: Mapping[str, Any]) -> None: ...


@dataclass(frozen=True)
class Command:
    """A T0 command for the executor (timers, volume, mute, open, approvals)."""

    name: str
    args: Mapping[str, Any] = field(default_factory=dict)


class CommandSink(Protocol):
    async def run(self, command: Command) -> None: ...


@dataclass(frozen=True)
class PendingApproval:
    id: str
    outward: bool          # sends or posts something to other people: only "send it" / "post it" count
    asked_at: float        # session clock seconds


class ApprovalBox(Protocol):
    """The approval queue (RUNTIME: approvals). The voice side only reads the open ask and answers it."""

    def pending(self) -> PendingApproval | None: ...


class Vad(Protocol):
    """Voice activity on one input frame (Silero on Laptop B; the client also gates locally)."""

    async def is_speech(self, frame: Any) -> bool: ...


class TurnDetector(Protocol):
    """End of turn (Smart Turn v3). Fed every frame; asked once the VAD hears silence."""

    def append(self, frame: Any, is_speech: bool) -> None: ...

    async def is_complete(self) -> bool: ...

    def clear(self) -> None: ...


class StreamingStt(Protocol):
    """Streaming speech to text (Nemotron via sherpa-onnx). Partials while he talks, a final at turn end."""

    async def accept(self, frame: Any) -> str:
        """Feed one frame, return the current partial (may be unchanged)."""
        ...

    async def finalize(self) -> str:
        """Finish the utterance and return the final text; resets for the next one."""
        ...


class LlmStream(Protocol):
    """The subset of ``anthropic.AsyncMessageStream`` the talker uses."""

    @property
    def text_stream(self) -> AsyncIterator[str]: ...

    async def get_final_message(self) -> Any: ...


class TtsPort(Protocol):
    """One warm streaming TTS connection with a context per turn (ElevenLabs multi-context socket)."""

    async def start(self) -> None: ...

    async def open(self, context_id: str) -> None: ...

    async def send(self, context_id: str, text: str) -> None: ...

    async def flush(self, context_id: str) -> None: ...

    async def cancel(self, context_id: str) -> None: ...

    def audio(self, context_id: str) -> AsyncIterator[bytes]: ...

    async def synthesize(self, text: str) -> bytes: ...

    async def aclose(self) -> None: ...


class AudioOut(Protocol):
    """Where Jarvis's audio goes (on Laptop B: the WebSocket to the client on Laptop A)."""

    async def write(self, pcm: bytes) -> None: ...

    def stop(self) -> None:
        """Drop anything buffered and go silent now (barge-in). Must not block."""
        ...


Clock = Callable[[], float]
WsConnect = Callable[[str, Mapping[str, str]], Awaitable[Any]]
