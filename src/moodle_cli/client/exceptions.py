"""Moodle API exception hierarchy."""

from __future__ import annotations


class MoodleError(Exception):
    """Base exception for all Moodle errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


class MoodleAPIError(MoodleError):
    """Error returned by the Moodle Web Services API."""

    HINTS: dict[str, str] = {
        "invalidtoken": "Your token is invalid or expired. Run: moodle auth login",
        "accessexception": "You don't have permission for this operation.",
        "invalidparameter": "One or more parameters are invalid.",
        "invalidrecord": "The requested record does not exist.",
        "webservicenotavailable": "This web service function is not enabled on the site.",
        "nopermissions": "You don't have the required capability.",
        "sitenotfound": "The Moodle site could not be reached.",
        "invalidresponse": "Unexpected response format from Moodle.",
        "servicenotavailable": "External services are disabled on this site.",
        "forabortedreason": "The operation was aborted by the server.",
    }

    def __init__(
        self, message: str, error_code: str | None = None, debug_info: str | None = None
    ) -> None:
        self.debug_info = debug_info
        super().__init__(message, error_code)

    @property
    def hint(self) -> str | None:
        if self.error_code:
            return self.HINTS.get(self.error_code)
        return None


class AuthenticationError(MoodleError):
    """Failed to authenticate with Moodle."""


class ConnectionError(MoodleError):
    """Failed to connect to the Moodle instance."""


class ConfigError(MoodleError):
    """Configuration file error."""


class ProfileNotFoundError(ConfigError):
    """Requested profile does not exist."""
