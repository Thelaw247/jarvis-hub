"""Forget for real: the bytes leave the main file, the WAL and the FTS index; a tombstone blocks re-learning."""
from jarvis.memory import ClaimIn, EpisodeIn, UndoError

from .helpers import from_, row, rows, said

SECRET = "zyxwquokka frobnitzalpha"   # distinctive words, easy to find as raw bytes


def raw(store) -> bytes:
    data = store.path.read_bytes()
    wal = store.path.with_name(store.path.name + "-wal")
    return data + (wal.read_bytes() if wal.exists() else b"")


def vectors(store, fid: int) -> list[bytes]:
    return [row(store, f"SELECT embedding FROM vec_facts_{s} WHERE rowid=?", fid)[0] for s in ("fast", "index")]


def vocab(store) -> set[str]:
    conn = store._wconn
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.v_facts USING fts5vocab(main, facts_fts, row)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.v_eps USING fts5vocab(main, episodes_fts, row)")
    return {r[0] for r in conn.execute("SELECT term FROM temp.v_facts UNION SELECT term FROM temp.v_eps")}


def seed(store, run, n: int = 150) -> None:
    for i in range(0, n, 50):
        run(store.add_episode(*said(f"batch {i}", *[ClaimIn(f"Filler fact {j} about lectures and labs")
                                                    for j in range(i, i + 50)])))


def test_forget_removes_the_bytes_everywhere(store, run):
    seed(store, run)
    r = run(store.add_episode(*said(f"my locker code word is {SECRET}",
                                    ClaimIn(f"Locker code word is {SECRET}", subject="locker", predicate="code_word",
                                            branch="residence"))))
    seed(store, run, 100)
    fid = r.outcomes[0].fact_id
    vecs = vectors(store, fid)
    store._wconn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = raw(store)
    # the check can fail: the words and vectors really are on disk and in the index first
    assert all(w.encode() in before for w in SECRET.split())
    assert all(v in before for v in vecs)
    assert {"zyxwquokka", "frobnitzalpha"} <= vocab(store)

    preview = run(store.forget(fact_ids=[fid], preview=True))
    assert preview.facts == [fid] and preview.episodes == [r.episode_id] and preview.change_id is None

    res = run(store.forget(fact_ids=[fid]))
    assert res.scrubbed and res.facts == [fid] and res.episodes == [r.episode_id] and res.tombstones >= 2

    after = raw(store)
    for w in SECRET.split():
        assert w.encode() not in after, f"{w} still in the database file or WAL"
    assert all(v not in after for v in vecs), "an embedding of the forgotten fact is still on disk"
    assert not ({"zyxwquokka", "frobnitzalpha"} & vocab(store))
    wal = store.path.with_name(store.path.name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0 or SECRET.split()[0].encode() not in wal.read_bytes()

    # nothing in the audit trail, the cards or the Memory view carries it
    assert all(SECRET.split()[0] not in (a[0] or "") + (a[1] or "") for a in rows(store, "SELECT before, after FROM audit"))
    assert "zyxwquokka" not in (row(store, "SELECT card_text FROM branch_cards WHERE branch_id='residence'")[0] or "")
    assert row(store, "SELECT summary FROM changes WHERE id=?", res.change_id)[0] == "2 items forgotten"
    assert all("zyxwquokka" not in h.text for h in run(store.search("zyxwquokka")))
    # the filler is untouched (the second seed reaffirmed the first 100)
    assert row(store, "SELECT count(*) FROM facts")[0] == 150


def test_tombstone_blocks_relearning_until_he_says_it_again(store, run):
    claim = ClaimIn(f"Locker code word is {SECRET}", subject="locker", predicate="code_word")
    r = run(store.add_episode(*said(f"code word {SECRET}", claim)))
    run(store.forget(fact_ids=[r.outcomes[0].fact_id]))

    again = run(store.add_episode(*said(f"code word {SECRET}", claim)))          # same text
    assert again.blocked and again.episode_id is None
    para = run(store.add_episode(*from_("gmail", "fyi new locker word",           # a paraphrase, same claim key
                                        ClaimIn("The locker's code word changed to bananas", subject="locker",
                                                predicate="code_word"))))
    assert para.outcomes[0].action == "blocked"
    assert row(store, "SELECT count(*) FROM facts")[0] == 0

    lifted = run(store.add_episode(EpisodeIn(f"code word {SECRET}", "chat", "user", explicit=True), [claim]))
    assert lifted.outcomes[0].action == "add"
    assert row(store, "SELECT count(*) FROM tombstones WHERE lifted_at IS NULL AND kind='content'")[0] < 2


def test_forget_a_topic_takes_its_facts_and_mentions(store, run):
    run(store.add_episode(*said("Zorblax club meets Tuesdays",
                                ClaimIn("Zorblax club meets Tuesdays", subject="Zorblax club", predicate="meets_on",
                                        value="Tuesday"))))
    run(store.add_episode(*said("I might skip Zorblax club this week")))
    keep = run(store.add_episode(*said("GE 122 lab is Wednesday", ClaimIn("GE 122 lab is Wednesday"))))
    eid = row(store, "SELECT id FROM entities WHERE canonical_name='Zorblax club'")[0]
    res = run(store.forget(entity_ids=[eid]))
    assert len(res.episodes) == 2 and res.entities == [eid]
    assert b"zorblax" not in raw(store).lower()
    assert row(store, "SELECT count(*) FROM facts")[0] == 1 and keep.episode_id


def test_forget_cannot_be_undone(store, run):
    r = run(store.add_episode(*said("x", ClaimIn("Something private"))))
    res = run(store.forget(fact_ids=[r.outcomes[0].fact_id]))
    for cid in (res.change_id, r.change_id):
        try:
            run(store.undo(cid))
        except UndoError:
            continue
        raise AssertionError("undo of a forget must be refused")
