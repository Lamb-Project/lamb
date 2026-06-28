"""Unit tests for ``services.import_service`` — direct function calls."""

from __future__ import annotations

import pytest
from _fakes import patch_markitdown
from _helpers import unique_id
from database.models import ContentImage, ContentItem, ImportJob
from services import content_service, import_service
from services.folder_service import create_folder
from services.library_service import create_library
from tasks import worker


@pytest.fixture
def lib(db_session):
    """Create a library and return (organization_id, library_id)."""
    org_id = unique_id("org")
    lib_id = unique_id("lib")
    create_library(db_session, lib_id, org_id, "Import Lib")
    return org_id, lib_id


@pytest.fixture
def storage(tmp_storage, monkeypatch):
    """Point both import_service and content_service at a throwaway CONTENT_DIR."""
    monkeypatch.setattr(import_service, "CONTENT_DIR", tmp_storage)
    monkeypatch.setattr(content_service, "CONTENT_DIR", tmp_storage)
    return tmp_storage


def _get_item(db, item_id):
    return db.query(ContentItem).filter(ContentItem.id == item_id).first()


def _get_job(db, job_id):
    return db.query(ImportJob).filter(ImportJob.id == job_id).first()


# ---------------------------------------------------------------------------
# _validate_folder_id
# ---------------------------------------------------------------------------


def test_validate_folder_id_none_is_noop(db_session, lib):
    """_validate_folder_id accepts None (library root)."""
    _, lib_id = lib
    import_service._validate_folder_id(db_session, lib_id, None)  # no raise


def test_validate_folder_id_valid_passes(db_session, lib):
    """_validate_folder_id accepts a folder in the same library."""
    _, lib_id = lib
    folder = create_folder(db_session, library_id=lib_id, name="F", parent_folder_id=None)
    import_service._validate_folder_id(db_session, lib_id, folder.id)  # no raise


def test_validate_folder_id_missing_raises(db_session, lib):
    """_validate_folder_id raises ValueError for an unknown folder."""
    _, lib_id = lib
    with pytest.raises(ValueError, match="not found"):
        import_service._validate_folder_id(db_session, lib_id, unique_id("ghost"))


def test_validate_folder_id_foreign_raises(db_session, lib):
    """_validate_folder_id raises ValueError for a folder in another library."""
    _, lib_id = lib
    other_lib = unique_id("lib")
    create_library(db_session, other_lib, unique_id("org"), "Other")
    foreign = create_folder(db_session, library_id=other_lib, name="F", parent_folder_id=None)
    with pytest.raises(ValueError, match="different library"):
        import_service._validate_folder_id(db_session, lib_id, foreign.id)


# ---------------------------------------------------------------------------
# queue_* — create pending item + pending job, no api_keys persisted
# ---------------------------------------------------------------------------


def test_queue_file_import_creates_pending_records(db_session, lib):
    """queue_file_import inserts a pending item + job and returns their ids."""
    org_id, lib_id = lib
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="My Doc",
        plugin_name="simple_import",
        file_path="/tmp/upload.txt",
        original_filename="upload.txt",
        content_type="text/plain",
        file_size=42,
        api_keys={"openai": "sk-secret"},
    )
    item = _get_item(db_session, item_id)
    job = _get_job(db_session, job_id)
    assert item.status == "pending"
    assert item.source_type == "file"
    assert item.original_filename == "upload.txt"
    assert job.status == "pending"
    assert job.source_path == "/tmp/upload.txt"
    assert job.plugin_name == "simple_import"


def test_queue_does_not_persist_api_keys(db_session, lib):
    """API keys never land on the ImportJob row (only in worker memory)."""
    org_id, lib_id = lib
    _, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="simple_import",
        file_path="/tmp/u.txt",
        original_filename="u.txt",
        api_keys={"openai": "sk-secret"},
    )
    job = _get_job(db_session, job_id)
    # No column holds the keys; the whole serialized row must not leak them.
    serialized = " ".join(
        str(getattr(job, c.name)) for c in ImportJob.__table__.columns
    )
    assert "sk-secret" not in serialized
    # They are held in the worker's in-memory dict instead.
    assert worker._job_api_keys.get(job_id) == {"openai": "sk-secret"}
    worker._job_api_keys.pop(job_id, None)


def test_queue_url_import_creates_pending(db_session, lib):
    """queue_url_import records a url-source pending item + job."""
    org_id, lib_id = lib
    item_id, job_id = import_service.queue_url_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Page",
        plugin_name="url_import",
        url="https://example.com",
    )
    item = _get_item(db_session, item_id)
    job = _get_job(db_session, job_id)
    assert item.source_type == "url"
    assert item.source_url == "https://example.com"
    assert job.source_url == "https://example.com"
    assert job.source_path is None


