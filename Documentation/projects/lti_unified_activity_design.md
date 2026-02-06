# Design: Unified LTI Activity Endpoint

**Status:** APPROVED (v2 — Dashboard & Chat Visibility)  
**Date:** February 6, 2026  
**Author:** Design conversation  
**Depends on:** [lti_landscape.md](../lti_landscape.md)

### Resolved Design Decisions

| Decision | Resolution |
|----------|-----------|
| Student identity scope | Per `resource_link_id` — each LTI placement = separate identity |
| Reconfiguration access | **Owner** of the activity manages assistants; any instructor sees the dashboard; org admins can manage all activities in their org |
| Activity org-binding | **Activities are bound to one organization.** Instructor must choose an org during setup; only assistants from that org are shown. No mixing across orgs. |
| Unpublished assistants in activity | OWI handles it naturally — model disappears from the chat UI |
| Instructor return behavior | Instructors see an **Instructor Dashboard** (not a direct OWI redirect) |
| Chat visibility | **Opt-in per activity.** Owner decides at creation time. Students must consent on first access. Chat transcripts are **always anonymized** for instructors. |

---

## 1. Problem Statement

The current Student LTI model has a **1:1 relationship** between LTI activities and assistants. Every time an instructor wants to expose an assistant via LTI, they must:
1. Publish the assistant in LAMB
2. Copy the consumer key/secret from LAMB
3. Create a new LTI activity in the LMS
4. Paste credentials

And for the student, each activity = one assistant = one isolated identity.

**We want:** One LTI tool configured once in the LMS, and **instructors choose which published assistants** are available per activity — including multiple assistants per activity. Instructors also need **visibility into how the tool is being used** without compromising student privacy.

---

## 2. Design Goals

1. **One LTI key/secret for all of LAMB** — configured in `.env` or overridden by admin in DB
2. **Instructor-driven setup** — First instructor launch shows a picker for published assistants
3. **Multi-assistant activities** — One LTI activity can expose N published assistants
4. **Instructor dashboard** — Any instructor landing on a configured activity sees usage stats, student access logs, and (optionally) anonymized chat history
5. **Activity ownership** — The instructor who creates the activity is the **owner** and can manage its assistant configuration
6. **Optional chat visibility** — Owner decides at creation time whether instructors can read anonymized chat transcripts; students are informed and must consent
7. **Same student experience** — After setup (and consent if needed), students arrive at OWI and see the selected assistants
8. **Minimal disruption** — New endpoint, no changes to existing LTI paths

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
         │  Is user Instructor? │                   │  Is user Instructor? │
         └───┬─────────────┬───┘                   └───┬─────────────┬───┘
             │             │                            │             │
          YES│          NO │                         YES│          NO │
             │             │                            │             │
             ▼             ▼                            ▼             ▼
    ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
    │ Identify as    │  │"Not set up   │  │  INSTRUCTOR      │  │  STUDENT     │
    │ Creator user   │  │ yet" waiting │  │  DASHBOARD       │  │  FLOW        │
    │                │  │ page         │  │                  │  │              │
    │ Show setup:    │  └──────────────┘  │ • Activity stats │  │ chat_visible │
    │ • Assistants   │                    │ • Student list   │  │ & no consent │
    │ • Activity name│                    │ • Chat history   │  │ yet?         │
    │ • Chat visible?│                    │   (if enabled)   │  │   ↓ YES      │
    │                │                    │ • [Open Chat] →  │  │ Show consent │
    │ OWNER = this   │                    │ • [Manage] →     │  │ page → then  │
    │ instructor     │                    │   (owner only)   │  │ OWI redirect │
    │                │                    └──────────────────┘  │   ↓ NO       │
    │ Save config    │                                          │ OWI redirect │
    │ → Create group │                                          └──────────────┘
    │ → Add models   │
    └────────────────┘
