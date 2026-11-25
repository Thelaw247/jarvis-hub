"""A first look at a review recording (jarvis/review): what happened, in numbers, so the reading can start at the
worst places.

    python tools/review_summary.py                 # C:\\Jarvis\\logs\\review (or JARVIS_ROOT)
    python tools/review_summary.py <review folder>

Reads every <date>/events.jsonl and prints, per day: turns and how they ended, the wait at each stage, what the
model and the tools did, every warning by name, what the voice window reported (sound running dry, the longest wait
inside a reply, near misses on the wake word) and the machine's load. Reads only; changes nothing.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load(folder: Path) -> dict[str, list[dict]]:
    days: dict[str, list[dict]] = {}
    for f in sorted(folder.glob("*/events.jsonl")):
        rows = []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        days[f.parent.name] = rows
    return days


def pct(values: list[float], q: float) -> float:
    xs = sorted(values)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else float("nan")


def spread(values: list[float], unit: str = "ms") -> str:
    if not values:
        return "none"
    return f"median {statistics.median(values):.0f} {unit}, 9 in 10 under {pct(values, 0.9):.0f}, worst {max(values):.0f} (n={len(values)})"


def summarise(day: str, rows: list[dict]) -> list[str]:
    by = defaultdict(list)
    for r in rows:
        by[r.get("k")].append(r)
    out = [f"== {day}: {len(rows)} lines =="]
    ended = {}
    for r in by["turn.ended"]:
        ended[r.get("turn")] = {**(ended.get(r.get("turn")) or {}), **(r.get("notes") or {}), **(r.get("extra") or {})}
    heard = {r.get("turn"): r.get("text", "") for r in by["turn.heard"]}
    said = {r.get("turn"): r.get("reply", "") for r in by["turn.said"]}
    outcome = Counter()
    for turn, notes in ended.items():
        if notes.get("interrupted"):
            outcome["interrupted"] += 1
        elif notes.get("no_reply"):
            outcome["no reply (said sorry)"] += 1
        elif notes.get("empty") or notes.get("dropped"):
            outcome["dropped or empty"] += 1
        elif said.get(turn):
            outcome["answered"] += 1
        else:
            outcome["ended with nothing said"] += 1
    out.append(f"turns: {len(ended)} ended, {len(heard)} heard as words, {len(said)} answered in words")
    out.append("  how they ended: " + (", ".join(f"{k} {v}" for k, v in outcome.most_common()) or "none"))
    flags = Counter(k for notes in ended.values() for k, v in notes.items() if v not in (None, False, 0, "", "end_turn"))
    out.append("  flags on turns: " + (", ".join(f"{k} {v}" for k, v in flags.most_common(14)) or "none"))
    stages = defaultdict(list)
    for r in by["turn.timing"]:
        for stage, ms in (r.get("ms") or {}).items():
            if stage != "vad_end":
                stages[stage].append(float(ms))
    for stage in ("stt_final", "route", "llm_first_token", "tts_first_byte", "audio_out"):
        out.append(f"  after he stops, {stage}: {spread(stages[stage])}")
    out.append(f"model: {len(by['llm.request'])} requests, {len(by['llm.error'])} errors; stops: "
               + (", ".join(f"{k} {v}" for k, v in Counter(str(r.get('stop')) for r in by['llm.response']).most_common()) or "none"))
    out.append("  first words after: " + spread([float(r["first_text_ms"]) for r in by["llm.response"] if r.get("first_text_ms") is not None]))
    empty = [r for r in by["llm.response"] if not any((b or {}).get("type") in ("text", "tool_use") for b in r.get("content") or [])]
    out.append(f"  replies with no words and no tool call: {len(empty)}" + (f" (turns {', '.join(str(r.get('turn')) for r in empty[:8])})" if empty else ""))
    tools = Counter(r.get("tool") for r in by["tool"])
    errors = Counter(r.get("tool") for r in by["tool"] if r.get("is_error"))
    out.append("tools: " + (", ".join(f"{t} {n}" + (f" ({errors[t]} failed)" if errors[t] else "") for t, n in tools.most_common()) or "none"))
    slow = sorted(by["tool"], key=lambda r: -float(r.get("ms") or 0))[:3]
    if slow:
        out.append("  slowest: " + ", ".join(f"{r.get('tool')} {float(r.get('ms') or 0):.0f} ms" for r in slow))
    warn = Counter(f"{r.get('event')}" for r in by["log"] if r.get("level") in ("warning", "error", "critical"))
    out.append("warnings: " + (", ".join(f"{k} {v}" for k, v in warn.most_common(16)) or "none"))
    notes = defaultdict(list)
    for r in by["client.note"]:
        notes[r.get("what")].append(r)
    replies = notes["reply_audio"]
    out.append(f"voice window: {len(notes['wake'])} wake-ups, {len(replies)} replies played; longest wait inside a reply: "
               + spread([float(r.get("longest_wait_ms") or 0) for r in replies]))
    window = notes["window"]
    if window:
        near = [r for r in window if r.get("asleep") and 0.15 <= float(r.get("wake_peak") or 0)]
        out.append(f"  sound ran dry {max(int(r.get('ran_dry') or 0) for r in window)} times, mic frames dropped "
                   f"{max(int(r.get('mic_dropped') or 0) for r in window)}, near misses on the wake word {len(near)}")
    load_rows = by["load"]
    if load_rows:
        out.append("load: event loop late " + spread([float(r.get("loop_late_ms") or 0) for r in load_rows])
                   + f"; machine busiest {max(float(r.get('machine_cpu_pct') or 0) for r in load_rows):.0f}%")
    sessions = Counter(f"{r.get('what')} {r.get('device')}" for r in by["voice.session"])
    out.append("voice connections: " + (", ".join(f"{k} x{v}" for k, v in sessions.items()) or "none"))
    acts = Counter(f"{r.get('action')}" + ("" if (r.get("result") or {}).get("ok") else " (refused)") for r in by["act"])
    out.append("buttons: " + (", ".join(f"{k} {v}" for k, v in acts.most_common(12)) or "none"))
    return out


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis") / "logs" / "review"
    days = load(folder)
    if not days:
        print(f"Nothing recorded in {folder} yet.")
        return 1
    for day, rows in days.items():
        print("\n".join(summarise(day, rows)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