def test_queue_youtube_import_creates_pending(db_session, lib):
    """queue_youtube_import records a youtube-source pending item + job."""
    org_id, lib_id = lib
    item_id, job_id = import_service.queue_youtube_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Video",
        plugin_name="youtube_import",
        video_url="https://youtu.be/abc",
    )
    item = _get_item(db_session, item_id)
    assert item.source_type == "youtube"
    assert item.source_url == "https://youtu.be/abc"


def test_queue_file_import_with_folder(db_session, lib):
    """queue_file_import stores the destination folder on the item."""
    org_id, lib_id = lib
    folder = create_folder(db_session, library_id=lib_id, name="Dest", parent_folder_id=None)
    item_id, _ = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="simple_import",
        file_path="/tmp/u.txt",
        original_filename="u.txt",
        folder_id=folder.id,
    )
    assert _get_item(db_session, item_id).folder_id == folder.id


def test_queue_file_import_bad_folder_raises(db_session, lib):
    """queue_file_import propagates folder validation errors."""
    org_id, lib_id = lib
    with pytest.raises(ValueError):
        import_service.queue_file_import(
            db_session,
            library_id=lib_id,
            organization_id=org_id,
            title="Doc",
            plugin_name="simple_import",
            file_path="/tmp/u.txt",
            original_filename="u.txt",
            folder_id=unique_id("ghost"),
        )


# ---------------------------------------------------------------------------
# execute_import_job — success
# ---------------------------------------------------------------------------


def test_execute_import_job_success(storage, db_session, lib):
    """execute_import_job runs the plugin, writes content, marks item ready."""
    org_id, lib_id = lib
    src = storage / "input.md"
    src.write_text("# Title\n\nbody text")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Title",
        plugin_name="simple_import",
        file_path=str(src),
        original_filename="input.md",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    import_service.execute_import_job(db_session, job, api_keys={})

    item = _get_item(db_session, item_id)
    assert item.status == "ready"
    assert item.page_count == 0
    assert item.image_count == 0
    base = storage / org_id / lib_id / item_id
    assert (base / "content" / "full.md").read_text() == "# Title\n\nbody text"
    assert item.full_markdown_path == str(base / "content" / "full.md")
    assert item.content_type == "text/markdown"  # from plugin metadata
    # Temp source file is removed after a successful file import.
    assert not src.exists()


def test_execute_import_job_inserts_image_rows(storage, db_session, lib, monkeypatch):
    """execute_import_job writes ContentImage rows for extracted images."""
    from plugins.base import ExtractedImage, ImportResult, PluginRegistry

    org_id, lib_id = lib
    src = storage / "doc.pdf"
    src.write_bytes(b"%PDF-fake")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="With Images",
        plugin_name="simple_import",
        file_path=str(src),
        original_filename="doc.pdf",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    fake_result = ImportResult(
        full_text="text",
        pages=[],
        images=[
            ExtractedImage(filename="img_001.png", data=b"PNG", page_number=1, description="d"),
        ],
        metadata={"content_type": "application/pdf"},
        source_ref={"type": "file"},
    )

    class _FakePlugin:
        def import_content(self, source, *, api_keys=None, **kwargs):
            return fake_result

    monkeypatch.setattr(PluginRegistry, "get_plugin", staticmethod(lambda name: _FakePlugin()))
    monkeypatch.setattr(PluginRegistry, "sanitize_params", staticmethod(lambda n, p: {}))

    import_service.execute_import_job(db_session, job, api_keys={})

    item = _get_item(db_session, item_id)
    assert item.status == "ready"
    assert item.image_count == 1
    imgs = db_session.query(ContentImage).filter(ContentImage.content_item_id == item_id).all()
    assert len(imgs) == 1
    assert imgs[0].image_path == "content/images/img_001.png"


def test_execute_import_job_plugin_not_found_raises(db_session, lib):
    """execute_import_job raises RuntimeError when the plugin is unknown."""
    org_id, lib_id = lib
    item_id, job_id = import_service.queue_url_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="X",
        plugin_name="does_not_exist",
        url="https://x",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)
    with pytest.raises(RuntimeError, match="Plugin not found"):
        import_service.execute_import_job(db_session, job, api_keys={})


def test_execute_import_job_url_success_no_temp_cleanup(storage, db_session, lib, monkeypatch):
    """A URL job writes content and skips the temp-file cleanup (no source_path)."""
    from plugins.base import ImportResult, PluginRegistry

    org_id, lib_id = lib
    item_id, job_id = import_service.queue_url_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Page",
        plugin_name="url_import",
        url="https://example.com",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    class _FakePlugin:
        def import_content(self, source, *, api_keys=None, **kwargs):
            return ImportResult(
                full_text="scraped",
                metadata={"file_size": 7},
                source_ref={"type": "url"},
            )

    monkeypatch.setattr(PluginRegistry, "get_plugin", staticmethod(lambda name: _FakePlugin()))
    monkeypatch.setattr(PluginRegistry, "sanitize_params", staticmethod(lambda n, p: {}))

    import_service.execute_import_job(db_session, job, api_keys={})
    item = _get_item(db_session, item_id)
    assert item.status == "ready"
    assert item.file_size == 7
    base = storage / org_id / lib_id / item_id
    assert (base / "content" / "full.md").read_text() == "scraped"


