"""Phrase cache: render once, store under the core root, play from disk; a voice change re-renders."""
import asyncio

from jarvis.voice.config import VoiceConfig
from jarvis.voice.fakes import FakeLatencies, FakeTts, make_rig, utterance
from jarvis.voice.phrases import PhraseBook, PhraseCache
from jarvis.voice.ports import PendingApproval


def cache(tmp_path, tts, voice="v1"):
    return PhraseCache(tmp_path, voice_id=voice, model="eleven_flash_v2_5", settings={"stability": 0.5},
                       output_format="pcm_24000", render=tts.synthesize)


def test_renders_once_and_plays_from_disk(tmp_path):
    tts = FakeTts(FakeLatencies(scale=0.01))

    async def main():
        c = cache(tmp_path, tts)
        assert c.get("Done.") is None
        audio = await c.ensure("Done.")
        again = await c.ensure("Done.")
        await asyncio.gather(*(c.ensure("Booked.") for _ in range(5)))  # concurrent asks share one render
        return c, audio, again

    c, audio, again = asyncio.run(main())
    assert tts.synthesized == ["Done.", "Booked."]
    assert audio == again and c.get("Done.") == audio
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "manifest.json" in files and len([f for f in files if f.endswith(".pcm")]) == 2
    # a new process reads the same manifest: no render
    assert cache(tmp_path, tts).get("Done.") == audio


def test_voice_change_misses_and_prune_removes_old_audio(tmp_path):
    tts = FakeTts(FakeLatencies(scale=0.01))
    asyncio.run(cache(tmp_path, tts, "v1").warm(["Done.", "Sent."]))
    c2 = cache(tmp_path, tts, "v2")
    assert c2.get("Done.") is None
    assert c2.prune() == 2
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".pcm"]


def test_phrase_dir_is_under_the_core_root():
    assert VoiceConfig(core_root="C:/Jarvis").phrase_dir.as_posix() == "C:/Jarvis/data/voice/phrases"


def test_pipeline_plays_a_cached_phrase_without_tts(tmp_path):
    async def main():
        rig = make_rig(scale=0.05, phrase_dir=tmp_path)
        await rig.phrases.warm(["What should change?"])
        rig.tts.synthesized.clear()
        rig.approvals.current = PendingApproval("ap-1", outward=False, asked_at=rig.session.clock())
        tid = await rig.turn(utterance("change it"))
        await rig.close()
        return rig, tid

    rig, tid = asyncio.run(main())
    assert rig.tts.sent == [] and rig.tts.synthesized == []
    assert rig.session.spend.cached_phrase_plays == 1 and rig.session.spend.characters == 0
    trace = rig.session.recorder.traces[-1]
    assert trace.turn_id == tid and "audio_out" in trace.ms


def test_a_missed_phrase_is_spoken_live_and_rendered_for_next_time(tmp_path):
    async def main():
        rig = make_rig(scale=0.05, phrase_dir=tmp_path)
        rig.approvals.current = PendingApproval("ap-1", outward=False, asked_at=rig.session.clock())
        await rig.turn(utterance("change it"))
        await asyncio.sleep(0.05)
        await rig.close()
        return rig

    rig = asyncio.run(main())
    assert [t for _, t in rig.tts.sent] == ["What should change?"]
    assert rig.phrases.has("What should change?")


def test_rotation_never_repeats_within_the_last_five():
    book = PhraseBook({"ack": ("a", "b", "c", "d", "e", "f")})
    picks = [book.pick("ack") for _ in range(30)]
    for i in range(5, len(picks)):
        assert picks[i] not in picks[i - 5:i]
