# End User Feature Documentation

**Version:** 1.0  
**Date:** October 2025  
**Status:** Implemented

---

## Overview

The **End User** feature extends LAMB's user management system to support two distinct user types:
- **Creator Users**: Full access to the creator interface for managing assistants
- **End Users**: Direct access only to Open WebUI for interacting with assistants

This feature allows administrators to create users who can interact with published assistants without having access to the creation and management interfaces.

---

## User Type Comparison

| Feature | Creator User | End User |
|---------|--------------|----------|
| Login to LAMB | ✅ Yes | ✅ Yes |
| Access Creator Interface | ✅ Yes | ❌ No (auto-redirected) |
| Create Assistants | ✅ Yes | ❌ No |
| Manage Knowledge Bases | ✅ Yes | ❌ No |
| Use Published Assistants | ✅ Yes (via OWI) | ✅ Yes (via OWI) |
| Belongs to Organization | ✅ Yes | ✅ Yes |
| Login Destination | Creator Interface | Open WebUI (automatic) |

---

## Implementation Details

### Database Schema Changes

**Creator_users Table:**
```sql
CREATE TABLE Creator_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    user_email TEXT NOT NULL UNIQUE,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
    user_config JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

**Migration:**
- Existing databases are automatically migrated on startup
- A `user_type` column is added if it doesn't exist
- Default value is `'creator'` for backward compatibility
- All existing users remain `'creator'` type

### API Changes

#### Login Response
The `/creator/login` endpoint now returns:
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGci...",
    "name": "John Doe",
    "email": "john@example.com",
    "user_id": "user-123",
    "role": "user",
    "user_type": "end_user",
    "launch_url": "http://openwebui.example.com/?token=..."
  }
}
```

#### Create User Endpoint
`POST /creator/admin/users/create` now accepts:
```
email (required)
name (required)
password (required)
role (optional, default: 'user')
organization_id (optional)
user_type (optional, default: 'creator', values: 'creator' | 'end_user')
```

---

## Usage Guide

### For System Administrators

#### Creating an End User

**Via Admin UI:**
1. Log in as an admin
2. Navigate to Admin Panel → Users
3. Click "Create New User"
4. Fill in user details:
   - Email
   - Name
   - Password
   - Role (user/admin)
   - **User Type**: Select "End User (Redirects to Open WebUI)"
   - Organization (optional)
5. Click "Create User"

**Via API:**
```bash
curl -X POST 'http://localhost:9099/creator/admin/users/create' \
-H 'Authorization: Bearer <admin_token>' \
-H 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode 'email=enduser@example.com' \
--data-urlencode 'name=End User' \
--data-urlencode 'password=securepass123' \
--data-urlencode 'role=user' \
--data-urlencode 'user_type=end_user' \
--data-urlencode 'organization_id=2'
```

#### Creating a Creator User

Same process, but select "Creator (Can create assistants)" for User Type or use `user_type=creator` in the API.

### For End Users

#### Login Experience

1. Navigate to LAMB login page
2. Enter email and password
3. Click "Login"
4. **Automatic redirect to Open WebUI** with authentication
5. Interact with published assistants

End users will **never see** the creator interface - they are immediately redirected to Open WebUI upon successful login.

### For Organization Admins

Organization admins can create both creator and end users within their organization:
1. Users created with `organization_id` belong to that organization
2. Both user types respect organization boundaries
3. End users can only access assistants published to their organization

---

## Login Flow Diagram

```
┌─────────────────┐
│   User Visits   │
│   Login Page    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Enter Email &   │
│   Password      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Authenticate   │
│  with Backend   │
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │user_type?│
    └────┬────┘
         │
    ┌────┴─────────┐
    │              │
    ▼              ▼
┌────────┐    ┌──────────┐
│creator │    │end_user  │
└───┬────┘    └────┬─────┘
    │              │
    ▼              ▼
┌─────────┐   ┌──────────────┐
│Continue │   │  Redirect to │
│   to    │   │  Open WebUI  │
│Creator  │   │  (launch_url)│
│Interface│   └──────────────┘
└─────────┘
```

---

## Use Cases

### 1. Educational Institution
- **Creator Users**: Professors and instructors who create course assistants
- **End Users**: Students who only interact with assistants

### 2. Corporate Training
- **Creator Users**: Training managers who design AI training assistants
- **End Users**: Employees who use the assistants for learning

### 3. Customer Support
- **Creator Users**: Support team leads who configure support assistants
- **End Users**: Support agents who use assistants to help customers

---

## Security Considerations

1. **Authentication**: Both user types authenticate through the same secure system
2. **Authorization**: End users are prevented from accessing creator endpoints at the API level
3. **Organization Isolation**: Both user types respect organization boundaries
4. **Data Privacy**: End users can only access assistants published to their organization

---

## Migration Notes

### Existing Deployments

When upgrading to this version:
1. Database migration runs automatically on first startup
2. All existing users become `'creator'` type by default
3. No changes to existing user behavior
4. No downtime required
5. Backward compatible with existing frontend

### Testing the Feature

1. Create a test end user via admin panel
2. Log out
3. Log in with the end user credentials
4. Verify automatic redirect to Open WebUI
5. Verify no access to creator interface

---

## Troubleshooting

### End User Not Redirected
- Check that `launch_url` is returned in login response
- Verify `user_type` is set to `'end_user'` in database
- Check browser console for JavaScript errors

### End User Can Access Creator Interface
- Verify user_type in database: `SELECT user_type FROM Creator_users WHERE user_email = 'user@example.com';`
- Check that frontend properly detects `user_type === 'end_user'`
- Clear browser cache and cookies

### Migration Issues
- Check backend logs for migration errors
- Verify database schema: `PRAGMA table_info(Creator_users);`
- Should see `user_type` column with CHECK constraint

---

## Future Enhancements

Potential future improvements:
- Bulk import of end users
- Self-service end user registration (with approval workflow)
- Granular permissions for end users (access specific assistants only)
- End user analytics and usage tracking
- Organization-specific landing pages for end users

---

## API Reference

### List Users (includes user_type)
```
GET /creator/users
Authorization: Bearer <admin_token>

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "email": "creator@example.com",
      "name": "Creator User",
      "role": "user",
      "user_type": "creator",
      "organization": "Engineering Dept"
    },
    {
      "id": 2,
      "email": "enduser@example.com",
      "name": "End User",
      "role": "user",
      "user_type": "end_user",
      "organization": "Engineering Dept"
    }
  ]
}
```

### Create User (with user_type)
```
POST /creator/admin/users/create
Authorization: Bearer <admin_token>
Content-Type: application/x-www-form-urlencoded

Parameters:
- email (required)
- name (required)
- password (required)
- role (optional, default: 'user')
- organization_id (optional)
- user_type (optional, default: 'creator')

Response:
{
  "success": true,
  "message": "User enduser@example.com created successfully"
}
```

---

## Conclusion

The End User feature provides a clear separation between users who create AI assistants and users who simply interact with them. This enables administrators to:
- Better control access to creation capabilities
- Simplify the user experience for non-technical users
- Support larger deployments with many interaction-only users
- Maintain security and organization boundaries

For questions or support, please refer to the main LAMB documentation or open an issue on GitHub.

