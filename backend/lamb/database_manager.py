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
import logging
from .lamb_classes import Assistant, LTIUser, Organization, OrganizationRole
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv
from .owi_bridge.owi_users import OwiUserManager
import jwt
import config


logging.basicConfig(level=logging.INFO)


class LambDatabaseManager:
    def __init__(self):

        #        logging.debug("Initializing LambDatabaseManager")
        try:
            # Load environment variables
            load_dotenv()

            # Get database configuration from environment variables
            self.table_prefix = os.getenv('LAMB_DB_PREFIX', '')
#            logging.debug(f"Table prefix: {self.table_prefix}")

            lamb_db_path = os.getenv('LAMB_DB_PATH')
            if not lamb_db_path:
                logging.error(
                    "LAMB_DB_PATH not found in environment variables")
                raise ValueError(
                    "LAMB_DB_PATH must be specified in environment variables")

            self.db_path = os.path.join(lamb_db_path, 'lamb_v4.db')
            if not os.path.exists(self.db_path):
                # Create the database file and directory if they don't exist
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                self.create_database_and_tables()
                logging.info(f"Created database at: {self.db_path}")
#            logging.debug(f"Found database at: {self.db_path}")
            
            # Always run migrations on initialization (handles existing databases)
            self.run_migrations()

        except Exception as e:
            logging.error(f"Error during initialization: {e}")
            raise

    def get_connection(self):
        # logging.debug(f"Attempting to connect to database at: {self.db_path}")
        try:
            connection = sqlite3.connect(self.db_path)
 #           logging.debug("Database connection established successfully")
            return connection
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to database: {e}")
            return None

    def create_database_and_tables(self):
        logging.debug("Starting database and tables creation")
        try:
            connection = self.get_connection()
            if not connection:
                logging.error("Failed to establish database connection")
                return

            with connection:
                cursor = connection.cursor()

                # Create the organizations table
                logging.debug("Creating organizations table")
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
                cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_slug ON {self.table_prefix}organizations(slug)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_status ON {self.table_prefix}organizations(status)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}organizations_is_system ON {self.table_prefix}organizations(is_system)")
                logging.info(
                    f"Table '{self.table_prefix}organizations' created successfully")

                # Create the organization_roles table
                logging.debug("Creating organization_roles table")
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
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_org ON {self.table_prefix}organization_roles(organization_id)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_user ON {self.table_prefix}organization_roles(user_id)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}org_roles_role ON {self.table_prefix}organization_roles(role)")
                logging.info(
                    f"Table '{self.table_prefix}organization_roles' created successfully")

                # Create usage_logs table
                logging.debug("Creating usage_logs table")
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
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}usage_logs_org_date ON {self.table_prefix}usage_logs(organization_id, created_at)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}usage_logs_user_date ON {self.table_prefix}usage_logs(user_id, created_at)")
                logging.info(
                    f"Table '{self.table_prefix}usage_logs' created successfully")

                # Create the model_permissions table
                logging.debug("Creating model_permissions table")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_prefix}model_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        access_type TEXT NOT NULL CHECK(access_type IN ('include', 'exclude')),
                        UNIQUE(user_email, model_name)
                    )
                """)
                logging.info(
                    f"Table '{self.table_prefix}model_permissions' created successfully")

                # Create the assistants table
                logging.debug("Creating assistants table")
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
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}assistants_org ON {self.table_prefix}assistants(organization_id)")
                logging.info(
                    f"Table '{self.table_prefix}assistants' created successfully")

                # Create the lti_users table
                logging.debug("Creating lti_users table")
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
                logging.info(
                    f"Table '{self.table_prefix}lti_users' created successfully")

                # Create the assistant_publish table
                logging.debug("Creating assistant_publish table")
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
                logging.info(
                    f"Table '{self.table_prefix}assistant_publish' created successfully")

                # Create the Creator_users table
                logging.debug("Creating Creator_users table")
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
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_org ON {self.table_prefix}Creator_users(organization_id)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_type ON {self.table_prefix}Creator_users(user_type)")
                logging.info(
                    f"Table '{self.table_prefix}Creator_users' created successfully")

                # Create the collections table
                logging.debug("Creating collections table")
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
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}collections_org ON {self.table_prefix}collections(organization_id)")
                logging.info(
                    f"Table '{self.table_prefix}collections' created successfully")

            
                # Create the config table
                logging.debug("Creating config table")
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

                logging.info(
                    f"Table '{self.table_prefix}config' created successfully")

            # Initialize system organization and admin user
            self.initialize_system_organization()
        except sqlite3.Error as e:
            logging.error(f"Database error occurred: {e}")

        finally:
            if connection:
                connection.close()
                logging.debug("Database connection closed")

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
            logging.info(f"Created OWI admin user: {config.OWI_ADMIN_EMAIL}")
        else:
            # Ensure the user has admin role in OWI
            if owi_user.get('role') != 'admin':
                owi_manager.update_user_role_by_email(config.OWI_ADMIN_EMAIL, 'admin')
                logging.info(f"Updated OWI user to admin role: {config.OWI_ADMIN_EMAIL}")
        
        # Note: LAMB creator user will be created in initialize_system_organization
        # to ensure it's created with the correct organization_id

    def initialize_system_organization(self):
        """Initialize the system organization and admin user"""
        logging.info("Initializing system organization")
        
        # Check if system organization exists
        system_org = self.get_organization_by_slug("lamb")
        
        if not system_org:
            # Create system organization from environment
            system_org_id = self.create_system_organization()
            if not system_org_id:
                logging.error("Failed to create system organization")
                return
        else:
            system_org_id = system_org['id']
            # Update system organization config from .env
            self.sync_system_org_with_env(system_org_id)
            logging.info("System organization configuration updated from environment")
        
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
                logging.info(f"Created LAMB admin user: {config.OWI_ADMIN_EMAIL}")
                # Assign admin role in organization
                self.assign_organization_role(
                    organization_id=system_org_id,
                    user_id=admin_user_id,
                    role="admin"
                )
                logging.info(f"Assigned admin role to user {admin_user_id} in system organization")
        else:
            # User exists, ensure they have correct organization and role
            admin_user_id = admin_user['id']
            
            # Check and update organization if needed
            if admin_user.get('organization_id') != system_org_id:
                self.update_user_organization(admin_user_id, system_org_id)
                logging.info(f"Updated admin user organization to system org")
            
            # Check and assign admin role if needed
            current_role = self.get_user_organization_role(admin_user_id, system_org_id)
            if current_role != "admin":
                self.assign_organization_role(
                    organization_id=system_org_id,
                    user_id=admin_user_id,
                    role="admin"
                )
                logging.info(f"Updated admin user role to 'admin' in system organization")
    
    def run_migrations(self):
        """Run database migrations for schema updates"""
        logging.info("Running database migrations")
        connection = self.get_connection()
        if not connection:
            logging.error("Could not establish database connection for migrations")
            return
        
        try:
            with connection:
                cursor = connection.cursor()
                
                # Migration 1: Add user_type column to Creator_users if it doesn't exist
                cursor.execute(f"PRAGMA table_info({self.table_prefix}Creator_users)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'user_type' not in columns:
                    logging.info("Adding user_type column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN user_type TEXT NOT NULL DEFAULT 'creator' 
                        CHECK(user_type IN ('creator', 'end_user'))
                    """)
                    # Create index for user_type
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_type ON {self.table_prefix}Creator_users(user_type)")
                    logging.info("Successfully added user_type column and index")
                else:
                    logging.debug("user_type column already exists in Creator_users table")
                
                # Migration 2: Add CASCADE to Creator_users organization foreign key
                # Check if the table needs migration by inspecting foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({self.table_prefix}Creator_users)")
                fks = cursor.fetchall()
                needs_cascade_migration = False
                
                for fk in fks:
                    # fk format: (id, seq, table, from, to, on_update, on_delete, match)
                    if fk[2] == f"{self.table_prefix}organizations" and fk[6] != 'CASCADE':
                        needs_cascade_migration = True
                        break
                
                if needs_cascade_migration:
                    logging.info("Adding CASCADE to Creator_users organization foreign key")
                    
                    # SQLite doesn't support modifying foreign keys, so we need to recreate the table
                    # Step 1: Create new table with CASCADE
                    cursor.execute(f"""
                        CREATE TABLE {self.table_prefix}Creator_users_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            organization_id INTEGER,
                            user_email TEXT NOT NULL,
                            user_name TEXT NOT NULL,
                            user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
                            user_config JSON,
                            created_at INTEGER NOT NULL,
                            updated_at INTEGER NOT NULL,
                            FOREIGN KEY (organization_id) REFERENCES {self.table_prefix}organizations(id) ON DELETE CASCADE,
                            UNIQUE(user_email)
                        )
                    """)
                    
                    # Step 2: Copy data from old table to new table
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}Creator_users_new
                        SELECT * FROM {self.table_prefix}Creator_users
                    """)
                    
                    # Step 3: Drop old table
                    cursor.execute(f"DROP TABLE {self.table_prefix}Creator_users")
                    
                    # Step 4: Rename new table to original name
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users_new 
                        RENAME TO {self.table_prefix}Creator_users
                    """)
                    
                    # Step 5: Recreate indexes
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_org ON {self.table_prefix}Creator_users(organization_id)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_type ON {self.table_prefix}Creator_users(user_type)")
                    
                    logging.info("Successfully added CASCADE to Creator_users foreign key")
                else:
                    logging.debug("Creator_users foreign key already has CASCADE")
                    
        except sqlite3.Error as e:
            logging.error(f"Migration error: {e}")
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
            logging.warning(f"Could not load assistant defaults for system org: {e}")
        
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
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "models": os.getenv("OPENAI_MODELS", "").split(",") if os.getenv("OPENAI_MODELS") else [],
                "default_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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
                Path(__file__).parent.parent / "static" / "json" / "defaults.json",
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
            
            logging.warning("defaults.json not found, using minimal defaults")
            return {
                "connector": "openai",
                "llm": "gpt-4o-mini",
                "prompt_processor": "simple_augment",
                "rag_processor": "No RAG"
            }
        except Exception as e:
            logging.error(f"Error loading assistant defaults from file: {e}")
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
            logging.warning("Cannot sync non-system organization")
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
            logging.warning(f"Could not ensure assistant_defaults during system sync: {e}")
        
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
                            config['assistant_defaults'] = system_cfg['assistant_defaults'].copy()
                        else:
                            # Fallback to loading from file
                            config['assistant_defaults'] = self._load_assistant_defaults_from_file()
                
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}organizations 
                    (slug, name, is_system, status, config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (slug, name, is_system, status, json.dumps(config), now, now))
                
                org_id = cursor.lastrowid
                logging.info(f"Organization '{name}' created with id: {org_id}")
                return org_id
                
        except sqlite3.Error as e:
            logging.error(f"Error creating organization: {e}")
            return None
        finally:
            connection.close()
    
    def create_organization_with_admin(self, slug: str, name: str, admin_user_id: int, 
                                     signup_enabled: bool = False, signup_key: str = None,
                                     use_system_baseline: bool = True, 
                                     config: Dict[str, Any] = None) -> Optional[int]:
        """
        Create a new organization with admin user assignment and signup configuration
        
        Args:
            slug: URL-friendly organization identifier
            name: Organization display name
            admin_user_id: ID of user from system org to become org admin
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
                is_valid, error_msg = self.validate_signup_key_format(signup_key)
                if not is_valid:
                    logging.error(f"Invalid signup key format: {error_msg}")
                    return None
                
                if not self.validate_signup_key_uniqueness(signup_key):
                    logging.error(f"Signup key '{signup_key}' already exists")
                    return None
            
            # Validate that admin user exists and is in system organization
            admin_user = self.get_creator_user_by_id(admin_user_id)
            if not admin_user:
                logging.error(f"Admin user {admin_user_id} not found")
                return None
            
            system_org = self.get_organization_by_slug("lamb")
            if not system_org or admin_user['organization_id'] != system_org['id']:
                logging.error(f"Admin user {admin_user_id} is not in system organization")
                return None
            
            # Check if user is currently an admin in the system organization
            current_role = self.get_user_organization_role(admin_user_id, system_org['id'])
            if current_role == "admin":
                logging.error(f"User {admin_user_id} is a system admin and cannot be assigned to a new organization")
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
                config['metadata']['admin_user_id'] = admin_user_id
                config['metadata']['admin_user_email'] = admin_user['user_email']
                config['metadata']['created_by_system_admin'] = True
                
                # Create organization
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}organizations 
                    (slug, name, is_system, status, config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (slug, name, False, "active", json.dumps(config), now, now))
                
                org_id = cursor.lastrowid
                logging.info(f"Organization '{name}' created with id: {org_id}")
                
                # Move admin user to new organization (inline to avoid connection conflicts)
                cursor.execute(f"""
                    UPDATE {self.table_prefix}Creator_users
                    SET organization_id = ?, updated_at = ?
                    WHERE id = ?
                """, (org_id, now, admin_user_id))
                
                if cursor.rowcount == 0:
                    logging.error(f"Failed to move admin user to new organization")
                    return None
                
                # Assign admin role to user in new organization (inline to avoid connection conflicts)
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                    (organization_id, user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (org_id, admin_user_id, "admin", now, now))
                
                logging.info(f"Assigned role 'admin' to user {admin_user_id} in organization {org_id}")
                
                logging.info(f"User {admin_user['user_email']} assigned as admin of organization '{name}'")
                return org_id
                
        except sqlite3.Error as e:
            logging.error(f"Error creating organization with admin: {e}")
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
            logging.error(f"Error getting organization by ID: {e}")
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
            logging.error(f"Error getting organization by slug: {e}")
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
            logging.error(f"Error updating organization: {e}")
            return False
        finally:
            connection.close()
    
    def update_organization_config(self, org_id: int, config: Dict[str, Any]) -> bool:
        """Update organization configuration"""
        return self.update_organization(org_id, config=config)
    
    def get_organization_user_count(self, org_id: int) -> int:
        """
        Get the count of users in an organization
        
        Args:
            org_id: Organization ID
            
        Returns:
            Number of users in the organization
        """
        connection = self.get_connection()
        if not connection:
            return 0
        
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.table_prefix}Creator_users
                    WHERE organization_id = ?
                """, (org_id,))
                
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except sqlite3.Error as e:
            logging.error(f"Error counting organization users: {e}")
            return 0
        finally:
            connection.close()
    
    def delete_organization(self, org_id: int) -> bool:
        """
        Delete an organization (cannot delete system organization)
        
        WARNING: With CASCADE enabled, this will also delete all users 
        belonging to this organization. Use get_organization_user_count() 
        to check for users before deletion and warn the user appropriately.
        """
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
                    logging.error("Cannot delete system organization")
                    return False
                
                # Delete organization (CASCADE will delete users and related records)
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}organizations WHERE id = ?
                """, (org_id,))
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logging.info(f"Deleted organization {org_id} (CASCADE deleted associated users)")
                
                return deleted
                
        except sqlite3.Error as e:
            logging.error(f"Error deleting organization: {e}")
            return False
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
            logging.error(f"Error listing organizations: {e}")
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
                
                logging.info(f"Assigned role '{role}' to user {user_id} in organization {organization_id}")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Error assigning organization role: {e}")
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
                           u.user_type
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
                        'user_type': row[5]
                    })
                
                return users
                
        except sqlite3.Error as e:
            logging.error(f"Error getting organization users: {e}")
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
            logging.error(f"Error getting user organizations: {e}")
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
            logging.error(f"Error getting user organization role: {e}")
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
            logging.error(f"Error updating user organization: {e}")
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
                    "providers": {},
                    "knowledge_base": {}
                }
            },
            "features": {
                "rag_enabled": True,
                "mcp_enabled": True,
                "lti_publishing": True,
                "signup_enabled": False
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
            logging.warning("System organization not found, using default config")
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
            logging.error("System organization not found")
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
                        existing_key = config.get('features', {}).get('signup_key')
                        if existing_key and existing_key.strip() == signup_key.strip():
                            logging.warning(f"Signup key '{signup_key}' already exists in organization {org_id}")
                            return False
                    except json.JSONDecodeError:
                        continue
                
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Error validating signup key uniqueness: {e}")
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
                            logging.info(f"Found organization '{slug}' (ID: {org_id}) for signup key")
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
                        logging.warning(f"Invalid JSON config for organization {org_id}")
                        continue
                
                logging.info(f"No organization found for signup key '{signup_key}'")
                return None
                
        except sqlite3.Error as e:
            logging.error(f"Error finding organization by signup key: {e}")
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
                logging.warning("System organization 'lamb' not found")
                return False
            
            # Check user's role in system organization
            user_role = self.get_user_organization_role(creator_user['id'], system_org['id'])
            return user_role == 'admin'
            
        except Exception as e:
            logging.error(f"Error checking system admin status for {user_email}: {e}")
            return False
    
    def is_organization_admin(self, user_email: str, organization_id: int) -> bool:
        """
        Check if a user is an admin or owner of a specific organization
        """
        try:
            creator_user = self.get_creator_user_by_email(user_email)
            if not creator_user:
                return False
            
            user_role = self.get_user_organization_role(creator_user['id'], organization_id)
            return user_role in ['admin', 'owner']
            
        except Exception as e:
            logging.error(f"Error checking organization admin status: {e}")
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
            logging.error("Could not establish database connection")
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
            logging.error(f"Database error in get_creator_user_by_id: {e}")
            return None
        except Exception as e:
            logging.error(
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
            Returns dict with: id, email, name, user_config
        """
        connection = self.get_connection()
        if not connection:
            logging.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id, organization_id, user_email, user_name, user_type, user_config 
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
                    'user_config': json.loads(result[5]) if result[5] else {}
                }

        except sqlite3.Error as e:
            logging.error(f"Database error in get_creator_user_by_email: {e}")
            return None
        except Exception as e:
            logging.error(
                f"Unexpected error in get_creator_user_by_email: {e}")
            return None
        finally:
            connection.close()
 #           logging.debug("Database connection closed")

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
        logging.debug(f"Creating creator user: {user_email}")

        try:
            # First check if creator user already exists
            connection = self.get_connection()
            if not connection:
                logging.error("Could not establish database connection")
                return None

            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT id FROM {self.table_prefix}Creator_users 
                    WHERE user_email = ?
                """, (user_email,))

                if cursor.fetchone():
                    logging.warning(
                        f"Creator user {user_email} already exists")
                    return None

            # Initialize OWI user manager and check/create OWI user
            owi_manager = OwiUserManager()
            owi_user = owi_manager.get_user_by_email(user_email)

            if not owi_user:
                # Create new OWI user if doesn't exist
                logging.debug(f"Creating new OWI user for {user_email}")
                owi_user = owi_manager.create_user(
                    name=user_name,
                    email=user_email,
                    password=password,
                    role="user"
                )

                if not owi_user:
                    logging.error(
                        f"Failed to create OWI user for {user_email}")
                    return None

            # If no organization_id provided, use system organization
            if organization_id is None:
                system_org = self.get_organization_by_slug("lamb")
                if system_org:
                    organization_id = system_org['id']
                else:
                    logging.error("System organization not found")
                    return None

            # Now create the creator user
            now = int(time.time())
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    INSERT INTO {self.table_prefix}Creator_users 
                    (organization_id, user_email, user_name, user_type, user_config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (organization_id, user_email, user_name, user_type, "{}", now, now))

                new_user_id = cursor.lastrowid
                logging.info(
                    f"Creator user {user_email} created successfully with id: {new_user_id}")
                return new_user_id

        except Exception as e:
            logging.error(f"Error creating creator user: {e}")
            return None
        finally:
            if connection:
                connection.close()
                logging.debug("Database connection closed")

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
            logging.error("Failed to get database connection")
            return False
            
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"DELETE FROM {self.table_prefix}Creator_users WHERE id = ?", 
                    (user_id,)
                )
                
                if cursor.rowcount > 0:
                    logging.info(f"Creator user with id {user_id} deleted successfully from LAMB database")
                    return True
                else:
                    logging.warning(f"No creator user found with id {user_id}")
                    return False
                    
        except Exception as e:
            logging.error(f"Error deleting creator user: {e}")
            return False
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
                    logging.info(
                        f"LTI user {lti_user.user_email} created with id: {cursor.lastrowid}")
                    return cursor.lastrowid
            except sqlite3.Error as e:
                logging.error(f"Error creating LTI user: {e}")
                return None
            finally:
                connection.close()
   #             logging.debug("Database connection closed")
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
                logging.error(f"Error getting LTI user: {e}")
                return None
            finally:
                connection.close()
        return None

    def update_model_permissions(self, user_data):
        #        logging.debug("Entering update_model_permissions method")
        #        logging.debug(f"Received user_data: {user_data}")
        try:
            connection = self.get_connection()
            logging.debug("Database connection established")

            with connection:
                cursor = connection.cursor()
                user_email = user_data['user_email']
                include_models = user_data['filter']['include']
                exclude_models = user_data['filter']['exclude']
#                logging.debug(f"Processing user_email: {user_email}")

                # First, remove all existing permissions for this user
                cursor.execute(
                    f"DELETE FROM {self.table_prefix}model_permissions WHERE user_email = ?", (user_email,))
#                logging.debug(
#                    f"Deleted existing permissions for user: {user_email}")

                # Insert 'include' permissions
                for model in include_models:
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}model_permissions (user_email, model_name, access_type)
                        VALUES (?, ?, ?)
                    """, (user_email, model, 'include'))
                    logging.debug(
                        f"Inserted 'include' permission for model: {model}")

                # Insert 'exclude' permissions
                for model in exclude_models:
                    cursor.execute(f"""
                        INSERT INTO {self.table_prefix}model_permissions (user_email, model_name, access_type)
                        VALUES (?, ?, ?)
                    """, (user_email, model, 'exclude'))
