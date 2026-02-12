"""Exception hierarchy and exit codes for LAMB CLI."""


class LambCliError(Exception):
    """Base exception for all LAMB CLI errors."""

    exit_code: int = 1


class ConfigError(LambCliError):
    """Configuration or local file errors."""

    exit_code = 1


class ApiError(LambCliError):
    """Server returned an error response."""

    exit_code = 2

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NetworkError(LambCliError):
    """Cannot reach the server."""

    exit_code = 3


class AuthenticationError(LambCliError):
    """Invalid or missing credentials."""

    exit_code = 4


class NotFoundError(LambCliError):
    """Requested resource does not exist."""

    exit_code = 5


def exit_code_for(exc: Exception) -> int:
    """Return the CLI exit code for an exception."""
    if isinstance(exc, LambCliError):
        return exc.exit_code
    return 1
