"""
E2E tests for system endpoints.
"""

import pytest
import httpx


pytestmark = pytest.mark.live


class TestHealthEndpoint:
    
    def test_health_check(self, live_client):
        response = live_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestRootEndpoint:
    
    def test_with_valid_auth(self, live_client):
        response = live_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Lamb" in data["message"]
    
    def test_without_auth(self, live_client, live_server_url):
        with httpx.Client(base_url=live_server_url, timeout=10.0) as client:
            response = client.get("/")
            assert response.status_code == 401
    
    def test_with_invalid_auth(self, live_client, live_server_url, invalid_auth_headers):
        with httpx.Client(base_url=live_server_url, headers=invalid_auth_headers, timeout=10.0) as client:
            response = client.get("/")
            assert response.status_code == 401


class TestDatabaseStatusEndpoint:
    
    def test_database_status(self, live_client):
        response = live_client.get("/database/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["sqlite_status"]["initialized"] is True
        assert data["chromadb_status"]["initialized"] is True
        assert "collections_count" in data


class TestEmbeddingsConfigEndpoint:
    
    def test_get_config(self, live_client):
        response = live_client.get("/config/embeddings")
        
        assert response.status_code == 200
        data = response.json()
        assert "model" in data
        assert "vendor" in data
    
    def test_update_config(self, live_client):
        original = live_client.get("/config/embeddings").json()
        update_data = {"model": original.get("model", "nomic-embed-text")}
        
        response = live_client.put("/config/embeddings", json=update_data)
        
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_reset_config(self, live_client):
        response = live_client.delete("/config/embeddings")
        
        assert response.status_code == 200
        assert "message" in response.json()


class TestIngestionConfigEndpoint:
    
    def test_get_config(self, live_client):
        response = live_client.get("/config/ingestion")
        
        assert response.status_code == 200
        data = response.json()
        assert "refresh_rate" in data
        assert isinstance(data["refresh_rate"], int)
