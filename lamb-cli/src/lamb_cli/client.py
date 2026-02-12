"""HTTP client wrapper for the LAMB API.

Provides a thin wrapper around httpx that handles auth headers,
base URL resolution, and maps HTTP errors to typed exceptions.
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from lamb_cli.config import get_server_url, get_token
from lamb_cli.errors import ApiError, AuthenticationError, NetworkError, NotFoundError


class LambClient:
    """Wrapper around httpx.Client for LAMB API calls."""

    def __init__(self, server_url: str, token: str | None = None, timeout: float = 30.0):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(
            base_url=server_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "LambClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- HTTP verbs ---

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

    def post_form(self, path: str, data: dict, **kwargs: Any) -> Any:
        """POST with form-encoded body."""
        return self._request("POST", path, data=data, **kwargs)

    def upload_file(
        self, path: str, file_path: str, field_name: str = "file", **kwargs: Any
    ) -> Any:
        """Upload a file via multipart form."""
        with open(file_path, "rb") as f:
            files = {field_name: f}
            return self._request("POST", path, files=files, **kwargs)

    def stream_post(self, path: str, **kwargs: Any) -> Iterator[str]:
        """POST and yield streaming text chunks."""
        try:
            with self._http.stream("POST", path, **kwargs) as resp:
                self._check_status(resp)
                for chunk in resp.iter_text():
                    yield chunk
        except httpx.HTTPStatusError as exc:
            self._raise_for_status(exc.response)

    # --- Internal ---

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise NetworkError(f"Cannot connect to server: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"HTTP error: {exc}") from exc
        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> Any:
        if resp.is_success:
            if not resp.content:
                return {}
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                return resp.json()
            return resp.text
        self._raise_for_status(resp)

    def _check_status(self, resp: httpx.Response) -> None:
        """Check status for streaming responses."""
        if not resp.is_success:
            self._raise_for_status(resp)

    def _raise_for_status(self, resp: httpx.Response) -> None:
        """Map HTTP status codes to typed exceptions."""
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text

        if resp.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {detail}")
        if resp.status_code == 403:
            raise AuthenticationError(f"Permission denied: {detail}")
        if resp.status_code == 404:
            raise NotFoundError(f"Not found: {detail}")
        raise ApiError(f"API error ({resp.status_code}): {detail}", status_code=resp.status_code)


def get_client(require_auth: bool = True) -> LambClient:
    """Build a LambClient from current config/credentials.

    Args:
        require_auth: If True, raise AuthenticationError when no token is available.
    """
    server_url = get_server_url()
    token = get_token()
    if require_auth and not token:
        raise AuthenticationError(
            "Not logged in. Run 'lamb login' first or set LAMB_TOKEN."
        )
    return LambClient(server_url=server_url, token=token)
