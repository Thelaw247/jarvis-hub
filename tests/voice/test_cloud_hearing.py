"""v0.25.0: his Cloud hearing switch. ElevenLabs writes his words down when it is on and working; the laptop's own
model takes the same sound the moment it isn't, so a turn is never lost to the switch."""
import asyncio
import base64
import json
from types import SimpleNamespace

from jarvis.voice.stt_cloud import CloudStt, Hearing


class Keyed:
    async def call(self, fn): return await fn("not-a-real-key")


class Socket:
    """A pretend ElevenLabs: echoes how much sound it has as the partial, settles the text on commit."""

    def __init__(self, say="pull up the physics assignment", fail_on=None):
        self.say, self.fail_on, self.got, self.sent, self.closed = say, fail_on, 0, [], False
        self.inbox: asyncio.Queue = asyncio.Queue()

    async def send(self, raw):
        if self.closed:
            raise ConnectionError("closed")
        msg = json.loads(raw)
        self.sent.append(msg)
        self.got += len(base64.b64decode(msg["audio_base_64"]))
        if self.fail_on == "commit" and msg["commit"]:
            await self.inbox.put({"message_type": "auth_error"})
        elif msg["commit"]:
            await self.inbox.put({"message_type": "committed_transcript", "text": self.say})
        else:
            await self.inbox.put({"message_type": "partial_transcript", "text": f"{self.got} bytes"})

    def __aiter__(self): return self

    async def __anext__(self):
        msg = await self.inbox.get()
        if msg is None:
            raise StopAsyncIteration
        return json.dumps(msg)

    async def close(self):
        self.closed = True
        await self.inbox.put(None)


class Local:
    def __init__(self): self.heard, self.finals = b"", 0

    async def accept_many(self, frames):
        self.heard += b"".join(f.audio for f in frames)
        return f"local {len(self.heard)}"

    async def finalize(self):
        self.finals += 1
        text, self.heard = (f"local heard {len(self.heard)} bytes" if self.heard else ""), b""
        return text


def frame(n=320): return SimpleNamespace(audio=b"\x01\x02" * (n // 2))


def rig(sockets, on=True, clock=None):
    made, headers = [], []

    async def connect(url, head):
        assert url.startswith("wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime") and "commit_strategy=manual" in url
        headers.append(dict(head))
        sock = sockets.pop(0)
        if isinstance(sock, Exception):
            raise sock
        made.append(sock)
        return sock

    local = Local()
    hearing = Hearing(local, CloudStt(Keyed(), connect=connect, final_wait_s=0.5), on=on, **({"clock": clock} if clock else {}))
    return hearing, local, made, headers


def test_off_is_the_default_and_nothing_leaves_the_laptop():
    async def scene():
        hearing, local, made, _ = rig([Socket()], on=False)
        assert Hearing(local, None).on is False
        assert await hearing.accept(frame()) == "local 320"
        assert await hearing.finalize() == "local heard 320 bytes" and made == []
    asyncio.run(scene())


def test_on_the_sound_goes_to_elevenlabs_and_the_settled_text_comes_back():
    async def scene():
        hearing, local, made, headers = rig([Socket()])
        await hearing.accept(frame())
        await asyncio.sleep(0.01)
        assert await hearing.accept_many([frame(), frame()]) == "320 bytes"      # the words so far, as they come
        assert await hearing.finalize() == "pull up the physics assignment"
        sock = made[0]
        assert headers == [{"xi-api-key": "not-a-real-key"}] and local.heard == b"" and local.finals == 0
        assert [m["commit"] for m in sock.sent] == [False, False, True] and sock.sent[0]["sample_rate"] == 16000
        assert sock.sent[-1]["audio_base_64"] == "" and sock.got == 960
        await hearing.accept(frame())                                           # the next turn reuses the open socket
        assert await hearing.finalize() == "pull up the physics assignment" and len(made) == 1
        assert await hearing.finalize() == ""                                   # nothing said: nothing asked of anyone
    asyncio.run(scene())


def test_when_elevenlabs_cannot_be_used_the_laptop_hears_the_whole_turn_and_takes_the_next_minute():
    async def scene():
        now = [100.0]
        hearing, local, made, _ = rig([ConnectionError("no network"), Socket(fail_on="commit"), Socket()], clock=lambda: now[0])
        assert await hearing.accept(frame()) == "local 320"                      # could not connect: nothing lost
        await hearing.accept(frame())
        assert await hearing.finalize() == "local heard 640 bytes" and hearing.fell_back == 1
        await hearing.accept(frame())                                           # still resting: the laptop, no new socket
        assert await hearing.finalize() == "local heard 320 bytes" and made == []
        now[0] += 61
        await hearing.accept(frame())
        await hearing.accept(frame())                                           # back on ElevenLabs...
        assert local.heard == b"" and len(made) == 1
        assert await hearing.finalize() == "local heard 640 bytes"              # ...which refuses the key at the end
        assert hearing.fell_back == 2 and made[0].closed
        now[0] += 61
        await hearing.accept(frame())
        assert await hearing.finalize() == "pull up the physics assignment"     # and works again later
    asyncio.run(scene())


def test_the_switch_changes_who_hears_from_his_next_sentence():
    async def scene():
        hearing, local, made, _ = rig([Socket(), Socket()], on=False)
        await hearing.accept(frame())
        await hearing.set_on(True)
        await hearing.accept(frame())                                           # this turn began on the laptop: it stays
        assert await hearing.finalize() == "local heard 640 bytes" and made == []
        await hearing.accept(frame())
        assert await hearing.finalize() == "pull up the physics assignment"
        await hearing.set_on(False)
        assert made[0].closed
        await hearing.accept(frame())
        assert await hearing.finalize() == "local heard 320 bytes"
    asyncio.run(scene())


def test_the_core_keeps_his_choice_and_the_hub_can_flip_it(tmp_path):
    from jarvis.core import hub_settings
    from jarvis.core.settings import CoreSettings

    assert hub_settings.is_valid(True, hub_settings.setting_schema("cloud_hearing"))
    assert not hub_settings.is_valid("yes", hub_settings.setting_schema("cloud_hearing"))
    settings = CoreSettings(tmp_path / "settings.json")
    settings.set_hub("cloud_hearing", True)
    assert CoreSettings(tmp_path / "settings.json").hub()["cloud_hearing"] is True
