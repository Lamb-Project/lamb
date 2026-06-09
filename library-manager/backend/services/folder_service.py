"""Folder operations for user-organized library hierarchies.

Folders are pure DB metadata: items remain physically at
``{org}/{lib}/{item_uuid}/`` on disk and their permalinks are unchanged.
A folder can contain other folders (unlimited depth) and items. An item
belongs to exactly one folder, or to the library root (``folder_id``
NULL).

Cycle prevention: every move walks the ancestor chain of the target
parent server-side. Unique sibling names are enforced via a DB
constraint plus an explicit pre-check that returns a friendly 409.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable

from database.models import ContentFolder, ContentItem, Library
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FolderError(Exception):
    """Base class for folder-service errors. Each subclass maps to an HTTP code."""

    status_code: int = 400


class FolderNotFoundError(FolderError):
    status_code = 404


class FolderConflictError(FolderError):
    """Raised on duplicate sibling names."""

    status_code = 409


class FolderCycleError(FolderError):
    """Raised when a move would create a cycle (move into self/descendant)."""

    status_code = 400


class FolderValidationError(FolderError):
    """Raised when input fails validation (cross-library FK, etc.)."""

    status_code = 400


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_folder(db: Session, folder_id: str) -> ContentFolder | None:
    """Return the folder with the given ID, or ``None`` if not found.

    Args:
        db: Database session.
        folder_id: The folder UUID to look up.

    Returns:
        The matching :class:`ContentFolder`, or ``None`` if no folder
        exists with that ID.
    """
    return db.query(ContentFolder).filter(ContentFolder.id == folder_id).first()


def list_folders(db: Session, library_id: str) -> list[ContentFolder]:
    """Return all folders in a library, ordered by name.

    Args:
        db: Database session.
        library_id: The library UUID whose folders to list.

    Returns:
        A list of :class:`ContentFolder` objects sorted alphabetically
        by name.
    """
    return (
        db.query(ContentFolder)
        .filter(ContentFolder.library_id == library_id)
        .order_by(ContentFolder.name)
        .all()
    )


def list_items_for_tree(db: Session, library_id: str) -> list[ContentItem]:
    """Return all items in a library for tree rendering, newest first.

    Args:
        db: Database session.
        library_id: The library UUID whose items to list.

    Returns:
        A list of :class:`ContentItem` objects ordered by
        ``created_at`` descending.
    """
    return (
        db.query(ContentItem)
        .filter(ContentItem.library_id == library_id)
        .order_by(ContentItem.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def create_folder(
    db: Session,
    *,
    library_id: str,
    name: str,
    parent_folder_id: str | None,
) -> ContentFolder:
    """Create a folder under ``parent_folder_id`` (or at the library root).

    Raises:
        FolderNotFoundError: library or parent doesn't exist.
        FolderValidationError: parent belongs to a different library.
        FolderConflictError: a sibling with the same name already exists.
    """
    lib = db.query(Library).filter(Library.id == library_id).first()
    if lib is None:
        raise FolderNotFoundError("Library not found.")

    if parent_folder_id is not None:
        parent = get_folder(db, parent_folder_id)
        if parent is None:
            raise FolderNotFoundError("Parent folder not found.")
        if parent.library_id != library_id:
            raise FolderValidationError(
                "Parent folder belongs to a different library."
            )

    _ensure_unique_sibling_name(db, library_id, parent_folder_id, name, exclude_id=None)

    folder = ContentFolder(
        id=str(uuid.uuid4()),
        library_id=library_id,
        parent_folder_id=parent_folder_id,
        name=name,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def rename_folder(db: Session, folder_id: str, new_name: str) -> ContentFolder:
    """Rename a folder, enforcing unique sibling names.

    Args:
        db: Database session.
        folder_id: The UUID of the folder to rename.
        new_name: The new name for the folder.

    Returns:
        The updated :class:`ContentFolder` with the new name applied.

    Raises:
        FolderNotFoundError: If no folder exists with ``folder_id``.
        FolderConflictError: If a sibling folder already has ``new_name``.
    """
    folder = get_folder(db, folder_id)
    if folder is None:
        raise FolderNotFoundError("Folder not found.")
    if folder.name == new_name:
        return folder
    _ensure_unique_sibling_name(
        db,
        folder.library_id,
        folder.parent_folder_id,
        new_name,
        exclude_id=folder.id,
    )
    folder.name = new_name
    db.commit()
    db.refresh(folder)
    return folder


def move_folder(
    db: Session,
    folder_id: str,
    new_parent_id: str | None,
) -> ContentFolder:
    """Re-parent ``folder_id`` under ``new_parent_id`` (or to root).

    Raises:
        FolderNotFoundError, FolderValidationError, FolderCycleError,
        FolderConflictError.
    """
    folder = get_folder(db, folder_id)
    if folder is None:
        raise FolderNotFoundError("Folder not found.")

    if new_parent_id == folder.id:
        raise FolderCycleError("A folder cannot be moved into itself.")

    if new_parent_id is not None:
        new_parent = get_folder(db, new_parent_id)
        if new_parent is None:
            raise FolderNotFoundError("Destination folder not found.")
        if new_parent.library_id != folder.library_id:
            raise FolderValidationError(
                "Cannot move a folder across libraries."
            )
        if _is_descendant(db, ancestor_id=folder.id, candidate_id=new_parent.id):
            raise FolderCycleError(
                "A folder cannot be moved into one of its own descendants."
            )

    if new_parent_id != folder.parent_folder_id:
        _ensure_unique_sibling_name(
            db,
            folder.library_id,
            new_parent_id,
            folder.name,
            exclude_id=folder.id,
        )

    folder.parent_folder_id = new_parent_id
    db.commit()
    db.refresh(folder)
    return folder


def delete_folder(db: Session, folder_id: str) -> str:
    """Delete a folder. Items and subfolders reparent up to its parent.

    Never cascade-deletes items. The disk layout is untouched.

    Returns:
        The parent_folder_id (or NULL) that orphans were re-homed under,
        so callers can refresh the right subtree.
    """
    folder = get_folder(db, folder_id)
    if folder is None:
        raise FolderNotFoundError("Folder not found.")

    new_parent_id = folder.parent_folder_id

    # Re-home items first
    items = (
        db.query(ContentItem)
        .filter(ContentItem.folder_id == folder.id)
        .all()
    )
    for item in items:
        item.folder_id = new_parent_id

    # Re-home subfolders. If a name collision arises with an existing
    # sibling of the parent, append a numeric suffix until unique. This is
    # rare but possible: parent already has "Drafts" and the deleted
    # folder also contained "Drafts".
    subfolders = (
        db.query(ContentFolder)
        .filter(ContentFolder.parent_folder_id == folder.id)
        .all()
    )
    for sub in subfolders:
        sub.parent_folder_id = new_parent_id
        sub.name = _next_available_name(
            db, folder.library_id, new_parent_id, sub.name, exclude_id=sub.id
        )

    db.delete(folder)
    db.commit()
    return new_parent_id


def move_items(
    db: Session,
    library_id: str,
    item_ids: Iterable[str],
    folder_id: str | None,
) -> int:
    """Move a batch of items to ``folder_id`` (or to root).

    Validates that every item belongs to ``library_id`` and that
    ``folder_id`` (if non-NULL) also belongs to ``library_id``.

    Returns:
        Number of items updated.

    Raises:
        FolderNotFoundError, FolderValidationError.
    """
    if folder_id is not None:
        folder = get_folder(db, folder_id)
        if folder is None:
            raise FolderNotFoundError("Destination folder not found.")
        if folder.library_id != library_id:
            raise FolderValidationError(
                "Destination folder belongs to a different library."
            )

    ids = list(item_ids)
    if not ids:
        return 0

    items = (
        db.query(ContentItem)
        .filter(ContentItem.id.in_(ids))
        .all()
    )
    if len(items) != len(set(ids)):
        raise FolderNotFoundError("One or more items not found.")
    for item in items:
        if item.library_id != library_id:
            raise FolderValidationError(
                "Cannot move items across libraries."
            )

    for item in items:
        item.folder_id = folder_id
    db.commit()
    return len(items)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_unique_sibling_name(
    db: Session,
    library_id: str,
    parent_folder_id: str | None,
    name: str,
    exclude_id: str | None,
) -> None:
    q = db.query(ContentFolder).filter(
        ContentFolder.library_id == library_id,
        ContentFolder.parent_folder_id == parent_folder_id,
        ContentFolder.name == name,
    )
    if exclude_id is not None:
        q = q.filter(ContentFolder.id != exclude_id)
    if q.first() is not None:
        raise FolderConflictError("A folder with this name already exists.")


def _next_available_name(
    db: Session,
    library_id: str,
    parent_folder_id: str | None,
    base_name: str,
    exclude_id: str | None,
) -> str:
    """Return ``base_name`` if free, else ``base_name (2)``, ``(3)``, ..."""
    try:
        _ensure_unique_sibling_name(
            db, library_id, parent_folder_id, base_name, exclude_id
        )
        return base_name
    except FolderConflictError:
        n = 2
        while True:
            candidate = f"{base_name} ({n})"
            try:
                _ensure_unique_sibling_name(
                    db, library_id, parent_folder_id, candidate, exclude_id
                )
                return candidate
            except FolderConflictError:
                n += 1


def _is_descendant(db: Session, ancestor_id: str, candidate_id: str) -> bool:
    """Return True if ``candidate_id`` is in the subtree rooted at ``ancestor_id``."""
    cursor: str | None = candidate_id
    seen: set[str] = set()
    while cursor is not None:
        if cursor in seen:
            # Defensive: data corruption shouldn't loop us forever
            return False
        seen.add(cursor)
        if cursor == ancestor_id:
            return True
        parent = get_folder(db, cursor)
        if parent is None:
            return False
        cursor = parent.parent_folder_id
    return False
