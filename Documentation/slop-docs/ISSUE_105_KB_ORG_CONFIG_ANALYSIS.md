# Issue #105: KB Organization-Specific Configuration Analysis

**Date:** November 10, 2025  
**Issue:** #105 - multi-kb-org-management  
**Status:** NOT IMPLEMENTED - Configuration exists but is not used  
**Impact:** High - All organizations use the same KB server regardless of configuration

---

## Executive Summary

**Finding:** While organizations CAN store KB server configuration (URL and API token), the Knowledge Base Server Manager is **NOT using** organization-specific configuration. All KB operations currently use **global environment variables** regardless of organization settings.

**Impact:**
- All organizations share the same KB server (`http://kb:9090` from env vars)
- Organization-specific KB server settings are stored but ignored
- Multi-KB-per-organization is not functional
- Issue #105's goal is not achieved

---

## Current State Analysis

### ✅ What IS Working

1. **Organization Configuration Storage**
   - Organizations can store KB server config in database
   - Schema supports `config.setups.default.knowledge_base`:
     - `server_url` (e.g., `"http://kb:9090"`)
     - `api_token` (e.g., `"0p3n-w3bu!"`)
   - Both "lamb" and "dev" orgs have KB config stored

2. **RAG Processor (Completions)**
   - `backend/lamb/completions/rag/simple_rag.py` **DOES** use org-specific KB config
   - Uses `OrganizationConfigResolver` to get KB server URL and token
   - Falls back to environment variables if org config not found
   - **This works correctly for assistant completions**

3. **Organization Config Resolver**
   - `backend/lamb/completions/org_config_resolver.py` exists
   - Has `get_knowledge_base_config()` method
   - Properly resolves org-specific KB config

### ❌ What Is NOT Working

1. **KB Server Manager (Creator Interface)**
   - `backend/creator_interface/kb_server_manager.py` uses **global env vars only**
   - `__init__` method sets:
     ```python
     self.kb_server_url = LAMB_KB_SERVER  # ❌ Global env var
     self.kb_server_token = LAMB_KB_SERVER_TOKEN  # ❌ Global env var
     ```
   - **All KB operations use these global values:**
     - List user KBs (`get_user_knowledge_bases`)
     - List shared KBs (`get_shared_knowledge_bases`)
     - Create KB
     - Upload files to KB
     - Query KB
     - Delete KB
     - Get KB details

2. **KB List Endpoints**
   - `GET /creator/knowledgebases/user` → Uses global KB server
   - `GET /creator/knowledgebases/shared` → Uses global KB server
   - No organization context passed to KB server manager

3. **Assistant Forms**
   - Create/Edit assistant forms load KB lists
   - KB lists come from endpoints above
   - Therefore, also using global KB server

---

## Detailed Code Analysis

### Current Implementation (KB Server Manager)

**File:** `backend/creator_interface/kb_server_manager.py`

```python
class KBServerManager:
    def __init__(self):
        # ❌ Uses global environment variables
        self.kb_server_url = LAMB_KB_SERVER  # From os.getenv('LAMB_KB_SERVER')
        self.kb_server_token = LAMB_KB_SERVER_TOKEN  # From os.getenv('LAMB_KB_SERVER_TOKEN')
        
    async def get_user_knowledge_bases(self, creator_user: Dict[str, Any]):
        # ...
        # ❌ Line 140: Uses self.kb_server_url (global)
        response = await client.get(
            f"{self.kb_server_url}/collections/{kb_id}",
            headers=self.get_auth_headers()  # Uses self.kb_server_token
        )
```

### Working Implementation (RAG Processor)

**File:** `backend/lamb/completions/rag/simple_rag.py`

