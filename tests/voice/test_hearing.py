"""v0.12.3: the mic profile the voice window uses, the Hearing check's scoring, and the glow range it gives the core."""
from __future__ import annotations

import numpy as np
import pytest

from jarvis.voice import mic_profile
from jarvis.voice.hearing_check import frame_db, process, word_errors


def test_word_errors_counts_words_not_letters():
    assert word_errors("When is my next chemistry lab due", "when is my next chemistry lab due") == 0
    assert word_errors("When is my next chemistry lab due", "when is my chemistry lab do") == 2
    assert word_errors("Open my lecture notes", "") == 4


def test_profile_round_trip_and_glow_range(tmp_path):
    assert mic_profile.load(tmp_path)["profile"] == "boost"          # nothing saved: the v0.9 boost
    mic_profile.save("agc", -58.24, -27.9, tmp_path)
    cal = mic_profile.load(tmp_path)
    assert (cal["profile"], cal["floor_db"], cal["speech_db"]) == ("agc", -58.2, -27.9)
    assert mic_profile.glow(cal) == {"quiet_db": -52.2, "loud_db": -24.9}
    assert mic_profile.glow({"floor_db": -40, "speech_db": -35}) is None  # voice barely above the room: no guess
    (tmp_path / "voice" / "mic.json").write_text("{broken", encoding="utf-8")
    assert mic_profile.load(tmp_path)["profile"] == "boost"


def test_every_profile_runs_and_the_boost_lifts_a_quiet_voice():
    """Auto-gain only reacts to what its own detector calls speech, which a synthetic tone isn't reliably: whether it
    beats the boost is for his real voice to decide (that's the Hearing check)."""
    pytest.importorskip("pywebrtc_audio")
    t = np.arange(16000 * 8) / 16000  # auto-gain ramps up over a few seconds (the check records ~21 s)
    env = (np.sin(2 * np.pi * 4 * t) > 0).astype(float)
    sig = sum(np.sin(2 * np.pi * f * t) for f in (180, 360, 540, 900, 1800)) * env
    sig = sig / np.sqrt(np.mean(sig[env > 0] ** 2)) * 32768 * 10 ** (-48 / 20)
    raw = np.clip(sig, -32768, 32767).astype(np.int16)
    for name, profile in mic_profile.PROFILES.items():
        out = process(np, raw, profile)
        assert out is not None and abs(len(out) - len(raw)) < 400, name
        if name == "boost":
            assert np.percentile(frame_db(np, out[-16000 * 2:]), 90) > -34   # 14+ dB louder than it came in


def test_the_glow_range_follows_his_hearing_check():
    import asyncio

    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.session import VoiceSession, level_of

    def tone(db):
        t = np.arange(320) / 16000
        return (np.sin(2 * np.pi * 300 * t) * 32768 * 10 ** (db / 20) * np.sqrt(2)).astype(np.int16).tobytes()

    quiet_voice = tone(-44)
    assert level_of(quiet_voice) < 0.25                         # the old fixed range: a laptop-mic voice barely lit it
    events = []

    class Events:
        async def publish(self, type, data):
            events.append(data)

    s = VoiceSession(VoiceConfig(voice_id="x"), events=Events())
    s.set_level_range(-62.0, -41.0)                             # from his check: room -68 dBFS, voice -44 dBFS
    s.set_level_range("junk", None)                             # nonsense is ignored
    s.set_level_range(-30.0, -28.0)                             # too narrow to trust: ignored
    assert s.level_range == (-62.0, -41.0)
    asyncio.run(s.show_level("listening", quiet_voice))
    assert events[-1]["level"] >= 0.8                           # his normal voice now fills the glow
    s._level_at = -1e9
    asyncio.run(s.show_level("speaking", quiet_voice))
    assert events[-1]["level"] < 0.25                           # Jarvis's own voice keeps the fixed range
