"""v0.13.0: "hey Jarvis" and push-to-talk. The gate's timing, the wake word, and a held key as one turn."""
import asyncio
import os
from pathlib import Path

import pytest

from jarvis.voice.fakes import FakeLatencies, make_rig, utterance
from jarvis.voice.frames import InputAudioRawFrame
from jarvis.voice.gate import Gate

SCALE = 0.02


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


# ---- the gate: when the mic goes to the core ---------------------------------------------------------------------
def test_asleep_sends_nothing_and_hey_jarvis_wakes_it():
    g = Gate("wake", clock=Clock())
    assert not g.sending and g.listening_for_wake
    assert g.wake() == [{"type": "listen", "on": True}]
    assert g.sending and not g.listening_for_wake
    assert g.wake() == []   # a second "hey Jarvis" while awake changes nothing


def test_stays_awake_through_the_conversation_then_sleeps_after_the_follow_up_window():
    clock = Clock()
    g = Gate("wake", follow_up_s=8.0, clock=clock)
    g.wake()
    g.core("listening")
    clock.t += 30          # a long question and a long answer: still awake
    g.core("thinking")
    g.core("speaking")
    assert g.tick() == [] and g.sending
    g.core("idle")
    clock.t += 7.9
    assert g.tick() == [] and g.sending          # "and what about Friday?" needs no second "hey Jarvis"
    clock.t += 0.2
    assert g.tick() == [{"type": "listen", "on": False}]
    assert not g.sending and g.listening_for_wake


def test_saying_nothing_after_hey_jarvis_goes_back_to_sleep():
    clock = Clock()
    g = Gate("wake", follow_up_s=8.0, clock=clock)
    g.wake()
    clock.t += 8.1
    assert g.tick() == [{"type": "listen", "on": False}]


def test_jarvis_speaking_unprompted_wakes_it_so_yes_or_stop_works():
    g = Gate("wake", clock=Clock())
    assert g.jarvis_audio() == [{"type": "listen", "on": True}]
    assert g.sending


def test_the_talk_key_works_while_asleep_and_leaves_a_follow_up_window():
    clock = Clock()
    g = Gate("wake", follow_up_s=8.0, clock=clock)
    assert g.key(True) == [{"type": "ptt", "down": True}]
    assert g.sending
    assert g.key(True) == []                      # key repeat while held
    assert g.key(False) == [{"type": "ptt", "down": False}, {"type": "listen", "on": True}]
    assert g.sending                              # carry on hands-free for a bit (and the orb shows it)
    clock.t += 8.1
    assert g.tick() == [{"type": "listen", "on": False}]


def test_push_to_talk_mode_only_sends_while_the_key_is_held():
    g = Gate("ptt", clock=Clock())
    assert not g.sending and not g.listening_for_wake
    assert g.jarvis_audio() == [] and g.wake() == []
    g.key(True)
    assert g.sending
    g.key(False)
    assert not g.sending


def test_always_mode_is_the_old_behaviour():
    g = Gate("always", clock=Clock())
    assert g.sending and not g.listening_for_wake
    assert g.tick() == []


def test_a_wrong_mode_is_refused():
    with pytest.raises(ValueError):
        Gate("sometimes")


# ---- the wake word ---------------------------------------------------------------------------------------------
class FakeModel:
    def __init__(self, scores):
        self.scores = list(scores)
        self.resets = 0

    def predict(self, chunk):
        assert len(chunk) == 1280
        return {"hey_jarvis": self.scores.pop(0) if self.scores else 0.0}

    def reset(self):
        self.resets += 1


def test_the_wake_word_fires_once_per_hey_jarvis_and_keeps_the_words_after_it():
    from jarvis.voice import wake

    clock = Clock()
    model = FakeModel([0.01, 0.02, 0.9, 0.95, 0.01] + [0.0] * 30 + [0.8])
    w = wake.WakeWord(level=0.5, model=model, clock=clock)
    frame = bytes(640)    # 20 ms; four of them make one 80 ms chunk
    fired = []
    for _ in range(4 * 6):
        fired.append(w.feed(frame))
        clock.t += 0.02
    assert fired.count(True) == 1               # 0.9 then 0.95: one wake, not two (cooldown)
    assert model.resets == 1
    assert len(w.preroll()) == int(wake.PREROLL_S * 1000 / 20)
    assert w.preroll() == []
    clock.t += 2.0
    for _ in range(4 * 31):
        if w.feed(frame):
            break
    else:
        pytest.fail("the next 'hey Jarvis' after the cooldown didn't fire")


def test_the_threshold_can_be_tuned_but_not_to_nonsense(monkeypatch):
    from jarvis.voice import wake

    monkeypatch.setenv("JARVIS_WAKE_THRESHOLD", "0.35")
    assert wake.threshold() == 0.35
    monkeypatch.setenv("JARVIS_WAKE_THRESHOLD", "3")
    assert wake.threshold() == wake.THRESHOLD
    monkeypatch.setenv("JARVIS_WAKE_THRESHOLD", "loud")
    assert wake.threshold() == wake.THRESHOLD


