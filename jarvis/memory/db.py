"""Opening jarvis.db: pragmas, sqlite-vec, migrations and vector spaces (MEMORY §3)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .embeddings import Embedder
from .migrations import migrate

MIN_SQLITE = (3, 43, 0)  # FTS5 contentless_delete (3.43) and secure-delete (3.42)


class MemoryConfigError(RuntimeError):
    """The database can't be opened safely with this SQLite build or these embedding models."""


def _load_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise MemoryConfigError("sqlite-vec is not installed (pip install sqlite-vec)") from exc
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    """Open one connection with Jarvis's pragmas. Every connection sets secure_delete (it isn't persistent)."""
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        raise MemoryConfigError(f"SQLite {sqlite3.sqlite_version} is too old; need {'.'.join(map(str, MIN_SQLITE))}+")
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    _load_vec(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA secure_delete=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")   # sorts and temp tables never touch disk
    conn.execute("PRAGMA busy_timeout=5000")
    if readonly:
        conn.execute("PRAGMA query_only=ON")
    return conn


def open_writer(path: str | Path, embedders: dict[str, Embedder]) -> sqlite3.Connection:
    """Open the single writer connection, migrate, and make sure each vector space exists."""
    conn = connect(path)
    migrate(conn)
    ensure_vec_spaces(conn, embedders)
    return conn


def vec_table(space: str, item: str) -> str:
    if not space.isidentifier() or not item.isidentifier():
        raise ValueError("bad vector space name")
    return f"vec_{item}_{space}"


def ensure_vec_spaces(conn: sqlite3.Connection, embedders: dict[str, Embedder]) -> None:
    """One vec0 table per (embedding space, item type). A model or size change needs a re-index."""
    conn.execute("CREATE TABLE IF NOT EXISTS vec_spaces(space TEXT PRIMARY KEY, model TEXT NOT NULL, dim INTEGER NOT NULL)")
    for space, emb in embedders.items():
        row = conn.execute("SELECT model, dim FROM vec_spaces WHERE space=?", (space,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO vec_spaces(space, model, dim) VALUES (?,?,?)", (space, emb.name, emb.dim))
        elif (row["model"], row["dim"]) != (emb.name, emb.dim):
            raise MemoryConfigError(
                f"space {space!r} was built with {row['model']} ({row['dim']}d); re-index before using {emb.name}"
            )
        for item in ("facts", "entities"):
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table(space, item)} "
                f"USING vec0(embedding float[{emb.dim}] distance_metric=cosine)"
            )
