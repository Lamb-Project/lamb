"""
Simple query plugin for similarity search.

This plugin performs a simple similarity search on a collection.
"""

import time
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

from database.connection import get_chroma_client, get_embedding_function
from database.models import Collection
from database.service import CollectionService
from plugins.base import PluginRegistry, QueryPlugin


@PluginRegistry.register
class SimpleQueryPlugin(QueryPlugin):
    """Simple query plugin for similarity search."""
    
    name = "simple_query"
    description = "Simple similarity search on a collection"
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        return {
            "top_k": {
                "type": "integer",
                "description": "Number of results to return",
                "required": False,
                "default": 5
            },
            "threshold": {
                "type": "number",
                "description": "Minimum similarity threshold (0-1)",
                "required": False,
                "default": 0.0
            }
        }
    
    def query(self, collection_id: int, query_text: str, **kwargs) -> List[Dict[str, Any]]:
        """Query a collection and return results.
        
        Args:
            collection_id: ID of the collection to query
            query_text: The query text
            **kwargs: Additional parameters:
                - top_k: Number of results to return (default: 5)
                - threshold: Minimum similarity threshold (default: 0.0)
                - db: SQLAlchemy database session (required)
                - embedding_function: The embedding function to use (optional)
                - chroma_collection: The ChromaDB collection to use (optional)
                
        Returns:
            A list of dictionaries, each containing:
                - similarity: Similarity score
                - data: The text content
                - metadata: A dictionary of metadata for the chunk
                
        Raises:
            ValueError: If the collection is not found
        """
        # Extract parameters
        top_k = kwargs.get("top_k", 5)
        threshold = kwargs.get("threshold", 0.0)
        db = kwargs.get("db")
        embedding_function = kwargs.get("embedding_function")
        chroma_collection = kwargs.get("chroma_collection")
        
        if not db:
            raise ValueError("Database session is required")
            
        # Validate query text
        if not query_text or query_text.strip() == "":
            raise ValueError("Query text cannot be empty")
        
        # If ChromaDB collection wasn't provided, get it from the DB
        if not chroma_collection:
            # Get the collection
            collection = CollectionService.get_collection(db, collection_id)
            if not collection:
                raise ValueError(f"Collection with ID {collection_id} not found")
            
            # Get collection name - handle both dict-like and attribute access
            collection_name = collection['name'] if isinstance(collection, dict) else collection.name
            
            # Get ChromaDB client and collection
            chroma_client = get_chroma_client()
            try:
                # Get the embedding function for this collection if not provided
                if not embedding_function:
                    print(f"DEBUG: [simple_query] Getting embedding function from collection")
                    collection_id_for_embedding = collection['id'] if isinstance(collection, dict) else collection.id
                    embedding_function = get_embedding_function(collection_id_for_embedding)
                else:
                    print(f"DEBUG: [simple_query] Using provided embedding function")
                
                # Get the collection with the embedding function
                try:
                    chroma_collection = chroma_client.get_collection(
                        name=collection_name,
                        embedding_function=embedding_function
                    )
                except Exception as e:
                    # If getting by name fails, try getting by name=uuid (as a fallback)
                    try:
                        # Check if collection_name might be a UUID
                        import uuid
                        # Try to parse as UUID to validate if it looks like a UUID
                        try:
                            uuid_obj = uuid.UUID(collection_name)
                            is_likely_uuid = True
                        except ValueError:
                            is_likely_uuid = False
                        
                        if is_likely_uuid:
                            print(f"DEBUG: [SimpleQueryPlugin] Collection name appears to be a UUID, trying as UUID")
                            chroma_collection = chroma_client.get_collection(
                                name=collection_name,
                                embedding_function=embedding_function
                            )
                        else:
                            raise ValueError(f"Collection '{collection_name}' not found in ChromaDB")
                    except Exception as e2:
                        raise ValueError(f"Collection '{collection_name}' exists in database but not in ChromaDB. Please recreate the collection. Errors: {str(e)}, {str(e2)}")
            except Exception as e:
                raise ValueError(f"Collection '{collection_name}' exists in database but not in ChromaDB. Please recreate the collection. Error: {str(e)}")
        else:
            print(f"DEBUG: [simple_query] Using provided ChromaDB collection")
        
        # Record start time
        start_time = time.time()
        
        # Perform query
        results = chroma_collection.query(
            query_texts=[query_text],
            n_results=top_k
        )
        
        # Record end time
        end_time = time.time()
        
        # Calculate elapsed time in milliseconds
        elapsed_ms = (end_time - start_time) * 1000
        
        # Format results
        formatted_results = []
        if results and len(results["documents"]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                if i < len(results["metadatas"][0]) and i < len(results["distances"][0]):
                    # Convert distance to similarity (ChromaDB returns distance, we want similarity)
                    similarity = 1.0 - results["distances"][0][i]
                    
                    # Apply threshold filter
                    if similarity >= threshold:
                        formatted_results.append({
                            "similarity": similarity,
                            "data": doc,
                            "metadata": results["metadatas"][0][i]
                        })
        
        # Just return the formatted results list - the QueryService will handle the rest
        return formatted_results


# Initialize plugin
simple_query_plugin = SimpleQueryPlugin()
