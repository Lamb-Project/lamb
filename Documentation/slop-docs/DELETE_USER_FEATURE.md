# Delete User Feature Implementation

## Overview
This feature allows administrators to safely delete disabled users from the LAMB system, with built-in safety checks to prevent accidental data loss.

## Safety Requirements

### Two-Level Safety Check
1. **User Must Be Disabled First**: The delete option only appears for disabled users
2. **No Dependencies**: User must have no associated resources (assistants or knowledge bases)

### What Gets Checked
- **Assistants**: Count of assistants owned by the user
- **Knowledge Bases**: Count of knowledge bases owned by the user

If any dependencies exist, deletion is blocked and the admin is shown:
- Count of each dependency type
- List of resource names (up to 5 per type)
- Clear instruction to delete or reassign resources first

## Implementation Details

### Backend Changes

#### 1. Database Manager (`/backend/lamb/database_manager.py`)

**New Methods:**

```python
def check_user_dependencies(self, user_id: int) -> Dict[str, Any]:
    """
    Check if a user has any dependencies (assistants or knowledge bases)
    
    Returns:
        - has_dependencies (bool): True if user has any dependencies
        - assistant_count (int): Number of assistants owned by user
        - kb_count (int): Number of knowledge bases owned by user
        - assistants (List[Dict]): List of assistant names and IDs
        - kbs (List[Dict]): List of KB names and IDs
    """
```

```python
def delete_user_safe(self, user_id: int) -> Tuple[bool, Optional[str]]:
    """
    Safely delete a user after checking they are disabled and have no dependencies
    
    Safety Checks:
    1. User exists
    2. User is disabled (enabled=0)
    3. User has no assistants
    4. User has no knowledge bases
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
```

#### 2. Creator Interface API (`/backend/creator_interface/main.py`)

**New Endpoints:**

```
DELETE /creator/admin/users/{user_id}
```
- Deletes a disabled user with no dependencies
- Admin only
- Returns 400 if user is enabled or has dependencies
- Returns 403 if trying to delete own account

```
GET /creator/admin/users/{user_id}/dependencies
```
- Checks user dependencies before deletion
- Returns detailed dependency information
- Admin only
- Used by frontend to show dependency details

### Frontend Changes

#### 1. Admin Service (`/frontend/svelte-app/src/lib/services/adminService.js`)

**New Functions:**

```javascript
export async function checkUserDependencies(token, userId)
```
- Fetches dependency information for a user

```javascript
export async function deleteUser(token, userId)
```
- Deletes a user (must be disabled and have no dependencies)

#### 2. Admin Page (`/frontend/svelte-app/src/routes/admin/+page.svelte`)

**New UI Elements:**

