"""Unit tests for ``services.folder_service`` — direct function calls."""

from __future__ import annotations

import pytest
from _helpers import unique_id
from database.models import ContentItem, Library
from services import folder_service
from services.folder_service import (
    FolderConflictError,
    FolderCycleError,
    FolderNotFoundError,
    FolderValidationError,
)
from services.library_service import create_library


@pytest.fixture
def lib(db_session):
    """Create a fresh library and return its id."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    create_library(db_session, lib_id, org_id, "Folder Lib")
    return lib_id


def _make_item(db, library_id, folder_id=None):
    """Insert a content item, optionally inside a folder."""
    lib = db.query(Library).filter(Library.id == library_id).first()
    org_id = lib.organization_id
    item = ContentItem(
        id=unique_id("item"),
        library_id=library_id,
        organization_id=org_id,
        folder_id=folder_id,
        title="t",
        source_type="file",
        base_path="/tmp/none",
        permalink_base="/docs/x",
        import_plugin="simple_import",
        status="ready",
    )
    db.add(item)
    db.commit()
    return item


# ---------------------------------------------------------------------------
# Error subclasses
# ---------------------------------------------------------------------------


def test_error_status_codes():
    """Each FolderError subclass carries the documented HTTP status code."""
    assert FolderNotFoundError().status_code == 404
    assert FolderConflictError().status_code == 409
    assert FolderCycleError().status_code == 400
    assert FolderValidationError().status_code == 400
    assert folder_service.FolderError().status_code == 400


# ---------------------------------------------------------------------------
# create_folder
# ---------------------------------------------------------------------------


def test_create_folder_at_root(db_session, lib):
    """create_folder creates a root-level folder with no parent."""
    f = folder_service.create_folder(
        db_session, library_id=lib, name="Root", parent_folder_id=None
    )
    assert f.parent_folder_id is None
    assert f.library_id == lib
    assert f.name == "Root"


def test_create_folder_nested(db_session, lib):
    """create_folder nests a folder under an existing parent."""
    parent = folder_service.create_folder(
        db_session, library_id=lib, name="Parent", parent_folder_id=None
    )
    child = folder_service.create_folder(
        db_session, library_id=lib, name="Child", parent_folder_id=parent.id
    )
    assert child.parent_folder_id == parent.id


def test_create_folder_unknown_library_raises_notfound(db_session):
    """create_folder raises FolderNotFoundError when the library is missing."""
    with pytest.raises(FolderNotFoundError):
        folder_service.create_folder(
            db_session, library_id=unique_id("x"), name="A", parent_folder_id=None
        )


def test_create_folder_unknown_parent_raises_notfound(db_session, lib):
    """create_folder raises FolderNotFoundError when the parent is missing."""
    with pytest.raises(FolderNotFoundError):
        folder_service.create_folder(
            db_session, library_id=lib, name="A", parent_folder_id=unique_id("x")
        )


def test_create_folder_parent_in_other_library_raises_validation(db_session, lib):
    """create_folder rejects a parent that lives in a different library."""
    other_lib = unique_id("lib")
    create_library(db_session, other_lib, unique_id("org"), "Other")
    foreign = folder_service.create_folder(
        db_session, library_id=other_lib, name="P", parent_folder_id=None
    )
    with pytest.raises(FolderValidationError):
        folder_service.create_folder(
            db_session, library_id=lib, name="A", parent_folder_id=foreign.id
        )


def test_create_folder_duplicate_sibling_raises_conflict(db_session, lib):
    """create_folder raises FolderConflictError (409) on a duplicate sibling."""
    folder_service.create_folder(
        db_session, library_id=lib, name="Same", parent_folder_id=None
    )
    db_session.rollback()  # discard nothing; just ensure clean state
    with pytest.raises(FolderConflictError) as exc:
        folder_service.create_folder(
            db_session, library_id=lib, name="Same", parent_folder_id=None
        )
    assert exc.value.status_code == 409


def test_create_folder_same_name_different_parent_ok(db_session, lib):
    """Identical names are allowed under different parents."""
    p1 = folder_service.create_folder(
        db_session, library_id=lib, name="P1", parent_folder_id=None
    )
    p2 = folder_service.create_folder(
        db_session, library_id=lib, name="P2", parent_folder_id=None
    )
    folder_service.create_folder(
        db_session, library_id=lib, name="Dup", parent_folder_id=p1.id
    )
    # No conflict — different parent.
    folder_service.create_folder(
        db_session, library_id=lib, name="Dup", parent_folder_id=p2.id
    )


# ---------------------------------------------------------------------------
# rename_folder
# ---------------------------------------------------------------------------


def test_rename_folder_changes_name(db_session, lib):
    """rename_folder updates the folder's name."""
    f = folder_service.create_folder(
        db_session, library_id=lib, name="Old", parent_folder_id=None
    )
    renamed = folder_service.rename_folder(db_session, f.id, "New")
    assert renamed.name == "New"


