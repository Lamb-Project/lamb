"""Direct tests for the knowledge_store_rag RAG processor (_run).

Covers the multi-KS fan-out, the early-return guards, error handling per
Knowledge Store, and the [N]-numbered context / aligned sources produced via
the shared _ks_query_helpers.build_context_and_sources.
"""

import pytest
from unittest.mock import AsyncMock, patch

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


def _ks_success(chunks):
    return {"status": "success", "data": {"results": chunks}}


@pytest.mark.asyncio
async def test_returns_numbered_context_and_aligned_sources():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [{"role": "user", "content": "What is photosynthesis?"}]
    resp = _ks_success([
        {"text": "Photosynthesis converts light.", "score": 0.9,
         "metadata": {"source_title": "Bio"}},
        {"text": "It happens in chloroplasts.", "score": 0.8,
         "metadata": {"source_title": "Bio"}},
    ])

    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=resp)) as mock_query:
        result = await knowledge_store_rag.rag_processor(messages, assistant)

    mock_query.assert_called_once_with("ks-1", "What is photosynthesis?", 3, "user@test.com")
    # Context chunks are numbered and sources carry the matching n.
    assert result["context"] == (
        "[1] Photosynthesis converts light.\n\n[2] It happens in chloroplasts."
    )
    assert [s["n"] for s in result["sources"]] == [1, 2]


@pytest.mark.asyncio
async def test_uses_last_user_message_as_query():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "the real question"},
    ]
    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=_ks_success([]))) as mock_query:
        await knowledge_store_rag.rag_processor(messages, assistant)
    mock_query.assert_called_once_with("ks-1", "the real question", 3, "user@test.com")


@pytest.mark.asyncio
async def test_multiple_knowledge_stores_queried_and_numbered_continuously():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="ks-1,ks-2")
    messages = [{"role": "user", "content": "q"}]

    async def fake_query(ks_id, *_a, **_k):
        if ks_id == "ks-1":
            return _ks_success([{"text": "from one", "score": 0.9, "metadata": {}}])
        return _ks_success([{"text": "from two", "score": 0.7, "metadata": {}}])

    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock(side_effect=fake_query)) as mock_query:
        result = await knowledge_store_rag.rag_processor(messages, assistant)

    assert mock_query.call_count == 2
    assert {c.args[0] for c in mock_query.call_args_list} == {"ks-1", "ks-2"}
    # Citation numbers are continuous across stores.
    assert result["context"] == "[1] from one\n\n[2] from two"
    assert result["sources"][0]["knowledge_store_id"] == "ks-1"
    assert result["sources"][1]["knowledge_store_id"] == "ks-2"


@pytest.mark.asyncio
async def test_failed_knowledge_store_contributes_nothing():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="ks-1,ks-2")
    messages = [{"role": "user", "content": "q"}]

    async def fake_query(ks_id, *_a, **_k):
        if ks_id == "ks-1":
            return {"status": "error", "error": "boom"}
        return _ks_success([{"text": "good", "score": 0.7, "metadata": {}}])

    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock(side_effect=fake_query)):
        result = await knowledge_store_rag.rag_processor(messages, assistant)

    # Only the successful KS contributes; numbering restarts cleanly at 1.
    assert result["context"] == "[1] good"
    assert len(result["sources"]) == 1
    # The raw responses still record both stores for diagnostics.
    assert set(result["raw_responses"].keys()) == {"ks-1", "ks-2"}


@pytest.mark.asyncio
async def test_no_collections_returns_early():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="")
    messages = [{"role": "user", "content": "hi"}]
    result = await knowledge_store_rag.rag_processor(messages, assistant)
    assert "No Knowledge Stores specified" in result["context"]
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_whitespace_only_collections_returns_early():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="  , ,")
    messages = [{"role": "user", "content": "hi"}]
    result = await knowledge_store_rag.rag_processor(messages, assistant)
    assert "RAG_collections is empty" in result["context"]
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_no_user_message_returns_early():
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [{"role": "assistant", "content": "only assistant"}]
    result = await knowledge_store_rag.rag_processor(messages, assistant)
    assert "No user message found" in result["context"]
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_no_assistant_returns_early():
    from lamb.completions.rag import knowledge_store_rag

    result = await knowledge_store_rag.rag_processor([{"role": "user", "content": "x"}], None)
    assert "No Knowledge Stores specified" in result["context"]
    assert result["sources"] == []
