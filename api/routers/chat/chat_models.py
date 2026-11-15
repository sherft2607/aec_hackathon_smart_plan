"""The chat's request and answer shapes.

An answer is a list of parts, and a part's kind says where it came from. The kinds are separate
types on purpose: a `record` part can only hold public records and site facts, a `case` part only
past cases, a `warning` part only early-warning rule results, an `action` part only action items,
and a `lead` part only web results. So a web page can never be shown as a record, and a rule's
pattern can never be shown as a fact on file.

These shapes are the chat's own; they are not part of the shared contracts.
"""

from datetime import date
from typing import Annotated, Literal, Optional, Union
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_QUESTION_CHARS = 1000
MAX_EARLIER_EXCHANGES = 8
MAX_EARLIER_ANSWER_CHARS = 4000
MAX_HISTORY_CHARS = 12000


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- the request ----


class Exchange(_Closed):
    """One earlier question and the text of the answer the reader saw."""

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    answer: str = Field(max_length=MAX_EARLIER_ANSWER_CHARS)


class ChatRequest(_Closed):
    """Over any limit the request is refused (HTTP 422), never cut to fit."""

    bbl: str = Field(pattern=r"^\d{10}$", description="The site's lot.")
    job_type: Optional[str] = Field(None, max_length=60)
    stage: Optional[str] = Field(None, max_length=40)
    as_of: Optional[date] = Field(None, description="The page's as-of day: nothing dated on or after it is used.")
    project_id: Optional[str] = Field(None, max_length=80, description="The open project, if any: needed to pin an answer.")
    history: list[Exchange] = Field(default_factory=list, max_length=MAX_EARLIER_EXCHANGES)
    question: str = Field("", max_length=MAX_QUESTION_CHARS)
    example_id: Optional[str] = Field(None, max_length=60, description="Ask for a saved example instead of a live answer.")

    @model_validator(mode="after")
    def _has_a_question_and_fits(self) -> "ChatRequest":
        if not self.question.strip() and not self.example_id:
            raise ValueError("a question or an example_id is required")
        size = sum(len(turn.question) + len(turn.answer) for turn in self.history)
        if size > MAX_HISTORY_CHARS:
            raise ValueError(f"the conversation is over {MAX_HISTORY_CHARS} characters: start a new chat")
        return self


# ---- sources ----


class RecordSource(_Closed):
    """A public record, a dataset count, or the site's facts. Its link is the data's own, never one the model wrote."""

    type: Literal["public_record", "site_facts", "lot_facts", "dataset_count"]
    ref: str
    label: str
    detail: Optional[str] = None
    date: Optional[str] = None
    bbl: Optional[str] = None
    url: Optional[str] = None


class CaseReport(_Closed):
    name: str
    url: Optional[str] = None
    date: Optional[str] = None


class CaseSource(_Closed):
    """A past case from the case library. What it says rests on the public reports listed with it."""

    type: Literal["past_case"] = "past_case"
    ref: str
    title: str
    date: Optional[str] = None
    summary: Optional[str] = None
    cause_status: Literal["reported", "under_investigation", "unknown"] = "unknown"
    matched_on: list[str] = Field(default_factory=list)
    differs_on: list[str] = Field(default_factory=list)
    bbl: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    reports: list[CaseReport] = Field(default_factory=list)


class WarningSource(_Closed):
    """The result of an early-warning rule: a pattern in the dated records, not a fact on file and not a prediction."""

    type: Literal["early_warning"] = "early_warning"
    ref: str
    rule_id: str
    title: str
    explanation: Optional[str] = None
    hazard: Optional[str] = None
    severity: Optional[int] = None
    first_seen: Optional[str] = None
    evidence_record_ids: list[str] = Field(default_factory=list)


class ActionSource(_Closed):
    """An action item a rule produced for a discipline. It is a prompt to act, not a determination."""

    type: Literal["action_item"] = "action_item"
    ref: str
    title: str
    discipline: Optional[str] = None
    why: Optional[str] = None
    code_ref: Optional[str] = None
    proof_needed: Optional[str] = None
    status: Optional[str] = None
    life_safety: bool = False


