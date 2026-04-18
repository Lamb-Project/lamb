"""Configuration manager — TOML-based profile storage."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel

from moodle_cli.client.exceptions import ConfigError, ProfileNotFoundError

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "moodle-cli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"


class Profile(BaseModel):
    """A Moodle connection profile."""

    url: str
    username: str
    service: str = "moodle_mobile_app"


class Config(BaseModel):
    """Root config file model."""

    default_profile: str = "default"
    profiles: dict[str, Profile] = {}


class ConfigManager:
    """Reads/writes the TOML config file and manages profiles."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.path = config_path or DEFAULT_CONFIG_FILE

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        try:
            with open(self.path, "rb") as f:
                raw = tomllib.load(f)
        except Exception as exc:
            raise ConfigError(f"Failed to read config: {exc}") from exc
        profiles: dict[str, Profile] = {}
        for name, data in raw.get("profiles", {}).items():
            profiles[name] = Profile(**data)
        return Config(
            default_profile=raw.get("default_profile", "default"),
            profiles=profiles,
        )

    def save(self, config: Config) -> None:
        self._ensure_dir()
        data: dict[str, Any] = {
            "default_profile": config.default_profile,
            "profiles": {
                name: prof.model_dump() for name, prof in config.profiles.items()
            },
        }
        with open(self.path, "wb") as f:
            tomli_w.dump(data, f)

    def get_profile(self, name: str | None = None) -> tuple[str, Profile]:
        config = self.load()
        profile_name = name or config.default_profile
        profile = config.profiles.get(profile_name)
        if profile is None:
            available = ", ".join(config.profiles.keys()) or "(none)"
            raise ProfileNotFoundError(
                f"Profile '{profile_name}' not found. Available: {available}"
            )
        return profile_name, profile

    def set_profile(self, name: str, profile: Profile) -> None:
        config = self.load()
        config.profiles[name] = profile
        if not config.profiles or len(config.profiles) == 1:
            config.default_profile = name
        self.save(config)

    def remove_profile(self, name: str) -> None:
        config = self.load()
        if name not in config.profiles:
            raise ProfileNotFoundError(f"Profile '{name}' not found.")
        del config.profiles[name]
        if config.default_profile == name:
            config.default_profile = next(iter(config.profiles), "default")
        self.save(config)

    def set_default(self, name: str) -> None:
        config = self.load()
        if name not in config.profiles:
            raise ProfileNotFoundError(f"Profile '{name}' not found.")
        config.default_profile = name
        self.save(config)

    def list_profiles(self) -> list[tuple[str, Profile, bool]]:
        config = self.load()
        return [
            (name, prof, name == config.default_profile)
            for name, prof in config.profiles.items()
        ]
