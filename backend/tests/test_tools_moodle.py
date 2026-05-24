"""
Tests for lamb.completions.tools.moodle — Moodle LMS tool implementations.

Tests cover:
- Utility functions (_moodle_ws_url, _now_ts, _ts_to_iso, _moodle_ws_get, etc.)
- Tool specifications (MOODLE_TOOL_SPEC, MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC)
- Tool implementations (get_moodle_courses, get_moodle_assignments_status)

Run with: pytest backend/tests/test_tools_moodle.py -v
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lamb.completions.tools.moodle import (
    MOODLE_TOOL_SPEC,
    MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC,
    _extract_moodle_user_id_from_request,
    _moodle_ws_get,
    _moodle_ws_url,
    _now_ts,
    _resolve_moodle_user_id_from_email,
    _ts_to_iso,
    get_moodle_courses,
    get_moodle_assignments_status,
)

# ===========================================================================
# Section 1: Shared Utilities
# ===========================================================================


class TestMoodleWsUrl:
    """_moodle_ws_url: URL construction for Moodle Web Services."""

    def test_appends_ws_path(self):
        """Plain URL gets /webservice/rest/server.php appended."""
        result = _moodle_ws_url("https://moodle.example.com")
        assert result == "https://moodle.example.com/webservice/rest/server.php"

    def test_handles_trailing_slash(self):
        """Trailing slash is stripped before appending."""
        result = _moodle_ws_url("https://moodle.example.com/")
        assert result == "https://moodle.example.com/webservice/rest/server.php"

    def test_preserves_existing_server_php(self):
        """URL that already contains server.php is returned as-is."""
        url = "https://moodle.example.com/webservice/rest/server.php"
        result = _moodle_ws_url(url)
        assert result == url

    def test_preserves_server_php_in_subpath(self):
        """server.php anywhere in the URL triggers passthrough."""
        url = "https://example.com/moodle/webservice/rest/server.php"
        result = _moodle_ws_url(url)
        assert result == url


class TestNowTs:
    """_now_ts: current UTC timestamp."""

    def test_returns_int(self):
        """Returns an integer Unix timestamp."""
        result = _now_ts()
        assert isinstance(result, int)
        assert result > 1_700_000_000  # Sanity check: well past 2023


class TestTsToIso:
    """_ts_to_iso: timestamp-to-ISO conversion."""

    def test_converts_valid_ts(self):
        """Valid Unix timestamp returns ISO 8601 string."""
        result = _ts_to_iso(1_700_000_000)
        assert result == "2023-11-14T22:13:20+00:00"

    def test_returns_none_for_none(self):
        """None input returns None."""
        assert _ts_to_iso(None) is None

    def test_returns_none_for_zero(self):
        """Zero or falsy timestamp returns None."""
        assert _ts_to_iso(0) is None

    def test_handles_string_input(self):
        """String timestamp is cast to int."""
        result = _ts_to_iso("1700000000")
        assert result == "2023-11-14T22:13:20+00:00"


@pytest.mark.asyncio
class TestMoodleWsGet:
    """_moodle_ws_get: generic Moodle WS GET request."""

    @patch("httpx.AsyncClient")
    async def test_successful_request(self, mock_client_cls):
        """Successful response returns parsed JSON."""
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "fullname": "Course 1"}]
        mock_client.get.return_value = mock_response

        result = await _moodle_ws_get(
            "https://moodle.test/ws.php", "token123", "core_course_get", [("userid", "5")]
        )

        assert result == [{"id": 1, "fullname": "Course 1"}]
        # Verify the correct params were passed
        call_params = mock_client.get.call_args[1]["params"]
        call_dict = dict(call_params)
        assert call_dict["wstoken"] == "token123"
        assert call_dict["wsfunction"] == "core_course_get"
        assert call_dict["userid"] == "5"

    @patch("httpx.AsyncClient")
    async def test_moodle_exception_raises(self, mock_client_cls):
        """Moodle error shape {'exception': ...} raises RuntimeError."""
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "exception": "dml_missing_record_exception",
            "message": "User not found",
        }
        mock_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="User not found"):
            await _moodle_ws_get("https://moodle.test/ws.php", "token", "core_course_get", [])

    @patch("httpx.AsyncClient")
    async def test_moodle_exception_fallback_message(self, mock_client_cls):
        """Moodle error without 'message' falls back to errorcode."""
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"exception": "invalid_parameter_exception"}
        mock_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="Moodle API error"):
            await _moodle_ws_get("https://moodle.test/ws.php", "token", "core_course_get", [])

    @patch("httpx.AsyncClient")
    async def test_http_error_raises(self, mock_client_cls):
        """HTTP errors are propagated."""
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock()
        )

        with pytest.raises(httpx.HTTPStatusError):
            await _moodle_ws_get("https://moodle.test/ws.php", "token", "core_course_get", [])

    @patch("httpx.AsyncClient")
    async def test_timeout_raises(self, mock_client_cls):
        """Timeout errors are propagated."""
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(httpx.TimeoutException):
            await _moodle_ws_get("https://moodle.test/ws.php", "token", "core_course_get", [])


class TestResolveMoodleUserIdFromEmail:
    """_resolve_moodle_user_id_from_email: email → numeric user ID."""

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle.httpx.Client")
    def test_resolves_email(self, mock_client_cls, mock_getenv):
        """Valid email returns numeric user ID."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 42, "email": "test@example.com"}]
        mock_client.get.return_value = mock_response

        result = _resolve_moodle_user_id_from_email("test@example.com")
        assert result == "42"

    @patch("lamb.completions.tools.moodle.os.getenv")
    def test_missing_config_returns_none(self, mock_getenv):
        """Missing env vars returns None."""
        mock_getenv.return_value = None
        result = _resolve_moodle_user_id_from_email("test@example.com")
        assert result is None

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle.httpx.Client")
    def test_empty_response_returns_none(self, mock_client_cls, mock_getenv):
        """Empty list response returns None."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_client.get.return_value = mock_response

        result = _resolve_moodle_user_id_from_email("test@example.com")
        assert result is None

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle.httpx.Client")
    def test_http_error_logged_returns_none(self, mock_client_cls, mock_getenv):
        """HTTP error is caught and returns None (does not crash)."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        result = _resolve_moodle_user_id_from_email("test@example.com")
        assert result is None


