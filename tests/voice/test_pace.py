"""v0.27.0, pace step 1: Jarvis waits at a pause according to how his words end, and records whether he carried on."""
import asyncio

import pytest

from jarvis.voice import pace
from jarvis.voice.config import VoiceConfig
from jarvis.voice.frames import (
    InputAudioRawFrame,
    TurnIncompleteFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from jarvis.voice.pipeline import TurnProcessor


@pytest.mark.parametrize("text, done, wait, why", [
    ("yes", True, 0, "quick"), ("no thanks", True, 0, "quick"), ("stop", True, 0, "quick"),
    ("pull up the physics assignment", True, 250, "clear"),
    ("a vertical spring stretches four centimetres and", True, 1600, "holder"),
    ("so the period is", True, 1600, "holder"), ("um", True, 1600, "holder"),
    ("this struggle", True, 600, "short"), ("", True, 450, "unheard"),
    ("what about the second question", False, 1500, "unfinished"), ("put canvas and", False, 2500, "unfinished"),
])
def test_the_wait_follows_how_his_words_end(text, done, wait, why):
    assert pace.patience_ms(text, smart_done=done) == (wait, why)


def test_his_pace_scales_the_wait_within_limits():
    assert pace.patience_ms("so the period is", smart_done=True, scale=2.0) == (2500, "holder")
    assert pace.patience_ms("pull up the physics assignment", smart_done=True, scale=0.5)[0] == 125
    assert pace.patience_ms("yes", smart_done=True, scale=3.0)[0] == 0


class Recorder:
    def __init__(self): self.notes = {}
    def note(self, turn, key, value): self.notes[(turn, key)] = value
    def get_note(self, turn, key, default=None): return self.notes.get((turn, key), default)


class Session:
    def __init__(self, patience=True):
        self.config, self.recorder, self.heard_so_far, self.pace_scale = VoiceConfig(patience=patience), Recorder(), "", 1.0
        self.ended = []

    def end_user_turn(self, turn): self.ended.append(turn)
    async def show_orb(self): pass


class Turn:
    def __init__(self, verdicts): self.verdicts = list(verdicts)
    def append(self, frame, speech): pass
    def clear(self): pass
    async def is_complete(self): return self.verdicts.pop(0)


def rig(verdicts, patience=True):
    session = Session(patience)
    proc, out = TurnProcessor(session, Turn(verdicts)), []

    async def push(frame, *a, **k): out.append(frame)

    proc.push_frame = push
    return proc, session, out


async def quiet(proc, ms, turn="t1"):
    for _ in range(int(ms / proc.session.config.frame_ms)):
        frame = InputAudioRawFrame(audio=b"\0\0")
        frame.turn_id = turn
        await proc.process_frame(frame)


def stopped(turn="t1", forced=False):
    frame = VADUserStoppedSpeakingFrame(turn_id=turn)
    frame.forced = forced
    return frame


def ends(out):
    return [f.turn_id for f in out if isinstance(f, UserStoppedSpeakingFrame)]


def test_a_clear_ending_waits_a_moment_then_ends_and_a_quick_answer_does_not_wait():
    async def scene():
        proc, session, out = rig([True, True])
        session.heard_so_far = "pull up the physics assignment"
        await proc.process_frame(stopped())
        assert ends(out) == []                                    # not at once any more
        await quiet(proc, 200)
        assert ends(out) == []
        await quiet(proc, 80)
        assert ends(out) == ["t1"] and session.recorder.notes[("t1", "end_why")] == "clear"
        session.heard_so_far = "yes"
        await proc.process_frame(stopped("t2"))
        assert ends(out) == ["t1", "t2"]                          # an answer or a command: no wait at all
    asyncio.run(scene())


def test_mid_sentence_he_keeps_the_floor_and_carrying_on_is_recorded():
    async def scene():
        proc, session, out = rig([True, True])
        session.heard_so_far = "a vertical spring stretches four centimetres and"
        await proc.process_frame(stopped())
        await quiet(proc, 1200)                                   # a long thinking pause
        assert ends(out) == [] and not any(isinstance(f, TurnIncompleteFrame) for f in out)   # the early answer keeps cooking
        await proc.process_frame(VADUserStartedSpeakingFrame(turn_id="t1"))                    # he carries on: same turn
        assert session.recorder.notes[("t1", "carried_on")] == 1
        session.heard_so_far = "a vertical spring stretches four centimetres and what is the spring constant"
        await proc.process_frame(stopped())
        await quiet(proc, 260)
        assert ends(out) == ["t1"] and session.recorder.notes[("t1", "pauses")] == 2
    asyncio.run(scene())


def test_unfinished_verdicts_and_the_talk_key_behave_as_before_and_off_changes_nothing():
    async def scene():
        proc, session, out = rig([False])
        session.heard_so_far = "what about the second question"
        await proc.process_frame(stopped())
        assert any(isinstance(f, TurnIncompleteFrame) for f in out)
        await quiet(proc, 1480)
        assert ends(out) == []
        await quiet(proc, 40)
        assert ends(out) == ["t1"]
        await proc.process_frame(stopped("t2", forced=True))
        assert ends(out) == ["t1", "t2"]                          # he let go of the talk key: over, at once
        old, session2, out2 = rig([True], patience=False)
        session2.heard_so_far = "so the period is"
        await old.process_frame(stopped())
        assert ends(out2) == ["t1"] and session2.recorder.notes == {}
    asyncio.run(scene())
