"""The voice window, end to end with a fake sound card and a fake core: it starts, sends his voice and its meter,
plays Jarvis through the soft-edged speaker, and survives the messages the core sends (v0.14.0)."""
import argparse
import asyncio
import json
import sys
import threading
import time
import types

import numpy as np
import pytest


class FakeIn:
    made = []

    def __init__(self, **kw):
        self.kw, self.on = kw, False
        FakeIn.made.append(self)

    def start(self):
        self.on = True
        cb, n = self.kw["callback"], self.kw["blocksize"]
        t = np.arange(n) / 16000

        def pump():
            block = (np.sin(2 * np.pi * 220 * t) * 6000).astype(np.int16).tobytes()
            while self.on:
                cb(block, n, None, None)
                time.sleep(n / 16000)

        threading.Thread(target=pump, daemon=True).start()

    def stop(self):
        self.on = False

    close = stop

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.stop()


class FakeOut:
    made = []

    def __init__(self, **kw):
        self.kw, self.on, self.heard = kw, False, []
        FakeOut.made.append(self)

    def start(self):
        self.on = True
        cb, n = self.kw["callback"], self.kw["blocksize"]

        def pump():
            while self.on:
                out = bytearray(n * 2)
                cb(out, n, None, None)
                self.heard.append(bytes(out))
                time.sleep(n / self.kw["samplerate"])

        threading.Thread(target=pump, daemon=True).start()

    def stop(self):
        self.on = False

    close = stop


class FakeWs:
    def __init__(self, script):
        self.sent, self._script = [], script
        self._first = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        return json.dumps({"type": "ready"})

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._script:
            raise StopAsyncIteration
        delay, msg = self._script.pop(0)
        await asyncio.sleep(delay)
        return msg


@pytest.fixture
def fake_audio(monkeypatch, tmp_path):
    FakeIn.made, FakeOut.made = [], []
    sd = types.ModuleType("sounddevice")
    sd.RawInputStream, sd.RawOutputStream = FakeIn, FakeOut
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setenv("JARVIS_ROOT", str(tmp_path))
    return sd


def test_the_voice_window_runs_a_whole_exchange(fake_audio, monkeypatch):
    from jarvis.voice import client

    voice = (np.sin(2 * np.pi * 300 * np.arange(24000) / 24000) * 9000).astype(np.int16).tobytes()   # 1 s of Jarvis
    script = [(0.15, json.dumps({"type": "orb", "state": "listening"})),
              (0.05, json.dumps({"type": "orb", "state": "speaking"})),
              (0.0, voice[:24000]), (0.0, voice[24000:]),
              (0.3, json.dumps({"type": "duck", "on": True})),
              (0.1, json.dumps({"type": "duck", "on": False})),
              (0.1, json.dumps({"type": "stop"})),
              (0.2, json.dumps({"type": "orb", "state": "idle"})),
              (0.1, "not json"), (0.1, json.dumps({"type": "error", "message": "bye"}))]
    ws = FakeWs(script)
    websockets = types.ModuleType("websockets")
    websockets.connect = lambda *a, **kw: ws
    monkeypatch.setitem(sys.modules, "websockets", websockets)
    args = argparse.Namespace(barge_in=False, half_duplex=False, mic=None, speaker=None, listen="always")
    why = asyncio.run(asyncio.wait_for(client.session("ws://x/ws/voice", "tok", args), 20))
    assert why == "bye" or "closed" in why
    hello = json.loads(ws.sent[0])
    assert hello["type"] == "hello" and hello["listen"] == "always"
    frames = [m for m in ws.sent if isinstance(m, bytes)]
    meters = [json.loads(m) for m in ws.sent[1:] if isinstance(m, str) and '"lv"' in m]
    assert len(frames) > 20 and all(len(f) == 640 for f in frames)        # his voice went to the core
    assert len(meters) >= 5 and max(m["m"] for m in meters) > 0.3          # with the mic's level
    assert max(m["o"] for m in meters) > 0.3                               # and Jarvis's own, while he spoke
    played = np.frombuffer(b"".join(FakeOut.made[0].heard), dtype=np.int16).astype(np.int32)
    assert np.abs(played).max() > 5000                                     # Jarvis was heard
    assert np.abs(np.diff(played)).max() < 3000                            # and nowhere did he click (a 300 Hz tone
    #                                                                        at 9000 moves < 710 a sample; a hard cut
    #                                                                        from full level would be up to 18000)


def test_asleep_it_sends_the_meter_but_none_of_his_voice(fake_audio, monkeypatch):
    from jarvis.voice import client

    class Hot:
        score = 0.0

        def feed(self, frame):
            return False

        def preroll(self):
            return []

    monkeypatch.setattr(client, "listen_setup", lambda args, loop: (client.Gate("wake"), Hot(), None))
    ws = FakeWs([(0.6, json.dumps({"type": "error", "message": "done"}))])
    websockets = types.ModuleType("websockets")
    websockets.connect = lambda *a, **kw: ws
    monkeypatch.setitem(sys.modules, "websockets", websockets)
    args = argparse.Namespace(barge_in=False, half_duplex=False, mic=None, speaker=None, listen="wake")
    asyncio.run(asyncio.wait_for(client.session("ws://x/ws/voice", "tok", args), 20))
    assert json.loads(ws.sent[0])["listen"] == "wake"
    assert not [m for m in ws.sent if isinstance(m, bytes)]                # nothing he said left the laptop
    meters = [json.loads(m) for m in ws.sent[1:] if isinstance(m, str)]
    assert meters and all(set(m) == {"type", "m", "o"} for m in meters)   # only loudness figures
