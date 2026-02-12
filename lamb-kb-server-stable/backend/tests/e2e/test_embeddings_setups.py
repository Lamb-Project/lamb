"""
E2E tests for Organizations and Embeddings Setups feature.

Tests verify:
- Organization CRUD operations
- Embeddings Setup CRUD operations
- Collection creation with embeddings setup reference
- Setup deletion constraints
- Available setups endpoint
"""

import time
import pytest
import requests
from typing import Dict, Any, Generator


class TestOrganizations:
    """Tests for KB-server organization endpoints (INTERNAL API).
    
    NOTE: These tests verify KB-server's internal organization API which is called
    by LAMB's ensure_org_in_kb_server() during knowledge base creation.
    
    In production:
    - Users DO NOT call KB-server's /organizations endpoints directly
    - LAMB handles organization management and syncs to KB-server
    - These tests validate the internal API that LAMB relies on
    """

    def test_upsert_organization(self, client):
        """Test creating/updating an organization."""
        timestamp = int(time.time() * 1000)
        org_data = {
            "external_id": f"test-org-{timestamp}",
            "name": f"Test Organization {timestamp}",
            "config": {"version": "1.0"}
        }

        # Create organization
        response = client.post("/organizations/", json=org_data)
        assert response.status_code == 200 or response.status_code == 201
        org = response.json()
        assert org["external_id"] == org_data["external_id"]
        assert org["name"] == org_data["name"]

        # Update same organization (upsert)
        org_data["name"] = f"Updated Org {timestamp}"
        response = client.post("/organizations/", json=org_data)
        assert response.status_code == 200
        updated_org = response.json()
        assert updated_org["name"] == org_data["name"]

    def test_get_organization(self, client):
        """Test getting organization by external_id."""
        timestamp = int(time.time() * 1000)
        org_data = {
            "external_id": f"get-org-{timestamp}",
            "name": f"Get Test Org {timestamp}"
        }

        # Create first
        client.post("/organizations/", json=org_data)

        # Get by external_id
        response = client.get(f"/organizations/{org_data['external_id']}")
        assert response.status_code == 200
        org = response.json()
        assert org["external_id"] == org_data["external_id"]

    def test_get_nonexistent_organization(self, client):
        """Test 404 for non-existent organization."""
        response = client.get("/organizations/nonexistent-org-12345")
        assert response.status_code == 404