1. **Delete Button**: 
   - Only visible for disabled users
   - Not shown for current user (can't delete self)
   - Red trash icon in the Actions column

2. **Delete Confirmation Modal**:
   - Shows user details (name, email)
   - Automatically checks dependencies when opened
   - Shows loading state while checking
   - If dependencies exist:
     - Red warning box with "Cannot delete" message
     - Lists assistants (up to 5, with count)
     - Lists knowledge bases (up to 5, with count)
     - Delete button is disabled
   - If no dependencies:
     - Green confirmation box
     - Delete button is enabled
   - Warning about action being permanent

## User Flow

### Admin Deletes a User

1. **Navigate to User Management**
   - Go to Admin Panel → User Management

2. **Disable User** (if not already disabled)
   - Click the disable button (red user icon)
   - Confirm the disable action
   - User status changes to "Disabled"

3. **Delete Button Appears**
   - Delete button (trash icon) appears for disabled user
   - Button is only visible for disabled users

4. **Click Delete**
   - Modal opens showing user information
   - System automatically checks for dependencies

5. **Two Possible Outcomes:**

   **A. User Has Dependencies:**
   - Red warning box appears
   - Shows list of assistants and/or knowledge bases
   - Delete button is disabled
   - Admin must:
     - Go to each resource and delete or reassign it
     - Come back and try again

   **B. User Has No Dependencies:**
   - Green confirmation box appears
   - Delete button is enabled
   - Admin clicks "Delete"
   - User is permanently removed

## API Examples

### Check Dependencies
```bash
curl -X GET 'http://localhost:9099/creator/admin/users/123/dependencies' \
  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'
```

Response (has dependencies):
```json
{
  "has_dependencies": true,
  "assistant_count": 2,
  "kb_count": 1,
  "assistants": [
    {"id": 45, "name": "Math Tutor"},
    {"id": 67, "name": "Writing Assistant"}
  ],
  "kbs": [
    {"id": "uuid-abc", "name": "Course Materials"}
  ]
}
```

Response (no dependencies):
```json
{
  "has_dependencies": false,
  "assistant_count": 0,
  "kb_count": 0,
  "assistants": [],
  "kbs": []
}
```

### Delete User
```bash
curl -X DELETE 'http://localhost:9099/creator/admin/users/123' \
  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'
```

Success:
```json
{
  "success": true,
  "message": "User deleted successfully",
  "data": {
    "user_id": "123"
  }
}
```

Error (user not disabled):
```json
{
  "detail": "User must be disabled before deletion"
}
```

Error (has dependencies):
```json
{
  "detail": "User has dependencies: 2 assistant(s), 1 knowledge base(s). Please delete or reassign these resources first."
}
```

## Database Impact

### What Gets Deleted
- User record from `Creator_users` table
- Related records in `organization_roles` (via CASCADE)

### What Remains
- Assistants remain (if any existed, deletion would be blocked)
- Knowledge bases remain (if any existed, deletion would be blocked)
- Chat history and analytics remain

## Security Considerations

1. **Admin Only**: Only system admins can delete users
2. **Cannot Delete Self**: Admins cannot delete their own account
3. **Two-Step Process**: Must disable first, then delete
4. **Dependency Prevention**: Cannot delete users with active resources
5. **Permanent Action**: No undo, clear warnings in UI

## Testing Checklist

- [ ] Delete enabled user (should fail with "must be disabled" error)
- [ ] Delete disabled user with assistants (should show dependency warning)
- [ ] Delete disabled user with knowledge bases (should show dependency warning)
- [ ] Delete disabled user with both (should show both dependencies)
- [ ] Delete disabled user with no dependencies (should succeed)
- [ ] Try to delete own account (delete button shouldn't appear)
- [ ] Non-admin tries to delete user (should get 403 error)
- [ ] Delete button only appears for disabled users in UI

## Future Enhancements

Potential improvements for future versions:

1. **Bulk Delete**: Allow deleting multiple disabled users at once
2. **Resource Reassignment**: Option to reassign resources to another user before deletion
3. **Soft Delete**: Archive users instead of permanent deletion
4. **Delete Queue**: Schedule users for deletion after grace period
5. **Audit Log**: Log all deletion attempts with timestamps and reasons
6. **Export User Data**: Download user's data before deletion (GDPR compliance)

## Files Modified

### Backend
- `/opt/lamb/backend/lamb/database_manager.py`
  - Added `check_user_dependencies()`
  - Added `delete_user_safe()`

- `/opt/lamb/backend/creator_interface/main.py`
  - Added `DELETE /creator/admin/users/{user_id}`
  - Added `GET /creator/admin/users/{user_id}/dependencies`

### Frontend
- `/opt/lamb/frontend/svelte-app/src/lib/services/adminService.js`
  - Added `checkUserDependencies()`
  - Added `deleteUser()`

- `/opt/lamb/frontend/svelte-app/src/routes/admin/+page.svelte`
  - Added delete button to actions column
  - Added delete confirmation modal with dependency checking
  - Added state management for delete flow

## Date Implemented
December 29, 2025
