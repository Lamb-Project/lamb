"""
Tests for Query endpoints.
"""

import pytest


class TestQueryCollection:
    """Tests for POST /collections/{id}/query endpoint."""
    
    def test_query_returns_results(self, client, ingested_collection):
        """Query should return matching results."""
        collection_id = ingested_collection["id"]
        
        result = client.query_collection(
            collection_id,
            "What is machine learning?",
            top_k=5,
            threshold=0.0
        )
        
        assert "results" in result
        assert "count" in result
        assert "timing" in result
        assert result["count"] >= 0
    
    def test_query_with_threshold(self, client, ingested_collection):
        """Query with threshold should filter low similarity results."""
        collection_id = ingested_collection["id"]
        
        result = client.query_collection(
            collection_id,
            "artificial intelligence neural networks",
            threshold=0.5
        )
        
        # All results should have similarity above threshold
        for r in result["results"]:
            assert r["similarity"] >= 0.5
    
    def test_query_with_top_k(self, client, ingested_collection):
        """Query with top_k should limit results."""
        collection_id = ingested_collection["id"]
        
        result = client.query_collection(
            collection_id,
            "machine learning",
            top_k=2
        )
        
        assert len(result["results"]) <= 2
    
    def test_query_empty_collection(self, client, test_collection):
        """Query empty collection should return no results."""
        result = client.query_collection(
            test_collection["id"],
            "any query text"
        )
        
        assert result["count"] == 0
        assert result["results"] == []
    
    def test_query_nonexistent_collection(self, client):
        """Query non-existent collection should return 404."""
        response = client.post(
            "/collections/999999/query",
            params={"plugin_name": "simple_query"},
            json={"query_text": "test", "top_k": 5}
        )
        
        assert response.status_code == 404
    
    def test_query_timing_info(self, client, ingested_collection):
        """Query should include timing information."""
        result = client.query_collection(
            ingested_collection["id"],
            "natural language processing"
        )
        
        assert "timing" in result
        assert "total_ms" in result["timing"]
        assert result["timing"]["total_ms"] >= 0


class TestQueryPlugins:
    """Tests for query plugin functionality."""
    
    def test_simple_query_plugin(self, client, ingested_collection):
        """Simple query plugin should work."""
        result = client.query_collection(
            ingested_collection["id"],
            "test query",
            plugin_name="simple_query"
        )
        
        assert "results" in result
    
    def test_invalid_plugin_returns_error(self, client, ingested_collection):
        """Invalid query plugin should return error."""
        response = client.post(
            f"/collections/{ingested_collection['id']}/query",
            params={"plugin_name": "nonexistent_plugin"},
            json={"query_text": "test", "top_k": 5}
        )
        
        assert response.status_code in [400, 404]
