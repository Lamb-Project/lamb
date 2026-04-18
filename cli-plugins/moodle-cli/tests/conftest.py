"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import respx
from click.testing import CliRunner
from httpx import Response

from moodle_cli.client.http import MoodleHTTPClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "responses"

BASE_URL = "https://moodle.example.com"
TOKEN = "test-token-abc123"


def load_fixture(name: str) -> Any:
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


@pytest.fixture
def client() -> MoodleHTTPClient:
    return MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_api() -> respx.MockRouter:
    """Activate respx mock for the Moodle REST API."""
    with respx.mock(assert_all_called=False) as router:
        yield router


def mock_ws_response(router: respx.MockRouter, data: Any) -> None:
    """Helper to mock a POST to the Moodle REST endpoint."""
    router.post(f"{BASE_URL}/webservice/rest/server.php").mock(
        return_value=Response(200, json=data)
    )
