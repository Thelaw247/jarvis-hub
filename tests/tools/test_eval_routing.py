"""tools/eval_routing.py (v0.15.0): both voice brains side by side, with the time to Claude's first word, and the
choice saved as the hub setting. No real API call here: a stand-in client plays Claude."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as NS

spec = importlib.util.spec_from_file_location("eval_routing", Path(__file__).resolve().parents[2] / "tools" / "eval_routing.py")
ev = importlib.util.module_from_spec(spec)
sys.modules["eval_routing"] = ev
spec.loader.exec_module(ev)

WANT = dict(ev.CASES)


class Stream:
    def __init__(self, model, text, delay):
        self.model, self.text, self.delay = model, text, delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def pick(self):
        want = WANT.get(self.text, {"none"})
        if self.model == "slow-and-right" or self.text != "what's my first class tomorrow":
            return sorted(want)[0]
        return "canvas_find"                       # the quick one's known mistake

    async def __aiter__(self):
        yield NS(type="message_start")
        await asyncio.sleep(self.delay)
        tool = self.pick()
        if tool == "none":
            yield NS(type="content_block_start", content_block=NS(type="text"))
            yield NS(type="content_block_delta", delta=NS(type="text_delta", text="Sure."))
        else:
            yield NS(type="content_block_start", content_block=NS(type="tool_use", name=tool))

    async def get_final_message(self):
        tool = self.pick()
        block = NS(type="text", text="Sure.") if tool == "none" else NS(type="tool_use", name=tool)
        return NS(content=[block])


class Client:
    def __init__(self):
        self.sent = []
        self.messages = NS(stream=self.stream)

    def stream(self, **req):
        self.sent.append(req)
        return Stream(req["model"], req["messages"][-1]["content"], 0.03 if req["model"] == "slow-and-right" else 0.005)


def test_each_brain_gets_every_case_a_score_and_a_time_to_first_word():
    client = Client()
    quick = asyncio.run(ev.run_brain(client, {"system": [], "tools": []}, "fast-and-loose"))
    deep = asyncio.run(ev.run_brain(client, {"system": [], "tools": []}, "slow-and-right"))
    assert len(client.sent) == 2 * (len(ev.CASES) + 1)                 # one warm-up each, then every case once
    assert all(r["max_tokens"] == 300 and len(r["messages"]) == 1 for r in client.sent)
    assert deep["score"] == 1.0 and deep["wrong"] == []
    assert [w[:2] for w in quick["wrong"]] == [("what's my first class tomorrow", "canvas_find")]
    assert 0.02 < deep["median_s"] < 0.5 and quick["median_s"] < deep["median_s"] <= deep["slow_s"]
    text = ev.report({"quick": quick, "deep": deep})
    assert "deep against quick: first word 0.0" in text and "s later, 1 more right first picks" in text
    assert "quick got these wrong:" in text and "wanted calendar" in text
    assert "deep got these wrong" not in text


def test_the_cases_cover_his_calendar_and_name_only_real_tools():
    from jarvis.tools import Registry

    real = set(Registry().specs) | {"none", "web_search", "web_fetch"}
    named = set().union(*(want for _, want in ev.CASES))
    assert named <= real, named - real
    assert sum(1 for _, want in ev.CASES if "school" in want) >= 5      # his classes and due work: the local files
    assert sum(1 for _, want in ev.CASES if want == {"calendar"}) >= 2  # his own events and free time


def test_choosing_a_brain_sets_the_hub_setting_and_enter_leaves_it(monkeypatch, capsys):
    calls = []

    def setting(value=None):
        calls.append(value)
        if value is not None:
            setting.now = value
        return setting.now

    setting.now = "quick"
    monkeypatch.setattr(ev, "core_setting", setting)
    results = {"quick": {"model": "claude-haiku-5-5"}, "deep": {"model": "claude-sonnet-5-5"}}
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    ev.pick_brain(results)
    assert calls == [None, "deep"] and "now uses the deep brain" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    ev.pick_brain(results)
    assert calls[-1] is None and "Left as it is" in capsys.readouterr().out


def test_with_the_core_off_it_says_so_and_changes_nothing(monkeypatch, capsys):
    monkeypatch.setattr(ev, "core_setting", lambda value=None: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": (_ for _ in ()).throw(AssertionError("must not ask")))
    ev.pick_brain({"quick": {"model": "a"}, "deep": {"model": "b"}})
    assert "wasn't changed" in capsys.readouterr().out
