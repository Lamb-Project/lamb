"""
Migration: Add ingestion tracking fields to file_registry table.

This migration adds new columns for:
- Processing timing (processing_started_at, processing_completed_at)
- Progress tracking (progress_current, progress_total, progress_message)
- Error tracking (error_message, error_details)
- New status value: PENDING, CANCELLED

Run this migration after upgrading to support enhanced ingestion job tracking.

Usage:
    python -m database.migrations.migration_add_ingestion_tracking

Or import and call:
    from database.migrations.migration_add_ingestion_tracking import run_migration
    run_migration()
"""

import sqlite3
import os
from pathlib import Path

# Database path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"


def run_migration():
    """Run the migration to add new columns to file_registry table."""
    
    if not SQLITE_DB_PATH.exists():
        print(f"Database not found at {SQLITE_DB_PATH}. Skipping migration.")
        return False
    
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Get existing columns
        cursor.execute("PRAGMA table_info(file_registry)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        print(f"Existing columns in file_registry: {existing_columns}")
        
        # Define new columns to add
        new_columns = [
            # Timing fields
            ("processing_started_at", "DATETIME", None),
            ("processing_completed_at", "DATETIME", None),
            
            # Progress tracking
            ("progress_current", "INTEGER", "0"),
            ("progress_total", "INTEGER", "0"),
            ("progress_message", "VARCHAR(255)", None),
            
            # Error tracking
            ("error_message", "TEXT", None),
            ("error_details", "JSON", None),
        ]
        
        added_columns = []
        
        for col_name, col_type, default in new_columns:
            if col_name not in existing_columns:
                if default is not None:
                    sql = f"ALTER TABLE file_registry ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                else:
                    sql = f"ALTER TABLE file_registry ADD COLUMN {col_name} {col_type}"
                
                print(f"Adding column: {col_name}")
                cursor.execute(sql)
                added_columns.append(col_name)
            else:
                print(f"Column already exists: {col_name}")
        
        # Update status enum - SQLite doesn't enforce enum constraints,
        # but we should update any existing COMPLETED statuses that were set as default
        # No action needed for SQLite as it stores enums as strings
        
        # Migrate existing PROCESSING status records that don't have started_at
        cursor.execute("""
            UPDATE file_registry 
            SET processing_started_at = created_at 
            WHERE status = 'processing' AND processing_started_at IS NULL
        """)
        
        # Migrate existing COMPLETED status records
        cursor.execute("""
            UPDATE file_registry 
            SET processing_started_at = created_at,
                processing_completed_at = updated_at,
                progress_message = 'Completed (migrated)'
            WHERE status = 'completed' 
            AND processing_started_at IS NULL
        """)
        
        # Migrate existing FAILED status records
        cursor.execute("""
            UPDATE file_registry 
            SET processing_started_at = created_at,
                processing_completed_at = updated_at,
                progress_message = 'Failed (migrated)',
                error_message = 'Unknown error (record migrated from previous version)'
            WHERE status = 'failed' 
            AND processing_started_at IS NULL
            AND error_message IS NULL
        """)
        
        conn.commit()
        
        print(f"\nMigration completed successfully!")
        print(f"Added {len(added_columns)} new columns: {added_columns}")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
        
    finally:
        conn.close()


def check_migration_status():
    """Check if migration has been applied."""
    
    if not SQLITE_DB_PATH.exists():
        return {"applied": False, "reason": "Database does not exist"}
    
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(file_registry)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            "processing_started_at",
            "processing_completed_at", 
            "progress_current",
            "progress_total",
            "progress_message",
            "error_message",
            "error_details"
        }
        
        missing = required_columns - existing_columns
        
        if missing:
            return {
                "applied": False, 
                "reason": f"Missing columns: {missing}",
                "existing": list(existing_columns)
            }
        
        return {"applied": True, "columns": list(existing_columns)}
        
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add Ingestion Tracking Fields")
    print("=" * 60)
    
    status = check_migration_status()
    print(f"\nCurrent status: {status}")
    
    if not status.get("applied"):
        print("\nRunning migration...")
        run_migration()
    else:
        print("\nMigration already applied. No changes needed.")

