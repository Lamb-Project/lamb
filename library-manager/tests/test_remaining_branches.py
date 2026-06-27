"""Coverage for the remaining small branch-added lines across library-manager:
the folder_id migration, plugin-discovery failure, markitdown error humanizer,
capability registry edge cases, handler 'unavailable' guards, and the simple/
markitdown import error paths.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# database._apply_lightweight_migrations (adds content_items.folder_id)
# ---------------------------------------------------------------------------


def test_apply_migration_adds_folder_id(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine

    from database.connection import _apply_lightweight_migrations

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        "CREATE TABLE content_items (id TEXT PRIMARY KEY, library_id TEXT);"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db}")
    _apply_lightweight_migrations(engine)  # should ADD COLUMN folder_id
    engine.dispose()

    conn = sqlite3.connect(str(db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(content_items)")}
    conn.close()
    assert "folder_id" in cols


# ---------------------------------------------------------------------------
# main._discover_plugins import failure
# ---------------------------------------------------------------------------


def test_discover_plugins_bad_package():
    import main

    main._discover_plugins("nonexistent_pkg_zzz")  # logged + return, no raise


# ---------------------------------------------------------------------------
# _markitdown_errors fallback
# ---------------------------------------------------------------------------


def test_humanize_missing_dependency_no_format():
    from plugins._markitdown_errors import humanize_markitdown_error

    exc = type("MissingDependencyException", (Exception,), {})("opaque failure")
    # filename without a recognisable extension -> generic reader fallback.
    msg = humanize_markitdown_error(exc, "documentwithoutext")
    assert "required reader" in msg


def test_humanize_generic_fallback():
    from plugins._markitdown_errors import humanize_markitdown_error

    msg = humanize_markitdown_error(RuntimeError("weird"), "x.bin")
    assert "x.bin" in msg


# ---------------------------------------------------------------------------
# CapabilityRegistry edge cases
# ---------------------------------------------------------------------------


def test_capability_registry_register_validation_and_dup(caplog):
    from plugins.content_handlers.capability import (
        Capability,
        CapabilityRegistry,
        ContentHandler,
    )

    saved = dict(CapabilityRegistry._handlers)
    try:
        # Handler without a Capability attribute -> ValueError.
        class _BadHandler(ContentHandler):
            def get(self, item_path):
                raise NotImplementedError

        with pytest.raises(ValueError, match="must set"):
            CapabilityRegistry.register(_BadHandler)

        # Duplicate capability -> replace-with-warning branch.
        class _H1(ContentHandler):
            capability = Capability.TEXT

            def get(self, item_path):
                raise NotImplementedError

        class _H2(ContentHandler):
            capability = Capability.TEXT

            def get(self, item_path):
                raise NotImplementedError

        CapabilityRegistry.register(_H1)
        CapabilityRegistry.register(_H2)  # logs "already registered ... replacing"
    finally:
        CapabilityRegistry._handlers.clear()
        CapabilityRegistry._handlers.update(saved)


def test_capability_registry_get_unknown_string():
    from plugins.content_handlers.capability import CapabilityRegistry

    # A string that isn't a valid Capability -> None.
    assert CapabilityRegistry.get("not-a-capability") is None


def test_capability_registry_reset():
    from plugins.content_handlers.capability import CapabilityRegistry

    saved = dict(CapabilityRegistry._handlers)
    try:
        CapabilityRegistry._reset()
        assert CapabilityRegistry._handlers == {}
    finally:
        CapabilityRegistry._handlers.update(saved)


# ---------------------------------------------------------------------------
# Handler "unavailable" guards (dir exists but empty)
# ---------------------------------------------------------------------------


def test_images_handler_unavailable_when_empty(tmp_path):
    from plugins.content_handlers.capability import HandlerUnavailable
    from plugins.content_handlers.images_handler import ImagesHandler

    (tmp_path / "content" / "images").mkdir(parents=True)  # exists but empty
    with pytest.raises(HandlerUnavailable):
        ImagesHandler().get(tmp_path)


def test_pages_handler_unavailable_when_empty(tmp_path):
    from plugins.content_handlers.capability import HandlerUnavailable
    from plugins.content_handlers.pages_handler import PagesHandler

    (tmp_path / "content" / "pages").mkdir(parents=True)  # exists but empty
    with pytest.raises(HandlerUnavailable):
        PagesHandler().get(tmp_path)


# ---------------------------------------------------------------------------
# import plugin error paths
# ---------------------------------------------------------------------------


def test_simple_import_non_utf8(tmp_path):
    from plugins.simple_import import SimpleImportPlugin

    f = tmp_path / "bad.md"
    f.write_bytes(b"\xff\xfe invalid utf-8 \x80")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        SimpleImportPlugin().import_content(str(f))


def test_markitdown_import_conversion_error(tmp_path, monkeypatch):
    import markitdown

    class FakeMD:
        def convert(self, path):
            raise RuntimeError("boom")

    monkeypatch.setattr(markitdown, "MarkItDown", FakeMD)
    f = tmp_path / "doc.docx"
    f.write_bytes(b"x")
    from plugins.markitdown_import import MarkItDownImportPlugin

    with pytest.raises(RuntimeError):
        MarkItDownImportPlugin().import_content(str(f))


# ---------------------------------------------------------------------------
# schemas.folders name validation
# ---------------------------------------------------------------------------


def test_folder_name_too_long_rejected():
    from pydantic import ValidationError

    from schemas.folders import FolderCreateRequest

    with pytest.raises(ValidationError):
        FolderCreateRequest(name="x" * 1000)


# ---------------------------------------------------------------------------
# url_import firecrawl object-doc with dict metadata
# ---------------------------------------------------------------------------


def test_validate_folder_name_too_long_direct():
    # The schema's Field(max_length=128) rejects over-long names before the
    # validator runs, so the validator's own length guard is only reachable
    # by calling it directly.
    from schemas.folders import _validate_folder_name

    with pytest.raises(ValueError, match="cannot exceed"):
        _validate_folder_name("x" * 200)


def test_detect_capabilities_no_content_dir(tmp_path):
    # No content/ directory -> early return with an empty capability list.
    from services.content_service import detect_capabilities

    assert detect_capabilities(tmp_path) == []


def test_url_import_firecrawl_object_doc_dict_metadata(monkeypatch):
    import firecrawl

    class _Doc:
        markdown = "# page\n\nbody"
        metadata = {"sourceURL": "https://x/p", "title": "P"}  # dict metadata

    class _Result:
        data = [_Doc()]

    class FakeApp:
        def __init__(self, **kw):
            pass

        def crawl(self, url, **kw):
            return _Result()

    monkeypatch.setattr(firecrawl, "FirecrawlApp", FakeApp)
    from plugins.url_import import UrlImportPlugin

    result = UrlImportPlugin().import_content(
        "https://x", api_keys={"firecrawl_key": "fc"}
    )
    assert "## P" in result.full_text
    assert "https://x/p" in result.full_text
