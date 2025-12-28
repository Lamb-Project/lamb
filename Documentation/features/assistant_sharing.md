# Assistant Sharing Feature

> **Parent Document:** [lamb_architecture_v2.md](../lamb_architecture_v2.md) § 8.3

## Overview

Assistant sharing allows users within an organization to share their assistants with specific colleagues. This provides fine-grained access control through a two-level permission system.

**Key Capabilities:**
- Share assistants with specific users (not organization-wide)
- Two-level permissions (organization + user level)
- Shared users get read-only access (view and chat)
- Owners retain full control (edit, delete, manage sharing)
- Real-time permission checks
- OWI group synchronization for chat access

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Assistant Sharing Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Owner clicks "Share"                                            │
│         │                                                         │
│         ▼                                                         │
│  Check permissions (org + user)                                  │
│         │                                                         │
│         ▼                                                         │
│  Show sharing modal (dual-panel)                                 │
│         │                                                         │
│         ▼                                                         │
│  PUT /lamb/v1/assistant-sharing/shares/{id}                      │
│         │                                                         │
│         ├──► Update assistant_shares table                       │
│         │                                                         │
│         └──► Sync OWI group membership                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Permission System

### Two-Level Requirements

For a user to have sharing capabilities, **BOTH** conditions must be true:

1. **Organization Level:** `config.features.sharing_enabled = true`
2. **User Level:** `user_config.can_share = true` (default: true)

### Permission Matrix

| Org `sharing_enabled` | User `can_share` | Result |
|-----------------------|------------------|--------|
| ✅ Enabled | ✅ True | ✅ User can share |
| ✅ Enabled | ❌ False | ❌ Cannot share |
| ❌ Disabled | ✅ True | ❌ Cannot share |
| ❌ Disabled | ❌ False | ❌ Cannot share |

**Rationale:** Organization admins control the feature at org level, then can selectively enable/disable for individual users.

### Access Levels

| Action | Owner | Shared User |
|--------|-------|-------------|
| View Assistant Properties | ✅ | ✅ |
| Chat with Assistant | ✅ | ✅ |
| Edit Assistant | ✅ | ❌ |
| Delete Assistant | ✅ | ❌ |
| Publish Assistant | ✅ | ❌ |
| Manage Sharing | ✅ | ❌ |

---

## Database Schema

### assistant_shares Table

```sql
CREATE TABLE assistant_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    shared_with_user_id INTEGER NOT NULL,
    shared_by_user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_by_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(assistant_id, shared_with_user_id)
);

-- Performance indexes
CREATE INDEX idx_shares_assistant ON assistant_shares(assistant_id);
CREATE INDEX idx_shares_user ON assistant_shares(shared_with_user_id);
```

**Fields:**
- `assistant_id`: The assistant being shared
- `shared_with_user_id`: User receiving access
- `shared_by_user_id`: User who shared (for audit)
- `created_at`: Timestamp of share creation

**Constraints:**
- UNIQUE prevents duplicate shares
- CASCADE deletes clean up when assistant or user is removed

### User Config (can_share permission)

Stored in `Creator_users.user_config` JSON:

```json
{
  "can_share": true,
  "preferences": {
    "language": "en"
  }
}
```

---

## API Endpoints

### Check Sharing Permission

Verify if current user can share assistants.

```http
GET /lamb/v1/assistant-sharing/check-permission
Authorization: Bearer {token}
```

**Response:**
```json
{
  "can_share": true,
  "message": "User has sharing permission"
}
```

### Get Organization Users

List users available for sharing (same organization, excludes self).

```http
GET /lamb/v1/assistant-sharing/organization-users
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "user_id": 2,
    "user_name": "Jane Smith",
    "user_email": "jane@example.com"
  },
  {
    "user_id": 3,
    "user_name": "Bob Wilson",
    "user_email": "bob@example.com"
  }
]
```

### Get Shared Users for Assistant

List users with whom an assistant is currently shared.

```http
GET /lamb/v1/assistant-sharing/shares/{assistant_id}
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "user_id": 2,
    "user_name": "Jane Smith",
    "user_email": "jane@example.com",
    "shared_by_name": "John Doe",
    "created_at": 1730908800
  }
]
```

