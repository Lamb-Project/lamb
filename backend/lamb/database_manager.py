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

                # Migration 2: Create rubrics table if it doesn't exist
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}rubrics'")
                rubrics_table_exists = cursor.fetchone()

                if not rubrics_table_exists:
                    logging.info("Creating rubrics table")
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
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_owner ON {self.table_prefix}rubrics(owner_email)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_org ON {self.table_prefix}rubrics(organization_id)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_rubric_id ON {self.table_prefix}rubrics(rubric_id)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_public ON {self.table_prefix}rubrics(is_public)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rubrics_showcase ON {self.table_prefix}rubrics(is_showcase)")

                    logging.info("Successfully created rubrics table and indexes")
                else:
                    logging.debug("rubrics table already exists")

                # Migration 3: Create prompt_templates table if it doesn't exist
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}prompt_templates'")
                prompt_templates_table_exists = cursor.fetchone()

                if not prompt_templates_table_exists:
                    logging.info("Creating prompt_templates table")
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
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_org_shared ON {self.table_prefix}prompt_templates(organization_id, is_shared)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_owner ON {self.table_prefix}prompt_templates(owner_email)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}prompt_templates_name ON {self.table_prefix}prompt_templates(name)")

                    logging.info("Successfully created prompt_templates table and indexes")
                else:
                    logging.debug("prompt_templates table already exists")

                # Migration 4: Add enabled column to Creator_users if it doesn't exist
                cursor.execute(f"PRAGMA table_info({self.table_prefix}Creator_users)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'enabled' not in columns:
                    logging.info("Adding enabled column to Creator_users table")
                    cursor.execute(f"""
                        ALTER TABLE {self.table_prefix}Creator_users 
                        ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1
                    """)
                    # Create index for performance
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}creator_users_enabled ON {self.table_prefix}Creator_users(enabled)")
                    logging.info("Successfully added enabled column and index")
                else:
                    logging.debug("enabled column already exists in Creator_users table")

                # Migration 5: Create kb_registry table if it doesn't exist
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_prefix}kb_registry'")
                kb_registry_table_exists = cursor.fetchone()

                if not kb_registry_table_exists:
                    logging.info("Creating kb_registry table")
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
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_owner ON {self.table_prefix}kb_registry(owner_user_id)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_org_shared ON {self.table_prefix}kb_registry(organization_id, is_shared)")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}kb_registry_kb_id ON {self.table_prefix}kb_registry(kb_id)")

                    logging.info("Successfully created kb_registry table and indexes")
                else:
                    logging.debug("kb_registry table already exists")

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
                    logging.error("Cannot delete system organization")
                    return False
                
                # Delete organization (cascade will handle related records)
                cursor.execute(f"""
                    DELETE FROM {self.table_prefix}organizations WHERE id = ?
                """, (org_id,))
                
                return cursor.rowcount > 0
                
        except sqlite3.Error as e:
            logging.error(f"Error deleting organization: {e}")
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
            logging.error(f"Error validating migration: {e}")
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
                logging.info(f"Migrated {migrated} users from org {source_org_id} to {target_org_id}")
                return migrated
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating users: {e}")
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
                
                logging.info(f"Migrated {migrated} roles from org {source_org_id} to {target_org_id} (preserve_admin={preserve_admin_roles})")
                return migrated
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating roles: {e}")
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
                            logging.warning(f"Skipping assistant {name} (conflict detected)")
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(f"Conflict detected for assistant '{name}' owned by '{owner}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}assistants
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, assistant_id))
                            renamed.append({"id": assistant_id, "old_name": name, "new_name": new_name, "owner": owner})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}assistants
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, assistant_id))
                    
                    migrated += 1
                
                logging.info(f"Migrated {migrated} assistants from org {source_org_id} to {target_org_id} ({len(renamed)} renamed)")
                return {"count": migrated, "renamed": renamed}
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating assistants: {e}")
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
                            logging.warning(f"Skipping template {name} (conflict detected)")
                            continue
                        elif conflict_strategy == "fail":
                            raise ValueError(f"Conflict detected for template '{name}' owned by '{owner_email}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}prompt_templates
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, template_id))
                            renamed.append({"id": template_id, "old_name": name, "new_name": new_name, "owner_email": owner_email})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}prompt_templates
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, template_id))
                    
                    migrated += 1
                
                logging.info(f"Migrated {migrated} templates from org {source_org_id} to {target_org_id} ({len(renamed)} renamed)")
                return {"count": migrated, "renamed": renamed}
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating templates: {e}")
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
                logging.info(f"Migrated {migrated} KB registry entries from org {source_org_id} to {target_org_id}")
                return migrated
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating KB registry: {e}")
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
                logging.info(f"Migrated {migrated} usage logs from org {source_org_id} to {target_org_id}")
                return migrated
                
        except sqlite3.Error as e:
            logging.error(f"Error migrating usage logs: {e}")
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
                logging.info(f"Migrated {users_migrated} users")
                
                # 2. Migrate roles
                cursor.execute(f"""
                    SELECT user_id, role FROM {self.table_prefix}organization_roles
                    WHERE organization_id = ?
                """, (source_org_id,))
                roles = cursor.fetchall()
                roles_migrated = 0
                for user_id, role in roles:
                    target_role = role if preserve_admin_roles else ('member' if role in ['admin', 'owner'] else role)
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {self.table_prefix}organization_roles
                        (organization_id, user_id, role, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (target_org_id, user_id, target_role, now, now))
                    roles_migrated += 1
                migration_report["resources_migrated"]["roles"] = roles_migrated
                logging.info(f"Migrated {roles_migrated} roles")
                
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
                            raise ValueError(f"Conflict detected for assistant '{name}' owned by '{owner}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}assistants
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, assistant_id))
                            assistants_renamed.append({"id": assistant_id, "old_name": name, "new_name": new_name, "owner": owner})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}assistants
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, assistant_id))
                    assistants_migrated += 1
                migration_report["resources_migrated"]["assistants"] = assistants_migrated
                migration_report["conflicts_resolved"]["assistants_renamed"] = len(assistants_renamed)
                logging.info(f"Migrated {assistants_migrated} assistants ({len(assistants_renamed)} renamed)")
                
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
                            raise ValueError(f"Conflict detected for template '{name}' owned by '{owner_email}'")
                        else:  # rename
                            new_name = f"{source_org_slug}_{name}"
                            cursor.execute(f"""
                                UPDATE {self.table_prefix}prompt_templates
                                SET organization_id = ?, name = ?, updated_at = ?
                                WHERE id = ?
                            """, (target_org_id, new_name, now, template_id))
                            templates_renamed.append({"id": template_id, "old_name": name, "new_name": new_name, "owner_email": owner_email})
                    else:
                        cursor.execute(f"""
                            UPDATE {self.table_prefix}prompt_templates
                            SET organization_id = ?, updated_at = ?
                            WHERE id = ?
                        """, (target_org_id, now, template_id))
                    templates_migrated += 1
                migration_report["resources_migrated"]["templates"] = templates_migrated
                migration_report["conflicts_resolved"]["templates_renamed"] = len(templates_renamed)
                logging.info(f"Migrated {templates_migrated} templates ({len(templates_renamed)} renamed)")
                
                # 5. Migrate KB registry
                cursor.execute(f"""
                    UPDATE {self.table_prefix}kb_registry
                    SET organization_id = ?, updated_at = ?
                    WHERE organization_id = ?
                """, (target_org_id, now, source_org_id))
                kbs_migrated = cursor.rowcount
                migration_report["resources_migrated"]["kbs"] = kbs_migrated
                logging.info(f"Migrated {kbs_migrated} KB registry entries")
                
                # 6. Migrate usage logs
                cursor.execute(f"""
                    UPDATE {self.table_prefix}usage_logs
                    SET organization_id = ?
                    WHERE organization_id = ?
                """, (target_org_id, source_org_id))
                logs_migrated = cursor.rowcount
                migration_report["resources_migrated"]["usage_logs"] = logs_migrated
                logging.info(f"Migrated {logs_migrated} usage logs")
                
                # All migrations successful
                migration_report["success"] = True
                logging.info(f"Successfully migrated organization {source_org_id} to {target_org_id}")
                
                return migration_report
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error during migration: {error_msg}")
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
                    SELECT id, organization_id, user_email, user_name, user_type, user_config, enabled 
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
                    'enabled': bool(result[6]) if len(result) > 6 else True
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
            logging.error("Failed to get database connection")
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
                    logging.warning(f"User {user_id} not found")
                    return False
                
                if row[0] == 0:  # Already disabled
                    logging.info(f"User {user_id} already disabled")
                    return False
                
                # Disable user
                cursor.execute(
                    f"""UPDATE {self.table_prefix}Creator_users 
                        SET enabled = 0, updated_at = ? 
                        WHERE id = ?""",
                    (int(time.time()), user_id)
                )
                logging.info(f"Successfully disabled user {user_id}")
                return True
                
        except Exception as e:
            logging.error(f"Error disabling user {user_id}: {e}")
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
            logging.error("Failed to get database connection")
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
                    logging.warning(f"User {user_id} not found")
                    return False
                
                if row[0] == 1:  # Already enabled
                    logging.info(f"User {user_id} already enabled")
                    return False
                
                # Enable user
                cursor.execute(
                    f"""UPDATE {self.table_prefix}Creator_users 
                        SET enabled = 1, updated_at = ? 
                        WHERE id = ?""",
                    (int(time.time()), user_id)
                )
                logging.info(f"Successfully enabled user {user_id}")
                return True
                
        except Exception as e:
            logging.error(f"Error enabling user {user_id}: {e}")
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
            logging.error("Failed to get database connection")
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
            logging.error(f"Error checking user enabled status: {e}")
            return False
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
            logging.error("Failed to get database connection")
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
                        logging.error(f"Error disabling user {user_id}: {e}")
                        results["failed"].append(user_id)
                
                logging.info(f"Bulk disable: {len(results['success'])} successful, {len(results['failed'])} failed")
                
        except Exception as e:
            logging.error(f"Error in bulk disable: {e}")
            # Mark all as failed
            results["failed"].extend([uid for uid in user_ids if uid not in results["success"] and uid not in results["already_disabled"] and uid not in results["failed"]])
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
            logging.error("Failed to get database connection")
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
                        logging.error(f"Error enabling user {user_id}: {e}")
                        results["failed"].append(user_id)
                
                logging.info(f"Bulk enable: {len(results['success'])} successful, {len(results['failed'])} failed")
                
        except Exception as e:
            logging.error(f"Error in bulk enable: {e}")
            # Mark all as failed
            results["failed"].extend([uid for uid in user_ids if uid not in results["success"] and uid not in results["already_enabled"] and uid not in results["failed"]])
        finally:
            if connection:
                connection.close()
        
        return results

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
                           COALESCE(r.role, 'member') as org_role, u.user_type, u.enabled
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
                        'enabled': bool(row[10]) if len(row) > 10 else True
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
            logging.error("Could not establish database connection")
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
                logging.info(f"Created prompt template '{template_data['name']}' with id: {template_id}")
                return template_id
                
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity error creating prompt template: {e}")
            return None
        except sqlite3.Error as e:
            logging.error(f"Database error creating prompt template: {e}")
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
            logging.error(f"Database error getting prompt template: {e}")
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
            logging.error(f"Database error getting user prompt templates: {e}")
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
            logging.error(f"Database error getting shared templates: {e}")
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
                    logging.warning(f"User {owner_email} attempted to update template {template_id} without ownership")
                    return False
                
                # Build update query
                allowed_fields = ['name', 'description', 'system_prompt', 'prompt_template', 'is_shared', 'metadata']
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
                    logging.warning("No valid fields to update")
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
                
                logging.info(f"Updated prompt template {template_id}")
                return cursor.rowcount > 0
                
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity error updating prompt template: {e}")
            return False
        except sqlite3.Error as e:
            logging.error(f"Database error updating prompt template: {e}")
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
                    logging.info(f"Deleted prompt template {template_id}")
                else:
                    logging.warning(f"User {owner_email} attempted to delete template {template_id} without ownership")
                
                return success
                
        except sqlite3.Error as e:
            logging.error(f"Database error deleting prompt template: {e}")
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
                    logging.error(f"Template {template_id} not found for duplication")
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
                logging.info(f"Duplicated template {template_id} to new template {new_id}")
                return new_id
                
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity error duplicating template (likely duplicate name): {e}")
            return None
        except sqlite3.Error as e:
            logging.error(f"Database error duplicating template: {e}")
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
            logging.error("Could not establish database connection")
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
                logging.info(f"Registered KB '{kb_name}' (ID: {kb_id}) in registry with id: {registry_id}")
                return registry_id
                
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity error registering KB: {e}")
            return None
        except sqlite3.Error as e:
            logging.error(f"Database error registering KB: {e}")
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
            logging.error(f"Database error getting KB registry entry: {e}")
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
                        result_dict['is_shared'] = bool(result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)
                
                return results
                
        except sqlite3.Error as e:
            logging.error(f"Database error getting owned KBs: {e}")
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
                        result_dict['is_shared'] = bool(result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)
                
                return results
                
        except sqlite3.Error as e:
            logging.error(f"Database error getting shared KBs: {e}")
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
                        result_dict['is_shared'] = bool(result_dict['is_shared'])
                    # Parse metadata JSON
                    if result_dict.get('metadata') and isinstance(result_dict['metadata'], str):
                        try:
                            result_dict['metadata'] = json.loads(result_dict['metadata'])
                        except:
                            result_dict['metadata'] = {}
                    results.append(result_dict)
                
                return results
                
        except sqlite3.Error as e:
            logging.error(f"Database error getting accessible KBs: {e}")
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
                cursor.execute(query, (kb_pattern, kb_owner_email, kb_owner_user_id))
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
                        collections = [c.strip() for c in rag_result[0].split(',') if c.strip()]
                        if kb_id in collections:
                            matching_assistants.append({
                                'id': assistant_id,
                                'name': assistant_name,
                                'owner_email': owner_email,
                                'owner_name': owner_name
                            })
                
                return matching_assistants
                
        except sqlite3.Error as e:
            logging.error(f"Database error checking KB usage: {e}")
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
                    logging.info(f"Toggled KB {kb_id} sharing to {is_shared}")
                else:
                    logging.warning(f"KB {kb_id} not found for sharing toggle")
                
                return success
                
        except sqlite3.Error as e:
            logging.error(f"Database error toggling KB sharing: {e}")
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
                    logging.info(f"Updated created_at for KB {kb_id} to {created_at}")
                    return True
                else:
                    logging.warning(f"KB {kb_id} not found in registry for created_at update")
                    return False
                    
        except sqlite3.Error as e:
            logging.error(f"Database error updating KB created_at: {e}")
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
                    logging.info(f"Updated KB {kb_id} name to '{kb_name}'")
                
                return success
                
        except sqlite3.Error as e:
            logging.error(f"Database error updating KB registry name: {e}")
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
                    logging.info(f"Deleted KB registry entry for {kb_id}")
                
                return success
                
        except sqlite3.Error as e:
            logging.error(f"Database error deleting KB registry entry: {e}")
            return False
        finally:
            connection.close()
