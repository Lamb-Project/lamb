"""Unit tests for ``services.export_service`` — direct function calls."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest
from _helpers import unique_id
from database.models import ContentItem
from services import export_service
from services.library_service import create_library, get_library


@pytest.fixture
def storage(tmp_storage, monkeypatch):
    """Point export_service at a throwaway CONTENT_DIR."""
    monkeypatch.setattr(export_service, "CONTENT_DIR", tmp_storage)
    return tmp_storage


def _write_item_dir(base, org, lib, item_id):
    """Materialize a minimal structured-content directory for an item."""
    item_dir = base / org / lib / item_id
    (item_dir / "content" / "pages").mkdir(parents=True)
    (item_dir / "content" / "images").mkdir(parents=True)
    (item_dir / "original").mkdir(parents=True)
    (item_dir / "content" / "full.md").write_text("# body")
    (item_dir / "content" / "pages" / "page_001.md").write_text("p1")
    (item_dir / "content" / "images" / "img_001.png").write_bytes(b"PNG")
    (item_dir / "original" / "src.txt").write_text("orig")
    (item_dir / "metadata.json").write_text(json.dumps({"item_id": item_id}))
    return item_dir


def _insert_item(db, lib, org, item_id, *, status="ready", **overrides):
    """Insert a content item row for export."""
    item = ContentItem(
        id=item_id,
        library_id=lib,
        organization_id=org,
        title="Doc",
        source_type="file",
        original_filename="src.txt",
        content_type="text/plain",
        import_plugin="simple_import",
        import_params=json.dumps({"x": 1}),
        metadata_=json.dumps({"page_count": 1, "language": "en"}),
        base_path="/tmp/x",
        permalink_base="/docs/x",
        status=status,
        **overrides,
    )
    db.add(item)
    db.commit()
    return item


# ---------------------------------------------------------------------------
# export_library_zip
# ---------------------------------------------------------------------------


def test_export_library_zip_manifest_and_content(storage, db_session):
    """export_library_zip writes a v1.0 manifest plus each ready item's files."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    item_id = unique_id("item")
    _write_item_dir(storage, org, lib, item_id)
    _insert_item(db_session, lib, org, item_id)

    buf = export_service.export_library_zip(
        db_session, lib, org, "Lib", {"plugin": "simple_import"}, exported_by="me@x"
    )
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format_version"] == "1.0"
    assert manifest["type"] == "library_export"
    assert manifest["exported_by"] == "me@x"
    assert manifest["items"][0]["id"] == item_id
    assert f"content/{item_id}/content/full.md" in names
    assert f"content/{item_id}/metadata.json" in names


def test_export_library_zip_excludes_non_ready(storage, db_session):
    """export_library_zip omits items whose status is not ready."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    ready_id = unique_id("item")
    pending_id = unique_id("item")
    _write_item_dir(storage, org, lib, ready_id)
    _write_item_dir(storage, org, lib, pending_id)
    _insert_item(db_session, lib, org, ready_id, status="ready")
    _insert_item(db_session, lib, org, pending_id, status="pending")

    buf = export_service.export_library_zip(db_session, lib, org, "Lib", None)
    with zipfile.ZipFile(buf) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        names = zf.namelist()
    ids = {i["id"] for i in manifest["items"]}
    assert ids == {ready_id}
    assert not any(pending_id in n for n in names)


def test_export_library_zip_missing_dir_still_lists_item(storage, db_session):
    """An item with no on-disk dir is still listed in the manifest."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    item_id = unique_id("item")
    _insert_item(db_session, lib, org, item_id)  # no dir written
    buf = export_service.export_library_zip(db_session, lib, org, "Lib", None)
    with zipfile.ZipFile(buf) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["items"][0]["id"] == item_id


# ---------------------------------------------------------------------------
# import_library_zip — round trip
# ---------------------------------------------------------------------------


def _build_zip(manifest, files):
    """Build an in-memory ZIP with manifest.json and the given arcname->bytes."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for arcname, data in files.items():
            zf.writestr(arcname, data)
    return buf.getvalue()


def test_import_library_zip_round_trip(storage, db_session):
    """import_library_zip recreates a library with new IDs and ready items."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Export Source")
    item_id = unique_id("item")
    _write_item_dir(storage, org, lib, item_id)
    _insert_item(db_session, lib, org, item_id)

    zip_bytes = export_service.export_library_zip(
        db_session, lib, org, "Export Source", {"plugin": "simple_import"}
    ).getvalue()

    target_org = unique_id("org")
    result = export_service.import_library_zip(db_session, zip_bytes, target_org)
    assert result["item_count"] == 1
    assert result["library_id"] != lib  # New library ID generated.
    assert result["library_name"] == "Export Source"

    new_lib = get_library(db_session, result["library_id"])
    assert new_lib.organization_id == target_org
    new_items = (
        db_session.query(ContentItem)
        .filter(ContentItem.library_id == result["library_id"])
        .all()
    )
    assert len(new_items) == 1
    new_item = new_items[0]
    assert new_item.id != item_id  # New item ID generated.
    assert new_item.status == "ready"
    assert new_item.page_count == 1
    assert new_item.image_count == 1
    # Permalink regenerated under the new org/lib/item.
    assert new_item.permalink_base.endswith(f"/{target_org}/{result['library_id']}/{new_item.id}")
    # Files landed on disk under the new path.
    new_dir = storage / target_org / result["library_id"] / new_item.id
    assert (new_dir / "content" / "full.md").read_text() == "# body"
    meta = json.loads((new_dir / "metadata.json").read_text())
    assert meta["item_id"] == new_item.id
    assert meta["permalinks"]["original"].endswith("/original/src.txt")
    assert meta["page_count"] == 1
    assert meta["language"] == "en"


