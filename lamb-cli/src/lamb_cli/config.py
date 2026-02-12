"""Configuration and credential management for LAMB CLI.

Config/credentials are stored as TOML files under the user config directory
(via platformdirs). Environment variables take precedence over file values.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from platformdirs import user_config_dir

from lamb_cli.errors import ConfigError

CONFIG_DIR = Path(user_config_dir("lamb"))
CONFIG_FILE = CONFIG_DIR / "config.toml"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.toml"

DEFAULT_SERVER_URL = "http://localhost:9099"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load config.toml, returning empty dict if missing."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"Failed to read {CONFIG_FILE}: {exc}") from exc


def save_config(config: dict) -> None:
    """Write config dict to config.toml."""
    _ensure_config_dir()
    try:
        CONFIG_FILE.write_text(tomli_w.dumps(config), encoding="utf-8")
    except Exception as exc:
        raise ConfigError(f"Failed to write {CONFIG_FILE}: {exc}") from exc


def _load_credentials() -> dict:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        return tomllib.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"Failed to read {CREDENTIALS_FILE}: {exc}") from exc


def get_server_url() -> str:
    """Resolve server URL: env var > config file > default."""
    env = os.environ.get("LAMB_SERVER_URL")
    if env:
        return env.rstrip("/")
    config = load_config()
    url = config.get("server_url", DEFAULT_SERVER_URL)
    return url.rstrip("/")


def get_token() -> str | None:
    """Resolve auth token: env var > credentials file."""
    env = os.environ.get("LAMB_TOKEN")
    if env:
        return env
    creds = _load_credentials()
    return creds.get("token")


def get_output_format() -> str:
    """Resolve default output format: config file > 'table'."""
    config = load_config()
    return config.get("output_format", "table")


def get_user_info() -> dict:
    """Return stored user info (email, role, user_type, organization_role)."""
    return _load_credentials()


def save_credentials(
    token: str,
    email: str,
    *,
    name: str = "",
    role: str = "",
    user_type: str = "",
    organization_role: str = "",
) -> None:
    """Persist credentials and user profile with restricted file permissions (0600).

    Stores role info so the CLI can make UX decisions:
    - Platform admins (role='admin') can administer any org.
    - Org admins (organization_role='owner'/'admin') are scoped to their own org.
    """
    _ensure_config_dir()
    data = {
        "token": token,
        "email": email,
        "name": name,
        "role": role,
        "user_type": user_type,
        "organization_role": organization_role,
    }
    try:
        CREDENTIALS_FILE.write_text(tomli_w.dumps(data), encoding="utf-8")
        CREDENTIALS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        raise ConfigError(f"Failed to write credentials: {exc}") from exc


def clear_credentials() -> None:
    """Remove stored credentials."""
    if CREDENTIALS_FILE.exists():
        try:
            CREDENTIALS_FILE.unlink()
        except Exception as exc:
            raise ConfigError(f"Failed to remove credentials: {exc}") from exc
