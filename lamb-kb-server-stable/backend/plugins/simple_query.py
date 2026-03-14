"""
Simple query plugin for similarity search.

This plugin performs a simple similarity search on a collection
using the knowledge store plugin abstraction.
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
        """Get the parameters accepted by this plugin."""
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
                - ks_plugin: Knowledge store plugin instance (required)
                - backend_collection: Backend collection handle (required)

        Returns:
            A list of dictionaries, each containing:
                - similarity: Similarity score
                - data: The text content
                - metadata: A dictionary of metadata for the chunk
        """
        top_k = kwargs.get("top_k", 5)
        threshold = kwargs.get("threshold", 0.0)
        db = kwargs.get("db")
        ks_plugin = kwargs.get("ks_plugin")
        backend_collection = kwargs.get("backend_collection")

        if not db:
            raise ValueError("Database session is required")

        if not query_text or query_text.strip() == "":
            raise ValueError("Query text cannot be empty")

        if not backend_collection or not ks_plugin:
            raise ValueError("backend_collection and ks_plugin parameters are required")

        start_time = time.time()

        # Use the knowledge store plugin for technology-agnostic querying
        results = ks_plugin.query_chunks(
            backend_collection,
            query_text=query_text,
            n_results=top_k
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Apply threshold filter
        filtered_results = [
            r for r in results if r.get("similarity", 0) >= threshold
        ]

        return filtered_results
