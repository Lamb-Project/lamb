# Knowledge Base "Not Found" Issue After v0.2 Migration

**Date:** November 23, 2025  
**Issue:** KBs showing as "(Not Found)" in assistant details after v0.2 migration  
**Status:** Fixed  
**Related GitHub Issue:** v0.2 migration breaks assistant-KB links

---

## Problem Description

After migrating to v0.2, assistants that previously had Knowledge Bases attached now display the KB ID followed by "(Not Found)" in the assistant detail view. For example, an assistant with `RAG_collections = "13"` shows "13 (Not Found)" instead of the actual Knowledge Base name.

### Example Scenario

**Production Database State:**
```sql
-- Assistant with KB reference
SELECT id, name, RAG_collections FROM LAMB_assistants WHERE id = 19;
-- Result: 19 | 3_asistente_ikasiker | 13

-- KB Registry (new in v0.2)
SELECT COUNT(*) FROM LAMB_kb_registry;
-- Result: 0 (empty!)
```

The assistant references KB ID "13", but the new `LAMB_kb_registry` table is empty.

---

## Root Cause Analysis

### What Changed in v0.2

1. **Table Renaming:** All tables were prefixed with `LAMB_` (e.g., `assistants` → `LAMB_assistants`)
2. **New KB Registry:** A new `LAMB_kb_registry` table was introduced for KB sharing features
3. **KB Fetching Logic:** Code was updated to fetch KBs from the registry table instead of directly from KB server

### The Gap

The v0.2 migration successfully:
- ✅ Renamed tables with `LAMB_` prefix
- ✅ Preserved existing assistant data including `RAG_collections` field
- ✅ Created the new `LAMB_kb_registry` table structure

But it **failed to**:
- ❌ Populate `LAMB_kb_registry` with existing KB references from assistants
- ❌ Migrate KB metadata from old `LAMB_collections` table (if it existed)

### Why "(Not Found)" Appears

```javascript
// Frontend code (assistants/+page.svelte)
{#each selectedAssistantData.RAG_collections.split(',') as kbId}
    {@const kb = accessibleKnowledgeBases.find(k => k.id === kbId)}
    <span>
        {kb ? kb.name : `${kbId} (Not Found)`}
    </span>
{/each}
```

**Flow:**
1. Assistant has `RAG_collections = "13"`
2. Frontend fetches accessible KBs via `/knowledgebases/user` and `/knowledgebases/shared`
3. Backend queries `LAMB_kb_registry` table → returns empty array
4. Frontend searches for KB with `id === "13"` in empty array → not found
5. Displays "13 (Not Found)"

---

## Solution Implemented

### Approach

Instead of requiring a database migration to populate `kb_registry`, we implemented a **runtime resolution** that fetches KB details directly from the KB Server (the source of truth for KB data).

### Backend Fix

**File:** `/opt/lamb/backend/creator_interface/assistant_router.py`  
**Function:** `get_assistant_proxy()`

Added KB name resolution logic after fetching assistant data:

```python
# Resolve KB names for RAG_collections (v0.2 migration fix)
# This handles legacy KB references that may not be in kb_registry yet
if assistant_data.get('RAG_collections'):
    try:
        from creator_interface.kb_server_manager import KBServerManager
        kb_manager = KBServerManager()
        
        # Get KB config for the user
        kb_config = kb_manager._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        # Split comma-separated KB IDs
        kb_ids = [kb_id.strip() for kb_id in assistant_data['RAG_collections'].split(',') if kb_id.strip()]
        kb_names_map = {}
        
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            for kb_id in kb_ids:
                try:
                    # Try to fetch KB details from KB server
                    response = await client.get(
                        f"{kb_server_url}/collections/{kb_id}",
                        headers={"Authorization": f"Bearer {kb_token}"}
                    )
                    if response.status_code == 200:
                        kb_data = response.json()
                        kb_names_map[kb_id] = kb_data.get('name', kb_id)
                        logger.info(f"Resolved KB {kb_id} to name: {kb_data.get('name')}")
                    else:
                        logger.warning(f"KB {kb_id} not found in KB server (status {response.status_code})")
                        kb_names_map[kb_id] = None
                except Exception as kb_err:
                    logger.warning(f"Error fetching KB {kb_id}: {str(kb_err)}")
                    kb_names_map[kb_id] = None
        
        # Add resolved KB names to response for frontend convenience
        assistant_data['_kb_names'] = kb_names_map
        logger.info(f"Added KB name resolution: {kb_names_map}")
        
    except Exception as e:
        logger.warning(f"Failed to resolve KB names for assistant {assistant_id}: {str(e)}")
        # Non-critical error, continue without KB name resolution
```

**What it does:**
1. When fetching an assistant, checks if `RAG_collections` field exists
2. For each KB ID, queries the KB Server directly: `GET /collections/{kb_id}`
3. Extracts KB names from responses
4. Adds `_kb_names` field to response: `{"13": "Actual KB Name"}`
5. Gracefully handles errors (KB server offline, KB deleted, etc.)

