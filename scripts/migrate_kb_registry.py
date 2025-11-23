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
"""

import os
import sys
import sqlite3
import argparse
import logging
from typing import List, Dict, Optional, Set
from dotenv import load_dotenv
import httpx
import asyncio
import time

# Load environment BEFORE importing LAMB modules
load_dotenv()

# Try to load from parent directory if not found
if not os.getenv('LAMB_DB_PATH'):
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(parent_dir, '.env'))

# Set minimal required env vars if not set
if not os.getenv('LAMB_BACKEND_HOST'):
    os.environ['LAMB_BACKEND_HOST'] = 'http://localhost:9099'
if not os.getenv('LAMB_BEARER_TOKEN'):
    os.environ['LAMB_BEARER_TOKEN'] = '0p3n-w3bu!'

# Add backend directory to path to import LAMB modules
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(os.path.dirname(script_dir), 'backend')
sys.path.insert(0, backend_dir)

from lamb.database_manager import LambDatabaseManager


class KBRegistryMigration:
    def __init__(self, dry_run: bool = False, verbose: bool = False, db_file: Optional[str] = None):
        self.dry_run = dry_run
        self.verbose = verbose
        self.db_file = db_file
        self.setup_logging()
        
        # Override database file if specified
        if db_file:
            db_path_dir = os.getenv('LAMB_DB_PATH', '.')
            full_db_path = os.path.join(db_path_dir, db_file) if not os.path.isabs(db_file) else db_file
            
            if not os.path.exists(full_db_path):
                raise FileNotFoundError(f"Database file not found: {full_db_path}")
            
            self.logger.info(f"Using database: {full_db_path}")
            # Override the db_path by setting it in the manager after creation
            self.db_manager = LambDatabaseManager()
            self.db_manager.db_path = full_db_path
        else:
            # Initialize database manager normally
            self.db_manager = LambDatabaseManager()
        
        # Get KB Server config
        self.kb_server_url = os.getenv('LAMB_KB_SERVER', '').rstrip('/')
        self.kb_server_token = os.getenv('LAMB_KB_SERVER_TOKEN', '')
        
        if not self.kb_server_url:
            raise ValueError("LAMB_KB_SERVER environment variable is required")
        
        # Statistics
        self.stats = {
            'assistants_scanned': 0,
            'assistants_with_kbs': 0,
            'unique_kb_ids': set(),
            'kbs_registered': 0,
            'kbs_already_registered': 0,
            'kbs_not_found': 0,
            'errors': 0
        }
    
    def setup_logging(self):
        """Configure logging"""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
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


async def main():
    parser = argparse.ArgumentParser(
        description='Migrate KB references to kb_registry table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be done
  python scripts/migrate_kb_registry.py --dry-run

  # Run migration with verbose logging
  python scripts/migrate_kb_registry.py --verbose

  # Use specific database file
  python scripts/migrate_kb_registry.py --db lamb_v4_prod.db --dry-run

  # Run actual migration
  python scripts/migrate_kb_registry.py
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--db', type=str,
                       help='Database file to use (relative to LAMB_DB_PATH or absolute path)')
    
    args = parser.parse_args()
    
    try:
        migration = KBRegistryMigration(
            dry_run=args.dry_run, 
            verbose=args.verbose,
            db_file=args.db
        )
        await migration.run()
        
        # Exit with error code if there were errors
        if migration.stats['errors'] > 0:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
