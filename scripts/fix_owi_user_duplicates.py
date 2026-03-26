#!/usr/bin/env python3
"""
Fix OWI User Duplicate Issue - Migration Script

This script:
1. Identifies duplicate users by email in the Open WebUI database
2. Keeps the most recently active user for each duplicate
3. Deletes older duplicates from both 'user' and 'auth' tables
4. Adds a UNIQUE constraint on the email column to prevent future duplicates

Usage:
    python scripts/fix_owi_user_duplicates.py --db-path /path/to/webui.db [--dry-run]
"""

import sqlite3
import argparse
import sys
from typing import List, Dict, Tuple


def find_duplicates(conn: sqlite3.Connection) -> List[str]:
    """Find email addresses that have duplicate user records."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, COUNT(*) as count
        FROM user
        GROUP BY email
        HAVING COUNT(*) > 1
    """)
    return [row[0] for row in cursor.fetchall()]


def get_duplicate_details(conn: sqlite3.Connection, email: str) -> List[Dict]:
    """Get details of all duplicate users for a given email."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, role, created_at, updated_at, last_active_at
        FROM user
        WHERE email = ?
        ORDER BY last_active_at DESC, created_at DESC
    """, (email,))
    
    columns = ['id', 'name', 'role', 'created_at', 'updated_at', 'last_active_at']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def delete_duplicate_users(conn: sqlite3.Connection, email: str, ids_to_delete: List[str], dry_run: bool = False) -> None:
    """Delete duplicate user records, keeping the first one in the list."""
    cursor = conn.cursor()
    
    for user_id in ids_to_delete:
        print(f"  {'[DRY RUN] Would delete' if dry_run else 'Deleting'} user ID: {user_id}")
        
        if not dry_run:
            # Delete from auth table
            cursor.execute("DELETE FROM auth WHERE id = ?", (user_id,))
            # Delete from user table
            cursor.execute("DELETE FROM user WHERE id = ?", (user_id,))


def check_unique_constraint_exists(conn: sqlite3.Connection) -> bool:
    """Check if UNIQUE constraint on email already exists."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' 
        AND (sql LIKE '%email%' AND (sql LIKE '%UNIQUE%' OR name LIKE '%email%'))
    """)
    indexes = cursor.fetchall()
    
    # Check if any index is on the email column
    for idx in indexes:
        cursor.execute(f"PRAGMA index_info({idx[0]})")
        columns = cursor.fetchall()
        for col in columns:
            if col[2] == 'email':  # col[2] is the column name
                return True
    return False


def add_unique_constraint(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    """Add UNIQUE constraint to email column."""
    if check_unique_constraint_exists(conn):
        print("✓ UNIQUE constraint on email already exists")
        return
    
    print(f"{'[DRY RUN] Would add' if dry_run else 'Adding'} UNIQUE constraint on email column...")
    
    if not dry_run:
        cursor = conn.cursor()
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS user_email ON user (email)")
        print("✓ UNIQUE constraint added successfully")


def main():
    parser = argparse.ArgumentParser(description='Fix OWI user duplicates and add UNIQUE constraint')
    parser.add_argument('--db-path', required=True, help='Path to webui.db database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()
    
    print(f"{'='*60}")
    print(f"OWI User Duplicate Fix - {'DRY RUN MODE' if args.dry_run else 'LIVE MODE'}")
    print(f"{'='*60}\n")
    
    try:
        # Connect to database
        conn = sqlite3.connect(args.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Find duplicates
        print("Scanning for duplicate users...")
        duplicate_emails = find_duplicates(conn)
        
        if not duplicate_emails:
            print("✓ No duplicate users found!\n")
        else:
            print(f"⚠ Found {len(duplicate_emails)} email(s) with duplicates:\n")
            
            total_duplicates_removed = 0
            
            for email in duplicate_emails:
                users = get_duplicate_details(conn, email)
                print(f"Email: {email} ({len(users)} records)")
                
                # Keep the most recent (first in list), delete the rest
                keep_user = users[0]
                delete_users = users[1:]
                
                print(f"  ✓ Keeping: ID={keep_user['id']}, role={keep_user['role']}, "
                      f"last_active={keep_user['last_active_at']}")
                
                ids_to_delete = [u['id'] for u in delete_users]
                delete_duplicate_users(conn, email, ids_to_delete, dry_run=args.dry_run)
                total_duplicates_removed += len(ids_to_delete)
                print()
            
            print(f"Summary: {'Would remove' if args.dry_run else 'Removed'} {total_duplicates_removed} duplicate record(s)\n")
        
        # Add UNIQUE constraint
        add_unique_constraint(conn, dry_run=args.dry_run)
        
        # Commit changes
        if not args.dry_run:
            conn.commit()
            print("\n✓ All changes committed successfully!")
        else:
            print("\n[DRY RUN] No changes were made. Run without --dry-run to apply changes.")
        
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