def test_rename_folder_noop_same_name(db_session, lib):
    """rename_folder is a no-op when the name is unchanged."""
    f = folder_service.create_folder(
        db_session, library_id=lib, name="Keep", parent_folder_id=None
    )
    result = folder_service.rename_folder(db_session, f.id, "Keep")
    assert result.name == "Keep"


def test_rename_folder_missing_raises_notfound(db_session):
    """rename_folder raises FolderNotFoundError for an unknown folder."""
    with pytest.raises(FolderNotFoundError):
        folder_service.rename_folder(db_session, unique_id("x"), "X")


def test_rename_folder_conflict_raises(db_session, lib):
    """rename_folder raises FolderConflictError when colliding with a sibling."""
    folder_service.create_folder(
        db_session, library_id=lib, name="A", parent_folder_id=None
    )
    b = folder_service.create_folder(
        db_session, library_id=lib, name="B", parent_folder_id=None
    )
    with pytest.raises(FolderConflictError):
        folder_service.rename_folder(db_session, b.id, "A")


# ---------------------------------------------------------------------------
# move_folder
# ---------------------------------------------------------------------------


def test_move_folder_reparents(db_session, lib):
    """move_folder re-parents a folder under a new parent."""
    p = folder_service.create_folder(
        db_session, library_id=lib, name="P", parent_folder_id=None
    )
    f = folder_service.create_folder(
        db_session, library_id=lib, name="F", parent_folder_id=None
    )
    moved = folder_service.move_folder(db_session, f.id, p.id)
    assert moved.parent_folder_id == p.id


def test_move_folder_to_root(db_session, lib):
    """move_folder with None parent moves the folder to the library root."""
    p = folder_service.create_folder(
        db_session, library_id=lib, name="P", parent_folder_id=None
    )
    f = folder_service.create_folder(
        db_session, library_id=lib, name="F", parent_folder_id=p.id
    )
    moved = folder_service.move_folder(db_session, f.id, None)
    assert moved.parent_folder_id is None


def test_move_folder_into_self_raises_cycle(db_session, lib):
    """move_folder raises FolderCycleError when moving a folder into itself."""
    f = folder_service.create_folder(
        db_session, library_id=lib, name="Self", parent_folder_id=None
    )
    with pytest.raises(FolderCycleError):
        folder_service.move_folder(db_session, f.id, f.id)


def test_move_folder_into_descendant_raises_cycle(db_session, lib):
    """move_folder raises FolderCycleError when moving into a descendant."""
    a = folder_service.create_folder(
        db_session, library_id=lib, name="A", parent_folder_id=None
    )
    b = folder_service.create_folder(
        db_session, library_id=lib, name="B", parent_folder_id=a.id
    )
    c = folder_service.create_folder(
        db_session, library_id=lib, name="C", parent_folder_id=b.id
    )
    with pytest.raises(FolderCycleError):
        folder_service.move_folder(db_session, a.id, c.id)


def test_move_folder_missing_raises_notfound(db_session):
    """move_folder raises FolderNotFoundError for an unknown folder."""
    with pytest.raises(FolderNotFoundError):
        folder_service.move_folder(db_session, unique_id("x"), None)


def test_move_folder_unknown_destination_raises_notfound(db_session, lib):
    """move_folder raises FolderNotFoundError for an unknown destination."""
    f = folder_service.create_folder(
        db_session, library_id=lib, name="F", parent_folder_id=None
    )
    with pytest.raises(FolderNotFoundError):
        folder_service.move_folder(db_session, f.id, unique_id("x"))


def test_move_folder_cross_library_raises_validation(db_session, lib):
    """move_folder rejects a destination in a different library."""
    other_lib = unique_id("lib")
    create_library(db_session, other_lib, unique_id("org"), "Other")
    dest = folder_service.create_folder(
        db_session, library_id=other_lib, name="Dest", parent_folder_id=None
    )
    f = folder_service.create_folder(
        db_session, library_id=lib, name="F", parent_folder_id=None
    )
    with pytest.raises(FolderValidationError):
        folder_service.move_folder(db_session, f.id, dest.id)


