# LAMB LTI Landscape

**Version:** 2.0  
**Last Updated:** February 6, 2026  
**Reading Time:** ~30 minutes

> This document provides a comprehensive overview of how LAMB integrates with Learning Management Systems (LMS) through LTI. It is split into two parts: a **non-technical overview** for educators, administrators, and project stakeholders, followed by a **technical deep-dive** for developers working on the codebase.

---

## Table of Contents

### Part 1 — Non-Technical Overview
1. [What is LTI and Why Does LAMB Use It?](#1-what-is-lti-and-why-does-lamb-use-it)
2. [The Three LTI Paths](#2-the-three-lti-paths)
3. [Unified LTI: The Recommended Approach (NEW)](#3-unified-lti-the-recommended-approach-new)
4. [Legacy Student LTI: Accessing a Single AI Assistant](#4-legacy-student-lti-accessing-a-single-ai-assistant)
5. [Creator LTI: Building AI Assistants from the LMS](#5-creator-lti-building-ai-assistants-from-the-lms)
6. [How Students Are Kept Isolated](#6-how-students-are-kept-isolated)
7. [The Confusing Parts (Honestly)](#7-the-confusing-parts-honestly)
8. [Summary: Which LTI Tool Does What?](#8-summary-which-lti-tool-does-what)

### Part 2 — Technical Deep-Dive
9. [Architecture Overview](#9-architecture-overview)
10. [Unified LTI: Code Walkthrough (NEW)](#10-unified-lti-code-walkthrough-new)
11. [Legacy Student LTI: Code Walkthrough](#11-legacy-student-lti-code-walkthrough)
12. [Creator LTI: Code Walkthrough](#12-creator-lti-code-walkthrough)
13. [Database Schema](#13-database-schema)
14. [OAuth 1.0 Signature Validation](#14-oauth-10-signature-validation)
15. [OWI Bridge Integration](#15-owi-bridge-integration)
16. [Publishing: How Activities Are Born](#16-publishing-how-activities-are-born)
17. [Key Files Reference](#17-key-files-reference)
18. [Design Decisions and Trade-offs](#18-design-decisions-and-trade-offs)
19. [Known Limitations and Future Directions](#19-known-limitations-and-future-directions)

---

# Part 1 — Non-Technical Overview

## 1. What is LTI and Why Does LAMB Use It?

**LTI** (Learning Tools Interoperability) is a standard created by IMS Global that allows external tools to be embedded inside a Learning Management System (LMS) like Canvas, Moodle, or Blackboard. When a student or instructor clicks an LTI activity in their course, the LMS securely sends them to the external tool — in our case, LAMB.

LAMB uses **LTI 1.1** (OAuth 1.0-based), which is supported by essentially every LMS on the market. This means:

- **No separate accounts needed** — Users authenticate through their LMS
- **Seamless experience** — One click takes users directly where they need to go
- **Institutional trust** — The LMS vouches for the user's identity
- **Automatic provisioning** — LAMB creates users on-the-fly when they first arrive

---

## 2. The Three LTI Paths

LAMB has **three LTI integrations** that serve different audiences and purposes. The **Unified LTI** (new in v2) is the recommended approach going forward, while the legacy Student LTI and Creator LTI remain supported.

![LAMB LTI Integration: Three Paths, One Platform](lti_landscape_overview.png)

| | Unified LTI (NEW) | Legacy Student LTI | Creator LTI |
|---|---|---|---|
| **Who uses it?** | Instructors + Students | Students only | Instructors/Educators |
| **What does it do?** | Multi-assistant AI tool with instructor dashboard | Opens a chat with a specific AI assistant | Opens the Creator Interface to build assistants |
| **Where do they land?** | Instructors: Dashboard; Students: Open WebUI | Open WebUI (chat interface) | LAMB Creator Interface (Svelte frontend) |
| **Endpoint** | `POST /lamb/v1/lti/launch` | `POST /lamb/v1/lti_users/lti` | `POST /lamb/v1/lti_creator/launch` |
| **Consumer key tied to** | Global LAMB instance | A specific published assistant | An entire organization |
| **Shared secret stored in** | Global config (DB or `.env`) | Global `LTI_SECRET` env var | Per-organization in database |
| **Assistants per activity** | Multiple (instructor's choice) | 1 | N/A (creation tool) |

Think of it this way:
- **Unified LTI** = "Use AI assistants in my course" (recommended, multi-assistant, with analytics)
- **Legacy Student LTI** = "Use this one AI assistant" (simple, single-assistant)
- **Creator LTI** = "Build AI assistants" (creation)

---

## 3. Unified LTI: The Recommended Approach (NEW)

### The Story

A university wants to give students access to AI assistants directly within their LMS course. Previously, each assistant required its own LTI activity. With the new Unified LTI, an instructor configures **one LTI link** in their course, selects which assistants to include, and students get access to all of them. The instructor also gets a **dashboard** showing usage analytics, student access logs, and optionally anonymized chat transcripts.

### The Flow (Human-Readable)

**First Time — Instructor Setup:**

1. **Instructor clicks** the "AI Assistants" LTI link in their LMS course
2. **LMS signs** the request and sends it to LAMB
3. **LAMB validates** the signature using the global LTI key/secret
4. **No activity configured yet** for this LTI placement → Setup mode
5. **LAMB identifies the instructor** as a Creator user (by email, LTI user ID, or manual account linking)
6. **Instructor sees a setup page** with checkboxes for published assistants, an option to enable chat transcript review, and an activity name field
7. **This instructor becomes the OWNER** of the activity
8. **After saving**, the instructor is redirected to the **Instructor Dashboard**

**Subsequent Visits — Instructor Dashboard:**

1. **Any instructor** clicks the same LTI link
2. **LAMB recognizes** the activity is configured and the user is an instructor
3. **Instructor sees the Dashboard** showing:
   - Summary stats (students, chats, messages, active users)
   - Configured assistants with per-assistant stats
   - Anonymized student access log
   - Anonymized chat transcripts (if chat visibility was enabled)
   - An "Open Chat" button to use the assistants themselves
4. **Only the owner** sees a "Manage Assistants" button to add/remove assistants

**Student Launch:**

1. **Student clicks** the same LTI link
2. **If chat visibility is enabled** and this is their first visit, they see a **consent notice** explaining that transcripts may be reviewed anonymously by the instructor. They must accept to continue.
3. **LAMB creates/retrieves** an OWI account with a synthetic email based on `resource_link_id`
4. **Student lands in Open WebUI** seeing all selected assistants (e.g., Physics Tutor, Lab Helper)

### Key Design Choices

**Activity Ownership:** The first instructor to configure the activity becomes its owner. Only the owner can manage the assistant selection. Any instructor can view the dashboard. Organization admins can transfer ownership if needed.

**Chat Visibility (Opt-in):** At setup time, the owner decides whether instructors can view anonymized chat transcripts. If enabled:
- Students are informed on first access and must consent
- All chat transcripts on the dashboard show "Student 1", "Student 2", etc. — never real names
- The anonymization is consistent (same student always maps to the same pseudonym)

**Multi-Assistant Activities:** Unlike legacy Student LTI (one assistant per LTI link), a single Unified LTI activity can expose multiple assistants. All students in the activity share one OWI group that grants access to all selected assistant models.

**One Identity Per Activity:** Students get a synthetic email per `resource_link_id`, not per assistant. This means one OWI account per LTI placement, with access to all that activity's assistants.

---

## 4. Legacy Student LTI: Accessing a Single AI Assistant

### The Story

An instructor has created an AI assistant in LAMB (say, "Physics Tutor for PHY101"). They publish it, which generates LTI credentials. They paste those credentials into their LMS as a new external tool activity. Now, when a student clicks that activity in Canvas/Moodle/Blackboard, they're whisked directly into a chat with the Physics Tutor.

### The Flow (Human-Readable)

1. **Student clicks** the "Physics Tutor" activity in their LMS course
2. **LMS signs** the request with OAuth 1.0 and sends it to LAMB
3. **LAMB validates** the signature (proves the LMS is legitimate)
4. **LAMB generates a private email** for this student — combining their username with the assistant name (e.g., `jsmith-PhysicsTutor@lamb-project.org`)
5. **If first visit:** LAMB creates an Open WebUI account for them and adds them to the Physics Tutor's access group
6. **If returning:** LAMB finds their existing account
7. **LAMB generates a session token** and redirects the student to Open WebUI
8. **Student lands in the chat interface**, seeing only the Physics Tutor assistant

### Key Design Choice: Privacy Through Generated Emails

LAMB deliberately does **not** use students' real email addresses. Instead, it generates a synthetic email from their username and the assistant they're accessing. This means:

- The student's real institutional email is never stored in Open WebUI
- A student accessing two different assistants gets two separate identities
- There's no way for students to see chats from other courses

---

## 5. Creator LTI: Building AI Assistants from the LMS

### The Story

A university wants its instructors to create AI assistants without needing separate LAMB accounts. The university admin configures one LTI activity in the LMS that points to LAMB's Creator Interface. When instructors click it, they land in the assistant creation tool, ready to build.

### The Flow (Human-Readable)

1. **Instructor clicks** the "LAMB Creator" activity in their LMS
2. **LMS signs** the request with the organization's OAuth credentials
3. **LAMB validates** the signature and identifies which organization this belongs to
4. **LAMB identifies the user** by their stable LMS `user_id` (not email!)
5. **If first visit:** LAMB creates a "creator" account with a generated email (e.g., `lti_creator_engineering_jsmith123@lamb-lti.local`)
6. **If returning:** LAMB finds the existing account
7. **LAMB generates a session token** and redirects to the Creator Interface with the token in the URL
8. **The Svelte frontend** picks up the token, stores it, and authenticates the instructor
9. **Instructor can now create, edit, publish, and manage AI assistants**

### Key Design Choice: One Instructor, Multiple Organizations

Because creators are identified by `organization_id + lti_user_id`, the same instructor can belong to multiple LAMB organizations. If they're in both the Engineering and Physics departments (each with their own LAMB organization), they get separate creator accounts — each scoped to its organization's resources and settings. This is admittedly confusing but provides clean isolation.

---

## 6. How Students Are Kept Isolated

This is one of LAMB's most important privacy features. When a student accesses an assistant via LTI, they get a **synthetic identity** that prevents cross-activity data leakage.

![Student Identity Isolation per Activity](lti_identity_isolation.png)

### Legacy Student LTI — Per-Assistant Isolation

**The email formula:**
```
{lms_username}-{assistant_oauth_consumer_name}@lamb-project.org
```

**Example:** Maria Garcia accesses two legacy LTI assistants:
- Physics Tutor → `mgarcia-PhysicsTutor@lamb-project.org`
- History Essay Helper → `mgarcia-HistoryEssayHelper@lamb-project.org`

These are **two completely separate Open WebUI accounts**. Maria's Physics chats are invisible from the History assistant and vice versa. Each identity belongs to only one OWI group, which only grants access to one assistant.

### Unified LTI — Per-Activity Isolation (NEW)

**The email formula:**
```
{lms_username}_{resource_link_id}@lamb-lti.local
```

**Example:** Maria Garcia accesses two Unified LTI activities:
- PHY101 AI Assistants (resource_link_id = `abc123`) → `mgarcia_abc123@lamb-lti.local`
- HIST200 Research Tools (resource_link_id = `def456`) → `mgarcia_def456@lamb-lti.local`

Again, these are **separate Open WebUI accounts**. Within each activity, Maria can see all selected assistants (e.g., both Physics Tutor and Lab Helper in PHY101), but her chats from one activity are invisible from the other.

**Key difference:** In Unified LTI, one identity grants access to **multiple assistants** within an activity, while legacy Student LTI creates a separate identity per assistant.

---

## 7. The Confusing Parts (Honestly)

Let's acknowledge the quirks:

### 7.1 The Shared Secret Asymmetry

- **Unified LTI** uses a global key/secret configurable via the admin UI (stored in `lti_global_config` table, or falls back to env vars). One key/secret for the entire LAMB instance.
- **Legacy Student LTI** uses a single global `LTI_SECRET` environment variable for all assistants. Every published assistant shares the same secret.
- **Creator LTI** stores per-organization secrets in the database (`lti_creator_keys` table). Each organization has its own key/secret pair.

This means both Unified and legacy Student LTI security rely on a single secret for the entire instance, while Creator LTI has proper per-tenant isolation. The Unified LTI improves on the legacy approach by allowing the admin to change the secret via the UI (with the DB value taking precedence over env vars).

### 7.2 "Consumer Key" Means Different Things

- In **Unified LTI**, the `oauth_consumer_key` is a **global key** for the entire LAMB instance. It identifies LAMB itself, not a specific assistant or organization. The `resource_link_id` parameter identifies the specific activity placement.
- In **Legacy Student LTI**, the `oauth_consumer_key` is the **assistant's name** (the `oauth_consumer_name` from publishing). It identifies *which assistant* the student wants.
- In **Creator LTI**, the `oauth_consumer_key` identifies *which organization* the instructor belongs to.

Same OAuth parameter, three completely different semantics.

### 7.3 Creator LTI Users Are "Creators" But With Some Differences

LTI creator users get `user_type = 'creator'` and can do almost everything a regular creator can: build assistants, create knowledge bases, publish, share. Their password is a random string they'll never see (they always enter through LTI). They are created as `member` by default, but a **system admin can promote them to organization admin** via the Members panel in the system admin interface.

### 7.4 Four Endpoints, Three Active

There are four LTI-related routing paths in the codebase:

| Endpoint | Status | Purpose |
|---|---|---|
| `POST /lamb/v1/lti/launch` | **Active (NEW)** | Unified LTI launch (recommended) |
| `POST /lamb/v1/lti_users/lti` | **Active (Legacy)** | Legacy Student LTI launch |
| `POST /lamb/v1/lti_creator/launch` | **Active** | Creator LTI launch |
| `POST /lamb/simple_lti/launch` | **Stub** | Placeholder, not fully implemented |

The **Unified LTI** (`/v1/lti/launch`) is the recommended approach for new deployments. It supports multiple assistants per activity, instructor dashboards, and chat analytics. The legacy Student LTI remains for backward compatibility.

The `simple_lti` router exists as a skeleton but doesn't actually process LTI launches — it returns a generic JSON response.

---

## 8. Summary: Which LTI Tool Does What?

| Aspect | Unified LTI (`/v1/lti/launch`) | Legacy Student LTI (`/v1/lti_users/lti`) | Creator LTI (`/v1/lti_creator/launch`) |
|---|---|---|---|
| **Purpose** | Multi-assistant activities with dashboard | Students chat with one published assistant | Instructors build and manage assistants |
| **Destination** | Instructors: Dashboard; Students: OWI | Open WebUI chat interface | LAMB Creator Interface (Svelte SPA) |
| **Identity** | `{username}_{resource_link_id}@lamb-lti.local` | `{username}-{assistant_name}@lamb-project.org` | `lti_creator_{org}_{user_id}@lamb-lti.local` |
| **Consumer key** | Global configurable key | Published assistant name | Organization's configured key |
| **Shared secret** | Global (DB or `.env`) | Global `LTI_SECRET` env var | Per-org in `lti_creator_keys` table |
| **User type created** | OWI end-user (via activity group) | OWI end-user (via assistant group) | LAMB creator user (`auth_provider: lti_creator`) |
| **Per-assistant setup in LMS?** | No (one LTI link, instructor picks assistants) | Yes (one LTI activity per assistant) | No (one LTI activity for all of LAMB Creator) |
| **Instructor features** | Dashboard, analytics, chat visibility | None | Full Creator Interface |
| **Password** | Random/synthetic (never used) | Set to `assistant_id` (never used) | Random string (never used) |
| **Recommended for new deployments?** | **Yes** | Legacy — migrate when possible | Yes (for assistant creation) |

---

# Part 2 — Technical Deep-Dive

## 9. Architecture Overview

### 9.1 LTI in the LAMB Stack

All LTI paths are mounted inside the LAMB Core API (`/backend/lamb/main.py`):

```
LAMB Application (main.py)
│
├── /lamb/                          ← LAMB Core API
│   ├── /v1/lti/                    ← Unified LTI router (NEW — recommended)
│   │   ├── POST /launch            ← Main entry point (routes to setup, dashboard, or OWI)
│   │   ├── GET  /setup             ← Instructor setup page
│   │   ├── POST /configure         ← Save activity config (sets owner)
│   │   ├── POST /reconfigure       ← Update config (owner only)
│   │   ├── GET  /dashboard         ← Instructor dashboard
│   │   ├── GET  /dashboard/stats   ← Dashboard stats (JSON)
│   │   ├── GET  /dashboard/students ← Student list (JSON, anonymized)
│   │   ├── GET  /dashboard/chats   ← Chat list (JSON, anonymized)
│   │   ├── GET  /dashboard/chats/{id} ← Chat transcript (JSON, anonymized)
│   │   ├── GET  /consent           ← Student consent page
│   │   ├── POST /consent           ← Accept consent
│   │   ├── GET  /enter-chat        ← Instructor → OWI redirect
│   │   ├── GET  /link-account      ← Instructor identity linking
│   │   └── GET  /info              ← LTI configuration info
│   │
│   ├── /v1/lti_users/              ← Legacy Student LTI router
│   │   └── POST /lti               ← Student launch endpoint
│   │
│   ├── /v1/lti_creator/            ← Creator LTI router
│   │   ├── POST /launch            ← Creator launch endpoint
│   │   └── GET /info               ← Configuration info
│   │
│   └── /simple_lti/                ← Simple LTI (stub)
│       └── POST /launch            ← Not implemented
│
├── /creator/                       ← Creator Interface API
│   └── /assistant/{id}/publish     ← Publishing endpoint
│
└── OWI Bridge (internal)
    ├── owi_users.py                ← User creation & tokens
    ├── owi_group.py                ← Group management
    ├── owi_model.py                ← Model registration
    └── owi_database.py             ← Direct OWI DB access (for chat analytics)
```

### 9.2 Dependency Graph

```
                          ┌──────────────────┐
                          │       LMS        │
                          │ (Canvas/Moodle)  │
                          └──┬────┬─────┬────┘
                             │    │     │
           Unified LTI      │    │     │    Creator LTI
           (multi-assistant  │    │     │    (org-level
            + dashboard)     │    │     │     access)
                             │    │     │
               Legacy        │    │     │
               Student LTI   │    │     │
                             ▼    ▼     ▼
                          ┌──────────────────┐
                          │   LAMB Backend   │
                          │    (FastAPI)     │
                          └────┬────────┬────┘
                               │        │
                    ┌──────────┘        └──────────┐
                    │                               │
                    ▼                               ▼
           ┌──────────────┐                ┌──────────────┐
           │   LAMB DB    │                │   OWI DB     │
           │  (SQLite)    │                │  (SQLite)    │
           ├──────────────┤                ├──────────────┤
           │ lti_users    │                │ user         │
           │ assistant_   │                │ auth         │
           │   publish    │                │ group        │
           │ lti_creator_ │                │ model        │
           │   keys       │                │ chat ◄───────│── Dashboard reads
           │ Creator_users│                │              │   (anonymized)
           │──────────────│                └──────────────┘
           │ lti_global_  │                       │
           │   config     │◄── Unified LTI        ▼
           │ lti_activities│   tables       ┌──────────────┐
           │ lti_activity_ │               │  Open WebUI  │
           │   assistants  │               │  (Chat UI)   │
           │ lti_activity_ │               └──────────────┘
           │   users       │
           │ lti_identity_ │
           │   links       │
           └──────────────┘
```

---

## 10. Unified LTI: Code Walkthrough (NEW)

**Primary files:**
- `/backend/lamb/lti_router.py` — Route handlers
- `/backend/lamb/lti_activity_manager.py` — Business logic
- `/backend/lamb/database_manager.py` — Database operations
- `/backend/lamb/templates/lti_dashboard.html` — Dashboard template
- `/backend/lamb/templates/lti_activity_setup.html` — Setup template
- `/backend/lamb/templates/lti_consent.html` — Consent template

### 10.1 Entry Point: `POST /lamb/v1/lti/launch`

The `lti_launch()` function is the single entry point. It decides what to do based on `resource_link_id` existence and user role:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         lti_launch()                                │
│                                                                     │
│  1. Parse form data from LMS POST                                  │
│  2. Validate consumer key against global LTI config                │
│  3. Build base URL (respecting X-Forwarded-* headers)              │
│  4. Validate OAuth 1.0 HMAC-SHA1 signature                        │
│  5. Extract resource_link_id, roles, user info                     │
│  6. Look up lti_activity by resource_link_id                       │
│                                                                     │
│  BRANCH: Activity exists and active?                               │
│  ├── YES + Instructor → Create dashboard token → Redirect to       │
│  │        GET /dashboard (Instructor Dashboard)                    │
│  │                                                                  │
│  ├── YES + Student + consent needed → Create consent token →       │
│  │        Redirect to GET /consent (Consent Page)                  │
│  │                                                                  │
│  ├── YES + Student + no consent needed →                           │
│  │        handle_student_launch() → Redirect to OWI               │
│  │                                                                  │
│  └── NO:                                                           │
│       ├── Instructor → identify_instructor() →                     │
│       │   ├── Found → Create setup token → Redirect to GET /setup  │
│       │   └── Not found → "Contact your LAMB administrator" page  │
│       └── Student → Render "not set up yet" waiting page          │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Token Management

The Unified LTI uses short-lived in-memory tokens (not JWTs) to manage state across its multi-step flows. Three token types are used:

| Token Type | TTL | Purpose |
|---|---|---|
| `setup` | 10 min | Carries instructor identity and LTI context for setup/reconfigure |
| `dashboard` | 30 min | Authorizes instructor access to the dashboard and its API endpoints |
| `consent` | 10 min | Carries student identity for the consent-then-launch flow |

```python
_tokens: dict = {}  # In-memory, cleared on restart

def _create_token(data: dict, ttl: int) -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = {**data, "expires": time.time() + ttl}
    # Prune expired tokens on every creation
    ...
    return token
```

Tokens are validated on each request and consumed (deleted) after one-time use where appropriate (e.g., after setup completes).

### 10.3 Instructor Dashboard Flow

When an instructor arrives at a configured activity:

```
POST /lti/launch (OAuth validated, activity exists, role=Instructor)
    │
    ▼
Create dashboard token with:
  - resource_link_id, lms_user_id, lms_email
  - is_owner: bool (true if lms_email == activity.owner_email)
    │
    ▼
GET /lti/dashboard?resource_link_id=X&token=Y
    │
    ├── Validate dashboard token
    ├── Fetch activity from DB
    ├── manager.get_dashboard_stats(activity)    → stats card data
    ├── manager.get_dashboard_students(activity)  → anonymized student list
    ├── manager.get_dashboard_chats(activity)     → anonymized chat list (if enabled)
    │
    ▼
Render lti_dashboard.html (Jinja2) with:
  - Activity details, org name, created date
  - Summary stats (students, chats, messages, active 7d)
  - Assistants list with per-assistant stats
  - Paginated student access log (anonymized)
  - Chat transcripts section (if chat_visibility_enabled)
  - is_owner flag (controls "Manage" button visibility)
```

**Dashboard JSON API** (for dynamic content loading):
- `GET /dashboard/stats` — Summary statistics
- `GET /dashboard/students` — Paginated, anonymized student list
- `GET /dashboard/chats` — Paginated, anonymized chat summaries (403 if visibility off)
- `GET /dashboard/chats/{id}` — Full anonymized transcript (403 if visibility off)

### 10.4 Student Consent Flow

When a student arrives at an activity with `chat_visibility_enabled = true` and they haven't consented yet:

```
POST /lti/launch → consent check fails → create consent token
    │
    ▼
GET /lti/consent?token=X
    │ (renders consent page explaining anonymized transcript review)
    ▼
POST /lti/consent (student clicks "I Understand & Continue")
    │
    ├── Validate consent token
    ├── Create/update lti_activity_user record
    ├── Set consent_given_at = now
    ├── handle_student_launch() → get OWI token
    ├── Consume consent token
    │
    ▼
Redirect to OWI: /api/v1/auths/complete?token=X
```

### 10.5 Anonymization Implementation

The dashboard **never reveals real student identities**. Anonymization works by ordering students by their `created_at` timestamp in `lti_activity_users`:

```python
def _build_anonymization_map(self, activity_id: int) -> dict:
    """Map owi_user_id → 'Student N' based on creation order."""
    users = db_manager.get_all_activity_user_owi_ids(activity_id)
    # users are sorted by created_at
    return {
        user['owi_user_id']: f"Student {i+1}"
        for i, user in enumerate(users)
        if user.get('owi_user_id')
    }
```

This mapping is:
- **Deterministic** — same student always gets the same pseudonym
- **Consistent across dashboard visits** — based on DB creation order
- **Non-reversible via API** — no endpoint exposes the mapping

### 10.6 Chat Data Access

Chat transcripts are queried directly from the OWI SQLite database using `OwiDatabaseManager` (the same approach used by `ChatAnalyticsService`):

```python
# Filter chats by:
# 1. Models matching lamb_assistant.{ids} for the activity's assistants
# 2. User IDs matching OWI users in the activity
# Then anonymize student identities using the mapping above
```

### 10.7 LTI Parameters Used

| LTI Parameter | Used For | Required |
|---|---|---|
| `oauth_consumer_key` | Must match global configurable key | Yes |
| `oauth_signature` | OAuth 1.0 HMAC-SHA1 signature | Yes |
| `resource_link_id` | Identifies this specific LTI placement | Yes |
| `roles` | Detect instructor vs student | Yes |
| `user_id` | LMS user identifier | Yes |
| `ext_user_username` | Username for email generation | Preferred |
| `lis_person_contact_email_primary` | Instructor identification + owner matching | For instructors |
| `lis_person_name_full` | Display name | Optional |
| `context_id` | Course identifier | Optional |
| `context_title` | Course name | Optional |

---

## 11. Legacy Student LTI: Code Walkthrough

**Primary file:** `/backend/lamb/lti_users_router.py`

> **Note:** This is the legacy path. For new deployments, use the [Unified LTI](#10-unified-lti-code-walkthrough-new) instead.

### 11.1 Entry Point: `POST /lamb/v1/lti_users/lti`

The `process_lti_connection()` function (lines 311-452) handles the entire student LTI flow:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    process_lti_connection()                          │
│                                                                     │
│  1. Parse form data from LMS POST                                  │
│  2. Load LTI_SECRET from environment                               │
│  3. Construct base_url (respecting X-Forwarded-* headers)          │
│  4. Validate OAuth 1.0 HMAC-SHA1 signature                        │
│  5. Generate synthetic email:                                      │
│     email = "{username}-{oauth_consumer_key}@lamb-project.org"     │
│  6. Check if lti_user exists in LAMB DB                            │
│     ├── YES: Get OWI auth token → Redirect to OWI                 │
│     └── NO:  Call sign_in_lti_user() →                             │
│              ├── Look up published assistant by oauth_consumer_key  │
│              ├── Create OWI user (password = assistant_id)          │
│              ├── Find OWI group by name                             │
│              ├── Add user to group                                  │
│              ├── Create lti_users record                            │
│              └── Get OWI auth token → Redirect to OWI              │
│  7. Redirect: {OWI_PUBLIC_BASE_URL}/api/v1/auths/complete?token=X  │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 Key Code Sections

**OAuth signature validation** (lines 348-367):
```python
computed_signature, base_string, encoded_params = generate_signature(
    post_data, "POST", base_url, lti_secret
)
if computed_signature != post_data.get("oauth_signature"):
    raise HTTPException(status_code=401, detail="Invalid OAuth signature")
```

**Email generation** (lines 374-382):
```python
username = post_data.get("ext_user_username", "") or post_data.get("user_id", "")
oauth_consumer_name = post_data.get("oauth_consumer_key", "")
email = f"{username}-{oauth_consumer_name}@lamb-project.org"
```

**New user creation** via `sign_in_lti_user()` (lines 130-268):
- Looks up published assistant by `oauth_consumer_name`
- Creates OWI user with `password = str(published_assistant['assistant_id'])`
- Finds the OWI group by the `group_id` stored in `assistant_publish`
- Adds user to the group via `owi_group_manager.add_user_to_group_by_email()`
- Records the LTI user in LAMB's `lti_users` table

**Redirect** (lines 405-411):
```python
owi_public_base_url = os.getenv("OWI_PUBLIC_BASE_URL") or os.getenv("OWI_BASE_URL")
redirect_url = f"{owi_public_base_url}/api/v1/auths/complete?token={user_token}"
return RedirectResponse(url=redirect_url, status_code=303)
```

### 11.3 LTI Parameters Used

| LTI Parameter | Used For | Required |
|---|---|---|
| `oauth_consumer_key` | Identifies the published assistant AND the OAuth consumer name | Yes |
| `ext_user_username` | Primary source for username | Preferred |
| `user_id` | Fallback username if `ext_user_username` missing | Fallback |
| `oauth_signature` | OAuth 1.0 HMAC-SHA1 signature | Yes |
| `oauth_timestamp` | Included in signature computation | Yes |
| `oauth_nonce` | Included in signature computation | Yes |

Note: `lis_person_contact_email_primary` is **intentionally ignored** — the email is synthesized for privacy.

---

## 12. Creator LTI: Code Walkthrough

**Primary file:** `/backend/lamb/lti_creator_router.py`

### 12.1 Entry Point: `POST /lamb/v1/lti_creator/launch`

The `lti_creator_launch()` function (lines 88-227) is cleaner and more modern than the student path:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      lti_creator_launch()                           │
│                                                                     │
│  1. Parse form data from LMS POST                                  │
│  2. Extract oauth_consumer_key                                     │
│  3. Look up organization by consumer key (lti_creator_keys table)  │
│  4. Reject if system organization                                  │
│  5. Get consumer secret from org's lti_creator config              │
│  6. Construct base_url (respecting X-Forwarded-* headers)          │
│  7. Validate OAuth 1.0 HMAC-SHA1 signature                        │
│  8. Extract user_id from LTI params                                │
│  9. Generate display name (with fallbacks)                         │
│ 10. Generate email:                                                │
│     "lti_creator_{org_slug}_{sanitized_user_id}@lamb-lti.local"   │
│ 11. Look up existing creator user by (org_id, lti_user_id)        │
│     ├── EXISTS: Fetch user email                                   │
│     └── NEW:   create_lti_creator_user() →                         │
│                ├── Create OWI user (random password)                │
│                ├── Create Creator_users record                      │
│                └── Assign 'member' org role                         │
│ 12. Check user.enabled (reject if disabled)                        │
│ 13. Get OWI auth token                                             │
│ 14. Redirect: {LAMB_PUBLIC_BASE_URL}/assistants?token={token}      │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.2 Key Code Sections

**Organization lookup** (lines 118-122):
```python
org = db_manager.get_organization_by_lti_consumer_key(oauth_consumer_key)
if not org:
    raise HTTPException(status_code=401, detail="Invalid consumer key")
```

This joins `lti_creator_keys` with `organizations` to find the org.

**Per-organization secret** (lines 130-133):
```python
consumer_secret = org.get('lti_creator', {}).get('oauth_consumer_secret')
```

Unlike Student LTI's global secret, this is stored per-org in the database.

**User identity** (lines 156-172):
```python
lti_user_id = post_data.get("user_id")  # Stable across LMS sessions
sanitized_lti_user_id = sanitize_lti_user_id(lti_user_id)
user_email = f"lti_creator_{org['slug']}_{sanitized_lti_user_id}@lamb-lti.local"
```

**User creation** (lines 176-195):
```python
creator_user = db_manager.get_creator_user_by_lti(org['id'], lti_user_id)
if not creator_user:
    user_id = db_manager.create_lti_creator_user(
        organization_id=org['id'],
        lti_user_id=lti_user_id,
        user_email=user_email,
        user_name=user_name
    )
```

`create_lti_creator_user()` (in `database_manager.py`) does three things:
1. Creates an OWI user with a random password
2. Creates a `Creator_users` record with `auth_provider='lti_creator'`
3. Assigns `'member'` role in the organization

**Redirect** (lines 216-221):
```python
redirect_url = f"{public_base_url}/assistants?token={auth_token}"
return RedirectResponse(url=redirect_url, status_code=303)
```

The frontend (`assistants/+page.svelte` lines 256-269) extracts the token from the URL, stores it in localStorage, and cleans the URL:
```javascript
const urlToken = $page.url.searchParams.get('token');
if (urlToken) {
    localStorage.setItem('userToken', urlToken);
    user.setToken(urlToken);
    const cleanUrl = new URL(window.location.href);
    cleanUrl.searchParams.delete('token');
    window.history.replaceState({}, '', cleanUrl.toString());
}
```

### 12.3 LTI Parameters Used

| LTI Parameter | Used For | Required |
|---|---|---|
| `oauth_consumer_key` | Identifies the organization | Yes |
| `user_id` | Stable user identifier across LMS sessions | Yes |
| `lis_person_name_full` | Display name (primary) | Optional |
| `ext_user_username` | Display name (fallback) | Optional |
| `oauth_signature` | OAuth 1.0 HMAC-SHA1 signature | Yes |

### 12.4 Info Endpoint

`GET /lamb/v1/lti_creator/info` returns configuration metadata for LMS administrators. No authentication required.

---

## 13. Database Schema

### 13.1 `lti_global_config` Table (Unified LTI — NEW)

Singleton table for the global LTI credentials used by the Unified LTI path.

```sql
CREATE TABLE lti_global_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    oauth_consumer_key TEXT NOT NULL,
    oauth_consumer_secret TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    updated_by TEXT  -- Email of admin who last changed it
);
```

**Precedence logic:** DB values override `.env` values. Falls back to `LTI_GLOBAL_CONSUMER_KEY` / `LTI_GLOBAL_SECRET` env vars if no DB record exists.

### 13.2 `lti_activities` Table (Unified LTI — NEW)

One row per LTI activity placement in an LMS. Bound to one organization.

```sql
CREATE TABLE lti_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_link_id TEXT NOT NULL UNIQUE,
    organization_id INTEGER NOT NULL,
    context_id TEXT,
    context_title TEXT,
    activity_name TEXT,
    owi_group_id TEXT NOT NULL,
    owi_group_name TEXT NOT NULL,
    owner_email TEXT NOT NULL,              -- Creator user email of the OWNER
    owner_name TEXT,
    configured_by_email TEXT NOT NULL,
    configured_by_name TEXT,
    chat_visibility_enabled INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

Key fields:
- `owner_email` — the instructor who first configured the activity; only this person can manage assistant selection
- `chat_visibility_enabled` — opt-in flag controlling anonymized chat transcript access on the dashboard

### 13.3 `lti_activity_assistants` Table (Unified LTI — NEW)

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
```

### 13.4 `lti_activity_users` Table (Unified LTI — NEW)

Tracks users who have accessed via a Unified LTI activity.

```sql
CREATE TABLE lti_activity_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    user_display_name TEXT NOT NULL DEFAULT '',
    lms_user_id TEXT,
    owi_user_id TEXT,                       -- OWI user UUID (for chat queries)
    consent_given_at INTEGER,              -- Timestamp of chat visibility consent
    last_access_at INTEGER,                -- Last launch timestamp
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES lti_activities(id) ON DELETE CASCADE,
    UNIQUE(user_email, activity_id)
);
```

Key fields:
- `owi_user_id` — needed to query chats for this student from the OWI database
- `consent_given_at` — when the student accepted the chat visibility notice (NULL = not yet)
- `last_access_at` / `access_count` — updated on every launch for dashboard analytics

### 13.5 `lti_identity_links` Table (Unified LTI — NEW)

Maps LMS identities to LAMB Creator users for instructor identification.

```sql
CREATE TABLE lti_identity_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lms_user_id TEXT NOT NULL,
    lms_email TEXT,
    creator_user_id INTEGER NOT NULL,
    linked_at INTEGER NOT NULL,
    FOREIGN KEY (creator_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE
);
```

### 13.6 `lti_users` Table (Legacy Student LTI)

```sql
CREATE TABLE lti_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL,          -- Links to published assistant
    assistant_name TEXT NOT NULL,
    group_id TEXT NOT NULL DEFAULT '',   -- OWI group ID
    group_name TEXT NOT NULL DEFAULT '',
    assistant_owner TEXT NOT NULL DEFAULT '',
    user_email TEXT NOT NULL,            -- Synthetic: {user}-{assistant}@lamb-project.org
    user_name TEXT NOT NULL DEFAULT '',
    user_display_name TEXT NOT NULL,
    lti_context_id TEXT NOT NULL,        -- Stores oauth_consumer_name
    lti_app_id TEXT,                     -- Also stores oauth_consumer_name
    UNIQUE(user_email, assistant_id)     -- One record per user per assistant
);
```

### 13.7 `assistant_publish` Table

```sql
CREATE TABLE assistant_publish (
    assistant_id INTEGER PRIMARY KEY,        -- FK to assistants.id
    assistant_name TEXT NOT NULL,
    assistant_owner TEXT NOT NULL,
    group_id TEXT NOT NULL,                  -- OWI group name (e.g., "assistant_42")
    group_name TEXT NOT NULL,
    oauth_consumer_name TEXT UNIQUE,         -- Used as LTI consumer key for student LTI
    created_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE
);
```

When `oauth_consumer_name` is `NULL`, the assistant is considered unpublished.

### 13.8 `lti_creator_keys` Table (Creator LTI)

```sql
CREATE TABLE lti_creator_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE,  -- One key set per org
    oauth_consumer_key TEXT NOT NULL UNIQUE,
    oauth_consumer_secret TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);
```

Indexed on both `oauth_consumer_key` (unique) and `organization_id`.

### 13.9 `Creator_users` Table (LTI-Relevant Fields)

```sql
-- Additional fields added by migration 8
ALTER TABLE Creator_users ADD COLUMN lti_user_id TEXT;
ALTER TABLE Creator_users ADD COLUMN auth_provider TEXT DEFAULT 'password';
```

For LTI creator users:
- `auth_provider = 'lti_creator'`
- `lti_user_id` = stable LMS user identifier
- `user_type = 'creator'`
- `organization_id` = linked organization

### 13.10 Entity Relationships

```
═══ UNIFIED LTI (NEW) ═══

lti_global_config (singleton) ─── provides oauth credentials ───► POST /v1/lti/launch
                                                                        │
organizations ──1:N──► lti_activities (bound to one org)                │
                            │                                           │
                            ├──1:N──► lti_activity_assistants ──N:1──► assistants
                            │                                              │
                            ├──1:N──► lti_activity_users                   ▼
                            │              │                        assistant_publish
                            │              ├── owi_user_id ──► OWI user
                            │              └── consent tracking
                            │
                            └── owi_group_id ──► OWI group ──► N models

lti_identity_links ──N:1──► Creator_users (maps LMS identity → LAMB creator)


═══ LEGACY STUDENT LTI ═══

assistants ──1:1──► assistant_publish (oauth_consumer_name)
                           │
                           │ oauth_consumer_name = oauth_consumer_key in LTI request
                           │
                           ▼
                     lti_users (per student, per assistant)
                           │
                           │ user_email
                           ▼
                     OWI user (separate database)
                           │
                           ▼
                     OWI group (access control to OWI model)


═══ CREATOR LTI ═══

organizations ──1:1──► lti_creator_keys
     │
     │ 1:N
     ▼
Creator_users (lti_user_id, auth_provider='lti_creator')
```

---

## 14. OAuth 1.0 Signature Validation

Both LTI paths use OAuth 1.0 HMAC-SHA1 signatures. The implementation is duplicated (each router has its own `generate_signature`/`generate_oauth_signature` function).

### 14.1 Algorithm

```
1. Remove oauth_signature from params
2. Sort remaining params alphabetically
3. URL-encode params into key=value&key=value string
4. Build base string: "POST&{url_encoded_base_url}&{url_encoded_params}"
5. Build signing key: "{consumer_secret}&{token_secret}"  (token_secret is empty)
6. Compute HMAC-SHA1(signing_key, base_string)
7. Base64-encode the result
8. Compare with received oauth_signature
```

### 14.2 URL Construction

Both endpoints handle reverse-proxy setups:
```python
proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
host = request.headers.get("Host", request.url.hostname)
prefix = request.headers.get('X-Forwarded-Prefix', '')
base_url = f"{proto}://{host}{prefix}{request.url.path}"
```

This is critical for signature validation — the URL used to compute the signature must exactly match the URL the LMS used.

### 14.3 Secret Sources

| Path | Secret Source | Lookup |
|---|---|---|
| Unified LTI | `lti_global_config` table or `LTI_GLOBAL_SECRET` env var | DB first, then env var fallback |
| Legacy Student LTI | `os.getenv("LTI_SECRET")` | Global env var |
| Creator LTI | `lti_creator_keys.oauth_consumer_secret` | Per-org from DB |

---

## 15. OWI Bridge Integration

Both LTI paths create users in Open WebUI through the OWI Bridge layer (`/backend/lamb/owi_bridge/`).

### 15.1 User Creation

**Student LTI:** Uses `OwiUserManager.create_user()` with password = `assistant_id` (string).

**Creator LTI:** Uses `create_lti_creator_user()` in `database_manager.py` which internally calls `OwiUserManager.create_user()` with a random password.

### 15.2 Token Generation

Both paths use `OwiUserManager.get_auth_token(email, username)` which calls OWI's internal API:
```
POST {OWI_BASE_URL}/api/v1/auths/signin
Headers: X-User-Email, X-User-Name
Returns: JWT token
```

### 15.3 Group Management

**Unified LTI:** Each activity creates an OWI group named `lti_activity_{resource_link_id}`. This group is added to each selected assistant's model `access_control.read.group_ids`. Students are added to this single group, granting them access to all selected assistants.

**Legacy Student LTI:** When publishing an assistant, an OWI group named `assistant_{id}` is created. During student LTI launch:

1. Look up the group by name: `owi_group_manager.get_group_by_name(group_name)`
2. Add student to group: `owi_group_manager.add_user_to_group_by_email(group_id, email)`
3. OWI's access control then grants the student visibility of the `lamb_assistant.{id}` model

**Creator LTI:** Users don't interact with groups — they access the Creator Interface, not the chat.

### 15.4 Direct OWI Database Access (Unified LTI Dashboard)

The Unified LTI dashboard queries chat data directly from the OWI SQLite database via `OwiDatabaseManager`. This is the same approach used by `ChatAnalyticsService`. It's necessary because OWI does not expose a REST API for querying chat data filtered by user/model.

```python
# Queries the OWI 'chat' table for:
# - Chats where model matches lamb_assistant.{ids} for the activity
# - Chats where user_id matches OWI user IDs from lti_activity_users
# Student identities are anonymized before returning to the dashboard
```

---

## 16. Publishing: How Activities Are Born

Publishing is the bridge between the Creator Interface and Student LTI. Here's what happens when an instructor publishes an assistant:

**Endpoint:** `PUT /creator/assistant/{id}/publish`  
**File:** `/backend/creator_interface/assistant_router.py` (lines 1626-1702)

```
1. Validate user owns the assistant
2. Generate group_id = "assistant_{id}"
3. INSERT OR REPLACE into assistant_publish:
   - assistant_id, assistant_name, assistant_owner
   - group_id = "assistant_{id}"
   - oauth_consumer_name = assistant.name  ← This becomes the LTI consumer key!
4. Return updated assistant data
```

**Unpublishing** simply sets `oauth_consumer_name = NULL` in the same table (using `INSERT OR REPLACE`).

**The consumer key lifecycle:**
```
Instructor publishes "Physics Tutor"
  → assistant_publish.oauth_consumer_name = "Physics Tutor"
  → LMS admin configures LTI with consumer_key = "Physics Tutor"
  → Student clicks LTI link → oauth_consumer_key = "Physics Tutor"
  → LAMB looks up assistant_publish WHERE oauth_consumer_name = "Physics Tutor"
  → Found! Route student to this assistant.
```

---

## 17. Key Files Reference

### Unified LTI (NEW)

| File | Purpose | Key Functions |
|---|---|---|
| `lamb/lti_router.py` | Unified LTI route handlers | `lti_launch()`, `lti_setup_page()`, `lti_configure_activity()`, `lti_dashboard()`, `lti_consent_page()`, `lti_consent_submit()`, `lti_enter_chat()`, `lti_reconfigure_activity()` |
| `lamb/lti_activity_manager.py` | Business logic for unified LTI | `get_lti_credentials()`, `configure_activity()`, `handle_student_launch()`, `identify_instructor()`, `get_dashboard_stats()`, `get_dashboard_students()`, `get_dashboard_chats()`, `get_dashboard_chat_detail()`, `check_student_consent()`, `record_consent()` |
| `lamb/templates/lti_activity_setup.html` | Setup page (Jinja2) | Assistant selection, chat visibility checkbox, org selection |
| `lamb/templates/lti_dashboard.html` | Instructor dashboard (Jinja2) | Stats, student log, chat transcripts (with JS for AJAX) |
| `lamb/templates/lti_consent.html` | Student consent page (Jinja2) | Chat visibility notice + accept button |
| `lamb/templates/lti_waiting.html` | "Not set up" page (Jinja2) | Shown to students at unconfigured activities |
| `lamb/templates/lti_contact_admin.html` | "Contact admin" page (Jinja2) | Shown to instructors without a Creator account at unconfigured activities |
| `lamb/templates/lti_link_account.html` | Account linking form (Jinja2) | Legacy — email/password form for unidentified instructors (no longer used in launch flow) |

### Legacy Student LTI

| File | Purpose | Key Functions |
|---|---|---|
| `lamb/lti_users_router.py` | Student LTI endpoint | `process_lti_connection()`, `sign_in_lti_user()`, `generate_signature()` |

### Creator LTI

| File | Purpose | Key Functions |
|---|---|---|
| `lamb/lti_creator_router.py` | Creator LTI endpoint | `lti_creator_launch()`, `generate_oauth_signature()`, `sanitize_lti_user_id()` |

### Shared / Supporting

| File | Purpose | Key Functions |
|---|---|---|
| `lamb/simple_lti/simple_lti_main.py` | Simple LTI stub | Not actively used for real LTI launches |
| `lamb/database_manager.py` | All DB operations | `create_lti_activity()`, `get_lti_activity_by_resource_link()`, `create_lti_activity_user()`, `record_student_consent()`, `get_activity_students()`, `get_all_activity_user_owi_ids()`, `create_lti_user()`, `get_lti_user_by_email()`, `publish_assistant()`, `create_lti_creator_user()`, `get_creator_user_by_lti()`, `get_organization_by_lti_consumer_key()` |
| `lamb/owi_bridge/owi_users.py` | OWI user management | `create_user()`, `get_auth_token()` |
| `lamb/owi_bridge/owi_group.py` | OWI group management | `add_user_to_group_by_email()`, `get_group_by_name()`, `create_group()` |
| `lamb/owi_bridge/owi_model.py` | OWI model registration | `create_model()`, `add_group_to_model()` |
| `lamb/owi_bridge/owi_database.py` | Direct OWI DB access | Chat queries for dashboard analytics |
| `lamb/lamb_classes.py` | Pydantic models | `LTIUser` class |
| `lamb/main.py` | Router registration | `lti_router`, `lti_users_router`, `lti_creator_router` |
| `creator_interface/assistant_router.py` | Publishing | `publish_assistant()` |
| `creator_interface/organization_router.py` | Org admin LTI management | LTI creator settings + activity management endpoints |
| `frontend/svelte-app/src/routes/admin/+page.svelte` | System admin LTI settings | Global LTI key/secret config, launch URL display |
| `frontend/svelte-app/src/routes/org-admin/+page.svelte` | Org admin activities view | LTI Activities table with owner and chat visibility columns |
| `frontend/svelte-app/src/routes/assistants/+page.svelte` | Token handling | Token extraction from URL (Creator LTI) |

---

## 18. Design Decisions and Trade-offs

### 18.1 LTI 1.1 vs LTI 1.3

LAMB uses **LTI 1.1** (OAuth 1.0 signatures). This was a deliberate choice:
- **Pro:** Universal LMS compatibility — every LMS supports 1.1
- **Pro:** Simpler implementation — no OIDC, no JWT, no platform registration dance
- **Pro:** No external library dependency (PyLTI1p3 not used)
- **Con:** OAuth 1.0 is considered less secure than 1.3's OpenID Connect
- **Con:** No deep linking, assignment & grades, or Names & Roles Provisioning services
- **Con:** The spec is technically deprecated by IMS Global in favor of 1.3

### 18.2 Generated Emails vs Real Emails

Using synthetic emails (`{user}-{assistant}@lamb-project.org`) instead of real ones:
- **Pro:** Privacy — real emails never touch Open WebUI
- **Pro:** Isolation — natural per-activity identity separation
- **Con:** No way to correlate a student across assistants (by design)
- **Con:** Analytics require cross-referencing with LMS data
- **Con:** If username changes in LMS, a new identity is created

### 18.3 Global vs Per-Org Secrets

Student LTI uses a global `LTI_SECRET` while Creator LTI uses per-org secrets:
- **Historical:** Student LTI was built first, with simpler security assumptions
- **Risk:** A compromised `LTI_SECRET` affects all published assistants across all organizations
- **Mitigation opportunity:** Future versions could move to per-assistant or per-org secrets

### 18.4 OWI as Auth Layer

LAMB delegates all authentication (password hashing, JWT tokens) to Open WebUI:
- **Pro:** Single source of truth for auth
- **Pro:** OWI's chat interface "just works" with tokens
- **Con:** Tight coupling — LAMB must speak OWI's internal API
- **Con:** Token generation requires an HTTP call to OWI

### 18.5 Unified LTI: Backend-Served Pages vs SPA (NEW)

The Unified LTI setup page, dashboard, and consent page are all **backend-served Jinja2 templates**, not part of the Svelte SPA:
- **Pro:** Works within LMS iframe contexts without complex SPA routing
- **Pro:** Independent of the frontend build — works even if the Svelte app is being rebuilt
- **Pro:** LTI context (resource_link_id, roles) comes from the launch POST, not from SPA state
- **Pro:** Simple token-based auth, no need for the full Creator auth flow
- **Con:** UI is less sophisticated than a full SPA (mitigated by TailwindCSS + vanilla JS)
- **Con:** Some dynamic features (chat loading, pagination) require manual AJAX calls

### 18.6 Unified LTI: Activity Ownership (NEW)

The "first instructor configures, becomes owner" model was chosen for simplicity:
- **Pro:** Deterministic — no ambiguity about who owns an activity
- **Pro:** Prevents configuration conflicts when multiple instructors access simultaneously
- **Con:** If the owner leaves the institution, someone must transfer ownership via org-admin
- **Mitigation:** Organization admins can view and manage all activities in their org

### 18.7 Unified LTI: Chat Visibility and Anonymization (NEW)

Opt-in chat visibility with mandatory anonymization balances pedagogical needs with privacy:
- **Pro:** Instructors can understand how students use AI tools
- **Pro:** Students are protected by consistent anonymization ("Student N")
- **Pro:** Consent requirement satisfies informed-consent principles
- **Con:** Anonymization is based on creation order — theoretically, an instructor who knows when each student first accessed could correlate
- **Mitigation:** No API endpoint exposes the anonymization mapping. The risk is low in practice.

### 18.8 Unified LTI: In-Memory Tokens (NEW)

The Unified LTI uses in-memory token stores instead of JWTs:
- **Pro:** Simple implementation, no JWT secret management
- **Pro:** Tokens are easily revocable (just delete from dict)
- **Con:** Tokens are lost on server restart (users must re-launch from LMS)
- **Con:** Not suitable for multi-instance deployments without shared state
- **Mitigation:** The TTLs are short (10-30 min), and re-launching from LMS is trivial

---

## 19. Known Limitations and Future Directions

### Current Limitations

1. **No LTI 1.3 support** — Limits advanced LTI services (grades, deep linking)
2. **Global legacy student LTI secret** — Security risk if compromised (legacy path only)
3. **No nonce/timestamp validation** — OAuth signatures are verified but replay protection is missing (all paths)
4. **No LTI Advantage services** — No grade passback, no roster sync, no deep linking
5. **Duplicated OAuth code** — `generate_signature()` exists in multiple LTI routers with minor differences
6. **simple_lti stub** — The `/simple_lti/launch` endpoint exists but doesn't do anything useful
7. **Password as assistant_id** — Legacy student OWI passwords are set to `assistant_id`, which is predictable
8. **In-memory tokens** — Unified LTI tokens are lost on server restart; not suitable for multi-instance deployments
9. **Dashboard anonymization correlation risk** — Theoretically, creation-order-based anonymization could be correlated by an instructor who knows exact student access times
10. **No chat export** — Dashboard shows transcripts inline but offers no CSV/PDF export

### Possible Future Improvements

1. **LTI 1.3 migration** — Full OIDC-based flow with proper security
2. **Per-assistant secrets** — Move from global `LTI_SECRET` to per-assistant or per-org secrets (legacy path)
3. **Unified OAuth module** — Extract shared signature logic into a single utility
4. **Grade passback** — Return scores/completion status to LMS
5. **Deep linking** — Let instructors select assistants from within LMS UI
6. **Nonce/replay protection** — Store and validate nonces to prevent replay attacks
7. **Simple LTI cleanup** — Either implement or remove the stub
8. **Persistent token store** — Move Unified LTI tokens to Redis or DB for multi-instance deployments
9. **Chat export** — Allow instructors to download anonymized chat transcripts as CSV/PDF
10. **Dashboard enhancements** — Usage trends over time, per-assistant usage charts, assignment correlation
11. **Ownership transfer UI** — Allow owners to delegate ownership to another instructor from the dashboard
12. **Legacy migration tool** — Script to migrate existing Student LTI activities to the Unified LTI model
13. **Randomized anonymization** — Replace creation-order-based "Student N" with randomized pseudonyms for stronger privacy

---

## Related Documentation

| Document | Purpose |
|---|---|
| [lamb_architecture_v2.md](./lamb_architecture_v2.md) | Full system architecture (includes Unified LTI summary) |
| [projects/lti_unified_activity_design.md](./projects/lti_unified_activity_design.md) | Detailed design document for the Unified LTI feature |
| [small-context/backend_lti_integration.md](./small-context/backend_lti_integration.md) | LTI integration technical reference |
| [small-context/backend_authentication.md](./small-context/backend_authentication.md) | Authentication flows |
| [small-context/database_schema.md](./small-context/database_schema.md) | Database schema reference |

---

*Maintainers: LAMB Development Team*  
*Last Updated: February 6, 2026*  
*Version: 2.0*