def test_import_library_zip_bad_zip_raises(db_session):
    """import_library_zip raises ValueError on a corrupt ZIP."""
    with pytest.raises(ValueError, match="Invalid ZIP"):
        export_service.import_library_zip(db_session, b"not a zip", unique_id("org"))


def test_import_library_zip_missing_manifest_raises(db_session):
    """import_library_zip raises ValueError when manifest.json is absent."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content/foo.txt", b"x")
    with pytest.raises(ValueError, match="missing manifest"):
        export_service.import_library_zip(db_session, buf.getvalue(), unique_id("org"))


def test_import_library_zip_bad_format_version_raises(db_session):
    """import_library_zip rejects an unsupported manifest format_version."""
    manifest = {"format_version": "2.0", "type": "library_export", "library": {}, "items": []}
    with pytest.raises(ValueError, match="Unsupported manifest version"):
        export_service.import_library_zip(
            db_session, _build_zip(manifest, {}), unique_id("org")
        )


def test_import_library_zip_bad_type_raises(db_session):
    """import_library_zip rejects an unexpected manifest type."""
    manifest = {"format_version": "1.0", "type": "not_a_library", "library": {}, "items": []}
    with pytest.raises(ValueError, match="Unexpected manifest type"):
        export_service.import_library_zip(
            db_session, _build_zip(manifest, {}), unique_id("org")
        )


def test_import_library_zip_default_name_when_missing(storage, db_session):
    """import_library_zip synthesizes a name when the manifest omits one."""
    manifest = {
        "format_version": "1.0",
        "type": "library_export",
        "library": {},
        "items": [],
    }
    result = export_service.import_library_zip(
        db_session, _build_zip(manifest, {}), unique_id("org")
    )
    assert result["library_name"].startswith("Imported Library ")
    assert result["item_count"] == 0


def test_import_library_zip_blocks_zip_slip(storage, db_session):
    """import_library_zip skips entries that try to escape via ``../``."""
    item_id = "evil-item"
    manifest = {
        "format_version": "1.0",
        "type": "library_export",
        "library": {"name": "Slip"},
        "items": [{"id": item_id, "title": "Evil"}],
    }
    files = {
        f"content/{item_id}/content/full.md": b"safe",
        f"content/{item_id}/../../../escape.txt": b"pwned",
    }
    target_org = unique_id("org")
    result = export_service.import_library_zip(
        db_session, _build_zip(manifest, files), target_org
    )
    new_dir = storage / target_org / result["library_id"]
    # The legitimate file landed; the escape file did not appear anywhere.
    assert any(p.name == "full.md" for p in new_dir.rglob("*"))
    assert not (storage / "escape.txt").exists()
    assert not (storage.parent / "escape.txt").exists()


# ---------------------------------------------------------------------------
# _regenerate_metadata
# ---------------------------------------------------------------------------


def test_regenerate_metadata_builds_permalinks(tmp_storage):
    """_regenerate_metadata rebuilds permalinks and merges manifest extras."""
    item_dir = tmp_storage / "item"
    (item_dir / "content" / "pages").mkdir(parents=True)
    (item_dir / "content" / "images").mkdir(parents=True)
    (item_dir / "original").mkdir(parents=True)
    (item_dir / "content" / "pages" / "page_001.md").write_text("p")
    (item_dir / "content" / "images" / "i.png").write_bytes(b"x")
    (item_dir / "original" / "o.txt").write_text("o")

    manifest = {
        "title": "Title",
        "source_type": "file",
        "original_filename": "o.txt",
        "content_type": "text/plain",
        "import_plugin": "simple_import",
        "metadata": {"page_count": 1, "language": "es", "description": "d"},
    }
    export_service._regenerate_metadata(item_dir, "new-id", "/docs/o/l/new-id", manifest)
    meta = json.loads((item_dir / "metadata.json").read_text())
    assert meta["item_id"] == "new-id"
    assert meta["permalinks"]["full_markdown"] == "/docs/o/l/new-id/content/full.md"
    assert meta["permalinks"]["pages"] == ["/docs/o/l/new-id/content/pages/page_001.md"]
    assert meta["permalinks"]["images"] == ["/docs/o/l/new-id/content/images/i.png"]
    assert meta["permalinks"]["original"] == "/docs/o/l/new-id/original/o.txt"
    assert meta["language"] == "es"
    assert meta["description"] == "d"


def test_regenerate_metadata_no_subdirs(tmp_storage):
    """_regenerate_metadata handles items with no pages/images/original."""
    item_dir = tmp_storage / "bare"
    item_dir.mkdir()
    export_service._regenerate_metadata(item_dir, "id2", "/docs/o/l/id2", {"title": "T"})
    meta = json.loads((item_dir / "metadata.json").read_text())
    assert meta["permalinks"]["pages"] == []
    assert meta["permalinks"]["images"] == []
    assert meta["permalinks"]["original"] is None