def test_move_folder_name_collision_raises_conflict(db_session, lib):
    """move_folder raises FolderConflictError when the destination has the name."""
    dest = folder_service.create_folder(
        db_session, library_id=lib, name="Dest", parent_folder_id=None
    )
    folder_service.create_folder(
        db_session, library_id=lib, name="Dup", parent_folder_id=dest.id
    )
    f = folder_service.create_folder(
        db_session, library_id=lib, name="Dup", parent_folder_id=None
    )
    with pytest.raises(FolderConflictError):
        folder_service.move_folder(db_session, f.id, dest.id)


# ---------------------------------------------------------------------------
# delete_folder
# ---------------------------------------------------------------------------


def test_delete_folder_reparents_items_up(db_session, lib):
    """delete_folder re-homes items up to the deleted folder's parent."""
    parent = folder_service.create_folder(
        db_session, library_id=lib, name="Parent", parent_folder_id=None
    )
    child = folder_service.create_folder(
        db_session, library_id=lib, name="Child", parent_folder_id=parent.id
    )
    item = _make_item(db_session, lib, folder_id=child.id)
    new_parent = folder_service.delete_folder(db_session, child.id)
    assert new_parent == parent.id
    db_session.refresh(item)
    assert item.folder_id == parent.id


def test_delete_folder_reparents_subfolders_up(db_session, lib):
    """delete_folder re-homes subfolders up to the deleted folder's parent."""
    parent = folder_service.create_folder(
        db_session, library_id=lib, name="Parent", parent_folder_id=None
    )
    mid = folder_service.create_folder(
        db_session, library_id=lib, name="Mid", parent_folder_id=parent.id
    )
    sub = folder_service.create_folder(
        db_session, library_id=lib, name="Sub", parent_folder_id=mid.id
    )
    folder_service.delete_folder(db_session, mid.id)
    db_session.refresh(sub)
    assert sub.parent_folder_id == parent.id


def test_delete_folder_root_reparents_to_none(db_session, lib):
    """Deleting a root folder re-homes its children to the library root."""
    root = folder_service.create_folder(
        db_session, library_id=lib, name="Root", parent_folder_id=None
    )
    child = folder_service.create_folder(
        db_session, library_id=lib, name="Child", parent_folder_id=root.id
    )
    new_parent = folder_service.delete_folder(db_session, root.id)
    assert new_parent is None
    db_session.refresh(child)
    assert child.parent_folder_id is None


def test_delete_folder_collision_renames_with_suffix(db_session, lib):
    """delete_folder appends ``(2)`` when a reparented subfolder name collides.

    NOTE: the deleted folder is at the library root so its children reparent
    to a NULL parent. The non-root case is covered by
    test_delete_folder_collision_under_nonroot_parent.
    """
    # Root already has a "Drafts".
    folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=None
    )
    mid = folder_service.create_folder(
        db_session, library_id=lib, name="Mid", parent_folder_id=None
    )
    # The deleted folder ALSO contains a "Drafts".
    collide = folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=mid.id
    )
    folder_service.delete_folder(db_session, mid.id)
    db_session.refresh(collide)
    assert collide.parent_folder_id is None
    assert collide.name == "Drafts (2)"


def test_delete_folder_collision_increments_suffix(db_session, lib):
    """_next_available_name keeps incrementing when ``(2)`` is also taken."""
    folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=None
    )
    folder_service.create_folder(
        db_session, library_id=lib, name="Drafts (2)", parent_folder_id=None
    )
    mid = folder_service.create_folder(
        db_session, library_id=lib, name="Mid", parent_folder_id=None
    )
    collide = folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=mid.id
    )
    folder_service.delete_folder(db_session, mid.id)
    db_session.refresh(collide)
    assert collide.name == "Drafts (3)"


def test_delete_folder_collision_under_nonroot_parent(db_session, lib):
    """A reparented subfolder colliding under a NON-root parent is renamed.

    The collided 'Drafts' is renamed to 'Drafts (2)' under the parent. The
    deduped name is computed before parent_folder_id is reassigned, so the
    autoflush during _next_available_name never writes a colliding row.
    """
    parent = folder_service.create_folder(
        db_session, library_id=lib, name="Parent", parent_folder_id=None
    )
    # Parent already has a "Drafts".
    folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=parent.id
    )
    mid = folder_service.create_folder(
        db_session, library_id=lib, name="Mid", parent_folder_id=parent.id
    )
    # Mid ALSO contains a "Drafts"; deleting Mid reparents it under Parent.
    collide = folder_service.create_folder(
        db_session, library_id=lib, name="Drafts", parent_folder_id=mid.id
    )
    folder_service.delete_folder(db_session, mid.id)
    db_session.refresh(collide)
    assert collide.parent_folder_id == parent.id
    assert collide.name == "Drafts (2)"


