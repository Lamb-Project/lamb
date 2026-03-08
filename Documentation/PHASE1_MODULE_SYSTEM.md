# Phase 1: Activity Module System — Implementation Summary

## Overview

Phase 1 establishes the backend foundation for LAMB's Activity Module System, a pluggable architecture that allows LAMB to host multiple LTI activity types (chat, file evaluation, quizzes, etc.) through a single Unified LTI endpoint. This phase also integrates improvements to instructor session management and ownership resolution that were developed in parallel on the `dev` branch.

## Files Created

### Module Framework (new)

| File | Purpose |
|------|---------|
| `backend/lamb/modules/__init__.py` | Module registry (`_registry` dict) and auto-discovery (`discover_modules()`) |
| `backend/lamb/modules/base.py` | `ActivityModule` abstract base class, `LTIContext` model, `SetupField` model |
| `backend/lamb/modules/chat/__init__.py` | `ChatModule` implementation — first concrete module |
| `backend/lamb/modules/chat/service.py` | `ChatModuleService` — OWI-specific logic (group creation, user management, dashboard queries) |

### Module Contract (`ActivityModule`)

Every module must implement 12 abstract methods:

```python
class ActivityModule(ABC):
    name: str              # "chat", "file_evaluation"
    display_name: str      # "AI Chat Activity"
    description: str       # Shown in setup dropdown

    # --- Infrastructure ---
    def get_migrations(self) -> List[str]            # Module-specific DB tables
    def get_routers(self) -> List[APIRouter]          # FastAPI routers (mounted at /lamb/v1/modules/{name}/)
    def get_setup_fields(self) -> List[SetupField]    # Extra config fields for setup page
    def get_frontend_build_path(self) -> str | None   # SPA path (future phases)

    # --- Lifecycle hooks ---
    def on_activity_configured(self, activity_id, setup_data)  # Called after manager creates DB record
    def on_activity_reconfigured(self, activity, added_ids, removed_ids)  # Called after manager updates DB
    def on_student_launch(self, ctx: LTIContext) -> RedirectResponse  # No-consent path only
    def on_instructor_launch(self, ctx: LTIContext) -> RedirectResponse  # Instructor launch at configured activity

    # --- User provisioning ---
    def launch_user(self, activity, username, display_name, lms_user_id, is_instructor=False) -> str
    # Provisions (or fetches) a user in the external system and returns a redirect URL.
    # Used for: student after consent, instructor "Enter Chat"

    # --- Dashboard data ---
    def get_dashboard_stats(self, activity) -> dict
    def get_dashboard_chats(self, activity, assistant_id=None, page=1, per_page=20) -> dict
    def get_dashboard_chat_detail(self, activity, chat_id) -> dict | None
```

**Ownership of concerns:**
- **Router** handles HTTP/OAuth, JWT sessions, consent flow, and routing decisions.
- **Manager** (`lti_activity_manager.py`) handles LAMB DB operations only: configure, reconfigure, identify instructor, link identity, check consent, get students.
- **Module** handles all external-system operations (OWI user/group management, embeddings, etc.) and provides dashboard data.

## Files Modified

### `backend/main.py` (outer — the main FastAPI app)

> **Note:** This is the outer `backend/main.py` (the root FastAPI application), NOT `backend/lamb/main.py` (the LAMB sub-app).

- **Added**: `from lamb.modules import discover_modules`
- **Added**: `discover_modules()` call during FastAPI lifespan startup (line 61)
- **Added**: Module router mounting loop — iterates `get_all_modules()` and mounts each module's routers at `/lamb/v1/modules/{name}` (lines 64-69)

### `backend/lamb/database_manager.py`
- **Schema**: Added `activity_type TEXT NOT NULL DEFAULT 'chat'` column to `lti_activities` table
- **Migration**: Auto-migration logic to add `activity_type` column to existing databases
- **Method**: `create_lti_activity()` now accepts `activity_type: str = 'chat'` parameter

### `backend/lamb/lti_activity_manager.py`

**Final state: DB-only business logic (~381 lines).** All OWI user-provisioning and group-management operations were moved out of the manager into modules. This is the key architectural boundary of Phase 1.

**Removed** (moved to `modules/chat/service.py` or modules in general):
- `handle_student_launch` — now `module.launch_user()`
- `create_instructor_activity_user` — subsumed by `module.launch_user(is_instructor=True)`
- `get_dashboard_stats` — now `module.get_dashboard_stats()`
- `get_dashboard_chats` — now `module.get_dashboard_chats()`
- `get_dashboard_chat_detail` — now `module.get_dashboard_chat_detail()`
- All private OWI helper methods (`_get_owi_user`, `_add_user_to_owi_group`, etc.)

