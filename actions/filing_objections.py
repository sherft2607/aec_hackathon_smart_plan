"""Pre-filing items from plan-exam objections on similar DOB NOW filings. Owner: Hongyu.

What public data holds: DOB NOW job filings (w9ak-ipjd) record each filing's current `filing_status`, and
"Objections" means the filing is held at plan-exam objections today. What it does not hold: what the
objections were about (no public objections dataset), or that a filing which cleared its objections ever
had them (it now shows as approved). So every item says how many similar filings are *still held*, against
the citywide share for the same job type, and never what DOB will say about this one.

Similar means what `site_profile.similarity.compare` says, run project against filing: same job type only
(objection rates differ sixfold between job types), then the work types and the size of the building. The
pool is stored as counts per (job type, scopes, storeys), because filings that share those look identical
to `compare`; the filings held at objections are kept by job number so the team can look them up.

Similar is ranked by the engine but not by `compare` alone: see `similar_group` for why the size comes from
`compare_buildings` and why exact DOB NOW scopes break ties. The engine has no location feature, so two
projects with the same job type, scopes and height band get the same answer anywhere in the city.

    python -c "from actions.filing_objections import write_pool; write_pool()"   # refresh the pool
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import urllib.parse
import urllib.request
from datetime import date
from typing import Optional

POOL_PATH = pathlib.Path(__file__).with_name("filing_objections.json")
DATASET = "w9ak-ipjd"
DATASET_URL = f"https://data.cityofnewyork.us/d/{DATASET}"
SINCE = "2022-01-01"

# Scope bit -> (work type in our contract, DOB NOW column). Order is the bit order in the stored pool.
# `support_of_excavation_work_type_` is not used: it reads "No" on every DOB NOW filing since 2022 (checked
# 2026-11-15, 737,189 filings), so in Open Data support of excavation travels with the earth-work filing.
SCOPES = [
    ("earth_work", "earth_work_work_type_"),
    ("foundation", "foundation_work_type_"),
    ("structural", "structural_work_type_"),
    ("demolition", "full_demolition_work_type_"),
]
# Our work types -> the DOB NOW scope that files them. Excavation and its support are filed as earth work.
WORK_TYPE_SCOPE = {"earth_work": "earth_work", "excavation": "earth_work", "support_of_excavation": "earth_work",
                   "foundation": "foundation", "structural": "structural", "demolition": "demolition"}

# Our job types -> DOB NOW job types compared with them.
FAMILIES = {
    "new_building": ("New Building", "ALT-CO - New Building with Existing Elements to Remain"),
    "alteration": ("Alteration", "Alteration CO"),
    "demolition": ("Full Demolition",),
}
FAMILY_WORDS = {"new_building": "new-building", "alteration": "alteration", "demolition": "full-demolition"}

# Who answers for each scope's drawings, and the hazard row it files under. Judgment calls: Hongyu.
SCOPE_RULES = {
    "earth_work": {"label": "earth-work and excavation-support", "discipline": "geotech", "hazard": "geotech"},
    "foundation": {"label": "foundation", "discipline": "structural", "hazard": "geotech"},
    "structural": {"label": "structural", "discipline": "structural", "hazard": "structural"},
    "demolition": {"label": "demolition", "discipline": "structural", "hazard": "construction_safety"},
}

SIMILAR_AT_LEAST = 40   # the similar group is every filing scoring at or above the 40th best
MIN_SCOPE_FILINGS = 20  # fewer similar filings with a scope than this says nothing about it
MIN_HELD = 3            # and fewer than this held at objections is not a pattern
# "Held more than usual" has to be both material and unlikely to be chance: at least a quarter above the
# citywide share, and a one-sided binomial tail under 5% at the citywide share. Half a point over thousands
# of filings is neither; 46 of 184 against 15.6% (2625 Bedford) is both.
MIN_LIFT = 1.25
MAX_CHANCE = 0.05
EXAMPLES = 5
STAGES = ("design", "pre_filing")


class PoolUnavailable(Exception):
    """The stored filing pool is missing or unreadable."""


# Pulling the pool -----------------------------------------------------------------------------------


def _where() -> str:
    structural_alt = " OR ".join(f"{col}='YES'" for _, col in SCOPES[:3])
    return (f"filing_date>='{SINCE}' AND job_filing_number like '%-I1' AND ("
            "job_type in('New Building','ALT-CO - New Building with Existing Elements to Remain','Full Demolition')"
            f" OR (job_type in('Alteration','Alteration CO') AND ({structural_alt})))")


def _get(params: dict) -> list[dict]:
    url = f"https://data.cityofnewyork.us/resource/{DATASET}.json?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)
    if os.environ.get("SOCRATA_APP_TOKEN"):
        request.add_header("X-App-Token", os.environ["SOCRATA_APP_TOKEN"])
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def pull(page: int = 20000) -> dict:
    """The pool from Open Data. Names of applicants, owners and representatives are never selected."""
    columns = ["job_filing_number", "job_type", "filing_status", "filing_date", "bbl",
               "proposed_no_of_stories"] + [col for _, col in SCOPES]
    rows: list[dict] = []
    while True:
        batch = _get({"$select": ",".join(columns), "$where": _where(), "$order": "job_filing_number",
                      "$limit": page, "$offset": len(rows)})
        rows.extend(batch)
        if len(batch) < page:
            break
    groups: dict[tuple, dict] = {}
    for r in rows:
        bits = sum(1 << i for i, (_, col) in enumerate(SCOPES) if str(r.get(col, "")).upper() == "YES")
        if r["job_type"] == "Full Demolition":
            bits |= 1 << 3
        try:
            storeys = int(float(r.get("proposed_no_of_stories") or 0)) or None
        except ValueError:
            storeys = None
        key = (r["job_type"], bits, storeys)
        group = groups.setdefault(key, {"job_type": key[0], "scopes": bits, "storeys": storeys, "n": 0, "held": []})
        group["n"] += 1
        if r.get("filing_status") == "Objections":
            group["held"].append([r["job_filing_number"], r.get("bbl"), (r.get("filing_date") or "")[:7]])
    for group in groups.values():
        group["held"].sort(key=lambda h: h[2], reverse=True)
    return {
        "source": {"name": "DOB NOW: Build job application filings", "dataset": DATASET, "url": DATASET_URL,
                   "pulled": date.today().isoformat(),
                   "filter": f"initial filings (-I1) filed since {SINCE}: new buildings, ALT-CO new buildings with "
                             "existing elements, full demolitions, and alterations with earth, foundation, "
                             "support-of-excavation or structural work"},
        "scope_bits": [name for name, _ in SCOPES],
        "filings": len(rows),
        "groups": sorted(groups.values(), key=lambda g: (g["job_type"], g["scopes"], g["storeys"] or 0)),
    }


# Reading and comparing ------------------------------------------------------------------------------


def load_pool(path: pathlib.Path = POOL_PATH) -> dict:
    try:
        pool = json.loads(path.read_text(encoding="utf-8"))
        pool["groups"]  # noqa: B018  (a pool without groups is unreadable, not empty)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise PoolUnavailable(str(error)) from error
    return pool


def _scopes(bits: int, names: list[str]) -> set[str]:
    return {name for i, name in enumerate(names) if bits & (1 << i)}


def project_scopes(profile: dict) -> Optional[set[str]]:
    work = profile.get("work_types")
    if work is None:
        return None
    return {WORK_TYPE_SCOPE[w] for w in work if w in WORK_TYPE_SCOPE}


def _comparison_profile(profile: dict) -> dict:
    """The project as `compare` should see it here: the building it will be, not the one on the lot today,
    and no neighbours or record signals (a filing reports neither, and they would match by accident)."""
    lot = dict(profile.get("lot") or {})
    storeys = profile.get("proposed_storeys")
    if profile.get("job_type") == "new_building":
        lot = {"floors": storeys}  # the building there today is not the one being filed
    elif storeys:
        lot["floors"] = storeys
    return {**profile, "lot": lot, "neighbors": [], "signals": [], "structural_model": None}


def similar_group(profile: dict, pool: dict) -> list[tuple[dict, tuple]]:
    """The groups of filings most like the project, cut where the SIMILAR_AT_LEAST-th filing falls so every
    filing that looks as alike as that one is kept.

    Ranked by the similarity engine, project against filing: `compare` for the work types, and
    `compare_buildings` for the size, called directly because `compare` looks for the building that stood
    next to a dig (an incident's hurt neighbour) while a filing's building is the project itself. The engine
    scores earth work, foundation and support of excavation as one feature, which is right for incidents but
    blunt for plan exam, so ties go to filings with exactly this project's DOB NOW scopes."""
    from site_profile.building_profile import case_building, site_buildings
    from site_profile.similarity import compare, compare_buildings

    family = FAMILIES.get(profile.get("job_type") or "")
    if not family:
        return []
    names = pool["scope_bits"]
    here = _comparison_profile(profile)
    project = site_buildings(here)[0]
    mine = project_scopes(profile) or set()
    scored = []
    for g in pool["groups"]:
        if g["job_type"] not in family:
            continue
        theirs = _scopes(g["scopes"], names)
        case = {"id": "filing", "address": f"{g['job_type']} filing", "bbl": None, "hazards": [],
                "work_types": sorted(theirs), "job_type": profile.get("job_type"),
                "conditions": {"floors": None if g["job_type"] == "Full Demolition" else g["storeys"]}}
        score = compare(here, case)["score"] + compare_buildings(project, case_building(case))["score"]
        if score > 0:
            scored.append((g, (round(score, 3), theirs == mine)))
    scored.sort(key=lambda gs: gs[1], reverse=True)
    total, cutoff = 0, None
    for g, key in scored:
        total += g["n"]
        if total >= SIMILAR_AT_LEAST:
            cutoff = key
            break
    if cutoff is None:
        return scored
    return [(g, k) for g, k in scored if k >= cutoff]


def _held(group: dict, own_bbl: Optional[str]) -> list[list]:
    return [h for h in group["held"] if not own_bbl or h[1] != own_bbl]


def scope_shares(groups: list[dict], scope: str, names: list[str], own_bbl: Optional[str]) -> tuple[int, int, list]:
    """(held, filings, examples) among the groups whose filings include the scope. The lot's own filings
    held at objections are left out of both counts: its own history is not a similar project."""
    bit = 1 << names.index(scope)
    held, n, examples = 0, 0, []
    for g in groups:
        if not g["scopes"] & bit:
            continue
        mine = len(g["held"]) - len(_held(g, own_bbl))
        held += len(g["held"]) - mine
        n += g["n"] - mine
        examples.extend(_held(g, own_bbl))
    examples.sort(key=lambda h: h[2], reverse=True)
    return held, n, examples


def chance_of_at_least(held: int, n: int, share: float) -> float:
    """P(at least `held` of `n` filings held) if each were held at the citywide `share`: an exact binomial
    tail, summed in log space so thousands of filings do not overflow."""
    if held <= 0:
        return 1.0
    if share <= 0:
        return 0.0
    if share >= 1:
        return 1.0
    log_p, log_q = math.log(share), math.log1p(-share)
    total = 0.0
    for k in range(held, n + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * log_p
                          + (n - k) * log_q)
    return min(total, 1.0)


def held_more_than_usual(held: int, n: int, base_held: int, base_n: int) -> bool:
    if n < MIN_SCOPE_FILINGS or held < MIN_HELD or not base_n:
        return False
    base = base_held / base_n
    return held / n >= MIN_LIFT * base and chance_of_at_least(held, n, base) < MAX_CHANCE


# Items ----------------------------------------------------------------------------------------------


def _item(rule_id: str, discipline: str, hazard: str, title: str, why: str, proof: Optional[str],
          owner_roles: dict, evidence: Optional[str] = None) -> dict:
    from actions.phases import phase_for

    source_rule = f"actions:objections:{rule_id}"
    return {
        "id": f"action-objections-{rule_id}", "discipline": discipline, "hazard": hazard, "title": title,
        "why": why, "code_ref": None, "proof_needed": proof, "status": "open",
        "owner_role": owner_roles.get(discipline), "source_rule": source_rule, "life_safety": False,
        **dict(zip(("phase", "when"), phase_for(source_rule, ["pre_filing"]))),
        "evidence": evidence,
    }


def _unresolved(reason: str, owner_roles: dict) -> dict:
    return _item("unresolved", "architect", "structural", "Compare this filing with similar DOB NOW filings",
                 f"{reason} So whether similar filings are held at plan-exam objections is not known for this "
                 "project.", None, owner_roles)


def objection_actions(profile: dict, stage: Optional[str], owner_roles: dict,
                      pool: Optional[dict] = None) -> list[dict]:
    """Pre-filing items for the scopes where similar filings are held at objections more than usual."""
    if stage is not None and stage not in STAGES:
        return []
    if pool is None:
        try:
            pool = load_pool()
        except PoolUnavailable:
            return [_unresolved("Couldn't load the DOB NOW filing comparison.", owner_roles)]
    job_type, scopes = profile.get("job_type"), project_scopes(profile)
    if job_type not in FAMILIES:
        return [_unresolved("The job type is not set, so this project could not be compared with similar "
                            "DOB NOW filings; set it on the project screen.", owner_roles)]
    if scopes is None:
        return [_unresolved("The work types are not set, so this project could not be compared with similar "
                            "DOB NOW filings; set them on the project screen.", owner_roles)]

    names, own = pool["scope_bits"], profile.get("bbl")
    family_groups = [g for g in pool["groups"] if g["job_type"] in FAMILIES[job_type]]
    similar = [g for g, _ in similar_group(profile, pool)]
    source = pool["source"]
    out = []
    for scope in sorted(scopes):
        held, n, examples = scope_shares(similar, scope, names, own)
        base_held, base_n, _ = scope_shares(family_groups, scope, names, None)
        if not held_more_than_usual(held, n, base_held, base_n):
            continue
        rule = SCOPE_RULES[scope]
        family = FAMILY_WORDS[job_type]
        refs = ", ".join(f"{h[0]} ({h[2]})" for h in examples[:EXAMPLES])
        out.append(_item(
            scope, rule["discipline"], rule["hazard"],
            f"Check the {rule['label']} drawings against objections on similar filings",
            f"{held} of the {n} DOB NOW {family} filings most like this project that include {rule['label']} "
            f"work are held at plan-exam objections, against {base_held / base_n:.0%} of all {base_n} such "
            f"{family} filings since {SINCE[:4]}. Similar means the same job type, then the work types and the "
            "size of the building. The public record says that objections were issued, not what they were about, "
            "and a filing that cleared its objections shows as approved, so this counts only filings still held. "
            "A pattern among similar filings, not a prediction for this one. "
            f"Source: {source['name']} ({source['dataset']}), pulled {source['pulled']}.",
            f"A review of the {rule['label']} drawings by the design professional of record before filing, noted "
            f"on the project. Similar filings held at objections, to look up in DOB NOW by job number: {refs}.",
            owner_roles,
            evidence=f"{held} of {n} similar filings held at objections; {base_held / base_n:.0%} of {family} "
                     f"filings with {rule['label']} work citywide",
        ))
    return out


def write_pool(path: pathlib.Path = POOL_PATH) -> None:
    """Pull the pool from Open Data and store it next to this module."""
    pool = pull()
    path.write_text(json.dumps(pool, separators=(",", ":")) + "\n", encoding="utf-8")
    held = sum(len(g["held"]) for g in pool["groups"])
    print(f"wrote {path.name}: {pool['filings']} filings in {len(pool['groups'])} groups, {held} held")
