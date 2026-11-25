"""Versioned schema migrations for jarvis.db (MEMORY §3 + LIFE_TREE §4).

Each migration runs once, in its own transaction, and bumps `PRAGMA user_version`. Never edit a shipped
migration: add a new one. Vector tables are not here because their size depends on the configured
embedding models; `db.ensure_vec_spaces` makes them.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

_KINDS = "'fact','preference','decision','commitment','procedure','policy','pattern','observation','correction'"
_HIS_ONLY = "'decision','preference','commitment','procedure','correction'"
_FTS_TOKENIZER = "tokenize='porter unicode61 remove_diacritics 2'"

M1_CORE = f"""
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Raw ground truth: one user-assistant round per row (MEMORY §3)
CREATE TABLE episodes(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  channel TEXT NOT NULL,
  speaker TEXT NOT NULL CHECK (speaker IN ('user','jarvis','system')),
  trust TEXT NOT NULL CHECK (trust IN ('his','jarvis','outside')),
  content TEXT NOT NULL,
  session_id TEXT,
  privacy_tier INTEGER NOT NULL DEFAULT 1 CHECK (privacy_tier IN (0,1,2)),
  hash TEXT NOT NULL,
  retention TEXT NOT NULL DEFAULT 'keep'
);
CREATE INDEX episodes_session ON episodes(session_id);
CREATE INDEX episodes_hash ON episodes(hash);

-- The things in his world
CREATE TABLE entities(
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]',
  summary TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  importance REAL NOT NULL DEFAULT 0.5,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  domain TEXT,
  privacy_tier INTEGER NOT NULL DEFAULT 1 CHECK (privacy_tier IN (0,1,2))
);
CREATE TABLE entity_names(
  id INTEGER PRIMARY KEY,
  entity_id INTEGER NOT NULL REFERENCES entities(id),
  name_norm TEXT NOT NULL,
  UNIQUE(name_norm, entity_id)
);
CREATE INDEX entity_names_norm ON entity_names(name_norm);

-- One claim per row: the core of the system (bi-temporal, provenance set, authority from trust)
CREATE TABLE facts(
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL,
  subject_id INTEGER REFERENCES entities(id),
  predicate TEXT,
  object_id INTEGER REFERENCES entities(id),
  object_value TEXT,
  kind TEXT NOT NULL CHECK (kind IN ({_KINDS})),
  claim_type TEXT NOT NULL CHECK (claim_type IN ('intent','world')),
  authority INTEGER NOT NULL CHECK (authority BETWEEN 1 AND 5),
  origin_trust TEXT NOT NULL CHECK (origin_trust IN ('his','jarvis','outside')),
  source_key TEXT NOT NULL,
  source_label TEXT NOT NULL,
  confirm_state TEXT NOT NULL CHECK (confirm_state IN ('stated','confirmed','observed','proposed')),
  confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  valid_from TEXT,
  valid_to TEXT,
  recorded_at TEXT NOT NULL,
  retired_at TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','retracted','archived')),
  superseded_by INTEGER REFERENCES facts(id),
  conflicts_with INTEGER REFERENCES facts(id),
  flagged_at TEXT,
  pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)),
  scope TEXT,
  domain_tags TEXT NOT NULL DEFAULT '[]',
  privacy_tier INTEGER NOT NULL DEFAULT 1 CHECK (privacy_tier IN (0,1,2)),
  importance REAL NOT NULL DEFAULT 0.5,
  strength REAL NOT NULL DEFAULT 1.0,
  last_used TEXT,
  use_count INTEGER NOT NULL DEFAULT 0,
  corrective_context TEXT,
  fact_keys TEXT,
  text_hash TEXT NOT NULL,
  -- C41 in the database too: only his word can be authority 1-2, a his-only kind, pinned or stated/confirmed
  CHECK (origin_trust = 'his' OR (authority >= 3 AND pinned = 0 AND kind NOT IN ({_HIS_ONLY})
                                  AND confirm_state IN ('observed','proposed')))
);
CREATE INDEX facts_key ON facts(subject_id, predicate, status);
CREATE INDEX facts_status ON facts(status, valid_to);
CREATE INDEX facts_hash ON facts(text_hash);

