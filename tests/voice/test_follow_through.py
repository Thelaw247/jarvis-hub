"""v0.14.0, from the logs of 2026-11-18 (35 answers in 310 turns): the ways a turn got lost, one test each.

- Claude's reply came back empty: a filler, then silence.
- A thought said in two parts: the first half was cancelled, only the second was answered.
- An interrupted answer was forgotten, so "no, the other one" meant nothing.
- "Yeah" on the last word of Jarvis's question was dropped as a listener noise.
- The orb closed and reopened under his voice; meter ticks could change its state.
- Hearing ran behind real time (a turn's words took 19 s) because every frame waited on the speech model.
- A turn that never ended left Jarvis deaf to everything after it.
"""
import asyncio
import time

from jarvis.voice.fakes import FakeLatencies, make_rig, silence, utterance
from jarvis.voice.frames import InputAudioRawFrame
from jarvis.voice.pipeline import answers_him
from jarvis.voice.talker_t1 import NO_REPLY

SCALE = 0.02


def run(coro):
    return asyncio.run(coro)


def said(rig):
    return [text for _, text in rig.tts.sent]


# ---- an empty reply ------------------------------------------------------------------------------------------
def test_an_empty_reply_is_asked_for_again_and_then_answered():
    replies = iter(["", "Your first class is GE 122 at 8:30."])

    async def main():
        rig = make_rig(scale=SCALE, script=lambda request: next(replies))
        tid = await rig.turn(utterance("what is my first class tomorrow"))
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    assert said(rig) == ["Your first class is GE 122 at 8:30."]
    assert len(rig.llm.requests) == 2
    assert rig.llm.requests[1]["max_tokens"] >= 1200                       # room to finish a cut-off tool call
    assert "came back empty" in rig.llm.requests[1]["system"][-1]["text"]
    trace = next(t for t in rig.session.recorder.traces if t.turn_id == tid)
    assert trace.notes["empty_first"] == "end_turn"                         # the log now says why, in a word


def test_still_nothing_when_he_was_talking_to_jarvis_says_so_instead_of_silence():
    async def main():
        rig = make_rig(scale=SCALE, script=lambda request: "")
        rig.session.addressed = True        # after "hey Jarvis" or with the talk key
        tid = await rig.turn(utterance("check that"))
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    assert said(rig) == [NO_REPLY]
    assert next(t for t in rig.session.recorder.traces if t.turn_id == tid).notes["no_reply"] is True


def test_a_stray_fragment_with_no_reply_stays_quiet_when_he_was_not_addressing_jarvis():
    async def main():
        rig = make_rig(scale=SCALE, script=lambda request: "")
        await rig.turn(utterance("okay then"))
        await rig.close()
        return rig

    assert said(run(main())) == []


# ---- one thought in two parts --------------------------------------------------------------------------------
def test_going_on_talking_before_jarvis_answers_joins_both_parts():
    async def main():
        lat = FakeLatencies(scale=0.05, llm_first_token_ms=4000.0)           # still thinking when he goes on
        rig = make_rig(lat=lat, reply=lambda text: "Done.")
        first = await rig.say(utterance("add a study block tomorrow"))
        await asyncio.sleep(0.01)
        assert rig.session.responding == first and not rig.session.bot_speaking
        second = await rig.turn(utterance("after my chemistry lab"), timeout=20.0)
        await rig.close()
        return rig, second

    rig, second = run(main())
    asked = [r["messages"][-1]["content"] for r in rig.llm.requests]
    assert asked[-1] == "add a study block tomorrow after my chemistry lab"
    assert next(t for t in rig.session.recorder.traces if t.turn_id == second).notes["joined"] is True
    assert rig.talker.history[-2]["content"] == "add a study block tomorrow after my chemistry lab"


