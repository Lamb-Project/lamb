#!/usr/bin/env python3
"""
KB Registry Migration Script for v0.2

This script populates the LAMB_kb_registry table with existing KB references
from assistants' RAG_collections field. It queries the KB Server to get
KB metadata and creates registry entries.

Usage:
    python scripts/migrate_kb_registry.py [--dry-run] [--verbose]

Options:
    --dry-run    Show what would be done without making changes
    --verbose    Show detailed logging
    --check-env  Check environment setup and exit
"""

import os
import sys
import sqlite3
import argparse
from typing import List, Dict, Optional, Set

# Print to stdout immediately for debugging Docker issues
print("KB Registry Migration Script - Starting...", flush=True)

# Load environment BEFORE importing LAMB modules
try:
    from dotenv import load_dotenv
    import httpx
    import asyncio
    import time
    from lamb.logging_config import get_logger
    
    load_dotenv()
    
    logger = get_logger(__name__, component="MAIN")
    
    # Try to load from parent directory if not found
    if not os.getenv('LAMB_DB_PATH'):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file = os.path.join(parent_dir, 'backend', '.env')
        if os.path.exists(env_file):
            print(f"Loading environment from: {env_file}", flush=True)
            load_dotenv(env_file)
        else:
            print(f"Warning: .env file not found at {env_file}", flush=True)
    
    # Set minimal required env vars if not set
    # These are needed by config.py which gets imported by database_manager
    if not os.getenv('LAMB_BACKEND_HOST'):
        os.environ['LAMB_BACKEND_HOST'] = 'http://localhost:9099'
    if not os.getenv('LAMB_BEARER_TOKEN'):
        os.environ['LAMB_BEARER_TOKEN'] = '0p3n-w3bu!'
    if not os.getenv('LAMB_WEB_HOST'):
        os.environ['LAMB_WEB_HOST'] = 'http://localhost:9099'
    if not os.getenv('OLLAMA_BASE_URL'):
        os.environ['OLLAMA_BASE_URL'] = 'http://localhost:11434'
    if not os.getenv('OLLAMA_MODEL'):
        os.environ['OLLAMA_MODEL'] = 'llama2'
    if not os.getenv('OPENAI_BASE_URL'):
        os.environ['OPENAI_BASE_URL'] = 'http://localhost:11434/v1'
    if not os.getenv('OPENAI_MODEL'):
        os.environ['OPENAI_MODEL'] = 'llama2'
    
    print("Environment variables loaded", flush=True)
    
