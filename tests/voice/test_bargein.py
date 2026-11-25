"""Barge-in: his voice stops Jarvis within 150 ms, cancels the LLM stream and closes the TTS context."""
import asyncio
import time

from jarvis.voice.fakes import FakeLatencies, make_rig, utterance

BUDGET_MS = 150.0


def test_his_voice_stops_tts_within_150_ms():
    async def main():
        # real-time playback (scale 1 for audio out) so Jarvis is mid-sentence when he speaks
        lat = FakeLatencies(scale=0.05, llm_token_gap_ms=200.0)  # a slow stream: the LLM is still going
        rig = make_rig(lat=lat, reply=lambda t: "Your next lab is Thursday at noon. " * 6)
        rig.out.scale = 1.0
        tid = await rig.say(utterance("when is my next lab"))
        for _ in range(500):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        assert rig.session.bot_speaking, "Jarvis never started speaking"
        await asyncio.sleep(0.1)  # mid-sentence
        t_speech = time.perf_counter()
        next_tid = await rig.say(utterance("stop")[:1])  # his first speech frame
        stopped = rig.out.stops[-1] if rig.out.stops else None
        await asyncio.sleep(0.2)
        late_writes = [t for t, _ in rig.out.writes if stopped is not None and t > stopped]
        await rig.close()
        return rig, tid, next_tid, t_speech, stopped, late_writes

    rig, tid, next_tid, t_speech, stopped, late_writes = asyncio.run(main())
    assert stopped is not None
    stop_ms = (stopped - t_speech) * 1000
    print(f"barge-in: audio stopped {stop_ms:.2f} ms after his first speech frame")
    assert stop_ms < BUDGET_MS
    assert rig.session.barge_ins and max(rig.session.barge_ins) < BUDGET_MS
    assert late_writes == []                                   # not one more slice of the old answer
    assert [ctx for ctx, _ in rig.tts.cancelled] == [tid]      # the ElevenLabs context was closed
    assert rig.llm.cancelled == 1                              # the LLM stream was cancelled
    trace = next(t for t in rig.session.recorder.traces if t.turn_id == tid)
    assert trace.notes.get("interrupted") is True
    assert next_tid != tid                                     # his new words start a new turn


def test_speech_before_the_answer_plays_also_cancels_it():
    async def main():
        rig = make_rig(lat=FakeLatencies(scale=0.05, llm_first_token_ms=4000.0))  # still thinking
        tid = await rig.say(utterance("when is my next lab"))
        await asyncio.sleep(0.002)  # thinking: the LLM hasn't answered yet
        assert rig.session.responding == tid and not rig.session.bot_speaking
        await rig.say(utterance("actually never mind"))
        await asyncio.sleep(0.3)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    assert all(ctx != tid for ctx, _ in rig.tts.sent)  # the old answer never reached TTS
    assert rig.llm.cancelled >= 1


# ---- "confirm" mode: talking over Jarvis like a person (client echo cancellation on) ---------------------------
def _speaking_rig(**cfg):
    from jarvis.voice.config import VoiceConfig

    lat = FakeLatencies(scale=0.05, llm_token_gap_ms=200.0)
    config = VoiceConfig(voice_id="fake-voice", barge_in_mode="confirm", **cfg)
    rig = make_rig(lat=lat, config=config, reply=lambda t: "Your next lab is Thursday at noon. " * 6)
    rig.out.scale = 1.0
    rig.ducks = []
    rig.out.duck = rig.ducks.append
    rig.session.duck = rig.out.duck
    return rig


async def _until_speaking(rig):
    tid = await rig.say(utterance("when is my next lab"))
    for _ in range(500):
        if rig.session.bot_speaking:
            break
        await asyncio.sleep(0.005)
    assert rig.session.bot_speaking
    await asyncio.sleep(0.1)
    return tid


def test_a_few_words_over_jarvis_do_not_stop_him_but_a_second_of_talking_does():
    """Some push-back (his ask, v0.11.2): Jarvis only stops after ~1 s of continuous talking, and (v0.12.5) only ducks
    after 0.3 s of speech, so a tap or a short noise leaves him at full volume."""
    async def main():
        rig = _speaking_rig()
        tid = await _until_speaking(rig)
        await rig.say(utterance("wait what"))                         # 6 frames = 120 ms of speech, then quiet
        await asyncio.sleep(0.05)
        stopped_early = bool(rig.out.stops)
        ducked_early = True in rig.ducks
        await rig.say(utterance(" ".join(["hold"] * 20)))              # 60 frames = 1.2 s of continuous talking
        await asyncio.sleep(0.05)
        await rig.close()
        return rig, tid, stopped_early, ducked_early

    rig, tid, stopped_early, ducked_early = asyncio.run(main())
    assert not ducked_early                                          # v0.12.5: a short sound doesn't even duck him
    assert True in rig.ducks                                         # real talking ducks him first
    assert not stopped_early                                         # two quick words: he carried on
    assert rig.out.stops                                             # a second of talking: he stopped
    assert next(t for t in rig.session.recorder.traces if t.turn_id == tid).notes.get("interrupted") is True


