"""The Life Tree: placement rules, subtree-filtered search, tier-2 privacy, cards in the hub's contract shapes."""
from datetime import UTC, datetime, timedelta

from jarvis.memory import ClaimIn, NowContext

from .helpers import contract_errors, row, said


def courses(store, run):
    run(store.create_branch("GE 122", "fall-2026", aliases=("engineering math",), created_by="official"))
    run(store.create_branch("CHEM 142", "fall-2026", created_by="official"))
    run(store.create_branch("Assessments", "ge-122"))


def test_course_codes_place_by_rule(store, run):
    courses(store, run)
    r = run(store.add_episode(*said("GE122 midterm is in the gym", ClaimIn("GE 122 midterm 2 is in the PAC gym"),
                                    ClaimIn("CHEM 142 lab report due Friday"),
                                    ClaimIn("Bought a new desk lamp"))))
    assert [o.branch for o in r.outcomes] == ["ge-122", "chem-142", "unsorted"]
    assert row(store, "SELECT assigned_by FROM branch_links WHERE item_id=? AND item_type='fact'",
               r.outcomes[0].fact_id)[0] == "rule"


def test_subtree_filtered_search(store, run):
    courses(store, run)
    run(store.add_episode(*said("x", ClaimIn("GE 122 midterm covers trusses"),
                                ClaimIn("Midterm for GE 122 assessments is worth 20%", branch="assessments"),
                                ClaimIn("CHEM 142 midterm covers stoichiometry"),
                                ClaimIn("Pen Reader midterm demo for the club", branch="pen-reader"))))
    ge = {h.text for h in run(store.search("midterm", branch="GE 122"))}
    assert ge == {"GE 122 midterm covers trusses", "Midterm for GE 122 assessments is worth 20%"}
    school = {h.branch for h in run(store.search("midterm", branch="school"))}
    assert school == {"ge-122", "assessments", "chem-142"}
    everywhere = {h.branch for h in run(store.search("midterm"))}
    assert "pen-reader" in everywhere
    # nothing on the branch: widen to the whole tree (one pass), unless told not to
    assert run(store.search("midterm", branch="high-valyrian"))
    assert run(store.search("midterm", branch="high-valyrian", widen=False)) == []


def test_tier2_branches_never_leak(store, run):
    run(store.add_episode(*said("x", ClaimIn("Student loan payment is 300 a month", branch="money"),
                                ClaimIn("Loan of a textbook from Riley"))))
    assert [h.text for h in run(store.search("loan"))] == ["Loan of a textbook from Riley"]
    assert "Student loan payment is 300 a month" in [h.text for h in run(store.search("loan", branch="money"))]


def test_his_move_is_never_undone_by_inference(store, run):
    courses(store, run)
    r = run(store.add_episode(*said("x", ClaimIn("GE 122 study group on Sunday"))))
    fid = r.outcomes[0].fact_id
    run(store.file_under("fact", fid, "Pen Reader"))
    placed = run(store.place("fact", fid))
    assert (placed.branch, placed.assigned_by, placed.changed) == ("pen-reader", "him", False)


def test_unsorted_keeps_the_extractors_guess(store, run):
    r = run(store.add_episode(*said("x", ClaimIn("Bought new flash cards", suggested_branch="study-system"))))
    assert r.outcomes[0].branch == "unsorted"
    f = run(store.fact(r.outcomes[0].fact_id))
    assert f["branch_id"] == "unsorted" and f["guess_branch_id"] == "study-system"


def test_cards_match_the_hub_contracts(store, run, clock):
    courses(store, run)
    run(store.add_episode(*said("x", ClaimIn("GE 122 lectures are in ENGR 1A10", importance=0.9),
                                ClaimIn("Do PPS before the tutorial", branch="ge-122", kind="decision",
                                        claim_type="intent"))))
    run(store.add_open_loop("Finish PPS 7", due=clock() + timedelta(days=2), slot="Tonight 7 pm", branch="ge-122"))
    card = run(store.branch_card("ge-122"))
    assert contract_errors("branch_card", card) == []
    assert card["due"][0]["title"] == "Finish PPS 7" and card["key_facts"] and card["decisions"]
    parent = run(store.branch_card("school"))
    assert contract_errors("branch_card", parent) == [] and "1 due this week" in parent["rollup"]

    ctx = NowContext(events=[{"title": "GE 122 lecture", "when": "Tue 10:00 am", "where": "ENGR 1A10"}],
                     active_branch="ge-122", gaps=["Nothing on Thursday afternoon"])
    now = run(store.rebuild_now_card(ctx))
    assert contract_errors("now_card", now) == []
    text = run(store.now_card_text())
    assert "Finish PPS 7" in text and "Context: ge-122" in text


def test_hot_recall_attaches_a_branch_card_when_a_branch_is_named(store, run):
    courses(store, run)
    run(store.add_episode(*said("x", ClaimIn("GE 122 quiz is Thursday"))))
    out = run(store.hot_recall("what's going on with GE 122"))
    assert out["branch_card"]["branch_id"] == "ge-122"
    out = run(store.hot_recall("when is the qui"))
    assert out["facts"] and out["facts"][0].text == "GE 122 quiz is Thursday"


def test_valid_at_filters_world_time(store, run):
    run(store.add_episode(*said("x", ClaimIn("Fall reading week", valid_from=datetime(2026, 11, 9, tzinfo=UTC),
                                             valid_to=datetime(2026, 11, 14, tzinfo=UTC)))))
    assert run(store.search("reading week", at=datetime(2026, 11, 10, tzinfo=UTC)))
    assert run(store.search("reading week", at=datetime(2026, 11, 20, tzinfo=UTC))) == []
