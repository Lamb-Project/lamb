"""Tests for MoodleHTTPClient."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from moodle_cli.client.exceptions import AuthenticationError, MoodleAPIError
from moodle_cli.client.http import MoodleHTTPClient, flatten_params

BASE_URL = "https://moodle.example.com"
TOKEN = "test-token"


class TestFlattenParams:
    def test_simple(self) -> None:
        assert flatten_params({"key": "value"}) == {"key": "value"}

    def test_nested_dict(self) -> None:
        result = flatten_params({"options": {"ids": "1"}})
        assert result == {"options[ids]": "1"}

    def test_list(self) -> None:
        result = flatten_params({"ids": [1, 2, 3]})
        assert result == {"ids[0]": "1", "ids[1]": "2", "ids[2]": "3"}

    def test_list_of_dicts(self) -> None:
        result = flatten_params({"courses": [{"id": 1, "name": "Test"}]})
        assert result == {"courses[0][id]": "1", "courses[0][name]": "Test"}

    def test_bool(self) -> None:
        result = flatten_params({"visible": True, "hidden": False})
        assert result == {"visible": "1", "hidden": "0"}

    def test_none_skipped(self) -> None:
        result = flatten_params({"key": None, "other": "val"})
        assert result == {"other": "val"}

    def test_deeply_nested(self) -> None:
        result = flatten_params({"a": {"b": {"c": "deep"}}})
        assert result == {"a[b][c]": "deep"}


class TestMoodleHTTPClient:
    @respx.mock
    def test_call_success(self) -> None:
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=[{"id": 1, "name": "Test"}])
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        result = client.call("core_course_get_courses")
        assert result == [{"id": 1, "name": "Test"}]

    @respx.mock
    def test_call_api_error(self) -> None:
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json={
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token",
            })
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        with pytest.raises(MoodleAPIError, match="Invalid token"):
            client.call("core_webservice_get_site_info")

    @respx.mock
    def test_call_sends_correct_params(self) -> None:
        route = respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json={})
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        client.call("test_func", courseid=42)
        request = route.calls[0].request
        body = request.content.decode()
        assert "wsfunction=test_func" in body
        assert "wstoken=test-token" in body
        assert "courseid=42" in body

    @respx.mock
    def test_authenticate_success(self) -> None:
        respx.post(f"{BASE_URL}/login/token.php").mock(
            return_value=Response(200, json={"token": "new-token-123"})
        )
        token = MoodleHTTPClient.authenticate(BASE_URL, "admin", "pass123")
        assert token == "new-token-123"

    @respx.mock
    def test_authenticate_failure(self) -> None:
        respx.post(f"{BASE_URL}/login/token.php").mock(
            return_value=Response(200, json={
                "error": "Invalid login",
                "errorcode": "invalidlogin",
            })
        )
        with pytest.raises(AuthenticationError, match="Invalid login"):
            MoodleHTTPClient.authenticate(BASE_URL, "admin", "wrong")

    def test_context_manager(self) -> None:
        with MoodleHTTPClient(base_url=BASE_URL, token=TOKEN) as client:
            assert client.rest_url == f"{BASE_URL}/webservice/rest/server.php"