def test_an_answer_he_cut_into_is_remembered_so_the_next_words_make_sense():
    async def main():
        lat = FakeLatencies(scale=0.05, llm_token_gap_ms=400.0)        # still writing the answer when he cuts in
        rig = make_rig(lat=lat, reply=lambda text: "No, actually." if "other" in text
                       else "Your next lab is Thursday at noon in Engineering 1B71. " * 5)
        rig.out.scale = 1.0
        await rig.say(utterance("when is my next lab"))
        for _ in range(600):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        assert rig.session.bot_speaking
        await asyncio.sleep(0.25)
        rig.talker_proc = next(p for p in rig.pipeline.processors if hasattr(p, "_carry"))
        rig.talker_proc._live.spoken_at -= 5.0          # he'd heard a few seconds of it
        await rig.turn(utterance("no the other one"), timeout=20.0)
        await rig.close()
        return rig

    rig = run(main())
    history = rig.talker.history
    assert history[0] == {"role": "user", "content": "when is my next lab"}
    assert "cut in" in history[1]["content"] and "Thursday" in history[1]["content"]
    assert rig.llm.requests[-1]["messages"][-1]["content"] == "no the other one"   # a new thought, not joined


def test_a_finished_answer_he_talks_over_in_its_first_second_is_joined_too():
    async def main():
        lat = FakeLatencies(scale=0.05)
        rig = make_rig(lat=lat, reply=lambda text: "Booked for tomorrow at nine in the morning, as you asked. " * 3)
        rig.out.scale = 1.0
        await rig.say(utterance("add a study block tomorrow"))
        for _ in range(600):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        assert rig.session.bot_speaking
        await asyncio.sleep(0.15)                                            # the answer has only just started
        await rig.turn(utterance("after my chemistry lab not before"), timeout=20.0)
        await rig.close()
        return rig

    rig = run(main())
    assert rig.llm.requests[-1]["messages"][-1]["content"] == "add a study block tomorrow after my chemistry lab not before"
    assert [m["content"] for m in rig.talker.history if m["role"] == "user"] == [
        "add a study block tomorrow after my chemistry lab not before"]      # one exchange, not a broken one and a half


# ---- short answers to his question ---------------------------------------------------------------------------
def test_a_short_answer_to_his_question_counts():
    assert answers_him("yeah", "Canvas needs you to sign in. Shall I open the page?")
    assert answers_him("no thanks", "Want me to open it?")
    assert answers_him("go ahead", "Should I?")
    assert not answers_him("yeah", "Your lab is Thursday at noon.")          # he wasn't asked anything
    assert not answers_him("mm", "Shall I open the page?")
    assert not answers_him("", "Shall I?")


def test_yeah_on_the_tail_of_his_question_is_answered_not_dropped():
    replies = iter(["Canvas needs you to sign in first. Shall I open the page for you now?", "Opening it."])

    async def main():
        lat = FakeLatencies(scale=0.05)
        from jarvis.voice.config import VoiceConfig

        rig = make_rig(lat=lat, config=VoiceConfig(voice_id="fake-voice", barge_in_mode="confirm"),
                       script=lambda request: next(replies))
        rig.out.scale = 1.0
        await rig.say(utterance("what is due on canvas"))
        for _ in range(600):
            if rig.session.bot_speaking:
                break
            await asyncio.sleep(0.005)
        assert rig.session.bot_speaking
        await asyncio.sleep(0.3)                                             # he answers before the last word ends
        tid = await rig.turn(utterance("yeah"), timeout=20.0)
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    trace = next(t for t in rig.session.recorder.traces if t.turn_id == tid)
    assert not trace.notes.get("dropped")
    assert said(rig)[-1] == "Opening it."


