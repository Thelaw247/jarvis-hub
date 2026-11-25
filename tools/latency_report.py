"""Latency report: p50/p95 per voice stage (M0.5).

    python tools/latency_report.py                       # 50-utterance scripted run with fakes
    python tools/latency_report.py --from C:/Jarvis/logs/latency.jsonl
    python tools/latency_report.py --json                # the hub's Under the hood rows (metrics.latency)

Traces hold ids and timings only (C21). Exit code 1 if a path misses its p95 target (with --strict).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jarvis.health.latency import build_report, format_table, load_traces, report_dict  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", type=Path, help="a latency.jsonl written by the core")
    ap.add_argument("-n", type=int, default=50, help="utterances in the scripted run (default 50)")
    ap.add_argument("--scale", type=float, default=0.25, help="fake-latency time scale for the scripted run")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a path misses its p95 target")
    args = ap.parse_args(argv)

    extra: dict = {}
    if args.src:
        report = build_report(load_traces(args.src))
        source = str(args.src)
    else:
        from jarvis.health.scripted import run_scripted_sync

        res = run_scripted_sync(args.n, scale=args.scale)
        report = res.report
        source = f"scripted run, {res.turns} utterances, fakes (simulated ms, time scale {res.scale})"
        extra = {"spend": res.spend, "speculation": res.speculation}

    if args.json:
        print(json.dumps({"source": source, **report_dict(report), **extra}, indent=1, default=float))
    else:
        print(f"Latency report: {source}")
        print(format_table(report))
        if extra:
            print(f"speculation: {extra['speculation']}")
            print(f"spend: {extra['spend']}")
    if args.strict and not all(t["ok"] for t in report.totals.values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
