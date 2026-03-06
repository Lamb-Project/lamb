# LTI Session Management Fix

**Status:** Implementation  
**Created:** March 4, 2026  
**Related:** `lti_router.py`, `lti_activity_manager.py`, `lamb/auth.py`

---

## 1. Problem Statement

Instructors using the Unified LTI activity (`POST /lamb/v1/lti/launch`) intermittently see a **"Session expired"** message when interacting with the dashboard, setup page, or reconfigure flow. This happens because the Unified LTI uses short-lived in-memory tokens for session management, which expire after 10–30 minutes.

*(Screenshot: Moodle LTI activity showing "Session expired. Please click the LTI link in your LMS again.")*

The root cause is that the Unified LTI router was built before LAMB had its own JWT infrastructure and was never updated when LAMB-native authentication was introduced (#265).

---

## 2. Current Architecture (The Problem)

### 2.1 How Sessions Work Today

The Unified LTI router (`lti_router.py`) manages sessions with an in-memory Python dict:

```python
_tokens: dict = {}
SETUP_TOKEN_TTL = 600       # 10 minutes
DASHBOARD_TOKEN_TTL = 1800  # 30 minutes
CONSENT_TOKEN_TTL = 600     # 10 minutes
```

On each LTI launch, LAMB validates the OAuth 1.0 signature from the LMS, creates a token, stores it in the dict, and redirects the user to a page with `?token=XYZ` in the URL. Every subsequent request validates the token against this dict.

### 2.2 Why It Fails

| Problem | Impact |
|---------|--------|
| Dashboard token expires after 30 minutes | Instructors reviewing students, reading chat transcripts, or simply leaving the tab open lose their session |
| Setup token expires after 10 minutes | Instructors deliberating over assistant selection lose their session |
| Tokens are in-memory | Lost on server restart — all active sessions invalidated |
| No refresh mechanism | Once expired, the only recovery is re-clicking the LTI link in the LMS |
| Not scalable | In-memory dict doesn't work for multi-instance deployments |

### 2.3 The Auth Refactoring Gap

In February 2026, commit `e48dbc7` (#265) introduced LAMB-native authentication:

- `lamb/auth.py` provides `create_token()` and `decode_token()` using HS256 JWTs
- LAMB became the source of truth for passwords and tokens
- OWI was demoted to a downstream mirror
- The **LTI Creator router** was updated to use LAMB JWTs (replacing `owi_user_manager.get_auth_token()` with `lamb_auth.create_token()`)

However, the **Unified LTI router was not updated**. It continues to use its pre-refactoring bespoke in-memory token store, making it the only LAMB-side authentication flow that doesn't use LAMB JWTs.

---

## 3. User Model Clarification

Three distinct user types participate in LTI flows. Understanding their differences is critical to the fix.

### 3.1 LTI Activity User (Student / Chat User)

- **Created by:** `handle_student_launch()` in `lti_activity_manager.py`
- **Identity:** OWI end-user with synthetic email `{username}_{resource_link_id}@lamb-lti.local`
- **Token:** OWI JWT (via `owi_user_manager.get_auth_token()`)
- **Stored in:** `lti_activity_users` table (LAMB DB) + `user`/`auth` tables (OWI DB)
- **Scope:** Bound to one specific LTI activity. Same Moodle person → N different activity users (one per `resource_link_id`)
- **Used by:** Students AND instructors when they click "Enter Chat" on the dashboard
- **Key point:** This is an OWI identity. The OWI token authenticates to OWI, not to LAMB's dashboard.

### 3.2 LTI Creator User (Creator LTI — Separate Endpoint)

- **Created by:** `lti_creator_launch()` in `lti_creator_router.py`
- **Identity:** LAMB Creator user in `Creator_users` with `auth_provider='lti_creator'`
- **Token:** LAMB JWT (via `lamb.auth.create_token()`) — updated in #265
- **Endpoint:** `POST /lamb/v1/lti_creator/launch` (completely separate from Unified LTI)
- **Scope:** Tied to an organization, identified by `lti_user_id` from LMS
- **Used by:** Educators building assistants in the Creator Interface (SPA)
- **Key point:** This is a LAMB identity with full Creator permissions. Not involved in the Unified LTI flow.

### 3.3 Unified LTI Instructor (The Gap)

- **Created by:** Currently not modeled as a persistent identity
- **Identity:** Identified via `identify_instructor()` → matched to a Creator user (if one exists)
- **Token:** In-memory bespoke token (30 min TTL) — the problem
- **Endpoint:** `POST /lamb/v1/lti/launch` → redirects to `/lti/dashboard`
- **Who they are:**
  - The **first instructor** to configure an activity MUST be a Creator user (typically an `lti_creator` user who built the assistants). `identify_instructor()` resolves them by email, `lti_user_id`, or identity link. If no Creator account is found, they see "Contact your LAMB administrator."
  - **Subsequent instructors** do NOT need Creator accounts. The code only checks `is_instructor(roles)` — a simple string match on the LMS roles parameter. Any Moodle "Instructor"/"Teacher" role qualifies.
- **Key point:** Today, the instructor's dashboard session has no persistent identity. It's a transient token that expires quickly and has no connection to any user record.

### 3.4 Relationship Between Types

```
Same Moodle instructor may have:

┌─────────────────────────────────────────────────────────────────┐
│ LTI Creator User (from /v1/lti_creator/launch)                  │
│   email: lti_creator_physics_jsmith@lamb-lti.local              │
│   auth: LAMB JWT (7 days)                                       │
│   purpose: Build assistants in Creator Interface                │
│   table: Creator_users                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Activity User for PHY101 activity (from "Enter Chat")           │
│   email: jsmith_abc123@lamb-lti.local                           │
│   auth: OWI JWT (for OWI chat)                                  │
│   purpose: Chat with assistants as end-user                     │
│   table: lti_activity_users                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Dashboard session (from /v1/lti/launch on configured activity)  │
│   auth: In-memory token (30 min) ← THE PROBLEM                 │
│   purpose: View dashboard, manage activity, enter chat          │
│   table: (none — stateless)                                     │
└─────────────────────────────────────────────────────────────────┘
```

Note that the first instructor has **all three** identities. Subsequent instructors (non-Creator) only have the bottom two.

---

## 4. Constraints

### 4.1 Iframe Context

Most LMS platforms (including Moodle) embed LTI tools in **iframes**. This means LAMB's domain is a third-party context, which rules out cookies:

- **Safari** blocks all third-party cookies (Intelligent Tracking Prevention)
- **Chrome** is increasingly restricting third-party cookies (Privacy Sandbox)
- **Firefox** Enhanced Tracking Protection can also block them
- Setting `SameSite=None; Secure` is unreliable across browsers in iframe contexts

**Consequence:** Session management must use URL-based tokens, not cookies.

### 4.2 Non-Creator Instructors

Subsequent instructors accessing a configured activity's dashboard may not have LAMB Creator accounts. The auth solution must work for users who only exist as LMS identities (identified by `user_id` and `roles` from the LTI POST).

### 4.3 OWI Redirect Requires OWI Tokens

When any user (student or instructor) enters the OWI chat interface, they need an OWI JWT obtained via `owi_user_manager.get_auth_token()`. This cannot be replaced by a LAMB JWT because OWI is a separate application with its own token validation. The OWI token is obtained at the moment of redirect and is not related to the dashboard session.

### 4.4 Server-Rendered Pages

The Unified LTI dashboard, setup, and consent pages are **Jinja2 templates** served by FastAPI, not part of the Svelte SPA. They cannot use the SPA's `localStorage`-based token management. Token passing happens via URL query parameters and form hidden fields.

---

## 5. Proposed Solution

### 5.1 Core Change: Replace In-Memory Tokens with LAMB JWTs

Use `lamb.auth.create_token()` / `decode_token()` for all instructor-facing Unified LTI sessions. This is the same infrastructure the Creator LTI and Creator Interface already use.

**Token payload for dashboard sessions:**

```python
from lamb import auth as lamb_auth

token = lamb_auth.create_token({
    "sub": lti_activity_user_id,        # activity-specific user identity
    "email": activity_user_email,        # synthetic email
    "lti_type": "dashboard",             # distinguishes from Creator JWTs
    "lti_resource_link_id": resource_link_id,
    "lti_activity_id": activity['id'],
    "lti_lms_user_id": lms_user_id,
    "lti_display_name": display_name,
})
```

**Token payload for setup sessions:**

```python
token = lamb_auth.create_token({
    "sub": str(creator_user['id']),      # Creator user (required for setup)
    "email": creator_user['user_email'],
    "lti_type": "setup",
    "lti_resource_link_id": resource_link_id,
    "lti_context_id": context_id,
    "lti_context_title": context_title,
    "lti_lms_user_id": lms_user_id,
    "lti_lms_email": lms_email,
    "lti_creator_user_ids": [cu['id'] for cu in creator_users],
}, expires_delta=timedelta(hours=2))
```

### 5.2 Activity-Specific Instructor Identity

On instructor LTI launch (for a configured activity), create the activity-specific OWI user **upfront** — not deferred to "Enter Chat":

```
POST /lti/launch (configured activity + instructor role)
    │
    ├── Create activity-specific OWI user (handle_student_launch)
    │     → email: {username}_{resource_link_id}@lamb-lti.local
    │     → OWI user created/fetched
    │     → Added to activity's OWI group
    │     → Recorded in lti_activity_users
    │
    ├── Issue LAMB JWT with activity claims
    │     → sub: lti_activity_user.id or owi_user_id
    │     → lti_type: "dashboard"
    │     → lti_resource_link_id: ...
    │
    └── Redirect to /lti/dashboard?token={LAMB_JWT}
```

This means:
- The instructor has a persistent identity in `lti_activity_users` from the first dashboard visit
- The LAMB JWT is tied to this identity
- "Enter Chat" only needs to obtain a fresh OWI token (the OWI user already exists)
- `is_owner` is derived from the database: `activity.owner_email == instructor_creator_email`

### 5.3 Distinguishing Instructor Activity Users

Add an `is_instructor` column to the `lti_activity_users` table to distinguish instructors from students. This is useful for:
- Dashboard anonymization (don't anonymize instructor entries)
- Access control (dashboard endpoints require `is_instructor = true`)
- Analytics (exclude instructor test chats from student stats)

```sql
ALTER TABLE lti_activity_users ADD COLUMN is_instructor INTEGER NOT NULL DEFAULT 0;
```

### 5.4 Dashboard Token Validation

Replace `_validate_token()` with `lamb.auth.decode_token()` in all dashboard endpoints:

```python
@router.get("/dashboard")
async def lti_dashboard(request: Request, resource_link_id: str = "", token: str = ""):
    payload = lamb_auth.decode_token(token)
    if not payload or payload.get("lti_type") != "dashboard":
        return HTMLResponse(
            "<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>",
            status_code=403
        )
    if payload.get("lti_resource_link_id") != resource_link_id:
        return HTMLResponse("<h2>Invalid request.</h2>", status_code=400)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    # ... derive is_owner from DB, not from token ...
```

### 5.5 Student Consent Flow

The student consent flow is a short-lived, one-shot interaction (student sees consent notice → accepts → redirect to OWI). Two options:

**Option A — Keep in-memory tokens:** The 10-minute TTL is adequate for a consent click. The student never returns to this page.

**Option B — Use LAMB JWT:** Issue a short-lived LAMB JWT with `lti_type: "consent"` and consent-specific claims. More consistent but not strictly necessary.

Recommendation: **Option A** for simplicity. The consent flow is not affected by the session expiration problem.

### 5.6 Owner Determination

Currently, `is_owner` is pre-computed at LTI launch time by comparing `lms_email` with `activity.owner_email`. This is fragile (email matching) and baked into the token.

With the new approach, derive it dynamically:

```python
# In lti_router.py, on each dashboard request:
activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
instructor_email = payload.get("email")

# Check if this instructor's Creator identity is the activity owner
is_owner = False
if activity.get('owner_email'):
    # The owner_email in lti_activities is the Creator user email
    # Check if this LMS user is linked to that Creator user
    creator_users = manager.identify_instructor(
        lms_user_id=payload.get("lti_lms_user_id"),
        lms_email=payload.get("email")
    )
    is_owner = any(cu['user_email'] == activity['owner_email'] for cu in (creator_users or []))
```

This is more accurate than email string matching and works even if the owner's email format differs from their LMS email.

---

## 6. Changes Required

### 6.1 `lti_router.py`

| Section | Change |
|---------|--------|
| Token store (`_tokens` dict) | Remove for instructor flows. Keep only for student consent. |
| `lti_launch()` — configured + instructor | Create activity-specific OWI user upfront. Issue LAMB JWT with LTI claims. |
| `lti_launch()` — unconfigured + instructor (setup) | Issue LAMB JWT with `lti_type: "setup"` and creator_user_ids. |
| `lti_setup_page()` | Validate LAMB JWT instead of `_validate_setup_token()`. Re-fetch Creator users from DB using IDs in JWT. |
| `lti_configure_activity()` | Validate LAMB JWT. Issue new dashboard LAMB JWT after configuration. |
| `lti_dashboard()` | Validate LAMB JWT with `lti_type: "dashboard"`. Derive `is_owner` from DB. |
| `lti_dashboard_*()` (AJAX endpoints) | Validate LAMB JWT. |
| `lti_enter_chat()` | Validate LAMB JWT. Get fresh OWI token for redirect (OWI user already exists). |
| `lti_reconfigure_activity()` | Validate LAMB JWT. Check ownership from DB. |

### 6.2 `lti_activity_manager.py`

| Change | Detail |
|--------|--------|
| New method: `create_instructor_activity_user()` | Wraps `handle_student_launch()` logic but marks the user as `is_instructor=1` |
| `handle_student_launch()` | Add optional `is_instructor` parameter, default `False` |

### 6.3 `database_manager.py`

| Change | Detail |
|--------|--------|
| Migration | Add `is_instructor` column to `lti_activity_users` |
| `create_lti_activity_user()` | Accept and store `is_instructor` flag |

### 6.4 Dashboard Template (`lti_dashboard.html`)

| Change | Detail |
|--------|--------|
| Token in AJAX calls | Use the LAMB JWT (longer-lived, no refresh needed within a session) |
| No keepalive needed | 7-day JWT TTL means no periodic refresh |

---

## 7. Pre-Existing Bug: `is_owner` Broken for LTI Creator Owners

### 7.1 The Bug

When an activity is configured, `owner_email` is stored as the **Creator user's LAMB email**:

```python
# database_manager.py — create_lti_activity()
# owner_email = configured_by_email = creator_user["user_email"]
# For lti_creator users: "lti_creator_physics_jsmith@lamb-lti.local"
```

At launch time, the owner check compares the **LMS email** with this stored email:

```python
# lti_router.py line 155
is_owner = (lms_email and lms_email == activity.get('owner_email'))
# lms_email = "john.smith@university.edu" (from lis_person_contact_email_primary)
# owner_email = "lti_creator_physics_jsmith@lamb-lti.local"
# → NEVER matches for lti_creator owners
```

**Result:** `lti_creator` owners (the primary use case in LTI-driven Moodle deployments) can never see the "Manage Assistants" button on the dashboard. The owner check only works for regular password-based Creator users whose LAMB email happens to be their institutional email.

### 7.2 How This Fix Resolves It

The new dynamic owner check uses `identify_instructor()` to resolve the LMS identity back to the Creator user, then compares Creator emails:

```python
creator_users = manager.identify_instructor(lms_user_id=..., lms_email=...)
is_owner = any(cu['user_email'] == activity['owner_email'] for cu in (creator_users or []))
```

This works because `identify_instructor()` searches by `lti_user_id` match (strategy 2 in `get_creator_users_by_lms_identity`), which correctly resolves `lti_creator` users regardless of email mismatch.

---

## 8. Backward Compatibility: Existing Activities

### 8.1 No Impact

| Aspect | Detail |
|--------|--------|
| **Student OWI accounts** | Untouched. `handle_student_launch()` does get-or-create — existing OWI users are reused. |
| **Activity configuration** | `lti_activities` table unchanged. Existing resource_link_id → activity mappings remain. |
| **OWI groups and model access** | Untouched. Group membership and model `access_control` are not modified. |
| **Creator LTI flow** | No changes (`lti_creator_router.py` already uses LAMB JWTs). |
| **Legacy Student LTI flow** | No changes (`lti_users_router.py` uses OWI tokens for OWI redirect). |

### 8.2 One-Time Disruption

Any instructor with an active in-memory dashboard token at the time of deployment will see "Session expired" when they next interact with the dashboard (server restart clears the `_tokens` dict). This is the same disruption that already occurs on every server restart — it just happens one final time. After re-clicking the LTI link, they get a LAMB JWT that lasts 7 days.

### 8.3 Migrations

| Migration | Effect on existing data |
|-----------|----------------------|
| `is_instructor` column on `lti_activity_users` | `DEFAULT 0` — all existing rows stay as students. Instructors who previously used "Enter Chat" are marked as students but get corrected to `is_instructor=1` on their next LTI launch. |
| Owner check logic change | **Fixes** the pre-existing bug for `lti_creator` owners (§7). No data migration needed. |

### 8.4 What Instructors Experience After Deployment

1. Instructor clicks LTI link in Moodle (as before)
2. New code creates their activity-specific OWI user upfront (was deferred to "Enter Chat")
3. Instructor receives a LAMB JWT → redirected to dashboard
4. Dashboard works for 7 days without "Session expired"
5. "Enter Chat" obtains a fresh OWI token (OWI user already exists from step 2)

---

## 9. Migration Notes

- The in-memory token store (`_tokens` dict) is kept for the student consent flow only
- Existing LTI activities are unaffected — no schema migration for `lti_activities`
- The `is_instructor` column migration uses `DEFAULT 0`, so existing `lti_activity_users` rows (all students) remain correct
- No changes to the Creator LTI flow (`lti_creator_router.py`) — it already uses LAMB JWTs
- No changes to the Legacy Student LTI flow (`lti_users_router.py`) — it uses OWI tokens for OWI redirect, which is correct

---

## 10. Security Considerations

### 10.1 JWT in URL

LAMB JWTs appear in the URL query string (`?token=...`). This is the same pattern the Creator LTI already uses (`/assistants?token={jwt}`). Risks and mitigations:

- **Browser history:** The URL with token is recorded. Mitigated by the 7-day expiry and the fact that the LTI iframe context typically doesn't expose history to the user.
- **Referrer leakage:** If the dashboard page links to external resources, the `Referer` header could leak the token. Mitigated by adding `Referrer-Policy: no-referrer` to dashboard responses.
- **Server logs:** URLs (including tokens) may appear in access logs. Same as existing Creator LTI behavior. Operational concern, not a code change.

### 10.2 Token Scope

The LAMB JWT for dashboard sessions includes `lti_type: "dashboard"`. All LTI dashboard endpoints check this claim, preventing a dashboard token from being used to access the Creator Interface or other LAMB APIs that expect a standard Creator user token.

### 10.3 Non-Creator Instructors

Instructors without Creator accounts receive a LAMB JWT with `sub` set to their activity-specific user ID (not a Creator user ID). The `AuthContext` system (`get_auth_context()`) is NOT used for these tokens — the LTI router validates them directly via `lamb.auth.decode_token()` and checks the `lti_type` claim. This avoids any confusion with Creator Interface authentication.

---

## 11. Testing Checklist

- [ ] Instructor launches configured activity → gets dashboard with LAMB JWT → session persists for hours
- [ ] Instructor stays on dashboard > 30 minutes → no "Session expired"
- [ ] Instructor clicks "Enter Chat" after extended time on dashboard → successfully redirects to OWI
- [ ] Instructor reconfigures assistants → works without session expiry
- [ ] Second instructor (non-Creator) launches same activity → gets dashboard
- [ ] Activity owner sees "Manage" button; non-owner instructor does not
- [ ] Student launches → consent flow works (in-memory token, unchanged)
- [ ] Student launches → direct OWI redirect works (unchanged)
- [ ] Server restart → instructor re-clicks LTI link in LMS → new JWT issued → works
- [ ] Server restart → student consent in progress → "Session expired" (acceptable — short flow)
- [ ] Dashboard AJAX calls (stats, students, chats) work with LAMB JWT
- [ ] Dashboard AJAX calls fail gracefully with expired JWT (7 days later)
- [ ] Setup flow → instructor takes 30+ minutes → still works
- [ ] Setup flow → instructor belongs to multiple orgs → org selection works

---

## 12. Summary

The Unified LTI dashboard's "Session expired" problem exists because its session management predates LAMB's JWT infrastructure. The fix aligns the Unified LTI with the rest of LAMB by:

1. Replacing the in-memory token store with `lamb.auth.create_token()` / `decode_token()` for instructor sessions
2. Creating activity-specific instructor identities upfront (not deferred to "Enter Chat")
3. Deriving `is_owner` from the database instead of baking it into the token
4. Adding an `is_instructor` flag to `lti_activity_users` to distinguish roles

No changes to the student flow, Creator LTI, or Legacy Student LTI. The cookie-based approach was considered but rejected due to third-party cookie restrictions in LMS iframe contexts.
