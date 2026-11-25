"""The Laptop B talk test (jarvis/voice/talk.py): it says plainly what's missing before it opens anything."""
import pytest

from jarvis.core.settings import CoreSettings
from jarvis.voice import talk


def test_no_voice_id_says_where_to_paste_it(tmp_path):
    with pytest.raises(SystemExit, match="Controls > Keys > Voice"):
        talk.build(tmp_path)


def test_no_speech_model_says_to_run_setup_voice(tmp_path):
    CoreSettings(tmp_path / "data" / "settings.json").set_voice_id("JBFqnCBsd6RMkjVDRZzb")
    with pytest.raises(SystemExit, match="setup-voice.bat"):
        talk.build(tmp_path)


def test_heard_stt_prints_what_it_heard(capsys):
    import asyncio

    class Stt:
        async def accept(self, frame):
            return "partial"

        async def finalize(self):
            return "what time is it"

    heard = talk.HeardStt(Stt())
    assert asyncio.run(heard.accept(None)) == "partial"
    assert asyncio.run(heard.finalize()) == "what time is it"
    assert "You: what time is it" in capsys.readouterr().out


def test_mic_boost_lifts_a_quiet_voice_without_touching_silence():
    import numpy as np

    boost = talk.MicBoost()
    quiet = (np.sin(np.arange(320) / 3) * 300).astype(np.int16).tobytes()   # about -44 dBFS
    for _ in range(100):                                                       # two seconds of him talking
        out = boost(quiet)
    level = float(np.sqrt(np.mean(np.frombuffer(out, np.int16).astype(np.float32) ** 2)))
    assert 1.0 < boost.gain <= talk.MicBoost.MAX_GAIN
    assert level > 300 * 0.7 * 4                                               # several times louder
    silence = boost(bytes(640))
    assert silence == bytes(640)                                               # digital silence stays silent
    loud = (np.sin(np.arange(320) / 3) * 30000).astype(np.int16).tobytes()
    assert np.abs(np.frombuffer(boost(loud), np.int16)).max() <= 32767        # clipped, never wrapped


def test_persona_sounds_like_jarvis_not_a_chatbot():
    from jarvis.voice.persona import PERSONA

    examples = PERSONA.split("# Examples of the register")[1]
    replies = [line.split(":", 1)[1].strip() for line in examples.splitlines() if line.startswith("Jarvis:")]
    assert len(replies) >= 10
    assert all(len(r.split()) <= 20 for r in replies)                          # short, like the films
    assert sum("sir" in r for r in replies) >= len(replies) // 2               # "sir" is part of the voice
    for banned in ("!", "happy to help", "what can i do", "how can i help", "anything else", "great question"):
        assert all(banned not in r.lower() for r in replies)


def test_now_card_gives_the_time_of_day():
    card = talk.now_card()
    assert card.startswith("# Now\n") and ("AM" in card or "PM" in card) and "Saskatoon" in card


def test_echo_canceller_removes_jarvis_from_the_mic():

    import numpy as np
    import pytest

    from jarvis.voice.audio_io import EchoCanceller

    if not EchoCanceller.available():
        pytest.skip("pywebrtc-audio not installed")
    # Jarvis's voice, speech-like: noise shaped into ~4 syllables a second (no model files needed); the mic hears it
    # 40 ms later through the room
    rng = np.random.default_rng(1)
    t = np.arange(24_000 * 4) / 24_000
    envelope = np.clip(np.sin(2 * np.pi * 4 * t), 0, None) ** 2
    voiced = np.convolve(rng.standard_normal(t.size), np.hanning(24), mode="same")
    far24 = (6000 * envelope * voiced / np.abs(voiced).max() * 3).clip(-32000, 32000).astype(np.int16)
    aec = EchoCanceller()
    far16 = np.interp(np.linspace(0, far24.size - 1, far24.size * 2 // 3), np.arange(far24.size), far24)
    echo = np.zeros_like(far16)
    echo[640:] = 0.5 * far16[:-640]
    out = []
    for i in range(0, far16.size - 319, 320):
        aec.played(far24[i * 3 // 2:(i + 320) * 3 // 2].tobytes())
        out.append(np.frombuffer(aec.process(echo[i:i + 320].astype(np.int16).tobytes()), np.int16))
    out = np.concatenate(out).astype(np.float32)
    half = out.size // 2
    erle = 10 * np.log10(np.mean(echo[half:out.size] ** 2) / max(np.mean(out[half:] ** 2), 1e-9))
    assert erle > 20, f"only {erle:.1f} dB of echo removed"
