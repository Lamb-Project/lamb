# Bulk User Import - Usage Guide

## Overview

The bulk user import feature allows organization administrators to create multiple users at once by uploading a JSON file. This is especially useful for:

- Onboarding new cohorts of students (50+ users)
- Setting up course rosters at the beginning of a semester
- Migrating users from other systems
- Creating test user accounts

## Features

✅ **Validation First**: Catch all errors before any users are created
✅ **Partial Success**: Continue processing even if some users fail
✅ **Bulk Activation**: Create users disabled, then activate when ready
✅ **Audit Trail**: All operations are logged for compliance
✅ **Template Download**: Get a pre-formatted JSON template
✅ **Detailed Results**: See exactly what succeeded and what failed

## Quick Start

### 1. Download the Template

1. Go to Organization Admin page
2. Click on "Bulk Import" tab
3. Click "Download Template" button
4. Open the downloaded JSON file in a text editor

### 2. Fill in Your Users

Edit the `users` array with your user data:

```json
{
  "version": "1.0",
  "users": [
    {
      "email": "user@example.com",
      "name": "User Name",
      "user_type": "creator",
      "enabled": false
    }
  ]
}
```

### 3. Upload and Validate

1. Click "Select JSON File" and choose your file
2. Click "Upload & Validate"
3. Review the validation results

### 4. Review and Import

1. Check the Preview tab for any errors
2. Fix errors in your JSON file if needed
3. Click "Import X Valid User(s)"

### 5. Activate Users

1. Go to User List
2. Select the newly created users (use checkboxes)
3. Click "Enable Selected"

## JSON File Format

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `version` | string | Schema version (must be "1.0") | `"1.0"` |
| `users` | array | Array of user objects | `[...]` |
| `users[].email` | string | User email (must be unique) | `"user@example.com"` |
| `users[].name` | string | User full name (1-100 chars) | `"John Doe"` |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `users[].user_type` | string | `"creator"` | `"creator"` or `"end_user"` |
| `users[].enabled` | boolean | `false` | Whether account is active |

### User Types

- **`creator`**: Full access to creator interface, can create assistants
- **`end_user`**: Auto-redirected to Open WebUI, chat-only access

### Enabled Status

- **`false`** (recommended): Create in disabled state, activate later
- **`true`**: Create active immediately

## Example Files

### Basic Import (5 users)

```json
{
  "version": "1.0",
  "users": [
    {
      "email": "alice@example.com",
      "name": "Alice Johnson",
      "user_type": "creator",
      "enabled": false
    },
    {
      "email": "bob@example.com",
      "name": "Bob Smith",
      "user_type": "end_user",
      "enabled": false
    }
  ]
}
```

### Large Import (100+ users)

For large imports, use a script to generate the JSON:

```python
import json

users = []
for i in range(1, 101):
    users.append({
        "email": f"student{i}@example.com",
        "name": f"Student {i}",
        "user_type": "end_user",
        "enabled": False
    })

data = {
    "version": "1.0",
    "users": users
}

with open('bulk_import_100_students.json', 'w') as f:
    json.dump(data, f, indent=2)
```

## Validation Rules

### Email Validation

✅ **Valid**:
- `user@example.com`
- `first.last@company.co.uk`
- `student123@university.edu`

❌ **Invalid**:
- `not-an-email` (missing @)
- `user@` (incomplete domain)
- `@example.com` (missing local part)

### Duplicate Detection

The system checks for:
1. ✅ Duplicate emails **within the file**
2. ✅ Emails that **already exist** in your organization
3. ✅ Emails that exist in **other organizations**

### Name Validation

- ✅ Minimum 1 character
- ✅ Maximum 100 characters
- ✅ Any UTF-8 characters allowed

### User Type Validation

- ✅ Must be exactly `"creator"` or `"end_user"`
- ❌ Case-sensitive (no `"Creator"` or `"END_USER"`)

## API Testing with cURL

### 1. Download Template

```bash
curl -X GET \
  'http://localhost:9099/creator/admin/org-admin/users/bulk-import/template' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -o template.json
```

