"""The open project as the chat reads it: its setup and its own checklist, read from the project store.

The project screen shows the project's checklist: the items drafted for its job type and scope, with the
owner and status its team set, plus any item a confirmed document added. The chat reads that same list
through the store's own read, so the two cannot disagree. Members' names are left out: the chat only
needs roles.

A project that is open and cannot be read is a failure with its reason, never "no project".
"""

from typing import Optional

from api.routers.chat.chat_site_context import Loaded
from api.routers.projects_router import project_store
from api.store.project_store import NotFound

NO_PROJECT = "no project is open"
ANOTHER_LOT = "the open project is for another lot"
# A project keeps only today's state of each item, so a view as of an earlier day cannot use it.
NOT_IN_AS_OF = "the project's checklist is today's, so a view as of an earlier day does not use it"
_SETUP = ("stage", "job_type", "construction_type", "work_types")


def open_project(project_id: Optional[str], bbl: str, as_of: Optional[str]) -> tuple[Loaded, Loaded]:
    """(the project's setup, its checklist items). Both are "ok" together, or neither is."""

    def neither(loaded: Loaded) -> tuple[Loaded, Loaded]:
        return loaded, loaded

    if not project_id:
        return neither(Loaded.not_available(NO_PROJECT))
    if as_of:
        return neither(Loaded.not_available(NOT_IN_AS_OF))
    try:
        project = project_store().get_project(project_id)
    except NotFound:
        return neither(Loaded.failed("the project store does not hold the project the page has open"))
    except Exception as error:  # a store that cannot answer is a failure, never read as "no project"
        return neither(Loaded.failed(f"the project store could not answer ({type(error).__name__})"))
    if str(project.get("site_bbl")) != bbl:
        return neither(Loaded.not_available(ANOTHER_LOT))
    return Loaded.ok({name: project.get(name) for name in _SETUP}), Loaded.ok(list(project.get("items") or []))
