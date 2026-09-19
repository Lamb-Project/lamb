"""
Tests for the KB query tool.

When the assistant has no RAG_collections the tool falls back to the legacy
stub; when it does, it queries the real KB server path (mocked here).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lamb.completions.tools.implementations.kb_query import run_kb_query


class TestKbQueryStub:
    """KB query is async — uses pytest-asyncio."""

    @pytest.mark.asyncio
    async def test_valid_query(self):
        """Valid query returns success with results."""
        result = await run_kb_query({"query": "What is Paris?"})
        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) > 0
        assert "content" in result["results"][0]
        assert "Stub result" in result["results"][0]["content"]

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Empty query returns error."""
        result = await run_kb_query({"query": ""})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_missing_query(self):
        """Missing query key returns error."""
        result = await run_kb_query({})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_similarity_included(self):
        """Result includes similarity score."""
        result = await run_kb_query({"query": "test"})
        assert result["results"][0]["similarity"] == 0.95


class TestKbQueryReal:
    """With RAG_collections configured, the tool hits the KB server path."""

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.query_kb_collection", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.kb.config_for_owner")
    async def test_returns_real_results(self, mock_config, mock_query):
        mock_config.return_value = {"url": "http://kb:9090", "token": "tok"}
        mock_query.return_value = {
            "results": [
                {"similarity": 0.81, "data": "chunk text", "metadata": {"p": 1}},
            ],
            "count": 1,
        }
        assistant = SimpleNamespace(
            RAG_collections="kb-1", RAG_Top_k=3, owner="student@lamb-lti.local")

        result = await run_kb_query({"query": "fractions"}, assistant=assistant)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["content"] == "chunk text"
        assert result["results"][0]["similarity"] == 0.81
        mock_query.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.query_kb_collection", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.kb.config_for_owner")
    async def test_multiple_collections_merged(self, mock_config, mock_query):
        mock_config.return_value = {"url": "http://kb:9090", "token": "tok"}
        mock_query.side_effect = [
            {"results": [{"similarity": 0.5, "data": "a", "metadata": {}}]},
            {"results": [{"similarity": 0.4, "data": "b", "metadata": {}}]},
        ]
        assistant = SimpleNamespace(
            RAG_collections="kb-1,kb-2", RAG_Top_k=2, owner="o@x.com")

        result = await run_kb_query({"query": "q"}, assistant=assistant)

        assert result["count"] == 2
        assert mock_query.await_count == 2
