# LAMB Application Quality Control Test - Test 4 (Admin Functionality)

## Overview

This document provides detailed test cases for verifying admin functionality in the LAMB (Learning Assistants Manager and Builder) application. These tests focus on admin authentication, user management, role administration, and admin interface features.

## Prerequisites

### Environment Setup
- LAMB application running at `http://localhost:9099`
- Admin user credentials configured in backend environment
- Backend API accessible with all services running
- Database properly initialized with admin user
- At least one regular user account available for testing

### Required Information
- Admin credentials: Check backend `.env` file for `OWI_ADMIN_EMAIL` and `OWI_ADMIN_PASSWORD`
- Test user credentials: `assistant@example.com` / `password123` (or create as needed)
- Access to LAMB web interface and admin panel
- Understanding of role-based access control system

## Test Case Overview

This test suite contains **12 test cases** organized into four main categories:

### **Admin Authentication and Access (Test Cases 1-3)**
1. **Admin Login Authentication** - Tests admin login with admin credentials and role verification
2. **Admin Navigation Visibility** - Verifies admin menu items only appear for admin users  
3. **Admin Authorization Testing** - Tests access control for admin-only endpoints and features

### **User Management Interface (Test Cases 4-7)**
4. **User List Management** - Tests viewing and managing the complete user list
5. **User Creation Functionality** - Verifies admin ability to create new users with role assignment
6. **Password Management** - Tests admin ability to change user passwords
7. **User Role Management** - Verifies role modification capabilities (user ↔ admin)

### **Admin Dashboard and Interface (Test Cases 8-9)**
8. **Admin Dashboard Functionality** - Tests admin dashboard features and information display
9. **Admin Interface Navigation** - Verifies tab navigation and view switching in admin panel

### **Admin API and Integration Testing (Test Cases 10-12)**
10. **Admin API Endpoints** - Tests all admin-specific backend API endpoints
11. **Admin Cross-Language Support** - Verifies admin interface works across all supported languages
12. **Admin Security and Edge Cases** - Tests security measures, validation, and error handling

### **Testing Focus Areas**
- **Authentication**: Admin login flow and token validation
- **Authorization**: Role-based access control and permission checking
- **User Management**: Complete user lifecycle management by admin
- **Interface Testing**: Admin UI components and user experience
- **API Integration**: Backend admin endpoint functionality
- **Security**: Input validation, permission checks, and error handling
- **Internationalization**: Multi-language support for admin interface
- **Error Handling**: Graceful error management and user feedback
- **Data Integrity**: Proper data validation and consistency
- **Session Management**: Admin session persistence and security

### **Key Features Tested**
- **Admin Authentication**: Secure admin login with credential validation
- **User List Display**: Complete user list with role indicators
- **User Creation**: New user creation with role assignment (user/admin)
- **Password Management**: Admin-initiated password changes for any user
- **Role Management**: User role modification with proper validation
- **Dashboard Interface**: Admin dashboard with navigation and information
- **API Security**: Admin endpoint protection and authorization
- **Cross-Language Support**: Admin interface in multiple languages
- **Error Handling**: Comprehensive error management and user feedback

## Test Cases

### Test Case 1: Admin Login Authentication

**Objective:** Verify admin user can log in successfully and receives proper admin role privileges.

**Steps:**
1. Navigate to LAMB application login page
2. Enter admin credentials:
   - Email: (from backend .env file - `OWI_ADMIN_EMAIL`)
   - Password: (from backend .env file - `OWI_ADMIN_PASSWORD`)
3. Submit login form
4. Verify successful authentication:
   - Redirected to main application
   - User profile shows admin information
   - Admin navigation items become visible
5. Check console for proper authentication messages
6. Verify authentication token includes admin role
7. Test session persistence across page reloads

**Expected Results:**
- Login completes successfully without errors ✅
- User profile displays admin name and role ✅
- Admin menu item appears in navigation bar ✅
- Authentication token contains admin role information ✅
- Session persists across page reloads ✅
- Console shows successful authentication messages ✅
- No authentication errors or access denied messages ✅