```

---

## 4. The Activity Lifecycle

### Phase 1: First Launch (Instructor Setup — becomes Owner)

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
Serve setup page:
  • Activity name
  • List of published assistants (checkboxes)
  • ☐ "Allow instructors to view anonymized chat transcripts" (chat_visibility option)
    │
    ▼
Instructor checks: ☑ Physics Tutor  ☑ Lab Helper  ☐ Essay Reviewer
                    ☑ Enable chat visibility
    │
    ▼
POST /lamb/v1/lti/configure
    │
    ├── Create OWI group: "lti_activity_abc123"
    ├── For each selected assistant model (lamb_assistant.{id}):
    │       call add_group_to_model(model_id, activity_group_id)
    ├── Store lti_activity record in LAMB DB
    │       → owner_email = this instructor's email
    │       → chat_visibility_enabled = true/false
    └── Redirect instructor to the INSTRUCTOR DASHBOARD (Phase 3)
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
Is chat_visibility_enabled AND student has NOT given consent?
    │
    ├── YES → Show CONSENT PAGE (see §4a)
    │           Student reads notice → clicks [Accept] → consent_given_at set
    │           → continue below
    │
    └── NO (visibility off, or already consented) → continue below
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

### Phase 2a: Student Consent Flow (when chat_visibility is enabled)

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  🐑 LAMB — PHY101 AI Assistants                         │
│                                                          │
│  Before you begin, please note:                          │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  ℹ  Your instructor has enabled chat transcript    │  │
│  │     review for this activity.                      │  │
│  │                                                    │  │
│  │  • Your conversations with the AI assistants may   │  │
│  │    be reviewed by your instructor for educational  │  │
│  │    purposes.                                       │  │
│  │                                                    │  │
│  │  • All transcripts are ANONYMIZED — your name and  │  │
│  │    identity are not visible to the instructor.     │  │
│  │                                                    │  │
│  │  • This helps your instructor understand how the   │  │
│  │    AI tools are being used and improve the course. │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  By clicking "I Understand & Continue", you acknowledge  │
│  this and agree to proceed.                              │
│                                                          │
│              [ I Understand & Continue ]                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Key rules:**
- Consent page is shown **only once** per student per activity (recorded in `lti_activity_users.consent_given_at`)
- If the student does not accept, they cannot proceed (no dismiss/skip)
- If `chat_visibility_enabled` is `false`, this page is never shown
- If the owner disables chat_visibility later, existing consents are kept but the page stops appearing for new students

### Phase 3: Instructor Returns → Instructor Dashboard

When **any** instructor (owner or not) clicks the LTI link for a configured activity:

```
Instructor clicks LTI link
    │
    ▼
lti_activity exists for "abc123" → CONFIGURED
    │
    ▼
LTI roles contain "Instructor"
    │
    ▼
Generate dashboard JWT token (short-lived, 30 min)
    │
    ▼
Redirect to GET /lamb/v1/lti/dashboard?resource_link_id=abc123&token={jwt}
    │
    ▼
INSTRUCTOR DASHBOARD (see §4b for full design)
    │
    ├── View activity stats & student access
    ├── View anonymized chat transcripts (if chat_visibility enabled)
    ├── [Open Chat] → creates OWI user + token → redirects to OWI
    └── [Manage Assistants] → (OWNER ONLY) → reconfigure assistant selection
```

### Phase 3a: Instructor Dashboard Design

See full design in **§10b** below.

### Phase 4: Owner Reconfigures Assistants

Only the **owner** can add/remove assistants. This is accessed from the dashboard.

```
Owner clicks [Manage Assistants] on dashboard
    │
    ▼
GET /lamb/v1/lti/setup?resource_link_id=abc123&token={jwt}&reconfigure=true
    │
    ▼
Setup page loads with current assistant selection pre-checked
    │
    ▼
Owner modifies selection, clicks [Save Changes]
    │
    ▼
POST /lamb/v1/lti/reconfigure
    │
    ├── Remove activity group from de-selected assistant models
    ├── Add activity group to newly-selected assistant models
    ├── Update lti_activity_assistants records
    └── Redirect back to dashboard
```

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
    owner_email TEXT NOT NULL,             -- Creator user email of the OWNER (first instructor)
    owner_name TEXT,                        -- Owner display name
    configured_by_email TEXT NOT NULL,      -- (legacy alias, same as owner_email on creation)
    configured_by_name TEXT,                -- Display name
    chat_visibility_enabled INTEGER NOT NULL DEFAULT 0,  -- 0=off, 1=on (instructors can view anonymized chats)
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'disabled'
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE UNIQUE INDEX idx_lti_activities_resource_link ON lti_activities(resource_link_id);
CREATE INDEX idx_lti_activities_org ON lti_activities(organization_id);
```

