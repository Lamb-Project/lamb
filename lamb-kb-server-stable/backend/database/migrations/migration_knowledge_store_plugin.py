"""
Migration: Knowledge Store Plugin Architecture

Renames embeddings_setups -> knowledge_store_setups, adds plugin_type and plugin_config
columns, migrates existing data into plugin_config JSON, and adds knowledge_store_setup_id
to collections.
"""

import json
from sqlalchemy import inspect, text

from database.connection import engine


def check_migration_status():
    """Check if the migration has already been applied."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return "knowledge_store_setups" in tables and "embeddings_setups" not in tables


def run_migration():
    """Run the knowledge store plugin migration."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.connect() as conn:
        # Step 1: Rename table if needed
        if "embeddings_setups" in tables and "knowledge_store_setups" not in tables:
            conn.execute(text("ALTER TABLE embeddings_setups RENAME TO knowledge_store_setups"))
            print("INFO: [migration] Renamed embeddings_setups -> knowledge_store_setups")

        # Refresh table list
        tables = inspect(engine).get_table_names()
        if "knowledge_store_setups" not in tables:
            print("WARNING: [migration] knowledge_store_setups table not found, skipping")
            conn.commit()
            return

        # Step 2: Add plugin_type column
        ks_columns = {col["name"] for col in inspect(engine).get_columns("knowledge_store_setups")}
        if "plugin_type" not in ks_columns:
            conn.execute(text(
                "ALTER TABLE knowledge_store_setups ADD COLUMN plugin_type TEXT NOT NULL DEFAULT 'chromadb'"
            ))
            print("INFO: [migration] Added plugin_type column")

        # Step 3: Add plugin_config column
        # Re-inspect after possible schema change
        ks_columns = {col["name"] for col in inspect(engine).get_columns("knowledge_store_setups")}
        if "plugin_config" not in ks_columns:
            conn.execute(text(
                "ALTER TABLE knowledge_store_setups ADD COLUMN plugin_config TEXT DEFAULT NULL"
            ))
            print("INFO: [migration] Added plugin_config column")

        # Step 4: Populate plugin_config from legacy columns
        rows = conn.execute(text(
            "SELECT id, vendor, api_endpoint, api_key, model_name, embedding_dimensions "
            "FROM knowledge_store_setups WHERE plugin_config IS NULL AND vendor IS NOT NULL"
        )).fetchall()

        for row in rows:
            config = {
                "vendor": row[1],
                "api_endpoint": row[2],
                "api_key": row[3],
                "model": row[4],
                "embedding_dimensions": row[5],
            }
            conn.execute(
                text("UPDATE knowledge_store_setups SET plugin_config = :config WHERE id = :id"),
                {"config": json.dumps(config), "id": row[0]}
            )
        if rows:
            print(f"INFO: [migration] Populated plugin_config for {len(rows)} setups")

        # Step 5: Add knowledge_store_setup_id column to collections
        coll_columns = {col["name"] for col in inspect(engine).get_columns("collections")}
        if "knowledge_store_setup_id" not in coll_columns:
            conn.execute(text(
                "ALTER TABLE collections ADD COLUMN knowledge_store_setup_id INTEGER "
                "REFERENCES knowledge_store_setups(id)"
            ))
            print("INFO: [migration] Added knowledge_store_setup_id to collections")

        # Step 6: Copy embeddings_setup_id -> knowledge_store_setup_id
        if "embeddings_setup_id" in coll_columns:
            conn.execute(text(
                "UPDATE collections SET knowledge_store_setup_id = embeddings_setup_id "
                "WHERE knowledge_store_setup_id IS NULL AND embeddings_setup_id IS NOT NULL"
            ))
            print("INFO: [migration] Copied embeddings_setup_id -> knowledge_store_setup_id")

        # Step 7: Create indexes for performance
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_collections_knowledge_store_setup "
                "ON collections(knowledge_store_setup_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_store_setups_org_plugin "
                "ON knowledge_store_setups(organization_id, plugin_type)"
            ))
            print("INFO: [migration] Created indexes")
        except Exception as idx_e:
            print(f"WARNING: [migration] Index creation skipped: {idx_e}")

        conn.commit()
        print("INFO: [migration] Knowledge store plugin migration completed")