**Security Verification:**
- Admin credentials are validated server-side ✅
- Authentication token is properly secured ✅
- Role information is accurately transmitted ✅

---

### Test Case 2: Admin Navigation Visibility

**Objective:** Verify admin-specific navigation elements are properly displayed for admin users and hidden from regular users.

**Steps:**
1. **Phase 1: Admin User Navigation**
   - Log in as admin user
   - Examine navigation bar for admin-specific items
   - Verify "Admin" menu item is visible and clickable
   - Click on "Admin" menu item
   - Confirm navigation to admin panel works

2. **Phase 2: Regular User Navigation Comparison**
   - Log out from admin account  
   - Log in as regular user (assistant@example.com)
   - Examine navigation bar
   - Verify "Admin" menu item is NOT visible
   - Test that direct navigation to /admin is blocked

3. **Phase 3: Role-Based Access Verification**
   - Attempt to access admin URLs directly as regular user
   - Verify proper access control responses
   - Test role-based content visibility

**Expected Results:**
**Admin User Navigation:**
- "Admin" menu item visible in navigation bar ✅
- Admin menu item is properly styled and clickable ✅
- Navigation to admin panel succeeds ✅
- Admin panel loads without errors ✅

**Regular User Navigation:**
- "Admin" menu item NOT visible in navigation ✅
- Direct admin URL access is blocked/redirected ✅
- Proper access denied messages displayed ✅
- No admin-specific content visible to regular users ✅

**Role-Based Access Control:**
- Role information properly checked client-side ✅
- Server-side authorization enforced ✅
- Consistent behavior across all admin endpoints ✅

---

### Test Case 3: Admin Authorization Testing

**Objective:** Verify admin authorization works correctly for all admin-specific endpoints and features.

**Steps:**
1. **Phase 1: Admin Endpoint Access Testing**
   - Log in as admin user
   - Test access to admin API endpoints:
     - `GET /creator/users` (list all users)
     - `POST /creator/admin/users/create` (create user)
     - `POST /creator/admin/users/update-password` (change password)
     - `PUT /creator/admin/users/update-role-by-email` (update role)
   - Verify all endpoints respond with success

2. **Phase 2: Regular User Authorization Testing**
   - Log in as regular user
   - Attempt to access same admin endpoints
   - Verify proper 403 Forbidden responses
   - Check error messages are appropriate

3. **Phase 3: Token Validation Testing**
   - Test with invalid/expired admin tokens
   - Test with malformed authorization headers
   - Verify proper error handling

**Expected Results:**
**Admin User Authorization:**
- All admin endpoints accessible with admin token ✅
- Admin operations complete successfully ✅
- Proper admin role validation in responses ✅

**Regular User Authorization:**
- Admin endpoints return 403 Forbidden for regular users ✅
- Clear error messages: "Access denied. Admin privileges required." ✅
- No unauthorized data access possible ✅

**Token Validation:**
- Invalid tokens properly rejected ✅
- Expired tokens handled gracefully ✅
- Malformed requests return appropriate errors ✅

---

### Test Case 4: User List Management

**Objective:** Verify admin can view and manage the complete user list with proper role indicators.

**Steps:**
1. Navigate to Admin panel
2. Click on "User Management" tab (should be default view)
3. Verify user list loads correctly:
   - All users displayed in table format
   - User information shows: Name, Email, Role
   - Role badges properly color-coded (Admin: red, User: blue)
   - Action buttons available for each user
4. Test table functionality:
   - Responsive design on different screen sizes
   - Proper data alignment and formatting
   - Loading states and error handling
5. Verify user count and data accuracy
6. Test refresh/reload behavior

**Expected Results:**
- Admin panel loads without errors ✅
- User Management tab is accessible and active ✅
- Complete user list displays in table format ✅
- User information accurately shows:
  - Name (with fallback for missing names) ✅
  - Email addresses ✅
  - Role badges with proper color coding ✅
- Action buttons present for each user:
  - Change Password button (key icon) ✅
