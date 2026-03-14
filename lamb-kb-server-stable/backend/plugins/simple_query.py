"""
Simple query plugin for similarity search.

This plugin performs a simple similarity search on a collection.
"""

import time
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

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
        
        # If ChromaDB collection wasn't provided, it indicates a failure in query service delegation
        if not chroma_collection:
            raise ValueError("chroma_collection parameter is required for simple query execution")
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
