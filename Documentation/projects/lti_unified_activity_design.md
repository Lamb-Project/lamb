# Design: Unified LTI Activity Endpoint

**Status:** APPROVED  
**Date:** February 6, 2026  
**Author:** Design conversation  
**Depends on:** [lti_landscape.md](../lti_landscape.md)

### Resolved Design Decisions

| Decision | Resolution |
|----------|-----------|
| Student identity scope | Per `resource_link_id` — each LTI placement = separate identity |
| Reconfiguration access | Org admins can manage all LTI activities in their org |
| Activity org-binding | **Activities are bound to one organization.** Instructor must choose an org during setup; only assistants from that org are shown. No mixing across orgs. |
| Unpublished assistants in activity | OWI handles it naturally — model disappears from the chat UI |

---

## 1. Problem Statement

The current Student LTI model has a **1:1 relationship** between LTI activities and assistants. Every time an instructor wants to expose an assistant via LTI, they must:
1. Publish the assistant in LAMB
2. Copy the consumer key/secret from LAMB
3. Create a new LTI activity in the LMS
4. Paste credentials

And for the student, each activity = one assistant = one isolated identity.

**We want:** One LTI tool configured once in the LMS, and **instructors choose which published assistants** are available per activity — including multiple assistants per activity.

---

## 2. Design Goals

1. **One LTI key/secret for all of LAMB** — configured in `.env` or overridden by admin in DB
2. **Instructor-driven setup** — First instructor launch shows a picker for published assistants
3. **Multi-assistant activities** — One LTI activity can expose N published assistants
4. **Same student experience** — After setup, students arrive at OWI and see the selected assistants
5. **Minimal disruption** — New endpoint, no changes to existing LTI paths

---

## 3. High-Level Flow

```
                            ┌──────────────────────────────┐
                            │         LMS Course           │
                            │                              │
                            │  [AI Assistants] ← LTI link  │
                            └──────────┬───────────────────┘
                                       │
                                       │ POST /lamb/v1/lti/launch
                                       │ (OAuth 1.0 signed)
                                       ▼
                            ┌──────────────────────────────┐
                            │      LAMB LTI Router         │
                            │                              │
                            │  1. Validate OAuth signature │
                            │  2. Check resource_link_id   │
                            └──────┬───────────┬───────────┘
                                   │           │
                    Activity       │           │  Activity
                    NOT configured │           │  IS configured
                                   │           │
                    ┌──────────────┘           └──────────────┐
                    │                                          │
                    ▼                                          ▼
         ┌─────────────────────┐                   ┌─────────────────────┐
         │  Is user Instructor? │                   │  Student/Instructor │
         └───┬─────────────┬───┘                   │  → Standard OWI    │
             │             │                        │    redirect        │
          YES│          NO │                        └─────────────────────┘
             │             │
             ▼             ▼
    ┌────────────────┐  ┌─────────────────┐
    │ Identify as    │  │ "Not set up yet"│
    │ Creator user   │  │  waiting page   │
    │                │  └─────────────────┘
    │ Show assistant │
    │ picker UI      │
    │                │
    │ Save config    │
    │ → Create group │
    │ → Add models   │
    └────────────────┘
```

---

## 4. The Activity Lifecycle

### Phase 1: First Launch (Instructor Setup)

```
Instructor clicks LTI link in LMS
    │
    ▼
LAMB receives POST with resource_link_id = "abc123"
    │
    ▼
No lti_activity exists for "abc123" → SETUP MODE
    │
    ▼
LTI roles contain "Instructor" → Proceed
    │
    ▼
Identify instructor as LAMB Creator user (see §5)
    │
    ▼
Serve setup page: list of published assistants the instructor can access
    │
    ▼
Instructor checks: ☑ Physics Tutor  ☑ Lab Helper  ☐ Essay Reviewer
    │
    ▼
POST /lamb/v1/lti/activity/configure
    │
    ├── Create OWI group: "lti_activity_abc123"
    ├── For each selected assistant model (lamb_assistant.{id}):
    │       call add_group_to_model(model_id, activity_group_id)
    ├── Store lti_activity record in LAMB DB
    └── Redirect instructor to OWI (they're now a user too)
```

### Phase 2: Student Launch (Normal Use)