**Retained `OwiUserManager`** (intentionally):
- `self.owi_user_manager = OwiUserManager()` is kept because `verify_creator_credentials()` uses `self.owi_user_manager.verify_user(email, password)` to check passwords via the OWI auth system during the `/link-account` identity-linking flow. This is the **only** remaining OWI dependency in the manager — all user provisioning and group management was moved to modules.

**Added / kept** (DB-only operations):

| Method | Description |
|--------|-------------|
| `configure_activity(...)` | Creates the `lti_activities` DB record with `activity_type` parameter. OWI fields left empty (`owi_group_id=""`, etc.) — the module fills these in `on_activity_configured()`. |
| `reconfigure_activity(activity, assistant_ids)` | Updates `lti_activity_assistants` and returns `Tuple[List[int], List[int]]` — `(added_ids, removed_ids)`. The router passes these to `module.on_activity_reconfigured()`. |
| `verify_creator_credentials(email, password)` | Verifies password via OWI auth endpoint + validates user is enabled in LAMB DB. Returns the creator user record or `None`. Used by `/link-account`. |
| `determine_is_owner(activity, lms_user_id, lms_email)` | Resolves LMS identity → Creator user via `get_creator_users_by_lms_identity()` and compares against `owner_email`. Dynamic resolution fixes a bug where `lms_email ≠ creator_email` always returned false. |
| `get_dashboard_students(activity_id, page, per_page)` | Query-only method returning anonymized student participation data from LAMB DB. Stays on the manager because it is pure DB. |
| `identify_instructor(lms_user_id, lms_email)` | Looks up Creator users linked to a given LMS identity. Called at first launch to start setup flow. |
| `link_identity(lms_user_id, creator_user_id, lms_email)` | Persists LMS↔Creator identity mapping. Called after `/link-account`. |
| `check_student_consent(activity, student_email)` | Returns `True` if student still needs to give consent for this activity. |
| `generate_student_email(username, resource_link_id)` | Deterministic email derivation for LTI students. |
| `get_published_assistants_for_instructor(creator_users)` | Returns dict of `{org_id: [assistants]}` for the setup page select UI. |

### `backend/lamb/lti_router.py`

#### Session management overhaul (from dev branch)

In-memory token dict for instructor flows was replaced with LAMB JWTs:

| Before | After |
|---|---|
| `_tokens` dict, `_create_token()`, `_validate_token()`, `_consume_token()` | Removed entirely |
| `_create_setup_token()` / `_validate_setup_token()` | `_create_setup_jwt()` + `_validate_lti_jwt(token, "setup")` |
| `_create_token({type: "dashboard"})` | `_create_dashboard_jwt(activity, instructor_user, ...)` |
| Consent: `_create_token({type: "consent"}, ttl=...)` | `_create_consent_token()` — still in-memory (one-shot, short TTL) |
| `SETUP_TOKEN_TTL = 600` (10 min) | `LTI_SETUP_JWT_EXPIRY = timedelta(hours=2)` |
| `DASHBOARD_TOKEN_TTL = 1800` (30 min) | `LTI_DASHBOARD_JWT_EXPIRY = timedelta(days=7)` |

JWT payloads carry: `lti_type`, `lti_resource_link_id`, `lti_activity_id`, `lti_lms_user_id`, `lti_lms_email`, `lti_creator_user_ids` (setup), `lti_display_name` (dashboard).

#### New helper: `_get_activity_module(activity)`

```python
def _get_activity_module(activity):
    activity_type = activity.get('activity_type', 'chat')
    module = get_module(activity_type)
    if not module:
        raise HTTPException(status_code=500, detail=f"Module '{activity_type}' is not installed.")
    return module
```

Called before every module delegation. Raises HTTP 500 if the activity's type has no registered module.

#### Import changes
- **Added**: `from lamb import auth as lamb_auth`, `from datetime import timedelta`, `from lamb.modules import get_all_modules, get_module`
- **Removed**: `from lamb.owi_bridge.owi_users import OwiUserManager`, `from lamb.auth_context import validate_user_enabled`

#### Endpoint-by-endpoint changes

