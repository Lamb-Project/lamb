# KB Registry Migration Script

This directory contains the migration script to populate the `LAMB_kb_registry` table with existing Knowledge Base references from assistants.

## Purpose

After upgrading to v0.2, the new `LAMB_kb_registry` table needs to be populated with existing KB references. This script:

1. Scans all assistants for KB references in the `RAG_collections` field
2. Fetches KB metadata from the KB Server
3. Creates registry entries for each KB
4. Preserves creation dates when available

## Prerequisites

- LAMB backend environment set up with `.env` file
- Access to the LAMB database (specified in `LAMB_DB_PATH`)
- KB Server running and accessible (specified in `LAMB_KB_SERVER`)
- Python 3.11+ with required dependencies installed

## Usage

### Check Environment (Recommended First Step)

Verify that all environment variables and dependencies are properly configured:

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py --check-env
```

This will check:

- Required environment variables (LAMB_DB_PATH, LAMB_KB_SERVER, etc.)
- Database file existence and accessibility
- KB Server connectivity

### Dry Run (Recommended Before Migration)

See what the script would do without making any changes:

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py --dry-run
```

### Run Migration

Execute the actual migration:

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py
```

### Use Specific Database File

Test with a production database copy:

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py --db lamb_v4_prod.db --dry-run
```

### Verbose Mode

Get detailed logging:

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py --verbose
```

### Combined Options

```bash
cd /opt/lamb
python scripts/migrate_kb_registry.py --db lamb_v4_prod.db --dry-run --verbose
```

### Running in Production (Docker)

When running in a Docker environment where the KB Server is accessible:

```bash
# First, check the environment setup
docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --check-env

# If environment check passes, run dry-run
docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --dry-run

# Finally, run the actual migration
docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py

# With verbose output for debugging
docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --dry-run --verbose
```

**Note:** The container name may vary depending on your setup. Use `docker ps` to find the exact name (e.g., `lamb-backend`, `lamb-backend-1`, `lamb_backend_1`).

## What It Does

### Step 1: Scan Assistants

- Queries `LAMB_assistants` table for all assistants with non-empty `RAG_collections`
- Extracts KB IDs from comma-separated values

### Step 2: Resolve Owners

- Looks up user IDs from the `LAMB_Creator_users` table
- Verifies organization IDs exist

### Step 3: Check Existing Entries

- Checks if each KB is already registered in `LAMB_kb_registry`
- Skips already-registered KBs

### Step 4: Fetch KB Data

- Queries KB Server for KB details: `GET /collections/{kb_id}`
- Extracts KB name and creation date

### Step 5: Register KBs

- Creates entries in `LAMB_kb_registry` with:
  - `kb_id`: Original KB ID from assistant
  - `kb_name`: Name from KB Server
  - `owner_user_id`: User ID of assistant owner
  - `organization_id`: Organization ID from assistant
  - `is_shared`: `false` (default, can be updated later)
  - `created_at`: Preserved from KB Server if available

## Output

The script provides detailed progress logging:

```
======================================================================
KB Registry Migration Script
======================================================================
KB Server: http://localhost:9090
Fetching assistants with KB references...
Found 15 assistant(s) with KB references

Processing assistants...
Processing assistant 19 '3_asistente_ikasiker' with 1 KB(s)
  Fetching KB 13 from KB Server...
  ✓ Registered KB 13 ('Course Materials')

