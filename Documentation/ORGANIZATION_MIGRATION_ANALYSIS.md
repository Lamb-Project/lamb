# Organization Migration Complexity & Risk Analysis

**Date:** January 2025  
**Purpose:** Analyze complexity and risks of migrating all users/resources from one organization to another  
**Status:** Feasible with conflict resolution

---

## Executive Summary

**Migration Complexity:** **MEDIUM**  
**Risk Level:** **LOW-MEDIUM** (with proper conflict handling)  
**Estimated Effort:** 4-6 hours for implementation + testing

**Overall Assessment:** ✅ **FEASIBLE** - Migration is straightforward for most resources, but requires careful handling of unique constraint conflicts for assistants and prompt templates.

---

## 1. Migration Components Breakdown

### 1.1 Users Migration

**Complexity:** ⭐ **LOW**  
**Risk:** ⭐ **LOW**

**What Needs to Happen:**
```sql
UPDATE Creator_users 
SET organization_id = <target_org_id>, updated_at = <timestamp>
WHERE organization_id = <source_org_id>
```

**Existing Infrastructure:**
- ✅ `update_user_organization(user_id, organization_id)` method exists (line 1214)
- ✅ Simple UPDATE statement
- ✅ No unique constraints on users table (only `UNIQUE(user_email)`)
- ✅ No conflicts possible

**Challenges:**
- None - straightforward operation

**Migration Steps:**
1. Query all users in source organization
2. For each user, call `update_user_organization(user_id, target_org_id)`
3. Done

**Time Estimate:** 15 minutes

---

### 1.2 Organization Roles Migration

**Complexity:** ⭐⭐ **LOW-MEDIUM**  
**Risk:** ⭐ **LOW**

**What Needs to Happen:**
1. Delete old roles: `DELETE FROM organization_roles WHERE organization_id = <source_org_id>`
2. Create new roles: `INSERT INTO organization_roles (organization_id, user_id, role, ...)`

**Existing Infrastructure:**
- ✅ `assign_organization_role()` method exists
- ✅ Must preserve role types (owner, admin, member)
- ✅ Cascade delete handles old roles automatically

**Challenges:**
- Must preserve role hierarchy
- **CRITICAL UI REQUIREMENT:** UI must ask admin whether old org admins should remain admins in target org
- Need to decide what role to assign migrated users (default: 'member' or preserve admin status based on user choice)

**Migration Steps:**
1. Query all users being migrated
2. For each user, check their current role in source organization
3. Assign same role in target organization (or downgrade to 'member' if target org has restrictions)
4. Old roles cascade delete automatically

**Time Estimate:** 30 minutes

---

### 1.3 Assistants Migration

**Complexity:** ⭐⭐⭐ **MEDIUM**  
**Risk:** ⭐⭐⭐ **MEDIUM-HIGH** (due to unique constraints)

**What Needs to Happen:**
```sql
UPDATE assistants 
SET organization_id = <target_org_id>, updated_at = <timestamp>
WHERE organization_id = <source_org_id>
```

**Critical Constraint:**
```sql
UNIQUE(organization_id, name, owner)
```

**Conflict Scenario:**
If target organization already has an assistant with:
- Same `name` 
- Same `owner` (email)

Then UPDATE will fail with UNIQUE constraint violation.

**Example:**
```
Source Org Assistant: {name: "Math_Tutor", owner: "teacher@school.edu"}
Target Org Assistant: {name: "Math_Tutor", owner: "teacher@school.edu"}
Result: ❌ UNIQUE CONSTRAINT VIOLATION
```

**Existing Infrastructure:**
- ✅ `get_assistants_by_organization()` method exists
- ✅ Can check for conflicts before migration
- ❌ No automatic conflict resolution

**Solutions:**

**Option A: Prefix Renaming (Recommended)**
```python
# If conflict detected:
new_name = f"{source_org_slug}_{original_name}"
UPDATE assistants SET name = new_name, organization_id = target_org_id
```

**Option B: Suffix with Timestamp**
```python
# If conflict detected:
new_name = f"{original_name}_migrated_{timestamp}"
```

**Option C: User Choice**
```python
# Report conflicts to admin
# Admin chooses: rename source, rename target, or skip migration
```

