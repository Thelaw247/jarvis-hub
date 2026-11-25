"""Bi-temporal facts: world time (valid_from/valid_to) and system time (recorded_at/retired_at), history kept."""
from datetime import UTC, datetime

from jarvis.memory import ClaimIn, ClaimType, Kind

from .helpers import contract_errors, from_, row, said

AUG31 = datetime(2026, 8, 31, tzinfo=UTC)
OCT1 = datetime(2026, 10, 1, tzinfo=UTC)


def lives(where: str, since: datetime) -> ClaimIn:
    return ClaimIn(f"Lives in {where}", subject="De Wet", subject_type="person", predicate="lives_in",
                   object=where, object_type="place", valid_from=since, branch="residence")


def test_supersede_keeps_history_in_both_times(store, run, clock):
    r1 = run(store.add_episode(*said("I moved into Birch House", lives("Birch House", AUG31))))
    recorded_first = clock()
    clock.advance(days=30)
    r2 = run(store.add_episode(*said("I live in Maple Hall now", lives("Maple Hall", OCT1))))
    old, new = r1.outcomes[0].fact_id, r2.outcomes[0].fact_id
    assert r2.outcomes[0].action == "supersede" and r2.outcomes[0].other_fact_id == old

    o = row(store, "SELECT * FROM facts WHERE id=?", old)
    assert o["status"] == "superseded" and o["superseded_by"] == new
    assert o["valid_to"].startswith("2026-10-01")          # world: true until he moved
    assert o["retired_at"] is not None                     # system: when Jarvis stopped believing it
    assert o["authority"] == 2                             # his earlier word
    assert row(store, "SELECT authority FROM facts WHERE id=?", new)[0] == 1

    assert [h.text for h in run(store.search("where do I live"))][:1] == ["Lives in Maple Hall"]
    # world time: where did he live in mid-September?
    assert run(store.search("lives", at=datetime(2026, 9, 15, tzinfo=UTC)))[0].text == "Lives in Birch House"
    # system time: what did Jarvis believe right after the first episode?
    assert run(store.search("lives", as_of=recorded_first))[0].text == "Lives in Birch House"

    fact = run(store.fact(new))
    assert contract_errors("fact", fact) == []
    assert [h["was"] for h in fact["history"]] == ["Lives in Birch House"]
    assert fact["history"][0]["when"].startswith("until ")


def test_invalidate_ends_a_fact_and_retract_says_it_was_never_true(store, run):
    r = run(store.add_episode(*said("I'm in the robotics club", ClaimIn("Member of the robotics club"))))
    fid = r.outcomes[0].fact_id
    run(store.invalidate(fid, valid_to=OCT1))
    f = row(store, "SELECT status, valid_to, retired_at FROM facts WHERE id=?", fid)
    assert f["status"] == "superseded" and f["valid_to"].startswith("2026-10-01") and f["retired_at"]
    assert run(store.search("robotics club")) == []
    assert run(store.search("robotics club", at=datetime(2026, 9, 20, tzinfo=UTC)))[0].fact_id == fid

    r2 = run(store.add_episode(*said("I have a lab on Monday", ClaimIn("Has a lab on Monday"))))
    run(store.invalidate(r2.outcomes[0].fact_id, retract=True))
    assert row(store, "SELECT status FROM facts WHERE id=?", r2.outcomes[0].fact_id)[0] == "retracted"
    found = run(store.search("lab Monday", at=datetime(2026, 9, 2, tzinfo=UTC)))
    assert r2.outcomes[0].fact_id not in [h.fact_id for h in found]


def quiz(day: str, **kw) -> ClaimIn:
    return ClaimIn(f"GE 122 quiz 5 is on {day}", subject="GE 122 quiz 5", subject_type="assessment",
                   predicate="date", value=day, importance=0.8, **kw)


def test_his_relayed_world_fact_wins_and_canvas_is_flagged_once(store, run, clock):
    run(store.add_episode(*said("the prof said quiz 5 is Thursday now", quiz("Thursday"))))
    clock.advance(hours=1)
    r = run(store.add_episode(*from_("connector:canvas", "Quiz 5 due Friday", quiz("Friday"))))
    o = r.outcomes[0]
    assert o.action == "conflict"
    loser = row(store, "SELECT kind, conflicts_with, source_label FROM facts WHERE id=?", o.fact_id)
    assert loser["kind"] == "fact" or loser["kind"] == "observation"
    hits = run(store.search("quiz 5"))
    assert len(hits) == 1 and hits[0].text.endswith("Thursday") and hits[0].tag.startswith("[you")
    assert hits[0].conflict is not None and hits[0].conflict.tag == "[Canvas]"
    assert "Canvas" in hits[0].line()

    card = run(store.now_card())
    assert contract_errors("now_card", card) == []
    assert "Friday" in card["flag"]["text"] and "Thursday" in card["flag"]["text"]
    run(store.mark_flagged(o.fact_id))
    assert run(store.rebuild_now_card())["flag"] is None          # said once, not again (C15)

    winner = run(store.fact(hits[0].fact_id))
    assert contract_errors("fact", winner) == []
    assert winner["conflict"]["kept"] == "mine" and winner["conflict"]["other_source"]["kind"] == "canvas"


def test_same_voice_updates_itself(store, run, clock):
    r1 = run(store.add_episode(*from_("connector:canvas", "due Wed", quiz("Wednesday"))))
    clock.advance(days=1)
    r2 = run(store.add_episode(*from_("connector:canvas", "due Fri", quiz("Friday"))))
    assert r2.outcomes[0].action == "supersede" and r2.outcomes[0].other_fact_id == r1.outcomes[0].fact_id


def test_a_pinned_fact_never_loses_to_anything_but_him(store, run, clock):
    run(store.add_episode(*said("remember: quiz 5 is Thursday", quiz("Thursday", kind=Kind.CORRECTION,
                                                                      claim_type=ClaimType.WORLD))))
    r = run(store.add_episode(*from_("connector:canvas", "x", quiz("Friday"))))
    assert r.outcomes[0].action == "conflict"
    assert run(store.search("quiz 5"))[0].text.endswith("Thursday")


def test_reaffirm_and_noop(store, run):
    ep, claims = said("lectures are in ENGR 1A10", ClaimIn("GE 122 lectures are in ENGR 1A10"))
    r1 = run(store.add_episode(ep, claims))
    r2 = run(store.add_episode(*from_("connector:paws", "ENGR 1A10", ClaimIn("GE 122 lectures are in ENGR 1A10"))))
    assert r2.outcomes[0].action == "reaffirm" and r2.outcomes[0].fact_id == r1.outcomes[0].fact_id
    assert row(store, "SELECT confidence FROM facts WHERE id=?", r1.outcomes[0].fact_id)[0] > 0.8
