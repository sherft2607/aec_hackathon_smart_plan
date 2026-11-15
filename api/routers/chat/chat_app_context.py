"""The site as the app's own routes serve it: each part is read through the function its route uses,
so the chat and the page cannot disagree about what is on record.

While a part is still the labelled sample (its owner's module has not landed), it describes the sample
site only. For any other lot that part is "not available": sample data is never shown as another site's.
A part that fails to load is a failure with its reason, never an empty list.
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, TypeAdapter

from api.contracts import WarningRuleCheck

from api.routers.chat.chat_fixture_context import datasets_from_profile, similar_entries
from api.routers.chat.chat_project_checklist import open_project
from api.routers.chat.chat_site_context import Loaded, SiteContext, SiteContextUnavailable
from api.routers.layers_router import load_layer_catalog
from api.routers.router_data import DataUnavailable, data_root, owner_function
from api.routers.sites_router import load_site_part
from api.stubs import fixture

SAMPLE_OF_ANOTHER_SITE = "only sample data is available, and it describes another site"
# What GET /api/sites/{bbl}/warnings/checks serves: one entry per early-warning rule, run or not.
RULE_CHECKS_SOURCE = ("early_warning.api", "site_warning_checks")
_RULE_CHECKS = TypeAdapter(list[WarningRuleCheck])


def _plain(value: Any) -> Any:
    """Contract models as the plain dicts and lists the chat reads."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_plain(entry) for entry in value]
    return value


def rule_checks(bbl: str, as_of: Optional[str], is_sample_site: bool) -> tuple[Loaded, bool]:
    """Whether each early-warning rule could run, and whether that is the labelled sample.

    `as_of` is a day the site routes have already accepted. A failure is a failure with its reason:
    the chat then says it cannot tell whether every rule ran, never that they all did.
    """
    where = ".".join(RULE_CHECKS_SOURCE)
    try:
        build = owner_function(*RULE_CHECKS_SOURCE)
        if build is None and not is_sample_site:
            return Loaded.not_available(SAMPLE_OF_ANOTHER_SITE), False
        answer = fixture("warning_checks") if build is None else build(bbl, as_of=date.fromisoformat(as_of) if as_of else None)
        return Loaded.ok(_plain(_RULE_CHECKS.validate_python(answer))), build is None
    except DataUnavailable as error:
        return Loaded.failed(str(error)), False
    except HTTPException as error:
        return Loaded.failed(f"{where}: {error.detail}"), False
    except Exception as error:  # any failure is reported as a failure, never read as "every rule ran"
        return Loaded.failed(f"{where} could not answer ({type(error).__name__})"), False


def app_context(bbl: str, job_type: Optional[str], stage: Optional[str], as_of: Optional[str],
                project_id: Optional[str] = None) -> SiteContext:
    """Raises SiteContextUnavailable when the site's profile cannot be had, and fastapi.HTTPException(422)
    for a lot or an option the site routes refuse.

    With a project open on this lot, the job type and stage the page did not send are the project's, and
    the action items are the project's own checklist, so the chat and the project screen show one list.
    """
    project, checklist = open_project(project_id, bbl, as_of)
    if project.status == "ok":
        job_type, stage = job_type or project.value.get("job_type"), stage or project.value.get("stage")
    is_sample_site = bbl == str(fixture("site_profile").get("bbl"))
    used_sample = False

    def part(name: str, **options: Optional[str]) -> Loaded:
        nonlocal used_sample
        try:
            loaded = load_site_part(name, bbl, **options)
        except DataUnavailable as error:
            return Loaded.failed(str(error))
        if loaded.sample and not is_sample_site:
            return Loaded.not_available(SAMPLE_OF_ANOTHER_SITE)
        used_sample = used_sample or loaded.sample
        return Loaded.ok(_plain(loaded.data))

    profile = part("profile", job_type=job_type, stage=stage, as_of=as_of)
    if profile.status != "ok":
        raise SiteContextUnavailable(profile.reason or "the site profile could not be loaded")
    try:
        layers = Loaded.ok(_plain(load_layer_catalog(data_root()).data))
    except DataUnavailable as error:
        layers = Loaded.failed(str(error))
    warnings = part("warnings", as_of=as_of)
    # The rule checks qualify the warnings list, so they are read only when there is a list to qualify.
    checks, checks_are_sample = rule_checks(bbl, as_of, is_sample_site) if warnings.status == "ok" else (
        Loaded.not_available("the early warnings did not load"), False)
    used_sample = used_sample or checks_are_sample
    return SiteContext(
        bbl=bbl, as_of=as_of, profile=profile, records=[], datasets=datasets_from_profile(profile.value, bbl),
        similar=similar_entries(part("similar")), warnings=warnings, warning_checks=checks,
        actions=checklist if project.status == "ok" else part("actions", stage=stage, job_type=job_type),
        project=project, layers=layers, sample=used_sample)
