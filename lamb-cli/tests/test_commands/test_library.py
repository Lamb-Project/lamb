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
