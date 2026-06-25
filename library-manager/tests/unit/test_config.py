"""Unit tests for ``backend/config.py`` env parsing, defaults, and helpers.

``config`` reads ``os.environ`` once at import time into module-level
constants. To test parsing of *different* env values we reload the module
under ``monkeypatch.setenv`` and always reload it back to the real
(session-conftest) environment afterwards, so neighbouring tests that import
``config`` see the canonical values.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import config
import pytest

# Constants these tests reload/patch and that other modules bind by value
# (e.g. ``from config import CONTENT_DIR``). They MUST be returned to their
# canonical session values after every test.
_CONFIG_CONSTANTS = (
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "LAMB_API_TOKEN",
    "DATA_DIR",
    "CONTENT_DIR",
    "DB_PATH",
    "MAX_CONCURRENT_IMPORTS",
    "IMPORT_TASK_TIMEOUT_SECONDS",
    "MAX_UPLOAD_SIZE_BYTES",
    "MAX_ZIP_IMPORT_SIZE_BYTES",
    "PERMALINK_PREFIX",
)


@pytest.fixture(autouse=True)
def _isolate_config():
    """Snapshot config's constants and restore them by value after each test.

    ``importlib.reload(config)`` mutates the module in place, and the in-test
    ``finally: _reload_config()`` runs *before* monkeypatch restores the
    environment — so without this fixture a reload under a patched/deleted env
    would leak the wrong ``config.CONTENT_DIR`` (etc.) into every later test in
    the session. Restoring by value here is independent of env-teardown
    ordering and keeps the session canonical.
    """
    saved = {k: getattr(config, k) for k in _CONFIG_CONSTANTS}
    yield
    for k, v in saved.items():
        setattr(config, k, v)


def _reload_config():
    """Reload the config module and return the fresh module object."""
    return importlib.reload(config)


class TestDefaults:
    """Defaults apply when the corresponding env vars are unset."""

    def test_server_defaults(self, monkeypatch):
        """HOST/PORT/LOG_LEVEL fall back to documented defaults."""
        for var in ("HOST", "PORT", "LOG_LEVEL"):
            monkeypatch.delenv(var, raising=False)
        try:
            cfg = _reload_config()
            assert cfg.HOST == "0.0.0.0", "default host"
            assert cfg.PORT == 9091, "default port"
            assert cfg.LOG_LEVEL == "INFO", "default log level"
        finally:
            _reload_config()

    def test_task_and_upload_defaults(self, monkeypatch):
        """Task concurrency/timeout and upload-size defaults match source."""
        for var in (
            "MAX_CONCURRENT_IMPORTS",
            "IMPORT_TASK_TIMEOUT_SECONDS",
            "MAX_UPLOAD_SIZE_BYTES",
            "MAX_ZIP_IMPORT_SIZE_BYTES",
            "PERMALINK_PREFIX",
        ):
            monkeypatch.delenv(var, raising=False)
        try:
            cfg = _reload_config()
            assert cfg.MAX_CONCURRENT_IMPORTS == 3
            assert cfg.IMPORT_TASK_TIMEOUT_SECONDS == 600
            assert cfg.MAX_UPLOAD_SIZE_BYTES == 500 * 1024 * 1024
            assert cfg.MAX_ZIP_IMPORT_SIZE_BYTES == 200 * 1024 * 1024
            assert cfg.PERMALINK_PREFIX == "/docs"
        finally:
            _reload_config()


class TestEnvParsing:
    """Environment values override the defaults and are typed correctly."""

    def test_int_vars_parsed_from_strings(self, monkeypatch):
        """Integer env vars are coerced from their string representation."""
        monkeypatch.setenv("PORT", "1234")
        monkeypatch.setenv("MAX_CONCURRENT_IMPORTS", "7")
        monkeypatch.setenv("IMPORT_TASK_TIMEOUT_SECONDS", "42")
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "999")
        monkeypatch.setenv("MAX_ZIP_IMPORT_SIZE_BYTES", "888")
        try:
            cfg = _reload_config()
            assert cfg.PORT == 1234 and isinstance(cfg.PORT, int)
            assert cfg.MAX_CONCURRENT_IMPORTS == 7
            assert cfg.IMPORT_TASK_TIMEOUT_SECONDS == 42
            assert cfg.MAX_UPLOAD_SIZE_BYTES == 999
            assert cfg.MAX_ZIP_IMPORT_SIZE_BYTES == 888
        finally:
            _reload_config()

    def test_log_level_uppercased(self, monkeypatch):
        """LOG_LEVEL is upper-cased regardless of the env value's case."""
        monkeypatch.setenv("LOG_LEVEL", "debug")
        try:
            cfg = _reload_config()
            assert cfg.LOG_LEVEL == "DEBUG", "log level should be upper-cased"
        finally:
            _reload_config()

    def test_token_and_permalink_from_env(self, monkeypatch):
        """LAMB_API_TOKEN and PERMALINK_PREFIX read raw string env values."""
        monkeypatch.setenv("LAMB_API_TOKEN", "secret-xyz")
        monkeypatch.setenv("PERMALINK_PREFIX", "/files")
        try:
            cfg = _reload_config()
            assert cfg.LAMB_API_TOKEN == "secret-xyz"
            assert cfg.PERMALINK_PREFIX == "/files"
        finally:
            _reload_config()

    def test_token_defaults_empty(self, monkeypatch):
        """LAMB_API_TOKEN defaults to an empty string when unset."""
        monkeypatch.delenv("LAMB_API_TOKEN", raising=False)
        try:
            cfg = _reload_config()
            assert cfg.LAMB_API_TOKEN == ""
        finally:
            _reload_config()


