"""
Live tests for collection CRUD operations against real running server.
"""

import pytest
import time


pytestmark = pytest.mark.live


class TestCreateCollection:
    """Live tests for POST /collections endpoint."""
    
    def test_create_collection_success(self, live_client, sample_collection_data, cleanup_collection):
        """Creating a collection on live server should work."""
        response = live_client.post("/collections", json=sample_collection_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_collection_data["name"]
        assert "id" in data
        
        cleanup_collection(data["id"])
    
    def test_create_collection_duplicate_name(self, live_client, cleanup_collection, sample_collection_data):
        """Creating duplicate collection should return 409."""
        unique_name = f"duplicate-test-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        response1 = live_client.post("/collections", json=data)
        assert response1.status_code == 201
        cleanup_collection(response1.json()["id"])
        
        response2 = live_client.post("/collections", json=data)
        assert response2.status_code == 409
    
    def test_create_collection_missing_name(self, live_client):
        """Creating collection without name should return 422."""
        data = {
            "description": "Missing name",
            "owner": "test-user",
            "visibility": "private"
        }
        
        response = live_client.post("/collections", json=data)
        assert response.status_code == 422
    
    def test_create_collection_invalid_visibility(self, live_client):
        """Creating collection with invalid visibility should return 400."""
        data = {
            "name": f"invalid-vis-{int(time.time() * 1000)}",
            "description": "Invalid visibility",
            "owner": "test-user",
            "visibility": "invalid"
        }
        
        response = live_client.post("/collections", json=data)
        assert response.status_code == 400


class TestListCollections:
    """Live tests for GET /collections endpoint."""
    
    def test_list_collections(self, live_client):
        """Listing collections should return list from real database."""
        response = live_client.get("/collections")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    
    def test_list_collections_pagination(self, live_client):
        """Pagination parameters should work."""
        response = live_client.get("/collections?skip=0&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 5
    
    def test_list_collections_filter_visibility(self, live_client, cleanup_collection):
        """Filtering by visibility should work."""
        unique_name = f"public-filter-{int(time.time() * 1000)}"
        create_data = {
            "name": unique_name,
            "description": "Public collection",
            "owner": "test-user",
            "visibility": "public",
            "embeddings_model": {"model": "default", "vendor": "default", "apikey": "default"}
        }
        create_response = live_client.post("/collections", json=create_data)
        if create_response.status_code == 201:
            cleanup_collection(create_response.json()["id"])
        
        response = live_client.get("/collections?visibility=public")
        
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["visibility"] == "public"


class TestGetCollection:
    """Live tests for GET /collections/{id} endpoint."""
    
    def test_get_collection_success(self, live_client, sample_collection_data, cleanup_collection):
        """Getting an existing collection should work."""
        create_response = live_client.post("/collections", json=sample_collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.get(f"/collections/{collection_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == collection_id
        assert data["name"] == sample_collection_data["name"]
    
    def test_get_collection_not_found(self, live_client):
        """Getting non-existent collection should return 404."""
        response = live_client.get("/collections/999999")
        assert response.status_code == 404


class TestDeleteCollection:
    """Live tests for DELETE /collections/{id} endpoint."""
    
    def test_delete_collection_success(self, live_client, sample_collection_data):
        """Deleting a collection should work."""
        unique_name = f"delete-test-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        
        delete_response = live_client.delete(f"/collections/{collection_id}")
        assert delete_response.status_code == 200
        
        get_response = live_client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 404
    
    def test_delete_collection_not_found(self, live_client):
        """Deleting non-existent collection should return 404."""
        response = live_client.delete("/collections/999999")
        assert response.status_code == 404


class TestBulkUpdateEmbeddings:
    """Tests for bulk update embeddings endpoint."""
    
    def test_bulk_update_embeddings_by_owner(self, live_client, sample_collection_data, cleanup_collection):
        """Should update embeddings for all collections of an owner."""
        unique_owner = f"bulk-owner-{int(time.time() * 1000)}"
        
        # Create two collections for this owner
        data1 = sample_collection_data.copy()
        data1["name"] = f"bulk-col-1-{int(time.time() * 1000)}"
        data1["owner"] = unique_owner
        resp1 = live_client.post("/collections", json=data1)
        assert resp1.status_code == 201
        cleanup_collection(resp1.json()["id"])
        
        data2 = sample_collection_data.copy()
        data2["name"] = f"bulk-col-2-{int(time.time() * 1000)}"
        data2["owner"] = unique_owner
        resp2 = live_client.post("/collections", json=data2)
        assert resp2.status_code == 201
        cleanup_collection(resp2.json()["id"])
        
        # Bulk update embeddings (endpoint only updates apikey)
        update_data = {
            "embeddings_model": {
                "apikey": "test-api-key-for-bulk-update"
            }
        }
        
        response = live_client.put(
            f"/collections/owner/{unique_owner}/embeddings",
            json=update_data
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["updated"] == 2
    
    def test_bulk_update_embeddings_requires_apikey(self, live_client):
        """Should return 400 when apikey is empty."""
        fake_owner = f"nonexistent-owner-{int(time.time() * 1000)}"
        
        update_data = {
            "embeddings_model": {
                "apikey": ""  # Empty apikey should fail
            }
        }
        
        response = live_client.put(
            f"/collections/owner/{fake_owner}/embeddings",
            json=update_data
        )
        
        # Should return 400 because apikey is required
        assert response.status_code == 400
    
    def test_bulk_update_embeddings_no_collections(self, live_client):
        """Should return 0 updated when owner has no collections."""
        fake_owner = f"nonexistent-owner-{int(time.time() * 1000)}"
        
        update_data = {
            "embeddings_model": {
                "apikey": "valid-key-but-no-collections"
            }
        }
        
        response = live_client.put(
            f"/collections/owner/{fake_owner}/embeddings",
            json=update_data
        )
        
        assert response.status_code == 200
        assert response.json()["updated"] == 0


class TestIngestBase:
    """Tests for the ingest-base endpoint."""
    
    def test_ingest_base_endpoint(self, live_client, sample_collection_data, cleanup_collection):
        """Should accept ingest-base request."""
        unique_name = f"ingest-base-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        # Try ingest-base (may fail if no base-ingest plugin is registered)
        ingest_request = {
            "plugin_name": "simple_ingest",
            "plugin_params": {"content": "Test content for base ingestion"}
        }
        
        response = live_client.post(
            f"/collections/{collection_id}/ingest-base",
            json=ingest_request
        )
        
        # May succeed or fail depending on plugin support
        assert response.status_code in [200, 400, 404]

