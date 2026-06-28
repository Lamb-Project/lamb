"""Unit tests for ``services.content_service`` — direct function calls."""

from __future__ import annotations

import json

import pytest
from _helpers import unique_id
from database.models import ContentItem
from plugins.base import ExtractedImage, PageContent
from services import content_service
from services.library_service import create_library


@pytest.fixture
def storage(tmp_storage, monkeypatch):
    """Point content_service at a throwaway CONTENT_DIR."""
    monkeypatch.setattr(content_service, "CONTENT_DIR", tmp_storage)
    return tmp_storage


def _write_sample(org, lib, item, *, pages=True, images=True, original=None):
    """Write a structured content item and return its base path."""
    page_list = (
        [PageContent(page_number=1, text="page one"), PageContent(page_number=2, text="page two")]
        if pages
        else []
    )
    image_list = (
        [
            ExtractedImage(
                filename="img_001.png", data=b"\x89PNG-bytes", page_number=1, description="d"
            )
        ]
        if images
        else []
    )
    return content_service.write_structured_content(
        item_id=item,
        library_id=lib,
        organization_id=org,
        title="Doc Title",
        full_text="# Full\n\nbody",
        pages=page_list,
        images=image_list,
        item_metadata={"language": "en", "character_count": 12},
        source_ref={"type": "file", "original_filename": "src.txt"},
        original_file_path=original,
        original_filename="src.txt" if original else None,
    )


# ---------------------------------------------------------------------------
# write_structured_content + detect_capabilities
# ---------------------------------------------------------------------------


def test_write_structured_content_creates_full_tree(storage):
    """write_structured_content writes metadata, source_ref, pages, images, full.md."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    base = _write_sample(org, lib, item)
    assert (base / "metadata.json").is_file()
    assert (base / "source_ref.json").is_file()
    assert (base / "content" / "full.md").read_text() == "# Full\n\nbody"
    assert (base / "content" / "pages" / "page_001.md").read_text() == "page one"
    assert (base / "content" / "pages" / "page_002.md").read_text() == "page two"
    assert (base / "content" / "images" / "img_001.png").read_bytes() == b"\x89PNG-bytes"


def test_write_structured_content_copies_original(storage, tmp_storage):
    """write_structured_content copies the original file into original/."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    src = tmp_storage / "upload.txt"
    src.write_text("raw original")
    base = _write_sample(org, lib, item, original=src)
    assert (base / "original" / "src.txt").read_text() == "raw original"
    meta = json.loads((base / "metadata.json").read_text())
    assert meta["permalinks"]["original"].endswith("/original/src.txt")


def test_write_structured_content_metadata_has_capabilities(storage):
    """metadata.json reflects the on-disk capabilities (text, pages, images)."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    base = _write_sample(org, lib, item)
    meta = json.loads((base / "metadata.json").read_text())
    assert sorted(meta["capabilities"]) == ["images", "pages", "text"]
    assert meta["title"] == "Doc Title"
    assert meta["language"] == "en"


def test_write_structured_content_permission_error_humanized(storage, monkeypatch):
    """A PermissionError on mkdir becomes a user-actionable RuntimeError."""
    from pathlib import Path

    def _deny(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "mkdir", _deny)
    with pytest.raises(RuntimeError, match="not writable"):
        _write_sample(unique_id("org"), unique_id("lib"), unique_id("item"))


def test_write_structured_content_oserror_humanized(storage, monkeypatch):
    """A generic OSError on mkdir becomes a storage-unavailable RuntimeError."""
    from pathlib import Path

    def _fail(self, *args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "mkdir", _fail)
    with pytest.raises(RuntimeError, match="storage is"):
        _write_sample(unique_id("org"), unique_id("lib"), unique_id("item"))


def test_detect_capabilities_text_only(storage):
    """detect_capabilities returns only ``text`` when there are no pages/images."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    base = _write_sample(org, lib, item, pages=False, images=False)
    assert content_service.detect_capabilities(base) == ["text"]


def test_detect_capabilities_empty_when_no_content_dir(tmp_storage):
    """detect_capabilities returns [] when no content/ directory exists."""
    assert content_service.detect_capabilities(tmp_storage / "ghost") == []


def test_detect_capabilities_ignores_non_image_files(storage, tmp_storage):
    """detect_capabilities does not advertise images for non-image files."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    base = _write_sample(org, lib, item, pages=False, images=False)
    images_dir = base / "content" / "images"
    images_dir.mkdir()
    (images_dir / "notes.txt").write_text("not an image")
    assert "images" not in content_service.detect_capabilities(base)


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def test_read_full_markdown(storage):
    """read_full_markdown returns the full.md contents."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.read_full_markdown(org, lib, item) == "# Full\n\nbody"


def test_read_full_markdown_missing_returns_none(storage):
    """read_full_markdown returns None when the file is absent."""
    assert content_service.read_full_markdown("o", "l", "missing") is None


