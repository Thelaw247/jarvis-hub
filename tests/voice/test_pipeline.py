"""The whole voice pipeline with fakes: a scripted conversation end to end, and the speculative start."""
import asyncio

from jarvis.voice.fakes import make_rig, utterance
from jarvis.voice.ports import PendingApproval
from jarvis.voice.talker_t1 import TalkerProcessor

SCALE = 0.05


def run(coro):
    return asyncio.run(coro)


def test_scripted_conversation_end_to_end(contract):
    async def main():
        rig = make_rig(scale=SCALE)
        t1 = await rig.turn(utterance("when is my next lab"))
        t2 = await rig.turn(utterance("what time is it"))
        t3 = await rig.turn(utterance("set a timer for five minutes"))
        t4 = await rig.turn(utterance("volume up"))
        # an approval is waiting: "book it" goes to the executor, never on a partial
        rig.approvals.current = PendingApproval("ap-9", outward=False, asked_at=rig.session.clock())
        t5 = await rig.turn(utterance("book it"))
        t6 = await rig.turn(utterance("and the one after that"))
        await rig.close()
        return rig, (t1, t2, t3, t4, t5, t6)

    rig, turns = run(main())
    traces = {t.turn_id: t for t in rig.session.recorder.traces}
    assert set(turns) <= set(traces)

    # chat turns: every stage stamped, in order
    for tid in (turns[0], turns[5]):
        ms = traces[tid].ms
        assert traces[tid].kind == "t1"
        assert ms["vad_end"] == 0.0
        assert ms["stt_final"] <= ms["route"] <= ms["tts_first_byte"] <= ms["audio_out"]
        assert ms["llm_first_token"] <= ms["tts_first_byte"]
    # T0 commands: routed on the partial, before the STT final
    assert traces[turns[1]].kind == "t0" and traces[turns[1]].notes["routed_on_partial"] is True
    assert traces[turns[4]].notes["routed_on_partial"] is False  # approvals wait for the final
    assert [c.name for c in rig.commands.ran] == ["timer.set", "volume.step", "approval.answer"]
    assert rig.commands.ran[2].args == {"id": "ap-9", "answer": "yes"}

    # what Jarvis said: the LLM answer (two chunks), the time, the timer
    said = [text for _, text in rig.tts.sent]
    assert said[:2] == ["Thursday at noon, in Engineering 1B71.", "You have two left."]
    assert "It's 4:12." in said and "5 minutes, starting now." in said
    # the LLM was asked twice (two chat turns), with the persona cached and the history carried
    assert len(rig.llm.requests) >= 2
    last = rig.llm.requests[-1]
    assert last["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert last["messages"][0] == {"role": "user", "content": "when is my next lab"}
    assert last["model"] == "claude-haiku-5-5"

    # hub events follow the contracts
    for type_, data in rig.events.events:
        name = {"orb.state": "orb_state", "caption.show": "caption"}[type_]
        assert contract(name, data) == []
    states = [d["state"] for d in rig.events.of("orb.state")]
    states = [x for i, x in enumerate(states) if i == 0 or x != states[i - 1]]  # level updates repeat a state
    # v0.14.0: "idle" only reaches the screen if it's still true 0.4 s later, so turns that follow each other
    # closely never show as close-then-open; the conversation ends idle
    assert states[:3] == ["listening", "thinking", "speaking"]
    assert states[-1] == "idle"
    assert rig.events.of("caption.show")[0]["text"].startswith("Thursday at noon")

    # spend: tokens and characters were counted; cache reads after the first call
    assert rig.session.spend.tokens["output"] > 0
    assert rig.session.spend.tokens["cache_read"] > 0
    assert rig.session.spend.characters == sum(len(t) for t in said)


def test_speculative_start_is_used_when_the_final_matches():
    async def main():
        rig = make_rig(scale=SCALE)
        tid = await rig.turn(utterance("when is my next lab"))
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    stats = rig.pipeline.get(TalkerProcessor).stats
    assert stats == {"spec_started": 1, "spec_hit": 1, "spec_cancelled": 0}
    assert rig.llm.started == 1  # no second call
    trace = rig.session.recorder.traces[-1]
    assert trace.notes["speculation"] == "hit"


def test_speculation_is_cancelled_when_the_partial_changes():
    async def main():
        rig = make_rig(scale=SCALE)
        # he pauses after "what did the prof" long enough to speculate, then goes on talking
        tid = await rig.turn(utterance("what did the prof say about the midterm", pause_after_word=3, pause_frames=9))
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    stats = rig.pipeline.get(TalkerProcessor).stats
    assert stats["spec_cancelled"] >= 1
    assert rig.llm.cancelled >= 1
    # the answer that was spoken came from the full sentence, not the partial
    asked = [r["messages"][-1]["content"] for r in rig.llm.requests]
    assert asked[0] == "what did the prof"
    assert asked[-1] == "what did the prof say about the midterm"
    spoken_turns = {ctx for ctx, _ in rig.tts.sent}
    assert spoken_turns == {tid}


def test_speculation_thrown_away_when_the_final_differs():
    async def main():
        rig = make_rig(scale=SCALE)
        await rig.turn(utterance("is the chem lab on thursday", final="is the chem lab on tuesday"))
        await rig.close()
        return rig

    rig = run(main())
    asked = [r["messages"][-1]["content"] for r in rig.llm.requests]
    assert asked == ["is the chem lab on thursday", "is the chem lab on tuesday"]
    assert rig.llm.cancelled == 1
    assert rig.session.recorder.traces[-1].notes["speculation"] == "miss"


def test_no_speculation_on_a_command():
    async def main():
        rig = make_rig(scale=SCALE)
        await rig.turn(utterance("set a timer for five minutes"))
        await rig.close()
        return rig

    rig = run(main())
    assert rig.llm.requests == []


def test_push_to_talk_skips_the_silence_wait():
    async def main():
        rig = make_rig(scale=SCALE)
        tid = await rig.turn(utterance("what time is it", ptt=True))
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    trace = rig.session.recorder.traces[-1]
    assert trace.turn_id == tid and trace.kind == "t0" and "audio_out" in trace.ms


def test_mute_ignores_hands_free_audio_until_unmuted_by_push_to_talk():
    async def main():
        rig = make_rig(scale=SCALE)
        await rig.turn(utterance("mute"))
        assert rig.session.muted
        before = len(rig.session.recorder.traces)
        await rig.say(utterance("when is my next lab"))
        await asyncio.sleep(0.05)
        assert len(rig.session.recorder.traces) == before and rig.llm.requests == []
        await rig.turn(utterance("unmute", ptt=True))
        assert not rig.session.muted
        await rig.close()
        return rig

    rig = run(main())
    assert [c.name for c in rig.commands.ran] == ["mute", "unmute"]


def test_a_failed_llm_call_says_so_plainly():
    def boom(_text):
        raise RuntimeError("provider down")

    async def main():
        rig = make_rig(scale=SCALE, reply=boom)
        await rig.turn(utterance("when is my next lab"))
        await rig.close()
        return rig

    rig = run(main())
    assert [t for _, t in rig.tts.sent] == ["Sorry, I can't answer that right now."]


def test_a_broken_voice_service_shows_the_answer_instead_of_hanging():
    """v0.8.2 picked a TTS model the WebSocket refuses: the orb sat on "thinking" forever. Now the answer is shown
    as a caption, the orb goes idle and the turn ends."""
    async def main():
        rig = make_rig(scale=SCALE, reply=lambda text: "Twenty to nine, sir.")

        async def refuse(*args, **kwargs):
            raise ConnectionError("handshake refused")

        rig.tts.open = refuse
        tid = await rig.turn(utterance("what is the meaning of this"), timeout=5.0)
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    shown = [e for e in rig.events.events if e[0] == "caption.show"]
    assert shown and "Twenty to nine" in shown[-1][1]["text"]
    assert [e for e in rig.events.events if e[0] == "orb.state"][-1][1]["state"] == "idle"
    assert rig.session.responding is None
