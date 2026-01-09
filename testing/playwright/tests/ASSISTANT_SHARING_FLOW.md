# Assistant Sharing Flow - Test Scripts

This document describes the manual test flows that will be automated with Playwright.

## Prerequisites

- LAMB application running at `http://localhost:9099/` or `http://localhost:5173/`
- System admin account: `admin@owi.com` / `admin`

---

## Test Suite: User and Organization Management + Assistant Sharing

### Test 1: Create a New User (System Admin)

**Flow:**
1. Login as `admin@owi.com`
2. Navigate to **Admin** → **User Management**
3. Click **Create User** button
4. Fill in the form:
   - **Email**: `sharing_test_user@test.com`
   - **Name**: `Sharing Test User`
   - **Password**: `test_password_123`
   - **Role**: `User`
   - **User Type**: `Creator (Can create assistants)`
   - **Organization**: Leave empty (will be assigned to system org)
5. Click **Create User** button
6. Verify success message appears
7. Verify user appears in the list

**Expected Result:** User is created and visible in the user list.

---

### Test 2: Create a New Organization

**Flow:**
1. From the Admin panel, navigate to **Organizations** tab
2. Click **Create Organization** button
3. Fill in the form:
   - **Slug**: `test-sharing-org`
   - **Name**: `Test Sharing Organization`
   - **Organization Admin**: Select the user created in Test 1
   - **Features**: Leave defaults
4. Click **Create Organization** button
5. Verify success message appears
6. Verify organization appears in the list

**Expected Result:** Organization is created with the test user as admin.

---

### Test 3: Create a Second User for the Organization

**Flow:**
1. Navigate to **Admin** → **User Management**
2. Click **Create User** button
3. Fill in the form:
   - **Email**: `sharing_test_user2@test.com`
   - **Name**: `Sharing Test User 2`
   - **Password**: `test_password_123`
   - **User Type**: `Creator (Can create assistants)`
   - **Organization**: Select `Test Sharing Organization`
4. Click **Create User** button
5. Verify success message appears

**Expected Result:** Second user is created in the test organization.

---

### Test 4: Login as Organization User and Create an Assistant

**Flow:**
1. Logout from admin account
2. Login as `sharing_test_user@test.com` / `test_password_123`
3. Navigate to **Learning Assistants**
4. Click **Create Assistant** button
5. Fill in the form:
   - **Name**: `Shared Test Assistant`
   - **Description**: `Assistant for testing sharing functionality`
   - **System Prompt**: `You are a helpful assistant.`
6. Click **Save** button
7. Verify assistant is created

**Expected Result:** Assistant is created and visible in the list.

---

### Test 5: Share Assistant with Organization User

**Flow:**
1. Still logged in as `sharing_test_user@test.com`
2. Navigate to **Learning Assistants** → view the created assistant
3. Click on the **Share** tab
4. Click **Manage Shared Users** button
5. In the modal:
   - Available Users panel should show `Sharing Test User 2`
   - Select the user (checkbox)
   - Click **Move selected → Shared** button (or **Move ALL**)
6. Click **Save Changes** button
7. Verify success message appears
8. Verify the modal closes or shows updated state

**Expected Result:** Assistant is shared with the second user.

---

### Test 6: Verify Shared Assistant Appears for Second User

**Flow:**
1. Logout from first user
2. Login as `sharing_test_user2@test.com` / `test_password_123`
3. Navigate to **Learning Assistants**
4. Check if `Shared Test Assistant` appears in the list (in "Shared With Me" section or marked as shared)

**Expected Result:** The shared assistant is visible to the second user.

---

### Test 7: Remove Sharing from Assistant

**Flow:**
1. Login as `sharing_test_user@test.com` (the owner)
2. Navigate to **Learning Assistants** → view the shared assistant
3. Click on the **Share** tab
4. Click **Manage Shared Users** button
5. In the modal:
   - Shared Users panel should show `Sharing Test User 2`
   - Select the user (checkbox)
   - Click **Move selected → Available** button
6. Click **Save Changes** button
7. Verify success message appears

**Expected Result:** Assistant is no longer shared with the second user.

---

### Test 8: Org Admin Can Manage Assistant Sharing

**Flow:**
1. Login as org admin user (first user who is now org admin)
2. Navigate to **Org Admin** panel (should be accessible if user is org admin)
3. Click on **Assistants Access** tab
4. Find the assistant in the list
5. Click **Manage Sharing** button for the assistant
6. Verify the sharing modal opens
7. Add a user to sharing
8. Save changes

**Expected Result:** Org admin can manage sharing for any assistant in their organization.

---

### Cleanup Tests

### Test 9: Delete the Test Assistant

**Flow:**
1. Login as `sharing_test_user@test.com`
2. Navigate to **Learning Assistants**
3. Find `Shared Test Assistant`
4. Click the delete button (trash icon)
5. Confirm deletion in the modal
6. Verify assistant is removed from the list

**Expected Result:** Assistant is deleted.

---

### Test 10: Delete Test Organization

**Flow:**
1. Login as `admin@owi.com`
2. Navigate to **Admin** → **Organizations**
3. Find `Test Sharing Organization`
4. Click the delete button
5. Confirm deletion
6. Verify organization is removed

**Expected Result:** Organization is deleted.

---

### Test 11: Disable/Delete Test Users

**Flow:**
1. Navigate to **Admin** → **User Management**
2. Find `sharing_test_user@test.com`
3. Click disable button
4. Confirm disable
5. Verify user is disabled
6. Repeat for `sharing_test_user2@test.com`

**Expected Result:** Both test users are disabled.

---

## API Endpoints Tested

| Flow | Endpoint | Method |
|------|----------|--------|
| Create User | `/creator/users` | POST |
| Create Organization | `/creator/organizations` | POST |
| Create Assistant | `/creator/lamb/assistant/*` | POST |
| Check Sharing Permission | `/creator/lamb/assistant-sharing/check-permission` | GET |
| Get Organization Users | `/creator/lamb/assistant-sharing/organization-users` | GET |
| Get Assistant Shares | `/creator/lamb/assistant-sharing/shares/{id}` | GET |
| Update Assistant Shares | `/creator/lamb/assistant-sharing/shares/{id}` | PUT |
| Get Shared Assistants | `/creator/lamb/assistant-sharing/shared-with-me` | GET |

---

## UI Elements Reference

### Admin Panel - User Management
- URL: `/admin?view=users`
- Create User button: `button` with name "Create User"
- Email input: `textbox` with label "Email *"
- Name input: `textbox` with label "Name *"
- Password input: `textbox` with label "Password *"
- User Type select: `combobox` with label "User Type"
- Organization select: `combobox` with label "Organization"

### Admin Panel - Organizations
- URL: `/admin?view=organizations`
- Create Organization button: `button` with name "Create Organization"
- Slug input: `textbox` with label "Slug *"
- Name input: `textbox` with label "Name *"
- Admin select: `combobox` with label "Organization Admin *"

### Assistant Detail - Share Tab
- URL: `/assistants?view=detail&id={id}`
- Share tab: Tab or link with "Share" text
- Manage Shared Users button: `button` with name "Manage Shared Users"

### Sharing Modal
- Available Users panel: Contains list of users not currently shared
- Shared Users panel: Contains list of users with access
- Move buttons: Transfer users between panels
- Save Changes button: Commits sharing changes

### Org Admin - Assistants Access
- URL: `/org-admin?view=assistants`
- Assistant table with "Manage Sharing" buttons
- Each row shows assistant name, owner, publish status, share status
