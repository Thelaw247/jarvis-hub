"""A spoken turn that uses tools (TOOLS §2, §5): Claude asks for a tool, Jarvis runs it, the answer is spoken; a
guess (speculation) runs no tool; a slow tool gets a filler; a finished task is said at a quiet moment."""
from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.tools import Registry, ToolContext
from jarvis.tools.voice import ROUTING, VoiceTools
from jarvis.voice.fakes import FakeLatencies, make_rig, utterance


class Canvas:
    needs_sign_in = False
    calls: list[str] = []

    async def find(self, query, course=None, kinds=None):
        Canvas.calls.append(query)

        class Hit:
            def line(self):
                return "[GE 122] assignment: Lab 5: Trusses · due Thu Nov 20 5:59 pm · https://canvas.usask.ca/x"
        return [Hit()]


def voice_tools() -> VoiceTools:
    return VoiceTools(Registry(), lambda: ToolContext(root=Path("."), canvas=Canvas()))


def script(request: dict):
    last = request["messages"][-1]["content"]
    if isinstance(last, list) and last and last[0].get("type") == "tool_result":
        assert "Lab 5" in last[0]["content"]
        return "Lab 5 is due Thursday at six, sir."
    return ("", ("canvas_find", {"query": "lab 5"}))


def test_a_question_about_canvas_runs_the_tool_and_speaks_the_answer():
    Canvas.calls = []

    async def main():
        rig = make_rig(lat=FakeLatencies(scale=0.02), script=script, tools=voice_tools())
        tid = await rig.say(utterance("when is lab five due"))
        await rig.session.wait_turn(tid, timeout=5)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    spoken = " ".join(t for ctx, t in rig.tts.sent if ctx == tid)
    assert "due Thursday" in spoken and Canvas.calls == ["lab 5"]
    first = rig.llm.requests[0]
    assert any(t.get("name") == "canvas_find" for t in first["tools"])
    assert any(ROUTING[:30] in b["text"] for b in first["system"])          # the routing policy is in the prompt
    assert sum("cache_control" in b for b in first["system"]) >= 2           # persona and policy both cached
    trace = next(t for t in rig.session.recorder.traces if t.turn_id == tid)
    assert trace.notes.get("tools") == "canvas_find"


def test_a_slow_tool_gets_a_filler_so_he_doesnt_hear_silence(tmp_path):
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.phrases import (
        PhraseCache,  # noqa: F401  (the rig renders fillers into its phrase cache)
    )

    class Docs:
        async def read(self, path, pages=None, question=None):
            await asyncio.sleep(0.2)

            class D:
                pages_returned, page_count = 1, 1

                def as_text(self):
                    return "Goggles required."
            return D()

    tools = VoiceTools(Registry(), lambda: ToolContext(root=Path("."), documents=Docs()))

    def doc_script(request):
        last = request["messages"][-1]["content"]
        if isinstance(last, list):
            return "Yes, goggles are required."
        return ("", ("read_document", {"path": "manual.pdf", "question": "goggles"}))

    async def main():
        cfg = VoiceConfig(voice_id="fake-voice", filler_after_ms=5000.0)  # the timer alone wouldn't fire in time
        rig = make_rig(lat=FakeLatencies(scale=0.02), config=cfg, script=doc_script, tools=tools,
                       phrase_dir=tmp_path)
        for text in cfg.fillers:
            await rig.phrases.ensure(text)
        tid = await rig.say(utterance("do we need goggles"))
        await rig.session.wait_turn(tid, timeout=5)
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    trace = next(t for t in rig.session.recorder.traces if t.turn_id == tid)
    assert trace.notes.get("filler") and trace.notes.get("tools") == "read_document"


def test_a_finished_task_is_said_at_the_next_quiet_moment():
    async def main():
        rig = make_rig(lat=FakeLatencies(scale=0.02), tools=voice_tools())
        from jarvis.voice.talker_t1 import TalkerProcessor
        talker = next(p for p in rig.pipeline.processors if isinstance(p, TalkerProcessor))
        tid = await rig.say(utterance("what's on today"))
        said = asyncio.create_task(talker.announce("Your research is done: the cheapest plan is Student Plus."))
        await rig.session.wait_turn(tid, timeout=5)
        ok = await said
        await asyncio.sleep(0.3)
        await rig.close()
        return rig, tid, ok

    rig, tid, ok = asyncio.run(main())
    contexts = [ctx for ctx, _ in rig.tts.sent]
    assert ok and contexts.index(tid) < len(contexts) - 1                     # after his answer, not over it
    assert "Student Plus" in " ".join(t for c, t in rig.tts.sent if c != tid)
    assert rig.talker.history[-1]["content"].startswith("Your research is done")


def test_a_guess_never_runs_a_tool_until_his_final_words_confirm_it():
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.fakes import FakeAnthropic, FakeKeyed
    from jarvis.voice.talker_t1 import TalkerT1

    Canvas.calls = []
    llm = FakeAnthropic(FakeLatencies(scale=0.01), script=script)
    talker = TalkerT1(VoiceConfig(voice_id="v"), FakeKeyed(), client_factory=llm.factory, tools=voice_tools())
    out: list[str] = []

    async def on_delta(d):
        out.append(d)

    async def never() -> bool:
        return False
    asyncio.run(talker.stream("when is lab five", on_delta, gate=never))
    assert Canvas.calls == [] and len(llm.requests) == 1     # abandoned: no tool, no second round

    async def yes() -> bool:
        return True
    asyncio.run(talker.stream("when is lab five", on_delta, gate=yes))
    assert Canvas.calls == ["lab 5"] and "due Thursday" in "".join(out)


def test_if_the_api_refuses_the_tool_list_jarvis_steps_down_instead_of_breaking():
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.fakes import FakeAnthropic, FakeKeyed
    from jarvis.voice.talker_t1 import TalkerT1

    class Refused(Exception):
        status_code = 400

    llm = FakeAnthropic(FakeLatencies(scale=0.01), reply=lambda t: "Hello, sir.")
    real = llm.stream

    def stream(**request):
        tools = request.get("tools") or []
        if any(str(t.get("type", "")).startswith(("tool_search", "web_search")) for t in tools):
            raise Refused("not enabled")
        return real(**request)
    llm.stream = stream
    talker = TalkerT1(VoiceConfig(voice_id="v"), FakeKeyed(), client_factory=llm.factory, tools=voice_tools())
    out: list[str] = []

    async def on_delta(d):
        out.append(d)
    asyncio.run(talker.stream("hi", on_delta))
    assert "".join(out) == "Hello, sir." and talker.tool_level == "no_server_tools"
    assert any(t.get("name") == "canvas_find" for t in talker.build_request("x")["tools"])  # still has his tools
