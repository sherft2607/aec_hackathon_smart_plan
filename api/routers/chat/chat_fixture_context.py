"""A site context read from contracts/fixtures/, for building and demoing before the site routes are real.

The fixtures describe one site. For any other lot this raises SiteContextUnavailable, so fixture
data is never shown as another site's. The fixtures carry no list of the site's records, so the
record search has nothing to search here and says so; dataset counts are the fixture's own.
"""

import json
from pathlib import Path
from typing import Optional

from api.routers.chat.chat_site_context import DatasetStatus, Loaded, SiteContext, SiteContextUnavailable

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


def _read(name: str) -> Loaded:
    try:
        return Loaded.ok(json.loads((FIXTURES / f"{name}.json").read_text()))
    except (OSError, ValueError) as error:
        return Loaded.failed(type(error).__name__)


def datasets_from_profile(profile: dict, bbl: str) -> list[DatasetStatus]:
    """The contract's per-site DatasetStatus as the chat's: capped is ok with a floor, an error stays an error."""
    return [DatasetStatus(bbl=bbl, key=d["key"], name=d.get("name") or d["key"], status="error" if d.get("status") == "error" else "ok",
                          capped=d.get("status") == "capped", count=d.get("count"), url=d.get("source_url"))
            for d in profile.get("datasets") or [] if d.get("key")]


def similar_entries(similar: Loaded) -> Loaded:
    """The contract's SimilarCases as the chat's list of {"similar": .., "case": ..}."""
    if similar.status != "ok":
        return similar
    results = (similar.value or {}).get("results") or []
    return Loaded.ok([{"similar": {k: v for k, v in result.items() if k != "case"}, "case": result.get("case") or {}}
                      for result in results])


def fixture_context(bbl: str, job_type: Optional[str], stage: Optional[str], as_of: Optional[str],
                    project_id: Optional[str] = None) -> SiteContext:
    """The sample site. `project_id` is not read: the sample files hold no project, so the items are the lot's list."""
    profile = _read("site_profile")
    if profile.status != "ok" or profile.value.get("bbl") != bbl:
        raise SiteContextUnavailable(f"the fixtures hold no site {bbl}")
    return SiteContext(
        bbl=bbl, as_of=as_of, profile=profile, records=[], datasets=datasets_from_profile(profile.value, bbl),
        similar=similar_entries(_read("similar_cases")), warnings=_read("warnings"),
        warning_checks=_read("warning_checks"), actions=_read("actions"),
        layers=_read("layer_catalog"), sample=True)
