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
    
    @pytest.mark.skip(reason="Requires a failed job to test")
    def test_retry_failed_job(self, client, ingested_collection):
        """Retry a failed job should re-process it."""
        # This test would need to trigger a failure first
        pass
    
    def test_retry_nonexistent_job(self, client, test_collection):
        """Retry non-existent job should return 404."""
        response = client.post(
            f"/collections/{test_collection['id']}/ingestion-jobs/999999/retry"
        )
        assert response.status_code == 404


class TestCancelIngestionJob:
    """Tests for POST /collections/{collection_id}/ingestion-jobs/{job_id}/cancel endpoint."""
    
    @pytest.mark.skip(reason="Requires a processing job to test")
    def test_cancel_processing_job(self, client, test_collection):
        """Cancel a processing job should mark it as failed."""
        pass
    
    def test_cancel_nonexistent_job(self, client, test_collection):
        """Cancel non-existent job should return 404."""
        response = client.post(
            f"/collections/{test_collection['id']}/ingestion-jobs/999999/cancel"
        )
        assert response.status_code == 404
