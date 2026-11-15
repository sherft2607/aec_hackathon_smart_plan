"""Pre-filing items from plan-exam objections on similar DOB NOW filings (actions/filing_objections.py)."""

import re
import unittest
from unittest import mock

from pydantic import TypeAdapter

from actions import filing_objections as fo
from actions.build import build_actions
from api.contracts import ActionItem

OWNERS = {"architect": "architect", "structural": "structural_engineer"}
SITE = "3000000001"
EARTH_AND_FOUNDATION = 0b0011  # bit order: earth_work, foundation, structural, demolition


def held(count, bbl="3999999999", start=0):
    return [[f"B{start + i:08d}-I1", bbl, "2025-06"] for i in range(count)]


def pool(groups):
    return {"source": {"name": "DOB NOW: Build job application filings", "dataset": "w9ak-ipjd",
                       "url": "https://data.cityofnewyork.us/d/w9ak-ipjd", "pulled": "2026-11-15", "filter": "test"},
            "scope_bits": ["earth_work", "foundation", "structural", "demolition"],
            "filings": sum(g["n"] for g in groups), "groups": groups}


def group(job_type, scopes, storeys, n, held_rows):
    return {"job_type": job_type, "scopes": scopes, "storeys": storeys, "n": n, "held": held_rows}


def profile(**over):
    base = {"bbl": SITE, "job_type": "new_building", "work_types": ["excavation", "foundation"],
            "proposed_storeys": 6, "neighbors": [], "signals": []}
    return {**base, **over}


# Six-storey new buildings that dig are held at 40%; tall ones at 5%, so citywide it is about 7%.
ELEVATED = pool([
    group("New Building", EARTH_AND_FOUNDATION, 6, 50, held(20)),
    group("New Building", EARTH_AND_FOUNDATION, 30, 1000, held(50, start=100)),
    group("Alteration", EARTH_AND_FOUNDATION, 6, 500, held(400, start=2000)),
])


