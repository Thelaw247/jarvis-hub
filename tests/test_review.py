"""v0.16.0: review recording. He asked (2026-11-19) for everything about every interaction to be kept so it can be
reviewed. Off, nothing is written. On, every layer leaves its line, and no secret is ever in one."""
import asyncio
import json
import logging
import time
import wave

import pytest
from fastapi.testclient import TestClient

from jarvis import review
from jarvis.core.app import create_app
from jarvis.core.config import Config
from jarvis.core.sessions import HubSessions


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "Jarvis"
    yield r
    review.recorder().flush()
    review.use(tmp_path / "elsewhere")          # the next test never writes into this one's folder


def lines(root, kind=None):
    review.recorder().flush()
    out = []
    for f in sorted((root / "logs" / "review").glob("*/events.jsonl")):
        out += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()]
    return [x for x in out if kind is None or x["k"] == kind]


def switch_on(root, days=1.0):
    review.switch(True, days, root)
    rec = review.use(root)
    rec._checked = -1e9
    return rec


# ---- the recorder itself ------------------------------------------------------------------------------------
def test_off_it_writes_nothing_at_all(root):
    rec = review.use(root)
    rec.note("tool", tool="calendar", result="GE 122 at 8:30")
    rec.sampled("bus", "orb", 0.1, type="orb.state")
    rec.flush()
    assert not (root / "logs").exists() and rec.save_audio("t1", [bytes(640)]) is None


def test_on_every_note_is_a_line_in_order_with_its_time(root):
    rec = switch_on(root)
    rec.note("turn.heard", turn="t1", text="what's my first class tomorrow")
    rec.note("tool", tool="calendar", input={"day": "tomorrow"}, result="Fri · 8:30 AM · GE 122", ms=412.5)
    got = lines(root)
    assert [x["k"] for x in got] == ["review", "turn.heard", "tool"]
    assert got[0]["what"] == "on" and got[1]["text"] == "what's my first class tomorrow"
    assert got[2]["input"] == {"day": "tomorrow"} and got[2]["ms"] == 412.5
    assert [x["n"] for x in got] == [1, 2, 3] and got[1]["t"].startswith(time.strftime("%Y-%m-%d"))
    assert got[1]["mono"] <= got[2]["mono"]


def test_no_key_password_token_or_cookie_is_ever_written(root):
    rec = switch_on(root)
    rec.note("llm.request", headers={"x-api-key": "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx", "Authorization": "Bearer abc.def.ghi-12345678"},
             env={"ANTHROPIC_API_KEY": "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx"}, password="hunter2hunter2",
             session_token="tok_live_123456", cookie="sid=1",
             text="my key is sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx and Bearer abcdefghijklmnop123 ok",
             link="https://connect.composio.dev/link/lk_AbCdEfGhIjKlMnOpQrSt", usage={"output_tokens": 42, "max_tokens": 600})
    raw = "\n".join(json.dumps(x) for x in lines(root))
    for secret in ("sk-ant-api03", "hunter2", "tok_live", "sid=1", "abc.def.ghi", "abcdefghijklmnop123", "lk_AbCd"):
        assert secret not in raw, secret
    line = lines(root, "llm.request")[0]
    assert line["usage"] == {"output_tokens": 42, "max_tokens": 600}        # counts are not secrets
    assert line["text"] == "my key is [redacted] and [redacted] ok"


def test_big_and_odd_values_are_cut_or_described_never_dropped(root):
    class Odd:
        def __init__(self):
            self.name, self._private = "x", "y"

    rec = switch_on(root)
    rec.note("tool", result="a" * (review.MAX_TEXT + 500), audio=bytes(640), thing=Odd(), when={1, 2}, f=1.23456789)
    line = lines(root, "tool")[0]
    assert len(line["result"]) < review.MAX_TEXT + 60 and "500 more characters" in line["result"]
    assert line["audio"] == "[640 bytes]" and line["thing"] == {"name": "x"} and sorted(line["when"]) == [1, 2]
    assert line["f"] == 1.2346


