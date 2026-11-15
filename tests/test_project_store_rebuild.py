"""A store file made under older value lists is rebuilt when the store opens, keeping every row. Temp files only."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from api.store import project_store_schema as schema
from api.store.project_store import ProjectStore

PROJECT = "0123456789abcdef"
# The tables as a file made before 2026-11-14 had them: no developer or contractor role, no document pin.
OLD_DDL = schema.DDL.replace(", 'developer', 'contractor'", "").replace(", 'document'", "")


def old_file(path: Path, ddl: str = OLD_DDL, member_role: str = "architect") -> None:
    """One project with a member, an item, a note and a pin, written the way the first release wrote them."""
    with closing(sqlite3.connect(path)) as db:
        db.executescript(ddl)
        db.execute("INSERT INTO projects (id, name, site_bbl, stage, version, created_at, updated_at)"
                   " VALUES (?, 'Old one', '3052110074', 'design', 7, '2026-11-01', '2026-11-02')", (PROJECT,))
        db.execute("INSERT INTO members VALUES (?, 0, 'Test member', ?)", (PROJECT, member_role))
        db.execute("INSERT INTO items (project_id, id, position, discipline, hazard, title, why, status, source_rule,"
                   " life_safety, updated_at) VALUES (?, 'item-1', 0, 'structural', 'structural', 'Check walls',"
                   " 'Because', 'in_progress', 'rule-1', 1, '2026-11-02')", (PROJECT,))
        db.execute("INSERT INTO notes VALUES ('note-1', ?, 'architect', 'old note', '2026-11-02')", (PROJECT,))
        db.execute("INSERT INTO pins (id, project_id, kind, ref_id, title, by_role, created_at)"
                   " VALUES ('pin-1', ?, 'record', 'r1', 'A record', 'architect', '2026-11-02')", (PROJECT,))
        db.commit()


def table_sql(path: Path, name: str) -> str:
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]


class RebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "projects.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_old_file_keeps_every_row_and_takes_the_new_values(self):
        old_file(self.path)
        store = ProjectStore(self.path)
        project, version = store.snapshot(PROJECT)
        self.assertEqual(version, 7)
        self.assertEqual(project["members"], [{"name": "Test member", "role": "architect"}])
        self.assertEqual([(i["id"], i["status"], i["life_safety"]) for i in project["items"]],
                         [("item-1", "in_progress", True)])
        self.assertEqual([n["text"] for n in project["notes"]], ["old note"])
        self.assertEqual([(p["kind"], p["ref_id"]) for p in project["pins"]], [("record", "r1")])
        # What the old file refused: a document pin, and developer and contractor members and owners.
        store.add_pin(PROJECT, "document", "structural", "S-101.pdf", "architect", "AI reading")
        new = store.create_project("New one", "3052110074", "design", [
            {"name": "Test developer", "role": "developer"}, {"name": "Test contractor", "role": "contractor"}])
        self.assertEqual({m["role"] for m in new["members"]}, {"developer", "contractor"})

    def test_the_rebuilt_file_still_refuses_values_outside_the_lists_and_keeps_its_links(self):
        old_file(self.path)
        ProjectStore(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], schema.SCHEMA_STAMP)
            self.assertEqual({row[2] for row in db.execute("PRAGMA foreign_key_list(members)")}, {"projects"})
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
            self.assertTrue({"notes_by_project", "pins_by_project"} <= names)
            self.assertFalse(any(name.startswith("_rebuild_") for name in names))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO members VALUES (?, 1, 'x', 'surveyor')", (PROJECT,))
        self.assertIn("'developer'", table_sql(self.path, "members"))

    def test_a_file_is_rebuilt_once_not_on_every_open(self):
        old_file(self.path)
        ProjectStore(self.path)
        with mock.patch("api.store.project_store.rebuild_tables") as rebuild:
            ProjectStore(self.path)
        rebuild.assert_not_called()

    def test_a_row_the_new_lists_refuse_stops_the_rebuild_and_leaves_the_file_as_it_was(self):
        # A role later removed from the contract: the rebuild refuses rather than dropping the member.
        old_file(self.path, schema.DDL.replace("'architect'", "'architect', 'surveyor'"), member_role="surveyor")
        before = table_sql(self.path, "members")
        with self.assertRaises(sqlite3.IntegrityError):
            ProjectStore(self.path)
        self.assertEqual(table_sql(self.path, "members"), before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT role FROM members").fetchall(), [("surveyor",)])
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_a_file_deleted_while_the_store_is_open_is_made_again(self):
        store = ProjectStore(self.path)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        project = store.create_project("After", "3052110074", "design", [{"name": "Test architect", "role": "architect"}])
        self.assertEqual(store.get_project(project["id"])["name"], "After")


if __name__ == "__main__":
    unittest.main()
