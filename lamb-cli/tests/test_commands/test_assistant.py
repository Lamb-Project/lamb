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

SAMPLE_METADATA = json.dumps({
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "prompt_processor": "simple_augment",
    "rag_processor": "no_rag",
    "capabilities": {"vision": False, "image_generation": False},
})

SAMPLE_ASSISTANT_WITH_METADATA = {
    **SAMPLE_ASSISTANT,
    "metadata": SAMPLE_METADATA,
}

SAMPLE_CAPABILITIES = {
    "connectors": {
        "openai": {"available_llms": ["gpt-4o", "gpt-4o-mini"]},
        "ollama": {"available_llms": ["llama3", "mistral"]},
    },
    "prompt_processors": ["simple_augment", "context_augment"],
    "rag_processors": ["no_rag", "simple_rag", "context_aware_rag"],
}

SAMPLE_DEFAULTS = {
    "config": {
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "prompt_processor": "simple_augment",
        "rag_processor": "no_rag",
    }
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

    def test_get_parses_metadata(self, httpx_mock, mock_token):
        """Metadata JSON string is parsed into display fields."""
        httpx_mock.add_response(json=SAMPLE_ASSISTANT_WITH_METADATA)
        result = runner.invoke(app, ["assistant", "get", "ast-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["connector"] == "openai"
        assert data["llm"] == "gpt-4o-mini"
        assert data["prompt_processor"] == "simple_augment"
        assert data["rag_processor"] == "no_rag"

    def test_get_metadata_as_dict(self, httpx_mock, mock_token):
        """Handle metadata that arrives as a dict instead of JSON string."""
        resp = {
            **SAMPLE_ASSISTANT,
            "metadata": {
                "connector": "ollama",
                "llm": "llama3",
                "prompt_processor": "context_augment",
                "rag_processor": "simple_rag",
            },
        }
        httpx_mock.add_response(json=resp)
        result = runner.invoke(app, ["assistant", "get", "ast-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["connector"] == "ollama"
        assert data["llm"] == "llama3"


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
            ["assistant", "create", "RAG Bot", "--rag-top-k", "5", "--rag-collections", "col1,col2"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["RAG_Top_k"] == 5
        assert body["RAG_collections"] == "col1,col2"

    def test_create_with_metadata_flags(self, httpx_mock, mock_token):
        """Create with explicit --connector, --llm flags sets metadata."""
        httpx_mock.add_response(
            json={"assistant_id": "ast-cfg", "name": "Config Bot", "description": "", "owner": "me", "publish_status": False}
        )
        result = runner.invoke(
            app,
            [
                "assistant", "create", "Config Bot",
                "--connector", "openai",
                "--llm", "gpt-4o",
                "--prompt-processor", "context_augment",
                "--rag-processor", "simple_rag",
                "--vision",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        metadata = json.loads(body["metadata"])
        assert metadata["connector"] == "openai"
        assert metadata["llm"] == "gpt-4o"
        assert metadata["prompt_processor"] == "context_augment"
        assert metadata["rag_processor"] == "simple_rag"
        assert metadata["capabilities"]["vision"] is True
        assert metadata["capabilities"]["image_generation"] is False

    def test_create_flags_fetch_defaults(self, httpx_mock, mock_token):
        """When only --connector is provided, missing fields come from server defaults."""
        # First response: defaults endpoint
        httpx_mock.add_response(json=SAMPLE_DEFAULTS)
        # Second response: create endpoint
        httpx_mock.add_response(
            json={"assistant_id": "ast-def", "name": "Default Bot", "description": "", "owner": "me", "publish_status": False}
        )
        result = runner.invoke(
            app,
            ["assistant", "create", "Default Bot", "--connector", "openai"],
        )
        assert result.exit_code == 0
        # The second request is the create call
        requests = httpx_mock.get_requests()
        create_req = requests[-1]
        body = json.loads(create_req.content)
        metadata = json.loads(body["metadata"])
        assert metadata["connector"] == "openai"
        assert metadata["llm"] == "gpt-4o-mini"  # from defaults
        assert metadata["prompt_processor"] == "simple_augment"  # from defaults
        assert metadata["rag_processor"] == "no_rag"  # from defaults

    def test_create_no_metadata_when_no_flags(self, httpx_mock, mock_token):
        """Without flags and non-TTY stdin, no metadata is sent."""
        httpx_mock.add_response(
            json={"assistant_id": "ast-plain", "name": "Plain Bot", "description": "", "owner": "me", "publish_status": False}
        )
        result = runner.invoke(
            app, ["assistant", "create", "Plain Bot", "--description", "test"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert "metadata" not in body


class TestAssistantUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"assistant_id": "ast-1", "message": "Updated"})
        result = runner.invoke(app, ["assistant", "update", "ast-1", "--name", "New Name"])
        assert result.exit_code == 0
        assert "Updated" in result.output or "updated" in result.output.lower()

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["assistant", "update", "ast-1"])
        assert result.exit_code == 1

    def test_update_metadata_merge(self, httpx_mock, mock_token):
        """Update --llm merges with existing metadata fetched from server."""
        # First response: get current assistant (for metadata merge)
        httpx_mock.add_response(json=SAMPLE_ASSISTANT_WITH_METADATA)
        # Second response: the PUT update
        httpx_mock.add_response(json={"assistant_id": "ast-1", "message": "Updated"})
        result = runner.invoke(
            app, ["assistant", "update", "ast-1", "--llm", "gpt-4o"]
        )
        assert result.exit_code == 0
        requests = httpx_mock.get_requests()
        update_req = requests[-1]
        body = json.loads(update_req.content)
        metadata = json.loads(body["metadata"])
        assert metadata["llm"] == "gpt-4o"  # changed
        assert metadata["connector"] == "openai"  # preserved from current

    def test_update_vision_flag(self, httpx_mock, mock_token):
        """Update --vision merges capability into existing metadata."""
        httpx_mock.add_response(json=SAMPLE_ASSISTANT_WITH_METADATA)
        httpx_mock.add_response(json={"assistant_id": "ast-1", "message": "Updated"})
        result = runner.invoke(
            app, ["assistant", "update", "ast-1", "--vision"]
        )
        assert result.exit_code == 0
        requests = httpx_mock.get_requests()
        update_req = requests[-1]
        body = json.loads(update_req.content)
        metadata = json.loads(body["metadata"])
        assert metadata["capabilities"]["vision"] is True
        assert metadata["capabilities"]["image_generation"] is False  # preserved

    def test_update_name_no_metadata_fetch(self, httpx_mock, mock_token):
        """Update --name alone does NOT fetch current metadata."""
        httpx_mock.add_response(json={"assistant_id": "ast-1", "message": "Updated"})
        result = runner.invoke(
            app, ["assistant", "update", "ast-1", "--name", "Renamed"]
        )
        assert result.exit_code == 0
        # Only one request (the PUT), not a GET + PUT
        assert len(httpx_mock.get_requests()) == 1
        body = json.loads(httpx_mock.get_request().content)
        assert body["name"] == "Renamed"
        assert "metadata" not in body


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


class TestAssistantConfig:
    def test_config_json(self, httpx_mock, mock_token):
        """Config command returns capabilities and defaults as JSON."""
        httpx_mock.add_response(json=SAMPLE_CAPABILITIES)
        httpx_mock.add_response(json=SAMPLE_DEFAULTS)
        result = runner.invoke(app, ["assistant", "config", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "capabilities" in data
        assert "defaults" in data
        assert "openai" in data["capabilities"]["connectors"]
        assert data["defaults"]["connector"] == "openai"

    def test_config_table(self, httpx_mock, mock_token):
        """Config command in default table mode prints to stderr."""
        httpx_mock.add_response(json=SAMPLE_CAPABILITIES)
        httpx_mock.add_response(json=SAMPLE_DEFAULTS)
        result = runner.invoke(app, ["assistant", "config"])
        assert result.exit_code == 0


class TestBuildMetadata:
    def test_build_metadata_structure(self):
        from lamb_cli.commands.assistant import _build_metadata

        result = _build_metadata(
            connector="openai",
            llm="gpt-4o",
            prompt_processor="simple_augment",
            rag_processor="no_rag",
            vision=True,
            image_generation=False,
        )
        md = json.loads(result)
        assert md["connector"] == "openai"
        assert md["llm"] == "gpt-4o"
        assert md["prompt_processor"] == "simple_augment"
        assert md["rag_processor"] == "no_rag"
        assert md["capabilities"]["vision"] is True
        assert md["capabilities"]["image_generation"] is False


class TestParseMetadata:
    def test_parse_from_json_string(self):
        from lamb_cli.commands.assistant import _parse_metadata

        data = {"name": "test", "metadata": SAMPLE_METADATA}
        result = _parse_metadata(data)
        assert result["connector"] == "openai"
        assert result["llm"] == "gpt-4o-mini"

    def test_parse_from_dict(self):
        from lamb_cli.commands.assistant import _parse_metadata

        data = {
            "name": "test",
            "metadata": {
                "connector": "ollama",
                "llm": "llama3",
                "prompt_processor": "context_augment",
                "rag_processor": "simple_rag",
            },
        }
        result = _parse_metadata(data)
        assert result["connector"] == "ollama"
        assert result["llm"] == "llama3"

    def test_parse_no_metadata(self):
        from lamb_cli.commands.assistant import _parse_metadata

        data = {"name": "test"}
        result = _parse_metadata(data)
        assert "connector" not in result

    def test_parse_invalid_json(self):
        from lamb_cli.commands.assistant import _parse_metadata

        data = {"name": "test", "metadata": "not-json{"}
        result = _parse_metadata(data)
        assert "connector" not in result