**New fields vs. v1:**
- `owner_email` / `owner_name` — the instructor who first configured the activity; only this person can manage assistant selection
- `chat_visibility_enabled` — opt-in flag set at creation time; controls whether instructors can view anonymized chat transcripts and whether students see a consent page

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
    user_display_name TEXT NOT NULL DEFAULT '',
    lms_user_id TEXT,                      -- Original user_id from LMS
    owi_user_id TEXT,                       -- OWI user UUID (for chat queries)
    consent_given_at INTEGER,              -- Timestamp when student accepted chat visibility notice (NULL = not yet)
    last_access_at INTEGER,                -- Last time the student accessed the activity
    access_count INTEGER NOT NULL DEFAULT 0, -- Number of times the student launched the activity
    created_at INTEGER NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES lti_activities(id) ON DELETE CASCADE,
    UNIQUE(user_email, activity_id)
);
```

**New fields vs. v1:**
- `owi_user_id` — OWI user UUID; needed to query chats for this student from the OWI database
- `consent_given_at` — when the student accepted the chat visibility notice; NULL means not yet accepted (or not required if `chat_visibility_enabled` is off)
- `last_access_at` — updated on every launch; used for dashboard "last seen" column
- `access_count` — incremented on every launch; used for dashboard stats

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
    "chat_visibility_enabled": true,
    "context_id": "course_456",
    "context_title": "Introduction to Physics"
}
```

**Processing:**
1. Validate instructor token
2. Verify all `assistant_ids` are published and accessible to this instructor
3. Create OWI group: `lti_activity_{resource_link_id}`
4. For each assistant: `owi_model.add_group_to_model("lamb_assistant.{id}", group_id, "read")`
5. Insert `lti_activities` record with `owner_email` = this instructor, `chat_visibility_enabled` = flag
6. Insert `lti_activity_assistants` records
7. Redirect instructor to the **Instructor Dashboard** (not directly to OWI)

### 7.5 Admin: Manage Global LTI Config

```
GET  /creator/admin/lti-global-config     → Current credentials (masked secret)
PUT  /creator/admin/lti-global-config     → Update credentials
```

Only accessible by system admins. Updates `lti_global_config` table.

### 7.6 Instructor Dashboard

```
GET /lamb/v1/lti/dashboard?resource_link_id={id}&token={jwt}
```

Serves the instructor dashboard HTML page. The page makes AJAX calls to the data endpoints below.

**Who can access:** Any user who arrives via LTI with an `Instructor` role for this `resource_link_id`.

### 7.7 Dashboard Data API (JSON)

All require the dashboard JWT token. Served as JSON for AJAX consumption.

```
GET /lamb/v1/lti/dashboard/stats?resource_link_id={id}&token={jwt}
```
Returns: `{ total_students, total_chats, total_messages, active_last_7d, assistants: [...] }`

```
GET /lamb/v1/lti/dashboard/students?resource_link_id={id}&token={jwt}
```
Returns: `[ { anonymous_id, first_access, last_access, access_count, chat_count, message_count }, ... ]`

- Students are listed with sequential anonymous IDs ("Student 1", "Student 2", ...) by order of first access.
- Real names/emails are **never** exposed to the dashboard — even the owner sees anonymous IDs.

```
GET /lamb/v1/lti/dashboard/chats?resource_link_id={id}&token={jwt}&page=1&per_page=20
```
Returns: `[ { chat_id, anonymous_student_id, assistant_name, title, message_count, created_at, updated_at }, ... ]`

- **Only available if `chat_visibility_enabled = true`** — returns 403 otherwise.
- Student identities are anonymized using consistent pseudonyms.
- Filterable by assistant: `&assistant_id=42`

```
GET /lamb/v1/lti/dashboard/chats/{chat_id}?token={jwt}
```
Returns: `{ chat_id, anonymous_student_id, assistant_name, messages: [ { role, content, timestamp }, ... ] }`

- Returns the full chat transcript with anonymized student identity.
- **Only available if `chat_visibility_enabled = true`.**

