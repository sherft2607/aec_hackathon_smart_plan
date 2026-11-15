"""What the chat reads about one site: the seam between the chat and the rest of the API.

The chat never pulls data itself. A loader hands it one `SiteContext`, built from the same functions
the site routes use, so the chat and the screen cannot disagree. Every piece that can fail to load
is a `Loaded`, because "could not load" and "loaded, and empty" must never look the same: the chat
turns the first into "unknown" and only the second into "none found".

The dicts are the shared contracts (SiteProfile, SimilarCase, Case, Warning, ActionItem,
LayerCatalogEntry) as plain JSON objects, so this module does not depend on how they are modeled.
"""

from dataclasses import dataclass, field
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Loaded(Generic[T]):
    status: str  # "ok", "error" (the load failed) or "not_available" (that part of the app is not built or not run)
    value: Optional[T] = None
    reason: Optional[str] = None

    @classmethod
    def ok(cls, value: T) -> "Loaded[T]":
        return cls("ok", value)

    @classmethod
    def failed(cls, reason: str) -> "Loaded[T]":
        return cls("error", None, reason)

    @classmethod
    def not_available(cls, reason: str) -> "Loaded[T]":
        return cls("not_available", None, reason)


@dataclass(frozen=True)
class SiteRecord:
    """One dated public record of the site or a touching lot."""

    id: str  # "<dataset_key>:<record_id>", unique in the context
    dataset_key: str
    dataset_name: str
    record_id: str
    bbl: str
    date: Optional[str]  # ISO day; None when the dataset gives none
    text: str  # the record's own words
    url: Optional[str] = None  # the query that returned it
    status_today: Optional[str] = None  # the datasets keep only the current status
    later_text: tuple[tuple[Optional[str], str], ...] = ()  # (day it was written, text): e.g. a resolution added later


@dataclass(frozen=True)
class DatasetStatus:
    """One dataset queried for one lot."""

    bbl: str
    key: str
    name: str
    status: str  # "ok", "error" or "skipped"
    capped: bool = False  # the pull hit its row cap: counts are a floor and the oldest records are missing
    count: Optional[int] = None  # the source's own count, used only when the records were not handed over
    reason: Optional[str] = None
    url: Optional[str] = None


@dataclass
class SiteContext:
    bbl: str
    as_of: Optional[str] = None  # ISO day: nothing dated on or after it may be used
    pulled_at: Optional[str] = None
    profile: Loaded[dict] = Loaded.not_available("the site profile is not loaded")
    records: list[SiteRecord] = field(default_factory=list)
    datasets: list[DatasetStatus] = field(default_factory=list)
    similar: Loaded[list[dict]] = Loaded.not_available("similar cases are not loaded")  # each {"similar": .., "case": ..}
    warnings: Loaded[list[dict]] = Loaded.not_available("early warnings are not loaded")
    # One entry per early-warning rule: {"rule_id", "title", "status": "ok" | "error" | "not_applicable", ..}.
    # A rule with status "error" could not run, so the warnings list may be missing its result.
    warning_checks: Loaded[list[dict]] = Loaded.not_available("the early-warning rule checks are not loaded")
    # The lot's general action list, or the open project's own checklist when `project` loaded.
    actions: Loaded[list[dict]] = Loaded.not_available("action items are not loaded")
    # The open project's setup ({"stage", "job_type", "construction_type", "work_types"}), when the page has a
    # project open on this lot. "error" means a project is open and could not be read.
    project: Loaded[dict] = Loaded.not_available("no project is open")
    layers: Loaded[list[dict]] = Loaded.not_available("the layer list is not loaded")
    sample: bool = False  # some of this is the labelled sample data, not live data for the site


class SiteContextUnavailable(Exception):
    """No context can be built for this site (unknown lot, or the site routes are not wired in)."""


# (bbl, job_type, stage, as_of, project_id) -> SiteContext. Set by the app once the site routes exist.
ContextLoader = Callable[[str, Optional[str], Optional[str], Optional[str], Optional[str]], SiteContext]