### Update Assistant Shares (Atomic)

Set the complete list of shared users. Backend calculates additions/removals.

```http
PUT /lamb/v1/assistant-sharing/shares/{assistant_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "user_ids": [2, 3, 5]
}
```

**Response:**
```json
{
  "success": true,
  "shared_with": [2, 3, 5],
  "added": [5],
  "removed": [4]
}
```

**Behavior:**
- Accepts desired final state
- Backend calculates diff automatically
- Updates LAMB database
- Syncs OWI group membership

### Update User Sharing Permission (Admin)

Enable/disable sharing permission for a specific user.

```http
PUT /lamb/v1/assistant-sharing/user-permission/{user_id}?can_share=true
Authorization: Bearer {admin_token}
```

**Response:**
```json
{
  "success": true,
  "user_id": 2,
  "can_share": true
}
```

### Get Shared Assistants

List assistants shared with the current user.

```http
GET /creator/assistant/shared
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": 42,
    "name": "Math Tutor",
    "owner": "john@example.com",
    "owner_name": "John Doe",
    "shared_at": 1730908800,
    "description": "Helps with algebra"
  }
]
```

---

## Backend Implementation

### Access Control

In `backend/creator_interface/assistant_router.py`:

```python
# Verify Ownership OR Sharing
is_owner = assistant_data.get('owner') == creator_user['email']
is_shared = db_check.is_assistant_shared_with_user(assistant_id, creator_user['id'])

if not is_owner and not is_shared:
    raise HTTPException(status_code=404, detail="Assistant not found")
```

In `backend/creator_interface/learning_assistant_proxy.py`:

```python
def verify_assistant_access(assistant, user):
    is_owner = assistant.owner == user['email']
    if not is_owner:
        is_shared = db.is_assistant_shared_with_user(assistant.id, user['id'])
        if not is_shared:
            return False
    return True
```

### OWI Group Synchronization

When shares are updated, sync with OWI group for chat access:

```python
@router.put("/v1/assistant-sharing/shares/{assistant_id}")
async def update_assistant_shares(assistant_id: int, request: UpdateSharesRequest):
    # ... update LAMB database ...
    
    # Sync with OWI group
    assistant = db.get_assistant_by_id(assistant_id)
    if assistant.get('group_id'):
        owi_group_manager = OwiGroupManager()
        all_user_ids = [owner_id] + list(request.user_ids)
        owi_users = [db.get_owi_user_by_creator_id(uid) for uid in all_user_ids]
        owi_user_ids = [u['id'] for u in owi_users if u]
        owi_group_manager.update_group_members(assistant['group_id'], owi_user_ids)
```

---

## Frontend Integration

### Sharing Modal Component

The frontend uses a dual-panel modal (similar to "Manage Ollama Models"):

```svelte
<!-- AssistantSharingModal.svelte -->
<div class="modal-container">
  <div class="dual-panel">
    <!-- Left: Currently Shared Users -->
    <div class="panel">
      <h3>Shared Users ({sharedUsers.length})</h3>
      <input type="search" bind:value={searchShared} placeholder="Search...">
      <div class="user-list">
        {#each filteredSharedUsers as user}
          <label class="user-item">
            <input type="checkbox" bind:group={selectedShared} value={user.user_id}>
            <span>{user.user_name}</span>
            <span class="email">{user.user_email}</span>
          </label>
        {/each}
      </div>
    </div>
    
    <!-- Center: Move Buttons -->
    <div class="move-buttons">
      <button onclick={moveAllToShared}>≪</button>
      <button onclick={moveToShared}>&lt;</button>
      <button onclick={moveToAvailable}>&gt;</button>
      <button onclick={moveAllToAvailable}>≫</button>
    </div>
    
    <!-- Right: Available Users -->
    <div class="panel">
      <h3>Available Users ({availableUsers.length})</h3>
      <input type="search" bind:value={searchAvailable} placeholder="Search...">
      <div class="user-list">
        {#each filteredAvailableUsers as user}
          <label class="user-item">
            <input type="checkbox" bind:group={selectedAvailable} value={user.user_id}>
            <span>{user.user_name}</span>
          </label>
        {/each}
      </div>
    </div>
  </div>
  
  <div class="modal-actions">
    <button class="btn-primary" onclick={saveChanges}>Save Changes</button>
    <button class="btn-secondary" onclick={onClose}>Cancel</button>
  </div>
</div>
```