class TestExtractMoodleUserIdFromRequest:
    """_extract_moodle_user_id_from_request: trusted header extraction."""

    @patch("lamb.completions.tools.moodle._resolve_moodle_user_id_from_email")
    def test_extracts_from_email(self, mock_resolve):
        """Email header is resolved to numeric ID."""
        mock_resolve.return_value = "42"
        request = {"__openwebui_headers__": {"x-openwebui-user-email": "student@example.com"}}
        result = _extract_moodle_user_id_from_request(request)
        assert result == "42"
        mock_resolve.assert_called_once_with("student@example.com")

    @patch("lamb.completions.tools.moodle._resolve_moodle_user_id_from_email")
    def test_email_resolve_returns_none_falls_back_to_user_id(self, mock_resolve):
        """When email resolution fails, falls back to numeric user-id header."""
        mock_resolve.return_value = None
        request = {
            "__openwebui_headers__": {
                "x-openwebui-user-email": "student@example.com",
                "x-openwebui-user-id": "99",
            }
        }
        result = _extract_moodle_user_id_from_request(request)
        assert result == "99"

    def test_uses_direct_user_id_if_numeric(self):
        """Numeric user-id header is used directly."""
        request = {"__openwebui_headers__": {"x-openwebui-user-id": "123"}}
        result = _extract_moodle_user_id_from_request(request)
        assert result == "123"

    def test_rejects_non_numeric_user_id(self):
        """Non-numeric user-id header returns None."""
        request = {"__openwebui_headers__": {"x-openwebui-user-id": "username123"}}
        result = _extract_moodle_user_id_from_request(request)
        assert result is None

    def test_returns_none_without_headers(self):
        """No headers at all returns None."""
        assert _extract_moodle_user_id_from_request({}) is None

    def test_returns_none_with_none(self):
        """None input returns None."""
        assert _extract_moodle_user_id_from_request(None) is None

    def test_handles_empty_openwebui_headers(self):
        """Empty __openwebui_headers__ dict returns None."""
        request = {"__openwebui_headers__": {}}
        result = _extract_moodle_user_id_from_request(request)
        assert result is None

    @patch("lamb.completions.tools.moodle._resolve_moodle_user_id_from_email")
    def test_handles_case_insensitive_email_header(self, mock_resolve):
        """X-OpenWebUI-User-Email (capitalized) is also accepted."""
        mock_resolve.return_value = "42"
        request = {"__openwebui_headers__": {"X-OpenWebUI-User-Email": "admin@example.com"}}
        result = _extract_moodle_user_id_from_request(request)
        assert result == "42"
        mock_resolve.assert_called_once_with("admin@example.com")


