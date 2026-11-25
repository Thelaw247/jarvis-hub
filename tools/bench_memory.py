"""Benchmark memory recall: FTS5 + sqlite-vec at 10k and 50k facts, with and without subtree filters (M1.1 exit).

    python tools/bench_memory.py [--sizes 10000 50000] [--queries 200] [--real]

Uses fake embedders sized like the real models (256d fast, 384d index) unless --real (Laptop B: loads
REAL_MODELS with sentence-transformers). Builds throwaway databases in a temp folder. Prints p50/p95 in ms.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.memory import REAL_MODELS, ClaimIn, EpisodeIn, MemoryStore  # noqa: E402
from jarvis.memory.store import default_embedders  # noqa: E402

WORDS = ("lecture lab quiz midterm tutorial trusses stoichiometry vectors matrix essay memo report pps laundry "
         "residence meal gym rover sensor plotter pen scanner valyrian flashcards slides deadline professor "
         "room building canvas paws syllabus grade exam final project robot hub voice orb widget").split()
COURSES = ["GE 122", "CHEM 142", "GEOL 121", "MATH 123", "CMPT 141"]
OTHER = ["jarvis", "pen-reader", "residence", "high-valyrian", "laptop-b", "friends"]


def pct(xs: list[float], p: int) -> float:
    return statistics.quantiles(xs, n=100)[p - 1]


async def build(path: Path, n: int, embedders: dict) -> tuple[MemoryStore, float]:
    s = MemoryStore(path, embedders, card_debounce=3600)
    await s.start()
    for c in COURSES:
        await s.create_branch(c, "fall-2026", created_by="official")
    rnd = random.Random(42)
    t0 = time.perf_counter()
    for e in range(0, n, 100):
        claims = [ClaimIn(f"Note {i}: " + " ".join(rnd.choice(WORDS) for _ in range(8)),
                          branch=rnd.choice(COURSES + OTHER)) for i in range(e, min(n, e + 100))]
        await s.add_episode(EpisodeIn(f"batch {e}", "chat"), claims)
    return s, time.perf_counter() - t0


def measure(s: MemoryStore, queries: list[str], **kw) -> tuple[float, float]:
    times = []
    for q in queries:
        t = time.perf_counter()
        s.search_sync(q, **kw)
        times.append((time.perf_counter() - t) * 1000)
    return pct(times, 50), pct(times, 95)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000])
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--real", action="store_true", help="use REAL_MODELS (Laptop B only)")
    args = ap.parse_args()
    if args.real:  # pragma: no cover
        from jarvis.memory.embeddings import SentenceTransformerEmbedder
        embedders = {k: SentenceTransformerEmbedder(str(REAL_MODELS[k]["model"]), int(REAL_MODELS[k]["dim"]))
                     for k in ("fast", "index")}
    else:
        embedders = default_embedders()
    rnd = random.Random(1)
    queries = [f"what about the {rnd.choice(WORDS)} {rnd.choice(WORDS)} {rnd.choice(WORDS)[:3]}"
               for _ in range(args.queries)]
    print(f"embedders: {', '.join(f'{k}={e.name}' for k, e in embedders.items())}")
    print(f"{'facts':>7} {'case':<34} {'p50 ms':>8} {'p95 ms':>8}")
    with tempfile.TemporaryDirectory() as tmp:
        for n in args.sizes:
            s, secs = await build(Path(tmp) / f"bench{n}.db", n, embedders)
            print(f"{n:>7} {'build (writes incl. audit)':<34} {secs / n * 1000:>8.2f} {'per fact':>8}")
            cases = [
                ("hot path: fast, k=5, whole tree", dict(space="fast", k=5, partial=True)),
                ("hot path: fast, k=5, course leaf", dict(space="fast", k=5, partial=True, branch="ge-122")),
                ("deep: index, k=10, whole tree", dict(space="index", k=10)),
                ("deep: index, k=10, area (school)", dict(space="index", k=10, branch="school")),
                ("deep: index, k=10, course leaf", dict(space="index", k=10, branch="ge-122")),
            ]
            s.search_sync("warm up", k=1)
            for label, kw in cases:
                p50, p95 = measure(s, queries, **kw)
                print(f"{n:>7} {label:<34} {p50:>8.1f} {p95:>8.1f}")
            await s.close()


if __name__ == "__main__":
    asyncio.run(main())