### 7.8 Student Consent

```
POST /lamb/v1/lti/consent
Content-Type: application/json
Authorization: Bearer {token}

{
    "resource_link_id": "abc123"
}
```

Records the student's consent to chat visibility. Sets `lti_activity_users.consent_given_at` to now.
After consent, redirects to OWI.

### 7.9 Instructor → OWI (Chat Button)

```
GET /lamb/v1/lti/enter-chat?resource_link_id={id}&token={jwt}
```

Called when instructor clicks "Open Chat" on the dashboard. Creates/gets OWI user for the instructor, adds them to the activity group, generates OWI token, and redirects to OWI.

### 7.10 Reconfigure Activity (Owner Only)

```
GET  /lamb/v1/lti/setup?resource_link_id={id}&token={jwt}&reconfigure=true
POST /lamb/v1/lti/reconfigure
```

Allows the **owner** to change the assistant selection for an existing activity:
1. Verify requester is the owner (`owner_email` matches)
2. Load current selection
3. Show picker with current state
4. On save: remove activity group from de-selected models, add to newly selected models
5. Can also toggle `chat_visibility_enabled`

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

**Step 2 — Assistant Selection & Options:**

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
│  ─────────────────────────────────────────────     │
│  Options:                                          │
│                                                    │
│  ☑ Allow instructors to review anonymized chat     │
│    transcripts                                     │
│    Students will be notified and must accept       │
│    before using the tool.                          │
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

## 10b. Instructor Dashboard (Backend-Served Page)

### Design Rationale

Like the setup page, the dashboard is a **self-contained HTML page** served by the backend. This keeps it independent of the Svelte SPA and allows it to work within the LTI iframe context that many LMS platforms use.

The page loads initial data server-side and uses lightweight AJAX calls for dynamic sections (chat list, pagination).

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  🐑 LAMB — PHY101 AI Assistants                    [Open Chat ▶]  │
│  Course: Introduction to Physics │ Physics Department              │
│  Owner: prof@uni.edu │ Created: Jan 15, 2026                       │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  👥 Students │  │  💬 Chats   │  │  📨 Messages│  │ 📊 Active │ │
│  │     42       │  │    156      │  │    1,284    │  │  18 / 7d  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════    │
│                                                                     │
│  ASSISTANTS                                    [Manage ✏] (owner)  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ● Physics Tutor         12 chats │ 98 messages │ active    │   │
│  │  ● Lab Report Helper      8 chats │ 64 messages │ active    │   │
│  │  ○ Essay Reviewer         0 chats │  0 messages │ removed   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════    │
│                                                                     │
│  STUDENT ACCESS LOG                                                │
│  ┌───────────────┬──────────────┬──────────────┬────────┬───────┐  │
│  │ Student       │ First Access │ Last Access  │ Visits │ Chats │  │
│  ├───────────────┼──────────────┼──────────────┼────────┼───────┤  │
│  │ Student 1     │ Jan 16 09:14 │ Feb 5 14:22  │   12   │   4   │  │
│  │ Student 2     │ Jan 16 09:15 │ Feb 6 08:01  │    9   │   3   │  │
│  │ Student 3     │ Jan 16 10:30 │ Feb 4 16:45  │    7   │   5   │  │
│  │ ...           │              │              │        │       │  │
│  ├───────────────┴──────────────┴──────────────┴────────┴───────┤  │
│  │                    ← Page 1 of 3 →                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════    │
│                                                                     │
│  CHAT TRANSCRIPTS (anonymized)               🔒 Chat visibility ON │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Filter: [All Assistants ▼]  Sort: [Most Recent ▼]          │  │
│  │                                                              │  │
│  │  📄 "Help with Newton's Third Law"                           │  │
│  │     Student 1 → Physics Tutor │ 8 messages │ Feb 5 14:22    │  │
│  │     ▸ Click to expand transcript                             │  │
│  │                                                              │  │
│  │  📄 "Lab report formatting question"                         │  │
│  │     Student 3 → Lab Report Helper │ 12 messages │ Feb 4     │  │
│  │     ▸ Click to expand transcript                             │  │
│  │                                                              │  │
│  │  📄 "Momentum conservation problem"                          │  │
│  │     Student 2 → Physics Tutor │ 6 messages │ Feb 3          │  │
│  │     ▸ Click to expand transcript                             │  │
│  │                                                              │  │
│  │                    ← Page 1 of 8 →                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Expanded transcript: "Help with Newton's Third Law"        │  │
│  │  Student 1 → Physics Tutor │ Feb 5, 2026 14:22              │  │
│  │                                                              │  │
│  │  Student 1:  Can you explain Newton's third law with a      │  │
│  │              real-world example?                              │  │
│  │                                                              │  │
│  │  Physics Tutor:  Newton's Third Law states that for every   │  │
│  │              action, there is an equal and opposite          │  │
│  │              reaction. For example, when you push against    │  │
│  │              a wall...                                       │  │
│  │                                                              │  │
│  │  Student 1:  So when I jump, I push the Earth down?         │  │
│  │                                                              │  │
│  │  Physics Tutor:  Exactly! When you jump, your feet push     │  │
│  │              down on the Earth with a force, and the Earth   │  │
│  │              pushes back up on you with an equal force...    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Dashboard Sections Explained

