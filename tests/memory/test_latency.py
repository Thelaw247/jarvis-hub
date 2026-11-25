"""Hot-path read (MEMORY §7.3, C10): speculative recall ≤ 50 ms p95 at 10k facts, with the fake embedder
sized like the real models (256d fast, 384d index). Sandbox numbers, not Laptop B."""
import random
import statistics
import time

import pytest

from jarvis.memory import ClaimIn, EpisodeIn, MemoryStore

WORDS = ("lecture lab quiz midterm tutorial trusses stoichiometry vectors matrix essay memo report pps "
         "laundry residence meal gym rover sensor plotter pen scanner valyrian flashcards slides deadline").split()
COURSES = ["GE 122", "CHEM 142", "GEOL 121", "MATH 123", "CMPT 141"]


def p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[18]


@pytest.fixture(scope="module")
def big(tmp_path_factory):
    import asyncio

    loop = asyncio.new_event_loop()
    s = MemoryStore(tmp_path_factory.mktemp("lat") / "jarvis.db", card_debounce=3600)
    loop.run_until_complete(s.start())
    rnd = random.Random(7)
    for c in COURSES:
        loop.run_until_complete(s.create_branch(c, "fall-2026", created_by="official"))
    for e in range(100):
        claims = []
        for i in range(100):
            n = e * 100 + i
            words = " ".join(rnd.choice(WORDS) for _ in range(6))
            claims.append(ClaimIn(f"Note {n}: {words}", branch=rnd.choice(COURSES + ["jarvis", "residence"])))
        loop.run_until_complete(s.add_episode(EpisodeIn(f"batch {e}", "chat"), claims))
    yield s, loop
    loop.run_until_complete(s.close())
    loop.close()


def test_hot_path_read_p95_under_50ms_at_10k_facts(big):
    store, loop = big
    assert store.search_sync("lab", k=1)          # warm
    rnd = random.Random(1)
    times, sub = [], []
    for _ in range(200):
        q = f"what about the {rnd.choice(WORDS)} {rnd.choice(WORDS)[:3]}"
        t = time.perf_counter()
        store.search_sync(q, k=5, space="fast", partial=True)
        times.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        store.search_sync(q, k=5, space="fast", partial=True, branch="ge-122")
        sub.append((time.perf_counter() - t) * 1000)
    hot = [0.0] * 50
    for i in range(50):
        t = time.perf_counter()
        loop.run_until_complete(store.hot_recall(f"anything on the {rnd.choice(WORDS)}"))
        hot[i] = (time.perf_counter() - t) * 1000
    print(f"\nsandbox 10k facts: p95 whole tree {p95(times):.1f} ms, subtree {p95(sub):.1f} ms, "
          f"hot_recall (async) {p95(hot):.1f} ms")
    assert p95(times) <= 50 and p95(sub) <= 50 and p95(hot) <= 50
