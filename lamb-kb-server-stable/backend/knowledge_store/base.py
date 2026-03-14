"""
Knowledge Store Plugin base interface and registry.

Defines the technology-agnostic interface that all retrieval backends must implement.
"""

import abc
import logging
from typing import Dict, List, Type, Any, Optional

logger = logging.getLogger(__name__)


class KnowledgeStorePlugin(abc.ABC):
    """Technology-agnostic interface for retrieval backends.

    Plugins work with chunks and metadata only.
    Embedding computation, graph construction, indexing, etc. are internal to each plugin.
    """
    name: str = ""
    description: str = ""
    supports_embeddings: bool = False
    supports_metadata: bool = True

    @abc.abstractmethod
    def initialize(self, global_config: dict) -> None:
        """One-time initialization (e.g. storage paths)."""

    @classmethod
    @abc.abstractmethod
    def validate_plugin_config(cls, plugin_config: dict) -> dict:
        """Validate a plugin_config dict. Returns {"valid": bool, "errors": [], "warnings": []}."""

    @abc.abstractmethod
    def create_collection(self, name: str, plugin_config: dict, metadata: dict = None) -> Any:
        """Create a backend collection. Returns a handle used by other methods."""

    @abc.abstractmethod
    def get_collection(self, name: str, plugin_config: dict) -> Any:
        """Get an existing backend collection by name."""

    @abc.abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete a backend collection."""

    @abc.abstractmethod
    def add_chunks(
        self, collection, chunk_ids: List[str], chunk_texts: List[str],
        chunk_metadata: List[Dict] = None, plugin_config: dict = None
    ) -> None:
        """Add chunks. The plugin decides how to process them (embed, index, graph, etc.)."""

    @abc.abstractmethod
    def query_chunks(
        self, collection, query_text: str,
        n_results: int = 10, filters: dict = None, plugin_config: dict = None
    ) -> List[Dict[str, Any]]:
        """Query chunks. Returns list of {similarity, data, metadata}."""

    @abc.abstractmethod
    def delete_chunks(self, collection, chunk_ids: List[str]) -> None:
        """Delete specific chunks by ID."""

    @abc.abstractmethod
    def count_chunks(self, collection) -> int:
        """Count chunks in a collection."""


class KnowledgeStoreRegistry:
    """Registry for knowledge store plugins."""
    _plugins: Dict[str, KnowledgeStorePlugin] = {}

    @classmethod
    def register(cls, plugin_class: Type[KnowledgeStorePlugin]):
        """Register a plugin class. Can be used as a decorator."""
        instance = plugin_class()
        cls._plugins[instance.name] = instance
        logger.info("Registered knowledge store plugin: %s", instance.name)
        return plugin_class

    @classmethod
    def get(cls, plugin_type: str) -> KnowledgeStorePlugin:
        """Get a plugin instance by type name."""
        plugin = cls._plugins.get(plugin_type)
        if not plugin:
            available = list(cls._plugins.keys())
            raise ValueError(f"Unknown plugin type '{plugin_type}'. Available: {available}")
        return plugin

    @classmethod
    def list_plugins(cls) -> List[Dict[str, Any]]:
        """List all registered plugins with metadata."""
        return [
            {
                "plugin_type": p.name,
                "description": p.description,
                "supports_embeddings": p.supports_embeddings,
                "supports_metadata": p.supports_metadata,
            }
            for p in cls._plugins.values()
        ]
