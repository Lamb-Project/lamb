"""Tests for library commands — lamb library *."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()


SAMPLE_LIBRARIES = {
    "libraries": [
        {
            "id": "lib-1",
            "name": "Course Materials",
            "description": "Intro to CS",
            "item_count": 12,
            "is_shared": False,
            "owner": "user1",
            "created_at": "2026-04-01T00:00:00Z",
        },
        {
            "id": "lib-2",
            "name": "Lab Notes",
            "description": "Weekly labs",
            "item_count": 3,
            "is_shared": True,
            "owner": "user1",
            "created_at": "2026-04-15T00:00:00Z",
        },
    ]
}

SAMPLE_LIBRARY = {
    "id": "lib-1",
    "name": "Course Materials",
    "description": "Intro to CS",
    "item_count": 12,
    "is_shared": False,
    "owner": "user1",
    "created_at": "2026-04-01T00:00:00Z",
}

SAMPLE_ITEMS = {
    "items": [
        {
            "id": "item-1",
            "title": "Chapter 1",
            "source_type": "file",
            "import_plugin": "simple_import",
            "status": "ready",
            "page_count": 8,
            "image_count": 0,
            "created_at": "2026-04-01T01:00:00Z",
        },
        {
            "id": "item-2",
            "title": "Lecture Video",
            "source_type": "youtube",
            "import_plugin": "youtube_transcript_import",
            "status": "ready",
            "page_count": 1,
            "image_count": 0,
            "created_at": "2026-04-02T01:00:00Z",
        },
    ]
}

SAMPLE_ITEM_DETAIL = {
    "id": "item-1",
    "title": "Chapter 1",
    "source_type": "file",
    "original_filename": "ch1.pdf",
    "content_type": "application/pdf",
    "file_size": 1024,
    "import_plugin": "simple_import",
    "status": "ready",
    "page_count": 8,
    "image_count": 0,
    "permalink_base": "/docs/lib-1/item-1",
    "created_at": "2026-04-01T01:00:00Z",
    "updated_at": "2026-04-01T01:05:00Z",
}

SAMPLE_PLUGINS = {
    "plugins": [
        {
            "name": "simple_import",
            "description": "Direct file import",
            "supported_source_types": ["file"],
        },
        {
            "name": "youtube_transcript_import",
            "description": "YouTube transcripts",
            "supported_source_types": ["youtube"],
        },
    ]
}


# ---------------------------------------------------------------------------
# list / get / create
# ---------------------------------------------------------------------------


class TestLibraryList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARIES)
        result = runner.invoke(app, ["library", "list"])
        assert result.exit_code == 0
        assert "Course Materials" in result.output
        assert "Lab Notes" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARIES)
        result = runner.invoke(app, ["library", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["id"] == "lib-1"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARIES)
        result = runner.invoke(app, ["library", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "lib-1" in lines[0]

    def test_list_request_url(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARIES)
        runner.invoke(app, ["library", "list"])
        req = httpx_mock.get_request()
        assert "/creator/libraries" in str(req.url)


class TestLibraryCreate:
    def test_create_with_description(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"id": "lib-new", "name": "New Lib", "description": "desc"})
        result = runner.invoke(
            app, ["library", "create", "New Lib", "--description", "desc"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "New Lib"
        assert body["description"] == "desc"

    def test_create_without_description(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"id": "lib-new", "name": "Plain"})
        result = runner.invoke(app, ["library", "create", "Plain"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Plain"
        # description should not be set when empty
        assert "description" not in body

    def test_create_missing_name_errors(self, mock_token):
        result = runner.invoke(app, ["library", "create"])
        assert result.exit_code != 0


class TestLibraryGet:
    def test_get_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARY)
        result = runner.invoke(app, ["library", "get", "lib-1"])
        assert result.exit_code == 0
        assert "Course Materials" in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_LIBRARY)
        result = runner.invoke(app, ["library", "get", "lib-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "lib-1"

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["library", "get", "lib-999"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# delete / share
# ---------------------------------------------------------------------------


class TestLibraryDelete:
    def test_delete_with_y_flag(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Library deleted"})
        result = runner.invoke(app, ["library", "delete", "lib-1", "-y"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert req.method == "DELETE"
        assert "/creator/libraries/lib-1" in str(req.url)

    def test_delete_with_no_rejection(self, mock_token):
        result = runner.invoke(app, ["library", "delete", "lib-1"], input="n\n")
        assert result.exit_code != 0


class TestLibraryShare:
    def test_share_enable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": True})
        result = runner.invoke(app, ["library", "share", "lib-1", "--enable"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is True

    def test_share_disable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": False})
        result = runner.invoke(app, ["library", "share", "lib-1", "--disable"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is False


# ---------------------------------------------------------------------------
# upload / import-url / import-youtube
# ---------------------------------------------------------------------------


class TestLibraryUpload:
    def test_upload_success(self, httpx_mock, mock_token, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 hi")
        httpx_mock.add_response(json={"item_id": "item-new"})
        result = runner.invoke(
            app,
            [
                "library",
                "upload",
                "lib-1",
                str(f),
                "--plugin",
                "simple_import",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert req.method == "POST"
        assert "/creator/libraries/lib-1/upload" in str(req.url)
        # multipart body should embed the plugin name
        assert b"simple_import" in req.content

    def test_upload_with_wait_polls_until_ready(self, httpx_mock, mock_token, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        # 1) upload
        httpx_mock.add_response(json={"item_id": "item-new"})
        # 2) first poll: processing
        httpx_mock.add_response(json={"status": "processing"})
        # 3) second poll: ready
        httpx_mock.add_response(
            json={"status": "ready", "page_count": 1}
        )
        with patch("lamb_cli.commands.library.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "library",
                    "upload",
                    "lib-1",
                    str(f),
                    "--wait",
                    "--max-wait",
                    "5",
                ],
            )
        assert result.exit_code == 0
        # we expect exactly 3 requests (upload + 2 polls)
        assert len(httpx_mock.get_requests()) == 3

    def test_upload_plugin_mismatch_passes_through(
        self, httpx_mock, mock_token, tmp_path
    ):
        """Plugin name `simple` (vs `simple_import`) — the CLI passes whatever
        name is given; the server returns 400. Verify CLI surfaces the error."""
        f = tmp_path / "x.txt"
        f.write_text("x")
        httpx_mock.add_response(
            status_code=400,
            json={"detail": "Unknown plugin 'simple' (did you mean 'simple_import'?)"},
        )
        result = runner.invoke(
            app,
            [
                "library",
                "upload",
                "lib-1",
                str(f),
                "--plugin",
                "simple",
            ],
        )
        assert result.exit_code != 0

    def test_upload_file_not_found(self, mock_token):
        result = runner.invoke(
            app, ["library", "upload", "lib-1", "/nonexistent/file.pdf"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestLibraryImportUrl:
    def test_import_url_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"item_id": "item-url-1"})
        result = runner.invoke(
            app,
            [
                "library",
                "import-url",
                "lib-1",
                "--url",
                "https://example.com/page",
            ],
        )
        assert result.exit_code == 0
        assert "item-url-1" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["url"] == "https://example.com/page"
        assert body["plugin_name"] == "url_import"
        assert "/creator/libraries/lib-1/import-url" in str(req.url)

    def test_import_url_invalid_url_returns_400(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=400, json={"detail": "Invalid URL"}
        )
        result = runner.invoke(
            app,
            ["library", "import-url", "lib-1", "--url", "not-a-url"],
        )
        assert result.exit_code != 0

    def test_import_url_with_wait(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"item_id": "item-url-2"})
        httpx_mock.add_response(json={"status": "ready", "page_count": 5})
        with patch("lamb_cli.commands.library.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "library",
                    "import-url",
                    "lib-1",
                    "--url",
                    "https://example.com",
                    "--wait",
                    "--max-wait",
                    "5",
                ],
            )
        assert result.exit_code == 0
        assert len(httpx_mock.get_requests()) == 2


class TestLibraryImportYoutube:
    def test_import_youtube_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"item_id": "item-yt-1"})
        result = runner.invoke(
            app,
            [
                "library",
                "import-youtube",
                "lib-1",
                "--url",
                "https://youtube.com/watch?v=abc",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["video_url"] == "https://youtube.com/watch?v=abc"
        assert body["plugin_name"] == "youtube_transcript_import"
        assert body["language"] == "en"

    def test_import_youtube_with_wait(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"item_id": "item-yt-2"})
        httpx_mock.add_response(json={"status": "ready", "page_count": 1})
        with patch("lamb_cli.commands.library.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "library",
                    "import-youtube",
                    "lib-1",
                    "--url",
                    "https://youtube.com/watch?v=xyz",
                    "--wait",
                    "--max-wait",
                    "5",
                ],
            )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# items / item / delete-item
# ---------------------------------------------------------------------------


class TestLibraryItems:
    def test_items_default_pagination(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ITEMS)
        result = runner.invoke(app, ["library", "items", "lib-1"])
        assert result.exit_code == 0
        # Rich tables wrap long text; check IDs which never wrap.
        assert "item-1" in result.output
        assert "item-2" in result.output
        req = httpx_mock.get_request()
        assert "limit=20" in str(req.url)
        assert "offset=0" in str(req.url)

    def test_items_with_status_filter(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ITEMS)
        result = runner.invoke(
            app,
            ["library", "items", "lib-1", "--status", "ready", "--limit", "5"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "status=ready" in str(req.url)
        assert "limit=5" in str(req.url)

    def test_items_with_offset(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"items": []})
        result = runner.invoke(
            app, ["library", "items", "lib-1", "--offset", "20"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "offset=20" in str(req.url)


class TestLibraryItem:
    def test_item_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ITEM_DETAIL)
        result = runner.invoke(app, ["library", "item", "lib-1", "item-1"])
        assert result.exit_code == 0
        assert "Chapter 1" in result.output

    def test_item_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ITEM_DETAIL)
        result = runner.invoke(
            app, ["library", "item", "lib-1", "item-1", "-o", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "item-1"

    def test_item_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["library", "item", "lib-1", "item-x"])
        assert result.exit_code != 0


class TestLibraryDeleteItem:
    def test_delete_item_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Item deleted."})
        result = runner.invoke(
            app, ["library", "delete-item", "lib-1", "item-1", "-y"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert req.method == "DELETE"
        assert "/creator/libraries/lib-1/items/item-1" in str(req.url)

    def test_delete_item_rejected(self, mock_token):
        result = runner.invoke(
            app, ["library", "delete-item", "lib-1", "item-1"], input="n\n"
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# plugins / import-config
# ---------------------------------------------------------------------------


class TestLibraryPlugins:
    def test_plugins_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_PLUGINS)
        result = runner.invoke(app, ["library", "plugins"])
        assert result.exit_code == 0
        assert "simple_import" in result.output
        assert "youtube_transcript_import" in result.output

    def test_plugins_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_PLUGINS)
        result = runner.invoke(app, ["library", "plugins", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # dispatcher unwraps either list or wrapped dict
        if isinstance(data, dict):
            data = data.get("plugins", data)
        assert any(p.get("name") == "simple_import" for p in data)


class TestLibraryImportConfig:
    def test_show_import_config(self, httpx_mock, mock_token):
        cfg = {"image_descriptions": "basic", "max_discovery_depth": 2}
        httpx_mock.add_response(json=cfg)
        result = runner.invoke(
            app, ["library", "import-config", "lib-1", "-o", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["image_descriptions"] == "basic"

    def test_set_import_config_image_descriptions(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"warning": ""})
        result = runner.invoke(
            app,
            [
                "library",
                "set-import-config",
                "lib-1",
                "--image-descriptions",
                "llm",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["image_descriptions"] == "llm"

    def test_set_import_config_crawl_depth(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={})
        result = runner.invoke(
            app,
            ["library", "set-import-config", "lib-1", "--crawl-depth", "3"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["max_discovery_depth"] == 3

    def test_set_import_config_no_options_errors(self, mock_token):
        result = runner.invoke(
            app, ["library", "set-import-config", "lib-1"]
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# export / import (ZIP)
# ---------------------------------------------------------------------------


class TestLibraryExport:
    def test_export_to_file(self, httpx_mock, mock_token, tmp_path):
        zip_bytes = b"PK\x03\x04 fake zip"
        httpx_mock.add_response(content=zip_bytes)
        out = tmp_path / "export.zip"
        result = runner.invoke(
            app,
            ["library", "export", "lib-1", "--output-file", str(out)],
        )
        assert result.exit_code == 0
        assert out.read_bytes() == zip_bytes

    def test_export_default_filename(self, httpx_mock, mock_token, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        httpx_mock.add_response(content=b"PK\x03\x04 zip")
        result = runner.invoke(app, ["library", "export", "lib-12345678"])
        assert result.exit_code == 0
        # default name uses the first 8 chars of the ID
        assert (tmp_path / "library-lib-1234.zip").exists()


class TestLibraryImport:
    def test_import_zip_round_trip(self, httpx_mock, mock_token, tmp_path):
        zip_path = tmp_path / "import.zip"
        zip_path.write_bytes(b"PK\x03\x04 dummy")
        httpx_mock.add_response(
            json={
                "library_id": "lib-imported",
                "library_name": "Imported",
                "item_count": 4,
            }
        )
        result = runner.invoke(app, ["library", "import", str(zip_path)])
        assert result.exit_code == 0
        assert "Imported" in result.output or "lib-imported" in result.output
        req = httpx_mock.get_request()
        assert req.method == "POST"
        assert "/creator/libraries/import" in str(req.url)

    def test_import_missing_file_errors(self, mock_token):
        result = runner.invoke(app, ["library", "import", "/nonexistent.zip"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Edge cases — guardrails surfaced through the CLI (#337)
# ---------------------------------------------------------------------------


class TestLibraryFR10:
    """A library item linked to any active Knowledge Store cannot be deleted
    (FR-10). The CLI must surface the blocking KS list, not a bare
    'API error (409)' that hides which KS is holding the item."""

    def test_delete_item_returns_409_lists_blocking_kses(
        self, httpx_mock, mock_token
    ):
        httpx_mock.add_response(
            status_code=409,
            json={
                "detail": "Item is linked to active Knowledge Stores",
                "blocking_knowledge_stores": [
                    {"id": "ks-1", "name": "Course KS"},
                    {"id": "ks-2", "name": "Lab KS"},
                ],
            },
        )
        result = runner.invoke(
            app, ["library", "delete-item", "lib-1", "item-1", "-y"]
        )
        from lamb_cli.errors import ApiError

        assert result.exit_code != 0
        assert isinstance(result.exception, ApiError)
        out = result.output
        # IDs surfaced
        assert "ks-1" in out and "ks-2" in out
        # At least one human-readable name surfaced
        assert "Course KS" in out or "Lab KS" in out
        # Hint at the recovery path
        assert "remove-content" in out

    def test_delete_library_returns_409_when_items_linked(
        self, httpx_mock, mock_token
    ):
        httpx_mock.add_response(
            status_code=409,
            json={
                "detail": "Library has items linked to active Knowledge Stores",
                "blocking_knowledge_stores": [
                    {"id": "ks-3", "name": "Big KS"},
                ],
            },
        )
        result = runner.invoke(app, ["library", "delete", "lib-1", "-y"])
        assert result.exit_code != 0
        assert "ks-3" in result.output
        assert "Big KS" in result.output

    def test_delete_item_without_blocking_list_still_errors(
        self, httpx_mock, mock_token
    ):
        """Tolerate older-format 409s that don't include the structured field
        — fall back to the generic error path without crashing."""
        httpx_mock.add_response(
            status_code=409, json={"detail": "Conflict"}
        )
        result = runner.invoke(
            app, ["library", "delete-item", "lib-1", "item-1", "-y"]
        )
        assert result.exit_code != 0


class TestLibraryBackendErrors:
    """Backend status codes must propagate as non-zero exits, never as
    Python tracebacks."""

    def test_upload_returns_413_payload_too_large(
        self, httpx_mock, mock_token, tmp_path
    ):
        httpx_mock.add_response(
            status_code=413, json={"detail": "File exceeds 50MB limit"}
        )
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * 100)
        result = runner.invoke(
            app, ["library", "upload", "lib-1", str(f), "--plugin", "simple_import"]
        )
        assert result.exit_code != 0

    def test_upload_returns_415_unsupported_filetype(
        self, httpx_mock, mock_token, tmp_path
    ):
        httpx_mock.add_response(
            status_code=415,
            json={"detail": "Plugin simple_import does not support .exe"},
        )
        f = tmp_path / "evil.exe"
        f.write_bytes(b"\x4d\x5a")  # PE header
        result = runner.invoke(
            app, ["library", "upload", "lib-1", str(f), "--plugin", "simple_import"]
        )
        assert result.exit_code != 0

    def test_import_url_returns_502_for_unreachable_target(
        self, httpx_mock, mock_token
    ):
        httpx_mock.add_response(
            status_code=502, json={"detail": "Bad gateway: target unreachable"}
        )
        result = runner.invoke(
            app,
            [
                "library",
                "import-url",
                "lib-1",
                "--url",
                "https://does-not-exist.invalid",
            ],
        )
        assert result.exit_code != 0

    def test_import_youtube_returns_404_no_captions(
        self, httpx_mock, mock_token
    ):
        httpx_mock.add_response(
            status_code=404,
            json={"detail": "No captions available for this video"},
        )
        result = runner.invoke(
            app,
            [
                "library",
                "import-youtube",
                "lib-1",
                "--url",
                "https://youtu.be/no-captions",
            ],
        )
        from lamb_cli.errors import NotFoundError

        assert result.exit_code != 0
        assert isinstance(result.exception, NotFoundError)

    def test_items_handles_missing_optional_fields(
        self, httpx_mock, mock_token
    ):
        """An item with no page_count/image_count must not break table render."""
        httpx_mock.add_response(
            json={
                "items": [
                    {
                        "id": "item-x",
                        "title": "Sparse",
                        "source_type": "url",
                        "import_plugin": "url_import",
                        "status": "ready",
                        # page_count, image_count, created_at all missing
                    }
                ]
            }
        )
        result = runner.invoke(app, ["library", "items", "lib-1"])
        assert result.exit_code == 0
        assert "Sparse" in result.output


class TestLibraryPolling:
    """Symmetric to TestKsPollingBackoff — same hardcoded schedule lives in
    library.py at lines ~42 and ~61. This locks it down."""

    def test_upload_wait_uses_documented_backoff(
        self, httpx_mock, mock_token, tmp_path
    ):
        f = tmp_path / "doc.md"
        f.write_text("# Hello")
        # 1 upload + 5 in_progress + 1 ready
        httpx_mock.add_response(json={"item_id": "item-1"})
        for _ in range(5):
            httpx_mock.add_response(json={"status": "processing"})
        httpx_mock.add_response(json={"status": "ready", "page_count": 1})

        sleeps: list[float] = []
        with patch(
            "lamb_cli.commands.library.time.sleep",
            side_effect=lambda d: sleeps.append(d),
        ):
            result = runner.invoke(
                app,
                [
                    "library",
                    "upload",
                    "lib-1",
                    str(f),
                    "--plugin",
                    "simple_import",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_upload_wait_caps_at_16_seconds(
        self, httpx_mock, mock_token, tmp_path
    ):
        f = tmp_path / "doc.md"
        f.write_text("# Hello")
        httpx_mock.add_response(json={"item_id": "item-1"})
        for _ in range(8):
            httpx_mock.add_response(json={"status": "processing"})
        httpx_mock.add_response(json={"status": "ready", "page_count": 1})

        sleeps: list[float] = []
        with patch(
            "lamb_cli.commands.library.time.sleep",
            side_effect=lambda d: sleeps.append(d),
        ):
            result = runner.invoke(
                app,
                [
                    "library",
                    "upload",
                    "lib-1",
                    str(f),
                    "--plugin",
                    "simple_import",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        # Last 3 sleeps must all be capped at 16.0
        assert sleeps[-3:] == [16.0, 16.0, 16.0]
        # Earlier ones must follow the doubling cadence.
        assert sleeps[:5] == [1.0, 2.0, 4.0, 8.0, 16.0]


class TestLibraryResilience:
    def test_upload_path_does_not_exist_no_http_call(
        self, httpx_mock, mock_token
    ):
        """Filesystem check must run BEFORE any network call."""
        result = runner.invoke(
            app,
            [
                "library",
                "upload",
                "lib-1",
                "/definitely/not/a/real/path.pdf",
                "--plugin",
                "simple_import",
            ],
        )
        assert result.exit_code != 0
        # No HTTP call must have happened — pre-flight check rejected it.
        assert len(httpx_mock.get_requests()) == 0

    def test_command_with_expired_token_errors_clearly(
        self, httpx_mock, mock_token
    ):
        """401 from backend must come back as AuthenticationError so the
        global handler points users at 'lamb login'."""
        httpx_mock.add_response(
            status_code=401, json={"detail": "Token expired"}
        )
        result = runner.invoke(app, ["library", "list"])
        from lamb_cli.errors import AuthenticationError

        assert result.exit_code != 0
        assert isinstance(result.exception, AuthenticationError)

    def test_network_error_does_not_leak_traceback(self, mock_token):
        """A connection failure surfaces as NetworkError (typed), not as a
        raw httpx.ConnectError traceback."""
        import httpx as _httpx

        from lamb_cli.errors import NetworkError

        with patch.object(
            _httpx.Client,
            "request",
            side_effect=_httpx.ConnectError("refused"),
        ):
            result = runner.invoke(app, ["library", "list"])
        assert result.exit_code != 0
        assert isinstance(result.exception, NetworkError)

    def test_create_with_unicode_description_round_trips(
        self, httpx_mock, mock_token
    ):
        """Library names/descriptions with non-ASCII must survive the request
        body — guards against future ascii-escape regressions."""
        httpx_mock.add_response(
            json={
                "id": "lib-uni",
                "name": "Curso de Cálculo — Δ",
                "description": "Material original",
            }
        )
        result = runner.invoke(
            app,
            [
                "library",
                "create",
                "Curso de Cálculo — Δ",
                "--description",
                "Material original",
            ],
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content.decode("utf-8"))
        assert body["name"] == "Curso de Cálculo — Δ"
        assert body["description"] == "Material original"

    def test_items_pagination_offset_passes_through(
        self, httpx_mock, mock_token
    ):
        """--offset and --limit must reach the backend as query params."""
        httpx_mock.add_response(json={"items": []})
        result = runner.invoke(
            app,
            ["library", "items", "lib-1", "--limit", "50", "--offset", "100"],
        )
        assert result.exit_code == 0
        url = str(httpx_mock.get_request().url)
        assert "limit=50" in url
        assert "offset=100" in url


class TestItemContent:
    """Tests for ``lamb library item-content`` (#370)."""

    def test_prints_markdown_to_stdout(self, httpx_mock, mock_token, mock_server_url):
        body = b"# Title\n\nbody line 1\nbody line 2\n"
        httpx_mock.add_response(
            url="http://test-server:9099/creator/libraries/L1/items/I1/content?format=markdown",
            content=body,
            headers={"content-type": "text/markdown"},
        )

        result = runner.invoke(app, ["library", "item-content", "L1", "I1"])

        assert result.exit_code == 0
        assert "# Title" in result.output
        assert "body line 1" in result.output
        assert "body line 2" in result.output

    def test_text_format(self, httpx_mock, mock_token, mock_server_url):
        body = b"plain text body"
        httpx_mock.add_response(
            url="http://test-server:9099/creator/libraries/L1/items/I1/content?format=text",
            content=body,
            headers={"content-type": "text/plain"},
        )

        result = runner.invoke(
            app, ["library", "item-content", "L1", "I1", "--format", "text"]
        )

        assert result.exit_code == 0
        assert "plain text body" in result.output

    def test_invalid_format_exits_with_2(self, mock_token, mock_server_url):
        result = runner.invoke(
            app, ["library", "item-content", "L1", "I1", "--format", "html"]
        )

        assert result.exit_code == 2
        assert "Invalid format" in result.output

    def test_413_shows_friendly_error(self, httpx_mock, mock_token, mock_server_url):
        httpx_mock.add_response(
            url="http://test-server:9099/creator/libraries/L1/items/I1/content?format=markdown",
            status_code=413,
            json={"detail": "Content exceeds 5 MB."},
        )

        result = runner.invoke(app, ["library", "item-content", "L1", "I1"])

        assert result.exit_code == 2
        assert "too large" in result.output.lower()
