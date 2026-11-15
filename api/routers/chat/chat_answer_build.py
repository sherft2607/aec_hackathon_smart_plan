"""Turn the model's proposed answer into the parts and page actions the reader gets, or into reasons to hold it back.

The model proposes; this module decides. A statement's kind comes from what it cites (a public
record, a past case, a warning, an action item, or a web result), never from what the model calls
it. Counts, search results, "none found" and "unknown" are written here from the data's own status,
so a failed query can never read as zero. A page action is checked against what the page really has.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from api.routers.chat import chat_case_search, chat_record_search, chat_wording_checks
from api.routers.chat.chat_case_search import CaseQuery
from api.routers.chat.chat_models import (
    ActionPart, AnswerPart, CasePart, FlyToAction, LeadPart, NotFoundPart, NoticePart, PageAction, PinAnswerAction,
    QueriedDataset, RecordPart, RecordSource, ToggleLayerAction, UnknownPart, WarningPart, WebSource,
)
from api.routers.chat.chat_record_search import RecordQuery
from api.routers.chat.chat_site_view import PIECES, SiteView

MAX_ITEMS = 12
MAX_ACTIONS = 4
MAX_STATEMENT_CHARS = 700
MAX_GAP_CHARS = 140

NOTICES = {
    "not_a_determination": "ForeSite is not engineering advice and is not exhaustive. It does not determine code "
    "compliance, structural adequacy or safety: the licensed professionals on the project and the Department of "
    "Buildings do.",
    "names_withheld": "ForeSite leaves out the names of owners, applicants, contractors and permit holders.",
    "cause_not_established": "Nothing in the public record here establishes the cause of any incident. A past case "
    "carries a cause only as publicly reported, or as under investigation.",
    "out_of_scope": "That is outside what this chat covers: this site's public records and facts, the past cases "
    "compared with it, its early warnings and its action items.",
    "status_is_todays": "A record's status is the one published when the data was pulled, not its status on an "
    "earlier date: the datasets keep only the current status.",
    "not_a_prediction": "A warning or a similar past case is a pattern compared with similar sites. It is not a "
    "prediction that anything will happen at this site.",
    "warning_rules_unchecked": "Not every early-warning rule could be confirmed as checked for this site, so the "
    "warnings shown here may not be all of them.",
    "complaints_overlap": "311 requests and DOB complaints can be the same complaint and share no key, so their "
    "counts are never added.",
    "web_off_as_of": "Web search is off in an as-of view: the web holds what is known today, not what was "
    "knowable on that day.",
    "held_back": "Part of the draft answer was held back because it could not be tied to a source.",
    "after_as_of": "Some of this prepared answer is not shown: it rests on material dated on or after the as-of day.",
    "no_answer": "No answer could be drawn from this site's data or the web for this question.",
    "action_dropped": "Something the answer asked the page to do was dropped because it did not match what the page has.",
    "pin_needs_project": "Nothing was pinned: open a project first, then ask again.",
    "pin_needs_answer": "Nothing was pinned: there is no earlier answer in this conversation to save.",
    "saved_example": "A saved example answer, written ahead of time and checked against this site's data. No model "
    "was called and no web search was run.",
    "mock_answer": "A mock answer: no model was called. The question was matched by keyword to a prepared answer, "
    "which was checked against this site's data. It uses no web search.",
    "mock_no_match": "No prepared answer matches this question, and the mock does not make one up. It can search "
    "the records and the past cases, count records in a dataset, list warnings and action items, show or hide a "
    "map layer, and pin the last answer.",
    "live_failed": "The live model call did not complete, so this is a mock answer.",
    "first_pass": "A first answer, from this site's data alone. The fuller answer, which also searches the records, "
    "the past cases and the web, is still being prepared and will replace this one.",
}
# The codes a model may ask for. The rest are the server's own.
MODEL_NOTICES = ("not_a_determination", "names_withheld", "cause_not_established", "out_of_scope", "status_is_todays",
                 "not_a_prediction")
_PART_FOR = {"record": RecordPart, "case": CasePart, "warning": WarningPart, "action": ActionPart}
_KIND_WORDS = {"record": "a public record or site fact", "case": "a past case", "warning": "an early warning",
               "action": "an action item", "lead": "a web result"}


class ProposedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["statement", "dataset_check", "record_search", "case_search", "gap", "notice"]
    text: str = ""
    refs: list[str] = Field(default_factory=list)
    bbl: str = ""
    dataset_key: str = ""
    date_from: str = ""
    date_to: str = ""
    hazard: str = ""
    severity_min: str = ""
    notice: str = ""


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["toggle_layer", "fly_to", "pin_answer"]
    layer_id: str = ""
    on: bool = True
    ref: str = ""


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ProposedItem] = Field(max_length=MAX_ITEMS)
    actions: list[ProposedAction] = Field(default_factory=list, max_length=MAX_ACTIONS)

    @model_validator(mode="after")
    def _says_or_does_something(self) -> "Proposal":
        if not self.items and not self.actions:
            raise ValueError("an answer needs at least one item or one action")
        return self


@dataclass(frozen=True)
class WebResult:
    url: str
    title: str
    page_age: Optional[str] = None


@dataclass
class Built:
    parts: list[AnswerPart] = field(default_factory=list)
    actions: list[PageAction] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # what to tell the model on its one retry
    actions_dropped: int = 0  # how many of the problems are page actions, not statements
    after_as_of: int = 0  # items resting on material the as-of view leaves out
    counted: set = field(default_factory=set)  # dataset keys a dataset_check reported on


def _same_page(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}?{parts.query}"


def _is_official(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host.endswith(".gov") or host == "cityofnewyork.us" or host.endswith(".cityofnewyork.us")


def _statement(view: SiteView, item: ProposedItem, web: dict[str, WebResult], built: Built, where: str) -> None:
    text = item.text.strip()
    refs = list(dict.fromkeys(ref.strip().strip("[]") for ref in item.refs if ref.strip()))
    if not text or len(text) > MAX_STATEMENT_CHARS:
        built.problems.append(f"{where}: a statement needs text of at most {MAX_STATEMENT_CHARS} characters.")
        return
    if not refs:
        built.problems.append(f"{where}: no source. Every statement cites the ids or the search result URLs it rests on.")
        return
    sources: dict[str, list] = {}  # kind of source -> the sources cited
    evidence = [view.shared_evidence]
    for ref in refs:
        if ref.lower().startswith(("http://", "https://")):
            result = web.get(_same_page(ref))
            if result is None:
                built.problems.append(f"{where}: {ref} is not a URL the web search returned in this conversation.")
                return
            sources.setdefault("lead", []).append(WebSource(url=result.url, title=result.title, page_age=result.page_age,
                                                            official=_is_official(result.url)))
        elif ref in view.items:
            cited = view.items[ref]
            sources.setdefault(cited.trust, []).append(cited.source)
            evidence.append(cited.evidence)
        else:
            built.after_as_of += ref in view.after_as_of
            built.problems.append(f"{where}: {ref} is not an item of this site's view.")
            return
    if len(sources) > 1:
        built.problems.append(f"{where}: it cites {' and '.join(_KIND_WORDS[kind] for kind in sources)}. Split it: the "
                              "reader sees each kind of source under its own label.")
        return
    kind = next(iter(sources))
    # A past case or a web result may relay a cause as reported; a record, a warning or an action item never states one.
    reasons = chat_wording_checks.statement_problems(text, None if kind == "lead" else " ".join(evidence),
                                                     is_lead=kind in ("lead", "case"))
    if reasons:
        built.problems += [f"{where}: {reason}" for reason in reasons]
        return
    built.parts.append(LeadPart(text=text, sources=sources[kind]) if kind == "lead"
                       else _PART_FOR[kind](text=text, sources=sources[kind]))


_LISTS = {"early_warnings": ("warnings", "warning", WarningPart, "early-warning rule result"),
          "action_items": ("actions", "action", ActionPart, "action item")}


def _list_check(view: SiteView, key: str, built: Built) -> None:
    """The site's early warnings or action items as a count, none, or unknown when the list did not load."""
    name, prefix, part_type, noun = _LISTS[key]
    piece, loaded = PIECES[name], view.piece(name)
    entries = view.warnings if name == "warnings" else view.actions
    # With a project open the action items are that project's own checklist, and the sentence says so.
    where = "on the open project's checklist" if name == "actions" and view.project_open else "for this site"
    general = (" This is the lot's general list: the open project's checklist could not be read."
               if name == "actions" and view.project_unread else "")
    before = f" dated before {view.as_of}" if view.as_of and name == "warnings" else ""
    if loaded.status != "ok":
        built.parts.append(UnknownPart(text=f"Unknown: the {noun}s {where} could not be loaded, so nothing is known "
                                            "about them. This is not the same as none.", queried=[piece]))
        return
    # A rule that could not run may be hiding a result: none becomes unknown, and a count becomes a floor.
    unchecked = view.rules_not_checked if name == "warnings" else []
    missing = (f"{len(unchecked)} early-warning rule{' was' if len(unchecked) == 1 else 's were'} not checked "
               f"({'; '.join(unchecked[:4])}{'; and more' if len(unchecked) > 4 else ''})") if unchecked else ""
    if name == "warnings" and view.rule_checks_failed:
        missing = "the checks on whether each early-warning rule ran could not be loaded"
    built.counted.add(key)
    if not entries and missing:
        built.parts.append(UnknownPart(text=f"Unknown: no {noun} was raised for this site{before}, but {missing}, so nothing is "
                                            "known from them. This is not the same as none.", queried=[piece]))
    elif not entries:
        built.parts.append(NotFoundPart(text=f"None found: no {noun} {where}{before}.{general}", queried=[piece]))
    else:
        text = f"{'At least ' if missing else ''}{len(entries)} {noun}{'' if len(entries) == 1 else 's'} {where}{before}.{general}"
        built.parts.append(part_type(text=text + (f" {missing[0].upper()}{missing[1:]}, so this is a floor." if missing else ""),
                                     sources=[view.items[f"{prefix}:{entry['id']}"].source for entry in entries[:8]]))


