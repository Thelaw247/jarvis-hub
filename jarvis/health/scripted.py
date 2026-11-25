"""The 50-utterance scripted run (M0.5 exit): a fixed conversation through the whole pipeline, with a latency
report at the end. With fakes it checks the plumbing and the harness; on Laptop B the same script runs with
the real adapters and a recorded voice.

Fake service latencies are scaled by ``scale`` to keep the run short; reported times are divided by ``scale``
again so they read as simulated real-time milliseconds (pipeline overhead is inflated by the same factor, so
the simulated numbers are conservative).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from jarvis.health.latency import Report, TurnTrace, build_report
from jarvis.voice.fakes import FakeLatencies, make_rig, utterance

# (text, options). 18 commands, 32 chat turns; some pause mid-sentence (Smart Turn: still talking), some
# have a final transcript that differs from the last partial (speculation must be thrown away).
SCRIPT: list[tuple[str, dict[str, Any]]] = [
    ("what time is it", {}),
    ("when is my next lab", {}),
    ("set a timer for five minutes", {}),
    ("whats due this week", {}),
    ("volume up", {}),
    ("how long is the walk to engineering", {}),
    ("open ge 122", {}),
    ("what did the prof say about the midterm", {"pause_after_word": 3}),
    ("stop", {}),
    ("summarize my email from canvas", {}),
    ("whats the time", {}),
    ("remind me what pps 7 covers", {}),
    ("set volume to 40", {}),
    ("is the chem lab on thursday", {"final": "is the chem lab on tuesday"}),
    ("cancel the timer", {}),
    ("what should I study tonight", {}),
    ("pull up the thermo deck", {}),
    ("how many questions are left in pps 7", {}),
    ("mute", {"ptt": True}),
    ("unmute", {"ptt": True}),
    ("what is a phasor", {}),
    ("time check", {}),
    ("when does the library close", {"pause_after_word": 2}),
    ("louder", {}),
    ("explain kirchhoffs voltage law in one line", {}),
    ("set a 10 minute timer", {}),
    ("whats next on my calendar", {}),
    ("show me pen reader", {}),
    ("did riley reply about the squad meeting", {}),
    ("what time is it", {"ptt": True}),
    ("how much is left on my spend cap", {}),
    ("quieter", {}),
    ("what was the answer to question three", {"final": "what was the answer to question four"}),
    ("whats the weather tomorrow morning", {}),
    ("never mind", {}),
    ("give me one tip for the math quiz", {}),
    ("open my week plan", {}),
    ("which room is the geol lecture in", {}),
    ("what time is it", {}),
    ("how far am I into the thermo reading", {"pause_after_word": 4}),
    ("set a timer for twenty minutes", {}),
    ("what is the derivative of sine", {}),
    ("volume down", {}),
    ("when is the chem 142 worksheet due", {}),
    ("whats the time now", {}),
    ("read me the last line again", {}),
    ("bring up the lab manual", {}),
    ("anything I am forgetting today", {}),
    ("stop talking", {}),
    ("thanks that is all for now", {}),
]


@dataclass
class ScriptedResult:
    traces: list[TurnTrace]
    report: Report
    spend: dict[str, Any]
    speculation: dict[str, int]
    turns: int
    scale: float


def _unscale(traces: list[TurnTrace], scale: float) -> list[TurnTrace]:
    if scale == 1.0:
        return traces
    return [TurnTrace(t.turn_id, t.kind, {k: round(v / scale, 3) for k, v in t.ms.items()}, dict(t.notes))
            for t in traces]


async def run_scripted(n: int = 50, *, scale: float = 0.25, lat: FakeLatencies | None = None) -> ScriptedResult:
    lat = lat or FakeLatencies(scale=scale)
    rig = make_rig(lat=lat)
    try:
        for i in range(n):
            text, opts = SCRIPT[i % len(SCRIPT)]
            await rig.turn(utterance(text, **opts), timeout=30.0)
    finally:
        await rig.close()
    from jarvis.voice.talker_t1 import TalkerProcessor

    stats = rig.pipeline.get(TalkerProcessor).stats
    traces = _unscale(rig.session.recorder.traces, lat.scale)
    return ScriptedResult(traces, build_report(traces), rig.session.spend.to_metrics(), dict(stats), n, lat.scale)


def run_scripted_sync(n: int = 50, *, scale: float = 0.25) -> ScriptedResult:
    return asyncio.run(run_scripted(n, scale=scale))