| Endpoint | Change |
|---|---|
| `POST /launch` | Instructor at configured activity → `module.on_instructor_launch(ctx)`. Student: consent check → consent redirect **or** `module.on_student_launch(ctx)`. |
| `GET /setup` | Accepts both setup JWT (first time) and dashboard JWT (reconfigure). Re-fetches creator user records from DB by IDs embedded in JWT instead of embedding user data. Passes `get_all_modules()` + `modules_json` to template. |
| `POST /configure` | Two-phase: (1) `manager.configure_activity(activity_type=...)` creates DB record; (2) `module.on_activity_configured(activity_id, form_data)` creates external resources (OWI group, model permissions). Activity is re-fetched after hook. Dashboard JWT issued (no OWI user yet). |
| `GET /link-account` | Unchanged (shows form). |
| `POST /link-account` | Uses `manager.verify_creator_credentials()` instead of inline OWI calls. Issues new setup JWT on success. |
| `POST /reconfigure` | `manager.determine_is_owner()` (dynamic identity resolution). `added_ids, removed_ids = manager.reconfigure_activity(activity, assistant_ids)`. Then `module.on_activity_reconfigured(activity, added_ids, removed_ids)`. |
| `GET /info` | Unchanged. |
| `GET /consent` | Uses `_validate_consent_token()` (unchanged logic). |
| `POST /consent` | Records consent + user in LAMB DB, then `redirect_url = module.launch_user(activity, username, display_name, lms_user_id)`. |
| `GET /dashboard` | Uses `manager.determine_is_owner()`. Calls `module.get_dashboard_stats(activity)` and `module.get_dashboard_chats(activity)` (if visibility enabled). Students still from `manager.get_dashboard_students()` (pure DB). |
| `GET /dashboard/stats` | `module.get_dashboard_stats(activity)` → JSON. |
| `GET /dashboard/students` | `manager.get_dashboard_students(activity_id, page, per_page)` → JSON. |
| `GET /dashboard/chats` | `module.get_dashboard_chats(activity, assistant_id, page, per_page)` → JSON. Requires `chat_visibility_enabled`. |
| `GET /dashboard/chats/{chat_id}` | `module.get_dashboard_chat_detail(activity, chat_id)` → JSON. Requires `chat_visibility_enabled`. |
| `GET /enter-chat` | `redirect_url = module.launch_user(activity, ..., is_instructor=True)` — provisions instructor user in OWI on demand. |

### `backend/lamb/lti_creator_router.py`

#### JWT migration

The LTI Creator Router handles a separate LTI endpoint for Creator Interface login (educators logging into the Creator UI via LTI from their LMS). This is independent from the Unified LTI activity endpoint but shares the same JWT infrastructure.

**Before**: Used OWI-native tokens for authentication.
**After**: Uses LAMB JWT via `lamb_auth.create_token()`:

```python
from lamb import auth as lamb_auth
auth_token = lamb_auth.create_token({
    "sub": str(creator_user['id']),
    "email": user_email,
    "role": creator_user.get('role', 'user')
})
```

The JWT is passed as a query parameter in the redirect to the Creator UI (`/assistants?token={auth_token}`), where the frontend stores it for subsequent API calls.

