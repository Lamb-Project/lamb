# Assistant Sharing Database Schema Analysis

## Current Schema

```mermaid
erDiagram
    Creator_users ||--o{ assistant_shares : "shared_with"
    Creator_users ||--o{ assistant_shares : "shared_by"
    assistants ||--o{ assistant_shares : "has"
    organizations ||--o{ Creator_users : "has"
    
    Creator_users {
        int id PK
        string user_email UK
        string user_name
        string password_hash
        int organization_id FK
        string user_type "creator or end_user"
        json user_config "can_share flag"
        int created_at
    }
    
    assistants {
        int id PK
        string name
        string owner "email of owner"
        int organization_id FK
        json config
        int created_at
    }
    
    assistant_shares {
        int id PK
        int assistant_id FK
        int shared_with_user_id FK
        int shared_by_user_id FK
        int shared_at
        UK assistant_id_shared_with "UNIQUE(assistant_id, shared_with_user_id)"
    }
    
    organizations {
        int id PK
        string slug UK
        string name
        json config "features.sharing_enabled"
        int created_at
    }
    
    owi_users {
        string id PK
        string email
        string name
        string role "admin or user"
    }
    
    owi_groups {
        string id PK
        string name
        json user_ids "JSON array"
    }
```

## Issue Identified

### Problem
**Admins are appearing in the organization users list for sharing.**

The query in `get_organization_users_endpoint` (line 210 in `assistant_sharing_router.py`) does:

```python
users = db_manager.get_organization_users(org_id)
```

The database query in `get_organization_users` (line 1802-1841 in `database_manager.py`) returns:

```sql
SELECT u.id, u.user_email, u.user_name, 
       COALESCE(r.role, 'member') as role, 
       COALESCE(r.created_at, u.created_at) as joined_at,
       u.user_type
FROM Creator_users u
LEFT JOIN organization_roles r ON u.id = r.user_id AND r.organization_id = ?
WHERE u.organization_id = ?
ORDER BY joined_at
```

**The issue**: This query returns ALL users, including:
- Admins (role = 'admin' in OWI)
- Regular users (role = 'user' in OWI)

### Why This Is Wrong

1. **Admins already have access to all assistants** in their organization
2. **Sharing with an admin is redundant** and confusing
3. **The UI should only show non-admin users** for sharing

## Solution

### Fix #1: Filter Out Admins in API

Modify `get_organization_users_endpoint` to exclude admin users:

```python
# Filter out current user AND admin users
for user in users:
    if user['id'] != current_user_id:
        # Check if user is admin in OWI
        user_manager = OwiUserManager()
        owi_user = user_manager.get_user_by_email(user['email'])
        
        # Skip admins (they already have access to all assistants)
        if owi_user and owi_user.get('role') == 'admin':
            continue
            
        result.append(UserResponse(
            id=user['id'],
            name=user['name'],
            email=user['email'],
            user_type=user.get('user_type', 'creator')
        ))
```

### Fix #2: Add Database Method

Add a dedicated method to get non-admin organization users:

```python
def get_organization_users_for_sharing(self, organization_id: int, exclude_admins: bool = True) -> List[Dict[str, Any]]:
    """Get users in organization, optionally excluding admins"""
    # ... implementation
```

### Fix #3: Validate at Share Time

Add validation in `update_assistant_shares` to prevent sharing with admins:

```python
# Validate user IDs - don't allow sharing with admins
user_manager = OwiUserManager()
for user_id in desired_user_ids:
    user = db_manager.get_creator_user_by_id(user_id)
    if user:
        owi_user = user_manager.get_user_by_email(user['email'])
        if owi_user and owi_user.get('role') == 'admin':
            raise HTTPException(
                status_code=400,
                detail=f"Cannot share with admin users: {user['email']}"
            )
```

## Recommended Fix

**Use Fix #1** (Filter in API endpoint) combined with **Fix #3** (validation).

This approach:
- ✅ Prevents admins from appearing in UI
- ✅ Validates at share time
- ✅ No database schema changes needed
- ✅ Clear error messages
- ✅ Works with existing OWI integration

## Implementation Status

### ✅ COMPLETED

1. ~~**API Filter**~~ - Reverted (admins CAN be shared with)
2. ~~**Share Validation**~~ - Reverted (admins are valid share targets)
3. **BUG FIX: SQL Query Error** - Fixed `get_assistants_shared_with_user` query

### Critical Bug Fix (November 6, 2025)

**Issue**: "Shared with Me" tab showing no assistants despite database having shares

**Root Cause**: The SQL query was attempting to SELECT columns that don't exist in the `assistants` table:
- `published` (doesn't exist)
- `published_at` (doesn't exist)  
- `group_id` (doesn't exist)
- `group_name` (doesn't exist)

This caused SQL error: `"no such column: a.published"`

**Fix**: Removed non-existent columns from SELECT query and adjusted row mapping

**File**: `backend/lamb/database_manager.py`  
**Method**: `get_assistants_shared_with_user` (Line 5208-5279)

## Testing Checklist

After fix:
- [x] "Shared with Me" tab displays assistants correctly
- [x] Database shares are retrieved successfully
- [x] SQL query no longer errors on missing columns
- [x] Admin users CAN appear in "Available Users" (as intended)
- [x] Admin users CAN be shared with (correct behavior)
- [x] Admins only see explicitly shared assistants in "Shared with Me"

## ✅ CORRECTED: Expected Behavior

### Admin User Permissions (Two Contexts)

#### Context 1: Org-Admin Interface (`/org-admin?view=assistants`)
- ✅ Admins CAN manage sharing for ANY assistant in the organization
- ✅ "Manage Sharing" button available for all assistants
- ✅ Admin can add/remove users from any assistant's share list

#### Context 2: Regular Assistants Interface (`/assistants`)
- ✅ Admins behave EXACTLY like creator users
- ✅ Admins only see assistants in "Shared with Me" if explicitly shared WITH them
- ✅ An explicit `assistant_shares` row must exist with admin's user_id as `shared_with_user_id`
- ✅ Admins CAN be shared with (appear in "Available Users" panel)
- ✅ Admins DO NOT automatically see all org assistants as shared

### Database Query Behavior

**Query for "Shared with Me"** (Line 5226-5253 in `database_manager.py`):
```sql
SELECT ...
FROM assistant_shares s
JOIN assistants a ON s.assistant_id = a.id
WHERE s.shared_with_user_id = ?
```

✅ **CORRECT**: This query ONLY returns assistants with explicit share rows
✅ **CORRECT**: Admins are NOT automatically included
✅ **CORRECT**: Admin must be explicitly shared with to see assistant

### Sharing Modal Behavior

1. **Available Users Panel**: Includes ALL org users (including admins)
   - ✅ Admins CAN be selected and shared with
   - ✅ No special filtering based on role
   
2. **Shared Users Panel**: Shows users with explicit share rows
   - ✅ May include admins if someone shared with them
   - ✅ Admins can be removed from shares like any user

### The Key Rule

**Being an admin gives privileges to MANAGE sharing (in org-admin UI), NOT automatic access to assistants.**

- Admin managing shares: Use `/org-admin?view=assistants` → "Manage Sharing"
- Admin viewing shared assistants: Use `/assistants?view=shared` → Only see explicitly shared assistants

