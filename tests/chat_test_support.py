"""Shared pieces for the chat tests: a made-up site shaped like the shared contracts, a scripted stand-in
for the model, and one for the Anthropic SDK client.

Nothing here reaches the network, and the site, its records and its past cases are invented for the
tests: none describes a real place or event.
"""

from types import SimpleNamespace

from api.routers.chat.chat_answer_build import WebResult
from api.routers.chat.chat_model_call import ModelTurn
from api.routers.chat.chat_models import ChatUsage
from api.routers.chat.chat_site_context import DatasetStatus, Loaded, SiteContext, SiteRecord

SITE_BBL, ATTACHED_BBL, OTHER_BBL = "3000010001", "3000010002", "3000010003"
FILING = "dob_now_filings:B00000001-I1"
STOP_WORK = "dob_violations:V100"  # dated 2026-04-20; a later line was added 2026-05-08
SAFEGUARD = "ecb_violations:E200"  # dated 2026-03-02
JULY_COMPLAINT = "dob_complaints:C301"  # dated 2026-07-02
OLD_CASE, FACADE_CASE, LATE_CASE = "case:ex-underpinning-2019", "case:ex-facade-2022", "case:ex-wall-2026"
MARCH_WARNING, JULY_WARNING = "warning:w1", "warning:w2"
SURVEY_ACTION, NOTICE_ACTION = "action:a1", "action:a2"
JUNE_1 = "2026-06-01"
WEB = WebResult(url="https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page", title="2022 Construction Codes")

_DATASETS = {"dob_now_filings": "DOB NOW job filings", "dob_violations": "DOB violations", "ecb_violations": "ECB violations",
             "dob_complaints": "DOB complaints", "dob_311_requests": "311 service requests routed to DOB"}


def _record(key, record_id, bbl, date, text, **more):
    return SiteRecord(id=f"{key}:{record_id}", dataset_key=key, dataset_name=_DATASETS[key], record_id=record_id, bbl=bbl,
                      date=date, text=text, url=f"https://data.example.org/{key}?bbl={bbl}", **more)


def example_context(as_of=None, **overrides) -> SiteContext:
    profile = {
        "bbl": SITE_BBL, "bins": ["3000001"], "address_matched": "10 EXAMPLE STREET", "lat": 40.6301, "lon": -73.9502,
        "lot": {"zoning": "R6", "far": 2.43, "year_built": 0, "floors": 0, "class": "V1", "landmark": None},
        "neighbors": [
            {"bbl": ATTACHED_BBL, "attached": True, "year_built": 1925, "floors": 4, "class": "C1", "height_ft": 44, "shared_wall_ft": 61},
            {"bbl": OTHER_BBL, "attached": False, "year_built": 1961, "floors": 2, "class": "B1", "height_ft": 22, "shared_wall_ft": 0}],
        "job_type": "new_building", "work_types": ["earth_work", "support_of_excavation"], "work_types_inferred": True,
        "soil": "urban land, till substratum", "bedrock_depth_ft": 85,
        "flood": {"fema_zone": "X", "stormwater": "none mapped", "sandy": False}, "e_designation": None,
        "signals": [{"date": "2026-04-18", "title": "structural-stability complaint on an attached lot"},
                    {"date": "2026-07-02", "title": "party-wall crack complaint on an attached lot"}],
        "structural_model": None, "as_of": as_of,
    }
    records = [
        _record("dob_now_filings", "B00000001-I1", SITE_BBL, "2026-01-10",
                "New building filing. Earth work: YES. Support of excavation: YES.", status_today="Permit issued"),
        _record("dob_violations", "V100", SITE_BBL, "2026-04-20",
                "Failure to protect adjoining property during excavation. STOP WORK ORDER issued.",
                later_text=(("2026-05-08", "Stop work order rescinded."),)),
        _record("ecb_violations", "E200", SITE_BBL, "2026-03-02",
                "BC 3309.4 failure to safeguard adjoining structure. Construction fence damaged."),
        _record("dob_311_requests", "R400", SITE_BBL, "2025-11-05", "Construction fence none or inadequate."),
        _record("dob_complaints", "C300", ATTACHED_BBL, "2026-04-18",
                "Category 30: building shaking, vibrating, structural stability affected.", status_today="Closed"),
        _record("dob_complaints", "C301", ATTACHED_BBL, "2026-07-02", "Cracks in party wall reported after excavation."),
        _record("dob_complaints", "C500", OTHER_BBL, "2024-02-01", "After-hours work reported."),
    ]
    datasets = [DatasetStatus(bbl=SITE_BBL, key=key, name=name, status="ok", url=f"https://data.example.org/{key}?bbl={SITE_BBL}")
                for key, name in _DATASETS.items()]
    datasets += [
        DatasetStatus(bbl=ATTACHED_BBL, key="dob_complaints", name=_DATASETS["dob_complaints"], status="ok"),
        DatasetStatus(bbl=ATTACHED_BBL, key="dob_violations", name=_DATASETS["dob_violations"], status="error", reason="timeout"),
        DatasetStatus(bbl=OTHER_BBL, key="dob_complaints", name=_DATASETS["dob_complaints"], status="ok", capped=True),
    ]

    def case(case_id, date, title, hazards, severity, score, cause_status, cause=None, **more):
        return {"similar": {"case_id": case_id, "score": score, "matched_on": ["attached pre-1940 neighbor", "support of excavation"],
                            "differs_on": ["soil"]},
                "case": {"id": case_id, "title": title, "address": "1 SAMPLE AVENUE", "bbl": "3000020001", "lat": 40.7, "lon": -73.9,
                         "date": date, "hazards": hazards, "severity": severity, "job_type": "new_building",
                         "work_types": ["underpinning"], "conditions": {"neighbor_year_built": 1920, "attached": True},
                         "summary": more.get("summary", "A wall of an attached building moved during excavation next door."),
                         "cause_as_reported": cause, "cause_status": cause_status,
                         "sources": [{"name": "City incident report", "url": "https://example.org/report", "date": date}]}}

    context = SiteContext(
        bbl=SITE_BBL, as_of=as_of, pulled_at="2026-11-14T12:00:00", profile=Loaded.ok(profile), records=records, datasets=datasets,
        similar=Loaded.ok([
            case("ex-facade-2022", "2022-03-03", "Facade failure onto a sidewalk", ["facade"], 3, 0.41, "under_investigation",
                 summary="Masonry fell from a facade under repair."),
            case("ex-underpinning-2019", "2019-06-12", "Partial collapse during underpinning", ["structural", "geotech"], 2, 0.82,
                 "reported", "undermining of the adjoining foundation"),
            case("ex-wall-2026", "2026-08-15", "Party wall failure next to an excavation", ["structural"], 3, 0.9, "under_investigation"),
        ]),
        warnings=Loaded.ok([
            {"id": "w1", "rule_id": "adjacent_protection_no_follow_up", "hazard": "structural", "severity": 1,
             "title": "Adjoining-protection violation with no follow-up record",
             "explanation": "A violation about protecting adjoining property is on file and no follow-up record appears within 21 days.",
             "evidence_record_ids": [SAFEGUARD], "first_seen": "2026-03-23", "as_of": as_of},
            {"id": "w2", "rule_id": "complaint_after_earth_work", "hazard": "structural", "severity": 0,
             "title": "Structural complaint after an earth-work filing next door",
             "explanation": "A complaint about a party wall followed an earth-work filing on a touching lot within 90 days.",
             "evidence_record_ids": [JULY_COMPLAINT], "first_seen": "2026-07-02", "as_of": as_of},
        ]),
        actions=Loaded.ok([
            {"id": "a2", "discipline": "architect", "title": "Notify the adjoining owners", "why": "Excavation is planned next to an attached building.",
             "code_ref": "BC 3309.1.1", "proof_needed": "Copies of the notices", "status": "open", "owner_role": "architect",
             "source_rule": "bc3309_notice", "life_safety": False},
            {"id": "a1", "discipline": "structural", "title": "Pre-construction survey of the adjoining buildings",
             "why": "An attached building built in 1925 shares a wall with the site.", "code_ref": "BC 3309.4.3",
             "proof_needed": "The survey report", "status": "open", "owner_role": "structural engineer",
             "source_rule": "bc3309_survey", "life_safety": True},
        ]),
        layers=Loaded.ok([
            {"layer_id": "sandy_inundation", "name": "Sandy Inundation Zone", "hazard": "flood", "status": "ok", "default_on": False},
            {"layer_id": "dob_complaints_structural", "name": "DOB complaints, structural codes", "hazard": "structural", "status": "ok"},
        ]),
    )
    for name, value in overrides.items():
        setattr(context, name, value)
    return context


