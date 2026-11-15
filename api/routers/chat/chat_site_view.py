"""One site as the chat may use it on the page's as-of day.

One place decides what is visible, so the model's reading text, the items a statement may cite, the
searches and the server-written counts cannot disagree. In an as-of view a record, a past case or a
warning dated on or after the day does not exist here, text written later is left out, and today's
statuses are dropped (the datasets keep only the current status, so it says nothing about the earlier
day). A piece that could not be loaded is kept as "not loaded", never as empty.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, Union

from api.routers.chat.chat_models import (
    ActionSource, CaseReport, CaseSource, QueriedDataset, RecordSource, WarningSource,
)
from api.routers.chat.chat_site_context import Loaded, SiteContext, SiteRecord

LATER = "[dated on or after the as-of day]"
RECORDS_SHOWN_PER_DATASET = 25
CASES_SHOWN = 12
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# What a part of the app is called when the chat says it looked there, or could not.
PIECES = {
    "similar": QueriedDataset(key="case_library", name="Similar past cases (the case library)"),
    "warnings": QueriedDataset(key="early_warnings", name="Early-warning rules"),
    "actions": QueriedDataset(key="action_items", name="Action items"),
}
_SITE_FACTS = ("address_matched", "bins", "lot", "job_type", "work_types", "soil", "bedrock_depth_ft", "flood",
               "e_designation")


@dataclass(frozen=True)
class Item:
    """One thing a statement may cite. `evidence` is the text its numbers are checked against."""

    ref: str
    trust: str  # "record", "case", "warning" or "action": the kind of part a statement citing it becomes
    source: Union[RecordSource, CaseSource, WarningSource, ActionSource]
    evidence: str


@dataclass(frozen=True)
class DatasetView:
    bbl: str
    key: str
    name: str
    status: str
    count: Optional[int]  # None unless status is ok
    capped: bool
    reason: Optional[str]
    url: Optional[str]
    lot_label: str
    records_loaded: bool = True  # False when the source gave only a count: there is nothing here to search

    def queried(self) -> QueriedDataset:
        return QueriedDataset(key=self.key, name=self.name, bbl=self.bbl, url=self.url)


@dataclass(frozen=True)
class FlyTarget:
    label: str
    bbl: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


def _words(value) -> str:
    """A stored choice as the reader would say it: structural_engineer -> structural engineer."""
    return str(value).replace("_", " ")


def _flat(value) -> str:
    """A contract object as one readable line: 'year built: 1931, floors: 6'."""
    if isinstance(value, dict):
        return ", ".join(f"{str(k).replace('_', ' ')}: {_flat(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, list):
        return "; ".join(_flat(v) for v in value)
    return "yes" if value is True else "no" if value is False else str(value)


def _number(value) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class SiteView:
    def __init__(self, context: SiteContext):
        self.context = context
        self.as_of: Optional[str] = context.as_of
        self.site_bbl = context.bbl
        self.profile: dict = context.profile.value if context.profile.status == "ok" and context.profile.value else {}
        self.lot_labels = self._lot_labels()
        visible = [r for r in context.records if self._dated_before(r.date)]
        self.records: list[SiteRecord] = sorted(visible, key=lambda r: r.date or "", reverse=True)  # newest first
        self.after_as_of = {r.id for r in context.records} - {r.id for r in self.records}
        self.items: dict[str, Item] = {}
        self.fly_targets: dict[str, FlyTarget] = {}
        self.datasets: dict[tuple[str, str], DatasetView] = {}
        self.cases: list[dict] = []  # {"similar": .., "case": ..} entries visible in this view, closest first
        self.warnings: list[dict] = []
        # Titles of early-warning rules that could not run: the warnings above may then not be all of them.
        self.rules_not_checked: list[str] = [
            str(check.get("title") or check.get("rule_id") or "an unnamed rule")
            for check in (context.warning_checks.value or []) if check.get("status") == "error"
        ] if context.warning_checks.status == "ok" else []
        # The checks themselves failed to load: whether every rule ran is not known.
        self.rule_checks_failed = context.warning_checks.status == "error"
        self.actions: list[dict] = []
        # The action items are the open project's own checklist, or the lot's general list.
        self.project_open = context.project.status == "ok"
        # A project is open and could not be read: the general list must not pass for its checklist.
        self.project_unread = context.project.reason if context.project.status == "error" else None
        self.layers: dict[str, str] = {}  # layer id -> name, when the layer list loaded
        self.layer_hazards: dict[str, str] = {}  # layer id -> the hazard it shows
        # Numbers a statement may always use: the view's own dates and the site's lot.
        self.shared_evidence = " ".join(filter(None, [self.as_of, (context.pulled_at or "")[:10], context.bbl,
                                                      str(self.profile.get("address_matched") or "")]))
        self._add_datasets()
        self._add_site_facts()
        for record in self.records:
            self._add_record(record)
        self._add_cases()
        self._add_warnings()
        self._add_actions()
        if context.layers.status == "ok":
            self.layers = {str(layer["layer_id"]): str(layer.get("name") or layer["layer_id"])
                           for layer in context.layers.value or [] if layer.get("layer_id")}
            self.layer_hazards = {str(layer["layer_id"]): str(layer.get("hazard") or "")
                                  for layer in context.layers.value or [] if layer.get("layer_id")}

    @property
    def warnings_may_be_incomplete(self) -> bool:
        """A rule could not run, or the checks that say which rules ran did not load."""
        return bool(self.rules_not_checked) or self.rule_checks_failed

    # ---- visibility ----

    def _dated_before(self, when: Optional[str]) -> bool:
        """Dated before the day. Undated text cannot be placed, so an as-of view leaves it out."""
        if self.as_of is None:
            return True
        if when is None:
            return False
        when = str(when)[:10]
        # A date given only as a year or a month ("2020") is before the day only if that whole year or month is.
        return when < self.as_of[:len(when)] if len(when) < 10 else when < self.as_of

    def _scrub(self, text: str) -> str:
        if self.as_of is None:
            return text
        return _ISO_DATE.sub(lambda m: m.group() if m.group() < self.as_of else LATER, text)

    def _later_text(self, record: SiteRecord) -> list[tuple[Optional[str], str]]:
        return [(day, text) for day, text in record.later_text if self._dated_before(day)]

    def record_text(self, record: SiteRecord) -> str:
        """The record's own words visible in this view, without the phrases this module adds: what a search reads."""
        own = [self._scrub(record.text)]
        if self.as_of is None and record.status_today:
            own.append(record.status_today)
        return " ".join(own + [text for _, text in self._later_text(record)])

    def piece(self, name: str) -> Loaded:
        return getattr(self.context, name)

    # ---- items ----

    def _lot_labels(self) -> dict[str, str]:
        address = self.profile.get("address_matched")
        labels = {self.site_bbl: f"{address} (lot {self.site_bbl}, the site)" if address else f"lot {self.site_bbl} (the site)"}
        for neighbor in self.profile.get("neighbors") or []:
            if neighbor.get("bbl"):
                attached = ", attached" if neighbor.get("attached") else ""
                where = f"lot {neighbor['bbl']}, touching the site{attached}"
                labels.setdefault(str(neighbor["bbl"]), f"{neighbor['address']} ({where})" if neighbor.get("address")
                                  else f"lot {neighbor['bbl']} (touching the site{attached})")
        for bbl in [d.bbl for d in self.context.datasets] + [r.bbl for r in self.context.records]:
            labels.setdefault(bbl, f"lot {bbl}")
        return labels

    def _add_datasets(self) -> None:
        for dataset in self.context.datasets:
            count = None
            listed = [r for r in self.context.records if r.bbl == dataset.bbl and r.dataset_key == dataset.key]
            if dataset.status == "ok" and (listed or dataset.count is None):
                count = sum(1 for r in listed if self._dated_before(r.date))
            elif dataset.status == "ok" and self.as_of is None:
                count = dataset.count  # the source's own count, when the records themselves were not handed over
            self.datasets[(dataset.bbl, dataset.key)] = DatasetView(
                bbl=dataset.bbl, key=dataset.key, name=dataset.name, status=dataset.status, count=count,
                capped=dataset.status == "ok" and dataset.capped, reason=dataset.reason, url=dataset.url,
                lot_label=self.lot_labels[dataset.bbl], records_loaded=bool(listed) or not dataset.count)

    def _add_site_facts(self) -> None:
        if not self.profile:
            return
        facts = {key: self.profile[key] for key in _SITE_FACTS if self.profile.get(key) not in (None, "", [], {})}
        detail = _flat(facts)
        if self.profile.get("work_types_inferred"):
            detail += ". The work types are inferred from the job type, not read from a filing"
        signals = [s for s in self.profile.get("signals") or []
                   if self.as_of is None or (isinstance(s, dict) and self._dated_before(s.get("date"))
                                             and not self.after_as_of & set(s.get("record_ids") or []))]
        if signals:
            detail += ". Signals: " + _flat(signals)
        ref = f"site:{self.site_bbl}"
        self.items[ref] = Item(ref=ref, trust="record", evidence=f"{self.site_bbl} {detail}", source=RecordSource(
            type="site_facts", ref=ref, label=f"Site facts, {self.lot_labels[self.site_bbl]}", detail=detail, bbl=self.site_bbl))
        self.fly_targets[ref] = FlyTarget(label=self.lot_labels[self.site_bbl], bbl=self.site_bbl,
                                          lat=_number(self.profile.get("lat")), lon=_number(self.profile.get("lon")))
        for neighbor in self.profile.get("neighbors") or []:
            bbl = str(neighbor.get("bbl") or "")
            if not bbl:
                continue
            ref, detail = f"neighbor:{bbl}", _flat({k: v for k, v in neighbor.items() if k != "bbl"})
            self.items[ref] = Item(ref=ref, trust="record", evidence=f"{bbl} {detail}", source=RecordSource(
                type="lot_facts", ref=ref, label=f"Lot facts, {self.lot_labels[bbl]}", detail=detail, bbl=bbl))
            self.fly_targets[ref] = FlyTarget(label=self.lot_labels[bbl], bbl=bbl)

    def _add_record(self, record: SiteRecord) -> None:
        detail = [self._scrub(record.text)]
        if self.as_of is None and record.status_today:
            detail.append(f"Status today: {record.status_today}.")
        detail += [f"Added {day or 'on an unstated date'}: {text}" for day, text in self._later_text(record)]
        text = " ".join(detail)
        label = self.lot_labels.get(record.bbl, f"lot {record.bbl}")
        self.items[record.id] = Item(
            ref=record.id, trust="record", evidence=f"{record.id} {record.date or ''} {label} {text}",
            source=RecordSource(type="public_record", ref=record.id, label=f"{record.dataset_name} {record.record_id}",
                                detail=text, date=record.date, bbl=record.bbl, url=record.url))
        self.fly_targets[record.id] = FlyTarget(label=f"{record.dataset_name} {record.record_id}, {label}", bbl=record.bbl)

    def _add_cases(self) -> None:
        if self.context.similar.status != "ok":
            return
        entries = [e for e in self.context.similar.value or [] if isinstance(e.get("case"), dict) and e["case"].get("id")]
        entries = [e for e in entries if self._dated_before(e["case"].get("date"))]
        self.cases = sorted(entries, key=lambda e: (e.get("similar") or {}).get("score") or 0, reverse=True)
        for entry in self.cases:
            case, similar = entry["case"], entry.get("similar") or {}
            status = case.get("cause_status") if case.get("cause_status") in ("reported", "under_investigation") else "unknown"
            ref = f"case:{case['id']}"
            self.items[ref] = Item(ref=ref, trust="case", evidence=json.dumps(entry, default=str), source=CaseSource(
                ref=ref, title=str(case.get("title") or case["id"]), date=case.get("date"), summary=case.get("summary"),
                cause_status=status, matched_on=[str(m) for m in similar.get("matched_on") or []],
                differs_on=[str(d) for d in similar.get("differs_on") or []], bbl=case.get("bbl"),
                lat=_number(case.get("lat")), lon=_number(case.get("lon")),
                reports=[CaseReport(name=str(s.get("name") or "a public report"), url=s.get("url"), date=s.get("date"))
                         for s in case.get("sources") or [] if isinstance(s, dict)]))
            self.fly_targets[ref] = FlyTarget(label=str(case.get("title") or case["id"]), bbl=case.get("bbl"),
                                              lat=_number(case.get("lat")), lon=_number(case.get("lon")))

    def _add_warnings(self) -> None:
        if self.context.warnings.status != "ok":
            return
        for warning in self.context.warnings.value or []:
            evidence_ids = [str(i) for i in warning.get("evidence_record_ids") or []]
            # A warning that rests on a record this view cannot see did not exist on the as-of day.
            if not warning.get("id") or not self._dated_before(warning.get("first_seen")) or self.after_as_of & set(evidence_ids):
                continue
            self.warnings.append(warning)
            ref = f"warning:{warning['id']}"
            self.items[ref] = Item(ref=ref, trust="warning", evidence=json.dumps(warning, default=str), source=WarningSource(
                ref=ref, rule_id=str(warning.get("rule_id") or ""), title=str(warning.get("title") or warning["id"]),
                explanation=warning.get("explanation"), hazard=warning.get("hazard"), severity=warning.get("severity"),
                first_seen=warning.get("first_seen"), evidence_record_ids=evidence_ids))

    def _add_actions(self) -> None:
        if self.context.actions.status != "ok":
            return
        for action in self.context.actions.value or []:
            if not action.get("id"):
                continue
            self.actions.append(action)
            ref = f"action:{action['id']}"
            self.items[ref] = Item(ref=ref, trust="action", evidence=json.dumps(action, default=str), source=ActionSource(
                ref=ref, title=str(action.get("title") or action["id"]), discipline=action.get("discipline"),
                why=action.get("why"), code_ref=action.get("code_ref"), proof_needed=action.get("proof_needed"),
                status=action.get("status"), life_safety=bool(action.get("life_safety"))))

    # ---- what the model reads ----

    def _actions_heading(self) -> str:
        kept = "prompts to act, not determinations; proof is never inferred from public data"
        if not self.project_open:
            return ("ACTION ITEMS (the lot's general list from the action rules, not a project's checklist: a project's own list "
                    f"follows its job type and scope and holds what its team added; {kept})")
        setup = self.context.project.value or {}
        scope = _flat([_words(work) for work in setup.get("work_types") or []]) or "not set"
        job, stage = (_words(setup.get(name) or "not set") for name in ("job_type", "stage"))
        return (f"PROJECT CHECKLIST (the open project's own items, the list its project screen shows; job type: "
                f"{job}; scope: {scope}; stage: {stage}; owner and status "
                f"are what the project's team recorded, not proof; {kept})")

    @staticmethod
    def _team_record(item: dict) -> str:
        added = (f" | added by the {_words(item['added_by_role'])}: {item.get('added_reason') or 'no reason given'}"
                 if item.get("added_by_role") else "")
        return f" | owner: {_words(item.get('owner_role') or 'not assigned')}{added}"

    def _shown_records(self) -> list[SiteRecord]:
        cited = {i for warning in self.warnings for i in warning.get("evidence_record_ids") or []}
        taken: dict[tuple[str, str], int] = {}
        shown = []
        for record in self.records:
            group = (record.bbl, record.dataset_key)
            if taken.get(group, 0) < RECORDS_SHOWN_PER_DATASET or record.id in cited:
                taken[group] = taken.get(group, 0) + 1
                shown.append(record)
        return shown

    def _not_loaded(self, name: str) -> Optional[str]:
        piece = self.piece(name)
        return None if piece.status == "ok" else f"could not be loaded ({piece.reason or piece.status}): nothing is known, which is not the same as none"

    def case_line(self, entry: dict) -> str:
        case, similar = entry["case"], entry.get("similar") or {}
        cause = {"reported": f"as publicly reported: {case.get('cause_as_reported') or 'no cause given'}",
                 "under_investigation": "under investigation"}.get(case.get("cause_status"), "no cause publicly reported")
        return (f"[case:{case['id']}] {case.get('date') or 'undated'} | {case.get('title')} | hazards: {_flat(case.get('hazards') or [])}"
                f" | severity {case.get('severity')} | similarity {similar.get('score')} | matches on: {_flat(similar.get('matched_on') or [])}"
                f" | differs on: {_flat(similar.get('differs_on') or [])} | {case.get('summary') or ''} | cause: {cause}")

    def digest(self) -> str:
        out = [f"SITE: {self.lot_labels[self.site_bbl]}" + (f" | data pulled {self.context.pulled_at[:10]}" if self.context.pulled_at else ""),
               f"AS-OF VIEW: only what is dated before {self.as_of}. Later records, past cases and warnings, later-written "
               "text and today's statuses are not here, and you have no web search in this view. Answer as a reader "
               "on that day: say nothing about anything on or after it, whatever you may know." if self.as_of else
               "VIEW: as loaded. Every status is today's, not the status on the record's date.",
               "", "SITE FACTS (compiled from city data, which can lag what is on the ground)"]
        site = self.items.get(f"site:{self.site_bbl}")
        out.append(f"[{site.ref}] {site.source.detail}" if site else
                   f"the site profile {self._not_loaded('profile') or 'is empty'}")
        out += [f"[{ref}] {item.source.label}: {item.source.detail}" for ref, item in self.items.items() if ref.startswith("neighbor:")]
        shown = self._shown_records()
        out += ["", "DATASETS QUERIED, by lot (key: count)"]
        for bbl, label in self.lot_labels.items():
            checks = []
            for (lot, key), dataset in self.datasets.items():
                if lot != bbl:
                    continue
                if dataset.status != "ok":
                    checks.append(f"{key}: {dataset.status} (nothing is known; not zero)")
                else:
                    listed = sum(1 for r in shown if r.bbl == bbl and r.dataset_key == key)
                    checks.append(f"{key}: {'at least ' if dataset.capped else ''}{dataset.count}"
                                  + (f" ({listed} listed below)" if listed < (dataset.count or 0) else "")
                                  + (" (hit the row cap: the oldest records are missing)" if dataset.capped else ""))
            if checks:
                out.append(f"{label} [bbl {bbl}]: " + "; ".join(checks))
        out += ["", "RECORDS, newest first (id | lot | date | text). Records not listed can be searched and counted."]
        out += [f"[{r.id}] lot {r.bbl} | {r.date or 'undated'} | {self.items[r.id].source.detail}" for r in shown]
        out += ["", "EARLY WARNINGS (results of rules over the dated records: patterns, never predictions)"]
        out += [self._not_loaded("warnings")] if self._not_loaded("warnings") else [
            f"[warning:{w['id']}] rule {w.get('rule_id')} | hazard {w.get('hazard')} | severity {w.get('severity')} | first seen "
            f"{w.get('first_seen')} | {w.get('title')}: {w.get('explanation')} | rests on records: {_flat(w.get('evidence_record_ids') or [])}"
            for w in self.warnings] or ["none in this view"]
        if self.warnings_may_be_incomplete and not self._not_loaded("warnings"):
            which = ("RULES THAT COULD NOT BE CHECKED: " + "; ".join(self.rules_not_checked) if self.rules_not_checked
                     else "WHETHER EVERY RULE RAN IS NOT KNOWN: the rule checks could not be loaded")
            out.append(f"{which}. The list above may be incomplete. To say how many warnings there are, use "
                       "dataset_check with the key early_warnings.")
        out += ["", "SIMILAR PAST CASES, closest first (a cause only as publicly reported, or under investigation)"]
        out += [self._not_loaded("similar")] if self._not_loaded("similar") else (
            [self.case_line(entry) for entry in self.cases[:CASES_SHOWN]] or ["none in this view"])
        if len(self.cases) > CASES_SHOWN:
            out.append(f"{len(self.cases) - CASES_SHOWN} more can be reached with search_similar_cases.")
        out += ["", self._actions_heading()]
        out += [self._not_loaded("actions")] if self._not_loaded("actions") else [
            f"[action:{a['id']}] {a.get('discipline')} | {a.get('title')} | why: {a.get('why')} | code: {a.get('code_ref')} | proof "
            f"needed: {a.get('proof_needed')} | status: {a.get('status')} | life safety: {'yes' if a.get('life_safety') else 'no'}"
            + (self._team_record(a) if self.project_open else "")
            for a in self.actions] or ["none on this project yet" if self.project_open else "none in this view"]
        if self.project_unread:
            out.append(f"THE OPEN PROJECT'S CHECKLIST COULD NOT BE READ ({self.project_unread}). The items above are the lot's "
                       "general list, not the project's checklist: say so, and never say what is or is not on the project's checklist.")
        out += ["", "MAP LAYERS the page can show or hide (layer id: name | hazard)"]
        out += [f"{layer_id}: {name} | {self.layer_hazards.get(layer_id) or 'no hazard given'}" for layer_id, name in self.layers.items()] or [
            f"the layer list {self._not_loaded('layers') or 'is empty'}"]
        return "\n".join(out)
