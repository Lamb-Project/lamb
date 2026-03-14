"""
Parent-child query plugin for hierarchical chunking.

This plugin extends the simple_query plugin to support parent-child chunking.
When child chunks are matched during semantic search, it returns the parent chunk
context to the LLM for better structural understanding.
"""

import time
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

from database.models import Collection
from database.service import CollectionService
from plugins.base import PluginRegistry, QueryPlugin


@PluginRegistry.register
class ParentChildQueryPlugin(QueryPlugin):
    """Query plugin that returns parent chunks when child chunks match."""

    name = "parent_child_query"
    description = "Query plugin that returns parent chunk context for child chunk matches"

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
            },
            "return_parent_context": {
                "type": "boolean",
                "description": "Whether to return parent context in results (default: True)",
                "required": False,
                "default": True
            }
        }

    def query(self, collection_id: int, query_text: str, **kwargs) -> List[Dict[str, Any]]:
        """Query a collection and return results with parent context.

        For chunks created with hierarchical_ingest plugin:
        - Searches using child chunks (optimized for semantic search)
        - Returns parent chunk text as the main content (better context for LLM)
        - Preserves all metadata including parent-child relationships

        Args:
            collection_id: ID of the collection to query
            query_text: The query text
            **kwargs: Additional parameters:
                - top_k: Number of results to return (default: 5)
                - threshold: Minimum similarity threshold (default: 0.0)
                - return_parent_context: Return parent text if available (default: True)
                - db: SQLAlchemy database session (required)
                - ks_plugin: Knowledge store plugin instance (required)
                - backend_collection: Backend collection handle (required)

        Returns:
            A list of dictionaries, each containing:
                - similarity: Similarity score
                - data: The parent chunk text (if available) or child chunk text
                - metadata: A dictionary including parent-child relationship info
        """
        top_k = kwargs.get("top_k", 5)
        threshold = kwargs.get("threshold", 0.0)
        return_parent_context = kwargs.get("return_parent_context", True)
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

        # Post-process: swap child text for parent text when available
        formatted_results = []
        for r in results:
            similarity = r.get("similarity", 0)
            if similarity < threshold:
                continue

            metadata = r.get("metadata", {})
            result_text = r.get("data", "")

            if return_parent_context and "parent_text" in metadata:
                result_text = metadata["parent_text"]
                print(f"DEBUG: [parent_child_query] Returning parent context for chunk "
                      f"(parent_id: {metadata.get('parent_chunk_id')}, "
                      f"child_id: {metadata.get('child_chunk_id')})")

            formatted_results.append({
                "similarity": similarity,
                "data": result_text,
                "metadata": metadata
            })

        print(f"INFO: [parent_child_query] Query completed in {elapsed_ms:.2f}ms, "
              f"returned {len(formatted_results)} results")

        return formatted_results