```python
def rag_processor(messages, assistant=None):
    # ✅ Resolves organization-specific KB config
    config_resolver = OrganizationConfigResolver(assistant.owner)
    kb_config = config_resolver.get_knowledge_base_config()
    
    if kb_config:
        KB_SERVER_URL = kb_config.get("server_url")  # ✅ Org-specific
        KB_API_KEY = kb_config.get("api_token")      # ✅ Org-specific
    else:
        # Fallback to env vars
        KB_SERVER_URL = os.getenv('LAMB_KB_SERVER')
        KB_API_KEY = os.getenv('LAMB_KB_SERVER_TOKEN')
```

### Organization Config Resolver

**File:** `backend/lamb/completions/org_config_resolver.py`

```python
class OrganizationConfigResolver:
    def get_knowledge_base_config(self) -> Dict[str, Any]:
        """Get knowledge base configuration"""
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        kb_config = setup.get("knowledge_base", {})  # ✅ Returns org KB config
        
        # Fallback to env vars for system org
        if not kb_config and self.organization.get('is_system', False):
            kb_config = {
                "server_url": os.getenv('LAMB_KB_SERVER'),
                "api_token": os.getenv('LAMB_KB_SERVER_TOKEN')
            }
        return kb_config
```

---

## Database Configuration Verification

**Query:**
```sql
SELECT id, slug, name, 
       json_extract(config, '$.setups.default.knowledge_base') as kb_config 
FROM LAMB_organizations;
```

**Results:**
```
1|lamb|LAMB System Organization|{"server_url":"http://kb:9090","api_token":"0p3n-w3bu!"}
2|dev|dev|{"server_url":"http://kb:9090","api_token":"0p3n-w3bu!"}
```

✅ **Configuration is stored correctly**  
❌ **Configuration is not being used by KB Server Manager**

---

## Affected Operations

### Creator Interface KB Operations

All these operations use **global KB server** instead of org-specific:

1. **List Operations:**
   - `GET /creator/knowledgebases/user` - List owned KBs
   - `GET /creator/knowledgebases/shared` - List shared KBs

2. **CRUD Operations:**
   - `POST /creator/knowledgebases/create` - Create KB
   - `PUT /creator/knowledgebases/kb/{kb_id}` - Update KB
   - `DELETE /creator/knowledgebases/kb/{kb_id}` - Delete KB
   - `GET /creator/knowledgebases/kb/{kb_id}` - Get KB details

3. **File Operations:**
   - `POST /creator/knowledgebases/kb/{kb_id}/upload` - Upload files
   - `DELETE /creator/knowledgebases/kb/{kb_id}/file/{file_id}` - Delete file

4. **Query Operations:**
   - `GET /creator/knowledgebases/kb/{kb_id}/query` - Query KB

5. **Sharing Operations:**
   - `PUT /creator/knowledgebases/kb/{kb_id}/share` - Toggle sharing

### Frontend Operations

1. **Tools → Knowledge Bases**
   - Loads KB list via `/creator/knowledgebases/user` → Uses global KB server
   - Loads shared KBs via `/creator/knowledgebases/shared` → Uses global KB server

2. **Create Assistant Form**
   - Loads available KBs for RAG selection → Uses global KB server
   - User can only see KBs from the global KB server

3. **Edit Assistant Form**
   - Loads available KBs for RAG selection → Uses global KB server
   - Selected KBs come from global KB server only

### ✅ What DOES Use Org-Specific Config

**Only the RAG processor during assistant completions:**
- When an assistant generates a response with RAG enabled
- The RAG processor correctly resolves org-specific KB server
- Queries go to the correct org KB server
- **This is the ONLY place organization-specific KB config is used**

---

## Issue #105 Goals vs Current State

### Issue #105 Requirements

From the issue description:
> "allow the org admin to manage the kb-port and api key ... thus we have multi-kbs per lamb system, as many as one per org"

**Goal:** Each organization should be able to:
1. Configure their own KB server URL/port
2. Configure their own KB API key
3. Have their own isolated KB server
4. Manage these settings via org admin UI

### Current State