**Migration Steps:**
1. Query all assistants in source organization
2. For each assistant:
   - Check if target org has assistant with same (name, owner) combo
   - If conflict: rename source assistant (add prefix/suffix)
   - If no conflict: update organization_id
3. Update all assistants

**Time Estimate:** 1-2 hours (including conflict detection and resolution)

---

### 1.4 Prompt Templates Migration

**Complexity:** ⭐⭐⭐ **MEDIUM**  
**Risk:** ⭐⭐ **MEDIUM** (due to unique constraints)

**What Needs to Happen:**
```sql
UPDATE prompt_templates 
SET organization_id = <target_org_id>, updated_at = <timestamp>
WHERE organization_id = <source_org_id>
```

**Critical Constraint:**
```sql
UNIQUE(organization_id, owner_email, name)
```

**Conflict Scenario:**
If target organization already has a template with:
- Same `name`
- Same `owner_email`

Then UPDATE will fail.

**Example:**
```
Source Org Template: {name: "CS101 Template", owner_email: "prof@university.edu"}
Target Org Template: {name: "CS101 Template", owner_email: "prof@university.edu"}
Result: ❌ UNIQUE CONSTRAINT VIOLATION
```

**Existing Infrastructure:**
- ✅ `get_user_prompt_templates()` method exists
- ✅ `get_organization_shared_templates()` method exists
- ❌ No automatic conflict resolution

**Solutions:**

**Option A: Prefix Renaming**
```python
# If conflict detected:
new_name = f"{source_org_slug}_{original_name}"
UPDATE prompt_templates SET name = new_name, organization_id = target_org_id
```

**Option B: Suffix with Timestamp**
```python
new_name = f"{original_name}_migrated_{timestamp}"
```

**Migration Steps:**
1. Query all templates in source organization
2. For each template:
   - Check if target org has template with same (name, owner_email) combo
   - If conflict: rename source template
   - If no conflict: update organization_id
3. Update all templates

**Time Estimate:** 1 hour (including conflict detection)

---

### 1.5 Knowledge Base Registry Migration

**Complexity:** ⭐ **LOW**  
**Risk:** ⭐ **LOW**

**What Needs to Happen:**
```sql
UPDATE kb_registry 
SET organization_id = <target_org_id>, updated_at = <timestamp>
WHERE organization_id = <source_org_id>
```

**Constraints:**
- ✅ No unique constraints on organization_id + name
- ✅ Only constraint: `UNIQUE(kb_id)` (preserved)

**Existing Infrastructure:**
- ✅ KB registry update methods exist
- ✅ No conflicts possible

**Challenges:**
- None - straightforward operation

**Migration Steps:**
1. Query all KB registry entries in source organization
2. Update organization_id for each entry
3. Done

**Time Estimate:** 15 minutes

---

### 1.6 Usage Logs Migration

**Complexity:** ⭐ **LOW**  
**Risk:** ⭐ **LOW**

**What Needs to Happen:**
```sql
UPDATE usage_logs 
SET organization_id = <target_org_id>
WHERE organization_id = <source_org_id>
```

**Constraints:**
- ✅ No unique constraints on organization_id
- ✅ Historical data preservation

**Existing Infrastructure:**
- ✅ Simple UPDATE statement
- ✅ No conflicts possible

**Migration Steps:**
1. Single UPDATE statement for all logs
2. Done

**Time Estimate:** 5 minutes

---

## 2. Complete Migration Workflow

### 2.1 Pre-Migration Validation

**Required Checks:**

```python
def validate_migration(source_org_id: int, target_org_id: int) -> Dict[str, Any]:
    """
    Validate migration feasibility.
    
    Returns:
        {
            "can_migrate": bool,
            "conflicts": {
                "assistants": List[Dict],  # Conflicting assistants
                "templates": List[Dict]    # Conflicting templates
            },
            "resources": {
                "users": int,
                "assistants": int,
                "templates": int,
                "kbs": int
            }
        }
    """
```

**Checks:**
1. ✅ Target organization exists
2. ✅ Source organization is not system organization
3. ✅ Count all resources to migrate
4. ✅ Detect assistant name conflicts
5. ✅ Detect template name conflicts
6. ✅ Check for published assistants (may need special handling)

**Time Estimate:** 30 minutes

---

### 2.2 Migration Execution Plan

**Transactional Approach:**

