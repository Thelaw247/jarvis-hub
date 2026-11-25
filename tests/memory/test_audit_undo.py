"""Every change is audited with before/after; "undo that" reverses only that change (MEMORY §9)."""
import asyncio
import json
from datetime import UTC, datetime

import pytest

from jarvis.memory import ClaimIn, UndoError

from .helpers import row, rows, said


def lives(where: str, month: int) -> ClaimIn:
    return ClaimIn(f"Lives in {where}", subject="De Wet", predicate="lives_in", object=where,
                   valid_from=datetime(2026, month, 1, tzinfo=UTC))


def test_every_change_has_audit_rows_with_before_and_after(store, run):
    r1 = run(store.add_episode(*said("I live in Birch House", lives("Birch House", 9))))
    r2 = run(store.add_episode(*said("now Maple Hall", lives("Maple Hall", 10))))
    run(store.pin(r2.outcomes[0].fact_id))
    run(store.create_branch("GE 122", "fall-2026", aliases=("engineering math",)))
    for c in rows(store, "SELECT id, op FROM changes"):
        assert row(store, "SELECT count(*) FROM audit WHERE change_id=?", c["id"])[0] >= 1, c["op"]

    # the supersede: the old fact's update carries both states
    a = row(store, "SELECT before, after FROM audit WHERE change_id=? AND tbl='facts' AND row_id=?",
            r2.change_id, r1.outcomes[0].fact_id)
    before, after = json.loads(a["before"]), json.loads(a["after"])
    assert (before["status"], after["status"]) == ("active", "superseded")
    assert before["superseded_by"] is None and after["superseded_by"] == r2.outcomes[0].fact_id
    # inserts have no before; the episode's raw text is never copied into the audit trail
    ep = row(store, "SELECT before, after FROM audit WHERE change_id=? AND tbl='episodes'", r1.change_id)
    assert ep["before"] is None and "content" not in json.loads(ep["after"])
    assert "Birch" not in ep["after"]


def test_undo_reverses_exactly_one_change(store, run):
    r1 = run(store.add_episode(*said("I live in Birch House", lives("Birch House", 9))))
    r2 = run(store.add_episode(*said("now Maple Hall", lives("Maple Hall", 10))))
    r3 = run(store.add_episode(*said("my lab partner is Riley", ClaimIn("Lab partner is Riley"))))
    old, new, other = r1.outcomes[0].fact_id, r2.outcomes[0].fact_id, r3.outcomes[0].fact_id

    res = run(store.undo(r2.change_id))
    assert res.undone == [r2.change_id] and res.conflicts == []
    o = row(store, "SELECT status, superseded_by, valid_to, retired_at, authority FROM facts WHERE id=?", old)
    assert tuple(o) == ("active", None, None, None, 1)
    assert row(store, "SELECT 1 FROM facts WHERE id=?", new) is None
    assert row(store, "SELECT status FROM facts WHERE id=?", other)[0] == "active"   # later work untouched
    assert [h.text for h in run(store.search("lives"))][:1] == ["Lives in Birch House"]
    assert row(store, "SELECT undone_by FROM changes WHERE id=?", r2.change_id)[0] == res.change_id

    with pytest.raises(UndoError):
        run(store.undo(r2.change_id))                       # once only
    run(store.undo(res.change_id))                          # undo the undo
    assert [h.text for h in run(store.search("lives"))][:1] == ["Lives in Maple Hall"]


def test_undo_keeps_later_edits_to_the_same_row(store, run):
    r = run(store.add_episode(*said("robotics club", ClaimIn("Member of the robotics club"))))
    fid = r.outcomes[0].fact_id
    c1 = run(store.invalidate(fid, valid_to=datetime(2026, 10, 1, tzinfo=UTC)))
    run(store.pin(fid))                                                   # a later, unrelated field
    run(store.invalidate(fid, valid_to=datetime(2026, 10, 5, tzinfo=UTC)))  # a later edit of the same field
    res = run(store.undo(c1.change_id))
    f = row(store, "SELECT status, pinned, valid_to FROM facts WHERE id=?", fid)
    assert f["pinned"] == 1                                 # later change survives
    assert f["valid_to"].startswith("2026-10-05")           # later value of a shared field wins
    assert any("valid_to" in c for c in res.conflicts)


def test_undo_everything_from_one_conversation(store, run):
    run(store.add_episode(*said("keep this", ClaimIn("Likes Night HUD"), session="s-keep")))
    run(store.add_episode(*said("a", ClaimIn("Fact A from the bad chat"), session="s-bad")))
    run(store.add_episode(*said("b", ClaimIn("Fact B from the bad chat"), session="s-bad")))
    res = run(store.undo(session_id="s-bad"))
    assert len(res.undone) == 2
    texts = [r[0] for r in rows(store, "SELECT text FROM facts")]
    assert texts == ["Likes Night HUD"]


def test_undo_that_means_the_latest_change(store, run):
    run(store.add_episode(*said("x", ClaimIn("Fact one"))))
    run(store.add_episode(*said("y", ClaimIn("Fact two"))))
    run(store.undo())
    assert [r[0] for r in rows(store, "SELECT text FROM facts")] == ["Fact one"]


def test_branch_changes_are_undoable(store, run):
    c = run(store.create_branch("Robotics club", "life"))
    assert row(store, "SELECT 1 FROM branches WHERE id='robotics-club'")
    r = run(store.add_episode(*said("x", ClaimIn("Robotics club builds a rover"))))
    assert r.outcomes[0].branch == "robotics-club"            # placed by name (rules step)
    m = run(store.file_under("fact", r.outcomes[0].fact_id, "projects"))
    run(store.undo(m.change_id))
    assert row(store, "SELECT branch_id, assigned_by FROM branch_links WHERE item_type='fact' AND item_id=?",
               r.outcomes[0].fact_id)[0] == "robotics-club"
    res = run(store.undo(c.change_id))       # the branch still holds a fact: kept, reported
    assert res.conflicts


def test_one_writer_many_concurrent_callers(store, run):
    async def burst():
        writes = [store.add_episode(*said(f"note {i}", ClaimIn(f"Burst fact number {i}"))) for i in range(40)]
        reads = [store.search("burst fact") for _ in range(20)]
        return await asyncio.gather(*writes, *reads)

    out = run(burst())
    change_ids = [r.change_id for r in out[:40]]
    assert len(set(change_ids)) == 40
    assert row(store, "SELECT count(*) FROM facts")[0] == 40
