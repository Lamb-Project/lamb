"""Core HTTP client for Moodle Web Services REST API."""

from __future__ import annotations

from typing import Any

import httpx

from moodle_cli.client.exceptions import (
    AuthenticationError,
    ConnectionError,
    MoodleAPIError,
)


def flatten_params(params: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested dicts/lists into Moodle's bracket-notation parameters.

    Example: {"courses": [{"id": 1}]} → {"courses[0][id]": "1"}
    """
    flat: dict[str, str] = {}
    for key, value in params.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_params(value, full_key))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                idx_key = f"{full_key}[{i}]"
                if isinstance(item, dict):
                    flat.update(flatten_params(item, idx_key))
                else:
                    flat[idx_key] = str(item)
        elif isinstance(value, bool):
            flat[full_key] = "1" if value else "0"
        elif value is not None:
            flat[full_key] = str(value)
    return flat


class MoodleHTTPClient:
    """HTTP client for Moodle Web Services."""

    def __init__(
        self,
        base_url: str,
        token: str,
        service: str = "moodle_mobile_app",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.service = service
        self._client = httpx.Client(timeout=timeout)

    @property
    def rest_url(self) -> str:
        return f"{self.base_url}/webservice/rest/server.php"

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Call a Moodle Web Services function.

        Returns the parsed JSON response (dict or list).
        Raises MoodleAPIError on Moodle-level errors.
        """
        flat = flatten_params(params)
        flat["wstoken"] = self.token
        flat["wsfunction"] = wsfunction
        flat["moodlewsrestformat"] = "json"

        try:
            resp = self._client.post(self.rest_url, data=flat)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Could not connect to {self.base_url}: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ConnectionError(
                f"HTTP {exc.response.status_code} from {self.base_url}"
            ) from exc

        data = resp.json()

        if isinstance(data, dict) and "exception" in data:
            raise MoodleAPIError(
                message=data.get("message", "Unknown Moodle error"),
                error_code=data.get("errorcode"),
                debug_info=data.get("debuginfo"),
            )

        return data

    @staticmethod
    def authenticate(base_url: str, username: str, password: str, service: str = "moodle_mobile_app") -> str:
        """Authenticate and return a token.

        Posts to /login/token.php and returns the token string.
        """
        url = f"{base_url.rstrip('/')}/login/token.php"
        try:
            resp = httpx.post(
                url,
                data={
                    "username": username,
                    "password": password,
                    "service": service,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Could not connect to {base_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ConnectionError(f"HTTP {exc.response.status_code} from {base_url}") from exc

        data = resp.json()
        if "token" in data:
            return data["token"]

        error = data.get("error", "Authentication failed")
        raise AuthenticationError(error, error_code=data.get("errorcode"))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MoodleHTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
