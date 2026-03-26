"""Tests for config and credential management."""

from __future__ import annotations

import os
import stat
from unittest.mock import patch

import pytest

from lamb_cli.config import (
    clear_credentials,
    get_output_format,
    get_server_url,
    get_token,
    get_user_info,
    load_config,
    save_config,
    save_credentials,
)


class TestGetServerUrl:
    def test_env_var_takes_precedence(self, tmp_config_dir):
        save_config({"server_url": "http://from-config:9099"})
        with patch.dict(os.environ, {"LAMB_SERVER_URL": "http://from-env:9099"}):
            assert get_server_url() == "http://from-env:9099"

    def test_config_file(self, tmp_config_dir):
        save_config({"server_url": "http://from-config:9099"})
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_SERVER_URL", None)
            assert get_server_url() == "http://from-config:9099"

    def test_default(self, tmp_config_dir):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_SERVER_URL", None)
            assert get_server_url() == "http://localhost:9099"

    def test_trailing_slash_stripped(self, tmp_config_dir):
        with patch.dict(os.environ, {"LAMB_SERVER_URL": "http://server:9099/"}):
            assert get_server_url() == "http://server:9099"


class TestGetToken:
    def test_env_var_takes_precedence(self, tmp_config_dir):
        save_credentials("file-token", "a@b.com")
        with patch.dict(os.environ, {"LAMB_TOKEN": "env-token"}):
            assert get_token() == "env-token"

    def test_credentials_file(self, tmp_config_dir):
        save_credentials("file-token", "a@b.com")
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            assert get_token() == "file-token"

    def test_none_when_missing(self, tmp_config_dir):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            assert get_token() is None


class TestGetOutputFormat:
    def test_from_config(self, tmp_config_dir):
        save_config({"output_format": "json"})
        assert get_output_format() == "json"

    def test_default_table(self, tmp_config_dir):
        assert get_output_format() == "table"


class TestSaveCredentials:
    def test_saves_all_fields(self, tmp_config_dir):
        save_credentials(
            "tok123", "user@test.com",
            name="Test User", role="admin",
            user_type="creator", organization_role="owner",
        )
        info = get_user_info()
        assert info["token"] == "tok123"
        assert info["email"] == "user@test.com"
        assert info["name"] == "Test User"
        assert info["role"] == "admin"
        assert info["user_type"] == "creator"
        assert info["organization_role"] == "owner"

    def test_file_permissions(self, tmp_config_dir):
        save_credentials("tok", "a@b.com")
        creds_file = tmp_config_dir / "credentials.toml"
        mode = creds_file.stat().st_mode
        assert mode & stat.S_IRUSR  # owner read
        assert mode & stat.S_IWUSR  # owner write
        assert not (mode & stat.S_IRGRP)  # no group read
        assert not (mode & stat.S_IROTH)  # no other read


class TestClearCredentials:
    def test_removes_file(self, tmp_config_dir):
        save_credentials("tok", "a@b.com")
        creds_file = tmp_config_dir / "credentials.toml"
        assert creds_file.exists()
        clear_credentials()
        assert not creds_file.exists()

    def test_noop_when_missing(self, tmp_config_dir):
        clear_credentials()  # should not raise


class TestLoadSaveConfig:
    def test_round_trip(self, tmp_config_dir):
        save_config({"server_url": "http://x:9099", "output_format": "json"})
        cfg = load_config()
        assert cfg["server_url"] == "http://x:9099"
        assert cfg["output_format"] == "json"

    def test_empty_when_missing(self, tmp_config_dir):
        assert load_config() == {}