# ---- the orb -------------------------------------------------------------------------------------------------
def test_the_orb_never_goes_idle_while_he_is_talking():
    """A bit of sound that turns out to be nothing ends while he's already speaking again: stay on listening."""
    async def main():
        rig = make_rig(scale=SCALE)
        s = rig.session
        tid = s.new_turn()                       # he's talking
        await s.show_orb()
        s.finish_turn("turn-0")                   # an older, empty turn is closed just now
        await s.show_orb()
        await s.settled()
        assert s.orb_state() == "listening"
        s.end_user_turn(tid)
        s.finish_turn(tid)
        await s.show_orb()
        early = [d["state"] for d in rig.events.of("orb.state")]
        await s.settled()
        await rig.close()
        return rig, early

    rig, early = run(main())
    assert early == ["listening"]                 # idle isn't shown the instant a turn ends...
    assert [d["state"] for d in rig.events.of("orb.state")] == ["listening", "idle"]   # ...only once it has held


def test_two_turns_close_together_never_show_idle_between_them():
    async def main():
        rig = make_rig(scale=SCALE)
        s = rig.session
        await rig.say(utterance("mm", final=""))          # sound, no words
        await rig.say(utterance("what time is it"))
        await s.settled()
        states = [d["state"] for d in rig.events.of("orb.state") if "level" not in d]
        await rig.close()
        return states

    states = run(main())
    first_idle = states.index("idle") if "idle" in states else len(states)
    assert "speaking" in states[:first_idle]              # no idle before he's answered


def test_a_meter_tick_can_never_change_the_orbs_state():
    async def main():
        rig = make_rig(scale=SCALE)
        s = rig.session
        s.shown = "thinking"
        loud = (b"\xff\x3f" * 320)
        await s.show_level("listening", loud)             # a late tick from the listening side
        s._level_at = -1e9
        await s.set_levels(0.7, 0.0)                      # the window's own meter
        await rig.close()
        return rig.events.of("orb.state")

    events = run(main())
    assert events and all(e["state"] == "thinking" for e in events)
    assert events[-1]["level"] == 0.7


def test_the_windows_meter_shows_his_voice_or_jarviss_by_what_is_happening():
    async def main():
        rig = make_rig(scale=SCALE)
        s = rig.session
        s.shown = "idle"
        await s.set_levels(0.31, 0.9)                     # the room, while nothing is said
        s.shown, s._level_at = "speaking", -1e9
        await s.set_levels(0.05, 0.66)                    # Jarvis speaking: what the speaker is playing now
        await s.set_levels("junk", None)                  # nonsense is ignored
        await rig.close()
        return rig.events.of("orb.state")

    events = run(main())
    assert events == [{"state": "idle", "level": 0.31}, {"state": "speaking", "level": 0.66}]


# ---- hearing keeps up with real time -------------------------------------------------------------------------
class SlowStt:
    """A speech model that needs 30 ms for every 20 ms frame: slower than real time."""

    def __init__(self):
        self.fed = 0
        self.batches = []

    async def accept_many(self, frames):
        self.batches.append(len(frames))
        await asyncio.sleep(0.03)
        self.fed += len(frames)
        return f"heard {self.fed}"

    async def finalize(self):
        await asyncio.sleep(0.01)
        return f"final after {self.fed}"


def test_a_slow_speech_model_never_holds_up_the_microphone_side():
    async def main():
        rig = make_rig(scale=SCALE)
        stt_proc = next(p for p in rig.pipeline.processors if type(p).__name__ == "SttProcessor")
        slow = stt_proc.stt = SlowStt()
        frames = utterance("one two three four five six seven eight nine ten", frames_per_word=5, quiet_frames=0)
        t0 = time.perf_counter()
        for f in frames:
            await rig.pipeline.queue_frame(f)
        took = time.perf_counter() - t0
        tid = rig.session.user_turn
        for f in silence(20):
            await rig.pipeline.queue_frame(f)
        await rig.session.wait_turn(tid, 10.0)
        await rig.close()
        return took, slow, len(frames)

    took, slow, n = run(main())
    assert took < 0.5                    # 50 frames x 30 ms would be 1.5 s if each one waited on the model
    assert slow.fed >= n                 # ...and not a frame was lost: all of it reached the model, in order
    assert max(slow.batches) > 1         # when behind, it takes what's waiting in one go