- Table responsive design works on mobile/desktop ✅
- Loading states display properly ✅
- Data refreshes correctly ✅
- Error handling shows appropriate messages ✅

**Data Verification:**
- User count matches expected number ✅
- All registered users appear in list ✅
- Role information is accurate ✅
- No duplicate or missing entries ✅

---

### Test Case 5: User Creation Functionality

**Objective:** Verify admin can create new users with proper role assignment and validation.

**Steps:**
1. **Phase 1: Access Create User Modal**
   - From User Management tab, click "Create User" button
   - Verify modal opens correctly
   - Check all form fields are present

2. **Phase 2: Create Regular User**
   - Fill in user creation form:
     - Email: `testuser1@example.com`
     - Name: `Test User 1`
     - Password: `securepass123`
     - Role: `User` (default)
   - Submit form
   - Verify success message
   - Check user appears in user list

3. **Phase 3: Create Admin User**
   - Open create user modal again
   - Fill in form for admin user:
     - Email: `testadmin@example.com`
     - Name: `Test Admin`
     - Password: `adminpass123`
     - Role: `Admin`
   - Submit form and verify creation

4. **Phase 4: Validation Testing**
   - Test form validation:
     - Empty required fields
     - Invalid email formats
     - Duplicate email addresses
     - Password requirements

**Expected Results:**
**Modal Functionality:**
- Create User button opens modal correctly ✅
- Modal displays all required form fields ✅
- Form fields properly labeled and functional ✅
- Modal can be closed without submitting ✅

**User Creation Process:**
- Regular user creation succeeds ✅
- Admin user creation succeeds ✅
- Success messages display appropriately ✅
- New users appear in user list immediately ✅
- Role assignment works correctly ✅

**Form Validation:**
- Required field validation works ✅
- Email format validation functional ✅
- Duplicate email prevention works ✅
- Password requirements enforced ✅
- Clear error messages for validation failures ✅

**Data Integrity:**
- Created users have correct information ✅
- Role assignments are properly saved ✅
- Passwords are securely hashed ✅

---

### Test Case 6: Password Management

**Objective:** Verify admin can change passwords for any user account.

**Steps:**
1. **Phase 1: Access Password Change Modal**
   - From user list, click "Change Password" button (key icon) for a user
   - Verify modal opens with correct user information
   - Check email field is pre-populated and disabled

2. **Phase 2: Change User Password**
   - Enter new password: `newpassword123`
   - Verify password requirements hint is displayed
   - Submit password change form
   - Verify success message appears

3. **Phase 3: Password Change Validation**
   - Close modal and verify user list unchanged
   - Test that new password works (logout and login as that user)
   - Verify old password no longer works

4. **Phase 4: Password Requirements Testing**
   - Test password validation:
     - Minimum length requirements (8+ characters)
     - Empty password field
     - Very weak passwords

5. **Phase 5: Multiple User Testing**
   - Change passwords for different users
   - Verify each change is independent
   - Test password changes for admin users

**Expected Results:**
**Modal Functionality:**
- Password change modal opens correctly ✅
- User email pre-populated and disabled ✅
- User name displayed in modal subtitle ✅
- New password field accepts input ✅

**Password Change Process:**
- Password changes complete successfully ✅
- Success message displays after change ✅
- Modal can be closed after successful change ✅
- User list remains unchanged after password change ✅

**Password Validation:**
- Minimum 8 character requirement enforced ✅
- Empty password field validation works ✅
- Password requirements hint displayed ✅
- Clear error messages for validation failures ✅

**Functionality Verification:**
- New passwords work for user login ✅
- Old passwords are invalidated ✅
- Password changes are immediate ✅
- Multiple user password changes work independently ✅
- Admin user passwords can be changed ✅

**Security Verification:**
- Passwords are properly hashed server-side ✅
- No plaintext passwords visible in responses ✅
- Password change requires admin authentication ✅

---

### Test Case 7: User Role Management

**Objective:** Verify admin can modify user roles (promote/demote between user and admin).

