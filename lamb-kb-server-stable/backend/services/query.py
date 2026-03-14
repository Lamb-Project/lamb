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
            from database.models import KnowledgeStoreSetup
            db_collection = CollectionService.get_collection(db, collection_id)
            if not db_collection:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection with ID {collection_id} not found"
                )

            collection_name = db_collection['name'] if isinstance(db_collection, dict) else db_collection.name

            # ── Resolve knowledge store plugin ──
            ks_plugin = None
            ks_plugin_config = None
            vendor = ""
            model_name = ""

            setup_id = (
                db_collection.get('knowledge_store_setup_id')
                if isinstance(db_collection, dict)
                else getattr(db_collection, 'knowledge_store_setup_id', None)
            )

            if setup_id:
                setup = db.query(KnowledgeStoreSetup).filter(KnowledgeStoreSetup.id == setup_id).first()
                if setup:
                    import json
                    ks_plugin_config = setup.plugin_config
                    if isinstance(ks_plugin_config, str):
                        ks_plugin_config = json.loads(ks_plugin_config)
                    ks_plugin_config = ks_plugin_config or {}

                    vendor = ks_plugin_config.get("vendor", "")
                    model_name = ks_plugin_config.get("model", "")

                    try:
                        from knowledge_store import get_knowledge_store
                        ks_plugin = get_knowledge_store(setup.plugin_type)
                        print(f"DEBUG: [query_collection] Using plugin: {setup.plugin_type}")
                    except ValueError:
                        print(f"WARNING: [query_collection] Plugin '{setup.plugin_type}' not found, falling back")

            # ── Get the backend collection and embedding function ──
            if ks_plugin and ks_plugin_config:
                # NEW MODE: use knowledge store plugin
                print(f"DEBUG: [query_collection] Getting collection via plugin")
                chroma_collection = ks_plugin.get_collection(collection_name, ks_plugin_config)
                # The embedding function is already set on the collection via get_collection
                collection_embedding_function = None  # plugin handles it
            else:
                # OLD MODE: direct ChromaDB access
                print(f"DEBUG: [query_collection] OLD MODE: using direct ChromaDB access")
                from database.connection import get_embedding_function, get_chroma_client
                collection_embedding_function = get_embedding_function(db_collection)
                chroma_client = get_chroma_client()

                # Verify collection exists
                collections = chroma_client.list_collections()
                if collections and isinstance(collections[0], str):
                    collection_exists = collection_name in collections
                else:
                    try:
                        collection_exists = any(col.name == collection_name for col in collections)
                    except (AttributeError, NotImplementedError):
                        try:
                            chroma_client.get_collection(name=collection_name)
                            collection_exists = True
                        except Exception:
                            collection_exists = False

                if not collection_exists:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Collection '{collection_name}' exists in database but not in ChromaDB."
                    )

                # Try UUID-based retrieval first, then name
                chromadb_uuid = db_collection.get("chromadb_uuid") if isinstance(db_collection, dict) else getattr(db_collection, 'chromadb_uuid', None)
                if chromadb_uuid:
                    try:
                        chroma_collection = chroma_client.get_collection(
                            name=chromadb_uuid, embedding_function=collection_embedding_function
                        )
                    except Exception:
                        chroma_collection = chroma_client.get_collection(
                            name=collection_name, embedding_function=collection_embedding_function
                        )
                else:
                    chroma_collection = chroma_client.get_collection(
                        name=collection_name, embedding_function=collection_embedding_function
                    )

                # Get embedding config for logging
                embedding_config = db_collection.get("embeddings_model") or {}
                if isinstance(embedding_config, str):
                    import json
                    embedding_config = json.loads(embedding_config)
                vendor = embedding_config.get("vendor", "")
                model_name = embedding_config.get("model", "")

            print(f"DEBUG: [query_collection] Using embeddings - vendor: {vendor}, model: {model_name}")

            # Pass backend collection to the query plugin
            params = PluginRegistry.sanitize_query_params(plugin_name, plugin_params or {})
            params["db"] = db
            params["embedding_function"] = collection_embedding_function
            params["chroma_collection"] = chroma_collection

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