| Requirement | Status | Notes |
|-------------|--------|-------|
| Store KB config per org | ✅ DONE | Config stored in database |
| Use KB config in RAG | ✅ DONE | simple_rag.py uses org config |
| Use KB config in Creator Interface | ❌ NOT DONE | Uses global env vars |
| Org admin UI to manage KB config | ❌ NOT DONE | No UI exists |
| Multiple KB servers per LAMB | ❌ NOT FUNCTIONAL | All orgs use same KB server |

---

## Why This Matters

### Current Behavior (Broken)

**Scenario:** Organization "Engineering" configures custom KB server:
```json
{
  "knowledge_base": {
    "server_url": "http://engineering-kb.company.com:9090",
    "api_token": "engineering-secret-key"
  }
}
```

**What Happens:**
1. ❌ Engineering admin opens Tools → Knowledge Bases
2. ❌ Request goes to `http://kb:9090` (global server), not engineering server
3. ❌ Lists KBs from global server, not engineering server
4. ❌ Creating KB creates it on global server
5. ✅ BUT, when assistant runs with RAG, it correctly queries engineering server!

**Result:** KB management and assistant RAG use DIFFERENT KB servers. Data inconsistency!

### Expected Behavior (After Fix)

1. ✅ Engineering admin opens Tools → Knowledge Bases
2. ✅ Request goes to `http://engineering-kb.company.com:9090`
3. ✅ Lists KBs from engineering server
4. ✅ Creating KB creates it on engineering server
5. ✅ Assistant RAG queries engineering server
6. ✅ Consistent KB server usage everywhere

---

## Comparison with Prompt Templates

Prompt Templates router (`backend/creator_interface/prompt_templates_router.py`) has a similar pattern but doesn't need organization resolution because templates are stored in LAMB database, not an external service.

KB Server Manager needs organization resolution because it connects to an external KB server service.

---

## Solution Requirements

To fully implement Issue #105, the following changes are needed:

### 1. Modify KBServerManager (Critical)

**File:** `backend/creator_interface/kb_server_manager.py`

**Changes needed:**
- Remove global `kb_server_url` and `kb_server_token` from `__init__`
- Add method to resolve KB config per organization:
  ```python
  def _get_kb_config_for_user(self, creator_user: Dict[str, Any]) -> Dict[str, str]:
      """Resolve KB server config based on user's organization"""
      user_email = creator_user.get('email')
      config_resolver = OrganizationConfigResolver(user_email)
      kb_config = config_resolver.get_knowledge_base_config()
      
      if kb_config:
          return {
              'url': kb_config.get('server_url'),
              'token': kb_config.get('api_token')
          }
      
      # Fallback to env vars
      return {
          'url': os.getenv('LAMB_KB_SERVER', 'http://localhost:9090'),
          'token': os.getenv('LAMB_KB_SERVER_TOKEN', '0p3n-w3bu!')
      }
  ```
- Update all methods to accept `creator_user` and resolve KB config dynamically
- Update all HTTP requests to use resolved KB server URL and token

### 2. Update KB Endpoints

**File:** `backend/creator_interface/knowledges_router.py`

**Changes needed:**
- Endpoints already receive `creator_user` ✅
- Ensure `creator_user` is passed to all KB server manager methods ✅
- KB server manager will handle org resolution internally

### 3. Add Org Admin UI (Optional)

**File:** `frontend/svelte-app/src/routes/org-admin/+page.svelte`

**New feature:**
- Add "Knowledge Base Settings" section
- Fields for KB server URL
- Fields for KB API token
- Save button to update organization config
- Similar to existing "API Settings" section

### 4. Add OrganizationConfigResolver to Creator Interface

**Currently:** Only available in `backend/lamb/completions/`  
**Needed:** Make it accessible from `backend/creator_interface/`

**Options:**
- Move to shared location (e.g., `backend/lamb/org_config_resolver.py`)
- Or import from completions folder (less clean)