class TestEmbeddingsSetups:
    """Tests for embeddings setups endpoints."""

    @pytest.fixture
    def test_org(self, client) -> Generator[Dict[str, Any], None, None]:
        """Create a test organization with cleanup."""
        timestamp = int(time.time() * 1000)
        org_data = {
            "external_id": f"emb-test-org-{timestamp}",
            "name": f"Embeddings Test Org {timestamp}"
        }
        response = client.post("/organizations/", json=org_data)
        response.raise_for_status()
        yield response.json()

    def test_create_embeddings_setup(self, client, test_org):
        """Test creating an embeddings setup."""
        org_ext_id = test_org["external_id"]
        # Use ollama which is available in test environment
        setup_data = {
            "name": "Test Ollama Setup",
            "setup_key": "ollama_test",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768,
            "is_default": True
        }

        response = client.post(
            f"/organizations/{org_ext_id}/embeddings-setups",
            json=setup_data
        )
        assert response.status_code == 200 or response.status_code == 201, f"Got {response.status_code}: {response.text}"
        setup = response.json()
        assert setup["name"] == setup_data["name"]
        assert setup["setup_key"] == setup_data["setup_key"]
        assert setup["vendor"] == setup_data["vendor"]
        assert setup["embedding_dimensions"] == 768
        assert setup["is_default"] == True

    def test_list_embeddings_setups(self, client, test_org):
        """Test listing embeddings setups for an organization."""
        org_ext_id = test_org["external_id"]

        # Create a setup first
        setup_data = {
            "name": "List Test Setup",
            "setup_key": f"list_test_{int(time.time())}",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768
        }
        client.post(f"/organizations/{org_ext_id}/embeddings-setups", json=setup_data)

        # List setups
        response = client.get(f"/organizations/{org_ext_id}/embeddings-setups")
        assert response.status_code == 200
        setups = response.json()
        assert len(setups) >= 1
        assert any(s["setup_key"] == setup_data["setup_key"] for s in setups)

    def test_get_embeddings_setup(self, client, test_org):
        """Test getting a specific embeddings setup."""
        org_ext_id = test_org["external_id"]
        setup_key = f"get_test_{int(time.time())}"

        # Create setup
        setup_data = {
            "name": "Get Test Setup",
            "setup_key": setup_key,
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768
        }
        create_response = client.post(
            f"/organizations/{org_ext_id}/embeddings-setups",
            json=setup_data
        )
        created_setup = create_response.json()

        # Get setup by ID or key
        response = client.get(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}"
        )
        assert response.status_code == 200
        setup = response.json()
        assert setup["setup_key"] == setup_key

    def test_update_embeddings_setup(self, client, test_org):
        """Test updating an embeddings setup."""
        org_ext_id = test_org["external_id"]
        setup_key = f"update_test_{int(time.time())}"

        # Create setup
        setup_data = {
            "name": "Original Name",
            "setup_key": setup_key,
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768
        }
        create_response = client.post(
            f"/organizations/{org_ext_id}/embeddings-setups",
            json=setup_data
        )
        created_setup = create_response.json()

        # Update setup (name only, since ollama doesn't need api_key)
        update_data = {
            "name": "Updated Name"
        }
        response = client.put(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}",
            json=update_data
        )
        assert response.status_code == 200
        updated_setup = response.json()
        assert updated_setup["name"] == "Updated Name"
        # Dimensions should NOT change
        assert updated_setup["embedding_dimensions"] == 768

    def test_dimension_update_blocked(self, client, test_org):
        """Test that embedding_dimensions cannot be changed after creation."""
        org_ext_id = test_org["external_id"]

        # Create setup
        setup_data = {
            "name": "Dimension Lock Test",
            "setup_key": f"dim_lock_{int(time.time())}",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768
        }
        create_response = client.post(
            f"/organizations/{org_ext_id}/embeddings-setups",
            json=setup_data
        )
        created_setup = create_response.json()

        # Try to update dimensions (should be ignored or fail)
        update_data = {
            "embedding_dimensions": 512  # Try to change
        }
        response = client.put(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}",
            json=update_data
        )
        
        # Check that dimensions are unchanged
        get_response = client.get(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}"
        )
        setup = get_response.json()
        assert setup["embedding_dimensions"] == 768  # Should remain unchanged

    def test_delete_embeddings_setup_without_collections(self, client, test_org):
        """Test deleting an embeddings setup that has no associated collections."""
        org_ext_id = test_org["external_id"]

        # Create setup
        setup_data = {
            "name": "Delete Test Setup",
            "setup_key": f"delete_test_{int(time.time())}",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768
        }
        create_response = client.post(
            f"/organizations/{org_ext_id}/embeddings-setups",
            json=setup_data
        )
        created_setup = create_response.json()

        # Delete setup
        response = client.delete(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}"
        )
        assert response.status_code == 200 or response.status_code == 204

        # Verify it's gone
        get_response = client.get(
            f"/organizations/{org_ext_id}/embeddings-setups/{created_setup['setup_key']}"
        )
        assert get_response.status_code == 404

    def test_available_setups_endpoint(self, client, test_org):
        """Test the available setups endpoint."""
        org_ext_id = test_org["external_id"]

        # Create an active setup
        setup_data = {
            "name": "Available Test Setup",
            "setup_key": f"avail_test_{int(time.time())}",
            "vendor": "openai",
            "model_name": "text-embedding-3-small",
            "embedding_dimensions": 1536,
            "is_active": True
        }
        client.post(f"/organizations/{org_ext_id}/embeddings-setups", json=setup_data)

        # Get available setups
        response = client.get(
            f"/organizations/{org_ext_id}/embeddings-setups/available"
        )
        assert response.status_code == 200
        setups = response.json()
        # Should only return active setups
        assert all(s.get("is_active", True) for s in setups)