### Tab Visibility

The "Share" tab only appears if user has permission:

```javascript
async function checkSharingPermission() {
    const response = await fetch(
        `${API_URL}/lamb/v1/assistant-sharing/check-permission`,
        { headers: { 'Authorization': `Bearer ${token}` } }
    );
    if (response.ok) {
        const data = await response.json();
        canShare = data.can_share || false;
    }
}

// In template
{#if canShare && isOwner}
  <button onclick={() => detailSubView = 'share'}>Share</button>
{/if}
```

### Save Logic

```javascript
async function saveChanges() {
    saving = true;
    errorMessage = '';
    
    const userIds = sharedUsers.map(u => u.user_id);
    
    try {
        const response = await fetch(
            `${API_URL}/lamb/v1/assistant-sharing/shares/${assistant.id}`,
            {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_ids: userIds })
            }
        );
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save');
        }
        
        onSaved();  // Refresh parent
        onClose();  // Close modal
    } catch (error) {
        errorMessage = error.message;
    } finally {
        saving = false;
    }
}
```

---

## Configuration

### Organization Level

Enable sharing for the organization:

```json
{
  "config": {
    "features": {
      "sharing_enabled": true
    }
  }
}
```

Set via: `PUT /creator/admin/organizations/{slug}/config`

### User Level

Default: `can_share = true` (users can share by default)

Disable for specific user via Admin UI or API:
`PUT /lamb/v1/assistant-sharing/user-permission/{user_id}?can_share=false`

---

## Usage Examples

### Share an Assistant

1. Owner opens assistant details
2. Clicks "Share" tab
3. Clicks "Manage Shared Users"
4. Selects users from "Available Users" panel
5. Clicks move button to add to "Shared Users"
6. Clicks "Save Changes"

### Access Shared Assistant

1. User navigates to "Shared Assistants" view
2. Sees list of assistants shared with them
3. Clicks "View" to see details (read-only)
4. Clicks "Chat" to interact with assistant

### Admin: Disable User Sharing

1. Org admin goes to User Management
2. Finds user in list
3. Toggles "Can Share" switch off
4. User can no longer share their assistants

---

## Security Considerations

### Authorization Checks

Every sharing operation verifies:
1. User is authenticated (valid JWT)
2. User has sharing permission (org + user level)
3. User owns the assistant being shared
4. Target users are in same organization

### Cross-Organization Protection

- Users can only share with organization members
- Cross-organization sharing is not supported
- System organization users cannot be shared with

### Audit Trail

Operations are logged with:
- Sharer's email
- Affected assistant ID
- User IDs added/removed
- Timestamp
- Success/failure status

---

## Differences from KB Sharing

| Aspect | KB Sharing | Assistant Sharing |
|--------|-----------|-------------------|
| **Scope** | Organization-wide (all or none) | Specific users |
| **Protection** | Cannot unshare if KB in use | No protection needed |
| **OWI Integration** | None | Group synchronization |
| **UI Pattern** | Simple toggle | Dual-panel modal |
| **Permission System** | None | Two-level (org + user) |

**Design Rationale:** Knowledge Bases are document collections that multiple assistants might reference, so organization-wide sharing is appropriate. Assistants are more personal and specialized, so user-specific sharing provides better control.

---

## Troubleshooting

### "Share" Tab Not Visible

1. Check organization has `sharing_enabled: true`
2. Check user has `can_share: true` in user_config
3. Verify user is the assistant owner (not shared user)

### Changes Not Saving

1. Check network requests for errors
2. Verify target users are in same organization
3. Check for duplicate share attempts

### Shared User Can't Access

1. Verify share was saved (check `assistant_shares` table)
2. Check OWI group membership was synced
3. Verify user can login to OWI

### Chat Not Working for Shared User

1. Verify assistant's OWI group includes shared user
2. Check `group_id` is set on assistant
3. Manually sync group: re-save sharing

---

*Last Updated: December 27, 2025*

