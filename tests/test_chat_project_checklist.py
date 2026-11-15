"""The chat reads the open project's own checklist, so it and the project screen show one list.

A temp project store and the fixture site parts only: nothing here reaches the network or the real store.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from api.routers.chat import chat_project_checklist, chat_service
from api.routers.chat.chat_answer_build import build_parts
from api.routers.chat.chat_app_context import app_context
from api.routers.chat.chat_models import ChatRequest
from api.routers.chat.chat_project_checklist import ANOTHER_LOT, NO_PROJECT, NOT_IN_AS_OF
from api.routers.chat.chat_site_view import SiteView
from api.store.project_store import ProjectStore
from tests.chat_test_support import ScriptedModel, item
from tests.test_chat_app_context import OTHER_BBL, SAMPLE_BBL, fixture, site_parts

TEAM = [{"name": "Person One", "role": "architect"}, {"name": "Person Two", "role": "structural_engineer"}]
FROM_A_DRAWING = {
    "id": "act-excavation-support-drawings", "discipline": "structural", "hazard": "structural",
    "title": "Excavation-support drawings", "why": "The confirmed drawing shows a cut next to an attached building.",
    "status": "open", "owner_role": "structural_engineer", "source_rule": "from-model", "life_safety": True,
    "added_reason": "the confirmed drawing shows excavation below the neighbour's footing"}


class ProjectChecklistTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = ProjectStore(Path(tmp.name) / "projects.sqlite")
        patched = mock.patch.object(chat_project_checklist, "project_store", return_value=self.store)
        patched.start()
        self.addCleanup(patched.stop)
        self.project_id = self.store.create_project(
            "A made-up job", OTHER_BBL, "pre_filing", TEAM, job_type="new_building", work_types=["support_of_excavation"])["id"]
        self.store.add_items(self.project_id, fixture("actions"))
        self.store.update_items(self.project_id, [{"id": "act-bc-3309-4", "status": "done"}])
        self.store.record_items(self.project_id, [FROM_A_DRAWING], "structural_engineer")

    def context(self, project_id="open", bbl=OTHER_BBL, as_of=None):
        with site_parts(bbl=bbl) as load:
            context = app_context(bbl, None, None, as_of, self.project_id if project_id == "open" else project_id)
        return context, {call.args[0]: call.kwargs for call in load.call_args_list}

    def count(self, context) -> str:
        """The sentence the server writes when the answer asks for the number of action items."""
        built = build_parts(SiteView(context), {"items": [item("dataset_check", dataset_key="action_items")], "actions": []}, [])
        self.assertEqual(built.problems, [])
        return built.parts[0].text

    def answer(self, question, project_id="open"):
        request = ChatRequest(bbl=OTHER_BBL, question=question, project_id=self.project_id if project_id == "open" else project_id)
        with site_parts(bbl=OTHER_BBL):
            return chat_service.answer(request, app_context, None)


class OpenProjectTests(ProjectChecklistTestCase):
    def test_the_action_items_are_the_projects_own_with_its_teams_status_and_added_items(self):
        context, asked = self.context()
        self.assertEqual(context.project.value, {"stage": "pre_filing", "job_type": "new_building", "construction_type": None,
                                                 "work_types": ["support_of_excavation"]})
        items = {item["id"]: item for item in context.actions.value}
        self.assertEqual(list(items), [a["id"] for a in fixture("actions")] + [FROM_A_DRAWING["id"]])
        self.assertEqual((items["act-bc-3309-4"]["status"], items[FROM_A_DRAWING["id"]]["added_by_role"]),
                         ("done", "structural_engineer"))
        # The lot's general list is not read at all, and the site facts are asked for the project's job and stage.
        self.assertNotIn("actions", asked)
        self.assertEqual(asked["profile"], {"job_type": "new_building", "stage": "pre_filing", "as_of": None})

    def test_the_model_reads_it_as_the_projects_checklist_with_owner_and_status_and_no_member_names(self):
        text = SiteView(self.context()[0]).digest()
        self.assertIn("PROJECT CHECKLIST (the open project's own items", text)
        self.assertIn("job type: new building; scope: support of excavation; stage: pre filing", text)
        self.assertIn("Excavation-support drawings", text)
        self.assertIn("status: done | life safety: yes | owner: structural engineer", text)
        self.assertIn("added by the structural engineer: the confirmed drawing shows excavation", text)
        self.assertNotIn("structural_engineer |", text)  # roles are read as words, not stored values
        self.assertIn("owner: not assigned", text)  # the fixture's third item has no owner
        self.assertNotIn("ACTION ITEMS (", text)
        self.assertNotIn("Person One", text)
        self.assertNotIn("Person Two", text)

    def test_the_count_and_an_empty_checklist_are_said_of_the_project_not_the_site(self):
        self.assertEqual(self.count(self.context()[0]), "4 action items on the open project's checklist.")
        listed = self.answer("What is on the checklist for the structural engineer?").plain_text
        self.assertIn('Project checklist item (owner: structural engineer; status: open): "Excavation-support drawings"', listed)
        self.assertIn("(owner: structural engineer; status: done)", listed)

    def test_who_owns_a_checklist_item_asks_for_a_role_so_it_gets_no_names_notice(self):
        def names_notice(question, project_id="open"):
            return "names_withheld" in [part.code for part in self.answer(question, project_id).parts if part.kind == "notice"]

        self.assertFalse(names_notice("Who owns the excavation-support drawings item on the checklist?"))
        # Asking for a name outright still gets the notice, and so does "who" with no project open or about the lot.
        self.assertTrue(names_notice("What is the name of the owner of that checklist item?"))
        self.assertTrue(names_notice("Who owns the excavation-support drawings item on the checklist?", None))
        self.assertTrue(names_notice("Who owns this building?"))
        empty = self.store.create_project("Not drafted yet", OTHER_BBL, "design", TEAM)["id"]
        context, _ = self.context(empty)
        self.assertEqual((context.project.status, context.actions.value), ("ok", []))
        self.assertIn("none on this project yet", SiteView(context).digest())
        self.assertIn("None found: no action item on the open project's checklist.", self.answer("Any action items?", empty).plain_text)

    def test_the_first_answer_reads_the_projects_checklist_too(self):
        model = ScriptedModel([item("dataset_check", dataset_key="action_items")])
        request = ChatRequest(bbl=OTHER_BBL, question="Who owns the checklist items?", project_id=self.project_id)
        with site_parts(bbl=OTHER_BBL):
            answer = chat_service.first_answer(request, app_context, model)
        self.assertIn("PROJECT CHECKLIST", " ".join(block["text"] for block in model.first_opened_with["system"]))
        self.assertIn("on the open project's checklist", answer.plain_text)
        self.assertNotIn("names_withheld", [part.code for part in answer.parts if part.kind == "notice"])


class NoProjectToReadTests(ProjectChecklistTestCase):
    def general(self, context, asked, reason):
        self.assertEqual((context.project.status, context.project.reason), ("not_available", reason))
        self.assertEqual([a["id"] for a in context.actions.value], [a["id"] for a in fixture("actions")])
        self.assertIn("actions", asked)
        text = SiteView(context).digest()
        self.assertIn("ACTION ITEMS (the lot's general list from the action rules, not a project's checklist", text)
        self.assertNotIn("PROJECT CHECKLIST", text)
        self.assertNotIn("owner:", text)

    def test_with_no_project_open_the_list_is_the_lots_general_one_and_says_so(self):
        self.general(*self.context(None), NO_PROJECT)
        self.assertEqual(self.count(self.context(None)[0]), "3 action items for this site.")

    def test_a_project_on_another_lot_is_not_this_sites_checklist(self):
        with site_parts(sample=("profile", "similar", "warnings", "actions")) as load:
            context = app_context(SAMPLE_BBL, None, None, None, self.project_id)
        self.general(context, {call.args[0]: call.kwargs for call in load.call_args_list}, ANOTHER_LOT)

    def test_a_view_as_of_an_earlier_day_does_not_use_todays_checklist(self):
        self.general(*self.context(as_of="2026-06-01"), NOT_IN_AS_OF)


class ProjectThatCannotBeReadTests(ProjectChecklistTestCase):
    def unread(self, context, said):
        self.assertEqual(context.project.status, "error")
        self.assertIn(said, context.project.reason)
        self.assertEqual(context.actions.status, "ok")  # the lot's general list still loads
        text = SiteView(context).digest()
        self.assertIn("THE OPEN PROJECT'S CHECKLIST COULD NOT BE READ", text)
        self.assertIn("never say what is or is not on the project's checklist", text)
        self.assertNotIn("PROJECT CHECKLIST (", text)

    def test_a_project_the_store_does_not_hold_is_a_failure_never_no_project(self):
        self.unread(self.context("0" * 32)[0], "does not hold the project")
        self.assertIn("This is the lot's general list: the open project's checklist could not be read.",
                      self.answer("What is on the checklist?", "0" * 32).plain_text)
        self.assertEqual(self.count(self.context("0" * 32)[0]),
                         "3 action items for this site. This is the lot's general list: the open project's checklist could not be read.")

    def test_a_store_that_cannot_answer_is_a_failure_with_its_reason(self):
        with mock.patch.object(self.store, "get_project", side_effect=sqlite3.OperationalError("database is locked")):
            self.unread(self.context()[0], "could not answer (OperationalError)")


if __name__ == "__main__":
    unittest.main()
