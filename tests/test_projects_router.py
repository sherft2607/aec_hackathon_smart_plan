"""The projects routes in the real app: two tabs as two roles, ETag polling, contract bodies, 404 and 422."""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from api.contracts import Project
from api.main import app
from api.routers.projects_router import project_store
from api.store.project_store import ProjectStore
from api.stubs import FIXTURE_HEADER

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"
BOTH = [{"name": "Architect", "role": "architect"}, {"name": "Structural engineer", "role": "structural_engineer"}]


def fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


class ProjectsRouterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        store = ProjectStore(Path(self.tmp.name) / "projects.sqlite")
        app.dependency_overrides[project_store] = lambda: store
        self.architect_tab, self.engineer_tab = TestClient(app), TestClient(app)
        created = self.architect_tab.post("/api/projects", json={"name": "Bedford", "site_bbl": "3052110074",
                                                                  "stage": "design", "members": BOTH})
        self.assertEqual(created.status_code, 200, created.text)
        self.project_id = created.json()["id"]
        self.path = f"/api/projects/{self.project_id}"

    def tearDown(self):
        app.dependency_overrides.pop(project_store, None)
        self.tmp.cleanup()


class ProjectsRouterTests(ProjectsRouterTestCase):
    def test_two_tabs_as_two_roles_on_one_project(self):
        seen = self.engineer_tab.get(self.path)
        self.assertEqual(self.engineer_tab.get(self.path, headers={"If-None-Match": seen.headers["ETag"]}).status_code, 304)
        self.architect_tab.post(f"{self.path}/items", json=fixture("actions"))
        self.engineer_tab.patch(f"{self.path}/items", json=[{"id": "act-bc-3309-4", "status": "in_progress"}])
        self.engineer_tab.post(f"{self.path}/notes", json={"author_role": "structural_engineer", "text": "Survey Tuesday."})
        polled = self.architect_tab.get(self.path, headers={"If-None-Match": seen.headers["ETag"]})
        self.assertEqual(polled.status_code, 200)
        project = Project.model_validate(polled.json())
        self.assertEqual(project.items[0].status, "in_progress")
        self.assertEqual(project.notes[0].author_role, "structural_engineer")
        self.assertNotEqual(polled.headers["ETag"], seen.headers["ETag"])
        self.assertIsNone(polled.headers.get(FIXTURE_HEADER), "a real project is never labelled sample data")

    def test_a_write_answers_with_the_whole_project_and_its_etag(self):
        answer = self.architect_tab.post(f"{self.path}/pins", json={"kind": "case", "ref_id": "case-714-39th-2018",
                                                                    "title": "A similar excavation", "by_role": "architect"})
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json()["pins"][0]["ref_id"], "case-714-39th-2018")
        self.assertEqual(self.architect_tab.get(self.path, headers={"If-None-Match": answer.headers["ETag"]}).status_code, 304)

    def test_patch_left_out_owner_stays_and_null_unassigns(self):
        self.architect_tab.post(f"{self.path}/items", json=fixture("actions"))
        kept = self.architect_tab.patch(f"{self.path}/items", json=[{"id": "act-bc-3309-4", "status": "done"}]).json()
        self.assertEqual(kept["items"][0]["owner_role"], "structural_engineer")
        cleared = self.architect_tab.patch(f"{self.path}/items", json=[{"id": "act-bc-3309-4", "owner_role": None}]).json()
        self.assertEqual((cleared["items"][0]["status"], cleared["items"][0]["owner_role"]), ("done", None))

    def test_the_structural_model_is_checked_and_kept(self):
        model = fixture("structural_model")
        self.assertEqual(self.architect_tab.post(f"{self.path}/model", json=model).json()["structural_model"], model)
        self.assertEqual(self.architect_tab.post(f"{self.path}/model", json={**model, "confidence": 2}).status_code, 422)

    def test_project_keeps_depth_and_storeys(self):
        body = {"name": "Park", "site_bbl": "3015790010", "stage": "design", "members": BOTH,
                "excavation_depth_ft": 20, "proposed_storeys": 9}
        made = self.architect_tab.post("/api/projects", json=body)
        self.assertEqual(made.status_code, 200, made.text)
        got = self.architect_tab.get(f"/api/projects/{made.json()['id']}").json()
        self.assertEqual((got["excavation_depth_ft"], got["proposed_storeys"], got["stage"]), (20, 9, "design"))
        # An older body without them still creates a project, with both left empty.
        old = self.architect_tab.get(self.path).json()
        self.assertEqual((old["excavation_depth_ft"], old["proposed_storeys"]), (None, None))
        bad = self.architect_tab.post("/api/projects", json={**body, "excavation_depth_ft": -1})
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_items_keep_phase_and_the_done_sign_off(self):
        item = {**fixture("actions")[0], "phase": "notice", "when": "60 days before work"}
        self.architect_tab.post(f"{self.path}/items", json=[item])
        got = {i["id"]: i for i in self.architect_tab.get(self.path).json()["items"]}[item["id"]]
        self.assertEqual((got["phase"], got["when"]), ("notice", "60 days before work"))
        done = self.engineer_tab.patch(f"{self.path}/items",
                                       json=[{"id": item["id"], "status": "done", "by_role": "structural_engineer"}]).json()
        row = {i["id"]: i for i in done["items"]}[item["id"]]
        self.assertEqual(row["done_by_role"], "structural_engineer")
        self.assertTrue(row["done_at"])
        reopened = self.engineer_tab.patch(f"{self.path}/items", json=[{"id": item["id"], "status": "open"}]).json()
        row = {i["id"]: i for i in reopened["items"]}[item["id"]]
        self.assertEqual((row["done_by_role"], row["done_at"]), (None, None))
        anon = self.engineer_tab.patch(f"{self.path}/items", json=[{"id": item["id"], "status": "done"}]).json()
        row = {i["id"]: i for i in anon["items"]}[item["id"]]
        self.assertIsNone(row["done_by_role"])
        self.assertTrue(row["done_at"])

    def test_items_keep_their_neighbors_and_record_line(self):
        item = {**fixture("actions")[0], "applies_to": ["19 Marcus Garvey Blvd (built 1931, attached)"],
                "evidence": "On record here: 2 complaints."}
        self.architect_tab.post(f"{self.path}/items", json=[item])
        got = {i["id"]: i for i in self.architect_tab.get(self.path).json()["items"]}[item["id"]]
        self.assertEqual(got["applies_to"], item["applies_to"])
        self.assertEqual(got["evidence"], item["evidence"])

    def test_unknown_projects_and_items_are_404(self):
        for response in (
            self.architect_tab.get("/api/projects/0123456789abcdef"),
            self.architect_tab.get("/api/projects/proj-sample"),
            self.architect_tab.post("/api/projects/0123456789abcdef/notes", json={"author_role": "architect", "text": "x"}),
            self.architect_tab.patch(f"{self.path}/items", json=[{"id": "nope", "status": "done"}]),
        ):
            self.assertEqual(response.status_code, 404, response.text)

    def test_refused_input_is_422(self):
        solo = self.architect_tab.post("/api/projects", json={"name": "Solo", "site_bbl": "3052110074", "stage": "design",
                                                               "members": BOTH[:1]}).json()["id"]
        for response in (
            self.architect_tab.post(f"/api/projects/{solo}/notes", json={"author_role": "structural_engineer", "text": "x"}),
            self.architect_tab.post(f"{self.path}/notes", json={"author_role": "architect", "text": "x", "extra": 1}),
            self.architect_tab.post(f"{self.path}/notes", json={"author_role": "architect", "text": "x" * 5000}),
            self.architect_tab.post("/api/projects", json={"name": "x", "site_bbl": "1", "stage": "design", "members": BOTH}),
            self.architect_tab.patch(f"{self.path}/items", json=[{"id": "act-bc-3309-4", "status": "verified"}]),
        ):
            self.assertEqual(response.status_code, 422, response.text)



