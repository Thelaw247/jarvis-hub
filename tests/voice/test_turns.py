"""v0.12.5: how Jarvis decides De Wet is talking. Pipecat's default set-up as the baseline, an echo guard while Jarvis
speaks, and the Conversation check's scoring."""
from __future__ import annotations

import asyncio
import json

import numpy as np
import pytest

from jarvis.voice import turn_tuning
from jarvis.voice.turn_check import SCRIPT, Turn, score, slots


def test_settings_default_load_and_fit(tmp_path):
    t = turn_tuning.load(tmp_path)
    assert t == turn_tuning.DEFAULT and t.echo_guard and (t.confidence, t.start_s, t.stop_s, t.min_volume) == (
        0.7, 0.2, 0.2, 0.6)                                         # Pipecat's own defaults
    assert (t.echo_confidence, t.echo_min_volume) == (0.85, 0.7)
    turn_tuning.save(turn_tuning.fitted(0.55, 0.88), "fitted", tmp_path)
    loaded = turn_tuning.load(tmp_path)
    assert loaded.min_volume == 0.66 and not loaded.echo_guard
    data = json.loads((tmp_path / "voice" / "turns.json").read_text())
    data.update(confidence=7, start_s="soon")                        # nonsense falls back field by field
    (tmp_path / "voice" / "turns.json").write_text(json.dumps(data))
    assert turn_tuning.load(tmp_path).confidence == 0.7 and turn_tuning.load(tmp_path).min_volume == 0.66
    assert turn_tuning.fitted(0.2, 0.3).min_volume == 0.45 and turn_tuning.fitted(0.8, 0.99).min_volume == 0.75


def test_the_check_counts_caught_split_missed_and_false():
    say = [(a, b) for k, _line, a, b in slots() if k == "say"]
    echo = next((a, b) for k, _line, a, b in slots() if k == "echo")
    turns = [Turn(say[0][0] + 0.5, say[0][0] + 2, "what's due this week"),
             Turn(say[1][0] + 0.5, say[1][0] + 1.5, "open my"),                      # split in two
             Turn(say[1][0] + 2.0, say[1][0] + 3, "chemistry lab manual"),
             Turn(echo[0] + 1.0, echo[0] + 2, "one moment"),                          # Jarvis heard himself
             Turn(say[2][0] + 0.5, say[2][0] + 1, "")]                                # an empty turn
    sc = score("x", turn_tuning.BASELINE, turns)
    n_lines = sum(1 for k, *_ in SCRIPT if k in ("say", "barge"))
    assert (sc.caught, sc.split, sc.echo) == (2, 1, 1)
    assert sc.missed == n_lines - 2 and sc.false == 2
    clean = score("y", turn_tuning.BASELINE, [turns[0], Turn(say[1][0] + 0.5, say[1][0] + 3, "open my chemistry lab manual")])
    assert clean.total < sc.total and (clean.split, clean.false, clean.echo) == (0, 0, 0)


def test_the_echo_guard_switches_with_jarvis_speaking():
    pytest.importorskip("pipecat.audio.vad.silero")
    from jarvis.voice.adapters_real import SileroVad
    from jarvis.voice.frames import InputAudioRawFrame

    plain, guarded = SileroVad.from_settings(turn_tuning.BASELINE), SileroVad.from_settings(turn_tuning.DEFAULT)
    assert plain._strict is None and guarded._strict is not None

    async def main():
        frame = InputAudioRawFrame(audio=np.zeros(320, dtype=np.int16).tobytes())
        guarded.strict = True
        return await guarded.is_speech(frame), await plain.is_speech(frame)

    assert asyncio.run(main()) == (False, False)                    # silence is silence either way