class TestDerivedPaths:
    """DATA_DIR drives the derived CONTENT_DIR and DB_PATH paths."""

    def test_data_dir_from_env_and_derived_paths(self, monkeypatch):
        """CONTENT_DIR and DB_PATH are derived under the configured DATA_DIR."""
        monkeypatch.setenv("DATA_DIR", "/tmp/lm-cfg-test")
        try:
            cfg = _reload_config()
            assert Path("/tmp/lm-cfg-test") == cfg.DATA_DIR
            assert Path("/tmp/lm-cfg-test/content") == cfg.CONTENT_DIR
            assert Path("/tmp/lm-cfg-test/library-manager.db") == cfg.DB_PATH
        finally:
            _reload_config()

    def test_default_data_dir_relative(self, monkeypatch):
        """DATA_DIR defaults to the relative ``data`` directory."""
        monkeypatch.delenv("DATA_DIR", raising=False)
        try:
            cfg = _reload_config()
            assert Path("data") == cfg.DATA_DIR
            assert Path("data/content") == cfg.CONTENT_DIR
            assert Path("data/library-manager.db") == cfg.DB_PATH
        finally:
            _reload_config()


class TestEnsureDirectories:
    """``ensure_directories`` creates DATA_DIR and CONTENT_DIR idempotently."""

    def test_creates_data_and_content(self, monkeypatch, tmp_storage):
        """Both DATA_DIR and CONTENT_DIR are created when missing."""
        data = tmp_storage / "newdata"
        content = data / "content"
        monkeypatch.setattr(config, "DATA_DIR", data)
        monkeypatch.setattr(config, "CONTENT_DIR", content)
        assert not data.exists()
        config.ensure_directories()
        assert data.is_dir(), "DATA_DIR should be created"
        assert content.is_dir(), "CONTENT_DIR should be created"

    def test_idempotent(self, monkeypatch, tmp_storage):
        """Calling twice with existing dirs does not raise (exist_ok=True)."""
        data = tmp_storage / "d"
        content = data / "content"
        monkeypatch.setattr(config, "DATA_DIR", data)
        monkeypatch.setattr(config, "CONTENT_DIR", content)
        config.ensure_directories()
        config.ensure_directories()
        assert content.is_dir()