def test_words_arrive_in_order_even_when_turns_end_close_together():
    order = []

    class Stt:
        def __init__(self):
            self.text = ""

        async def accept(self, frame):
            self.text = frame.meta.get("partial", self.text)
            return self.text

        async def finalize(self):
            await asyncio.sleep(0.05)     # still finishing the first when the second turn ends
            text, self.text = self.text, ""
            return text

    async def main():
        rig = make_rig(scale=SCALE, reply=lambda text: order.append(text) or "Right.")
        next(p for p in rig.pipeline.processors if type(p).__name__ == "SttProcessor").stt = Stt()
        await rig.say(utterance("mute the microphone please now", quiet_frames=14))
        tid = await rig.say(utterance("and what is due this week"))
        await rig.session.wait_turn(tid, 10.0)
        await rig.close()
        return rig

    run(main())
    assert order and order[-1].endswith("and what is due this week")
    assert all("mute" not in t or t.startswith("mute") for t in order)   # never the second turn's words first


# ---- turns that would never end ------------------------------------------------------------------------------
def test_when_the_window_goes_to_sleep_an_open_turn_ends_at_once():
    async def main():
        rig = make_rig(scale=SCALE)
        frames = utterance("what time is it", quiet_frames=0)
        for f in frames:
            await rig.pipeline.queue_frame(f)
        tid = rig.session.user_turn
        assert tid is not None                    # mid-sentence, and then no more audio comes
        await rig.pipeline.queue_frame(InputAudioRawFrame(audio=b"", meta={"end_turn": True}))
        await rig.session.wait_turn(tid, 5.0)
        await rig.close()
        return rig, tid

    rig, tid = run(main())
    assert rig.session.user_turn is None
    assert next(t for t in rig.session.recorder.traces if t.turn_id == tid).kind == "t0"   # and it was answered


def test_a_turn_whose_voice_never_finishes_is_closed_so_he_can_hear_again():
    async def main():
        rig = make_rig(scale=SCALE, reply=lambda text: "One thing." if "first" in text else "Still here.")

        async def never_flush(context_id):       # the voice service never says "that's all"
            return None

        rig.tts.flush = never_flush
        first = await rig.say(utterance("first question"))
        await rig.session.wait_turn(first, 10.0)
        second = await rig.turn(utterance("second question please"), timeout=10.0)
        await rig.close()
        return rig, first, second

    rig, first, second = run(main())
    traces = {t.turn_id: t for t in rig.session.recorder.traces}
    assert traces[first].notes.get("stuck") is True
    assert not traces[second].notes.get("dropped")           # the next thing he says is heard as a new question
    assert "Still here." in said(rig)


def test_words_that_come_after_his_voice_ran_out_are_still_spoken():
    """A tool takes a while, the voice's context closes, then the rest of the answer arrives: before, it was shown
    as a caption and never said."""
    from jarvis.voice.frames import LLMFullResponseEndFrame, TTSSpeakFrame

    async def main():
        rig = make_rig(scale=SCALE)
        s = rig.session
        tts_proc = next(p for p in rig.pipeline.processors if type(p).__name__ == "TtsProcessor")
        turn = s.new_turn()
        s.user_turn, s.responding, s.live_turn = None, turn, turn      # the talker is still working on it
        await tts_proc.process_frame(TTSSpeakFrame(text="One moment.", turn_id=turn))
        await rig.tts.flush(turn)                                      # the voice service closes the context
        for _ in range(200):
            if tts_proc._ctx is None:
                break
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.05)
        assert s.responding == turn                                    # the turn stays open: more is coming
        await tts_proc.process_frame(TTSSpeakFrame(text="Your lab is Thursday.", turn_id=turn))
        s.live_turn = None
        await tts_proc.process_frame(LLMFullResponseEndFrame(turn_id=turn))
        await s.wait_turn(turn, 5.0)
        await rig.close()
        return rig, turn

    rig, turn = run(main())
    assert rig.tts.sent == [(turn, "One moment."), (f"{turn}.2", "Your lab is Thursday.")]
