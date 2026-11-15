"""A stand-in for the model while the server has no key: a typed question gets a prepared answer.

No model runs. The question is matched by keyword to a search, a count, the site's warnings, action
items or closest cases, or a page action, and the result is a proposed answer in the same shape a
model submits, so it goes through the same checks. A question nothing matches gets None: the mock
never makes an answer up, and it never stands in for a web search.
"""

import re
from typing import Optional

from api.routers.chat.chat_case_search import HAZARDS
from api.routers.chat.chat_site_view import SiteView

_COUNT_CUE = re.compile(r"\bhow many\b|\bcount\b|\bnumber of\b", re.I)
_SEARCH_CUE = re.compile(r"\b(?:search(?:\s+the)?(?:\s+records?)?(?:\s+for)?|find|look\s+up|look\s+for|"
                         r"mention(?:s|ing|ed)?|contain(?:s|ing)?|records?\s+(?:about|with|for|on))\b(.*)", re.I)
_QUOTED = re.compile(r"[\"“]([^\"“”]{2,60})[\"”]")
_FILLER = set("a an any all the of for in on at about with records record that which mention mentions mentioning "
              "contain contains containing please site lot lots this these those here there is are do does".split())
_CASE_CUE = re.compile(r"\bsimilar\b|\bpast cases?\b|\bcases?\b|\bprecedents?\b|\bhappened (?:before|elsewhere)\b", re.I)
_WARNING_CUE = re.compile(r"\bwarnings?\b|\bearly[- ]warning\b|\bred flags?\b|\bpatterns?\b", re.I)
_ACTION_CUE = re.compile(r"\baction(?:s| items?)?\b|\bchecklist\b|\bto[- ]do\b|\bwhat (?:should|do|must)\b.*\bdo\b|\bwhat (?:should|do) (?:we|i)\b|"
                         r"\bnext steps?\b|\bduties\b|\bresponsib\w+\b", re.I)
_PIN_CUE = re.compile(r"\b(?:pin|save)\b.*\b(?:answer|this|that|project)\b|\bpin (?:it|that|this)\b", re.I)
_LAYER_CUE = re.compile(r"\b(show|turn on|display|add|hide|turn off|remove)\b(.*)", re.I)
_FLY_CUE = re.compile(r"\b(?:fly|zoom|go|take me|jump)\s+to\b(.*)", re.I)
_LAYER_FILLER = set("layer layers map and next older zone fly zoom similar cases case".split())
_DISCIPLINES = ("architect", "structural", "geotech", "contractor")


def _item(kind: str, **fields) -> dict:
    return {"kind": kind, "text": "", "refs": [], "bbl": "", "dataset_key": "", "date_from": "", "date_to": "",
            "hazard": "", "severity_min": "", "notice": "", **fields}


def _says(text: str, *refs: str) -> dict:
    return _item("statement", text=text, refs=list(refs))


def _action(kind: str, **fields) -> dict:
    return {"type": kind, "layer_id": "", "on": True, "ref": "", **fields}


def _hazard(question: str) -> str:
    plain = question.lower().replace("-", " ")
    return next((h for h in HAZARDS if h.replace("_", " ") in plain), "")


def _dataset(view: SiteView, question: str) -> str:
    """The dataset the question names most fully by its key or its name ('ECB violations', 'complaints')."""
    asked = set(re.findall(r"[a-z0-9]+", question.lower()))
    asked |= {word.rstrip("s") for word in asked}
    best, best_score = "", 0
    for (_, key), dataset in view.datasets.items():
        words = set(re.findall(r"[a-z0-9]+", f"{key.replace('_', ' ')} {dataset.name}".lower())) - _FILLER - {"dob", "nyc", "to", "now"}
        score = len(asked & ({w for w in words if len(w) > 2} | {w.rstrip("s") for w in words if len(w) > 3}))
        if score > best_score:
            best, best_score = key, score
    return best


def _search_words(question: str) -> list[str]:
    quoted, cue = _QUOTED.search(question), _SEARCH_CUE.search(question)
    if quoted:
        return quoted.group(1).split()[:6]
    if not cue:
        return []
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", cue.group(1)) if w.lower() not in _FILLER][:6]


