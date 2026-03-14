"""
ChromaDB Knowledge Store Plugin.

Wraps ChromaDB as a retrieval backend. Handles embedding computation internally —
callers only pass chunks and metadata.
"""

import json
import logging
from typing import Dict, List, Any

from .base import KnowledgeStorePlugin, KnowledgeStoreRegistry

logger = logging.getLogger(__name__)


def _resolve_plugin_config(plugin_config: dict) -> dict:
    """Parse plugin_config if it's a string, decrypt api_key."""
    if isinstance(plugin_config, str):
        plugin_config = json.loads(plugin_config)
    # Decrypt api_key if present
    api_key = plugin_config.get("api_key", "")
    if api_key:
        try:
            from utils.encryption import decrypt_api_key
            plugin_config = {**plugin_config, "api_key": decrypt_api_key(api_key)}
        except Exception:
            pass  # Already decrypted or no encryption configured
    return plugin_config


def _get_embedding_function(plugin_config: dict):
    """Build a ChromaDB-compatible embedding function from plugin_config."""
    from database.connection import get_embedding_function_by_params
    cfg = _resolve_plugin_config(plugin_config)
    return get_embedding_function_by_params(
        vendor=cfg.get("vendor", ""),
        model_name=cfg.get("model", ""),
        api_key=cfg.get("api_key", ""),
        api_endpoint=cfg.get("api_endpoint", ""),
    )


@KnowledgeStoreRegistry.register
class ChromaDBPlugin(KnowledgeStorePlugin):
    """ChromaDB vector database plugin."""

    name = "chromadb"
    description = "Vector database with persistent storage (ChromaDB)"
    supports_embeddings = True

    def initialize(self, global_config: dict) -> None:
        pass  # ChromaDB client is managed by database.connection

    @classmethod
    def validate_plugin_config(cls, plugin_config: dict) -> dict:
        """Validate by creating an embedding function and testing it."""
        errors, warnings = [], []
        required = ["vendor", "model"]
        for field in required:
            if not plugin_config.get(field):
                errors.append(f"Missing required field: {field}")
        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        try:
            emb_func = _get_embedding_function(plugin_config)
            test_result = emb_func(["test"])
            actual_dims = len(test_result[0])
            expected_dims = plugin_config.get("embedding_dimensions")
            if expected_dims and actual_dims != expected_dims:
                errors.append(
                    f"Dimension mismatch: config says {expected_dims}, actual is {actual_dims}"
                )
        except Exception as e:
            errors.append(f"Embedding test failed: {str(e)}")

        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def _get_client(self):
        from database.connection import get_chroma_client
        return get_chroma_client()

    def create_collection(self, name: str, plugin_config: dict, metadata: dict = None):
        client = self._get_client()
        emb_func = _get_embedding_function(plugin_config)
        col_metadata = {"hnsw:space": "cosine"}
        if metadata:
            col_metadata.update(metadata)
        return client.create_collection(
            name=name, embedding_function=emb_func, metadata=col_metadata
        )

    def get_collection(self, name: str, plugin_config: dict):
        client = self._get_client()
        emb_func = _get_embedding_function(plugin_config)
        return client.get_collection(name=name, embedding_function=emb_func)

    def delete_collection(self, name: str) -> None:
        self._get_client().delete_collection(name)

    def add_chunks(
        self, collection, chunk_ids: List[str], chunk_texts: List[str],
        chunk_metadata: List[Dict] = None, plugin_config: dict = None
    ) -> None:
        kwargs = {"ids": chunk_ids, "documents": chunk_texts}
        if chunk_metadata:
            kwargs["metadatas"] = chunk_metadata
        collection.add(**kwargs)

    def query_chunks(
        self, collection, query_text: str,
        n_results: int = 10, filters: dict = None, plugin_config: dict = None
    ) -> List[Dict[str, Any]]:
        query_kwargs = {"query_texts": [query_text], "n_results": n_results}
        if filters:
            query_kwargs["where"] = filters
        results = collection.query(**query_kwargs)

        formatted = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 0
                similarity = 1.0 - distance
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                formatted.append({"similarity": similarity, "data": doc, "metadata": meta})
        return formatted

    def delete_chunks(self, collection, chunk_ids: List[str]) -> None:
        collection.delete(ids=chunk_ids)

    def count_chunks(self, collection) -> int:
        return collection.count()
