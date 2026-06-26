"""Direct unit tests for ``knowledge_store_rag._run()``.

The ``knowledge_store_rag`` processor is the primary retrieval entry point for
Knowledge Store assistants, but until now only its helpers
(``_ks_query_helpers`` / ``query_rewriting_ks_rag``) were covered. This module
exercises ``_run()`` itself: the early-return guards, the multi-KS fan-out, the
per-store error handling, and the context/source assembly.

Pattern (mirrors ``test_query_rewriting_ks_rag.py``): build a real ``Assistant``,
patch the module-level ``query_one_ks`` with an ``AsyncMock`` so no network or
DB is touched, and assert on the structured dict ``_run`` returns. The real
``serialize_assistant`` and ``_extract_sources`` helpers are left unpatched so
their integration with ``_run`` is covered too.
"""

import pytest
from unittest.mock import patch, AsyncMock
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


def _ks_success(*texts, metadata=None):
    """Build a successful KB Server response carrying one chunk per text."""
    results = [
        {"text": t, "score": 0.9, "metadata": (metadata or {})} for t in texts
    ]
    return {"status": "success", "data": {"results": results}}


def _ks_error(message="boom"):
    return {"status": "error", "error": message}


# =============================================================================
# Guard branches (early returns)
# =============================================================================

@pytest.mark.asyncio
async def test_no_assistant_returns_early():
    """A missing assistant short-circuits before any KS is queried."""
    from lamb.completions.rag import knowledge_store_rag

    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock()) as mock_query:
        result = await knowledge_store_rag._run([{"role": "user", "content": "hi"}], None, None)

    assert "No Knowledge Stores specified" in result["context"]
    assert result["sources"] == []
    assert result["assistant_data"] == {}
    mock_query.assert_not_called()


@pytest.mark.asyncio
async def test_no_collections_returns_early():
    """An assistant with no RAG_collections returns the info message, no query."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="")
    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock()) as mock_query:
        result = await knowledge_store_rag._run([{"role": "user", "content": "hi"}], assistant, None)

    assert "No Knowledge Stores specified" in result["context"]
    assert result["sources"] == []
    mock_query.assert_not_called()


@pytest.mark.asyncio
async def test_no_user_message_returns_early():
    """With no user-role message there is nothing to query on."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [{"role": "assistant", "content": "previous answer"}]
    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock()) as mock_query:
        result = await knowledge_store_rag._run(messages, assistant, None)

    assert "No user message found" in result["context"]
    assert result["sources"] == []
    mock_query.assert_not_called()


@pytest.mark.asyncio
async def test_blank_collections_returns_early():
    """RAG_collections made only of separators/whitespace parses to no IDs."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="  , ,  ")
    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock()) as mock_query:
        result = await knowledge_store_rag._run([{"role": "user", "content": "hi"}], assistant, None)

    assert "RAG_collections is empty or improperly formatted" in result["context"]
    assert result["sources"] == []
    mock_query.assert_not_called()


# =============================================================================
# Success path & query construction
# =============================================================================

@pytest.mark.asyncio
async def test_success_single_ks_builds_context_and_sources():
    """A single successful KS yields its chunk text as context and a source."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [{"role": "user", "content": "What is photosynthesis?"}]
    response = _ks_success(
        "Photosynthesis converts light to energy.",
        metadata={
            "source_title": "Biology 101",
            "permalink_page": "/docs/bio/1",
            "library_id": "lib-9",
            "source_item_id": "item-3",
        },
    )

    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=response)) as mock_query:
        result = await knowledge_store_rag._run(messages, assistant, None)

    mock_query.assert_called_once_with("ks-1", "What is photosynthesis?", 3, "user@test.com")
    assert "Photosynthesis converts light to energy." in result["context"]
    assert len(result["sources"]) == 1
    source = result["sources"][0]
    assert source["knowledge_store_id"] == "ks-1"
    assert source["title"] == "Biology 101"
    assert source["url"] == "/docs/bio/1"
    assert result["raw_responses"]["ks-1"]["status"] == "success"
    assert result["assistant_data"]["id"] == 1


