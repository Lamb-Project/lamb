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

Every module must implement:

```python
class ActivityModule(ABC):
    name: str              # "chat", "file_evaluation"
    display_name: str      # "AI Chat Activity"
    description: str       # Shown in setup dropdown

    def get_migrations(self) -> List[str]           # Module-specific DB tables
    def get_routers(self) -> List[APIRouter]         # FastAPI routers (mounted at /lamb/v1/modules/{name}/)
    def get_setup_fields(self) -> List[SetupField]   # Extra config fields for setup page
    def on_activity_configured(self, activity_id, setup_data)  # Post-setup hook
    def on_student_launch(self, ctx: LTIContext) -> RedirectResponse
    def on_instructor_launch(self, ctx: LTIContext) -> RedirectResponse
    def get_frontend_build_path(self) -> str | None  # SPA path (future phases)
```

## Files Modified

### `backend/main.py`
- **Added**: `from lamb.modules import discover_modules`
- **Added**: `discover_modules()` call during FastAPI lifespan startup

### `backend/lamb/database_manager.py`
- **Schema**: Added `activity_type TEXT NOT NULL DEFAULT 'chat'` column to `lti_activities` table
- **Migration**: Auto-migration logic to add `activity_type` column to existing databases
- **Method**: `create_lti_activity()` now accepts `activity_type: str = 'chat'` parameter

### `backend/lamb/lti_activity_manager.py`

Changes from Phase 1 module refactoring:
- `configure_activity()`: Added `activity_type` parameter, passed through to DB

Changes integrated from dev branch:
- **`__init__`**: Added `self.owi_user_manager` (OwiUserManager) and `self.owi_group_manager` (OwiGroupManager) as instance attributes
- **`verify_creator_credentials(email, password)`**: New method — verifies credentials via OWI + validates user is enabled. Replaces inline logic that was scattered in the router
- **`handle_student_launch(activity, username, display_name, lms_user_id, is_instructor)`**: New method — handles the full OWI user lifecycle (get/create user → add to group → record in LAMB DB → get auth token). The `is_instructor` flag marks instructor-as-user entries
- **`create_instructor_activity_user(activity, username, display_name, lms_user_id)`**: New method — creates OWI user for instructor but returns metadata instead of an auth token (token obtained later when "Enter Chat" is clicked, avoiding unnecessary OWI calls during dashboard access)
- **`determine_is_owner(activity, lms_user_id, lms_email)`**: New method — resolves LMS identity to Creator user via `get_creator_users_by_lms_identity` and compares against `owner_email`. Fixes a bug where `lms_email ≠ creator_email` caused ownership to always be false

### `backend/lamb/lti_router.py`

#### Changes from Phase 1 module refactoring:
- **Import**: Added `from lamb.modules import get_all_modules`
- **`/launch` endpoint**: Module dispatch for configured activities — resolves `activity_type`, gets module via `get_module()`, delegates to `module.on_instructor_launch(ctx)` or `module.on_student_launch(ctx)` with a normalized `LTIContext`
- **`/setup` endpoint**: Passes `get_all_modules()` and `modules_json` to the setup template for the activity type selector UI
- **`/configure` endpoint**: Extracts `activity_type` from form data and passes it to `manager.configure_activity()`

#### Changes integrated from dev branch:

**Session management overhaul** — replaced in-memory tokens for instructor flows with LAMB JWTs:

| Before (old) | After (integrated) |
|---|---|
| `_tokens` dict, `_create_token()`, `_validate_token()`, `_consume_token()` | Removed entirely |
| `_create_setup_token()` / `_validate_setup_token()` | `_create_setup_jwt()` → `_validate_lti_jwt(token, "setup")` |
| `_create_token({type: "dashboard"})` | `_create_dashboard_jwt(activity, instructor_user, ...)` |
| Consent: `_create_token({type: "consent"}, ttl=...)` | `_create_consent_token()` (still in-memory, one-shot) |
| `SETUP_TOKEN_TTL = 600` (10 min) | `LTI_SETUP_JWT_EXPIRY = timedelta(hours=2)` |
| `DASHBOARD_TOKEN_TTL = 1800` (30 min) | `LTI_DASHBOARD_JWT_EXPIRY = timedelta(days=7)` |

