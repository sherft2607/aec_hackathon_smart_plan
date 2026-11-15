"""SQLite project store, shaped by the Project contract: members by role, action items, notes, pins, the model.

There are no accounts. A tab acts as a role, and a note or pin is refused unless the project has a member
in that role. Every method returns the whole project as a Project-shaped dict.
"""

import json
import re
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from api.store.project_store_schema import (
    ADDED_COLUMNS, CONSTRUCTION_TYPES, DDL, DISCIPLINES, HAZARDS, ITEM_STATUSES, JOB_TYPES, MAX_MODEL_BYTES, MAX_ROWS_PER_PROJECT,
    MAX_TEXT, PIN_KINDS, ROLES, SCHEMA_STAMP, STAGES, WORK_TYPES, rebuild_tables,
)

_BBL = re.compile(r"[1-5][0-9]{9}", re.ASCII)  # fullmatch: no trailing newline gets through
_PROJECT_ID = re.compile(r"[0-9a-f]{16}", re.ASCII)
UNCHANGED = object()  # update_items: leave the field as it is
_ITEM_FIELDS = ("id", "discipline", "hazard", "title", "why", "code_ref", "proof_needed", "status", "owner_role",
                "source_rule", "life_safety", "phase", "due_when", "applies_to_json", "evidence")
_PROVENANCE = ("added_by_role", "added_reason", "added_at")
# When the item is due (the column is due_when: WHEN is an SQL keyword) and who marked it done, and when.
_TIMING = ("phase", "due_when")
_SIGN_OFF = ("done_by_role", "done_at")
PHASES = ("design", "filing", "notice", "before_excavation", "during_work")


class ProjectStoreError(ValueError):
    """Input the store refuses (the router answers 422)."""


class NotFound(ProjectStoreError):
    """No such project, or no such item in it (the router answers 404)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value, field: str, cap: str, required: bool = True):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ProjectStoreError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ProjectStoreError(f"{field} must be text")
    if len(value.strip()) > MAX_TEXT[cap]:
        raise ProjectStoreError(f"{field} is over {MAX_TEXT[cap]} characters")
    return value.strip()


def _choice(value, field: str, allowed: tuple, nullable: bool = False):
    if value is None and nullable:
        return None
    if value not in allowed:
        raise ProjectStoreError(f"{field} must be one of: {', '.join(allowed)}")
    return value


def _item_row(item: dict) -> dict:
    """An ActionItem checked against the store's closed sets and caps."""
    if not isinstance(item.get("life_safety"), bool):
        raise ProjectStoreError("life_safety must be true or false")
    return {
        "id": _text(item.get("id"), "item id", "ref"),
        "discipline": _choice(item.get("discipline"), "discipline", DISCIPLINES),
        "hazard": _choice(item.get("hazard"), "hazard", HAZARDS),
        "title": _text(item.get("title"), "title", "title"),
        "why": _text(item.get("why"), "why", "item_text"),
        "code_ref": _text(item.get("code_ref"), "code_ref", "ref", required=False),
        "proof_needed": _text(item.get("proof_needed"), "proof_needed", "item_text", required=False),
        "status": _choice(item.get("status"), "status", ITEM_STATUSES),
        "owner_role": _choice(item.get("owner_role"), "owner_role", ROLES, nullable=True),
        "source_rule": _text(item.get("source_rule"), "source_rule", "ref"),
        "life_safety": int(item["life_safety"]),
        "phase": _choice(item.get("phase"), "phase", PHASES, nullable=True),
        "due_when": _text(item.get("when"), "when", "ref", required=False),
        "applies_to_json": json.dumps([_text(a, "applies_to", "ref") for a in (item.get("applies_to") or [])][:40]),
        "evidence": _text(item.get("evidence"), "evidence", "item_text", required=False),
    }


