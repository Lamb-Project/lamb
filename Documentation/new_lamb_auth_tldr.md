# LAMB AuthContext — TL;DR

**Introduced:** v2.5 (Feb 2026) | **Issue:** #265 | **File:** `backend/lamb/auth_context.py`

---

## What Changed

Before v2.5, every endpoint **manually** extracted the JWT token, decoded it, looked up the user, checked roles, and decided permissions inline — scattered across 10+ router files with inconsistent logic. This caused bugs like organization members seeing LLM models from other organizations.

Now, a single `AuthContext` object is built once per request via FastAPI `Depends()`. It carries the user's full identity, roles, organization, and feature flags. Resource-level checks (assistants, KBs) are methods on the object.

**The API surface did not change.** Every endpoint URL, request body, and response format is identical.

---

## How to Use It (3 Patterns)

### 1. Standard Protected Endpoint

```python
from fastapi import Depends
from lamb.auth_context import AuthContext, get_auth_context

@router.get("/my-stuff")
async def my_stuff(auth: AuthContext = Depends(get_auth_context)):
    user = auth.user           # dict: id, email, name, role, ...
    org = auth.organization    # dict: id, name, slug, config, ...
    features = auth.features   # dict: sharing_enabled, signup_enabled, ...
    return {"email": user["email"], "org": org["name"]}
```

`get_auth_context` returns 401 automatically if the token is missing or invalid.

### 2. Admin / Org-Admin Endpoint

```python
@router.delete("/admin/nuke-user/{user_id}")
async def nuke_user(user_id: int, auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()      # 403 if not system admin
    # ... proceed

@router.put("/org/{org_id}/config")
async def update_org(org_id: int, auth: AuthContext = Depends(get_auth_context)):
    auth.require_org_admin()         # 403 if not org admin or system admin
    # Also verify the org_id matches (org admin can only manage their own org):
    if not auth.is_system_admin and auth.organization.get("id") != org_id:
        raise HTTPException(status_code=403, detail="Access denied for this organization")
    # ... proceed
```

### 3. Resource-Guarded Endpoint

```python
@router.put("/assistant/{id}")
async def update_assistant(id: int, auth: AuthContext = Depends(get_auth_context)):
    auth.require_assistant_access(id, level="owner_or_admin")
    # Raises 404 if assistant not found, 403 if no permission
    # ... proceed with update

@router.get("/assistant/{id}")
async def get_assistant(id: int, auth: AuthContext = Depends(get_auth_context)):
    auth.require_assistant_access(id, level="any")
    # "any" = owner, shared user, or org admin of same org
```

---

## AuthContext Fields at a Glance

| Field | Type | Always Present | Description |
|-------|------|:-:|---|
| `user` | `dict` | Yes | Full `Creator_users` row |
| `token_payload` | `dict` | Yes | Raw JWT claims |
| `is_system_admin` | `bool` | Yes | `role == "admin"` in JWT |
| `organization_role` | `str\|None` | Yes | `"owner"`, `"admin"`, `"member"`, or `None` |
| `is_org_admin` | `bool` | Yes | `organization_role in ("owner", "admin")` |
| `organization` | `dict` | Yes | Full org row (id, name, slug, config) |
| `features` | `dict` | Yes | Parsed from `organization.config.features` |

---

## Resource Access Methods

| Method | What it checks | Returns |
|--------|---|---|
| `can_access_assistant(id)` | ownership, org admin (same org), sharing | `"owner"` / `"org_admin"` / `"shared"` / `"none"` |
| `can_modify_assistant(id)` | ownership or system admin | `bool` |
| `can_delete_assistant(id)` | same as modify | `bool` |
| `can_access_kb(id)` | ownership, sharing, system admin | `"owner"` / `"shared"` / `"none"` |

---

## Guard Methods (raise on denial)

| Method | Raises | When |
|--------|--------|------|
| `require_system_admin()` | 403 | Not system admin |
| `require_org_admin()` | 403 | Not org admin or system admin |
| `require_assistant_access(id, level)` | 404/403 | `level` = `"any"`, `"owner"`, `"owner_or_admin"` |
| `require_kb_access(id, level)` | 404/403 | `level` = `"any"`, `"owner"` |

---

## Key Insight: Org-Scoped Checks

An org admin of Org A **cannot** touch resources in Org B. This is enforced automatically inside `can_access_assistant`:

```python
# from auth_context.py
if self.is_org_admin and assistant.get("organization_id") == self.organization.get("id"):
    return "org_admin"
# If org IDs don't match → falls through to "none"
```

For organization management endpoints, you must **also** verify the target `organization_id` matches `auth.organization["id"]` (unless system admin):

```python
if not auth.is_system_admin and auth.organization.get("id") != target_org_id:
    raise HTTPException(status_code=403, detail="Access denied for this organization")
```

---

## Optional Auth

For endpoints that should work both authenticated and anonymously (e.g., listing available models):

```python
from lamb.auth_context import get_optional_auth_context

@router.get("/public-data")
async def public_data(auth: Optional[AuthContext] = Depends(get_optional_auth_context)):
    if auth:
        return scoped_data(auth.organization["id"])
    return public_only_data()
```

---

## Feature Flag Checks

Organization feature flags live in `auth.features`:

```python
if not auth.features.get("sharing_enabled"):
    raise HTTPException(status_code=403, detail="Sharing disabled for this org")
```

Common flags: `sharing_enabled`, `signup_enabled`, `signup_key`, `rag_enabled`.

---

## Dependency Functions Summary

| Function | Returns | 401 on missing token? |
|---|---|:-:|
| `get_auth_context` | `AuthContext` | Yes |
| `get_optional_auth_context` | `AuthContext \| None` | No (returns None) |
| `require_admin` | `AuthContext` | Yes + 403 if not admin |

---

## Serialization / Debugging

Call `auth.to_dict()` to get a JSON-serializable snapshot of the full context:

```python
logger.debug("Auth context: %s", auth.to_dict())
```

Returns:
```json
{
  "user": {"id": 5, "email": "prof@uni.edu", "name": "Prof"},
  "is_system_admin": false,
  "organization_role": "admin",
  "is_org_admin": true,
  "organization": {"id": 2, "name": "Physics Dept", "slug": "physics"},
  "features": {"sharing_enabled": true, "signup_enabled": false}
}
```

---

## Legacy Functions (Do Not Use in New Code)

These still exist for backward compatibility but are deprecated:

| Function | Replacement |
|---|---|
| `get_creator_user_from_token(auth_header)` | `auth.user` |
| `is_admin_user(auth_header)` | `auth.is_system_admin` |
| Manual token decode + user lookup | `Depends(get_auth_context)` |

---

## Testing

- **Unit tests:** `backend/tests/test_auth_context.py` (38 tests covering all AuthContext logic)
- **CLI E2E tests:** `testing/cli/tests/test_15_auth_context.py` (34 tests via `lamb` CLI against live backend)

---

*See [lamb_architecture_v2.md](./lamb_architecture_v2.md) Section 5 for full architectural context.*