class ModelInputHookTests(ProjectsRouterTestCase):
    """Once PR 13's model_input is in: its reader cleans a Revit export, its store gets the site's copy."""

    def setUp(self):
        super().setUp()
        self.saved = []
        revit = types.ModuleType("model_input.revit")

        class ModelInputError(ValueError):
            pass

        def read_revit(payload):
            if payload["levels"] == 99:
                raise ModelInputError("levels out of range")
            return {**payload, "material": payload["material"].strip()}

        revit.ModelInputError, revit.read_revit = ModelInputError, read_revit
        model_store = types.ModuleType("model_input.store")
        model_store.save = lambda project_id, bbl, model: self.saved.append((project_id, bbl, model))
        self.modules = {"model_input": types.ModuleType("model_input"), "model_input.revit": revit,
                        "model_input.store": model_store}
        self.model = {**fixture("structural_model"), "source": "revit", "material": "  steel  "}

    def post(self, model):
        with mock.patch.dict(sys.modules, self.modules):
            return self.architect_tab.post(f"{self.path}/model", json=model)

    def test_a_revit_export_is_cleaned_kept_and_handed_to_the_site_profile(self):
        kept = self.post(self.model).json()["structural_model"]
        self.assertEqual(kept["material"], "steel")
        self.assertEqual(self.saved, [(self.project_id, "3052110074", kept)])

    def test_a_refused_export_is_422_and_kept_nowhere(self):
        self.assertEqual(self.post({**self.model, "levels": 99}).status_code, 422)
        self.assertIsNone(self.engineer_tab.get(self.path).json()["structural_model"])
        self.assertEqual(self.saved, [])

    def test_a_broken_model_input_refuses_rather_than_skipping_it(self):
        def broken_import(name, *args, **kwargs):
            raise ImportError("half-installed")
        with mock.patch("api.routers.router_data.importlib.import_module", broken_import):
            answer = TestClient(app).post(f"{self.path}/model", json=self.model)
        self.assertEqual(answer.status_code, 500, answer.text)
        self.assertIsNone(self.engineer_tab.get(self.path).json()["structural_model"])