```python
def migrate_organization(source_org_id: int, target_org_id: int, conflict_strategy: str = "rename") -> Dict[str, Any]:
    """
    Migrate all resources from source to target organization.
    
    Args:
        source_org_id: Source organization ID
        target_org_id: Target organization ID
        conflict_strategy: "rename" | "skip" | "fail"
    
    Returns:
        Migration report with success/failure counts
    """
    with database.transaction():
        # 1. Migrate users (no conflicts)
        migrate_users(source_org_id, target_org_id)
        
        # 2. Migrate organization roles
        migrate_roles(source_org_id, target_org_id)
        
        # 3. Migrate assistants (with conflict handling)
        migrate_assistants(source_org_id, target_org_id, conflict_strategy)
        
        # 4. Migrate prompt templates (with conflict handling)
        migrate_templates(source_org_id, target_org_id, conflict_strategy)
        
        # 5. Migrate KB registry
        migrate_kb_registry(source_org_id, target_org_id)
        
        # 6. Migrate usage logs
        migrate_usage_logs(source_org_id, target_org_id)
        
        # 7. Delete source organization (if migration successful)
        # delete_organization(source_org_id)
```

**Important:** Use database transactions to ensure all-or-nothing migration.

---

### 2.3 Conflict Resolution Strategies

#### Strategy 1: Automatic Renaming (Recommended for Most Cases)

**Pros:**
- ✅ No user intervention required
- ✅ All resources migrated
- ✅ Predictable naming pattern

**Cons:**
- ⚠️ Assistant/template names change (may break references)
- ⚠️ Users need to be notified

**Implementation:**
```python
def resolve_conflict(current_name: str, source_org_slug: str) -> str:
    """Generate conflict-free name"""
    return f"{source_org_slug}_{current_name}"
```

#### Strategy 2: Skip Conflicting Resources

**Pros:**
- ✅ No name changes
- ✅ Preserves target organization resources

**Cons:**
- ⚠️ Some resources not migrated
- ⚠️ Requires manual cleanup

**Implementation:**
```python
# Skip migration if conflict detected
# Log conflict for admin review
```

#### Strategy 3: User Choice (Interactive)

**Pros:**
- ✅ Full control
- ✅ Can choose per-resource

**Cons:**
- ⚠️ Requires user interaction
- ⚠️ More complex implementation

**Implementation:**
```python
# Detect conflicts
# Present to admin
# Admin chooses: rename source, rename target, or skip
```

---

## 3. Risk Assessment

### 3.1 Data Integrity Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Unique Constraint Violation** | HIGH | HIGH | Pre-flight conflict detection |
| **Partial Migration** | LOW | HIGH | Use database transactions |
| **Lost Role Permissions** | LOW | MEDIUM | Preserve role types during migration |
| **Broken References** | MEDIUM | MEDIUM | Rename conflicts predictably, notify users |
| **OWI Integration Issues** | LOW | LOW | OWI resources not org-specific |

### 3.2 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Migration Timeout** | LOW | MEDIUM | Batch operations, progress tracking |
| **Database Lock** | LOW | MEDIUM | Use transactions efficiently |
| **Missing Resources** | LOW | HIGH | Validation before migration |
| **User Confusion** | MEDIUM | LOW | Clear migration report, notifications |

---

## 4. Implementation Recommendations

### 4.1 Phase 1: Pre-Migration Validation Endpoint

**Endpoint:** `POST /creator/admin/organizations/{slug}/migration/validate`

**Purpose:** Check migration feasibility before execution

**Response:**
```json
{
  "can_migrate": true,
  "conflicts": {
    "assistants": [
      {
        "id": 123,
        "name": "Math_Tutor",
        "owner": "teacher@school.edu",
        "conflict_reason": "Target org already has assistant with same name and owner"
      }
    ],
    "templates": []
  },
  "resources": {
    "users": 10,
    "assistants": 25,
    "templates": 5,
    "kbs": 8,
    "usage_logs": 1500
  },
  "estimated_time_seconds": 45
}
```

**Benefits:**
- Admin can see conflicts before committing
- Admin can choose conflict resolution strategy
- Prevents failed migrations

---

### 4.2 Phase 2: Migration Execution Endpoint

**Endpoint:** `POST /creator/admin/organizations/{slug}/migrate`

