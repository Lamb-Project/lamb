# Knowledge Base ID Mismatch Fix

## Problem Summary

When viewing assistant details, the Knowledge Bases showed "2 (Not Found)" even though:
- The assistant had `RAG_collections = "2"` 
- A KB with ID "2" existed in the LAMB registry
- The backend claimed to return 1 owned KB
- The KB belonged to the correct user and organization

## Root Cause

**ID Format Mismatch Between LAMB Registry and KB Server Responses**

The issue was that:
1. **LAMB Registry** stores KB IDs as simple integers or strings (e.g., "2")
2. **KB Server** may return collections with different ID formats (e.g., UUIDs)
3. When the backend fetched KB details from the KB server, it used the **KB server's ID** instead of the **LAMB registry ID**
4. This caused a mismatch when the frontend tried to match assistant's `RAG_collections` with the fetched KB list

### Code Locations

**File**: `backend/creator_interface/kb_server_manager.py`

**Functions Affected:**
- `get_user_knowledge_bases()` - Line 143-178
- `get_org_shared_knowledge_bases()` - Line 238-270

## The Fix

Added explicit ID assignment to ensure consistency:

```python
# CRITICAL FIX: Use the kb_id from LAMB registry, not from KB server
# The KB server may return a different ID format (UUID vs integer)
# We must use the LAMB registry ID for consistency with RAG_collections
kb_data['id'] = kb_id
```

### Changes Made:

1. **Owned KBs** (`kb_server_manager.py` line 149):
   - Added: `kb_data['id'] = kb_id` 
   - This ensures the ID returned to frontend matches the LAMB registry

2. **Shared KBs** (`kb_server_manager.py` line 244):
   - Added: `kb_data['id'] = kb_id`
   - Same fix for organization-shared KBs

## Why This Fixes the Issue

**Before:**
```
1. Assistant has RAG_collections="2"
2. Backend queries LAMB registry for kb_id="2"
3. Backend queries KB server: GET /collections/2
4. KB server returns: {"id": "some-uuid-here", "name": "test", ...}
5. Frontend receives KB with id="some-uuid-here"
6. Frontend tries to match "2" with "some-uuid-here" ❌ MISMATCH
7. Result: "2 (Not Found)"
```

**After:**
```
1. Assistant has RAG_collections="2"
2. Backend queries LAMB registry for kb_id="2"
3. Backend queries KB server: GET /collections/2
4. KB server returns: {"id": "some-uuid-here", "name": "test", ...}
5. Backend OVERWRITES id: kb_data['id'] = "2" ✅ FIX APPLIED
6. Frontend receives KB with id="2"
7. Frontend matches "2" with "2" ✅ SUCCESS
8. Result: KB displays correctly
```

## Testing Instructions

1. **Restart the backend**:
   ```bash
   cd /opt/lamb/backend
   pkill -f "python.*main.py"
   sleep 2
   python main.py &
   ```

2. **Refresh the browser** at http://localhost:5173/assistants?view=detail&id=5

3. **Expected Result**: 
   - Knowledge Bases should show "test" (or 1 KB) instead of "2 (Not Found)"
   - The KB selection should be properly displayed

## Impact

**Affected Features:**
- ✅ Viewing assistant details with KBs
- ✅ Editing assistant KB selections  
- ✅ Creating assistants with KBs
- ✅ Sharing KBs across organization

**Why This Happened:**
- The LAMB registry uses simple integer IDs for KBs
- The KB server might return different ID formats in its responses
- The backend was trusting the KB server's ID instead of enforcing the registry ID
- This caused a mismatch when the frontend compared stored IDs with fetched IDs

## Prevention

To prevent this in the future:
1. **Always use LAMB registry IDs** as the source of truth
2. **Never trust external service IDs** (like KB server) without validation
3. **Enforce ID consistency** when bridging LAMB database with external services

## Related Issues

This fix resolves:
- Frontend showing "X (Not Found)" for KBs
- KBs not being selectable when editing assistants
- Organization-scoped KBs not displaying correctly

## Technical Details

The fix is minimal and surgical:
- 2 lines added (one for owned KBs, one for shared KBs)
- No changes to database schema
- No changes to API contracts
- Pure data normalization fix

**Risk Level**: Low
- The change only affects how IDs are returned to frontend
- No changes to how IDs are stored or queried
- Backward compatible with existing data

