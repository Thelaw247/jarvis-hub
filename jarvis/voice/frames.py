"""Frames that flow through the voice pipeline. Names follow Pipecat's (pipecat.frames.frames) so the graph
maps one to one onto a Pipecat pipeline; these are plain dataclasses so tests need no Pipecat install."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Frame:
    turn_id: str | None = field(default=None, kw_only=True)


@dataclass
class SystemFrame(Frame):
    """Handled at once, never queued behind data (Pipecat: SystemFrame)."""


@dataclass
class InputAudioRawFrame(Frame):
    audio: bytes = b""
    meta: dict[str, Any] = field(default_factory=dict)   # fakes carry their script here
    ptt: bool = False


@dataclass
class VADUserStartedSpeakingFrame(SystemFrame):
    pass


@dataclass
class UserPausedFrame(SystemFrame):
    """First quiet frame after speech: the speculative start may begin (no Pipecat equivalent)."""


@dataclass
class VADUserStoppedSpeakingFrame(SystemFrame):
    forced: bool = False   # push-to-talk released: the turn is over, no need to ask Smart Turn


@dataclass
class TurnIncompleteFrame(SystemFrame):
    """Smart Turn says he is still talking: cancel any speculative start."""


@dataclass
class UserStoppedSpeakingFrame(SystemFrame):
    """Smart Turn says the turn is over. ``partial`` is the last STT partial."""

    partial: str = ""


@dataclass
class InterimTranscriptionFrame(Frame):
    text: str = ""
    t0_match: bool = False          # set by the T0 router so the talker never speculates on a command


@dataclass
class TranscriptionFrame(Frame):
    text: str = ""


@dataclass
class UserTextFrame(Frame):
    """A finished user turn for the T1 talker."""

    text: str = ""


@dataclass
class T0RoutedFrame(Frame):
    intent: str = ""


@dataclass
class TTSSpeakFrame(Frame):
    text: str = ""


@dataclass
class PhraseFrame(Frame):
    """Speak a cached phrase from disk (falls back to TTS on a miss)."""

    text: str = ""


@dataclass
class FillerFrame(Frame):
    """A short "thinking" sound ("Mm.", "One moment.") played from the phrase cache while the answer is still coming.
    Unlike PhraseFrame it never ends the turn, and it's skipped (never synthesised live) if it isn't cached."""

    text: str = ""


@dataclass
class LLMFullResponseEndFrame(Frame):
    text: str = ""


@dataclass
class TTSAudioRawFrame(Frame):
    audio: bytes = b""
    cached: bool = False


@dataclass
class TTSStoppedFrame(Frame):
    """No more audio will come for this turn."""


@dataclass
class InterruptionFrame(SystemFrame):
    """Barge-in: stop speaking, cancel the LLM stream, close the TTS context."""

    reason: str = "barge_in"


@dataclass
class EndFrame(Frame):
    pass
