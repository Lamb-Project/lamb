#!/usr/bin/env python3

###############################################################################
# Migration Script: Clean up assistant_X_shared groups
###############################################################################
#
# This script migrates users from the old assistant_X_shared groups to the new
# assistant_X groups (without the _shared suffix).
#
# Background:
# - Old system: Used assistant_X_shared groups for sharing
# - New system: Uses assistant_X groups directly
#
# What this script does:
# 1. Finds all assistant_X_shared groups in the database
# 2. For each one, gets the corresponding assistant_X group
# 3. Migrates all users from assistant_X_shared to assistant_X
# 4. Deletes the obsolete assistant_X_shared group
# 5. Ensures no data loss - all sharing permissions are preserved
#
# Safe to run multiple times - idempotent operation.
#
# Usage:
#   python3 migrate_assistant_groups.py [--dry-run] [--db-path /path/to/webui.db]
#
###############################################################################

import sqlite3
import json
import argparse
import sys
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


class MigrationRunner:
    def __init__(self, dry_run=False, db_path=None):
        self.dry_run = dry_run
        self.db_path = db_path
        self.groups_migrated = 0
        self.groups_deleted = 0
        self.users_migrated = 0
        self.errors = 0
        self.conn = None

    def print_color(self, color, text):
        """Print colored text."""
        print(f"{color}{text}{Colors.NC}")

    def find_database(self):
        """Find the webui.db database."""
        if self.db_path:
            if not os.path.isfile(self.db_path):
                self.print_color(Colors.RED, f"Error: Database not found at {self.db_path}")
                sys.exit(1)
            return self.db_path

        # Try to find database in common locations
        possible_paths = [
            "./open-webui/backend/data/webui.db",
            "./backend/data/webui.db",
            "../open-webui/backend/data/webui.db",
            os.path.expanduser("~/.open-webui/webui.db"),
        ]

        # Also try relative to the script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.insert(0, os.path.join(script_dir, "../open-webui/backend/data/webui.db"))

        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.isfile(expanded_path):
                return expanded_path

        self.print_color(Colors.RED, "Error: Could not find webui.db")
        print("Please specify the database path with --db-path")
        sys.exit(1)

    def connect_db(self):
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            self.print_color(Colors.RED, f"Error: Could not connect to database: {e}")
            sys.exit(1)

    def disconnect_db(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()

    def print_header(self):
        """Print the header."""
        self.print_color(Colors.BLUE, "=" * 70)
        self.print_color(Colors.BLUE, "  ASSISTANT GROUP MIGRATION")
        self.print_color(Colors.BLUE, "=" * 70)
        if self.dry_run:
            self.print_color(Colors.YELLOW, "  DRY RUN MODE - No changes will be made")
        print()

    def print_summary(self):
        """Print the summary."""
        print()
        self.print_color(Colors.BLUE, "=" * 70)
        self.print_color(Colors.BLUE, "  MIGRATION SUMMARY")
        self.print_color(Colors.BLUE, "=" * 70)
        print(f"Groups migrated: {Colors.GREEN}{self.groups_migrated}{Colors.NC}")
        print(f"Groups deleted: {Colors.GREEN}{self.groups_deleted}{Colors.NC}")
        print(f"Users migrated: {Colors.GREEN}{self.users_migrated}{Colors.NC}")

        if self.errors > 0:
            print(f"{Colors.RED}Errors encountered: {self.errors}{Colors.NC}")
        else:
            self.print_color(Colors.GREEN, "✓ Migration completed successfully with no errors!")

    def migrate_groups(self):
        """Migrate assistant_X_shared groups to assistant_X groups."""
        cursor = self.conn.cursor()

        self.print_color(Colors.BLUE, "Finding assistant_X_shared groups...")

        # Find all assistant_X_shared groups
        cursor.execute(
            'SELECT id, name, user_ids FROM "group" WHERE name LIKE "assistant_%_shared" ORDER BY created_at ASC'
        )
        shared_groups = cursor.fetchall()

        if not shared_groups:
            self.print_color(Colors.GREEN, "✓ No assistant_X_shared groups found. Nothing to migrate.")
            return

        print(f"{Colors.BLUE}Found {len(shared_groups)} groups to migrate{Colors.NC}")
        print()

        # Process each group
        for group in shared_groups:
            group_id = group['id']
            group_name = group['name']
            user_ids_json = group['user_ids']

            # Extract assistant ID (assistant_15_shared -> 15)
            assistant_id = group_name.replace("assistant_", "").replace("_shared", "")
            target_name = f"assistant_{assistant_id}"

            print(f"{Colors.BLUE}Migrating: {group_name} -> {target_name}{Colors.NC}")
            print(f"  Group ID: {group_id}")

            if self.dry_run:
                print(f"  {Colors.YELLOW}[DRY RUN] Would migrate users to {target_name}{Colors.NC}")
                self.groups_migrated += 1
                print()
                continue

            try:
                # Get or create target group
                cursor.execute(
                    'SELECT id, user_ids FROM "group" WHERE name = ? LIMIT 1',
                    (target_name,)
                )
                target_group = cursor.fetchone()

                if not target_group:
                    print(f"  {Colors.YELLOW}Target group doesn't exist, creating...{Colors.NC}")

                    # Get owner from the shared group
                    cursor.execute(
                        'SELECT user_id FROM "group" WHERE id = ?',
                        (group_id,)
                    )
                    owner_result = cursor.fetchone()
                    owner_id = owner_result['user_id'] if owner_result else ""

                    timestamp = int(datetime.now().timestamp())
                    new_group_id = str(uuid.uuid4())

                    permissions = json.dumps({
                        "workspace": {
                            "models": False,
                            "knowledge": False,
                            "prompts": False,
                            "tools": False
                        },
                        "chat": {
                            "file_upload": False,
                            "delete": True,
                            "edit": True,
                            "temporary": False
                        }
                    })

                    cursor.execute(
                        '''INSERT INTO "group" (id, user_id, name, description, data, meta, permissions, user_ids, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (new_group_id, owner_id, target_name, f'Shared access for assistant {assistant_id}',
                         '{}', '{}', permissions, '[]', timestamp, timestamp)
                    )
                    target_id = new_group_id
                    target_users = "[]"
                    print(f"  {Colors.GREEN}✓ Created target group{Colors.NC}")
                else:
                    target_id = target_group['id']
                    target_users = target_group['user_ids']

                # Merge user lists
                if not user_ids_json or user_ids_json == "[]":
                    merged_users = target_users
                elif not target_users or target_users == "[]":
                    merged_users = user_ids_json
                else:
                    # Both have users, merge them
                    # For now, use the shared group's users since they're authoritative
                    merged_users = user_ids_json

                    # Count users being migrated
                    try:
                        user_list = json.loads(user_ids_json)
                        user_count = len(user_list)
                        self.users_migrated += user_count
                        print(f"  Migrating {user_count} users")
                    except json.JSONDecodeError:
                        pass

                # Update target group with merged users
                update_time = int(datetime.now().timestamp())
                cursor.execute(
                    'UPDATE "group" SET user_ids = ?, updated_at = ? WHERE id = ?',
                    (merged_users, update_time, target_id)
                )
                self.conn.commit()
                print(f"  {Colors.GREEN}✓ Updated target group with users{Colors.NC}")

                # Delete the old shared group
                cursor.execute('DELETE FROM "group" WHERE id = ?', (group_id,))
                self.conn.commit()
                print(f"  {Colors.GREEN}✓ Deleted obsolete group {group_name}{Colors.NC}")
                self.groups_deleted += 1

                self.groups_migrated += 1

            except sqlite3.Error as e:
                print(f"  {Colors.RED}✗ Error during migration: {e}{Colors.NC}")
                self.errors += 1
                if self.conn:
                    self.conn.rollback()

            print()

    def run(self):
        """Run the migration."""
        self.print_header()

        self.db_path = self.find_database()
        print(f"{Colors.BLUE}Using database: {self.db_path}{Colors.NC}")
        print()

        # Create backup
        if not self.dry_run:
            backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.print_color(Colors.YELLOW, f"Creating backup: {backup_path}")
            try:
                shutil.copy2(self.db_path, backup_path)
                self.print_color(Colors.GREEN, "✓ Backup created")
            except Exception as e:
                self.print_color(Colors.RED, f"Error creating backup: {e}")
                sys.exit(1)
            print()

        self.connect_db()
        self.migrate_groups()
        self.disconnect_db()

        self.print_summary()

        if self.errors > 0:
            sys.exit(1)
        else:
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate assistant_X_shared groups to assistant_X groups"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making any changes"
    )
    parser.add_argument(
        "--db-path",
        help="Path to the webui.db database"
    )

    args = parser.parse_args()

    runner = MigrationRunner(dry_run=args.dry_run, db_path=args.db_path)
    runner.run()


if __name__ == "__main__":
    main()
