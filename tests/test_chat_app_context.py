"""The chat's site loader over the app's own site functions: real data, the labelled sample, and failures."""

import contextlib
import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from api.routers.chat import chat_app_context, chat_service
from api.routers.chat.chat_app_context import RULE_CHECKS_SOURCE, SAMPLE_OF_ANOTHER_SITE, app_context
from api.routers.chat.chat_fixture_context import fixture_context
from api.routers.chat.chat_models import ChatRequest
from api.routers.chat.chat_site_context import SiteContextUnavailable
from api.routers.router_data import DataUnavailable, LoadedData

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
SAMPLE_BBL = "3052110074"
OTHER_BBL = "1000010001"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


@contextlib.contextmanager
def site_parts(sample=(), failing=(), bbl=SAMPLE_BBL, checks=fixture):
    """A stand-in for load_site_part: every part answers from the fixtures, as real data unless named in `sample`.

    `checks` stands in for the rule-check function: by default it answers from the fixture, a function is
    called as the real one is (lot, as-of day), and None is "that function has not landed". The loader mock
    this yields carries the two stand-ins as `.rule_checks` and `.find_rule_checks`.
    """
    names = {"profile": "site_profile", "similar": "similar_cases", "warnings": "warnings", "actions": "actions"}

    def load(part, asked_bbl, **options):
        if part in failing:
            raise DataUnavailable(f"{part} module could not answer (RuntimeError)")
        data = fixture(names[part])
        if part == "profile":
            data = {**data, "bbl": bbl if part not in sample else SAMPLE_BBL}
        return LoadedData(data, part in sample)

    def rule_checks(asked_bbl, as_of=None):
        return checks("warning_checks") if checks is fixture else checks(asked_bbl, as_of)
    owner = mock.Mock(side_effect=rule_checks)
    with mock.patch.object(chat_app_context, "load_site_part", side_effect=load) as loader, \
            mock.patch.object(chat_app_context, "owner_function", return_value=None if checks is None else owner) as find:
        loader.rule_checks, loader.find_rule_checks = owner, find
        yield loader


def kinds(answer):
    return [part.code if part.kind == "notice" else part.kind for part in answer.parts][1:]


def ask(question, bbl):
    return chat_service.answer(ChatRequest(bbl=bbl, question=question), app_context, None)


class AppContextTests(unittest.TestCase):
    def test_real_parts_are_read_for_the_lot_asked_about_and_not_marked_sample(self):
        with site_parts(bbl=OTHER_BBL) as load:
            context = app_context(OTHER_BBL, "new_building", "design", "2026-06-01")
        self.assertEqual((context.sample, context.profile.status, context.warnings.status, context.actions.status, context.similar.status),
                         (False, "ok", "ok", "ok", "ok"))
        self.assertEqual({call.args[0]: call.kwargs for call in load.call_args_list}, {
            "profile": {"job_type": "new_building", "stage": "design", "as_of": "2026-06-01"}, "similar": {},
            "warnings": {"as_of": "2026-06-01"}, "actions": {"stage": "design", "job_type": "new_building"}})
        self.assertEqual({call.args[1] for call in load.call_args_list}, {OTHER_BBL})
        self.assertEqual(context.similar.value[0].keys(), {"similar", "case"})

    def test_sample_parts_are_used_for_the_sample_site_and_marked(self):
        with site_parts(sample=("profile", "similar", "warnings", "actions")):
            context = app_context(SAMPLE_BBL, None, None, None)
        self.assertEqual((context.sample, context.warnings.status), (True, "ok"))

    def test_sample_data_is_never_shown_as_another_sites(self):
        with site_parts(sample=("profile",)), self.assertRaises(SiteContextUnavailable):
            app_context(OTHER_BBL, None, None, None)
        with site_parts(sample=("warnings", "actions"), bbl=OTHER_BBL):
            context = app_context(OTHER_BBL, None, None, None)
            self.assertEqual((context.sample, context.warnings.status, context.warnings.reason), (False, "not_available", SAMPLE_OF_ANOTHER_SITE))
            self.assertEqual(kinds(ask("Any early warnings?", OTHER_BBL)), ["unknown"])
            self.assertEqual(kinds(ask("What are the action items?", OTHER_BBL)), ["unknown"])
            self.assertIn("case", kinds(ask("Any similar cases?", OTHER_BBL)))

    def test_a_part_that_fails_is_a_failure_never_an_empty_list(self):
        with site_parts(failing=("warnings", "similar"), bbl=OTHER_BBL):
            context = app_context(OTHER_BBL, None, None, None)
            self.assertEqual((context.warnings.status, context.similar.status), ("error", "error"))
            self.assertIn("could not answer", context.warnings.reason)
            self.assertEqual(kinds(ask("Any early warnings?", OTHER_BBL)), ["unknown"])
            self.assertEqual(kinds(ask("Any similar cases?", OTHER_BBL)), ["unknown"])
        with site_parts(failing=("profile",)), self.assertRaises(SiteContextUnavailable):
            app_context(SAMPLE_BBL, None, None, None)

    def test_a_broken_layer_file_is_a_failure_and_a_bad_lot_is_refused(self):
        with site_parts(), mock.patch.object(chat_app_context, "load_layer_catalog", side_effect=DataUnavailable("catalog.json is broken")):
            self.assertEqual(app_context(SAMPLE_BBL, None, None, None).layers.status, "error")
        with self.assertRaises(HTTPException):
            app_context("9000000000", None, None, None)


def one_rule_failed(bbl, as_of):
    return [{**check, "status": "error", "detail": "the weather source couldn't load", "warnings": 0} if number == 0 else check
            for number, check in enumerate(fixture("warning_checks"))]


