# "Shared with Me" Tab - Critical Bug Fix

**Date**: November 6, 2025  
**Status**: ✅ FIXED

## Issue Report

Admin user (admin@dev.com) was seeing empty "Shared with Me" tab despite database showing assistants 8 and 9 were shared with them by u2@dev.com.

## Investigation Steps

### 1. Database Verification

```sql
-- Confirmed shares exist in database
SELECT * FROM LAMB_assistant_shares;
```

Results:
- Row 3: assistant 8 shared with user 2 (admin@dev.com) by user 4 (u2@dev.com) ✓
- Row 6: assistant 9 shared with user 2 (admin@dev.com) by user 4 (u2@dev.com) ✓

### 2. User Mapping Verification

```sql
-- OWI user → Creator_user mapping
SELECT id, user_email FROM LAMB_Creator_users WHERE user_email = 'admin@dev.com';
```

Result: User ID 2 ✓

### 3. API Test

```bash
curl http://localhost:9099/lamb/v1/assistant-sharing/shared-with-me \
  -H "Authorization: Bearer ..."
```

Result: `{"assistants":[],"count":0}` ❌

### 4. Backend Logs

Added debug logging revealed:
- ✅ User ID correctly identified as 2
- ✅ Query method called
- ❌ SQL error: `"no such column: a.published"`

## Root Cause

The SQL query in `get_assistants_shared_with_user` was attempting to SELECT columns that **do not exist** in the `assistants` table schema:

```sql
SELECT 
    a.published,        -- ❌ Column doesn't exist!
    a.published_at,     -- ❌ Column doesn't exist!
    a.group_id,         -- ❌ Column doesn't exist!
    a.group_name,       -- ❌ Column doesn't exist!
    ...
FROM LAMB_assistant_shares s
JOIN LAMB_assistants a ON s.assistant_id = a.id
```

### Actual `assistants` Table Schema

```
id, organization_id, name, description, owner, 
api_callback, system_prompt, prompt_template,
RAG_endpoint, RAG_Top_k, RAG_collections,
pre_retrieval_endpoint, post_retrieval_endpoint,
created_at, updated_at
```

Missing columns: `published`, `published_at`, `group_id`, `group_name`

## Solution

### Fix Applied

**File**: `backend/lamb/database_manager.py`  
**Method**: `get_assistants_shared_with_user` (Lines 5208-5279)

1. Removed non-existent columns from SELECT statement
2. Adjusted row index mapping in the result dictionary

**Before** (Lines 5230-5250):
```python
SELECT 
    a.published,      # Index 12 - doesn't exist
    a.published_at,   # Index 13 - doesn't exist
    a.group_id,       # Index 14 - doesn't exist
    a.group_name,     # Index 15 - doesn't exist
    s.shared_at,      # Index 16
    s.shared_by_user_id,  # Index 17
    ...
```

**After** (Lines 5230-5246):
```python
SELECT 
    s.shared_at,      # Index 12 ✓
    s.shared_by_user_id,  # Index 13 ✓
    u.user_email as shared_by_email,  # Index 14 ✓
    u.user_name as shared_by_name     # Index 15 ✓
```

## Verification

### Database Query (Manual)
```sql
SELECT a.id, a.name FROM LAMB_assistant_shares s
JOIN LAMB_assistants a ON s.assistant_id = a.id
WHERE s.shared_with_user_id = 2;
```

Result: Returns assistants 8 and 9 ✓

### API Response (After Fix)
```json
{
  "assistants": [
    {"id": 9, "name": "4_shared-2", ...},
    {"id": 8, "name": "4_shared", ...}
  ],
  "count": 2
}
```

### UI Display (After Fix)

"Shared with Me" tab now shows:
- ✅ **4_shared-2** (ID: 9) - Shared with you
- ✅ **4_shared** (ID: 8) - Shared with you

## Additional Improvements Needed

1. **Tab Visibility Logic**: Currently, the "Shared with Me" tab is always visible. It should be hidden when there are no shared assistants.

2. **Frontend Implementation**: The AssistantsList component with `showShared` prop needs proper Svelte 5 implementation to display shared assistants correctly.

## Files Modified

- ✅ `backend/lamb/database_manager.py` - Fixed SQL query
- ✅ `ASSISTANT_SHARING_SCHEMA.md` - Updated with bug fix documentation

## Summary

The critical bug preventing "Shared with Me" from displaying assistants was a SQL error caused by attempting to SELECT non-existent columns. The fix was straightforward: remove those columns from the query and adjust the row mapping accordingly.

**Status: RESOLVED** ✅

Assistants shared with admin@dev.com are now correctly displayed in the "Shared with Me" tab.

