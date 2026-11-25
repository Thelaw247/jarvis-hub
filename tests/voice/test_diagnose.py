"""v0.14.0: the opt-in test recording. Off unless he switches it on; then it keeps what was heard and said."""
import asyncio
import time
import wave

from jarvis.voice import diagnose
from jarvis.voice.config import VoiceConfig
from jarvis.voice.fakes import make_rig, utterance


def test_nothing_is_recorded_unless_he_switched_it_on(tmp_path):
    async def main():
        rig = make_rig(scale=0.02, config=VoiceConfig(voice_id="fake-voice", core_root=tmp_path))
        await rig.turn(utterance("when is my next lab"))
        await rig.close()
        return rig

    rig = asyncio.run(main())
    assert rig.session.debug is None
    assert not (tmp_path / "voice" / "diagnose").exists()


def test_switched_on_it_keeps_what_was_heard_what_was_said_and_his_side_as_sound(tmp_path):
    diagnose.switch(True, 20, tmp_path)

    async def main():
        rig = make_rig(scale=0.02, config=VoiceConfig(voice_id="fake-voice", core_root=tmp_path),
                       reply=lambda text: "Thursday at noon.")
        for f in utterance("when is my next lab"):
            f.audio = b"\x01\x00" * 320
        frames = utterance("when is my next lab")
        for f in frames:
            f.audio = b"\x01\x00" * 320
        await rig.turn(frames)
        await rig.close()
        return rig

    asyncio.run(main())
    folder = tmp_path / "voice" / "diagnose"
    text = (folder / "conversation.txt").read_text(encoding="utf-8")
    assert "heard: 'when is my next lab'" in text
    assert "Jarvis said: 'Thursday at noon.'" in text and "ended:" in text
    wavs = list(folder.glob("turn-*.wav"))
    assert len(wavs) == 1
    with wave.open(str(wavs[0])) as w:
        assert w.getframerate() == 16000 and w.getnframes() > 320 * 5


def test_it_switches_itself_off(tmp_path):
    t = diagnose.switch(True, 20, tmp_path)
    rec = diagnose.Diagnose.current(tmp_path, None)
    assert rec is not None and diagnose.Diagnose.current(tmp_path, rec) is rec     # the same one while it's on
    diagnose.flag(tmp_path).write_text(str(int(time.time()) - 5), encoding="ascii")  # its time is up
    assert diagnose.Diagnose.current(tmp_path, rec) is None
    diagnose.switch(True, 20, tmp_path)
    diagnose.switch(False, root=tmp_path)
    assert diagnose.until(tmp_path) == 0.0 and t > time.time()