```
Student clicks same LTI link
    │
    ▼
LAMB receives POST with resource_link_id = "abc123"
    │
    ▼
lti_activity exists for "abc123" → LAUNCH MODE
    │
    ▼
Generate email: {username}_{resource_link_id}@lamb-lti.local
    │
    ▼
Get/create OWI user → Add to activity group → Get token
    │
    ▼
Redirect to OWI: /api/v1/auths/complete?token=X
    │
    ▼
Student sees: Physics Tutor, Lab Helper (both accessible)
```

### Phase 3: Reconfiguration (Instructor Returns)

When an instructor returns to an already-configured activity:
- They go to OWI like everyone else (default behavior)
- A **"Reconfigure"** link/button in OWI or a special URL param allows re-entering setup mode
- OR: we add a `?setup=true` param that instructors can use

---

## 5. Instructor Identification

This is the trickiest part. When an instructor arrives via LTI, we need to map them to a LAMB Creator user to know which published assistants they can see.

### Identification Strategy (waterfall)

```
1. Try: match lis_person_contact_email_primary → Creator_users.user_email
         (works for password-auth creator users with institutional email)

2. Try: match user_id → Creator_users.lti_user_id
         (works for existing LTI creator users)

3. Try: check lti_identity_links table for previous mapping
         (works for returning instructors who linked manually)

4. Fallback: show "Link your LAMB account" page
         → Instructor enters LAMB Creator email + password
         → LAMB verifies credentials
         → Stores mapping in lti_identity_links for future visits
```

### Why not auto-create?

Unlike the Creator LTI path (which auto-creates creator users), here the instructor **must already be a Creator user** because we need them to have published assistants. Auto-creating would give them an empty account with no assistants to pick.

### Multi-Organization Access & Org-Binding

**Activities are bound to one organization.** An instructor cannot mix assistants from different orgs into one activity.

If the instructor identification (§5 waterfall) resolves to **multiple Creator accounts** across different organizations, the setup flow adds an **org selection step** before showing assistants:

```
Instructor identified → found in 2 orgs: Engineering, Physics
    │
    ▼
"Choose organization for this activity:"
    ○ Engineering Department
    ○ Physics Department
    │
    ▼ (selects Physics)
    │
Activity bound to Physics org → show only Physics published assistants
```

If the instructor belongs to only one org, this step is skipped.

Once bound, the activity's `organization_id` is set and only assistants from that org are ever shown — including on reconfiguration.

### Org Admin Access to Activities

Organization admins can view and manage all LTI activities bound to their organization. This enables:
- Viewing which activities exist in the org
- Reconfiguring activities (e.g., if the original instructor leaves)
- Disabling activities

This is exposed via a new section in the org-admin panel and backed by:
```
GET /creator/admin/lti-activities          → List activities for admin's org
PUT /creator/admin/lti-activities/{id}     → Update activity (reconfigure, disable)
```

---

## 6. Database Schema

### 6.1 New Table: `lti_global_config`

Singleton table for the global LTI credentials.

```sql
CREATE TABLE lti_global_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    oauth_consumer_key TEXT NOT NULL,
    oauth_consumer_secret TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    updated_by TEXT  -- Email of admin who last changed it
);
```

**Precedence logic:**
```python
def get_lti_credentials():
    # DB overrides .env
    db_config = db_manager.get_lti_global_config()
    if db_config:
        return db_config['oauth_consumer_key'], db_config['oauth_consumer_secret']
    
    # Fall back to .env
    key = os.getenv('LTI_GLOBAL_CONSUMER_KEY', 'lamb')
    secret = os.getenv('LTI_GLOBAL_SECRET')  # or reuse LTI_SECRET
    return key, secret
```

### 6.2 New Table: `lti_activities`

One row per LTI activity placement in an LMS. **Bound to one organization.**

