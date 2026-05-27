"""Folder + tree routes for user-organized library hierarchies.

Folders are pure metadata in the Library Manager DB. See
``services/folder_service.py`` for the semantics.

LAMB enforces ACL upstream — these endpoints trust the bearer token via
``verify_token`` (same pattern as the other routers).
"""

import logging

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends, HTTPException
from schemas.folders import (
    FolderCreateRequest,
    FolderMoveRequest,
    FolderRenameRequest,
    FolderSummary,
    ItemsMoveRequest,
    LibraryTreeResponse,
)
from services import content_service, folder_service
from services.folder_service import FolderError
from services.library_service import get_library
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/libraries", tags=["Folders"], dependencies=[Depends(verify_token)])


def _raise_for_folder_error(exc: FolderError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


@router.get("/{lib_id}/tree", response_model=LibraryTreeResponse)
async def get_library_tree(
    lib_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Return all folders and items in a library as flat lists.

    The frontend builds the nested tree from these lists. Items at the
    library root have ``folder_id == null``.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    folders = folder_service.list_folders(db, lib_id)
    items = folder_service.list_items_for_tree(db, lib_id)

    return {
        "library_id": lib_id,
        "folders": [FolderSummary.model_validate(f) for f in folders],
        "items": [content_service.item_to_summary(i) for i in items],
    }


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------


@router.post("/{lib_id}/folders", response_model=FolderSummary, status_code=201)
async def create_folder(
    lib_id: str,
    body: FolderCreateRequest,
    db: Session = Depends(get_session),
) -> FolderSummary:
    try:
        folder = folder_service.create_folder(
            db,
            library_id=lib_id,
            name=body.name,
            parent_folder_id=body.parent_folder_id,
        )
    except FolderError as exc:
        _raise_for_folder_error(exc)
    return FolderSummary.model_validate(folder)


@router.put("/{lib_id}/folders/{folder_id}", response_model=FolderSummary)
async def rename_folder(
    lib_id: str,
    folder_id: str,
    body: FolderRenameRequest,
    db: Session = Depends(get_session),
) -> FolderSummary:
    folder = folder_service.get_folder(db, folder_id)
    if folder is None or folder.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Folder not found.")
    try:
        folder = folder_service.rename_folder(db, folder_id, body.name)
    except FolderError as exc:
        _raise_for_folder_error(exc)
    return FolderSummary.model_validate(folder)


@router.put("/{lib_id}/folders/{folder_id}/move", response_model=FolderSummary)
async def move_folder(
    lib_id: str,
    folder_id: str,
    body: FolderMoveRequest,
    db: Session = Depends(get_session),
) -> FolderSummary:
    folder = folder_service.get_folder(db, folder_id)
    if folder is None or folder.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Folder not found.")
    try:
        folder = folder_service.move_folder(db, folder_id, body.parent_folder_id)
    except FolderError as exc:
        _raise_for_folder_error(exc)
    return FolderSummary.model_validate(folder)


@router.delete("/{lib_id}/folders/{folder_id}")
async def delete_folder(
    lib_id: str,
    folder_id: str,
    db: Session = Depends(get_session),
) -> dict:
    folder = folder_service.get_folder(db, folder_id)
    if folder is None or folder.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Folder not found.")
    try:
        new_parent_id = folder_service.delete_folder(db, folder_id)
    except FolderError as exc:
        _raise_for_folder_error(exc)
    return {"message": "Folder deleted.", "items_reparented_to": new_parent_id}


# ---------------------------------------------------------------------------
# Item move (bulk)
# ---------------------------------------------------------------------------


@router.post("/{lib_id}/items/move")
async def move_items(
    lib_id: str,
    body: ItemsMoveRequest,
    db: Session = Depends(get_session),
) -> dict:
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")
    try:
        moved = folder_service.move_items(
            db, library_id=lib_id, item_ids=body.item_ids, folder_id=body.folder_id
        )
    except FolderError as exc:
        _raise_for_folder_error(exc)
    return {"moved": moved, "folder_id": body.folder_id}
