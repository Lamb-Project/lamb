import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from lamb.lamb_classes import Assistant


def _make_assistant(**overrides):
    defaults = {
        "id": 1,
        "name": "Test",
        "description": "",
        "system_prompt": "",
        "prompt_template": "",
        "RAG_collections": "ks-1",
        "RAG_Top_k": 3,
        "owner": "user@test.com",
        "api_callback": "",
        "pre_retrieval_endpoint": "",
        "post_retrieval_endpoint": "",
        "RAG_endpoint": "",
    }
    defaults.update(overrides)
    return Assistant(**defaults)


@pytest.mark.asyncio
async def test_fallback_to_last_user_message_when_no_small_fast_model():
    """When small-fast-model is not configured, use last user message as query."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant()
    messages = [
        {"role": "user", "content": "What is photosynthesis?"},
        {"role": "assistant", "content": "It is a process..."},
        {"role": "user", "content": "How does it work in detail?"},
    ]

    mock_ks_response = {
        "status": "success",
        "data": {"results": [{"text": "chunk text", "score": 0.9, "metadata": {"source_title": "Bio"}}]},
    }

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="How does it work in detail?")), \
         patch.object(query_rewriting_ks_rag, "query_one_ks", new=AsyncMock(return_value=mock_ks_response)) as mock_query:
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)

        mock_query.assert_called_once_with("ks-1", "How does it work in detail?", 3, "user@test.com")
        assert "chunk text" in result["context"]
        assert len(result["sources"]) == 1


@pytest.mark.asyncio
async def test_uses_small_fast_model_query_when_configured():
    """When small-fast-model is configured, use its output as the query."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant()
    messages = [
        {"role": "user", "content": "What is ML?"},
        {"role": "assistant", "content": "Machine learning is..."},
        {"role": "user", "content": "How does it differ from DL?"},
    ]

    mock_ks_response = {
        "status": "success",
        "data": {"results": [{"text": "ML vs DL chunk", "score": 0.85, "metadata": {}}]},
    }

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="machine learning vs deep learning comparison")), \
         patch.object(query_rewriting_ks_rag, "query_one_ks", new=AsyncMock(return_value=mock_ks_response)) as mock_query:
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)

        mock_query.assert_called_once_with("ks-1", "machine learning vs deep learning comparison", 3, "user@test.com")
        assert "ML vs DL chunk" in result["context"]


@pytest.mark.asyncio
async def test_no_collections_returns_early():
    """When RAG_collections is empty, return early with info message."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant(RAG_collections="")
    messages = [{"role": "user", "content": "Hello"}]

    result = await query_rewriting_ks_rag.rag_processor(messages, assistant)
    assert "No Knowledge Stores specified" in result["context"]
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_no_user_message_returns_early():
    """When there is no user message, return early."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant()
    messages = [{"role": "assistant", "content": "Hello"}]

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="")):
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)
        assert "No user message found" in result["context"]


@pytest.mark.asyncio
async def test_multiple_ks_queried_concurrently():
    """When multiple KS IDs are specified, all are queried."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant(RAG_collections="ks-1,ks-2")
    messages = [{"role": "user", "content": "Test query"}]

    mock_response = {"status": "success", "data": {"results": []}}

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="Test query")), \
         patch.object(query_rewriting_ks_rag, "query_one_ks", new=AsyncMock(return_value=mock_response)) as mock_query:
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)

        assert mock_query.call_count == 2
        called_ids = {call.args[0] for call in mock_query.call_args_list}
        assert called_ids == {"ks-1", "ks-2"}


@pytest.mark.asyncio
async def test_sfm_error_falls_back_to_last_user_message():
    """When small-fast-model raises an exception, fall back to last user message."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant()
    messages = [
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI is..."},
        {"role": "user", "content": "Give me examples"},
    ]

    mock_ks_response = {"status": "success", "data": {"results": []}}

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="Give me examples")), \
         patch.object(query_rewriting_ks_rag, "query_one_ks", new=AsyncMock(return_value=mock_ks_response)) as mock_query:
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)

        mock_query.assert_called_once_with("ks-1", "Give me examples", 3, "user@test.com")


@pytest.mark.asyncio
async def test_handles_multimodal_content_in_fallback():
    """When user message is multimodal (list), extract text parts."""
    from lamb.completions.rag import query_rewriting_ks_rag

    assistant = _make_assistant()
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Describe this image"},
            {"type": "image_url", "image_url": {"url": "http://example.com/img.png"}},
        ]},
    ]

    mock_ks_response = {"status": "success", "data": {"results": []}}

    with patch.object(query_rewriting_ks_rag, "generate_optimal_query", new=AsyncMock(return_value="Describe this image")), \
         patch.object(query_rewriting_ks_rag, "query_one_ks", new=AsyncMock(return_value=mock_ks_response)) as mock_query:
        result = await query_rewriting_ks_rag.rag_processor(messages, assistant)

        mock_query.assert_called_once_with("ks-1", "Describe this image", 3, "user@test.com")