```sql
CREATE TABLE lti_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_link_id TEXT NOT NULL UNIQUE,  -- LTI resource_link_id (unique per placement)
    organization_id INTEGER NOT NULL,       -- Bound organization (NO mixing across orgs)
    context_id TEXT,                         -- LTI context_id (course identifier)
    context_title TEXT,                      -- Course name from LTI
    activity_name TEXT,                      -- Custom name set by instructor
    owi_group_id TEXT NOT NULL,             -- OWI group UUID for this activity
    owi_group_name TEXT NOT NULL,           -- OWI group name
    configured_by_email TEXT NOT NULL,      -- Creator user email who configured it
    configured_by_name TEXT,                -- Display name
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'disabled'
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE UNIQUE INDEX idx_lti_activities_resource_link ON lti_activities(resource_link_id);
CREATE INDEX idx_lti_activities_org ON lti_activities(organization_id);
```

### 6.3 New Table: `lti_activity_assistants`

Junction table: which assistants belong to which activity.

```sql
CREATE TABLE lti_activity_assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    assistant_id INTEGER NOT NULL,
    added_at INTEGER NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES lti_activities(id) ON DELETE CASCADE,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    UNIQUE(activity_id, assistant_id)
);

CREATE INDEX idx_lti_activity_assistants_activity ON lti_activity_assistants(activity_id);
```

### 6.4 New Table: `lti_activity_users`

Track users who have accessed via this activity (equivalent to current `lti_users`).

```sql
CREATE TABLE lti_activity_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,              -- Synthetic email
    user_name TEXT NOT NULL DEFAULT '',
    user_display_name TEXT NOT NULL,
    lms_user_id TEXT,                      -- Original user_id from LMS
    created_at INTEGER NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES lti_activities(id) ON DELETE CASCADE,
    UNIQUE(user_email, activity_id)
);
```

### 6.5 New Table: `lti_identity_links`

Maps LMS identities to LAMB Creator users (for instructor identification).

```sql
CREATE TABLE lti_identity_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lms_user_id TEXT NOT NULL,             -- user_id from LTI
    lms_email TEXT,                         -- lis_person_contact_email_primary
    creator_user_id INTEGER NOT NULL,      -- FK to Creator_users.id
    linked_at INTEGER NOT NULL,
    FOREIGN KEY (creator_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE
);

CREATE INDEX idx_lti_identity_lms_user ON lti_identity_links(lms_user_id);
CREATE INDEX idx_lti_identity_lms_email ON lti_identity_links(lms_email);
```

Note: No UNIQUE on `lms_user_id` alone — the same LMS user could be linked to different Creator accounts in different orgs.

### 6.6 Entity Relationship Diagram

```
lti_global_config (singleton)
    │
    │ provides oauth credentials
    │
    ▼
POST /lamb/v1/lti/launch
    │
    │ resource_link_id
    ▼
lti_activities ──N:1──► organizations (activity bound to one org)
    │
    ├──1:N──► lti_activity_assistants ──N:1──► assistants
    │                                              │
    │   owi_group_id                               ▼
    │                                        assistant_publish
    │                                        (must be published, same org)
    │
    ├──1:N──► lti_activity_users (students)
    │              │
    │              │ user_email
    │              ▼
    │         OWI user → OWI group (owi_group_id)
    │
    │
lti_identity_links
    │
    │ maps LMS user → Creator user(s)
    ▼
Creator_users ──N:1──► organizations
    │
    └── owns/shared → assistants (within same org)
```

---

## 7. API Endpoints

### 7.1 Main Launch Endpoint

```
POST /lamb/v1/lti/launch
```

The single entry point for all LTI launches. The router decides what to do based on `resource_link_id` and `roles`.

**LTI Parameters Used:**

| Parameter | Purpose | Required |
|-----------|---------|----------|
| `oauth_consumer_key` | Must match global key | Yes |
| `oauth_signature` | OAuth 1.0 HMAC-SHA1 | Yes |
| `resource_link_id` | Identifies this specific LTI placement | Yes |
| `roles` | Detect instructor vs student | Yes |
| `user_id` | LMS user identifier | Yes |
| `ext_user_username` | Username for email generation | Preferred |
| `lis_person_contact_email_primary` | Instructor identification | For instructors |
| `lis_person_name_full` | Display name | Optional |
| `context_id` | Course identifier | Optional |
| `context_title` | Course name | Optional |

**Decision logic:**