def test_execute_import_job_missing_item_raises(storage, db_session, lib, monkeypatch):
    """execute_import_job raises RuntimeError when the ContentItem vanished."""
    from plugins.base import ImportResult, PluginRegistry

    org_id, lib_id = lib
    src = storage / "x.txt"
    src.write_text("body")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="simple_import",
        file_path=str(src),
        original_filename="x.txt",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    class _FakePlugin:
        def import_content(self, source, *, api_keys=None, **kwargs):
            return ImportResult(full_text="t", metadata={}, source_ref={})

    monkeypatch.setattr(PluginRegistry, "get_plugin", staticmethod(lambda name: _FakePlugin()))
    monkeypatch.setattr(PluginRegistry, "sanitize_params", staticmethod(lambda n, p: {}))

    # Delete the item after queueing but before execution.
    db_session.query(ContentItem).filter(ContentItem.id == item_id).delete()
    db_session.commit()

    with pytest.raises(RuntimeError, match="not found"):
        import_service.execute_import_job(db_session, job, api_keys={})


def test_execute_import_job_temp_unlink_failure_is_tolerated(
    storage, db_session, lib, monkeypatch
):
    """A failure to delete the temp source file does not fail the import."""
    from pathlib import Path as _Path

    org_id, lib_id = lib
    src = storage / "keep.md"
    src.write_text("# body")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="simple_import",
        file_path=str(src),
        original_filename="keep.md",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    real_unlink = _Path.unlink

    def _boom_unlink(self, *args, **kwargs):
        if self == src:
            raise OSError("cannot delete")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "unlink", _boom_unlink)
    import_service.execute_import_job(db_session, job, api_keys={})
    assert _get_item(db_session, item_id).status == "ready"


def test_execute_import_job_no_source_raises(storage, db_session, lib):
    """execute_import_job raises RuntimeError when the job has no source."""
    org_id, lib_id = lib
    item_id, job_id = import_service.queue_url_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="X",
        plugin_name="simple_import",
        url="placeholder",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)
    job.source_url = None
    job.source_path = None
    db_session.commit()
    with pytest.raises(RuntimeError, match="no source"):
        import_service.execute_import_job(db_session, job, api_keys={})


# ---------------------------------------------------------------------------
# execute_import_job — failure cleans up the partial dir
# ---------------------------------------------------------------------------


def test_execute_import_job_failure_cleans_dir(storage, db_session, lib, monkeypatch):
    """A write failure rmtree's the partial item directory and re-raises."""
    from plugins.base import ImportResult, PluginRegistry

    org_id, lib_id = lib
    src = storage / "doc.txt"
    src.write_text("body")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="simple_import",
        file_path=str(src),
        original_filename="doc.txt",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    class _FakePlugin:
        def import_content(self, source, *, api_keys=None, **kwargs):
            return ImportResult(full_text="t", metadata={}, source_ref={})

    monkeypatch.setattr(PluginRegistry, "get_plugin", staticmethod(lambda name: _FakePlugin()))
    monkeypatch.setattr(PluginRegistry, "sanitize_params", staticmethod(lambda n, p: {}))

    # Make the disk write blow up after the directory is created.
    item_dir = storage / org_id / lib_id / item_id

    def _boom(**kwargs):
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "marker").write_text("partial")
        raise RuntimeError("disk full")

    monkeypatch.setattr(content_service, "write_structured_content", _boom)

    with pytest.raises(RuntimeError, match="disk full"):
        import_service.execute_import_job(db_session, job, api_keys={})

    assert not item_dir.exists()  # Partial dir removed.


def test_execute_import_job_markitdown_failure_propagates(storage, db_session, lib):
    """A plugin that raises inside import_content propagates (item not ready)."""
    org_id, lib_id = lib
    src = storage / "doc.docx"
    src.write_bytes(b"fake-docx")
    item_id, job_id = import_service.queue_file_import(
        db_session,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        plugin_name="markitdown_import",
        file_path=str(src),
        original_filename="doc.docx",
    )
    worker._job_api_keys.pop(job_id, None)
    job = _get_job(db_session, job_id)

    with patch_markitdown(raises=RuntimeError("conversion boom")), pytest.raises(Exception):
        import_service.execute_import_job(db_session, job, api_keys={})

    db_session.rollback()
    item = _get_item(db_session, item_id)
    # The item never reached ``ready`` — the service layer leaves status
    # handling to the worker, so it stays at its pre-execution value.
    assert item.status != "ready"
