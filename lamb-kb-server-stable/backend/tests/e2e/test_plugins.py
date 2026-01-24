"""
Tests for Plugins endpoints.
"""

import pytest


class TestIngestionPlugins:
    """Tests for GET /ingestion/plugins endpoint."""
    
    def test_list_ingestion_plugins(self, client):
        """List ingestion plugins should return available plugins."""
        response = client.get("/ingestion/plugins")
        assert response.status_code == 200
        
        plugins = response.json()
        assert isinstance(plugins, list)
        
        # simple_ingest should always exist
        plugin_names = [p["name"] for p in plugins]
        assert "simple_ingest" in plugin_names
    
    def test_plugin_has_required_fields(self, client):
        """Each plugin should have required metadata."""
        response = client.get("/ingestion/plugins")
        plugins = response.json()
        
        for plugin in plugins:
            assert "name" in plugin
            assert "kind" in plugin


class TestQueryPlugins:
    """Tests for query plugins (via collection query endpoint)."""
    
    def test_simple_query_plugin_exists(self, client, ingested_collection):
        """Simple query plugin should work."""
        result = client.query_collection(
            ingested_collection["id"],
            "test",
            plugin_name="simple_query"
        )
        
        assert "results" in result


class TestIngestionConfig:
    """Tests for GET /config/ingestion endpoint."""
    
    def test_get_ingestion_config(self, client):
        """Get ingestion config should return configuration values."""
        config = client.get_ingestion_config()
        assert isinstance(config, dict)