```python
@router.post("/launch")
async def lti_launch(request: Request):
    # 1. Validate OAuth
    # 2. Look up activity by resource_link_id
    
    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    
    if activity and activity['status'] == 'active':
        # CONFIGURED → route to student/user flow
        return await handle_configured_launch(request, post_data, activity)
    else:
        # NOT CONFIGURED → check if instructor
        if is_instructor(post_data.get('roles', '')):
            return await handle_instructor_setup(request, post_data, resource_link_id)
        else:
            # Student at unconfigured activity
            return HTMLResponse(WAITING_PAGE_HTML, status_code=200)
```

### 7.2 Setup Page

```
GET /lamb/v1/lti/setup?resource_link_id={id}&token={jwt}
```

Serves an HTML page showing the instructor their published assistants with checkboxes. This is a **self-contained HTML page** served by the backend (not the Svelte SPA), keeping the setup flow independent.

The page is lightweight: a list of assistants with checkboxes, an activity name input, and a "Save" button.

### 7.3 Instructor Login (Linking) Page

```
GET /lamb/v1/lti/link-account?resource_link_id={id}&lms_user_id={id}
POST /lamb/v1/lti/link-account
```

Shown when automatic instructor identification fails. Simple form: email + password. On success, stores a record in `lti_identity_links` and redirects to setup.

### 7.4 Configure Activity

```
POST /lamb/v1/lti/configure
Content-Type: application/json
Authorization: Bearer {token}

{
    "resource_link_id": "abc123",
    "activity_name": "PHY101 AI Tutors",
    "assistant_ids": [42, 67, 103],
    "context_id": "course_456",
    "context_title": "Introduction to Physics"
}
```

**Processing:**
1. Validate instructor token
2. Verify all `assistant_ids` are published and accessible to this instructor
3. Create OWI group: `lti_activity_{resource_link_id}`
4. For each assistant: `owi_model.add_group_to_model("lamb_assistant.{id}", group_id, "read")`
5. Insert `lti_activities` record
6. Insert `lti_activity_assistants` records
7. Redirect instructor to OWI as first user of the activity

### 7.5 Admin: Manage Global LTI Config

```
GET  /creator/admin/lti-global-config     → Current credentials (masked secret)
PUT  /creator/admin/lti-global-config     → Update credentials
```

Only accessible by system admins. Updates `lti_global_config` table.

### 7.6 Reconfigure Activity

```
GET  /lamb/v1/lti/setup?resource_link_id={id}&token={jwt}&reconfigure=true
POST /lamb/v1/lti/reconfigure
```

Allows instructor to change the assistant selection for an existing activity:
1. Load current selection
2. Show picker with current state
3. On save: remove activity group from de-selected models, add to newly selected models

---

## 8. Email & Identity for Students

### Student Email Format

```
{username}_{resource_link_id}@lamb-lti.local
```

Examples:
- `jsmith_abc123@lamb-lti.local`
- `mgarcia_def456@lamb-lti.local`

**Why `resource_link_id` instead of assistant name?**
- One identity per activity (not per assistant)
- Student sees all assistants in the activity with one account
- `resource_link_id` is guaranteed unique per LTI placement

### Instructor Email (When Using as Student)

After setup, the instructor is redirected to OWI. They get the same treatment as students:
- Synthetic email based on `resource_link_id`
- Added to the activity's OWI group
- Can chat with all selected assistants

---

## 9. OWI Group & Model Integration

### How Multi-Assistant Access Works

```
                    ┌─────────────────────────────┐
                    │   OWI Group                  │
                    │   "lti_activity_abc123"       │
                    │                               │
                    │   user_ids: [                 │
                    │     "uuid-jsmith",            │
                    │     "uuid-mgarcia",           │
                    │     "uuid-instructor"         │
                    │   ]                           │
                    └──────────┬────────────────────┘
                               │
                  access_control.read.group_ids
                  contains "lti_activity_abc123"
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ lamb_asst.42 │ │ lamb_asst.67 │ │ lamb_asst.103│
    │ Physics Tutor│ │ Lab Helper   │ │ Study Guide  │
    │              │ │              │ │              │
    │ access_ctrl: │ │ access_ctrl: │ │ access_ctrl: │
    │  read:       │ │  read:       │ │  read:       │
    │   group_ids: │ │   group_ids: │ │   group_ids: │
    │   - asst_42  │ │   - asst_67  │ │   - asst_103 │
    │   - lti_abc  │ │   - lti_abc  │ │   - lti_abc  │
    └──────────────┘ └──────────────┘ └──────────────┘
```

