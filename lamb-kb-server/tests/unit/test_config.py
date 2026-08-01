"""Unit tests for backend/config.py.

Config is loaded at import time, so env-var resolution tests use
``importlib.reload(config)`` after ``monkeypatch.setenv``. Each test that
manipulates env vars restores the original state via the ``reload_config``
fixture so subsequent tests are unaffected.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture()
def reload_config(monkeypatch) -> Iterator[None]:
    """Reload config before the test body runs and restore afterwards.

    Yields the module so tests can re-reload after changing env vars:

        def test_foo(reload_config, monkeypatch):
            monkeypatch.setenv("HOST", "1.2.3.4")
            import config
            importlib.reload(config)
            assert config.HOST == "1.2.3.4"
    """
    import config  # noqa: PLC0415

    yield
    # Restore the module to the state expected by the rest of the test session.
    importlib.reload(config)


# ---------------------------------------------------------------------------
# Defaults (env vars not set)
# ---------------------------------------------------------------------------


def test_defaults(monkeypatch, reload_config) -> None:
    """When no env vars are set, all defaults must match their documented values."""
    for key in (
        "HOST",
        "PORT",
        "LOG_LEVEL",
        "MAX_CONCURRENT_INGESTIONS",
        "INGESTION_TASK_TIMEOUT_SECONDS",
        "MAX_REQUEST_SIZE_BYTES",
        "DATA_DIR",
        "QDRANT_URL",
        "QDRANT_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.HOST == "0.0.0.0"
    assert config.PORT == 9092
    assert config.LOG_LEVEL == "INFO"
    assert config.MAX_CONCURRENT_INGESTIONS == 3
    assert config.INGESTION_TASK_TIMEOUT_SECONDS == 1800
    assert config.MAX_REQUEST_SIZE_BYTES == 200 * 1024 * 1024
    assert config.DATA_DIR == Path("data")
    assert config.QDRANT_URL == ""
    assert config.QDRANT_API_KEY == ""


# ---------------------------------------------------------------------------
# LOG_LEVEL uppercasing
# ---------------------------------------------------------------------------


def test_log_level_is_uppercased(monkeypatch, reload_config) -> None:
    """LOG_LEVEL must be upper-cased regardless of input case."""
    monkeypatch.setenv("LOG_LEVEL", "debug")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.LOG_LEVEL == "DEBUG"


def test_log_level_mixed_case(monkeypatch, reload_config) -> None:
    monkeypatch.setenv("LOG_LEVEL", "Warning")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.LOG_LEVEL == "WARNING"


# ---------------------------------------------------------------------------
# Derived path constants
# ---------------------------------------------------------------------------


def test_storage_dir_is_under_data_dir(monkeypatch, reload_config) -> None:
    """STORAGE_DIR must be DATA_DIR / 'storage'."""
    monkeypatch.setenv("DATA_DIR", "/tmp/kbs-test-data")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.STORAGE_DIR == config.DATA_DIR / "storage"
    assert config.STORAGE_DIR == Path("/tmp/kbs-test-data/storage")


def test_db_path_is_under_data_dir(monkeypatch, reload_config) -> None:
    """DB_PATH must be DATA_DIR / 'kb-server.db'."""
    monkeypatch.setenv("DATA_DIR", "/tmp/kbs-test-data")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.DB_PATH == config.DATA_DIR / "kb-server.db"
    assert config.DB_PATH == Path("/tmp/kbs-test-data/kb-server.db")


# ---------------------------------------------------------------------------
# ensure_directories()
# ---------------------------------------------------------------------------


def test_ensure_directories_creates_dirs(monkeypatch, reload_config, tmp_path) -> None:
    """ensure_directories() must create DATA_DIR and STORAGE_DIR."""
    data = tmp_path / "fresh-data"
    monkeypatch.setenv("DATA_DIR", str(data))

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert not data.exists()
    assert not config.STORAGE_DIR.exists()

    config.ensure_directories()

    assert data.is_dir()
    assert config.STORAGE_DIR.is_dir()


def test_ensure_directories_is_idempotent(monkeypatch, reload_config, tmp_path) -> None:
    """Calling ensure_directories() twice must not raise."""
    data = tmp_path / "idempotent-data"
    monkeypatch.setenv("DATA_DIR", str(data))

    import config  # noqa: PLC0415

    importlib.reload(config)

    config.ensure_directories()
    config.ensure_directories()  # must not raise

    assert data.is_dir()
    assert config.STORAGE_DIR.is_dir()


def test_ensure_directories_when_already_exist(
    monkeypatch, reload_config, tmp_path
) -> None:
    """If DATA_DIR and STORAGE_DIR already exist, ensure_directories() is a no-op."""
    data = tmp_path / "existing-data"
    storage = data / "storage"
    data.mkdir(parents=True)
    storage.mkdir(parents=True)

    monkeypatch.setenv("DATA_DIR", str(data))

    import config  # noqa: PLC0415

    importlib.reload(config)

    config.ensure_directories()  # must not raise

    assert data.is_dir()
    assert storage.is_dir()


# ---------------------------------------------------------------------------
# plugin_mode()
# ---------------------------------------------------------------------------


def test_plugin_mode_default_is_enable(monkeypatch) -> None:
    """plugin_mode returns 'ENABLE' when the env var is not set."""
    monkeypatch.delenv("VECTOR_DB_CHROMADB", raising=False)

    import config  # noqa: PLC0415

    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "ENABLE"


def test_plugin_mode_disable(monkeypatch) -> None:
    """plugin_mode returns 'DISABLE' when env var is set to 'DISABLE'."""
    monkeypatch.setenv("VECTOR_DB_CHROMADB", "DISABLE")

    import config  # noqa: PLC0415

    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "DISABLE"


def test_plugin_mode_enable_lowercase(monkeypatch) -> None:
    """plugin_mode is case-insensitive — 'enable' should return 'ENABLE'."""
    monkeypatch.setenv("VECTOR_DB_CHROMADB", "enable")

    import config  # noqa: PLC0415

    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "ENABLE"


def test_plugin_mode_disable_lowercase(monkeypatch) -> None:
    """plugin_mode is case-insensitive — 'disable' should return 'DISABLE'."""
    monkeypatch.setenv("VECTOR_DB_CHROMADB", "disable")

    import config  # noqa: PLC0415

    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "DISABLE"


def test_plugin_mode_unknown_value_defaults_to_enable(monkeypatch) -> None:
    """Unknown env var values default to 'ENABLE'."""
    monkeypatch.setenv("VECTOR_DB_CHROMADB", "MAYBE")

    import config  # noqa: PLC0415

    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "ENABLE"


def test_plugin_mode_builds_correct_env_key(monkeypatch) -> None:
    """plugin_mode reads the correct env key: {CATEGORY}_{NAME} upper-cased."""
    monkeypatch.setenv("CHUNKING_SIMPLE", "DISABLE")
    monkeypatch.delenv("VECTOR_DB_CHROMADB", raising=False)

    import config  # noqa: PLC0415

    assert config.plugin_mode("chunking", "simple") == "DISABLE"
    assert config.plugin_mode("VECTOR_DB", "CHROMADB") == "ENABLE"


def test_plugin_mode_empty_value_defaults_to_enable(monkeypatch) -> None:
    """An empty string value is not in ('ENABLE', 'DISABLE') so defaults to 'ENABLE'."""
    monkeypatch.setenv("EMBEDDING_OPENAI", "")

    import config  # noqa: PLC0415

    assert config.plugin_mode("EMBEDDING", "OPENAI") == "ENABLE"


# ---------------------------------------------------------------------------
# Qdrant env vars
# ---------------------------------------------------------------------------


def test_qdrant_url_loaded_from_env(monkeypatch, reload_config) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.QDRANT_URL == "http://qdrant:6333"


def test_qdrant_api_key_loaded_from_env(monkeypatch, reload_config) -> None:
    monkeypatch.setenv("QDRANT_API_KEY", "super-secret-key")

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.QDRANT_API_KEY == "super-secret-key"


def test_qdrant_defaults_empty_string(monkeypatch, reload_config) -> None:
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    import config  # noqa: PLC0415

    importlib.reload(config)

    assert config.QDRANT_URL == ""
    assert config.QDRANT_API_KEY == ""