def _dataset_check(view: SiteView, item: ProposedItem, built: Built, where: str) -> None:
    if item.dataset_key.strip() in _LISTS:
        return _list_check(view, item.dataset_key.strip(), built)
    dataset = view.datasets.get((item.bbl.strip(), item.dataset_key.strip()))
    if dataset is None:
        built.problems.append(f"{where}: this site has no dataset '{item.dataset_key}' for lot '{item.bbl}'.")
        return
    queried, lot = [dataset.queried()], dataset.lot_label
    built.counted.add(dataset.key)
    before = f" among records dated before {view.as_of}" if view.as_of else ""
    if dataset.status != "ok":
        why = "the query failed" if dataset.status == "error" else f"it was not queried ({dataset.reason or 'no reason given'})"
        built.parts.append(UnknownPart(text=f"Unknown: {dataset.name} for {lot}: {why}, so nothing is known. This is not zero.",
                                       queried=queried))
    elif dataset.count is None:
        # The source gave a count for today only and no records to cut at the day.
        built.parts.append(UnknownPart(text=f"Unknown: {dataset.name} for {lot}{before}: the records were not loaded, so they "
                                            "cannot be counted for this view. This is not zero.", queried=queried))
    elif not dataset.count and dataset.capped:
        # A capped pull lost its oldest records, so an empty as-of view cannot say "none".
        built.parts.append(UnknownPart(
            text=f"Unknown: {dataset.name} for {lot}{before}: the pull hit its row cap and its oldest records are "
                 "missing, so nothing is known for this view. This is not zero.", queried=queried))
    elif not dataset.count:
        built.parts.append(NotFoundPart(text=f"None found in {dataset.name} for {lot}{before}.", queried=queried))
    else:
        noun = "record" if dataset.count == 1 else "records"
        floor = "At least " if dataset.capped else ""
        cap = " The pull hit its row cap, so the oldest records are missing." if dataset.capped else ""
        built.parts.append(RecordPart(
            text=f"{floor}{dataset.count} {noun} in {dataset.name} for {lot}{before}.{cap}",
            sources=[RecordSource(type="dataset_count", ref=f"dataset:{dataset.bbl}:{dataset.key}", label=dataset.name,
                                  bbl=dataset.bbl, url=dataset.url)]))