def test_things_that_repeat_many_times_a_second_are_thinned_with_a_count(root):
    rec = switch_on(root)
    for i in range(50):
        rec.sampled("bus", "orb:listening", 0.05, type="orb.state", level=i)
    time.sleep(0.06)
    rec.sampled("bus", "orb:listening", 0.05, type="orb.state", level=99)
    rec.sampled("bus", "orb:thinking", 0.05, type="orb.state", level=0)      # a new state is never held back
    got = lines(root, "bus")
    assert [x["level"] for x in got] == [0, 99, 0] and got[1]["left_out"] == 49


def test_it_switches_itself_off_at_its_time(root):
    rec = switch_on(root)
    assert rec.on() is True
    review.flag(root).write_text(str(int(time.time()) - 5), encoding="ascii")
    rec._checked = -1e9
    assert rec.on() is False and review.until(root) == 0.0
    rec.note("tool", tool="x")
    assert lines(root, "tool") == []


def test_his_side_of_a_turn_is_kept_as_sound_with_what_was_heard_and_said(root):
    rec = switch_on(root)
    tap = review.tap(root, None)
    assert isinstance(tap, review.TurnTap) and review.tap(root, tap) is tap       # the same one while it's on
    for _ in range(40):
        tap.audio(None, bytes(640))                                               # before he spoke
    for _ in range(100):
        tap.audio("turn-7", b"\x01\x00" * 320)                                    # 2 s of him talking
    tap.heard("turn-7", "what's due this week")
    tap.said("turn-7", "what's due this week", "Two things: the CHEM lab and WeBWorK 9.")
    tap.ended("turn-7", {"words": 4, "stop": "end_turn"}, {"interrupted": False})
    got = {x["k"]: x for x in lines(root)}
    assert got["turn.heard"]["text"] == "what's due this week"
    assert got["turn.said"]["reply"].startswith("Two things")
    end = got["turn.ended"]
    assert end["notes"]["stop"] == "end_turn" and end["heard_s"] == 2.6            # 0.6 s of lead-in + 2 s
    wav = next((root / "logs" / "review").glob("*/audio/*.wav"))
    assert wav.name == end["wav"]
    with wave.open(str(wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16000, 1, 130 * 320)
    review.switch(False, root=root)
    rec._checked = -1e9
    assert review.tap(root, tap) is None                                           # off again: nothing is kept


def test_the_switch_from_the_command_line(root, monkeypatch, capsys):
    from jarvis.review.__main__ import main

    monkeypatch.setenv("JARVIS_ROOT", str(root))
    assert main(["on", "2"]) == 0 and 1.9 * 86400 < review.until(root) - time.time() < 2.1 * 86400
    assert "ON until" in capsys.readouterr().out
    assert main(["status"]) == 0 and "ON until" in capsys.readouterr().out
    assert main(["off"]) == 0 and review.until(root) == 0.0
    assert main([]) == 0 and "OFF" in capsys.readouterr().out


# ---- every layer of Jarvis leaves its line -------------------------------------------------------------------
def test_a_spoken_turn_records_what_was_heard_what_claude_was_sent_and_what_came_back(root):
    from jarvis.tools import Registry, ToolContext
    from jarvis.tools.voice import VoiceTools
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.fakes import make_rig, utterance

    switch_on(root)

    async def main():
        rig = make_rig(scale=0.02, config=VoiceConfig(voice_id="fake-voice", core_root=str(root)),
                       reply=lambda text: "Your first class is GE 122 at 8:30.",
                       tools=VoiceTools(Registry(), lambda: ToolContext(root=root)))
        frames = utterance("what is my first class tomorrow")
        for f in frames:
            f.audio = b"\x02\x00" * 320             # the rig's frames are silent by default; his voice isn't
        tid = await rig.turn(frames)
        await rig.close()
        return tid

    tid = asyncio.run(main())
    kinds = [x["k"] for x in lines(root)]
    for kind in ("turn.heard", "llm.request", "llm.response", "turn.said", "turn.ended", "turn.timing"):
        assert kind in kinds, (kind, kinds)
    req = lines(root, "llm.request")[0]
    assert req["turn"] == tid and req["model"] == "claude-haiku-5-5" and "show_page" in req["tools"]
    assert req["messages"][-1] == {"role": "user", "content": "what is my first class tomorrow"}
    assert "Jarvis" in req["system"] and req["system_chars"] == len(req["system"])
    resp = lines(root, "llm.response")[0]
    assert resp["total_ms"] > 0 and resp["first_text_ms"] is not None
    assert lines(root, "turn.said")[0]["reply"] == "Your first class is GE 122 at 8:30."
    timing = lines(root, "turn.timing")[0]
    assert "llm_first_token" in timing["ms"] and timing["kind"] == "t1"            # a field called "kind" is fine
    assert lines(root, "turn.ended")[0]["wav"]                                    # and his side of it, as sound


def test_a_field_may_be_called_anything_without_breaking_the_turn(root):
    rec = switch_on(root)
    review.note("task", kind="research", key="orb", every_s=1, n=3, t="x", k="y")
    review.sampled("bus", "a", 0.0, kind="hub", key="b")
    got = lines(root)
    task = next(x for x in got if x["k"] == "task")
    assert task["kind"] == "research" and task["n_"] == 3 and task["t_"] == "x" and task["k_"] == "y"
    assert next(x for x in got if x["k"] == "bus")["kind"] == "hub" and rec.written >= 3


def test_a_tool_call_records_what_went_in_and_what_came_back(root):
    from jarvis.tools import Registry, ToolContext

    switch_on(root)
    out = asyncio.run(Registry().run("show_page", {"pages": [{"url": "https://example.com/a", "title": "A"}]},
                                     ToolContext(root=root)))
    assert not out.is_error
    line = lines(root, "tool")[0]
    assert line["tool"] == "show_page" and line["input"]["pages"][0]["title"] == "A"
    assert line["result"] == "On screen: A." and line["show"] == "window.push" and line["ms"] >= 0
    assert line["shown"]["data"]["pages"][0]["url"] == "https://example.com/a"


def test_the_core_records_buttons_bus_events_logs_with_their_errors_and_what_it_runs_on(root, monkeypatch):
    from jarvis.core import review_wiring

    monkeypatch.setattr(review_wiring, "LOAD_EVERY_S", 0.1)
    monkeypatch.setattr(review_wiring, "PROBE_S", 0.05)
    switch_on(root)
    config = Config.from_env({}, root=root, extra_hosts=("testserver",), keystore="memory", voice_preload=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("laptop-a", can_write=True)
    app = create_app(config, log_to_stderr=False)
    with TestClient(app) as c:
        head = {"X-Jarvis-Session": token}
        ok = c.post("/api/act", json={"action": "set", "target": "muted", "args": {"value": True}}, headers=head)
        assert ok.json()["ok"] is True
        try:
            raise ValueError("the reason it failed")
        except ValueError:
            logging.getLogger("jarvis.voice.pipeline").warning("voice.stt_failed", extra={"turn": "t9"})
        time.sleep(0.5)
        c.get("/api/health")
    got = lines(root)
    act = next(x for x in got if x["k"] == "act")
    assert act["action"] == "set" and act["args"] == {"value": True} and act["result"] == {"ok": True}
    assert any(x["k"] == "bus" and x["type"] == "settings.updated" for x in got)
    assert any(x["k"] == "log" and x["event"] == "http.request" and x["fields"]["route"] == "/api/act" for x in got)
    failed = next(x for x in got if x["k"] == "log" and x["event"] == "voice.stt_failed")
    assert failed["fields"]["turn"] == "t9" and "the reason it failed" in failed["trace"]   # the whole error, not its name
    env = next(x for x in got if x["k"] == "env")
    assert env["version"] == config.version and env["settings"]["muted"] is True and "anthropic" in env["packages"]
    load = next(x for x in got if x["k"] == "load")
    assert load["loop_late_ms"] >= 0 and "core_cpu_pct" in load
    raw = json.dumps(got)
    assert token not in raw                                                         # the pairing never lands in it
    ordinary = (config.log_file.read_text(encoding="utf-8") if config.log_file.exists() else "")
    assert "the reason it failed" not in ordinary                                   # the everyday log is unchanged


def test_the_voice_window_is_told_and_its_own_notes_are_kept(root, monkeypatch):
    from jarvis.voice import service as svc

    class Quiet:
        def __init__(self, out):
            self.out = out

        async def queue_frame(self, frame):
            pass

        async def stop(self):
            pass

    async def build(self, voice_id):
        out = svc.ClientAudio()
        return {"voice_id": voice_id, "pipeline": Quiet(out), "tts": None, "out": out}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)
    config = Config.from_env({}, root=root, extra_hosts=("testserver",), keystore="memory", voice_preload=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("laptop-a", can_write=True)
    app = create_app(config, log_to_stderr=False)
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}               # off: exactly as before
        switch_on(root)
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready", "review": True}
            ws.send_text(json.dumps({"type": "hello", "device": "laptop-a", "listen": "wake"}))
            ws.send_text(json.dumps({"type": "note", "what": "wake", "score": 0.83, "threshold": 0.5}))
            for i in range(30):
                ws.send_text(json.dumps({"type": "lv", "m": i / 100, "o": 0}))
            ws.send_text(json.dumps({"type": "listen", "on": True}))
            ws.send_bytes(bytes(640))
    got = lines(root)
    assert [x["what"] for x in got if x["k"] == "voice.session"] == ["connected", "disconnected"]
    note = next(x for x in got if x["k"] == "client.note")
    assert note == {**note, "device": "laptop-a", "what": "wake", "score": 0.83}
    client = [x["msg"]["type"] for x in got if x["k"] == "voice.client"]
    assert client.count("lv") == 1 and "hello" in client and "listen" in client       # the meter is thinned, not kept whole
    assert all("bytes" not in json.dumps(x) or x["k"] != "voice.client" for x in got)  # sound is never a line


def test_the_voice_windows_notes_are_numbers_only_and_quiet_when_nothing_happens():
    from types import SimpleNamespace as NS

    from jarvis.voice.client import Notes

    t = {"now": 100.0}
    mic = NS(frames=NS(qsize=lambda: 0), dropped=0, trouble=0)
    speaker = NS(play=NS(underruns=0), trouble=0)
    off = Notes(False, clock=lambda: t["now"])
    assert off.start(listen="wake") == [] and off.woke(0.9, 0.5) == [] and off.reply_done(speaker) == []
    n = Notes(True, clock=lambda: t["now"])
    assert n.start(listen="wake", mic={"name": "Realtek"})[0] == {"type": "note", "what": "start", "listen": "wake", "mic": {"name": "Realtek"}}
    assert n.tick(mic, speaker, asleep=True) == []                    # not yet 5 s
    t["now"] += 5.1
    first = n.tick(mic, speaker, asleep=True)[0]
    assert first["what"] == "window" and first["asleep"] is True and first["wake_peak"] == 0.0
    t["now"] += 5.1
    assert n.tick(mic, speaker, asleep=True) == []                    # nothing changed: quiet
    n.wake_score(0.41)                                                # a near miss on "hey Jarvis"
    t["now"] += 5.1
    assert n.tick(mic, speaker, asleep=True)[0]["wake_peak"] == 0.41
    speaker.play.underruns = 2                                        # his sound ran dry twice
    t["now"] += 5.1
    assert n.tick(mic, speaker, asleep=False)[0]["ran_dry"] == 2
    t["now"] += 61
    assert n.tick(mic, speaker, asleep=True)[0]["what"] == "window"   # once a minute regardless: it's alive
    n.audio(4800)
    t["now"] += 0.02
    n.audio(4800)
    t["now"] += 0.4                                                   # a 400 ms hole in the middle of a reply
    n.audio(4800)
    done = n.reply_done(speaker)[0]
    assert done["what"] == "reply_audio" and done["chunks"] == 3 and done["longest_wait_ms"] == 400
    assert done["seconds"] == 0.3 and n.reply_done(speaker) == []
    for msg in (first, done):
        assert all(isinstance(v, int | float | bool | str) for v in msg.values())


def test_a_recording_can_be_summarised_to_find_where_to_look_first(root, capsys):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("review_summary", Path(__file__).resolve().parents[1] / "tools" / "review_summary.py")
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)
    assert summary.main([str(root / "logs" / "review")]) == 1                    # nothing yet: says so
    rec = switch_on(root)
    rec.note("turn.heard", turn="t1", text="what's due")
    rec.note("turn.said", turn="t1", asked="what's due", reply="Two things.")
    rec.note("turn.ended", turn="t1", notes={"words": 2, "stop": "end_turn"}, extra={})
    rec.note("turn.ended", turn="t2", notes={"empty": True}, extra={})
    rec.note("turn.timing", turn="t1", kind="t1", ms={"vad_end": 0, "stt_final": 180.0, "llm_first_token": 900.0, "audio_out": 1500.0})
    rec.note("llm.request", turn="t1", round=0)
    rec.note("llm.response", turn="t1", round=0, stop="end_turn", first_text_ms=640.0, content=[{"type": "text", "text": "Two things."}])
    rec.note("llm.response", turn="t2", round=0, stop="end_turn", first_text_ms=None, content=[])
    rec.note("tool", tool="calendar", is_error=True, ms=2300.0)
    rec.note("log", level="warning", event="voice.tts_closed", fields={})
    rec.note("client.note", device="laptop-a", what="reply_audio", longest_wait_ms=420, ran_dry=1)
    rec.note("client.note", device="laptop-a", what="window", asleep=True, wake_peak=0.4, ran_dry=3, mic_dropped=0)
    rec.note("load", loop_late_ms=85.0, machine_cpu_pct=97.0)
    rec.flush()
    capsys.readouterr()
    assert summary.main([str(root / "logs" / "review")]) == 0
    text = capsys.readouterr().out
    for want in ("turns: 2 ended", "answered 1", "dropped or empty 1", "after he stops, llm_first_token: median 900 ms",
                 "replies with no words and no tool call: 1 (turns t2)", "calendar 1 (1 failed)", "voice.tts_closed 1",
                 "sound ran dry 3 times", "near misses on the wake word 1", "machine busiest 97%"):
        assert want in text, (want, text)


