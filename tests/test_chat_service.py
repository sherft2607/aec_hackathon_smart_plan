"""Offline tests for one question end to end: live with a scripted model, the mock, the model's tools, the route."""

import os
import unittest
from unittest import mock

from pydantic import ValidationError

from api import contracts
from api.routers.chat import chat_service, chat_tools
from api.routers.chat.chat_contract_map import from_contract, to_contract
from api.routers.chat.chat_model_call import AnthropicChatModel
from api.routers.chat.chat_models import ChatRequest
from api.routers.chat.chat_site_context import Loaded, SiteContextUnavailable
from api.routers.chat.chat_site_view import SiteView
from tests.chat_test_support import (
    JULY_COMPLAINT, JUNE_1, LATE_CASE, MARCH_WARNING, OLD_CASE, SAFEGUARD, SITE_BBL, STOP_WORK, SURVEY_ACTION, WEB,
    FakeAnthropicClient, ScriptedModel, action, example_context, item, loader, response, says, submit_block, tool_call,
)

GOOD = says("A stop work order was issued on 2026-04-20.", STOP_WORK)
UNSOURCED = says("Everything looks fine here.")


def ask(question="What is on file?", model=None, load=None, **fields):
    return chat_service.answer(ChatRequest(bbl=SITE_BBL, question=question, **fields), load or loader(), model)


def kinds(answer):
    return [part.code if part.kind == "notice" else part.kind for part in answer.parts]


