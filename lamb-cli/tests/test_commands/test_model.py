"""Tests for model commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_MODELS = {
    "object": "list",
    "data": [
        {"id": "lamb_assistant.1", "name": "Math Tutor", "owned_by": "user1"},
        {"id": "lamb_assistant.2", "name": "History Helper", "owned_by": "user2"},
    ],
}


class TestModelList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_MODELS)
        result = runner.invoke(app, ["model", "list"])
        assert result.exit_code == 0
        assert "Math Tutor" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_MODELS)
        result = runner.invoke(app, ["model", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["id"] == "lamb_assistant.1"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_MODELS)
        result = runner.invoke(app, ["model", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "lamb_assistant.1" in lines[0]
