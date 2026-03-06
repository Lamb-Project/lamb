"""
Test concurrent user creation to verify file locking prevents race conditions.

This test spawns multiple processes that simultaneously try to create the same user,
verifying that only one user record is created despite concurrent attempts.
"""

import sys
import os
import multiprocessing
import sqlite3
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lamb.owi_bridge.owi_users import OwiUserManager


def create_test_user(worker_id: int, email: str, db_path: str) -> dict:
    """Worker function that tries to create a user."""
    try:
        # Each worker creates its own manager instance (simulating separate uvicorn workers)
        # Configure test database
        os.environ['OWI_PATH'] = os.path.dirname(db_path)
        
        manager = OwiUserManager()
        result = manager.create_user(
            name=f"Test User {worker_id}",
            email=email,
            password="test123",
            role="user"
        )
        
        if result:
            return {"worker_id": worker_id, "success": True, "user_id": result.get('id')}
        else:
            return {"worker_id": worker_id, "success": False, "error": "create_user returned None"}
            
    except Exception as e:
        return {"worker_id": worker_id, "success": False, "error": str(e)}


def setup_test_database(db_path: str):
    """Create a minimal test database with required tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create user table with UNIQUE constraint on email
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            profile_image_url TEXT NOT NULL,
            settings TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL
        )
    """)
    
    # Add UNIQUE constraint on email
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS user_email ON user (email)")
    
    # Create auth table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            active INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()


def count_users_by_email(db_path: str, email: str) -> int:
    """Count how many user records exist for a given email."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user WHERE email = ?", (email,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def test_concurrent_user_creation():
    """
    Test that concurrent user creation with file locking prevents duplicates.
    
    Spawns 4 workers simultaneously trying to create the same user.
    Expected: Only 1 user record created.
    """
    # Create temporary database
    temp_dir = tempfile.mkdtemp(prefix='lamb_test_')
    db_path = os.path.join(temp_dir, 'webui.db')
    
    try:
        print("=" * 70)
        print("Testing Concurrent User Creation with File Locking")
        print("=" * 70)
        print(f"\nTest database: {db_path}")
        
        # Setup test database
        setup_test_database(db_path)
        print("✓ Test database initialized")
        
        # Test email
        test_email = "concurrent.test@example.com"
        num_workers = 4
        
        print(f"\n🔄 Spawning {num_workers} workers to create user: {test_email}")
        print("   (simulating uvicorn --workers 4 scenario)\n")
        
        # Spawn multiple processes simultaneously
        with multiprocessing.Pool(processes=num_workers) as pool:
            results = pool.starmap(
                create_test_user,
                [(i, test_email, db_path) for i in range(num_workers)]
            )
        
        # Analyze results
        print("Worker Results:")
        print("-" * 70)
        for result in results:
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            print(f"  Worker {result['worker_id']}: {status}")
            if 'user_id' in result:
                print(f"    User ID: {result['user_id']}")
            if 'error' in result:
                print(f"    Error: {result['error']}")
        
        # Check database state
        user_count = count_users_by_email(db_path, test_email)
        
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Users created in database: {user_count}")
        
        if user_count == 1:
            print("✅ TEST PASSED: File locking prevented race condition!")
            print("   Only one user was created despite 4 concurrent attempts.")
            return True
        else:
            print(f"❌ TEST FAILED: Expected 1 user, found {user_count}")
            print("   File locking did not prevent race condition.")
            return False
            
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_concurrent_user_creation()
    sys.exit(0 if success else 1)