def _record_search(view: SiteView, item: ProposedItem, built: Built, where: str) -> None:
    query = RecordQuery(text=item.text.strip(), bbl=item.bbl.strip(), dataset_key=item.dataset_key.strip(),
                        date_from=item.date_from.strip(), date_to=item.date_to.strip())
    problem = chat_record_search.query_problem(view, query)
    if problem:
        built.problems.append(f"{where}: {problem}")
        return
    built.parts += chat_record_search.search_parts(view, chat_record_search.search(view, query))


def _case_search(view: SiteView, item: ProposedItem, built: Built, where: str) -> None:
    query = CaseQuery(text=item.text.strip(), hazard=item.hazard.strip(), severity_min=item.severity_min.strip())
    problem = chat_case_search.query_problem(query)
    if problem:
        built.problems.append(f"{where}: {problem}")
        return
    built.parts += chat_case_search.search_parts(view, chat_case_search.search(view, query))


def _gap(view: SiteView, item: ProposedItem, searched: bool, built: Built, where: str) -> None:
    topic = item.text.strip().rstrip(".")
    reasons = chat_wording_checks.statement_problems(topic, "", is_lead=False) if topic else ["a gap needs a topic."]
    if len(topic) > MAX_GAP_CHARS:
        reasons.append(f"a gap's topic is at most {MAX_GAP_CHARS} characters.")
    if reasons:
        built.problems += [f"{where}: {reason}" for reason in reasons]
        return
    names = {d.key: d.name for d in view.datasets.values() if d.status == "ok"}
    looked = [QueriedDataset(key=key, name=name) for key, name in names.items()]
    looked += [piece for name, piece in PIECES.items() if view.piece(name).status == "ok"]
    scope = "this site's data or the web results read for this answer" if searched else "this site's data"
    if not looked:  # nothing could be read at all: that is unknown, not "not found"
        built.parts.append(UnknownPart(text=f"Unknown: none of this site's data could be loaded, so nothing is known about: {topic}.",
                                       queried=list(PIECES.values())))
        return
    built.parts.append(NotFoundPart(text=f"Not found in {scope}: {topic}.", queried=looked))


