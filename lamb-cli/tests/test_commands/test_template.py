"""Tests for prompt template commands."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_TEMPLATES = {
    "templates": [
        {
            "id": 1,
            "name": "Socratic Tutor",
            "description": "Ask guiding questions",
            "is_shared": False,
            "is_owner": True,
            "system_prompt": "Guide via questions.",
            "prompt_template": "{{question}}",
            "owner_name": "Alice",
            "created_at": 1700000000,
            "updated_at": 1700000000,
        },
        {
            "id": 2,
            "name": "Essay Feedback",
            "description": "Structured writing feedback",
            "is_shared": True,
            "is_owner": True,
            "system_prompt": "Provide feedback.",
            "prompt_template": "{{essay}}",
            "owner_name": "Alice",
            "created_at": 1700001000,
            "updated_at": 1700001000,
        },
    ],
    "total": 2,
    "page": 1,
    "limit": 50,
}

SAMPLE_TEMPLATE = {
    "id": 1,
    "name": "Socratic Tutor",
    "description": "Ask guiding questions",
    "is_shared": False,
    "is_owner": True,
    "system_prompt": "Guide via questions.",
    "prompt_template": "{{question}}",
    "owner_name": "Alice",
    "created_at": 1700000000,
    "updated_at": 1700000000,
}

SAMPLE_EXPORT = {
    "export_version": "1.0",
    "exported_at": "2024-01-01T00:00:00Z",
    "templates": [
        {
            "name": "Socratic Tutor",
            "description": "Ask guiding questions",
            "system_prompt": "Guide via questions.",
            "prompt_template": "{{question}}",
            "metadata": {},
        }
    ],
}


class TestTemplateList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list"])
        assert result.exit_code == 0
        assert "Socratic Tutor" in result.output
        assert "Essay Feedback" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "Socratic Tutor"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "1" in lines[0]

    def test_list_with_pagination(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list", "--limit", "10", "--offset", "5"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "limit=10" in str(req.url)
        assert "offset=5" in str(req.url)


class TestTemplateListShared:
    def test_list_shared_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list-shared"])
        assert result.exit_code == 0
        assert "Socratic Tutor" in result.output

    def test_list_shared_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATES)
        result = runner.invoke(app, ["template", "list-shared", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2


class TestTemplateGet:
    def test_get_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(app, ["template", "get", "1"])
        assert result.exit_code == 0
        assert "Socratic Tutor" in result.output
        assert "Guide via questions." in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(app, ["template", "get", "1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == 1
        assert data["name"] == "Socratic Tutor"

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["template", "get", "999"])
        assert result.exit_code != 0


class TestTemplateCreate:
    def test_create_basic(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(app, ["template", "create", "Socratic Tutor"])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "1" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Socratic Tutor"
        assert body["is_shared"] is False

    def test_create_with_description(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(
            app, ["template", "create", "Test", "--description", "A test template"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["description"] == "A test template"

    def test_create_with_shared(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "is_shared": True})
        result = runner.invoke(app, ["template", "create", "Shared Bot", "--shared"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is True

    def test_create_with_prompts(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(
            app,
            [
                "template", "create", "Full",
                "--system-prompt", "Be helpful.",
                "--prompt-template", "{{input}}",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["system_prompt"] == "Be helpful."
        assert body["prompt_template"] == "{{input}}"


class TestTemplateUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "name": "Renamed"})
        result = runner.invoke(app, ["template", "update", "1", "--name", "Renamed"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Renamed"

    def test_update_description(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TEMPLATE)
        result = runner.invoke(app, ["template", "update", "1", "--description", "New desc"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["description"] == "New desc"

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["template", "update", "1"])
        assert result.exit_code == 1


class TestTemplateDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=204)
        result = runner.invoke(app, ["template", "delete", "1", "--confirm"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=204)
        result = runner.invoke(app, ["template", "delete", "1"], input="y\n")
        assert result.exit_code == 0

    def test_delete_interactive_no(self, mock_token):
        result = runner.invoke(app, ["template", "delete", "1"], input="n\n")
        assert result.exit_code != 0


class TestTemplateDuplicate:
    def test_duplicate_default_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "id": 3, "name": "Socratic Tutor (Copy)"})
        result = runner.invoke(app, ["template", "duplicate", "1"])
        assert result.exit_code == 0
        assert "duplicated" in result.output.lower() or "3" in result.output

    def test_duplicate_custom_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "id": 4, "name": "My Copy"})
        result = runner.invoke(app, ["template", "duplicate", "1", "--new-name", "My Copy"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["new_name"] == "My Copy"


class TestTemplateShare:
    def test_share_enable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "is_shared": True})
        result = runner.invoke(app, ["template", "share", "1", "--enable"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is True

    def test_share_disable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={**SAMPLE_TEMPLATE, "is_shared": False})
        result = runner.invoke(app, ["template", "share", "1", "--disable"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["is_shared"] is False

    def test_share_no_flag_fails(self, mock_token):
        result = runner.invoke(app, ["template", "share", "1"])
        assert result.exit_code == 1


class TestTemplateExport:
    def test_export_stdout(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_EXPORT)
        result = runner.invoke(app, ["template", "export", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["export_version"] == "1.0"
        assert len(data["templates"]) == 1

    def test_export_to_file(self, httpx_mock, mock_token, tmp_path):
        httpx_mock.add_response(json=SAMPLE_EXPORT)
        outfile = tmp_path / "export.json"
        result = runner.invoke(app, ["template", "export", "1", "-f", str(outfile)])
        assert result.exit_code == 0
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["export_version"] == "1.0"

    def test_export_multiple_ids(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_EXPORT)
        result = runner.invoke(app, ["template", "export", "1", "2"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["template_ids"] == [1, 2]
