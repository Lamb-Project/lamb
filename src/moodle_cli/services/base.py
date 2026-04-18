"""Base service class for Moodle Web Services."""

from __future__ import annotations

from typing import Any

from moodle_cli.client.http import MoodleHTTPClient


class BaseService:
    """Base class for Moodle service wrappers."""

    def __init__(self, client: MoodleHTTPClient) -> None:
        self.client = client

    def call(self, wsfunction: str, **params: Any) -> Any:
        return self.client.call(wsfunction, **params)
