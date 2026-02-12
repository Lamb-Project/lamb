# LAMB Architecture Documentation v2

**Version:** 2.3
**Last Updated:** February 11, 2026
**Reading Time:** ~35 minutes

> This is the streamlined architecture guide. For deep implementation details, see [lamb_architecture.md](./lamb_architecture.md). For quick navigation, see [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [Dual API Architecture](#3-dual-api-architecture)
4. [Data Architecture](#4-data-architecture)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [Completion Pipeline](#6-completion-pipeline)
7. [Organizations & Multi-Tenancy](#7-organizations--multi-tenancy)
8. [Feature Integration](#8-feature-integration)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Development & Deployment](#10-development--deployment)
11. [Logging System](#11-logging-system)
12. [Quick Reference](#12-quick-reference)
13. [Security Summary](#13-security-summary)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. System Overview

### 1.1 High-Level Architecture

LAMB is a distributed system for creating and managing AI learning assistants:

```
┌─────────────────────────────────────────────────────────────────┐
│                         LAMB Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Frontend   │  │   Backend    │  │  Open WebUI  │          │
│  │   (Svelte)   │◄─┤   (FastAPI)  │◄─┤   (Python)   │          │
│  │   :5173/     │  │   :9099      │  │   :8080      │          │
│  │   built SPA  │  │              │  │              │          │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘          │
│                            │                  │                  │
│                            ▼                  ▼                  │
│                    ┌──────────────┐  ┌──────────────┐          │
│                    │  Knowledge   │  │   ChromaDB   │          │
│                    │  Base Server │  │   (Vectors)  │          │
│                    │  :9090       │  │              │          │
│                    └──────────────┘  └──────────────┘          │
│                            │                                      │
│                            ▼                                      │
│                    ┌──────────────┐                              │
│                    │  LLM Provider│                              │
│                    │ OpenAI/Ollama│                              │
│                    └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Service Responsibilities

| Service | Purpose | Technology | Port |
|---------|---------|------------|------|
| **Frontend** | Creator UI, Admin panels | Svelte 5, SvelteKit | 5173 (dev) / served by backend |
| **Backend** | Core API, Completions | FastAPI, Python 3.11 | 9099 |
| **Open WebUI** | Auth, Chat UI, Model management | FastAPI, Python | 8080 |
| **KB Server** | Document processing, Vector search | FastAPI, ChromaDB | 9090 |

### 1.3 Technology Stack

**Backend:**
- Python 3.11+
- FastAPI (async API framework)
- SQLite with WAL mode
- ChromaDB (vector storage)

**Frontend:**
- Svelte 5 with SvelteKit
- TailwindCSS
- Axios for HTTP

**Infrastructure:**
- Docker & Docker Compose
- Caddy (reverse proxy)

---

## 2. Architecture Principles

### 2.1 Design Principles

1. **Privacy-First** — All data remains within institutional control
2. **Modular** — Components can be updated or replaced independently
3. **Extensible** — Plugin architecture for LLMs, prompts, and RAG
4. **Multi-Tenant** — Organizations isolated with independent configs
5. **Standards-Compliant** — OpenAI API compatibility, LTI 1.1
6. **Educator-Centric** — Non-technical users can create AI assistants

### 2.2 Key Patterns

| Pattern | Usage |
|---------|-------|
| **Layered Architecture** | Creator Interface → LAMB Core → Database |
| **Proxy Pattern** | Creator Interface proxies and enhances LAMB Core |
| **Plugin Architecture** | Dynamic loading of processors and connectors |
| **Repository Pattern** | Database managers encapsulate data access |
| **Service Layer** | Business logic separated from HTTP handlers |

---

## 3. Dual API Architecture

### 3.1 Two-Tier Design

LAMB uses a **dual API architecture** where the Creator Interface acts as an enhanced proxy to LAMB Core:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         Creator Interface API (/creator)                     │
│                                                               │
│  • User authentication & session management                  │
│  • File operations (upload/download)                         │
│  • Enhanced request validation                               │
│  • Proxies requests with additional logic                    │
│                                                               │
│  Location: /backend/creator_interface/                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ (Internal HTTP calls)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         LAMB Core API (/lamb/v1)                             │
│                                                               │
│  • Direct database access                                    │
│  • Core business logic                                       │
│  • Assistant, user, organization management                  │
│  • Completions processing                                    │
│                                                               │
│  Location: /backend/lamb/                                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Database/OWI  │
                    └───────────────┘
```

**Why Dual API?**
- **Separation of Concerns** — User-facing logic (auth, file handling) separate from core
- **Flexibility** — Add Creator Interface features without modifying core
- **Security** — Additional validation layer before core operations
- **Evolution** — Maintain API stability while core evolves

### 3.2 Main Entry Point

**File:** `/backend/main.py`

**Mounts:**
- `/lamb` → LAMB Core API
- `/creator` → Creator Interface API
- `/static` → Static file serving
- `/{path:path}` → SPA catch-all (serves frontend)

**Key Root Endpoints:**
- `GET /v1/models` — List assistants as OpenAI models
- `POST /v1/chat/completions` — Generate completions
- `GET /status` — Health check
- `GET /openapi.json` — Full OpenAPI specification (all endpoints, schemas, and parameters)

### 3.3 LAMB Core Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `lti_router` | `/v1/lti` | **Unified LTI** — multi-assistant activities (new) |
| `lti_users_router` | `/v1/lti_users` | Legacy student LTI (single assistant) |
| `simple_lti_router` | `/simple_lti` | Student LTI launch handling (stub) |
| `lti_creator_router` | `/v1/lti_creator` | LTI Creator launch (educators) |
| `completions_router` | `/v1/completions` | Completion generation |
| `mcp_router` | `/v1/mcp` | MCP endpoints |

### 3.4 Creator Interface Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `assistant_router` | `/creator/assistant` | Assistant CRUD |
| `knowledges_router` | `/creator/knowledgebases` | KB operations |
| `organization_router` | `/creator/admin` | Org management |
| `analytics_router` | `/creator/analytics` | Chat analytics |
| `evaluaitor_router` | `/creator/rubrics` | Rubric management |
| `prompt_templates_router` | `/creator/prompt-templates` | Prompt templates |

**Direct Endpoints in Creator Interface:**
- `POST /creator/login` — User login
- `POST /creator/signup` — User signup  
- `GET /creator/user/current` — Current user info
- `POST /creator/files/upload` — File upload
- `GET /creator/admin/users` — List users (admin)

### 3.5 OWI Bridge Components

LAMB integrates with Open WebUI through dedicated bridge classes in `/backend/lamb/owi_bridge/`:

| Component | File | Purpose |
|-----------|------|---------|
| `OwiDatabaseManager` | `owi_database.py` | Direct database access to OWI SQLite |
| `OwiUserManager` | `owi_users.py` | User operations (create, verify, get token) |
| `OwiGroupManager` | `owi_group.py` | Group operations for LTI access control |
| `OwiModelManager` | `owi_model.py` | Model (assistant) registration |

**Key Operations:**
- Create OWI user when LAMB creator user is created
- Create OWI user for LTI creator users (with random password)
- Verify passwords against OWI auth table (bcrypt)
- Generate JWT tokens for authenticated sessions (including LTI creator logins)
- Create/update OWI groups for published assistants
- Register assistants as OWI models

> **Security Note:** OWI router endpoints (`/v1/OWI/*`) were removed (Dec 2025) for security. OWI operations are now internal service classes only.

---

## 4. Data Architecture

### 4.1 Database Overview

| Database | File | Purpose |
|----------|------|---------|
| **LAMB DB** | `$LAMB_DB_PATH/lamb_v4.db` | Assistants, users, orgs |
| **OWI DB** | `$OWI_DATA_PATH/webui.db` | Auth, chat history |
| **ChromaDB** | `$OWI_DATA_PATH/vector_db/` | KB document vectors |

### 4.2 LAMB Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `organizations` | Organization/tenant records | id, slug, name, config (JSON), is_system |
| `organization_roles` | User-organization membership | organization_id, user_id, role |
| `Creator_users` | User accounts | email, name, user_type, organization_id, enabled, auth_provider, lti_user_id |
| `assistants` | Assistant definitions | name, owner, system_prompt, metadata*, published |
| `assistant_shares` | Assistant sharing records | assistant_id, shared_with_user_id |
| `kb_registry` | Knowledge Base metadata | kb_id, owner_user_id, is_shared |
| `lti_users` | LTI launch user mappings | assistant_id, user_email |
| `lti_creator_keys` | LTI Creator OAuth credentials | organization_id, consumer_key, consumer_secret |
| `shared_prompt_templates` | Reusable prompt templates | name, template, organization_id |
| `usage_logs` | Usage tracking and analytics | organization_id, assistant_id, usage_data (JSON) |

> **Note:** The `assistants.metadata` field is stored in the `api_callback` column (legacy naming).

### 4.3 Field Mapping Gotcha

**Critical:** The `assistants` table has a field mapping that can confuse developers:

| Application Code | Database Column | Why |
|-----------------|-----------------|-----|
| `assistant.metadata` | `api_callback` | Legacy naming, avoids schema migration |

The `pre_retrieval_endpoint`, `post_retrieval_endpoint`, and `RAG_endpoint` columns are **DEPRECATED** and always empty.

### 4.4 Key JSON Structures

**Organization Config:**
```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "default_model": "gpt-4o-mini",
          "models": ["gpt-4o", "gpt-4o-mini"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "models": ["llama3.1:latest"]
        }
      },
      "global_default_model": {"provider": "openai", "model": "gpt-4o"},
      "small_fast_model": {"provider": "openai", "model": "gpt-4o-mini"}
    }
  },
  "kb_server": {"url": "http://localhost:9090", "api_key": "..."},
  "features": {
    "signup_enabled": false,
    "signup_key": "org-signup-key",
    "sharing_enabled": true
  }
}
```

**Assistant Metadata:**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag",
  "capabilities": {"vision": true}
}
```

### 4.5 Open WebUI Tables (Key)

| Table | Purpose |
|-------|---------|
| `user` | End-user accounts (username, role, api_key) |
| `auth` | Passwords (bcrypt hashed) and sessions |
| `model` | LLM models (published assistants use ID: `lamb_assistant.{id}`) |
| `group` | User groups for access control |
| `chat` | Chat history with JSON messages |

---

## 5. Authentication & Authorization

### 5.1 Authentication Flow

```
┌─────────┐   POST /creator/login    ┌──────────────┐   Verify    ┌─────┐
│ Browser │ ────────────────────────►│   Creator    │ ───────────►│ OWI │
│         │   email + password       │  Interface   │  password   │     │
└─────────┘                          └──────────────┘             └─────┘
     ▲                                      │                         │
     │                                      │                         │
     │      200 OK {token, user_type}       │◄────────────────────────┘
     │◄─────────────────────────────────────┤       JWT token
     │                                      │
     │  Subsequent: Authorization: Bearer   │
     ├─────────────────────────────────────►│
```

**User Types:**
- `creator` — Full access to creator interface
- `lti_creator` — Creator user authenticated via LTI (same permissions as creator, password cannot be changed; can be promoted to org admin by a system admin)
- `end_user` — Redirected to Open WebUI only (no creator access)

**Auth Providers:**
- `password` — Standard email/password authentication (default)
- `lti_creator` — LTI-based authentication for creator users

### 5.2 Token Validation

Every authenticated endpoint:
1. Extracts `Authorization: Bearer {token}` header
2. Calls `get_creator_user_from_token()` helper
3. Validates token against OWI database
4. Verifies user exists in LAMB Creator_users table
5. Enriches the returned dict with the user's OWI `role` (e.g. `"admin"` or `"user"`)
6. Returns user object or raises 401

### 5.3 Authorization Levels

**Organization Roles:**
| Role | Permissions |
|------|-------------|
| `owner` | Full control over organization |
| `admin` | Manage settings and members |
| `member` | Create assistants within org |

**Admin Detection:**
```python
def is_admin_user(user_or_auth_header):
    # Accepts a creator_user dict (with 'role' field from OWI) or an auth header string.
    # Returns True when the user's OWI role == 'admin'.
```

### 5.4 API Key Authentication

For `/v1/chat/completions` and `/v1/models`:
- Uses `LAMB_BEARER_TOKEN` environment variable
- Format: `Authorization: Bearer {LAMB_BEARER_TOKEN}`
- Default: `0p3n-w3bu!` (change in production!)

### 5.5 Security Considerations

**Password Storage:**
- Passwords stored in OWI `auth` table
- Hashed with bcrypt (cost factor 12)
- LAMB never stores passwords directly

**JWT Tokens:**
- Generated by OWI on successful login
- Validated against OWI database on each request
- Include user ID and expiration

**API Security:**
- `LAMB_BEARER_TOKEN` for completion endpoints
- User tokens for creator interface endpoints
- Organization isolation enforced at data layer

### 5.6 Error Handling

**Standard Error Response:**
```json
{
  "detail": "Human-readable error message"
}
```

**Common Status Codes:**

| Code | Meaning | Example |
|------|---------|---------|
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | User doesn't have permission |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate resource (e.g., assistant name) |
| 422 | Unprocessable | Invalid request data |
| 500 | Server Error | Internal error |

---

## 6. Completion Pipeline

### 6.1 Request Flow

```
POST /v1/chat/completions
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ 1. Validate API key                                               │
│ 2. Load assistant from database                                   │
│ 3. Parse plugin config from assistant.metadata                    │
│ 4. Load plugins (RAG, PPS, Connector)                            │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ RAG Processor │───►│ Prompt        │───►│  Connector    │
│               │    │ Processor     │    │               │
│ Query KB      │    │ Augment msgs  │    │ Call LLM      │
└───────────────┘    └───────────────┘    └───────────────┘
                                                  │
                                                  ▼
                                          ┌───────────────┐
                                          │ LLM Provider  │
                                          │ (OpenAI/etc)  │
                                          └───────────────┘
                                                  │
                                                  ▼
                                          Stream/Return Response
```

### 6.2 Plugin Processing Stages

| Stage | Plugin Type | Purpose |
|-------|-------------|---------|
| 1. Before | RAG Processor | Query KB, get context |
| 2. Before | Prompt Processor | Transform/augment messages |
| 3. Execute | Connector | Call LLM provider |
| 4. After | (Optional) | Post-processing, logging |

### 6.3 Organization Config Resolution

When resolving LLM configuration:
1. **Explicit** in request → use that
2. **Assistant metadata** → use that
3. **Organization global_default_model** → use that
4. **Provider default_model** → use that
5. **First available model** → use that

```python
class OrganizationConfigResolver:
    def get_provider_config(self, provider_name: str) -> Dict
    def get_global_default_model_config(self) -> Dict
    def get_small_fast_model_config(self) -> Dict
    def get_kb_server_config(self) -> Dict
```

### 6.4 Plugin System

**Plugin Types & Locations:**

| Type | Directory | Function Name |
|------|-----------|---------------|
| Prompt Processor | `lamb/completions/pps/` | `prompt_processor()` |
| Connector | `lamb/completions/connectors/` | `llm_connect()` |
| RAG Processor | `lamb/completions/rag/` | `rag_processor()` |

**Available Plugins:**

| Prompt Processors | Connectors | RAG Processors |
|-------------------|------------|----------------|
| `simple_augment` | `openai` | `simple_rag` |
| | `ollama` | `single_file_rag` |
| | `anthropic` | `no_rag` |
| | `banana_img`* | |
| | `bypass` | |

> *`banana_img` uses Google Gen AI (Gemini) for image generation with intelligent routing (title requests → GPT-4o-mini, image requests → Gemini).

**Creating a Custom Plugin:**

1. Create file in appropriate directory (e.g., `lamb/completions/pps/my_pps.py`)
2. Implement required function signature:

```python
# Prompt Processor
def prompt_processor(request: Dict, assistant=None, rag_context=None) -> List[Dict]:
    messages = []
    # ... transform messages
    return messages

# Connector
async def llm_connect(messages: list, stream: bool, body: Dict, 
                      llm: str, assistant_owner: str):
    # ... call LLM
    return response  # or async generator if streaming

# RAG Processor
def rag_processor(messages: List[Dict], assistant=None) -> Dict:
    # ... query KB
    return {"context": "...", "sources": [...]}
```

3. Plugin is auto-loaded at runtime — no registration needed
4. Configure assistant metadata to use it

### 6.5 Connection Pooling

LLM connectors use **shared HTTP client pools** to avoid creating new TCP connections on every request. Without pooling, concurrent users exhaust OS-level connection resources and the system becomes unresponsive.

**OpenAI Connector** (`openai.py`):
- Shared `AsyncOpenAI` clients cached by `(api_key, base_url)`
- A single client is created on the first request for each credential pair and reused for all subsequent requests
- Explicit timeouts configured via environment variables

**Ollama Connector** (`ollama.py`):
- Shared `aiohttp.ClientSession` instances cached by `base_url`
- Each session uses a `TCPConnector` with configurable connection limits and keepalive
- Sessions are recreated transparently if closed

**Configuration** (via `backend/.env`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_REQUEST_TIMEOUT` | Total request timeout for OpenAI calls (seconds) | `120` |
| `LLM_CONNECT_TIMEOUT` | TCP connection establishment timeout (seconds) | `10` |
| `LLM_MAX_CONNECTIONS` | Max concurrent connections per client pool | `50` |
| `OLLAMA_REQUEST_TIMEOUT` | Total request timeout for Ollama calls (seconds) | `120` |

> **Performance:** With connection pooling and a single uvicorn worker, the system handles 50+ concurrent users at 100% success rate with a median response time under 5 seconds against real OpenAI models.

### 6.6 Streaming Responses

For streaming completions (`"stream": true`), responses use Server-Sent Events (SSE):

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Content-Type:** `text/event-stream`

### 6.7 Multimodal Support

LAMB supports images via OpenAI's vision API format:

```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "What's in this image?"},
      {"type": "image_url", "image_url": {"url": "https://..."}}
    ]
  }]
}
```

**Requirements:**
- Assistant must have `capabilities.vision = true` in metadata
- Supported formats: JPEG, PNG, GIF, WebP
- Supported sources: HTTP URLs, Base64 data URLs

---

## 7. Organizations & Multi-Tenancy

### 7.1 Organization Structure

```
System Organization (slug: "system", is_system: true)
    │
    ├── Organization A (slug: "engineering")
    │   ├── Users (with roles: owner, admin, member)
    │   ├── Assistants
    │   └── Knowledge Bases
    │
    └── Organization B (slug: "physics")
        ├── Users
        ├── Assistants
        └── Knowledge Bases
```

**Isolation:**
- Each org has independent LLM provider configs
- Users belong to one organization
- Assistants and KBs scoped to organization
- Signup keys are org-specific

### 7.2 System Organization

The "system" organization is special:
- `is_system = true`
- Cannot be deleted
- Fallback configuration source
- System admins are members with admin role

### 7.3 Organization Creation

Organizations can be created with or without an admin:

1. System admin creates org via `/creator/admin/organizations/enhanced`
2. **With admin:** A user from the system org is moved to the new org and assigned the admin role
3. **Without admin:** Org is created with no admin; a system admin can promote a member later via the Members panel

### 7.4 Organization Signup Flow

1. Admin creates org with `signup_enabled: true` and `signup_key`
2. User enters email, name, password, and signup key
3. System matches key to organization
4. User created in that org with "member" role

### 7.5 Key Organization APIs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/creator/admin/organizations` | List organizations |
| POST | `/creator/admin/organizations/enhanced` | Create org (admin optional) |
| PUT | `/creator/admin/organizations/{slug}/config` | Update config |
| PUT | `/creator/admin/organizations/{slug}/members/{user_id}/role` | Promote/demote member (sys admin only) |
| GET | `/lamb/v1/organizations/{slug}/members` | List members |

---

## 8. Feature Integration

### 8.1 Knowledge Base System

**Architecture:**
```
Frontend → Creator Interface → KB Server → ChromaDB
```

**Key Operations:**
1. **Create:** `POST /creator/knowledgebases/create`
2. **Upload:** `POST /creator/knowledgebases/{id}/upload`
3. **Query:** `GET /creator/knowledgebases/{id}/query`

**Collection Naming:** `{org_slug}_{user_email}_{collection_name}`

**KB Sharing:**
- Toggle `is_shared` to share with organization
- Shared KBs visible to all org members (read-only)
- Protection prevents unsharing when KB is in use by other users' assistants

**RAG Integration:**
- Assistant references KB IDs in `RAG_collections`
- RAG processor queries KBs during completion
- Context injected into system prompt

### 8.2 LTI Integration

LAMB supports three types of LTI integration:
1. **Unified LTI** — Multi-assistant activities configured by instructors (recommended, new in v2.2)
2. **Legacy Student LTI** — Students access a single published assistant via LTI
3. **LTI Creator** — Educators access the Creator Interface via LTI (new in v2.1)

> For full details, see [lti_landscape.md](./lti_landscape.md) and [projects/lti_unified_activity_design.md](./projects/lti_unified_activity_design.md).

#### 8.2.1 Unified LTI (Multi-Assistant Activities) — Recommended

**Purpose:** One LTI tool for the entire LAMB instance. Instructors configure which published assistants are available per activity. Students see multiple assistants in one activity. Instructors get a **dashboard** with usage stats and optional anonymized chat transcript review.

**Global credentials:** Set via `LTI_GLOBAL_CONSUMER_KEY`/`LTI_GLOBAL_SECRET` in `.env`, or overridden by admin via the database.

**Launch Flow:**
```
User clicks LTI link in LMS
    → LMS sends OAuth 1.0 signed POST to /lamb/v1/lti/launch
    → LAMB validates signature with global key/secret
    → LAMB checks resource_link_id:
        │
        ├── Activity NOT configured:
        │     ├── Instructor → Identify as Creator user → Setup page
        │     │     (pick assistants, name, chat visibility option)
        │     │     → First instructor becomes OWNER
        │     │     → Redirect to Instructor Dashboard
        │     └── Student → "Not set up yet" waiting page
        │
        └── Activity IS configured:
              ├── Instructor → INSTRUCTOR DASHBOARD
              │     (stats, student access log, chat transcripts if enabled)
              │     • [Open Chat] → OWI redirect
              │     • [Manage Assistants] → reconfigure (owner only)
              │
              └── Student:
                    ├── Chat visibility ON + no consent yet → Consent page
                    │     → Student accepts → redirect to OWI
                    └── Otherwise → direct OWI redirect
```

**Key Endpoints:**
- `POST /lamb/v1/lti/launch` — Main LTI entry point (routes to setup, dashboard, consent, or OWI)
- `GET /lamb/v1/lti/setup` — Instructor setup page (first-time or reconfigure)
- `POST /lamb/v1/lti/configure` — Save activity configuration
- `GET /lamb/v1/lti/dashboard` — Instructor dashboard (HTML) with AJAX data endpoints:
  - `GET /dashboard/stats`, `/dashboard/students`, `/dashboard/chats`, `/dashboard/chats/{id}`
- `GET /lamb/v1/lti/consent` + `POST` — Student consent page for chat visibility
- `GET /lamb/v1/lti/enter-chat` — Dashboard → OWI redirect for instructors
- `GET /lamb/v1/lti/info` — LTI tool configuration info

**Key Design Decisions:**
- Activities are bound to one organization (no cross-org mixing)
- **Activity ownership:** first instructor to configure = owner (can manage assistants, toggle chat visibility)
- **Instructor dashboard:** any instructor sees stats; only owner can reconfigure
- **Chat visibility:** opt-in per activity at creation; students must consent on first access; all transcripts anonymized ("Student 1", "Student 2", ...)
- Student identity is per `resource_link_id` (each LTI placement = separate identity)
- Org admins can manage activities: `GET/PUT /creator/admin/lti-activities`
- Global credentials managed by system admin: `GET/PUT /creator/admin/lti-global-config`

**Database Tables:**
- `lti_global_config` — Global consumer key/secret (singleton)
- `lti_activities` — Activity records (resource_link_id → org, OWI group, **owner**, **chat_visibility_enabled**)
- `lti_activity_assistants` — Junction: assistants per activity
- `lti_activity_users` — Student access tracking (**owi_user_id**, **consent_given_at**, **last_access_at**, **access_count**)
- `lti_identity_links` — Maps LMS identities to Creator users

#### 8.2.2 Legacy Student LTI (Single Published Assistant)

> **Note:** This is the older approach. Consider using Unified LTI (§8.2.1) for new deployments.

**Publishing Flow:**
```
Creator publishes assistant
    → Create OWI Group
    → Register as OWI Model
    → Generate LTI consumer key/secret
    → Return LTI launch URL
```

**LTI Launch Flow:**
```
Student clicks LTI link in LMS
    → LMS sends OAuth-signed POST
    → LAMB validates signature
    → Create/get OWI user
    → Add user to assistant's group
    → Generate JWT token
    → Redirect to OWI chat
```

**Key Endpoints:**
- `POST /lamb/v1/lti_users/lti` — Student LTI launch handler

**LTI Parameters Extracted:**
- `ext_user_username` / `user_id` — Username for email generation
- `oauth_consumer_key` — Published assistant name (identifies the assistant)
- Uses global `LTI_SECRET` env var for OAuth validation

#### 8.2.3 LTI Creator (Creator Interface Access)

**Purpose:** Allow educators to access the LAMB Creator Interface directly from their LMS without separate login credentials.

**Setup Flow:**
```
1. Organization admin configures LTI Creator in org settings
    → Sets OAuth consumer key (format: {org_id}_{custom_name})
    → Sets OAuth consumer secret
2. Admin configures LTI activity in LMS with these credentials
3. Educators click LTI link → land in Creator Interface
```

**LTI Creator Launch Flow:**
```
Educator clicks LTI link in LMS
    → LMS sends OAuth 1.0 signed POST to /lamb/v1/lti_creator/launch
    → LAMB validates OAuth signature
    → Extract organization from consumer key prefix
    → Identify user by LMS user_id (stable across sessions)
    → Create LTI creator user if first launch (or fetch existing)
    → Create OWI user with random password
    → Generate JWT token
    → Redirect to Creator Interface with token in URL
    → Frontend stores token and authenticates user
```

**Key Endpoints:**
- `POST /lamb/v1/lti_creator/launch` — LTI Creator launch handler
- `GET /lamb/v1/lti_creator/info` — LTI Creator configuration info

**LTI Creator User Characteristics:**
| Attribute | Value |
|-----------|-------|
| `user_type` | `creator` |
| `auth_provider` | `lti_creator` |
| `organization_role` | `member` (default; can be promoted to admin by a system admin) |
| Password changeable | No (random password, unused) |
| Can share assistants | Yes (same as regular creator) |
| Can create KBs | Yes |
| Can publish assistants | Yes |

**User Identification:**
- Users identified by `lti_user_id` from LMS (stable across launches)
- Email format: `lti_creator_{org_slug}_{lti_user_id}@lamb-lti.local`
- Same user can launch from different LTI consumer instances

**Organization Admin Configuration:**
```json
{
  "lti_creator": {
    "oauth_consumer_key": "2_my_lti_creator",
    "oauth_consumer_secret": "secret123"
  }
}
```

**Database Tables:**
- `lti_creator_keys` — Stores OAuth credentials per organization
- `Creator_users.lti_user_id` — LMS user identifier
- `Creator_users.auth_provider` — Set to `lti_creator`

### 8.3 Assistant Sharing

**Two-Level Permission System:**

| Org `sharing_enabled` | User `can_share` | Result |
|----------------------|------------------|--------|
| ✅ | ✅ | Can share |
| ✅ | ❌ | Cannot share |
| ❌ | ✅ | Cannot share |
| ❌ | ❌ | Cannot share |

**Access Levels:**

| Action | Owner | Shared User |
|--------|-------|-------------|
| View/Chat | ✅ | ✅ |
| Edit/Delete | ✅ | ❌ |
| Publish | ✅ | ❌ |
| Manage sharing | ✅ | ❌ |

**Key Endpoints:**
- `GET /lamb/v1/assistant-sharing/check-permission`
- `GET /lamb/v1/assistant-sharing/shares/{id}`
- `PUT /lamb/v1/assistant-sharing/shares/{id}`

### 8.4 Chat Analytics

**Purpose:** Provide assistant owners insights into usage.

**Features:**
- Chat list with filtering and pagination
- Full conversation detail view
- Usage statistics (total chats, unique users, messages)
- Activity timeline (configurable period)
- Privacy-respecting anonymization (default on)

**Key Endpoints:**
- `GET /creator/analytics/assistant/{id}/chats`
- `GET /creator/analytics/assistant/{id}/chats/{chat_id}`
- `GET /creator/analytics/assistant/{id}/stats`
- `GET /creator/analytics/assistant/{id}/timeline`

> See [chat_analytics_project.md](./chat_analytics_project.md) for implementation details.

### 8.5 User Blocking

**Purpose:** Disable accounts without deleting data.

**Behavior:**
- Set `Creator_users.enabled = false`
- Blocked users get 403 on login
- Published assistants remain accessible
- Shared resources remain functional

**Key Endpoints:**
- `PUT /creator/admin/users/{id}/disable`
- `PUT /creator/admin/users/{id}/enable`
- `POST /creator/admin/users/disable-bulk`

### 8.6 Admin User Management

**User Type Display in Admin UI:**

The admin user management panel identifies users by type with color-coded badges:

| User Type | Badge | Criteria |
|-----------|-------|----------|
| Admin | Red | OWI role = 'admin' |
| Org Admin | Purple | organization_role IN ('admin', 'owner') |
| LTI Creator | Blue | auth_provider = 'lti_creator' |
| Creator | Green | Default for creator users |
| End User | Gray | user_type = 'end_user' |

**LTI Creator User Management:**
- Displayed with blue "LTI Creator" badge
- Filter dropdown includes "LTI Creator" option
- Password change button disabled (LTI users have random passwords)
- Can be enabled/disabled by admin
- Can be promoted to organization admin by a system admin

---

## 9. Frontend Architecture

The project uses Svelte 5 , with Javascript and JSDOC ( NOT Typescript !!! repeat NOT Typescript!!! )
### 9.1 Structure

```
/frontend/svelte-app/
├── src/
│   ├── routes/                  # SvelteKit pages
│   │   ├── +layout.svelte       # Root layout
│   │   ├── +page.svelte         # Home
│   │   ├── assistants/          # Assistant management
│   │   ├── knowledge-bases/     # KB management
│   │   ├── admin/               # System admin
│   │   └── org-admin/           # Org admin
│   │
│   └── lib/
│       ├── components/          # UI components
│       ├── services/            # API clients
│       ├── stores/              # Svelte stores
│       └── config.js            # Runtime config
```

### 9.2 Key Routes

| Route | Purpose |
|-------|---------|
| `/` | Home (redirects to /assistants) |
| `/assistants` | Assistant list and management |
| `/knowledge-bases` | KB list and management |
| `/admin` | System admin panel |
| `/org-admin` | Organization admin |

### 9.3 UX Patterns (Critical)

#### Form Dirty State Tracking

**Problem:** Svelte 5's reactivity can overwrite user edits on prop reference changes.

**Solution:**
```javascript
let formDirty = $state(false);
let previousId = $state(null);

// Mark dirty on user input
function handleFieldChange() {
    formDirty = true;
}

// Only repopulate on meaningful changes
$effect(() => {
    if (data?.id !== previousId) {
        if (!formDirty) {
            populateFormFields(data);
            previousId = data.id;
        }
    }
});

// Reset on save
async function handleSave() {
    await saveData();
    formDirty = false;
}
```

#### Async Data Loading Race Conditions

**⚠️ CRITICAL:** Setting selections before options load causes silent failures.

**Problem:**
```javascript
// ❌ BAD - Race condition
selectedKnowledgeBases = ["abc123"];  // Set selection
fetchKnowledgeBases();                 // Load async - happens LATER
// bind:group can't match to empty list!
```

**Solution:**
```javascript
// ✅ CORRECT - Load then select
async function populateFormFields(data) {
    await fetchKnowledgeBases();  // Wait for options
    selectedKnowledgeBases = data.RAG_collections?.split(',') || [];
}
```

#### Preventing Spurious Repopulation

**Problem:** Reference changes (not data changes) trigger form reset.

**Solution:** Use ID-based change detection:
```javascript
$effect(() => {
    const idChanged = data?.id !== previousId;
    if (idChanged) {
        populateFormFields(data);
        previousId = data.id;
    }
    // Skip reference-only changes
});
```

### 9.4 Service Layer Pattern

```javascript
// lib/services/assistantService.js
import { getApiUrl } from '$lib/config';

export async function getAssistants(token) {
    const response = await fetch(getApiUrl('/creator/assistant/list'), {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.json();
}
```

### 9.5 Runtime Configuration

```javascript
// static/config.js
window.LAMB_CONFIG = {
    api: {
        lambServer: 'http://localhost:9099',
        owebuiServer: 'http://localhost:8080'
    }
};
```

---

## 10. Development & Deployment

### 10.1 Quick Start

```bash
# Clone
git clone https://github.com/Lamb-Project/lamb.git
cd lamb

# Setup
./scripts/setup.sh

# Start all services
docker-compose up -d

# Access
# - Frontend: http://localhost:5173
# - Backend: http://localhost:9099
# - Open WebUI: http://localhost:8080
# - KB Server: http://localhost:9090
```

### 10.2 Development Workflow

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 9099
```

**Frontend:**
```bash
cd frontend/svelte-app
npm install
npm run dev
```

### 10.3 Key Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LAMB_DB_PATH` | LAMB database directory | `.` |
| `OWI_DATA_PATH` | OWI data directory | - |
| `LAMB_BEARER_TOKEN` | API key for completions | `0p3n-w3bu!` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `KB_SERVER_URL` | KB server address | `http://localhost:9090` |
| `OWI_BASE_URL` | OWI internal URL | `http://openwebui:8080` |
| `OWI_PUBLIC_BASE_URL` | OWI public URL | - |
| `LTI_GLOBAL_CONSUMER_KEY` | Unified LTI consumer key | `lamb` |
| `LTI_GLOBAL_SECRET` | Unified LTI shared secret | (falls back to `LTI_SECRET`) |
| `LTI_SECRET` | Legacy student LTI secret | - |
| `LLM_REQUEST_TIMEOUT` | OpenAI request timeout (seconds) | `120` |
| `LLM_CONNECT_TIMEOUT` | TCP connect timeout (seconds) | `10` |
| `LLM_MAX_CONNECTIONS` | Max connections per client pool | `50` |
| `OLLAMA_REQUEST_TIMEOUT` | Ollama request timeout (seconds) | `120` |

> See [ENVIRONMENT_VARIABLES.md](../backend/ENVIRONMENT_VARIABLES.md) for complete list.

### 10.4 Database Migrations

LAMB uses automatic migrations on startup. To add a new field:

1. Add migration code in `lamb/database_manager.py` → `run_migrations()`:
```python
def run_migrations(self):
    cursor.execute("PRAGMA table_info(Creator_users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'my_new_field' not in columns:
        cursor.execute("""
            ALTER TABLE Creator_users 
            ADD COLUMN my_new_field TEXT DEFAULT ''
        """)
```

2. Migrations run automatically on backend startup
3. Designed for backward compatibility (always use DEFAULT values)

### 10.5 Testing

**Test Locations:**
- `/testing/playwright/` — E2E tests with Playwright
- `/testing/unit-tests/` — Python unit tests
- `/testing/curls/` — API test scripts
- `/testing/load_test_completions.py` — Concurrent load test for completions endpoint

**Running Playwright Tests:**
```bash
cd testing/playwright
npm install
npx playwright test
```

**Running Load Tests:**
```bash
# Test with 30 concurrent users
python3 testing/load_test_completions.py --users 30 --url http://localhost:9099

# Test with 50 concurrent users and custom timeout
python3 testing/load_test_completions.py --users 50 --url http://localhost:9099 --timeout 180
```

### 10.6 Production Checklist

- [ ] Change `LAMB_BEARER_TOKEN` from default
- [ ] Configure SSL/TLS via Caddy or reverse proxy
- [ ] Set up database backups
- [ ] Configure organization LLM API keys
- [ ] Review logging levels (`GLOBAL_LOG_LEVEL=WARNING`)
- [ ] Set up monitoring

---

## 11. Logging System

### 11.1 Centralized Configuration

All logging uses the centralized module at `lamb/logging_config.py`:

```python
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")
logger.info("Processing request")
```

### 11.2 Environment Variables

**Global:**
```bash
GLOBAL_LOG_LEVEL=WARNING  # Default for all components
```

**Component-Specific (optional overrides):**
```bash
MAIN_LOG_LEVEL=INFO
API_LOG_LEVEL=WARNING
DB_LOG_LEVEL=DEBUG
RAG_LOG_LEVEL=INFO
EVALUATOR_LOG_LEVEL=WARNING
OWI_LOG_LEVEL=WARNING
```

### 11.3 Log Levels

| Level | Use For |
|-------|---------|
| `DEBUG` | Detailed debugging info |
| `INFO` | General operational events |
| `WARNING` | Unexpected but handled situations |
| `ERROR` | Errors requiring attention |
| `CRITICAL` | System failures |

### 11.4 Configuration Examples

**Development:**
```bash
GLOBAL_LOG_LEVEL=DEBUG
```

**Production:**
```bash
GLOBAL_LOG_LEVEL=WARNING
```

**Debugging specific component:**
```bash
GLOBAL_LOG_LEVEL=WARNING
DB_LOG_LEVEL=DEBUG
```

---

## 12. Quick Reference

### 12.1 "I Want To..." Directory

| Task | Where to Look |
|------|---------------|
| Add API endpoint | `creator_interface/` or `lamb/` routers |
| Create plugin | `lamb/completions/{pps,connectors,rag}/` |
| Add database field | `lamb/database_manager.py` → `run_migrations()` |
| Add frontend page | `frontend/svelte-app/src/routes/` |
| Configure logging | `lamb/logging_config.py` + env vars |
| Understand completion flow | `lamb/completions/main.py` |
| Debug OWI integration | `lamb/owi_bridge/` |

### 12.2 Key Files by Task

| Task | Primary Files |
|------|---------------|
| **Auth** | `creator_interface/main.py`, `lamb/owi_bridge/owi_users.py` |
| **Assistants** | `creator_interface/assistant_router.py`, `lamb/assistant_router.py` |
| **Completions** | `lamb/completions/main.py`, `lamb/completions/connectors/` |
| **KBs** | `creator_interface/knowledges_router.py`, `kb_server_manager.py` |
| **Orgs** | `creator_interface/organization_router.py`, `lamb/organization_router.py` |
| **LTI (Unified)** | `lamb/lti_router.py`, `lamb/lti_activity_manager.py` |
| **LTI (Student legacy)** | `lamb/lti_users_router.py` |
| **LTI (Creator)** | `lamb/lti_creator_router.py` |
| **Frontend** | `frontend/svelte-app/src/routes/`, `src/lib/components/` |

### 12.3 Common Patterns

**Adding a Protected Endpoint:**
```python
@router.get("/my-endpoint")
async def my_endpoint(request: Request):
    auth_header = request.headers.get("Authorization")
    creator_user = get_creator_user_from_token(auth_header)
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Your logic here
    return {"success": True}
```

**Admin-Only Endpoint:**
```python
@router.get("/admin/my-endpoint")
async def admin_endpoint(request: Request):
    auth_header = request.headers.get("Authorization")
    creator_user = get_creator_user_from_token(auth_header)
    if not creator_user or not is_admin_user(creator_user):
        raise HTTPException(status_code=403, detail="Admin required")
    
    # Admin logic here
```

**Using Organization Config:**
```python
from lamb.completions.organization_config import OrganizationConfigResolver

resolver = OrganizationConfigResolver(user_email)
openai_config = resolver.get_provider_config("openai")
api_key = openai_config.get("api_key")
```

### 12.4 API Quick Reference

**Auth:**
| POST `/creator/login` | POST `/creator/signup` | GET `/creator/user/current` |

**Assistants:**
| GET `/creator/assistant/list` | POST `/creator/assistant/create` | PUT `/creator/assistant/update` |

**Knowledge Bases:**
| GET `/creator/knowledgebases/user` | POST `/creator/knowledgebases/create` | POST `/{id}/upload` |

**Completions:**
| GET `/v1/models` | POST `/v1/chat/completions` |

**Admin:**
| GET `/creator/admin/users` | PUT `/creator/admin/users/{id}/status` |

---

## 13. Security Summary

### Data Isolation
- Organizations have independent data namespaces
- Users can only access resources in their organization
- Cross-organization access is prevented at data layer

### Authentication Security
- Passwords hashed with bcrypt (cost 12)
- JWT tokens with expiration
- Token validation on every request

### API Security
- LAMB_BEARER_TOKEN for external completion API
- User tokens for creator interface
- Rate limiting via reverse proxy (recommended)

### Best Practices
- Change default `LAMB_BEARER_TOKEN` in production
- Use HTTPS in production (via Caddy/nginx)
- Rotate organization API keys periodically
- Review user access regularly

---

## 14. Troubleshooting

### Common Issues

**"401 Unauthorized" on all requests:**
- Check token is valid and not expired
- Verify user exists in both OWI and LAMB databases

**Assistant not appearing in OWI:**
- Check assistant is published (`published = true`)
- Verify OWI model was created (`lamb_assistant.{id}`)
- Check group membership

**KB queries returning no results:**
- Verify documents were uploaded and processed
- Check collection ID is correct in assistant's `RAG_collections`
- Test query directly against KB server

**LTI launch failing (Student):**
- Verify OAuth signature matches
- Check consumer key/secret match
- Ensure `custom_assistant_id` is set

**LTI Creator launch failing:**
- Verify consumer key format: `{org_id}_{name}`
- Check OAuth signature validation in backend logs
- Ensure organization has `lti_creator` config set
- Check that organization is not the system organization

**Frontend not loading:**
- Check `static/config.js` has correct API URLs
- Verify backend is running on expected port
- Check browser console for CORS errors

### Debug Logging

Enable verbose logging:
```bash
GLOBAL_LOG_LEVEL=DEBUG
DB_LOG_LEVEL=DEBUG
API_LOG_LEVEL=DEBUG
```

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md) | Quick navigation guide |
| [lamb_architecture.md](./lamb_architecture.md) | Full detailed reference |
| [chat_analytics_project.md](./chat_analytics_project.md) | Analytics implementation |
| [ENVIRONMENT_VARIABLES.md](../backend/ENVIRONMENT_VARIABLES.md) | All env vars |
| [prd.md](./prd.md) | Product requirements |
| [deployment.apache.md](./deployment.apache.md) | Apache deployment |
| [features/](./features/) | Detailed feature documentation |

---

## Support

- **GitHub:** https://github.com/Lamb-Project/lamb
- **Website:** https://lamb-project.org

---

*Maintainers: LAMB Development Team*  
*Last Updated: February 11, 2026*
*Version: 2.3*

