"""Unit tests for ``backend/database/models.py`` ORM behavior.

The session database is shared across the whole run, so every test creates
rows with unique ids/names and tears down what it created. Foreign keys are
enforced (``PRAGMA foreign_keys=ON``), so cascade / SET NULL behavior is real.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _helpers import unique_id
from database.models import (
    ContentFolder,
    ContentImage,
    ContentItem,
    Library,
    Organization,
    _utcnow,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def _make_org(db) -> Organization:
    """Persist and return a fresh organization."""
    org = Organization(id=unique_id("org"), name="Org " + unique_id("n"))
    db.add(org)
    db.commit()
    return org


def _make_library(db, org: Organization, name: str | None = None) -> Library:
    """Persist and return a fresh library under ``org``."""
    lib = Library(
        id=unique_id("lib"),
        organization_id=org.id,
        name=name or ("Lib " + unique_id("ln")),
    )
    db.add(lib)
    db.commit()
    return lib


def _make_item(db, lib: Library, org: Organization, folder_id=None) -> ContentItem:
    """Persist and return a minimal content item under ``lib``."""
    item = ContentItem(
        id=unique_id("item"),
        library_id=lib.id,
        organization_id=org.id,
        folder_id=folder_id,
        title="T " + unique_id("t"),
        source_type="file",
        base_path="base/path",
        permalink_base="/docs/x",
        import_plugin="simple",
    )
    db.add(item)
    db.commit()
    return item


class TestUtcNow:
    """``_utcnow`` returns a timezone-aware UTC datetime."""

    def test_returns_aware_utc(self):
        """Result is tz-aware and in UTC."""
        now = _utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None, "must be timezone-aware"
        assert now.utcoffset() == UTC.utcoffset(now), "must be UTC offset"


class TestUniqueConstraints:
    """Composite unique constraints reject duplicate rows."""

    def test_library_org_name_unique(self, db_session):
        """Two libraries with the same org+name violate uq_library_org_name."""
        org = _make_org(db_session)
        name = "Dup " + unique_id("d")
        _make_library(db_session, org, name=name)
        dup = Library(id=unique_id("lib"), organization_id=org.id, name=name)
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_folder_sibling_name_unique(self, db_session):
        """Two sibling folders with the same name violate uq_folder_sibling_name.

        SQLite treats NULL as distinct in unique constraints, so the
        duplicates must share a non-NULL parent for the constraint to bite.
        """
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        parent = ContentFolder(id=unique_id("fld"), library_id=lib.id, name="P")
        db_session.add(parent)
        db_session.commit()
        name = "Folder " + unique_id("f")
        f1 = ContentFolder(
            id=unique_id("fld"),
            library_id=lib.id,
            parent_folder_id=parent.id,
            name=name,
        )
        db_session.add(f1)
        db_session.commit()
        f2 = ContentFolder(
            id=unique_id("fld"),
            library_id=lib.id,
            parent_folder_id=parent.id,
            name=name,
        )
        db_session.add(f2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_name_different_parent_allowed(self, db_session):
        """Same folder name is allowed under different parents."""
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        parent = ContentFolder(id=unique_id("fld"), library_id=lib.id, name="P")
        db_session.add(parent)
        db_session.commit()
        name = "Child " + unique_id("c")
        top = ContentFolder(id=unique_id("fld"), library_id=lib.id, name=name)
        nested = ContentFolder(
            id=unique_id("fld"),
            library_id=lib.id,
            parent_folder_id=parent.id,
            name=name,
        )
        db_session.add_all([top, nested])
        db_session.commit()  # must not raise
        assert top.id != nested.id


class TestCascades:
    """Foreign-key cascade and SET NULL rules are enforced."""

    def test_delete_library_cascades_items_and_folders_and_images(self, db_session):
        """Deleting a library removes its folders, items, and images."""
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        folder = ContentFolder(id=unique_id("fld"), library_id=lib.id, name="F")
        db_session.add(folder)
        db_session.commit()
        item = _make_item(db_session, lib, org, folder_id=folder.id)
        img = ContentImage(
            id=unique_id("img"), content_item_id=item.id, image_path="p.png"
        )
        db_session.add(img)
        db_session.commit()
        item_id, folder_id, img_id = item.id, folder.id, img.id

        db_session.delete(lib)
        db_session.commit()
        # The library row deletion fires DB-level ON DELETE CASCADE for folders
        # (no ORM relationship covers them); expire the identity map so reads
        # hit the database rather than returning stale cached objects.
        db_session.expire_all()

        assert db_session.get(ContentItem, item_id) is None, "item cascaded"
        assert db_session.get(ContentFolder, folder_id) is None, "folder cascaded"
        assert db_session.get(ContentImage, img_id) is None, "image cascaded"

    def test_delete_org_cascades_libraries(self, db_session):
        """Deleting an org removes its libraries (ORM cascade)."""
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        lib_id = lib.id
        db_session.delete(org)
        db_session.commit()
        assert db_session.get(Library, lib_id) is None, "library cascaded with org"

    def test_delete_folder_sets_item_folder_id_null(self, db_session):
        """Deleting a folder SETs NULL on referencing items' folder_id."""
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        folder = ContentFolder(id=unique_id("fld"), library_id=lib.id, name="F")
        db_session.add(folder)
        db_session.commit()
        item = _make_item(db_session, lib, org, folder_id=folder.id)
        item_id = item.id

        # Delete folder via raw SQL so the DB-level SET NULL fires (ORM-level
        # delete-orphan on the library relationship is not involved here).
        from sqlalchemy import text  # noqa: PLC0415

        db_session.execute(
            text("DELETE FROM content_folders WHERE id = :i"), {"i": folder.id}
        )
        db_session.commit()
        db_session.expire_all()

        refreshed = db_session.get(ContentItem, item_id)
        assert refreshed is not None, "item must survive folder deletion"
        assert refreshed.folder_id is None, "folder_id set NULL on folder delete"

        # cleanup
        db_session.delete(lib)
        db_session.commit()


class TestMetadataColumn:
    """The ``metadata_`` attribute maps to the ``metadata`` DB column."""

    def test_metadata_attr_maps_to_metadata_column(self, db_session):
        """Writing ``metadata_`` round-trips via the ``metadata`` column."""
        org = _make_org(db_session)
        lib = _make_library(db_session, org)
        item = _make_item(db_session, lib, org)
        item.metadata_ = '{"k": "v"}'
        db_session.commit()

        from sqlalchemy import text  # noqa: PLC0415

        raw = db_session.execute(
            text("SELECT metadata FROM content_items WHERE id = :i"), {"i": item.id}
        ).scalar()
        assert raw == '{"k": "v"}', "metadata_ stored in the metadata column"

        # And reads back through the ORM attribute.
        db_session.expire_all()
        again = db_session.execute(
            select(ContentItem).where(ContentItem.id == item.id)
        ).scalar_one()
        assert again.metadata_ == '{"k": "v"}'

        db_session.delete(lib)
        db_session.commit()
