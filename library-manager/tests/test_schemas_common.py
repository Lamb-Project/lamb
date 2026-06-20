"""Unit tests for ``schemas.common`` (shared pagination/message models)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.common import MessageResponse, PaginationParams


def test_pagination_defaults():
    p = PaginationParams()
    assert p.limit == 20
    assert p.offset == 0


def test_pagination_bounds():
    assert PaginationParams(limit=100, offset=5).limit == 100
    with pytest.raises(ValidationError):
        PaginationParams(limit=0)
    with pytest.raises(ValidationError):
        PaginationParams(limit=101)
    with pytest.raises(ValidationError):
        PaginationParams(offset=-1)


def test_message_response():
    assert MessageResponse(message="ok").message == "ok"
    with pytest.raises(ValidationError):
        MessageResponse()