def test_mm_hmm_and_his_own_echo_do_not_stop_him():
    async def main():
        rig = _speaking_rig()
        tid = await _until_speaking(rig)
        await rig.say(utterance("mm hmm"))                              # a listener noise
        await asyncio.sleep(0.05)
        await rig.say(utterance("thursday at noon"))                    # Jarvis's own words leaking back
        await asyncio.sleep(0.3)
        speaking = rig.session.bot_speaking
        await rig.close()
        return rig, tid, speaking

    rig, tid, speaking = asyncio.run(main())
    assert rig.out.stops == [] and speaking                           # he kept talking
    assert rig.ducks.count(False) >= 1                               # back to full volume after each
    answered = [t.turn_id for t in rig.session.recorder.traces if t.notes.get("dropped")]
    assert len(answered) == 2                                        # neither became a question


def test_long_speech_stops_him_even_without_words_yet():
    async def main():
        rig = _speaking_rig(barge_confirm_ms=200.0)
        await _until_speaking(rig)
        await rig.say(utterance("mm hmm mm hmm mm hmm mm hmm"))        # 24 frames = 480 ms of sound (> 200 ms here)
        await asyncio.sleep(0.05)
        await rig.close()
        return rig

    rig = asyncio.run(main())
    assert rig.out.stops


def test_a_slow_answer_gets_one_filler_from_the_cache(tmp_path):
    from jarvis.voice.config import VoiceConfig

    async def main():
        config = VoiceConfig(voice_id="fake-voice", filler_after_ms=50.0, fillers=("Mm.",))
        rig = make_rig(lat=FakeLatencies(scale=0.05, llm_first_token_ms=6000.0), config=config,
                       phrase_dir=tmp_path, reply=lambda t: "Thursday at noon, sir.")
        rig.out.scale = 1.0
        await rig.pipeline.get(__import__("jarvis.voice.pipeline", fromlist=["TtsProcessor"]).TtsProcessor) \
            .cache.ensure("Mm.")
        tid = await rig.say(utterance("when is my next lab"))
        await asyncio.sleep(0.6)
        await rig.say(utterance("and the one after that"))  # a second slow turn right away: no second filler
        await asyncio.sleep(0.6)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    notes = [t.notes.get("filler") for t in rig.session.recorder.traces]
    assert notes.count("Mm.") == 1
    assert any(w for _, w in rig.out.writes)                         # the filler actually played


def _thinking_rig():
    from jarvis.voice.config import VoiceConfig

    config = VoiceConfig(voice_id="fake-voice", barge_in_mode="confirm")
    return make_rig(lat=FakeLatencies(scale=0.05, llm_first_token_ms=4000.0), config=config,
                    reply=lambda t: "Thursday at noon, sir.")


def test_a_noise_while_he_thinks_does_not_lose_the_answer():
    """v0.10.2 bug on Laptop B: a fan or a cough right after a question started a new 'turn', which threw the
    pending answer away, so Jarvis heard him and said nothing."""
    from jarvis.voice.frames import InputAudioRawFrame

    async def main():
        rig = _thinking_rig()
        tid = await rig.say(utterance("when is my next lab"))
        await asyncio.sleep(0.002)
        assert rig.session.responding == tid and not rig.session.bot_speaking
        noise = [InputAudioRawFrame(meta={"speech": True}) for _ in range(10)]
        await rig.say(noise + utterance("")[-14:])                     # sound, no words
        await asyncio.sleep(0.6)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    assert any(ctx == tid for ctx, _ in rig.tts.sent)                 # the answer was still spoken
    assert rig.llm.cancelled == 0


def test_a_new_question_while_he_thinks_replaces_the_old_one():
    async def main():
        rig = _thinking_rig()
        tid = await rig.say(utterance("when is my next lab"))
        await asyncio.sleep(0.002)
        new = await rig.say(utterance("actually what about friday"))
        await asyncio.sleep(0.6)
        await rig.close()
        return rig, tid, new

    rig, tid, new = asyncio.run(main())
    assert all(ctx != tid for ctx, _ in rig.tts.sent)                 # the old answer was dropped
    assert any(ctx == new for ctx, _ in rig.tts.sent)                 # the new question was answered


def test_the_orb_glow_follows_the_voice_level():
    from jarvis.voice.session import level_of

    loud = (b"\x00\x40" * 320)        # 16384: about -6 dBFS
    soft = (b"\x40\x00" * 320)        # 64: about -54 dBFS
    assert level_of(loud) == 1.0 and level_of(soft) == 0.0 and level_of(b"") == 0.0
    assert 0.0 < level_of(b"\x00\x04" * 320) < 1.0  # 1024: about -30 dBFS, in between


def test_the_orb_says_speaking_until_the_client_has_played_the_last_words():
    """His clip: the orb went back to standby ~0.4 s before Jarvis's voice ended (audio is sent ahead)."""
    async def main():
        rig = make_rig(lat=FakeLatencies(scale=0.05), reply=lambda t: "Thursday at noon, sir.")
        rig.out.remaining = lambda: 0.25 if rig.session.bot_speaking else 0.0
        await rig.say(utterance("when is my next lab"))
        for _ in range(400):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        while not rig.events.of("orb.state") or rig.events.of("orb.state")[-1]["state"] != "idle":
            await asyncio.sleep(0.005)
        idle_at = time.perf_counter()
        last_write = rig.out.writes[-1][0]
        await rig.close()
        return idle_at - last_write

    gap = asyncio.run(main())
    assert gap >= 0.2  # idle only once the client's buffer has played out
