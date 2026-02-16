"""Shared fixtures for LAMB CLI tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_config_dir(tmp_path: Path):
    """Redirect config/credentials to a temp directory."""
    config_dir = tmp_path / "lamb-config"
    config_dir.mkdir()
    with (
        patch("lamb_cli.config.CONFIG_DIR", config_dir),
        patch("lamb_cli.config.CONFIG_FILE", config_dir / "config.toml"),
        patch("lamb_cli.config.CREDENTIALS_FILE", config_dir / "credentials.toml"),
    ):
        yield config_dir


@pytest.fixture()
def mock_token():
    """Provide a fake token via environment variable."""
    with patch.dict(os.environ, {"LAMB_TOKEN": "test-token-abc123"}):
        yield "test-token-abc123"


@pytest.fixture()
def mock_server_url():
    """Provide a fake server URL via environment variable."""
    with patch.dict(os.environ, {"LAMB_SERVER_URL": "http://test-server:9099"}):
        yield "http://test-server:9099"
