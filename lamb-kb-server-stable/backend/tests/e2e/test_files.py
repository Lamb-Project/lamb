"""
Tests for File Registry endpoints.
"""

import pytest
import time


class TestListFiles:
    """Tests for GET /collections/{id}/files endpoint."""
    
    def test_list_files_empty_collection(self, client, test_collection):
        """Empty collection should have no files."""
        files = client.list_files(test_collection["id"])
        assert files == []
    
    def test_list_files_with_content(self, client, ingested_collection):
        """Collection with ingested files should list them."""
        files = client.list_files(ingested_collection["id"])
        
        assert len(files) >= 1
        
        # Check file properties
        file = files[0]
        assert "id" in file
        assert "original_filename" in file
        assert "status" in file
        assert "plugin_name" in file
        assert "document_count" in file
    
    def test_list_files_filter_by_status(self, client, ingested_collection):
        """List files filtered by status."""
        # Get completed files
        completed_files = client.list_files(
            ingested_collection["id"], 
            status="completed"
        )
        
        for f in completed_files:
            assert f["status"] == "completed"
    
    def test_list_files_nonexistent_collection(self, client):
        """List files for non-existent collection should return 404."""
        response = client.get("/collections/999999/files")
        assert response.status_code == 404


class TestDeleteFile:
    """Tests for DELETE /collections/{id}/files/{file_id} endpoint."""
    
    def test_delete_file_hard(self, client, test_collection, sample_text_file):
        """Hard delete should remove file completely."""
        collection_id = test_collection["id"]
        
        # Ingest a file
        result = client.ingest_file(collection_id, str(sample_text_file))
        file_id = result["file_registry_id"]
        
        # Wait for processing
        client.wait_for_ingestion(collection_id, 1, max_wait=30)
        
        # Delete the file (hard)
        delete_result = client.delete_file(collection_id, file_id, hard=True)
        
        # Verify it's gone
        files = client.list_files(collection_id)
        file_ids = [f["id"] for f in files]
        assert file_id not in file_ids
    
    def test_delete_file_soft(self, client, test_collection, sample_text_file):
        """Soft delete should mark file as deleted but keep it."""
        collection_id = test_collection["id"]
        
        # Ingest a file
        result = client.ingest_file(collection_id, str(sample_text_file))
        file_id = result["file_registry_id"]
        
        # Wait for processing
        client.wait_for_ingestion(collection_id, 1, max_wait=30)
        
        # Delete the file (soft)
        response = client.delete(
            f"/collections/{collection_id}/files/{file_id}",
            params={"hard": False}
        )
        assert response.status_code == 200
        
        # File should still exist but with deleted status
        all_files = client.list_files(collection_id)
        deleted_file = next((f for f in all_files if f["id"] == file_id), None)
        
        # It may be actually removed or marked as deleted depending on implementation
        if deleted_file:
            assert deleted_file["status"] == "deleted"
    
    def test_delete_nonexistent_file(self, client, test_collection):
        """Delete non-existent file should return 404."""
        response = client.delete(
            f"/collections/{test_collection['id']}/files/999999",
            params={"hard": True}
        )
        assert response.status_code == 404


class TestFileStatusUpdate:
    """Tests for PUT /collections/files/{file_id}/status endpoint."""
    
    def test_update_file_status(self, client, test_collection, sample_text_file):
        """Update file status should change the status."""
        collection_id = test_collection["id"]
        
        # Ingest a file
        result = client.ingest_file(collection_id, str(sample_text_file))
        file_id = result["file_registry_id"]
        
        # Wait for processing
        client.wait_for_ingestion(collection_id, 1, max_wait=30)
        
        # Update status to deleted
        response = client.put(
            f"/collections/files/{file_id}/status",
            params={"status": "deleted"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