**Note:** This test case verifies the backend API endpoints exist, but UI implementation may be pending.

**Steps:**
1. **Phase 1: Backend API Testing (via browser console)**
   - Open browser developer tools
   - Test role update API endpoints directly:
     - `PUT /creator/admin/users/update-role-by-email`
     - `PUT /creator/admin/users/{user_id}/update-role`

2. **Phase 2: Role Update by Email**
   ```javascript
   // Browser console test
   fetch('/creator/admin/users/update-role-by-email', {
     method: 'PUT',
     headers: {
       'Authorization': 'Bearer ' + userToken,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       email: 'testuser1@example.com',
       role: 'admin'
     })
   })
   ```

3. **Phase 3: Role Update by User ID**
   ```javascript
   // Browser console test  
   fetch('/creator/admin/users/2/update-role', {
     method: 'PUT',
     headers: {
       'Authorization': 'Bearer ' + userToken,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       role: 'user'
     })
   })
   ```

4. **Phase 4: Verification Testing**
   - Refresh user list to verify role changes
   - Test that role badges update correctly
   - Verify user gains/loses admin privileges appropriately

5. **Phase 5: Protected User Testing**
   - Attempt to change role of primary admin (ID 1)
   - Verify this is properly blocked

**Expected Results:**
**API Endpoint Functionality:**
- Role update by email endpoint works ✅
- Role update by ID endpoint works ✅
- Proper JSON responses returned ✅
- Success messages include updated role information ✅

**Role Update Process:**
- User roles can be changed from 'user' to 'admin' ✅
- Admin roles can be changed to 'user' ✅
- Role changes are immediate and persistent ✅
- User list reflects role changes after refresh ✅

**Validation and Security:**
- Primary admin (ID 1) role cannot be changed ✅
- Invalid roles (not 'user' or 'admin') are rejected ✅
- Non-existent users return appropriate errors ✅
- Only admin users can change roles ✅

**Data Integrity:**
- Role changes are properly saved to database ✅
- User permissions update immediately ✅
- No data corruption during role changes ✅

**Note:** If UI buttons for role management are added in the future, update this test case to include UI testing steps.

---

### Test Case 8: Admin Dashboard Functionality

**Objective:** Verify admin dashboard displays correctly and provides useful administrative information.

**Steps:**
1. **Phase 1: Dashboard Access**
   - Navigate to Admin panel
   - Click on "Dashboard" tab
   - Verify dashboard view loads correctly

2. **Phase 2: Dashboard Content Verification**
   - Check dashboard title: "Admin Dashboard"
   - Verify welcome message is displayed
   - Check for any dashboard metrics or information
   - Verify proper styling and layout

3. **Phase 3: Dashboard Navigation**
   - Test tab switching between Dashboard and User Management
   - Verify active tab highlighting works correctly
   - Check URL updates properly with tab changes

4. **Phase 4: Responsive Design Testing**
   - Test dashboard on different screen sizes
   - Verify mobile responsiveness
   - Check tablet and desktop layouts

**Expected Results:**
**Dashboard Display:**
- Dashboard tab is accessible and functional ✅
- Dashboard loads without errors ✅
- Title "Admin Dashboard" displays correctly ✅
- Welcome message is visible and properly translated ✅

**Layout and Styling:**
- Dashboard uses consistent LAMB branding ✅
- Proper spacing and typography ✅
- Color scheme matches application theme ✅
- No layout breaks or visual issues ✅

**Navigation Functionality:**
- Tab switching works smoothly ✅
- Active tab is properly highlighted ✅
- URL reflects current dashboard view ✅
- Browser back/forward buttons work correctly ✅

**Responsive Design:**
- Dashboard works on mobile devices ✅
- Tablet view displays correctly ✅
- Desktop layout is optimal ✅
- No horizontal scrolling issues ✅

---

### Test Case 9: Admin Interface Navigation

**Objective:** Verify complete admin interface navigation and tab management functionality.

