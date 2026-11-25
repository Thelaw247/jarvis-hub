"""Voice settings: one place for model ids, the voice id, speaking rules and timings.

Everything a person might tune lives here so code never hard-codes a model or a voice. K0's core config
builds a ``VoiceConfig`` with ``VoiceConfig.from_mapping(...)``; tests use the defaults.

C38/C39: there is exactly one voice id, an original voice made with ElevenLabs Voice Design. The default is
empty on purpose: the pipeline refuses to open a real TTS connection until he has picked the voice (0.4).
He pastes it in the hub (Controls › Keys › Voice); the core keeps it in data\\settings.json (jarvis/core/settings.py),
whose `voice_id` key ``from_mapping`` picks up.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SpeakingRules:
    """When the talker hands text to TTS (VOICE design, speaking rules)."""

    first_chunk_min_words: int = 6      # first chunk at the first . ! ? , ; once >= this many words
    first_chunk_max_words: int = 12     # ...or this many words with no punctuation at all
    max_sentences: int = 2              # 1-2 spoken sentences; longer goes on the hub


@dataclass(frozen=True)
class SpeculationRules:
    """Speculative start of the LLM call on a stable STT partial."""

    enabled: bool = True
    stable_ms: float = 120.0            # the partial has not changed for this long
    min_words: int = 2                  # never speculate on one word
    max_per_turn: int = 2               # cap: speculative starts cost tokens


@dataclass(frozen=True)
class VoiceConfig:
    core_root: Path = Path("C:/Jarvis")
    # T1 talker (Anthropic Messages API, streaming, prompt caching)
    llm_model: str = "claude-haiku-5-5"
    llm_max_tokens: int = 600           # room for a tool call's arguments; the persona keeps what he says short
    history_turns: int = 6
    # TTS (ElevenLabs Flash v2.5 over one warm multi-context WebSocket)
    # Flash v2.5 on the TTS multi-context WebSocket. Eleven v4 Turbo is NOT served on this endpoint (only on the Text
    # to Dialogue WebSocket, which this client doesn't speak yet): v0.8.2 tried it and the handshake was refused.
    tts_model: str = "eleven_flash_v2_5"
    voice_id: str = ""                  # set once he picks the designed voice (C38/C39); never a clone
    tts_output_format: str = "pcm_24000"
    tts_sample_rate: int = 24000
    tts_url: str = "wss://api.elevenlabs.io"
    tts_keepalive_s: float = 10.0       # ElevenLabs closes idle sockets after ~20 s
    tts_inactivity_timeout_s: int = 180
    voice_settings: Mapping[str, Any] = field(
        default_factory=lambda: {"stability": 0.4, "similarity_boost": 0.8, "speed": 1.0}  # lower stability = a little more expressive
    )
    # Turn taking
    vad_stop_ms: float = 200.0          # Silero: silence before "stopped speaking"
    barge_in_budget_ms: float = 150.0   # his voice stops TTS within this
    # Barge-in, "confirm" mode (with the client's echo cancellation): his voice ducks Jarvis at once, and Jarvis stops
    # once it's clearly him and clearly meant: barge_min_words real words (not "mm-hmm", not Jarvis's own words
    # leaking through) or barge_confirm_ms of speech. "immediate" stops on the first speech frame (headphones).
    barge_in_mode: str = "immediate"
    # Pace (v0.27.0, jarvis.voice.pace): at a pause the turn model calls "finished", still wait a little, longer
    # when his words end mid-sentence. Off here so the pipeline's own timing tests stay exact; the core turns it on.
    patience: bool = False
    barge_confirm_ms: float = 1000.0
    barge_quiet_ms: float = 300.0       # he went quiet before it was confirmed: carry on at full volume
    duck_after_ms: float = 300.0        # speech over Jarvis this long (after the detector's own 0.2 s) ducks him
    barge_min_words: int = 2
    # Thinking filler: if Claude's first word hasn't arrived this long after he finished, play one short cached
    # filler in Jarvis's voice. 0 = off. At most one per turn, none within filler_gap_s of the last one.
    filler_after_ms: float = 0.0
    filler_gap_s: float = 20.0
    fillers: tuple[str, ...] = ("Mm.", "One moment.", "Let me see.")
    approval_window_s: float = 10.0     # T0 approval answers count within this window
    frame_ms: int = 20                  # audio out is written in 20 ms frames so a stop lands fast
    speaking: SpeakingRules = field(default_factory=SpeakingRules)
    speculation: SpeculationRules = field(default_factory=SpeculationRules)

    @property
    def phrase_dir(self) -> Path:
        """Rendered phrase audio lives under the core root, outside git."""
        return Path(self.core_root) / "data" / "voice" / "phrases"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> VoiceConfig:
        """Build from a plain mapping (K0's config file). Unknown keys are ignored."""
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in known}
        if "core_root" in kwargs:
            kwargs["core_root"] = Path(kwargs["core_root"])
        if isinstance(kwargs.get("speaking"), Mapping):
            kwargs["speaking"] = SpeakingRules(**kwargs["speaking"])
        if isinstance(kwargs.get("speculation"), Mapping):
            kwargs["speculation"] = SpeculationRules(**kwargs["speculation"])
        return cls(**kwargs)

    def with_(self, **changes: Any) -> VoiceConfig:
        return replace(self, **changes)