======================================================================
Migration Summary
======================================================================
Assistants scanned:       15
Assistants with KBs:      15
Unique KB IDs found:      8
KBs registered:           5
KBs already registered:   2
KBs not found in server:  1
Errors:                   0
======================================================================
```

## Error Handling

The script handles various error conditions gracefully:

- **KB not found in KB Server (404)**: Logged as warning, counted in stats
- **Owner user not found**: Assistant skipped, error logged
- **No organization ID**: Assistant skipped, error logged
- **KB Server offline**: Error logged, migration continues with other KBs
- **Database errors**: Caught and logged, migration continues

## Exit Codes

- `0`: Success (no errors)
- `1`: Errors occurred during migration (check logs)
- `130`: Interrupted by user (Ctrl+C)

## Safety Features

### Idempotent

- Safe to run multiple times
- Checks for existing entries before registering
- Won't create duplicates

### Dry Run Mode

- Test the migration without making changes
- See exactly what would be registered
- Verify KB Server connectivity

### Transaction Safety

- Uses database manager's built-in methods
- Each KB registration is atomic

## Post-Migration

After running the migration:

1. **Verify Registration**:

   ```sql
   SELECT COUNT(*) FROM LAMB_kb_registry;
   ```

2. **Check for Issues**:

   ```sql
   SELECT kb_id, kb_name, owner_user_id, is_shared
   FROM LAMB_kb_registry
   ORDER BY created_at DESC
   LIMIT 10;
   ```

3. **Restart Backend Service** (CRITICAL):

   ```bash
   # Docker deployment
   docker restart lamb-backend-1

   # Or restart the entire stack
   docker-compose restart
   ```

   ⚠️ **The backend must be restarted** after migration to ensure it reads the updated registry data and clears any internal caches.

4. **Test Assistant Display**:

   - **Hard refresh** the browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows/Linux) to clear frontend cache
   - Open assistants with KBs in the web interface
   - Verify KB names display correctly (not "X (Not Found)")
   - Check browser console for errors if KBs still show "(Not Found)"

5. **Test Backend KB API** (if still showing "Not Found"):

   ```bash
   # Test the backend KB list endpoint (replace with your user token)
   curl -H 'Authorization: Bearer <your_user_token>' \
        https://lamb.lamb-project.org/creator/knowledgebases/user
   ```

   This should return a JSON array of KBs. Verify that:
   - The response includes KB ID "13" (or whichever KB is showing "Not Found")
   - The `id` field matches exactly (not `_id` or other variations)
   - The `name` field is populated

6. **Verify KB Server Has the KB** (if backend API doesn't return it):

   ```bash
   # Test that KB Server has the KB
   curl -H "Authorization: Bearer $LAMB_KB_SERVER_TOKEN" \
        http://localhost:9090/collections/13
   ```

   Replace `13` with the KB ID that's showing "(Not Found)". If this returns 404, the KB was deleted from the KB Server but still referenced in assistants.

7. **Check Browser Console** (if KB is in backend API but not displaying):
   
   - Open browser Developer Tools (F12)
   - Go to Console tab
   - Look for errors when loading the assistant detail page
   - Check for KB fetch errors or ID mismatch messages

8. **Update Sharing Status** (if needed):

   ```sql
   -- Make specific KBs shared
   UPDATE LAMB_kb_registry
   SET is_shared = 1
   WHERE kb_id IN ('kb_id_1', 'kb_id_2');
   ```

## Cleanup Stale References

If KBs were found in assistants but not in the KB Server (deleted KBs), you may want to clean up the references:

```sql
-- Find assistants with stale KB references
-- (Run after migration to identify which KB IDs don't exist)

-- Option 1: Set RAG_collections to empty for affected assistants
UPDATE LAMB_assistants
SET RAG_collections = ''
WHERE id IN (19, 42, 67);  -- Replace with actual IDs

-- Option 2: Remove specific KB IDs from comma-separated list
-- (Requires manual editing per assistant)
```

## Troubleshooting

### Script produces no output in Docker

If the script runs but produces no output when executed via `docker exec`:

1. **Check environment variables in the container**:

   ```bash
   docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --check-env
   ```

2. **Verify the .env file is mounted**:

   ```bash
   docker exec lamb-backend-1 cat /opt/lamb/backend/.env
   ```

3. **Check Python and import errors**:

   ```bash
   docker exec lamb-backend-1 python -c "import sys; sys.path.insert(0, '/opt/lamb/backend'); from lamb.database_manager import LambDatabaseManager; print('Import successful')"
   ```

4. **Run with verbose flag**:

   ```bash
   docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --dry-run --verbose
   ```

5. **Capture both stdout and stderr**:
   ```bash
   docker exec lamb-backend-1 python /opt/lamb/scripts/migrate_kb_registry.py --check-env 2>&1
   ```

### "LAMB_KB_SERVER environment variable is required"

- Ensure `.env` file has `LAMB_KB_SERVER` set
- Check that `LAMB_KB_SERVER_TOKEN` is also set
- Run `--check-env` to diagnose the issue

### "Failed to connect to database"

- Verify `LAMB_DB_PATH` in `.env`
- Check database file exists: `ls -l $LAMB_DB_PATH/lamb_v4.db`
- Ensure proper file permissions
- Run `--check-env` to see detailed database information

### "KB Server returned status 500"

- Check KB Server logs
- Verify KB Server is running: `curl http://localhost:9090/health`
- Test authentication: `curl -H "Authorization: Bearer $LAMB_KB_SERVER_TOKEN" http://localhost:9090/collections`

### "Could not find user ID for owner"

- User may have been deleted
- Check `LAMB_Creator_users` table for the email
- May need to reassign assistant ownership before migration

### Module import errors in Docker

- Ensure the backend directory is accessible in the container
- Verify all Python dependencies are installed: `docker exec lamb-backend-1 pip list`
- Check that the script path is correct: `/opt/lamb/scripts/migrate_kb_registry.py`

### Migration successful but KBs still show "(Not Found)" in frontend

This is the most common post-migration issue. The migration completed successfully (e.g., "✓ Successfully registered 11 KB(s)") but the frontend still displays "13 (Not Found)".

**Root Cause:** The backend service needs to be restarted to read the fresh KB registry data. The backend may have cached the old state.

**Solution:**

1. **Restart the backend** (most important):
   ```bash
   ssh user@server "docker restart lamb-backend-1"
   ```

2. **Verify backend is running**:
   ```bash
   ssh user@server "docker ps | grep lamb-backend"
   ```

3. **Clear browser cache**:
   - Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)
   - Or clear site data in browser DevTools

