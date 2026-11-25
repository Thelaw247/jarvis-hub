"""The voice loop inside the core (/ws/voice, jarvis/voice/service.py): who may connect, what it says when voice
isn't ready, and the round trip: mic frames in, Jarvis's audio out, orb on the bus, one client at a time."""
import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from jarvis.core.app import create_app
from jarvis.core.config import Config
from jarvis.core.sessions import HubSessions
from jarvis.voice import service as svc


@pytest.fixture
def config(tmp_path):
    return Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver",), keystore="memory",
                           voice_preload=False)


def pair(config, name, write=True):
    return HubSessions(config.data_dir / "hub_sessions.json").pair(name, can_write=write)


class EchoPipeline:
    """Stands in for the real pipeline: every mic frame comes straight back as Jarvis's audio."""

    def __init__(self, out, bus):
        self.out, self.bus, self.frames = out, bus, 0

    async def queue_frame(self, frame):
        self.frames += 1
        if self.frames == 3:
            self.bus.publish("orb.state", {"state": "speaking"})
            await self.out.write(b"\x01\x02" * 240)

    async def stop(self):
        pass


@pytest.fixture
def ready_voice(monkeypatch):
    async def build(self, voice_id):
        out = svc.ClientAudio()
        return {"voice_id": voice_id, "pipeline": EchoPipeline(out, self.bus), "tts": None, "out": out}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)


def test_only_paired_devices_that_may_act_can_talk(config):
    app = create_app(config, log_to_stderr=False)
    phone = pair(config, "phone", write=False)
    with TestClient(app) as c:
        for headers, code in (({}, 4401), ({"X-Jarvis-Session": "nope"}, 4401), ({"X-Jarvis-Session": phone}, 4403)):
            with pytest.raises(WebSocketDisconnect) as err, c.websocket_connect("/ws/voice", headers=headers) as ws:
                ws.receive_text()
            assert err.value.code == code


def test_says_what_is_missing_when_voice_is_not_set_up(config):
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    with TestClient(app) as c:
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            msg = json.loads(ws.receive_text())
        assert msg["type"] == "error" and "setup-voice.bat" in msg["message"]
        assert c.get("/healthz").json()["status"] == "green"                      # voice is optional: still green
        status = c.get("/api/voice", headers={"X-Jarvis-Session": token}).json()
    assert status["status"] == "off" and "setup-voice.bat" in status["missing"]


def test_mic_in_voice_out_and_the_orb_on_the_bus(config, ready_voice):
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            for _ in range(3):
                ws.send_bytes(bytes(640))
            assert ws.receive_bytes() == b"\x01\x02" * 240                      # Jarvis's voice back to the laptop
            state = c.get("/api/state", headers={"X-Jarvis-Session": token}).json()
            assert state["orb"]["state"] == "speaking"                          # the hub's orb follows the voice
            assert c.get("/api/voice", headers={"X-Jarvis-Session": token}).json()["device"] == "laptop-b"
        state = c.get("/api/state", headers={"X-Jarvis-Session": token}).json()
        assert state["orb"]["state"] == "idle"                                  # gone quiet when the laptop left


def test_the_hello_tunes_the_glow_to_his_voice(config, ready_voice, monkeypatch):
    """v0.12.3: the voice window passes on the Hearing check's range; the core's glow uses it for his voice."""
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.session import VoiceSession

    session = VoiceSession(VoiceConfig(voice_id="x"))
    built = svc.VoiceService._build

    async def build(self, voice_id):
        parts = await built(self, voice_id)
        return {**parts, "session": session}

    monkeypatch.setattr(svc.VoiceService, "_build", build)
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            ws.send_text(json.dumps({"type": "hello", "device": "laptop-b", "glow": {"quiet_db": -62, "loud_db": -41}}))
            ws.send_text("not json")
            for _ in range(3):
                ws.send_bytes(bytes(640))
            assert ws.receive_bytes()                                           # still serving after the junk
    assert session.level_range == (-62.0, -41.0)


