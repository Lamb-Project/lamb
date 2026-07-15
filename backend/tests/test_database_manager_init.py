"""Tests for LambDatabaseManager one-time process initialization."""

import pytest
from unittest.mock import patch

from lamb.database_manager import LambDatabaseManager


@pytest.fixture(autouse=True)
def reset_class_flags():
    """Isolate tests: each test starts with fresh class-level init flags."""
    LambDatabaseManager._optimizations_applied = False
    LambDatabaseManager._migrations_applied = False
    LambDatabaseManager._system_org_initialized = False
    yield
    LambDatabaseManager._optimizations_applied = False
    LambDatabaseManager._migrations_applied = False
    LambDatabaseManager._system_org_initialized = False


@patch.object(LambDatabaseManager, "initialize_system_organization")
@patch.object(LambDatabaseManager, "run_migrations")
@patch.object(LambDatabaseManager, "_configure_database_optimizations")
@patch("lamb.database_manager.os.path.exists", return_value=True)
@patch("lamb.database_manager.load_dotenv")
def test_second_instance_skips_optimizations_and_migrations(
    _load_dotenv,
    _exists,
    mock_configure,
    mock_migrations,
    mock_init_system_org,
):
    LambDatabaseManager()
    LambDatabaseManager()

    mock_configure.assert_called_once()
    mock_migrations.assert_called_once()
    mock_init_system_org.assert_called_once()