4. **Verify the fix**:
   - Navigate to the assistant detail page
   - KB names should now appear instead of "13 (Not Found)"

5. **If still not working, check backend API directly**:
   ```bash
   # Get your user token from browser localStorage (F12 > Console > localStorage.getItem('userToken'))
   curl -H 'Authorization: Bearer <your_token>' \
        https://your-domain.com/creator/knowledgebases/user
   ```
   
   **If this returns an empty array `[]`:**
   - Your user may not be registered in the Creator system
   - Check if your email exists: `SELECT * FROM LAMB_Creator_users WHERE user_email = 'your@email.com';`
   - You may need to login to the Creator interface at least once to auto-register
   - Or manually register the user in the `LAMB_Creator_users` table
   
   **If this returns KBs:**
   - The response should include your KB with `id: "13"` and `name: "ikasiker"` (or whatever name)
   - The issue is in the frontend - check browser console for errors

6. **Check browser console** for JavaScript errors that might prevent KB loading

### Backend API returns empty array for /creator/knowledgebases/user

If the curl command `curl -H 'Authorization: Bearer <token>' https://your-domain.com/creator/knowledgebases/user` returns `[]` (empty array), this can have multiple causes.

**Check Backend Logs First** (most important diagnostic step):

```bash
# Watch backend logs while making the request
ssh user@server "docker logs -f lamb-backend-1"
```

Look for these key log messages:
- `KB server response status: 401` → **KB Server authentication issue** (see Solution A below)
- `No creator user found for email` → **User registration issue** (see Solution B below)
- `KB Server returned 404 for KB X` → **KB doesn't exist** (see Solution C below)

#### Solution A: KB Server Returns 401 Unauthorized (Most Common)

**Symptoms in logs:**
```
INFO: KB server response status: 401
ERROR: KB server returned non-200 status: 401
WARNING: KB Server returned 401 for KB 13, skipping
```

**Root Cause:** The organization's KB Server API token in the database doesn't match the token the KB Server expects. This happens when:
- The organization was created with an incorrect token
- The KB Server token was changed but the organization config wasn't updated
- Multiple organizations exist with different KB Server configurations

**Diagnosis:**

1. **Check what token the backend is using** (from backend logs or database):
   ```sql
   -- View the organization's KB Server configuration
   SELECT id, name, slug, 
          json_extract(config, '$.setups.default.knowledge_base.api_token') as kb_token,
          json_extract(config, '$.setups.default.knowledge_base.server_url') as kb_url
   FROM LAMB_organizations;
   ```

