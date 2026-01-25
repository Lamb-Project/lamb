"""
Tests for Collection CRUD endpoints.
"""

import pytest
import time


class TestCreateCollection:
    """Tests for POST /collections endpoint."""
    
    def test_create_collection_success(self, client):
        """Create collection should return the created collection."""
        timestamp = int(time.time() * 1000)
        name = f"test-create-{timestamp}"
        
        collection = client.create_collection(
            name=name,
            description="Test description",
            owner="test-owner"
        )
        
        try:
            assert collection["name"] == name
            assert collection["description"] == "Test description"
            assert collection["owner"] == "test-owner"
            assert "id" in collection
            assert "creation_date" in collection
            assert "embeddings_model" in collection
        finally:
            # Cleanup
            client.delete_collection(collection["id"])
    
    def test_create_collection_with_custom_embeddings(self, client):
        """Create collection with custom embeddings model."""
        timestamp = int(time.time() * 1000)
        name = f"test-custom-embed-{timestamp}"
        
        collection = client.create_collection(
            name=name,
            embeddings_model={
                "model": "nomic-embed-text",
                "vendor": "ollama",
                "api_endpoint": "http://host.docker.internal:11434/api/embeddings",
                "apikey": ""
            }
        )
        
        try:
            assert collection["embeddings_model"]["model"] == "nomic-embed-text"
            assert collection["embeddings_model"]["vendor"] == "ollama"
        finally:
            client.delete_collection(collection["id"])
    
    def test_create_collection_duplicate_name_fails(self, client, test_collection):
        """Creating a collection with duplicate name should fail."""
        response = client.post("/collections", json={
            "name": test_collection["name"],
            "description": "Duplicate",
            "owner": "test-user",
            "visibility": "private",
            "embeddings_model": {"model": "default", "vendor": "default"}
        })
        
        # Should fail with conflict or bad request
        assert response.status_code in [400, 409]


class TestListCollections:
    """Tests for GET /collections endpoint."""
    
    def test_list_collections_returns_items(self, client, test_collection):
        """List collections should return items list."""
        data = client.list_collections()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1
    
    def test_list_collections_with_owner_filter(self, client, test_collection):
        """List collections filtered by owner."""
        data = client.list_collections(owner="test-user")
        
        for item in data["items"]:
            assert item["owner"] == "test-user"
    
    def test_list_collections_with_pagination(self, client):
        """List collections with pagination parameters."""
        data = client.list_collections(skip=0, limit=5)
        
        assert len(data["items"]) <= 5


class TestGetCollection:
    """Tests for GET /collections/{id} endpoint."""
    
    def test_get_collection_success(self, client, test_collection):
        """Get collection by ID should return collection details."""
        collection = client.get_collection(test_collection["id"])
        
        assert collection["id"] == test_collection["id"]
        assert collection["name"] == test_collection["name"]
        assert "embeddings_model" in collection
    
    def test_get_collection_not_found(self, client):
        """Get non-existent collection should return 404."""
        response = client.get("/collections/999999")
        assert response.status_code == 404


class TestDeleteCollection:
    """Tests for DELETE /collections/{id} endpoint."""
    
    def test_delete_collection_success(self, client):
        """Delete collection should remove it."""
        # Create a collection to delete
        timestamp = int(time.time() * 1000)
        collection = client.create_collection(name=f"to-delete-{timestamp}")
        
        # Delete it
        result = client.delete_collection(collection["id"])
        # The response includes info about the deleted collection
        assert result.get("id") == collection["id"] or result.get("deleted") or result.get("message")
        
        # Verify it's gone
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 404
    
    def test_delete_collection_not_found(self, client):
        """Delete non-existent collection should return 404."""
        response = client.delete("/collections/999999")
        assert response.status_code == 404
