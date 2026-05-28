import json
import os
from unittest.mock import patch, MagicMock, mock_open
import pytest

from backend.lamb.completions.rag.single_file_rag import rag_processor


class MockAssistant:
    def __init__(self, metadata_dict, owner="test@example.com"):
        self.id = "mock-assistant-id"
        self.api_callback = json.dumps(metadata_dict)
        self.metadata = self.api_callback
        self.owner = owner


MOCK_LM_URL = "http://localhost:9091"
MOCK_LM_TOKEN = "test-token"
MOCK_ENV = {
    "LAMB_LIBRARY_SERVER": MOCK_LM_URL,
    "LAMB_LIBRARY_TOKEN": MOCK_LM_TOKEN,
}


def _make_messages(user_message="What does the document say?"):
    return [{"role": "user", "content": user_message}]


# --- Library Manager path (new behavior) ---

@patch.dict(os.environ, MOCK_ENV)
@patch("backend.lamb.completions.rag.single_file_rag.httpx.get")
def test_library_item_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "# Document Title\nThis is the content."
    mock_get.return_value = mock_response

    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "# Document Title" in result["context"]
    assert "This is the content." in result["context"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["title"] == "Library Document"
    assert result["sources"][0]["url"] == "/docs/lib-123/item-456"
    assert result["sources"][0]["similarity"] == 1.0
    mock_get.assert_called_once_with(
        f"{MOCK_LM_URL}/libraries/lib-123/items/item-456/content",
        params={"format": "markdown"},
        headers={"Authorization": f"Bearer {MOCK_LM_TOKEN}"},
        timeout=30.0,
    )


@patch.dict(os.environ, MOCK_ENV)
@patch("backend.lamb.completions.rag.single_file_rag.httpx.get")
def test_library_item_connection_error_returns_empty_context(mock_get):
    import httpx
    mock_get.side_effect = httpx.ConnectError("Connection refused")

    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


@patch.dict(os.environ, MOCK_ENV)
@patch("backend.lamb.completions.rag.single_file_rag.httpx.get")
def test_library_item_not_found_returns_empty_context(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"
    mock_get.return_value = mock_response

    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-nonexistent",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


@patch.dict(os.environ, MOCK_ENV)
@patch("backend.lamb.completions.rag.single_file_rag.httpx.get")
def test_library_item_server_error_returns_empty_context(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


@patch.dict(os.environ, {}, clear=True)
def test_library_item_missing_env_vars_returns_empty_context():
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


# --- Backward compatibility: file_path (existing behavior) ---

@patch("backend.lamb.completions.rag.single_file_rag.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="File content here")
def test_file_path_backward_compat_success(mock_file, mock_exists):
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "file_path": "1/notes.md",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "File content here" in result["context"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["title"] == "notes.md"
    assert result["sources"][0]["url"] == "/static/public/1/notes.md"
    assert result["sources"][0]["similarity"] == 1.0


@patch("backend.lamb.completions.rag.single_file_rag.os.path.exists", return_value=False)
def test_file_path_not_found_returns_error_in_context(mock_exists):
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "file_path": "1/missing.md",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "Error" in result["context"] or "not found" in result["context"].lower()
    assert result["sources"] == []


# --- Error cases ---

def test_no_file_path_no_library_id_returns_empty_context():
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


def test_library_id_without_item_id_returns_empty_context():
    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


def test_invalid_metadata_json_returns_empty_context():
    assistant = MockAssistant.__new__(MockAssistant)
    assistant.id = "mock-assistant-id"
    assistant.api_callback = "not valid json"
    assistant.metadata = "not valid json"
    assistant.owner = "test@example.com"

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert result["context"] == ""
    assert result["sources"] == []


# --- Priority: library_id+item_id takes precedence over file_path ---

@patch.dict(os.environ, MOCK_ENV)
@patch("backend.lamb.completions.rag.single_file_rag.httpx.get")
def test_library_id_takes_precedence_over_file_path(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "LM content"
    mock_get.return_value = mock_response

    assistant = MockAssistant({
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
        "file_path": "1/old_file.md",
    })

    result = rag_processor(messages=_make_messages(), assistant=assistant)

    assert "LM content" in result["context"]
    assert result["sources"][0]["title"] == "Library Document"
    assert result["sources"][0]["url"] == "/docs/lib-123/item-456"
    mock_get.assert_called_once()
