import json

from .base import KnowledgeStorePlugin, KnowledgeStoreRegistry
from .chromadb_plugin import ChromaDBPlugin


def get_knowledge_store(plugin_type: str) -> KnowledgeStorePlugin:
    """Get an initialized knowledge store plugin by type."""
    return KnowledgeStoreRegistry.get(plugin_type)


def list_knowledge_store_plugins() -> list:
    """List all registered knowledge store plugins."""
    return KnowledgeStoreRegistry.list_plugins()


def resolve_plugin_for_collection(db_collection, db) -> tuple:
    """Resolve knowledge store plugin and config for a collection.

    Handles both NEW MODE (setup reference) and OLD MODE (inline config) by
    converting OLD MODE to a chromadb plugin call.

    Args:
        db_collection: Collection model instance or dict
        db: SQLAlchemy session

    Returns:
        (plugin, plugin_config, collection_name) tuple
    """
    from database.models import KnowledgeStoreSetup

    if isinstance(db_collection, dict):
        name = db_collection.get("name", "")
        setup_id = db_collection.get("knowledge_store_setup_id")
        embeddings_model = db_collection.get("embeddings_model")
    else:
        name = db_collection.name
        setup_id = getattr(db_collection, "knowledge_store_setup_id", None)
        embeddings_model = getattr(db_collection, "embeddings_model", None)

    # NEW MODE: resolve from setup
    if setup_id:
        setup = db.query(KnowledgeStoreSetup).filter(
            KnowledgeStoreSetup.id == setup_id
        ).first()
        if setup:
            plugin_config = setup.plugin_config
            if isinstance(plugin_config, str):
                plugin_config = json.loads(plugin_config)
            plugin = get_knowledge_store(setup.plugin_type)
            return plugin, plugin_config or {}, name

    # OLD MODE: build chromadb plugin_config from inline embeddings_model
    if embeddings_model:
        if isinstance(embeddings_model, str):
            embeddings_model = json.loads(embeddings_model)
        plugin_config = {
            "vendor": embeddings_model.get("vendor", ""),
            "model": embeddings_model.get("model", ""),
            "api_key": embeddings_model.get("apikey", ""),
            "api_endpoint": embeddings_model.get("api_endpoint", ""),
        }
        plugin = get_knowledge_store("chromadb")
        return plugin, plugin_config, name

    # Fallback: chromadb with empty config (for delete operations that don't need embeddings)
    plugin = get_knowledge_store("chromadb")
    return plugin, {}, name
