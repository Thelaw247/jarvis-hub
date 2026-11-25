"""v0.14.0: what the speech model gets wrong for him becomes a note Jarvis reads with every question."""
import json

from jarvis.voice.config import VoiceConfig
from jarvis.voice.fakes import FakeKeyed
from jarvis.voice.lessons import SENTENCES, align, misheard, vocabulary_note
from jarvis.voice.talker_t1 import TalkerT1


def test_words_that_came_out_wrong_are_paired_with_what_he_said():
    said = "open the lecture slides for g e one twenty two".split()
    heard = "open the lecture slights for gee one twenty".split()
    pairs = align(said, heard)
    assert ("slides", "slights") in pairs and ("open", "open") in pairs
    assert misheard(pairs) == [("slides", "slights"), ("g e", "gee")]      # neighbours join; a dropped word alone isn't a habit
    assert misheard(align("stop".split(), "stop".split())) == []


def test_the_note_is_read_with_every_question(tmp_path):
    assert vocabulary_note(tmp_path) == ""                                 # no lesson yet: nothing added
    (tmp_path / "voice").mkdir()
    (tmp_path / "voice" / "vocabulary.json").write_text(json.dumps(
        {"checked": "2026-11-19", "misheard": [["canvas", "campus"], ["crowdmark", "crowd mark"], ["", "x"]]}))
    note = vocabulary_note(tmp_path)
    assert 'heard "campus" → he most likely said "canvas"' in note and "crowd mark" in note and '"x"' not in note
    talker = TalkerT1(VoiceConfig(voice_id="v"), FakeKeyed())
    talker.hearing_note = note
    request = talker.build_request("is anything new on campus")
    assert any("campus" in block["text"] for block in request["system"])
    (tmp_path / "voice" / "vocabulary.json").write_text("not json")
    assert vocabulary_note(tmp_path) == ""                                 # a broken file never breaks a turn


def test_the_sentences_are_things_he_would_really_say():
    assert len(SENTENCES) >= 20 and len(set(SENTENCES)) == len(SENTENCES)
    assert any("Canvas" in s for s in SENTENCES) and any(len(s.split()) <= 2 for s in SENTENCES)