def test_a_newer_laptop_takes_over(config, ready_voice):
    app = create_app(config, log_to_stderr=False)
    a, b = pair(config, "laptop-a"), pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": b}) as first:
            assert json.loads(first.receive_text())["type"] == "ready"
            with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": a}) as second:
                assert json.loads(second.receive_text())["type"] == "ready"
                kicked = json.loads(first.receive_text())
                assert kicked["code"] == "taken_over" and "took over" in kicked["message"]
                assert c.get("/api/voice", headers={"X-Jarvis-Session": a}).json()["device"] == "laptop-a"


def test_restart_only_from_laptop_b_itself(config, monkeypatch):
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    exits = []
    import jarvis.core.app as core_app
    monkeypatch.setattr(core_app.os, "_exit", lambda code: exits.append(code))
    with TestClient(app) as c:
        assert c.post("/api/restart").status_code == 401
        r = c.post("/api/restart", headers={"X-Jarvis-Session": token})
        assert r.status_code == 200 and "Restarting" in r.json()["message"]


def test_voice_url_follows_the_hub_setting():
    from jarvis.voice.client import voice_url

    assert voice_url("http://127.0.0.1:8770") == "ws://127.0.0.1:8770/ws/voice"
    assert voice_url("https://laptop-b.tail1234.ts.net/") == "wss://laptop-b.tail1234.ts.net/ws/voice"


def test_a_window_that_was_taken_over_stops_instead_of_taking_it_back(monkeypatch, capsys):
    """Two Talk to Jarvis windows used to take the voice from each other every 2 s, forever."""
    import argparse
    import asyncio

    from jarvis.voice import client

    calls = []

    async def kicked(url, token, args):
        calls.append(url)
        return client.TAKEN_OVER

    monkeypatch.setattr(client, "session", kicked)
    monkeypatch.setenv("JARVIS_CORE_SESSION", "token")
    assert asyncio.run(client.run(argparse.Namespace())) == 0
    assert len(calls) == 1
    assert "has the voice now" in capsys.readouterr().out


class RecordingPipeline:
    """Keeps every frame, so the test sees what the core made of the talk key."""

    def __init__(self, out):
        self.out, self.got = out, []

    async def queue_frame(self, frame):
        self.got.append(frame)
        if len(self.got) == 6:
            await self.out.write(b"\x01\x02" * 240)   # so the test knows everything before it arrived

    async def stop(self):
        pass


def test_the_talk_key_marks_its_frames_and_release_ends_the_turn(config, monkeypatch):
    """v0.13.0: frames while the key is held are his; the first is marked (stop Jarvis now); release ends the turn."""
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.session import VoiceSession

    session = VoiceSession(VoiceConfig(voice_id="x"))
    holder = {}

    async def build(self, voice_id):
        out = svc.ClientAudio()
        events = svc.BusEvents(self.bus)
        holder["pipeline"] = RecordingPipeline(out)
        return {"voice_id": voice_id, "pipeline": holder["pipeline"], "tts": None, "out": out,
                "session": session, "events": events}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            ws.send_bytes(bytes(640))                                  # before the key: hands-free
            ws.send_text(json.dumps({"type": "ptt", "down": True}))
            ws.send_bytes(bytes(640))
            ws.send_bytes(bytes(640))
            ws.send_text(json.dumps({"type": "ptt", "down": False}))
            ws.send_bytes(bytes(640))                                  # after: hands-free again
            ws.send_bytes(bytes(640))
            assert ws.receive_bytes()
            state = c.get("/api/state", headers={"X-Jarvis-Session": token}).json()
    got = holder["pipeline"].got
    assert got[-1].meta.get("end_turn")                                # the window left: any open turn is closed
    got = got[:-1]
    assert [f.ptt for f in got] == [False, True, True, True, False, False]
    assert got[1].meta.get("ptt_down") and not got[2].meta.get("ptt_down")
    assert got[3].meta.get("ptt_release")
    assert state["orb"]["state"] == "idle"                             # pressed and let go with nothing said


