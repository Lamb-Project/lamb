# Multi-Tool Assistant Frontend Testing

## Test Environment
- **Frontend URL:** http://localhost:5173
- **Backend URL:** http://localhost:9099
- **Test User:** admin@admin.owi / admin

## Issue Found: Authentication Error

### Problem
When accessing `/assistants` or `/multi-tool-assistants`, the frontend shows:
```
Error: Invalid authentication or user not found in creator database
```

### Root Cause
The authentication token stored in the browser session is expired or invalid. The token validation fails at the Open WebUI API level with:
```
"Your session has expired or the token is invalid. Please sign in again."
```

### Solution
**The user must log out and log back in to get a fresh authentication token.**

### Fix Applied
Created the creator user `admin@admin.owi` in the LAMB creator database:
- User ID: 7
- Organization: LAMB System Organization (ID: 1)
- Role: admin
- Status: enabled

## Test Steps

### Prerequisites
1. Ensure all services are running:
   ```bash
   docker-compose ps
   ```
2. Verify the creator user exists:
   ```bash
   docker-compose exec backend python -c "from lamb.database_manager import LambDatabaseManager; db = LambDatabaseManager(); user = db.get_creator_user_by_email('admin@admin.owi'); print('User exists:', user is not None)"
   ```

### Test 1: Classic Assistant Creation

1. **Navigate to frontend:**
   - Open http://localhost:5173
   - If not logged in, login with `admin@admin.owi` / `admin`

2. **Access Assistants Page:**
   - Click "Learning Assistants" in navigation
   - Select "📚 All Assistants"
   - URL should be: http://localhost:5173/assistants

3. **Create Classic Assistant:**
   - Click "Create Assistant" button
   - Fill in the form:
     - **Name:** `test_classic_assistant`
     - **Description:** `A test classic assistant`
     - **System Prompt:** `You are a helpful assistant.`
     - **Prompt Template:** Use default or customize
   - Configure:
     - **LLM:** gpt-4o-mini
     - **RAG Processor:** No Rag (or Simple Rag if KB available)
   - Click "Save"

4. **Expected Results:**
   - Assistant is created successfully
   - Redirected to assistant list or detail view
   - No authentication errors
   - Assistant appears in "My Assistants" list

### Test 2: Multi-Tool Assistant Creation

1. **Navigate to Multi-Tool Assistants:**
   - From Learning Assistants dropdown, select "🔧 Multi-Tool Assistants"
   - Or navigate directly to: http://localhost:5173/multi-tool-assistants

2. **Create Multi-Tool Assistant:**
   - Click "Create Multi-Tool Assistant" button
   - Fill in basic information:
     - **Name:** `test_multi_tool_assistant`
     - **Description:** `A test multi-tool assistant`
     - **System Prompt:** `You are a helpful assistant that uses multiple tools.`
   - Add tools:
     - Click "Add Tool"
     - Select tool type (e.g., Simple RAG, Rubric RAG, Single File RAG)
     - Configure tool settings
     - Set placeholder name (e.g., `{context}`, `{rubric}`)
   - Configure orchestrator:
     - Select orchestrator strategy (e.g., "sequential", "parallel")
   - Set LLM and other settings
   - Click "Save"

3. **Expected Results:**
   - Multi-tool assistant is created successfully
   - Redirected to assistant list or detail view
   - No authentication errors
   - Assistant appears in multi-tool assistants list
   - Tools are properly configured

### Test 3: Verify Both Types Work

1. **List Classic Assistants:**
   - Navigate to `/assistants`
   - Verify classic assistant appears in list
   - Click on assistant to view details

2. **List Multi-Tool Assistants:**
   - Navigate to `/multi-tool-assistants`
   - Verify multi-tool assistant appears in list
   - Click on assistant to view details

3. **Expected Results:**
   - Both types of assistants are accessible
   - No errors when switching between views
   - Details load correctly for both types

## Troubleshooting

### If Authentication Error Persists

1. **Clear browser session:**
   - Open browser DevTools (F12)
   - Go to Application/Storage tab
   - Clear localStorage and sessionStorage
   - Refresh page and login again

2. **Check backend logs:**
   ```bash
   docker-compose logs backend --tail=100 | grep -i "auth\|token"
   ```

3. **Verify user exists in both databases:**
   ```bash
   # Check OWI database
   docker-compose exec backend python -c "from lamb.owi_bridge.owi_users import OwiUserManager; owi = OwiUserManager(); user = owi.get_user_by_email('admin@admin.owi'); print('OWI user:', user is not None)"
   
   # Check LAMB creator database
   docker-compose exec backend python -c "from lamb.database_manager import LambDatabaseManager; db = LambDatabaseManager(); user = db.get_creator_user_by_email('admin@admin.owi'); print('Creator user:', user is not None)"
   ```

4. **Manually create creator user if missing:**
   ```bash
   docker-compose exec backend python -c "
   from lamb.database_manager import LambDatabaseManager
   from lamb.owi_bridge.owi_users import OwiUserManager
   db = LambDatabaseManager()
   owi = OwiUserManager()
   org = db.get_organization_by_slug('lamb')
   org_id = org['id']
   user_id = db.create_creator_user('admin@admin.owi', 'Admin User', 'admin', org_id)
   if user_id:
       db.assign_organization_role(org_id, user_id, 'admin')
       print('Created creator user:', user_id)
   "
   ```

## Known Issues

1. **Token Expiration:** Tokens expire and require re-login
2. **User Sync:** Users must exist in both OWI and LAMB creator databases
3. **Email Mismatch:** Config uses `admin@owi.com` but test user is `admin@admin.owi`

## Notes

- The frontend forms load correctly even with authentication errors
- The error appears when making API calls to fetch assistants/KBs
- After fixing authentication, all features should work normally