Each model keeps its original group (`assistant_{id}`) AND gets the activity group added. This means:
- Students via the old Student LTI path still work (via `assistant_{id}` group)
- Students via the new Unified LTI path work (via `lti_activity_{id}` group)
- Both paths coexist

### Key OWI Bridge Calls

```python
# During activity configuration:
owi_group = owi_group_manager.create_group(
    name=f"lti_activity_{resource_link_id}",
    user_id=instructor_owi_user_id,
    description=f"LTI Activity: {activity_name}"
)

for assistant_id in selected_assistant_ids:
    owi_model.add_group_to_model(
        model_id=f"lamb_assistant.{assistant_id}",
        group_id=owi_group['id'],
        permission_type="read"
    )

# During student launch:
owi_group_manager.add_user_to_group_by_email(
    group_id=activity['owi_group_id'],
    user_email=student_synthetic_email
)
```

---

## 10. Setup UI (Backend-Served Page)

A self-contained HTML page served by the backend. Minimal dependencies, clean design.

### Why Not the Svelte SPA?

1. **Independence** — Setup flow works even if frontend is broken/rebuilding
2. **Context** — The page needs LTI context (resource_link_id, course info) which comes from the launch POST, not the SPA routing
3. **Simplicity** — It's a checkbox list + save button, doesn't need a full SPA
4. **No auth complexity** — Uses a short-lived setup token, not the full Creator auth flow

### Page Contents

**Step 1 — Org Selection (only if instructor is in multiple orgs):**

```
┌──────────────────────────────────────────────────┐
│  🐑 LAMB Activity Setup                          │
│                                                    │
│  Course: Introduction to Physics (PHY101)          │
│                                                    │
│  You have accounts in multiple organizations.      │
│  Choose one for this activity:                     │
│                                                    │
│  ○ Engineering Department                          │
│  ● Physics Department                              │
│                                                    │
│  ⚠ This cannot be changed later.                  │
│                                                    │
│                      [ Continue ]                  │
└──────────────────────────────────────────────────┘
```

**Step 2 — Assistant Selection:**

```
┌──────────────────────────────────────────────────┐
│  🐑 LAMB Activity Setup                          │
│                                                    │
│  Course: Introduction to Physics (PHY101)          │
│  Organization: Physics Department                  │
│                                                    │
│  Activity Name: [PHY101 AI Assistants          ]   │
│                                                    │
│  Select assistants for this activity:              │
│                                                    │
│  Your Assistants:                                  │
│  ☑ Physics Tutor            (published)            │
│  ☑ Lab Report Helper        (published)            │
│  ☐ Essay Reviewer           (published)            │
│                                                    │
│  Shared With You:                                  │
│  ☐ General Science Helper   (by: prof@uni.edu)     │
│  ☐ Math Foundations         (by: math@uni.edu)     │
│                                                    │
│              [ Save & Launch ]                     │
└──────────────────────────────────────────────────┘
```

### Implementation

- Served as a Jinja2 template from `lamb/templates/lti_activity_setup.html`
- CSS: inline or minimal stylesheet (TailwindCSS CDN for consistent look)
- JS: minimal vanilla JS for the form submission
- The form POSTs to `/lamb/v1/lti/configure`

---

## 11. Comparison: Old vs New

