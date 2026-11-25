"""v0.27.2: Jarvis keeps what he checked beside what he said. On 23 Nov his own answers looked unchecked to him one
turn later (only the words were kept), so he re-read the timetable five turns running and "corrected" a right answer."""
from jarvis.voice.config import VoiceConfig
from jarvis.voice.talker_t1 import WORK_RESULT_CHARS, TalkerT1


class Keyed:
    async def call(self, fn): return await fn("k")


def work(result="His classes on Tuesday: 8:30 PHYS 152 lab"):
    return [{"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "school", "input": {"about": "day", "day": "tomorrow"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": result}]}]


def answered(talker, user, reply, checks=None):
    if checks is not None:
        talker._pending_work = (user, checks)   # noqa: SLF001 - what a finished run leaves behind
    talker.remember(user, reply)


def test_the_next_turn_sees_the_check_behind_the_last_answer():
    t = TalkerT1(VoiceConfig(), Keyed())
    answered(t, "what class do I have first", "The physics lab at half past eight, sir.", work())
    answered(t, "thanks", "Very good, sir.")
    msgs = t.build_request("and after that?")["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user", "assistant", "user"]
    assert msgs[1]["content"][0]["name"] == "school" and msgs[2]["content"][0]["type"] == "tool_result"   # the check, before the answer
    assert msgs[3]["content"] == "The physics lab at half past eight, sir." and msgs[-1]["content"] == "and after that?"
    assert [m["content"] for m in t.history] == ["what class do I have first", "The physics lab at half past eight, sir.", "thanks", "Very good, sir."]


def test_only_a_clean_finished_check_is_kept_and_long_results_are_cut():
    t = TalkerT1(VoiceConfig(), Keyed())
    answered(t, "one", "first", work("x" * 5000))
    kept = t.build_request("next")["messages"][2]["content"][0]["content"]
    assert len(kept) < WORK_RESULT_CHARS + 5 and kept.endswith("…")
    t._pending_work = ("something else he said", work())   # noqa: SLF001 - an early answer that was thrown away
    t.remember("two", "second")
    answered(t, "three", "third", work()[:1])               # a call with no result: never sent back
    answered(t, "four", "", work())                         # nothing was said: nothing to stand behind
    roles = [m["role"] for m in t.build_request("next")["messages"]]
    assert roles.count("user") - 1 == roles.count("assistant") - 1 + 1 and len(t._work) == 1   # noqa: SLF001


def test_checks_leave_with_the_turns_they_belong_to():
    t = TalkerT1(VoiceConfig(history_turns=2), Keyed())
    answered(t, "one", "first", work())
    answered(t, "two", "second")
    assert len(t._work) == 1                                # noqa: SLF001
    answered(t, "three", "third")
    assert t._work == [] and [m["content"] for m in t.history] == ["two", "second", "three", "third"]   # noqa: SLF001


def test_he_speaks_first_and_old_thinking_is_never_sent_back():
    quick = TalkerT1(VoiceConfig(llm_model="claude-haiku-5-5"), Keyed())
    assert quick.build_request("hello")["thinking"] == {"type": "disabled"}        # no hidden thinking before his first word
    assert "thinking" not in TalkerT1(VoiceConfig(llm_model="claude-sonnet-5-5"), Keyed()).build_request("hello")   # deep: untouched for now
    checked = work()
    checked[0]["content"].insert(0, {"type": "thinking", "thinking": "", "signature": "sig"})
    answered(quick, "what class do I have first", "The physics lab, sir.", checked)
    sent = quick.build_request("and then?")["messages"][1]["content"]
    assert [b["type"] for b in sent] == ["tool_use"]