def notice(code: str) -> NoticePart:
    return NoticePart(code=code, text=NOTICES[code])


def _actions(view: SiteView, proposed: list[ProposedAction], project_id: Optional[str], has_history: bool, built: Built) -> None:
    """A page action is kept only if it names something the page has: a listed layer, an item with a place, an
    open project and an answer to pin. Each one kept is also said in words, for a reader who cannot see the map."""
    def drop(reason: str) -> None:
        built.problems.append(reason)
        built.actions_dropped += 1

    def keep(action: PageAction, said: str) -> None:
        built.actions.append(action)
        built.parts.append(NoticePart(code="page_action", text=said))

    for number, action in enumerate(proposed, start=1):
        where = f"action {number}"
        if action.type == "toggle_layer":
            layer_id = action.layer_id.strip()
            if layer_id not in view.layers:
                drop(f"{where}: '{layer_id}' is not a layer id under MAP LAYERS.")
            else:
                keep(ToggleLayerAction(layer_id=layer_id, name=view.layers[layer_id], on=action.on),
                     f"The page was asked to {'show' if action.on else 'hide'} the map layer: {view.layers[layer_id]}.")
        elif action.type == "fly_to":
            ref = action.ref.strip().strip("[]")
            target = view.fly_targets.get(ref)
            if target is None or not (target.bbl or (target.lat is not None and target.lon is not None)):
                drop(f"{where}: {ref or 'an empty ref'} is not an item of this view with a place on the map. Use a "
                     "site, neighbor, record or case id.")
            else:
                keep(FlyToAction(ref=ref, label=target.label, bbl=target.bbl, lat=target.lat, lon=target.lon),
                     f"The page was asked to move the map to: {target.label}.")
        elif not project_id:
            built.parts.append(notice("pin_needs_project"))  # nothing the model can fix: tell the reader
        elif action.ref.strip() == "previous":
            if has_history:
                keep(PinAnswerAction(project_id=project_id, target="previous"),
                     "The page was asked to save the previous answer to the open project.")
            else:
                built.parts.append(notice("pin_needs_answer"))
        elif all(part.kind == "notice" for part in built.parts):
            drop(f"{where}: there is nothing in this answer to pin.")
        else:
            keep(PinAnswerAction(project_id=project_id, target="this"),
                 "The page was asked to save this answer to the open project.")


