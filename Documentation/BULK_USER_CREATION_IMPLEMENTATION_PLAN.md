# Bulk User Creation Implementation Plan

**Version:** 1.0  
**Date:** November 3, 2025  
**Feature:** Bulk User Creation and Activation for Organization Admins  
**Status:** Planning

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current System Analysis](#2-current-system-analysis)
3. [Requirements](#3-requirements)
4. [Architecture Design](#4-architecture-design)
5. [Database Schema](#5-database-schema)
6. [Backend Implementation](#6-backend-implementation)
7. [Frontend Implementation](#7-frontend-implementation)
8. [Security Considerations](#8-security-considerations)
9. [Error Handling](#9-error-handling)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Success Metrics](#12-success-metrics)

---

## 1. Executive Summary

### 1.1 Objective

Enable organization administrators to efficiently onboard multiple users simultaneously through JSON file import, with the ability to create users in a pending (disabled) state and activate them in bulk once ready.

### 1.2 Key Benefits

- **Efficiency**: Reduce time to onboard 50+ users from hours to minutes
- **Validation**: Catch errors before creation with pre-import validation
- **Control**: Create users in disabled state, activate when ready
- **Audit Trail**: Track bulk operations for compliance
- **Error Recovery**: Partial success handling with detailed reporting

### 1.3 User Workflow

```
1. Org Admin prepares JSON file with user list
2. Admin uploads file via UI
3. System validates JSON structure and data
4. System displays preview with validation results
5. Admin reviews and confirms import
6. System creates users (disabled by default)
7. System displays detailed results (success/failures)
8. Admin reviews created users in user list
9. Admin selects users to activate
10. Admin performs bulk activation
```

---

## 2. Current System Analysis

### 2.1 Existing Capabilities

**✅ Already Implemented:**
- Individual user creation for org-admins (`POST /creator/admin/org-admin/users`)
- Bulk enable/disable for system admins (`POST /creator/admin/users/enable-bulk`)
- User listing with enabled status (`GET /creator/admin/org-admin/users`)
- User type support (creator/end_user)
- Organization-scoped user management
- Transaction-safe bulk operations pattern

**Database Schema:**
```sql
CREATE TABLE Creator_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    user_email TEXT NOT NULL UNIQUE,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
    enabled BOOLEAN NOT NULL DEFAULT 1,
    user_config JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

### 2.2 What's Missing

**❌ Not Yet Implemented:**
- Bulk user creation endpoint
- JSON file upload and parsing
- Pre-import validation
- Import preview functionality
- Bulk operation result tracking
- Bulk import audit logging
- Frontend bulk import UI
- JSON template generation

### 2.3 Existing Code to Leverage

**Backend:**
- `backend/lamb/database_manager.py`: User CRUD operations
- `backend/creator_interface/organization_router.py`: Org-admin endpoints
- `backend/lamb/owi_bridge/owi_users.py`: OWI user creation
- `backend/utils/pipelines/user_creator_manager.py`: User creation pipeline

**Frontend:**
- `frontend/svelte-app/src/routes/org-admin/+page.svelte`: Org admin UI
- `frontend/svelte-app/src/lib/services/orgAdminService.js`: Org admin API calls
- Bulk selection pattern from admin user management

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-BULK-001: JSON File Upload
- Org-admins shall upload JSON files up to 5MB
- System shall support .json file extension
- System shall validate JSON syntax before processing

#### FR-BULK-002: JSON Schema Validation
- System shall validate JSON structure against schema
- System shall validate required fields: email, name
- System shall validate optional fields: user_type, enabled
- System shall validate email format (RFC 5322)
- System shall check for duplicate emails within file
- System shall check for existing emails in organization
- System shall provide detailed validation errors

#### FR-BULK-003: Import Preview
- System shall display all users from JSON before import
- System shall show validation status per user
- System shall allow filtering valid/invalid entries
- System shall provide import summary (total, valid, invalid)
- Admin shall confirm or cancel import

#### FR-BULK-004: Bulk User Creation
- System shall create all valid users in single operation
- System shall create users in disabled state by default
- System shall generate random secure passwords
- System shall create corresponding OWI accounts
- System shall assign users to organization
- System shall use transactions for atomicity per user
- System shall continue on individual failures (partial success)

#### FR-BULK-005: Creation Results
- System shall return detailed results per user
- System shall indicate success/failure per user
- System shall provide error messages for failures
- System shall count: total, created, failed, skipped
- System shall log all bulk operations

#### FR-BULK-006: Bulk Activation (Leverage Existing)
- Org-admins shall select multiple users from list
- Org-admins shall activate selected users
- System shall enable all selected users
- System shall prevent self-deactivation

#### FR-BULK-007: Template Generation
- System shall provide downloadable JSON template
- Template shall include example users with all fields
- Template shall include field descriptions as comments

### 3.2 Non-Functional Requirements

#### NFR-BULK-001: Performance
- Validation shall complete within 2 seconds for 100 users
- Import shall process 100 users within 30 seconds
- UI shall remain responsive during operations

#### NFR-BULK-002: Scalability
- System shall support up to 500 users per import
- System shall handle 10 concurrent imports across organizations

#### NFR-BULK-003: Usability
- JSON schema shall be simple and human-readable
- UI shall provide clear progress indicators
- Error messages shall be actionable
- Template shall be self-documenting

#### NFR-BULK-004: Security
- File uploads shall be scanned for malicious content
- JSON parsing shall prevent injection attacks
- Org-admins shall only import to their organization
- Audit logs shall track all bulk operations

#### NFR-BULK-005: Reliability
- Partial failures shall not rollback successful creations
- System shall recover gracefully from errors
- Operations shall be idempotent where possible

---

## 4. Architecture Design

### 4.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Bulk Import Architecture                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐                                  ┌──────────────┐
│   Frontend   │                                  │   Backend    │
│  Org Admin   │                                  │  API Layer   │
│     UI       │                                  │              │
└──────┬───────┘                                  └──────┬───────┘
       │                                                 │
       │ 1. Upload JSON file                            │
       ├────────────────────────────────────────────────►
       │                                                 │
       │                            2. Validate JSON    │
       │                               Parse structure  │
       │                               Check schema     │
       │                               Validate emails  │
       │                                                 │
       │ 3. Return validation results                   │
       │    (preview data)                               │
       │◄────────────────────────────────────────────────┤
       │                                                 │
       │ 4. Display preview                             │
       │    Show valid/invalid entries                  │
       │    Request confirmation                        │
       │                                                 │
       │ 5. Confirm import                              │
       ├────────────────────────────────────────────────►
       │                                                 │
       │                         ┌──────────────────────┤
       │                         │ 6. Create users loop │
       │                         │    For each user:    │
       │                         │    - Validate        │
       │                         │    - Create OWI user │
       │                         │    - Create LAMB user│
       │                         │    - Track result    │
       │                         └──────────────────────┤
       │                                                 │
       │ 7. Return detailed results                     │
       │◄────────────────────────────────────────────────┤
       │                                                 │
       │ 8. Display results table                       │
       │    Show success/failures                       │
       │    Provide download option                     │
       │                                                 │
       │ 9. User navigates to user list                 │
       │    Selects created users                       │
       │    Clicks "Enable Selected"                    │
       ├────────────────────────────────────────────────►
       │                                                 │
       │                         10. Bulk enable users  │
       │                             (existing endpoint)│
       │                                                 │
       │ 11. Return success                             │
       │◄────────────────────────────────────────────────┤
```

### 4.2 Data Flow

**Phase 1: Upload & Validation**
```
JSON File → Frontend → Backend (validation) → Preview Response → Frontend Display
```

**Phase 2: Import**
```
Confirmation → Backend (bulk create) → For each user:
    → Validate individually
    → Create OWI user
    → Create LAMB user
    → Record result
→ Aggregate results → Frontend Display
```

**Phase 3: Activation**
```
User Selection → Bulk Enable Request → Backend (existing) → Success
```

### 4.3 JSON Schema Design

**File Structure:**
```json
{
  "version": "1.0",
  "users": [
    {
      "email": "user1@example.com",
      "name": "John Doe",
      "user_type": "creator",
      "enabled": false
    },
    {
      "email": "user2@example.com",
      "name": "Jane Smith",
      "user_type": "end_user",
      "enabled": false
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `version` | string | Yes | - | Must be "1.0" |
| `users` | array | Yes | - | Min 1, Max 500 users |
| `users[].email` | string | Yes | - | Valid email, unique in file |
| `users[].name` | string | Yes | - | 1-100 chars |
| `users[].user_type` | string | No | "creator" | "creator" or "end_user" |
| `users[].enabled` | boolean | No | false | true or false |

**Validation Rules:**
1. Email must be unique within file
2. Email must not exist in organization
3. Email must be valid format
4. Name must not be empty
5. user_type must be valid enum value

---

## 5. Database Schema

### 5.1 New Tables

#### Bulk Import Log Table

**Purpose:** Track bulk import operations for audit and debugging

```sql
CREATE TABLE bulk_import_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    admin_user_id INTEGER NOT NULL,
    admin_email TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK(operation_type IN ('user_creation', 'user_activation')),
    total_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failure_count INTEGER NOT NULL,
    details JSON,  -- Stores per-user results
    created_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_user_id) REFERENCES Creator_users(id) ON DELETE SET NULL
);

CREATE INDEX idx_bulk_import_logs_org ON bulk_import_logs(organization_id);
CREATE INDEX idx_bulk_import_logs_admin ON bulk_import_logs(admin_user_id);
CREATE INDEX idx_bulk_import_logs_created ON bulk_import_logs(created_at);
```

**Details JSON Structure:**
```json
{
  "filename": "users_import_2025.json",
  "results": [
    {
      "email": "user1@example.com",
      "name": "John Doe",
      "status": "success",
      "user_id": 123
    },
    {
      "email": "user2@example.com",
      "name": "Jane Smith",
      "status": "failed",
      "error": "Email already exists"
    }
  ]
}
```

### 5.2 Database Manager Methods

**New Methods in `LambDatabaseManager`:**

```python
def log_bulk_import(
    self,
    organization_id: int,
    admin_user_id: int,
    admin_email: str,
    operation_type: str,
    total_count: int,
    success_count: int,
    failure_count: int,
    details: dict
) -> int:
    """Log a bulk import operation"""
    
def get_bulk_import_logs(
    self,
    organization_id: int = None,
    admin_user_id: int = None,
    limit: int = 50
) -> List[Dict]:
    """Retrieve bulk import logs"""
```

### 5.3 Migration Strategy

**Automatic Migration:**
```python
def run_migrations(self):
    """Add bulk import logging table if needed"""
    cursor = self.conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='bulk_import_logs'
    """)
    
    if not cursor.fetchone():
        # Create table
        cursor.execute("""
            CREATE TABLE bulk_import_logs (
                -- schema as above
            )
        """)
        # Create indexes
        cursor.execute("CREATE INDEX idx_bulk_import_logs_org ...")
        cursor.execute("CREATE INDEX idx_bulk_import_logs_admin ...")
        cursor.execute("CREATE INDEX idx_bulk_import_logs_created ...")
        
        self.conn.commit()
        logger.info("Created bulk_import_logs table")
```

---

## 6. Backend Implementation

### 6.1 API Endpoints

#### 6.1.1 Validate Import File

**Endpoint:** `POST /creator/admin/org-admin/users/bulk-import/validate`

**Purpose:** Validate JSON file and return preview

**Request:**
```http
POST /creator/admin/org-admin/users/bulk-import/validate
Authorization: Bearer {token}
Content-Type: multipart/form-data

file=@users_import.json
```

**Response (Success):**
```json
{
  "valid": true,
  "summary": {
    "total": 50,
    "valid": 48,
    "invalid": 2
  },
  "users": [
    {
      "email": "user1@example.com",
      "name": "John Doe",
      "user_type": "creator",
      "enabled": false,
      "valid": true,
      "errors": []
    },
    {
      "email": "invalid-email",
      "name": "Bad User",
      "user_type": "creator",
      "enabled": false,
      "valid": false,
      "errors": ["Invalid email format"]
    }
  ]
}
```

**Response (Invalid JSON):**
```json
{
  "valid": false,
  "error": "Invalid JSON syntax at line 5",
  "summary": null,
  "users": []
}
```

**Implementation:**
```python
@router.post("/org-admin/users/bulk-import/validate")
async def validate_bulk_import(
    file: UploadFile = File(...),
    request: Request = None
):
    """
    Validate bulk user import JSON file
    """
    # 1. Auth check - org admin only
    creator_user = get_creator_user_from_token(
        request.headers.get("Authorization")
    )
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not is_org_admin(creator_user):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    
    # 2. File size check
    if file.size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    # 3. Read and parse JSON
    try:
        content = await file.read()
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"Invalid JSON syntax: {str(e)}",
            "summary": None,
            "users": []
        }
    
    # 4. Validate schema
    validator = BulkImportValidator(creator_user['organization_id'])
    validation_result = validator.validate_import_data(data)
    
    return validation_result
```

#### 6.1.2 Execute Import

**Endpoint:** `POST /creator/admin/org-admin/users/bulk-import/execute`

**Purpose:** Create users from validated JSON

**Request:**
```http
POST /creator/admin/org-admin/users/bulk-import/execute
Authorization: Bearer {token}
Content-Type: application/json

{
  "users": [
    {
      "email": "user1@example.com",
      "name": "John Doe",
      "user_type": "creator",
      "enabled": false
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "summary": {
    "total": 50,
    "created": 48,
    "failed": 2,
    "skipped": 0
  },
  "results": [
    {
      "email": "user1@example.com",
      "name": "John Doe",
      "status": "success",
      "user_id": 123,
      "message": "User created successfully"
    },
    {
      "email": "duplicate@example.com",
      "name": "Duplicate User",
      "status": "failed",
      "user_id": null,
      "message": "Email already exists"
    }
  ],
  "log_id": 456
}
```

**Implementation:**
```python
@router.post("/org-admin/users/bulk-import/execute")
async def execute_bulk_import(
    import_data: BulkImportRequest,
    request: Request = None
):
    """
    Execute bulk user creation
    """
    # 1. Auth check
    creator_user = get_creator_user_from_token(
        request.headers.get("Authorization")
    )
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not is_org_admin(creator_user):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    
    # 2. Execute bulk creation
    bulk_creator = BulkUserCreator(
        organization_id=creator_user['organization_id'],
        admin_user_id=creator_user['id'],
        admin_email=creator_user['user_email']
    )
    
    result = await bulk_creator.create_users(import_data.users)
    
    # 3. Log operation
    db_manager = LambDatabaseManager()
    log_id = db_manager.log_bulk_import(
        organization_id=creator_user['organization_id'],
        admin_user_id=creator_user['id'],
        admin_email=creator_user['user_email'],
        operation_type='user_creation',
        total_count=result['summary']['total'],
        success_count=result['summary']['created'],
        failure_count=result['summary']['failed'],
        details={
            "filename": import_data.filename if hasattr(import_data, 'filename') else "direct_api",
            "results": result['results']
        }
    )
    
    result['log_id'] = log_id
    
    return result
```

#### 6.1.3 Download Template

**Endpoint:** `GET /creator/admin/org-admin/users/bulk-import/template`

**Purpose:** Download JSON template with examples

**Request:**
```http
GET /creator/admin/org-admin/users/bulk-import/template
Authorization: Bearer {token}
```

**Response:**
```json
{
  "_comment": "LAMB Bulk User Import Template v1.0",
  "_instructions": [
    "Fill in the users array with your user data",
    "Required fields: email, name",
    "Optional fields: user_type (default: creator), enabled (default: false)",
    "Valid user_types: creator, end_user",
    "Maximum 500 users per import"
  ],
  "version": "1.0",
  "users": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "user_type": "creator",
      "enabled": false
    },
    {
      "email": "jane.smith@example.com",
      "name": "Jane Smith",
      "user_type": "end_user",
      "enabled": false
    }
  ]
}
```

**Implementation:**
```python
@router.get("/org-admin/users/bulk-import/template")
async def download_bulk_import_template(request: Request = None):
    """
    Download bulk user import JSON template
    """
    # Auth check
    creator_user = get_creator_user_from_token(
        request.headers.get("Authorization")
    )
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not is_org_admin(creator_user):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    
    template = {
        "_comment": "LAMB Bulk User Import Template v1.0",
        "_instructions": [
            "Fill in the users array with your user data",
            "Required fields: email, name",
            "Optional fields: user_type (default: creator), enabled (default: false)",
            "Valid user_types: creator, end_user",
            "Maximum 500 users per import"
        ],
        "version": "1.0",
        "users": [
            {
                "email": "john.doe@example.com",
                "name": "John Doe",
                "user_type": "creator",
                "enabled": False
            },
            {
                "email": "jane.smith@example.com",
                "name": "Jane Smith",
                "user_type": "end_user",
                "enabled": False
            }
        ]
    }
    
    return JSONResponse(
        content=template,
        headers={
            "Content-Disposition": "attachment; filename=lamb_bulk_import_template.json"
        }
    )
```

#### 6.1.4 Leverage Existing Bulk Enable

**Endpoint:** `POST /creator/admin/org-admin/users/enable-bulk` (NEW)

**Purpose:** Enable multiple users (extend existing system admin endpoint)

**Request:**
```http
POST /creator/admin/org-admin/users/enable-bulk
Authorization: Bearer {token}
Content-Type: application/json

{
  "user_ids": [1, 2, 3, 4, 5]
}
```

**Response:** (Same as system admin version)

**Implementation:**
```python
@router.post("/org-admin/users/enable-bulk")
async def org_admin_enable_users_bulk(
    request_data: BulkUserActionRequest,
    request: Request = None
):
    """
    Enable multiple users (org-admin version)
    """
    # Auth check
    creator_user = get_creator_user_from_token(
        request.headers.get("Authorization")
    )
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not is_org_admin(creator_user):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    
    # Filter to only users in same organization
    db_manager = LambDatabaseManager()
    user_ids = request_data.user_ids
    
    # Verify all users belong to admin's organization
    valid_user_ids = []
    for user_id in user_ids:
        user = db_manager.get_creator_user_by_id(user_id)
        if user and user['organization_id'] == creator_user['organization_id']:
            valid_user_ids.append(user_id)
    
    if not valid_user_ids:
        raise HTTPException(
            status_code=400,
            detail="No valid users found in your organization"
        )
    
    # Execute bulk enable
    result = db_manager.enable_users_bulk(valid_user_ids)
    
    return {
        "success": True,
        "enabled": len(result['success']),
        "failed": len(result['failed']),
        "already_enabled": len(result['already_enabled']),
        "details": result
    }
```

### 6.2 Core Business Logic Classes

#### 6.2.1 BulkImportValidator

**File:** `backend/utils/bulk_import_validator.py`

```python
import re
from typing import Dict, List, Any
from backend.lamb.database_manager import LambDatabaseManager

class BulkImportValidator:
    """Validates bulk user import data"""
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    MAX_USERS = 500
    VALID_USER_TYPES = ['creator', 'end_user']
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.db_manager = LambDatabaseManager()
    
    def validate_import_data(self, data: Dict) -> Dict:
        """
        Validate entire import data structure
        
        Returns:
            {
                "valid": bool,
                "summary": {"total": int, "valid": int, "invalid": int},
                "users": [validated user objects],
                "error": str (if schema invalid)
            }
        """
        # 1. Validate top-level structure
        if not isinstance(data, dict):
            return self._error_response("Data must be a JSON object")
        
        if 'version' not in data:
            return self._error_response("Missing 'version' field")
        
        if data['version'] != '1.0':
            return self._error_response(f"Unsupported version: {data['version']}")
        
        if 'users' not in data:
            return self._error_response("Missing 'users' array")
        
        if not isinstance(data['users'], list):
            return self._error_response("'users' must be an array")
        
        if len(data['users']) == 0:
            return self._error_response("'users' array cannot be empty")
        
        if len(data['users']) > self.MAX_USERS:
            return self._error_response(
                f"Too many users (max {self.MAX_USERS}, got {len(data['users'])})"
            )
        
        # 2. Validate each user
        validated_users = []
        emails_in_file = set()
        
        for idx, user in enumerate(data['users']):
            validated_user = self._validate_user(user, idx, emails_in_file)
            validated_users.append(validated_user)
            
            if validated_user['valid']:
                emails_in_file.add(validated_user['email'])
        
        # 3. Generate summary
        valid_count = sum(1 for u in validated_users if u['valid'])
        invalid_count = len(validated_users) - valid_count
        
        return {
            "valid": invalid_count == 0,
            "summary": {
                "total": len(validated_users),
                "valid": valid_count,
                "invalid": invalid_count
            },
            "users": validated_users,
            "error": None
        }
    
    def _validate_user(
        self, 
        user: Dict, 
        index: int, 
        emails_in_file: set
    ) -> Dict:
        """
        Validate individual user
        
        Returns:
            {
                "email": str,
                "name": str,
                "user_type": str,
                "enabled": bool,
                "valid": bool,
                "errors": [str]
            }
        """
        errors = []
        
        # Extract fields with defaults
        email = user.get('email', '').strip()
        name = user.get('name', '').strip()
        user_type = user.get('user_type', 'creator')
        enabled = user.get('enabled', False)
        
        # Validate email
        if not email:
            errors.append("Email is required")
        elif not self.EMAIL_REGEX.match(email):
            errors.append("Invalid email format")
        elif email in emails_in_file:
            errors.append("Duplicate email in file")
        else:
            # Check if email exists in organization
            existing_user = self.db_manager.get_creator_user_by_email(email)
            if existing_user:
                if existing_user['organization_id'] == self.organization_id:
                    errors.append("Email already exists in organization")
        
        # Validate name
        if not name:
            errors.append("Name is required")
        elif len(name) > 100:
            errors.append("Name too long (max 100 characters)")
        
        # Validate user_type
        if user_type not in self.VALID_USER_TYPES:
            errors.append(f"Invalid user_type (must be one of: {', '.join(self.VALID_USER_TYPES)})")
        
        # Validate enabled
        if not isinstance(enabled, bool):
            errors.append("enabled must be boolean (true/false)")
        
        return {
            "email": email,
            "name": name,
            "user_type": user_type,
            "enabled": enabled,
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _error_response(self, error: str) -> Dict:
        """Return error response"""
        return {
            "valid": False,
            "summary": None,
            "users": [],
            "error": error
        }
```

#### 6.2.2 BulkUserCreator

**File:** `backend/utils/bulk_user_creator.py`

```python
import logging
from typing import List, Dict, Any
from backend.utils.pipelines.user_creator_manager import UserCreatorManager
from backend.lamb.database_manager import LambDatabaseManager

logger = logging.getLogger(__name__)

class BulkUserCreator:
    """Handles bulk user creation with detailed result tracking"""
    
    def __init__(
        self,
        organization_id: int,
        admin_user_id: int,
        admin_email: str
    ):
        self.organization_id = organization_id
        self.admin_user_id = admin_user_id
        self.admin_email = admin_email
        self.user_creator = UserCreatorManager()
        self.db_manager = LambDatabaseManager()
    
    async def create_users(self, users: List[Dict]) -> Dict:
        """
        Create multiple users with result tracking
        
        Args:
            users: List of user dicts with email, name, user_type, enabled
        
        Returns:
            {
                "success": bool,
                "summary": {
                    "total": int,
                    "created": int,
                    "failed": int,
                    "skipped": int
                },
                "results": [
                    {
                        "email": str,
                        "name": str,
                        "status": "success" | "failed" | "skipped",
                        "user_id": int | None,
                        "message": str
                    }
                ]
            }
        """
        results = []
        created_count = 0
        failed_count = 0
        skipped_count = 0
        
        logger.info(
            f"Bulk user creation started by {self.admin_email} "
            f"for organization {self.organization_id}: {len(users)} users"
        )
        
        for user in users:
            result = await self._create_single_user(user)
            results.append(result)
            
            if result['status'] == 'success':
                created_count += 1
            elif result['status'] == 'failed':
                failed_count += 1
            elif result['status'] == 'skipped':
                skipped_count += 1
        
        logger.info(
            f"Bulk user creation completed: "
            f"{created_count} created, {failed_count} failed, {skipped_count} skipped"
        )
        
        return {
            "success": True,
            "summary": {
                "total": len(users),
                "created": created_count,
                "failed": failed_count,
                "skipped": skipped_count
            },
            "results": results
        }
    
    async def _create_single_user(self, user: Dict) -> Dict:
        """
        Create a single user with error handling
        
        Returns:
            {
                "email": str,
                "name": str,
                "status": str,
                "user_id": int | None,
                "message": str
            }
        """
        email = user['email']
        name = user['name']
        user_type = user.get('user_type', 'creator')
        enabled = user.get('enabled', False)
        
        try:
            # Check if user already exists (shouldn't happen if validation worked)
            existing_user = self.db_manager.get_creator_user_by_email(email)
            if existing_user:
                logger.warning(f"User {email} already exists, skipping")
                return {
                    "email": email,
                    "name": name,
                    "status": "skipped",
                    "user_id": existing_user['id'],
                    "message": "User already exists"
                }
            
            # Generate random secure password
            import secrets
            password = secrets.token_urlsafe(32)
            
            # Create user via UserCreatorManager
            result = await self.user_creator.create_user(
                email=email,
                name=name,
                password=password,
                role='user',  # Default role
                organization_id=self.organization_id,
                user_type=user_type
            )
            
            if not result.get('success'):
                logger.error(f"Failed to create user {email}: {result.get('message')}")
                return {
                    "email": email,
                    "name": name,
                    "status": "failed",
                    "user_id": None,
                    "message": result.get('message', 'Unknown error')
                }
            
            user_id = result['user_id']
            
            # Set enabled status if different from default
            if not enabled:
                self.db_manager.disable_user(user_id)
            
            logger.info(f"Created user {email} (ID: {user_id})")
            
            return {
                "email": email,
                "name": name,
                "status": "success",
                "user_id": user_id,
                "message": "User created successfully"
            }
        
        except Exception as e:
            logger.error(f"Exception creating user {email}: {str(e)}", exc_info=True)
            return {
                "email": email,
                "name": name,
                "status": "failed",
                "user_id": None,
                "message": f"Error: {str(e)}"
            }
```

### 6.3 Request/Response Models

**File:** `backend/schemas.py` (add to existing)

```python
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class BulkImportUser(BaseModel):
    """Single user in bulk import"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    user_type: str = Field(default='creator', pattern='^(creator|end_user)$')
    enabled: bool = False

class BulkImportRequest(BaseModel):
    """Bulk import execution request"""
    users: List[BulkImportUser] = Field(..., min_items=1, max_items=500)
    filename: Optional[str] = None

class BulkUserActionRequest(BaseModel):
    """Bulk enable/disable request"""
    user_ids: List[int] = Field(..., min_items=1, max_items=500)
```

---

## 7. Frontend Implementation

### 7.1 New Components

#### 7.1.1 BulkUserImport.svelte

**File:** `frontend/svelte-app/src/lib/components/admin/BulkUserImport.svelte`

**Purpose:** Complete bulk import wizard

```svelte
<script>
  import { onMount } from 'svelte';
  import { 
    validateBulkImport, 
    executeBulkImport, 
    downloadImportTemplate 
  } from '$lib/services/orgAdminService.js';
  import { userStore } from '$lib/stores/userStore.js';
  
  // State
  let currentStep = $state(1); // 1: Upload, 2: Preview, 3: Results
  let file = $state(null);
  let uploading = $state(false);
  let validationResult = $state(null);
  let importing = $state(false);
  let importResult = $state(null);
  let filterStatus = $state('all'); // 'all', 'valid', 'invalid'
  
  // Computed
  let filteredUsers = $derived(() => {
    if (!validationResult?.users) return [];
    
    if (filterStatus === 'valid') {
      return validationResult.users.filter(u => u.valid);
    } else if (filterStatus === 'invalid') {
      return validationResult.users.filter(u => !u.valid);
    }
    return validationResult.users;
  });
  
  // Handlers
  function handleFileChange(event) {
    const files = event.target.files;
    if (files && files.length > 0) {
      file = files[0];
    }
  }
  
  async function handleUpload() {
    if (!file) return;
    
    uploading = true;
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      validationResult = await validateBulkImport(
        $userStore.token,
        formData
      );
      
      if (validationResult.valid || validationResult.summary) {
        currentStep = 2; // Move to preview
      } else {
        alert('Validation failed: ' + validationResult.error);
      }
    } catch (error) {
      alert('Upload failed: ' + error.message);
    } finally {
      uploading = false;
    }
  }
  
  async function handleImport() {
    if (!validationResult) return;
    
    // Only import valid users
    const validUsers = validationResult.users.filter(u => u.valid);
    
    if (validUsers.length === 0) {
      alert('No valid users to import');
      return;
    }
    
    const confirmMsg = `Import ${validUsers.length} user(s)? They will be created in disabled state.`;
    if (!confirm(confirmMsg)) return;
    
    importing = true;
    try {
      importResult = await executeBulkImport($userStore.token, {
        users: validUsers,
        filename: file.name
      });
      
      currentStep = 3; // Move to results
    } catch (error) {
      alert('Import failed: ' + error.message);
    } finally {
      importing = false;
    }
  }
  
  function handleReset() {
    currentStep = 1;
    file = null;
    validationResult = null;
    importResult = null;
    filterStatus = 'all';
  }
  
  async function handleDownloadTemplate() {
    try {
      await downloadImportTemplate($userStore.token);
    } catch (error) {
      alert('Download failed: ' + error.message);
    }
  }
  
  function downloadResults() {
    if (!importResult) return;
    
    const blob = new Blob(
      [JSON.stringify(importResult, null, 2)],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `import_results_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="bulk-import-wizard card bg-base-100 shadow-xl p-6">
  <h2 class="card-title text-2xl mb-4">Bulk User Import</h2>
  
  <!-- Progress Steps -->
  <div class="steps mb-8">
    <div class="step" class:step-primary={currentStep >= 1}>Upload</div>
    <div class="step" class:step-primary={currentStep >= 2}>Preview</div>
    <div class="step" class:step-primary={currentStep >= 3}>Results</div>
  </div>
  
  <!-- Step 1: Upload -->
  {#if currentStep === 1}
    <div class="upload-section">
      <p class="mb-4">
        Upload a JSON file with user information. Maximum 500 users per file.
      </p>
      
      <button 
        class="btn btn-outline btn-sm mb-4" 
        onclick={handleDownloadTemplate}
      >
        📥 Download Template
      </button>
      
      <div class="form-control">
        <label class="label">
          <span class="label-text">Select JSON File</span>
        </label>
        <input 
          type="file" 
          accept=".json"
          class="file-input file-input-bordered w-full"
          onchange={handleFileChange}
        />
      </div>
      
      {#if file}
        <p class="text-sm mt-2">Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
      {/if}
      
      <button 
        class="btn btn-primary mt-4"
        disabled={!file || uploading}
        onclick={handleUpload}
      >
        {uploading ? 'Validating...' : 'Upload & Validate'}
      </button>
    </div>
  {/if}
  
  <!-- Step 2: Preview -->
  {#if currentStep === 2 && validationResult}
    <div class="preview-section">
      <!-- Summary -->
      <div class="stats shadow mb-4">
        <div class="stat">
          <div class="stat-title">Total Users</div>
          <div class="stat-value">{validationResult.summary.total}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Valid</div>
          <div class="stat-value text-success">{validationResult.summary.valid}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Invalid</div>
          <div class="stat-value text-error">{validationResult.summary.invalid}</div>
        </div>
      </div>
      
      <!-- Filter -->
      <div class="tabs tabs-boxed mb-4">
        <button 
          class="tab" 
          class:tab-active={filterStatus === 'all'}
          onclick={() => filterStatus = 'all'}
        >
          All ({validationResult.summary.total})
        </button>
        <button 
          class="tab" 
          class:tab-active={filterStatus === 'valid'}
          onclick={() => filterStatus = 'valid'}
        >
          Valid ({validationResult.summary.valid})
        </button>
        <button 
          class="tab" 
          class:tab-active={filterStatus === 'invalid'}
          onclick={() => filterStatus = 'invalid'}
        >
          Invalid ({validationResult.summary.invalid})
        </button>
      </div>
      
      <!-- User List -->
      <div class="overflow-x-auto max-h-96">
        <table class="table table-zebra table-sm">
          <thead>
            <tr>
              <th>Status</th>
              <th>Email</th>
              <th>Name</th>
              <th>Type</th>
              <th>Enabled</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredUsers() as user}
              <tr>
                <td>
                  {#if user.valid}
                    <span class="badge badge-success">✓</span>
                  {:else}
                    <span class="badge badge-error">✗</span>
                  {/if}
                </td>
                <td>{user.email}</td>
                <td>{user.name}</td>
                <td>{user.user_type}</td>
                <td>{user.enabled ? 'Yes' : 'No'}</td>
                <td>
                  {#if user.errors && user.errors.length > 0}
                    <ul class="text-error text-xs">
                      {#each user.errors as error}
                        <li>• {error}</li>
                      {/each}
                    </ul>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      
      <!-- Actions -->
      <div class="flex gap-4 mt-6">
        <button class="btn btn-outline" onclick={handleReset}>
          Cancel
        </button>
        <button 
          class="btn btn-primary"
          disabled={validationResult.summary.valid === 0 || importing}
          onclick={handleImport}
        >
          {importing ? 'Importing...' : `Import ${validationResult.summary.valid} Valid User(s)`}
        </button>
      </div>
    </div>
  {/if}
  
  <!-- Step 3: Results -->
  {#if currentStep === 3 && importResult}
    <div class="results-section">
      <!-- Summary -->
      <div class="alert alert-success mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Import completed! {importResult.summary.created} user(s) created successfully.</span>
      </div>
      
      <div class="stats shadow mb-4">
        <div class="stat">
          <div class="stat-title">Total</div>
          <div class="stat-value">{importResult.summary.total}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Created</div>
          <div class="stat-value text-success">{importResult.summary.created}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Failed</div>
          <div class="stat-value text-error">{importResult.summary.failed}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Skipped</div>
          <div class="stat-value text-warning">{importResult.summary.skipped}</div>
        </div>
      </div>
      
      <!-- Detailed Results -->
      <div class="overflow-x-auto max-h-96">
        <table class="table table-zebra table-sm">
          <thead>
            <tr>
              <th>Status</th>
              <th>Email</th>
              <th>Name</th>
              <th>User ID</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {#each importResult.results as result}
              <tr>
                <td>
                  {#if result.status === 'success'}
                    <span class="badge badge-success">Success</span>
                  {:else if result.status === 'failed'}
                    <span class="badge badge-error">Failed</span>
                  {:else}
                    <span class="badge badge-warning">Skipped</span>
                  {/if}
                </td>
                <td>{result.email}</td>
                <td>{result.name}</td>
                <td>{result.user_id || 'N/A'}</td>
                <td class="text-sm">{result.message}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      
      <!-- Actions -->
      <div class="flex gap-4 mt-6">
        <button class="btn btn-outline" onclick={downloadResults}>
          📥 Download Results
        </button>
        <button class="btn btn-primary" onclick={handleReset}>
          Import More Users
        </button>
        <a href="/org-admin" class="btn btn-success">
          Go to User List
        </a>
      </div>
    </div>
  {/if}
</div>
```

#### 7.1.2 Integrate into Org Admin Page

**File:** `frontend/svelte-app/src/routes/org-admin/+page.svelte`

**Add bulk import section:**

```svelte
<script>
  import BulkUserImport from '$lib/components/admin/BulkUserImport.svelte';
  import { /* existing imports */ } from '$lib/services/orgAdminService.js';
  
  let showBulkImport = $state(false);
  let selectedUsers = $state([]);
  
  // ... existing code ...
  
  async function handleBulkEnable() {
    if (selectedUsers.length === 0) return;
    
    if (!confirm(`Enable ${selectedUsers.length} selected user(s)?`)) return;
    
    try {
      const result = await enableUsersBulk($userStore.token, selectedUsers);
      alert(`Successfully enabled ${result.enabled} user(s)`);
      await loadUsers(); // Refresh list
      selectedUsers = [];
    } catch (error) {
      alert('Bulk enable failed: ' + error.message);
    }
  }
  
  function toggleUserSelection(userId) {
    if (selectedUsers.includes(userId)) {
      selectedUsers = selectedUsers.filter(id => id !== userId);
    } else {
      selectedUsers = [...selectedUsers, userId];
    }
  }
</script>

<div class="org-admin-page">
  <h1>Organization Admin Panel</h1>
  
  <!-- Tabs -->
  <div class="tabs tabs-boxed mb-4">
    <button 
      class="tab" 
      class:tab-active={!showBulkImport}
      onclick={() => showBulkImport = false}
    >
      User Management
    </button>
    <button 
      class="tab" 
      class:tab-active={showBulkImport}
      onclick={() => showBulkImport = true}
    >
      Bulk Import
    </button>
  </div>
  
  {#if showBulkImport}
    <BulkUserImport />
  {:else}
    <!-- Existing user management UI -->
    
    <!-- Bulk Actions Toolbar -->
    {#if selectedUsers.length > 0}
      <div class="bulk-actions-toolbar alert alert-info mb-4">
        <span>{selectedUsers.length} user(s) selected</span>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-success" onclick={handleBulkEnable}>
            Enable Selected
          </button>
          <button class="btn btn-sm" onclick={() => selectedUsers = []}>
            Clear Selection
          </button>
        </div>
      </div>
    {/if}
    
    <!-- User Table with Selection -->
    <table class="table">
      <thead>
        <tr>
          <th>
            <input 
              type="checkbox" 
              class="checkbox"
              onchange={(e) => {
                if (e.target.checked) {
                  selectedUsers = users.map(u => u.id);
                } else {
                  selectedUsers = [];
                }
              }}
            />
          </th>
          <!-- ... other headers ... -->
        </tr>
      </thead>
      <tbody>
        {#each users as user}
          <tr>
            <td>
              <input 
                type="checkbox" 
                class="checkbox"
                checked={selectedUsers.includes(user.id)}
                onchange={() => toggleUserSelection(user.id)}
              />
            </td>
            <!-- ... other columns ... -->
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
```

### 7.2 Service Layer Updates

**File:** `frontend/svelte-app/src/lib/services/orgAdminService.js`

**Add new methods:**

```javascript
import { getApiUrl } from '$lib/config.js';

/**
 * Validate bulk import JSON file
 */
export async function validateBulkImport(token, formData) {
  const response = await fetch(
    getApiUrl('/admin/org-admin/users/bulk-import/validate'),
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Validation failed');
  }
  
  return await response.json();
}

/**
 * Execute bulk user import
 */
export async function executeBulkImport(token, importData) {
  const response = await fetch(
    getApiUrl('/admin/org-admin/users/bulk-import/execute'),
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(importData)
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Import failed');
  }
  
  return await response.json();
}

/**
 * Download bulk import template
 */
export async function downloadImportTemplate(token) {
  const response = await fetch(
    getApiUrl('/admin/org-admin/users/bulk-import/template'),
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Download failed');
  }
  
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'lamb_bulk_import_template.json';
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Bulk enable users (org-admin version)
 */
export async function enableUsersBulk(token, userIds) {
  const response = await fetch(
    getApiUrl('/admin/org-admin/users/enable-bulk'),
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user_ids: userIds })
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Bulk enable failed');
  }
  
  return await response.json();
}
```

---

## 8. Security Considerations

### 8.1 Authentication & Authorization

**✅ Enforced:**
- All endpoints require Bearer token authentication
- Org-admin role verified for all bulk operations
- Users can only import to their own organization
- Self-activation prevention (admin cannot disable self)

**Implementation:**
```python
# Check org-admin role
if not is_org_admin(creator_user):
    raise HTTPException(status_code=403, detail="Org admin required")

# Verify users belong to admin's organization
for user_id in user_ids:
    user = db_manager.get_creator_user_by_id(user_id)
    if user['organization_id'] != creator_user['organization_id']:
        raise HTTPException(status_code=403, detail="Unauthorized")
```

### 8.2 Input Validation

**✅ Protected Against:**
- JSON injection attacks (strict schema validation)
- SQL injection (parameterized queries)
- Email format spoofing (regex validation)
- Resource exhaustion (500 user limit per import)
- File size bombs (5MB limit)

**Validation Layers:**
1. File size check (5MB max)
2. JSON syntax validation
3. Schema structure validation
4. Field-level validation (email, name, user_type)
5. Business logic validation (duplicates, existing users)

### 8.3 File Upload Security

**✅ Protections:**
- File extension whitelist (.json only)
- MIME type validation
- File size limits (5MB)
- Content parsing in memory (no disk writes)
- No script execution

**Implementation:**
```python
# File validation
if file.size > 5 * 1024 * 1024:
    raise HTTPException(status_code=400, detail="File too large")

if not file.filename.endswith('.json'):
    raise HTTPException(status_code=400, detail="Only .json files allowed")

# Safe parsing
try:
    content = await file.read()
    data = json.loads(content)
except json.JSONDecodeError:
    return {"error": "Invalid JSON"}
```

### 8.4 Password Security

**✅ Best Practices:**
- Random secure passwords generated (32 bytes, URL-safe)
- Passwords never returned in API responses
- Passwords hashed with bcrypt (cost factor 12)
- Passwords stored only in OWI auth table

**Implementation:**
```python
import secrets
password = secrets.token_urlsafe(32)  # 256-bit entropy
```

### 8.5 Audit Trail

**✅ Logged:**
- All bulk operations with admin info
- Success/failure counts
- Individual user creation results
- Timestamps
- Organization context

**Log Structure:**
```json
{
  "operation_type": "user_creation",
  "admin_email": "admin@org.com",
  "organization_id": 5,
  "total_count": 50,
  "success_count": 48,
  "failure_count": 2,
  "created_at": 1730678400,
  "details": {
    "filename": "users_import.json",
    "results": [...]
  }
}
```

### 8.6 Rate Limiting (Future Enhancement)

**Recommended:**
- 10 imports per organization per hour
- 100 imports per organization per day
- Alert on excessive failed attempts

---

## 9. Error Handling

### 9.1 Error Categories

| Category | HTTP Code | Example | Handling |
|----------|-----------|---------|----------|
| **Validation Errors** | 400 | Invalid email format | Show in preview, allow correction |
| **Authentication Errors** | 401 | Invalid/expired token | Redirect to login |
| **Authorization Errors** | 403 | Not org-admin | Show error message |
| **Resource Errors** | 404 | Organization not found | Show error message |
| **Conflict Errors** | 409 | Email already exists | Mark as invalid in preview |
| **Server Errors** | 500 | Database failure | Show retry option |

### 9.2 Partial Success Handling

**Strategy:** Continue processing on individual failures

**Example:**
- Import 50 users
- 48 succeed, 2 fail (duplicate emails)
- Result: Success status with detailed breakdown
- User sees: "48 created, 2 failed" with error details

**Benefits:**
- No need to rollback successful creations
- Users can fix failures and re-import
- Clear feedback on what worked

### 9.3 Error Messages

**User-Friendly Messages:**

```javascript
// Validation errors
"Invalid email format" → "Please check the email address format"
"Email already exists" → "This email is already registered in your organization"
"Name too long" → "Name must be 100 characters or less"

// System errors
"Database error" → "System error occurred. Please try again later."
"Network error" → "Connection failed. Please check your internet connection."
```

### 9.4 Frontend Error Display

**Validation Phase:**
```svelte
{#if user.errors && user.errors.length > 0}
  <ul class="text-error text-xs">
    {#each user.errors as error}
      <li>• {error}</li>
    {/each}
  </ul>
{/if}
```

**Import Phase:**
```svelte
{#if importResult.summary.failed > 0}
  <div class="alert alert-warning">
    <span>
      {importResult.summary.failed} user(s) could not be created.
      Check the results table below for details.
    </span>
  </div>
{/if}
```

### 9.5 Retry Logic

**Idempotency:**
- Duplicate email detection prevents double-creation
- Safe to retry entire import after fixing errors
- Results downloadable for record-keeping

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Backend Tests:** `tests/test_bulk_import.py`

```python
import pytest
from backend.utils.bulk_import_validator import BulkImportValidator
from backend.utils.bulk_user_creator import BulkUserCreator

class TestBulkImportValidator:
    def test_valid_json(self):
        """Test validation of valid JSON"""
        validator = BulkImportValidator(organization_id=1)
        data = {
            "version": "1.0",
            "users": [
                {
                    "email": "test@example.com",
                    "name": "Test User",
                    "user_type": "creator",
                    "enabled": False
                }
            ]
        }
        result = validator.validate_import_data(data)
        assert result['valid'] is True
        assert result['summary']['valid'] == 1
    
    def test_invalid_email(self):
        """Test rejection of invalid email"""
        validator = BulkImportValidator(organization_id=1)
        data = {
            "version": "1.0",
            "users": [
                {
                    "email": "not-an-email",
                    "name": "Test User",
                    "user_type": "creator",
                    "enabled": False
                }
            ]
        }
        result = validator.validate_import_data(data)
        assert result['valid'] is False
        assert result['summary']['invalid'] == 1
        assert 'Invalid email format' in result['users'][0]['errors']
    
    def test_duplicate_emails_in_file(self):
        """Test detection of duplicate emails"""
        validator = BulkImportValidator(organization_id=1)
        data = {
            "version": "1.0",
            "users": [
                {
                    "email": "duplicate@example.com",
                    "name": "User 1",
                    "user_type": "creator",
                    "enabled": False
                },
                {
                    "email": "duplicate@example.com",
                    "name": "User 2",
                    "user_type": "creator",
                    "enabled": False
                }
            ]
        }
        result = validator.validate_import_data(data)
        assert result['summary']['invalid'] >= 1
        assert any('Duplicate email' in err 
                   for u in result['users'] 
                   for err in u['errors'])
    
    def test_max_users_limit(self):
        """Test enforcement of max users limit"""
        validator = BulkImportValidator(organization_id=1)
        data = {
            "version": "1.0",
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "name": f"User {i}",
                    "user_type": "creator",
                    "enabled": False
                }
                for i in range(501)  # Exceed limit
            ]
        }
        result = validator.validate_import_data(data)
        assert result['valid'] is False
        assert 'Too many users' in result['error']

class TestBulkUserCreator:
    @pytest.mark.asyncio
    async def test_create_single_user_success(self):
        """Test successful user creation"""
        creator = BulkUserCreator(
            organization_id=1,
            admin_user_id=1,
            admin_email="admin@example.com"
        )
        
        users = [
            {
                "email": "newuser@example.com",
                "name": "New User",
                "user_type": "creator",
                "enabled": False
            }
        ]
        
        result = await creator.create_users(users)
        assert result['success'] is True
        assert result['summary']['created'] == 1
        assert result['results'][0]['status'] == 'success'
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_skip(self):
        """Test skipping duplicate users"""
        # Create initial user
        # ... setup code ...
        
        creator = BulkUserCreator(
            organization_id=1,
            admin_user_id=1,
            admin_email="admin@example.com"
        )
        
        users = [
            {
                "email": "existing@example.com",
                "name": "Existing User",
                "user_type": "creator",
                "enabled": False
            }
        ]
        
        result = await creator.create_users(users)
        assert result['summary']['skipped'] == 1
        assert result['results'][0]['status'] == 'skipped'
```

### 10.2 Integration Tests

**API Tests:** `tests/test_bulk_import_api.py`

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestBulkImportAPI:
    def test_validate_endpoint_requires_auth(self):
        """Test authentication requirement"""
        response = client.post("/creator/admin/org-admin/users/bulk-import/validate")
        assert response.status_code == 401
    
    def test_validate_endpoint_requires_org_admin(self):
        """Test org-admin authorization"""
        # Login as regular user
        token = get_user_token(email="user@example.com")
        
        response = client.post(
            "/creator/admin/org-admin/users/bulk-import/validate",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.json", b'{"version":"1.0","users":[]}')}
        )
        assert response.status_code == 403
    
    def test_execute_bulk_import(self):
        """Test successful bulk import"""
        token = get_org_admin_token()
        
        import_data = {
            "users": [
                {
                    "email": "bulk1@example.com",
                    "name": "Bulk User 1",
                    "user_type": "creator",
                    "enabled": False
                },
                {
                    "email": "bulk2@example.com",
                    "name": "Bulk User 2",
                    "user_type": "end_user",
                    "enabled": False
                }
            ]
        }
        
        response = client.post(
            "/creator/admin/org-admin/users/bulk-import/execute",
            headers={"Authorization": f"Bearer {token}"},
            json=import_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['summary']['created'] == 2
```

### 10.3 End-to-End Tests

**Playwright Tests:** `testing/playwright/bulk_import/test_bulk_import_flow.js`

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Bulk User Import', () => {
  test.beforeEach(async ({ page }) => {
    // Login as org-admin
    await page.goto('http://localhost:5173/login');
    await page.fill('input[name="email"]', 'orgadmin@example.com');
    await page.fill('input[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/assistants');
  });
  
  test('Complete bulk import workflow', async ({ page }) => {
    // 1. Navigate to org-admin
    await page.goto('http://localhost:5173/org-admin');
    
    // 2. Click bulk import tab
    await page.click('text=Bulk Import');
    
    // 3. Download template
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('text=Download Template')
    ]);
    expect(download.suggestedFilename()).toBe('lamb_bulk_import_template.json');
    
    // 4. Upload JSON file
    const fileInput = await page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test_import.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({
        version: '1.0',
        users: [
          {
            email: 'e2etest1@example.com',
            name: 'E2E Test User 1',
            user_type: 'creator',
            enabled: false
          },
          {
            email: 'e2etest2@example.com',
            name: 'E2E Test User 2',
            user_type: 'end_user',
            enabled: false
          }
        ]
      }))
    });
    
    // 5. Upload and validate
    await page.click('text=Upload & Validate');
    await page.waitForSelector('.preview-section');
    
    // 6. Verify preview
    await expect(page.locator('text=Valid')).toContainText('2');
    await expect(page.locator('text=Invalid')).toContainText('0');
    
    // 7. Execute import
    await page.click('text=Import 2 Valid User(s)');
    page.on('dialog', dialog => dialog.accept()); // Accept confirmation
    await page.waitForSelector('.results-section');
    
    // 8. Verify results
    await expect(page.locator('text=Created')).toContainText('2');
    await expect(page.locator('text=Failed')).toContainText('0');
    
    // 9. Go to user list
    await page.click('text=Go to User List');
    await page.waitForURL('**/org-admin');
    
    // 10. Verify users appear in list
    await expect(page.locator('text=e2etest1@example.com')).toBeVisible();
    await expect(page.locator('text=e2etest2@example.com')).toBeVisible();
    
    // 11. Select users for activation
    const checkboxes = await page.locator('input[type="checkbox"]').all();
    for (const checkbox of checkboxes.slice(0, 2)) {
      await checkbox.check();
    }
    
    // 12. Bulk enable
    await page.click('text=Enable Selected');
    page.on('dialog', dialog => dialog.accept());
    await page.waitForTimeout(1000);
    
    // 13. Verify enabled status
    await expect(page.locator('text=Active').first()).toBeVisible();
  });
  
  test('Handle validation errors', async ({ page }) => {
    await page.goto('http://localhost:5173/org-admin');
    await page.click('text=Bulk Import');
    
    // Upload invalid JSON
    const fileInput = await page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'invalid.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({
        version: '1.0',
        users: [
          {
            email: 'invalid-email',  // Invalid format
            name: 'Bad User',
            user_type: 'creator',
            enabled: false
          }
        ]
      }))
    });
    
    await page.click('text=Upload & Validate');
    await page.waitForSelector('.preview-section');
    
    // Verify error shown
    await expect(page.locator('text=Invalid')).toContainText('1');
    await expect(page.locator('text=Invalid email format')).toBeVisible();
    
    // Import button should show 0 valid users
    await expect(page.locator('button[disabled]')).toContainText('Import 0 Valid User(s)');
  });
});
```

### 10.4 Performance Tests

**Load Test:** `tests/test_bulk_import_performance.py`

```python
import pytest
import time
from backend.utils.bulk_import_validator import BulkImportValidator
from backend.utils.bulk_user_creator import BulkUserCreator

def test_validate_100_users_performance():
    """Ensure validation completes within 2 seconds for 100 users"""
    validator = BulkImportValidator(organization_id=1)
    
    data = {
        "version": "1.0",
        "users": [
            {
                "email": f"perftest{i}@example.com",
                "name": f"Perf Test User {i}",
                "user_type": "creator",
                "enabled": False
            }
            for i in range(100)
        ]
    }
    
    start_time = time.time()
    result = validator.validate_import_data(data)
    elapsed_time = time.time() - start_time
    
    assert elapsed_time < 2.0, f"Validation took {elapsed_time:.2f}s (limit: 2s)"
    assert result['valid'] is True

@pytest.mark.asyncio
async def test_create_100_users_performance():
    """Ensure creation completes within 30 seconds for 100 users"""
    creator = BulkUserCreator(
        organization_id=1,
        admin_user_id=1,
        admin_email="admin@example.com"
    )
    
    users = [
        {
            "email": f"perfcreate{i}@example.com",
            "name": f"Perf Create User {i}",
            "user_type": "creator",
            "enabled": False
        }
        for i in range(100)
    ]
    
    start_time = time.time()
    result = await creator.create_users(users)
    elapsed_time = time.time() - start_time
    
    assert elapsed_time < 30.0, f"Creation took {elapsed_time:.2f}s (limit: 30s)"
    assert result['summary']['created'] == 100
```

### 10.5 Test Data

**Sample Import Files:**

**Valid file:** `tests/fixtures/valid_import.json`
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

**Invalid file:** `tests/fixtures/invalid_import.json`
```json
{
  "version": "1.0",
  "users": [
    {
      "email": "not-an-email",
      "name": "",
      "user_type": "invalid_type",
      "enabled": "not_boolean"
    }
  ]
}
```

---

## 11. Implementation Roadmap

### 11.1 Phase 1: Backend Foundation (Week 1)

**Tasks:**
- [ ] Create database migration for `bulk_import_logs` table
- [ ] Implement `BulkImportValidator` class
- [ ] Implement `BulkUserCreator` class
- [ ] Add database manager methods for logging
- [ ] Write unit tests for validator and creator
- [ ] Code review and refactoring

**Deliverables:**
- Fully tested backend business logic
- Database schema ready

**Estimated Effort:** 3-4 days

### 11.2 Phase 2: API Endpoints (Week 1-2)

**Tasks:**
- [ ] Implement `/bulk-import/validate` endpoint
- [ ] Implement `/bulk-import/execute` endpoint
- [ ] Implement `/bulk-import/template` endpoint
- [ ] Implement `/enable-bulk` org-admin endpoint
- [ ] Add Pydantic request/response models
- [ ] Write API integration tests
- [ ] Test with Postman/curl
- [ ] API documentation

**Deliverables:**
- Complete API implementation
- API tests passing
- Postman collection

**Estimated Effort:** 2-3 days

### 11.3 Phase 3: Frontend UI (Week 2)

**Tasks:**
- [ ] Create `BulkUserImport.svelte` component
- [ ] Implement step 1: Upload
- [ ] Implement step 2: Preview
- [ ] Implement step 3: Results
- [ ] Add service layer methods
- [ ] Integrate into org-admin page
- [ ] Add bulk selection to user list
- [ ] Implement bulk enable button
- [ ] Style with TailwindCSS/DaisyUI
- [ ] Responsive design testing

**Deliverables:**
- Complete bulk import UI
- Integrated with backend API
- Responsive and accessible

**Estimated Effort:** 3-4 days

### 11.4 Phase 4: Testing & Polish (Week 2-3)

**Tasks:**
- [ ] Write Playwright E2E tests
- [ ] Performance testing (100+ users)
- [ ] Security testing (injection, auth)
- [ ] Error scenario testing
- [ ] Browser compatibility testing
- [ ] Accessibility audit (WCAG AA)
- [ ] User documentation
- [ ] Admin guide

**Deliverables:**
- Full test coverage
- Performance validated
- Documentation complete

**Estimated Effort:** 2-3 days

### 11.5 Phase 5: Deployment & Monitoring (Week 3)

**Tasks:**
- [ ] Deploy to staging environment
- [ ] Run full test suite on staging
- [ ] Monitor bulk import operations
- [ ] Set up logging/alerting
- [ ] Performance monitoring
- [ ] Train org-admins
- [ ] Deploy to production
- [ ] Post-deployment monitoring

**Deliverables:**
- Feature live in production
- Monitoring active
- Users trained

**Estimated Effort:** 2 days

### 11.6 Timeline Summary

```
Week 1: Backend + API
  Day 1-2: Business logic (Validator, Creator)
  Day 3-4: API endpoints
  Day 5: Testing and refinement

Week 2: Frontend + Integration
  Day 1-2: UI components
  Day 3: Integration and styling
  Day 4-5: E2E testing

Week 3: Polish + Deploy
  Day 1: Final testing
  Day 2: Documentation
  Day 3: Staging deployment
  Day 4: Production deployment
  Day 5: Monitoring and support
```

**Total Estimated Time:** 15-17 working days (3 weeks)

---

## 12. Success Metrics

### 12.1 Functional Metrics

**Validation Success Rate:**
- Target: 95% of valid JSON files pass validation
- Measure: Validation API success rate

**Import Success Rate:**
- Target: 98% of valid users created successfully
- Measure: Created count / Valid count ratio

**Performance:**
- Validation: < 2 seconds for 100 users
- Import: < 30 seconds for 100 users
- Measure: Server-side timing logs

### 12.2 User Experience Metrics

**Time Savings:**
- Baseline: 2 minutes per user (manual creation)
- Target: 5 minutes total for 50 users
- Improvement: 95% time reduction

**Error Recovery:**
- Target: < 5% of imports require retry
- Measure: Retry rate from logs

**User Satisfaction:**
- Target: 4.5/5 rating from org-admins
- Measure: Post-release survey

### 12.3 System Health Metrics

**Error Rate:**
- Target: < 2% server errors
- Measure: 5xx responses / total requests

**Audit Coverage:**
- Target: 100% of bulk operations logged
- Measure: Log count vs operation count

**Security:**
- Target: 0 security incidents
- Measure: Security audit findings

### 12.4 Adoption Metrics

**Usage Rate:**
- Target: 50% of org-admins use bulk import within 3 months
- Measure: Unique org-admins using feature

**Volume:**
- Target: 20% of user creation via bulk import
- Measure: Bulk created / Total created ratio

---

## Appendices

### Appendix A: JSON Schema (JSON Schema Draft 7)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LAMB Bulk User Import",
  "description": "Schema for bulk user import JSON files",
  "type": "object",
  "required": ["version", "users"],
  "properties": {
    "version": {
      "type": "string",
      "enum": ["1.0"],
      "description": "Schema version"
    },
    "users": {
      "type": "array",
      "minItems": 1,
      "maxItems": 500,
      "items": {
        "type": "object",
        "required": ["email", "name"],
        "properties": {
          "email": {
            "type": "string",
            "format": "email",
            "description": "User email address (must be unique)"
          },
          "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "User full name"
          },
          "user_type": {
            "type": "string",
            "enum": ["creator", "end_user"],
            "default": "creator",
            "description": "Type of user account"
          },
          "enabled": {
            "type": "boolean",
            "default": false,
            "description": "Whether user account is enabled"
          }
        }
      }
    }
  }
}
```

### Appendix B: API Curl Examples

**Validate Import:**
```bash
curl -X POST \
  http://localhost:9099/creator/admin/org-admin/users/bulk-import/validate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@users_import.json"
```

**Execute Import:**
```bash
curl -X POST \
  http://localhost:9099/creator/admin/org-admin/users/bulk-import/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "users": [
      {
        "email": "user1@example.com",
        "name": "User One",
        "user_type": "creator",
        "enabled": false
      }
    ]
  }'
```

**Download Template:**
```bash
curl -X GET \
  http://localhost:9099/creator/admin/org-admin/users/bulk-import/template \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o template.json
```

**Bulk Enable:**
```bash
curl -X POST \
  http://localhost:9099/creator/admin/org-admin/users/enable-bulk \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": [123, 124, 125]
  }'
```

### Appendix C: Database Queries

**Get Bulk Import Logs:**
```sql
SELECT 
  l.id,
  l.operation_type,
  l.admin_email,
  l.total_count,
  l.success_count,
  l.failure_count,
  datetime(l.created_at, 'unixepoch') as created_at,
  o.name as organization_name
FROM bulk_import_logs l
JOIN organizations o ON l.organization_id = o.id
WHERE l.organization_id = ?
ORDER BY l.created_at DESC
LIMIT 50;
```

**Find Users Created in Bulk Import:**
```sql
SELECT u.*
FROM Creator_users u
WHERE u.created_at >= ?  -- Start of bulk import
  AND u.created_at <= ?  -- End of bulk import
  AND u.organization_id = ?
ORDER BY u.created_at ASC;
```

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding bulk user creation and activation capabilities to the LAMB platform. The feature is designed with security, usability, and reliability as top priorities, following established patterns in the existing codebase.

**Key Success Factors:**
1. **Validation First**: Catch errors before creation
2. **Partial Success**: Don't fail entire import on single error
3. **Audit Trail**: Log everything for compliance
4. **User Experience**: Clear feedback at every step
5. **Security**: Multiple layers of validation and authorization

**Next Steps:**
1. Review and approve this plan
2. Create GitHub issues for each phase
3. Assign developers
4. Begin Phase 1 implementation

---

**Document Control:**
- **Author:** LAMB Development Team
- **Reviewers:** Technical Lead, Product Owner
- **Approval Required:** Yes
- **Implementation Start:** TBD
- **Target Completion:** 3 weeks from start

