"""
Tests for AAC Moodle command passthrough and integration support in the pastor branch.

These tests verify the `moodle` passthrough command in liteshell, credential
injection from the per-user integrations store, and command key resolution for
passthrough commands.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is on sys.path when running from repository root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lamb.aac.authorization import ActionAuthorizer, classify_user_confirmation
from lamb.aac.liteshell.commands import moodle_cmd
from lamb.aac.liteshell.shell import CommandContext, LiteShell


class DummyProcess:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_ctx() -> CommandContext:
    return CommandContext(
        http=None,
        server_url="http://localhost",
        token="fake-token",
        user_email="tester@example.com",
        organization_id=1,
        user_id=42,
    )


@patch("subprocess.run")
@patch("shutil.which", return_value="/usr/bin/moodle")
@patch("lamb.aac.liteshell.commands._integrations_store")
def test_moodle_cmd_uses_user_integration_credentials(
    mock_store_factory, mock_which, mock_run
):
    """moodle_cmd injects stored Moodle credentials into the subprocess environment."""
    mock_store = MagicMock()
    mock_store.get_config.return_value = {
        "url": "https://moodle.example.com",
        "token": "token123",
        "service": "moodle_mobile_app",
    }
    mock_store_factory.return_value = mock_store
    mock_run.return_value = DummyProcess(returncode=0, stdout="success", stderr="")

    ctx = _make_ctx()
    result = moodle_cmd(ctx, ["course", "list"], {})

    assert result["exit_code"] == 0
    assert result["stdout"] == "success"
    assert result["credential_source"] == "user_integration"
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["/usr/bin/moodle", "course", "list"]
    assert kwargs["env"]["MOODLE_URL"] == "https://moodle.example.com"
    assert kwargs["env"]["MOODLE_TOKEN"] == "token123"
    assert kwargs["env"]["MOODLE_SERVICE"] == "moodle_mobile_app"


@patch("subprocess.run")
@patch("shutil.which", return_value="/usr/bin/moodle")
@patch("lamb.aac.liteshell.commands._integrations_store")
def test_moodle_cmd_falls_back_to_ambient_env(
    mock_store_factory, mock_which, mock_run
):
    """moodle_cmd uses ambient environment when no user integration is configured."""
    mock_store = MagicMock()
    mock_store.get_config.return_value = None
    mock_store_factory.return_value = mock_store
    mock_run.return_value = DummyProcess(returncode=0, stdout="ambient", stderr="")

    ctx = _make_ctx()
    result = moodle_cmd(ctx, ["assignment", "list", "--course", "10"], {})

    assert result["credential_source"] == "ambient"
    assert result["command"] == "moodle assignment list --course 10"
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["env"] is None


@patch("shutil.which", return_value=None)
def test_moodle_cmd_raises_when_binary_missing(mock_which):
    """moodle_cmd fails cleanly when the moodle CLI binary is not installed."""
    ctx = _make_ctx()
    with pytest.raises(RuntimeError, match="moodle-cli is not installed"):
        moodle_cmd(ctx, ["course", "list"], {})


@pytest.mark.asyncio
@patch("lamb.aac.liteshell.shell.LiteShell._get_http", return_value=None)
@patch("subprocess.run")
@patch("shutil.which", return_value="/usr/bin/moodle")
@patch("lamb.aac.liteshell.commands._integrations_store")
async def test_liteshell_passes_through_moodle_commands(
    mock_store_factory, mock_which, mock_run, mock_get_http
):
    """LiteShell routes `moodle ...` commands through the passthrough handler."""
    mock_store = MagicMock()
    mock_store.get_config.return_value = {
        "url": "https://moodle.example.com",
        "token": "token123",
    }
    mock_store_factory.return_value = mock_store
    mock_run.return_value = DummyProcess(returncode=0, stdout="ok", stderr="")

    shell = LiteShell(
        server_url="http://localhost",
        token="fake-token",
        user_email="tester@example.com",
        organization_id=1,
        user_id=42,
    )

    for command, expected_args in [
        ("lamb moodle course list", ["course", "list"]),
        ("lamb moodle assignment list --course 10", ["assignment", "list", "--course", "10"]),
        ("lamb moodle report summary", ["report", "summary"]),
    ]:
        result = await shell.execute(command)
        assert result.success is True
        assert result.data["command"] == f"moodle {' '.join(expected_args)}"
        assert mock_run.call_args[0][0] == ["/usr/bin/moodle", *expected_args]


def test_action_authorizer_resolves_moodle_passthrough_key():
    authorizer = ActionAuthorizer()
    action_key = authorizer.resolve_action_key("lamb moodle course list")
    assert action_key == "moodle"


def test_classify_user_confirmation_approval_and_rejection():
    assert classify_user_confirmation("sí") == "approve"
    assert classify_user_confirmation("no gracias") == "reject"
    assert classify_user_confirmation("please do it") == "approve"
    assert classify_user_confirmation("not now") == "reject"
