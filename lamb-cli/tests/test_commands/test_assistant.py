"""Tests for assistant commands."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SERVER = "http://localhost:9099"

SAMPLE_ASSISTANTS = {
    "assistants": [
        {
            "assistant_id": "ast-1",
            "name": "Math Tutor",
            "description": "Helps with algebra",
            "publish_status": True,
            "owner": "user1",
        },
        {
            "assistant_id": "ast-2",
            "name": "History Helper",
            "description": "WWII study guide",
            "publish_status": False,
            "owner": "user2",
        },
    ],
    "total_count": 2,
}

SAMPLE_ASSISTANT = {
    "assistant_id": "ast-1",
    "name": "Math Tutor",
    "description": "Helps with algebra",
    "system_prompt": "You are a math tutor.",
    "publish_status": True,
    "owner": "user1",
    "rag_top_k": 3,
    "rag_collection_names": [],
}


class TestAssistantList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANTS)
        result = runner.invoke(app, ["assistant", "list"])
        assert result.exit_code == 0
        assert "Math Tutor" in result.output
        assert "History Helper" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANTS)
        result = runner.invoke(app, ["assistant", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "Math Tutor"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANTS)
        result = runner.invoke(app, ["assistant", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "ast-1" in lines[0]

    def test_list_with_limit_offset(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"assistants": [], "total_count": 0})
        result = runner.invoke(app, ["assistant", "list", "--limit", "5", "--offset", "10"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "limit=5" in str(req.url)
        assert "offset=10" in str(req.url)


class TestAssistantGet:
    def test_get_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANT)
        result = runner.invoke(app, ["assistant", "get", "ast-1"])
        assert result.exit_code == 0
        assert "Math Tutor" in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANT)
        result = runner.invoke(app, ["assistant", "get", "ast-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["assistant_id"] == "ast-1"

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["assistant", "get", "ast-999"])
        assert result.exit_code != 0


class TestAssistantCreate:
    def test_create_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={
                "assistant_id": "ast-new",
                "name": "New Bot",
                "description": "desc",
                "owner": "me",
                "publish_status": False,
            }
        )
        result = runner.invoke(
            app, ["assistant", "create", "New Bot", "--description", "desc"]
        )
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "ast-new" in result.output

    def test_create_with_system_prompt_file(self, httpx_mock, mock_token, tmp_path):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("You are a helpful assistant.", encoding="utf-8")
        httpx_mock.add_response(
            json={"assistant_id": "ast-new", "name": "Bot", "description": "", "owner": "me", "publish_status": False}
        )
        result = runner.invoke(
            app,
            ["assistant", "create", "Bot", "--system-prompt-file", str(prompt_file)],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["system_prompt"] == "You are a helpful assistant."

    def test_create_with_rag_options(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"assistant_id": "ast-rag", "name": "RAG Bot", "description": "", "owner": "me", "publish_status": False}
        )
        result = runner.invoke(
            app,
            ["assistant", "create", "RAG Bot", "--rag-top-k", "5", "--rag-collections", "col1, col2"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["rag_top_k"] == 5
        assert body["rag_collection_names"] == ["col1", "col2"]


class TestAssistantUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"assistant_id": "ast-1", "message": "Updated"})
        result = runner.invoke(app, ["assistant", "update", "ast-1", "--name", "New Name"])
        assert result.exit_code == 0
        assert "Updated" in result.output or "updated" in result.output.lower()

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["assistant", "update", "ast-1"])
        assert result.exit_code == 1


class TestAssistantDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["assistant", "delete", "ast-1", "--confirm"])
        assert result.exit_code == 0
        assert "Deleted" in result.output or "deleted" in result.output.lower()

    def test_delete_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["assistant", "delete", "ast-1"], input="y\n")
        assert result.exit_code == 0

    def test_delete_interactive_no(self, mock_token):
        result = runner.invoke(app, ["assistant", "delete", "ast-1"], input="n\n")
        assert result.exit_code != 0


class TestAssistantPublish:
    def test_publish(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_ASSISTANT, "publish_status": True})
        result = runner.invoke(app, ["assistant", "publish", "ast-1"])
        assert result.exit_code == 0
        assert "published" in result.output.lower()

    def test_unpublish(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_ASSISTANT, "publish_status": False})
        result = runner.invoke(app, ["assistant", "unpublish", "ast-1"])
        assert result.exit_code == 0
        assert "unpublished" in result.output.lower()


class TestAssistantExport:
    def test_export_stdout(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ASSISTANT)
        result = runner.invoke(app, ["assistant", "export", "ast-1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["assistant_id"] == "ast-1"

    def test_export_to_file(self, httpx_mock, mock_token, tmp_path):
        httpx_mock.add_response(json=SAMPLE_ASSISTANT)
        out_file = tmp_path / "export.json"
        result = runner.invoke(app, ["assistant", "export", "ast-1", "--output-file", str(out_file)])
        assert result.exit_code == 0
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["assistant_id"] == "ast-1"
