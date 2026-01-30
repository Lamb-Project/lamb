"""
Tests for Bulk Update endpoints.
"""

import pytest
import time


class TestBulkUpdateEmbeddingsApiKey:
    """Tests for PUT /collections/owner/{owner}/embeddings endpoint."""
    
    def test_bulk_update_apikey(self, client):
        """Bulk update should update all collections for an owner."""
        timestamp = int(time.time() * 1000)
        owner = f"bulk-test-owner-{timestamp}"
        
        # Create several collections for this owner
        collections = []
        for i in range(2):
            coll = client.create_collection(
                name=f"bulk-test-{timestamp}-{i}",
                owner=owner
            )
            collections.append(coll)
        
        try:
            # Bulk update the API key
            response = client.put(
                f"/collections/owner/{owner}/embeddings",
                json={
                    "embeddings_model": {
                        "apikey": "new-test-api-key-123"
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["total"] == 2
            assert data["updated"] == 2
            assert data["failed"] == 0
            
        finally:
            # Cleanup
            for coll in collections:
                try:
                    client.delete_collection(coll["id"])
                except Exception:
                    pass
    
    def test_bulk_update_no_collections(self, client):
        """Bulk update for owner with no collections should return zero."""
        timestamp = int(time.time() * 1000)
        
        response = client.put(
            f"/collections/owner/nonexistent-owner-{timestamp}/embeddings",
            json={
                "embeddings_model": {
                    "apikey": "test-key"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
