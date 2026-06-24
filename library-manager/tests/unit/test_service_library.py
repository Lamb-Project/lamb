"""Unit tests for ``services.library_service`` — direct function calls."""

from __future__ import annotations

import json
import uuid

import pytest
from _helpers import unique_id
from database.models import ContentItem, Library
from services import library_service
from sqlalchemy.exc import IntegrityError


def _make_item(db, library_id, organization_id, **overrides):
    """Insert a minimal ready ContentItem for count assertions."""
    item = ContentItem(
        id=unique_id("item"),
        library_id=library_id,
        organization_id=organization_id,
        title="t",
        source_type="file",
        base_path="/tmp/none",
        permalink_base="/docs/x",
        import_plugin="simple_import",
        status="ready",
        **overrides,
    )
    db.add(item)
    db.commit()
    return item


def test_ensure_organization_creates_when_missing(db_session):
    """ensure_organization creates a new org row when it does not exist."""
    org_id = unique_id("org")
    org = library_service.ensure_organization(db_session, org_id, name="My Org")
    db_session.commit()
    assert org.id == org_id
    assert org.name == "My Org"


def test_ensure_organization_defaults_name_to_id(db_session):
    """ensure_organization falls back to the id when no name is given."""
    org_id = unique_id("org")
    org = library_service.ensure_organization(db_session, org_id)
    db_session.commit()
    assert org.name == org_id


def test_ensure_organization_idempotent_returns_existing(db_session):
    """ensure_organization returns the existing row rather than duplicating."""
    org_id = unique_id("org")
    first = library_service.ensure_organization(db_session, org_id, name="First")
    db_session.commit()
    second = library_service.ensure_organization(db_session, org_id, name="Second")
    db_session.commit()
    assert second.id == first.id
    # Name is not overwritten on the second call.
    assert second.name == "First"


def test_create_library_persists_row_and_config(db_session):
    """create_library inserts a row and serializes import_config to JSON."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    cfg = {"plugin": "simple_import", "params": {"a": 1}}
    lib = library_service.create_library(db_session, lib_id, org_id, "Lib A", cfg)
    assert lib.id == lib_id
    assert lib.organization_id == org_id
    assert json.loads(lib.import_config) == cfg


def test_create_library_null_config_when_omitted(db_session):
    """create_library stores NULL import_config when none is supplied."""
    org_id = unique_id("org")
    lib = library_service.create_library(db_session, unique_id("lib"), org_id, "Lib")
    assert lib.import_config is None


def test_create_library_duplicate_org_name_raises_integrity_error(db_session):
    """Duplicate (org, name) violates the unique constraint and raises."""
    org_id = unique_id("org")
    name = f"Dup {uuid.uuid4().hex[:6]}"
    library_service.create_library(db_session, unique_id("lib"), org_id, name)
    with pytest.raises(IntegrityError):
        library_service.create_library(db_session, unique_id("lib"), org_id, name)
    db_session.rollback()


def test_get_library_returns_none_when_missing(db_session):
    """get_library returns None for an unknown id."""
    assert library_service.get_library(db_session, unique_id("nope")) is None


def test_get_library_returns_row(db_session):
    """get_library returns the matching Library row."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    library_service.create_library(db_session, lib_id, org_id, "Lib")
    found = library_service.get_library(db_session, lib_id)
    assert found is not None and found.id == lib_id


def test_get_library_with_item_count_none_when_missing(db_session):
    """get_library_with_item_count returns None for an unknown id."""
    assert library_service.get_library_with_item_count(db_session, unique_id("x")) is None