2. **Check what token the KB Server expects**:
   ```bash
   # Check the KB Server's environment
   docker exec lamb-kb-server-stable-backend-1 env | grep -i token
   
   # Or check the KB Server's .env file
   docker exec lamb-kb-server-stable-backend-1 cat /opt/lamb/lamb-kb-server-stable/backend/.env | grep KB_TOKEN
   ```

3. **Test KB Server authentication manually**:
   ```bash
   # Test with the token from organization config
   curl -H "Authorization: Bearer 0p3n-w3bu!" http://localhost:9090/collections
   
   # If it returns 401, the token is wrong
   # If it returns 200, the token is correct but something else is wrong
   ```

**Fix:**

```sql
-- Update the organization's KB Server token
-- Replace 2 with your organization_id and 'correct_token' with the actual token
UPDATE LAMB_organizations 
SET config = json_set(
    config, 
    '$.setups.default.knowledge_base.api_token', 
    'correct_token_here'
),
updated_at = strftime('%s', 'now')
WHERE id = 2;

-- Verify the update
SELECT id, name, 
       json_extract(config, '$.setups.default.knowledge_base.api_token') as kb_token
FROM LAMB_organizations 
WHERE id = 2;
```

**After fixing the token, restart the backend:**
```bash
docker restart lamb-backend-1
```

Then test again - the KBs should now appear!

#### Solution B: User Not Registered in Creator System

**Symptoms in logs:**
```
ERROR: No creator user found for email: user@example.com
```

**Diagnosis:**

1. **Check if your user exists in Creator system**:
   ```sql
   -- Replace with your actual email
   SELECT * FROM LAMB_Creator_users WHERE user_email = 'your@email.com';
   ```

2. **Check who owns the KB**:
   ```sql
   SELECT r.kb_id, r.kb_name, r.owner_user_id, u.user_email
   FROM LAMB_kb_registry r 
   LEFT JOIN LAMB_Creator_users u ON r.owner_user_id = u.id
   WHERE r.kb_id = '13';
   ```

**Fix:**

Option 1: **Auto-register by logging in**:
- Navigate to the Creator interface: `https://your-domain.com/creator/`
- Login with your credentials
- The system should auto-register you in `LAMB_Creator_users`

Option 2: **Manual registration** (if auto-registration doesn't work):
```sql
-- Find the next available user ID
SELECT MAX(id) + 1 FROM LAMB_Creator_users;

-- Register the user (replace values as needed)
INSERT INTO LAMB_Creator_users (
    id, 
    organization_id, 
    user_email, 
    user_name, 
    created_at, 
    updated_at, 
    user_type, 
    enabled
) VALUES (
    <next_id>,
    1,  -- Replace with your organization_id
    'your@email.com',
    'Your Name',
    strftime('%s', 'now'),
    strftime('%s', 'now'),
    'creator',
    1
);
```

#### Solution C: KB Belongs to Different User / Access Issue

**Symptoms in logs:**
```
INFO: Found 1 owned KB registry entries for user 3
INFO: Returning 0 owned KBs to user 3  (mismatch indicates access issue)
```

**Fix:**

- If the KB was created by `alexander.mendiburu@ehu.eus` but you're logged in as a different user
- You won't see the KB unless it's marked as shared
- Either:
  - Login as the KB owner
  - Or have an admin mark the KB as shared: `UPDATE LAMB_kb_registry SET is_shared = 1 WHERE kb_id = '13';`

## Related Documentation

- [KB Not Found Fix](../Documentation/KB_NOT_FOUND_V02_MIGRATION_FIX.md) - Root cause analysis and runtime fix
- [LAMB Architecture](../Documentation/lamb_architecture.md) - System architecture overview
- [Database Schema](../Documentation/LAMB_DATABASE_SCHEMA.md) - Database structure reference

## Support

If you encounter issues during migration:

1. Run with `--dry-run --verbose` to see detailed information
2. Check the error messages in the output
3. Verify environment variables are set correctly
4. Ensure KB Server is accessible and responding
5. Check database permissions

For persistent issues, please open an issue on the LAMB GitHub repository.