**Steps:**
1. **Phase 1: Tab Navigation Testing**
   - Access admin panel
   - Test clicking between "Dashboard" and "User Management" tabs
   - Verify tab state persistence
   - Check active tab visual indicators

2. **Phase 2: URL Management**
   - Verify URLs update correctly with tab changes:
     - `/admin` for Dashboard
     - `/admin?view=users` for User Management
   - Test direct URL access to specific tabs
   - Verify browser navigation (back/forward) works

3. **Phase 3: State Persistence**
   - Switch to User Management tab
   - Refresh the page
   - Verify the correct tab remains active
   - Test state persistence across browser sessions

4. **Phase 4: Admin Panel Integration**
   - Navigate away from admin panel
   - Return to admin panel
   - Verify it remembers last viewed tab
   - Test integration with main navigation

**Expected Results:**
**Tab Navigation:**
- Smooth switching between Dashboard and User Management ✅
- Visual feedback for active tab (blue background, white text) ✅
- Tab content updates immediately ✅
- No loading delays between tab switches ✅

**URL Management:**
- URLs correctly reflect current admin view ✅
- Direct URL access works for both tabs ✅
- Browser navigation (back/forward) functions properly ✅
- URL changes are handled gracefully ✅

**State Persistence:**
- Tab state persists across page refreshes ✅
- Last viewed tab remembered when returning to admin panel ✅
- State maintained across browser sessions ✅
- No state corruption or unexpected behavior ✅

**Integration Testing:**
- Admin panel integrates smoothly with main application ✅
- Navigation between admin and other sections works ✅
- User authentication state maintained ✅
- Consistent user experience across transitions ✅

---

### Test Case 10: Admin API Endpoints

**Objective:** Verify all admin-specific backend API endpoints function correctly with proper authentication and authorization.

**Steps:**
1. **Phase 1: User List Endpoint**
   ```bash
   # Test GET /creator/users
   curl -X GET 'http://localhost:9099/creator/users' \
   -H 'Authorization: Bearer <admin_token>'
   ```
   - Verify returns complete user list
   - Check response format and data completeness

2. **Phase 2: User Creation Endpoint**
   ```bash
   # Test POST /creator/admin/users/create
   curl -X POST 'http://localhost:9099/creator/admin/users/create' \
   -H 'Authorization: Bearer <admin_token>' \
   -H 'Content-Type: application/x-www-form-urlencoded' \
   --data-urlencode 'email=apitest@example.com' \
   --data-urlencode 'name=API Test User' \
   --data-urlencode 'password=testpass123' \
   --data-urlencode 'role=user'
   ```

3. **Phase 3: Password Update Endpoint**
   ```bash
   # Test POST /creator/admin/users/update-password
   curl -X POST 'http://localhost:9099/creator/admin/users/update-password' \
   -H 'Authorization: Bearer <admin_token>' \
   -H 'Content-Type: application/x-www-form-urlencoded' \
   --data-urlencode 'email=apitest@example.com' \
   --data-urlencode 'new_password=newpass456'
   ```

4. **Phase 4: Role Update Endpoints**
   ```bash
   # Test PUT /creator/admin/users/update-role-by-email
   curl -X PUT 'http://localhost:9099/creator/admin/users/update-role-by-email' \
   -H 'Authorization: Bearer <admin_token>' \
   -H 'Content-Type: application/json' \
   -d '{"email": "apitest@example.com", "role": "admin"}'
   
   # Test PUT /creator/admin/users/{user_id}/update-role
   curl -X PUT 'http://localhost:9099/creator/admin/users/2/update-role' \
   -H 'Authorization: Bearer <admin_token>' \
   -H 'Content-Type: application/json' \
   -d '{"role": "user"}'
   ```

5. **Phase 5: Authorization Testing**
   - Test all endpoints with regular user token
   - Verify 403 Forbidden responses
   - Test with invalid/missing tokens

**Expected Results:**
**Endpoint Functionality:**
- GET /creator/users returns complete user list ✅
- POST /creator/admin/users/create creates users successfully ✅
- POST /creator/admin/users/update-password changes passwords ✅
- PUT role update endpoints modify roles correctly ✅