#### 1. Header Bar
- Activity name, course, organization
- Owner name and creation date
- **[Open Chat]** button — always visible to all instructors. Creates/gets OWI user for the instructor, adds to activity group, redirects to OWI.

#### 2. Summary Stats (Cards)
- **Students** — count of unique students who have accessed
- **Chats** — total chat sessions across all assistants in this activity
- **Messages** — total messages (student + assistant)
- **Active (7d)** — students who accessed in the last 7 days

Data source: `lti_activity_users` table + OWI `chat` table (via `ChatAnalyticsService` pattern)

#### 3. Assistants Section
- Lists all configured assistants with per-assistant chat/message counts
- Shows status (active = published & in activity, removed = unpublished or removed from activity)
- **[Manage]** button — **only visible to the owner** (`owner_email`). Links to the reconfigure page.

#### 4. Student Access Log
- Paginated table of students who have accessed
- **Always anonymized**: "Student 1", "Student 2", etc. (by order of `created_at`)
- Columns: Anonymous ID, First Access, Last Access, Visit Count, Chat Count
- Data source: `lti_activity_users` table + OWI chat count per user

#### 5. Chat Transcripts (conditional)
- **Only shown if `chat_visibility_enabled = true`**
- If disabled: section replaced with a note: "Chat transcript review is not enabled for this activity."
- Filterable by assistant
- Sortable by date (most recent first)
- Each chat shows: title, anonymized student ID, assistant name, message count, date
- **Expandable**: click to reveal the full transcript inline
- All student messages show the anonymized ID, never the real name

### Anonymization Strategy

The dashboard **never reveals real student identities** to instructors:

| Data point | What instructors see | Source |
|------------|---------------------|--------|
| Student name | "Student 1", "Student 2", ... | Sequential by `created_at` in `lti_activity_users` |
| Student email | Never shown | — |
| Chat author | Same anonymized ID | Mapped via `owi_user_id` → `lti_activity_users` → sequential number |
| Chat content | Full text, no redaction | OWI `chat` table |
| Assistant responses | Full text, attributed to assistant name | OWI `chat` table |

**Consistency**: The same student always maps to the same "Student N" within an activity. The mapping is deterministic (based on `created_at` ordering), so it's stable across dashboard visits.

### Implementation Details

- **Template**: `lamb/templates/lti_dashboard.html`
- **Stack**: Self-contained HTML + TailwindCSS CDN + vanilla JS
- **Data loading**: Initial stats rendered server-side; chat list and transcripts loaded via AJAX (`fetch()`)
- **JWT token**: Passed as query param, also stored in a JS variable for AJAX calls
- **Chat data**: Queried from OWI SQLite via `OwiDatabaseManager` (same pattern as `ChatAnalyticsService`)
  - Filter chats by: models matching `lamb_assistant.{ids}` AND user_id matching OWI users in the activity group