def test_hey_jarvis_shows_on_the_orb_and_the_orb_goes_back_to_the_window(config, monkeypatch):
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.session import VoiceSession

    holder = {}

    async def build(self, voice_id):
        out = svc.ClientAudio()
        events = svc.BusEvents(self.bus)
        holder["events"] = events
        session = VoiceSession(VoiceConfig(voice_id="x"), events=events)
        return {"voice_id": voice_id, "pipeline": RecordingPipeline(out), "tts": None, "out": out,
                "session": session, "events": events}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": token}) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            ws.send_text(json.dumps({"type": "listen", "on": True}))
            ws.send_bytes(bytes(640))
            listening = None
            for _ in range(50):
                listening = c.get("/api/state", headers={"X-Jarvis-Session": token}).json()["orb"]["state"]
                if listening == "listening":
                    break
            assert json.loads(ws.receive_text()) == {"type": "orb", "state": "listening"}   # awake: shown at once
            c.portal.call(holder["events"].publish, "orb.state", {"state": "thinking"})
            assert json.loads(ws.receive_text()) == {"type": "orb", "state": "thinking"}
            c.portal.call(holder["events"].publish, "orb.state", {"state": "listening", "level": 0.4})
            c.portal.call(holder["events"].publish, "orb.state", {"state": "idle"})
            assert json.loads(ws.receive_text()) == {"type": "orb", "state": "idle"}   # level ticks stay on the bus
    assert listening == "listening"


# ---- v0.15.0: the hub runs the voice, politely ------------------------------------------------------------------
def test_a_hub_that_asks_politely_waits_its_turn_and_gets_the_voice_when_the_other_leaves(config, ready_voice):
    app = create_app(config, log_to_stderr=False)
    a, b = pair(config, "laptop-a"), pair(config, "laptop-b")
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers={"X-Jarvis-Session": b}) as first:
            assert json.loads(first.receive_text())["type"] == "ready"
            with c.websocket_connect("/ws/voice?polite=1", headers={"X-Jarvis-Session": a}) as second:
                busy = json.loads(second.receive_text())
                assert busy["type"] == "error" and busy["code"] == "busy" and busy["device"] == "laptop-b"
            assert c.get("/api/voice", headers={"X-Jarvis-Session": a}).json()["device"] == "laptop-b"  # untouched
            first.send_bytes(bytes(640))            # and still served
        with c.websocket_connect("/ws/voice?polite=1", headers={"X-Jarvis-Session": a}) as again:
            assert json.loads(again.receive_text())["type"] == "ready"      # the other closed: now it's this one's


def test_a_hosted_voice_window_waits_and_takes_only_when_told(monkeypatch, capsys):
    import argparse
    import asyncio

    from jarvis.voice import client

    calls = []
    answers = [client.BUSY + "laptop-b", client.BUSY + "laptop-b", "ok-then-drop", client.TAKEN_OVER, "stop"]

    async def session(url, token, args):
        calls.append(url)
        why = answers.pop(0)
        if why == "stop":
            raise KeyboardInterrupt
        return why

    monkeypatch.setattr(client, "session", session)
    monkeypatch.setattr(client, "watch_host", lambda loop, take: None)
    monkeypatch.setattr(client, "WAIT_TURN_S", 0.01)
    monkeypatch.setenv("JARVIS_CORE_SESSION", "token")
    real_sleep = asyncio.sleep

    async def quick(seconds):
        await real_sleep(0)

    monkeypatch.setattr(client.asyncio, "sleep", quick)
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(client.run(argparse.Namespace(hosted=True, take=False)))
    assert all(u.endswith("?polite=1") for u in calls)          # it never takes the voice by itself,
    assert len(calls) == 5                                      # and being taken over doesn't make it give up
    out = capsys.readouterr().out
    assert out.count("@@ waiting laptop-b") == 2 and "@@ waiting" in out.splitlines()[-1] or "@@ waiting" in out
    calls.clear()
    answers[:] = ["stop"]
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(client.run(argparse.Namespace(hosted=True, take=True)))
    assert calls == [client.voice_url("http://127.0.0.1:8770")]  # "Talk here": this once, it takes it


