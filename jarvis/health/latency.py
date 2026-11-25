"""Latency harness (M0.5): stage timestamps per turn and a p50/p95 report per stage.

Stages, in order: VAD end -> STT final -> route -> LLM first token -> TTS first byte -> audio out.
Every time is kept as milliseconds after VAD end (the moment he stopped talking). Traces hold ids, stage
names, timings and flags only, never what was said (C21).
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAGES = ("vad_end", "stt_final", "route", "llm_first_token", "tts_first_byte", "audio_out")
ORDER = {
    "t0": ("vad_end", "route", "tts_first_byte", "audio_out"),
    "t1": STAGES,
}
LABELS = {
    "vad_end": "VAD end",
    "stt_final": "STT final",
    "route": "Route",
    "llm_first_token": "LLM first token",
    "tts_first_byte": "TTS first byte",
    "audio_out": "Audio out",
}
# p50 budget for each step (VOICE latency table) and the p95 targets for the whole path (BUILD_PLAN budget).
STEP_BUDGET_MS = {"stt_final": 150, "route": 50, "llm_first_token": 500, "tts_first_byte": 350, "audio_out": 60}
TOTAL_TARGET_MS = {"t0": 300, "t1": 1500}


@dataclass
class TurnTrace:
    turn_id: str
    kind: str = "t1"
    ms: dict[str, float] = field(default_factory=dict)       # stage -> ms after VAD end
    notes: dict[str, Any] = field(default_factory=dict)      # flags and counts only

    def to_json(self) -> str:
        return json.dumps({"turn": self.turn_id, "kind": self.kind, "ms": self.ms, "notes": self.notes},
                          separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> TurnTrace:
        d = json.loads(line)
        return cls(d["turn"], d.get("kind", "t1"), {k: float(v) for k, v in d["ms"].items()}, d.get("notes", {}))


class LatencyRecorder:
    """Collects stage marks per turn. ``mark`` is T0 (a dict write); the first mark of a stage wins."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter, sink: Path | None = None) -> None:
        self._clock = clock
        self._sink = sink
        self._open: dict[str, dict[str, Any]] = {}
        self._closed: set[str] = set()
        self.traces: list[TurnTrace] = []

    def _rec(self, turn_id: str) -> dict[str, Any] | None:
        if turn_id in self._closed:
            return None  # late marks (an STT final after a T0 reply finished) don't reopen a turn
        return self._open.setdefault(turn_id, {"marks": {}, "kind": "t1", "notes": {}})

    def mark(self, turn_id: str | None, stage: str, t: float | None = None) -> None:
        """T0. Stamp a stage for a turn (seconds on the session clock)."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage}")
        rec = self._rec(turn_id) if turn_id is not None else None
        if rec is not None:
            rec["marks"].setdefault(stage, self._clock() if t is None else t)

    def clear(self, turn_id: str | None, stage: str) -> None:
        """Forget a mark (he went on talking after a VAD stop, so that wasn't the end of speech)."""
        rec = self._open.get(turn_id) if turn_id is not None else None
        if rec is not None:
            rec["marks"].pop(stage, None)

    def has(self, turn_id: str | None, stage: str) -> bool:
        return turn_id in self._open and stage in self._open[turn_id]["marks"]

    def kind(self, turn_id: str | None, kind: str) -> None:
        rec = self._rec(turn_id) if turn_id is not None else None
        if rec is not None:
            rec["kind"] = kind

    def note(self, turn_id: str | None, key: str, value: Any) -> None:
        rec = self._rec(turn_id) if turn_id is not None else None
        if rec is not None:
            rec["notes"][key] = value

    def notes(self, turn_id: str | None) -> dict[str, Any]:
        rec = self._open.get(turn_id) if turn_id is not None else None
        return dict(rec["notes"]) if rec is not None else {}

    def get_note(self, turn_id: str | None, key: str, default: Any = None) -> Any:
        rec = self._open.get(turn_id) if turn_id is not None else None
        return default if rec is None else rec["notes"].get(key, default)

    def finish(self, turn_id: str | None) -> TurnTrace | None:
        """Close a turn. Turns with no VAD end (e.g. typed) are dropped from the voice report."""
        rec = self._open.pop(turn_id, None) if turn_id is not None else None
        if turn_id is not None:
            self._closed.add(turn_id)
        if rec is None or "vad_end" not in rec["marks"]:
            return None
        base = rec["marks"]["vad_end"]
        trace = TurnTrace(turn_id, rec["kind"], {s: round((t - base) * 1000.0, 3) for s, t in rec["marks"].items()},
                          dict(rec["notes"]))
        self.traces.append(trace)
        if self._sink is not None:
            self._sink.parent.mkdir(parents=True, exist_ok=True)
            with self._sink.open("a", encoding="utf-8") as f:
                f.write(trace.to_json() + "\n")
        return trace


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile (same as numpy's default). ``q`` in [0, 100]."""
    if not values:
        return math.nan
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return float(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo))


@dataclass(frozen=True)
class StageRow:
    kind: str
    stage: str
    n: int
    p50_ms: float          # ms after VAD end
    p95_ms: float
    step_p50_ms: float     # ms since the previous stage of this kind
    step_p95_ms: float
    budget_ms: float | None


@dataclass(frozen=True)
class Report:
    rows: list[StageRow]
    turns: dict[str, int]
    totals: dict[str, dict[str, float]]   # kind -> {p50, p95, target, ok}
    notes: dict[str, float]

    def row(self, kind: str, stage: str) -> StageRow | None:
        return next((r for r in self.rows if r.kind == kind and r.stage == stage), None)


def build_report(traces: Iterable[TurnTrace]) -> Report:
    by_kind: dict[str, list[TurnTrace]] = {}
    for tr in traces:
        by_kind.setdefault(tr.kind, []).append(tr)
    rows: list[StageRow] = []
    totals: dict[str, dict[str, float]] = {}
    for kind in ("t0", "t1"):
        trs = by_kind.get(kind, [])
        order = ORDER[kind]
        for i, stage in enumerate(order):
            since = [tr.ms[stage] for tr in trs if stage in tr.ms]
            steps = []
            for tr in trs:
                if stage not in tr.ms:
                    continue
                prev = next((tr.ms[s] for s in reversed(order[:i]) if s in tr.ms), None)
                if prev is not None:
                    steps.append(tr.ms[stage] - prev)
            if not since:
                continue
            rows.append(StageRow(kind, stage, len(since), percentile(since, 50), percentile(since, 95),
                                 percentile(steps, 50) if steps else 0.0, percentile(steps, 95) if steps else 0.0,
                                 STEP_BUDGET_MS.get(stage) if stage != "vad_end" else None))
        ends = [tr.ms["audio_out"] for tr in trs if "audio_out" in tr.ms]
        if ends:
            p95 = percentile(ends, 95)
            totals[kind] = {"p50": percentile(ends, 50), "p95": p95, "target": TOTAL_TARGET_MS[kind],
                            "ok": float(p95 <= TOTAL_TARGET_MS[kind])}
    spec = [tr.notes["speculation"] for tr in by_kind.get("t1", []) if "speculation" in tr.notes]
    notes = {}
    if spec:
        notes["speculation_hit_rate"] = sum(1 for s in spec if s == "hit") / len(spec)
    partial = [tr.notes.get("routed_on_partial", False) for tr in by_kind.get("t0", [])]
    if partial:
        notes["t0_routed_on_partial_rate"] = sum(1 for p in partial if p) / len(partial)
    return Report(rows, {k: len(v) for k, v in by_kind.items()}, totals, notes)


def format_table(report: Report) -> str:
    out = ["kind  stage            n    p50     p95   | step p50  step p95  budget(p50)"]
    for r in report.rows:
        budget = f"{r.budget_ms:>6.0f}" if r.budget_ms is not None else "     -"
        out.append(f"{r.kind:<5} {LABELS[r.stage]:<16} {r.n:>3} {r.p50_ms:>7.1f} {r.p95_ms:>7.1f} |"
                   f" {r.step_p50_ms:>8.1f} {r.step_p95_ms:>9.1f}  {budget}")
    for kind, t in report.totals.items():
        name = "command" if kind == "t0" else "chat"
        verdict = "OK" if t["ok"] else "OVER"
        out.append(f"{name} end of speech -> first sound: p50 {t['p50']:.1f} ms, p95 {t['p95']:.1f} ms"
                   f" (target p95 <= {t['target']:.0f} ms) {verdict}")
    for k, v in report.notes.items():
        out.append(f"{k}: {v:.0%}")
    return "\n".join(out)


def to_metrics_latency(report: Report) -> list[dict[str, float | str]]:
    """Rows for contracts/metrics.schema.json ``latency`` (the hub's Under the hood view)."""
    picks = [
        ("t1", "stt_final", "Hear (speech to text)"),
        ("t0", "route", "Route (commands)"),
        ("t1", "llm_first_token", "Think (first words)"),
        ("t1", "tts_first_byte", "Speak (first sound)"),
    ]
    rows: list[dict[str, float | str]] = []
    for kind, stage, label in picks:
        r = report.row(kind, stage)
        if r is not None:
            rows.append({"stage": label, "p50_ms": round(r.step_p50_ms, 1), "p95_ms": round(r.step_p95_ms, 1),
                         "target_ms": float(STEP_BUDGET_MS[stage])})
    for kind, label in (("t0", "Command (end of speech to sound)"), ("t1", "Chat (end of speech to sound)")):
        t = report.totals.get(kind)
        if t:
            rows.append({"stage": label, "p50_ms": round(t["p50"], 1), "p95_ms": round(t["p95"], 1),
                         "target_ms": float(t["target"])})
    return rows


def load_traces(path: Path) -> list[TurnTrace]:
    return [TurnTrace.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def report_dict(report: Report) -> Mapping[str, Any]:
    return {
        "turns": report.turns,
        "rows": [r.__dict__ for r in report.rows],
        "totals": report.totals,
        "notes": report.notes,
        "metrics_latency": to_metrics_latency(report),
    }