**Import changes:**
- Added: `from lamb import auth as lamb_auth`, `from datetime import timedelta`
- Removed: `from lamb.owi_bridge.owi_users import OwiUserManager`, `from lamb.auth_context import validate_user_enabled`

**Endpoint-specific changes:**

| Endpoint | Change |
|---|---|
| `/setup` | Accepts both setup and dashboard JWTs (for reconfigure). Re-fetches creator users from DB via `get_creator_user_by_id()` instead of embedding them in the token |
| `/configure` | Uses JWT. Issues dashboard JWT after configure (no OWI user creation at this point) |
| `/link-account` | Uses `manager.verify_creator_credentials()` instead of inline OWI+validate logic. Issues new setup JWT after linking |
| `/reconfigure` | Uses `manager.determine_is_owner()` (dynamic) instead of `data.get("is_owner")` (static from token) |
| `/dashboard` | Uses `determine_is_owner()` dynamically |
| `/dashboard/*` APIs | All use `_validate_lti_jwt(token, "dashboard")` |
| `/enter-chat` | Passes `is_instructor=True` to `manager.handle_student_launch()` |
| `/consent` | Uses `_validate_consent_token()` / `_consume_consent_token()` (unchanged logic, just renamed functions) |

### `backend/lamb/templates/lti_activity_setup.html`

- **Added**: Activity Type radio selector that loops through `modules` context variable
- **Added**: Dynamic rendering of module-specific setup fields via JavaScript (`modulesData` JSON + `renderOptions()`)
- Each module's `get_setup_fields()` output is serialized to JSON and used to render extra form fields

### `backend/lamb/modules/chat/__init__.py` (post-dev integration)

- `on_instructor_launch()`: Updated to use `_create_dashboard_jwt()` instead of old `_create_token()` with dict payload. Ownership is now determined dynamically by the dashboard endpoint, not embedded in the token.

## Architecture: How Module Dispatch Works

```
POST /lamb/v1/lti/launch
    │
    ├── Validate OAuth
    ├── Look up activity by resource_link_id
    │
    ├── Activity IS configured:
    │   ├── activity_type = activity['activity_type']   (default: 'chat')
    │   ├── module = get_module(activity_type)
    │   ├── Build LTIContext(resource_link_id, lms_user_id, roles, ...)
    │   │
    │   ├── Student:
    │   │   ├── Consent check (router-level, pre-module)
    │   │   └── module.on_student_launch(ctx) → RedirectResponse
    │   │
    │   └── Instructor:
    │       └── module.on_instructor_launch(ctx) → RedirectResponse
    │
    └── Activity NOT configured:
        ├── Student → "Not configured yet" page
        └── Instructor → Setup flow (JWT) → /setup page with module selector
```

## Database Changes

```sql
-- Added to lti_activities table
ALTER TABLE lti_activities ADD COLUMN activity_type TEXT NOT NULL DEFAULT 'chat';
```

## Known Limitations (to address in future phases)

1. **Module routers not mounted**: `ActivityModule.get_routers()` is defined but `main.py` does not yet mount them. Future modules with custom API endpoints will need this.
2. **Chat module `on_activity_configured`** calls `ChatModuleService.configure_activity()` for OWI group setup, but this hook is not yet called from the router's `/configure` endpoint (OWI group creation still happens via the old path in the manager).
3. **Frontend**: LTI-facing pages still use Jinja2 templates. Phase 3 will port these to SvelteKit.

## Verification

All three modified Python files parse correctly and have no lint errors:
- `backend/lamb/lti_router.py`
- `backend/lamb/lti_activity_manager.py`
- `backend/lamb/modules/chat/__init__.py`
