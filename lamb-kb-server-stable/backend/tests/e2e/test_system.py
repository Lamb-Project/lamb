"""
Tests for System endpoints: health, database status, embeddings config.
"""

import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check_returns_ok(self, client):
        """Health check should return status ok without authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDatabaseStatus:
    """Tests for /database/status endpoint."""
    
    def test_database_status_returns_info(self, client):
        """Database status should return SQLite and ChromaDB info."""
        data = client.database_status()
        
        assert "sqlite_status" in data
        assert "chromadb_status" in data
        assert data["sqlite_status"]["initialized"] is True
        assert data["chromadb_status"]["initialized"] is True


class TestEmbeddingsConfig:
    """Tests for /embeddings/config endpoint."""
    
    def test_get_embeddings_config(self, client):
        """Get embeddings config should return server defaults."""
        data = client.get_embeddings_config()
        
        assert "vendor" in data
        assert "model" in data
        # API key should be masked
        if "apikey" in data:
            assert data["apikey"] == "****" or data["apikey"] == ""


class TestRootEndpoint:
    """Tests for root / endpoint."""
    
    def test_root_requires_auth(self, client):
        """Root endpoint should return welcome message with auth."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