def build_parts(view: SiteView, proposed: object, web_results: list[WebResult], searched: bool = False,
                project_id: Optional[str] = None, has_history: bool = False) -> Built:
    built = Built()
    try:
        proposal = Proposal.model_validate(proposed)
    except ValidationError as error:
        built.problems.append(f"the answer did not fit the tool's shape ({error.error_count()} problems): up to "
                              f"{MAX_ITEMS} items and {MAX_ACTIONS} actions, at least one of either, each with every field.")
        return built
    web = {_same_page(result.url): result for result in web_results}
    for number, item in enumerate(proposal.items, start=1):
        where = f"item {number}"
        if item.kind == "statement":
            _statement(view, item, web, built, where)
        elif item.kind == "dataset_check":
            _dataset_check(view, item, built, where)
        elif item.kind == "record_search":
            _record_search(view, item, built, where)
        elif item.kind == "case_search":
            _case_search(view, item, built, where)
        elif item.kind == "gap":
            _gap(view, item, searched, built, where)
        elif item.notice in MODEL_NOTICES:
            built.parts.append(notice(item.notice))
        else:
            built.problems.append(f"{where}: '{item.notice}' is not a notice. Use one of: {', '.join(MODEL_NOTICES)}.")
    if {"dob_complaints", "dob_311_requests"} <= built.counted:
        built.parts.append(notice("complaints_overlap"))
    if any(part.kind in ("case", "warning") for part in built.parts):
        built.parts.append(notice("not_a_prediction"))
    if view.warnings_may_be_incomplete and "early_warnings" not in built.counted and any(part.kind == "warning" for part in built.parts):
        built.parts.append(notice("warning_rules_unchecked"))
    _actions(view, proposal.actions, project_id, has_history, built)
    return built


def without_repeats(parts: list[AnswerPart]) -> list[AnswerPart]:
    """Each notice once, in the order first seen."""
    seen, kept = set(), []
    for part in parts:
        if part.kind == "notice":
            if (part.code, part.text) in seen:  # the text too: each page action has its own line under one code
                continue
            seen.add((part.code, part.text))
        kept.append(part)
    return kept


_SPOKEN = {
    "record": "From the public record: ",
    "case": "From the case library, as publicly reported: ",
    "warning": "An early-warning pattern, not a prediction: ",
    "action": "An action item from the rules, not a determination: ",
    "lead": "From the web, not checked by us: ",
}


def plain_text(parts: list[AnswerPart]) -> str:
    """One text for a voice client: each part says where it came from, and links are left out."""
    return "\n".join(_SPOKEN.get(part.kind, "") + part.text for part in parts)