def test_real_turns_become_candidate_cases_with_the_ones_that_went_wrong_first(tmp_path, capsys):
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location("review_golden", "tools/review_golden.py")
    golden = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(golden)
    rows = [
        {"k": "tool", "tool": "stray"},                                              # before any turn: ignored
        {"k": "turn.heard", "text": "what's due this week"}, {"k": "tool", "tool": "school"},
        {"k": "turn.said", "reply": "Two things."}, {"k": "turn.ended"},
        {"k": "turn.heard", "text": "what room is my lab in"}, {"k": "tool", "tool": "calendar", "is_error": True},
        {"k": "tool", "tool": "school"}, {"k": "turn.said", "reply": "ENGR 2A20."}, {"k": "turn.ended"},
        {"k": "turn.heard", "text": "who won the game last night"}, {"k": "turn.said", "reply": ""}, {"k": "turn.ended"},
        {"k": "turn.heard", "text": "What's due this  week"}, {"k": "turn.said", "reply": "Same two."}, {"k": "turn.ended"},
        {"k": "turn.heard", "text": "yes"}, {"k": "turn.ended"},
    ]
    found = golden.candidates(rows)
    assert [(c["text"], c["picked"], c["why"], c["times"]) for c in found] == [
        ("who won the game last night", "none", "no answer", 1),
        ("what room is my lab in", "calendar", "a tool failed", 1),
        ("what's due this week", "school", "worked", 2)]
    assert found[1]["then"] == ["school"]
    day = tmp_path / "2026-11-23"
    day.mkdir()
    (day / "events.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
    assert golden.main([str(tmp_path)]) == 0
    assert len(json.loads((tmp_path / "golden-candidates.json").read_text(encoding="utf-8"))) == 3
    assert "3 candidate cases from 5 turns (2 went wrong)" in capsys.readouterr().out
    assert golden.main([str(tmp_path / "nothing")]) == 1