def test_get_library_with_item_count_reflects_items(db_session):
    """item_count matches the number of items in the library."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    cfg = {"k": "v"}
    library_service.create_library(db_session, lib_id, org_id, "Lib", cfg)
    _make_item(db_session, lib_id, org_id)
    _make_item(db_session, lib_id, org_id)
    info = library_service.get_library_with_item_count(db_session, lib_id)
    assert info["item_count"] == 2
    assert info["import_config"] == cfg
    assert info["id"] == lib_id


def test_list_libraries_filters_by_organization(db_session):
    """list_libraries only returns libraries for the requested org."""
    org_a = unique_id("orgA")
    org_b = unique_id("orgB")
    library_service.create_library(db_session, unique_id("lib"), org_a, "A1")
    library_service.create_library(db_session, unique_id("lib"), org_a, "A2")
    library_service.create_library(db_session, unique_id("lib"), org_b, "B1")
    libs, total = library_service.list_libraries(db_session, org_a)
    assert total == 2
    assert {lib["organization_id"] for lib in libs} == {org_a}


def test_list_libraries_pagination_boundaries(db_session):
    """list_libraries honors limit/offset while reporting the full total."""
    org_id = unique_id("org")
    for i in range(5):
        library_service.create_library(db_session, unique_id("lib"), org_id, f"L{i}")
    page1, total = library_service.list_libraries(db_session, org_id, limit=2, offset=0)
    page2, _ = library_service.list_libraries(db_session, org_id, limit=2, offset=2)
    page3, _ = library_service.list_libraries(db_session, org_id, limit=2, offset=4)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    ids = {lib["id"] for lib in page1 + page2 + page3}
    assert len(ids) == 5  # No overlap across pages.


def test_list_libraries_includes_item_count(db_session):
    """list_libraries embeds a per-library item_count."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    library_service.create_library(db_session, lib_id, org_id, "Lib")
    _make_item(db_session, lib_id, org_id)
    libs, _ = library_service.list_libraries(db_session, org_id)
    assert libs[0]["item_count"] == 1


def test_delete_library_removes_row_and_cascades(db_session):
    """delete_library removes the library and cascades to its items."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    library_service.create_library(db_session, lib_id, org_id, "Lib")
    item = _make_item(db_session, lib_id, org_id)
    item_id = item.id
    assert library_service.delete_library(db_session, lib_id) is True
    assert library_service.get_library(db_session, lib_id) is None
    assert db_session.query(ContentItem).filter(ContentItem.id == item_id).first() is None


def test_delete_library_returns_false_when_missing(db_session):
    """delete_library returns False for an unknown id."""
    assert library_service.delete_library(db_session, unique_id("nope")) is False


def test_update_import_config_persists_json(db_session):
    """update_import_config persists the new config as JSON."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    library_service.create_library(db_session, lib_id, org_id, "Lib")
    new_cfg = {"plugin": "markitdown_import", "x": [1, 2, 3]}
    updated = library_service.update_import_config(db_session, lib_id, new_cfg)
    assert json.loads(updated.import_config) == new_cfg
    # Re-read to confirm it was committed.
    reread = library_service.get_library(db_session, lib_id)
    assert json.loads(reread.import_config) == new_cfg


def test_update_import_config_only_affects_target(db_session):
    """update_import_config does not touch sibling libraries."""
    org_id = unique_id("org")
    lib_a = unique_id("lib")
    lib_b = unique_id("lib")
    library_service.create_library(db_session, lib_a, org_id, "A", {"orig": "a"})
    library_service.create_library(db_session, lib_b, org_id, "B", {"orig": "b"})
    library_service.update_import_config(db_session, lib_a, {"changed": True})
    other = library_service.get_library(db_session, lib_b)
    assert json.loads(other.import_config) == {"orig": "b"}


def test_update_import_config_returns_none_when_missing(db_session):
    """update_import_config returns None for an unknown library."""
    assert library_service.update_import_config(db_session, unique_id("x"), {}) is None


def test_delete_library_removes_content_dir(db_session, tmp_storage, monkeypatch):
    """delete_library rmtree's the on-disk content directory when present."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    monkeypatch.setattr(library_service, "CONTENT_DIR", tmp_storage)
    content_dir = tmp_storage / org_id / lib_id
    content_dir.mkdir(parents=True)
    (content_dir / "marker.txt").write_text("x")
    library_service.create_library(db_session, lib_id, org_id, "Lib")
    assert library_service.delete_library(db_session, lib_id) is True
    assert not content_dir.exists()


def test_create_library_returns_library_instance(db_session):
    """create_library returns a refreshed Library ORM instance."""
    org_id = unique_id("org")
    lib = library_service.create_library(db_session, unique_id("lib"), org_id, "L")
    assert isinstance(lib, Library)
    assert lib.created_at is not None
