from .base import KnowledgeStorePlugin, KnowledgeStoreRegistry
from .chromadb_plugin import ChromaDBPlugin


def get_knowledge_store(plugin_type: str) -> KnowledgeStorePlugin:
    """Get an initialized knowledge store plugin by type."""
    return KnowledgeStoreRegistry.get(plugin_type)


def list_knowledge_store_plugins() -> list:
    """List all registered knowledge store plugins."""
    return KnowledgeStoreRegistry.list_plugins()