def test_missing_models_mean_not_available(tmp_path):
    from jarvis.voice import wake

    assert not wake.available(tmp_path)


MODELS = Path(os.environ.get("JARVIS_WAKE_MODELS", "/tmp/wwm"))


@pytest.mark.skipif(not (MODELS / "hey_jarvis_v0.1.onnx").exists(), reason="openWakeWord models not downloaded")
def test_the_real_model_stays_quiet_on_silence_and_noise(tmp_path):
    import numpy as np

    from jarvis.voice import wake

    d = tmp_path / "voice" / "wakeword"
    d.mkdir(parents=True)
    for f in wake.FILES:
        (d / f).write_bytes((MODELS / f).read_bytes())
    assert wake.available(tmp_path)
    w = wake.WakeWord(tmp_path)
    rng = np.random.default_rng(7)
    noise = (rng.normal(0, 800, 16000 * 4)).astype(np.int16).tobytes()
    fired = [w.feed(noise[i:i + 640]) for i in range(0, len(noise), 640)]
    assert not any(fired) and w.score < 0.2


# ---- push-to-talk in the pipeline ------------------------------------------------------------------------------
def test_holding_the_key_through_a_pause_is_one_turn_with_every_word():
    """Hands-free, a long pause splits the sentence. With the key held it's one turn, and release ends it at once."""
    async def main():
        rig = make_rig(scale=SCALE)
        frames = utterance("remind me to call mom tomorrow", ptt=True, pause_after_word=2, pause_frames=60)
        frames[-1].meta["final"] = "remind me to call mom tomorrow"
        rig.pipeline_turn = next(p for p in rig.pipeline.processors if hasattr(p, "turn")).turn
        tid = await rig.turn(frames)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    turns = [t for t in rig.session.recorder.traces if t.turn_id]
    assert len(turns) == 1 and turns[0].turn_id == tid
    assert rig.pipeline_turn.asked == 0        # release is the end: Smart Turn isn't asked


def test_pressing_the_key_while_jarvis_speaks_stops_him_at_once():
    async def main():
        lat = FakeLatencies(scale=0.05, llm_token_gap_ms=200.0)
        from jarvis.voice.config import VoiceConfig

        config = VoiceConfig(voice_id="fake-voice", barge_in_mode="confirm")   # talking over him needs a second
        rig = make_rig(lat=lat, config=config, reply=lambda t: "Your next lab is Thursday at noon. " * 6)
        rig.out.scale = 1.0
        await rig.say(utterance("when is my next lab"))
        for _ in range(500):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        assert rig.session.bot_speaking
        await asyncio.sleep(0.1)
        press = InputAudioRawFrame(meta={"speech": False, "ptt_down": True}, ptt=True)
        await rig.pipeline.queue_frame(press)       # the key, before he's said a word
        await asyncio.sleep(0.05)
        stopped = bool(rig.out.stops)
        await rig.close()
        return rig, stopped

    rig, stopped = asyncio.run(main())
    assert stopped and rig.llm.cancelled == 1


@pytest.mark.skipif(not (MODELS / "hey_jarvis_v0.1.onnx").exists(), reason="openWakeWord models not downloaded")
def test_our_runner_scores_exactly_like_openwakeword():
    """v0.13.4: the models run without the openwakeword package (its scikit-learn import broke on Laptop A)."""
    np = pytest.importorskip("numpy")
    oww = pytest.importorskip("openwakeword.model")
    from jarvis.voice.wake import FILES, HeyJarvisModel

    rng = np.random.default_rng(3)
    t = np.arange(16000 * 3) / 16000
    voiced = (np.sin(2 * np.pi * 180 * t) * np.sin(2 * np.pi * 3 * t) * 6000).astype(np.int16)
    audio = np.concatenate([rng.normal(0, 300, 16000).astype(np.int16), voiced, rng.normal(0, 300, 16000).astype(np.int16)])
    audio = audio[: len(audio) // 1280 * 1280]
    np.random.seed(42)
    ours = HeyJarvisModel(MODELS)
    np.random.seed(42)
    ref = oww.Model(wakeword_models=[str(MODELS / FILES[0])], inference_framework="onnx",
                    melspec_model_path=str(MODELS / FILES[1]), embedding_model_path=str(MODELS / FILES[2]))
    for i in range(0, len(audio), 1280):
        chunk = audio[i:i + 1280]
        assert ours.predict(chunk)["hey_jarvis"] == pytest.approx(list(ref.predict(chunk).values())[0], abs=1e-5)


def test_download_fetches_the_three_models_once(tmp_path, monkeypatch):
    from jarvis.voice import wake

    asked = []

    class Reply:
        def __init__(self, url):
            asked.append(url)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"onnx"

    monkeypatch.setattr(wake.urllib.request, "urlopen", lambda url, timeout: Reply(url))
    d = wake.download(tmp_path)
    assert sorted(p.name for p in d.iterdir()) == sorted(wake.FILES)
    assert asked == [wake.RELEASE + f for f in wake.FILES]
    wake.download(tmp_path)
    assert len(asked) == 3            # already there: not fetched again
