"""Build the action list for a site, grouped by discipline.

Two sources feed it:
  * the BC 3309 / Chapter 17 duties already encoded in `checklist/checklist_rules.py`, mapped
    from that module's party names onto the contract's four disciplines, kept only when the job's scope
    can call for them (CODE_SCOPE: no digging, no excavation duties; no underpinning, no underpinning duties);
  * the hazard rules in `actions/rules.json` (flood, fire, contamination, facade, weather).
  * pre-filing items where DOB NOW filings like this project are held at plan-exam objections more than
    usual for their job type (`actions/filing_objections.py`).

Nothing here marks an item done. Every row's proof is a document that public data does not
hold, so an item's status is always "open" until a person changes it.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Iterable, Optional

from checklist.checklist_rules import RULES as CODE_RULES
from actions.phases import phase_for
from actions.filing_objections import objection_actions
from actions.site_context import applies_to, evidence
from checklist.applicability import _monitoring, _survey

RULES_PATH = pathlib.Path(__file__).with_name("rules.json")

STAGES = ("pre_acquisition", "design", "pre_filing", "construction")


def _load() -> dict:
    with RULES_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


# --- conditions -------------------------------------------------------------
# Each returns True / False / None. None means "we could not tell from what we have",
# which is shown as an unresolved item rather than dropped: a failed lookup is never a no.

def _truthy(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() not in ("", "none", "no", "false", "x", "unknown")
    return bool(value)


def _excavating(profile: dict) -> Optional[bool]:
    wt = profile.get("work_types")
    if wt is None:
        return None
    return bool({"earth_work", "excavation", "foundation", "support_of_excavation", "underpinning"} & set(wt))


def _below_grade(profile: dict) -> Optional[bool]:
    # Only the user or a drawing can confirm this; public data does not record it reliably.
    return profile.get("has_below_grade_occupancy")


def evaluate_condition(name: str, profile: dict) -> Optional[bool]:
    flood = profile.get("flood") or {}
    if name == "excavation":
        return _excavating(profile)
    if name == "flood_zone_mapped":
        return _truthy(flood.get("fema_zone"))
    if name == "stormwater_flood_area":
        mapped = _truthy(flood.get("fema_zone"))
        storm = _truthy(flood.get("stormwater"))
        if storm is None:
            return None
        return bool(storm and not mapped)
    if name == "has_below_grade_occupancy":
        return _below_grade(profile)
    if name == "e_designation_or_remediation_site":
        return _truthy(profile.get("e_designation"))
    if name == "e_designation_or_remediation_site_and_excavation":
        site = _truthy(profile.get("e_designation"))
        dig = _excavating(profile)
        if site is None or dig is None:
            return None
        return bool(site and dig)
    if name == "facade_cycle_applies":
        floors = profile.get("proposed_storeys") or (profile.get("lot") or {}).get("floors")
        if floors is None:
            return None
        return float(floors) > 6
    if name == "work_at_height":
        wt = profile.get("work_types")
        if wt is None:
            return None
        return bool({"facade", "demolition", "structural"} & set(wt))
    if name == "alteration_with_occupancy":
        jt = profile.get("job_type")
        if jt is None:
            return None
        return jt == "alteration"
    if name == "multi_unit_residential":
        bc = (profile.get("lot") or {}).get("building_class")
        if bc is None:
            return None
        return str(bc)[:1] in ("C", "D", "R")
    if name == "gas_work_in_scope":
        wt = profile.get("work_types")
        if wt is None:
            return None
        return "plumbing" in wt or "mechanical" in wt
    if name == "underpinning_in_scope":
        wt = profile.get("work_types")
        if wt is None:
            return None
        return "underpinning" in wt
    if name == "excavation_or_exposed_wall":
        dig, exposed = _excavating(profile), evaluate_condition("exposed_wall", profile)
        if dig is None or exposed is None:
            return None
        return dig or exposed
    if name == "always":
        return True
    if name == "exposed_wall":
        wt = profile.get("work_types")
        if wt is None:
            return None
        return bool({"demolition", "underpinning"} & set(wt))
    raise ValueError(f"unknown condition: {name}")


# --- the code rows ----------------------------------------------------------

# Which scope condition (above) decides whether a checklist row is on a job's list, by the row's condition
# in checklist_rules. Only the scope the team picked is used here: the depth and distance thresholds the full
# checklist engine applies need inputs this list does not have, so a row kept here may still not apply.
CODE_SCOPE = {
    "adjoining_access": "always",  # notice, license, examination: any work on an attached site
    "excavation": "excavation",
    "survey_threshold": "excavation",
    "monitoring_distance": "excavation",
    "dob_decides": "excavation",
    "underpinning": "underpinning_in_scope",
    "exposed_wall": "excavation_or_exposed_wall",
}

def _discipline_for(parties: Iterable[str], mapping: dict) -> Optional[str]:
    """First mapped discipline wins; the party order in checklist_rules is duty order."""
    for p in parties:
        d = mapping.get(p)
        if d:
            return d
    return None


# Rows the code ties to dig depth and distance. Setup gives the depth; a touching lot is 0 ft away.
DEPTH_RULES = {"survey_threshold": _survey, "monitoring_distance": _monitoring}


def depth_check(condition: str, profile: dict) -> dict:
    """The applicability engine's answer for a depth row, with each attached neighbor at 0 ft."""
    attached = [n["bbl"] for n in profile.get("neighbors") or [] if n.get("attached")]
    inputs = {"excavation_depth_ft": profile.get("excavation_depth_ft"),
              "distance_to_building_ft": {bbl: 0 for bbl in attached}}
    return DEPTH_RULES[condition](inputs, {"status": "applies"}, attached[0] if attached else None)