def _amount(value, field: str):
    """A number of feet or storeys, 0 or more, or None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ProjectStoreError(f"{field} must be a number, 0 or more")
    return float(value)


class ProjectStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._prepare()

    def _prepare(self) -> None:
        """Make the tables, add the columns added since a file was made, and rebuild an out-of-date file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db:
            db.execute("PRAGMA journal_mode = WAL")  # one tab reading never blocks the other tab's write
            db.executescript(DDL)
            for table, column, kind in ADDED_COLUMNS:  # names from our own schema file, never from input
                if column not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            db.commit()
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_STAMP:
                rebuild_tables(db)

    @contextmanager
    def _db(self, write: bool = False):
        """One transaction. A write takes the lock first, so a check (a cap, a member) and its insert are atomic."""
        if not self.db_path.exists():  # deleted or moved aside while the server runs: make a fresh one
            self._prepare()
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            with db:  # commit on success, roll back on any error
                yield db
        finally:
            db.close()

    def _project(self, db, project_id) -> sqlite3.Row:
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise NotFound("no such project")
        row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise NotFound("no such project")
        return row

    def _member_role(self, db, project_id: str, role, field: str, nullable: bool = False):
        role = _choice(role, field, ROLES, nullable=nullable)
        if role is not None and db.execute("SELECT 1 FROM members WHERE project_id = ? AND role = ?",
                                           (project_id, role)).fetchone() is None:
            raise ProjectStoreError(f"{field}: this project has no {role}")
        return role

    def _room(self, db, project_id: str, table: str, adding: int = 1) -> None:
        # `table` comes from MAX_ROWS_PER_PROJECT's fixed keys, never from a request.
        (count,) = db.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (project_id,)).fetchone()
        if count + adding > MAX_ROWS_PER_PROJECT[table]:
            raise ProjectStoreError(f"this project has a limit of {MAX_ROWS_PER_PROJECT[table]} {table}")

    def _touch(self, db, project_id: str) -> None:
        db.execute("UPDATE projects SET version = version + 1, updated_at = ? WHERE id = ?", (_now(), project_id))

    def create_project(self, name, site_bbl, stage, members: list[dict], job_type=None, construction_type=None,
                       work_types=None, excavation_depth_ft=None, proposed_storeys=None) -> dict:
        """`job_type`, `construction_type`, `work_types`, the dig depth and the new building's storeys are what the
        team picked on the setup step; all optional."""
        depth = _amount(excavation_depth_ft, "excavation_depth_ft")
        storeys = _amount(proposed_storeys, "proposed_storeys")
        name = _text(name, "name", "name")
        job_type = _choice(job_type, "job_type", JOB_TYPES, nullable=True)
        construction_type = _choice(construction_type, "construction_type", CONSTRUCTION_TYPES, nullable=True)
        if work_types is not None and not isinstance(work_types, list):
            raise ProjectStoreError("work_types must be a list")
        scope = list(dict.fromkeys(_choice(w, "work_types", WORK_TYPES) for w in work_types or []))
        if not isinstance(site_bbl, str) or not _BBL.fullmatch(site_bbl):
            raise ProjectStoreError("site_bbl must be a 10-digit BBL")
        stage = _choice(stage, "stage", STAGES)
        if not members or len(members) > MAX_ROWS_PER_PROJECT["members"]:
            raise ProjectStoreError(f"a project needs 1 to {MAX_ROWS_PER_PROJECT['members']} members")
        rows = [(_text(m.get("name"), "member name", "member_name"), _choice(m.get("role"), "role", ROLES))
                for m in members]
        project_id, now = secrets.token_hex(8), _now()
        with self._db(write=True) as db:
            db.execute("INSERT INTO projects (id, name, site_bbl, stage, created_at, updated_at, job_type, construction_type,"
                       " work_types_json, excavation_depth_ft, proposed_storeys) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (project_id, name, site_bbl, stage, now, now, job_type, construction_type, json.dumps(scope),
                        depth, storeys))
            db.executemany("INSERT INTO members (project_id, position, name, role) VALUES (?, ?, ?, ?)",
                           [(project_id, i, n, r) for i, (n, r) in enumerate(rows)])
        return self.get_project(project_id)

    def add_items(self, project_id, items: list[dict]) -> dict:
        """Add action items. An item already on the project keeps its status and owner; it is not reset.

        Provenance (`added_by_role`, `added_reason`, `added_at`) is never taken from here: only `record_items`
        sets it, with the server's time."""
        rows = [_item_row(item) for item in items]
        with self._db(write=True) as db:
            self._project(db, project_id)
            existing = {r["id"] for r in db.execute("SELECT id FROM items WHERE project_id = ?", (project_id,))}
            new = list({row["id"]: row for row in rows if row["id"] not in existing}.values())
            self._room(db, project_id, "items", len(new))
            for row in new:
                self._member_role(db, project_id, row["owner_role"], "owner_role", nullable=True)
            start, now = len(existing), _now()
            db.executemany(
                f"INSERT INTO items (project_id, position, updated_at, {', '.join(_ITEM_FIELDS)})"
                f" VALUES (?, ?, ?, {', '.join('?' for _ in _ITEM_FIELDS)})",
                [(project_id, start + i, now, *(row[f] for f in _ITEM_FIELDS)) for i, row in enumerate(new)])
            if new:
                self._touch(db, project_id)
        return self.get_project(project_id)

    def record_items(self, project_id, items: list[dict], by_role) -> dict:
        """Items a team member's document brought in, each with its `added_reason`, stamped with who and when.

        A new item is added (its owner kept only if the project has that role). An item already on the
        project keeps its status and owner, takes the new reason (`flagged_reason` when given) and time, and
        gets the item's owner if it had none: so everyone sees that this document changed it. One transaction, one version bump.
        """
        rows = [(_item_row(item), _text(item.get("added_reason"), "added_reason", "reason"),
                 _text(item.get("flagged_reason"), "flagged_reason", "reason", required=False)) for item in items]
        with self._db(write=True) as db:
            self._project(db, project_id)
            role = self._member_role(db, project_id, by_role, "added_by_role")
            members = {r["role"] for r in db.execute("SELECT role FROM members WHERE project_id = ?", (project_id,))}
            existing = {r["id"]: r["owner_role"] for r in
                        db.execute("SELECT id, owner_role FROM items WHERE project_id = ?", (project_id,))}
            by_id = {row["id"]: (row, added, flagged) for row, added, flagged in rows}
            new = [(row, added) for row, added, _ in by_id.values() if row["id"] not in existing]
            self._room(db, project_id, "items", len(new))
            start, now = len(existing), _now()
            for i, (row, reason) in enumerate(new):
                row = {**row, "owner_role": row["owner_role"] if row["owner_role"] in members else None}
                columns = (*_ITEM_FIELDS, *_PROVENANCE)
                db.execute(f"INSERT INTO items (project_id, position, updated_at, {', '.join(columns)})"
                           f" VALUES (?, ?, ?, {', '.join('?' for _ in columns)})",
                           (project_id, start + i, now, *(row[f] for f in _ITEM_FIELDS), role, reason, now))
            for row, added, flagged in by_id.values():
                if row["id"] not in existing:
                    continue
                reason = flagged or added
                owner = existing[row["id"]]
                if owner is None and row["owner_role"] in members:
                    owner = row["owner_role"]
                db.execute("UPDATE items SET added_by_role = ?, added_reason = ?, added_at = ?, owner_role = ?,"
                           " updated_at = ? WHERE project_id = ? AND id = ?",
                           (role, reason, now, owner, now, project_id, row["id"]))
            if by_id:
                self._touch(db, project_id)
        return self.get_project(project_id)

    def update_items(self, project_id, updates: list[dict]) -> dict:
        """Each update: {"id", "status"?, "owner_role"?}; owner_role None unassigns, UNCHANGED leaves it."""
        with self._db(write=True) as db:
            self._project(db, project_id)
            for update in updates:
                item_id = update.get("id")
                if db.execute("SELECT 1 FROM items WHERE project_id = ? AND id = ?", (project_id, item_id)).fetchone() is None:
                    raise NotFound(f"no item {item_id!r} on this project")
                changes = {}
                if update.get("status", UNCHANGED) is not UNCHANGED and update["status"] is not None:
                    changes["status"] = _choice(update["status"], "status", ITEM_STATUSES)
                    # The sign-off: who marked it done and when; any other status clears it.
                    done = changes["status"] == "done"
                    by = update.get("by_role")
                    changes["done_by_role"] = self._member_role(db, project_id, by, "by_role", nullable=True) if done else None
                    changes["done_at"] = _now() if done else None
                if update.get("owner_role", UNCHANGED) is not UNCHANGED:
                    changes["owner_role"] = self._member_role(db, project_id, update["owner_role"], "owner_role", nullable=True)
                if not changes:
                    raise ProjectStoreError(f"nothing to change for item {item_id!r}: send status or owner_role")
                columns = ", ".join(f"{column} = ?" for column in changes)  # names from the fixed keys above
                db.execute(f"UPDATE items SET {columns}, updated_at = ? WHERE project_id = ? AND id = ?",
                           (*changes.values(), _now(), project_id, item_id))
            if updates:
                self._touch(db, project_id)
        return self.get_project(project_id)

    def add_note(self, project_id, author_role, text) -> dict:
        text = _text(text, "text", "note")
        with self._db(write=True) as db:
            self._project(db, project_id)
            role = self._member_role(db, project_id, author_role, "author_role")
            self._room(db, project_id, "notes")
            db.execute("INSERT INTO notes (id, project_id, author_role, text, created_at) VALUES (?, ?, ?, ?, ?)",
                       (secrets.token_hex(8), project_id, role, text, _now()))
            self._touch(db, project_id)
        return self.get_project(project_id)

    def add_pin(self, project_id, kind, ref_id, title, by_role, body=None) -> dict:
        """`body` is the pinned text as the reader saw it (a chat answer with its source labels): kept exactly as sent."""
        kind, title = _choice(kind, "kind", PIN_KINDS), _text(title, "title", "title")
        ref_id = _text(ref_id, "ref_id", "ref")
        if body is not None and not isinstance(body, str):
            raise ProjectStoreError("body must be text")
        if body is not None and len(body) > MAX_TEXT["pin_body"]:
            raise ProjectStoreError(f"body is over {MAX_TEXT['pin_body']} characters")
        body = body or None
        with self._db(write=True) as db:
            self._project(db, project_id)
            role = self._member_role(db, project_id, by_role, "by_role")
            self._room(db, project_id, "pins")
            db.execute("INSERT INTO pins (id, project_id, kind, ref_id, title, by_role, created_at, body)"
                       " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (secrets.token_hex(8), project_id, kind, ref_id, title, role, _now(), body))
            self._touch(db, project_id)
        return self.get_project(project_id)

    def set_structural_model(self, project_id, model: dict) -> dict:
        """Keep the Revit reader's model as sent (already checked against the StructuralModel contract)."""
        model_json = json.dumps(model, ensure_ascii=False, sort_keys=True)
        if len(model_json.encode()) > MAX_MODEL_BYTES:
            raise ProjectStoreError(f"the model is over {MAX_MODEL_BYTES} bytes")
        with self._db(write=True) as db:
            self._project(db, project_id)
            db.execute("UPDATE projects SET structural_model_json = ? WHERE id = ?", (model_json, project_id))
            self._touch(db, project_id)
        return self.get_project(project_id)

    def version(self, project_id) -> int:
        """Bumped by every write: a tab polls it and refetches the project when it changes."""
        with self._db() as db:
            return self._project(db, project_id)["version"]

    def get_project(self, project_id) -> dict:
        return self.snapshot(project_id)[0]

    def snapshot(self, project_id) -> tuple[dict, int]:
        """The project and its version from one read, so an ETag never runs ahead of the body it labels."""
        with self._db() as db:
            row = self._project(db, project_id)

            def rows(sql: str) -> list[dict]:
                return [dict(r) for r in db.execute(sql, (project_id,)).fetchall()]

            items = rows(f"SELECT {', '.join(_ITEM_FIELDS + _PROVENANCE + _SIGN_OFF)} FROM items WHERE project_id = ? ORDER BY position")
            for item in items:
                item["when"] = item.pop("due_when")
                raw = item.pop("applies_to_json")
                item["applies_to"] = json.loads(raw) if raw else []
            project = {
                "id": row["id"], "name": row["name"], "site_bbl": row["site_bbl"], "stage": row["stage"],
                "members": rows("SELECT name, role FROM members WHERE project_id = ? ORDER BY position"),
                "items": [{**item, "life_safety": bool(item["life_safety"])} for item in items],
                "notes": rows("SELECT id, author_role, text, created_at FROM notes WHERE project_id = ? ORDER BY created_at, rowid"),
                "pins": rows("SELECT id, kind, ref_id, title, by_role, created_at, body FROM pins WHERE project_id = ?"
                             " ORDER BY created_at, rowid"),
                "structural_model": json.loads(row["structural_model_json"]) if row["structural_model_json"] else None,
                "created_at": row["created_at"],
                "job_type": row["job_type"],
                "construction_type": row["construction_type"],
                "work_types": json.loads(row["work_types_json"]) if row["work_types_json"] else [],
                "excavation_depth_ft": row["excavation_depth_ft"],
                "proposed_storeys": row["proposed_storeys"],
            }
            return project, row["version"]
