import json
from backend.creator_interface.metadata_validators import validate_update_plugin_metadata


def _make_body(metadata_dict):
    return {"metadata": json.dumps(metadata_dict)}


# --- single_file_rag validation ---

def test_single_file_rag_with_library_id_and_item_id_valid():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
        "item_id": "item-456",
    })
    result, error = validate_update_plugin_metadata(body)
    assert error is None
    assert result is not None
    parsed = json.loads(result)
    assert parsed["library_id"] == "lib-123"
    assert parsed["item_id"] == "item-456"


def test_single_file_rag_with_file_path_valid():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "single_file_rag",
        "file_path": "1/notes.md",
    })
    result, error = validate_update_plugin_metadata(body)
    assert error is None
    assert result is not None


def test_single_file_rag_missing_all_references_returns_error():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "single_file_rag",
    })
    result, error = validate_update_plugin_metadata(body)
    assert result is None
    assert error is not None
    assert "single_file_rag" in error.lower() or "file" in error.lower()


def test_single_file_rag_library_id_without_item_id_returns_error():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "single_file_rag",
        "library_id": "lib-123",
    })
    result, error = validate_update_plugin_metadata(body)
    assert result is None
    assert error is not None


def test_single_file_rag_empty_library_id_returns_error():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "single_file_rag",
        "library_id": "",
        "item_id": "item-456",
    })
    result, error = validate_update_plugin_metadata(body)
    assert result is None
    assert error is not None


# --- Non single_file_rag should not be affected ---

def test_no_rag_not_affected():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "no_rag",
    })
    result, error = validate_update_plugin_metadata(body)
    assert error is None
    assert result is not None


def test_simple_rag_not_affected():
    body = _make_body({
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "rag_processor": "simple_rag",
    })
    result, error = validate_update_plugin_metadata(body)
    assert error is None
    assert result is not None