def test_read_page_markdown_with_and_without_extension(storage):
    """read_page_markdown accepts the page name with or without ``.md``."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.read_page_markdown(org, lib, item, "page_001.md") == "page one"
    assert content_service.read_page_markdown(org, lib, item, "page_002") == "page two"


def test_read_page_markdown_missing_returns_none(storage):
    """read_page_markdown returns None for a non-existent page."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.read_page_markdown(org, lib, item, "page_999") is None


def test_read_metadata_json(storage):
    """read_metadata_json parses and returns metadata.json."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    meta = content_service.read_metadata_json(org, lib, item)
    assert meta["item_id"] == item


def test_read_metadata_json_missing_returns_none(storage):
    """read_metadata_json returns None when metadata.json is absent."""
    assert content_service.read_metadata_json("o", "l", "missing") is None


def test_read_source_ref(storage):
    """read_source_ref parses and returns source_ref.json."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    ref = content_service.read_source_ref(org, lib, item)
    assert ref["original_filename"] == "src.txt"


def test_read_source_ref_missing_returns_none(storage):
    """read_source_ref returns None when source_ref.json is absent."""
    assert content_service.read_source_ref("o", "l", "missing") is None


def test_list_pages(storage):
    """list_pages returns sorted page filenames."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.list_pages(org, lib, item) == ["page_001.md", "page_002.md"]


def test_list_pages_empty_when_no_dir(storage):
    """list_pages returns [] when there is no pages directory."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item, pages=False)
    assert content_service.list_pages(org, lib, item) == []


def test_list_images(storage):
    """list_images returns sorted image filenames."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.list_images(org, lib, item) == ["img_001.png"]


def test_list_images_empty_when_no_dir(storage):
    """list_images returns [] when there is no images directory."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item, images=False)
    assert content_service.list_images(org, lib, item) == []


def test_get_image_path_resolves(storage):
    """get_image_path returns the path to an existing image file."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    path = content_service.get_image_path(org, lib, item, "img_001.png")
    assert path is not None and path.is_file()


def test_get_image_path_missing_returns_none(storage):
    """get_image_path returns None for a non-existent image."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.get_image_path(org, lib, item, "nope.png") is None


def test_get_original_path_resolves(storage, tmp_storage):
    """get_original_path returns the path to the stored original file."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    src = tmp_storage / "upload.txt"
    src.write_text("raw")
    _write_sample(org, lib, item, original=src)
    path = content_service.get_original_path(org, lib, item, "src.txt")
    assert path is not None and path.is_file()


def test_get_original_path_missing_returns_none(storage):
    """get_original_path returns None when no original file is stored."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.get_original_path(org, lib, item, "src.txt") is None


# ---------------------------------------------------------------------------
# Path-traversal guards
# ---------------------------------------------------------------------------


def test_safe_resolve_blocks_traversal(tmp_storage):
    """_safe_resolve returns None when the path escapes the expected parent."""
    base = tmp_storage / "item"
    base.mkdir()
    escaped = base / ".." / ".." / "etc" / "passwd"
    assert content_service._safe_resolve(escaped, base) is None


def test_safe_resolve_allows_inside(tmp_storage):
    """_safe_resolve returns the resolved path when it stays inside the parent."""
    base = tmp_storage / "item"
    base.mkdir()
    inside = base / "content" / "full.md"
    resolved = content_service._safe_resolve(inside, base)
    assert resolved is not None


def test_read_page_markdown_traversal_sanitized(storage):
    """read_page_markdown sanitizes ``../`` page names to a single component."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    # Sanitization strips directory components, so it cannot escape; returns None.
    assert content_service.read_page_markdown(org, lib, item, "../../../etc/passwd") is None


def test_get_image_path_traversal_sanitized(storage):
    """get_image_path sanitizes traversal attempts in the image name."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    _write_sample(org, lib, item)
    assert content_service.get_image_path(org, lib, item, "../../secret.png") is None


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_filename_strips_directories():
    """_sanitize_filename keeps only the final path component."""
    assert content_service._sanitize_filename("../../etc/passwd") == "passwd"
    assert content_service._sanitize_filename("/abs/path/file.png") == "file.png"


def test_sanitize_filename_strips_null_bytes():
    """_sanitize_filename removes embedded null bytes."""
    assert content_service._sanitize_filename("a\x00b.txt") == "ab.txt"


def test_sanitize_filename_fallback_for_empty():
    """_sanitize_filename falls back to ``unnamed`` for empty/dot names."""
    assert content_service._sanitize_filename("") == "unnamed"
    assert content_service._sanitize_filename(".") == "unnamed"
    assert content_service._sanitize_filename("..") == "unnamed"


# ---------------------------------------------------------------------------
# delete_content_item
# ---------------------------------------------------------------------------


def test_delete_content_item_removes_row_and_disk(storage, db_session):
    """delete_content_item removes the DB row and the on-disk directory."""
    org, lib, item_id = unique_id("org"), unique_id("lib"), unique_id("item")
    create_library(db_session, lib, org, "Lib")
    base = _write_sample(org, lib, item_id)
    db_session.add(
        ContentItem(
            id=item_id,
            library_id=lib,
            organization_id=org,
            title="t",
            source_type="file",
            base_path=str(base),
            permalink_base="/docs/x",
            import_plugin="simple_import",
            status="ready",
        )
    )
    db_session.commit()
    assert content_service.delete_content_item(db_session, org, lib, item_id) is True
    assert content_service.get_content_item(db_session, item_id) is None
    assert not base.exists()