except Exception as e:
    print(f"FATAL ERROR during initialization: {str(e)}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Add backend directory to path to import LAMB modules
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(os.path.dirname(script_dir), 'backend')
sys.path.insert(0, backend_dir)

print(f"Python path includes: {backend_dir}", flush=True)

# Import LAMB modules with error handling
try:
    from lamb.database_manager import LambDatabaseManager
    print("Successfully imported LambDatabaseManager", flush=True)
except Exception as e:
    print(f"FATAL ERROR importing LambDatabaseManager: {str(e)}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)


class KBRegistryMigration:
    def __init__(self, dry_run: bool = False, verbose: bool = False, db_file: Optional[str] = None):
        self.dry_run = dry_run
        self.verbose = verbose
        self.db_file = db_file
        self.setup_logging()
        
        print("Initializing database manager...", flush=True)
        
        # Override database file if specified
        if db_file:
            db_path_dir = os.getenv('LAMB_DB_PATH', '.')
            full_db_path = os.path.join(db_path_dir, db_file) if not os.path.isabs(db_file) else db_file
            
            if not os.path.exists(full_db_path):
                error_msg = f"Database file not found: {full_db_path}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            self.logger.info(f"Using database: {full_db_path}")
            # Override the db_path by setting it in the manager after creation
            try:
                self.db_manager = LambDatabaseManager()
                self.db_manager.db_path = full_db_path
            except Exception as e:
                error_msg = f"Failed to initialize database manager: {str(e)}"
                self.logger.error(error_msg)
                raise
        else:
            # Initialize database manager normally
            try:
                self.db_manager = LambDatabaseManager()
                self.logger.info(f"Using database from LAMB_DB_PATH: {os.getenv('LAMB_DB_PATH')}")
            except Exception as e:
                error_msg = f"Failed to initialize database manager: {str(e)}"
                self.logger.error(error_msg)
                print(error_msg, file=sys.stderr, flush=True)
                raise
        
        # Get KB Server config
        self.kb_server_url = os.getenv('LAMB_KB_SERVER', '').rstrip('/')
        self.kb_server_token = os.getenv('LAMB_KB_SERVER_TOKEN', '')
        
        if not self.kb_server_url:
            error_msg = "LAMB_KB_SERVER environment variable is required"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not self.kb_server_token:
            self.logger.warning("LAMB_KB_SERVER_TOKEN not set - KB Server requests may fail")
        
        self.logger.info(f"KB Server configured: {self.kb_server_url}")
        
        # Statistics
        self.stats = {
            'assistants_scanned': 0,
            'assistants_with_kbs': 0,
            'assistants_deleted': 0,
            'unique_kb_ids': set(),
            'kbs_registered': 0,
            'kbs_already_registered': 0,
            'kbs_not_found': 0,
            'errors': 0
        }
    
    def setup_logging(self):
        """Configure logging"""
        level = logging.DEBUG if self.verbose else logging.INFO
        
        # Configure logging to output to stdout explicitly
        # This ensures output is visible in Docker exec
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            stream=sys.stdout,
            force=True  # Override any existing configuration
        )
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)
    
    async def fetch_kb_from_server(self, kb_id: str) -> Optional[Dict]:
        """Fetch KB details from KB Server"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.kb_server_url}/collections/{kb_id}",
                    headers={"Authorization": f"Bearer {self.kb_server_token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    self.logger.warning(f"KB {kb_id} not found in KB Server (404)")
                    return None
                else:
                    self.logger.error(f"KB Server returned status {response.status_code} for KB {kb_id}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error fetching KB {kb_id} from server: {str(e)}")
            return None
    
    def get_all_assistants(self) -> List[Dict]:
        """Get all assistants from database"""
        connection = self.db_manager.get_connection()
        if not connection:
            raise Exception("Failed to connect to database")
        
        try:
            cursor = connection.cursor()
            table_name = self.db_manager._get_table_name('assistants')
            
            query = f"""
                SELECT id, name, owner, RAG_collections, organization_id
                FROM {table_name}
                WHERE RAG_collections IS NOT NULL 
                  AND RAG_collections != ''
            """
            
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            
            assistants = []
            for row in cursor.fetchall():
                assistants.append(dict(zip(columns, row)))
            
            return assistants
            
        finally:
            connection.close()
    
    def get_user_id_by_email(self, email: str) -> Optional[int]:
        """Get user ID from email"""
        connection = self.db_manager.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            table_name = self.db_manager._get_table_name('Creator_users')
            
            cursor.execute(f"SELECT id FROM {table_name} WHERE user_email = ?", (email,))
            result = cursor.fetchone()
            
            return result[0] if result else None
            
        finally:
            connection.close()
    
    def extract_kb_ids(self, rag_collections: str) -> List[str]:
        """Extract KB IDs from RAG_collections string"""
        if not rag_collections:
            return []
        
        # Split by comma and clean up
        kb_ids = [kb_id.strip() for kb_id in rag_collections.split(',') if kb_id.strip()]
        return kb_ids
    
    async def process_assistant(self, assistant: Dict) -> None:
        """Process a single assistant and register its KBs"""
        self.stats['assistants_scanned'] += 1
        
        kb_ids = self.extract_kb_ids(assistant.get('RAG_collections', ''))
        if not kb_ids:
            return
        
        self.stats['assistants_with_kbs'] += 1
        self.logger.info(f"Processing assistant {assistant['id']} '{assistant['name']}' with {len(kb_ids)} KB(s)")
        
        # Get owner user ID
        owner_email = assistant.get('owner')
        
        # Check for deleted assistants (special marker email)
        if owner_email == 'deleted_assistant@owi.com':
            self.logger.info(f"  Skipping deleted assistant {assistant['id']}")
            self.stats['assistants_deleted'] += 1
            return
        
        owner_user_id = self.get_user_id_by_email(owner_email) if owner_email else None
        
        if not owner_user_id:
            self.logger.warning(f"  Could not find user ID for owner '{owner_email}', skipping assistant {assistant['id']}")
            self.stats['errors'] += 1
            return
        
        org_id = assistant.get('organization_id')
        if not org_id:
            self.logger.warning(f"  Assistant {assistant['id']} has no organization_id, skipping")
            self.stats['errors'] += 1
            return
        
        # Process each KB
        for kb_id in kb_ids:
            await self.process_kb(kb_id, owner_user_id, org_id, assistant['id'], assistant['name'])
    
    async def process_kb(self, kb_id: str, owner_user_id: int, org_id: int, 
                        assistant_id: int, assistant_name: str) -> None:
        """Process a single KB and register it if needed"""
        self.stats['unique_kb_ids'].add(kb_id)
        
        # Check if already registered
        existing = self.db_manager.get_kb_registry_entry(kb_id)
        if existing:
            self.logger.debug(f"  KB {kb_id} already registered ('{existing.get('kb_name')}')")
            self.stats['kbs_already_registered'] += 1
            return
        
        # Fetch KB from server
        self.logger.info(f"  Fetching KB {kb_id} from KB Server...")
        kb_data = await self.fetch_kb_from_server(kb_id)
        
        if not kb_data:
            self.logger.warning(f"  KB {kb_id} not found in KB Server, cannot register")
            self.stats['kbs_not_found'] += 1
            return
        
        kb_name = kb_data.get('name', kb_id)
        created_at = None
        
        # Try to parse creation date from KB server
        if 'creation_date' in kb_data:
            try:
                from datetime import datetime
                if isinstance(kb_data['creation_date'], str):
                    dt = datetime.fromisoformat(kb_data['creation_date'].replace('Z', '+00:00'))
                    created_at = int(dt.timestamp())
                elif isinstance(kb_data['creation_date'], (int, float)):
                    created_at = int(kb_data['creation_date'])
            except Exception as e:
                self.logger.debug(f"  Could not parse creation_date: {e}")
        
        if self.dry_run:
            self.logger.info(f"  [DRY RUN] Would register KB {kb_id} ('{kb_name}') for user {owner_user_id}, org {org_id}")
            self.stats['kbs_registered'] += 1
        else:
            try:
                # Register the KB
                self.db_manager.register_kb(
                    kb_id=kb_id,
                    kb_name=kb_name,
                    owner_user_id=owner_user_id,
                    organization_id=org_id,
                    is_shared=False,  # Default to not shared, can be updated later
                    metadata={'migrated_from_assistant': assistant_id}
                )
                
                # Update created_at if we have it
                if created_at:
                    self.db_manager.update_kb_registry_created_at(kb_id, created_at)
                
                self.logger.info(f"  ✓ Registered KB {kb_id} ('{kb_name}')")
                self.stats['kbs_registered'] += 1
                
            except Exception as e:
                self.logger.error(f"  ✗ Error registering KB {kb_id}: {str(e)}")
                self.stats['errors'] += 1
    
    async def run(self) -> None:
        """Run the migration"""
        self.logger.info("=" * 70)
        self.logger.info("KB Registry Migration Script")
        self.logger.info("=" * 70)
        
        if self.dry_run:
            self.logger.info("*** DRY RUN MODE - No changes will be made ***")
        
        self.logger.info(f"KB Server: {self.kb_server_url}")
        self.logger.info("")
        
        # Get all assistants with KBs
        self.logger.info("Fetching assistants with KB references...")
        assistants = self.get_all_assistants()
        self.logger.info(f"Found {len(assistants)} assistant(s) with KB references")
        self.logger.info("")
        
        if not assistants:
            self.logger.info("No assistants with KBs found. Nothing to migrate.")
            return
        
        # Process each assistant
        self.logger.info("Processing assistants...")
        for assistant in assistants:
            await self.process_assistant(assistant)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print migration summary"""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("Migration Summary")
        self.logger.info("=" * 70)
        self.logger.info(f"Assistants scanned:       {self.stats['assistants_scanned']}")
        self.logger.info(f"Assistants with KBs:      {self.stats['assistants_with_kbs']}")
        if self.stats['assistants_deleted'] > 0:
            self.logger.info(f"Assistants deleted:       {self.stats['assistants_deleted']} (skipped)")
        self.logger.info(f"Unique KB IDs found:      {len(self.stats['unique_kb_ids'])}")
        self.logger.info(f"KBs registered:           {self.stats['kbs_registered']}")
        self.logger.info(f"KBs already registered:   {self.stats['kbs_already_registered']}")
        self.logger.info(f"KBs not found in server:  {self.stats['kbs_not_found']}")
        self.logger.info(f"Errors:                   {self.stats['errors']}")
        self.logger.info("=" * 70)
        
        if self.dry_run:
            self.logger.info("")
            self.logger.info("This was a DRY RUN. Run without --dry-run to apply changes.")
        elif self.stats['kbs_registered'] > 0:
            self.logger.info("")
            self.logger.info(f"✓ Successfully registered {self.stats['kbs_registered']} KB(s)")
        
        if self.stats['kbs_not_found'] > 0:
            self.logger.warning("")
            self.logger.warning(f"⚠ {self.stats['kbs_not_found']} KB(s) were referenced but not found in KB Server")
            self.logger.warning("  These may have been deleted. Consider cleaning up assistant references.")
        
        if self.stats['errors'] > 0:
            self.logger.error("")
            self.logger.error(f"✗ {self.stats['errors']} error(s) occurred during migration")


