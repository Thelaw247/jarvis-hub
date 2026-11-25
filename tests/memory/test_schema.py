"""jarvis.db: versioned migrations, WAL, secure_delete, FTS5 secure-delete, sqlite-vec, the seeded tree."""
import sqlite3

import pytest

from jarvis.memory import FakeEmbedder, MemoryStore
from jarvis.memory.db import MemoryConfigError, connect, open_writer
from jarvis.memory.migrations import MIGRATIONS, migrate

from .helpers import row, rows


def test_migrations_apply_once_and_record_the_version(tmp_path):
    conn = open_writer(tmp_path / "j.db", {"index": FakeEmbedder(16)})
    assert conn.execute("PRAGMA user_version").fetchone()[0] == MIGRATIONS[-1][0]
    assert migrate(conn) == []          # nothing new to apply
    conn.close()


def test_pragmas_and_extensions(store):
    conn = store._wconn
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA secure_delete").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("SELECT vec_version()").fetchone()[0].startswith("v")
    for fts in ("facts_fts", "episodes_fts"):
        assert conn.execute(f"SELECT v FROM {fts}_config WHERE k='secure-delete'").fetchone()[0] == 1
    # every reader also overwrites deleted bytes and cannot write
    rconn = store._pool.get()
    try:
        assert rconn.execute("PRAGMA secure_delete").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            rconn.execute("INSERT INTO meta(key, value) VALUES ('x', 'y')")
    finally:
        store._pool.put(rconn)


def test_all_design_tables_exist(store):
    names = {r[0] for r in rows(store, "SELECT name FROM sqlite_master WHERE type IN ('table')")}
    wanted = {"episodes", "entities", "facts", "fact_sources", "patterns", "procedures", "open_loops", "routine_stats",
              "corrections", "suggestions", "changes", "audit", "tombstones", "now_card", "branches", "branch_links",
              "branch_cards", "vec_facts_fast", "vec_facts_index", "vec_entities_index", "facts_fts", "episodes_fts"}
    assert wanted <= names


def test_seeded_life_tree(store):
    assert row(store, "SELECT path FROM branches WHERE id='fall-2026'")[0] == "school/fall-2026/"
    assert row(store, "SELECT kind FROM branches WHERE id='unsorted'")[0] == "system"
    assert row(store, "SELECT privacy_tier FROM branches WHERE id='money'")[0] == 2


def test_changing_the_embedding_model_needs_a_reindex(tmp_path, run):
    open_writer(tmp_path / "j.db", {"index": FakeEmbedder(16, "a")}).close()
    with pytest.raises(MemoryConfigError):
        open_writer(tmp_path / "j.db", {"index": FakeEmbedder(32, "b")})


def test_store_survives_reopen(tmp_path, run, clock):
    from jarvis.memory import ClaimIn

    from .helpers import said

    emb = {"index": FakeEmbedder(16, "x")}
    s = MemoryStore(tmp_path / "j.db", emb, clock=clock, card_debounce=0)
    run(s.start())
    run(s.add_episode(*said("I live in Maple Hall", ClaimIn("Lives in Maple Hall"))))
    run(s.close())
    s2 = MemoryStore(tmp_path / "j.db", emb, clock=clock, card_debounce=0)
    run(s2.start())
    assert [h.text for h in run(s2.search("Maple"))] == ["Lives in Maple Hall"]
    run(s2.close())


def test_connect_refuses_old_sqlite(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 0))
    with pytest.raises(MemoryConfigError):
        connect(tmp_path / "x.db")