class TestObjectionItems(unittest.TestCase):
    def items(self, prof=None, stage=None, data=ELEVATED):
        return fo.objection_actions(prof or profile(), stage, OWNERS, pool=data)

    def test_a_scope_held_more_than_usual_becomes_a_pre_filing_item_per_scope(self):
        items = {i["id"]: i for i in self.items()}
        self.assertEqual(set(items), {"action-objections-earth_work", "action-objections-foundation"})
        earth = items["action-objections-earth_work"]
        self.assertEqual((earth["discipline"], earth["hazard"], earth["status"], earth["life_safety"]),
                         ("geotech", "geotech", "open", False))
        self.assertEqual(items["action-objections-foundation"]["discipline"], "structural")
        self.assertEqual(earth["phase"], "filing")
        self.assertIn("20 of the 50", earth["why"])
        TypeAdapter(list[ActionItem]).validate_python(list(items.values()))

    def test_the_wording_is_a_pattern_with_its_source_never_a_prediction(self):
        for item in self.items():
            text = f"{item['title']} {item['why']} {item['proof_needed']}"
            self.assertIn("not a prediction for this one", item["why"])
            self.assertIn("not what they were about", item["why"])
            self.assertIn("still held", item["why"])
            self.assertIn("w9ak-ipjd", item["why"])
            self.assertIn("pulled 2026-11-15", item["why"])
            self.assertNotRegex(text, re.compile(r"\bwill (object|be objected|reject)", re.I))

    def test_nothing_is_raised_when_similar_filings_are_held_no_more_than_usual(self):
        usual = pool([group("New Building", EARTH_AND_FOUNDATION, 6, 50, held(3)),
                      group("New Building", EARTH_AND_FOUNDATION, 30, 1000, held(200, start=100))])
        self.assertEqual(self.items(data=usual), [])

    def test_only_the_same_job_type_is_compared(self):
        # The alterations are held at 80%, but a new building is never compared with them.
        for item in self.items():
            self.assertNotIn("B00002", item["proof_needed"])

    def test_half_a_point_over_thousands_of_filings_is_not_more_than_usual(self):
        marginal = pool([group("New Building", EARTH_AND_FOUNDATION, 6, 4000, held(680)),
                         group("New Building", EARTH_AND_FOUNDATION, 30, 600, held(71, start=5000))])
        self.assertEqual(self.items(data=marginal), [])

    def test_a_gap_a_small_group_makes_by_chance_is_not_more_than_usual(self):
        # 9 of 40 is 22.5% against about 15.6%: a lift, but 40 filings make that gap by chance about 1 in 7.
        chance = pool([group("New Building", EARTH_AND_FOUNDATION, 6, 40, held(9)),
                       group("New Building", EARTH_AND_FOUNDATION, 30, 2000, held(312, start=100))])
        self.assertEqual(self.items(data=chance), [])

    def test_the_chance_is_an_exact_binomial_tail(self):
        self.assertAlmostEqual(fo.chance_of_at_least(1, 1, 0.5), 0.5)
        self.assertAlmostEqual(fo.chance_of_at_least(2, 2, 0.5), 0.25)
        self.assertAlmostEqual(fo.chance_of_at_least(1, 2, 0.5), 0.75)
        self.assertLess(fo.chance_of_at_least(46, 184, 0.156), 0.01)  # 2625 Bedford

    def test_too_few_held_is_not_a_pattern(self):
        few = pool([group("New Building", EARTH_AND_FOUNDATION, 6, 50, held(2)),
                    group("New Building", EARTH_AND_FOUNDATION, 30, 1000, held(5, start=100))])
        self.assertEqual(self.items(data=few), [])

    def test_the_lots_own_filings_are_not_similar_projects(self):
        own = pool([group("New Building", EARTH_AND_FOUNDATION, 6, 50, held(17) + held(3, bbl=SITE, start=500)),
                    group("New Building", EARTH_AND_FOUNDATION, 30, 1000, held(50, start=100))])
        item = next(i for i in self.items(data=own) if i["id"] == "action-objections-earth_work")
        self.assertIn("17 of the 47", item["why"])
        self.assertNotIn("B00000500", item["proof_needed"])

    def test_items_belong_to_design_and_pre_filing_only(self):
        self.assertTrue(self.items(stage="pre_filing"))
        self.assertTrue(self.items(stage="design"))
        self.assertEqual(self.items(stage="construction"), [])
        self.assertEqual(self.items(stage="pre_acquisition"), [])

    def test_a_missing_pool_is_said_never_silent(self):
        with mock.patch.object(fo, "load_pool", side_effect=fo.PoolUnavailable("gone")):
            items = fo.objection_actions(profile(), None, OWNERS)
        self.assertEqual([i["id"] for i in items], ["action-objections-unresolved"])
        self.assertIn("Couldn't load", items[0]["why"])

    def test_an_unset_job_type_or_scope_is_said_never_silent(self):
        for prof, words in ((profile(job_type=None), "job type is not set"),
                            (profile(work_types=None), "work types are not set")):
            items = self.items(prof)
            self.assertEqual([i["id"] for i in items], ["action-objections-unresolved"])
            self.assertIn(words, items[0]["why"])

    def test_support_of_excavation_is_compared_through_earth_work(self):
        # DOB NOW's support-of-excavation column reads "No" on every filing, so it cannot be its own scope.
        items = self.items(profile(work_types=["support_of_excavation"]))
        self.assertEqual([i["id"] for i in items], ["action-objections-earth_work"])


class TestShippedPool(unittest.TestCase):
    def test_the_pool_loads_and_stores_no_names(self):
        data = fo.load_pool()
        self.assertEqual(set(data), {"source", "scope_bits", "filings", "groups"})
        self.assertEqual({k for g in data["groups"] for k in g}, {"job_type", "scopes", "storeys", "n", "held"})
        for g in data["groups"]:
            for row in g["held"]:
                self.assertEqual(len(row), 3)
                self.assertRegex(row[0], r"^[A-Z]\d{8}-I1$")

    def test_build_actions_carries_the_objection_items(self):
        items = build_actions(profile(bbl="3052110074"), "pre_filing")
        self.assertTrue(any(i["source_rule"].startswith("actions:objections:") for i in items))


if __name__ == "__main__":
    unittest.main()
