"""Real turns from the review recording, as candidate test cases for the tool-choice check (tools/eval_routing.py).

    python tools/review_golden.py [<root>/logs/review] [--out golden.json]

JARVIS_RESEARCH_GOOD_AGENT.md, proposal 1: the cases that tell us whether Jarvis got better should be the things he
really said, not the ones we made up. For each turn in the recording this keeps what he said, the first tool Jarvis
used ("none" for a straight answer), whether that tool failed, and whether he got an answer at all. Turns that went
wrong come first: those are the ones worth turning into cases.

It only proposes. Nothing is added to the check until a case is confirmed (what the right first tool was), and the
output stays on the laptop with the recording: it holds his words.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def turns(rows: list[dict]) -> list[dict]:
    """The recording's rows, folded into one record per turn (tools belong to the turn they follow)."""
    out: list[dict] = []
    cur: dict | None = None
    for r in rows:
        kind = r.get("k")   # the recording writes each row's kind as "k"
        if kind == "turn.heard" and str(r.get("text") or "").strip():
            cur = {"text": str(r["text"]).strip(), "tools": [], "failed": [], "answered": False}
            out.append(cur)
        elif cur is None:
            continue
        elif kind == "tool":
            cur["tools"].append(str(r.get("tool")))
            if r.get("is_error"):
                cur["failed"].append(str(r.get("tool")))
        elif kind == "turn.said":
            cur["answered"] = cur["answered"] or bool(str(r.get("reply") or "").strip())
        elif kind == "turn.ended":
            cur = None
    return out


def candidates(rows: list[dict], limit: int = 60) -> list[dict]:
    """One candidate per distinct thing he said: went-wrong first (no answer, a failed tool), then the rest."""
    seen: dict[str, dict] = {}
    for t in turns(rows):
        key = " ".join(t["text"].lower().split())
        if len(key.split()) < 3:     # "yes", "stop", "thanks": not a routing case
            continue
        case = {"text": t["text"], "picked": t["tools"][0] if t["tools"] else "none", "then": t["tools"][1:],
                "tool_failed": bool(t["failed"]), "answered": t["answered"], "times": 1}
        case["why"] = "no answer" if not t["answered"] else "a tool failed" if t["failed"] else "worked"
        if key in seen:
            seen[key]["times"] += 1
            if case["why"] != "worked":   # keep the worst outcome for something he said more than once
                seen[key].update({k: case[k] for k in ("picked", "then", "tool_failed", "answered", "why")})
        else:
            seen[key] = case
    order = {"no answer": 0, "a tool failed": 1, "worked": 2}
    return sorted(seen.values(), key=lambda c: (order[c["why"]], -c["times"]))[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", nargs="?", default=str(Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis") / "logs" / "review"))
    parser.add_argument("--out", help="write the candidates here as JSON (default: <folder>/golden-candidates.json)")
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    rows: list[dict] = []
    for f in sorted(folder.glob("*/events.jsonl")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    found = candidates(rows)
    if not found:
        print(f"No turns recorded in {folder} yet.")
        return 1
    out = Path(args.out) if args.out else folder / "golden-candidates.json"
    out.write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = sum(1 for c in found if c["why"] != "worked")
    print(f"{len(found)} candidate cases from {len(turns(rows))} turns ({bad} went wrong) -> {out}")
    for c in found[:12]:
        print(f"  [{c['why']:<13}] {c['text'][:70]!r} -> {c['picked']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