### Frontend Fix

**File:** `/opt/lamb/frontend/svelte-app/src/routes/assistants/+page.svelte`

Updated KB display logic to use resolved names:

```svelte
{#each selectedAssistantData.RAG_collections.split(',') as kbId}
    {@const kb = accessibleKnowledgeBases.find(k => k.id === kbId)}
    {@const resolvedName = selectedAssistantData._kb_names?.[kbId]}
    <span class="inline-block bg-gray-200 rounded px-2 py-0.5 text-xs font-medium text-gray-700">
        {kb ? kb.name : (resolvedName || `${kbId} (Not Found)`)}
    </span>
{/each}
```

**Priority order:**
1. First, try to find KB in `accessibleKnowledgeBases` (registered KBs)
2. If not found, use `_kb_names` from backend resolution
3. If both fail, show "X (Not Found)"

---

## Benefits of This Approach

### 1. **No Database Migration Required**
- Works immediately without needing to populate `kb_registry`
- Doesn't require downtime or complex migration scripts

### 2. **Source of Truth**
- KB Server is the actual source of truth for KB data
- This solution queries it directly, ensuring accuracy

### 3. **Handles Multiple Scenarios**
- ✅ Legacy numeric KB IDs (pre-v0.2)
- ✅ New UUID-based KB IDs (v0.2+)
- ✅ KBs that were never registered in `kb_registry`
- ✅ KBs that exist in KB Server but not in LAMB database

### 4. **Backward Compatible**
- If KB is in `accessibleKnowledgeBases`, uses that (fast path)
- If not, falls back to direct resolution (slow path, but accurate)
- Existing functionality unchanged for properly registered KBs

### 5. **Graceful Degradation**
- If KB Server is offline: shows "(Not Found)" (same as before)
- If KB was deleted: shows "(Not Found)" (correct behavior)
- Non-critical errors don't break assistant display

---

## Testing Recommendations

### 1. Test Legacy KB References

```sql
-- Find assistants with KB references
SELECT id, name, RAG_collections 
FROM LAMB_assistants 
WHERE RAG_collections IS NOT NULL AND RAG_collections != '';
```

For each assistant:
1. Open assistant detail view in frontend
2. Verify KB names are displayed correctly (not "X (Not Found)")
3. Check browser console for KB resolution logs

### 2. Test KB Server Connectivity

- Stop KB Server
- Open assistant with KBs
- Should show "(Not Found)" gracefully without errors

### 3. Test Mixed Scenarios

Create test cases with:
- Assistant with registered KB (should use fast path)
- Assistant with legacy KB ID (should use resolution)
- Assistant with deleted KB (should show "Not Found")
- Assistant with multiple KBs (mix of registered and legacy)

---

## Future Improvements

### Option 1: Migration Script (Recommended for Long-Term)

Create a migration script to populate `kb_registry` from existing KB references:

```python
# Pseudo-code for migration
for assistant in get_all_assistants():
    if assistant.RAG_collections:
        for kb_id in assistant.RAG_collections.split(','):
            # Fetch KB from KB Server
            kb_data = kb_server.get_collection(kb_id)
            if kb_data:
                # Register in kb_registry if not exists
                if not kb_registry.exists(kb_id):
                    kb_registry.register(
                        kb_id=kb_id,
                        kb_name=kb_data['name'],
                        owner_user_id=get_user_id(assistant.owner),
                        organization_id=assistant.organization_id,
                        is_shared=False
                    )
```

### Option 2: Lazy Registration (Current Auto-Registration)

The KB system already has auto-registration for owned KBs. This fix ensures that even before auto-registration happens, KB names are displayed correctly.

### Option 3: Background Sync Job

Implement a background job that:
1. Runs periodically (e.g., daily)
2. Scans all assistants for KB references
3. Ensures all referenced KBs are registered
4. Cleans up stale registry entries

---

## Related Code Locations

- **Backend Assistant Router:** `/opt/lamb/backend/creator_interface/assistant_router.py` (lines ~805-850)
- **Frontend Assistant View:** `/opt/lamb/frontend/svelte-app/src/routes/assistants/+page.svelte` (lines ~1229-1237)
- **KB Server Manager:** `/opt/lamb/backend/creator_interface/kb_server_manager.py`
- **KB Registry Schema:** `/opt/lamb/backend/lamb/database_manager.py` (search for "kb_registry")

---

## Conclusion

This fix resolves the immediate issue of KBs showing as "Not Found" after v0.2 migration by implementing runtime resolution against the KB Server. The solution is production-ready, backward-compatible, and handles edge cases gracefully.

For long-term maintenance, consider implementing one of the future improvement options to reduce the overhead of runtime resolution.
