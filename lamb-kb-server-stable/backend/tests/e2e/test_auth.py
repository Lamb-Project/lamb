"""
Tests for Authentication and Authorization.
"""

import pytest
import requests


class TestAuthentication:
    """Tests for authentication requirements."""
    
    def test_unauthenticated_request_fails(self, client):
        """Request without auth token should fail."""
        response = requests.get(
            f"{client.base_url}/collections",
            headers={},  # No auth
            timeout=10
        )
        assert response.status_code == 401
    
    def test_invalid_token_fails(self, client):
        """Request with invalid token should fail."""
        response = requests.get(
            f"{client.base_url}/collections",
            headers={"Authorization": "Bearer invalid-token"},
            timeout=10
        )
        assert response.status_code == 401
    
    def test_health_no_auth_required(self, client):
        """Health endpoint should not require authentication."""
        response = requests.get(
            f"{client.base_url}/health",
            headers={},  # No auth
            timeout=10
        )
        assert response.status_code == 200
    
    def test_valid_token_succeeds(self, client):
        """Request with valid token should succeed."""
        response = client.get("/collections")
        assert response.status_code == 200


class TestErrorResponses:
    """Tests for error response format."""
    
    def test_404_returns_detail(self, client):
        """404 response should include detail message."""
        response = client.get("/collections/999999")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
    
    def test_invalid_json_returns_422(self, client, test_collection):
        """Invalid JSON body should return 422."""
        response = requests.post(
            f"{client.base_url}/collections/{test_collection['id']}/query",
            headers=client.headers,
            params={"plugin_name": "simple_query"},
            data="not valid json",  # Invalid JSON
            timeout=10
        )
        assert response.status_code == 422
