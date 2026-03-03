# OWI User Race Condition Fix

**Issue:** #TBD  
**Date:** March 3, 2026  
**Status:** Fixed in dev branch

## Problem

When running Open WebUI with multiple uvicorn workers (`--workers 4`), a race condition could occur during user creation that resulted in duplicate user records for the same email address.

### Root Cause

1. **No UNIQUE constraint** on the `email` column in Open WebUI's `user` table
2. **Check-then-insert pattern** without proper locking:
   ```python
   if self.db.get_user_by_email(email):  # Check
       return None
   # Race window here - multiple workers can pass this check
   INSERT INTO user (...)  # Insert - all succeed
   ```
3. **Multi-worker setup** amplified the race condition (4 workers = 4 duplicates)

### Impact

- Duplicate user records with same email but different UUIDs
- Inconsistent authentication state
- Navigation menu showing incorrect permissions (e.g., "Org Admin" instead of "Admin")

## Solution

### 1. Database Schema Fix

Added UNIQUE constraint on email column to enforce data integrity:
```sql
CREATE UNIQUE INDEX user_email ON user (email);
```

This prevents duplicate users at the database level, regardless of application-level race conditions.

### 2. Code Fix - Proactive File-Based Locking

**Primary Defense:** Added file-based locking to prevent race conditions **before** they occur.

Updated `backend/lamb/owi_bridge/owi_users.py` with a `UserCreationLock` context manager that uses `fcntl` (POSIX file locking) to serialize user creation across multiple workers:

```python
class UserCreationLock:
    """
    File-based lock to prevent race conditions during user creation across multiple workers.
    
    Uses fcntl for POSIX systems (Linux, macOS). Falls back to no-op on Windows.
    """
    def __enter__(self):
        # Acquire exclusive lock (blocks other workers)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Release lock
        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
```

**Updated create_user() method:**

```python
def create_user(self, name: str, email: str, password: str, role: str = "user"):
    try:
        # PROACTIVE: Acquire lock BEFORE checking if user exists
        with UserCreationLock(email):
            # Check if user already exists (inside lock to prevent TOCTOU)
            existing_user = self.db.get_user_by_email(email)
            if existing_user:
                return existing_user
            
            # Create user (only one worker can be here at a time)
            INSERT INTO user (...)
            
    except sqlite3.IntegrityError as e:
        # DEFENSE IN DEPTH: Backup safety net if lock somehow fails
        if "UNIQUE constraint" in str(e) and "email" in str(e).lower():
            return self.db.get_user_by_email(email)
```

**How it works:**

1. **Worker 1** calls `create_user("Marc", "marc@example.com")`:
   - Acquires file lock for "marc@example.com"
   - Checks if user exists → NO
   - Creates user in database
   - Releases lock

2. **Workers 2, 3, 4** call `create_user("Marc", "marc@example.com")` simultaneously:
   - Try to acquire file lock → **BLOCKED** (Worker 1 holds it)
   - Wait until Worker 1 releases the lock
   - Worker 2 acquires lock, checks if user exists → **YES** (Worker 1 created it)
   - Returns existing user, releases lock
   - Workers 3 and 4 follow the same pattern

**Result:** Only one user is created, no race condition occurs.

### 3. Defense in Depth

The `IntegrityError` exception handling remains as a backup safety mechanism:

```python
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint" in str(e):
        logger.warning(f"User {email} already exists (rare race bypassed lock)")
        return self.db.get_user_by_email(email)
```

This catches the rare edge case where:
- File lock fails (e.g., unsupported OS, filesystem issues)
- Database UNIQUE constraint is the last line of defense

### 4. Migration Script

Created `scripts/fix_owi_user_duplicates.py` to:
- Detect duplicate users by email
- Keep most recently active user
- Delete older duplicates from both `user` and `auth` tables  
- Add UNIQUE constraint if not present

## Usage

### For Existing Installations with Duplicates

```bash
# Dry run (safe, shows what would be done)
python scripts/fix_owi_user_duplicates.py --db-path /path/to/webui.db --dry-run

# Apply fixes
python scripts/fix_owi_user_duplicates.py --db-path /path/to/webui.db
```

### For Production Servers

**On the server:**
```bash
cd /path/to/lamb
source .venv/bin/activate

# Update code to dev branch
git fetch
git checkout dev
git pull

# Run migration
python scripts/fix_owi_user_duplicates.py --db-path /path/to/webui.db --dry-run
python scripts/fix_owi_user_duplicates.py --db-path /path/to/webui.db

# Restart services
docker compose down
docker compose up -d
```

### For New Installations

No action needed - the code fix and UNIQUE constraint prevent the issue from occurring.

## Verification

After applying the fix:

```bash
# Check no duplicates remain
sqlite3 /path/to/webui.db "SELECT email, COUNT(*) as count FROM user GROUP BY email HAVING COUNT(*) > 1;"

# Verify UNIQUE constraint exists
sqlite3 /path/to/webui.db "SELECT sql FROM sqlite_master WHERE type='index' AND name='user_email';"
```

Expected result: No duplicates, and constraint exists.

## Related Changes

- Updated `backend/lamb/owi_bridge/owi_users.py`:
  - Added `import sqlite3` and `import fcntl` for database and file locking
  - Added `UserCreationLock` context manager class for POSIX file-based locking
  - Refactored `create_user()` to use file lock **before** checking user existence (proactive)
  - Added `IntegrityError` handling as defense-in-depth (reactive fallback)
  - Improved logging to track lock acquisition and user creation
  
- Created `scripts/fix_owi_user_duplicates.py` migration script:
  - Detects and cleans up existing duplicate users
  - Adds UNIQUE constraint on email column
  - Supports dry-run mode for safe testing

## Testing Recommendations

1. **Multi-worker concurrency test:**
   ```bash
   # Start with 4 workers
   uvicorn main:app --workers 4 --port 9099
   
   # Verify only one admin user created
   sqlite3 webui.db "SELECT COUNT(*) FROM user WHERE email = 'admin@example.com';"
   ```

2. Verify authentication works correctly with file locking
3. Check navigation menu displays correct role-based items
4. Test LTI user provisioning (high concurrency scenario)
5. Test user creation under load with concurrent requests

## Architecture: Why File Locking?

**Considered alternatives:**

1. ❌ **Database transaction isolation alone** - SQLite's locking is database-wide, not row-level  
2. ❌ **Redis distributed lock** - Adds external dependency
3. ❌ **INSERT OR IGNORE** - Doesn't work well when we need to return the created user
4. ✅ **File-based fcntl locking** - POSIX standard, no external deps, works across processes

**Trade-offs:**
- ✅ Simple, no external dependencies
- ✅ Works across multiple uvicorn workers (separate processes)
- ✅ Automatic lock release on process crash
- ⚠️ Not available on Windows (gracefully falls back to IntegrityError handling)
- ⚠️ File I/O overhead (minimal, lock files are tiny)
