"""Projects: create one, read it (ETag = version, for polling), add or update items, notes, pins, the model.

There are no accounts: each tab acts as a role, and the store refuses a note, pin or owner in a role the
project has no member for. Bodies are the contract models; the store checks caps, so this file only
maps its errors to HTTP and returns the whole project.
"""

import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from api.contracts import ActionItem, ActionItemUpdate, NoteCreate, PinCreate, Project, ProjectCreate, StructuralModel
from api.routers.router_data import DataUnavailable, owner_function
from api.store.project_store import UNCHANGED, NotFound, ProjectStore, ProjectStoreError

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "store" / "data" / "projects.sqlite"  # gitignored

projects_router = APIRouter(prefix="/api/projects")


@lru_cache(maxsize=1)
def project_store() -> ProjectStore:
    return ProjectStore(os.environ.get("FORESITE_PROJECTS_DB", _DEFAULT_DB))


def _run(action, *args):
    try:
        return action(*args)
    except NotFound as error:
        raise HTTPException(404, str(error)) from None
    except ProjectStoreError as error:
        raise HTTPException(422, str(error)) from None
    except sqlite3.IntegrityError:
        # The store checks every value first, and rebuilds an older file when it opens, so this is a file
        # changed under a running server. A restart rebuilds it; deleting it would lose every project.
        raise HTTPException(422, "the project store file refused this value; restart the API so it updates the file "
                                 "(see api/store/README.md)") from None


def _etag(version: int) -> str:
    return f'"v{version}"'


def _answer(response: Response, store: ProjectStore, project_id: str) -> dict:
    """The whole project, with the ETag of the very version it shows."""
    project, version = _run(store.snapshot, project_id)
    response.headers["ETag"] = _etag(version)
    return project


@projects_router.post("", response_model=Project)
def create_project(body: ProjectCreate, response: Response, store: ProjectStore = Depends(project_store)):
    members = [member.model_dump() for member in body.members]
    project = _run(store.create_project, body.name, body.site_bbl, body.stage, members, body.job_type,
                   body.construction_type, list(body.work_types or []), body.excavation_depth_ft, body.proposed_storeys)
    return _answer(response, store, project["id"])


@projects_router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, request: Request, response: Response, store: ProjectStore = Depends(project_store)):
    # A tab polls with If-None-Match; while nothing has changed it gets 304 and no body. Read from the
    # request rather than declared, so the published API stays the stubs'.
    etag = _etag(_run(store.version, project_id))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return _answer(response, store, project_id)


@projects_router.post("/{project_id}/items", response_model=Project)
def add_items(project_id: str, body: list[ActionItem], response: Response, store: ProjectStore = Depends(project_store)):
    # Adds the site's action items; one already on the project keeps its status and owner.
    _run(store.add_items, project_id, [item.model_dump() for item in body])
    return _answer(response, store, project_id)


@projects_router.patch("/{project_id}/items", response_model=Project)
def update_items(project_id: str, body: list[ActionItemUpdate], response: Response,
                 store: ProjectStore = Depends(project_store)):
    # All or nothing. owner_role sent as null unassigns the item; left out, it stays as it is.
    updates = [{"id": update.id, "status": update.status, "by_role": update.by_role,
                "owner_role": update.owner_role if "owner_role" in update.model_fields_set else UNCHANGED}
               for update in body]
    _run(store.update_items, project_id, updates)
    return _answer(response, store, project_id)


@projects_router.post("/{project_id}/notes", response_model=Project)
def add_note(project_id: str, body: NoteCreate, response: Response, store: ProjectStore = Depends(project_store)):
    _run(store.add_note, project_id, body.author_role, body.text)
    return _answer(response, store, project_id)


@projects_router.post("/{project_id}/pins", response_model=Project)
def add_pin(project_id: str, body: PinCreate, response: Response, store: ProjectStore = Depends(project_store)):
    _run(store.add_pin, project_id, body.kind, body.ref_id, body.title, body.by_role, body.body)
    return _answer(response, store, project_id)


@projects_router.post("/{project_id}/model", response_model=Project)
def add_structural_model(project_id: str, body: StructuralModel, response: Response,
                         store: ProjectStore = Depends(project_store)):
    # The Revit reader's model, checked against the StructuralModel contract, kept on the project. With PR 13
    # (model_input) in, its reader cleans a Revit export first, and its store gets a copy for the site profile.
    project = _run(store.get_project, project_id)
    read, refused, save = _model_input()
    model = body.model_dump()
    if read is not None and model["source"] == "revit":
        model = _read_revit(read, refused, model)
    _run(store.set_structural_model, project_id, model)
    if save is not None:
        try:
            save(project_id, project["site_bbl"], model)
        except Exception as error:
            raise HTTPException(500, "the model is kept on the project, but model_input.store.save failed "
                                     f"({type(error).__name__}), so the site profile does not have it") from error
    return _answer(response, store, project_id)


def _model_input():
    """PR 13's reader, its refusal and its store, each None until it lands. A broken module refuses the write."""
    try:
        return (owner_function("model_input.revit", "read_revit"),
                owner_function("model_input.revit", "ModelInputError") or (),
                owner_function("model_input.store", "save"))
    except DataUnavailable as error:
        raise HTTPException(error.status_code, str(error)) from None


def _read_revit(read, refused, model: dict) -> dict:
    try:
        return StructuralModel.model_validate(read(model)).model_dump()
    except refused as error:
        raise HTTPException(422, str(error)) from None
    except ValidationError:
        raise HTTPException(500, "model_input.revit.read_revit answered off the StructuralModel contract") from None
