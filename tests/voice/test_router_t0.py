"""T0 router: the reflexes, the approval grammar, and the < 50 ms budget (micro-benchmark)."""
import time
from datetime import datetime

import pytest

from jarvis.health.latency import percentile
from jarvis.voice.fakes import FakeApprovals
from jarvis.voice.ports import PendingApproval
from jarvis.voice.router_t0 import RouterT0, normalize

NOW = datetime(2026, 11, 15, 16, 12)


def router(**kw):
    return RouterT0(now=lambda: NOW, **kw)


@pytest.mark.parametrize("text,intent,args", [
    ("What time is it?", "time", None),
    ("Hey Jarvis, what's the time", "time", None),
    ("set a timer for five minutes", "timer.set", {"seconds": 300}),
    ("Set a 10 minute timer please", "timer.set", {"seconds": 600}),
    ("timer for an hour", "timer.set", {"seconds": 3600}),
    ("remind me in two and a half minutes", "timer.set", {"seconds": 150}),
    ("cancel the timer", "timer.cancel", None),
    ("stop", "stop", None),
    ("Never mind.", "stop", None),
    ("mute", "mute", None),
    ("unmute", "unmute", None),
    ("volume up", "volume.up", {"delta": 10}),
    ("quieter", "volume.down", {"delta": -10}),
    ("set volume to 40%", "volume.set", {"level": 40}),
    ("volume 250", "volume.set", {"level": 100}),
])
def test_commands(text, intent, args):
    res = router().route(text)
    assert res is not None and res.intent == intent
    if args is not None:
        assert dict(res.command.args) == args
    assert res.safe_on_partial


@pytest.mark.parametrize("text", [
    "when is my next lab", "show me what's due", "open question: what is a phasor", "what is the time constant of an RC circuit",
    "yes", "stop the bleeding in chapter three means what", "",
    "Open GE 122", "pull up the thermo deck", "pull up the physics assignment",  # nothing here can open: the talker's tools do
])
def test_everything_else_goes_to_the_talker(text):
    assert router().route(text) is None


def test_time_reply_is_short_and_formal():
    assert router().route("what time is it").reply == "It's 4:12."


def test_open_uses_the_resolver_and_falls_through_when_unknown():
    r = router(resolve_open=lambda q: "ge-122" if q == "ge 122" else None)
    assert r.route("open GE 122").command.args["target"] == "ge-122"
    assert r.route("open the pod bay doors") is None
    assert dict(r.route("pull up GE 122").command.args) == {"query": "ge 122", "target": "ge-122"}


def test_normalize():
    assert normalize("Hey Jarvis, could you set a timer for 5 minutes, please?") == "set a timer for 5 minutes"
    assert normalize("What’s the time?") == "whats the time"


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def test_approval_grammar():
    box, clock = FakeApprovals(), Clock()
    r = router(approvals=box, clock=clock, approval_window_s=10)
    assert r.route("book it") is None  # nothing pending: not an answer
    box.current = PendingApproval("ap-1", outward=False, asked_at=95.0)
    yes = r.route("Book it")
    assert yes.intent == "approval.yes" and yes.command.args == {"id": "ap-1", "answer": "yes"}
    assert not yes.safe_on_partial  # never fired on a partial
    assert r.route("not now").intent == "approval.later"
    assert r.route("no").intent == "approval.no"
    assert r.route("change it").intent == "approval.edit"
    assert r.route("yes but make it 3 pm") is None  # longer answers are the talker's
    clock.t = 106.0
    assert r.route("yes") is None  # window over


def test_outward_actions_need_send_it():
    box = FakeApprovals(PendingApproval("ap-2", outward=True, asked_at=0.0))
    r = router(approvals=box, clock=lambda: 1.0)
    hint = r.route("yes")
    assert hint.intent == "approval.hint" and hint.command is None
    assert r.route("send it").intent == "approval.yes"
    assert r.route("post it").intent == "approval.yes"


def test_t0_micro_benchmark_under_50_ms():
    box = FakeApprovals(PendingApproval("ap-3", outward=False, asked_at=0.0))
    r = router(approvals=box, clock=lambda: 1.0)
    samples = ["what time is it", "set a timer for twenty minutes", "when is my next lab and what room is it in",
               "volume up", "open ge 122", "book it", "summarize the email from my chem prof about the lab"]
    times = []
    for i in range(2000):
        t0 = time.perf_counter()
        r.route(samples[i % len(samples)])
        times.append((time.perf_counter() - t0) * 1000)
    p95 = percentile(times, 95)
    print(f"T0 route p50 {percentile(times, 50) * 1000:.1f} us, p95 {p95 * 1000:.1f} us")
    assert p95 < 5.0  # budget 50 ms; a regex router should be ~1000x under it