---

## Testing Strategy

### Verify Current Broken Behavior

1. Set up two KB servers on different ports
2. Configure "dev" org to use KB server on port 9091
3. Login as dev org user
4. Open Tools → Knowledge Bases
5. **Expected (broken):** Lists KBs from port 9090 (global)
6. **Should be (after fix):** Lists KBs from port 9091 (org-specific)

### Verify Fix

1. Apply KB server manager changes
2. Restart backend
3. Login as dev org user
4. Open Tools → Knowledge Bases
5. **Verify:** Lists KBs from port 9091 (org KB server)
6. Create a test KB
7. **Verify:** KB created on port 9091, not 9090
8. Edit assistant, check KB list
9. **Verify:** Shows KBs from port 9091
10. Run assistant with RAG
11. **Verify:** RAG queries port 9091 (should already work)

---

## Priority and Effort Estimate

### Priority: **HIGH**

**Reasons:**
- Core feature of Issue #105
- Data consistency issue (management UI vs RAG use different servers)
- Blocks multi-organization KB isolation
- Stored configuration is not being used

### Effort Estimate: **Medium** (4-8 hours)

**Breakdown:**
1. Refactor KBServerManager (3-4 hours)
   - Add org config resolution method
   - Update all methods to use dynamic config
   - Test all KB operations
   
2. Test and verify (1-2 hours)
   - Set up test KB servers
   - Test with multiple organizations
   - Verify consistency

3. Org Admin UI (2-3 hours) - Optional
   - Add KB settings section
   - Form validation
   - Save functionality

4. Documentation (1 hour)
   - Update architecture docs
   - Add KB server configuration guide

**Total:** 4-8 hours (without UI), 6-11 hours (with UI)

---

## Recommendations

### Immediate Actions

1. **Fix KBServerManager** to use organization-specific config
   - This is the critical fix
   - Restores consistency between KB management and RAG usage
   - Enables Issue #105's core functionality

2. **Add org admin UI** for KB server management
   - Currently, KB server config can only be set via database or API
   - UI would make it accessible to org admins

3. **Test with multiple KB servers**
   - Verify isolation between organizations
   - Ensure no cross-contamination

### Long-term Improvements

1. **KB Server Health Monitoring**
   - Add endpoint to check if org KB server is reachable
   - Display status in org admin UI

2. **KB Migration Tools**
   - When changing KB server, provide migration tools
   - Move existing KBs from old server to new server

3. **Per-Organization KB Quotas**
   - Track KB usage per organization
   - Enforce storage/collection limits

---

## Related Files

### Backend Files to Modify
- `backend/creator_interface/kb_server_manager.py` (main changes)
- `backend/creator_interface/knowledges_router.py` (verification)
- `backend/lamb/completions/org_config_resolver.py` (reference)

### Backend Files That Work Correctly
- `backend/lamb/completions/rag/simple_rag.py` (reference implementation)

### Frontend Files
- `frontend/svelte-app/src/routes/org-admin/+page.svelte` (add KB settings UI)
- `frontend/svelte-app/src/lib/services/knowledgeBaseService.js` (no changes needed)

---

## Conclusion

**Current State:**
- ❌ KB Server Manager uses global configuration
- ❌ All organizations share the same KB server
- ❌ Organization-specific KB config is stored but not used
- ✅ RAG processor correctly uses org-specific config

**To Fix:**
- Refactor KBServerManager to resolve KB config per organization
- Follow the pattern already implemented in simple_rag.py
- Add org admin UI for KB server management

**Impact After Fix:**
- ✅ Each organization can have its own KB server
- ✅ KB management and RAG use consistent KB server
- ✅ True multi-KB-per-organization support
- ✅ Issue #105 requirements fulfilled

---

**Report prepared by:** AI Assistant  
**Status:** Ready for implementation  
**Next Step:** Implement KBServerManager organization config resolution

