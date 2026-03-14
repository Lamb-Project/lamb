"""
Query service for retrieving data from collections.

This module provides services for querying collections using query plugins.
"""

import time
from typing import Dict, List, Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from plugins.base import PluginRegistry, QueryPlugin


class QueryService:
    """Service for querying collections."""
    
    @classmethod
    def get_plugin(cls, name: str) -> Optional[QueryPlugin]:
        """Get a query plugin by name.
        
        Args:
            name: Name of the plugin
            
        Returns:
            Plugin instance or None if not found
        """
        plugin_class = PluginRegistry.get_query_plugin(name)
        if plugin_class:
            return plugin_class()
        return None
    
    @classmethod
    def list_plugins(cls) -> List[Dict[str, Any]]:
        """List all available query plugins.
        
        Returns:
            List of plugins with metadata
        """
        return PluginRegistry.list_query_plugins()
    
    @classmethod
    def query_collection(
        cls, 
        db: Session,
        collection_id: int,
        query_text: str,
        plugin_name: str,
        plugin_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query a collection using the specified query plugin.

        Resolves the collection's knowledge store setup to get the appropriate
        backend, then passes the backend collection to the query plugin.

        Args:
            db: Database session
            collection_id: ID of the collection
            query_text: Query text
            plugin_name: Name of the query plugin to use
            plugin_params: Parameters for the query plugin

        Returns:
            Query results with timing information

        Raises:
            HTTPException: If the plugin is not found or query fails
        """
        plugin = cls.get_plugin(plugin_name)
        if not plugin:
            raise HTTPException(
                status_code=404,
                detail=f"Query plugin '{plugin_name}' not found"
            )

        try:
            # Get the collection from DB
            from database.service import CollectionService
            db_collection = CollectionService.get_collection(db, collection_id)
            if not db_collection:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection with ID {collection_id} not found"
                )

            collection_name = db_collection['name'] if isinstance(db_collection, dict) else db_collection.name

            # ── Resolve knowledge store plugin (handles both NEW and OLD MODE) ──
            from knowledge_store import resolve_plugin_for_collection
            ks_plugin, plugin_config, col_name = resolve_plugin_for_collection(db_collection, db)
            vendor = plugin_config.get("vendor", "")
            model_name = plugin_config.get("model", "")

            # Get the backend collection handle
            backend_collection = ks_plugin.get_collection(col_name, plugin_config)

            print(f"DEBUG: [query_collection] Using plugin: {ks_plugin.name}, vendor: {vendor}, model: {model_name}")

            # Pass backend collection and plugin to the query plugin
            params = PluginRegistry.sanitize_query_params(plugin_name, plugin_params or {})
            params["db"] = db
            params["ks_plugin"] = ks_plugin
            params["backend_collection"] = backend_collection

            # Record timing
            start_time = time.time()

            results = plugin.query(
                collection_id=collection_id,
                query_text=query_text,
                **params
            )

            elapsed_time = time.time() - start_time

            return {
                "results": results,
                "count": len(results),
                "timing": {
                    "total_seconds": elapsed_time,
                    "total_ms": elapsed_time * 1000
                },
                "query": query_text,
                "embedding_info": {
                    "vendor": vendor,
                    "model": model_name
                }
            }
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to query collection: {str(e)}"
            )