def test_delete_content_item_missing_returns_false(storage, db_session):
    """delete_content_item returns False for an unknown item."""
    assert content_service.delete_content_item(db_session, "o", "l", unique_id("x")) is False


def test_delete_content_item_no_disk_dir(storage, db_session):
    """delete_content_item still succeeds when there is no on-disk directory."""
    org, lib, item_id = unique_id("org"), unique_id("lib"), unique_id("item")
    create_library(db_session, lib, org, "Lib")
    db_session.add(
        ContentItem(
            id=item_id,
            library_id=lib,
            organization_id=org,
            title="t",
            source_type="file",
            base_path="/tmp/none",
            permalink_base="/docs/x",
            import_plugin="simple_import",
            status="ready",
        )
    )
    db_session.commit()
    # No directory was written for this item.
    assert content_service.delete_content_item(db_session, org, lib, item_id) is True


def test_detect_capabilities_pages_without_full_md(storage):
    """detect_capabilities reports ``pages`` even when full.md is absent."""
    org, lib, item = unique_id("org"), unique_id("lib"), unique_id("item")
    base = _write_sample(org, lib, item, pages=True, images=False)
    (base / "content" / "full.md").unlink()
    caps = content_service.detect_capabilities(base)
    assert "pages" in caps
    assert "text" not in caps


# ---------------------------------------------------------------------------
# get_content_item / item_to_summary / list_content_items
# ---------------------------------------------------------------------------


def _insert_item(db, lib, org, **overrides):
    """Insert a content item directly into the DB."""
    overrides.setdefault("status", "ready")
    item = ContentItem(
        id=unique_id("item"),
        library_id=lib,
        organization_id=org,
        title="T",
        source_type="file",
        base_path="/tmp/x",
        permalink_base="/docs/x",
        import_plugin="simple_import",
        **overrides,
    )
    db.add(item)
    db.commit()
    return item


def test_get_content_item_returns_row(db_session):
    """get_content_item returns the matching row."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    item = _insert_item(db_session, lib, org)
    assert content_service.get_content_item(db_session, item.id).id == item.id


def test_get_content_item_missing_returns_none(db_session):
    """get_content_item returns None for an unknown id."""
    assert content_service.get_content_item(db_session, unique_id("x")) is None


def test_item_to_summary_shape():
    """item_to_summary exposes the canonical API summary keys."""
    item = ContentItem(
        id="i1",
        library_id="l1",
        organization_id="o1",
        title="T",
        source_type="url",
        source_url="http://x",
        original_filename="f.txt",
        content_type="text/plain",
        file_size=10,
        import_plugin="url_import",
        status="ready",
        error_message=None,
        page_count=3,
        image_count=2,
        folder_id="fold1",
        base_path="/x",
        permalink_base="/docs/x",
    )
    summary = content_service.item_to_summary(item)
    assert summary["id"] == "i1"
    assert summary["page_count"] == 3
    assert summary["folder_id"] == "fold1"
    assert summary["source_url"] == "http://x"
    assert set(summary) == {
        "id", "title", "source_type", "source_url", "original_filename",
        "content_type", "file_size", "import_plugin", "status", "error_message",
        "page_count", "image_count", "folder_id", "created_at", "updated_at",
    }


def test_list_content_items_filters_by_library(db_session):
    """list_content_items returns only the requested library's items."""
    org, lib = unique_id("org"), unique_id("lib")
    other = unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    create_library(db_session, other, org, "Other")
    _insert_item(db_session, lib, org)
    _insert_item(db_session, lib, org)
    _insert_item(db_session, other, org)
    items, total = content_service.list_content_items(db_session, lib)
    assert total == 2
    assert all(i.library_id == lib for i in items)


def test_list_content_items_status_filter(db_session):
    """list_content_items honors the status filter."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    _insert_item(db_session, lib, org, status="ready")
    _insert_item(db_session, lib, org, status="failed")
    items, total = content_service.list_content_items(db_session, lib, status_filter="failed")
    assert total == 1
    assert items[0].status == "failed"


def test_list_content_items_ids_filter_and_pagination(db_session):
    """list_content_items supports an id filter plus limit/offset."""
    org, lib = unique_id("org"), unique_id("lib")
    create_library(db_session, lib, org, "Lib")
    a = _insert_item(db_session, lib, org)
    b = _insert_item(db_session, lib, org)
    _insert_item(db_session, lib, org)
    items, total = content_service.list_content_items(
        db_session, lib, ids_filter=[a.id, b.id]
    )
    assert total == 2
    page, total2 = content_service.list_content_items(db_session, lib, limit=1, offset=0)
    assert total2 == 3
    assert len(page) == 1


def test_get_item_base_path_layout(storage, tmp_storage):
    """get_item_base_path composes {CONTENT_DIR}/{org}/{lib}/{item}."""
    path = content_service.get_item_base_path("o", "l", "i")
    assert path == tmp_storage / "o" / "l" / "i"
