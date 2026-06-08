import json
import os
from unittest.mock import patch, mock_open
import pytest

from backend.lamb.completions.rag.single_file_rag import rag_processor


class MockAssistant:
    def __init__(self, metadata_dict, owner="test@example.com"):
        self.id = "mock-assistant-id"
        self.api_callback = json.dumps(metadata_dict)
        self.metadata = self.api_callback
        self.owner = owner


def _make_messages(user_message="What does the document say?"):
    return [{"role": "user", "content": user_message}]


@patch("backend.lamb.completions.rag.single_file_rag.os.path.exists", return_value=True)
@patch("backend.lamb.completions.rag.single_file_rag.os.stat")
@patch("builtins.open", new_callable=mock_open, read_data="File content here")
def test_file_path_success(mock_file, mock_stat, mock_exists):
    mock_stat.return_value.st_size = 100
    mock_stat.return_value.st_mtime = 0
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "file_path": "1/notes.md",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "File content here" in result["context"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["source"] == "1/notes.md"
    assert result["sources"][0]["score"] == 1.0


@patch("backend.lamb.completions.rag.single_file_rag.os.path.exists", return_value=False)
def test_file_path_not_found(mock_exists):
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "file_path": "1/missing.md",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "not found" in result["context"].lower() or "Error" in result["context"]
    assert result["sources"] == []


def test_no_file_path_returns_empty_context():
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


def test_no_assistant_returns_empty_context():
    result = rag_processor(messages=_make_messages(), assistant=None)

    assert result["context"] == ""
    assert result["sources"] == []


def test_invalid_metadata_json():
    assistant = MockAssistant.__new__(MockAssistant)
    assistant.id = "mock-assistant-id"
    assistant.api_callback = "not valid json"
    assistant.metadata = "not valid json"
    assistant.owner = "test@example.com"

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "Error" in result["context"] or result["context"] == ""
    assert result["sources"] == []


def test_path_traversal_blocked():
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "file_path": "../../etc/passwd",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "Error" in result["context"] or "Invalid" in result["context"]
    assert result["sources"] == []
