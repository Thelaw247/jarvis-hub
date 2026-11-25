"""T1 talker request shape and key handling, the chunker, and the ElevenLabs socket client (fake socket)."""
import asyncio
import base64
import json

import pytest

from jarvis.voice.chunker import Chunker
from jarvis.voice.config import VoiceConfig
from jarvis.voice.fakes import FakeAnthropic, FakeKeyed, FakeLatencies
from jarvis.voice.talker_t1 import TalkerT1
from jarvis.voice.tts_elevenlabs import ElevenLabsTTS


def test_request_caches_the_persona_and_keeps_the_now_card_out_of_the_cache():
    t = TalkerT1(VoiceConfig(llm_model="claude-haiku-5-5"), FakeKeyed(), now_card=lambda: "now: GE 122 at 10")
    req = t.build_request("hi")
    assert req["model"] == "claude-haiku-5-5"
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in req["system"][1]


def test_key_goes_through_keyed_client_and_sdk_clients_stay_warm():
    llm, keyed = FakeAnthropic(FakeLatencies(scale=0.0)), FakeKeyed("k-one")
    t = TalkerT1(VoiceConfig(), keyed, client_factory=llm.factory)

    async def main():
        got = []

        async def on(d):
            got.append(d)

        await t.stream("a", on)
        await t.stream("b", on)
        keyed.key = "k-two"  # a swap: the next request builds a client for the new key
        await t.stream("c", on)
        return got

    got = asyncio.run(main())
    assert "".join(got).startswith("Thursday")
    assert keyed.calls == 3 and llm.keys_seen == ["k-one", "k-two"]


@pytest.mark.parametrize("stream,expected", [
    (["Thursday ", "at ", "noon, ", "in ", "Engineering ", "1B71. ", "You ", "have ", "two ", "left."],
     ["Thursday at noon, in Engineering 1B71.", "You have two left."]),
    (["Yes, ", "it ", "is."], ["Yes, it is."]),  # short: the first clause waits for 6 words, then flush
    (["one two three four five six seven eight nine ten eleven twelve thirteen"],
     ["one two three four five six seven eight nine ten eleven twelve", "thirteen"]),
])
def test_chunker(stream, expected):
    c = Chunker()
    out = []
    for s in stream:
        out += c.feed(s)
    out += c.flush()
    assert out == expected


class FakeSocket:
    def __init__(self):
        self.sent, self.inbox, self.closed = [], asyncio.Queue(), False

    async def send(self, msg):
        m = json.loads(msg)
        self.sent.append(m)
        ctx = m.get("context_id")
        if m.get("text", "").strip():
            self.inbox.put_nowait(json.dumps({"contextId": ctx, "audio": base64.b64encode(b"pcm:" + m["text"].encode()).decode()}))
        if m.get("close_context"):
            self.inbox.put_nowait(json.dumps({"contextId": ctx, "isFinal": True}))

    async def recv(self):
        return await self.inbox.get()

    async def close(self):
        self.closed = True


def test_elevenlabs_client_over_a_fake_socket():
    sock, seen = FakeSocket(), {}

    async def connect(url, headers):
        seen.update(url=url, headers=dict(headers))
        return sock

    cfg = VoiceConfig(voice_id="designed-voice", tts_keepalive_s=0.05)

    async def main():
        tts = ElevenLabsTTS(cfg, FakeKeyed("k-el"), connect=connect)
        await tts.start()  # warm before the first turn
        await tts.open("turn-1")
        await tts.send("turn-1", "Thursday at noon.")
        await tts.flush("turn-1")
        audio = [a async for a in tts.audio("turn-1")]
        await asyncio.sleep(0.12)  # idle: keep-alives go out
        await tts.open("turn-2")
        await tts.cancel("turn-2")
        await tts.send("turn-2", "never spoken")
        whole = await tts.synthesize("Done.")
        await tts.aclose()
        return tts, audio, whole

    tts, audio, whole = asyncio.run(main())
    assert "/v1/text-to-speech/designed-voice/multi-stream-input?model_id=eleven_flash_v2_5" in seen["url"]
    assert "output_format=pcm_24000" in seen["url"]
    assert seen["headers"] == {"xi-api-key": "k-el"} and tts.connects == 1
    assert audio == [b"pcm:Thursday at noon. "]
    assert sock.sent[0]["voice_settings"]["stability"] == 0.4
    # idle with no context open: no keep-alive (a message without a context_id would close the socket)
    assert all("context_id" in m for m in sock.sent)
    assert {"context_id": "turn-2", "close_context": True} in sock.sent
    assert not any(m.get("text") == "never spoken " for m in sock.sent)
    assert whole == b"pcm:Done. " and sock.closed


def test_elevenlabs_refuses_to_start_without_the_designed_voice():
    tts = ElevenLabsTTS(VoiceConfig(voice_id=""), FakeKeyed())
    with pytest.raises(RuntimeError, match="designed Jarvis voice"):
        asyncio.run(tts.start())


def test_real_adapters_import_without_their_packages():
    import jarvis.voice.adapters_real as real

    assert real.SAMPLE_RATE == 16000


def test_tts_reconnects_when_the_elevenlabs_key_is_swapped():
    """Overseer (v0.5.0): keys.updated for a promote or a fallback re-opens the socket with the current key."""
    from jarvis.voice.tts_elevenlabs import follow_keys

    opened = []

    async def connect(url, headers):
        opened.append(headers["xi-api-key"])
        return FakeSocket()

    keyed = FakeKeyed("k-old")

    async def events():
        yield {"row": {"id": "elevenlabs", "status": "checking"}}  # a check: the live key is the same
        yield {"row": {"id": "anthropic"}, "audit": {"what": "replaced"}}  # another service
        keyed.key = "k-new"
        yield {"row": {"id": "elevenlabs", "status": "old_kept"}, "audit": {"what": "replaced"}}
        keyed.key = "k-old"
        yield {"row": {"id": "elevenlabs", "status": "fell_back"}, "audit": {"what": "fell_back"}}

    async def main():
        tts = ElevenLabsTTS(VoiceConfig(voice_id="designed-voice", tts_keepalive_s=5), keyed, connect=connect)
        await tts.start()
        await follow_keys(tts, events())
        await tts.aclose()

    asyncio.run(main())
    assert opened == ["k-old", "k-new", "k-old"]
