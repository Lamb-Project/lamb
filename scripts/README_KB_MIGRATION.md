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

### Dry Run (Recommended First Step)

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
# From within the LAMB backend container
python /opt/lamb/scripts/migrate_kb_registry.py --dry-run

# Or using docker exec
docker exec lamb-backend python /opt/lamb/scripts/migrate_kb_registry.py --dry-run
```

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

3. **Test Assistant Display**:
   - Open assistants with KBs in the web interface
   - Verify KB names display correctly (not "X (Not Found)")

4. **Update Sharing Status** (if needed):
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

### "LAMB_KB_SERVER environment variable is required"
- Ensure `.env` file has `LAMB_KB_SERVER` set
- Check that `LAMB_KB_SERVER_TOKEN` is also set

### "Failed to connect to database"
- Verify `LAMB_DB_PATH` in `.env`
- Check database file exists: `ls -l $LAMB_DB_PATH/lamb_v4.db`
- Ensure proper file permissions

### "KB Server returned status 500"
- Check KB Server logs
- Verify KB Server is running: `curl http://localhost:9090/health`
- Test authentication: `curl -H "Authorization: Bearer $LAMB_KB_SERVER_TOKEN" http://localhost:9090/collections`

### "Could not find user ID for owner"
- User may have been deleted
- Check `LAMB_Creator_users` table for the email
- May need to reassign assistant ownership before migration

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
