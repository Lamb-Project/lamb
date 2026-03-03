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

Added UNIQUE constraint on email column:
```sql
CREATE UNIQUE INDEX user_email ON user (email);
```

### 2. Code Fix

Updated `backend/lamb/owi_bridge/owi_users.py` to handle race conditions gracefully:

```python
try:
    cursor.execute(user_query, user_params)
    cursor.execute(auth_query, auth_params)
    conn.commit()
    return self.db.get_user_by_id(user_id)
except sqlite3.IntegrityError as e:
    conn.rollback()
    if "UNIQUE constraint" in str(e) and "email" in str(e).lower():
        logger.warning(f"User {email} already exists (race condition), fetching existing user")
        return self.db.get_user_by_email(email)
    else:
        logger.error(f"Integrity error creating user: {e}")
        return None
```

Now when multiple workers try to create the same user:
- First worker succeeds
- Other workers get `IntegrityError` and fetch the existing user
- All requests succeed, but only one user record is created

### 3. Migration Script

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
  - Added `import sqlite3`
  - Added `IntegrityError` handling in `create_user()`
  
- Created `scripts/fix_owi_user_duplicates.py` migration script

## Testing Recommendations

1. Test user creation with multiple workers
2. Verify authentication works correctly
3. Check navigation menu displays correct role-based items
4. Test LTI user provisioning (high concurrency scenario)

## Future Improvements

Consider adding:
- Transaction isolation levels for critical sections
- Distributed locking for high-concurrency scenarios
- Monitoring/alerting for IntegrityError occurrences
