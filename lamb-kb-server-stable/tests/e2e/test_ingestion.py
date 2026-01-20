"""
Live tests for file ingestion against real running server.

Run with: pytest tests/live/test_ingestion.py -v --live-server=http://localhost:9090
"""

import pytest
import time
import json


pytestmark = pytest.mark.live


class TestIngestionPlugins:
    """Live tests for ingestion plugins endpoint."""
    
    def test_list_ingestion_plugins(self, live_client):
        """Should list real available plugins."""
        response = live_client.get("/ingestion/plugins")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Should have at least simple_ingest plugin
        plugin_names = [p["name"] for p in data]
        assert "simple_ingest" in plugin_names


class TestFileIngest:
    """Live tests for file ingestion."""
    
    def test_ingest_file_success(self, live_client, test_text_file, cleanup_collection, sample_collection_data):
        """Ingesting a file on live server should work."""
        # Create collection
        unique_name = f"ingest-test-{int(time.time() * 1000)}"
        collection_data = sample_collection_data.copy()
        collection_data["name"] = unique_name
        collection_data["description"] = "Ingestion test"
        create_response = live_client.post("/collections", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        # Ingest file
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            data = {
                "plugin_name": "simple_ingest",
                "plugin_params": json.dumps({
                    "chunk_size": 500,
                    "chunk_unit": "char",
                    "chunk_overlap": 50
                })
            }
            
            # Remove Content-Type from headers for multipart
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert "documents_added" in result or "file_id" in result
    
    def test_ingest_file_collection_not_found(self, live_client, test_text_file):
        """Ingesting to non-existent collection should return 404."""
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            data = {
                "plugin_name": "simple_ingest",
                "plugin_params": "{}"
            }
            
            response = live_client.post(
                "/collections/999999/ingest-file",
                files=files,
                data=data
            )
        
        assert response.status_code == 404
    
    def test_ingest_file_invalid_plugin(self, live_client, test_text_file, cleanup_collection, sample_collection_data):
        """Ingesting with invalid plugin should return error."""
        # Create collection
        unique_name = f"invalid-plugin-test-{int(time.time() * 1000)}"
        collection_data = sample_collection_data.copy()
        collection_data["name"] = unique_name
        collection_data["description"] = "Invalid plugin test"
        create_response = live_client.post("/collections", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            data = {
                "plugin_name": "nonexistent_plugin",
                "plugin_params": "{}"
            }
            
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=data
            )
        
        assert response.status_code in [400, 404]


class TestAddDocuments:
    """Live tests for adding documents directly."""
    
    def test_add_documents_success(self, live_client, sample_documents, cleanup_collection, sample_collection_data):
        """Adding documents should work on live server."""
        # Create collection
        unique_name = f"add-docs-test-{int(time.time() * 1000)}"
        collection_data = sample_collection_data.copy()
        collection_data["name"] = unique_name
        collection_data["description"] = "Add docs test"
        create_response = live_client.post("/collections", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        # Add documents
        response = live_client.post(
            f"/collections/{collection_id}/documents",
            json=sample_documents
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["documents_added"] == len(sample_documents["documents"])
    
    def test_add_documents_collection_not_found(self, live_client, sample_documents):
        """Adding documents to non-existent collection should return 404."""
        response = live_client.post(
            "/collections/999999/documents",
            json=sample_documents
        )
        
        assert response.status_code == 404