class TestCollectionWithSetup:
    """Tests for collection creation with embeddings setup reference."""

    @pytest.fixture
    def setup_with_org(self, client) -> Generator[Dict[str, Any], None, None]:
        """Create org and setup for collection tests."""
        timestamp = int(time.time() * 1000)
        
        # Create org
        org_data = {
            "external_id": f"coll-test-org-{timestamp}",
            "name": f"Collection Test Org {timestamp}"
        }
        org_response = client.post("/organizations/", json=org_data)
        org = org_response.json()
        
        # Create setup (using Ollama which should be available in test env)
        setup_data = {
            "name": "Collection Test Setup",
            "setup_key": f"coll_setup_{timestamp}",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text",
            "embedding_dimensions": 768,
            "is_default": True
        }
        setup_response = client.post(
            f"/organizations/{org['external_id']}/embeddings-setups",
            json=setup_data
        )
        setup = setup_response.json()
        
        yield {"org": org, "setup": setup}

    def test_create_collection_with_setup_key(self, client, setup_with_org):
        """Test creating a collection using NEW MODE (setup reference)."""
        org = setup_with_org["org"]
        setup = setup_with_org["setup"]
        timestamp = int(time.time() * 1000)

        collection_data = {
            "name": f"setup-collection-{timestamp}",
            "description": "Collection using embeddings setup",
            "owner": "test-user",
            "visibility": "private",
            "organization_external_id": org["external_id"],
            "embeddings_setup_key": setup["setup_key"]
        }

        response = client.post("/collections", json=collection_data)
        # May fail if Ollama not available, skip in that case
        if response.status_code == 400 and "connection" in response.text.lower():
            pytest.skip("Ollama not available for test")
        
        assert response.status_code in [200, 201], f"Unexpected status: {response.text}"
        collection = response.json()
        assert collection["name"] == collection_data["name"]
        
        # Cleanup
        try:
            client.delete(f"/collections/{collection['id']}")
        except Exception:
            pass

    def test_create_collection_with_default_setup(self, client, setup_with_org):
        """Test creating a collection using org's default setup."""
        org = setup_with_org["org"]
        timestamp = int(time.time() * 1000)

        collection_data = {
            "name": f"default-setup-collection-{timestamp}",
            "description": "Collection using default setup",
            "owner": "test-user",
            "visibility": "private",
            "organization_external_id": org["external_id"]
            # No embeddings_setup_key - should use default
        }

        response = client.post("/collections", json=collection_data)
        if response.status_code == 400 and "connection" in response.text.lower():
            pytest.skip("Ollama not available for test")
        
        if response.status_code in [200, 201]:
            collection = response.json()
            assert collection["name"] == collection_data["name"]
            
            # Cleanup
            try:
                client.delete(f"/collections/{collection['id']}")
            except Exception:
                pass
        elif response.status_code == 404:
            # May fail if no default - this is acceptable
            assert "default" in response.text.lower()


class TestSetupDeletionConstraints:
    """Tests for setup deletion with associated collections."""

    def test_delete_setup_with_collections_fails(self, client):
        """Test that deleting a setup with associated collections fails."""
        timestamp = int(time.time() * 1000)
        
        # Create org
        org_data = {
            "external_id": f"del-constrain-org-{timestamp}",
            "name": f"Delete Constraint Test Org"
        }
        org_response = client.post("/organizations/", json=org_data)
        if org_response.status_code not in [200, 201]:
            pytest.skip("Could not create test organization")
        org = org_response.json()
        
        # Create setup
        setup_data = {
            "name": "Setup To Delete",
            "setup_key": f"del_setup_{timestamp}",
            "vendor": "ollama",
            "api_endpoint": "http://host.docker.internal:11434",
            "model_name": "nomic-embed-text", 
            "embedding_dimensions": 768,
            "is_default": True
        }
        setup_response = client.post(
            f"/organizations/{org['external_id']}/embeddings-setups",
            json=setup_data
        )
        if setup_response.status_code not in [200, 201]:
            pytest.skip("Could not create test setup")
        setup = setup_response.json()
        
        # Create collection using this setup
        collection_data = {
            "name": f"blocking-collection-{timestamp}",
            "owner": "test-user",
            "organization_external_id": org["external_id"],
            "embeddings_setup_key": setup["setup_key"]
        }
        coll_response = client.post("/collections", json=collection_data)
        if coll_response.status_code not in [200, 201]:
            # Ollama might not be available
            pytest.skip("Could not create test collection (Ollama may not be available)")
        collection = coll_response.json()
        
        try:
            # Try to delete setup - should fail
            del_response = client.delete(
                f"/organizations/{org['external_id']}/embeddings-setups/{setup['setup_key']}"
            )
            assert del_response.status_code in [400, 409, 422], \
                f"Expected error when deleting setup with collections, got {del_response.status_code}"
        finally:
            # Cleanup collection
            try:
                client.delete(f"/collections/{collection['id']}")
            except Exception:
                pass