**Response Format Verification:**
- All responses use proper JSON format ✅
- Success responses include expected data ✅
- Error responses have clear error messages ✅
- HTTP status codes are appropriate ✅

**Authorization Testing:**
- Admin endpoints require admin privileges ✅
- Regular users receive 403 Forbidden errors ✅
- Invalid tokens are properly rejected ✅
- Clear authorization error messages provided ✅

**Data Integrity:**
- Created users appear in database ✅
- Password changes are effective immediately ✅
- Role updates are properly saved ✅
- No data corruption during operations ✅

---

### Test Case 11: Admin Cross-Language Support

**Objective:** Verify admin interface works correctly across all supported LAMB languages (English, Spanish, Catalan, Basque).

**Steps:**
1. **Phase 1: Admin Interface in Spanish**
   - Switch LAMB interface to Spanish (ES)
   - Access admin panel
   - Verify admin interface elements are translated:
     - Tab labels: "Dashboard" → "Panel de Control", "User Management" → "Gestión de Usuarios"
     - Buttons: "Create User" → "Crear Usuario"
     - Table headers and content
     - Modal dialogs and forms

2. **Phase 2: Admin Interface in Catalan**
   - Switch to Catalan (CA)
   - Test admin panel functionality
   - Verify Catalan translations for:
     - Navigation elements
     - Form labels and buttons
     - Success/error messages
     - Modal content

3. **Phase 3: Admin Interface in Basque**
   - Switch to Basque (EU)
   - Access all admin features
   - Verify Basque translations complete and accurate

4. **Phase 4: Language Switching in Admin Panel**
   - While in admin panel, switch between languages
   - Verify interface updates immediately
   - Test that admin functionality remains intact
   - Check no broken translations or layout issues

5. **Phase 5: Admin Operations Cross-Language**
   - Create users while interface is in different languages
   - Change passwords with non-English interface
   - Verify success/error messages display in correct language

**Expected Results:**
**Spanish Interface (ES):**
- Admin navigation properly translated ✅
- User management interface in Spanish ✅
- Create user modal and forms translated ✅
- Success/error messages in Spanish ✅

**Catalan Interface (CA):**
- Complete Catalan translation for admin features ✅
- Proper Catalan typography and text display ✅
- Modal dialogs and forms in Catalan ✅
- No missing or broken translations ✅

**Basque Interface (EU):**
- Admin interface fully translated to Basque ✅
- All admin functionality works in Basque ✅
- Consistent translation quality ✅

**Language Switching:**
- Real-time language switching in admin panel ✅
- No loss of functionality during language changes ✅
- Layout remains intact across all languages ✅
- Admin operations work in all languages ✅

**Operational Consistency:**
- User creation works in all languages ✅
- Password changes function across languages ✅
- Error handling consistent across languages ✅
- All admin features maintain functionality ✅

---

### Test Case 12: Admin Security and Edge Cases

**Objective:** Verify admin interface handles security measures, validation, and edge cases properly.

**Steps:**
1. **Phase 1: Input Validation Testing**
   - Test user creation with invalid inputs:
     - Very long names (>1000 characters)
     - Invalid email formats
     - Special characters in names
     - SQL injection attempts in form fields
     - XSS attempts in user data

2. **Phase 2: Password Security Testing**
   - Test password change validation:
     - Empty passwords
     - Very short passwords (<8 characters)
     - Very long passwords (>1000 characters)
     - Passwords with special characters
     - Unicode characters in passwords

3. **Phase 3: Authorization Edge Cases**
   - Test admin access with expired tokens
   - Test concurrent admin sessions
   - Test admin access after password change
   - Test primary admin protection (ID 1 cannot be demoted)

4. **Phase 4: Error Handling Testing**
   - Test admin operations with database unavailable
   - Test with network connection issues
   - Test with malformed API responses
   - Test concurrent user modifications

