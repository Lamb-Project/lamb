"""
Migration Script: Sanitize Assistant and Knowledge Base Names

This script migrates existing Assistant and KB names to conform to the new naming rules:
- Only ASCII letters, numbers, and underscores
- Spaces converted to underscores
- Lowercase
- Max 50 characters

Usage:
    python -m utils.migrate_sanitize_names [--dry-run] [--assistants-only] [--kbs-only]

Options:
    --dry-run: Show what would be changed without making changes
    --assistants-only: Only migrate assistant names
    --kbs-only: Only migrate knowledge base names
    --verbose: Show detailed logging

Important:
    - Backup your database before running this migration
    - This script handles foreign key updates for OWI groups and models
    - Creates a rollback file with original names
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_database import OwiDatabaseManager
from utils.name_sanitizer import sanitize_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NameMigrator:
    """Handles migration of assistant and KB names to sanitized format"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.lamb_db = LambDatabaseManager()
        self.owi_db = OwiDatabaseManager()
        self.changes_log = []
        
    def migrate_assistants(self) -> Tuple[int, int, List[Dict]]:
        """
        Migrate all assistant names to sanitized format.
        
        Returns:
            Tuple of (total_assistants, migrated_count, conflicts)
        """
        logger.info("Starting assistant name migration...")
        
        # Get all assistants
        assistants = self.lamb_db.get_all_assistants()
        total_count = len(assistants)
        migrated_count = 0
        conflicts = []
        
        # Track names by owner to detect duplicates
        names_by_owner = {}
        
        for assistant in assistants:
            assistant_id = assistant['id']
            original_name = assistant['name']
            owner = assistant['owner']
            
            # Extract user ID prefix and base name
            # Format: {user_id}_{base_name}
            parts = original_name.split('_', 1)
            if len(parts) < 2:
                logger.warning(f"Assistant {assistant_id} has invalid name format: {original_name}")
                continue
            
            user_id_str = parts[0]
            base_name = parts[1] if len(parts) > 1 else ""
            
            # Sanitize the base name
            sanitized_base, was_modified = sanitize_name(base_name, max_length=50, to_lowercase=True)
            sanitized_full_name = f"{user_id_str}_{sanitized_base}"
            
            if not was_modified:
                # Name is already sanitized
                logger.debug(f"Assistant {assistant_id} already has sanitized name: {original_name}")
                continue
            
            # Check for conflicts with existing names
            if owner not in names_by_owner:
                names_by_owner[owner] = set()
            
            # Handle duplicate by appending counter
            final_name = sanitized_full_name
            counter = 2
            while final_name in names_by_owner[owner]:
                final_name = f"{user_id_str}_{sanitized_base}_{counter}"
                counter += 1
                if counter > 999:
                    logger.error(f"Too many duplicates for assistant {assistant_id}, skipping")
                    conflicts.append({
                        'id': assistant_id,
                        'original_name': original_name,
                        'reason': 'Too many duplicates'
                    })
                    break
            
            if counter > 2:
                logger.info(f"Resolved duplicate: {sanitized_full_name} → {final_name}")
            
            # Log change
            change = {
                'type': 'assistant',
                'id': assistant_id,
                'original_name': original_name,
                'new_name': final_name,
                'owner': owner
            }
            self.changes_log.append(change)
            names_by_owner[owner].add(final_name)
            
            logger.info(f"  Assistant {assistant_id}: '{original_name}' → '{final_name}'")
            
            if not self.dry_run:
                # Update assistant name in LAMB database
                success = self._update_assistant_name(assistant_id, final_name)
                if success:
                    # Update OWI group name if exists
                    self._update_owi_group_name(assistant, final_name)
                    # Update OWI model name if exists
                    self._update_owi_model_name(assistant, final_name)
                    migrated_count += 1
                else:
                    conflicts.append({
                        'id': assistant_id,
                        'original_name': original_name,
                        'new_name': final_name,
                        'reason': 'Database update failed'
                    })
            else:
                migrated_count += 1
        
        logger.info(f"Assistant migration complete: {migrated_count}/{total_count} assistants migrated")
        return total_count, migrated_count, conflicts
    
    def migrate_knowledge_bases(self) -> Tuple[int, int, List[Dict]]:
        """
        Migrate all KB names to sanitized format.
        
        Returns:
            Tuple of (total_kbs, migrated_count, conflicts)
        """
        logger.info("Starting Knowledge Base name migration...")
        
        # Get all KB registry entries
        kb_entries = self.lamb_db.get_all_kb_registry_entries()
        total_count = len(kb_entries)
        migrated_count = 0
        conflicts = []
        
        # Track names by user+org to detect duplicates
        names_by_user_org = {}
        
        for kb_entry in kb_entries:
            kb_id = kb_entry['kb_id']
            original_name = kb_entry['kb_name']
            owner_user_id = kb_entry['owner_user_id']
            org_id = kb_entry['organization_id']
            
            # Sanitize the name
            sanitized_name, was_modified = sanitize_name(original_name, max_length=50, to_lowercase=True)
            
            if not was_modified:
                # Name is already sanitized
                logger.debug(f"KB {kb_id} already has sanitized name: {original_name}")
                continue
            
            # Check for conflicts
            key = (owner_user_id, org_id)
            if key not in names_by_user_org:
                names_by_user_org[key] = set()
            
            # Handle duplicate
            final_name = sanitized_name
            counter = 2
            while final_name in names_by_user_org[key]:
                final_name = f"{sanitized_name}_{counter}"
                counter += 1
                if counter > 999:
                    logger.error(f"Too many duplicates for KB {kb_id}, skipping")
                    conflicts.append({
                        'id': kb_id,
                        'original_name': original_name,
                        'reason': 'Too many duplicates'
                    })
                    break
            
            if counter > 2:
                logger.info(f"Resolved duplicate: {sanitized_name} → {final_name}")
            
            # Log change
            change = {
                'type': 'knowledge_base',
                'id': kb_id,
                'original_name': original_name,
                'new_name': final_name,
                'owner_user_id': owner_user_id,
                'organization_id': org_id
            }
            self.changes_log.append(change)
            names_by_user_org[key].add(final_name)
            
            logger.info(f"  KB {kb_id}: '{original_name}' → '{final_name}'")
            
            if not self.dry_run:
                # Update KB name in LAMB registry
                success = self._update_kb_name(kb_id, final_name)
                if success:
                    # Note: KB Server names should also be updated, but that requires API calls
                    # For now, just log that manual update may be needed
                    logger.warning(f"  KB {kb_id}: Registry updated, but KB Server may need manual update")
                    migrated_count += 1
                else:
                    conflicts.append({
                        'id': kb_id,
                        'original_name': original_name,
                        'new_name': final_name,
                        'reason': 'Database update failed'
                    })
            else:
                migrated_count += 1
        
        logger.info(f"KB migration complete: {migrated_count}/{total_count} KBs migrated")
        return total_count, migrated_count, conflicts
    
    def _update_assistant_name(self, assistant_id: int, new_name: str) -> bool:
        """Update assistant name in LAMB database"""
        try:
            self.lamb_db.update_assistant_name(assistant_id, new_name)
            return True
        except Exception as e:
            logger.error(f"Failed to update assistant {assistant_id}: {e}")
            return False
    
    def _update_owi_group_name(self, assistant: Dict, new_name: str):
        """Update OWI group name if it exists"""
        group_id = assistant.get('group_id')
        if not group_id:
            return
        
        try:
            # Get group
            conn = self.owi_db.get_DB()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM group WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            
            if row:
                # Update group name to match new assistant name
                new_group_name = f"assistant_{assistant['id']}"
                cursor.execute(
                    "UPDATE group SET name = ?, updated_at = ? WHERE id = ?",
                    (new_group_name, int(datetime.now().timestamp()), group_id)
                )
                conn.commit()
                logger.debug(f"Updated OWI group {group_id} name")
        except Exception as e:
            logger.warning(f"Failed to update OWI group for assistant {assistant['id']}: {e}")
    
    def _update_owi_model_name(self, assistant: Dict, new_name: str):
        """Update OWI model name if it exists"""
        model_id = f"lamb_assistant.{assistant['id']}"
        
        try:
            conn = self.owi_db.get_DB()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM model WHERE id = ?", (model_id,))
            row = cursor.fetchone()
            
            if row:
                # Update model name
                new_model_name = f"LAMB:{new_name}"
                cursor.execute(
                    "UPDATE model SET name = ?, updated_at = ? WHERE id = ?",
                    (new_model_name, int(datetime.now().timestamp()), model_id)
                )
                conn.commit()
                logger.debug(f"Updated OWI model {model_id} name")
        except Exception as e:
            logger.warning(f"Failed to update OWI model for assistant {assistant['id']}: {e}")
    
    def _update_kb_name(self, kb_id: str, new_name: str) -> bool:
        """Update KB name in LAMB registry"""
        try:
            self.lamb_db.update_kb_registry_name(kb_id, new_name)
            return True
        except Exception as e:
            logger.error(f"Failed to update KB {kb_id}: {e}")
            return False
    
    def save_rollback_file(self):
        """Save changes log to a rollback file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"name_migration_rollback_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.changes_log, f, indent=2)
        
        logger.info(f"Rollback file saved: {filename}")
        return filename


def main():
    """Main migration script"""
    parser = argparse.ArgumentParser(description='Migrate Assistant and KB names to sanitized format')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying them')
    parser.add_argument('--assistants-only', action='store_true', help='Only migrate assistants')
    parser.add_argument('--kbs-only', action='store_true', help='Only migrate knowledge bases')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.WARNING)
    
    logger.info("="*70)
    logger.info("LAMB Name Sanitization Migration")
    logger.info("="*70)
    
    if args.dry_run:
        logger.info("DRY RUN MODE: No changes will be applied")
    else:
        logger.warning("LIVE MODE: Database will be modified")
        logger.warning("Please ensure you have backed up your database!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Migration cancelled")
            return
    
    migrator = NameMigrator(dry_run=args.dry_run)
    
    # Migrate assistants
    if not args.kbs_only:
        logger.info("\n" + "-"*70)
        logger.info("Migrating Assistants...")
        logger.info("-"*70)
        total_asst, migrated_asst, conflicts_asst = migrator.migrate_assistants()
        logger.info(f"\nAssistants: {migrated_asst}/{total_asst} migrated")
        if conflicts_asst:
            logger.error(f"  {len(conflicts_asst)} conflicts encountered")
            for conflict in conflicts_asst:
                logger.error(f"    - {conflict['original_name']}: {conflict['reason']}")
    
    # Migrate KBs
    if not args.assistants_only:
        logger.info("\n" + "-"*70)
        logger.info("Migrating Knowledge Bases...")
        logger.info("-"*70)
        total_kb, migrated_kb, conflicts_kb = migrator.migrate_knowledge_bases()
        logger.info(f"\nKnowledge Bases: {migrated_kb}/{total_kb} migrated")
        if conflicts_kb:
            logger.error(f"  {len(conflicts_kb)} conflicts encountered")
            for conflict in conflicts_kb:
                logger.error(f"    - {conflict['original_name']}: {conflict['reason']}")
    
    # Save rollback file
    if not args.dry_run and migrator.changes_log:
        rollback_file = migrator.save_rollback_file()
        logger.info(f"\nRollback information saved to: {rollback_file}")
    
    logger.info("\n" + "="*70)
    logger.info("Migration Complete!")
    logger.info("="*70)
    
    if args.dry_run:
        logger.info("\nThis was a dry run. Run without --dry-run to apply changes.")
    else:
        logger.info("\nPlease test your application to ensure everything works correctly.")
        logger.info("If issues occur, use the rollback file to restore original names.")


if __name__ == "__main__":
    main()

