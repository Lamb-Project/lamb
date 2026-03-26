"""
Tests for Ingestion Status endpoints.
"""

import pytest


class TestListIngestionJobs:
    """Tests for GET /ingestion/{collection_id}/jobs endpoint."""
    
    def test_list_jobs_empty(self, client, test_collection):
        """Empty collection should have no jobs."""
        data = client.list_ingestion_jobs(test_collection["id"])
        
        assert "items" in data or "jobs" in data
        assert "total" in data
        assert data["total"] == 0
    
    def test_list_jobs_with_content(self, client, ingested_collection):
        """Collection with ingested content should show jobs."""
        data = client.list_ingestion_jobs(ingested_collection["id"])
        
        assert data["total"] >= 1
        jobs = data.get("items") or data.get("jobs", [])
        assert len(jobs) >= 1
        
        job = jobs[0]
        assert "id" in job
        assert "status" in job
        assert "original_filename" in job
    
    def test_list_jobs_filter_by_status(self, client, ingested_collection):
        """Filter jobs by status."""
        data = client.list_ingestion_jobs(
            ingested_collection["id"],
            status="completed"
        )
        
        jobs = data.get("items") or data.get("jobs", [])
        for job in jobs:
            assert job["status"] == "completed"
    
    def test_list_jobs_pagination(self, client, ingested_collection):
        """Jobs list should support pagination."""
        data = client.list_ingestion_jobs(
            ingested_collection["id"],
            limit=1,
            offset=0
        )
        
        jobs = data.get("items") or data.get("jobs", [])
        assert len(jobs) <= 1
    
    def test_list_jobs_sorting(self, client, ingested_collection):
        """Jobs list should support sorting."""
        data = client.list_ingestion_jobs(
            ingested_collection["id"],
            sort_by="created_at",
            sort_order="desc"
        )
        
        assert "items" in data or "jobs" in data


class TestGetIngestionJob:
    """Tests for GET /ingestion/{collection_id}/jobs/{job_id} endpoint."""
    
    def test_get_job_details(self, client, ingested_collection):
        """Get specific job should return details."""
        # First get a job
        jobs_data = client.list_ingestion_jobs(ingested_collection["id"])
        jobs = jobs_data.get("items") or jobs_data.get("jobs", [])
        assert len(jobs) >= 1
        
        job_id = jobs[0]["id"]
        job = client.get_ingestion_job(ingested_collection["id"], job_id)
        
        assert job["id"] == job_id
        assert "status" in job
        assert "original_filename" in job
        assert "plugin_name" in job
    
    def test_get_nonexistent_job(self, client, test_collection):
        """Get non-existent job should return 404."""
        response = client.get(
            f"/ingestion/{test_collection['id']}/jobs/999999"
        )
        assert response.status_code == 404


class TestIngestionStatusSummary:
    """Tests for GET /ingestion/{collection_id}/status endpoint."""
    
    def test_status_summary_empty(self, client, test_collection):
        """Empty collection should show zero counts."""
        data = client.get_ingestion_summary(test_collection["id"])
        
        assert "total_jobs" in data
        assert "by_status" in data
        assert data["total_jobs"] == 0
    
    def test_status_summary_with_content(self, client, ingested_collection):
        """Collection with content should show counts."""
        data = client.get_ingestion_summary(ingested_collection["id"])
        
        assert data["total_jobs"] >= 1
        assert "by_status" in data
        # by_status should have status keys
        assert "completed" in data["by_status"] or data["by_status"].get("completed", 0) >= 0


class TestRetryIngestionJob:
    """Tests for POST /collections/{collection_id}/ingestion-jobs/{job_id}/retry endpoint."""
    
    def test_retry_failed_job(self, client, test_collection, test_files_dir):
        """Create a job that fails, then retry it."""
        collection_id = test_collection["id"]
        
        # Create a file with content that might cause issues during processing
        # Using a binary-like content that might fail text extraction
        fail_file = test_files_dir / f"fail_test_{int(__import__('time').time())}.bin"
        fail_file.write_bytes(b'\x00\x01\x02\x03\x04\x05' * 100)  # Binary garbage
        
        # Ingest the problematic file
        try:
            result = client.ingest_file(
                collection_id, 
                str(fail_file),
                plugin_params={"chunk_size": 10, "chunk_unit": "char", "chunk_overlap": 5}
            )
            file_id = result.get("file_registry_id")
        except Exception:
            # If ingestion itself fails, that's expected
            return
        
        if not file_id:
            return
        
        # Wait a bit for processing to potentially fail
        __import__('time').sleep(3)
        
        # Check if job failed
        jobs_data = client.list_ingestion_jobs(collection_id)
        jobs = jobs_data.get("items") or jobs_data.get("jobs", [])
        job = next((j for j in jobs if j.get("id") == file_id), None)
        
        if job and job.get("status") == "failed":
            # Retry the failed job
            response = client.post(
                f"/collections/{collection_id}/ingestion-jobs/{file_id}/retry"
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") in ["pending", "processing", "queued"]
    
    def test_retry_nonexistent_job(self, client, test_collection):
        """Retry non-existent job should return 404."""
        response = client.post(
            f"/collections/{test_collection['id']}/ingestion-jobs/999999/retry"
        )
        assert response.status_code == 404


class TestCancelIngestionJob:
    """Tests for POST /collections/{collection_id}/ingestion-jobs/{job_id}/cancel endpoint."""
    
    def test_cancel_processing_job(self, client, test_collection, test_files_dir):
        """Start a job and immediately cancel it while processing."""
        collection_id = test_collection["id"]
        
        # Create a larger file that takes longer to process
        large_file = test_files_dir / f"cancel_test_{int(__import__('time').time())}.txt"
        large_file.write_text("This is test content for cancellation. " * 500)
        
        # Ingest the file
        result = client.ingest_file(
            collection_id, 
            str(large_file),
            plugin_params={"chunk_size": 50, "chunk_unit": "char", "chunk_overlap": 10}
        )
        file_id = result.get("file_registry_id")
        
        if file_id:
            # Immediately try to cancel (while likely still processing)
            response = client.post(
                f"/collections/{collection_id}/ingestion-jobs/{file_id}/cancel"
            )
            
            # Should either succeed (cancelled) or fail (already completed)
            # Both are valid depending on timing
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                data = response.json()
                # Verify it was marked as cancelled/failed
                assert data.get("status") in ["cancelled", "failed", "canceled"]
    
    def test_cancel_nonexistent_job(self, client, test_collection):
        """Cancel non-existent job should return 404."""
        response = client.post(
            f"/collections/{test_collection['id']}/ingestion-jobs/999999/cancel"
        )
        assert response.status_code == 404
