"""
Live tests for ingestion status endpoints.
"""

import pytest
import time
import json


pytestmark = pytest.mark.live


class TestIngestionStatus:
    """Live tests for ingestion status and jobs."""
    
    def _create_collection_and_ingest(self, live_client, sample_collection_data, test_text_file):
        """Helper to create collection and start ingestion."""
        unique_name = f"status-test-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        data["description"] = "Status test collection"
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            plugin_data = {
                "plugin_name": "simple_ingest",
                "plugin_params": json.dumps({"chunk_size": 200})
            }
            
            ingest_response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
            
        assert ingest_response.status_code == 200
        return collection_id, ingest_response.json()

    def test_get_ingestion_job_details(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should retrieve detailed status of a specific job."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        
        job_id = ingest_result["file_registry_id"]
        
        response = live_client.get(f"/collections/{collection_id}/ingestion-jobs/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["collection_id"] == collection_id
        assert "status" in data
        assert "file_path" in data
        assert "created_at" in data

    def test_list_ingestion_jobs(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should list ingestion jobs with pagination."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        
        response = live_client.get(f"/collections/{collection_id}/ingestion-jobs")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["id"] == ingest_result["file_registry_id"]

    def test_list_ingestion_jobs_filter_status(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should filter jobs by status."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        
        # Filter by 'deleted' (should be empty)
        response = live_client.get(f"/collections/{collection_id}/ingestion-jobs?status=deleted")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_get_ingestion_status_summary(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should return summary statistics."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        
        response = live_client.get(f"/collections/{collection_id}/ingestion-status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["collection_id"] == collection_id
        assert "by_status" in data
        assert "recent_failures" in data
        
        summary = data["by_status"]
        total = (
            summary.get("pending", 0) + 
            summary.get("processing", 0) + 
            summary.get("completed", 0) + 
            summary.get("failed", 0)
        )
        assert total >= 1

    def test_get_job_not_found(self, live_client, sample_collection_data, cleanup_collection):
        """Should return 404 for non-existent job."""
        unique_name = f"notfound-test-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        create_response = live_client.post("/collections", json=data)
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.get(f"/collections/{collection_id}/ingestion-jobs/999999")
        assert response.status_code == 404

    def test_cancel_processing_job(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should be able to cancel a processing job."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        job_id = ingest_result["file_registry_id"]
        
        # Try to cancel (may already be completed, which is fine)
        response = live_client.post(f"/collections/{collection_id}/ingestion-jobs/{job_id}/cancel")
        
        # 200 if cancelled, 400 if already completed
        assert response.status_code in [200, 400]
    
    def test_cancel_job_not_found(self, live_client, sample_collection_data, cleanup_collection):
        """Should return 404 for canceling non-existent job."""
        unique_name = f"cancel-notfound-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        create_response = live_client.post("/collections", json=data)
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.post(f"/collections/{collection_id}/ingestion-jobs/999999/cancel")
        assert response.status_code == 404

    def test_retry_failed_job(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        """Should be able to retry a job (will fail if job isn't in failed state)."""
        collection_id, ingest_result = self._create_collection_and_ingest(
            live_client, sample_collection_data, test_text_file
        )
        cleanup_collection(collection_id)
        job_id = ingest_result["file_registry_id"]
        
        time.sleep(2)
        
        # Try to retry (likely will fail since job completed successfully)
        response = live_client.post(f"/collections/{collection_id}/ingestion-jobs/{job_id}/retry")
        
        # 200 if retried, 400 if not in failed state
        assert response.status_code in [200, 400]
    
    def test_retry_job_not_found(self, live_client, sample_collection_data, cleanup_collection):
        """Should return 404 for retrying non-existent job."""
        unique_name = f"retry-notfound-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        create_response = live_client.post("/collections", json=data)
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.post(f"/collections/{collection_id}/ingestion-jobs/999999/retry")
        assert response.status_code == 404

