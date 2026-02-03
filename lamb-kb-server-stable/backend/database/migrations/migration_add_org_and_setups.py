"""
Migration: Add Organizations and Embeddings Setups tables.

This migration adds:
1. organizations table - for organization-level management
2. embeddings_setups table - for reusable embeddings configurations
3. New columns to collections table:
   - organization_id (FK to organizations)
   - embeddings_setup_id (FK to embeddings_setups)
   - embedding_dimensions (stores locked dimension value)

This maintains backward compatibility by keeping the existing embeddings_model column.
"""

from sqlalchemy import text, inspect


def check_migration_status():
    """Check if migration has already been applied."""
    from database.connection import engine

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Migration is complete if all new tables and columns exist
    if "organizations" not in existing_tables:
        return False

    if "embeddings_setups" not in existing_tables:
        return False

    # Check if collection table has new columns
    existing_columns = {col["name"] for col in inspector.get_columns("collections")}
    required_columns = {"organization_id", "embeddings_setup_id", "embedding_dimensions"}

    if not required_columns.issubset(existing_columns):
        return False

    return True


def run_migration():
    """Execute the migration."""
    from database.connection import engine

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.begin() as conn:
        # ═══════════════════════════════════════════════════════════════════════════
        # Create organizations table
        # ═══════════════════════════════════════════════════════════════════════════
        if "organizations" not in existing_tables:
            print("  Creating organizations table...")
            conn.execute(text("""
                CREATE TABLE organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    config TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX idx_organizations_external_id ON organizations(external_id)"))
            print("  ✓ organizations table created")

        # ═══════════════════════════════════════════════════════════════════════════
        # Create embeddings_setups table
        # ═══════════════════════════════════════════════════════════════════════════
        if "embeddings_setups" not in existing_tables:
            print("  Creating embeddings_setups table...")
            conn.execute(text("""
                CREATE TABLE embeddings_setups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    setup_key TEXT NOT NULL,
                    description TEXT,
                    vendor TEXT NOT NULL,
                    api_endpoint TEXT,
                    api_key TEXT,
                    model_name TEXT NOT NULL,
                    embedding_dimensions INTEGER NOT NULL,
                    is_default INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    UNIQUE(organization_id, setup_key)
                )
            """))
            conn.execute(text("CREATE INDEX idx_embeddings_setups_org ON embeddings_setups(organization_id)"))
            print("  ✓ embeddings_setups table created")

        # ═══════════════════════════════════════════════════════════════════════════
        # Add new columns to collections table
        # ═══════════════════════════════════════════════════════════════════════════
        existing_columns = {col["name"] for col in inspector.get_columns("collections")}

        if "organization_id" not in existing_columns:
            print("  Adding organization_id column to collections...")
            conn.execute(text("ALTER TABLE collections ADD COLUMN organization_id INTEGER"))
            conn.execute(text("CREATE INDEX idx_collections_org ON collections(organization_id)"))
            print("  ✓ organization_id column added")

        if "embeddings_setup_id" not in existing_columns:
            print("  Adding embeddings_setup_id column to collections...")
            conn.execute(text("ALTER TABLE collections ADD COLUMN embeddings_setup_id INTEGER"))
            conn.execute(text("CREATE INDEX idx_collections_setup ON collections(embeddings_setup_id)"))
            print("  ✓ embeddings_setup_id column added")

        if "embedding_dimensions" not in existing_columns:
            print("  Adding embedding_dimensions column to collections...")
            conn.execute(text("ALTER TABLE collections ADD COLUMN embedding_dimensions INTEGER"))
            print("  ✓ embedding_dimensions column added")

    print("✓ Migration completed successfully")


if __name__ == "__main__":
    if check_migration_status():
        print("Migration already applied.")
    else:
        print("Running migration: Add Organizations and Embeddings Setups...")
        run_migration()