5. **Phase 5: Rate Limiting and Performance**
   - Test rapid successive admin operations
   - Test creating many users quickly
   - Test with large user lists (100+ users)
   - Verify no memory leaks in admin interface

**Expected Results:**
**Input Validation:**
- Long inputs handled gracefully without crashes ✅
- Invalid email formats rejected with clear messages ✅
- Special characters properly escaped and handled ✅
- SQL injection attempts blocked ✅
- XSS attempts sanitized ✅

**Password Security:**
- Empty passwords rejected ✅
- Short passwords fail validation ✅
- Very long passwords handled appropriately ✅
- Special characters in passwords supported ✅
- Unicode characters properly processed ✅

**Authorization Security:**
- Expired tokens properly rejected ✅
- Concurrent admin sessions handled correctly ✅
- Admin access revoked after password change ✅
- Primary admin (ID 1) cannot be demoted ✅
- Proper error messages for authorization failures ✅

**Error Handling:**
- Database unavailability handled gracefully ✅
- Network issues show appropriate error messages ✅
- Malformed responses don't crash interface ✅
- Concurrent modifications handled properly ✅
- Recovery mechanisms work correctly ✅

**Performance and Reliability:**
- Rapid operations don't cause conflicts ✅
- Large user lists display efficiently ✅
- No memory leaks during extended admin sessions ✅
- Interface remains responsive under load ✅
- Rate limiting prevents abuse ✅

---

## Performance and Technical Verification

### Console Output Verification

**Expected Console Messages:**
- Admin authentication success messages
- User management operation logs
- API request/response logging for admin endpoints
- No critical errors during admin operations
- Proper role validation confirmations

**Error Indicators to Watch For:**
- Failed admin authentication attempts
- Authorization errors for admin endpoints
- User creation/modification failures
- Database connection issues
- Memory leaks in admin interface

### Network Requests

**Expected API Calls:**
- `POST /creator/login` (admin authentication)
- `GET /creator/users` (user list retrieval)
- `POST /creator/admin/users/create` (user creation)
- `POST /creator/admin/users/update-password` (password changes)
- `PUT /creator/admin/users/update-role-by-email` (role updates)
- `PUT /creator/admin/users/{user_id}/update-role` (role updates by ID)

### Data Integrity Verification

**Database Consistency Checks:**
- Created users properly saved with correct roles
- Password changes are immediately effective
- Role modifications are persistent
- No orphaned or corrupt user records
- Admin operations maintain referential integrity

## Success Criteria

All test cases should pass with:
- Admin authentication works securely and reliably
- Admin interface is accessible only to authorized admin users
- User management operations complete successfully
- Role-based access control functions properly
- Admin API endpoints are secure and functional
- Cross-language support works for all admin features
- Input validation prevents security vulnerabilities
- Error handling provides clear, actionable feedback
- Performance meets requirements under normal load
- Data integrity is maintained throughout all operations
- Security measures prevent unauthorized access
- Admin operations are logged and auditable

## Known Issues and Workarounds

1. **Role Management UI**: Role update functionality currently requires API testing via browser console - UI buttons may be added in future versions
2. **Dashboard Metrics**: Admin dashboard is basic - may be enhanced with user statistics and system metrics
3. **Bulk Operations**: No bulk user operations available - operations must be performed individually
4. **User Deletion**: User deletion functionality not implemented - users can only be password-reset or role-changed
5. **Audit Logging**: Admin operation audit logs may not be visible in UI - check server logs for detailed admin activity
6. **Session Timeout**: Admin sessions may timeout - refresh page and re-authenticate if needed
7. **Password Complexity**: Password requirements are basic (8+ characters) - may need enhancement for production

---

**Document Version:** 1.0  
**Last Updated:** January 2025  
**Based on Testing:** LAMB v0.1 admin functionality  
**Dependencies:** Backend authentication system, OWI integration, role-based access control  
**i18n Support:** Full support for English (en), Spanish (es), Catalan (ca), Basque (eu)  
**Security Note:** Admin credentials should never be stored in documentation - always reference environment configuration files