class RuleCheckLoadTests(unittest.TestCase):
    """The early-warning rule checks: read through the function the page's route uses, and never assumed."""

    def test_they_are_read_for_the_lot_and_day_asked_about(self):
        with site_parts(bbl=OTHER_BBL) as load:
            context = app_context(OTHER_BBL, None, None, "2026-06-01")
        self.assertEqual(load.find_rule_checks.call_args.args, RULE_CHECKS_SOURCE)
        self.assertEqual(load.rule_checks.call_args, mock.call(OTHER_BBL, as_of=date(2026, 6, 1)))
        self.assertEqual((context.warning_checks.status, context.sample), ("ok", False))
        self.assertEqual([check["status"] for check in context.warning_checks.value], ["ok", "ok", "ok", "not_applicable"])
        with site_parts(bbl=OTHER_BBL) as load:
            app_context(OTHER_BBL, None, None, None)
        self.assertEqual(load.rule_checks.call_args, mock.call(OTHER_BBL, as_of=None))

    def test_the_name_resolves_to_the_function_behind_the_page_route(self):
        from early_warning import api as early_warning_api

        from api.routers.router_data import owner_function
        self.assertIs(owner_function(*RULE_CHECKS_SOURCE), early_warning_api.site_warning_checks)
        served = [route.path for route in early_warning_api.router.routes if route.endpoint is early_warning_api.site_warning_checks]
        self.assertEqual(served, ["/api/sites/{bbl}/warnings/checks"])

    def test_a_rule_that_could_not_run_turns_the_count_into_a_floor(self):
        with site_parts(bbl=OTHER_BBL, checks=one_rule_failed):
            answer = ask("Any early warnings?", OTHER_BBL)
        counted = [part.text for part in answer.parts if part.kind == "warning" and part.text.startswith("At least")]
        self.assertEqual(len(counted), 1)
        self.assertIn("1 early-warning rule was not checked", counted[0])
        with site_parts(bbl=OTHER_BBL):
            self.assertNotIn("At least", ask("Any early warnings?", OTHER_BBL).plain_text)

    def test_checks_that_fail_to_load_are_a_failure_and_the_count_is_still_a_floor(self):
        def refused(bbl, as_of):
            raise HTTPException(503, "Couldn't load the public record for this lot")

        def broke(bbl, as_of):
            raise RuntimeError("boom")

        def off_contract(bbl, as_of):
            return [{"rule_id": "r1", "status": "fine"}]
        for failing, reason in ((refused, "early_warning.api.site_warning_checks: Couldn't load the public record for this lot"),
                                (broke, "early_warning.api.site_warning_checks could not answer (RuntimeError)"),
                                (off_contract, "early_warning.api.site_warning_checks could not answer (ValidationError)")):
            with site_parts(bbl=OTHER_BBL, checks=failing):
                context = app_context(OTHER_BBL, None, None, None)
                self.assertEqual((context.warning_checks.status, context.warning_checks.reason, context.warnings.status),
                                 ("error", reason, "ok"))
                self.assertIn("The checks on whether each early-warning rule ran could not be loaded, so this is a floor",
                              ask("Any early warnings?", OTHER_BBL).plain_text)
        with site_parts(bbl=OTHER_BBL), mock.patch.object(chat_app_context, "owner_function", side_effect=DataUnavailable("early_warning.api could not be imported")):
            self.assertEqual(app_context(OTHER_BBL, None, None, None).warning_checks.reason, "early_warning.api could not be imported")

    def test_while_the_function_has_not_landed_the_sample_is_the_sample_sites_only(self):
        with site_parts(checks=None):
            context = app_context(SAMPLE_BBL, None, None, None)
        self.assertEqual((context.warning_checks.status, len(context.warning_checks.value), context.sample), ("ok", 4, True))
        with site_parts(checks=None, bbl=OTHER_BBL):
            context = app_context(OTHER_BBL, None, None, None)
        self.assertEqual((context.warning_checks.status, context.warning_checks.reason, context.sample),
                         ("not_available", SAMPLE_OF_ANOTHER_SITE, False))

    def test_they_are_not_read_when_the_warnings_did_not_load(self):
        with site_parts(failing=("warnings",), bbl=OTHER_BBL) as load:
            context = app_context(OTHER_BBL, None, None, None)
        self.assertEqual((context.warning_checks.status, load.rule_checks.called), ("not_available", False))


class FixtureContextTests(unittest.TestCase):
    """The sample-site loader the saved answers are built from."""

    def test_it_describes_the_sample_site_only_and_says_it_is_sample(self):
        context = fixture_context(SAMPLE_BBL, None, None, None)
        self.assertEqual((context.sample, context.profile.status, context.records), (True, "ok", []))
        with self.assertRaises(SiteContextUnavailable):
            fixture_context(OTHER_BBL, None, None, None)


class AppRouteSampleLabelTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api.main import app
        self.client = TestClient(app)
        patch = mock.patch.dict(os.environ, {"FORESITE_CHAT_LIVE": "0"})
        patch.start()
        self.addCleanup(patch.stop)

    def post(self, bbl):
        return self.client.post("/api/chat", json={"question": "Any early warnings?", "bbl": bbl})

    def test_the_sample_header_follows_the_data_the_answer_rests_on(self):
        with site_parts(sample=("profile", "similar", "warnings", "actions")):
            self.assertEqual(self.post(SAMPLE_BBL).headers.get("X-ForeSite-Fixture"), "true")
        with site_parts(bbl=OTHER_BBL):
            real = self.post(OTHER_BBL)
        self.assertEqual((real.status_code, real.headers.get("X-ForeSite-Fixture")), (200, None))
        self.assertEqual(self.post("9000000000").status_code, 422)


if __name__ == "__main__":
    unittest.main()