def needs_input_note(found: dict) -> str:
    if "excavation_depth_ft" in found["needs"]:
        return "Needs input: dig depth."
    if "distance_to_building_ft" in found["needs"]:
        return "Needs input: distance to the adjacent buildings."
    return "Needs input: " + (found["notes"][0] if found["notes"] else ", ".join(found["needs"]))


def code_actions(profile: dict, cfg: dict) -> list[dict]:
    mapping = cfg["party_to_discipline"]
    overrides = cfg.get("code_rule_overrides", {})
    owner_roles = cfg["owner_role"]
    out = []
    for rule in CODE_RULES:
        ov = overrides.get(rule.id)
        if ov:
            discipline, hazard = ov["discipline"], ov["hazard"]
        else:
            discipline = _discipline_for(rule.parties, mapping)
            hazard = "structural"
        if discipline is None:
            continue  # a DOB-only or adjoining-owner-only duty: in the checklist, not an action
        applies = evaluate_condition(CODE_SCOPE.get(rule.condition, "always"), profile)
        if applies is False:
            continue  # the job's scope rules it out (no digging, no underpinning)
        why = rule.requirement
        if applies is None:
            why += " Whether this applies could not be determined from the work picked for this job."
        elif rule.condition in DEPTH_RULES:
            found = depth_check(rule.condition, profile)
            if found["status"] == "does_not_apply":
                continue  # the code's depth and distance thresholds rule it out
            if found["status"] == "needs_input":
                why += " " + needs_input_note(found)
        out.append({
            "id": f"action-code-{rule.id}",
            "discipline": discipline,
            "hazard": hazard,
            "title": rule.title,
            "why": why,
            "code_ref": f"2022 NYC BC {rule.section}",
            "proof_needed": rule.proof_needed,
            "status": "open",
            "owner_role": owner_roles.get(discipline),
            "source_rule": f"checklist:{rule.id}",
            "life_safety": rule.life_safety,
            **dict(zip(("phase", "when"), phase_for(f"checklist:{rule.id}"))),
            "applies_to": applies_to(rule.id, profile),
            "evidence": evidence(rule.id, profile),
        })
    return out


# --- the hazard rows --------------------------------------------------------

def hazard_actions(profile: dict, cfg: dict, stage: Optional[str]) -> list[dict]:
    owner_roles = cfg["owner_role"]
    out = []
    for r in cfg["hazard_rules"]:
        if stage and stage not in r["stages"]:
            continue
        applies = evaluate_condition(r["condition"], profile)
        if applies is False:
            continue
        why = r["why"]
        if applies is None:
            why += " Whether this applies could not be determined from the data loaded for this site."
        out.append({
            "id": f"action-{r['id']}",
            "discipline": r["discipline"],
            "hazard": r["hazard"],
            "title": r["title"],
            "why": why,
            "code_ref": r["code_ref"],
            "proof_needed": r["proof_needed"],
            "status": "open",
            "owner_role": owner_roles.get(r["discipline"]),
            "source_rule": f"actions:{r['id']}",
            "life_safety": r["life_safety"],
            **dict(zip(("phase", "when"), phase_for(f"actions:{r['id']}", r["stages"]))),
        })
    return out


# --- the lesson rows --------------------------------------------------------

def lesson_actions(profile: dict, cfg: dict) -> list[dict]:
    """Prevention that lessons from past incidents point to and the code rows don't cover, when the scope fits."""
    owner_roles = cfg["owner_role"]
    work = set(profile.get("work_types") or [])
    out = []
    for r in cfg.get("lesson_rules", []):
        if not work & set(r["scopes"]):
            continue
        out.append({
            "id": f"action-lesson-{r['id']}",
            "discipline": r["discipline"],
            "hazard": r["hazard"],
            "title": r["title"],
            "why": r["why"],
            "code_ref": r["code_ref"],
            "proof_needed": r["proof_needed"],
            "status": "open",
            "owner_role": owner_roles.get(r["discipline"]),
            "source_rule": f"lesson:{r['id']}",
            "life_safety": r["life_safety"],
            **dict(zip(("phase", "when"), phase_for(f"lesson:{r['id']}", r["stages"]))),
        })
    return out


# --- entry point ------------------------------------------------------------

DISCIPLINE_ORDER = ("structural", "geotech", "architect", "contractor")


def build_actions(profile: dict, stage: Optional[str] = None) -> list[dict]:
    """Return ActionItem dicts for a site profile, life-safety first within each discipline."""
    if stage is not None and stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    cfg = _load()
    items = code_actions(profile, cfg) + hazard_actions(profile, cfg, stage) + lesson_actions(profile, cfg)
    items += objection_actions(profile, stage, cfg["owner_role"])
    items.sort(key=lambda a: (DISCIPLINE_ORDER.index(a["discipline"]),
                              not a["life_safety"],
                              a["title"]))
    return items


def group_by_discipline(items: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {d: [] for d in DISCIPLINE_ORDER}
    for a in items:
        out[a["discipline"]].append(a)
    return out
