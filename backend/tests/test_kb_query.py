"""
Tests for the KB query tool stub.
"""

import pytest
from lamb.completions.tools.implementations.kb_query import run_kb_query


class TestKbQuery:
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