# ===========================================================================
# Section 2: Tool Specifications
# ===========================================================================


class TestMoodleToolSpec:
    """MOODLE_TOOL_SPEC is a valid OpenAI function-calling spec."""

    def test_is_dict_with_type_function(self):
        assert MOODLE_TOOL_SPEC["type"] == "function"
        assert "function" in MOODLE_TOOL_SPEC

    def test_has_name_and_description(self):
        fn = MOODLE_TOOL_SPEC["function"]
        assert fn["name"] == "get_moodle_courses"
        assert len(fn["description"]) > 0

    def test_has_parameters_with_user_id(self):
        props = MOODLE_TOOL_SPEC["function"]["parameters"]["properties"]
        assert "user_id" in props
        assert props["user_id"]["type"] == "string"


class TestMoodleAssignmentsStatusToolSpec:
    """MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC is a valid OpenAI function-calling spec."""

    def test_is_dict_with_type_function(self):
        assert MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC["type"] == "function"
        assert "function" in MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC

    def test_has_name_and_description(self):
        fn = MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC["function"]
        assert fn["name"] == "get_moodle_assignments_status"
        assert len(fn["description"]) > 0

    def test_has_parameters(self):
        props = MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC["function"]["parameters"]["properties"]
        for key in ("user_id", "days_past", "days_future", "limit"):
            assert key in props, f"Missing parameter: {key}"


# ===========================================================================
# Section 3: Tool Implementations
# ===========================================================================