- **Pagination**: Server-side pagination for student list and chat list (20 per page default)

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
│   ├── POST /launch                 ← Entry point (routes to setup, dashboard, or student flow)
│   ├── GET  /setup                  ← Setup page (first-time or reconfigure)
│   ├── POST /configure              ← Save activity config (sets owner)
│   ├── POST /reconfigure            ← Update activity config (owner only)
│   ├── POST /link-account           ← Instructor identity linking
│   ├── GET  /dashboard              ← Instructor dashboard page
│   ├── GET  /dashboard/stats        ← Dashboard stats JSON
│   ├── GET  /dashboard/students     ← Dashboard student list JSON
│   ├── GET  /dashboard/chats        ← Dashboard chat list JSON (if chat_visibility)
│   ├── GET  /dashboard/chats/{id}   ← Chat transcript JSON (if chat_visibility)
│   ├── POST /consent                ← Student accepts chat visibility notice
│   └── GET  /enter-chat             ← Instructor → OWI redirect
│
├── lti_activity_manager.py          ← NEW: Activity business logic
│   ├── get_lti_credentials()
│   ├── get_or_create_activity()
│   ├── get_published_assistants_for_instructor()
│   ├── configure_activity()         ← Sets owner + chat_visibility
│   ├── handle_student_launch()      ← Includes consent check
│   ├── identify_instructor()
│   ├── get_dashboard_stats()        ← Aggregates from LAMB DB + OWI DB
│   ├── get_dashboard_students()     ← With anonymization mapping
│   ├── get_dashboard_chats()        ← Via OWI ChatAnalyticsService pattern
│   └── record_student_consent()
│
├── templates/
│   ├── lti_activity_setup.html      ← NEW: Setup page (with chat_visibility checkbox)
│   ├── lti_dashboard.html           ← NEW: Instructor dashboard
│   ├── lti_consent.html             ← NEW: Student consent page
│   ├── lti_link_account.html        ← NEW: Account linking form
│   └── lti_waiting.html             ← NEW: "Not set up yet" page
│
├── database_manager.py              ← MODIFIED: New table operations
│   ├── create_lti_activity()        ← Now with owner_email, chat_visibility_enabled
│   ├── get_lti_activity_by_resource_link()
│   ├── get_lti_activities_by_org()
│   ├── update_lti_activity()        ← Now supports chat_visibility_enabled toggle
│   ├── add_assistants_to_activity()
│   ├── remove_assistants_from_activity()
│   ├── get_activity_assistants()
│   ├── create_lti_activity_user()   ← Now with owi_user_id, consent tracking
│   ├── update_lti_activity_user_access()  ← Updates last_access_at, access_count
│   ├── record_student_consent()     ← Sets consent_given_at
│   ├── get_activity_students()      ← Paginated, for dashboard
│   ├── get_lti_global_config()
│   ├── set_lti_global_config()
│   ├── create_lti_identity_link()
│   ├── get_creator_user_by_lms_identity()
│   └── get_published_assistants_for_org_user()
│
├── main.py                          ← MODIFIED: Mount new router
│   └── app.include_router(lti_router, prefix="/v1/lti")
│
creator_interface/
└── organization_router.py           ← MODIFIED: Add org-admin LTI activity management
    ├── GET  /admin/lti-activities                → List activities in org
    ├── GET  /admin/lti-activities/{id}           → Activity detail + assistants
    ├── PUT  /admin/lti-activities/{id}           → Reconfigure/disable/transfer ownership
    ├── GET  /admin/lti-global-config             → View global LTI credentials
    └── PUT  /admin/lti-global-config             → Update global LTI credentials