### 2. Validate Import File

```bash
curl -X POST \
  'http://localhost:9099/creator/admin/org-admin/users/bulk-import/validate' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'file=@users_import.json'
```

### 3. Execute Import

```bash
curl -X POST \
  'http://localhost:9099/creator/admin/org-admin/users/bulk-import/execute' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d @- << EOF
{
  "users": [
    {
      "email": "test@example.com",
      "name": "Test User",
      "user_type": "creator",
      "enabled": false
    }
  ],
  "filename": "test_import.json"
}
EOF
```

### 4. Bulk Enable Users

```bash
curl -X POST \
  'http://localhost:9099/creator/admin/org-admin/users/enable-bulk' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_ids": [123, 124, 125]
  }'
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid email format" | Email doesn't match pattern | Check email has @ and domain |
| "Email already exists in your organization" | Duplicate in system | Remove from file or skip |
| "Duplicate email in file" | Same email appears twice | Remove duplicates |
| "Name is required" | Empty name field | Add a name (min 1 char) |
| "Invalid user_type" | Typo in user_type | Use "creator" or "end_user" |
| "File too large" | File exceeds 5MB | Split into multiple imports |
| "Too many users" | More than 500 users | Import in batches |

## Best Practices

### 1. Start Small

Test with 5-10 users first to verify your format is correct.

### 2. Use Disabled State

Create users with `enabled: false`, review in user list, then activate:
- Gives you time to review before users get access
- Allows fixing any mistakes
- Better for coordinated course start dates

### 3. Download Results

Always download the results JSON after import for your records.

### 4. Batch Large Imports

For 500+ users:
- Split into batches of 500
- Import one batch at a time
- Verify each batch before continuing

### 5. Keep Original Files

Save your import JSON files as backups:
```
imports/
  ├── 2025-01-fall-semester.json
  ├── 2025-01-fall-semester-results.json
  └── 2025-02-spring-semester.json
```

## Troubleshooting

### Issue: "No valid users to import"

**Cause**: All users failed validation

**Solution**:
1. Check the Preview tab for specific errors
2. Fix errors in your JSON file
3. Re-upload and validate

### Issue: "Some users were skipped"

**Cause**: Users already exist in system

**Solution**:
- This is expected if re-running an import
- Check the detailed results to see which users were skipped
- Remove existing users from your JSON file

### Issue: "Import failed" error

**Cause**: Server error during import

**Solution**:
1. Check that users were not already created (check user list)
2. If some were created, remove them from your JSON
3. Try again with remaining users
4. Contact administrator if problem persists

## Security & Privacy

### Passwords

- **Automatically Generated**: Users get random 32-character secure passwords
- **Not Returned**: Passwords are NEVER shown in API responses or UI
- **Distribution**: Admins must communicate passwords separately (email, LMS, etc.)
- **Change on First Login**: Recommend users change password after first login

### Audit Logging

All bulk operations are logged with:
- Admin who performed the operation
- Timestamp
- Number of users affected
- Success/failure counts
- Detailed per-user results

### Organization Isolation

- Users can only be imported to your organization
- Emails from other organizations are rejected
- Admins cannot see users from other organizations

## Limitations

- **Maximum 500 users** per import
- **Maximum 5MB** file size
- **JSON format only** (no CSV, Excel, etc.)
- **No password customization** (auto-generated)
- **Organization-scoped only** (cannot create cross-org users)

## Support

For issues or questions:

1. Check this guide first
2. Review the comprehensive implementation plan: `/Documentation/BULK_USER_CREATION_IMPLEMENTATION_PLAN.md`
3. Check server logs for detailed error messages
4. Contact your system administrator

## Related Features

- **Individual User Creation**: `/org-admin` → "Create User" button
- **User Management**: `/org-admin` → "User Management" tab
- **Enable/Disable Users**: Select users → "Enable Selected" / "Disable Selected"
- **Password Reset**: Individual user → "Change Password"

---

**Last Updated**: November 2025  
**Feature Version**: 1.0