def test_the_hubs_microphone_switch_mutes_and_follows_a_spoken_mute(config, monkeypatch):
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.session import VoiceSession

    holder = {}

    async def build(self, voice_id):
        out = svc.ClientAudio()
        events = svc.BusEvents(self.bus)
        events.on_muted = lambda muted: self.on_muted(muted) if self.on_muted is not None else None
        holder["session"] = VoiceSession(VoiceConfig(voice_id="x"), events=events)
        return {"voice_id": voice_id, "pipeline": RecordingPipeline(out), "tts": None, "out": out,
                "session": holder["session"], "events": events}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)
    app = create_app(config, log_to_stderr=False)
    token = pair(config, "laptop-b")
    head = {"X-Jarvis-Session": token}

    def muted_setting(c):
        return c.get("/api/state", headers=head).json()["settings"].get("muted")

    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        with c.websocket_connect("/ws/voice", headers=head) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            s = holder["session"]
            ok = c.post("/api/act", json={"action": "set", "target": "muted", "args": {"value": True}}, headers=head)
            assert ok.json()["ok"] is True
            assert s.muted is True and muted_setting(c) is True               # the switch mutes the mic
            assert c.post("/api/act", json={"action": "set", "target": "muted", "args": {"value": False}},
                          headers=head).json()["ok"] is True
            assert s.muted is False and muted_setting(c) is False             # and is the way back on
            s.muted = True                                                    # "mute the microphone", said aloud
            c.portal.call(s.show_orb)
            c.portal.call(s.settled)
            assert muted_setting(c) is True                                   # the switch follows


def test_the_voice_brain_setting_switches_the_model_without_a_restart_and_is_remembered(config, monkeypatch):
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.talker_t1 import TalkerProcessor, TalkerT1

    class Parts:
        def __init__(self, out, talker):
            self.out, self.processors = out, [TalkerProcessor.__new__(TalkerProcessor)]
            self.processors[0].talker = talker

        async def queue_frame(self, frame):
            pass

        async def stop(self):
            pass

    made = {}

    async def build(self, voice_id):
        out = svc.ClientAudio()
        made["talker"] = TalkerT1(VoiceConfig(voice_id="x", llm_model=svc.BRAINS[self.brain]), keyed=None)
        return {"voice_id": voice_id, "pipeline": Parts(out, made["talker"]), "tts": None, "out": out}

    monkeypatch.setattr(svc.VoiceService, "missing", lambda self: "")
    monkeypatch.setattr(svc.VoiceService, "_build", build)
    head = {"X-Jarvis-Session": pair(config, "laptop-b")}

    def choose(c, value):
        return c.post("/api/act", json={"action": "set", "target": "voice_brain", "args": {"value": value}},
                      headers=head).json()["ok"]

    app = create_app(config, log_to_stderr=False)
    with TestClient(app) as c:
        app.state.voice.settings.set_voice_id("JBFqnCBsd6RMkjVDRZzb")
        assert c.get("/api/state", headers=head).json()["settings"]["voice_brain"] == "quick"   # shown from the start
        with c.websocket_connect("/ws/voice", headers=head) as ws:
            assert json.loads(ws.receive_text()) == {"type": "ready"}
            assert made["talker"].build_request("hi")["model"] == "claude-haiku-5-5"
            assert choose(c, "deep") is True
            assert made["talker"].build_request("hi")["model"] == "claude-sonnet-5-5"            # his next sentence
            assert choose(c, "opus") is False                                                    # only the two
            assert made["talker"].build_request("hi")["model"] == "claude-sonnet-5-5"
    again = create_app(config, log_to_stderr=False)                                              # after a restart
    with TestClient(again) as c:
        assert again.state.voice.brain == "deep"
        assert c.get("/api/state", headers=head).json()["settings"]["voice_brain"] == "deep"


def test_both_voice_brains_have_a_price_so_the_spend_meter_counts_them():
    from jarvis.health.spend import Prices

    assert set(svc.BRAINS.values()) <= set(Prices().anthropic)