def check_environment():
    """Check and display environment configuration"""
    print("\n" + "=" * 70)
    print("Environment Check")
    print("=" * 70)
    
    # Check critical environment variables
    critical_vars = {
        'LAMB_DB_PATH': 'Database directory path',
        'LAMB_KB_SERVER': 'KB Server URL',
        'LAMB_KB_SERVER_TOKEN': 'KB Server authentication token',
    }
    
    optional_vars = {
        'LAMB_BACKEND_HOST': 'Backend host URL',
        'LAMB_WEB_HOST': 'Web host URL',
        'LAMB_BEARER_TOKEN': 'Bearer token',
    }
    
    all_good = True
    
    print("\nCritical Variables:")
    for var, description in critical_vars.items():
        value = os.getenv(var)
        if value:
            # Mask tokens for security
            if 'TOKEN' in var or 'KEY' in var:
                display_value = value[:8] + '...' if len(value) > 8 else '***'
            else:
                display_value = value
            print(f"  ✓ {var}: {display_value}")
        else:
            print(f"  ✗ {var}: NOT SET - {description}")
            all_good = False
    
    print("\nOptional Variables (with defaults):")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            if 'TOKEN' in var or 'KEY' in var:
                display_value = value[:8] + '...' if len(value) > 8 else '***'
            else:
                display_value = value
            print(f"  ✓ {var}: {display_value}")
        else:
            print(f"  ℹ {var}: using default")
    
    # Check database file
    print("\nDatabase Check:")
    db_path = os.getenv('LAMB_DB_PATH')
    if db_path:
        db_file = os.path.join(db_path, 'lamb_v4.db')
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            print(f"  ✓ Database file exists: {db_file} ({size} bytes)")
        else:
            print(f"  ✗ Database file not found: {db_file}")
            all_good = False
    else:
        print(f"  ✗ LAMB_DB_PATH not set, cannot check database")
        all_good = False
    
    # Check KB Server connectivity
    print("\nKB Server Connectivity:")
    kb_server = os.getenv('LAMB_KB_SERVER')
    kb_token = os.getenv('LAMB_KB_SERVER_TOKEN')
    if kb_server and kb_token:
        try:
            import httpx
            response = httpx.get(
                f"{kb_server.rstrip('/')}/health",
                headers={"Authorization": f"Bearer {kb_token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                print(f"  ✓ KB Server reachable: {kb_server}")
            else:
                print(f"  ⚠ KB Server responded with status {response.status_code}")
        except Exception as e:
            print(f"  ✗ Cannot reach KB Server: {str(e)}")
            all_good = False
    else:
        print(f"  ✗ KB Server URL or token not set")
        all_good = False
    
    print("\n" + "=" * 70)
    if all_good:
        print("✓ Environment check passed - ready to run migration")
        return 0
    else:
        print("✗ Environment check failed - please fix the issues above")
        return 1


async def main():
    parser = argparse.ArgumentParser(
        description='Migrate KB references to kb_registry table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check environment setup
  python scripts/migrate_kb_registry.py --check-env

  # Dry run to see what would be done
  python scripts/migrate_kb_registry.py --dry-run

  # Run migration with verbose logging
  python scripts/migrate_kb_registry.py --verbose

  # Use specific database file
  python scripts/migrate_kb_registry.py --db lamb_v4_prod.db --dry-run

  # Run actual migration
  python scripts/migrate_kb_registry.py

  # Docker execution
  docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --check-env
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--db', type=str,
                       help='Database file to use (relative to LAMB_DB_PATH or absolute path)')
    parser.add_argument('--check-env', action='store_true',
                       help='Check environment configuration and exit')
    
    args = parser.parse_args()
    
    # Handle --check-env flag
    if args.check_env:
        sys.exit(check_environment())
    
    try:
        print("Initializing migration...", flush=True)
        migration = KBRegistryMigration(
            dry_run=args.dry_run, 
            verbose=args.verbose,
            db_file=args.db
        )
        print("Starting migration run...", flush=True)
        await migration.run()
        
        # Exit with error code if there were errors
        if migration.stats['errors'] > 0:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nFATAL ERROR in main: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