```

---

## 13. Resolved Design Questions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | Student identity scope | **Per `resource_link_id`** | Safest isolation; each LTI placement = separate identity |
| Q2 | Unpublished assistants | **OWI handles naturally** | Model disappears from chat UI; stale activity records cleaned on reconfigure |
| Q3 | Instructor after setup | **Redirect to Instructor Dashboard** (v2) | Instructors need to monitor usage, not just chat |
| Q4 | Reconfiguration access | **Owner only** for assistant management; any instructor sees the dashboard; org admins can manage all activities | Clear ownership model |
| Q5 | Keep old Student LTI? | **Yes** | Coexistence; institutions migrate at own pace |
| Q6 | Multi-org instructors | **Must choose one org per activity** | No mixing assistants across orgs; activity is bound to `organization_id` |
| Q7 | Who is the "owner"? | **The first instructor who configures the activity** | Simple, deterministic; org admins can transfer ownership if needed |
| Q8 | Chat visibility | **Opt-in per activity, set at creation time** | Respects student privacy by default; owner makes explicit choice |
| Q9 | Student anonymization | **Always anonymized on the dashboard** — even for the owner | Students should feel comfortable being honest with AI. Instructor sees "Student 1", "Student 2", never real names |
| Q10 | Chat visibility consent | **Required, one-time, per student per activity** | Students must be informed; consent stored in DB; shown only on first access |
| Q11 | Can chat_visibility be toggled after creation? | **Owner can toggle it via reconfigure** | Turning it ON later triggers consent for students who haven't consented yet. Turning it OFF hides the chat section from the dashboard. |
| Q12 | Non-owner instructors | **See the same dashboard (read-only)** | Teaching teams can monitor usage; only assistant management is restricted to owner |

---

## 14. Implementation Order

### Phase A — Core (already implemented in v1)
1. ~~Database migrations — New tables~~  ✅
2. ~~Admin config endpoint — GET/PUT `/creator/admin/lti-global-config`~~  ✅
3. ~~Main launch endpoint — POST `/v1/lti/launch` with OAuth validation and routing~~  ✅
4. ~~Instructor identification — Email matching + identity linking~~  ✅
5. ~~Setup page — Template + published assistant query~~  ✅
6. ~~Configure endpoint — Activity creation + OWI group/model wiring~~  ✅
7. ~~Student launch flow — User creation + group add + redirect~~  ✅
8. ~~Admin UI — LTI Settings tab, Org-admin LTI Activities tab~~  ✅

### Phase B — Dashboard & Chat Visibility (v2, this design)
9. **DB schema update** — Add `owner_email`, `chat_visibility_enabled` to `lti_activities`; add `owi_user_id`, `consent_given_at`, `last_access_at`, `access_count` to `lti_activity_users`
10. **Setup page update** — Add chat visibility checkbox; record `owner_email` on configure
11. **Student consent page** — New template + POST `/v1/lti/consent` endpoint
12. **Student launch update** — Check consent requirement before OWI redirect; update `last_access_at`/`access_count`
13. **Instructor dashboard page** — Template + server-rendered initial data
14. **Dashboard data API** — Stats, students, chats endpoints (JSON)
15. **Chat query service** — Query OWI chats filtered by activity's assistant models + user IDs
16. **Anonymization layer** — Consistent "Student N" mapping based on `created_at` ordering
17. **Launch routing update** — Instructors on configured activities → dashboard (not OWI)
18. **Enter-chat endpoint** — Instructor dashboard → OWI redirect
19. **Reconfiguration update** — Owner-only check + chat_visibility toggle
20. **Tests** — Unit tests for dashboard, consent flow, anonymization; E2E with Playwright

---

## 15. Security & Privacy Considerations

- **OAuth replay protection:** Consider adding nonce/timestamp validation (currently missing in all LTI paths)
- **Setup token:** Short-lived JWT (5 min) for the setup page, prevents unauthorized configuration
- **Dashboard token:** Short-lived JWT (30 min) for the dashboard; contains `resource_link_id`, instructor identity, and `is_owner` flag
- **Identity linking:** Rate-limit the login form to prevent brute force
- **Resource_link_id trust:** This value comes from the LMS via signed OAuth — trustworthy as long as signature is valid
- **Global secret rotation:** When admin changes the secret, existing LMS tools need updating. Consider a "rotation period" where both old and new secrets are valid
- **Anonymization integrity:** The "Student N" mapping is derived from `created_at` ordering — deterministic and consistent, but **no reverse lookup is exposed** via any API endpoint. Even the owner cannot de-anonymize.
- **Chat visibility consent:** Consent is recorded per-student per-activity with a timestamp. The student cannot use the tool without consenting (when enabled). This satisfies informed consent principles.
- **Chat data access:** Dashboard chat endpoints check both (a) the requesting token belongs to an instructor for this activity, and (b) `chat_visibility_enabled` is true. No chat data is ever returned if the flag is false — not even to the owner.
- **Owner privilege scope:** The owner can manage assistants and toggle chat visibility, but **cannot** see real student identities. Ownership transfer is only possible via the org-admin panel.
