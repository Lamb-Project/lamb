# Authentication Issue Investigation

## Date: December 11, 2025

## Issue
Frontend shows error: `"Invalid authentication or user not found in creator database"` when accessing `/assistants` or `/multi-tool-assistants`.

## Investigation

### Error Flow
1. Frontend makes API call to `/creator/assistant/get_assistants`
2. Backend receives request with Authorization header containing JWT token
3. Backend calls `get_creator_user_from_token()` in `creator_interface/assistant_router.py`
4. Function calls `owi_user_manager.get_user_auth(auth_header)` to validate token
5. `get_user_auth()` makes request to Open WebUI API: `GET http://openwebui:8080/api/v1/auths/`
6. Open WebUI returns 401: `"Your session has expired or the token is invalid. Please sign in again."`
7. Backend returns 401 to frontend with message: `"Invalid authentication or user not found in creator database"`

### Root Causes Identified

#### 1. Expired/Invalid Token (Primary Issue)
- The JWT token stored in browser session is expired or invalid
- Token validation fails at Open WebUI API level
- **Solution:** User must log out and log back in to get fresh token

#### 2. Missing Creator User (Secondary Issue - Fixed)
- User `admin@admin.owi` existed in Open WebUI database but not in LAMB creator database
- Even with valid token, authentication would fail because creator user lookup returns None
- **Solution:** Created creator user in LAMB database:
  ```python
  user_id = db.create_creator_user('admin@admin.owi', 'Admin User', 'admin', org_id)
  db.assign_organization_role(org_id, user_id, 'admin')
  ```

### Code Flow Analysis

#### Authentication Function: `get_creator_user_from_token()`
**Location:** `backend/creator_interface/assistant_router.py:167`

```python
def get_creator_user_from_token(auth_header: str) -> Optional[Dict[str, Any]]:
    # 1. Validate token with OWI
    user_auth = owi_user_manager.get_user_auth(auth_header)
    if not user_auth:
        return None  # Token invalid/expired
    
    # 2. Extract email from token
    user_email = user_auth.get("email", "")
    
    # 3. Look up creator user in LAMB database
    creator_user = db_manager.get_creator_user_by_email(user_email)
    if not creator_user:
        return None  # User not in creator database
    
    return creator_user
```

#### Token Validation: `get_user_auth()`
**Location:** `backend/lamb/owi_bridge/owi_users.py:675`

```python
def get_user_auth(self, token) -> Optional[Dict]:
    # Makes HTTP request to Open WebUI API
    response = requests.get(
        f"{self.OWI_API_BASE_URL}/auths/",
        headers={'Authorization': f'Bearer {clean_token}'}
    )
    # Returns None if status != 200
    return response.json() if response.status_code == 200 else None
```

## Fixes Applied

### Fix 1: Created Missing Creator User
```bash
docker-compose exec backend python -c "
from lamb.database_manager import LambDatabaseManager
db = LambDatabaseManager()
org = db.get_organization_by_slug('lamb')
org_id = org['id']
user_id = db.create_creator_user('admin@admin.owi', 'Admin User', 'admin', org_id)
db.assign_organization_role(org_id, user_id, 'admin')
"
```

**Result:** Creator user now exists in LAMB database with:
- Email: `admin@admin.owi`
- Name: `Admin User`
- Organization: LAMB System Organization (ID: 1)
- Role: admin
- Status: enabled

### Fix 2: User Action Required
**User must log out and log back in** to get a fresh authentication token.

## Verification

### Check Creator User Exists
```bash
docker-compose exec backend python -c "
from lamb.database_manager import LambDatabaseManager
db = LambDatabaseManager()
user = db.get_creator_user_by_email('admin@admin.owi')
print('User exists:', user is not None)
print('User:', user)
"
```

### Check OWI User Exists
```bash
docker-compose exec backend python -c "
from lamb.owi_bridge.owi_users import OwiUserManager
owi = OwiUserManager()
user = owi.get_user_by_email('admin@admin.owi')
print('OWI user exists:', user is not None)
"
```

## Recommendations

### Short Term
1. ✅ Create missing creator users when they don't exist
2. ⚠️ User must log out/in to refresh expired tokens
3. ✅ Document authentication flow and troubleshooting steps

### Long Term Improvements
1. **Auto-create creator users:** When a user logs in with valid OWI credentials but no creator user exists, automatically create one
2. **Token refresh mechanism:** Implement token refresh endpoint to avoid requiring full re-login
3. **Better error messages:** Distinguish between "token expired" and "user not found" errors
4. **User sync on login:** Ensure creator user exists during login flow

### Code Changes Needed

#### Option 1: Auto-create on Login
Modify `UserCreatorManager.verify_user()` to create creator user if missing:
```python
# After successful OWI verification
creator_user = db_manager.get_creator_user_by_email(email)
if not creator_user:
    # Auto-create creator user
    org = db_manager.get_organization_by_slug('lamb')
    user_id = db_manager.create_creator_user(email, name, password, org['id'])
```

#### Option 2: Auto-create on Token Validation
Modify `get_creator_user_from_token()` to create user if missing:
```python
creator_user = db_manager.get_creator_user_by_email(user_email)
if not creator_user:
    # Auto-create from OWI user data
    org = db_manager.get_organization_by_slug('lamb')
    user_id = db_manager.create_creator_user(
        user_email, 
        user_auth.get('name', 'User'),
        '',  # No password needed, already authenticated
        org['id']
    )
    creator_user = db_manager.get_creator_user_by_email(user_email)
```

## Related Files
- `backend/creator_interface/assistant_router.py` - Authentication helper
- `backend/lamb/owi_bridge/owi_users.py` - OWI token validation
- `backend/lamb/database_manager.py` - Creator user management
- `backend/creator_interface/main.py` - Login endpoint

## Test Scripts
See `test_assistant_creation.md` for manual testing steps.
