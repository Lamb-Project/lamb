"""Tests for LambDatabaseManager.assistant_has_rubric_for_eval helper."""

import json
import pytest
from lamb.database_manager import LambDatabaseManager


@pytest.mark.parametrize(
    "api_callback,expected",
    [
        # Fully valid: rubric_id + rubric_rag
        (
            json.dumps({"rubric_id": "abc-123", "rag_processor": "rubric_rag", "connector": "openai"}),
            True,
        ),
        # rubric_id present but wrong rag_processor
        (
            json.dumps({"rubric_id": "abc-123", "rag_processor": "simple_rag"}),
            False,
        ),
        # rag_processor correct but rubric_id empty string
        (
            json.dumps({"rubric_id": "", "rag_processor": "rubric_rag"}),
            False,
        ),
        # rag_processor correct but no rubric_id key
        (
            json.dumps({"rag_processor": "rubric_rag"}),
            False,
        ),
        # No rag_processor at all
        (
            json.dumps({"rubric_id": "abc-123"}),
            False,
        ),
        # None input
        (None, False),
        # Empty string
        ("", False),
        # Invalid JSON
        ("not-json", False),
        # Whitespace-only rubric_id
        (
            json.dumps({"rubric_id": "   ", "rag_processor": "rubric_rag"}),
            False,
        ),
        # Numeric rubric_id (edge case: should still pass if truthy and stripped)
        (
            json.dumps({"rubric_id": 42, "rag_processor": "rubric_rag"}),
            True,
        ),
    ],
    ids=[
        "valid_rubric_rag",
        "wrong_rag_processor",
        "empty_rubric_id",
        "no_rubric_id_key",
        "no_rag_processor",
        "none_input",
        "empty_string",
        "invalid_json",
        "whitespace_rubric_id",
        "numeric_rubric_id",
    ],
)
def test_assistant_has_rubric_for_eval(api_callback, expected):
    assert LambDatabaseManager.assistant_has_rubric_for_eval(api_callback) is expected
