"""
IMPORTANT: Field Mapping Documentation

The Assistant model uses a virtual field mapping for historical reasons:
- 'metadata' (application level) -> 'api_callback' (database column)
- This mapping avoids database schema changes while providing semantic clarity
- The following fields exist in DB but are DEPRECATED and always empty:
  - pre_retrieval_endpoint
  - post_retrieval_endpoint  
  - RAG_endpoint

When working with this code:
1. Use assistant.metadata in application code
2. Use 'api_callback' in SQL queries (it stores the metadata)
3. Always set deprecated fields to empty strings
"""

import sqlite3
import os
from .lamb_classes import Assistant, LTIUser, Organization, OrganizationRole
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv
from .owi_bridge.owi_users import OwiUserManager
import jwt
import config
from lamb.logging_config import get_logger


# Set up logger for database operations
logger = get_logger(__name__, component="DB")


class LambDatabaseManager:
    def __init__(self):
        try:
            # Load environment variables
            load_dotenv()

            # Get database configuration from environment variables
            self.table_prefix = os.getenv('LAMB_DB_PREFIX', '')

            lamb_db_path = os.getenv('LAMB_DB_PATH')
            if not lamb_db_path:
                logger.error("LAMB_DB_PATH not found in environment variables")
                raise ValueError("LAMB_DB_PATH must be specified in environment variables")

            self.db_path = os.path.join(lamb_db_path, 'lamb_v4.db')
            if not os.path.exists(self.db_path):
                # Create the database file and directory if they don't exist
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                self.create_database_and_tables()
                logger.info(f"Created database at: {self.db_path}")

            # Configure database optimizations
            self._configure_database_optimizations()
            
            # Always run migrations on initialization (handles existing databases)
            self.run_migrations()

        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise

    def _configure_database_optimizations(self):
        """
        Configure SQLite PRAGMA settings for optimal performance and scalability.
        This should be called once during initialization.
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish connection for optimization")
            return
        
        try:
            cursor = connection.cursor()
            
            # Enable WAL (Write-Ahead Logging) mode for better concurrency
            # WAL allows multiple readers while a write is in progress
            cursor.execute("PRAGMA journal_mode=WAL")
            logger.info("WAL mode enabled")
            
            # Set synchronous to NORMAL for better performance
            # NORMAL is safe with WAL mode and provides good balance
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Set page size (must be set before any tables are created, but we can check)
            # 4096 is a good balance for modern systems
            cursor.execute("PRAGMA page_size=4096")
            
            # Set cache size to 10MB (-10000 pages = ~40MB with 4KB pages)
            # Negative value means KB, positive means pages
            cursor.execute("PRAGMA cache_size=-10000")
            
            # Enable memory-mapped I/O for better performance (256MB)
            cursor.execute("PRAGMA mmap_size=268435456")
            
            # Set temp store to memory for faster temporary operations
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # Enable automatic indexing for optimization
            cursor.execute("PRAGMA automatic_index=ON")
            
            # Set busy timeout to 5 seconds to handle concurrent access
            cursor.execute("PRAGMA busy_timeout=5000")
            
            connection.commit()
            
            # Log current settings for verification
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA synchronous")
            sync_mode = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]
            
            logger.info(f"Database optimizations applied - Journal: {journal_mode}, Sync: {sync_mode}, Cache: {cache_size}")
            
        except sqlite3.Error as e:
            logger.error(f"Error configuring database optimizations: {e}")
        finally:
            connection.close()

    def get_connection(self):
        """
        Get a database connection with per-connection optimizations.
        """
        try:
            connection = sqlite3.connect(self.db_path, timeout=10.0)
            
            # Per-connection optimizations
            cursor = connection.cursor()
            
            # Set busy timeout for this connection (5 seconds)
            cursor.execute("PRAGMA busy_timeout=5000")
            
            # Enable foreign keys for referential integrity
            cursor.execute("PRAGMA foreign_keys=ON")
            
            return connection
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    def optimize_database(self, vacuum: bool = True):
        """
        Perform database optimization operations.

        Args:
            vacuum (bool): If True perform VACUUM (costly). If False run only ANALYZE and PRAGMA optimize.

        Should be called periodically (e.g., during maintenance windows).
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish connection for optimization")
            return False
        
        try:
            cursor = connection.cursor()
            
            # Analyze the database to update statistics for query optimization
            logger.info("Running ANALYZE on database...")
            cursor.execute("ANALYZE")
            
            # VACUUM is optional because it's expensive; perform only when requested
            if vacuum:
                # Ensure WAL is checkpointed before VACUUM
                logger.info("Checkpointing WAL before VACUUM...")
                try:
                    self.checkpoint_wal()
                except Exception as e:
                    logger.warning(f"Failed to checkpoint WAL before VACUUM: {e}")

                # Vacuum the database to reclaim space and defragment
                # Note: VACUUM requires exclusive access and can take time
                logger.info("Running VACUUM on database...")
                cursor.execute("VACUUM")
            else:
                logger.info("Skipping VACUUM (scheduled optimize without vacuum)")
            
            # Optimize the database
            cursor.execute("PRAGMA optimize")
            
            connection.commit()
            logger.info("Database optimization completed successfully (vacuum=%s)" % vacuum)
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error during database optimization: {e}")
            return False
        finally:
            connection.close()

    def checkpoint_wal(self):
        """
        Checkpoint the WAL file to move data into the main database.
        This is useful for periodic maintenance.
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish connection for WAL checkpoint")
            return False
        
        try:
            cursor = connection.cursor()
            
            # Perform WAL checkpoint
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = cursor.fetchone()
            
            logger.info(f"WAL checkpoint completed: {result}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error during WAL checkpoint: {e}")
            return False
        finally:
            connection.close()

    def get_database_stats(self):
        """
        Get database statistics for monitoring.
        """
        connection = self.get_connection()
        if not connection:
            return {}
        
        try:
            cursor = connection.cursor()
            stats = {}
            
            # Get database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            stats['database_size_mb'] = (page_count * page_size) / (1024 * 1024)
            
            # Get WAL file size
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            stats['journal_mode'] = journal_mode
            
            if journal_mode == 'wal':
                wal_path = self.db_path + '-wal'
                if os.path.exists(wal_path):
                    stats['wal_size_mb'] = os.path.getsize(wal_path) / (1024 * 1024)
            
            # Get table counts
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self.table_prefix}Creator_users
            """)
            stats['user_count'] = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self.table_prefix}assistants
            """)
            stats['assistant_count'] = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self.table_prefix}organizations
            """)
            stats['organization_count'] = cursor.fetchone()[0]
            
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
        finally:
            connection.close()
        
    def create_database_and_tables(self):
        logger.debug("Starting database and tables creation")
        try:
            connection = self.get_connection()
            if not connection:
                logger.error("Failed to establish database connection")
                return

            with connection:
                cursor = connection.cursor()

                # Create the organizations table
                logger.debug("Creating organizations table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}organizations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        slug TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        is_system BOOLEAN DEFAULT FALSE,
                        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'trial')),
                        config JSON NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                """)
                cursor.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_slug ON {self.table_prefix}organizations(slug)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_status ON {self.table_prefix}organizations(status)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_is_system ON {self.table_prefix}organizations(is_system)")
                logger.info(
                    f"Table '{self.table_prefix}organizations' created successfully")

                # Create the organization_roles table
                logger.debug("Creating organization_roles table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}organization_roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('owner', 'admin', 'member')),
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                        UNIQUE(organization_id, user_id)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_org ON {self.table_prefix}organization_roles(organization_id)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_user ON {self.table_prefix}organization_roles(user_id)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_role ON {self.table_prefix}organization_roles(role)")
                logger.info(
                    f"Table '{self.table_prefix}organization_roles' created successfully")

                # Create usage_logs table
                logger.debug("Creating usage_logs table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}usage_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER NOT NULL,
                        user_id INTEGER,
                        assistant_id INTEGER,
                        usage_data JSON NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id),
                        FOREIGN KEY (user_id) REFERENCES {self.table_prefix}Creator_users(id),
                        FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}usage_logs_org_date ON {self.table_prefix}usage_logs(organization_id, created_at)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}usage_logs_user_date ON {self.table_prefix}usage_logs(user_id, created_at)")
                logger.info(
                    f"Table '{self.table_prefix}usage_logs' created successfully")

                # Create the model_permissions table
                logger.debug("Creating model_permissions table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}model_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        access_type TEXT NOT NULL CHECK(access_type IN ('include', 'exclude')),
                        UNIQUE(user_email, model_name)
                    )
                """)
                logger.info(
                    f"Table '{self.table_prefix}model_permissions' created successfully")

                # Create the assistants table
                logger.debug("Creating assistants table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}assistants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        owner TEXT NOT NULL,
                        api_callback TEXT,
                        system_prompt TEXT,
                        prompt_template TEXT,
                        RAG_endpoint TEXT,
                        RAG_Top_k INTEGER,
                        RAG_collections TEXT,
                        pre_retrieval_endpoint TEXT,
                        post_retrieval_endpoint TEXT,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id),
                        UNIQUE(organization_id, name, owner)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistants_org ON {self.table_prefix}assistants(organization_id)")
                logger.info(
                    f"Table '{self.table_prefix}assistants' created successfully")

                # Create the lti_users table
                logger.debug("Creating lti_users table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}lti_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assistant_id TEXT NOT NULL,
                        assistant_name TEXT NOT NULL,
                        group_id TEXT NOT NULL DEFAULT '',
                        group_name TEXT NOT NULL DEFAULT '',
                        assistant_owner TEXT NOT NULL DEFAULT '',
                        user_email TEXT NOT NULL,
                        user_name TEXT NOT NULL DEFAULT '',
                        user_display_name TEXT NOT NULL,
                        lti_context_id TEXT NOT NULL,
                        lti_app_id TEXT,
                        UNIQUE(user_email, assistant_id)
                    )
                """)
                logger.info(
                    f"Table '{self.table_prefix}lti_users' created successfully")

                # Create the assistant_publish table
                logger.debug("Creating assistant_publish table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}assistant_publish (
                        assistant_id INTEGER PRIMARY KEY, -- Made assistant_id the primary key
                        assistant_name TEXT NOT NULL,
                        assistant_owner TEXT NOT NULL,
                        group_id TEXT NOT NULL, -- Keep group_id/name for informational purposes
                        group_name TEXT NOT NULL,
                        oauth_consumer_name TEXT UNIQUE, -- Added UNIQUE constraint
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id) ON DELETE CASCADE -- Optional: Add foreign key constraint
                    )
                """)
                logger.info(
                    f"Table '{self.table_prefix}assistant_publish' created successfully")

                # Create the assistant_shares table
                logger.debug("Creating assistant_shares table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}assistant_shares (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assistant_id INTEGER NOT NULL,
                        shared_with_user_id INTEGER NOT NULL,
                        shared_by_user_id INTEGER NOT NULL,
                        shared_at INTEGER NOT NULL,
                        FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id) ON DELETE CASCADE,
                        FOREIGN KEY (shared_with_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                        FOREIGN KEY (shared_by_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                        UNIQUE(assistant_id, shared_with_user_id)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistant_shares_assistant ON {self.table_prefix}assistant_shares(assistant_id)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistant_shares_shared_with ON {self.table_prefix}assistant_shares(shared_with_user_id)")
                logger.info(
                    f"Table '{self.table_prefix}assistant_shares' created successfully")

                # Create the Creator_users table
                logger.debug("Creating Creator_users table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}Creator_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER,
                        user_email TEXT NOT NULL,
                        user_name TEXT NOT NULL,
                        user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
                        user_config JSON,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id),
                        UNIQUE(user_email)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_org ON {self.table_prefix}Creator_users(organization_id)")
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_type ON {self.table_prefix}Creator_users(user_type)")
                logger.info(
                    f"Table '{self.table_prefix}Creator_users' created successfully")

                # Create the collections table
                logger.debug("Creating collections table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}collections (
                        id TEXT PRIMARY KEY,
                        organization_id INTEGER NOT NULL,
                        collection_name TEXT NOT NULL,
                        owner TEXT NOT NULL,
                        metadata JSON,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id),
                        UNIQUE(organization_id, collection_name)
                    )
                """)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}collections_org ON {self.table_prefix}collections(organization_id)")
                logger.info(
                    f"Table '{self.table_prefix}collections' created successfully")

                # Create the config table
                logger.debug("Creating config table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}config (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        config JSON NOT NULL
                    )
                """)

                # Insert default config if it doesn't exist
                cursor.execute(f"""
                    INSERT OR IGNORE INTO {self.table_prefix}config (id, config)
                    VALUES (1, '{{}}')
                """)

                logger.info(
                    f"Table '{self.table_prefix}config' created successfully")

            # Initialize system organization and admin user
            self.initialize_system_organization()
        except sqlite3.Error as e:
            logger.error(f"Database error occurred: {e}")

        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed")

    def create_admin_user(self):
        """Create the system admin user in both OWI and LAMB systems"""
        owi_manager = OwiUserManager()

        # Create or verify OWI admin user
        owi_user = owi_manager.get_user_by_email(config.OWI_ADMIN_EMAIL)
        if not owi_user:
            owi_manager.create_user(
                name=config.OWI_ADMIN_NAME,
                email=config.OWI_ADMIN_EMAIL,
                password=config.OWI_ADMIN_PASSWORD,
                role="admin"
            )
            logger.info(f"Created OWI admin user: {config.OWI_ADMIN_EMAIL}")
        else:
            # Ensure the user has admin role in OWI
            if owi_user.get('role') != 'admin':
                owi_manager.update_user_role_by_email(
                    config.OWI_ADMIN_EMAIL, 'admin')
                logger.info(
                    f"Updated OWI user to admin role: {config.OWI_ADMIN_EMAIL}")

        # Note: LAMB creator user will be created in initialize_system_organization
        # to ensure it's created with the correct organization_id

    def initialize_system_organization(self):
        """Initialize the system organization and admin user"""
        logger.info("Initializing system organization")

        # Check if system organization exists
        system_org = self.get_organization_by_slug("lamb")

        if not system_org:
            # Create system organization from environment
            system_org_id = self.create_system_organization()
            if not system_org_id:
                logger.error("Failed to create system organization")
                return
        else:
            system_org_id = system_org['id']
            # Update system organization config from .env
            self.sync_system_org_with_env(system_org_id)
            logger.info(
                "System organization configuration updated from environment")

        # Always ensure admin user exists and has proper roles
        self.ensure_system_admin(system_org_id)

    def ensure_system_admin(self, system_org_id: int):
        """Ensure the system admin exists and has proper roles in both OWI and LAMB"""
        # First, ensure OWI admin exists
        self.create_admin_user()

        # Check if LAMB creator user exists
        admin_user = self.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)

        if not admin_user:
            # Create LAMB creator user with system organization
            admin_user_id = self.create_creator_user(
                user_email=config.OWI_ADMIN_EMAIL,
                user_name=config.OWI_ADMIN_NAME,
                password=config.OWI_ADMIN_PASSWORD,
                organization_id=system_org_id
            )
            if admin_user_id:
                logger.info(
                    f"Created LAMB admin user: {config.OWI_ADMIN_EMAIL}")
                # Assign admin role in organization
                self.assign_organization_role(
                    organization_id=system_org_id,
                    user_id=admin_user_id,
                    role="admin"
                )
                logger.info(
                    f"Assigned admin role to user {admin_user_id} in system organization")
        else:
            # User exists, ensure they have correct organization and role
            admin_user_id = admin_user['id']

            # Check and update organization if needed
            if admin_user.get('organization_id') != system_org_id:
                self.update_user_organization(admin_user_id, system_org_id)
                logger.info(f"Updated admin user organization to system org")

            # Check and assign admin role if needed
            current_role = self.get_user_organization_role(
                admin_user_id, system_org_id)
            if current_role != "admin":
                self.assign_organization_role(
                    organization_id=system_org_id,
                    user_id=admin_user_id,
                    role="admin"
                )
                logger.info(
                    f"Updated admin user role to 'admin' in system organization")

    def run_migrations(self):
        """Run database migrations for schema updates"""
        logger.info("Running database migrations")
        connection = self.get_connection()
        if not connection:
            logger.error(
                "Could not establish database connection for migrations")
            return

        try:
            with connection:
                cursor = connection.cursor()

                # Migration 1: Add user_type column to Creator_users if it doesn't exist
                cursor.execute(
                    f"PRAGMA table_info({self.table_prefix}Creator_users)")
                columns = [row[1] for row in cursor.fetchall()]

                if 'user_type' not in columns:
                    logger.info(
                        "Adding user_type column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN user_type TEXT NOT NULL DEFAULT 'creator' 
                        CHECK(user_type IN ('creator', 'end_user'))
                    """)
                    # Create index for user_type
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_type ON {self.table_prefix}Creator_users(user_type)")
                    logger.info(
                        "Successfully added user_type column and index")
                else:
                    logger.debug(
                        "user_type column already exists in Creator_users table")

                # Migration 2: Create rubrics table if it doesn't exist
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}rubrics'")
                rubrics_table_exists = cursor.fetchone()

                if not rubrics_table_exists:
                    logger.info("Creating rubrics table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}rubrics (
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
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE,
                            FOREIGN KEY (parent_rubric_id) REFERENCES {self.table_prefix}rubrics(rubric_id) ON DELETE SET NULL
                        )
                    """)

                    # Create indexes for performance
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_owner ON {self.table_prefix}rubrics(owner_email)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_org ON {self.table_prefix}rubrics(organization_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_rubric_id ON {self.table_prefix}rubrics(rubric_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_public ON {self.table_prefix}rubrics(is_public)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_showcase ON {self.table_prefix}rubrics(is_showcase)")

                    logger.info(
                        "Successfully created rubrics table and indexes")
                else:
                    logger.debug("rubrics table already exists")

                # Migration 3: Create prompt_templates table if it doesn't exist
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}prompt_templates'")
                prompt_templates_table_exists = cursor.fetchone()

                if not prompt_templates_table_exists:
                    logger.info("Creating prompt_templates table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}prompt_templates (
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
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE,
                            FOREIGN KEY (owner_email) REFERENCES {self.table_prefix}Creator_users(user_email) ON DELETE CASCADE,
                            UNIQUE(organization_id, owner_email, name)
                        )
                    """)

                    # Create indexes for performance
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_org_shared ON {self.table_prefix}prompt_templates(organization_id, is_shared)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_owner ON {self.table_prefix}prompt_templates(owner_email)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_name ON {self.table_prefix}prompt_templates(name)")

                    logger.info(
                        "Successfully created prompt_templates table and indexes")
                else:
                    logger.debug("prompt_templates table already exists")

                # Migration 4: Add enabled column to Creator_users if it doesn't exist
                cursor.execute(
                    f"PRAGMA table_info({self.table_prefix}Creator_users)")
                columns = [row[1] for row in cursor.fetchall()]

                if 'enabled' not in columns:
                    logger.info("Adding enabled column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1
                    """)
                    # Create index for performance
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_enabled ON {self.table_prefix}Creator_users(enabled)")
                    logger.info("Successfully added enabled column and index")
                else:
                    logger.debug(
                        "enabled column already exists in Creator_users table")

                # Migration 5: Create kb_registry table if it doesn't exist
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}kb_registry'")
                kb_registry_table_exists = cursor.fetchone()

                if not kb_registry_table_exists:
                    logger.info("Creating kb_registry table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}kb_registry (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            kb_id TEXT NOT NULL UNIQUE,
                            kb_name TEXT NOT NULL,
                            owner_user_id INTEGER NOT NULL,
                            organization_id INTEGER NOT NULL,
                            is_shared BOOLEAN DEFAULT FALSE,
                            metadata JSON,
                            created_at INTEGER NOT NULL,
                            updated_at INTEGER NOT NULL,
                            FOREIGN KEY (owner_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE
                        )
                    """)

                    # Create indexes for performance
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_owner ON {self.table_prefix}kb_registry(owner_user_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_org_shared ON {self.table_prefix}kb_registry(organization_id, is_shared)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_kb_id ON {self.table_prefix}kb_registry(kb_id)")

                    logger.info(
                        "Successfully created kb_registry table and indexes")
                else:
                    logger.debug("kb_registry table already exists")

                # Migration 6: Create bulk_import_logs table if it doesn't exist
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}bulk_import_logs'")
                bulk_import_logs_table_exists = cursor.fetchone()

                if not bulk_import_logs_table_exists:
                    logger.info("Creating bulk_import_logs table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}bulk_import_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            organization_id INTEGER NOT NULL,
                            admin_user_id INTEGER,
                            admin_email TEXT NOT NULL,
                            operation_type TEXT NOT NULL CHECK(operation_type IN ('user_creation', 'user_activation', 'user_deactivation')),
                            total_count INTEGER NOT NULL,
                            success_count INTEGER NOT NULL,
                            failure_count INTEGER NOT NULL,
                            details JSON,
                            created_at INTEGER NOT NULL,
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE,
                            FOREIGN KEY (admin_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE SET NULL
                        )
                    """)

                    # Create indexes for performance
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}bulk_import_logs_org ON {self.table_prefix}bulk_import_logs(organization_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}bulk_import_logs_admin ON {self.table_prefix}bulk_import_logs(admin_user_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}bulk_import_logs_created ON {self.table_prefix}bulk_import_logs(created_at)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}bulk_import_logs_type ON {self.table_prefix}bulk_import_logs(operation_type)")

                    logger.info(
                        "Successfully created bulk_import_logs table and indexes")
                else:
                    logger.debug("bulk_import_logs table already exists")

                # Migration: Check if assistant_shares table exists
                cursor.execute(f"""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='{self.table_prefix}assistant_shares'
                """)
                if not cursor.fetchone():
                    logger.info("Creating assistant_shares table")
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_prefix}assistant_shares (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            assistant_id INTEGER NOT NULL,
                            shared_with_user_id INTEGER NOT NULL,
                            shared_by_user_id INTEGER NOT NULL,
                            shared_at INTEGER NOT NULL,
                            FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id) ON DELETE CASCADE,
                            FOREIGN KEY (shared_with_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                            FOREIGN KEY (shared_by_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                            UNIQUE(assistant_id, shared_with_user_id)
                        )
                    """)
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistant_shares_assistant ON {self.table_prefix}assistant_shares(assistant_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistant_shares_shared_with ON {self.table_prefix}assistant_shares(shared_with_user_id)")
                    logger.info(
                        f"Table '{self.table_prefix}assistant_shares' created successfully")
                else:
                    logger.debug("assistant_shares table already exists")

                # Migration 7: Create lamb_chats table for internal chat persistence
                # This mirrors the OWI chat table structure for unified analytics
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lamb_chats'")
                lamb_chats_table_exists = cursor.fetchone()

                if not lamb_chats_table_exists:
                    logger.info(
                        "Creating lamb_chats table for internal chat persistence")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lamb_chats (
                            id TEXT PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            assistant_id INTEGER NOT NULL,
                            title TEXT NOT NULL DEFAULT 'New Chat',
                            created_at INTEGER NOT NULL,
                            updated_at INTEGER NOT NULL,
                            chat JSON NOT NULL DEFAULT '{{"history": {{"messages": {{}}}}}}',
                            archived INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE,
                            FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id) ON DELETE CASCADE
                        )
                    """)

                    # Create indexes for common query patterns
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lamb_chats_user ON {self.table_prefix}lamb_chats(user_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lamb_chats_assistant ON {self.table_prefix}lamb_chats(assistant_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lamb_chats_user_assistant ON {self.table_prefix}lamb_chats(user_id, assistant_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lamb_chats_updated ON {self.table_prefix}lamb_chats(updated_at)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lamb_chats_archived ON {self.table_prefix}lamb_chats(archived)")

                    logger.info(
                        "Successfully created lamb_chats table and indexes")
                else:
                    logger.debug("lamb_chats table already exists")

                # Migration 8: Add LTI creator user fields to Creator_users
                cursor.execute(
                    f"PRAGMA table_info({self.table_prefix}Creator_users)")
                columns = [row[1] for row in cursor.fetchall()]

                if 'lti_user_id' not in columns:
                    logger.info("Adding lti_user_id column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN lti_user_id TEXT
                    """)
                    logger.info("Successfully added lti_user_id column")
                else:
                    logger.debug("lti_user_id column already exists in Creator_users table")

                if 'auth_provider' not in columns:
                    logger.info("Adding auth_provider column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'password'
                    """)
                    logger.info("Successfully added auth_provider column")
                else:
                    logger.debug("auth_provider column already exists in Creator_users table")

                # Create unique index for (organization_id, lti_user_id) if not exists
                # This ensures one LTI user per org
                cursor.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_org_lti 
                    ON {self.table_prefix}Creator_users(organization_id, lti_user_id)
                    WHERE lti_user_id IS NOT NULL
                """)
                logger.debug("Ensured unique index on (organization_id, lti_user_id)")

                # Create index on lti_user_id for fast lookups
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_lti_user_id 
                    ON {self.table_prefix}Creator_users(lti_user_id)
                    WHERE lti_user_id IS NOT NULL
                """)
                logger.debug("Ensured index on lti_user_id")

                # Migration 9: Create lti_creator_keys table for org LTI consumer keys
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_creator_keys'")
                lti_creator_keys_table_exists = cursor.fetchone()

                if not lti_creator_keys_table_exists:
                    logger.info("Creating lti_creator_keys table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_creator_keys (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            organization_id INTEGER NOT NULL UNIQUE,
                            oauth_consumer_key TEXT NOT NULL UNIQUE,
                            oauth_consumer_secret TEXT NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            created_at INTEGER NOT NULL,
                            updated_at INTEGER NOT NULL,
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE
                        )
                    """)
                    cursor.execute(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_creator_keys_consumer_key ON {self.table_prefix}lti_creator_keys(oauth_consumer_key)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_creator_keys_org ON {self.table_prefix}lti_creator_keys(organization_id)")
                    logger.info("Successfully created lti_creator_keys table and indexes")
                else:
                    logger.debug("lti_creator_keys table already exists")

                # Migration 10: Create unified LTI activity tables
                # lti_global_config — singleton for global LTI consumer key/secret
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_global_config'")
                if not cursor.fetchone():
                    logger.info("Creating lti_global_config table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_global_config (
                            id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                            oauth_consumer_key TEXT NOT NULL,
                            oauth_consumer_secret TEXT NOT NULL,
                            updated_at INTEGER NOT NULL,
                            updated_by TEXT
                        )
                    """)
                    logger.info("Successfully created lti_global_config table")

                # lti_activities — one row per LTI activity placement, bound to one org
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_activities'")
                if not cursor.fetchone():
                    logger.info("Creating lti_activities table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_activities (
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
                            status TEXT NOT NULL DEFAULT 'active',
                            created_at INTEGER NOT NULL,
                            updated_at INTEGER NOT NULL,
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id)
                        )
                    """)
                    cursor.execute(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_activities_resource_link ON {self.table_prefix}lti_activities(resource_link_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_activities_org ON {self.table_prefix}lti_activities(organization_id)")
                    logger.info("Successfully created lti_activities table and indexes")
                else:
                    # Migrate existing table: add new columns if missing
                    cursor.execute(f"PRAGMA table_info({self.table_prefix}lti_activities)")
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    if 'owner_email' not in existing_cols:
                        logger.info("Migrating lti_activities: adding owner_email, owner_name, chat_visibility_enabled")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activities ADD COLUMN owner_email TEXT NOT NULL DEFAULT ''")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activities ADD COLUMN owner_name TEXT")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activities ADD COLUMN chat_visibility_enabled INTEGER NOT NULL DEFAULT 0")
                        # Backfill owner_email from configured_by_email
                        cursor.execute(f"UPDATE {self.table_prefix}lti_activities SET owner_email = configured_by_email, owner_name = configured_by_name WHERE owner_email = ''")
                        logger.info("Migrated lti_activities with owner and chat_visibility fields")

                # lti_activity_assistants — junction: which assistants belong to which activity
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_activity_assistants'")
                if not cursor.fetchone():
                    logger.info("Creating lti_activity_assistants table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_activity_assistants (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            activity_id INTEGER NOT NULL,
                            assistant_id INTEGER NOT NULL,
                            added_at INTEGER NOT NULL,
                            FOREIGN KEY (activity_id) REFERENCES {self.table_prefix}lti_activities(id) ON DELETE CASCADE,
                            FOREIGN KEY (assistant_id) REFERENCES {self.table_prefix}assistants(id) ON DELETE CASCADE,
                            UNIQUE(activity_id, assistant_id)
                        )
                    """)
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_activity_assistants_activity ON {self.table_prefix}lti_activity_assistants(activity_id)")
                    logger.info("Successfully created lti_activity_assistants table")

                # lti_activity_users — track students who accessed via each activity
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_activity_users'")
                if not cursor.fetchone():
                    logger.info("Creating lti_activity_users table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_activity_users (
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
                            FOREIGN KEY (activity_id) REFERENCES {self.table_prefix}lti_activities(id) ON DELETE CASCADE,
                            UNIQUE(user_email, activity_id)
                        )
                    """)
                    logger.info("Successfully created lti_activity_users table")
                else:
                    # Migrate existing table: add new columns if missing
                    cursor.execute(f"PRAGMA table_info({self.table_prefix}lti_activity_users)")
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    if 'owi_user_id' not in existing_cols:
                        logger.info("Migrating lti_activity_users: adding owi_user_id, consent_given_at, last_access_at, access_count")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activity_users ADD COLUMN owi_user_id TEXT")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activity_users ADD COLUMN consent_given_at INTEGER")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activity_users ADD COLUMN last_access_at INTEGER")
                        cursor.execute(f"ALTER TABLE {self.table_prefix}lti_activity_users ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0")
                        logger.info("Migrated lti_activity_users with dashboard fields")

                # lti_identity_links — map LMS identities to LAMB Creator users
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}lti_identity_links'")
                if not cursor.fetchone():
                    logger.info("Creating lti_identity_links table")
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}lti_identity_links (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lms_user_id TEXT NOT NULL,
                            lms_email TEXT,
                            creator_user_id INTEGER NOT NULL,
                            linked_at INTEGER NOT NULL,
                            FOREIGN KEY (creator_user_id) REFERENCES {self.table_prefix}Creator_users(id) ON DELETE CASCADE
                        )
                    """)
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_identity_lms_user ON {self.table_prefix}lti_identity_links(lms_user_id)")
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}lti_identity_lms_email ON {self.table_prefix}lti_identity_links(lms_email)")
                    logger.info("Successfully created lti_identity_links table and indexes")

                # ---- Migration 11: Add password_hash and role to Creator_users ----
                cursor.execute(f"PRAGMA table_info({self.table_prefix}Creator_users)")
                existing_cols = {row[1] for row in cursor.fetchall()}

                if 'password_hash' not in existing_cols:
                    logger.info("Migration 11: Adding password_hash column to Creator_users")
                    cursor.execute(
                        f"ALTER TABLE {self.table_prefix}Creator_users ADD COLUMN password_hash TEXT")

                if 'role' not in existing_cols:
                    logger.info("Migration 11: Adding role column to Creator_users")
                    cursor.execute(
                        f"ALTER TABLE {self.table_prefix}Creator_users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

                connection.commit()
                logger.info("Migration 11 complete")

                # ---- Migration 11b: Copy password hashes and roles from OWI ----
                try:
                    cursor.execute(f"""
                        SELECT id, user_email FROM {self.table_prefix}Creator_users
                        WHERE auth_provider = 'password' AND password_hash IS NULL
                    """)
                    users_to_migrate = cursor.fetchall()

                    if users_to_migrate:
                        logger.info(f"Migration 11b: Migrating {len(users_to_migrate)} password hashes from OWI")
                        try:
                            from .owi_bridge.owi_database import OwiDatabaseManager
                            owi_db = OwiDatabaseManager()
                            owi_conn = owi_db.get_connection()

                            if owi_conn:
                                try:
                                    owi_cursor = owi_conn.cursor()
                                    for user_id, user_email in users_to_migrate:
                                        try:
                                            # Get password hash from OWI auth table
                                            owi_cursor.execute(
                                                "SELECT password FROM auth WHERE email = ?",
                                                (user_email,))
                                            auth_row = owi_cursor.fetchone()

                                            # Get role from OWI user table
                                            owi_cursor.execute(
                                                "SELECT role FROM user WHERE email = ?",
                                                (user_email,))
                                            role_row = owi_cursor.fetchone()

                                            pw_hash = auth_row[0] if auth_row else None
                                            owi_role = role_row[0] if role_row else 'user'

                                            if pw_hash:
                                                cursor.execute(f"""
                                                    UPDATE {self.table_prefix}Creator_users
                                                    SET password_hash = ?, role = ?
                                                    WHERE id = ?
                                                """, (pw_hash, owi_role, user_id))
                                                logger.debug(f"Migrated hash for {user_email}")
                                        except Exception as row_err:
                                            logger.warning(f"Migration 11b: Skipping {user_email}: {row_err}")

                                    connection.commit()
                                    logger.info("Migration 11b complete")
                                finally:
                                    owi_conn.close()
                            else:
                                logger.warning("Migration 11b: Could not connect to OWI DB, skipping hash migration")
                        except Exception as owi_err:
                            logger.warning(f"Migration 11b: OWI DB unavailable, skipping: {owi_err}")
                    else:
                        logger.info("Migration 11b: No users need hash migration")
                except Exception as mig_err:
                    logger.warning(f"Migration 11b error (non-fatal): {mig_err}")

        except sqlite3.Error as e:
            logger.error(f"Migration error: {e}")
        finally:
            if connection:
                connection.close()

    def create_system_organization(self) -> Optional[int]:
        """Create the 'lamb' system organization from .env configuration"""
        import os
        from datetime import datetime

        config_data = {
            "version": "1.0",
            "metadata": {
                "description": "System default organization",
                "system_managed": True,
                "created_at": datetime.now().isoformat()
            },
            "setups": {
                "default": {
                    "name": "System Default",
                    "is_default": True,
                    "providers": self._load_providers_from_env(),
                    "knowledge_base": self._load_kb_config_from_env()
                }
            },
            "features": self._load_features_from_env(),
            "limits": {
                "usage": {
                    "tokens_per_month": -1,  # -1 represents unlimited for system
                    "max_assistants": -1,
                    "storage_gb": -1
                }
            }
        }

        # Seed assistant defaults from defaults.json
        try:
            config_data['assistant_defaults'] = self._load_assistant_defaults_from_file()
        except Exception as e:
            logger.warning(
                f"Could not load assistant defaults for system org: {e}")

        return self.create_organization(
            slug="lamb",
            name="LAMB System Organization",
            is_system=True,
            config=config_data
        )

    def _load_providers_from_env(self) -> Dict[str, Any]:
        """Load provider configurations from environment variables"""
        import os
        providers = {}

        # OpenAI configuration
        if os.getenv("OPENAI_API_KEY"):
            providers["openai"] = {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_BASE_URL") or config.OPENAI_BASE_URL,
                "models": os.getenv("OPENAI_MODELS", "").split(",") if os.getenv("OPENAI_MODELS") else [],
                "default_model": os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL
            }

        # Ollama configuration
        if os.getenv("OLLAMA_BASE_URL"):
            providers["ollama"] = {
                "base_url": os.getenv("OLLAMA_BASE_URL"),
                "models": [os.getenv("OLLAMA_MODEL", "llama3.1")]
            }

        return providers

    def _load_kb_config_from_env(self) -> Dict[str, Any]:
        """Load knowledge base configuration from environment variables"""
        import os
        return {
            "server_url": os.getenv("LAMB_KB_SERVER", ""),
            "api_token": os.getenv("LAMB_KB_SERVER_TOKEN", "")
        }

    def _load_features_from_env(self) -> Dict[str, Any]:
        """Load feature flags from environment variables"""
        import os
        features = {
            "signup_enabled": os.getenv("SIGNUP_ENABLED", "false").lower() == "true",
            "dev_mode": os.getenv("DEV_MODE", "false").lower() == "true",
            "mcp_enabled": True,  # Always enabled for system org
            "lti_publishing": True,
            "rag_enabled": True
        }

        # Add signup key if signup is enabled and key is available
        signup_key = os.getenv("SIGNUP_SECRET_KEY")
        if features["signup_enabled"] and signup_key:
            features["signup_key"] = signup_key.strip()

        return features

    def _load_assistant_defaults_from_file(self) -> Dict[str, Any]:
        """Load assistant defaults from /backend/static/json/defaults.json"""
        import json
        import os
        from pathlib import Path

        try:
            # Try multiple possible paths
            possible_paths = [
                Path(__file__).parent.parent /
                "static" / "json" / "defaults.json",
                Path("/opt/lamb_v4/backend/static/json/defaults.json"),
                Path("static/json/defaults.json"),
                Path("backend/static/json/defaults.json")
            ]

            for path in possible_paths:
                if path.exists():
                    with open(path, 'r') as f:
                        data = json.load(f)
                        # Extract the config section which contains the assistant defaults
                        if 'config' in data:
                            return data['config']
                        return data

            logger.warning("defaults.json not found, using minimal defaults")
            return {
                "connector": "openai",
                "llm": "gpt-4o-mini",
                "prompt_processor": "simple_augment",
                "rag_processor": "No RAG"
            }
        except Exception as e:
            logger.error(f"Error loading assistant defaults from file: {e}")
            return {
                "connector": "openai",
                "llm": "gpt-4o-mini",
                "prompt_processor": "simple_augment",
                "rag_processor": "No RAG"
            }

    def _ensure_assistant_defaults_in_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure assistant_defaults exists in config, merging with file defaults"""
        if 'assistant_defaults' not in config:
            config['assistant_defaults'] = self._load_assistant_defaults_from_file()
        else:
            # Merge new keys from file without overwriting existing values
            file_defaults = self._load_assistant_defaults_from_file()
            for key, value in file_defaults.items():
                if key not in config['assistant_defaults']:
                    config['assistant_defaults'][key] = value
        return config

    def sync_system_org_with_env(self, org_id: int):
        """Update system organization configuration from environment variables"""
        org = self.get_organization_by_id(org_id)
        if not org or not org.get('is_system'):
            logger.warning("Cannot sync non-system organization")
            return

        # Update config with latest env values
        config = org['config']
        config["setups"]["default"]["providers"] = self._load_providers_from_env()
        config["setups"]["default"]["knowledge_base"] = self._load_kb_config_from_env()
        config["features"] = self._load_features_from_env()

        # Ensure assistant defaults exist and include any new keys from defaults.json
        try:
            config = self._ensure_assistant_defaults_in_config(config)
        except Exception as e:
            logger.warning(
                f"Could not ensure assistant_defaults during system sync: {e}")

        # Sync global default model from environment
        global_default_provider = os.getenv(
            'GLOBAL_DEFAULT_MODEL_PROVIDER', '').strip()
        global_default_model = os.getenv(
            'GLOBAL_DEFAULT_MODEL_NAME', '').strip()

        if global_default_provider and global_default_model:
            if 'default' not in config['setups']:
                config['setups']['default'] = {}

            config['setups']['default']['global_default_model'] = {
                "provider": global_default_provider,
                "model": global_default_model
            }
            logger.info(
                f"Synced global-default-model: {global_default_provider}/{global_default_model}")

        # Sync small fast model from environment
        small_fast_provider = os.getenv(
            'SMALL_FAST_MODEL_PROVIDER', '').strip()
        small_fast_model = os.getenv('SMALL_FAST_MODEL_NAME', '').strip()

        if small_fast_provider and small_fast_model:
            if 'default' not in config['setups']:
                config['setups']['default'] = {}

            config['setups']['default']['small_fast_model'] = {
                "provider": small_fast_provider,
                "model": small_fast_model
            }
            logger.info(
                f"Synced small-fast-model: {small_fast_provider}/{small_fast_model}")

        self.update_organization_config(org_id, config)

    # Organization Management Methods

    def create_organization(self, slug: str, name: str, is_system: bool = False,
                            config: Dict[str, Any] = None, status: str = "active") -> Optional[int]:
        """Create a new organization"""
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Set default config if none provided
                if config is None:
                    # Inherit from system organization baseline (includes assistant_defaults)
                    config = self.get_system_org_config_as_baseline()
                else:
                    # If provided config lacks assistant_defaults, seed from system baseline or defaults file
                    if not isinstance(config.get('assistant_defaults'), dict):
                        # Prefer system baseline when available
                        system_cfg = self.get_system_org_config_as_baseline()
                        if isinstance(system_cfg.get('assistant_defaults'), dict):
                            config['assistant_defaults'] = system_cfg['assistant_defaults'].copy(
                            )
                        else:
                            # Fallback to loading from file
                            config['assistant_defaults'] = self._load_assistant_defaults_from_file(
                            )

                    # Ensure both global models exist if not provided
                    if 'setups' in config and 'default' in config['setups']:
                        system_cfg = self.get_system_org_config_as_baseline()
                        if 'setups' in system_cfg and 'default' in system_cfg['setups']:
                            # Inherit global_default_model
                            if 'global_default_model' not in config['setups']['default']:
                                config['setups']['default']['global_default_model'] = system_cfg['setups']['default'].get(
                                    'global_default_model', {
                                        "provider": "", "model": ""}
                                )
                            # Inherit small_fast_model
                            if 'small_fast_model' not in config['setups']['default']:
                                config['setups']['default']['small_fast_model'] = system_cfg['setups']['default'].get(
                                    'small_fast_model', {
                                        "provider": "", "model": ""}
                                )

                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}organizations 
                    (slug, name, is_system, status, config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (slug, name, is_system, status, json.dumps(config), now, now))

                org_id = cursor.lastrowid
                logger.info(f"Organization '{name}' created with id: {org_id}")
                return org_id

        except sqlite3.Error as e:
            logger.error(f"Error creating organization: {e}")
            return None
        finally:
            connection.close()

    def create_organization_with_admin(self, slug: str, name: str, admin_user_id: int = None,
                                       signup_enabled: bool = False, signup_key: str = None,
                                       use_system_baseline: bool = True,
                                       config: Dict[str, Any] = None) -> Optional[int]:
        """
        Create a new organization with optional admin user assignment and signup configuration

        Args:
            slug: URL-friendly organization identifier
            name: Organization display name
            admin_user_id: ID of user from system org to become org admin (optional — if None, org is created without an admin)
            signup_enabled: Whether signup is enabled for this organization
            signup_key: Unique signup key for organization-specific signup
            use_system_baseline: Whether to copy system org config as baseline
            config: Custom config (overrides system baseline if provided)

        Returns:
            Organization ID if successful, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            # Validate signup key if provided
            if signup_key:
                is_valid, error_msg = self.validate_signup_key_format(
                    signup_key)
                if not is_valid:
                    logger.error(f"Invalid signup key format: {error_msg}")
                    return None

                if not self.validate_signup_key_uniqueness(signup_key):
                    logger.error(f"Signup key '{signup_key}' already exists")
                    return None

            # Validate admin user if provided
            admin_user = None
            if admin_user_id is not None:
                admin_user = self.get_creator_user_by_id(admin_user_id)
                if not admin_user:
                    logger.error(f"Admin user {admin_user_id} not found")
                    return None

                system_org = self.get_organization_by_slug("lamb")
                if not system_org or admin_user['organization_id'] != system_org['id']:
                    logger.error(
                        f"Admin user {admin_user_id} is not in system organization")
                    return None

                # Check if user is currently an admin in the system organization
                current_role = self.get_user_organization_role(
                    admin_user_id, system_org['id'])
                if current_role == "admin":
                    logger.error(
                        f"User {admin_user_id} is a system admin and cannot be assigned to a new organization")
                    return None

            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Prepare organization configuration
                if config is None:
                    if use_system_baseline:
                        config = self.get_system_org_config_as_baseline()
                    else:
                        config = self._get_default_org_config()

                # Configure signup settings
                if 'features' not in config:
                    config['features'] = {}
                config['features']['signup_enabled'] = signup_enabled
                if signup_enabled and signup_key:
                    config['features']['signup_key'] = signup_key.strip()
                elif 'signup_key' in config['features']:
                    del config['features']['signup_key']

                # Add creation metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['created_by_system_admin'] = True
                if admin_user is not None:
                    config['metadata']['admin_user_id'] = admin_user_id
                    config['metadata']['admin_user_email'] = admin_user['user_email']

                # Create organization
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}organizations 
                    (slug, name, is_system, status, config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (slug, name, False, "active", json.dumps(config), now, now))

                org_id = cursor.lastrowid
                logger.info(f"Organization '{name}' created with id: {org_id}")

                # If admin user provided, move them to the new org and assign admin role
                if admin_user_id is not None:
                    # Move admin user to new organization
                    cursor.execute(f"""
                        UPDATE {self.table_prefix}Creator_users
                        SET organization_id = ?, updated_at = ?
                        WHERE id = ?
                    """, (org_id, now, admin_user_id))

                    if cursor.rowcount == 0:
                        logger.error(
                            f"Failed to move admin user to new organization")
                        return None

                    # Assign admin role to user in new organization
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                        (organization_id, user_id, role, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (org_id, admin_user_id, "admin", now, now))

                    logger.info(
                        f"Assigned role 'admin' to user {admin_user_id} in organization {org_id}")
                    logger.info(
                        f"User {admin_user['user_email']} assigned as admin of organization '{name}'")
                else:
                    logger.info(
                        f"Organization '{name}' created without an admin. An admin can be assigned later.")

                return org_id

        except sqlite3.Error as e:
            logger.error(f"Error creating organization with admin: {e}")
            return None
        finally:
            connection.close()

    def get_organization_by_id(self, org_id: int) -> Optional[Dict[str, Any]]:
        """Get organization by ID"""
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, slug, name, is_system, status, config, created_at, updated_at
                    FROM {self.table_prefix}organizations
                    WHERE id = ?
                """, (org_id,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'slug': result[1],
                    'name': result[2],
                    'is_system': bool(result[3]),
                    'status': result[4],
                    'config': json.loads(result[5]) if result[5] else {},
                    'created_at': result[6],
                    'updated_at': result[7]
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting organization by ID: {e}")
            return None
        finally:
            connection.close()

    def get_organization_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get organization by slug"""
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, slug, name, is_system, status, config, created_at, updated_at
                    FROM {self.table_prefix}organizations
                    WHERE slug = ?
                """, (slug,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'slug': result[1],
                    'name': result[2],
                    'is_system': bool(result[3]),
                    'status': result[4],
                    'config': json.loads(result[5]) if result[5] else {},
                    'created_at': result[6],
                    'updated_at': result[7]
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting organization by slug: {e}")
            return None
        finally:
            connection.close()

    def update_organization(self, org_id: int, name: str = None, status: str = None,
                            config: Dict[str, Any] = None) -> bool:
        """Update organization details"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Build update query dynamically
                updates = []
                params = []

                if name is not None:
                    updates.append("name = ?")
                    params.append(name)

                if status is not None:
                    updates.append("status = ?")
                    params.append(status)

                if config is not None:
                    updates.append("config = ?")
                    params.append(json.dumps(config))

                updates.append("updated_at = ?")
                params.append(now)

                params.append(org_id)

                query = f"""
                    UPDATE {self.table_prefix}organizations
                    SET {', '.join(updates)}
                    WHERE id = ?
                """

                cursor.execute(query, params)
                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error updating organization: {e}")
            return False
        finally:
            connection.close()

    def update_organization_config(self, org_id: int, config: Dict[str, Any]) -> bool:
        """Update organization configuration"""
        return self.update_organization(org_id, config=config)

    def delete_organization(self, org_id: int) -> bool:
        """Delete an organization (cannot delete system organization)"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Check if it's a system organization
                cursor.execute(f"""
                    SELECT is_system FROM {self.table_prefix}organizations WHERE id = ?
                """, (org_id,))

                result = cursor.fetchone()
                if result and result[0]:
                    logger.error("Cannot delete system organization")
                    return False

                # Delete organization (cascade will handle related records)
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}organizations WHERE id = ?
                """, (org_id,))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error deleting organization: {e}")
            return False
        finally:
            connection.close()

    # Organization Migration Methods

    def validate_migration(self, source_org_id: int, target_org_id: int) -> Dict[str, Any]:
        """
        Validate migration feasibility before execution.

        Args:
            source_org_id: Source organization ID
            target_org_id: Target organization ID

        Returns:
            Dict with validation results, conflicts, and resource counts
        """
        connection = self.get_connection()
        if not connection:
            return {
                "can_migrate": False,
                "error": "Database connection failed",
                "conflicts": {"assistants": [], "templates": []},
                "resources": {}
            }

        try:
            with connection:
                cursor = connection.cursor()

                # Check if organizations exist
                cursor.execute(f"""
                    SELECT id, slug, is_system FROM {self.table_prefix}organizations WHERE id = ?
                """, (source_org_id,))
                source_org = cursor.fetchone()
                if not source_org:
                    return {
                        "can_migrate": False,
                        "error": "Source organization not found",
                        "conflicts": {"assistants": [], "templates": []},
                        "resources": {}
                    }

                if source_org[2]:  # is_system
                    return {
                        "can_migrate": False,
                        "error": "Cannot migrate system organization",
                        "conflicts": {"assistants": [], "templates": []},
                        "resources": {}
                    }

                cursor.execute(f"""
                    SELECT id, slug FROM {self.table_prefix}organizations WHERE id = ?
                """, (target_org_id,))
                target_org = cursor.fetchone()
                if not target_org:
                    return {
                        "can_migrate": False,
                        "error": "Target organization not found",
                        "conflicts": {"assistants": [], "templates": []},
                        "resources": {}
                    }

                source_org_slug = source_org[1]

                # Count resources
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}Creator_users WHERE organization_id = ?
                """, (source_org_id,))
                user_count = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}assistants WHERE organization_id = ?
                """, (source_org_id,))
                assistant_count = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}prompt_templates WHERE organization_id = ?
                """, (source_org_id,))
                template_count = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}kb_registry WHERE organization_id = ?
                """, (source_org_id,))
                kb_count = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}usage_logs WHERE organization_id = ?
                """, (source_org_id,))
                log_count = cursor.fetchone()[0]

                # Detect assistant conflicts
                cursor.execute(f"""
                    SELECT a.id, a.name, a.owner
                    FROM {self.table_prefix}assistants a
                    WHERE a.organization_id = ?
                    AND EXISTS (
                        SELECT 1 FROM {self.table_prefix}assistants t
                        WHERE t.organization_id = ?
                        AND t.name = a.name
                        AND t.owner = a.owner
                    )
                """, (source_org_id, target_org_id))
                assistant_conflicts = []
                for row in cursor.fetchall():
                    assistant_conflicts.append({
                        "id": row[0],
                        "name": row[1],
                        "owner": row[2],
                        "conflict_reason": "Target org already has assistant with same name and owner"
                    })

                # Detect template conflicts
                cursor.execute(f"""
                    SELECT pt.id, pt.name, pt.owner_email
                    FROM {self.table_prefix}prompt_templates pt
                    WHERE pt.organization_id = ?
                    AND EXISTS (
                        SELECT 1 FROM {self.table_prefix}prompt_templates t
                        WHERE t.organization_id = ?
                        AND t.name = pt.name
                        AND t.owner_email = pt.owner_email
                    )
                """, (source_org_id, target_org_id))
                template_conflicts = []
                for row in cursor.fetchall():
                    template_conflicts.append({
                        "id": row[0],
                        "name": row[1],
                        "owner_email": row[2],
                        "conflict_reason": "Target org already has template with same name and owner"
                    })

                return {
                    "can_migrate": True,
                    "conflicts": {
                        "assistants": assistant_conflicts,
                        "templates": template_conflicts
                    },
                    "resources": {
                        "users": user_count,
                        "assistants": assistant_count,
                        "templates": template_count,
                        "kbs": kb_count,
                        "usage_logs": log_count
                    },
                    "source_org_slug": source_org_slug,
                    "estimated_time_seconds": max(10, (user_count + assistant_count + template_count) // 10)
                }

        except sqlite3.Error as e:
            logger.error(f"Error validating migration: {e}")
            return {
                "can_migrate": False,
                "error": str(e),
                "conflicts": {"assistants": [], "templates": []},
                "resources": {}
            }
        finally:
            connection.close()

    def migrate_users(self, source_org_id: int, target_org_id: int) -> int:
        """Migrate users from source to target organization"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET organization_id = ?, updated_at = ?
                    WHERE organization_id = ?
                """, (target_org_id, now, source_org_id))

                migrated = cursor.rowcount
                logger.info(
                    f"Migrated {migrated} users from org {source_org_id} to {target_org_id}")
                return migrated

        except sqlite3.Error as e:
            logger.error(f"Error migrating users: {e}")
            raise
        finally:
            connection.close()

    def migrate_roles(self, source_org_id: int, target_org_id: int, preserve_admin_roles: bool = False) -> int:
        """
        Migrate organization roles from source to target organization.

        Args:
            source_org_id: Source organization ID
            target_org_id: Target organization ID
            preserve_admin_roles: If True, keep admin/owner roles. If False, downgrade to 'member'

        Returns:
            Number of roles migrated
        """
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Get all roles from source org
                cursor.execute(f"""
                    SELECT user_id, role FROM {self.table_prefix}organization_roles
                    WHERE organization_id = ?
                """, (source_org_id,))

                roles = cursor.fetchall()
                migrated = 0

                for user_id, role in roles:
                    # Determine target role
                    if preserve_admin_roles:
                        target_role = role  # Keep same role
                    else:
                        # Downgrade admins/owners to members
                        if role in ['admin', 'owner']:
                            target_role = 'member'
                        else:
                            target_role = role  # Keep member as member

                    # Assign role in target organization
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                        (organization_id, user_id, role, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (target_org_id, user_id, target_role, now, now))
                    migrated += 1

                logger.info(
                    f"Migrated {migrated} roles from org {source_org_id} to {target_org_id} (preserve_admin={preserve_admin_roles})")
                return migrated

        except sqlite3.Error as e:
            logger.error(f"Error migrating roles: {e}")
            raise
        finally:
            connection.close()

    def migrate_assistants(self, source_org_id: int, target_org_id: int, source_org_slug: str,
                           conflict_strategy: str = "rename") -> Dict[str, Any]:
        """
        Migrate assistants from source to target organization with conflict resolution.

        Args:
            source_org_id: Source organization ID
            target_org_id: Target organization ID
            source_org_slug: Source organization slug (for renaming)
            conflict_strategy: "rename" (prefix with org slug), "skip", or "fail"

        Returns:
            Dict with count and renamed list
        """
        connection = self.get_connection()
        if not connection:
            return {"count": 0, "renamed": []}

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Get all assistants from source org
                cursor.execute(f"""
                    SELECT id, name, owner FROM {self.table_prefix}assistants
                    WHERE organization_id = ?
                """, (source_org_id,))

                assistants = cursor.fetchall()
                migrated = 0
                renamed = []

                for assistant_id, name, owner in assistants:
                    # Check for conflict
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {self.table_prefix}assistants
                        WHERE organization_id = ? AND name = ? AND owner = ?
                    """, (target_org_id, name, owner))

                    conflict_exists = cursor.fetchone()[0] > 0

                    if conflict_exists:
                        if conflict_strategy == "skip":
                            logger.warning(
                                f"Skipping assistant {name} (conflict detected)")
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(
                                f"Conflict detected for assistant '{name}' owned by '{owner}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}assistants
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, assistant_id))
                            renamed.append(
                                {"id": assistant_id, "old_name": name, "new_name": new_name, "owner": owner})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}assistants
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, assistant_id))

                    migrated += 1

                logger.info(
                    f"Migrated {migrated} assistants from org {source_org_id} to {target_org_id} ({len(renamed)} renamed)")
                return {"count": migrated, "renamed": renamed}

        except sqlite3.Error as e:
            logger.error(f"Error migrating assistants: {e}")
            raise
        finally:
            connection.close()

    def migrate_templates(self, source_org_id: int, target_org_id: int, source_org_slug: str,
                          conflict_strategy: str = "rename") -> Dict[str, Any]:
        """
        Migrate prompt templates from source to target organization with conflict resolution.

        Args:
            source_org_id: Source organization ID
            target_org_id: Target organization ID
            source_org_slug: Source organization slug (for renaming)
            conflict_strategy: "rename" (prefix with org slug), "skip", or "fail"

        Returns:
            Dict with count and renamed list
        """
        connection = self.get_connection()
        if not connection:
            return {"count": 0, "renamed": []}

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Get all templates from source org
                cursor.execute(f"""
                    SELECT id, name, owner_email FROM {self.table_prefix}prompt_templates
                    WHERE organization_id = ?
                """, (source_org_id,))

                templates = cursor.fetchall()
                migrated = 0
                renamed = []

                for template_id, name, owner_email in templates:
                    # Check for conflict
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {self.table_prefix}prompt_templates
                        WHERE organization_id = ? AND name = ? AND owner_email = ?
                    """, (target_org_id, name, owner_email))

                    conflict_exists = cursor.fetchone()[0] > 0

                    if conflict_exists:
                        if conflict_strategy == "skip":
                            logger.warning(
                                f"Skipping template {name} (conflict detected)")
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(
                                f"Conflict detected for template '{name}' owned by '{owner_email}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}prompt_templates
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, template_id))
                            renamed.append(
                                {"id": template_id, "old_name": name, "new_name": new_name, "owner_email": owner_email})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}prompt_templates
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, template_id))

                    migrated += 1

                logger.info(
                    f"Migrated {migrated} templates from org {source_org_id} to {target_org_id} ({len(renamed)} renamed)")
                return {"count": migrated, "renamed": renamed}

        except sqlite3.Error as e:
            logger.error(f"Error migrating templates: {e}")
            raise
        finally:
            connection.close()

    def migrate_kb_registry(self, source_org_id: int, target_org_id: int) -> int:
        """Migrate KB registry entries from source to target organization"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry
                    SET organization_id = ?, updated_at = ?
                    WHERE organization_id = ?
                """, (target_org_id, now, source_org_id))

                migrated = cursor.rowcount
                logger.info(
                    f"Migrated {migrated} KB registry entries from org {source_org_id} to {target_org_id}")
                return migrated

        except sqlite3.Error as e:
            logger.error(f"Error migrating KB registry: {e}")
            raise
        finally:
            connection.close()

    def migrate_usage_logs(self, source_org_id: int, target_org_id: int) -> int:
        """Migrate usage logs from source to target organization"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    UPDATE {self.table_prefix}usage_logs
                    SET organization_id = ?
                    WHERE organization_id = ?
                """, (target_org_id, source_org_id))

                migrated = cursor.rowcount
                logger.info(
                    f"Migrated {migrated} usage logs from org {source_org_id} to {target_org_id}")
                return migrated

        except sqlite3.Error as e:
            logger.error(f"Error migrating usage logs: {e}")
            raise
        finally:
            connection.close()

    def migrate_organization_comprehensive(self, source_org_id: int, target_org_id: int,
                                           source_org_slug: str, conflict_strategy: str = "rename",
                                           preserve_admin_roles: bool = False) -> Dict[str, Any]:
        """
        Comprehensive organization migration with transaction safety.
        All operations use the same connection for atomicity.

        Args:
            source_org_id: Source organization ID
            target_org_id: Target organization ID
            source_org_slug: Source organization slug
            conflict_strategy: "rename", "skip", or "fail"
            preserve_admin_roles: Whether to preserve admin roles

        Returns:
            Migration report dict
        """
        connection = self.get_connection()
        if not connection:
            return {
                "success": False,
                "error": "Database connection failed",
                "resources_migrated": {},
                "conflicts_resolved": {}
            }

        migration_report = {
            "success": False,
            "resources_migrated": {},
            "conflicts_resolved": {},
            "errors": []
        }

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # 1. Migrate users
                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET organization_id = ?, updated_at = ?
                    WHERE organization_id = ?
                """, (target_org_id, now, source_org_id))
                users_migrated = cursor.rowcount
                migration_report["resources_migrated"]["users"] = users_migrated
                logger.info(f"Migrated {users_migrated} users")

                # 2. Migrate roles
                cursor.execute(f"""
                    SELECT user_id, role FROM {self.table_prefix}organization_roles
                    WHERE organization_id = ?
                """, (source_org_id,))
                roles = cursor.fetchall()
                roles_migrated = 0
                for user_id, role in roles:
                    target_role = role if preserve_admin_roles else (
                        'member' if role in ['admin', 'owner'] else role)
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                        (organization_id, user_id, role, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (target_org_id, user_id, target_role, now, now))
                    roles_migrated += 1
                migration_report["resources_migrated"]["roles"] = roles_migrated
                logger.info(f"Migrated {roles_migrated} roles")

                # 3. Migrate assistants
                cursor.execute(f"""
                    SELECT id, name, owner FROM {self.table_prefix}assistants
                    WHERE organization_id = ?
                """, (source_org_id,))
                assistants = cursor.fetchall()
                assistants_migrated = 0
                assistants_renamed = []
                for assistant_id, name, owner in assistants:
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {self.table_prefix}assistants
                        WHERE organization_id = ? AND name = ? AND owner = ?
                    """, (target_org_id, name, owner))
                    conflict_exists = cursor.fetchone()[0] > 0

                    if conflict_exists:
                        if conflict_strategy == "skip":
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(
                                f"Conflict detected for assistant '{name}' owned by '{owner}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}assistants
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, assistant_id))
                            assistants_renamed.append(
                                {"id": assistant_id, "old_name": name, "new_name": new_name, "owner": owner})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}assistants
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, assistant_id))
                    assistants_migrated += 1
                migration_report["resources_migrated"]["assistants"] = assistants_migrated
                migration_report["conflicts_resolved"]["assistants_renamed"] = len(
                    assistants_renamed)
                logger.info(
                    f"Migrated {assistants_migrated} assistants ({len(assistants_renamed)} renamed)")

                # 4. Migrate templates
                cursor.execute(f"""
                    SELECT id, name, owner_email FROM {self.table_prefix}prompt_templates
                    WHERE organization_id = ?
                """, (source_org_id,))
                templates = cursor.fetchall()
                templates_migrated = 0
                templates_renamed = []
                for template_id, name, owner_email in templates:
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {self.table_prefix}prompt_templates
                        WHERE organization_id = ? AND name = ? AND owner_email = ?
                    """, (target_org_id, name, owner_email))
                    conflict_exists = cursor.fetchone()[0] > 0

                    if conflict_exists:
                        if conflict_strategy == "skip":
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(
                                f"Conflict detected for template '{name}' owned by '{owner_email}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}prompt_templates
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, template_id))
                            templates_renamed.append(
                                {"id": template_id, "old_name": name, "new_name": new_name, "owner_email": owner_email})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}prompt_templates
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, template_id))
                    templates_migrated += 1
                migration_report["resources_migrated"]["templates"] = templates_migrated
                migration_report["conflicts_resolved"]["templates_renamed"] = len(
                    templates_renamed)
                logger.info(
                    f"Migrated {templates_migrated} templates ({len(templates_renamed)} renamed)")

                # 5. Migrate KB registry
                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry
                    SET organization_id = ?, updated_at = ?
                    WHERE organization_id = ?
                """, (target_org_id, now, source_org_id))
                kbs_migrated = cursor.rowcount
                migration_report["resources_migrated"]["kbs"] = kbs_migrated
                logger.info(f"Migrated {kbs_migrated} KB registry entries")

                # 6. Migrate usage logs
                cursor.execute(f"""
                    UPDATE {self.table_prefix}usage_logs
                    SET organization_id = ?
                    WHERE organization_id = ?
                """, (target_org_id, source_org_id))
                logs_migrated = cursor.rowcount
                migration_report["resources_migrated"]["usage_logs"] = logs_migrated
                logger.info(f"Migrated {logs_migrated} usage logs")

                # All migrations successful
                migration_report["success"] = True
                logger.info(
                    f"Successfully migrated organization {source_org_id} to {target_org_id}")

                return migration_report

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during migration: {error_msg}")
            migration_report["success"] = False
            migration_report["errors"].append(error_msg)
            # Transaction will rollback automatically on exception
            raise
        finally:
            connection.close()

    def list_organizations(self, status: str = None) -> List[Dict[str, Any]]:
        """List all organizations, optionally filtered by status"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                if status:
                    query = f"""
                        SELECT id, slug, name, is_system, status, config, created_at, updated_at
                        FROM {self.table_prefix}organizations
                        WHERE status = ?
                        ORDER BY created_at DESC
                    """
                    cursor.execute(query, (status,))
                else:
                    query = f"""
                        SELECT id, slug, name, is_system, status, config, created_at, updated_at
                        FROM {self.table_prefix}organizations
                        ORDER BY created_at DESC
                    """
                    cursor.execute(query)

                organizations = []
                for row in cursor.fetchall():
                    organizations.append({
                        'id': row[0],
                        'slug': row[1],
                        'name': row[2],
                        'is_system': bool(row[3]),
                        'status': row[4],
                        'config': json.loads(row[5]) if row[5] else {},
                        'created_at': row[6],
                        'updated_at': row[7]
                    })

                return organizations

        except sqlite3.Error as e:
            logger.error(f"Error listing organizations: {e}")
            return []
        finally:
            connection.close()

    # Organization Role Management

    def assign_organization_role(self, organization_id: int, user_id: int, role: str) -> bool:
        """Assign a role to a user in an organization"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Insert or update role
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                    (organization_id, user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (organization_id, user_id, role, now, now))

                logger.info(
                    f"Assigned role '{role}' to user {user_id} in organization {organization_id}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Error assigning organization role: {e}")
            return False
        finally:
            connection.close()

    def get_organization_users(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get all users in an organization with their roles"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()
                # Use LEFT JOIN to include users who might not have explicit roles yet
                # For users without explicit roles, default to 'member'
                cursor.execute(f"""
                    SELECT u.id, u.user_email, u.user_name, 
                           COALESCE(r.role, 'member') as role, 
                           COALESCE(r.created_at, u.created_at) as joined_at,
                           u.user_type, u.auth_provider, u.lti_user_id
                    FROM {self.table_prefix}Creator_users u
                    LEFT JOIN {self.table_prefix}organization_roles r ON u.id = r.user_id AND r.organization_id = ?
                    WHERE u.organization_id = ?
                    ORDER BY joined_at
                """, (organization_id, organization_id))

                users = []
                for row in cursor.fetchall():
                    users.append({
                        'id': row[0],
                        'email': row[1],
                        'name': row[2],
                        'role': row[3],
                        'joined_at': row[4],
                        'user_type': row[5],
                        'auth_provider': row[6] or 'password',
                        'lti_user_id': row[7]
                    })

                return users

        except sqlite3.Error as e:
            logger.error(f"Error getting organization users: {e}")
            return []
        finally:
            connection.close()

    def get_user_organizations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all organizations a user belongs to"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT o.id, o.slug, o.name, o.is_system, o.status,
                           ur.role, o.created_at, o.updated_at
                    FROM {self.table_prefix}organizations o
                    JOIN {self.table_prefix}organization_roles ur ON o.id = ur.organization_id
                    WHERE ur.user_id = ?
                    ORDER BY o.is_system DESC, o.name
                """, (user_id,))

                results = cursor.fetchall()
                organizations = []
                for row in results:
                    organizations.append({
                        'id': row[0],
                        'slug': row[1],
                        'name': row[2],
                        'is_system': row[3],
                        'status': row[4],
                        'role': row[5],  # User's role in this organization
                        'created_at': row[6],
                        'updated_at': row[7]
                    })

                return organizations

        except sqlite3.Error as e:
            logger.error(f"Error getting user organizations: {e}")
            return []
        finally:
            connection.close()

    def get_user_organization_role(self, user_id: int, organization_id: int) -> Optional[str]:
        """
        Get the user's role in a specific organization

        Args:
            user_id: LAMB creator user ID
            organization_id: Organization ID

        Returns:
            Role string ('owner', 'admin', 'member') or None if not found
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT role
                    FROM {self.table_prefix}organization_roles
                    WHERE user_id = ? AND organization_id = ?
                """, (user_id, organization_id))

                result = cursor.fetchone()
                return result[0] if result else None

        except sqlite3.Error as e:
            logger.error(f"Error getting user organization role: {e}")
            return None
        finally:
            connection.close()

    def update_user_organization(self, user_id: int, organization_id: int) -> bool:
        """Update user's organization assignment"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET organization_id = ?, updated_at = ?
                    WHERE id = ?
                """, (organization_id, now, user_id))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error updating user organization: {e}")
            return False
        finally:
            connection.close()

    def update_user_config(self, user_id: int, user_config: dict) -> bool:
        """
        Update user's configuration (stored as JSON).

        Args:
            user_id: User ID to update
            user_config: Dictionary of user configuration

        Returns:
            bool: True if update successful, False otherwise
        """
        import json as json_lib

        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())

                # Convert dict to JSON string
                config_json = json_lib.dumps(user_config)

                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET user_config = ?, updated_at = ?
                    WHERE id = ?
                """, (config_json, now, user_id))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error updating user config: {e}")
            return False
        finally:
            connection.close()

    def _get_default_org_config(self) -> Dict[str, Any]:
        """Get default configuration for new organizations"""
        return {
            "version": "1.0",
            "setups": {
                "default": {
                    "name": "Default Setup",
                    "is_default": True,
                    "global_default_model": {
                        "provider": "",
                        "model": ""
                    },
                    "small_fast_model": {
                        "provider": "",
                        "model": ""
                    },
                    "providers": {},
                    "knowledge_base": {}
                }
            },
            "features": {
                "rag_enabled": True,
                "mcp_enabled": True,
                "lti_publishing": True,
                "signup_enabled": False,
                "sharing_enabled": True  # Controls if users can share assistants/resources
            },
            "limits": {
                "usage": {
                    "tokens_per_month": 1000000,
                    "max_assistants": 100,
                    "max_assistants_per_user": 10,
                    "storage_gb": 10
                }
            }
        }

    def get_system_org_config_as_baseline(self) -> Dict[str, Any]:
        """Get system organization configuration to use as baseline for new organizations"""
        system_org = self.get_organization_by_slug("lamb")
        if not system_org:
            logger.warning(
                "System organization not found, using default config")
            return self._get_default_org_config()

        # Deep copy the system config and modify it for new organizations
        import copy
        baseline_config = copy.deepcopy(system_org['config'])

        # Modify for non-system organizations
        baseline_config['metadata'] = {
            "description": "Organization created from system baseline",
            "system_managed": False,
            "created_from_system": True
        }

        # Set reasonable limits (not unlimited like system org)
        baseline_config['limits'] = {
            "usage": {
                "tokens_per_month": 1000000,
                "max_assistants": 100,
                "max_assistants_per_user": 10,
                "storage_gb": 10
            }
        }

        # Disable signup by default (will be configured during creation)
        if 'features' not in baseline_config:
            baseline_config['features'] = {}
        baseline_config['features']['signup_enabled'] = False
        if 'signup_key' in baseline_config['features']:
            del baseline_config['features']['signup_key']

        return baseline_config

    def get_system_org_users(self) -> List[Dict[str, Any]]:
        """Get all users from the system organization ('lamb') for admin assignment"""
        system_org = self.get_organization_by_slug("lamb")
        if not system_org:
            logger.error("System organization not found")
            return []

        return self.get_organization_users(system_org['id'])

    def validate_signup_key_uniqueness(self, signup_key: str, exclude_org_id: Optional[int] = None) -> bool:
        """Validate that signup key is unique across all organizations"""
        if not signup_key or len(signup_key.strip()) == 0:
            return False

        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Search for existing signup key in all organization configs
                if exclude_org_id:
                    cursor.execute(f"""
                        SELECT id, config FROM {self.table_prefix}organizations
                        WHERE id != ?
                    """, (exclude_org_id,))
                else:
                    cursor.execute(f"""
                        SELECT id, config FROM {self.table_prefix}organizations
                    """)

                for row in cursor.fetchall():
                    org_id, config_json = row
                    try:
                        config = json.loads(config_json)
                        existing_key = config.get(
                            'features', {}).get('signup_key')
                        if existing_key and existing_key.strip() == signup_key.strip():
                            logger.warning(
                                f"Signup key '{signup_key}' already exists in organization {org_id}")
                            return False
                    except json.JSONDecodeError:
                        continue

                return True

        except sqlite3.Error as e:
            logger.error(f"Error validating signup key uniqueness: {e}")
            return False
        finally:
            connection.close()

    def validate_signup_key_format(self, signup_key: str) -> tuple[bool, str]:
        """Validate signup key format and return (is_valid, error_message)"""
        if not signup_key:
            return False, "Signup key is required"

        signup_key = signup_key.strip()

        # Minimum length requirement
        if len(signup_key) < 8:
            return False, "Signup key must be at least 8 characters long"

        # Maximum length requirement
        if len(signup_key) > 64:
            return False, "Signup key must be no more than 64 characters long"

        # Character validation - allow alphanumeric, hyphens, and underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', signup_key):
            return False, "Signup key can only contain letters, numbers, hyphens, and underscores"

        # Must not start or end with hyphen or underscore
        if signup_key.startswith(('-', '_')) or signup_key.endswith(('-', '_')):
            return False, "Signup key cannot start or end with hyphen or underscore"

        return True, ""

    def get_organization_by_signup_key(self, signup_key: str) -> Optional[Dict[str, Any]]:
        """Find organization by signup key and return organization data if signup is enabled"""
        if not signup_key or len(signup_key.strip()) == 0:
            return None

        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()

                # Search for organization with matching signup key
                cursor.execute(f"""
                    SELECT id, slug, name, is_system, status, config, created_at, updated_at 
                    FROM {self.table_prefix}organizations
                    WHERE status = 'active'
                """)

                for row in cursor.fetchall():
                    org_id, slug, name, is_system, status, config_json, created_at, updated_at = row
                    try:
                        config = json.loads(config_json)
                        features = config.get('features', {})
                        existing_key = features.get('signup_key')
                        signup_enabled = features.get('signup_enabled', False)

                        # Check if this organization has the matching signup key and signup is enabled
                        if (existing_key and existing_key.strip() == signup_key.strip() and signup_enabled):
                            logger.info(
                                f"Found organization '{slug}' (ID: {org_id}) for signup key")
                            return {
                                'id': org_id,
                                'slug': slug,
                                'name': name,
                                'is_system': bool(is_system),
                                'status': status,
                                'config': config,
                                'created_at': created_at,
                                'updated_at': updated_at
                            }
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON config for organization {org_id}")
                        continue

                logger.info(
                    f"No organization found for signup key '{signup_key}'")
                return None

        except sqlite3.Error as e:
            logger.error(f"Error finding organization by signup key: {e}")
            return None
        finally:
            connection.close()

    def is_system_admin(self, user_email: str) -> bool:
        """
        Check if a user is a system admin by verifying:
        1. They have admin role in OWI
        2. They have admin role in the system organization ("lamb")

        This handles the dual admin requirement in our evolving system.
        """
        try:
            # Check OWI admin status
            owi_manager = OwiUserManager()
            owi_user = owi_manager.get_user_by_email(user_email)
            if not owi_user or owi_user.get('role') != 'admin':
                return False

            # Check LAMB system organization admin status
            creator_user = self.get_creator_user_by_email(user_email)
            if not creator_user:
                return False

            # Get system organization
            system_org = self.get_organization_by_slug("lamb")
            if not system_org:
                logger.warning("System organization 'lamb' not found")
                return False

            # Check user's role in system organization
            user_role = self.get_user_organization_role(
                creator_user['id'], system_org['id'])
            return user_role == 'admin'

        except Exception as e:
            logger.error(
                f"Error checking system admin status for {user_email}: {e}")
            return False

    def is_organization_admin(self, user_email: str, organization_id: int) -> bool:
        """
        Check if a user is an admin or owner of a specific organization
        """
        try:
            creator_user = self.get_creator_user_by_email(user_email)
            if not creator_user:
                return False

            user_role = self.get_user_organization_role(
                creator_user['id'], organization_id)
            return user_role in ['admin', 'owner']

        except Exception as e:
            logger.error(f"Error checking organization admin status: {e}")
            return False

    def get_creator_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get creator user details by ID

        Args:
            user_id (str): User ID to look up

        Returns:
            Optional[Dict]: User details if found, None otherwise
            Returns dict with: id, email, name, user_config
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, organization_id, user_email, user_name, user_config 
                    FROM {self.table_prefix}Creator_users 
                    WHERE id = ?
                """, (user_id,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'organization_id': result[1],
                    'user_email': result[2],
                    'user_name': result[3],
                    'user_config': json.loads(result[4]) if result[4] else {}
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_creator_user_by_id: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in get_creator_user_by_id: {e}")
            return None
        finally:
            connection.close()

    def get_creator_user_by_email(self, user_email: str) -> Optional[Dict[str, Any]]:
        """
        Get creator user details by email

        Args:
            user_email (str): Email to look up

        Returns:
            Optional[Dict]: User details if found, None otherwise
            Returns dict with: id, email, name, user_config, lti_user_id, auth_provider
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, organization_id, user_email, user_name, user_type, user_config,
                           enabled, lti_user_id, auth_provider, password_hash, role
                    FROM {self.table_prefix}Creator_users
                    WHERE user_email = ?
                """, (user_email,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'organization_id': result[1],
                    'email': result[2],
                    'name': result[3],
                    'user_type': result[4],
                    'user_config': json.loads(result[5]) if result[5] else {},
                    'enabled': bool(result[6]) if len(result) > 6 else True,
                    'lti_user_id': result[7] if len(result) > 7 else None,
                    'auth_provider': result[8] if len(result) > 8 else 'password',
                    'password_hash': result[9] if len(result) > 9 else None,
                    'role': result[10] if len(result) > 10 else 'user'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_creator_user_by_email: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in get_creator_user_by_email: {e}")
            return None
        finally:
            connection.close()
 #           logger.debug("Database connection closed")

    def update_creator_user_password_hash(self, user_email: str, password_hash: str) -> bool:
        """Update the password_hash column for a creator user."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET password_hash = ?, updated_at = ?
                    WHERE user_email = ?
                """, (password_hash, int(time.time()), user_email))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating password_hash for {user_email}: {e}")
            return False
        finally:
            connection.close()

    def update_creator_user_role(self, user_email: str, role: str) -> bool:
        """Update the role column for a creator user."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET role = ?, updated_at = ?
                    WHERE user_email = ?
                """, (role, int(time.time()), user_email))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating role for {user_email}: {e}")
            return False
        finally:
            connection.close()

    def create_creator_user(self, user_email: str, user_name: str, password: str, organization_id: int = None, user_type: str = 'creator'):
        """
        Create a new creator user after verifying/creating OWI user

        Args:
            user_email (str): User's email
            user_name (str): User's name
            password (str): User's password
            organization_id (int): Organization ID (if None, uses system org)
            user_type (str): Type of user - 'creator' (default) or 'end_user'

        Returns:
            Optional[int]: ID of created user or None if creation fails
        """
        logger.debug(f"Creating creator user: {user_email}")

        try:
            # First check if creator user already exists
            connection = self.get_connection()
            if not connection:
                logger.error("Could not establish database connection")
                return None

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}Creator_users
                    WHERE user_email = ?
                """, (user_email,))

                if cursor.fetchone():
                    logger.warning(
                        f"Creator user {user_email} already exists")
                    return None

            # Hash password locally (LAMB is source of truth)
            from lamb.auth import hash_password
            local_hash = hash_password(password)

            # Create OWI mirror user (best-effort, non-fatal during dual-write)
            try:
                owi_manager = OwiUserManager()
                owi_user = owi_manager.get_user_by_email(user_email)

                if not owi_user:
                    logger.debug(f"Creating OWI mirror user for {user_email}")
                    owi_user = owi_manager.create_user(
                        name=user_name,
                        email=user_email,
                        password=password,
                        role="user"
                    )
                    if not owi_user:
                        logger.warning(f"Failed to create OWI mirror user for {user_email} (non-fatal)")
            except Exception as owi_err:
                logger.warning(f"OWI mirror user creation failed for {user_email} (non-fatal): {owi_err}")

            # If no organization_id provided, use system organization
            if organization_id is None:
                system_org = self.get_organization_by_slug("lamb")
                if system_org:
                    organization_id = system_org['id']
                else:
                    logger.error("System organization not found")
                    return None

            # Now create the creator user with password_hash and role
            now = int(time.time())
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}Creator_users
                    (organization_id, user_email, user_name, user_type, user_config,
                     password_hash, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (organization_id, user_email, user_name, user_type, "{}",
                      local_hash, "user", now, now))

                new_user_id = cursor.lastrowid
                logger.info(
                    f"Creator user {user_email} created successfully with id: {new_user_id}")
                return new_user_id

        except Exception as e:
            logger.error(f"Error creating creator user: {e}")
            return None
        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed")

    def delete_creator_user(self, user_id: int) -> bool:
        """
        Delete a creator user from the LAMB database

        Args:
            user_id (int): The user ID to delete

        Returns:
            bool: True if user was deleted successfully, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return False

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"DELETE FROM {self.table_prefix}Creator_users WHERE id = ?",
                    (user_id,)
                )

                if cursor.rowcount > 0:
                    logger.info(
                        f"Creator user with id {user_id} deleted successfully from LAMB database")
                    return True
                else:
                    logger.warning(f"No creator user found with id {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting creator user: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def disable_user(self, user_id: int) -> bool:
        """
        Disable a user account

        Args:
            user_id: User ID to disable

        Returns:
            bool: True if successful, False if user not found or already disabled
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Check current status
                cursor.execute(
                    f"SELECT enabled FROM {self.table_prefix}Creator_users WHERE id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"User {user_id} not found")
                    return False

                if row[0] == 0:  # Already disabled
                    logger.info(f"User {user_id} already disabled")
                    return False

                # Disable user
                cursor.execute(
                    f"""UPDATE {self.table_prefix}Creator_users 
                        SET enabled = 0, updated_at = ? 
                        WHERE id = ?""",
                    (int(time.time()), user_id)
                )
                logger.info(f"Successfully disabled user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error disabling user {user_id}: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def enable_user(self, user_id: int) -> bool:
        """
        Enable a user account

        Args:
            user_id: User ID to enable

        Returns:
            bool: True if successful, False if user not found or already enabled
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Check current status
                cursor.execute(
                    f"SELECT enabled FROM {self.table_prefix}Creator_users WHERE id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"User {user_id} not found")
                    return False

                if row[0] == 1:  # Already enabled
                    logger.info(f"User {user_id} already enabled")
                    return False

                # Enable user
                cursor.execute(
                    f"""UPDATE {self.table_prefix}Creator_users 
                        SET enabled = 1, updated_at = ? 
                        WHERE id = ?""",
                    (int(time.time()), user_id)
                )
                logger.info(f"Successfully enabled user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error enabling user {user_id}: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def is_user_enabled(self, user_id: int) -> bool:
        """
        Check if user account is enabled

        Args:
            user_id: User ID to check

        Returns:
            bool: True if enabled, False if disabled or not found
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT enabled FROM {self.table_prefix}Creator_users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row and row[0] == 1

        except Exception as e:
            logger.error(f"Error checking user enabled status: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def check_user_dependencies(self, user_id: int) -> Dict[str, Any]:
        """
        Check if a user has any dependencies (assistants or knowledge bases)

        Args:
            user_id: User ID to check

        Returns:
            Dict with:
                - has_dependencies (bool): True if user has any dependencies
                - assistant_count (int): Number of assistants owned by user
                - kb_count (int): Number of knowledge bases owned by user
                - assistants (List[Dict]): List of assistant names and IDs
                - kbs (List[Dict]): List of KB names and IDs
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return {
                'has_dependencies': False,
                'assistant_count': 0,
                'kb_count': 0,
                'assistants': [],
                'kbs': []
            }

        try:
            cursor = connection.cursor()

            # Get user email for owner lookup
            cursor.execute(
                f"SELECT user_email FROM {self.table_prefix}Creator_users WHERE id = ?",
                (user_id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                logger.warning(f"User {user_id} not found")
                return {
                    'has_dependencies': False,
                    'assistant_count': 0,
                    'kb_count': 0,
                    'assistants': [],
                    'kbs': []
                }

            user_email = user_row[0]

            # Check assistants owned by user (using owner = user_email)
            cursor.execute(
                f"SELECT id, name FROM {self.table_prefix}assistants WHERE owner = ?",
                (user_email,)
            )
            assistants = [{'id': row[0], 'name': row[1]}
                          for row in cursor.fetchall()]
            assistant_count = len(assistants)

            # Check knowledge bases owned by user
            cursor.execute(
                f"SELECT kb_id, kb_name FROM {self.table_prefix}kb_registry WHERE owner_user_id = ?",
                (user_id,)
            )
            kbs = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
            kb_count = len(kbs)

            has_dependencies = assistant_count > 0 or kb_count > 0

            logger.info(
                f"User {user_id} has {assistant_count} assistants and {kb_count} KBs")

            return {
                'has_dependencies': has_dependencies,
                'assistant_count': assistant_count,
                'kb_count': kb_count,
                'assistants': assistants,
                'kbs': kbs
            }

        except Exception as e:
            logger.error(f"Error checking user dependencies: {e}")
            return {
                'has_dependencies': False,
                'assistant_count': 0,
                'kb_count': 0,
                'assistants': [],
                'kbs': []
            }
        finally:
            if connection:
                connection.close()

    def delete_user_safe(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Safely delete a user after checking they are disabled and have no dependencies

        Args:
            user_id: User ID to delete

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return False, "Database connection failed"

        try:
            with connection:
                cursor = connection.cursor()

                # Check if user exists and is disabled
                cursor.execute(
                    f"SELECT enabled, user_email, user_name FROM {self.table_prefix}Creator_users WHERE id = ?",
                    (user_id,)
                )
                user_row = cursor.fetchone()

                if not user_row:
                    logger.warning(f"User {user_id} not found")
                    return False, "User not found"

                is_enabled = user_row[0]
                user_email = user_row[1]
                user_name = user_row[2]

                # Safety check: user must be disabled
                if is_enabled:
                    logger.warning(
                        f"Attempted to delete enabled user {user_id} ({user_email})")
                    return False, "User must be disabled before deletion"

                # Check for dependencies
                dependencies = self.check_user_dependencies(user_id)

                if dependencies['has_dependencies']:
                    error_parts = []
                    if dependencies['assistant_count'] > 0:
                        error_parts.append(
                            f"{dependencies['assistant_count']} assistant(s)")
                    if dependencies['kb_count'] > 0:
                        error_parts.append(
                            f"{dependencies['kb_count']} knowledge base(s)")

                    error_msg = f"User has dependencies: {', '.join(error_parts)}. Please delete or reassign these resources first."
                    logger.warning(
                        f"Cannot delete user {user_id} ({user_email}): {error_msg}")
                    return False, error_msg

                # Safe to delete - user is disabled and has no dependencies
                cursor.execute(
                    f"DELETE FROM {self.table_prefix}Creator_users WHERE id = ?",
                    (user_id,)
                )

                if cursor.rowcount > 0:
                    logger.info(
                        f"Successfully deleted disabled user {user_id} ({user_email}, {user_name})")
                    return True, None
                else:
                    logger.warning(f"No user deleted with id {user_id}")
                    return False, "User not found"

        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False, f"Database error: {str(e)}"
        finally:
            if connection:
                connection.close()

    def disable_users_bulk(self, user_ids: List[int]) -> Dict[str, Any]:
        """
        Disable multiple user accounts in a single transaction

        Args:
            user_ids: List of user IDs to disable

        Returns:
            Dict with success/failed lists and counts
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return {"success": [], "failed": user_ids, "already_disabled": []}

        results = {"success": [], "failed": [], "already_disabled": []}

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                for user_id in user_ids:
                    try:
                        # Check if user exists and current status
                        cursor.execute(
                            f"SELECT enabled FROM {self.table_prefix}Creator_users WHERE id = ?",
                            (user_id,)
                        )
                        row = cursor.fetchone()

                        if not row:
                            results["failed"].append(user_id)
                            continue

                        if row[0] == 0:  # Already disabled
                            results["already_disabled"].append(user_id)
                            continue

                        # Disable user
                        cursor.execute(
                            f"""UPDATE {self.table_prefix}Creator_users 
                                SET enabled = 0, updated_at = ? 
                                WHERE id = ?""",
                            (current_time, user_id)
                        )
                        results["success"].append(user_id)
                    except Exception as e:
                        logger.error(f"Error disabling user {user_id}: {e}")
                        results["failed"].append(user_id)

                logger.info(
                    f"Bulk disable: {len(results['success'])} successful, {len(results['failed'])} failed")

        except Exception as e:
            logger.error(f"Error in bulk disable: {e}")
            # Mark all as failed
            results["failed"].extend([uid for uid in user_ids if uid not in results["success"]
                                     and uid not in results["already_disabled"] and uid not in results["failed"]])
        finally:
            if connection:
                connection.close()

        return results

    def enable_users_bulk(self, user_ids: List[int]) -> Dict[str, Any]:
        """
        Enable multiple user accounts in a single transaction

        Args:
            user_ids: List of user IDs to enable

        Returns:
            Dict with success/failed lists and counts
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return {"success": [], "failed": user_ids, "already_enabled": []}

        results = {"success": [], "failed": [], "already_enabled": []}

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                for user_id in user_ids:
                    try:
                        # Check if user exists and current status
                        cursor.execute(
                            f"SELECT enabled FROM {self.table_prefix}Creator_users WHERE id = ?",
                            (user_id,)
                        )
                        row = cursor.fetchone()

                        if not row:
                            results["failed"].append(user_id)
                            continue

                        if row[0] == 1:  # Already enabled
                            results["already_enabled"].append(user_id)
                            continue

                        # Enable user
                        cursor.execute(
                            f"""UPDATE {self.table_prefix}Creator_users 
                                SET enabled = 1, updated_at = ? 
                                WHERE id = ?""",
                            (current_time, user_id)
                        )
                        results["success"].append(user_id)
                    except Exception as e:
                        logger.error(f"Error enabling user {user_id}: {e}")
                        results["failed"].append(user_id)

                logger.info(
                    f"Bulk enable: {len(results['success'])} successful, {len(results['failed'])} failed")

        except Exception as e:
            logger.error(f"Error in bulk enable: {e}")
            # Mark all as failed
            results["failed"].extend([uid for uid in user_ids if uid not in results["success"]
                                     and uid not in results["already_enabled"] and uid not in results["failed"]])
        finally:
            if connection:
                connection.close()

        return results

    def log_bulk_import(
        self,
        organization_id: int,
        admin_user_id: int,
        admin_email: str,
        operation_type: str,
        total_count: int,
        success_count: int,
        failure_count: int,
        details: Dict[str, Any]
    ) -> Optional[int]:
        """
        Log a bulk import operation to the database

        Args:
            organization_id: Organization ID
            admin_user_id: ID of the admin performing the operation
            admin_email: Email of the admin
            operation_type: Type of operation (user_creation, user_activation, user_deactivation)
            total_count: Total number of items processed
            success_count: Number of successful operations
            failure_count: Number of failed operations
            details: Additional details as JSON dict

        Returns:
            Log ID if successful, None if failed
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                cursor.execute(
                    f"""INSERT INTO {self.table_prefix}bulk_import_logs 
                        (organization_id, admin_user_id, admin_email, operation_type, 
                         total_count, success_count, failure_count, details, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        organization_id,
                        admin_user_id,
                        admin_email,
                        operation_type,
                        total_count,
                        success_count,
                        failure_count,
                        json.dumps(details),
                        current_time
                    )
                )

                log_id = cursor.lastrowid
                logger.info(
                    f"Logged bulk operation {operation_type} "
                    f"by {admin_email} (ID: {log_id})"
                )
                return log_id

        except sqlite3.Error as e:
            logger.error(f"Error logging bulk operation: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def get_bulk_import_logs(
        self,
        organization_id: Optional[int] = None,
        admin_user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve bulk import logs

        Args:
            organization_id: Filter by organization (optional)
            admin_user_id: Filter by admin user (optional)
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of log dicts
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Failed to get database connection")
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Build query with optional filters
                query = f"""
                    SELECT 
                        l.id,
                        l.organization_id,
                        l.admin_user_id,
                        l.admin_email,
                        l.operation_type,
                        l.total_count,
                        l.success_count,
                        l.failure_count,
                        l.details,
                        l.created_at,
                        o.name as organization_name,
                        u.user_name as admin_name
                    FROM {self.table_prefix}bulk_import_logs l
                    LEFT JOIN {self.table_prefix}organizations o ON l.organization_id = o.id
                    LEFT JOIN {self.table_prefix}Creator_users u ON l.admin_user_id = u.id
                    WHERE 1=1
                """
                params = []

                if organization_id is not None:
                    query += " AND l.organization_id = ?"
                    params.append(organization_id)

                if admin_user_id is not None:
                    query += " AND l.admin_user_id = ?"
                    params.append(admin_user_id)

                query += " ORDER BY l.created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                logs = []
                for row in rows:
                    logs.append({
                        'id': row[0],
                        'organization_id': row[1],
                        'admin_user_id': row[2],
                        'admin_email': row[3],
                        'operation_type': row[4],
                        'total_count': row[5],
                        'success_count': row[6],
                        'failure_count': row[7],
                        'details': json.loads(row[8]) if row[8] else {},
                        'created_at': row[9],
                        'organization_name': row[10],
                        'admin_name': row[11]
                    })

                return logs

        except sqlite3.Error as e:
            logger.error(f"Error retrieving bulk import logs: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def create_lti_user(self, lti_user: LTIUser):
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}lti_users 
                        (assistant_id, assistant_name, group_id, group_name, assistant_owner,
                         user_email, user_name, user_display_name, lti_context_id, lti_app_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (lti_user.assistant_id, lti_user.assistant_name, lti_user.group_id,
                          lti_user.group_name, lti_user.assistant_owner, lti_user.user_email,
                          lti_user.user_name, lti_user.user_display_name,
                          lti_user.lti_context_id, lti_user.lti_app_id))
                    logger.info(
                        f"LTI user {lti_user.user_email} created with id: {cursor.lastrowid}")
                    return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Error creating LTI user: {e}")
                return None
            finally:
                connection.close()
   #             logger.debug("Database connection closed")
        return None

    def get_lti_user_by_email(self, user_email):
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        f"SELECT * FROM {self.table_prefix}lti_users WHERE user_email = ?", (user_email,))
                    user_data = cursor.fetchone()

                    if user_data:
                        # Get column names
                        cursor.execute(
                            f"PRAGMA table_info({self.table_prefix}lti_users)")
                        columns = [column[1] for column in cursor.fetchall()]

                        # Create a dictionary mapping column names to values
                        user_dict = dict(zip(columns, user_data))
                        return {
                            'id': user_dict['id'],
                            'assistant_id': user_dict['assistant_id'],
                            'assistant_name': user_dict['assistant_name'],
                            'group_id': user_dict['group_id'],
                            'group_name': user_dict['group_name'],
                            'assistant_owner': user_dict['assistant_owner'],
                            'user_email': user_dict['user_email'],
                            'user_name': user_dict['user_name'],
                            'user_display_name': user_dict['user_display_name'],
                            'lti_context_id': user_dict['lti_context_id'],
                            'lti_app_id': user_dict['lti_app_id']
                        }
                    return None
            except sqlite3.Error as e:
                logger.error(f"Error getting LTI user: {e}")
                return None
            finally:
                connection.close()
        return None

    def update_model_permissions(self, user_data):
        #        logger.debug("Entering update_model_permissions method")
        #        logger.debug(f"Received user_data: {user_data}")
        try:
            connection = self.get_connection()
            logger.debug("Database connection established")

            with connection:
                cursor = connection.cursor()
                user_email = user_data['user_email']
                include_models = user_data['filter']['include']
                exclude_models = user_data['filter']['exclude']
#                logger.debug(f"Processing user_email: {user_email}")

                # First, remove all existing permissions for this user
                cursor.execute(
                    f"DELETE FROM {self.table_prefix}model_permissions WHERE user_email = ?", (user_email,))
#                logger.debug(
#                    f"Deleted existing permissions for user: {user_email}")

                # Insert 'include' permissions
                for model in include_models:
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}model_permissions (user_email, model_name, access_type)
                        VALUES (?, ?, ?)
                    """, (user_email, model, 'include'))
                    logger.debug(
                        f"Inserted 'include' permission for model: {model}")

                # Insert 'exclude' permissions
                for model in exclude_models:
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}model_permissions (user_email, model_name, access_type)
                        VALUES (?, ?, ?)
                    """, (user_email, model, 'exclude'))
#                    logger.debug(
#                        f"Inserted 'exclude' permission for model: {model}")

            logger.debug(f"Changes committed to database")

        except sqlite3.Error as e:
            logger.error(f"Error occurred: {e}")

        finally:
            if connection:
                connection.close()
#                logger.debug("SQLite connection closed")

    def get_model_permissions(self, user_email):
        try:
            connection = self.get_connection()

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT model_name, access_type
                    FROM {self.table_prefix}model_permissions
                    WHERE user_email = ?
                """, (user_email,))

                permissions = cursor.fetchall()

                return [
                    {"model_name": model_name, "access_type": access_type}
                    for model_name, access_type in permissions
                ]

        except sqlite3.Error as e:
            logger.error(f"Error: {e}")
            return None

        finally:
            if connection:
                connection.close()

    def filter_models(self, email: str, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter models based on user permissions.

        Args:
            email: User's email address
            models: List of model dictionaries to filter

        Returns:
            List of filtered model dictionaries
        """
        try:
            user_filters = self.get_model_permissions(email)
            if user_filters is None:
                logger.warning(
                    f"No permissions found for user {email}, returning unfiltered models")
                return models
            logger.debug(f"Applying filter for user: {user_filters}")

            include_models = [f['model_name']
                              for f in user_filters if f['access_type'] == 'include']
            exclude_models = [f['model_name']
                              for f in user_filters if f['access_type'] == 'exclude']

            filtered_models = []
            for model in models:
                model_id = model['id'] if isinstance(model, dict) else model
                if model_id in include_models:
                    filtered_models.append(model)
                elif any(model_id.startswith(exclude) for exclude in exclude_models):
                    pass
                elif "*" in exclude_models:
                    pass
                else:
                    filtered_models.append(model)

#            logger.debug(f"Filtered models: {filtered_models}")
            return filtered_models
        except Exception as e:
            logger.error(f"Error in filter_models: {str(e)}")
            raise

    def add_assistant(self, assistant: Assistant):
        """
        Add a new assistant to the database.

        IMPORTANT: The database column 'api_callback' stores what is semantically 'metadata'.
        This mapping is handled by the Assistant model's property. DO NOT change the SQL column name.
        Deprecated fields (pre/post_retrieval_endpoint, RAG_endpoint) are stored as empty strings.
        """
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    # Ensure deprecated fields are always empty strings
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}assistants 
                        (organization_id, name, description, owner, api_callback, system_prompt, prompt_template, 
                        RAG_endpoint, RAG_Top_k, RAG_collections, pre_retrieval_endpoint, post_retrieval_endpoint,
                        created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (assistant.organization_id, assistant.name, assistant.description, assistant.owner,
                          assistant.api_callback,  # This stores the metadata content
                          assistant.system_prompt, assistant.prompt_template,
                          "",  # RAG_endpoint - DEPRECATED, always empty
                          assistant.RAG_Top_k, assistant.RAG_collections,
                          "",  # pre_retrieval_endpoint - DEPRECATED, always empty
                          "",  # post_retrieval_endpoint - DEPRECATED, always empty
                          # created_at (using time.time() since datetime was removed)
                          int(time.time()),
                          int(time.time())))  # updated_at
                    logger.info(
                        f"Assistant {assistant.name} created with id: {cursor.lastrowid}")
                    return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Error creating assistant: {e}")
                return None
            finally:
                connection.close()
#                logger.debug("Database connection closed")
        return None

    def get_assistant_by_id(self, assistant_id: int) -> Optional[Assistant]:
        connection = self.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()
            table_name = self._get_table_name('assistants')
            cursor.execute(
                f"SELECT * FROM {table_name} WHERE id = ?", (assistant_id,))
            assistant_data = cursor.fetchone()
            if not assistant_data:
                return None

            # Get column names
            cursor.execute(f"PRAGMA table_info({self.table_prefix}assistants)")
            columns = [column[1] for column in cursor.fetchall()]

            # Create a dictionary mapping column names to values
            assistant_dict = dict(zip(columns, assistant_data))
            # Create Assistant object from dictionary
            assistant = Assistant(
                id=assistant_dict['id'],
                name=assistant_dict['name'],
                description=assistant_dict['description'],
                owner=assistant_dict['owner'],
                api_callback=assistant_dict['api_callback'],
                system_prompt=assistant_dict['system_prompt'],
                prompt_template=assistant_dict['prompt_template'],
                RAG_endpoint=assistant_dict['RAG_endpoint'],
                RAG_Top_k=assistant_dict['RAG_Top_k'],
                RAG_collections=assistant_dict['RAG_collections'],
                pre_retrieval_endpoint=assistant_dict['pre_retrieval_endpoint'],
                post_retrieval_endpoint=assistant_dict['post_retrieval_endpoint']
            )
            return assistant
        except sqlite3.Error as e:
            logger.error(f"Database error in get_assistant_by_id: {e}")
            return None
        finally:
            connection.close()

    def get_assistant_by_id_with_publication(self, assistant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get assistant with publication data by ID with correct published flag

        Args:
            assistant_id: The assistant ID to get

        Returns:
            Optional[Dict[str, Any]]: Assistant dictionary with publication data if found, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            return None

        assistants_table = self._get_table_name('assistants')
        published_table = self._get_table_name('assistant_publish')

        try:
            with connection:
                cursor = connection.cursor()

                # Get assistant with publication data using LEFT JOIN
                query = f"""
                    SELECT
                        a.id, a.name, a.description, a.owner, a.api_callback,
                        a.organization_id,
                        a.system_prompt, a.prompt_template, a.RAG_endpoint, a.RAG_Top_k,
                        a.RAG_collections, a.pre_retrieval_endpoint, a.post_retrieval_endpoint,
                        a.created_at, a.updated_at,
                        p.group_id, p.group_name, p.oauth_consumer_name, p.created_at as published_at,
                        CASE 
                            WHEN p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {assistants_table} a
                    LEFT JOIN {published_table} p ON a.id = p.assistant_id
                    WHERE a.id = ?
                """
                cursor.execute(query, (assistant_id,))
                result = cursor.fetchone()

                if not result:
                    return None

                # Get column names from the cursor description after execution
                columns = [desc[0] for desc in cursor.description]

                assistant_dict = dict(zip(columns, result))
                # Convert boolean flag back to Python boolean
                assistant_dict['published'] = bool(
                    assistant_dict.get('published'))
                # Handle null strings
                if assistant_dict.get('oauth_consumer_name') == "null":
                    assistant_dict['oauth_consumer_name'] = None
                # Map api_callback to metadata field for new API responses (Phase 1 refactor completion)
                assistant_dict['metadata'] = assistant_dict.get(
                    'api_callback', '')

                return assistant_dict

        except sqlite3.Error as e:
            logger.error(
                f"Error getting assistant {assistant_id} with publication: {e}")
            return None
        finally:
            connection.close()

    def get_assistant_by_name(self, assistant_name: str, owner: Optional[str] = None):
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    # Get column names
                    cursor.execute(
                        f"PRAGMA table_info({self.table_prefix}assistants)")
                    columns = [column[1] for column in cursor.fetchall()]
                    if owner:
                        # Get assistant data
                        cursor.execute(f"SELECT * FROM {self.table_prefix}assistants WHERE name = ? AND owner = ?",
                                       (assistant_name, owner))
                    else:
                        # Get assistant data
                        cursor.execute(f"SELECT * FROM {self.table_prefix}assistants WHERE name = ?",
                                       (assistant_name,))
                    assistant_data = cursor.fetchone()

                    if assistant_data:
                        try:
                            # Create a dictionary mapping column names to values
                            assistant_dict = dict(zip(columns, assistant_data))
                            # Create Assistant object from dictionary
                            assistant = Assistant(
                                id=assistant_dict['id'],
                                name=assistant_dict['name'],
                                description=assistant_dict['description'],
                                owner=assistant_dict['owner'],
                                api_callback=assistant_dict['api_callback'],
                                system_prompt=assistant_dict['system_prompt'],
                                prompt_template=assistant_dict['prompt_template'],
                                RAG_endpoint=assistant_dict['RAG_endpoint'],
                                RAG_Top_k=assistant_dict['RAG_Top_k'],
                                RAG_collections=assistant_dict['RAG_collections'],
                                pre_retrieval_endpoint=assistant_dict['pre_retrieval_endpoint'],
                                post_retrieval_endpoint=assistant_dict['post_retrieval_endpoint']
                            )
                            return assistant
                        except Exception as e:
                            logger.error(f"Error creating assistant: {e}")
                            return None
                    else:
                        return None
            except sqlite3.Error as e:
                logger.error(f"Error getting assistant: {e}")
                return None
            finally:
                connection.close()
        return None

    def get_list_of_assistants(self, owner: str) -> List[Dict[str, Any]]:
        """Get list of assistants for an owner."""
        connection = self.get_connection()
        if not connection:
            return []  # Return empty list instead of None

        try:
            with connection:
                cursor = connection.cursor()
                # Get column names
                cursor.execute(
                    f"PRAGMA table_info({self.table_prefix}assistants)")
                columns = [column[1] for column in cursor.fetchall()]

                cursor.execute(
                    f"SELECT * FROM {self.table_prefix}assistants WHERE owner = ?", (owner,))
                assistants_data = cursor.fetchall()
#                logger.debug(f"Retrieved assistants data: {assistants_data}")

                # Convert the tuples to dictionaries with proper keys
                assistants_list = []
                for assistant_data in assistants_data:
                    assistant_dict = dict(zip(columns, assistant_data))
                    assistants_list.append({
                        'id': assistant_dict['id'],
                        'name': assistant_dict['name'],
                        'description': assistant_dict['description'],
                        'owner': assistant_dict['owner'],
                        'api_callback': assistant_dict['api_callback'],
                        'system_prompt': assistant_dict['system_prompt'],
                        'prompt_template': assistant_dict['prompt_template'],
                        'RAG_endpoint': assistant_dict['RAG_endpoint'],
                        'RAG_Top_k': assistant_dict['RAG_Top_k'],
                        'RAG_collections': assistant_dict['RAG_collections'],
                        'pre_retrieval_endpoint': assistant_dict['pre_retrieval_endpoint'],
                        'post_retrieval_endpoint': assistant_dict['post_retrieval_endpoint']
                    })
                return assistants_list
        except sqlite3.Error as e:
            logger.error(f"Error getting assistants: {e}")
            return []  # Return empty list on error
        finally:
            connection.close()

    def get_full_list_of_assistants(self):
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    # Get column names
                    cursor.execute(
                        f"PRAGMA table_info({self.table_prefix}assistants)")
                    columns = [column[1] for column in cursor.fetchall()]

                    cursor.execute(
                        f"SELECT * FROM {self.table_prefix}assistants")
                    assistants_data = cursor.fetchall()

                    # Convert the tuples to dictionaries with proper keys
                    assistants_list = []
                    for assistant_data in assistants_data:
                        assistant_dict = dict(zip(columns, assistant_data))
                        assistants_list.append({
                            'id': assistant_dict['id'],
                            'name': assistant_dict['name'],
                            'description': assistant_dict['description'],
                            'owner': assistant_dict['owner'],
                            'api_callback': assistant_dict['api_callback'],
                            'system_prompt': assistant_dict['system_prompt'],
                            'prompt_template': assistant_dict['prompt_template'],
                            'RAG_endpoint': assistant_dict['RAG_endpoint'],
                            'RAG_Top_k': assistant_dict['RAG_Top_k'],
                            'RAG_collections': assistant_dict['RAG_collections'],
                            'pre_retrieval_endpoint': assistant_dict['pre_retrieval_endpoint'],
                            'post_retrieval_endpoint': assistant_dict['post_retrieval_endpoint']
                        })
                    return assistants_list
            except sqlite3.Error as e:
                logger.error(f"Error getting assistants: {e}")
                return None
            finally:
                if connection:
                    connection.close()
                    logger.debug("Database connection closed")
        return None

    def get_all_assistants_with_publication(self) -> List[Dict[str, Any]]:
        """
        Get all assistants with publication data and correct published flag

        Returns:
            List[Dict[str, Any]]: List of assistant dictionaries with publication data
        """
        connection = self.get_connection()
        if not connection:
            return []

        assistants_list = []
        assistants_table = self._get_table_name('assistants')
        published_table = self._get_table_name('assistant_publish')

        try:
            with connection:
                cursor = connection.cursor()

                # Get assistants with publication data using LEFT JOIN
                query = f"""
                    SELECT
                        a.id, a.name, a.description, a.owner, a.api_callback,
                        a.system_prompt, a.prompt_template, a.RAG_endpoint, a.RAG_Top_k,
                        a.RAG_collections, a.pre_retrieval_endpoint, a.post_retrieval_endpoint,
                        p.group_id, p.group_name, p.oauth_consumer_name, p.created_at as published_at,
                        CASE 
                            WHEN p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {assistants_table} a
                    LEFT JOIN {published_table} p ON a.id = p.assistant_id
                    ORDER BY a.id DESC
                """
                cursor.execute(query)
                rows = cursor.fetchall()

                # Get column names from the cursor description after execution
                columns = [desc[0] for desc in cursor.description]

                for row in rows:
                    assistant_dict = dict(zip(columns, row))
                    # Convert boolean flag back to Python boolean
                    assistant_dict['published'] = bool(
                        assistant_dict.get('published'))
                    # Handle null strings
                    if assistant_dict.get('oauth_consumer_name') == "null":
                        assistant_dict['oauth_consumer_name'] = None
                    assistants_list.append(assistant_dict)

                return assistants_list

        except sqlite3.Error as e:
            logger.error(f"Error getting all assistants with publication: {e}")
            return []
        finally:
            connection.close()

    def get_list_of_assitants_id_and_name(self):
        """Get list of assistants providing only id, name, owner, api_callback, and published status"""
        connection = self.get_connection()
        if not connection:
            return []
        assistants_list = []
        assistants_table = self._get_table_name('assistants')
        published_table = self._get_table_name('assistant_publish')
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        a.id, a.name, a.owner, a.api_callback,
                        CASE 
                            WHEN p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {assistants_table} a
                    LEFT JOIN {published_table} p ON a.id = p.assistant_id
                """)
                rows = cursor.fetchall()
                for row in rows:
                    assistants_list.append({
                        'id': row[0],
                        'name': row[1],
                        'owner': row[2],
                        'api_callback': row[3],
                        'published': bool(row[4])
                    })
                return assistants_list
        except sqlite3.Error as e:
            logger.error(f"Error getting list of assistants: {e}")
            return []
        finally:
            connection.close()

    def get_assistants_by_owner_paginated(self, owner: str, limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
        """Get a paginated list of assistants for an owner, including publication status."""
        connection = self.get_connection()
        if not connection:
            return [], 0

        assistants_list = []
        total_count = 0
        assistants_table = self._get_table_name('assistants')
        published_table = self._get_table_name('assistant_publish')

        try:
            with connection:
                cursor = connection.cursor()

                # Get total count for the owner
                count_query = f"SELECT COUNT(*) FROM {assistants_table} WHERE owner = ?"
                cursor.execute(count_query, (owner,))
                total_count = cursor.fetchone()[0]

                # Get paginated assistants with publication data using LEFT JOIN
                query = f"""
                    SELECT
                        a.id, a.name, a.description, a.owner, a.api_callback,
                        a.system_prompt, a.prompt_template, a.RAG_endpoint, a.RAG_Top_k,
                        a.RAG_collections, a.pre_retrieval_endpoint, a.post_retrieval_endpoint,
                        a.created_at, a.updated_at,
                        p.group_id, p.group_name, p.oauth_consumer_name, p.created_at as published_at,
                        CASE 
                            WHEN p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {assistants_table} a
                    LEFT JOIN {published_table} p ON a.id = p.assistant_id
                    WHERE a.owner = ?
                    ORDER BY a.id DESC -- Or another suitable order
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, (owner, limit, offset))
                rows = cursor.fetchall()

                # Get column names from the cursor description after execution
                columns = [desc[0] for desc in cursor.description]

                # --- Add Logging --- #
                # logger.info(f"DB Query for owner '{owner}' (limit={limit}, offset={offset}) - Total Count: {total_count}")
                # logger.debug(f"DB Query Raw Rows ({len(rows)}): {rows}")
                # --- End Logging --- #

                for row in rows:
                    assistant_dict = dict(zip(columns, row))
                    # Convert boolean flag back to Python boolean
                    assistant_dict['published'] = bool(
                        assistant_dict.get('published'))
                    # Map api_callback to metadata field for new API responses (Phase 1 refactor completion)
                    assistant_dict['metadata'] = assistant_dict.get(
                        'api_callback', '')
                    assistants_list.append(assistant_dict)

                return assistants_list, total_count

        except sqlite3.Error as e:
            logger.error(
                f"Error getting paginated assistants for owner {owner}: {e}")
            return [], 0  # Return empty list and 0 count on error
        finally:
            connection.close()

    def get_assistants_by_organization(self, organization_id: int) -> List[Dict[str, Any]]:
        """
        Get all assistants in an organization with publication status

        Args:
            organization_id: ID of the organization

        Returns:
            List of assistant dictionaries with publication info
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            assistants_table = self._get_table_name('assistants')
            published_table = self._get_table_name('assistant_publish')

            with connection:
                cursor = connection.cursor()

                # Get all assistants in organization with publication data
                query = f"""
                    SELECT
                        a.id, a.name, a.description, a.owner, a.api_callback,
                        a.system_prompt, a.prompt_template, a.RAG_endpoint, a.RAG_Top_k,
                        a.RAG_collections, a.pre_retrieval_endpoint, a.post_retrieval_endpoint,
                        a.created_at, a.updated_at,
                        p.group_id, p.group_name, p.oauth_consumer_name, p.created_at as published_at,
                        CASE 
                            WHEN p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {assistants_table} a
                    LEFT JOIN {published_table} p ON a.id = p.assistant_id
                    WHERE a.organization_id = ?
                    ORDER BY a.created_at DESC
                """
                cursor.execute(query, (organization_id,))
                rows = cursor.fetchall()

                columns = [desc[0] for desc in cursor.description]
                assistants_list = []

                for row in rows:
                    assistant_dict = dict(zip(columns, row))
                    assistant_dict['published'] = bool(
                        assistant_dict.get('published'))
                    assistant_dict['metadata'] = assistant_dict.get(
                        'api_callback', '')
                    assistants_list.append(assistant_dict)

                logger.info(
                    f"Retrieved {len(assistants_list)} assistants for organization {organization_id}")
                return assistants_list

        except sqlite3.Error as e:
            logger.error(
                f"Error getting assistants for organization {organization_id}: {e}")
            return []
        finally:
            connection.close()

    def delete_assistant(self, assistant_id, owner):
        connection = self.get_connection()
        if connection:
            try:
                # First, check if the assistant exists and belongs to the owner
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(f"SELECT * FROM {self.table_prefix}assistants WHERE id = ? AND owner = ?",
                                   (assistant_id, owner))
                    existing_assistant = cursor.fetchone()

                    if not existing_assistant:
                        logger.warning(
                            f"Assistant {assistant_id} not found or doesn't belong to {owner}")
                        return False

                # If the assistant exists and belongs to the owner, proceed with deletion
                with connection:
                    cursor = connection.cursor()
                    # Deletion will cascade to assistant_publish due to FOREIGN KEY ON DELETE CASCADE
                    cursor.execute(f"DELETE FROM {self.table_prefix}assistants WHERE id = ? AND owner = ?",
                                   (assistant_id, owner))
                    logger.info(
                        f"Assistant {assistant_id} deleted successfully")
                    return True
            except sqlite3.Error as e:
                logger.error(f"Error deleting assistant: {e}")
                return False
            finally:
                if connection:
                    connection.close()
                    logger.debug("Database connection closed")
        return False

    def get_lti_users_by_assistant_id(self, assistant_id: str) -> list[LTIUser]:
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        f"SELECT * FROM {self.table_prefix}lti_users WHERE assistant_id = ?", (assistant_id,))
                    rows = cursor.fetchall()

                    # Get column names
                    cursor.execute(
                        f"PRAGMA table_info({self.table_prefix}lti_users)")
                    columns = [column[1] for column in cursor.fetchall()]

                    users = []
                    for row in rows:
                        # Create a dictionary mapping column names to values
                        user_dict = dict(zip(columns, row))
                        users.append({
                            'id': user_dict['id'],
                            'assistant_id': user_dict['assistant_id'],
                            'user_email': user_dict['user_email'],
                            'owner': user_dict['owner'],
                            'user_display_name': user_dict['user_display_name'],
                            'lti_context_id': user_dict['lti_context_id'],
                            'lti_app_id': user_dict['lti_app_id']
                        })
                    return users
            except sqlite3.Error as e:
                logger.error(
                    f"Database error when fetching LTI users by assistant_id: {e}")
                raise e
            finally:
                connection.close()
        return []

    def publish_assistant(self, assistant_id: int, assistant_name: str, assistant_owner: str,
                          group_id: str, group_name: str, oauth_consumer_name: Optional[str]) -> bool:  # Allow None for oauth_consumer_name
        """Publish an assistant. Uses INSERT OR REPLACE based on assistant_id primary key."""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    # Using INSERT OR REPLACE because assistant_id is the primary key
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {self.table_prefix}assistant_publish
                        (assistant_id, assistant_name, assistant_owner, group_id,
                         group_name, oauth_consumer_name, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (assistant_id, assistant_name, assistant_owner, group_id,
                          group_name, oauth_consumer_name, int(time.time())))
                    logger.info(
                        f"Assistant {assistant_id} publication created/updated successfully")
                    return True
            except sqlite3.Error as e:
                # Specifically catch integrity errors for unique constraint violation
                if "UNIQUE constraint failed" in str(e) and "oauth_consumer_name" in str(e):
                    logger.error(
                        f"Error publishing assistant {assistant_id}: OAuth Consumer Name '{oauth_consumer_name}' is already in use.")
                    # Re-raise or return specific error? For now, just log and return False
                    return False
                logger.error(f"Error publishing assistant {assistant_id}: {e}")
                return False
            finally:
                connection.close()
        return False

    def get_published_assistants(self) -> list:
        """Get list of published assistants, optionally filtered by owner"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    query = f"SELECT * FROM {self.table_prefix}assistant_publish"
                    cursor.execute(query)
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logger.error(f"Error getting published assistants: {e}")
                return []
            finally:
                connection.close()
        return []

    def unpublish_assistant(self, assistant_id: int) -> bool:
        """Remove the publication record for an assistant"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    # Delete based only on assistant_id as it's the primary key
                    cursor.execute(
                        f"DELETE FROM {self.table_prefix}assistant_publish WHERE assistant_id = ?",
                        (assistant_id,)
                    )
                    deleted_count = cursor.rowcount
                    if deleted_count > 0:
                        logger.info(f"Unpublished assistant {assistant_id}")
                    else:
                        logger.warning(
                            f"Attempted to unpublish assistant {assistant_id}, but no publication record was found.")
                    # Return True if a record was deleted, False otherwise
                    return deleted_count > 0
            except sqlite3.Error as e:
                logger.error(
                    f"Error unpublishing assistant {assistant_id}: {e}")
                return False
            finally:
                connection.close()
        return False

    def _validate_table_name(self, table_name: str) -> str:
        """Validate table name to prevent SQL injection"""
        if not table_name.isalnum() and not all(c in '_' for c in table_name if not c.isalnum()):
            raise ValueError(f"Invalid table name: {table_name}")
        return table_name

    def _get_table_name(self, base_name: str) -> str:
        """Get full table name with prefix"""
        return self._validate_table_name(f"{self.table_prefix}{base_name}")

    def get_published_assistant_by_oauth_consumer(self, oauth_consumer_name: str) -> Optional[Dict]:
        """Get published assistant by oauth_consumer_name"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        f"SELECT * FROM {self.table_prefix}assistant_publish WHERE oauth_consumer_name = ?",
                        (oauth_consumer_name,)
                    )
                    result = cursor.fetchone()

                    if result:
                        # Get column names - Use cursor.description after fetchone
                        columns = [column[0] for column in cursor.description]

                        # Create a dictionary mapping column names to values
                        return dict(zip(columns, result))
                    return None

            except sqlite3.Error as e:
                logger.error(f"Error getting published assistant: {e}")
                return None
            finally:
                connection.close()
        return None

    def get_creator_users(self) -> List[Dict]:
        """
        Get all creator users with their organization information

        Returns:
            List[Dict]: List of creator users with their details and organization info
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT u.id, u.user_email, u.user_name, u.user_config, u.organization_id,
                           o.name as org_name, o.slug as org_slug, o.is_system,
                           COALESCE(r.role, 'member') as org_role, u.user_type, u.enabled,
                           u.lti_user_id, u.auth_provider, u.role
                    FROM {self.table_prefix}Creator_users u
                    LEFT JOIN {self.table_prefix}organizations o ON u.organization_id = o.id
                    LEFT JOIN {self.table_prefix}organization_roles r ON u.id = r.user_id AND r.organization_id = u.organization_id
                    ORDER BY u.id
                """)

                rows = cursor.fetchall()
                users = []
                for row in rows:
                    user_config = json.loads(row[3]) if row[3] else {}
                    users.append({
                        'id': row[0],
                        'email': row[1],
                        'name': row[2],
                        'user_config': user_config,
                        'organization_id': row[4],
                        'organization': {
                            'name': row[5],
                            'slug': row[6],
                            'is_system': bool(row[7]) if row[7] is not None else False
                        },
                        'organization_role': row[8],
                        'user_type': row[9] if len(row) > 9 else 'creator',
                        'enabled': bool(row[10]) if len(row) > 10 else True,
                        'lti_user_id': row[11] if len(row) > 11 else None,
                        'auth_provider': row[12] if len(row) > 12 else 'password',
                        'role': row[13] if len(row) > 13 else 'user'
                    })
                return users

        except sqlite3.Error as e:
            logger.error(f"Database error in get_creator_users: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_creator_users: {e}")
            return None
        finally:
            connection.close()
            logger.debug("Database connection closed")

    # ==================== LTI Creator Methods ====================

    def get_organization_by_lti_consumer_key(self, oauth_consumer_key: str) -> Optional[Dict[str, Any]]:
        """
        Get organization by LTI creator consumer key.
        
        Args:
            oauth_consumer_key: The OAuth consumer key to look up
            
        Returns:
            Organization dict with LTI key info if found, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT o.id, o.slug, o.name, o.is_system, o.status, o.config,
                           k.oauth_consumer_key, k.oauth_consumer_secret, k.enabled as lti_enabled
                    FROM {self.table_prefix}lti_creator_keys k
                    JOIN {self.table_prefix}organizations o ON k.organization_id = o.id
                    WHERE k.oauth_consumer_key = ? AND k.enabled = 1
                """, (oauth_consumer_key,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'slug': result[1],
                    'name': result[2],
                    'is_system': bool(result[3]),
                    'status': result[4],
                    'config': json.loads(result[5]) if result[5] else {},
                    'lti_creator': {
                        'oauth_consumer_key': result[6],
                        'oauth_consumer_secret': result[7],
                        'enabled': bool(result[8])
                    }
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_organization_by_lti_consumer_key: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def get_lti_creator_key(self, organization_id: int) -> Optional[Dict[str, Any]]:
        """
        Get LTI creator key config for an organization.
        
        Args:
            organization_id: The organization ID
            
        Returns:
            LTI key config dict if found, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, organization_id, oauth_consumer_key, oauth_consumer_secret, 
                           enabled, created_at, updated_at
                    FROM {self.table_prefix}lti_creator_keys
                    WHERE organization_id = ?
                """, (organization_id,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'organization_id': result[1],
                    'oauth_consumer_key': result[2],
                    'oauth_consumer_secret': result[3],
                    'enabled': bool(result[4]),
                    'created_at': result[5],
                    'updated_at': result[6]
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_lti_creator_key: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def create_lti_creator_key(self, organization_id: int, oauth_consumer_key: str, 
                                oauth_consumer_secret: str, enabled: bool = True) -> Optional[int]:
        """
        Create LTI creator key for an organization.
        
        Args:
            organization_id: The organization ID
            oauth_consumer_key: The OAuth consumer key (must be unique)
            oauth_consumer_secret: The OAuth consumer secret
            enabled: Whether the key is enabled (default True)
            
        Returns:
            Key ID if created, None if failed (e.g., duplicate key)
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            now = int(time.time())
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}lti_creator_keys 
                    (organization_id, oauth_consumer_key, oauth_consumer_secret, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (organization_id, oauth_consumer_key, oauth_consumer_secret, enabled, now, now))
                
                key_id = cursor.lastrowid
                logger.info(f"Created LTI creator key for org {organization_id}: {oauth_consumer_key}")
                return key_id

        except sqlite3.IntegrityError as e:
            logger.warning(f"LTI creator key already exists or constraint violated: {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error in create_lti_creator_key: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def update_lti_creator_key(self, organization_id: int, oauth_consumer_key: str = None,
                                oauth_consumer_secret: str = None, enabled: bool = None) -> bool:
        """
        Update LTI creator key for an organization.
        
        Args:
            organization_id: The organization ID
            oauth_consumer_key: New OAuth consumer key (optional)
            oauth_consumer_secret: New OAuth consumer secret (optional)
            enabled: Whether the key is enabled (optional)
            
        Returns:
            True if updated, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return False

        try:
            now = int(time.time())
            updates = []
            params = []
            
            if oauth_consumer_key is not None:
                updates.append("oauth_consumer_key = ?")
                params.append(oauth_consumer_key)
            if oauth_consumer_secret is not None:
                updates.append("oauth_consumer_secret = ?")
                params.append(oauth_consumer_secret)
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(enabled)
            
            if not updates:
                return True  # Nothing to update
            
            updates.append("updated_at = ?")
            params.append(now)
            params.append(organization_id)
            
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}lti_creator_keys 
                    SET {', '.join(updates)}
                    WHERE organization_id = ?
                """, params)
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated LTI creator key for org {organization_id}")
                    return True
                return False

        except sqlite3.IntegrityError as e:
            logger.warning(f"LTI creator key update failed (constraint violation): {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error in update_lti_creator_key: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def delete_lti_creator_key(self, organization_id: int) -> bool:
        """
        Delete LTI creator key for an organization.
        
        Args:
            organization_id: The organization ID
            
        Returns:
            True if deleted, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return False

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}lti_creator_keys 
                    WHERE organization_id = ?
                """, (organization_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"Deleted LTI creator key for org {organization_id}")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"Database error in delete_lti_creator_key: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_creator_user_by_lti(self, organization_id: int, lti_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get creator user by organization ID and LTI user ID.
        
        Args:
            organization_id: The organization ID
            lti_user_id: The LTI user ID from LMS
            
        Returns:
            User dict if found, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, organization_id, user_email, user_name, user_type, user_config,
                           enabled, lti_user_id, auth_provider, password_hash, role
                    FROM {self.table_prefix}Creator_users
                    WHERE organization_id = ? AND lti_user_id = ?
                """, (organization_id, lti_user_id))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'organization_id': result[1],
                    'email': result[2],
                    'name': result[3],
                    'user_type': result[4],
                    'user_config': json.loads(result[5]) if result[5] else {},
                    'enabled': bool(result[6]),
                    'lti_user_id': result[7],
                    'auth_provider': result[8],
                    'password_hash': result[9] if len(result) > 9 else None,
                    'role': result[10] if len(result) > 10 else 'user'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_creator_user_by_lti: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def create_lti_creator_user(self, organization_id: int, lti_user_id: str, 
                                 user_email: str, user_name: str) -> Optional[int]:
        """
        Create a new LTI creator user.
        
        LTI creator users:
        - Have auth_provider = 'lti_creator'
        - Have user_type = 'creator' (can use creator interface)
        - Cannot have their password changed
        - Are identified by (organization_id, lti_user_id)
        
        Args:
            organization_id: The organization ID (must not be system org)
            lti_user_id: The LTI user ID from LMS
            user_email: Generated email for the user
            user_name: Display name from LMS
            
        Returns:
            User ID if created, None if failed
        """
        # Check org is not system
        org = self.get_organization_by_id(organization_id)
        if not org:
            logger.error(f"Organization {organization_id} not found")
            return None
        if org.get('is_system'):
            logger.error("Cannot create LTI creator user in system organization")
            return None

        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            # First check if user already exists
            existing = self.get_creator_user_by_lti(organization_id, lti_user_id)
            if existing:
                logger.warning(f"LTI creator user already exists for org {organization_id}, lti_user_id {lti_user_id}")
                return existing['id']

            # Also check by email
            existing_by_email = self.get_creator_user_by_email(user_email)
            if existing_by_email:
                logger.warning(f"User with email {user_email} already exists")
                return None

            # Create OWI user (with random password since LTI users don't use password)
            import secrets
            random_password = secrets.token_urlsafe(32)
            
            owi_manager = OwiUserManager()
            owi_user = owi_manager.get_user_by_email(user_email)
            
            if not owi_user:
                logger.debug(f"Creating OWI user for LTI creator: {user_email}")
                owi_user = owi_manager.create_user(
                    name=user_name,
                    email=user_email,
                    password=random_password,
                    role="user"
                )
                if not owi_user:
                    logger.error(f"Failed to create OWI user for LTI creator: {user_email}")
                    return None

            # Create the creator user (password_hash NULL for LTI users, role defaults to 'user')
            now = int(time.time())
            user_id = None
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}Creator_users
                    (organization_id, user_email, user_name, user_type, user_config,
                     lti_user_id, auth_provider, enabled, password_hash, role, created_at, updated_at)
                    VALUES (?, ?, ?, 'creator', '{{}}', ?, 'lti_creator', 1, NULL, 'user', ?, ?)
                """, (organization_id, user_email, user_name, lti_user_id, now, now))

                user_id = cursor.lastrowid
                logger.info(f"Created LTI creator user {user_email} (ID: {user_id}) for org {organization_id}")

        except sqlite3.IntegrityError as e:
            logger.warning(f"LTI creator user creation failed (constraint violation): {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error in create_lti_creator_user: {e}")
            return None
        finally:
            if connection:
                connection.close()
        
        # Assign member role AFTER connection is closed to avoid "database is locked" error
        # (assign_organization_role creates its own connection)
        if user_id:
            self.assign_organization_role(organization_id, user_id, 'member')
            return user_id
        
        return None

    # ==================== End LTI Creator Methods ====================

    def update_assistant(self, assistant_id: int, assistant: Assistant) -> bool:
        """
        Update an existing assistant in the database.

        IMPORTANT: The database column 'api_callback' stores what is semantically 'metadata'.
        Deprecated fields are always set to empty strings regardless of input.
        """
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(f"""
                        UPDATE {self.table_prefix}assistants 
                        SET name = ?, description = ?, owner = ?, api_callback = ?, 
                            system_prompt = ?, prompt_template = ?, RAG_endpoint = ?, 
                            RAG_Top_k = ?, RAG_collections = ?, pre_retrieval_endpoint = ?, 
                            post_retrieval_endpoint = ?
                        WHERE id = ?
                    """, (assistant.name, assistant.description, assistant.owner,
                          assistant.api_callback,  # This stores the metadata content
                          assistant.system_prompt, assistant.prompt_template,
                          "",  # RAG_endpoint - DEPRECATED, always empty
                          assistant.RAG_Top_k, assistant.RAG_collections,
                          "",  # pre_retrieval_endpoint - DEPRECATED, always empty
                          "",  # post_retrieval_endpoint - DEPRECATED, always empty
                          assistant_id))
                    return cursor.rowcount > 0
            except sqlite3.Error as e:
                logger.error(f"Error updating assistant: {e}")
                return False
            finally:
                connection.close()
                logger.debug("Database connection closed")
        return False

    def get_published_assistants_by_owner(self, owner: str) -> list:
        """Get list of published assistants filtered by owner"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    query = f"SELECT * FROM {self.table_prefix}assistant_publish WHERE assistant_owner = ?"
                    cursor.execute(query, (owner,))
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logger.error(
                    f"Error getting published assistants for owner {owner}: {e}")
                return []
            finally:
                connection.close()
        return []

    def get_publication_by_assistant_id(self, assistant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the publication record for a specific assistant ID

        Args:
            assistant_id: The assistant ID to get publication for

        Returns:
            Optional[Dict[str, Any]]: The publication record if found, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"SELECT * FROM {self.table_prefix}assistant_publish WHERE assistant_id = ?",
                    (assistant_id,)
                )
                result = cursor.fetchone()

                if not result:
                    return None

                # Get column names
                columns = [col[0] for col in cursor.description]

                # Create a dictionary mapping column names to values
                pub_record = dict(zip(columns, result))

                # Process oauth_consumer_name
                if pub_record.get('oauth_consumer_name') == "null":
                    pub_record['oauth_consumer_name'] = None

                return pub_record

        except sqlite3.Error as e:
            logger.error(
                f"Error getting publication for assistant {assistant_id}: {e}")
            return None
        finally:
            connection.close()

    def get_creator_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get creator user details by JWT token

        Args:
            token (str): JWT token to verify

        Returns:
            Optional[Dict]: User details if token is valid, None otherwise
        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, os.getenv(
                'JWT_SECRET_KEY', 'your-secret-key'), algorithms=['HS256'])
            user_email = payload.get('email')

            if not user_email:
                return None

            # Get user details from database
            return self.get_creator_user_by_email(user_email)

        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None

    def get_collections_by_owner(self, owner: str) -> List[Dict[str, Any]]:
        """Get all collections owned by a specific user"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT 
                    id,
                    collection_name,
                    owner,
                    metadata,
                    created_at,
                    updated_at
                FROM {self.table_prefix}collections 
                WHERE owner = ?
            ''', (owner,))

            collections = cursor.fetchall()

            return [{
                'id': row[0],
                'collection_name': row[1],
                'owner': row[2],
                'metadata': row[3],
                'created_at': row[4],
                'updated_at': row[5]
            } for row in collections]

        except Exception as e:
            logger.error(f"Error getting collections by owner: {str(e)}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_collection_by_id(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific collection by its ID"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT 
                    id,
                    collection_name,
                    owner,
                    metadata,
                    created_at,
                    updated_at
                FROM {self.table_prefix}collections 
                WHERE id = ?
            ''', (collection_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'collection_name': row[1],
                'owner': row[2],
                'metadata': row[3],
                'created_at': row[4],
                'updated_at': row[5]
            }

        except Exception as e:
            logger.error(f"Error getting collection by ID: {str(e)}")
            return None
        finally:
            cursor.close()
            conn.close()

    def insert_collection(self, collection_data: Dict[str, Any]) -> bool:
        """Insert a new collection into the database"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO {self.table_prefix}collections (
                    id,
                    collection_name,
                    owner,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                collection_data['id'],
                collection_data['collection_name'],
                collection_data['owner'],
                collection_data['metadata'],
                collection_data['created_at'],
                collection_data['updated_at']
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(
                f"Error inserting collection into database: {str(e)}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection from the database"""
        try:
            connection = self.get_connection()
            if not connection:
                logger.error("Could not establish database connection")
                return False

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}collections 
                    WHERE id = ?
                """, (collection_id,))
                connection.commit()
                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Database error in delete_collection: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_config(self) -> dict:
        """Get the full config"""
        connection = self.get_connection()
        if not connection:
            return {}

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"SELECT config FROM {self.table_prefix}config WHERE id = 1")
                result = cursor.fetchone()
                return json.loads(result[0]) if result else {}
        except sqlite3.Error as e:
            logger.error(f"Error getting config: {e}")
            return {}
        finally:
            connection.close()

    def update_config(self, config: dict) -> bool:
        """Update the entire config"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"UPDATE {self.table_prefix}config SET config = ? WHERE id = 1",
                    (json.dumps(config),)
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Error updating config: {e}")
            return False
        finally:
            connection.close()

    def get_config_key(self, key: str) -> Any:
        """Get a specific config key"""
        config = self.get_config()
        return config.get(key)

    def set_config_key(self, key: str, value: Any) -> bool:
        """Set a specific config key"""
        config = self.get_config()
        config[key] = value
        return self.update_config(config)

    def delete_config_key(self, key: str) -> bool:
        """Delete a specific config key"""
        config = self.get_config()
        if key in config:
            del config[key]
            return self.update_config(config)
        return False

    # ========== Prompt Templates Methods ==========

    def create_prompt_template(self, template_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new prompt template.

        Args:
            template_data: Dictionary containing:
                - organization_id: int
                - owner_email: str
                - name: str
                - description: str (optional)
                - system_prompt: str (optional)
                - prompt_template: str (optional)
                - is_shared: bool (default False)
                - metadata: dict (optional)

        Returns:
            Template ID if successful, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                metadata_json = json.dumps(template_data.get('metadata', {}))

                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}prompt_templates 
                    (organization_id, owner_email, name, description, system_prompt, 
                     prompt_template, is_shared, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    template_data['organization_id'],
                    template_data['owner_email'],
                    template_data['name'],
                    template_data.get('description', ''),
                    template_data.get('system_prompt', ''),
                    template_data.get('prompt_template', ''),
                    template_data.get('is_shared', False),
                    metadata_json,
                    current_time,
                    current_time
                ))

                template_id = cursor.lastrowid
                logger.info(
                    f"Created prompt template '{template_data['name']}' with id: {template_id}")
                return template_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error creating prompt template: {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error creating prompt template: {e}")
            return None
        finally:
            connection.close()

    def get_prompt_template_by_id(self, template_id: int, requester_email: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a prompt template by ID.

        Args:
            template_id: Template ID
            requester_email: Email of user requesting (to check ownership)

        Returns:
            Dictionary with template data and owner info, or None if not found
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        pt.id, pt.organization_id, pt.owner_email, pt.name, pt.description,
                        pt.system_prompt, pt.prompt_template, pt.is_shared, pt.metadata,
                        pt.created_at, pt.updated_at,
                        cu.user_name as owner_name
                    FROM {self.table_prefix}prompt_templates pt
                    LEFT JOIN {self.table_prefix}Creator_users cu ON pt.owner_email = cu.user_email
                    WHERE pt.id = ?
                """, (template_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                template = {
                    'id': row[0],
                    'organization_id': row[1],
                    'owner_email': row[2],
                    'name': row[3],
                    'description': row[4],
                    'system_prompt': row[5],
                    'prompt_template': row[6],
                    'is_shared': bool(row[7]),
                    'metadata': json.loads(row[8]) if row[8] else {},
                    'created_at': row[9],
                    'updated_at': row[10],
                    'owner_name': row[11],
                    'is_owner': requester_email == row[2] if requester_email else None
                }

                return template

        except sqlite3.Error as e:
            logger.error(f"Database error getting prompt template: {e}")
            return None
        finally:
            connection.close()

    def get_user_prompt_templates(self, owner_email: str, organization_id: int,
                                  limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get prompt templates owned by a user.

        Args:
            owner_email: Owner email
            organization_id: Organization ID
            limit: Number of results to return
            offset: Offset for pagination

        Returns:
            Tuple of (list of templates, total count)
        """
        connection = self.get_connection()
        if not connection:
            return [], 0

        try:
            with connection:
                cursor = connection.cursor()

                # Get total count
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM {self.table_prefix}prompt_templates
                    WHERE owner_email = ? AND organization_id = ?
                """, (owner_email, organization_id))
                total = cursor.fetchone()[0]

                # Get templates
                cursor.execute(f"""
                    SELECT 
                        pt.id, pt.organization_id, pt.owner_email, pt.name, pt.description,
                        pt.system_prompt, pt.prompt_template, pt.is_shared, pt.metadata,
                        pt.created_at, pt.updated_at,
                        cu.user_name as owner_name
                    FROM {self.table_prefix}prompt_templates pt
                    LEFT JOIN {self.table_prefix}Creator_users cu ON pt.owner_email = cu.user_email
                    WHERE pt.owner_email = ? AND pt.organization_id = ?
                    ORDER BY pt.updated_at DESC
                    LIMIT ? OFFSET ?
                """, (owner_email, organization_id, limit, offset))

                templates = []
                for row in cursor.fetchall():
                    templates.append({
                        'id': row[0],
                        'organization_id': row[1],
                        'owner_email': row[2],
                        'name': row[3],
                        'description': row[4],
                        'system_prompt': row[5],
                        'prompt_template': row[6],
                        'is_shared': bool(row[7]),
                        'metadata': json.loads(row[8]) if row[8] else {},
                        'created_at': row[9],
                        'updated_at': row[10],
                        'owner_name': row[11],
                        'is_owner': True
                    })

                return templates, total

        except sqlite3.Error as e:
            logger.error(f"Database error getting user prompt templates: {e}")
            return [], 0
        finally:
            connection.close()

    def get_organization_shared_templates(self, organization_id: int, requester_email: str,
                                          limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get shared prompt templates within an organization (excluding requester's own).

        Args:
            organization_id: Organization ID
            requester_email: Email of user requesting (to exclude their templates)
            limit: Number of results to return
            offset: Offset for pagination

        Returns:
            Tuple of (list of templates, total count)
        """
        connection = self.get_connection()
        if not connection:
            return [], 0

        try:
            with connection:
                cursor = connection.cursor()

                # Get total count
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM {self.table_prefix}prompt_templates
                    WHERE organization_id = ? AND is_shared = 1 AND owner_email != ?
                """, (organization_id, requester_email))
                total = cursor.fetchone()[0]

                # Get templates
                cursor.execute(f"""
                    SELECT 
                        pt.id, pt.organization_id, pt.owner_email, pt.name, pt.description,
                        pt.system_prompt, pt.prompt_template, pt.is_shared, pt.metadata,
                        pt.created_at, pt.updated_at,
                        cu.user_name as owner_name
                    FROM {self.table_prefix}prompt_templates pt
                    LEFT JOIN {self.table_prefix}Creator_users cu ON pt.owner_email = cu.user_email
                    WHERE pt.organization_id = ? AND pt.is_shared = 1 AND pt.owner_email != ?
                    ORDER BY pt.updated_at DESC
                    LIMIT ? OFFSET ?
                """, (organization_id, requester_email, limit, offset))

                templates = []
                for row in cursor.fetchall():
                    templates.append({
                        'id': row[0],
                        'organization_id': row[1],
                        'owner_email': row[2],
                        'name': row[3],
                        'description': row[4],
                        'system_prompt': row[5],
                        'prompt_template': row[6],
                        'is_shared': bool(row[7]),
                        'metadata': json.loads(row[8]) if row[8] else {},
                        'created_at': row[9],
                        'updated_at': row[10],
                        'owner_name': row[11],
                        'is_owner': False
                    })

                return templates, total

        except sqlite3.Error as e:
            logger.error(f"Database error getting shared templates: {e}")
            return [], 0
        finally:
            connection.close()

    def update_prompt_template(self, template_id: int, updates: Dict[str, Any], owner_email: str) -> bool:
        """
        Update a prompt template (only owner can update).

        Args:
            template_id: Template ID
            updates: Dictionary of fields to update
            owner_email: Email of owner (for authorization check)

        Returns:
            True if successful, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Check ownership
                cursor.execute(f"""
                    SELECT owner_email FROM {self.table_prefix}prompt_templates WHERE id = ?
                """, (template_id,))
                row = cursor.fetchone()

                if not row or row[0] != owner_email:
                    logger.warning(
                        f"User {owner_email} attempted to update template {template_id} without ownership")
                    return False

                # Build update query
                allowed_fields = ['name', 'description', 'system_prompt',
                                  'prompt_template', 'is_shared', 'metadata']
                update_fields = []
                values = []

                for field in allowed_fields:
                    if field in updates:
                        update_fields.append(f"{field} = ?")
                        if field == 'metadata':
                            values.append(json.dumps(updates[field]))
                        else:
                            values.append(updates[field])

                if not update_fields:
                    logger.warning("No valid fields to update")
                    return False

                # Add updated_at
                update_fields.append("updated_at = ?")
                values.append(int(time.time()))
                values.append(template_id)

                cursor.execute(f"""
                    UPDATE {self.table_prefix}prompt_templates 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, values)

                logger.info(f"Updated prompt template {template_id}")
                return cursor.rowcount > 0

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error updating prompt template: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error updating prompt template: {e}")
            return False
        finally:
            connection.close()

    def delete_prompt_template(self, template_id: int, owner_email: str) -> bool:
        """
        Delete a prompt template (only owner can delete).

        Args:
            template_id: Template ID
            owner_email: Email of owner (for authorization check)

        Returns:
            True if successful, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}prompt_templates 
                    WHERE id = ? AND owner_email = ?
                """, (template_id, owner_email))

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Deleted prompt template {template_id}")
                else:
                    logger.warning(
                        f"User {owner_email} attempted to delete template {template_id} without ownership")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error deleting prompt template: {e}")
            return False
        finally:
            connection.close()

    def duplicate_prompt_template(self, template_id: int, new_owner_email: str,
                                  new_organization_id: int, new_name: str = None) -> Optional[int]:
        """
        Duplicate a prompt template (create a copy for another user).

        Args:
            template_id: Original template ID
            new_owner_email: Email of new owner
            new_organization_id: Organization ID for new template
            new_name: Optional new name (if None, adds "Copy of " prefix)

        Returns:
            New template ID if successful, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()

                # Get original template
                cursor.execute(f"""
                    SELECT name, description, system_prompt, prompt_template, metadata
                    FROM {self.table_prefix}prompt_templates
                    WHERE id = ?
                """, (template_id,))

                row = cursor.fetchone()
                if not row:
                    logger.error(
                        f"Template {template_id} not found for duplication")
                    return None

                # Create new template
                current_time = int(time.time())
                duplicate_name = new_name if new_name else f"Copy of {row[0]}"

                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}prompt_templates 
                    (organization_id, owner_email, name, description, system_prompt, 
                     prompt_template, is_shared, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_organization_id,
                    new_owner_email,
                    duplicate_name,
                    row[1],  # description
                    row[2],  # system_prompt
                    row[3],  # prompt_template
                    False,   # is_shared (always false for duplicates)
                    row[4],  # metadata
                    current_time,
                    current_time
                ))

                new_id = cursor.lastrowid
                logger.info(
                    f"Duplicated template {template_id} to new template {new_id}")
                return new_id

        except sqlite3.IntegrityError as e:
            logger.error(
                f"Integrity error duplicating template (likely duplicate name): {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error duplicating template: {e}")
            return None
        finally:
            connection.close()

    def toggle_template_sharing(self, template_id: int, owner_email: str, is_shared: bool) -> bool:
        """
        Toggle sharing status of a template.

        Args:
            template_id: Template ID
            owner_email: Email of owner (for authorization check)
            is_shared: New sharing status

        Returns:
            True if successful, False otherwise
        """
        return self.update_prompt_template(template_id, {'is_shared': is_shared}, owner_email)

    # ========== KB Registry Methods ==========

    def register_kb(self, kb_id: str, kb_name: str, owner_user_id: int, organization_id: int,
                    is_shared: bool = False, metadata: Dict[str, Any] = None) -> Optional[int]:
        """
        Register a KB in LAMB's registry.
        Called when KB is created or auto-registered on first access.

        Args:
            kb_id: UUID from KB Server
            kb_name: Display name
            owner_user_id: Creator user ID
            organization_id: Organization ID
            is_shared: Whether KB is shared with org (default: False)
            metadata: Optional metadata dict

        Returns:
            Registry entry ID if successful, None otherwise
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())
                metadata_json = json.dumps(metadata or {})

                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}kb_registry 
                    (kb_id, kb_name, owner_user_id, organization_id, is_shared, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (kb_id, kb_name, owner_user_id, organization_id, is_shared, metadata_json, current_time, current_time))

                registry_id = cursor.lastrowid
                logger.info(
                    f"Registered KB '{kb_name}' (ID: {kb_id}) in registry with id: {registry_id}")
                return registry_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error registering KB: {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error registering KB: {e}")
            return None
        finally:
            connection.close()

    def get_kb_registry_entry(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """
        Get KB registry entry with owner info.

        Args:
            kb_id: KB UUID

        Returns:
            Registry entry dict or None
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        kr.id, kr.kb_id, kr.kb_name, kr.owner_user_id, kr.organization_id,
                        kr.is_shared, kr.metadata, kr.created_at, kr.updated_at,
                        cu.user_name as owner_name, cu.user_email as owner_email
                    FROM {self.table_prefix}kb_registry kr
                    LEFT JOIN {self.table_prefix}Creator_users cu ON kr.owner_user_id = cu.id
                    WHERE kr.kb_id = ?
                """, (kb_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'id': row[0],
                    'kb_id': row[1],
                    'kb_name': row[2],
                    'owner_user_id': row[3],
                    'organization_id': row[4],
                    'is_shared': bool(row[5]),
                    'metadata': json.loads(row[6]) if row[6] else {},
                    'created_at': row[7],
                    'updated_at': row[8],
                    'owner_name': row[9],
                    'owner_email': row[10]
                }

        except sqlite3.Error as e:
            logger.error(f"Database error getting KB registry entry: {e}")
            return None
        finally:
            connection.close()

    def get_owned_kbs(self, user_id: int, organization_id: int) -> List[Dict[str, Any]]:
        """
        Get KBs owned by user.

        Args:
            user_id: User ID
            organization_id: Organization ID

        Returns:
            List of KB registry entries owned by user
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        kr.id, kr.kb_id, kr.kb_name, kr.owner_user_id, kr.organization_id,
                        kr.is_shared, kr.metadata, kr.created_at, kr.updated_at,
                        cu.user_name as owner_name, cu.user_email as owner_email
                    FROM {self.table_prefix}kb_registry kr
                    LEFT JOIN {self.table_prefix}Creator_users cu ON kr.owner_user_id = cu.id
                    WHERE kr.organization_id = ? AND kr.owner_user_id = ?
                    ORDER BY kr.updated_at DESC
                """, (organization_id, user_id))

                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    # Convert is_shared boolean
                    if isinstance(result_dict.get('is_shared'), int):
                        result_dict['is_shared'] = bool(
                            result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(
                                result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)

                return results

        except sqlite3.Error as e:
            logger.error(f"Database error getting owned KBs: {e}")
            return []
        finally:
            connection.close()

    def get_shared_kbs(self, user_id: int, organization_id: int) -> List[Dict[str, Any]]:
        """
        Get KBs shared in organization (excluding user's own).

        Args:
            user_id: User ID (to exclude own KBs)
            organization_id: Organization ID

        Returns:
            List of KB registry entries shared in org (not owned by user)
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        kr.id, kr.kb_id, kr.kb_name, kr.owner_user_id, kr.organization_id,
                        kr.is_shared, kr.metadata, kr.created_at, kr.updated_at,
                        cu.user_name as owner_name, cu.user_email as owner_email
                    FROM {self.table_prefix}kb_registry kr
                    LEFT JOIN {self.table_prefix}Creator_users cu ON kr.owner_user_id = cu.id
                    WHERE kr.organization_id = ? 
                    AND kr.is_shared = TRUE
                    AND kr.owner_user_id != ?
                    ORDER BY kr.updated_at DESC
                """, (organization_id, user_id))

                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    # Convert is_shared boolean
                    if isinstance(result_dict.get('is_shared'), int):
                        result_dict['is_shared'] = bool(
                            result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(
                                result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)

                return results

        except sqlite3.Error as e:
            logger.error(f"Database error getting shared KBs: {e}")
            return []
        finally:
            connection.close()

    def get_accessible_kbs(self, user_id: int, organization_id: int) -> List[Dict[str, Any]]:
        """
        Get KBs accessible to user (owned OR shared in org).
        Mirrors template access pattern.
        NOTE: Consider using get_owned_kbs() and get_shared_kbs() separately for better UX.

        Args:
            user_id: User ID
            organization_id: Organization ID

        Returns:
            List of KB registry entries with owner info, ordered by ownership (owned first)
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT 
                        kr.id, kr.kb_id, kr.kb_name, kr.owner_user_id, kr.organization_id,
                        kr.is_shared, kr.metadata, kr.created_at, kr.updated_at,
                        cu.user_name as owner_name, cu.user_email as owner_email
                    FROM {self.table_prefix}kb_registry kr
                    LEFT JOIN {self.table_prefix}Creator_users cu ON kr.owner_user_id = cu.id
                    WHERE kr.organization_id = ? 
                    AND (kr.owner_user_id = ? OR kr.is_shared = TRUE)
                    ORDER BY kr.owner_user_id = ? DESC, kr.updated_at DESC
                """, (organization_id, user_id, user_id))

                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    # Convert is_shared boolean
                    if isinstance(result_dict.get('is_shared'), int):
                        result_dict['is_shared'] = bool(
                            result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(
                                result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)

                return results

        except sqlite3.Error as e:
            logger.error(f"Database error getting accessible KBs: {e}")
            return []
        finally:
            connection.close()

    def user_can_access_kb(self, kb_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Check if user can access KB and return access level.
        Mirrors template access checking.

        Args:
            kb_id: KB UUID
            user_id: User ID

        Returns:
            (can_access, access_type) where access_type is 'owner', 'shared', or 'none'
        """
        entry = self.get_kb_registry_entry(kb_id)

        if not entry:
            return (False, 'none')

        # User is owner
        if entry['owner_user_id'] == user_id:
            return (True, 'owner')

        # KB is shared in user's organization
        user = self.get_creator_user_by_id(user_id)
        if user and entry['is_shared'] and entry['organization_id'] == user.get('organization_id'):
            return (True, 'shared')

        return (False, 'none')

    def check_kb_used_by_other_users(self, kb_id: str, kb_owner_user_id: int) -> List[Dict[str, Any]]:
        """
        Check if a KB is used by assistants owned by other users.

        Args:
            kb_id: KB UUID to check
            kb_owner_user_id: User ID of the KB owner

        Returns:
            List of assistants using this KB (owned by other users).
            Empty list if KB is not used by other users or can be safely unshared.
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Get KB owner's email
                kb_owner = self.get_creator_user_by_id(kb_owner_user_id)
                if not kb_owner:
                    return []

                kb_owner_email = kb_owner['user_email']

                # Find assistants that reference this KB in RAG_collections
                # RAG_collections is comma-separated, so we need to check if kb_id appears in the string
                # Only check assistants owned by users OTHER than the KB owner
                query = f"""
                    SELECT a.id, a.name, a.owner, u.user_name as owner_name
                    FROM {self.table_prefix}assistants a
                    JOIN {self.table_prefix}Creator_users u ON a.owner = u.user_email
                    WHERE a.RAG_collections LIKE ? 
                    AND a.owner != ?
                    AND u.id != ?
                """

                # Use LIKE with wildcards to match KB ID in comma-separated list
                # Match patterns: "kb_id", "kb_id,", ",kb_id", ",kb_id,"
                kb_pattern = f"%{kb_id}%"
                cursor.execute(
                    query, (kb_pattern, kb_owner_email, kb_owner_user_id))
                rows = cursor.fetchall()

                # Additional check: verify KB ID is actually in the list (not just substring match)
                matching_assistants = []
                for row in rows:
                    assistant_id, assistant_name, owner_email, owner_name = row
                    # Get full RAG_collections string to verify exact match
                    cursor.execute(f"""
                        SELECT RAG_collections 
                        FROM {self.table_prefix}assistants 
                        WHERE id = ?
                    """, (assistant_id,))
                    rag_result = cursor.fetchone()

                    if rag_result and rag_result[0]:
                        collections = [c.strip()
                                       for c in rag_result[0].split(',') if c.strip()]
                        if kb_id in collections:
                            matching_assistants.append({
                                'id': assistant_id,
                                'name': assistant_name,
                                'owner_email': owner_email,
                                'owner_name': owner_name
                            })

                return matching_assistants

        except sqlite3.Error as e:
            logger.error(f"Database error checking KB usage: {e}")
            return []

    def toggle_kb_sharing(self, kb_id: str, is_shared: bool) -> bool:
        """
        Toggle KB sharing status.
        Only owner can call this.

        Args:
            kb_id: KB UUID
            is_shared: New sharing state

        Returns:
            True if updated, False if not found
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry 
                    SET is_shared = ?, updated_at = ?
                    WHERE kb_id = ?
                """, (is_shared, current_time, kb_id))

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Toggled KB {kb_id} sharing to {is_shared}")
                else:
                    logger.warning(f"KB {kb_id} not found for sharing toggle")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error toggling KB sharing: {e}")
            return False
        finally:
            connection.close()

    def update_kb_registry_created_at(self, kb_id: str, created_at: int) -> bool:
        """
        Update KB registry created_at timestamp.
        Used when auto-registering KBs to preserve original creation date.

        Args:
            kb_id: KB UUID
            created_at: Unix timestamp (seconds since epoch)

        Returns:
            True if updated, False if not found
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry
                    SET created_at = ?
                    WHERE kb_id = ?
                """, (created_at, kb_id))

                if cursor.rowcount > 0:
                    logger.info(
                        f"Updated created_at for KB {kb_id} to {created_at}")
                    return True
                else:
                    logger.warning(
                        f"KB {kb_id} not found in registry for created_at update")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Database error updating KB created_at: {e}")
            return False
        finally:
            connection.close()

    def update_kb_registry_name(self, kb_id: str, kb_name: str) -> bool:
        """
        Update cached KB name.
        Called when KB is renamed.

        Args:
            kb_id: KB UUID
            kb_name: New KB name

        Returns:
            True if updated, False if not found
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry 
                    SET kb_name = ?, updated_at = ?
                    WHERE kb_id = ?
                """, (kb_name, current_time, kb_id))

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Updated KB {kb_id} name to '{kb_name}'")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error updating KB registry name: {e}")
            return False
        finally:
            connection.close()

    def get_all_kb_registry_entries(self) -> List[Dict[str, Any]]:
        """
        Get all KB registry entries (for migration operations).

        Returns:
            List of all KB registry entries
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT 
                        kb_id, 
                        kb_name, 
                        owner_user_id, 
                        organization_id, 
                        is_shared, 
                        created_at, 
                        updated_at
                    FROM {self.table_prefix}kb_registry
                    ORDER BY created_at
                """)

                rows = cursor.fetchall()

                if not rows:
                    return []

                entries = []
                for row in rows:
                    entries.append({
                        'kb_id': row[0],
                        'kb_name': row[1],
                        'owner_user_id': row[2],
                        'organization_id': row[3],
                        'is_shared': bool(row[4]) if row[4] is not None else False,
                        'created_at': row[5],
                        'updated_at': row[6]
                    })

                return entries

        except sqlite3.Error as e:
            logger.error(f"Database error getting KB registry entries: {e}")
            return []
        finally:
            connection.close()

    def update_assistant_name(self, assistant_id: int, new_name: str) -> bool:
        """
        Update assistant name (for migration operations).

        Args:
            assistant_id: Assistant ID
            new_name: New assistant name

        Returns:
            True if updated, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                cursor.execute(f"""
                    UPDATE {self.table_prefix}assistants 
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                """, (new_name, current_time, assistant_id))

                success = cursor.rowcount > 0
                if success:
                    logger.info(
                        f"Updated assistant {assistant_id} name to '{new_name}'")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error updating assistant name: {e}")
            return False
        finally:
            connection.close()

    def delete_kb_registry_entry(self, kb_id: str) -> bool:
        """
        Delete KB registry entry.
        Called when KB is deleted.

        Args:
            kb_id: KB UUID

        Returns:
            True if deleted, False if not found
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}kb_registry 
                    WHERE kb_id = ?
                """, (kb_id,))

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Deleted KB registry entry for {kb_id}")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error deleting KB registry entry: {e}")
            return False
        finally:
            connection.close()

    # Assistant Sharing Methods

    def share_assistant(self, assistant_id: int, shared_with_user_id: int, shared_by_user_id: int) -> bool:
        """
        Share an assistant with another user in the same organization

        Args:
            assistant_id: ID of the assistant to share
            shared_with_user_id: ID of the user to share with
            shared_by_user_id: ID of the user sharing the assistant

        Returns:
            True if shared successfully, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                current_time = int(time.time())

                # Check if already shared
                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}assistant_shares 
                    WHERE assistant_id = ? AND shared_with_user_id = ?
                """, (assistant_id, shared_with_user_id))

                if cursor.fetchone():
                    logger.info(
                        f"Assistant {assistant_id} already shared with user {shared_with_user_id}")
                    return True

                # Add sharing record
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}assistant_shares 
                    (assistant_id, shared_with_user_id, shared_by_user_id, shared_at)
                    VALUES (?, ?, ?, ?)
                """, (assistant_id, shared_with_user_id, shared_by_user_id, current_time))

                success = cursor.rowcount > 0
                if success:
                    logger.info(
                        f"Shared assistant {assistant_id} with user {shared_with_user_id}")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error sharing assistant: {e}")
            return False
        finally:
            connection.close()

    def unshare_assistant(self, assistant_id: int, shared_with_user_id: int) -> bool:
        """
        Remove assistant sharing with a user

        Args:
            assistant_id: ID of the assistant to unshare
            shared_with_user_id: ID of the user to remove sharing from

        Returns:
            True if unshared successfully, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}assistant_shares 
                    WHERE assistant_id = ? AND shared_with_user_id = ?
                """, (assistant_id, shared_with_user_id))

                success = cursor.rowcount > 0
                if success:
                    logger.info(
                        f"Unshared assistant {assistant_id} from user {shared_with_user_id}")

                return success

        except sqlite3.Error as e:
            logger.error(f"Database error unsharing assistant: {e}")
            return False
        finally:
            connection.close()

    def get_assistant_shares(self, assistant_id: int) -> List[Dict[str, Any]]:
        """
        Get list of users an assistant is shared with

        Args:
            assistant_id: ID of the assistant

        Returns:
            List of share records with user information
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT 
                        s.id,
                        s.assistant_id,
                        s.shared_with_user_id,
                        s.shared_by_user_id,
                        s.shared_at,
                        u.user_email as shared_with_email,
                        u.user_name as shared_with_name,
                        u.user_type as shared_with_type,
                        u2.user_email as shared_by_email,
                        u2.user_name as shared_by_name
                    FROM {self.table_prefix}assistant_shares s
                    JOIN {self.table_prefix}Creator_users u ON s.shared_with_user_id = u.id
                    JOIN {self.table_prefix}Creator_users u2 ON s.shared_by_user_id = u2.id
                    WHERE s.assistant_id = ?
                    ORDER BY s.shared_at DESC
                """, (assistant_id,))

                shares = []
                for row in cursor.fetchall():
                    shares.append({
                        'id': row[0],
                        'assistant_id': row[1],
                        'shared_with_user_id': row[2],
                        'shared_by_user_id': row[3],
                        'shared_at': row[4],
                        'shared_with_email': row[5],
                        'shared_with_name': row[6],
                        'shared_with_type': row[7],
                        'shared_by_email': row[8],
                        'shared_by_name': row[9]
                    })

                return shares

        except sqlite3.Error as e:
            logger.error(f"Database error getting assistant shares: {e}")
            return []
        finally:
            connection.close()

    def get_assistants_shared_with_user(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get list of assistants shared with a specific user

        Args:
            user_id: ID of the user

        Returns:
            List of assistants shared with the user
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT 
                        a.id,
                        a.organization_id,
                        a.name,
                        a.description,
                        a.owner,
                        a.api_callback as metadata,
                        a.system_prompt,
                        a.prompt_template,
                        a.RAG_Top_k,
                        a.RAG_collections,
                        a.created_at,
                        a.updated_at,
                        s.shared_at,
                        s.shared_by_user_id,
                        u.user_email as shared_by_email,
                        u.user_name as shared_by_name
                    FROM {self.table_prefix}assistant_shares s
                    JOIN {self.table_prefix}assistants a ON s.assistant_id = a.id
                    JOIN {self.table_prefix}Creator_users u ON s.shared_by_user_id = u.id
                    WHERE s.shared_with_user_id = ?
                    ORDER BY s.shared_at DESC
                """, (user_id,))

                assistants = []
                for row in cursor.fetchall():
                    assistants.append({
                        'id': row[0],
                        'organization_id': row[1],
                        'name': row[2],
                        'description': row[3],
                        'owner': row[4],
                        'metadata': row[5],
                        'system_prompt': row[6],
                        'prompt_template': row[7],
                        'RAG_Top_k': row[8],
                        'RAG_collections': row[9],
                        'created_at': row[10],
                        'updated_at': row[11],
                        'shared_at': row[12],
                        'shared_by_user_id': row[13],
                        'shared_by_email': row[14],
                        'shared_by_name': row[15],
                        'is_shared': True  # Flag to indicate this is a shared assistant
                    })

                return assistants

        except sqlite3.Error as e:
            logger.error(f"Database error getting shared assistants: {e}")
            return []
        finally:
            connection.close()

    def is_assistant_shared_with_user(self, assistant_id: int, user_id: int) -> bool:
        """
        Check if an assistant is shared with a specific user

        Args:
            assistant_id: ID of the assistant
            user_id: ID of the user

        Returns:
            True if shared, False otherwise
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}assistant_shares 
                    WHERE assistant_id = ? AND shared_with_user_id = ?
                """, (assistant_id, user_id))

                return cursor.fetchone() is not None

        except sqlite3.Error as e:
            logger.error(f"Database error checking assistant share: {e}")
            return False
        finally:
            connection.close()

    def get_users_in_organization(self, organization_id: int, include_lti: bool = False) -> List[Dict[str, Any]]:
        """
        Get all users in an organization (for sharing UI)

        Args:
            organization_id: ID of the organization
            include_lti: Whether to include LTI users (default False)

        Returns:
            List of users in the organization
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Get regular creator and end users
                cursor.execute(f"""
                    SELECT 
                        u.id,
                        u.user_email,
                        u.user_name,
                        u.user_type,
                        r.role as org_role
                    FROM {self.table_prefix}Creator_users u
                    LEFT JOIN {self.table_prefix}organization_roles r 
                        ON u.id = r.user_id AND r.organization_id = u.organization_id
                    WHERE u.organization_id = ?
                    ORDER BY u.user_name
                """, (organization_id,))

                users = []
                for row in cursor.fetchall():
                    users.append({
                        'id': row[0],
                        'email': row[1],
                        'name': row[2],
                        'user_type': row[3],
                        'org_role': row[4] or 'member'
                    })

                return users

        except sqlite3.Error as e:
            logger.error(f"Database error getting organization users: {e}")
            return []
        finally:
            connection.close()

    def get_all_assistants(self) -> List[Dict[str, Any]]:
        """
        Get all assistants (for admin operations like OWI group sync)

        Returns:
            List of all assistants
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT 
                        id,
                        organization_id,
                        name,
                        description,
                        owner,
                        api_callback as metadata,
                        system_prompt,
                        prompt_template,
                        RAG_Top_k,
                        RAG_collections,
                        created_at,
                        updated_at,
                        published,
                        published_at,
                        group_id,
                        group_name
                    FROM {self.table_prefix}assistants
                    ORDER BY created_at DESC
                """)

                assistants = []
                for row in cursor.fetchall():
                    assistants.append({
                        'id': row[0],
                        'organization_id': row[1],
                        'name': row[2],
                        'description': row[3],
                        'owner': row[4],
                        'metadata': row[5],
                        'system_prompt': row[6],
                        'prompt_template': row[7],
                        'RAG_Top_k': row[8],
                        'RAG_collections': row[9],
                        'created_at': row[10],
                        'updated_at': row[11],
                        'published': row[12],
                        'published_at': row[13],
                        'group_id': row[14],
                        'group_name': row[15]
                    })

                return assistants

        except sqlite3.Error as e:
            logger.error(f"Database error getting all assistants: {e}")
            return []
        finally:
            connection.close()

    def user_can_access_rubric(self, rubric_id: str, user_id: int) -> bool:
        """
        Check if user has access to a rubric

        Args:
            rubric_id: ID of the rubric
            user_id: ID of the user

        Returns:
            True if user has access, False otherwise

        Note: This is a placeholder implementation.
              Proper rubric sharing should be implemented when adding
              sharing permission checks to KB/template/rubric sharing.
        """
        # For now, return True as rubric sharing is not fully implemented
        # This should be replaced with actual rubric access checking
        # when rubric sharing is implemented
        return True

    def get_published_assistant_by_id(self, assistant_id: int) -> Optional[Dict[str, Any]]:
        """Alias for get_publication_by_assistant_id for consistency"""
        return self.get_publication_by_assistant_id(assistant_id)

    # =========================================================================
    # LAMB Internal Chat Methods (lamb_chats table)
    # =========================================================================

    def create_lamb_chat(
        self,
        chat_id: str,
        user_id: int,
        assistant_id: int,
        title: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new internal chat record.

        Args:
            chat_id: UUID for the chat (generated by caller)
            user_id: Creator user ID
            assistant_id: LAMB assistant ID
            title: Optional title (defaults to 'New Chat')

        Returns:
            Created chat record or None on error
        """
        import time

        connection = self.get_connection()
        if not connection:
            return None

        try:
            now = int(time.time())
            title = title or "New Chat"
            initial_chat = json.dumps({"history": {"messages": {}}})

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}lamb_chats 
                    (id, user_id, assistant_id, title, created_at, updated_at, chat, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """, (chat_id, user_id, assistant_id, title, now, now, initial_chat))

                logger.info(
                    f"Created lamb_chat {chat_id} for user {user_id}, assistant {assistant_id}")

                return {
                    "id": chat_id,
                    "user_id": user_id,
                    "assistant_id": assistant_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": now,
                    "chat": {"history": {"messages": {}}},
                    "archived": 0
                }

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error creating lamb_chat: {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error creating lamb_chat: {e}")
            return None
        finally:
            connection.close()

    def get_lamb_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single chat record by ID.

        Args:
            chat_id: UUID of the chat

        Returns:
            Chat record with parsed JSON, or None if not found
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, user_id, assistant_id, title, created_at, updated_at, chat, archived
                    FROM {self.table_prefix}lamb_chats
                    WHERE id = ?
                """, (chat_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                chat_data = json.loads(row[6]) if row[6] else {
                    "history": {"messages": {}}}

                return {
                    "id": row[0],
                    "user_id": row[1],
                    "assistant_id": row[2],
                    "title": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "chat": chat_data,
                    "archived": row[7]
                }

        except sqlite3.Error as e:
            logger.error(f"Database error getting lamb_chat {chat_id}: {e}")
            return None
        finally:
            connection.close()

    def get_lamb_chats_for_user_assistant(
        self,
        user_id: int,
        assistant_id: int,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of chats for a user with a specific assistant.

        Args:
            user_id: Creator user ID
            assistant_id: LAMB assistant ID
            include_archived: Whether to include archived chats
            limit: Maximum number of chats to return
            offset: Offset for pagination

        Returns:
            List of chat summaries (without full message content)
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                archived_filter = "" if include_archived else "AND archived = 0"

                cursor.execute(f"""
                    SELECT id, user_id, assistant_id, title, created_at, updated_at, chat, archived
                    FROM {self.table_prefix}lamb_chats
                    WHERE user_id = ? AND assistant_id = ? {archived_filter}
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, assistant_id, limit, offset))

                chats = []
                for row in cursor.fetchall():
                    # Parse chat to get message count
                    chat_data = json.loads(row[6]) if row[6] else {
                        "history": {"messages": {}}}
                    message_count = len(chat_data.get(
                        "history", {}).get("messages", {}))

                    chats.append({
                        "id": row[0],
                        "user_id": row[1],
                        "assistant_id": row[2],
                        "title": row[3],
                        "created_at": row[4],
                        "updated_at": row[5],
                        "message_count": message_count,
                        "archived": row[7]
                    })

                return chats

        except sqlite3.Error as e:
            logger.error(
                f"Database error getting lamb_chats for user {user_id}, assistant {assistant_id}: {e}")
            return []
        finally:
            connection.close()

    def update_lamb_chat(
        self,
        chat_id: str,
        title: str = None,
        chat_json: Dict = None,
        archived: int = None
    ) -> bool:
        """
        Update a chat record.

        Args:
            chat_id: UUID of the chat
            title: New title (optional)
            chat_json: New chat JSON with messages (optional)
            archived: Archive status (optional)

        Returns:
            True if updated successfully
        """
        import time

        connection = self.get_connection()
        if not connection:
            return False

        try:
            # Build dynamic update
            updates = []
            params = []

            if title is not None:
                updates.append("title = ?")
                params.append(title)

            if chat_json is not None:
                updates.append("chat = ?")
                params.append(json.dumps(chat_json))

            if archived is not None:
                updates.append("archived = ?")
                params.append(archived)

            if not updates:
                logger.warning(f"No updates provided for lamb_chat {chat_id}")
                return False

            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(int(time.time()))

            params.append(chat_id)

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}lamb_chats
                    SET {", ".join(updates)}
                    WHERE id = ?
                """, tuple(params))

                if cursor.rowcount == 0:
                    logger.warning(
                        f"No lamb_chat found with id {chat_id} to update")
                    return False

                logger.debug(f"Updated lamb_chat {chat_id}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Database error updating lamb_chat {chat_id}: {e}")
            return False
        finally:
            connection.close()

    def add_message_to_lamb_chat(
        self,
        chat_id: str,
        message_id: str,
        role: str,
        content: str,
        timestamp: int = None
    ) -> bool:
        """
        Add a message to an existing chat.

        Args:
            chat_id: UUID of the chat
            message_id: UUID for the new message
            role: Message role ('user' or 'assistant')
            content: Message content
            timestamp: Unix timestamp (defaults to now)

        Returns:
            True if message added successfully
        """
        import time

        # Get current chat
        chat = self.get_lamb_chat(chat_id)
        if not chat:
            logger.error(f"Cannot add message: lamb_chat {chat_id} not found")
            return False

        timestamp = timestamp or int(time.time())

        # Get existing messages and find parent
        messages = chat.get("chat", {}).get("history", {}).get("messages", {})

        # Find the last message to set as parent
        parent_id = None
        if messages:
            # Sort by timestamp to find last message
            sorted_msgs = sorted(
                messages.items(),
                key=lambda x: x[1].get("timestamp", 0)
            )
            if sorted_msgs:
                parent_id = sorted_msgs[-1][0]
                # Update parent's childrenIds
                if "childrenIds" not in messages[parent_id]:
                    messages[parent_id]["childrenIds"] = []
                messages[parent_id]["childrenIds"].append(message_id)

        # Create new message in OWI-compatible format
        new_message = {
            "id": message_id,
            "parentId": parent_id,
            "childrenIds": [],
            "role": role,
            "content": content,
            "timestamp": timestamp
        }

        messages[message_id] = new_message

        # Update chat with new messages
        chat_data = chat.get("chat", {})
        if "history" not in chat_data:
            chat_data["history"] = {}
        chat_data["history"]["messages"] = messages

        return self.update_lamb_chat(chat_id, chat_json=chat_data)

    def delete_lamb_chat(self, chat_id: str) -> bool:
        """
        Delete a chat record.

        Args:
            chat_id: UUID of the chat

        Returns:
            True if deleted successfully
        """
        connection = self.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}lamb_chats
                    WHERE id = ?
                """, (chat_id,))

                if cursor.rowcount == 0:
                    logger.warning(
                        f"No lamb_chat found with id {chat_id} to delete")
                    return False

                logger.info(f"Deleted lamb_chat {chat_id}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Database error deleting lamb_chat {chat_id}: {e}")
            return False
        finally:
            connection.close()

    def get_lamb_chats_for_assistant_analytics(
        self,
        assistant_id: int,
        start_date: int = None,
        end_date: int = None,
        search_content: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all chats for an assistant (for analytics/Activity tab).
        This method is used by ChatAnalyticsService to query LAMB internal chats.

        Args:
            assistant_id: LAMB assistant ID
            start_date: Filter from timestamp (optional)
            end_date: Filter until timestamp (optional)
            search_content: Search for content in chat messages (optional)
            limit: Maximum records
            offset: Pagination offset

        Returns:
            List of chat summaries with user info
        """
        connection = self.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Build WHERE clause
                where_clauses = ["c.assistant_id = ?"]
                params = [assistant_id]

                if start_date:
                    where_clauses.append("c.created_at >= ?")
                    params.append(start_date)

                if end_date:
                    where_clauses.append("c.created_at <= ?")
                    params.append(end_date)

                if search_content:
                    where_clauses.append("c.chat LIKE ?")
                    params.append(f'%{search_content}%')

                where_sql = " AND ".join(where_clauses)
                params.extend([limit, offset])

                cursor.execute(f"""
                    SELECT 
                        c.id,
                        c.user_id,
                        c.assistant_id,
                        c.title,
                        c.created_at,
                        c.updated_at,
                        c.chat,
                        c.archived,
                        u.user_name,
                        u.user_email
                    FROM {self.table_prefix}lamb_chats c
                    LEFT JOIN {self.table_prefix}Creator_users u ON c.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """, tuple(params))

                chats = []
                for row in cursor.fetchall():
                    chat_data = json.loads(row[6]) if row[6] else {
                        "history": {"messages": {}}}
                    message_count = len(chat_data.get(
                        "history", {}).get("messages", {}))

                    chats.append({
                        "id": row[0],
                        "user_id": row[1],
                        "assistant_id": row[2],
                        "title": row[3],
                        "created_at": row[4],
                        "updated_at": row[5],
                        "message_count": message_count,
                        "archived": row[7],
                        "user_name": row[8],
                        "user_email": row[9],
                        "source": "lamb_internal"  # Mark source for unified analytics
                    })

                return chats

        except sqlite3.Error as e:
            logger.error(
                f"Database error getting lamb_chats for analytics, assistant {assistant_id}: {e}")
            return []
        finally:
            connection.close()

    def count_lamb_chats_for_assistant(self, assistant_id: int) -> int:
        """
        Get total count of chats for an assistant.

        Args:
            assistant_id: LAMB assistant ID

        Returns:
            Count of chats
        """
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}lamb_chats
                    WHERE assistant_id = ?
                """, (assistant_id,))

                result = cursor.fetchone()
                return result[0] if result else 0

        except sqlite3.Error as e:
            logger.error(
                f"Database error counting lamb_chats for assistant {assistant_id}: {e}")
            return 0
        finally:
            connection.close()

    def generate_chat_title(self, first_message: str, max_length: int = 35) -> str:
        """
        Generate an auto-title from the first message content.
        Format: "First few words... - Dec 29 10:45"

        Args:
            first_message: Content of the first message
            max_length: Maximum length for the message portion

        Returns:
            Generated title string
        """
        from datetime import datetime

        # Clean and truncate message
        clean_msg = first_message.strip().replace('\n', ' ')
        if len(clean_msg) > max_length:
            # Find a good break point (word boundary)
            truncated = clean_msg[:max_length]
            last_space = truncated.rfind(' ')
            if last_space > max_length // 2:
                truncated = truncated[:last_space]
            clean_msg = truncated + "..."

        # Add timestamp
        now = datetime.now()
        timestamp = now.strftime("%b %d %H:%M")

        return f"{clean_msg} - {timestamp}" if clean_msg else f"New Chat - {timestamp}"

    # =========================================================================
    # Unified LTI Activity Operations
    # =========================================================================

    def get_lti_global_config(self) -> Optional[Dict[str, Any]]:
        """Get the global LTI config from DB (singleton row)."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"SELECT * FROM {self.table_prefix}lti_global_config WHERE id = 1")
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    return dict(zip(columns, row))
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting LTI global config: {e}")
            return None
        finally:
            connection.close()

    def set_lti_global_config(self, oauth_consumer_key: str, oauth_consumer_secret: str, updated_by: str = None) -> bool:
        """Set or update the global LTI config (INSERT OR REPLACE singleton)."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.table_prefix}lti_global_config
                    (id, oauth_consumer_key, oauth_consumer_secret, updated_at, updated_by)
                    VALUES (1, ?, ?, ?, ?)
                """, (oauth_consumer_key, oauth_consumer_secret, int(time.time()), updated_by))
                return True
        except sqlite3.Error as e:
            logger.error(f"Error setting LTI global config: {e}")
            return False
        finally:
            connection.close()

    def get_lti_activity_by_resource_link(self, resource_link_id: str) -> Optional[Dict[str, Any]]:
        """Get an LTI activity by its resource_link_id."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT * FROM {self.table_prefix}lti_activities
                    WHERE resource_link_id = ?
                """, (resource_link_id,))
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    return dict(zip(columns, row))
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting LTI activity: {e}")
            return None
        finally:
            connection.close()

    def create_lti_activity(self, resource_link_id: str, organization_id: int,
                            owi_group_id: str, owi_group_name: str,
                            configured_by_email: str, configured_by_name: str = None,
                            context_id: str = None, context_title: str = None,
                            activity_name: str = None,
                            chat_visibility_enabled: bool = False) -> Optional[int]:
        """Create a new LTI activity. Returns the activity id."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}lti_activities
                    (resource_link_id, organization_id, context_id, context_title, activity_name,
                     owi_group_id, owi_group_name, owner_email, owner_name,
                     configured_by_email, configured_by_name,
                     chat_visibility_enabled, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """, (resource_link_id, organization_id, context_id, context_title,
                      activity_name, owi_group_id, owi_group_name,
                      configured_by_email, configured_by_name,
                      configured_by_email, configured_by_name,
                      1 if chat_visibility_enabled else 0, now, now))
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error creating LTI activity: {e}")
            return None
        finally:
            connection.close()

    def get_lti_activities_by_org(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get all LTI activities for an organization (for org-admin)."""
        connection = self.get_connection()
        if not connection:
            return []
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT * FROM {self.table_prefix}lti_activities
                    WHERE organization_id = ?
                    ORDER BY created_at DESC
                """, (organization_id,))
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting LTI activities by org: {e}")
            return []
        finally:
            connection.close()

    def update_lti_activity(self, activity_id: int, **kwargs) -> bool:
        """Update an LTI activity. Pass fields to update as keyword arguments."""
        allowed_fields = {'activity_name', 'status', 'context_title', 'chat_visibility_enabled', 'owner_email', 'owner_name'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                updates['updated_at'] = int(time.time())
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                values = list(updates.values()) + [activity_id]
                cursor.execute(f"""
                    UPDATE {self.table_prefix}lti_activities
                    SET {set_clause}
                    WHERE id = ?
                """, values)
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating LTI activity: {e}")
            return False
        finally:
            connection.close()

    def add_assistants_to_activity(self, activity_id: int, assistant_ids: List[int]) -> bool:
        """Add assistants to an LTI activity (junction table)."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())
                for aid in assistant_ids:
                    cursor.execute(f"""
                        INSERT OR IGNORE INTO {self.table_prefix}lti_activity_assistants
                        (activity_id, assistant_id, added_at)
                        VALUES (?, ?, ?)
                    """, (activity_id, aid, now))
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding assistants to activity: {e}")
            return False
        finally:
            connection.close()

    def remove_assistants_from_activity(self, activity_id: int, assistant_ids: List[int]) -> bool:
        """Remove assistants from an LTI activity."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                placeholders = ",".join("?" for _ in assistant_ids)
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}lti_activity_assistants
                    WHERE activity_id = ? AND assistant_id IN ({placeholders})
                """, [activity_id] + list(assistant_ids))
                return True
        except sqlite3.Error as e:
            logger.error(f"Error removing assistants from activity: {e}")
            return False
        finally:
            connection.close()

    def get_activity_assistants(self, activity_id: int) -> List[Dict[str, Any]]:
        """Get all assistants linked to an LTI activity, with assistant details."""
        connection = self.get_connection()
        if not connection:
            return []
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT a.id, a.name, a.owner, a.description,
                           aa.added_at,
                           ap.oauth_consumer_name
                    FROM {self.table_prefix}lti_activity_assistants aa
                    JOIN {self.table_prefix}assistants a ON aa.assistant_id = a.id
                    LEFT JOIN {self.table_prefix}assistant_publish ap ON a.id = ap.assistant_id
                    WHERE aa.activity_id = ?
                    ORDER BY a.name
                """, (activity_id,))
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting activity assistants: {e}")
            return []
        finally:
            connection.close()

    def create_lti_activity_user(self, activity_id: int, user_email: str,
                                  user_name: str = '', user_display_name: str = '',
                                  lms_user_id: str = None,
                                  owi_user_id: str = None) -> Optional[int]:
        """Create or get an LTI activity user record. Updates access tracking on each call. Returns the user record id."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                now = int(time.time())
                # Check if exists
                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}lti_activity_users
                    WHERE user_email = ? AND activity_id = ?
                """, (user_email, activity_id))
                existing = cursor.fetchone()
                if existing:
                    # Update access tracking
                    cursor.execute(f"""
                        UPDATE {self.table_prefix}lti_activity_users
                        SET last_access_at = ?, access_count = access_count + 1
                        WHERE id = ?
                    """, (now, existing[0]))
                    # Update owi_user_id if provided and not set
                    if owi_user_id:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}lti_activity_users
                            SET owi_user_id = ?
                            WHERE id = ? AND (owi_user_id IS NULL OR owi_user_id = '')
                        """, (owi_user_id, existing[0]))
                    return existing[0]
                # Create
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}lti_activity_users
                    (activity_id, user_email, user_name, user_display_name,
                     lms_user_id, owi_user_id, last_access_at, access_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (activity_id, user_email, user_name, user_display_name,
                      lms_user_id, owi_user_id, now, now))
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error creating LTI activity user: {e}")
            return None
        finally:
            connection.close()

    def record_student_consent(self, activity_id: int, user_email: str) -> bool:
        """Record that a student has accepted the chat visibility consent."""
        connection = self.get_connection()
        if not connection:
            return False
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    UPDATE {self.table_prefix}lti_activity_users
                    SET consent_given_at = ?
                    WHERE activity_id = ? AND user_email = ?
                """, (int(time.time()), activity_id, user_email))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error recording student consent: {e}")
            return False
        finally:
            connection.close()

    def get_activity_user(self, activity_id: int, user_email: str) -> Optional[Dict[str, Any]]:
        """Get a specific LTI activity user record."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT * FROM {self.table_prefix}lti_activity_users
                    WHERE activity_id = ? AND user_email = ?
                """, (activity_id, user_email))
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    return dict(zip(columns, row))
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting activity user: {e}")
            return None
        finally:
            connection.close()

    def get_activity_students(self, activity_id: int, page: int = 1,
                               per_page: int = 20) -> Dict[str, Any]:
        """Get paginated list of students for an activity (for dashboard)."""
        connection = self.get_connection()
        if not connection:
            return {"students": [], "total": 0}
        try:
            with connection:
                cursor = connection.cursor()
                # Count total
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}lti_activity_users
                    WHERE activity_id = ?
                """, (activity_id,))
                total = cursor.fetchone()[0]
                # Get page
                offset = (page - 1) * per_page
                cursor.execute(f"""
                    SELECT * FROM {self.table_prefix}lti_activity_users
                    WHERE activity_id = ?
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?
                """, (activity_id, per_page, offset))
                columns = [col[0] for col in cursor.description]
                students = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return {"students": students, "total": total}
        except sqlite3.Error as e:
            logger.error(f"Error getting activity students: {e}")
            return {"students": [], "total": 0}
        finally:
            connection.close()

    def get_all_activity_user_owi_ids(self, activity_id: int) -> List[str]:
        """Get all OWI user IDs for an activity (for chat queries)."""
        connection = self.get_connection()
        if not connection:
            return []
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT owi_user_id FROM {self.table_prefix}lti_activity_users
                    WHERE activity_id = ? AND owi_user_id IS NOT NULL AND owi_user_id != ''
                """, (activity_id,))
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting activity user OWI IDs: {e}")
            return []
        finally:
            connection.close()

    def create_lti_identity_link(self, lms_user_id: str, creator_user_id: int,
                                  lms_email: str = None) -> Optional[int]:
        """Create a link between an LMS identity and a LAMB Creator user."""
        connection = self.get_connection()
        if not connection:
            return None
        try:
            with connection:
                cursor = connection.cursor()
                # Check if this exact link already exists
                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}lti_identity_links
                    WHERE lms_user_id = ? AND creator_user_id = ?
                """, (lms_user_id, creator_user_id))
                existing = cursor.fetchone()
                if existing:
                    return existing[0]
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}lti_identity_links
                    (lms_user_id, lms_email, creator_user_id, linked_at)
                    VALUES (?, ?, ?, ?)
                """, (lms_user_id, lms_email, creator_user_id, int(time.time())))
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error creating LTI identity link: {e}")
            return None
        finally:
            connection.close()

    def get_creator_users_by_lms_identity(self, lms_user_id: str = None,
                                           lms_email: str = None) -> List[Dict[str, Any]]:
        """
        Find Creator users matching an LMS identity.
        Tries: 1) email match in Creator_users, 2) lti_user_id match, 3) lti_identity_links.
        Returns list of Creator user dicts (may be multiple if in different orgs).
        """
        results = []
        seen_ids = set()
        connection = self.get_connection()
        if not connection:
            return results
        try:
            with connection:
                cursor = connection.cursor()

                # Strategy 1: Direct email match in Creator_users
                if lms_email:
                    cursor.execute(f"""
                        SELECT id, organization_id, user_email, user_name, user_type, 
                               enabled, lti_user_id, auth_provider
                        FROM {self.table_prefix}Creator_users
                        WHERE user_email = ? AND enabled = 1
                    """, (lms_email,))
                    for row in cursor.fetchall():
                        columns = [col[0] for col in cursor.description]
                        user = dict(zip(columns, row))
                        if user['id'] not in seen_ids:
                            results.append(user)
                            seen_ids.add(user['id'])

                # Strategy 2: Match by lti_user_id in Creator_users
                if lms_user_id:
                    cursor.execute(f"""
                        SELECT id, organization_id, user_email, user_name, user_type,
                               enabled, lti_user_id, auth_provider
                        FROM {self.table_prefix}Creator_users
                        WHERE lti_user_id = ? AND enabled = 1
                    """, (lms_user_id,))
                    for row in cursor.fetchall():
                        columns = [col[0] for col in cursor.description]
                        user = dict(zip(columns, row))
                        if user['id'] not in seen_ids:
                            results.append(user)
                            seen_ids.add(user['id'])

                # Strategy 3: Check lti_identity_links
                if lms_user_id:
                    cursor.execute(f"""
                        SELECT cu.id, cu.organization_id, cu.user_email, cu.user_name,
                               cu.user_type, cu.enabled, cu.lti_user_id, cu.auth_provider
                        FROM {self.table_prefix}lti_identity_links lil
                        JOIN {self.table_prefix}Creator_users cu ON lil.creator_user_id = cu.id
                        WHERE lil.lms_user_id = ? AND cu.enabled = 1
                    """, (lms_user_id,))
                    for row in cursor.fetchall():
                        columns = [col[0] for col in cursor.description]
                        user = dict(zip(columns, row))
                        if user['id'] not in seen_ids:
                            results.append(user)
                            seen_ids.add(user['id'])

                return results
        except sqlite3.Error as e:
            logger.error(f"Error finding creator users by LMS identity: {e}")
            return results
        finally:
            connection.close()

    def get_published_assistants_for_org_user(self, organization_id: int,
                                               creator_user_id: int,
                                               creator_user_email: str) -> List[Dict[str, Any]]:
        """
        Get all published assistants accessible by a Creator user within an org.
        Includes: owned assistants + assistants shared with them. Only published ones.
        """
        connection = self.get_connection()
        if not connection:
            return []
        try:
            with connection:
                cursor = connection.cursor()
                # Published assistants owned by this user in this org
                cursor.execute(f"""
                    SELECT a.id, a.name, a.description, a.owner,
                           ap.oauth_consumer_name, ap.group_id, ap.group_name,
                           'owned' as access_type
                    FROM {self.table_prefix}assistants a
                    JOIN {self.table_prefix}assistant_publish ap ON a.id = ap.assistant_id
                    WHERE a.owner = ? AND a.organization_id = ?
                          AND ap.oauth_consumer_name IS NOT NULL
                          AND ap.oauth_consumer_name != 'null'
                    ORDER BY a.name
                """, (creator_user_email, organization_id))
                columns = [col[0] for col in cursor.description]
                owned = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Published assistants shared with this user in this org
                cursor.execute(f"""
                    SELECT a.id, a.name, a.description, a.owner,
                           ap.oauth_consumer_name, ap.group_id, ap.group_name,
                           'shared' as access_type
                    FROM {self.table_prefix}assistant_shares s
                    JOIN {self.table_prefix}assistants a ON s.assistant_id = a.id
                    JOIN {self.table_prefix}assistant_publish ap ON a.id = ap.assistant_id
                    WHERE s.shared_with_user_id = ? AND a.organization_id = ?
                          AND ap.oauth_consumer_name IS NOT NULL
                          AND ap.oauth_consumer_name != 'null'
                    ORDER BY a.name
                """, (creator_user_id, organization_id))
                columns = [col[0] for col in cursor.description]
                shared = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Deduplicate (in case somehow both owned and shared)
                seen = set()
                result = []
                for a in owned + shared:
                    if a['id'] not in seen:
                        result.append(a)
                        seen.add(a['id'])
                return result
        except sqlite3.Error as e:
            logger.error(f"Error getting published assistants for org user: {e}")
            return []
        finally:
            connection.close()

    # ------------------------------------------------------------------ #
    #  User Profile — aggregated overview of a user's resources           #
    # ------------------------------------------------------------------ #

    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a comprehensive profile for a user including all owned resources
        and resources shared with them.

        Args:
            user_id: LAMB creator user ID

        Returns:
            Dict with user info, organization, owned resources, and shared resources.
            None if user not found or database error.
        """
        connection = self.get_connection()
        if not connection:
            logger.error("Could not establish database connection for get_user_profile")
            return None

        try:
            with connection:
                cursor = connection.cursor()

                # 1. User info + organization
                cursor.execute(f"""
                    SELECT 
                        u.id, u.user_email, u.user_name, u.user_type,
                        u.enabled, u.auth_provider, u.lti_user_id,
                        u.created_at, u.updated_at, u.organization_id,
                        o.name as org_name, o.slug as org_slug, o.is_system as org_is_system,
                        r.role as org_role
                    FROM {self.table_prefix}Creator_users u
                    LEFT JOIN {self.table_prefix}organizations o ON u.organization_id = o.id
                    LEFT JOIN {self.table_prefix}organization_roles r 
                        ON r.user_id = u.id AND r.organization_id = u.organization_id
                    WHERE u.id = ?
                """, (user_id,))

                row = cursor.fetchone()
                if not row:
                    logger.warning(f"User {user_id} not found for profile")
                    return None

                user_email = row[1]
                organization_id = row[9]

                user_info = {
                    'id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'user_type': row[3],
                    'enabled': bool(row[4]),
                    'auth_provider': row[5],
                    'lti_user_id': row[6],
                    'created_at': row[7],
                    'updated_at': row[8],
                }

                organization_info = {
                    'id': organization_id,
                    'name': row[10],
                    'slug': row[11],
                    'is_system': bool(row[12]) if row[12] is not None else False,
                    'role': row[13],
                } if organization_id else None

                # 2. Owned assistants (linked by email — soft reference)
                cursor.execute(f"""
                    SELECT 
                        a.id, a.name, a.description, a.created_at, a.updated_at,
                        CASE 
                            WHEN ap.oauth_consumer_name IS NOT NULL 
                                 AND ap.oauth_consumer_name != 'null' THEN 1 
                            ELSE 0 
                        END as published
                    FROM {self.table_prefix}assistants a
                    LEFT JOIN {self.table_prefix}assistant_publish ap ON a.id = ap.assistant_id
                    WHERE a.owner = ?
                    ORDER BY a.created_at DESC
                """, (user_email,))

                owned_assistants = []
                for r in cursor.fetchall():
                    owned_assistants.append({
                        'id': r[0], 'name': r[1], 'description': r[2],
                        'created_at': r[3], 'updated_at': r[4], 'published': bool(r[5])
                    })

                # 3. Owned knowledge bases (linked by user_id — hard FK)
                cursor.execute(f"""
                    SELECT id, kb_id, kb_name, is_shared, created_at, updated_at
                    FROM {self.table_prefix}kb_registry
                    WHERE owner_user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,))

                owned_kbs = []
                for r in cursor.fetchall():
                    owned_kbs.append({
                        'id': r[0], 'kb_id': r[1], 'kb_name': r[2],
                        'is_shared': bool(r[3]), 'created_at': r[4], 'updated_at': r[5]
                    })

                # 4. Owned rubrics (linked by email — soft reference)
                cursor.execute(f"""
                    SELECT id, rubric_id, title, description, is_public, created_at, updated_at
                    FROM {self.table_prefix}rubrics
                    WHERE owner_email = ?
                    ORDER BY created_at DESC
                """, (user_email,))

                owned_rubrics = []
                for r in cursor.fetchall():
                    owned_rubrics.append({
                        'id': r[0], 'rubric_id': r[1], 'title': r[2],
                        'description': r[3], 'is_public': bool(r[4]),
                        'created_at': r[5], 'updated_at': r[6]
                    })

                # 5. Owned templates (linked by email — hard FK)
                cursor.execute(f"""
                    SELECT id, name, description, is_shared, created_at, updated_at
                    FROM {self.table_prefix}prompt_templates
                    WHERE owner_email = ?
                    ORDER BY created_at DESC
                """, (user_email,))

                owned_templates = []
                for r in cursor.fetchall():
                    owned_templates.append({
                        'id': r[0], 'name': r[1], 'description': r[2],
                        'is_shared': bool(r[3]), 'created_at': r[4], 'updated_at': r[5]
                    })

                # 6. Assistants shared with this user (by user_id — hard FK)
                cursor.execute(f"""
                    SELECT 
                        a.id, a.name, a.description,
                        s.shared_at,
                        u.user_name as owner_name, u.user_email as owner_email
                    FROM {self.table_prefix}assistant_shares s
                    JOIN {self.table_prefix}assistants a ON s.assistant_id = a.id
                    JOIN {self.table_prefix}Creator_users u ON s.shared_by_user_id = u.id
                    WHERE s.shared_with_user_id = ?
                    ORDER BY s.shared_at DESC
                """, (user_id,))

                shared_assistants = []
                for r in cursor.fetchall():
                    shared_assistants.append({
                        'id': r[0], 'name': r[1], 'description': r[2],
                        'shared_at': r[3], 'owner_name': r[4], 'owner_email': r[5]
                    })

                # 7. Shared KBs in org (org-level, excluding own)
                shared_kbs = []
                if organization_id:
                    cursor.execute(f"""
                        SELECT 
                            kr.id, kr.kb_id, kr.kb_name, kr.created_at,
                            cu.user_name as owner_name, cu.user_email as owner_email
                        FROM {self.table_prefix}kb_registry kr
                        JOIN {self.table_prefix}Creator_users cu ON kr.owner_user_id = cu.id
                        WHERE kr.organization_id = ? AND kr.is_shared = 1 AND kr.owner_user_id != ?
                        ORDER BY kr.updated_at DESC
                    """, (organization_id, user_id))

                    for r in cursor.fetchall():
                        shared_kbs.append({
                            'id': r[0], 'kb_id': r[1], 'kb_name': r[2],
                            'created_at': r[3], 'owner_name': r[4], 'owner_email': r[5]
                        })

                # 8. Shared templates in org (org-level, excluding own)
                shared_templates = []
                if organization_id:
                    cursor.execute(f"""
                        SELECT 
                            pt.id, pt.name, pt.description, pt.created_at,
                            cu.user_name as owner_name, cu.user_email as owner_email
                        FROM {self.table_prefix}prompt_templates pt
                        LEFT JOIN {self.table_prefix}Creator_users cu ON pt.owner_email = cu.user_email
                        WHERE pt.organization_id = ? AND pt.is_shared = 1 AND pt.owner_email != ?
                        ORDER BY pt.updated_at DESC
                    """, (organization_id, user_email))

                    for r in cursor.fetchall():
                        shared_templates.append({
                            'id': r[0], 'name': r[1], 'description': r[2],
                            'created_at': r[3], 'owner_name': r[4], 'owner_email': r[5]
                        })

                # 9. Public rubrics in org (org-level, excluding own)
                shared_rubrics = []
                if organization_id:
                    cursor.execute(f"""
                        SELECT 
                            r.id, r.rubric_id, r.title, r.description, r.created_at,
                            cu.user_name as owner_name, cu.user_email as owner_email
                        FROM {self.table_prefix}rubrics r
                        LEFT JOIN {self.table_prefix}Creator_users cu ON r.owner_email = cu.user_email
                        WHERE r.organization_id = ? AND r.is_public = 1 AND r.owner_email != ?
                        ORDER BY r.updated_at DESC
                    """, (organization_id, user_email))

                    for r in cursor.fetchall():
                        shared_rubrics.append({
                            'id': r[0], 'rubric_id': r[1], 'title': r[2],
                            'description': r[3], 'created_at': r[4],
                            'owner_name': r[5], 'owner_email': r[6]
                        })

                # Assemble the response
                published_count = sum(1 for a in owned_assistants if a['published'])

                return {
                    'user': user_info,
                    'organization': organization_info,
                    'owned': {
                        'assistants': {
                            'total': len(owned_assistants),
                            'published': published_count,
                            'items': owned_assistants,
                        },
                        'knowledge_bases': {
                            'total': len(owned_kbs),
                            'shared': sum(1 for kb in owned_kbs if kb['is_shared']),
                            'items': owned_kbs,
                        },
                        'rubrics': {
                            'total': len(owned_rubrics),
                            'public': sum(1 for r in owned_rubrics if r['is_public']),
                            'items': owned_rubrics,
                        },
                        'templates': {
                            'total': len(owned_templates),
                            'shared': sum(1 for t in owned_templates if t['is_shared']),
                            'items': owned_templates,
                        },
                    },
                    'shared_with_me': {
                        'assistants': {
                            'total': len(shared_assistants),
                            'items': shared_assistants,
                        },
                        'knowledge_bases': {
                            'total': len(shared_kbs),
                            'items': shared_kbs,
                        },
                        'rubrics': {
                            'total': len(shared_rubrics),
                            'items': shared_rubrics,
                        },
                        'templates': {
                            'total': len(shared_templates),
                            'items': shared_templates,
                        },
                    },
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in get_user_profile: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_user_profile: {e}")
            return None
        finally:
            connection.close()
