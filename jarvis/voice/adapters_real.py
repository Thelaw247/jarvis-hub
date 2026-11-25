"""Real adapters for Laptop B: Silero VAD and Smart Turn v3 (through Pipecat's analyzers) and Nemotron
streaming STT (sherpa-onnx). Every heavy import is inside a constructor, so importing this module never needs
the packages or the models. Not exercised in the sandbox: they run for the first time in the M0.2 benchmark
on Laptop B (see jarvis/voice/README.md for the versions to install).

Input audio is 16 kHz mono 16-bit PCM in 20 ms frames (640 bytes), sent by the client on Laptop A after the
wake word or push-to-talk.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

SAMPLE_RATE = 16_000


def _need(module: str, package: str) -> Any:
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - depends on the machine
        raise RuntimeError(f"{package} is not installed (see jarvis/voice/README.md)") from exc


class SileroVad:
    """Speech yes/no from Pipecat's SileroVADAnalyzer, with Pipecat's own smoothing (v0.12.5).

    True only for confirmed speech: SPEAKING, and STOPPING (a pause shorter than stop_secs is still him talking).
    Before v0.12.5 start_secs and stop_secs were 0 and STARTING counted, so one stray 32 ms window started a turn
    and every short pause ended one (turn_tuning.py has the story and the settings)."""

    def __init__(self, confidence: float = 0.7, min_volume: float = 0.6, start_secs: float = 0.2,
                 stop_secs: float = 0.2, echo: tuple[float, float] | None = None) -> None:
        self._silero = _need("pipecat.audio.vad.silero", "pipecat-ai[silero]")
        self._vad = _need("pipecat.audio.vad.vad_analyzer", "pipecat-ai")
        self._states = self._vad.VADState
        self._analyzer = self._make(confidence, min_volume, start_secs, stop_secs)
        # echo guard: a second, stricter detector used while Jarvis is speaking (strict = True); both hear every
        # frame so the switch is seamless. Silero costs ~1 ms per 32 ms window, so two is cheap.
        self._strict = self._make(echo[0], echo[1], start_secs, stop_secs) if echo else None
        self.strict = False

    def _make(self, confidence: float, min_volume: float, start_secs: float, stop_secs: float) -> Any:
        params = self._vad.VADParams(confidence=confidence, start_secs=start_secs, stop_secs=stop_secs,
                                     min_volume=min_volume)
        analyzer = self._silero.SileroVADAnalyzer(sample_rate=SAMPLE_RATE, params=params)
        analyzer.set_sample_rate(SAMPLE_RATE)  # pipecat 1.x sizes its window here (normally on StartFrame)
        return analyzer

    @classmethod
    def from_settings(cls, t: Any) -> SileroVad:
        echo = (t.echo_confidence, t.echo_min_volume) if getattr(t, "echo_guard", False) else None
        return cls(t.confidence, t.min_volume, t.start_s, t.stop_s, echo=echo)

    async def is_speech(self, frame: Any) -> bool:
        state = await self._analyzer.analyze_audio(frame.audio)
        if self._strict is not None:
            strict = await self._strict.analyze_audio(frame.audio)
            if self.strict:
                state = strict
        return state in (self._states.SPEAKING, self._states.STOPPING)


class SmartTurnV3:
    """End of turn from Pipecat's LocalSmartTurnAnalyzerV3 (bundled smart-turn-v3.2-cpu.onnx, ~12 ms on CPU)."""

    def __init__(self, model_path: Path | None = None, cpu_count: int = 1) -> None:
        mod = _need("pipecat.audio.turn.smart_turn.local_smart_turn_v3", "pipecat-ai")
        base = _need("pipecat.audio.turn.base_turn_analyzer", "pipecat-ai")
        self._complete = base.EndOfTurnState.COMPLETE
        kwargs: dict[str, Any] = {"cpu_count": cpu_count, "sample_rate": SAMPLE_RATE}
        if model_path is not None:
            kwargs["smart_turn_model_path"] = str(model_path)
        self._analyzer = mod.LocalSmartTurnAnalyzerV3(**kwargs)
        self._analyzer.set_sample_rate(SAMPLE_RATE)

    def append(self, frame: Any, is_speech: bool) -> None:
        self._analyzer.append_audio(frame.audio, is_speech)

    async def is_complete(self) -> bool:
        state, _metrics = await self._analyzer.analyze_end_of_turn()
        return state == self._complete

    def clear(self) -> None:
        self._analyzer.clear()


class SherpaNemotronStt:
    """Nemotron Speech Streaming EN 0.6B (int8) through sherpa-onnx's OnlineRecognizer (a streaming transducer).

    ``model_dir`` holds encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx and tokens.txt from
    sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25. Decoding runs in a worker thread.
    """

    def __init__(self, model_dir: Path, num_threads: int = 2, hotwords: Path | None = None) -> None:
        self._sherpa = _need("sherpa_onnx", "sherpa-onnx")
        self._np = _need("numpy", "numpy")
        d = Path(model_dir)
        kwargs: dict[str, Any] = dict(
            tokens=str(d / "tokens.txt"), encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"), joiner=str(d / "joiner.int8.onnx"),
            num_threads=num_threads, sample_rate=SAMPLE_RATE, feature_dim=80, decoding_method="greedy_search",
            enable_endpoint_detection=False,  # Smart Turn decides the end of the turn
        )
        if hotwords is not None:  # Life Tree aliases ("GE 122") as a word boost; needs modified_beam_search
            kwargs.update(hotwords_file=str(hotwords), decoding_method="modified_beam_search")
        self._rec = self._sherpa.OnlineRecognizer.from_transducer(**kwargs)
        self._stream = self._rec.create_stream()
        # One user of the recognizer at a time (v0.12.3). sherpa-onnx streams aren't thread-safe: on Laptop B a turn
        # was finalized in a worker thread while the next audio went into the same stream, the native feature code
        # aborted ("GetFrames 56 + 65 > 69") and took the whole core down mid-answer.
        self._lock = asyncio.Lock()

    def _decode(self, stream: Any) -> str:
        while self._rec.is_ready(stream):
            self._rec.decode_stream(stream)
        return str(self._rec.get_result(stream)).strip()

    async def accept(self, frame: Any) -> str:
        samples = self._np.frombuffer(frame.audio, dtype=self._np.int16).astype(self._np.float32) / 32768.0
        async with self._lock:
            stream = self._stream
            stream.accept_waveform(SAMPLE_RATE, samples)
            return await asyncio.to_thread(self._decode, stream)

    async def accept_many(self, frames: list) -> str:
        """Several frames at once (the worker's backlog): one hand-off to the model instead of one per 20 ms."""
        pcm = b"".join(f.audio for f in frames)
        samples = self._np.frombuffer(pcm, dtype=self._np.int16).astype(self._np.float32) / 32768.0
        async with self._lock:
            stream = self._stream
            stream.accept_waveform(SAMPLE_RATE, samples)
            return await asyncio.to_thread(self._decode, stream)

    async def finalize(self) -> str:
        tail = self._np.zeros(int(0.3 * SAMPLE_RATE), dtype=self._np.float32)  # flush the right context
        async with self._lock:
            stream, self._stream = self._stream, self._rec.create_stream()  # the next turn gets a fresh stream
            stream.accept_waveform(SAMPLE_RATE, tail)
            stream.input_finished()
            return await asyncio.to_thread(self._decode, stream)
