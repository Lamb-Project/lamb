# LAMB LTI Landscape

**Version:** 1.0  
**Last Updated:** February 6, 2026  
**Reading Time:** ~25 minutes

> This document provides a comprehensive overview of how LAMB integrates with Learning Management Systems (LMS) through LTI. It is split into two parts: a **non-technical overview** for educators, administrators, and project stakeholders, followed by a **technical deep-dive** for developers working on the codebase.

---

## Table of Contents

### Part 1 — Non-Technical Overview
1. [What is LTI and Why Does LAMB Use It?](#1-what-is-lti-and-why-does-lamb-use-it)
2. [The Two LTI Paths](#2-the-two-lti-paths)
3. [Student LTI: Accessing AI Assistants](#3-student-lti-accessing-ai-assistants)
4. [Creator LTI: Building AI Assistants from the LMS](#4-creator-lti-building-ai-assistants-from-the-lms)
5. [How Students Are Kept Isolated](#5-how-students-are-kept-isolated)
6. [The Confusing Parts (Honestly)](#6-the-confusing-parts-honestly)
7. [Summary: Which LTI Tool Does What?](#7-summary-which-lti-tool-does-what)

### Part 2 — Technical Deep-Dive
8. [Architecture Overview](#8-architecture-overview)
9. [Student LTI: Code Walkthrough](#9-student-lti-code-walkthrough)
10. [Creator LTI: Code Walkthrough](#10-creator-lti-code-walkthrough)
11. [Database Schema](#11-database-schema)
12. [OAuth 1.0 Signature Validation](#12-oauth-10-signature-validation)
13. [OWI Bridge Integration](#13-owi-bridge-integration)
14. [Publishing: How Activities Are Born](#14-publishing-how-activities-are-born)
15. [Key Files Reference](#15-key-files-reference)
16. [Design Decisions and Trade-offs](#16-design-decisions-and-trade-offs)
17. [Known Limitations and Future Directions](#17-known-limitations-and-future-directions)

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

## 2. The Two LTI Paths

LAMB has **two completely separate LTI integrations** that serve different audiences and purposes:

![LAMB LTI Integration: Two Paths, One Platform](lti_landscape_overview.png)

| | Student LTI | Creator LTI |
|---|---|---|
| **Who uses it?** | Students (and instructors reviewing) | Instructors/Educators |
| **What does it do?** | Opens a chat with a specific AI assistant | Opens the Creator Interface to build assistants |
| **Where do they land?** | Open WebUI (chat interface) | LAMB Creator Interface (Svelte frontend) |
| **Endpoint** | `POST /lamb/v1/lti_users/lti` | `POST /lamb/v1/lti_creator/launch` |
| **Consumer key tied to** | A specific published assistant | An entire organization |
| **Shared secret stored in** | Global `LTI_SECRET` env var | Per-organization in database |

Think of it this way:
- **Student LTI** = "Use this AI assistant" (consumption)
- **Creator LTI** = "Build AI assistants" (creation)

---

## 3. Student LTI: Accessing AI Assistants

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

## 4. Creator LTI: Building AI Assistants from the LMS

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

## 5. How Students Are Kept Isolated

This is one of LAMB's most important privacy features. When a student accesses an assistant via LTI:

![Student Identity Isolation per Activity](lti_identity_isolation.png)

**The email formula:**
```
{lms_username}-{assistant_oauth_consumer_name}@lamb-project.org
```

**Example:** Maria Garcia accesses two LTI assistants:
- Physics Tutor → `mgarcia-PhysicsTutor@lamb-project.org`
- History Essay Helper → `mgarcia-HistoryEssayHelper@lamb-project.org`

These are **two completely separate Open WebUI accounts**. Maria's Physics chats are invisible from the History assistant and vice versa. Each identity belongs to only one OWI group, which only grants access to one assistant.

---

## 6. The Confusing Parts (Honestly)

Let's acknowledge the quirks:

### 6.1 The Shared Secret Asymmetry

- **Student LTI** uses a single global `LTI_SECRET` environment variable for all assistants. Every published assistant shares the same secret.
- **Creator LTI** stores per-organization secrets in the database (`lti_creator_keys` table). Each organization has its own key/secret pair.

This means student LTI security relies on one secret for the entire instance, while creator LTI has proper per-tenant isolation.

### 6.2 "Consumer Key" Means Different Things

- In **Student LTI**, the `oauth_consumer_key` is the **assistant's name** (the `oauth_consumer_name` from publishing). It identifies *which assistant* the student wants.
- In **Creator LTI**, the `oauth_consumer_key` identifies *which organization* the instructor belongs to.

Same OAuth parameter, completely different semantics.

### 6.3 Creator LTI Users Are "Creators" But With Limits

LTI creator users get `user_type = 'creator'` and can do almost everything a regular creator can: build assistants, create knowledge bases, publish, share. But they **cannot** become organization admins, and their password is a random string they'll never see (they always enter through LTI).

### 6.4 Three Endpoints, Two Active

There are actually three LTI-related routing paths in the codebase:

| Endpoint | Status | Purpose |
|---|---|---|
| `POST /lamb/v1/lti_users/lti` | **Active** | Student LTI launch |
| `POST /lamb/v1/lti_creator/launch` | **Active** | Creator LTI launch |
| `POST /lamb/simple_lti/launch` | **Stub** | Placeholder, not fully implemented |

The `simple_lti` router exists as a skeleton but doesn't actually process LTI launches — it returns a generic JSON response. The real student LTI work happens in `lti_users_router.py`.

---

## 7. Summary: Which LTI Tool Does What?

| Aspect | Student LTI (`/v1/lti_users/lti`) | Creator LTI (`/v1/lti_creator/launch`) |
|---|---|---|
| **Purpose** | Students chat with a published assistant | Instructors build and manage assistants |
| **Destination** | Open WebUI chat interface | LAMB Creator Interface (Svelte SPA) |
| **Identity** | `{username}-{assistant_name}@lamb-project.org` | `lti_creator_{org}_{user_id}@lamb-lti.local` |
| **Consumer key = ** | Published assistant name | Organization's configured key |
| **Shared secret** | Global `LTI_SECRET` env var | Per-org in `lti_creator_keys` table |
| **User type created** | OWI end-user (role: `user`) | LAMB creator user (`auth_provider: lti_creator`) |
| **Needs per-assistant setup in LMS?** | Yes (one LTI activity per assistant) | No (one LTI activity for all of LAMB Creator) |
| **Password** | Set to `assistant_id` (never used by human) | Random string (never used by human) |

---

# Part 2 — Technical Deep-Dive

## 8. Architecture Overview

### 8.1 LTI in the LAMB Stack

Both LTI paths are mounted inside the LAMB Core API (`/backend/lamb/main.py`):

```
LAMB Application (main.py)
│
├── /lamb/                          ← LAMB Core API
│   ├── /v1/lti_users/              ← Student LTI router
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
    └── owi_model.py                ← Model registration
```

### 8.2 Dependency Graph

```
                          ┌──────────────────┐
                          │       LMS        │
                          │ (Canvas/Moodle)  │
                          └────┬────────┬────┘
                               │        │
               Student LTI    │        │    Creator LTI
               (assistant-     │        │    (org-level
                specific)      │        │     access)
                               ▼        ▼
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
           │   keys       │                │              │
           │ Creator_users│                │              │
           └──────────────┘                └──────────────┘
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │  Open WebUI  │
                                           │  (Chat UI)   │
                                           └──────────────┘
```

---

## 9. Student LTI: Code Walkthrough

**Primary file:** `/backend/lamb/lti_users_router.py`

### 9.1 Entry Point: `POST /lamb/v1/lti_users/lti`

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

### 9.2 Key Code Sections

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

### 9.3 LTI Parameters Used

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

## 10. Creator LTI: Code Walkthrough

**Primary file:** `/backend/lamb/lti_creator_router.py`

### 10.1 Entry Point: `POST /lamb/v1/lti_creator/launch`

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

### 10.2 Key Code Sections

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

### 10.3 LTI Parameters Used

| LTI Parameter | Used For | Required |
|---|---|---|
| `oauth_consumer_key` | Identifies the organization | Yes |
| `user_id` | Stable user identifier across LMS sessions | Yes |
| `lis_person_name_full` | Display name (primary) | Optional |
| `ext_user_username` | Display name (fallback) | Optional |
| `oauth_signature` | OAuth 1.0 HMAC-SHA1 signature | Yes |

### 10.4 Info Endpoint

`GET /lamb/v1/lti_creator/info` returns configuration metadata for LMS administrators. No authentication required.

---

## 11. Database Schema

### 11.1 `lti_users` Table (Student LTI)

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

### 11.2 `assistant_publish` Table

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

### 11.3 `lti_creator_keys` Table (Creator LTI)

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

### 11.4 `Creator_users` Table (LTI-Relevant Fields)

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

### 11.5 Entity Relationships

```
organizations ──1:1──► lti_creator_keys
     │
     │ 1:N
     ▼
Creator_users (lti_user_id, auth_provider='lti_creator')
     
     
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
```

---

## 12. OAuth 1.0 Signature Validation

Both LTI paths use OAuth 1.0 HMAC-SHA1 signatures. The implementation is duplicated (each router has its own `generate_signature`/`generate_oauth_signature` function).

### 12.1 Algorithm

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

### 12.2 URL Construction

Both endpoints handle reverse-proxy setups:
```python
proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
host = request.headers.get("Host", request.url.hostname)
prefix = request.headers.get('X-Forwarded-Prefix', '')
base_url = f"{proto}://{host}{prefix}{request.url.path}"
```

This is critical for signature validation — the URL used to compute the signature must exactly match the URL the LMS used.

### 12.3 Secret Sources

| Path | Secret Source | Lookup |
|---|---|---|
| Student LTI | `os.getenv("LTI_SECRET")` | Global env var |
| Creator LTI | `lti_creator_keys.oauth_consumer_secret` | Per-org from DB |

---

## 13. OWI Bridge Integration

Both LTI paths create users in Open WebUI through the OWI Bridge layer (`/backend/lamb/owi_bridge/`).

### 13.1 User Creation

**Student LTI:** Uses `OwiUserManager.create_user()` with password = `assistant_id` (string).

**Creator LTI:** Uses `create_lti_creator_user()` in `database_manager.py` which internally calls `OwiUserManager.create_user()` with a random password.

### 13.2 Token Generation

Both paths use `OwiUserManager.get_auth_token(email, username)` which calls OWI's internal API:
```
POST {OWI_BASE_URL}/api/v1/auths/signin
Headers: X-User-Email, X-User-Name
Returns: JWT token
```

### 13.3 Group Management (Student LTI Only)

When publishing an assistant, an OWI group named `assistant_{id}` is created. During student LTI launch:

1. Look up the group by name: `owi_group_manager.get_group_by_name(group_name)`
2. Add student to group: `owi_group_manager.add_user_to_group_by_email(group_id, email)`
3. OWI's access control then grants the student visibility of the `lamb_assistant.{id}` model

Creator LTI users don't interact with groups — they access the Creator Interface, not the chat.

---

## 14. Publishing: How Activities Are Born

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

## 15. Key Files Reference

| File | Purpose | Key Functions/Lines |
|---|---|---|
| `lamb/lti_users_router.py` | Student LTI endpoint | `process_lti_connection()` (311-452), `sign_in_lti_user()` (130-268), `generate_signature()` (271-309) |
| `lamb/lti_creator_router.py` | Creator LTI endpoint | `lti_creator_launch()` (88-227), `generate_oauth_signature()` (33-73), `sanitize_lti_user_id()` (76-85) |
| `lamb/simple_lti/simple_lti_main.py` | Simple LTI stub | Not actively used for real LTI launches |
| `lamb/database_manager.py` | All DB operations | `create_lti_user()`, `get_lti_user_by_email()`, `publish_assistant()`, `get_published_assistant_by_oauth_consumer()`, `create_lti_creator_user()`, `get_creator_user_by_lti()`, `get_organization_by_lti_consumer_key()` |
| `lamb/owi_bridge/owi_users.py` | OWI user management | `create_user()`, `get_auth_token()` |
| `lamb/owi_bridge/owi_group.py` | OWI group management | `add_user_to_group_by_email()`, `get_group_by_name()` |
| `lamb/owi_bridge/owi_model.py` | OWI model registration | `create_model()` |
| `lamb/lamb_classes.py` | Pydantic models | `LTIUser` class (lines 94-105) |
| `lamb/main.py` | Router registration | `lti_users_router` (line 80), `lti_creator_router` (line 81) |
| `creator_interface/assistant_router.py` | Publishing | `publish_assistant()` (lines 1626-1702) |
| `creator_interface/organization_router.py` | LTI creator admin | LTI creator settings endpoints (lines 3492-3682) |
| `frontend/svelte-app/src/routes/assistants/+page.svelte` | Token handling | Token extraction from URL (lines 256-269) |

---

## 16. Design Decisions and Trade-offs

### 16.1 LTI 1.1 vs LTI 1.3

LAMB uses **LTI 1.1** (OAuth 1.0 signatures). This was a deliberate choice:
- **Pro:** Universal LMS compatibility — every LMS supports 1.1
- **Pro:** Simpler implementation — no OIDC, no JWT, no platform registration dance
- **Pro:** No external library dependency (PyLTI1p3 not used)
- **Con:** OAuth 1.0 is considered less secure than 1.3's OpenID Connect
- **Con:** No deep linking, assignment & grades, or Names & Roles Provisioning services
- **Con:** The spec is technically deprecated by IMS Global in favor of 1.3

### 16.2 Generated Emails vs Real Emails

Using synthetic emails (`{user}-{assistant}@lamb-project.org`) instead of real ones:
- **Pro:** Privacy — real emails never touch Open WebUI
- **Pro:** Isolation — natural per-activity identity separation
- **Con:** No way to correlate a student across assistants (by design)
- **Con:** Analytics require cross-referencing with LMS data
- **Con:** If username changes in LMS, a new identity is created

### 16.3 Global vs Per-Org Secrets

Student LTI uses a global `LTI_SECRET` while Creator LTI uses per-org secrets:
- **Historical:** Student LTI was built first, with simpler security assumptions
- **Risk:** A compromised `LTI_SECRET` affects all published assistants across all organizations
- **Mitigation opportunity:** Future versions could move to per-assistant or per-org secrets

### 16.4 OWI as Auth Layer

LAMB delegates all authentication (password hashing, JWT tokens) to Open WebUI:
- **Pro:** Single source of truth for auth
- **Pro:** OWI's chat interface "just works" with tokens
- **Con:** Tight coupling — LAMB must speak OWI's internal API
- **Con:** Token generation requires an HTTP call to OWI

---

## 17. Known Limitations and Future Directions

### Current Limitations

1. **No LTI 1.3 support** — Limits advanced LTI services (grades, deep linking)
2. **Global student LTI secret** — Security risk if compromised
3. **No nonce/timestamp validation** — OAuth signatures are verified but replay protection is missing
4. **No LTI Advantage services** — No grade passback, no roster sync, no deep linking
5. **Duplicated OAuth code** — `generate_signature()` exists in both LTI routers with minor differences
6. **simple_lti stub** — The `/simple_lti/launch` endpoint exists but doesn't do anything useful
7. **Password as assistant_id** — Student OWI passwords are set to `assistant_id`, which is predictable

### Possible Future Improvements

1. **LTI 1.3 migration** — Full OIDC-based flow with proper security
2. **Per-assistant secrets** — Move from global `LTI_SECRET` to per-assistant or per-org secrets
3. **Unified OAuth module** — Extract shared signature logic into a single utility
4. **Grade passback** — Return scores/completion status to LMS
5. **Deep linking** — Let instructors select assistants from within LMS UI
6. **Nonce/replay protection** — Store and validate nonces to prevent replay attacks
7. **Simple LTI cleanup** — Either implement or remove the stub

---

## Related Documentation

| Document | Purpose |
|---|---|
| [lamb_architecture_v2.md](./lamb_architecture_v2.md) | Full system architecture |
| [small-context/backend_lti_integration.md](./small-context/backend_lti_integration.md) | LTI integration technical reference |
| [small-context/backend_authentication.md](./small-context/backend_authentication.md) | Authentication flows |
| [small-context/database_schema.md](./small-context/database_schema.md) | Database schema reference |

---

*Maintainers: LAMB Development Team*  
*Last Updated: February 6, 2026*  
*Version: 1.0*