def _layer_actions(view: SiteView, question: str) -> list[dict]:
    cue = _LAYER_CUE.search(question)
    if not cue or not view.layers:
        return []
    on = cue.group(1).lower() in ("show", "turn on", "display", "add")
    asked = {w for w in re.findall(r"[a-z0-9]+", cue.group(2).lower()) if len(w) > 2} - _FILLER - _LAYER_FILLER

    def words(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))

    # A layer named in the question; failing that, the layers showing the hazard it names.
    named = [layer_id for layer_id, name in view.layers.items() if asked & words(f"{layer_id} {name}")]
    chosen = named or [layer_id for layer_id in view.layers if asked & words(view.layer_hazards.get(layer_id, ""))]
    return [_action("toggle_layer", layer_id=layer_id, on=on) for layer_id in chosen][:4]


def _fly_action(view: SiteView, question: str) -> list[dict]:
    cue = _FLY_CUE.search(question)
    if not cue:
        return []
    asked = cue.group(1).lower()
    for ref, target in view.fly_targets.items():
        if ref.lower() in asked or ref.split(":", 1)[-1].lower() in asked.split():
            return [_action("fly_to", ref=ref)]
    return [_action("fly_to", ref=f"site:{view.site_bbl}")] if re.search(r"\bsite\b", asked) else []


def propose(view: SiteView, question: str) -> Optional[dict]:
    """A proposed answer ({"items": [...], "actions": [...]}) for the question, or None when nothing prepared matches it."""
    if _PIN_CUE.search(question):  # "pin that": the answer the reader was just shown
        return {"items": [], "actions": [_action("pin_answer", ref="previous")]}
    actions = _layer_actions(view, question) or _fly_action(view, question)
    if actions:
        return {"items": [], "actions": actions}
    dataset, words = _dataset(view, question), _search_words(question)
    if _COUNT_CUE.search(question) and dataset:
        return {"items": [_item("dataset_check", bbl=bbl, dataset_key=key) for (bbl, key) in view.datasets if key == dataset][:8],
                "actions": []}
    if _CASE_CUE.search(question):
        case_words = [w for w in words if not _CASE_CUE.fullmatch(w) and w.lower() not in ("similar", "past")]
        return {"items": [_item("case_search", text=" ".join(case_words)[:60], hazard=_hazard(question))], "actions": []}
    if words:
        words = [w for w in words if w.lower() not in dataset.replace("_", " ").split()] or words
        return {"items": [_item("record_search", text=" ".join(words)[:60], dataset_key=dataset)], "actions": []}
    if _WARNING_CUE.search(question):
        items = [_says(f'Early warning "{w.get("title")}": "{w.get("explanation")}"', f"warning:{w['id']}") for w in view.warnings[:6]]
        # With nothing to quote, or a rule that could not run, the server says what is known: none, unknown or a floor.
        if not items or view.warnings_may_be_incomplete:
            items.append(_item("dataset_check", dataset_key="early_warnings"))
        return {"items": items, "actions": []}
    if _ACTION_CUE.search(question):
        wanted = [d for d in _DISCIPLINES if d in question.lower()]
        chosen = [a for a in view.actions if not wanted or a.get("discipline") in wanted]
        chosen.sort(key=lambda a: not a.get("life_safety"))  # life safety first
        # With a project open these are its own checklist items, said with the owner and status its team recorded.
        items = [_says((f'Project checklist item (owner: {str(a.get("owner_role") or "not assigned").replace("_", " ")}; status: '
                        f'{str(a.get("status")).replace("_", " ")})'
                        if view.project_open else f'Action item ({a.get("discipline")})')
                       + f': "{a.get("title")}". Proof needed: "{a.get("proof_needed")}".', f"action:{a['id']}") for a in chosen[:6]]
        if items and view.project_unread:  # the count sentence says this is the lot's general list, not the project's
            items.append(_item("dataset_check", dataset_key="action_items"))
        if not items and view.actions:  # the list loaded, with nothing for the discipline asked about
            items = [_item("gap", text=f"an action item for the {' or '.join(wanted)} discipline")]
        return {"items": items or [_item("dataset_check", dataset_key="action_items")], "actions": []}
    if dataset:
        return {"items": [_item("dataset_check", bbl=bbl, dataset_key=key) for (bbl, key) in view.datasets if key == dataset][:8],
                "actions": []}
    return None