@pytest.mark.asyncio
class TestGetMoodleCourses:
    """get_moodle_courses: enrolled courses for a Moodle user."""

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_success(self, mock_ws_get, mock_getenv):
        """Returns courses list when Moodle API responds."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.return_value = [
            {"id": 1, "fullname": "Course 1", "shortname": "C1", "categoryname": "Cat A"},
            {"id": 2, "fullname": "Course 2", "shortname": "C2", "categoryname": "Cat B"},
        ]

        result = await get_moodle_courses(user_id="42")
        data = json.loads(result)

        assert data["success"] is True
        assert data["user_id"] == "42"
        assert data["course_count"] == 2
        assert data["courses"][0]["name"] == "Course 1"
        assert data["source"] == "moodle_api"

    @patch("lamb.completions.tools.moodle.os.getenv")
    async def test_missing_config(self, mock_getenv):
        """Missing env vars returns error JSON."""
        mock_getenv.return_value = None

        result = await get_moodle_courses(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "not configured" in data["error"]

    @patch("lamb.completions.tools.moodle.os.getenv")
    async def test_missing_user_id(self, mock_getenv):
        """No user_id and no request returns error."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)

        result = await get_moodle_courses()
        data = json.loads(result)

        assert data["success"] is False
        assert "No Moodle user ID" in data["error"]

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._extract_moodle_user_id_from_request")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_uses_request_header_id(self, mock_ws_get, mock_extract, mock_getenv):
        """user_id from request headers takes precedence over caller-provided value."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_extract.return_value = "99"
        mock_ws_get.return_value = []

        request = {"__openwebui_headers__": {"x-openwebui-user-id": "99"}}
        result = await get_moodle_courses(user_id="1", request=request)
        data = json.loads(result)

        assert data["user_id"] == "99"

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_handles_timeout(self, mock_ws_get, mock_getenv):
        """Timeout returns error JSON."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.side_effect = httpx.TimeoutException("Timeout")

        result = await get_moodle_courses(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "timeout" in data["error"].lower()

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_handles_generic_exception(self, mock_ws_get, mock_getenv):
        """Unexpected exception returns error JSON."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.side_effect = RuntimeError("Something went wrong")

        result = await get_moodle_courses(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "Something went wrong" in data["error"]


@pytest.mark.asyncio
class TestGetMoodleAssignmentsStatus:
    """get_moodle_assignments_status: assignment completion/due/missed status."""

    MOCK_COURSES = [
        {"id": 10, "fullname": "Mathematics", "shortname": "MATH101"},
        {"id": 20, "fullname": "Physics", "shortname": "PHY101"},
    ]

    MOCK_ASSIGNMENTS_PAYLOAD = {
        "courses": [
            {
                "id": 10,
                "assignments": [
                    {
                        "id": 1001,
                        "name": "Homework 1",
                        "duedate": 1_750_000_000,
                        "cutoffdate": 1_750_086_400,
                    },
                    {
                        "id": 1002,
                        "name": "Homework 2 (past due)",
                        "duedate": 1_700_000_000,
                        "cutoffdate": 1_700_086_400,
                    },
                ],
            },
            {
                "id": 20,
                "assignments": [
                    {
                        "id": 2001,
                        "name": "Lab Report",
                        "duedate": 1_750_500_000,
                        "cutoffdate": 0,
                    },
                ],
            },
        ]
    }

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_success(self, mock_ws_get, mock_getenv):
        """Returns structured assignment status JSON."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
            "MOODLE_ASSIGNMENTS_LIMIT": "40",
            "MOODLE_ASSIGNMENTS_CONCURRENCY": "8",
        }.get(k, d)

        # Three sequential calls: courses → assignments → submission statuses
        mock_ws_get.side_effect = [
            self.MOCK_COURSES,
            self.MOCK_ASSIGNMENTS_PAYLOAD,
            {"submissionstatus": "submitted", "graded": True},  # Homewok 1: completed
            {"submissionstatus": "", "graded": False},           # HW 2 past due: missed
            {"submissionstatus": "", "graded": False},           # Lab Report: due
        ]

        result = await get_moodle_assignments_status(user_id="42")
        data = json.loads(result)

        assert data["success"] is True
        assert data["source"] == "moodle_api"
        assert "counts" in data
        assert data["counts"]["completed"] >= 0
        assert data["counts"]["due"] >= 0
        assert data["counts"]["missed"] >= 0

    @patch("lamb.completions.tools.moodle.os.getenv")
    async def test_missing_config(self, mock_getenv):
        """Missing env vars returns error JSON."""
        mock_getenv.return_value = None

        result = await get_moodle_assignments_status(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "not configured" in data["error"]

    @patch("lamb.completions.tools.moodle.os.getenv")
    async def test_missing_user_id(self, mock_getenv):
        """No user_id and no request returns error."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)

        result = await get_moodle_assignments_status()
        data = json.loads(result)

        assert data["success"] is False
        assert "No Moodle user ID" in data["error"]

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_no_enrolled_courses(self, mock_ws_get, mock_getenv):
        """User with no courses returns empty counts."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.return_value = []  # no courses

        result = await get_moodle_assignments_status(user_id="42")
        data = json.loads(result)

        assert data["success"] is True
        assert data["counts"]["completed"] == 0
        assert data["counts"]["due"] == 0
        assert data["counts"]["missed"] == 0
        assert "No enrolled courses" in data.get("note", "")

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_handles_timeout(self, mock_ws_get, mock_getenv):
        """Timeout returns error JSON."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.side_effect = httpx.TimeoutException("Timeout")

        result = await get_moodle_assignments_status(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "timeout" in data["error"].lower()

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_handles_generic_exception(self, mock_ws_get, mock_getenv):
        """Unexpected exception returns error JSON."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_ws_get.side_effect = RuntimeError("Unexpected error")

        result = await get_moodle_assignments_status(user_id="42")
        data = json.loads(result)

        assert data["success"] is False
        assert "Unexpected error" in data["error"]

    @patch("lamb.completions.tools.moodle.os.getenv")
    @patch("lamb.completions.tools.moodle._extract_moodle_user_id_from_request")
    @patch("lamb.completions.tools.moodle._moodle_ws_get")
    async def test_uses_request_header_id(self, mock_ws_get, mock_extract, mock_getenv):
        """user_id from request headers overrides caller-provided value."""
        mock_getenv.side_effect = lambda k, d=None: {
            "MOODLE_API_URL": "https://moodle.test",
            "MOODLE_TOKEN": "tok",
        }.get(k, d)
        mock_extract.return_value = "88"
        mock_ws_get.return_value = []

        request = {"__openwebui_headers__": {"x-openwebui-user-id": "88"}}
        result = await get_moodle_assignments_status(user_id="1", request=request)
        data = json.loads(result)

        assert data["resolved_user_id"] == "88"