| Aspect | Old Student LTI | New Unified LTI |
|--------|-----------------|-----------------|
| **Activities per LTI tool** | 1 assistant per LTI link | N assistants per LTI link |
| **LMS setup** | One LTI tool per assistant | One LTI tool for all of LAMB |
| **LTI credentials** | Global `LTI_SECRET` + assistant name as key | Global key/secret (configurable) |
| **Who configures?** | Instructor in LAMB → copy to LMS | Instructor directly in LTI flow |
| **Student email** | `{user}-{assistant_name}@lamb-project.org` | `{user}_{resource_link_id}@lamb-lti.local` |
| **OWI group** | Per assistant | Per activity |
| **Assistants visible** | 1 | 1-N (instructor's choice) |
| **Coexists with old?** | — | Yes, different endpoint |

---

## 12. File Structure (Proposed)

```
backend/lamb/
├── lti_router.py                    ← NEW: Main unified LTI router
│   ├── POST /launch                 ← Entry point
│   ├── GET  /setup                  ← Setup page
│   ├── POST /configure              ← Save activity config
│   ├── POST /link-account           ← Instructor identity linking
│   ├── GET  /activity/{id}/info     ← Activity info
│   └── POST /reconfigure            ← Update activity config
│
├── lti_activity_manager.py          ← NEW: Activity business logic
│   ├── get_lti_credentials()
│   ├── get_or_create_activity()
│   ├── get_published_assistants_for_instructor()
│   ├── configure_activity()
│   ├── handle_student_launch()
│   └── identify_instructor()
│
├── templates/
│   ├── lti_activity_setup.html      ← NEW: Setup page template
│   ├── lti_link_account.html        ← NEW: Account linking form
│   └── lti_waiting.html             ← NEW: "Not set up yet" page
│
├── database_manager.py              ← MODIFIED: New table operations
│   ├── create_lti_activity()
│   ├── get_lti_activity_by_resource_link()
│   ├── get_lti_activities_by_org()         ← For org-admin panel
│   ├── add_assistants_to_activity()
│   ├── remove_assistants_from_activity()
│   ├── get_activity_assistants()
│   ├── create_lti_activity_user()
│   ├── get_lti_global_config()
│   ├── set_lti_global_config()
│   ├── create_lti_identity_link()
│   ├── get_creator_user_by_lms_identity()
│   └── get_published_assistants_for_org_user()  ← owned + shared, published only
│
├── main.py                          ← MODIFIED: Mount new router
│   └── app.include_router(lti_router, prefix="/v1/lti")
│
creator_interface/
└── organization_router.py           ← MODIFIED: Add org-admin LTI activity management
    ├── GET  /admin/lti-activities                → List activities in org
    ├── GET  /admin/lti-activities/{id}           → Activity detail + assistants
    ├── PUT  /admin/lti-activities/{id}           → Reconfigure/disable activity
    ├── GET  /admin/lti-global-config             → View global LTI credentials
    └── PUT  /admin/lti-global-config             → Update global LTI credentials
```

---

## 13. Resolved Design Questions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | Student identity scope | **Per `resource_link_id`** | Safest isolation; each LTI placement = separate identity |
| Q2 | Unpublished assistants | **OWI handles naturally** | Model disappears from chat UI; stale activity records cleaned on reconfigure |
| Q3 | Instructor after setup | **Redirect to OWI** | Instructor can immediately test the assistants |
| Q4 | Reconfiguration access | **Org admins** of the activity's org can reconfigure; instructors who arrive via LTI with `Instructor` role too | Covers teaching teams and admin oversight |
| Q5 | Keep old Student LTI? | **Yes** | Coexistence; institutions migrate at own pace |
| Q6 | Multi-org instructors | **Must choose one org per activity** | No mixing assistants across orgs; activity is bound to `organization_id` |

---

## 14. Implementation Order

1. **Database migrations** — New tables (`lti_global_config`, `lti_activities`, `lti_activity_assistants`, `lti_activity_users`, `lti_identity_links`)
2. **Admin config endpoint** — GET/PUT `/creator/admin/lti-global-config`
3. **Main launch endpoint** — POST `/v1/lti/launch` with OAuth validation and routing
4. **Instructor identification** — Email matching + identity linking
5. **Setup page** — Template + published assistant query
6. **Configure endpoint** — Activity creation + OWI group/model wiring
7. **Student launch flow** — User creation + group add + redirect
8. **Reconfiguration** — Update activity + adjust model permissions
9. **Tests** — Unit tests for each component, E2E with Playwright

---

## 15. Security Considerations

- **OAuth replay protection:** Consider adding nonce/timestamp validation (currently missing in all LTI paths)
- **Setup token:** Short-lived JWT (5 min) for the setup page, prevents unauthorized configuration
- **Identity linking:** Rate-limit the login form to prevent brute force
- **Resource_link_id trust:** This value comes from the LMS via signed OAuth — trustworthy as long as signature is valid
- **Global secret rotation:** When admin changes the secret, existing LMS tools need updating. Consider a "rotation period" where both old and new secrets are valid
