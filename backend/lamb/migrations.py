"""
Database migration system for LAMB.

Uses a schema_version table to track applied migrations, ensuring each
migration runs exactly once across all workers and processes. Migrations
are idempotent by design (using IF NOT EXISTS / PRAGMA table_info guards).

The MigrationRunner is called from:
  1. LambDatabaseManager.__init__ (with a class-level guard, once per process)
  2. main.py lifespan startup (belt-and-suspenders, idempotent)

To add a new migration:
  1. Add a new method _migration_{N} below
  2. Increment LATEST_VERSION
"""

import time
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MIGRATIONS")

# Increment this when adding a new migration method below.
LATEST_VERSION = 29


class MigrationRunner:
    """Runs database migrations with version tracking via schema_version table."""

    def __init__(self, db_manager):
        """
        Args:
            db_manager: LambDatabaseManager instance (provides get_connection()
                        and table_prefix).
        """
        self.db = db_manager
        self._owi_db = None  # Lazy-loaded OWI DB for password migration

    # ── Public API ──────────────────────────────────────────────────────

    def apply_all(self):
        """Apply all pending migrations in order. Idempotent — safe to call
        any number of times from any number of processes/workers."""
        connection = self.db.get_connection()
        if not connection:
            logger.error(
                "Could not establish database connection for migrations")
            return

        try:
            with connection:
                cursor = connection.cursor()

                self._ensure_schema_version_table(cursor)
                current_version = self._get_current_version(cursor)

                if current_version >= LATEST_VERSION:
                    logger.debug(
                        f"Schema up to date (v{current_version}), no migrations needed")
                    return

                logger.info(
                    f"Running migrations: current=v{current_version}, "
                    f"latest=v{LATEST_VERSION}")

                for version in range(current_version + 1, LATEST_VERSION + 1):
                    method = getattr(self, f'_migration_{version}', None)
                    if method is None:
                        logger.error(
                            f"Migration {version} method not found — "
                            f"skipping. Did you forget to implement _migration_{version}?")
                        continue

                    logger.info(f"Applying migration {version}...")
                    method(cursor)
                    self._record_version(cursor, version)
                    logger.info(f"Migration {version} complete")

                connection.commit()
                logger.info(
                    f"All migrations applied. Schema now at v{LATEST_VERSION}.")

        except Exception as e:
            logger.error(f"Migration error: {e}")
            raise
        finally:
            # Clean up OWI connection if it was opened
            if self._owi_db is not None:
                try:
                    owi_conn = self._owi_db.get_connection()
                    if owi_conn:
                        owi_conn.close()
                except Exception:
                    pass
                self._owi_db = None

    # ── Schema version tracking ─────────────────────────────────────────

    def _ensure_schema_version_table(self, cursor):
        """Create the schema_version tracking table if it doesn't exist."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.db.table_prefix}schema_version (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
        """)

    def _get_current_version(self, cursor) -> int:
        """Return the highest applied migration version, or 0 if none."""
        cursor.execute(
            f"SELECT COALESCE(MAX(version), 0) "
            f"FROM {self.db.table_prefix}schema_version")
        row = cursor.fetchone()
        return row[0] if row else 0

    def _record_version(self, cursor, version: int):
        """Record that a migration version has been applied."""
        cursor.execute(
            f"INSERT OR IGNORE INTO {self.db.table_prefix}schema_version "
            f"(version, applied_at) VALUES (?, ?)",
            (version, int(time.time()))
        )

    # ── Helper ──────────────────────────────────────────────────────────

    def _column_exists(self, cursor, table: str, column: str) -> bool:
        """Check if a column exists in a table."""
        cursor.execute(f"PRAGMA table_info({self.db.table_prefix}{table})")
        return column in {row[1] for row in cursor.fetchall()}

    def _table_exists(self, cursor, table: str) -> bool:
        """Check if a table exists."""
        cursor.execute(
            f"SELECT name FROM sqlite_master "
            f"WHERE type='table' AND name='{self.db.table_prefix}{table}'")
        return cursor.fetchone() is not None

    # ══════════════════════════════════════════════════════════════════════
    #  Migration methods  (numbered sequentially, applied in order)
    # ══════════════════════════════════════════════════════════════════════

    def _migration_1(self, cursor):
        """Add user_type column to Creator_users."""
        if self._column_exists(cursor, 'Creator_users', 'user_type'):
            return
        logger.info("Adding user_type column to Creator_users table")
        cursor.execute(f"""
            ALTER TABLE {self.db.table_prefix}Creator_users
            ADD COLUMN user_type TEXT NOT NULL DEFAULT 'creator'
            CHECK(user_type IN ('creator', 'end_user'))
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}creator_users_type "
            f"ON {self.db.table_prefix}Creator_users(user_type)")

    def _migration_2(self, cursor):
        """Create rubrics table."""
        if self._table_exists(cursor, 'rubrics'):
            return
        logger.info("Creating rubrics table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}rubrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rubric_id TEXT UNIQUE NOT NULL,
                organization_id INTEGER NOT NULL,
                owner_email TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                rubric_data JSON NOT NULL,
                is_public BOOLEAN DEFAULT FALSE,
                is_showcase BOOLEAN DEFAULT FALSE,
                parent_rubric_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (parent_rubric_id)
                    REFERENCES {self.db.table_prefix}rubrics(rubric_id)
                    ON DELETE SET NULL
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.db.table_prefix}rubrics_owner "
            f"ON {self.db.table_prefix}rubrics(owner_email)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.db.table_prefix}rubrics_org "
            f"ON {self.db.table_prefix}rubrics(organization_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.db.table_prefix}rubrics_rubric_id "
            f"ON {self.db.table_prefix}rubrics(rubric_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.db.table_prefix}rubrics_public "
            f"ON {self.db.table_prefix}rubrics(is_public)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.db.table_prefix}rubrics_showcase "
            f"ON {self.db.table_prefix}rubrics(is_showcase)")

    def _migration_3(self, cursor):
        """Create prompt_templates table."""
        if self._table_exists(cursor, 'prompt_templates'):
            return
        logger.info("Creating prompt_templates table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                owner_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                system_prompt TEXT,
                prompt_template TEXT,
                is_shared BOOLEAN DEFAULT FALSE,
                metadata JSON,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (owner_email)
                    REFERENCES {self.db.table_prefix}Creator_users(user_email)
                    ON DELETE CASCADE,
                UNIQUE(organization_id, owner_email, name)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}prompt_templates_org_shared "
            f"ON {self.db.table_prefix}prompt_templates(organization_id, is_shared)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}prompt_templates_owner "
            f"ON {self.db.table_prefix}prompt_templates(owner_email)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}prompt_templates_name "
            f"ON {self.db.table_prefix}prompt_templates(name)")

    def _migration_4(self, cursor):
        """Add enabled column to Creator_users."""
        if self._column_exists(cursor, 'Creator_users', 'enabled'):
            return
        logger.info("Adding enabled column to Creator_users table")
        cursor.execute(f"""
            ALTER TABLE {self.db.table_prefix}Creator_users
            ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}creator_users_enabled "
            f"ON {self.db.table_prefix}Creator_users(enabled)")

    def _migration_5(self, cursor):
        """Create kb_registry table."""
        if self._table_exists(cursor, 'kb_registry'):
            return
        logger.info("Creating kb_registry table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}kb_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kb_id TEXT NOT NULL UNIQUE,
                kb_name TEXT NOT NULL,
                owner_user_id INTEGER NOT NULL,
                organization_id INTEGER NOT NULL,
                is_shared BOOLEAN DEFAULT FALSE,
                metadata JSON,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (owner_user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
                    ON DELETE CASCADE
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}kb_registry_owner "
            f"ON {self.db.table_prefix}kb_registry(owner_user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}kb_registry_org_shared "
            f"ON {self.db.table_prefix}kb_registry(organization_id, is_shared)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}kb_registry_kb_id "
            f"ON {self.db.table_prefix}kb_registry(kb_id)")

    def _migration_6(self, cursor):
        """Create bulk_import_logs table."""
        if self._table_exists(cursor, 'bulk_import_logs'):
            return
        logger.info("Creating bulk_import_logs table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}bulk_import_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                admin_user_id INTEGER,
                admin_email TEXT NOT NULL,
                operation_type TEXT NOT NULL
                    CHECK(operation_type IN
                        ('user_creation','user_activation','user_deactivation')),
                total_count INTEGER NOT NULL,
                success_count INTEGER NOT NULL,
                failure_count INTEGER NOT NULL,
                details JSON,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (admin_user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE SET NULL
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}bulk_import_logs_org "
            f"ON {self.db.table_prefix}bulk_import_logs(organization_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}bulk_import_logs_admin "
            f"ON {self.db.table_prefix}bulk_import_logs(admin_user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}bulk_import_logs_created "
            f"ON {self.db.table_prefix}bulk_import_logs(created_at)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}bulk_import_logs_type "
            f"ON {self.db.table_prefix}bulk_import_logs(operation_type)")

    def _migration_7(self, cursor):
        """Create assistant_shares table."""
        if self._table_exists(cursor, 'assistant_shares'):
            return
        logger.info("Creating assistant_shares table")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.db.table_prefix}assistant_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assistant_id INTEGER NOT NULL,
                shared_with_user_id INTEGER NOT NULL,
                shared_by_user_id INTEGER NOT NULL,
                shared_at INTEGER NOT NULL,
                FOREIGN KEY (assistant_id)
                    REFERENCES {self.db.table_prefix}assistants(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (shared_with_user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (shared_by_user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE CASCADE,
                UNIQUE(assistant_id, shared_with_user_id)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}assistant_shares_assistant "
            f"ON {self.db.table_prefix}assistant_shares(assistant_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}assistant_shares_shared_with "
            f"ON {self.db.table_prefix}assistant_shares(shared_with_user_id)")

    def _migration_8(self, cursor):
        """Create lamb_chats table for internal chat persistence."""
        if self._table_exists(cursor, 'lamb_chats'):
            return
        logger.info("Creating lamb_chats table for internal chat persistence")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lamb_chats (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                assistant_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                chat JSON NOT NULL DEFAULT '{{"history": {{"messages": {{}}}}}}',
                archived INTEGER DEFAULT 0,
                FOREIGN KEY (user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (assistant_id)
                    REFERENCES {self.db.table_prefix}assistants(id)
                    ON DELETE CASCADE
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lamb_chats_user "
            f"ON {self.db.table_prefix}lamb_chats(user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lamb_chats_assistant "
            f"ON {self.db.table_prefix}lamb_chats(assistant_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lamb_chats_user_assistant "
            f"ON {self.db.table_prefix}lamb_chats(user_id, assistant_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lamb_chats_updated "
            f"ON {self.db.table_prefix}lamb_chats(updated_at)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lamb_chats_archived "
            f"ON {self.db.table_prefix}lamb_chats(archived)")

    def _migration_9(self, cursor):
        """Add LTI creator user fields (lti_user_id, auth_provider) to Creator_users."""
        tp = self.db.table_prefix
        if not self._column_exists(cursor, 'Creator_users', 'lti_user_id'):
            logger.info("Adding lti_user_id column to Creator_users table")
            cursor.execute(
                f"ALTER TABLE {tp}Creator_users ADD COLUMN lti_user_id TEXT")

        if not self._column_exists(cursor, 'Creator_users', 'auth_provider'):
            logger.info("Adding auth_provider column to Creator_users table")
            cursor.execute(
                f"ALTER TABLE {tp}Creator_users "
                f"ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'password'")

        cursor.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_{tp}creator_users_org_lti
            ON {tp}Creator_users(organization_id, lti_user_id)
            WHERE lti_user_id IS NOT NULL
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS
            idx_{tp}creator_users_lti_user_id
            ON {tp}Creator_users(lti_user_id)
            WHERE lti_user_id IS NOT NULL
        """)

    def _migration_10(self, cursor):
        """Create lti_creator_keys table for org LTI consumer keys."""
        if self._table_exists(cursor, 'lti_creator_keys'):
            return
        logger.info("Creating lti_creator_keys table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_creator_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL UNIQUE,
                oauth_consumer_key TEXT NOT NULL UNIQUE,
                oauth_consumer_secret TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
                    ON DELETE CASCADE
            )
        """)
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_creator_keys_consumer_key "
            f"ON {self.db.table_prefix}lti_creator_keys(oauth_consumer_key)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_creator_keys_org "
            f"ON {self.db.table_prefix}lti_creator_keys(organization_id)")

    def _migration_11(self, cursor):
        """Create lti_global_config table (singleton for global LTI key/secret)."""
        if self._table_exists(cursor, 'lti_global_config'):
            return
        logger.info("Creating lti_global_config table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_global_config (
                id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                oauth_consumer_key TEXT NOT NULL,
                oauth_consumer_secret TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                updated_by TEXT
            )
        """)

    def _migration_12(self, cursor):
        """Create lti_activities table."""
        if self._table_exists(cursor, 'lti_activities'):
            return
        logger.info("Creating lti_activities table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_link_id TEXT NOT NULL UNIQUE,
                organization_id INTEGER NOT NULL,
                context_id TEXT,
                context_title TEXT,
                activity_name TEXT,
                owi_group_id TEXT NOT NULL,
                owi_group_name TEXT NOT NULL,
                owner_email TEXT NOT NULL,
                owner_name TEXT,
                configured_by_email TEXT NOT NULL,
                configured_by_name TEXT,
                chat_visibility_enabled INTEGER NOT NULL DEFAULT 0,
                activity_type TEXT NOT NULL DEFAULT 'chat',
                setup_config TEXT DEFAULT '{{}}',
                lis_outcome_service_url TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {self.db.table_prefix}organizations(id)
            )
        """)
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_activities_resource_link "
            f"ON {self.db.table_prefix}lti_activities(resource_link_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_activities_org "
            f"ON {self.db.table_prefix}lti_activities(organization_id)")

    def _migration_13(self, cursor):
        """Add owner_email, owner_name, chat_visibility_enabled to lti_activities
        (for databases where the table was created before these columns existed)."""
        tp = self.db.table_prefix
        if not self._table_exists(cursor, 'lti_activities'):
            return
        existing_cols = set()
        cursor.execute(f"PRAGMA table_info({tp}lti_activities)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if 'owner_email' in existing_cols:
            return  # Already migrated
        logger.info(
            "Migrating lti_activities: adding owner_email, owner_name, "
            "chat_visibility_enabled")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activities "
            f"ADD COLUMN owner_email TEXT NOT NULL DEFAULT ''")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activities "
            f"ADD COLUMN owner_name TEXT")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activities "
            f"ADD COLUMN chat_visibility_enabled INTEGER NOT NULL DEFAULT 0")
        # Backfill owner_email from configured_by_email
        cursor.execute(
            f"UPDATE {tp}lti_activities "
            f"SET owner_email = configured_by_email, owner_name = configured_by_name "
            f"WHERE owner_email = ''")

    def _migration_14(self, cursor):
        """Create lti_activity_assistants junction table."""
        if self._table_exists(cursor, 'lti_activity_assistants'):
            return
        logger.info("Creating lti_activity_assistants table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_activity_assistants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                assistant_id INTEGER NOT NULL,
                added_at INTEGER NOT NULL,
                FOREIGN KEY (activity_id)
                    REFERENCES {self.db.table_prefix}lti_activities(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (assistant_id)
                    REFERENCES {self.db.table_prefix}assistants(id)
                    ON DELETE CASCADE,
                UNIQUE(activity_id, assistant_id)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_activity_assistants_activity "
            f"ON {self.db.table_prefix}lti_activity_assistants(activity_id)")

    def _migration_15(self, cursor):
        """Create lti_activity_users table."""
        if self._table_exists(cursor, 'lti_activity_users'):
            return
        logger.info("Creating lti_activity_users table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_activity_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                user_name TEXT NOT NULL DEFAULT '',
                user_display_name TEXT NOT NULL DEFAULT '',
                lms_user_id TEXT,
                owi_user_id TEXT,
                consent_given_at INTEGER,
                last_access_at INTEGER,
                access_count INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (activity_id)
                    REFERENCES {self.db.table_prefix}lti_activities(id)
                    ON DELETE CASCADE,
                UNIQUE(user_email, activity_id)
            )
        """)

    def _migration_16(self, cursor):
        """Add dashboard columns (owi_user_id, consent_given_at, last_access_at,
        access_count) to lti_activity_users for pre-existing tables."""
        tp = self.db.table_prefix
        if not self._table_exists(cursor, 'lti_activity_users'):
            return
        if self._column_exists(cursor, 'lti_activity_users', 'owi_user_id'):
            return
        logger.info(
            "Migrating lti_activity_users: adding owi_user_id, "
            "consent_given_at, last_access_at, access_count")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activity_users ADD COLUMN owi_user_id TEXT")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activity_users "
            f"ADD COLUMN consent_given_at INTEGER")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activity_users "
            f"ADD COLUMN last_access_at INTEGER")
        cursor.execute(
            f"ALTER TABLE {tp}lti_activity_users "
            f"ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0")

    def _migration_17(self, cursor):
        """Create lti_identity_links table."""
        if self._table_exists(cursor, 'lti_identity_links'):
            return
        logger.info("Creating lti_identity_links table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}lti_identity_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_user_id TEXT NOT NULL,
                lms_email TEXT,
                creator_user_id INTEGER NOT NULL,
                linked_at INTEGER NOT NULL,
                FOREIGN KEY (creator_user_id)
                    REFERENCES {self.db.table_prefix}Creator_users(id)
                    ON DELETE CASCADE
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_identity_lms_user "
            f"ON {self.db.table_prefix}lti_identity_links(lms_user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}lti_identity_lms_email "
            f"ON {self.db.table_prefix}lti_identity_links(lms_email)")

    def _migration_18(self, cursor):
        """Add password_hash and role columns to Creator_users."""
        tp = self.db.table_prefix
        if not self._column_exists(cursor, 'Creator_users', 'password_hash'):
            logger.info("Adding password_hash column to Creator_users")
            cursor.execute(
                f"ALTER TABLE {tp}Creator_users ADD COLUMN password_hash TEXT")

        if not self._column_exists(cursor, 'Creator_users', 'role'):
            logger.info("Adding role column to Creator_users")
            cursor.execute(
                f"ALTER TABLE {tp}Creator_users "
                f"ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    def _migration_19(self, cursor):
        """Copy password hashes and roles from OWI database to Creator_users.

        NOTE: This is an expensive migration — it opens a connection to the
        OWI database. The schema_version table ensures it only runs once.
        """
        tp = self.db.table_prefix
        cursor.execute(f"""
            SELECT id, user_email FROM {tp}Creator_users
            WHERE auth_provider = 'password' AND password_hash IS NULL
        """)
        users_to_migrate = cursor.fetchall()

        if not users_to_migrate:
            logger.info("Migration 19: No users need OWI hash migration")
            return

        logger.info(
            f"Migration 19: Migrating {len(users_to_migrate)} "
            f"password hashes from OWI")

        try:
            from .owi_bridge.owi_database import OwiDatabaseManager
            owi_db = OwiDatabaseManager()
            owi_conn = owi_db.get_connection()

            if not owi_conn:
                logger.warning(
                    "Migration 19: Could not connect to OWI DB, "
                    "skipping hash migration")
                return

            try:
                owi_cursor = owi_conn.cursor()
                for user_id, user_email in users_to_migrate:
                    try:
                        owi_cursor.execute(
                            "SELECT password FROM auth WHERE email = ?",
                            (user_email,))
                        auth_row = owi_cursor.fetchone()

                        owi_cursor.execute(
                            "SELECT role FROM user WHERE email = ?",
                            (user_email,))
                        role_row = owi_cursor.fetchone()

                        pw_hash = auth_row[0] if auth_row else None
                        owi_role = role_row[0] if role_row else 'user'

                        if pw_hash:
                            cursor.execute(
                                f"UPDATE {tp}Creator_users "
                                f"SET password_hash = ?, role = ? "
                                f"WHERE id = ?",
                                (pw_hash, owi_role, user_id))
                            logger.debug(f"Migrated hash for {user_email}")
                    except Exception as row_err:
                        logger.warning(
                            f"Migration 19: Skipping {user_email}: {row_err}")
            finally:
                owi_conn.close()

            logger.info("Migration 19 (OWI password) complete")
        except Exception as owi_err:
            logger.warning(
                f"Migration 19: OWI DB unavailable, skipping: {owi_err}")

    def _migration_20(self, cursor):
        """Add model_name + provider columns to usage_logs, create model_pricing
        table with seed data, and add assistant index on usage_logs."""
        tp = self.db.table_prefix

        if not self._column_exists(cursor, 'usage_logs', 'model_name'):
            logger.info("Adding model_name column to usage_logs")
            cursor.execute(
                f"ALTER TABLE {tp}usage_logs ADD COLUMN model_name TEXT")

        if not self._column_exists(cursor, 'usage_logs', 'provider'):
            logger.info("Adding provider column to usage_logs")
            cursor.execute(
                f"ALTER TABLE {tp}usage_logs ADD COLUMN provider TEXT")

        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tp}usage_logs_assistant
            ON {tp}usage_logs(assistant_id)
        """)

        if self._table_exists(cursor, 'model_pricing'):
            return

        logger.info("Creating model_pricing table")
        cursor.execute(f"""
            CREATE TABLE {tp}model_pricing (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                provider      TEXT NOT NULL,
                model_name    TEXT NOT NULL,
                input_per_1m  REAL NOT NULL DEFAULT 0,
                output_per_1m REAL NOT NULL DEFAULT 0,
                notes         TEXT,
                updated_at    INTEGER NOT NULL,
                UNIQUE(provider, model_name)
            )
        """)
        now = int(time.time())
        seed_rows = [
            ("openai", "gpt-4.1",                      2.00,  8.00),
            ("openai", "gpt-4.1-mini",                 0.40,  1.60),
            ("openai", "gpt-4.1-nano",                 0.10,  0.40),
            ("openai", "gpt-4o",                       2.50, 10.00),
            ("openai", "gpt-4o-mini",                  0.15,  0.60),
            ("openai", "gpt-4-turbo",                 10.00, 30.00),
            ("openai", "gpt-4",                       30.00, 60.00),
            ("openai", "o3-mini",                      1.10,  4.40),
            ("anthropic", "claude-3-5-sonnet-20241022", 3.00, 15.00),
            ("anthropic", "claude-3-5-haiku-20241022",  0.80,  4.00),
        ]
        cursor.executemany(
            f"INSERT OR IGNORE INTO {tp}model_pricing "
            f"(provider, model_name, input_per_1m, output_per_1m, updated_at) "
            f"VALUES (?, ?, ?, ?, ?)",
            [(p, m, i, o, now) for p, m, i, o in seed_rows]
        )

    def _migration_21(self, cursor):
        """Create assistant_usage_totals and assistant_quota_alerts tables,
        and backfill usage totals from existing usage_logs.

        NOTE: The backfill is an expensive aggregation query. The schema_version
        table ensures it only runs once.
        """
        tp = self.db.table_prefix

        logger.info("Creating assistant_usage_totals table if not exists")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}assistant_usage_totals (
                assistant_id INTEGER PRIMARY KEY,
                prompt_tokens_total INTEGER DEFAULT 0,
                completion_tokens_total INTEGER DEFAULT 0,
                total_tokens_total INTEGER DEFAULT 0,
                cost_usd_total REAL DEFAULT 0.0,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (assistant_id)
                    REFERENCES {tp}assistants(id) ON DELETE CASCADE
            )
        """)

        logger.info("Creating assistant_quota_alerts table if not exists")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}assistant_quota_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assistant_id INTEGER UNIQUE NOT NULL,
                quota_limit_usd REAL,
                thresholds_config JSON,
                current_alert_level INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT 0,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (assistant_id)
                    REFERENCES {tp}assistants(id) ON DELETE CASCADE
            )
        """)

        logger.info(
            "Backfilling assistant_usage_totals from usage_logs")
        cursor.execute(f"""
            INSERT INTO {tp}assistant_usage_totals (
                assistant_id,
                prompt_tokens_total,
                completion_tokens_total,
                total_tokens_total,
                cost_usd_total,
                updated_at
            )
            SELECT
                a.id AS assistant_id,
                COALESCE(SUM(
                    json_extract(ul.usage_data, '$.prompt_tokens')), 0
                ) AS prompt_tokens_total,
                COALESCE(SUM(
                    json_extract(ul.usage_data, '$.completion_tokens')), 0
                ) AS completion_tokens_total,
                COALESCE(SUM(
                    json_extract(ul.usage_data, '$.total_tokens')), 0
                ) AS total_tokens_total,
                COALESCE(SUM(
                    COALESCE(
                        json_extract(ul.usage_data, '$.prompt_tokens'), 0
                    ) * COALESCE(mp.input_per_1m, 0) / 1000000.0
                    +
                    COALESCE(
                        json_extract(ul.usage_data, '$.completion_tokens'), 0
                    ) * COALESCE(mp.output_per_1m, 0) / 1000000.0
                ), 0.0) AS cost_usd_total,
                strftime('%s', 'now') AS updated_at
            FROM {tp}assistants a
            JOIN {tp}usage_logs ul ON ul.assistant_id = a.id
            LEFT JOIN {tp}model_pricing mp
                ON ul.model_name = mp.model_name
                AND ul.provider = mp.provider
            GROUP BY a.id
            ON CONFLICT(assistant_id) DO UPDATE SET
                prompt_tokens_total = excluded.prompt_tokens_total,
                completion_tokens_total = excluded.completion_tokens_total,
                total_tokens_total = excluded.total_tokens_total,
                cost_usd_total = excluded.cost_usd_total,
                updated_at = excluded.updated_at
        """)

    def _migration_22(self, cursor):
        """Create aac_sessions table."""
        if self._table_exists(cursor, 'aac_sessions'):
            return
        logger.info("Creating aac_sessions table")
        cursor.execute(f"""
            CREATE TABLE {self.db.table_prefix}aac_sessions (
                id TEXT PRIMARY KEY,
                assistant_id INTEGER,
                user_email TEXT NOT NULL,
                organization_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                conversation TEXT DEFAULT '[]',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{self.db.table_prefix}aac_sessions_user "
            f"ON {self.db.table_prefix}aac_sessions(user_email)")

    def _migration_23(self, cursor):
        """Add title column to aac_sessions."""
        tp = self.db.table_prefix
        if not self._table_exists(cursor, 'aac_sessions'):
            return
        if self._column_exists(cursor, 'aac_sessions', 'title'):
            return
        logger.info("Adding title column to aac_sessions")
        cursor.execute(
            f"ALTER TABLE {tp}aac_sessions "
            f"ADD COLUMN title TEXT DEFAULT ''")

    def _migration_24(self, cursor):
        """Create assistant test scenario, run, and evaluation tables."""
        tp = self.db.table_prefix
        if self._table_exists(cursor, 'assistant_test_scenarios'):
            return
        logger.info(
            "Creating test scenarios, runs, and evaluations tables")

        cursor.execute(f"""
            CREATE TABLE {tp}assistant_test_scenarios (
                id TEXT PRIMARY KEY,
                assistant_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                scenario_type TEXT DEFAULT 'single_turn',
                messages TEXT NOT NULL,
                expected_behavior TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_by TEXT NOT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}test_scenarios_assistant "
            f"ON {tp}assistant_test_scenarios(assistant_id)")

        cursor.execute(f"""
            CREATE TABLE {tp}assistant_test_runs (
                id TEXT PRIMARY KEY,
                assistant_id INTEGER NOT NULL,
                scenario_id TEXT,
                input_messages TEXT NOT NULL,
                output TEXT NOT NULL,
                token_usage TEXT,
                assistant_snapshot TEXT,
                model_used TEXT,
                elapsed_ms REAL,
                created_at TIMESTAMP
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}test_runs_assistant "
            f"ON {tp}assistant_test_runs(assistant_id)")

        cursor.execute(f"""
            CREATE TABLE {tp}assistant_test_evaluations (
                id TEXT PRIMARY KEY,
                test_run_id TEXT NOT NULL,
                evaluator TEXT NOT NULL,
                verdict TEXT,
                notes TEXT DEFAULT '',
                dimensions TEXT,
                confirmed_by_user BOOLEAN,
                created_at TIMESTAMP
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}test_evals_run "
            f"ON {tp}assistant_test_evaluations(test_run_id)")

    def _migration_25(self, cursor):
        """Create library tables (libraries, library_items) and audit_log."""
        tp = self.db.table_prefix

        logger.info("Creating library tables if not exist")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}libraries (
                id TEXT PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                owner_user_id INTEGER NOT NULL,
                is_shared INTEGER DEFAULT 0,
                import_config TEXT,
                status TEXT DEFAULT 'active',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {tp}organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_user_id)
                    REFERENCES {tp}Creator_users(id),
                UNIQUE(organization_id, name)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}libraries_owner "
            f"ON {tp}libraries(owner_user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}libraries_org_shared "
            f"ON {tp}libraries(organization_id, is_shared)")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}library_items (
                id TEXT PRIMARY KEY,
                library_id TEXT NOT NULL,
                organization_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                original_filename TEXT,
                content_type TEXT,
                file_size INTEGER,
                source_url TEXT,
                import_plugin TEXT NOT NULL,
                import_params TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                uploader_user_id INTEGER NOT NULL,
                metadata TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (library_id)
                    REFERENCES {tp}libraries(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id)
                    REFERENCES {tp}organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (uploader_user_id)
                    REFERENCES {tp}Creator_users(id)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}library_items_library "
            f"ON {tp}library_items(library_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}library_items_org "
            f"ON {tp}library_items(organization_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}library_items_status "
            f"ON {tp}library_items(status)")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                actor_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                details TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {tp}organizations(id),
                FOREIGN KEY (actor_user_id)
                    REFERENCES {tp}Creator_users(id)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}audit_log_org_date "
            f"ON {tp}audit_log(organization_id, created_at)")

    def _migration_26(self, cursor):
        """Add activity_type, setup_config, lis_outcome_service_url to lti_activities
        for databases created before the file-eval module."""
        tp = self.db.table_prefix
        if not self._table_exists(cursor, 'lti_activities'):
            return
        if not self._column_exists(cursor, 'lti_activities', 'activity_type'):
            logger.info("Migrating lti_activities: adding activity_type")
            cursor.execute(
                f"ALTER TABLE {tp}lti_activities "
                f"ADD COLUMN activity_type TEXT NOT NULL DEFAULT 'chat'")
        if not self._column_exists(cursor, 'lti_activities', 'setup_config'):
            logger.info("Migrating lti_activities: adding setup_config")
            cursor.execute(
                f"ALTER TABLE {tp}lti_activities "
                f"ADD COLUMN setup_config TEXT DEFAULT '{{}}'")
        if not self._column_exists(cursor, 'lti_activities', 'lis_outcome_service_url'):
            logger.info("Migrating lti_activities: adding lis_outcome_service_url")
            cursor.execute(
                f"ALTER TABLE {tp}lti_activities "
                f"ADD COLUMN lis_outcome_service_url TEXT")

    def _migration_27(self, cursor):
        """Create knowledge_stores and kb_content_links tables."""
        tp = self.db.table_prefix

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}knowledge_stores (
                id TEXT PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                owner_user_id INTEGER NOT NULL,
                is_shared INTEGER DEFAULT 0,
                chunking_strategy TEXT NOT NULL,
                chunking_params TEXT,
                embedding_vendor TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_endpoint TEXT,
                vector_db_backend TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (organization_id)
                    REFERENCES {tp}organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_user_id)
                    REFERENCES {tp}Creator_users(id),
                UNIQUE(organization_id, name)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}knowledge_stores_owner "
            f"ON {tp}knowledge_stores(owner_user_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}knowledge_stores_org_shared "
            f"ON {tp}knowledge_stores(organization_id, is_shared)")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tp}kb_content_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_store_id TEXT NOT NULL,
                library_id TEXT NOT NULL,
                library_item_id TEXT NOT NULL,
                organization_id INTEGER NOT NULL,
                kb_job_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                chunks_created INTEGER DEFAULT 0,
                error_message TEXT,
                created_by_user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (knowledge_store_id)
                    REFERENCES {tp}knowledge_stores(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id)
                    REFERENCES {tp}organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id)
                    REFERENCES {tp}Creator_users(id),
                UNIQUE(knowledge_store_id, library_item_id)
            )
        """)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}kb_content_links_ks "
            f"ON {tp}kb_content_links(knowledge_store_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}kb_content_links_item "
            f"ON {tp}kb_content_links(library_item_id)")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"idx_{tp}kb_content_links_status "
            f"ON {tp}kb_content_links(status)")

    def _migration_28(self, cursor):
        """Add cache-aware columns to model_pricing and assistant_usage_totals.
        Seed OpenAI cached rates."""
        tp = self.db.table_prefix

        if not self._column_exists(cursor, 'model_pricing', 'cached_input_per_1m'):
            cursor.execute(
                f"ALTER TABLE {tp}model_pricing "
                f"ADD COLUMN cached_input_per_1m REAL")

        if not self._column_exists(cursor, 'assistant_usage_totals', 'cached_prompt_tokens_total'):
            cursor.execute(
                f"ALTER TABLE {tp}assistant_usage_totals "
                f"ADD COLUMN cached_prompt_tokens_total INTEGER DEFAULT 0")
        if not self._column_exists(cursor, 'assistant_usage_totals', 'non_cached_prompt_tokens_total'):
            cursor.execute(
                f"ALTER TABLE {tp}assistant_usage_totals "
                f"ADD COLUMN non_cached_prompt_tokens_total INTEGER DEFAULT 0")

        import time
        now = int(time.time())
        upsert_rows = [
            ("openai", "gpt-4.1",       2.00,  1.00,  8.00),
            ("openai", "gpt-4.1-mini",   0.40,  0.20,  1.60),
            ("openai", "gpt-4.1-nano",   0.10,  0.025, 0.40),
            ("openai", "gpt-4o",         2.50,  1.25, 10.00),
            ("openai", "gpt-4o-mini",    0.15,  0.075, 0.60),
            ("openai", "gpt-4-turbo",   10.00,  None, 30.00),
            ("openai", "gpt-4",         30.00,  None, 60.00),
            ("openai", "o3-mini",        1.10,  0.55,  4.40),
        ]
        for provider, model, inp, cached, out in upsert_rows:
            cursor.execute(
                f"""UPDATE {tp}model_pricing
                    SET cached_input_per_1m = ?,
                        input_per_1m = ?,
                        output_per_1m = ?,
                        updated_at = ?
                    WHERE provider = ? AND model_name = ?""",
                (cached, inp, out, now, provider, model),
            )

    def _migration_29(self, cursor):
        """Add cache write, explicit cache, and immutable cost columns.
        Backfill cost_usd for legacy usage_logs and rebuild totals."""
        tp = self.db.table_prefix

        # 29a: Add cache_read/write/explicit to model_pricing
        if not self._column_exists(cursor, 'model_pricing', 'cache_read_per_1m'):
            cursor.execute(
                f"ALTER TABLE {tp}model_pricing ADD COLUMN cache_read_per_1m REAL")
        if not self._column_exists(cursor, 'model_pricing', 'cache_write_per_1m'):
            cursor.execute(
                f"ALTER TABLE {tp}model_pricing ADD COLUMN cache_write_per_1m REAL")
        if not self._column_exists(cursor, 'model_pricing', 'requires_explicit_cache'):
            cursor.execute(
                f"ALTER TABLE {tp}model_pricing "
                f"ADD COLUMN requires_explicit_cache INTEGER DEFAULT 0")

        # 29b: Copy cached_input_per_1m values to cache_read_per_1m
        if self._column_exists(cursor, 'model_pricing', 'cached_input_per_1m'):
            cursor.execute(
                f"UPDATE {tp}model_pricing "
                f"SET cache_read_per_1m = cached_input_per_1m "
                f"WHERE cache_read_per_1m IS NULL AND cached_input_per_1m IS NOT NULL")

        # 29c: Add cache token columns to assistant_usage_totals
        if not self._column_exists(cursor, 'assistant_usage_totals', 'cache_read_tokens_total'):
            cursor.execute(
                f"ALTER TABLE {tp}assistant_usage_totals "
                f"ADD COLUMN cache_read_tokens_total INTEGER DEFAULT 0")
        if not self._column_exists(cursor, 'assistant_usage_totals', 'cache_write_tokens_total'):
            cursor.execute(
                f"ALTER TABLE {tp}assistant_usage_totals "
                f"ADD COLUMN cache_write_tokens_total INTEGER DEFAULT 0")

        # 29d: Copy cached_prompt_tokens_total to cache_read_tokens_total
        if self._column_exists(cursor, 'assistant_usage_totals', 'cached_prompt_tokens_total'):
            cursor.execute(
                f"UPDATE {tp}assistant_usage_totals "
                f"SET cache_read_tokens_total = cached_prompt_tokens_total "
                f"WHERE cache_read_tokens_total = 0 AND cached_prompt_tokens_total > 0")

        # 29e: Add cost_usd to usage_logs
        if not self._column_exists(cursor, 'usage_logs', 'cost_usd'):
            cursor.execute(
                f"ALTER TABLE {tp}usage_logs ADD COLUMN cost_usd REAL")

        # 29f: Seed Qwen pricing row
        import time
        now = int(time.time())
        cursor.execute(
            f"""INSERT OR IGNORE INTO {tp}model_pricing
                (provider, model_name, input_per_1m, cache_read_per_1m,
                 cache_write_per_1m, output_per_1m, requires_explicit_cache,
                 notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "openai", "qwen3.6-plus",
                0.80, 0.16, 1.00, 2.00, 1,
                "Alibaba Qwen 3.6 Plus via compatible API",
                now,
            ),
        )

        # 29g: Backfill cost_usd for existing usage_logs rows where cost_usd IS NULL
        cursor.execute(
            f"SELECT id, usage_data, model_name, provider "
            f"FROM {tp}usage_logs WHERE cost_usd IS NULL")
        legacy_rows = cursor.fetchall()
        if legacy_rows:
            logger.info(
                f"Migration 29: Backfilling cost_usd for "
                f"{len(legacy_rows)} legacy usage_logs rows")
            import json
            from lamb.completions.token_repartition import extract_token_buckets
            from lamb.completions.cost_formula import compute_cost_usd

            pricing_cache = {}
            for legacy_id, usage_json, leg_model, leg_provider in legacy_rows:
                try:
                    usage_obj = json.loads(usage_json) if isinstance(usage_json, str) else {}
                except Exception:
                    usage_obj = {}

                pricing_key = (leg_provider, leg_model)
                if pricing_key not in pricing_cache:
                    cursor.execute(
                        f"""SELECT input_per_1m, cache_read_per_1m,
                                   cache_write_per_1m, output_per_1m,
                                   requires_explicit_cache
                            FROM {tp}model_pricing
                            WHERE provider = ? AND model_name = ?""",
                        (leg_provider, leg_model),
                    )
                    p_row = cursor.fetchone()
                    if p_row:
                        pricing_cache[pricing_key] = {
                            "input_per_1m": p_row[0],
                            "cache_read_per_1m": p_row[1],
                            "cache_write_per_1m": p_row[2],
                            "output_per_1m": p_row[3],
                            "requires_explicit_cache": bool(p_row[4]),
                        }
                    else:
                        pricing_cache[pricing_key] = None

                buckets = extract_token_buckets(usage_obj)
                cost = compute_cost_usd(pricing_cache[pricing_key], buckets)
                cursor.execute(
                    f"UPDATE {tp}usage_logs SET cost_usd = ? WHERE id = ?",
                    (cost, legacy_id),
                )

            # 29h: Rebuild cost_usd_total from usage_logs.cost_usd
            cursor.execute(f"""
                UPDATE {tp}assistant_usage_totals
                SET cost_usd_total = COALESCE((
                    SELECT SUM(ul.cost_usd)
                    FROM {tp}usage_logs ul
                    WHERE ul.assistant_id = {tp}assistant_usage_totals.assistant_id
                ), 0.0)
            """)

            # 29i: Rebuild cache token totals in assistant_usage_totals
            cursor.execute(f"""
                SELECT assistant_id,
                       SUM(COALESCE(json_extract(usage_data, '$.prompt_tokens'), 0)),
                       SUM(COALESCE(json_extract(usage_data, '$.prompt_tokens_details.cached_tokens'), 0)),
                       SUM(COALESCE(json_extract(usage_data, '$.prompt_tokens_details.cache_creation_input_tokens'), 0))
                FROM {tp}usage_logs
                GROUP BY assistant_id
            """)
            for aid, prompt_sum, read_sum, write_sum in cursor.fetchall():
                prompt_sum = int(prompt_sum or 0)
                read_sum = int(read_sum or 0)
                write_sum = int(write_sum or 0)
                non_cached = max(0, prompt_sum - read_sum - write_sum)
                cursor.execute(
                    f"""UPDATE {tp}assistant_usage_totals
                        SET cache_read_tokens_total = ?,
                            cache_write_tokens_total = ?,
                            non_cached_prompt_tokens_total = ?
                        WHERE assistant_id = ?""",
                    (read_sum, write_sum, non_cached, aid),
                )

            logger.info(
                "Migration 29: Backfill complete "
                "(cost_usd + cache_read + cache_write + non_cached)")