-- Provenance is a set, never a single id (C16)
CREATE TABLE fact_sources(
  id INTEGER PRIMARY KEY,
  fact_id INTEGER NOT NULL REFERENCES facts(id),
  episode_id INTEGER NOT NULL REFERENCES episodes(id),
  UNIQUE(fact_id, episode_id)
);
CREATE INDEX fact_sources_episode ON fact_sources(episode_id);

-- Reflections and the user model: start as authority 5, proposed
CREATE TABLE patterns(
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL,
  authority INTEGER NOT NULL DEFAULT 5 CHECK (authority BETWEEN 1 AND 5),
  confirm_state TEXT NOT NULL DEFAULT 'proposed' CHECK (confirm_state IN ('stated','confirmed','observed','proposed')),
  confidence REAL NOT NULL DEFAULT 0.5,
  status TEXT NOT NULL DEFAULT 'active',
  pinned INTEGER NOT NULL DEFAULT 0,
  recorded_at TEXT NOT NULL,
  retired_at TEXT,
  privacy_tier INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE pattern_cites(
  id INTEGER PRIMARY KEY,
  pattern_id INTEGER NOT NULL REFERENCES patterns(id),
  fact_id INTEGER REFERENCES facts(id),
  episode_id INTEGER REFERENCES episodes(id)
);

-- How he wants things done. Only he can create one (a his-trust fact of kind procedure)
CREATE TABLE procedures(
  id INTEGER PRIMARY KEY,
  fact_id INTEGER NOT NULL UNIQUE REFERENCES facts(id),
  rule_text TEXT NOT NULL,
  scope TEXT,
  pinned INTEGER NOT NULL DEFAULT 1,
  skill_ref TEXT
);
CREATE TRIGGER procedures_his_only BEFORE INSERT ON procedures
WHEN (SELECT origin_trust FROM facts WHERE id = NEW.fact_id) IS NOT 'his'
BEGIN SELECT RAISE(ABORT, 'C41: only his word can create a procedure'); END;

CREATE TABLE open_loops(
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL,
  origin_episode INTEGER REFERENCES episodes(id),
  due TEXT,
  planned_slot TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  last_flagged_state TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE routine_stats(
  id INTEGER PRIMARY KEY,
  context TEXT NOT NULL,
  next_action TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  last_seen TEXT,
  UNIQUE(context, next_action)
);

CREATE TABLE corrections(
  id INTEGER PRIMARY KEY,
  wrong_fact_id INTEGER REFERENCES facts(id),
  new_fact_id INTEGER REFERENCES facts(id),
  ts TEXT NOT NULL,
  repeat_count INTEGER NOT NULL DEFAULT 0,
  test_case_id TEXT
);

CREATE TABLE suggestions(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  trigger TEXT NOT NULL,
  context TEXT,
  outcome TEXT CHECK (outcome IN ('accepted','rejected','ignored'))
);

-- Every change with its exact before/after (MEMORY §9). A change groups the row edits of one action.
CREATE TABLE changes(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  session_id TEXT,
  op TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  undo_of INTEGER REFERENCES changes(id),
  undone_by INTEGER REFERENCES changes(id),
  forgotten INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX changes_session ON changes(session_id);
CREATE TABLE audit(
  id INTEGER PRIMARY KEY,
  change_id INTEGER NOT NULL REFERENCES changes(id),
  seq INTEGER NOT NULL,
  tbl TEXT NOT NULL,
  row_id INTEGER NOT NULL,
  before TEXT,
  after TEXT,
  forgotten INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX audit_change ON audit(change_id, seq);
CREATE INDEX audit_row ON audit(tbl, row_id);
CREATE TABLE change_branches(
  change_id INTEGER NOT NULL REFERENCES changes(id),
  branch_id TEXT NOT NULL,
  PRIMARY KEY(change_id, branch_id)
) WITHOUT ROWID;
CREATE INDEX change_branches_branch ON change_branches(branch_id, change_id);

-- What has been forgotten: hashes and (subject, predicate) keys only, never text (MEMORY §9)
CREATE TABLE tombstones(
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('content','claim_key','entity')),
  hash TEXT NOT NULL,
  ts TEXT NOT NULL,
  lifted_at TEXT,
  UNIQUE(kind, hash)
);

-- The current briefing (MEMORY §7.1)
CREATE TABLE now_card(
  id INTEGER PRIMARY KEY CHECK (id = 1),
  card_json TEXT NOT NULL,
  card_text TEXT NOT NULL,
  built_at TEXT NOT NULL,
  inputs_hash TEXT NOT NULL
);

-- Search indexes. Contentless: the text lives only in facts/episodes. Rows leave the index through FTS5's
-- 'delete' command (with the indexed values) so secure-delete overwrites them in place; contentless_delete
-- is not used because its tombstones leave the old tokens in the segment until a merge.
CREATE VIRTUAL TABLE facts_fts USING fts5(text, fact_keys, corrective, content='', {_FTS_TOKENIZER});
CREATE VIRTUAL TABLE episodes_fts USING fts5(content, content='', {_FTS_TOKENIZER});
INSERT INTO facts_fts(facts_fts, rank) VALUES('secure-delete', 1);
INSERT INTO episodes_fts(episodes_fts, rank) VALUES('secure-delete', 1);
"""

M2_LIFE_TREE = """
-- The Life Tree (LIFE_TREE §4). id is a stable slug (the contract id); path is the materialised path.
CREATE TABLE branches(
  id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES branches(id),
  path TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]',
  level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 4),
  kind TEXT NOT NULL CHECK (kind IN ('root','area','branch','leaf','detail','system')),
  entity_id INTEGER REFERENCES entities(id),
  icon TEXT,
  glyph TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','proposed','archived')),
  privacy_tier INTEGER CHECK (privacy_tier IN (0,1,2)),
  created_by TEXT NOT NULL DEFAULT 'jarvis-proposed' CHECK (created_by IN ('his','official','jarvis-proposed','system')),
  confirm_state TEXT NOT NULL DEFAULT 'stated',
  sort_hint INTEGER,
  pinned INTEGER NOT NULL DEFAULT 0,
  centroid BLOB,
  activity_14d INTEGER NOT NULL DEFAULT 0,
  next_due_at TEXT,
  open_loop_count INTEGER NOT NULL DEFAULT 0,
  pending_yes_count INTEGER NOT NULL DEFAULT 0,
  valid_from TEXT,
  valid_to TEXT
);
CREATE INDEX branches_parent ON branches(parent_id);

CREATE TABLE branch_links(
  id INTEGER PRIMARY KEY,
  item_type TEXT NOT NULL CHECK (item_type IN ('fact','entity','episode','open_loop','file','event','action','pattern')),
  item_id INTEGER NOT NULL,
  branch_id TEXT NOT NULL REFERENCES branches(id),
  role TEXT NOT NULL DEFAULT 'primary' CHECK (role IN ('primary','also')),
  assigned_by TEXT NOT NULL CHECK (assigned_by IN ('rule','entity','embedding','llm','him','unsorted')),
  confidence REAL NOT NULL DEFAULT 1.0,
  guess TEXT,
  ts TEXT NOT NULL,
  UNIQUE(item_type, item_id, branch_id)
);
CREATE INDEX branch_links_branch ON branch_links(branch_id, item_type);
CREATE INDEX branch_links_item ON branch_links(item_type, item_id);

CREATE TABLE branch_cards(
  branch_id TEXT PRIMARY KEY REFERENCES branches(id),
  card_json TEXT NOT NULL,
  card_text TEXT NOT NULL,
  story TEXT,
  built_at TEXT NOT NULL,
  inputs_hash TEXT NOT NULL,
  dirty INTEGER NOT NULL DEFAULT 0
);
"""

# The seed tree (LIFE_TREE §3.2). Course leaves come later from PAWS; he renames, moves or deletes anything.
SEED = [
    # id, parent, name, kind, tier, glyph, aliases
    ("root", None, "De Wet", "root", 1, "DW", []),
    ("school", "root", "School", "area", None, "SC", ["usask", "university"]),
    ("fall-2026", "school", "Fall 2026", "branch", None, "F26", ["this term", "fall term"]),
    ("study-system", "school", "Study system", "branch", None, "ST", ["study plans"]),
    ("school-admin", "school", "Admin", "branch", None, "AD", ["registration"]),
    ("projects", "root", "Projects", "area", None, "PR", []),
    ("jarvis", "projects", "Jarvis", "branch", None, "JV", ["horatio"]),
    ("pen-reader", "projects", "Pen Reader", "branch", None, "PN", ["worldpenscan", "scannote"]),
    ("praelecta", "projects", "Praelecta", "branch", None, "PL", []),
    ("cedar-student-pilot", "projects", "Cedar Student Pilot", "branch", None, "CP", ["academiaos"]),
    ("ideas", "projects", "Ideas", "branch", None, "ID", []),
    ("people", "root", "People", "area", None, "PE", []),
    ("family", "people", "Family", "branch", None, "FA", []),
    ("friends", "people", "Friends", "branch", None, "FR", []),
    ("classmates", "people", "Classmates", "branch", None, "CL", []),
    ("profs-tas", "people", "Profs & TAs", "branch", None, "PT", ["profs", "tas"]),
    ("people-others", "people", "Others", "branch", None, "OT", []),
    ("life", "root", "Life", "area", None, "LI", []),
    ("residence", "life", "Residence", "branch", None, "RE", ["maple hall", "laundry"]),
    ("errands", "life", "Errands & admin", "branch", None, "ER", []),
    ("money", "life", "Money", "branch", 2, "MO", ["finances"]),
    ("health", "life", "Health & fitness", "branch", 2, "HE", ["fitness"]),
    ("plans-trips", "life", "Plans & trips", "branch", None, "TR", ["trips"]),
    ("learning", "root", "Learning", "area", None, "LE", []),
    ("high-valyrian", "learning", "High Valyrian", "branch", None, "HV", ["valyrian"]),
    ("tech", "root", "Tech & setup", "area", None, "TE", []),
    ("laptop-a", "tech", "Laptop A", "branch", None, "LA", []),
    ("laptop-b", "tech", "Laptop B (hub)", "branch", None, "LB", ["the hub"]),
    ("phone", "tech", "Phone", "branch", None, "PH", []),
    ("gaming", "tech", "Gaming", "branch", None, "GA", []),
    ("desk-setup", "tech", "Desk setup", "branch", None, "DS", []),
    ("unsorted", "root", "Unsorted", "system", None, "?", []),
]


def _seed_tree(conn: sqlite3.Connection) -> None:
    import json

    paths: dict[str, str] = {}
    levels: dict[str, int] = {}
    for bid, parent, name, kind, tier, glyph, aliases in SEED:
        if parent is None:
            path, level = "", 0
        else:
            path = f"{paths[parent]}{bid}/"
            level = levels[parent] + 1
        paths[bid], levels[bid] = path, level
        created_by = "system" if kind in ("root", "system") else "his"
        conn.execute(
            "INSERT INTO branches(id, parent_id, path, name, aliases, level, kind, glyph, privacy_tier, created_by)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (bid, parent, path, name, json.dumps(aliases), level, kind, glyph, tier, created_by),
        )


Migration = tuple[int, str, str | Callable[[sqlite3.Connection], None]]

MIGRATIONS: list[Migration] = [
    (1, "core memory tables, audit, tombstones, FTS5 with secure-delete", M1_CORE),
    (2, "Life Tree: branches, branch_links, branch_cards", M2_LIFE_TREE),
    (3, "seed the Life Tree areas", _seed_tree),
]


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply every migration newer than `PRAGMA user_version`. Returns the versions applied. Tier: T2."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    applied: list[int] = []
    for version, _name, step in MIGRATIONS:
        if version <= current:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            if callable(step):
                step(conn)
            else:
                for stmt in _split(step):
                    conn.execute(stmt)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied


def _split(script: str) -> list[str]:
    """Split a migration script into statements (triggers keep their inner semicolons)."""
    out, buf = [], ""
    for line in script.splitlines(keepends=True):
        if line.strip().startswith("--"):
            continue
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