**Request:**
```json
{
  "target_organization_slug": "target-org",
  "conflict_strategy": "rename",  // "rename" | "skip" | "interactive"
  "rename_prefix": "old_org_",    // Optional prefix for renaming
  "preserve_admin_roles": true,   // Keep old org admins as admins in target org?
  "delete_source": false           // Delete source org after migration?
}
```

**Response:**
```json
{
  "success": true,
  "migration_id": "mig_1234567890",
  "resources_migrated": {
    "users": 10,
    "assistants": 25,
    "templates": 5,
    "kbs": 8,
    "usage_logs": 1500
  },
  "conflicts_resolved": {
    "assistants_renamed": 2,
    "templates_renamed": 0
  },
  "warnings": [
    "2 assistants were renamed due to conflicts"
  ]
}
```

---

### 4.3 Phase 3: Rollback Capability (Optional)

**Endpoint:** `POST /creator/admin/organizations/migrations/{migration_id}/rollback`

**Purpose:** Undo migration if issues discovered

**Implementation:**
- Store migration record with mappings
- Allow reversal of all changes
- Restore original organization_id values

**Complexity:** HIGH  
**Recommendation:** Defer to Phase 2 if needed

---

## 5. Edge Cases to Handle

### 5.1 Published Assistants

**Issue:** Published assistants have OWI groups and models

**Handling:**
- ✅ OWI resources are not organization-specific
- ✅ Groups and models remain functional after migration
- ✅ No OWI cleanup needed

**Risk:** LOW

---

### 5.2 Shared Knowledge Bases

**Issue:** KBs shared within organization

**Handling:**
- ✅ KB registry entries migrated
- ✅ KB Server collections remain (not org-specific)
- ✅ Sharing status preserved
- ✅ New organization members can access shared KBs

**Risk:** LOW

---

### 5.3 Shared Prompt Templates

**Issue:** Templates shared within organization

**Handling:**
- ✅ Templates migrated with sharing status
- ✅ New organization members can access shared templates
- ✅ If conflict: rename template (may break references)

**Risk:** MEDIUM (if renamed)

---

### 5.4 Users Without Organization Roles

**Issue:** Users exist but no role assigned

**Handling:**
- ✅ Assign default 'member' role in target organization
- ✅ Log warning for admin review

**Risk:** LOW

---

### 5.5 Empty Organization

**Issue:** Organization has no resources

**Handling:**
- ✅ Validate: if no resources, allow immediate deletion
- ✅ Skip migration if nothing to migrate

**Risk:** LOW

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
def test_migrate_users():
    """Test user migration"""
    # Create source org with users
    # Migrate to target org
    # Verify users have new org_id
    # Verify old roles deleted, new roles created

def test_assistant_conflict_detection():
    """Test conflict detection"""
    # Create conflicting assistants
    # Validate migration detects conflicts
    # Verify conflict resolution

def test_migration_transaction():
    """Test transaction rollback"""
    # Start migration
    # Force error mid-migration
    # Verify rollback
    # Verify no partial data
```

### 6.2 Integration Tests

```python
def test_full_migration():
    """Test complete migration workflow"""
    # Create source org with all resource types
    # Create target org with some conflicts
    # Execute migration
    # Verify all resources migrated
    # Verify conflicts resolved
    # Verify source org deleted (if requested)
```

### 6.3 Manual Testing Checklist

- [ ] Migrate organization with 0 users
- [ ] Migrate organization with 1 user
- [ ] Migrate organization with 100 users
- [ ] Migrate with assistant name conflicts
- [ ] Migrate with template name conflicts
- [ ] Migrate with published assistants
- [ ] Migrate with shared KBs
- [ ] Migrate with shared templates
- [ ] Verify OWI integration still works
- [ ] Verify users can login after migration
- [ ] Verify assistants still function

---

## 7. User Communication

### 7.1 Pre-Migration Notification

**Email Template:**
```
Subject: Organization Migration Scheduled

Dear [Organization Name] Members,

Your organization "[Source Org]" will be migrated to "[Target Org]" on [Date].

What this means:
- All your assistants, templates, and knowledge bases will be moved
- If there are naming conflicts, some resources may be renamed
- You will continue to have access to all your resources
- Your login credentials remain unchanged

If you have any questions, please contact your administrator.

[Admin Contact Info]
```

### 7.2 Post-Migration Report

**Email Template:**
```
Subject: Organization Migration Complete

Dear [Organization Name] Members,