class WebSource(_Closed):
    """A web search result the model received in this call."""

    type: Literal["web_result"] = "web_result"
    url: str
    title: str
    page_age: Optional[str] = None
    official: bool = Field(description="The host is a city, state or federal government site. A hint about the host only.")

    @field_validator("url")
    @classmethod
    def _is_a_web_address(cls, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("not a web address")
        return url


class QueriedDataset(_Closed):
    key: str
    name: str
    bbl: Optional[str] = None
    url: Optional[str] = None


# ---- answer parts ----


class RecordPart(_Closed):
    """Rests on public records, a dataset count, or the site's facts."""

    kind: Literal["record"] = "record"
    text: str
    sources: list[RecordSource] = Field(min_length=1)


class CasePart(_Closed):
    """Rests on past cases from the case library, as publicly reported."""

    kind: Literal["case"] = "case"
    text: str
    sources: list[CaseSource] = Field(min_length=1)


class WarningPart(_Closed):
    """Rests on early-warning rule results: patterns, never predictions."""

    kind: Literal["warning"] = "warning"
    text: str
    sources: list[WarningSource] = Field(min_length=1)


class ActionPart(_Closed):
    """Rests on action items from the action rules."""

    kind: Literal["action"] = "action"
    text: str
    sources: list[ActionSource] = Field(min_length=1)


class LeadPart(_Closed):
    """From the web. Not checked by us; never evidence."""

    kind: Literal["lead"] = "lead"
    text: str
    sources: list[WebSource] = Field(min_length=1)


class NotFoundPart(_Closed):
    """Looked for and nothing found, with what was searched named."""

    kind: Literal["not_found"] = "not_found"
    text: str
    queried: list[QueriedDataset] = Field(min_length=1)


class UnknownPart(_Closed):
    """A query or a load failed or was skipped: nothing is known. Never zero."""

    kind: Literal["unknown"] = "unknown"
    text: str
    queried: list[QueriedDataset] = Field(min_length=1)


NoticeCode = Literal[
    "not_a_determination", "names_withheld", "cause_not_established", "out_of_scope", "status_is_todays",
    "not_a_prediction", "warning_rules_unchecked", "complaints_overlap", "web_off_as_of", "held_back", "after_as_of", "no_answer",
    "page_action", "action_dropped", "pin_needs_project", "pin_needs_answer", "saved_example", "mock_answer", "mock_no_match", "live_failed",
    "first_pass",
]


class NoticePart(_Closed):
    """A status line the server wrote. The model can ask for one by code; it cannot word one."""

    kind: Literal["notice"] = "notice"
    code: NoticeCode
    text: str


AnswerPart = Annotated[
    Union[RecordPart, CasePart, WarningPart, ActionPart, LeadPart, NotFoundPart, UnknownPart, NoticePart],
    Field(discriminator="kind")]


# ---- page actions: things the page does beside showing the answer ----


class ToggleLayerAction(_Closed):
    type: Literal["toggle_layer"] = "toggle_layer"
    layer_id: str
    name: str
    on: bool


class FlyToAction(_Closed):
    """Move the map to something the answer is about. At least one of bbl or lat and lon is set."""

    type: Literal["fly_to"] = "fly_to"
    ref: str
    label: str
    bbl: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class PinAnswerAction(_Closed):
    """Save this answer to the open project. The page does the saving, as the person signed in."""

    type: Literal["pin_answer"] = "pin_answer"
    project_id: str
    target: Literal["this", "previous"] = Field(description="this answer, or the one the reader saw just before it")


PageAction = Annotated[Union[ToggleLayerAction, FlyToAction, PinAnswerAction], Field(discriminator="type")]


class ExampleQuestion(_Closed):
    id: str
    question: str


class ChatUsage(_Closed):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0


class ChatAnswer(_Closed):
    mode: Literal["live", "saved", "mock"] = Field(
        description="live: a model answered now. saved: an example written ahead of time, checked against this "
        "site's data. mock: no model was called (no key on the server, or the call failed); the question was "
        "matched by keyword to a prepared answer.")
    question: str
    parts: list[AnswerPart]
    actions: list[PageAction] = Field(default_factory=list, description="For the page to carry out, in order.")
    plain_text: str = Field(description="The parts as one text, each prefixed by where it came from. For a voice client.")
    as_of: Optional[str] = None
    web_search: Literal["used", "not_used", "off_as_of", "off"]
    examples: list[ExampleQuestion] = Field(default_factory=list)
    usage: Optional[ChatUsage] = None