class ProjectSetupRouterTests(ProjectsRouterTestCase):
    def test_create_round_trips_setup_fields(self):
        created = self.architect_tab.post("/api/projects", json={
            "name": "Setup", "site_bbl": "3052110074", "stage": "pre_filing", "members": BOTH,
            "job_type": "new_building", "construction_type": "concrete", "work_types": ["excavation", "foundation"]})
        self.assertEqual(created.status_code, 200, created.text)
        read = self.engineer_tab.get(f"/api/projects/{created.json()['id']}").json()
        self.assertEqual((read["job_type"], read["construction_type"], read["work_types"]),
                         ("new_building", "concrete", ["excavation", "foundation"]))


if __name__ == "__main__":
    unittest.main()


class OldStoreFileTests(unittest.TestCase):
    """A store file made before the developer/contractor roles and document pins takes them once it is reopened."""

    def test_old_store_file_takes_new_roles_and_document_pins(self):
        import sqlite3
        from contextlib import closing

        from api.store import project_store_schema as schema

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projects.sqlite"
            old_ddl = schema.DDL.replace(", 'developer', 'contractor'", "").replace(", 'document'", "")
            self.assertNotEqual(old_ddl, schema.DDL)
            with closing(sqlite3.connect(path)) as db:
                db.executescript(old_ddl)
            store = ProjectStore(path)
            app.dependency_overrides[project_store] = lambda: store
            try:
                client = TestClient(app, raise_server_exceptions=False)
                response = client.post("/api/projects", json={
                    "name": "Four", "site_bbl": "3052110074", "stage": "design",
                    "members": BOTH + [{"name": "Developer", "role": "developer"}]})
                pin = client.post(f"/api/projects/{response.json()['id']}/pins", json={
                    "kind": "document", "ref_id": "structural", "title": "S-101.pdf", "by_role": "developer"})
            finally:
                app.dependency_overrides.pop(project_store, None)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(pin.status_code, 200, pin.text)