The migration from "[Source Org]" to "[Target Org]" has been completed successfully.

Migration Summary:
- [X] users migrated
- [X] assistants migrated ([X] renamed due to conflicts)
- [X] templates migrated ([X] renamed due to conflicts)
- [X] knowledge bases migrated

Renamed Resources:
- Assistant "Math_Tutor" → "old_org_Math_Tutor"
- Template "CS101" → "old_org_CS101"

If you notice any issues, please contact support.

[Admin Contact Info]
```

---

## 8. Implementation Timeline

### Week 1: Foundation
- ✅ Pre-migration validation endpoint
- ✅ Conflict detection logic
- ✅ Unit tests

### Week 2: Migration Logic
- ✅ Migration execution endpoint
- ✅ Conflict resolution strategies
- ✅ Transaction handling
- ✅ Integration tests

### Week 3: UI & Polish
- ✅ Frontend migration UI
- ✅ Progress tracking
- ✅ User notifications
- ✅ Documentation

**Total Estimated Time:** 2-3 weeks

---

## 9. Conclusion

**Migration Feasibility:** ✅ **FEASIBLE**

**Key Points:**
- ✅ Most resources migrate easily (users, KBs, logs)
- ⚠️ Conflicts require resolution (assistants, templates)
- ✅ Transaction safety ensures data integrity
- ✅ Pre-flight validation prevents failed migrations
- ✅ Predictable renaming strategy minimizes surprises

**Recommended Approach:**
1. **Implement pre-migration validation** first
2. **Auto-rename conflicts** with predictable patterns
3. **Use database transactions** for safety
4. **Notify users** before and after migration
5. **Provide migration reports** showing what changed

**Risk Level:** **LOW-MEDIUM** (with proper conflict handling)

**Complexity:** **MEDIUM** (4-6 hours core implementation + testing)

---

## 10. Code Example: Migration Function

```python
def migrate_organization_comprehensive(
    source_org_id: int, 
    target_org_id: int,
    conflict_strategy: str = "rename",
    delete_source: bool = False
) -> Dict[str, Any]:
    """
    Comprehensive organization migration.
    
    Returns migration report with success/failure details.
    """
    connection = get_connection()
    source_org = get_organization_by_id(source_org_id)
    target_org = get_organization_by_id(target_org_id)
    
    conflicts = detect_conflicts(source_org_id, target_org_id)
    
    migration_report = {
        "success": False,
        "resources_migrated": {},
        "conflicts_resolved": {},
        "errors": []
    }
    
    try:
        with connection:
            cursor = connection.cursor()
            
            # 1. Migrate users
            users_migrated = migrate_users(cursor, source_org_id, target_org_id)
            migration_report["resources_migrated"]["users"] = users_migrated
            
            # 2. Migrate roles
            roles_migrated = migrate_roles(cursor, source_org_id, target_org_id)
            
            # 3. Migrate assistants (with conflict resolution)
            assistants_result = migrate_assistants(
                cursor, source_org_id, target_org_id, conflicts, conflict_strategy
            )
            migration_report["resources_migrated"]["assistants"] = assistants_result["count"]
            migration_report["conflicts_resolved"]["assistants_renamed"] = assistants_result["renamed"]
            
            # 4. Migrate templates
            templates_result = migrate_templates(
                cursor, source_org_id, target_org_id, conflicts, conflict_strategy
            )
            migration_report["resources_migrated"]["templates"] = templates_result["count"]
            migration_report["conflicts_resolved"]["templates_renamed"] = templates_result["renamed"]
            
            # 5. Migrate KB registry
            kbs_migrated = migrate_kb_registry(cursor, source_org_id, target_org_id)
            migration_report["resources_migrated"]["kbs"] = kbs_migrated
            
            # 6. Migrate usage logs
            logs_migrated = migrate_usage_logs(cursor, source_org_id, target_org_id)
            migration_report["resources_migrated"]["usage_logs"] = logs_migrated
            
            # 7. Delete source organization (if requested)
            if delete_source:
                delete_organization(source_org_id)
            
            migration_report["success"] = True
            
    except Exception as e:
        migration_report["success"] = False
        migration_report["errors"].append(str(e))
        raise  # Transaction will rollback
    
    return migration_report
```

---

**Report Prepared By:** AI Analysis  
**Date:** January 2025  
**Status:** Ready for Implementation Review