#                    logging.debug(
#                        f"Inserted 'exclude' permission for model: {model}")

            logging.debug(f"Changes committed to database")

        except sqlite3.Error as e:
            logging.error(f"Error occurred: {e}")

        finally:
            if connection:
                connection.close()
#                logging.debug("SQLite connection closed")

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
            logging.error(f"Error: {e}")
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
                logging.warning(
                    f"No permissions found for user {email}, returning unfiltered models")
                return models
            logging.debug(f"Applying filter for user: {user_filters}")

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

#            logging.debug(f"Filtered models: {filtered_models}")
            return filtered_models
        except Exception as e:
            logging.error(f"Error in filter_models: {str(e)}")
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
                          int(time.time()),  # created_at (using time.time() since datetime was removed)
                          int(time.time())))  # updated_at
                    logging.info(
                        f"Assistant {assistant.name} created with id: {cursor.lastrowid}")
                    return cursor.lastrowid
            except sqlite3.Error as e:
                logging.error(f"Error creating assistant: {e}")
                return None
            finally:
                connection.close()
#                logging.debug("Database connection closed")
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
            logging.error(f"Database error in get_assistant_by_id: {e}")
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
                        a.system_prompt, a.prompt_template, a.RAG_endpoint, a.RAG_Top_k,
                        a.RAG_collections, a.pre_retrieval_endpoint, a.post_retrieval_endpoint,
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
                assistant_dict['published'] = bool(assistant_dict.get('published'))
                # Handle null strings
                if assistant_dict.get('oauth_consumer_name') == "null":
                    assistant_dict['oauth_consumer_name'] = None
                # Map api_callback to metadata field for new API responses (Phase 1 refactor completion)
                assistant_dict['metadata'] = assistant_dict.get('api_callback', '')
                
                return assistant_dict

        except sqlite3.Error as e:
            logging.error(f"Error getting assistant {assistant_id} with publication: {e}")
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
                            logging.error(f"Error creating assistant: {e}")
                            return None
                    else:
                        return None
            except sqlite3.Error as e:
                logging.error(f"Error getting assistant: {e}")
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
#                logging.debug(f"Retrieved assistants data: {assistants_data}")

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
            logging.error(f"Error getting assistants: {e}")
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
                logging.error(f"Error getting assistants: {e}")
                return None
            finally:
                if connection:
                    connection.close()
                    logging.debug("Database connection closed")
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
                    assistant_dict['published'] = bool(assistant_dict.get('published'))
                    # Handle null strings
                    if assistant_dict.get('oauth_consumer_name') == "null":
                        assistant_dict['oauth_consumer_name'] = None
                    assistants_list.append(assistant_dict)

                return assistants_list

        except sqlite3.Error as e:
            logging.error(f"Error getting all assistants with publication: {e}")
            return []
        finally:
            connection.close()

    def get_list_of_assitants_id_and_name(self):
        """Get list of assistants providing only id and name"""
        connection = self.get_connection()
        if not connection:
            return []
        assistants_list = []
        assistants_table = self._get_table_name('assistants')
        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"SELECT id, name, owner FROM {assistants_table}")
                rows = cursor.fetchall()
                for row in rows:
                    assistants_list.append({
                        'id': row[0],
                        'name': row[1],
                        'owner': row[2]
                    })
                return assistants_list
        except sqlite3.Error as e:
            logging.error(f"Error getting list of assistants: {e}")
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
                #logging.info(f"DB Query for owner '{owner}' (limit={limit}, offset={offset}) - Total Count: {total_count}")
                #logging.debug(f"DB Query Raw Rows ({len(rows)}): {rows}")
                # --- End Logging --- #

                for row in rows:
                    assistant_dict = dict(zip(columns, row))
                    # Convert boolean flag back to Python boolean
                    assistant_dict['published'] = bool(assistant_dict.get('published'))
                    # Map api_callback to metadata field for new API responses (Phase 1 refactor completion)
                    assistant_dict['metadata'] = assistant_dict.get('api_callback', '')
                    assistants_list.append(assistant_dict)

                return assistants_list, total_count

        except sqlite3.Error as e:
            logging.error(f"Error getting paginated assistants for owner {owner}: {e}")
            return [], 0 # Return empty list and 0 count on error
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
                    assistant_dict['published'] = bool(assistant_dict.get('published'))
                    assistant_dict['metadata'] = assistant_dict.get('api_callback', '')
                    assistants_list.append(assistant_dict)
                
                logging.info(f"Retrieved {len(assistants_list)} assistants for organization {organization_id}")
                return assistants_list
                
        except sqlite3.Error as e:
            logging.error(f"Error getting assistants for organization {organization_id}: {e}")
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
                        logging.warning(
                            f"Assistant {assistant_id} not found or doesn't belong to {owner}")
                        return False

                # If the assistant exists and belongs to the owner, proceed with deletion
                with connection:
                    cursor = connection.cursor()
                    # Deletion will cascade to assistant_publish due to FOREIGN KEY ON DELETE CASCADE
                    cursor.execute(f"DELETE FROM {self.table_prefix}assistants WHERE id = ? AND owner = ?",
                                   (assistant_id, owner))
                    logging.info(
                        f"Assistant {assistant_id} deleted successfully")
                    return True
            except sqlite3.Error as e:
                logging.error(f"Error deleting assistant: {e}")
                return False
            finally:
                if connection:
                    connection.close()
                    logging.debug("Database connection closed")
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
                logging.error(
                    f"Database error when fetching LTI users by assistant_id: {e}")
                raise e
            finally:
                connection.close()
        return []

    def publish_assistant(self, assistant_id: int, assistant_name: str, assistant_owner: str,
                          group_id: str, group_name: str, oauth_consumer_name: Optional[str]) -> bool: # Allow None for oauth_consumer_name
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
                    logging.info(
                        f"Assistant {assistant_id} publication created/updated successfully")
                    return True
            except sqlite3.Error as e:
                # Specifically catch integrity errors for unique constraint violation
                if "UNIQUE constraint failed" in str(e) and "oauth_consumer_name" in str(e):
                     logging.error(f"Error publishing assistant {assistant_id}: OAuth Consumer Name '{oauth_consumer_name}' is already in use.")
                     # Re-raise or return specific error? For now, just log and return False
                     return False
                logging.error(f"Error publishing assistant {assistant_id}: {e}")
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
                logging.error(f"Error getting published assistants: {e}")
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
                        logging.info(f"Unpublished assistant {assistant_id}")
                    else:
                        logging.warning(f"Attempted to unpublish assistant {assistant_id}, but no publication record was found.")
                    # Return True if a record was deleted, False otherwise
                    return deleted_count > 0
            except sqlite3.Error as e:
                logging.error(f"Error unpublishing assistant {assistant_id}: {e}")
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
                logging.error(f"Error getting published assistant: {e}")
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
            logging.error("Could not establish database connection")
            return None

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT u.id, u.user_email, u.user_name, u.user_config, u.organization_id,
                           o.name as org_name, o.slug as org_slug, o.is_system,
                           COALESCE(r.role, 'member') as org_role
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
                        'organization_role': row[8]
                    })
                return users

        except sqlite3.Error as e:
            logging.error(f"Database error in get_creator_users: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in get_creator_users: {e}")
            return None
        finally:
            connection.close()
            logging.debug("Database connection closed")

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
                logging.error(f"Error updating assistant: {e}")
                return False
            finally:
                connection.close()
                logging.debug("Database connection closed")
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
                logging.error(
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
            logging.error(f"Error getting publication for assistant {assistant_id}: {e}")
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
            logging.error("Invalid JWT token")
            return None
        except Exception as e:
            logging.error(f"Error verifying token: {e}")
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
            logging.error(f"Error getting collections by owner: {str(e)}")
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
            logging.error(f"Error getting collection by ID: {str(e)}")
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
            logging.error(
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
                logging.error("Could not establish database connection")
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
            logging.error(f"Database error in delete_collection: {e}")
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
            logging.error(f"Error getting config: {e}")
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
            logging.error(f"Error updating config: {e}")
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
