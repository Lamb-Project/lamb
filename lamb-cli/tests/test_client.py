"""Tests for the HTTP client wrapper."""

from __future__ import annotations

import pytest
import httpx

from lamb_cli.client import LambClient, get_client
from lamb_cli.errors import ApiError, AuthenticationError, NetworkError, NotFoundError


class TestLambClient:
    def test_auth_header_injected(self):
        client = LambClient("http://localhost:9099", token="my-token")
        assert client._http.headers["authorization"] == "Bearer my-token"
        client.close()

    def test_no_auth_header_without_token(self):
        client = LambClient("http://localhost:9099")
        assert "authorization" not in client._http.headers
        client.close()

    def test_context_manager(self):
        with LambClient("http://localhost:9099") as client:
            assert client._http is not None


class TestHandleResponse:
    def test_success_json(self, httpx_mock):
        httpx_mock.add_response(json={"ok": True})
        with LambClient("http://localhost:9099") as client:
            data = client.get("/test")
        assert data == {"ok": True}

    def test_success_empty_body(self, httpx_mock):
        httpx_mock.add_response(status_code=200, content=b"")
        with LambClient("http://localhost:9099") as client:
            data = client.get("/test")
        assert data == {}

    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"detail": "bad token"})
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(AuthenticationError, match="bad token"):
                client.get("/test")

    def test_403_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"detail": "forbidden"})
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(AuthenticationError, match="forbidden"):
                client.get("/test")

    def test_404_raises_not_found(self, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"detail": "missing"})
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(NotFoundError, match="missing"):
                client.get("/test")

    def test_500_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"detail": "server error"})
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(ApiError, match="500"):
                client.get("/test")

    def test_api_error_has_status_code(self, httpx_mock):
        httpx_mock.add_response(status_code=422, json={"detail": "validation"})
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(ApiError) as exc_info:
                client.post("/test", json={})
        assert exc_info.value.status_code == 422


class TestNetworkErrors:
    def test_connection_refused(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(NetworkError, match="Cannot connect"):
                client.get("/test")

    def test_timeout(self, httpx_mock):
        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        with LambClient("http://localhost:9099") as client:
            with pytest.raises(NetworkError, match="timed out"):
                client.get("/test")


class TestGetClient:
    def test_requires_token_by_default(self, tmp_config_dir):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            with pytest.raises(AuthenticationError, match="Not logged in"):
                get_client()

    def test_no_auth_required(self, tmp_config_dir):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            client = get_client(require_auth=False)
            client.close()

    def test_uses_env_token(self, tmp_config_dir, mock_token, mock_server_url):
        client = get_client()
        assert client._http.headers["authorization"] == "Bearer test-token-abc123"
        client.close()
