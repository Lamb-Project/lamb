"""Tests for knowledge base commands."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_KBS = {
    "knowledge_bases": [
        {
            "id": "kb-1",
            "name": "Course Materials",
            "description": "Intro to CS readings",
            "is_owner": True,
            "is_shared": False,
        },
        {
            "id": "kb-2",
            "name": "Lab Notes",
            "description": "Weekly lab summaries",
            "is_owner": True,
            "is_shared": True,
        },
    ]
}

SAMPLE_KB_DETAIL = {
    "id": "kb-1",
    "name": "Course Materials",
    "description": "Intro to CS readings",
    "is_owner": True,
    "is_shared": False,
    "can_modify": True,
    "owner": "user1",
    "files": [
        {"id": "f-1", "filename": "chapter1.pdf", "size": 1024, "content_type": "application/pdf"},
        {"id": "f-2", "filename": "notes.txt", "size": 256, "content_type": "text/plain"},
    ],
}

SAMPLE_PLUGINS = [
    {"name": "file_upload", "description": "Upload files", "kind": "ingestion"},
    {"name": "web_scraper", "description": "Scrape web pages", "kind": "ingestion"},
]

SAMPLE_QUERY_PLUGINS = [
    {"name": "default", "description": "Default vector search", "kind": "query"},
]

SAMPLE_QUERY_RESULTS = {
    "results": [
        {"similarity": 0.95, "data": "Chapter 1 covers basic algorithms and data structures."},
        {"similarity": 0.82, "data": "Introduction to Big-O notation."},
    ]
}


class TestKbList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KBS)
        result = runner.invoke(app, ["kb", "list"])
        assert result.exit_code == 0
        assert "Course Materials" in result.output
        assert "Lab Notes" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KBS)
        result = runner.invoke(app, ["kb", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "Course Materials"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KBS)
        result = runner.invoke(app, ["kb", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "kb-1" in lines[0]


class TestKbListShared:
    def test_list_shared_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KBS)
        result = runner.invoke(app, ["kb", "list-shared"])
        assert result.exit_code == 0
        assert "Course Materials" in result.output

    def test_list_shared_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KBS)
        result = runner.invoke(app, ["kb", "list-shared", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2


class TestKbGet:
    def test_get_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KB_DETAIL)
        result = runner.invoke(app, ["kb", "get", "kb-1"])
        assert result.exit_code == 0
        assert "Course Materials" in result.output
        # File count should show instead of full list
        assert "2" in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KB_DETAIL)
        result = runner.invoke(app, ["kb", "get", "kb-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "kb-1"
        assert len(data["files"]) == 2

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["kb", "get", "kb-999"])
        assert result.exit_code != 0


class TestKbCreate:
    def test_create_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "kb-new", "name": "New KB", "description": "test", "is_owner": True, "is_shared": False}
        )
        result = runner.invoke(app, ["kb", "create", "New KB", "--description", "test"])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "kb-new" in result.output

    def test_create_with_access_control(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "kb-ac", "name": "AC KB", "description": "", "is_owner": True, "is_shared": False}
        )
        result = runner.invoke(
            app, ["kb", "create", "AC KB", "--access-control", '{"groups": ["staff"]}']
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["access_control"] == '{"groups": ["staff"]}'


class TestKbUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Updated"})
        result = runner.invoke(app, ["kb", "update", "kb-1", "--name", "Renamed KB"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Renamed KB"

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["kb", "update", "kb-1"])
        assert result.exit_code == 1

    def test_update_description(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Updated"})
        result = runner.invoke(app, ["kb", "update", "kb-1", "--description", "New desc"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["description"] == "New desc"


class TestKbDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["kb", "delete", "kb-1", "--confirm"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower() or "Deleted" in result.output

    def test_delete_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["kb", "delete", "kb-1"], input="y\n")
        assert result.exit_code == 0

    def test_delete_interactive_no(self, mock_token):
        result = runner.invoke(app, ["kb", "delete", "kb-1"], input="n\n")
        assert result.exit_code != 0


class TestKbShare:
    def test_share_enable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": True})
        result = runner.invoke(app, ["kb", "share", "kb-1", "--enable"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is True

    def test_share_disable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": False})
        result = runner.invoke(app, ["kb", "share", "kb-1", "--disable"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is False

    def test_share_no_flag_fails(self, mock_token):
        result = runner.invoke(app, ["kb", "share", "kb-1"])
        assert result.exit_code == 1


class TestKbUpload:
    def test_upload_single_file(self, httpx_mock, mock_token, tmp_path):
        f1 = tmp_path / "doc.pdf"
        f1.write_bytes(b"%PDF-1.4 test content")
        httpx_mock.add_response(json={"uploaded": 1})
        result = runner.invoke(app, ["kb", "upload", "kb-1", str(f1)])
        assert result.exit_code == 0
        assert "1 file" in result.output

    def test_upload_multiple_files(self, httpx_mock, mock_token, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        httpx_mock.add_response(json={"uploaded": 2})
        result = runner.invoke(app, ["kb", "upload", "kb-1", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "2 files" in result.output

    def test_upload_file_not_found(self, mock_token):
        result = runner.invoke(app, ["kb", "upload", "kb-1", "/nonexistent/file.pdf"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestKbIngest:
    def test_ingest_url(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-1"})
        result = runner.invoke(
            app, ["kb", "ingest", "kb-1", "--plugin", "web_scraper", "--url", "https://example.com"]
        )
        assert result.exit_code == 0
        assert "job-1" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["plugin_name"] == "web_scraper"
        assert body["plugin_params"]["url"] == "https://example.com"

    def test_ingest_youtube(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-2"})
        result = runner.invoke(
            app,
            ["kb", "ingest", "kb-1", "--plugin", "youtube", "--youtube", "https://youtube.com/watch?v=abc"],
        )
        assert result.exit_code == 0
        assert "job-2" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["plugin_params"]["youtube_url"] == "https://youtube.com/watch?v=abc"

    def test_ingest_with_params(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-3"})
        result = runner.invoke(
            app,
            ["kb", "ingest", "kb-1", "--plugin", "custom", "--param", "key1=val1", "--param", "key2=val2"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["plugin_params"]["key1"] == "val1"
        assert body["plugin_params"]["key2"] == "val2"

    def test_ingest_invalid_param_format(self, mock_token):
        result = runner.invoke(
            app, ["kb", "ingest", "kb-1", "--plugin", "test", "--param", "badformat"]
        )
        assert result.exit_code == 1


class TestKbQuery:
    def test_query_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY_RESULTS)
        result = runner.invoke(app, ["kb", "query", "kb-1", "What is Big-O?"])
        assert result.exit_code == 0
        assert "0.95" in result.output

    def test_query_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY_RESULTS)
        result = runner.invoke(app, ["kb", "query", "kb-1", "What is Big-O?", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    def test_query_with_plugin_params(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY_RESULTS)
        result = runner.invoke(
            app,
            ["kb", "query", "kb-1", "search text", "--plugin", "custom_search", "--top-k", "5", "--threshold", "0.7"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["plugin_name"] == "custom_search"
        assert body["plugin_params"]["top_k"] == 5
        assert body["plugin_params"]["threshold"] == 0.7


class TestKbDeleteFile:
    def test_delete_file_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "File deleted"})
        result = runner.invoke(app, ["kb", "delete-file", "kb-1", "f-1", "--confirm"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_file_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "File deleted"})
        result = runner.invoke(app, ["kb", "delete-file", "kb-1", "f-1"], input="y\n")
        assert result.exit_code == 0

    def test_delete_file_interactive_no(self, mock_token):
        result = runner.invoke(app, ["kb", "delete-file", "kb-1", "f-1"], input="n\n")
        assert result.exit_code != 0


class TestKbPlugins:
    def test_plugins_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_PLUGINS)
        result = runner.invoke(app, ["kb", "plugins"])
        assert result.exit_code == 0
        assert "file_upload" in result.output
        assert "web_scraper" in result.output

    def test_plugins_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_PLUGINS)
        result = runner.invoke(app, ["kb", "plugins", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    def test_plugins_with_wrapper(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"plugins": SAMPLE_PLUGINS})
        result = runner.invoke(app, ["kb", "plugins"])
        assert result.exit_code == 0
        assert "file_upload" in result.output


class TestKbQueryPlugins:
    def test_query_plugins_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY_PLUGINS)
        result = runner.invoke(app, ["kb", "query-plugins"])
        assert result.exit_code == 0
        assert "default" in result.output

    def test_query_plugins_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY_PLUGINS)
        result = runner.invoke(app, ["kb", "query-plugins", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
