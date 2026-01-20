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
        """Query a collection using the specified plugin.
        
        This method ensures the embedding function used for querying is consistent
        with the one specified in the SQLite collection record, guaranteeing that
        the same embedding model is used for both ingestion and querying.
        
        Args:
            db: Database session
            collection_id: ID of the collection
            query_text: Query text
            plugin_name: Name of the plugin to use
            plugin_params: Parameters for the plugin
            
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
            # Get the collection from SQLite to ensure we use the same embedding function
            from database.service import CollectionService
            db_collection = CollectionService.get_collection(db, collection_id)
            if not db_collection:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection with ID {collection_id} not found"
                )
            
            # Get the embedding function for this collection using the SQLite record
            from database.connection import get_embedding_function, get_chroma_client
            try:
                # Create embedding function from collection record
                print(f"DEBUG: [query_collection] Creating embedding function from collection record")
                collection_embedding_function = get_embedding_function(db_collection)
                print(f"DEBUG: [query_collection] Created embedding function: {collection_embedding_function is not None}")
                
                # Verify ChromaDB collection exists and is accessible with this embedding function
                chroma_client = get_chroma_client()
                
                # Check if collection exists
                collections = chroma_client.list_collections()
                
                # In ChromaDB v0.6.0+, list_collections returns a list of collection names (strings)
                # In older versions, it returned objects with a name attribute
                if collections and isinstance(collections[0], str):
                    # ChromaDB v0.6.0+ - collections is a list of strings
                    collection_exists = db_collection["name"] in collections
                    print(f"DEBUG: [query_collection] Using ChromaDB v0.6.0+ API: collections are strings")
                else:
                    # Older ChromaDB - collections is a list of objects with name attribute
                    try:
                        collection_exists = any(col.name == db_collection["name"] for col in collections)
                        print(f"DEBUG: [query_collection] Using older ChromaDB API: collections have name attribute")
                    except (AttributeError, NotImplementedError):
                        # Fall back to checking if we can get the collection
                        try:
                            chroma_client.get_collection(name=db_collection["name"])
                            collection_exists = True
                            print(f"DEBUG: [query_collection] Verified collection exists by get_collection")
                        except Exception:
                            collection_exists = False
                
                if not collection_exists:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Collection '{db_collection['name']}' exists in database but not in ChromaDB. "
                              f"This indicates data inconsistency. Please recreate the collection."
                    )
                
                # Get the ChromaDB collection with our embedding function
                try:
                    if db_collection["chromadb_uuid"]:
                        # Use ChromaDB UUID if available
                        # In ChromaDB API, try with name parameter because id isn't supported here
                        try:
                            # Try first with name=uuid (this works in some versions)
                            chroma_collection = chroma_client.get_collection(
                                name=db_collection["chromadb_uuid"],
                                embedding_function=collection_embedding_function
                            )
                            print(f"DEBUG: [query_collection] Retrieved collection by UUID as name: {db_collection['chromadb_uuid']}")
                        except Exception as e1:
                            # If that fails, try with the collection name
                            try:
                                chroma_collection = chroma_client.get_collection(
                                    name=db_collection["name"],
                                    embedding_function=collection_embedding_function
                                )
                                print(f"DEBUG: [query_collection] Retrieved collection by name: {db_collection['name']}")
                            except Exception as e2:
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Failed to get collection from ChromaDB. Errors: {str(e1)}, {str(e2)}"
                                )
                    else:
                        # Fall back to name-based retrieval
                        try:
                            chroma_collection = chroma_client.get_collection(
                                name=db_collection["name"],
                                embedding_function=collection_embedding_function
                            )
                            print(f"DEBUG: [query_collection] Retrieved collection by name: {db_collection['name']}")
                        except Exception as e:
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to get collection '{db_collection['name']}' from ChromaDB. Error: {str(e)}"
                            )
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to get collection from ChromaDB. Error: {str(e)}"
                    )
                
                # Add ChromaDB collection and embedding function to plugin params
                params = plugin_params.copy()
                params["db"] = db
                params["embedding_function"] = collection_embedding_function
                params["chroma_collection"] = chroma_collection
                
                # Extract embedding model info for debugging
                embedding_config = db_collection["embeddings_model"]
                vendor = embedding_config.get("vendor", "")
                model_name = embedding_config.get("model", "")
                print(f"DEBUG: [query_collection] Using embeddings - vendor: {vendor}, model: {model_name}")
                
            except Exception as ef_e:
                print(f"DEBUG: [query_collection] ERROR preparing embedding function: {str(ef_e)}")
                import traceback
                print(f"DEBUG: [query_collection] Stack trace:\n{traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to prepare embedding function: {str(ef_e)}"
                )
            
            # Record start time
            start_time = time.time()
            
            # Execute query
            results = plugin.query(
                collection_id=collection_id,
                query_text=query_text,
                **params
            )
            
            # Record end time
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            return {
                "results": results,
                "count": len(results),
                "timing": {
                    "total_seconds": elapsed_time,
                    "total_ms": elapsed_time * 1000  # Add milliseconds for test script
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