def test_delete_folder_missing_raises_notfound(db_session):
    """delete_folder raises FolderNotFoundError for an unknown folder."""
    with pytest.raises(FolderNotFoundError):
        folder_service.delete_folder(db_session, unique_id("x"))


# ---------------------------------------------------------------------------
# move_items
# ---------------------------------------------------------------------------


def test_move_items_single_into_folder(db_session, lib):
    """move_items moves one item into a folder."""
    folder = folder_service.create_folder(
        db_session, library_id=lib, name="Dest", parent_folder_id=None
    )
    item = _make_item(db_session, lib)
    n = folder_service.move_items(db_session, lib, [item.id], folder.id)
    assert n == 1
    db_session.refresh(item)
    assert item.folder_id == folder.id


def test_move_items_bulk_to_root(db_session, lib):
    """move_items moves multiple items to the library root (folder_id None)."""
    folder = folder_service.create_folder(
        db_session, library_id=lib, name="Dest", parent_folder_id=None
    )
    i1 = _make_item(db_session, lib, folder_id=folder.id)
    i2 = _make_item(db_session, lib, folder_id=folder.id)
    n = folder_service.move_items(db_session, lib, [i1.id, i2.id], None)
    assert n == 2
    db_session.refresh(i1)
    db_session.refresh(i2)
    assert i1.folder_id is None
    assert i2.folder_id is None


def test_move_items_empty_list_returns_zero(db_session, lib):
    """move_items returns 0 for an empty item list without touching the DB."""
    assert folder_service.move_items(db_session, lib, [], None) == 0


def test_move_items_unknown_destination_raises_notfound(db_session, lib):
    """move_items raises FolderNotFoundError for an unknown destination."""
    item = _make_item(db_session, lib)
    with pytest.raises(FolderNotFoundError):
        folder_service.move_items(db_session, lib, [item.id], unique_id("x"))


def test_move_items_destination_other_library_raises_validation(db_session, lib):
    """move_items rejects a destination folder in a different library."""
    other_lib = unique_id("lib")
    create_library(db_session, other_lib, unique_id("org"), "Other")
    dest = folder_service.create_folder(
        db_session, library_id=other_lib, name="Dest", parent_folder_id=None
    )
    item = _make_item(db_session, lib)
    with pytest.raises(FolderValidationError):
        folder_service.move_items(db_session, lib, [item.id], dest.id)


def test_move_items_missing_item_raises_notfound(db_session, lib):
    """move_items raises FolderNotFoundError when an item id does not exist."""
    item = _make_item(db_session, lib)
    with pytest.raises(FolderNotFoundError):
        folder_service.move_items(db_session, lib, [item.id, unique_id("ghost")], None)


def test_move_items_cross_library_item_raises_validation(db_session, lib):
    """move_items rejects items that belong to a different library."""
    other_lib = unique_id("lib")
    create_library(db_session, other_lib, unique_id("org"), "Other")
    foreign_item = _make_item(db_session, other_lib)
    with pytest.raises(FolderValidationError):
        folder_service.move_items(db_session, lib, [foreign_item.id], None)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def test_get_folder_returns_none_when_missing(db_session):
    """get_folder returns None for an unknown id."""
    assert folder_service.get_folder(db_session, unique_id("x")) is None


def test_list_folders_sorted_by_name(db_session, lib):
    """list_folders returns the library's folders ordered alphabetically."""
    folder_service.create_folder(
        db_session, library_id=lib, name="Zebra", parent_folder_id=None
    )
    folder_service.create_folder(
        db_session, library_id=lib, name="Alpha", parent_folder_id=None
    )
    names = [f.name for f in folder_service.list_folders(db_session, lib)]
    assert names == ["Alpha", "Zebra"]


def test_list_items_for_tree_returns_library_items(db_session, lib):
    """list_items_for_tree returns the items belonging to the library."""
    i1 = _make_item(db_session, lib)
    i2 = _make_item(db_session, lib)
    ids = {i.id for i in folder_service.list_items_for_tree(db_session, lib)}
    assert {i1.id, i2.id} <= ids