class LiveTests(unittest.TestCase):
    def test_a_sourced_answer_is_shown_with_its_kinds_and_actions(self):
        model = ScriptedModel({"items": [GOOD, says("A past case resembles this site.", OLD_CASE)],
                               "actions": [action("fly_to", ref=OLD_CASE)]})
        answer = ask(model=model)
        self.assertEqual((answer.mode, answer.web_search), ("live", "not_used"))
        self.assertEqual(kinds(answer), ["record", "case", "not_a_prediction", "page_action"])
        self.assertEqual([a.type for a in answer.actions], ["fly_to"])
        self.assertTrue(answer.plain_text.startswith("From the public record: A stop work order"))
        self.assertIn("From the case library, as publicly reported: ", answer.plain_text)

    def test_the_model_reads_the_site_data_and_gets_both_search_tools(self):
        model = ScriptedModel([GOOD])
        ask("Which filings cover earth work?", model=model, history=[{"question": "Hi", "answer": "Hello."}])
        opened = model.opened_with
        self.assertIn(f"[{STOP_WORK}]", opened["system"][1]["text"])
        self.assertEqual(opened["system"][1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual([m["content"] for m in opened["messages"]], ["Hi", "Hello.", "Which filings cover earth work?"])
        self.assertEqual([t.schema["name"] for t in opened["client_tools"]], ["search_records", "search_similar_cases"])
        self.assertTrue(opened["allow_web"])

    def test_one_correction_round_then_what_still_fails_is_dropped_and_said(self):
        fixed = ScriptedModel([GOOD, UNSOURCED], [GOOD])
        self.assertEqual(kinds(ask(model=fixed)), ["record"])
        self.assertIn("no source", fixed.problems_seen[1][0])
        still = ScriptedModel([GOOD, UNSOURCED], [GOOD, UNSOURCED])
        self.assertEqual(kinds(ask(model=still)), ["record", "held_back"])
        self.assertEqual(kinds(ask(model=ScriptedModel([UNSOURCED], [UNSOURCED]))), ["held_back", "no_answer"])

    def test_a_dropped_action_is_said_and_an_action_alone_is_an_answer(self):
        bad = {"items": [GOOD], "actions": [action("toggle_layer", layer_id="made_up")]}
        self.assertEqual(kinds(ask(model=ScriptedModel(bad, bad))), ["record", "action_dropped"])
        only = ScriptedModel({"items": [], "actions": [action("toggle_layer", layer_id="sandy_inundation")]})
        answer = ask("Show the Sandy layer", model=only)
        self.assertEqual((kinds(answer), len(answer.actions)), (["page_action"], 1))

    def test_a_replay_has_no_web_search_and_no_later_material(self):
        model = ScriptedModel([says("A complaint is on file.", JULY_COMPLAINT), says("A later case.", LATE_CASE), GOOD],
                              [GOOD])
        answer = ask(model=model, as_of=JUNE_1)
        self.assertFalse(model.opened_with["allow_web"])
        self.assertEqual((answer.as_of, answer.web_search, kinds(answer)), (JUNE_1, "off_as_of", ["record", "web_off_as_of"]))
        for later in ("C301", "ex-wall-2026", "2026-07-02", "Permit issued"):
            self.assertNotIn(later, model.opened_with["system"][1]["text"] + answer.model_dump_json())

    def test_a_web_statement_is_a_lead_and_never_a_record(self):
        model = ScriptedModel([says("The city publishes the 2022 construction codes.", WEB.url)], web_results=[WEB], searched=True)
        answer = ask(model=model)
        self.assertEqual((kinds(answer), answer.web_search), (["lead"], "used"))
        self.assertTrue(answer.plain_text.startswith("From the web, not checked by us: "))

    def test_questions_asking_for_a_verdict_a_forecast_or_a_name_get_the_notice(self):
        self.assertEqual(kinds(ask("Is it safe to dig here?", model=ScriptedModel([GOOD])))[0], "not_a_determination")
        self.assertEqual(kinds(ask("Will this building collapse?", model=ScriptedModel([GOOD])))[0], "not_a_prediction")
        self.assertEqual(kinds(ask("Who is the contractor?", model=ScriptedModel([GOOD])))[0], "names_withheld")

    def test_a_failed_live_call_falls_back_to_a_labeled_mock(self):
        answer = ask("Search the records for fence", model=ScriptedModel(fails=RuntimeError("boom")))
        self.assertEqual((answer.mode, kinds(answer)[:2]), ("mock", ["live_failed", "mock_answer"]))
        self.assertNotIn("boom", answer.model_dump_json())

    def test_an_unknown_site_and_a_saved_example_are_refused(self):
        def missing(*_):
            raise SiteContextUnavailable("no such lot")
        with self.assertRaises(SiteContextUnavailable):
            ask(load=missing)
        with self.assertRaises(LookupError):
            ask(question="", example_id="x")


class FirstAnswerTests(unittest.TestCase):
    """The quick first answer the page shows while the full one is still at work."""

    def first(self, model, question="What is on file?", **fields):
        return chat_service.first_answer(ChatRequest(bbl=SITE_BBL, question=question, **fields), loader(), model)

    def test_a_first_answer_is_labeled_checked_and_takes_no_page_action(self):
        model = ScriptedModel({"items": [GOOD, UNSOURCED], "actions": [action("fly_to", ref=OLD_CASE)]})
        answer = self.first(model)
        self.assertEqual(kinds(answer), ["first_pass", "record"])  # the unsourced line is dropped, as in a full answer
        self.assertEqual((answer.mode, answer.actions, answer.web_search), ("live", [], "not_used"))
        self.assertIn("THE FIRST ANSWER, BEFORE THE FULL ONE", model.first_opened_with["system"][-1]["text"])
        self.assertIn(f"[{STOP_WORK}]", model.first_opened_with["system"][1]["text"])
        self.assertIsNone(model.opened_with)  # never the full call, with its searches

    def test_a_gap_is_dropped_because_this_pass_searched_nothing(self):
        answer = self.first(ScriptedModel([GOOD, item("gap", text="the soil report")]))
        self.assertEqual(kinds(answer), ["first_pass", "record"])

    def test_nothing_is_shown_without_a_sourced_part(self):
        self.assertIsNone(self.first(None))
        self.assertIsNone(self.first(ScriptedModel(fails=RuntimeError("slow"))))
        for items in ([item("gap", text="the soil report")], [UNSOURCED], [item("notice", notice="out_of_scope")]):
            self.assertIsNone(self.first(ScriptedModel(items)), items)
        self.assertIsNone(self.first(ScriptedModel("not a tool input")))

    def test_a_question_asking_for_a_verdict_still_gets_the_notice(self):
        self.assertEqual(kinds(self.first(ScriptedModel([GOOD]), "Is this site safe?")), ["first_pass", "not_a_determination", "record"])

    def test_a_replay_first_answer_holds_back_later_material(self):
        late = says("A party-wall crack was reported on 2026-07-02.", JULY_COMPLAINT)
        answer = self.first(ScriptedModel([GOOD, late]), as_of=JUNE_1)
        self.assertEqual((kinds(answer), answer.web_search), (["first_pass", "record"], "off_as_of"))

    def test_one_correction_round_only_when_nothing_got_through(self):
        fixed = ScriptedModel([UNSOURCED], [GOOD])
        self.assertEqual(kinds(self.first(fixed)), ["first_pass", "record"])
        self.assertIn("no source", fixed.problems_seen[1][0])
        partly = ScriptedModel([GOOD, UNSOURCED], [GOOD])  # something got through: shown at once, no second request
        self.assertEqual(kinds(self.first(partly)), ["first_pass", "record"])
        self.assertEqual(len(partly.proposals), 1)
        self.assertIsNone(self.first(ScriptedModel([UNSOURCED], [UNSOURCED])))

    def test_the_fast_call_is_one_request_with_only_the_answer_tool(self):
        client = FakeAnthropicClient(response([submit_block([GOOD])]))
        self.assertEqual(kinds(self.first(AnthropicChatModel(client))), ["first_pass", "record"])
        (sent,) = client.requests
        self.assertEqual((sent["model"], sent["tool_choice"]), ("claude-haiku-5-5", {"type": "tool", "name": "submit_answer"}))
        self.assertEqual([tool["name"] for tool in sent["tools"]], ["submit_answer"])
        self.assertFalse({"betas", "fallbacks"} & set(sent))  # fallback models are not offered for this one
        self.assertLessEqual(sent["timeout"], 20)

    def test_the_fast_call_is_sent_back_once_with_the_reasons_and_never_a_third_time(self):
        client = FakeAnthropicClient(response([submit_block([UNSOURCED])]), response([submit_block([GOOD], call_id="submit_2")]))
        self.assertEqual(kinds(self.first(AnthropicChatModel(client))), ["first_pass", "record"])
        self.assertEqual(len(client.requests), 2)
        report = client.requests[1]["messages"][-1]["content"][0]
        self.assertEqual((report["type"], report["is_error"]), ("tool_result", True))
        twice = FakeAnthropicClient(response([submit_block([UNSOURCED])]), response([submit_block([UNSOURCED], call_id="submit_2")]),
                                    response([submit_block([GOOD], call_id="submit_3")]))
        self.assertIsNone(self.first(AnthropicChatModel(twice)))
        self.assertEqual(len(twice.requests), 2)

    def test_a_fast_call_that_submits_nothing_is_not_asked_again(self):
        from types import SimpleNamespace
        client = FakeAnthropicClient(response([SimpleNamespace(type="text", text="One moment.")], stop_reason="end_turn"),
                                     response([submit_block([GOOD])]))
        self.assertIsNone(self.first(AnthropicChatModel(client)))
        self.assertEqual(len(client.requests), 1)


class MockTests(unittest.TestCase):
    def body(self, question, **fields):
        answer = ask(question, **fields)
        self.assertEqual((answer.mode, answer.parts[0].code, answer.web_search, answer.usage), ("mock", "mock_answer", "off", None))
        return answer, kinds(answer)[1:]

    def test_searches_counts_warnings_and_action_items_come_from_the_site_data(self):
        self.assertEqual(self.body("Search the records for fence")[1], ["record", "unknown"])
        self.assertEqual(self.body("How many ECB violations are there?")[1], ["record"])
        self.assertEqual(self.body("Any similar cases with underpinning?")[1], ["case", "not_a_prediction"])
        self.assertEqual(self.body("What warnings are there?")[1], ["warning", "warning", "not_a_prediction"])
        answer, got = self.body("What are the action items for the structural engineer?")
        self.assertEqual((got, answer.parts[1].sources[0].ref), (["action"], SURVEY_ACTION))

    def test_life_safety_action_items_come_first(self):
        answer, _ = self.body("What should we do next?")
        self.assertEqual([p.sources[0].life_safety for p in answer.parts[1:]], [True, False])
        answer, got = self.body("What should the structural engineer do first?")
        self.assertEqual((got, [p.sources[0].discipline for p in answer.parts[1:]]), (["action"], ["structural"]))

    def test_page_actions_are_matched_and_checked(self):
        answer, got = self.body("Show the Sandy layer")
        self.assertEqual((got, [(a.type, a.layer_id, a.on) for a in answer.actions]), (["page_action"], [("toggle_layer", "sandy_inundation", True)]))
        answer, _ = self.body("hide the sandy layer")
        self.assertFalse(answer.actions[0].on)
        # By the hazard a layer shows when no layer is named, and never on a small word such as "to".
        self.assertEqual([a.layer_id for a in self.body("Show the flood layer and fly to the site")[0].actions], ["sandy_inundation"])
        self.assertEqual([a.layer_id for a in self.body("Show the structural complaints")[0].actions], ["dob_complaints_structural"])
        watchlist = loader(layers=Loaded.ok([{"layer_id": "watchlist", "name": "Excavation next to older attached buildings", "hazard": "structural"}]))
        self.assertEqual(self.body("Show me the way to the door", load=watchlist)[0].actions, [])
        self.assertEqual([a.layer_id for a in self.body("Show the excavation layer", load=watchlist)[0].actions], ["watchlist"])
        answer, _ = self.body("Fly to case ex-underpinning-2019")
        self.assertEqual(answer.actions[0].ref, OLD_CASE)
        answer, got = self.body("Pin that", project_id="p1", history=[{"question": "q", "answer": "a"}])
        self.assertEqual((got, answer.actions[0].target), (["page_action"], "previous"))
        self.assertEqual(self.body("Pin that", history=[{"question": "q", "answer": "a"}])[1], ["pin_needs_project"])
        self.assertEqual(self.body("Pin that", project_id="p1")[1], ["pin_needs_answer"])

    def test_nothing_is_made_up_when_no_keyword_matches_or_a_piece_did_not_load(self):
        self.assertEqual(self.body("What's the weather like?")[1], ["mock_no_match"])
        self.assertEqual(self.body("Any similar cases?", load=loader(similar=Loaded.failed("timeout")))[1], ["unknown"])

    def test_warnings_or_action_items_that_did_not_load_are_unknown_never_none(self):
        for question, piece in (("Any early warnings?", "warnings"), ("What are the action items?", "actions")):
            answer, got = self.body(question, load=loader(**{piece: Loaded.failed("timeout")}))
            self.assertEqual(got, ["unknown"], question)
            self.assertIn("This is not the same as none", answer.parts[1].text)
            self.assertEqual(self.body(question, load=loader(**{piece: Loaded.ok([])}))[1], ["not_found"], question)
        # The list loaded, with nothing for the discipline asked about: that is a plain not found.
        self.assertEqual(self.body("What are the geotech action items?")[1], ["not_found"])

    def test_a_rule_that_could_not_run_is_said_with_the_warnings(self):
        checks = Loaded.ok([{"rule_id": "r2", "title": "Heavy rain on an open excavation", "status": "error"}])
        answer, got = self.body("What warnings are there?", load=loader(warning_checks=checks))
        self.assertEqual(got, ["warning", "warning", "warning", "not_a_prediction"])
        self.assertTrue(answer.parts[3].text.startswith("At least 2 "))
        self.assertEqual(self.body("What warnings are there?", load=loader(warning_checks=checks, warnings=Loaded.ok([])))[1], ["unknown"])

    def test_a_replay_mock_stays_before_the_day(self):
        answer, got = self.body("What warnings are there?", as_of=JUNE_1)
        self.assertEqual(got, ["warning", "not_a_prediction"])
        self.assertEqual(answer.parts[1].sources[0].ref, MARCH_WARNING)
        self.assertNotIn("C301", ask("search the records for party wall", as_of=JUNE_1).model_dump_json())


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.records, self.cases = chat_tools.tools_for(SiteView(example_context()))

    def test_the_tools_return_ids_the_model_can_cite(self):
        view = SiteView(example_context())
        text = self.records.run({"text": "safeguard", "bbl": "", "dataset_key": "", "date_from": "", "date_to": ""})
        self.assertIn(f"[{SAFEGUARD}]", text)
        self.assertIn("NOT SEARCHED", text)  # the attached lot's violations query failed
        cases = self.cases.run({"text": "", "hazard": "structural", "severity_min": "2"})
        ids = [line[1:line.index("]")] for line in cases.splitlines() if line.startswith("[")]
        self.assertEqual(ids, [LATE_CASE, OLD_CASE])
        self.assertTrue(all(ref in view.items for ref in ids))

    def test_a_tool_says_not_loaded_or_not_run_and_never_raises_on_bad_input(self):
        _, cases = chat_tools.tools_for(SiteView(example_context(similar=Loaded.failed("timeout"))))
        self.assertTrue(cases.run({"text": "", "hazard": "", "severity_min": ""}).startswith("NOT LOADED"))
        self.assertTrue(self.cases.run({"hazard": "earthquake"}).startswith("The search was not run"))
        self.assertTrue(self.records.run({"text": None, "bbl": "nope"}).startswith("The search was not run"))

    def test_a_replay_tool_never_shows_later_material(self):
        records, cases = chat_tools.tools_for(SiteView(example_context(as_of=JUNE_1)))
        self.assertNotIn("C301", records.run({"text": "", "bbl": "", "dataset_key": "dob_complaints", "date_from": "", "date_to": ""}))
        self.assertNotIn("ex-wall-2026", cases.run({"text": "", "hazard": "", "severity_min": ""}))

    def test_the_model_call_runs_a_tool_returns_its_result_and_takes_the_answer_with_actions(self):
        view = SiteView(example_context())
        client = FakeAnthropicClient(
            response([tool_call("search_similar_cases", "c1", text="", hazard="structural", severity_min="")]),
            response([submit_block([says("A past case resembles this site.", OLD_CASE)], [action("fly_to", ref=OLD_CASE)])]))
        chat = AnthropicChatModel(client).open([], [{"role": "user", "content": "q"}], False, tuple(chat_tools.tools_for(view)))
        turn = chat.turn()
        self.assertEqual(turn.proposal["actions"][0]["ref"], OLD_CASE)
        first, second = client.requests
        self.assertEqual([t["name"] for t in first["tools"]], ["search_records", "search_similar_cases", "submit_answer"])
        self.assertTrue(all(t["strict"] for t in first["tools"]))
        [result] = second["messages"][-1]["content"]
        self.assertEqual((result["type"], result["tool_use_id"]), ("tool_result", "c1"))
        self.assertIn(f"[{OLD_CASE}]", result["content"])


class ContractTests(unittest.TestCase):
    def test_every_part_kind_maps_to_the_contract_with_its_source(self):
        view_answer = ask(model=ScriptedModel({"items": [
            GOOD, says("A past case resembles this site.", OLD_CASE), says("A rule found a pattern.", MARCH_WARNING),
            says("A survey is listed for the structural engineer.", SURVEY_ACTION), item("record_search", text="zebra", bbl=SITE_BBL),
            item("dataset_check", bbl="3000010002", dataset_key="dob_violations")],
            "actions": [action("fly_to", ref=OLD_CASE), action("toggle_layer", layer_id="sandy_inundation"), action("pin_answer", ref="this")]}),
            project_id="p1")
        sent = to_contract(view_answer)
        contracts.ChatResponse.model_validate(sent.model_dump())
        self.assertEqual([p.kind for p in sent.answer_parts],
                         ["public_record", "case", "warning", "action", "not_found", "unknown", "notice", "notice", "notice", "notice"])
        record, case, warning, act = sent.answer_parts[:4]
        self.assertEqual((record.record_id, record.source_name, record.source_url),
                         (STOP_WORK, "DOB violations V100", "https://data.example.org/dob_violations?bbl=3000010001"))
        self.assertEqual((case.record_id, case.source_url), ("ex-underpinning-2019", "https://example.org/report"))
        self.assertIn("as publicly reported: City incident report", case.source_name)
        self.assertEqual((warning.record_id, act.record_id, act.source_name), ("w1", "a1", "BC 3309.4.3"))
        self.assertFalse(sent.offline)
        self.assertEqual([a.type for a in sent.actions], ["fly_to", "toggle_layer", "pin"])
        self.assertEqual(sent.actions[0].payload["bbl"], "3000020001")
        self.assertEqual(sent.actions[2].payload, {"kind": "chat_answer", "project_id": "p1", "target": "this", "title": "What is on file?"})

    def test_a_mock_answer_is_offline_and_a_web_part_keeps_its_link(self):
        self.assertTrue(to_contract(ask("What warnings are there?")).offline)
        web = to_contract(ask(model=ScriptedModel([says("The city publishes its codes.", WEB.url)], web_results=[WEB], searched=True)))
        self.assertEqual((web.answer_parts[0].kind, web.answer_parts[0].source_url), ("web", WEB.url))

    def test_a_contract_request_over_a_cap_or_without_a_site_is_refused(self):
        ok = from_contract(contracts.ChatRequest(question="x", bbl=SITE_BBL, as_of=JUNE_1, history=[{"question": "q", "answer": "a"}]))
        self.assertEqual((ok.bbl, ok.as_of.isoformat(), len(ok.history)), (SITE_BBL, JUNE_1, 1))
        for bad in ({"question": "x"}, {"question": "x" * 1001, "bbl": SITE_BBL}, {"question": "x", "bbl": "12"},
                    {"question": "x", "bbl": SITE_BBL, "as_of": "June"}, {"question": " ", "bbl": SITE_BBL},
                    {"question": "x", "bbl": SITE_BBL, "history": [{"question": "q", "answer": "a"}] * 9}):
            with self.assertRaises(ValidationError, msg=bad):
                from_contract(contracts.ChatRequest(**bad))


class AppRouteTests(unittest.TestCase):
    """POST /api/chat on the real app, which reads the sample site from contracts/fixtures/ until the site routes are real."""

    FIXTURE_BBL = "3052110074"

    def setUp(self):
        from fastapi.testclient import TestClient
        from api.main import app
        patcher = mock.patch.dict(os.environ, {"FORESITE_CHAT_LIVE": "0"})
        patcher.start()
        self.addCleanup(patcher.stop)
        # Every site part from its fixture, as if no owner module had landed, so the answers below stay fixed.
        owners = mock.patch("api.routers.sites_router.owner_function", return_value=None)
        owners.start()
        self.addCleanup(owners.stop)
        self.client = TestClient(app)

    def post(self, question, **more):
        return self.client.post("/api/chat", json={"question": question, "bbl": self.FIXTURE_BBL, **more})

    def kinds(self, reply):
        return [part.kind for part in contracts.ChatResponse.model_validate(reply.json()).answer_parts]

    def test_the_chat_route_is_ours_and_marks_fixture_data(self):
        reply = self.post("What warnings are there?")
        self.assertEqual((reply.status_code, reply.headers["X-ForeSite-Fixture"], reply.json()["offline"]), (200, "true", True))
        served = self.client.get(f"/api/sites/{self.FIXTURE_BBL}/warnings").json()
        self.assertEqual(self.kinds(reply), ["notice", *["warning"] * len(served), "notice"])
        self.assertFalse(self.client.get("/api/chat/setup").json()["live"])

    def test_similar_cases_actions_and_page_actions_come_from_the_fixtures(self):
        self.assertIn("case", self.kinds(self.post("Any similar cases?")))
        self.assertIn("action", self.kinds(self.post("What are the action items?")))
        reply = self.post("Fly to the site")
        self.assertEqual([a["type"] for a in reply.json()["actions"]], ["fly_to"])
        self.assertEqual(reply.json()["actions"][0]["payload"]["bbl"], self.FIXTURE_BBL)

    def test_a_count_is_the_sources_own_and_a_failed_dataset_is_unknown(self):
        ecb = self.post("How many ECB violations are there?")
        self.assertEqual(self.kinds(ecb)[1], "public_record")
        self.assertTrue(ecb.json()["answer_parts"][1]["text"].startswith("3 records in "))
        self.assertEqual(self.kinds(self.post("How many 311 requests are there?"))[1], "unknown")
        self.assertEqual(self.kinds(self.post("How many ECB violations are there?", as_of="2026-06-01"))[1], "unknown")

    def test_a_search_over_records_that_were_not_loaded_is_unknown_never_none_found(self):
        self.assertEqual(self.kinds(self.post("Search the records for fence"))[1:], ["unknown"])

    def test_the_first_answer_route_answers_only_with_a_live_model_and_never_refuses(self):
        from api.routers.chat import chat_model_call
        body = {"question": "How many ECB violations are there?", "bbl": self.FIXTURE_BBL}
        nothing = {"answer_parts": [], "actions": [], "offline": False}
        self.assertEqual(self.client.post("/api/chat/first", json=body).json(), nothing)  # no live model
        counted = lambda: ScriptedModel([item("dataset_check", bbl=self.FIXTURE_BBL, dataset_key="ecb_violations")])
        with mock.patch.object(chat_model_call, "default_model", side_effect=counted):
            reply = self.client.post("/api/chat/first", json=body)
            self.assertEqual((self.kinds(reply), reply.headers["X-ForeSite-Fixture"]), (["notice", "public_record"], "true"))
            self.assertIn("first answer", reply.json()["answer_parts"][0]["text"])
            self.assertEqual(reply.json()["actions"], [])
            for refused_by_the_full_route in ({"question": "x"}, {**body, "bbl": "3999999999"}, {**body, "question": "x" * 1001}):
                self.assertEqual(self.client.post("/api/chat/first", json=refused_by_the_full_route).json(), nothing)
            with mock.patch.dict(os.environ, {"FORESITE_CHAT_FIRST": "0"}):
                self.assertEqual(self.client.post("/api/chat/first", json=body).json(), nothing)

    def test_no_site_another_site_and_an_oversized_question(self):
        none = self.client.post("/api/chat", json={"question": "hello"})
        self.assertEqual((none.status_code, self.kinds(none)), (200, ["notice"]))
        self.assertEqual(self.client.post("/api/chat", json={"question": "x", "bbl": "3999999999"}).status_code, 404)
        self.assertEqual(self.post("x" * 1001).status_code, 422)
        self.assertEqual(self.client.post("/api/chat", json={"question": "x", "surprise": 1}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
