"""Tests for exception hierarchy."""

from moodle_cli.client.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    MoodleAPIError,
    MoodleError,
    ProfileNotFoundError,
)


def test_hierarchy() -> None:
    assert issubclass(MoodleAPIError, MoodleError)
    assert issubclass(AuthenticationError, MoodleError)
    assert issubclass(ConnectionError, MoodleError)
    assert issubclass(ConfigError, MoodleError)
    assert issubclass(ProfileNotFoundError, ConfigError)


def test_api_error_hint() -> None:
    err = MoodleAPIError("bad token", error_code="invalidtoken")
    assert err.hint is not None
    assert "login" in err.hint.lower()


def test_api_error_no_hint() -> None:
    err = MoodleAPIError("something", error_code="unknowncode")
    assert err.hint is None


def test_api_error_debug_info() -> None:
    err = MoodleAPIError("msg", error_code="x", debug_info="stack trace here")
    assert err.debug_info == "stack trace here"