This router does NOT participate in the module system (it's not an LTI activity type) — it's a direct LTI-to-JWT authentication bridge for the Creator Interface.

### `backend/lamb/templates/lti_activity_setup.html`

- **Added**: Activity Type radio selector that loops through `modules` context variable
- **Added**: Dynamic rendering of module-specific setup fields via JavaScript (`modulesData` JSON + `renderOptions()`)
- Each module's `get_setup_fields()` output is serialized to JSON and used to render extra form fields

### `backend/lamb/modules/chat/__init__.py`

`ChatModule` implements all 12 abstract methods:

| Method | Implementation |
|--------|---------------|
| `on_activity_configured(activity_id, setup_data)` | Calls `self.service.configure_activity(activity_id, setup_data)` — creates the OWI group for this activity. |
| `on_activity_reconfigured(activity, added_ids, removed_ids)` | Uses `OwiDatabaseManager` + `OWIModel` directly to add/remove model permissions for the changed assistant IDs. |
| `on_student_launch(ctx)` | Called only for students who have already given consent (consent check is router-level). Delegates to `service.handle_student_launch()`. Returns `RedirectResponse`. |
| `on_instructor_launch(ctx)` | Handles instructor launch at a configured activity. Issues a dashboard JWT and redirects to `/dashboard`. Imports `_create_dashboard_jwt` from `lti_router`. |
| `launch_user(activity, username, display_name, lms_user_id, is_instructor)` | Calls `service.handle_student_launch(...)` → returns OWI redirect URL string. `is_instructor=True` marks the user entry appropriately. |
| `get_dashboard_stats(activity)` | Delegates to `service.get_dashboard_stats(activity)` → dict with total sessions, active users, etc. |
| `get_dashboard_chats(activity, assistant_id, page, per_page)` | Delegates to `service.get_dashboard_chats(activity, ...)` → dict with paginated chat list. |
| `get_dashboard_chat_detail(activity, chat_id)` | Delegates to `service.get_dashboard_chat_detail(activity, chat_id)` → dict or `None`. |

## Architecture: Module Dispatch and Separation of Concerns

### `/launch` decision tree

```
POST /lamb/v1/lti/launch
    │
    ├── Validate OAuth signature
    ├── Look up activity by resource_link_id
    │
    ├── Activity IS configured (status = 'active'):
    │   ├─── Instructor:
    │   │     └── module.on_instructor_launch(ctx) → RedirectResponse
    │   │
    │   └─── Student:
    │         ├── check_student_consent()?  YES → redirect to /consent (in-memory token)
    │         └── No consent needed →  _get_activity_module(activity)
    │                                      └── module.on_student_launch(ctx) → RedirectResponse
    │
    └── Activity NOT configured:
          ├── Student → "Not configured yet" page
          └── Instructor:
                ├── identify_instructor(lms_user_id, lms_email)
                │    └── no match → "contact admin" page
                └── match → setup JWT → redirect to /setup
```

### `/configure` two-phase flow

```
POST /lamb/v1/lti/configure
    │
    ├── Validate setup JWT
    ├── [Phase 1 — DB] manager.configure_activity(activity_type=...) → activity row created
    ├── module = _get_activity_module(activity)
    ├── [Phase 2 — External] module.on_activity_configured(activity_id, form_data)
    │       e.g. ChatModule creates OWI group, sets model permissions
    ├── Re-fetch activity (OWI fields now populated by module)
    ├── Issue dashboard JWT
    └── Redirect to /dashboard
```

### Dashboard data flow

```
GET /dashboard/stats   → module.get_dashboard_stats(activity)      → JSON
GET /dashboard/chats   → module.get_dashboard_chats(activity, ...) → JSON   [requires chat_visibility]
GET /dashboard/chats/{id} → module.get_dashboard_chat_detail(...)  → JSON   [requires chat_visibility]
GET /dashboard/students → manager.get_dashboard_students(...)      → JSON   (pure DB, stays on manager)
```

### User provisioning via `launch_user`

`module.launch_user()` is the single method that provisions a user in the external system and returns a redirect URL. It is called in two places:
- `POST /consent` — student accepted consent, needs to enter OWI
- `GET /enter-chat` — instructor clicks "Enter Chat" from dashboard (`is_instructor=True`)

## Database Changes

```sql
-- Added to lti_activities table
ALTER TABLE lti_activities ADD COLUMN activity_type TEXT NOT NULL DEFAULT 'chat';
```

## Known Limitations (to address in future phases)

1. ~~**Module routers not mounted**~~ — ✅ **Resolved.** `backend/main.py` now iterates `get_all_modules()` and mounts routers at `/lamb/v1/modules/{name}` during lifespan startup.
2. **`on_activity_configured` is now called** from `/configure` — ✅ resolved in Phase 1.2.
3. **Manager OWI methods now in modules** — ✅ resolved in Phase 1.2. Manager is now DB-only (except `verify_creator_credentials` which uses `OwiUserManager` for password checking only).
4. **Frontend**: LTI-facing pages still use Jinja2 templates. Phase 3 will port these to SvelteKit.

## Verification

All Phase 1 files parse correctly:
- `backend/lamb/lti_router.py` — ~898 lines, syntax OK, no old manager method calls
- `backend/lamb/lti_activity_manager.py` — ~381 lines (stripped from 863), DB-only (retains `OwiUserManager` only for `verify_creator_credentials`), returns tuple from `reconfigure_activity`
- `backend/lamb/modules/base.py` — 12 abstract methods in `ActivityModule` ABC
- `backend/lamb/modules/chat/__init__.py` — all 12 abstract methods implemented
- `backend/lamb/modules/chat/service.py` — all OWI operations, `handle_student_launch` with `is_instructor` param
- `backend/lamb/lti_creator_router.py` — JWT via `lamb_auth.create_token()` for Creator Interface LTI login

Verification commands:
```bash
cd backend/lamb
python3 -c "import ast; [ast.parse(open(f).read()) or print('OK:', f) for f in ['lti_router.py', 'lti_activity_manager.py', 'modules/base.py', 'modules/chat/__init__.py', 'modules/chat/service.py', 'lti_creator_router.py']]"
```
