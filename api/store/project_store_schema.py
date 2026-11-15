"""The project store's tables, closed value sets and size caps.

The closed sets come from api/contracts.py, so the store and the contract cannot drift apart. One
SQLite file holds every project; each write bumps its project's `version`, which a browser tab polls
(as an ETag) to see the other tab's work.
"""

import hashlib
import re
import sqlite3
from typing import get_args

from api.contracts import ActionItem, ConstructionType, Discipline, Hazard, JobType, ProjectPin, Role, Stage, WorkType

ROLES = get_args(Role)
STAGES = get_args(Stage)
JOB_TYPES = get_args(JobType)
CONSTRUCTION_TYPES = get_args(ConstructionType)
WORK_TYPES = get_args(WorkType)
DISCIPLINES = get_args(Discipline)
HAZARDS = get_args(Hazard)
ITEM_STATUSES = get_args(ActionItem.model_fields["status"].annotation)
PIN_KINDS = get_args(ProjectPin.model_fields["kind"].annotation)

# A request over a cap is refused, never cut, so one project cannot grow without bound.
MAX_TEXT = {"name": 120, "member_name": 80, "title": 200, "ref": 200, "note": 4000, "item_text": 2000, "pin_body": 8000,
            "reason": 600}
MAX_MODEL_BYTES = 200_000
MAX_ROWS_PER_PROJECT = {"members": 20, "items": 500, "notes": 2000, "pins": 500}


def _one_of(column: str, values: tuple[str, ...], nullable: bool = False) -> str:
    allowed = f"{column} IN ({', '.join(repr(v) for v in values)})"
    return f"CHECK ({column} IS NULL OR {allowed})" if nullable else f"CHECK ({allowed})"


DDL = f"""
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  site_bbl TEXT NOT NULL,
  stage TEXT NOT NULL {_one_of("stage", STAGES)},
  structural_model_json TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  project_id TEXT NOT NULL REFERENCES projects(id),
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL {_one_of("role", ROLES)},
  PRIMARY KEY (project_id, position)
);
CREATE TABLE IF NOT EXISTS items (
  project_id TEXT NOT NULL REFERENCES projects(id),
  id TEXT NOT NULL,
  position INTEGER NOT NULL,
  discipline TEXT NOT NULL {_one_of("discipline", DISCIPLINES)},
  hazard TEXT NOT NULL {_one_of("hazard", HAZARDS)},
  title TEXT NOT NULL,
  why TEXT NOT NULL,
  code_ref TEXT,
  proof_needed TEXT,
  status TEXT NOT NULL {_one_of("status", ITEM_STATUSES)},
  owner_role TEXT {_one_of("owner_role", ROLES, nullable=True)},
  source_rule TEXT NOT NULL,
  life_safety INTEGER NOT NULL CHECK (life_safety IN (0, 1)),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, id)
);
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  author_role TEXT NOT NULL {_one_of("author_role", ROLES)},
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pins (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL {_one_of("kind", PIN_KINDS)},
  ref_id TEXT NOT NULL,
  title TEXT NOT NULL,
  by_role TEXT NOT NULL {_one_of("by_role", ROLES)},
  created_at TEXT NOT NULL,
  body TEXT
);
CREATE INDEX IF NOT EXISTS notes_by_project ON notes(project_id);
CREATE INDEX IF NOT EXISTS pins_by_project ON pins(project_id);
"""

# Columns added after the first release, as (table, column, type): a store file made before one gets it on open.
ADDED_COLUMNS = (("pins", "body", "TEXT"), ("projects", "job_type", "TEXT"), ("projects", "construction_type", "TEXT"),
                 ("projects", "work_types_json", "TEXT"), ("items", "added_by_role", "TEXT"),
                 ("items", "added_reason", "TEXT"), ("items", "added_at", "TEXT"),
                 ("projects", "excavation_depth_ft", "REAL"), ("projects", "proposed_storeys", "REAL"),
                 ("items", "phase", "TEXT"), ("items", "due_when", "TEXT"), ("items", "done_by_role", "TEXT"),
                 ("items", "done_at", "TEXT"),
                 ("items", "applies_to_json", "TEXT"), ("items", "evidence", "TEXT"))

# Each table's columns by name, for rebuilding it, and the indexes, which a dropped table takes with it.
TABLES = dict(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) (\(.*?\n\));", DDL, re.S))
INDEXES = tuple(re.findall(r"CREATE INDEX IF NOT EXISTS [^;]+;", DDL))
if len(TABLES) != DDL.count("CREATE TABLE") or len(INDEXES) != DDL.count("CREATE INDEX"):
    raise RuntimeError("the DDL no longer matches the shape TABLES and INDEXES read; update them together")
# Changes with any table or value list. A file stamped with another value (PRAGMA user_version) is rebuilt on open.
SCHEMA_STAMP = int(hashlib.sha256(repr((DDL, ADDED_COLUMNS)).encode()).hexdigest()[:7], 16)


def rebuild_tables(db: sqlite3.Connection) -> None:
    """Copy every table into one made from today's DDL, all in one transaction, then stamp the file.

    A CHECK constraint is fixed when its table is made, so a file made before a value list grew refuses the
    new values (the developer and contractor roles, document pins). This is SQLite's recipe for changing
    one: make the new table, copy, drop the old, rename. A row today's lists refuse stops the rebuild and
    leaves the file as it was.
    """
    db.isolation_level = None  # the BEGIN and COMMIT below are ours
    db.execute("PRAGMA foreign_keys = OFF")  # a table is dropped while the others still point at it
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_STAMP:  # another process may have done it
            for table, columns_ddl in TABLES.items():  # names from our own DDL, never from input
                db.execute(f"CREATE TABLE _rebuild_{table} {columns_ddl}")
                made = {row[1] for row in db.execute(f"PRAGMA table_info(_rebuild_{table})")}
                for added_to, column, kind in ADDED_COLUMNS:
                    if added_to == table and column not in made:  # some later columns are in the DDL itself
                        db.execute(f"ALTER TABLE _rebuild_{table} ADD COLUMN {column} {kind}")
                columns = ", ".join(row[1] for row in db.execute(f"PRAGMA table_info({table})"))
                db.execute(f"INSERT INTO _rebuild_{table} ({columns}) SELECT {columns} FROM {table}")
                db.execute(f"DROP TABLE {table}")
                db.execute(f"ALTER TABLE _rebuild_{table} RENAME TO {table}")
            for index in INDEXES:
                db.execute(index)
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise sqlite3.IntegrityError("a row in the project store points to a project that is not there")
            db.execute(f"PRAGMA user_version = {SCHEMA_STAMP}")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:  # SQLite rolls some failures back itself
            db.execute("ROLLBACK")
        raise