@pytest.mark.asyncio
async def test_uses_last_user_message_and_forwards_top_k_and_owner():
    """The query is the last user turn; top_k and owner are forwarded verbatim."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_Top_k=7, owner="prof@uni.edu")
    messages = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "an answer"},
        {"role": "user", "content": "the real question"},
    ]

    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=_ks_success())) as mock_query:
        await knowledge_store_rag._run(messages, assistant, None)

    mock_query.assert_called_once_with("ks-1", "the real question", 7, "prof@uni.edu")


# =============================================================================
# Multi-KS fan-out
# =============================================================================

@pytest.mark.asyncio
async def test_multi_ks_fanout_combines_context_and_sources():
    """Every configured KS is queried; contexts and sources are aggregated."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="ks-1, ks-2")
    messages = [{"role": "user", "content": "q"}]

    async def fake_query(ks_id, query_text, top_k, owner):
        return _ks_success(f"chunk from {ks_id}", metadata={"source_title": ks_id})

    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock(side_effect=fake_query)) as mock_query:
        result = await knowledge_store_rag._run(messages, assistant, None)

    assert mock_query.call_count == 2
    queried_ids = {call.args[0] for call in mock_query.call_args_list}
    assert queried_ids == {"ks-1", "ks-2"}
    # Both chunks are present, joined into a single combined context.
    assert "chunk from ks-1" in result["context"]
    assert "chunk from ks-2" in result["context"]
    assert "\n\n" in result["context"]
    assert len(result["sources"]) == 2
    assert set(result["raw_responses"].keys()) == {"ks-1", "ks-2"}


# =============================================================================
# Per-store error handling
# =============================================================================

@pytest.mark.asyncio
async def test_failed_store_does_not_sink_successful_one():
    """One KS erroring is logged and skipped; the healthy KS still contributes."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="ks-good, ks-bad")
    messages = [{"role": "user", "content": "q"}]

    async def fake_query(ks_id, query_text, top_k, owner):
        if ks_id == "ks-bad":
            return _ks_error("connection refused")
        return _ks_success("good chunk", metadata={"source_title": "Good"})

    with patch.object(knowledge_store_rag, "query_one_ks", new=AsyncMock(side_effect=fake_query)):
        result = await knowledge_store_rag._run(messages, assistant, None)

    assert "good chunk" in result["context"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["knowledge_store_id"] == "ks-good"
    assert result["raw_responses"]["ks-bad"]["status"] == "error"
    assert result["raw_responses"]["ks-good"]["status"] == "success"


@pytest.mark.asyncio
async def test_all_stores_failing_yields_empty_context():
    """If every KS errors, context is empty and no sources are produced."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant(RAG_collections="ks-1, ks-2")
    messages = [{"role": "user", "content": "q"}]

    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=_ks_error())):
        result = await knowledge_store_rag._run(messages, assistant, None)

    assert result["context"] == ""
    assert result["sources"] == []
    assert all(r["status"] == "error" for r in result["raw_responses"].values())


# =============================================================================
# Context / source assembly edge cases
# =============================================================================

@pytest.mark.asyncio
async def test_empty_text_chunk_is_sourced_but_omitted_from_context():
    """A chunk with empty text still yields a source but adds nothing to context."""
    from lamb.completions.rag import knowledge_store_rag

    assistant = _make_assistant()
    messages = [{"role": "user", "content": "q"}]
    response = {
        "status": "success",
        "data": {"results": [
            {"text": "", "score": 0.5, "metadata": {"source_title": "Empty"}},
            {"text": "real text", "score": 0.8, "metadata": {"source_title": "Real"}},
        ]},
    }

    with patch.object(knowledge_store_rag, "query_one_ks",
                      new=AsyncMock(return_value=response)):
        result = await knowledge_store_rag._run(messages, assistant, None)

    # Only the non-empty chunk contributes to the context...
    assert result["context"] == "real text"
    # ...but both chunks are surfaced as sources.
    assert len(result["sources"]) == 2
