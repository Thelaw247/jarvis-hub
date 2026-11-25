"""v0.14.0: Jarvis's voice starts, stops and survives gaps without a click, and the speaker stays awake."""
import numpy as np

from jarvis.voice.client import Meter
from jarvis.voice.playout import DUCKED, KEEP_AWAKE_AMPLITUDE, Playout

RATE = 24_000
BLOCK = 240   # 10 ms


def tone(seconds, amp=12000, hz=220):
    t = np.arange(int(RATE * seconds)) / RATE
    return (np.sin(2 * np.pi * hz * t) * amp).astype(np.int16)


def play(p, blocks):
    return np.concatenate([p.pull(BLOCK) for _ in range(blocks)]).astype(np.int32)


def biggest_jump(x):
    return int(np.abs(np.diff(x)).max())


def test_his_voice_fades_in_and_out_instead_of_starting_and_stopping_on_a_sample():
    p = Playout(RATE, keep_awake=False)
    voice = np.full(int(RATE * 0.5), 12000, dtype=np.int16)        # the worst case: full level from sample one
    p.feed(voice.tobytes())
    out = play(p, 60)
    assert out[0] < 200 and out[-1] == 0                           # starts from silence, ends in silence
    assert biggest_jump(out) < 12000 / 200                         # no step anywhere: a ramp of >= 200 samples
    assert out[int(RATE * 0.02):int(RATE * 0.4)].min() == 12000    # full level in between, untouched
    assert p.underruns == 0


def test_a_stop_is_a_short_fade_and_the_rest_is_dropped():
    p = Playout(RATE, keep_awake=False)
    p.feed(np.full(RATE * 2, 12000, dtype=np.int16).tobytes())
    play(p, 10)
    p.stop()
    out = play(p, 10)
    assert biggest_jump(out) < 12000 / 200
    assert out[int(RATE * 0.02):].max() == 0                       # silent within 20 ms
    assert p.buffered_s == 0.0                                     # the two seconds still to come are gone
    p.feed(tone(0.2).tobytes())                                    # and the next thing he says plays normally
    assert np.abs(play(p, 25)).max() > 10000


def test_a_gap_in_the_audio_fades_instead_of_clicking():
    p = Playout(RATE, keep_awake=False)
    p.feed(np.full(int(RATE * 0.1), 12000, dtype=np.int16).tobytes())
    first = play(p, 15)                                            # runs dry after 100 ms
    p.feed(np.full(int(RATE * 0.1), 12000, dtype=np.int16).tobytes())
    second = play(p, 15)
    both = np.concatenate([first, second])
    assert biggest_jump(both) < 12000 / 200
    assert first[-1] == 0 and second[0] < 200


def test_being_talked_over_lowers_him_smoothly_and_brings_him_back():
    p = Playout(RATE, keep_awake=False)
    p.feed(np.full(RATE, 12000, dtype=np.int16).tobytes())
    play(p, 10)
    p.duck(True)
    down = play(p, 10)
    assert biggest_jump(down) < 60
    assert abs(int(down[-1]) - int(12000 * DUCKED)) <= 2
    p.duck(False)
    up = play(p, 10)
    assert biggest_jump(up) < 60 and up[-1] == 12000


def test_the_speaker_never_goes_fully_silent_while_the_window_is_open():
    p = Playout(RATE, keep_awake=True)
    quiet = play(p, 50)
    assert np.abs(quiet).max() <= KEEP_AWAKE_AMPLITUDE and np.abs(quiet).max() > 0     # there, and far below hearing
    assert np.count_nonzero(quiet) > quiet.size // 2
    assert Playout(RATE, keep_awake=False).pull(BLOCK).max() == 0


def test_it_knows_how_loud_jarvis_is_right_now():
    p = Playout(RATE, keep_awake=False)
    assert p.level == 0.0 and not p.active
    p.feed(tone(0.3, amp=9000).tobytes())
    play(p, 10)
    assert p.level > 0.6 and p.active
    play(p, 40)
    assert p.level == 0.0 and not p.active                         # he stopped: so does the glow


def test_feeding_and_pulling_from_two_threads_loses_nothing():
    import threading

    p = Playout(RATE, keep_awake=False)
    total = 200 * 480

    def feeder():
        for _ in range(200):
            p.feed(np.full(480, 1000, dtype=np.int16).tobytes())

    t = threading.Thread(target=feeder)
    t.start()
    heard = 0
    for _ in range(4000):
        heard += int(np.count_nonzero(p.pull(BLOCK)))
        if not t.is_alive() and p.buffered_s == 0:
            break
    t.join()
    assert heard >= total - 50 * 2     # every sample came out (less the few at each fade's zero end)


def test_the_meter_gives_the_loudest_of_the_last_80_ms_on_his_own_range():
    m = Meter(-62.0, -41.0)
    loud = (np.sin(2 * np.pi * 300 * np.arange(320) / 16000) * 32768 * 10 ** (-41 / 20) * np.sqrt(2)).astype(np.int16).tobytes()
    assert m.feed(bytes(640), 0.0, now=10.0) == (0.0, 0.0)
    assert m.feed(loud, 0.2, now=10.02) is None                    # not yet: 12 a second
    assert m.feed(bytes(640), 0.7, now=10.04) is None
    got = m.feed(bytes(640), 0.1, now=10.09)
    assert got is not None and got[0] >= 0.95 and got[1] == 0.7    # the peak of both since the last one
    assert Meter("junk", None).range == Meter().range              # no hearing check: the standard range
