"""Moodle HTTP client and exceptions."""

from moodle_cli.client.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    MoodleAPIError,
    MoodleError,
    ProfileNotFoundError,
)
from moodle_cli.client.http import MoodleHTTPClient

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "MoodleAPIError",
    "MoodleError",
    "MoodleHTTPClient",
    "ProfileNotFoundError",
]
