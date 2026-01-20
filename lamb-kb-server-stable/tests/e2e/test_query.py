"""
Live tests for query functionality against real running server.

Run with: pytest tests/live/test_query.py -v --live-server=http://localhost:9090
"""

import pytest
import time


pytestmark = pytest.mark.live


class TestQueryCollection:
    """Live tests for querying collections."""
    
    def _create_collection_with_documents(self, live_client, cleanup_collection, sample_collection_data):
        """Helper to create a collection with sample documents."""
        unique_name = f"query-test-{int(time.time() * 1000)}"
        collection_data = sample_collection_data.copy()
        collection_data["name"] = unique_name
        collection_data["description"] = "Query test collection"
        
        create_response = live_client.post("/collections", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        # Add documents
        documents = {
            "documents": [
                {
                    "text": "Machine learning is a subset of artificial intelligence.",
                    "metadata": {"source": "ml.txt", "chunk_index": 0}
                },
                {
                    "text": "Python is widely used for data science and machine learning.",
                    "metadata": {"source": "python.txt", "chunk_index": 0}
                },
                {
                    "text": "Deep learning uses neural networks with many layers.",
                    "metadata": {"source": "dl.txt", "chunk_index": 0}
                }
            ]
        }
        add_response = live_client.post(f"/collections/{collection_id}/documents", json=documents)
        assert add_response.status_code == 200
        
        return collection_id
    
    def test_query_collection_success(self, live_client, cleanup_collection, sample_collection_data):
        """Querying a collection should return real results."""
        collection_id = self._create_collection_with_documents(live_client, cleanup_collection, sample_collection_data)
        
        query_data = {
            "query_text": "What is machine learning?",
            "top_k": 3,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post(f"/collections/{collection_id}/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        # Should find relevant results about machine learning
        assert len(data["results"]) > 0
    
    def test_query_with_top_k(self, live_client, cleanup_collection, sample_collection_data):
        """Query should respect top_k limit."""
        collection_id = self._create_collection_with_documents(live_client, cleanup_collection, sample_collection_data)
        
        query_data = {
            "query_text": "machine learning",
            "top_k": 1,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post(f"/collections/{collection_id}/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 1
    
    def test_query_empty_collection(self, live_client, cleanup_collection, sample_collection_data):
        """Querying empty collection should return empty results."""
        # Create empty collection
        unique_name = f"empty-query-{int(time.time() * 1000)}"
        collection_data = sample_collection_data.copy()
        collection_data["name"] = unique_name
        collection_data["description"] = "Empty collection"
        create_response = live_client.post("/collections", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        query_data = {
            "query_text": "test query",
            "top_k": 5,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post(f"/collections/{collection_id}/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
    
    def test_query_collection_not_found(self, live_client):
        """Querying non-existent collection should return 404."""
        query_data = {
            "query_text": "test",
            "top_k": 5,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post("/collections/999999/query", json=query_data)
        assert response.status_code == 404
    
    def test_query_invalid_plugin(self, live_client, cleanup_collection, sample_collection_data):
        """Querying with invalid plugin should return 404."""
        collection_id = self._create_collection_with_documents(live_client, cleanup_collection, sample_collection_data)
        
        query_data = {
            "query_text": "test",
            "top_k": 5,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post(
            f"/collections/{collection_id}/query?plugin_name=nonexistent_plugin",
            json=query_data
        )
        
        assert response.status_code == 404
    
    def test_query_result_structure(self, live_client, cleanup_collection, sample_collection_data):
        """Query results should have expected structure."""
        collection_id = self._create_collection_with_documents(live_client, cleanup_collection, sample_collection_data)
        
        query_data = {
            "query_text": "machine learning",
            "top_k": 5,
            "threshold": 0.0,
            "plugin_params": {}
        }
        
        response = live_client.post(f"/collections/{collection_id}/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["results"]:
            result = data["results"][0]
            # Check expected fields exist
            assert "data" in result or "text" in result
            assert "similarity" in result or "distance" in result
            assert "metadata" in result