def loader(**overrides):
    """A context loader for chat_service.answer, over the made-up site."""
    return lambda bbl, job_type, stage, as_of, project_id=None: example_context(as_of=as_of, **overrides)


def item(kind, **fields):
    return {"kind": kind, "text": "", "refs": [], "bbl": "", "dataset_key": "", "date_from": "", "date_to": "",
            "hazard": "", "severity_min": "", "notice": "", **fields}


def says(text, *refs):
    return item("statement", text=text, refs=list(refs))


def check(bbl, dataset_key):
    return item("dataset_check", bbl=bbl, dataset_key=dataset_key)


def action(kind, **fields):
    return {"type": kind, "layer_id": "", "on": True, "ref": "", **fields}


class ScriptedModel:
    """Stands in for AnthropicChatModel: returns the given proposals in order and records what it was asked."""

    def __init__(self, *proposals, web_results=(), searched=False, fails=None):
        self.proposals, self.web_results, self.searched, self.fails = list(proposals), list(web_results), searched, fails
        self.opened_with = None
        self.problems_seen = []
        self.usage = ChatUsage(model="scripted")

    def open(self, system, messages, allow_web, client_tools=()):
        self.opened_with = {"system": system, "messages": messages, "allow_web": allow_web, "client_tools": client_tools}
        return self

    def open_first(self, system, messages):
        self.first_opened_with = {"system": system, "messages": messages}
        return self

    def turn(self, problems=None):
        if self.fails:
            raise self.fails
        self.problems_seen.append(problems)
        proposal = self.proposals.pop(0)
        return ModelTurn(proposal=proposal if isinstance(proposal, dict) else {"items": proposal, "actions": []},
                         web_results=self.web_results, searched=self.searched)


def tool_call(name, call_id="call_1", **given):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=given)


def submit_block(items, actions=(), call_id="submit_1"):
    return tool_call("submit_answer", call_id, items=items, actions=list(actions))


def response(blocks, stop_reason="tool_use", searches=0):
    usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0,
                            server_tool_use=SimpleNamespace(web_search_requests=searches))
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=usage, model="claude-test")


class FakeAnthropicClient:
    """`client.beta.messages.create(**kwargs)` returning scripted responses; keeps every request it was sent."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        reply = self.responses.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
