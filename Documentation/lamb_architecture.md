# LAMB Architecture Documentation

**Version:** 3.0
**Last Updated:** December 27, 2025  
**Target Audience:** Developers, DevOps Engineers, AI Agents, Technical Architects

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [System Components](#3-system-components)
4. [Data Architecture](#4-data-architecture)
5. [API Architecture](#5-api-architecture)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [Completion Pipeline](#7-completion-pipeline)
8. [Organization & Multi-Tenancy](#8-organization--multi-tenancy)
9. [Knowledge Base Integration](#9-knowledge-base-integration)
   - [9.7 Assistant Sharing](#97-assistant-sharing)
10. [LTI Integration](#10-lti-integration)
11. [Plugin Architecture](#11-plugin-architecture)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Deployment Architecture](#13-deployment-architecture)
14. [Development Workflow](#14-development-workflow)
15. [End User Feature](#15-end-user-feature)
16. [User Blocking Feature](#16-user-blocking-feature)
17. [Chat Analytics Feature](#17-chat-analytics-feature)
18. [Centralized Logging System](#18-centralized-logging-system)
19. [Frontend UX Patterns & Best Practices](#19-frontend-ux-patterns--best-practices)
20. [API Reference](#20-api-reference)
21. [File Structure](#21-file-structure-summary)

---

## 1. System Overview

### 1.1 High-Level Architecture

LAMB is a distributed system consisting of four main services:

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
│                            │                  │                  │
│                            ▼                  ▼                  │
│                    ┌──────────────┐  ┌──────────────┐          │
│                    │  Knowledge   │  │   ChromaDB   │          │
│                    │  Base Server │  │   (Vectors)  │          │
│                    │  :9090       │  │              │          │
│                    └──────────────┘  └──────────────┘          │
│                                                                   │
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
| **Frontend** | Creator UI, Admin panels | Svelte 5, SvelteKit | 5173 (dev) / served by backend (prod) |
| **Backend** | Core API, Assistant management, Completions | FastAPI, Python 3.11 | 9099 |
| **Open WebUI** | Authentication, Model management, Chat UI | FastAPI, Python | 8080 |
| **Knowledge Base Server** | Document processing, Vector search | FastAPI, ChromaDB | 9090 |

---

## 2. Architecture Principles

### 2.1 Design Principles

1. **Privacy-First:** All user data and assistant configurations remain within institutional control
2. **Modular:** Components can be updated or replaced independently
3. **Extensible:** Plugin architecture for LLM connectors, prompt processors, and RAG
4. **Multi-Tenant:** Organizations isolated with independent configurations
5. **Standards-Compliant:** OpenAI API compatibility, LTI 1.1 compliance
6. **Educator-Centric:** Non-technical users can create sophisticated AI assistants

### 2.2 Architectural Patterns

- **Layered Architecture:** Creator Interface API → LAMB Core API → Database/External Services
- **Proxy Pattern:** Creator Interface acts as enhanced proxy to LAMB Core
- **Plugin Architecture:** Dynamically loaded processors and connectors
- **Repository Pattern:** Database managers encapsulate data access
- **Service Layer:** Business logic separated from HTTP layer

---

## 3. System Components

### 3.1 Backend Architecture

#### 3.1.1 Dual API Design

LAMB employs a **two-tier API architecture**:

```
┌───────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                          │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────────┐
│         Creator Interface API (/creator)                       │
│         - User authentication & session management             │
│         - File operations (upload/download)                    │
│         - Enhanced request validation                          │
│         - Acts as proxy with additional logic                  │
│         Location: /backend/creator_interface/                  │
└────────────────────────────┬──────────────────────────────────┘
                             │ (Internal HTTP calls)
                             ▼
┌───────────────────────────────────────────────────────────────┐
│         LAMB Core API (/lamb/v1)                               │
│         - Direct database access                               │
│         - Core business logic                                  │
│         - Assistant, user, organization management             │
│         - Completions processing                               │
│         Location: /backend/lamb/                               │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Database/OWI  │
                    └────────────────┘
```

**Why Dual API?**
- **Separation of Concerns:** User-facing logic (auth, validation) separated from core operations
- **Flexibility:** Creator Interface can add features without modifying core
- **Evolution:** Legacy endpoints maintained while new patterns emerge
- **Security:** Additional validation layer before core operations

#### 3.1.2 Main Entry Point (`/backend/main.py`)

- **Mounts:**
  - `/lamb` → LAMB Core API
  - `/creator` → Creator Interface API
  - `/static` → Static file serving
  - `/{path:path}` → SPA catch-all (serves frontend)

- **Key Endpoints:**
  - `GET /v1/models` - List assistants as OpenAI models
  - `POST /v1/chat/completions` - Generate completions
  - `GET /status` - Health check

#### 3.1.3 LAMB Core API (`/backend/lamb/main.py`)

**Mounted Routers:**

| Router | Prefix | Purpose | File |
|--------|--------|---------|------|
| lti_users_router | `/v1/lti_users` | LTI user management | `lti_users_router.py` |
| simple_lti_router | `/simple_lti` | LTI launch handling | `simple_lti/simple_lti_main.py` |
| completions_router | `/v1/completions` | Completion generation | `completions/main.py` |
| mcp_router | `/v1/mcp` | MCP endpoints | `mcp_router.py` |

> **Security Note (Dec 2025):** OWI router endpoints (`/v1/OWI/*`) were removed for security reasons. OWI operations are now performed through internal service classes (`OwiUserManager`, `OwiGroupManager`, etc.) and are not exposed via HTTP endpoints.

#### 3.1.4 Creator Interface API (`/backend/creator_interface/main.py`)

**Mounted Routers:**

| Router | Prefix | Purpose | File |
|--------|--------|---------|------|
| assistant_router | `/creator/assistant` | Assistant operations | `assistant_router.py` |
| knowledges_router | `/creator/knowledgebases` | Knowledge Base operations | `knowledges_router.py` |
| organization_router | `/creator/admin` | Organization management | `organization_router.py` |
| analytics_router | `/creator/analytics` | Chat analytics and usage insights | `analytics_router.py` |
| learning_assistant_proxy_router | `/creator` | Learning assistant proxy | `learning_assistant_proxy.py` |
| evaluaitor_router | `/creator/rubrics` | Rubric management | `evaluaitor_router.py` |
| prompt_templates_router | `/creator/prompt-templates` | Prompt template management | `prompt_templates_router.py` |

**Direct Endpoints:**
- `POST /creator/login` - User login
- `POST /creator/signup` - User signup
- `GET /creator/users` - List users (admin)
- `POST /creator/admin/users/create` - Create user (admin)
- `PUT /creator/admin/users/update-role-by-email` - Update user role (admin)
- `PUT /creator/admin/users/{id}/status` - Enable/disable user (admin)
- `GET /creator/files/list` - List user files
- `POST /creator/files/upload` - Upload files
- `DELETE /creator/files/delete/{path}` - Delete files
- `GET /creator/user/current` - Get current user info

### 3.2 Open WebUI Integration

LAMB deeply integrates with Open WebUI:

**Integration Points:**

1. **User Authentication:** OWI manages user credentials and JWT tokens
2. **Model Management:** Published assistants become OWI "models"
3. **Knowledge Base:** OWI's ChromaDB stores document vectors
4. **Chat Interface:** Students interact with assistants via OWI chat UI
5. **Group Management:** OWI groups control assistant access

**OWI Bridge (`/backend/lamb/owi_bridge/`):**

| Component | Purpose | File |
|-----------|---------|------|
| `OwiDatabaseManager` | Direct database access to OWI SQLite | `owi_database.py` |
| `OwiUserManager` | User operations (create, verify, update) | `owi_users.py` |
| `OwiGroupManager` | Group operations for LTI | `owi_group.py` |
| `OwiModelManager` | Model (assistant) registration | `owi_model.py` |

**Key Operations:**
- Create OWI user when LAMB creator user is created
- Verify passwords against OWI auth table
- Generate JWT tokens for authenticated sessions
- Create/update OWI groups for published assistants
- Register assistants as OWI models

### 3.3 Knowledge Base Server

Independent service for document processing:

**Key Features:**
- Document ingestion (PDF, Word, Markdown, TXT, JSON)
- Text extraction and chunking
- Semantic embeddings (sentence-transformers)
- Vector storage (ChromaDB)
- Semantic search API

**API Endpoints:**
- `POST /api/collection` - Create collection
- `POST /api/collection/{id}/upload` - Upload document
- `GET /api/collection/{id}/query` - Query collection
- `DELETE /api/collection/{id}` - Delete collection

**Integration with LAMB:**
- Collections belong to users (by email) and organizations
- Assistants reference collections by ID
- RAG processors query KB server during completions

### 3.4 Frontend Application

**Technology Stack:**
- Svelte 5 (latest reactivity model)
- SvelteKit (SSR and routing)
- TailwindCSS (styling)
- Axios (HTTP client)
- svelte-i18n (internationalization)

**Key Components (`/frontend/svelte-app/src/lib/components/`):**

| Component | Purpose | File |
|-----------|---------|------|
| `Login.svelte` | Login form | `Login.svelte` |
| `Signup.svelte` | Signup form | `Signup.svelte` |
| `AssistantsList.svelte` | List user's assistants | `AssistantsList.svelte` |
| `AssistantForm.svelte` | Create/edit assistant | `assistants/AssistantForm.svelte` |
| `KnowledgeBasesList.svelte` | List Knowledge Bases | `KnowledgeBasesList.svelte` |
| `KnowledgeBaseDetail.svelte` | KB detail and operations | `KnowledgeBaseDetail.svelte` |
| `ChatInterface.svelte` | Test assistant chat | `ChatInterface.svelte` |
| `Nav.svelte` | Navigation bar | `Nav.svelte` |
| `PublishModal.svelte` | Publish assistant modal | `PublishModal.svelte` |

**Services (`/frontend/svelte-app/src/lib/services/`):**

| Service | Purpose | File |
|---------|---------|------|
| `authService.js` | Login, signup, token management | `authService.js` |
| `assistantService.js` | Assistant CRUD operations | `assistantService.js` |
| `knowledgeBaseService.js` | Knowledge Base operations | `knowledgeBaseService.js` |

**Stores (`/frontend/svelte-app/src/lib/stores/`):**

| Store | Purpose | File |
|--------|---------|------|
| `userStore.js` | User session state | `userStore.js` |
| `assistantStore.js` | Assistant list state | `assistantStore.js` |
| `assistantConfigStore.js` | Assistant editor state | `assistantConfigStore.js` |
| `assistantPublish.js` | Publish modal state | `assistantPublish.js` |

---

## 4. Data Architecture

### 4.1 LAMB Database (SQLite)

**Location:** `$LAMB_DB_PATH/lamb_v4.db`

**Schema Overview:**

#### 4.1.1 Organizations Table

```sql
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'trial')),
    config JSON NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

**Config Structure:**
```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "name": "Default Setup",
      "global_default_model": {
        "provider": "openai",
        "model": "gpt-4o"
      },
      "small_fast_model": {
        "provider": "openai",
        "model": "gpt-4o-mini"
      },
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "base_url": "https://api.openai.com/v1",
          "default_model": "gpt-4o-mini",
          "models": ["gpt-4o", "gpt-4o-mini"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "default_model": "llama3.1:latest",
          "models": ["llama3.1:latest", "mistral:latest"]
        }
      }
    }
  },
  "kb_server": {
    "url": "http://localhost:9090",
    "api_key": "kb-api-key"
  },
  "assistant_defaults": {
    "prompt_template": "User: {user_message}\nAssistant:",
    "system_prompt": "You are a helpful assistant."
  },
  "features": {
    "signup_enabled": false,
    "signup_key": "org-signup-key"
  }
}
```

**Global Model Configuration:**
- `global_default_model`: Organization-wide default model used when no specific model is configured (overrides per-provider defaults)
- `small_fast_model`: Lightweight model for auxiliary plugin operations (query rewriting, classification, etc.) - provides cost optimization and faster response times

#### 4.1.2 Organization Roles Table

```sql
CREATE TABLE organization_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner', 'admin', 'member')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(organization_id, user_id)
);
```

**Roles:**
- `owner`: Full control over organization
- `admin`: Can manage organization settings and members
- `member`: Can create assistants within organization

#### 4.1.3 Creator Users Table

```sql
CREATE TABLE Creator_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    user_email TEXT NOT NULL UNIQUE,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
    user_config JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

**User Types:**
- `creator`: Users who can access the creator interface and manage assistants
- `end_user`: Users who are automatically redirected to Open WebUI for direct interaction

**User Config Structure:**
```json
{
  "preferences": {
    "language": "en",
    "theme": "light"
  }
}
```

**Note on User Types:**
The `user_type` field distinguishes between:
- **Creator Users:** Have access to the full creator interface at `/creator`, can create and manage assistants, Knowledge Bases, and configurations
- **End Users:** Upon login, are automatically redirected to Open WebUI (`launch_url`), bypassing the creator interface entirely. These users are intended for direct interaction with published assistants without creation capabilities.

#### 4.1.4 Assistants Table

```sql
CREATE TABLE assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    owner TEXT NOT NULL,
    api_callback TEXT,  -- IMPORTANT: Stores 'metadata' field
    system_prompt TEXT,
    prompt_template TEXT,
    RAG_endpoint TEXT,  -- DEPRECATED
    RAG_Top_k INTEGER,
    RAG_collections TEXT,
    pre_retrieval_endpoint TEXT,  -- DEPRECATED
    post_retrieval_endpoint TEXT,  -- DEPRECATED
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    published BOOLEAN DEFAULT FALSE,
    published_at INTEGER,
    group_id TEXT,
    group_name TEXT,
    oauth_consumer_name TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE(organization_id, name, owner)
);
```

**Field Mapping (CRITICAL):**
- Application code uses `assistant.metadata`
- Database stores it in `api_callback` column
- This avoids schema changes while providing semantic clarity
- `pre_retrieval_endpoint`, `post_retrieval_endpoint`, `RAG_endpoint` are **DEPRECATED** and always empty

**Metadata Structure (stored in `api_callback`):**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag"
}
```

#### 4.1.5 LTI Users Table

```sql
CREATE TABLE lti_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL,
    assistant_name TEXT NOT NULL,
    group_id TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT '',
    assistant_owner TEXT NOT NULL DEFAULT '',
    user_email TEXT NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    user_display_name TEXT NOT NULL,
    user_role TEXT NOT NULL DEFAULT 'student',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

**Purpose:** Maps LTI launches to OWI users for tracking and analytics

#### 4.1.6 Usage Logs Table

```sql
CREATE TABLE usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER,
    assistant_id INTEGER,
    usage_data JSON NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES Creator_users(id),
    FOREIGN KEY (assistant_id) REFERENCES assistants(id)
);
```

**Usage Data Structure:**
```json
{
  "event": "completion",
  "tokens_used": 150,
  "model": "gpt-4o-mini",
  "duration_ms": 1234
}
```

### 4.2 Open WebUI Database (SQLite)

**Location:** `$OWI_PATH/webui.db`

**Key Tables:**

#### 4.2.1 User Table

```sql
CREATE TABLE user (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    profile_image_url TEXT,
    api_key TEXT UNIQUE,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_active_at INTEGER NOT NULL,
    settings TEXT,
    info TEXT,
    oauth_sub TEXT
);
```

#### 4.2.2 Auth Table

```sql
CREATE TABLE auth (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    active INTEGER NOT NULL
);
```

**Password Hashing:** bcrypt with cost factor 12

#### 4.2.3 Group Table

```sql
CREATE TABLE group (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    name TEXT,
    description TEXT,
    data JSON,
    meta JSON,
    permissions JSON,
    user_ids JSON,
    created_at INTEGER,
    updated_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

**Permissions Structure:**
```json
{
  "read": {
    "group_ids": [],
    "user_ids": ["user-uuid-1", "user-uuid-2"]
  },
  "write": {
    "group_ids": [],
    "user_ids": []
  }
}
```

#### 4.2.4 Model Table

```sql
CREATE TABLE model (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    base_model_id TEXT,
    name TEXT,
    params JSON,
    meta JSON,
    created_at INTEGER,
    updated_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

**Published Assistant as Model:**
- `id` = `lamb_assistant.{assistant_id}`
- `base_model_id` = Backend URL endpoint
- `params` = Assistant configuration
- `meta` = Additional metadata

### 4.3 Knowledge Base Storage (ChromaDB)

**Location:** `$OWI_PATH/vector_db/`

**Collection Structure:**
- Collections are isolated per user and organization
- Each document is split into chunks
- Chunks have embeddings (sentence-transformers)
- Metadata includes source, page number, user, organization

**Embedding Model:** Configurable, typically `all-MiniLM-L6-v2`

---

## 5. API Architecture

### 5.1 RESTful Design

LAMB follows REST principles:

- **Resource-Based URLs:** `/assistant/{id}`, `/knowledgebases/{id}`
- **HTTP Methods:** GET (read), POST (create), PUT (update), DELETE (delete)
- **Status Codes:** 200 (success), 201 (created), 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 500 (server error)
- **JSON Payloads:** All request/response bodies in JSON
- **Pagination:** `?limit=10&offset=0` for list endpoints

### 5.2 OpenAI API Compatibility

LAMB provides OpenAI-compatible endpoints for completions:

**Models Endpoint:**

```http
GET /v1/models
Authorization: Bearer {API_KEY}
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "lamb_assistant.1",
      "object": "model",
      "created": 1678886400,
      "owned_by": "lamb_v4",
      "capabilities": {
        "vision": true
      }
    }
  ]
}
```

**Capabilities Field:**
- `vision`: Boolean indicating multimodal image support
- Only present for assistants configured with vision capability
- Defaults to `false` for backward compatibility
- Added in November 2025 as part of multimodal support implementation

**Chat Completions Endpoint:**

```http
POST /v1/chat/completions
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "model": "lamb_assistant.1",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": false
}
```

**Response (Non-Streaming):**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1678886400,
  "model": "lamb_assistant.1",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ]
}
```

**Multimodal Chat Completions:**

```http
POST /v1/chat/completions
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "model": "lamb_assistant.1",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Describe this image:"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg"
          }
        }
      ]
    }
  ],
  "stream": false
}
```

**Response (Streaming):**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1678886400,"model":"lamb_assistant.1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 5.3 Error Handling

**Standard Error Response:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Error Scenarios:**
- **401 Unauthorized:** Missing or invalid token
- **403 Forbidden:** User doesn't have permission
- **404 Not Found:** Resource doesn't exist
- **409 Conflict:** Duplicate resource (e.g., assistant name)
- **422 Unprocessable Entity:** Invalid request data
- **500 Internal Server Error:** Server-side error

---

## 6. Authentication & Authorization

### 6.1 Authentication Flow

```
┌─────────┐                    ┌──────────────┐                ┌────────────┐
│ Browser │                    │   Creator    │                │    OWI     │
│         │                    │  Interface   │                │            │
└────┬────┘                    └──────┬───────┘                └─────┬──────┘
     │                                │                               │
     │  POST /creator/login           │                               │
     │  email, password               │                               │
     ├───────────────────────────────►│                               │
     │                                │                               │
     │                                │  Verify credentials           │
     │                                │  (via OWI bridge)             │
     │                                ├──────────────────────────────►│
     │                                │                               │
     │                                │  Password matches?            │
     │                                │◄──────────────────────────────┤
     │                                │                               │
     │                                │  Generate JWT token           │
     │                                ├──────────────────────────────►│
     │                                │                               │
     │                                │  JWT token + user_type        │
     │                                │◄──────────────────────────────┤
     │                                │                               │
     │  200 OK                        │                               │
     │  {token, user_info, user_type, │                               │
     │   launch_url}                  │                               │
     │◄───────────────────────────────┤                               │
     │                                │                               │
     │  Frontend checks user_type:    │                               │
     │  - If 'creator': Continue to   │                               │
     │    creator interface           │                               │
     │  - If 'end_user': Redirect to  │                               │
     │    launch_url (OWI)            │                               │
     │                                │                               │
     │  [For creator users only]      │                               │
     │  Store token in localStorage   │                               │
     │                                │                               │
     │  Subsequent requests           │                               │
     │  Authorization: Bearer {token} │                               │
     ├───────────────────────────────►│                               │
     │                                │                               │
     │                                │  Verify token                 │
     │                                │  (via OWI bridge)             │
     │                                ├──────────────────────────────►│
     │                                │                               │
     │                                │  User info                    │
     │                                │◄──────────────────────────────┤
     │                                │                               │
     │                                │  Check LAMB Creator user      │
     │                                │  exists & user_type           │
     │                                │                               │
     │  200 OK {data}                 │                               │
     │◄───────────────────────────────┤                               │
```

**End User Login Flow:**
When an end_user logs in:
1. Login credentials are verified normally
2. Response includes `user_type: 'end_user'` and `launch_url`
3. Frontend detects `user_type === 'end_user'`
4. Browser is redirected to `launch_url` (OWI with authentication token)
5. User interacts only with Open WebUI, never seeing the creator interface

### 6.2 Token Validation

Every authenticated endpoint follows this pattern:

1. Extract `Authorization: Bearer {token}` header
2. Call `get_creator_user_from_token(token)` helper
3. Helper calls `OwiUserManager.get_user_auth(token)` to validate with OWI
4. Helper then checks if user exists in LAMB Creator_users table
5. Returns creator user object or raises 401 error

**Implementation (`/backend/creator_interface/assistant_router.py`):**

```python
def get_creator_user_from_token(auth_header: str):
    """
    Extract user info from JWT token and verify in LAMB database
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split("Bearer ")[1].strip()
    
    # Verify token with OWI
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_auth(token)
    
    if not owi_user:
        return None
    
    # Check if user exists in LAMB Creator database
    db_manager = LambDatabaseManager()
    creator_user = db_manager.get_creator_user_by_email(owi_user['email'])
    
    return creator_user
```

### 6.3 Admin Check

Admin users have additional privileges:

```python
def is_admin_user(creator_user_or_token):
    """
    Check if user is an admin
    """
    # If token string is passed, get creator user first
    if isinstance(creator_user_or_token, str):
        creator_user = get_creator_user_from_token(creator_user_or_token)
    else:
        creator_user = creator_user_or_token
    
    if not creator_user:
        return False
    
    # Check OWI role
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_by_email(creator_user['email'])
    
    if owi_user and owi_user.get('role') == 'admin':
        return True
    
    # Also check organization role
    db_manager = LambDatabaseManager()
    system_org = db_manager.get_organization_by_slug("lamb")
    if system_org:
        org_role = db_manager.get_user_organization_role(
            system_org['id'], 
            creator_user['id']
        )
        if org_role == 'admin':
            return True
    
    return False
```

### 6.4 API Key Authentication (for Completions)

The `/v1/chat/completions` and `/v1/models` endpoints use API key authentication:

```python
api_key = request.headers.get("Authorization")
if api_key and api_key.startswith("Bearer "):
    api_key = api_key.split("Bearer ")[1].strip()
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

**Configuration:**
- `API_KEY` comes from `LAMB_BEARER_TOKEN` environment variable
- Default: `0p3n-w3bu!` (should be changed in production)

---

## 7. Completion Pipeline
   - 7.1 Multimodal Support

### 7.1 Request Flow

```
┌─────────┐    1. POST /v1/chat/completions    ┌──────────┐
│ Client  │──────────────────────────────────►│  Backend │
│         │    Authorization: Bearer {key}     │  main.py │
└─────────┘                                     └────┬─────┘
                                                     │
                                                     │ 2. Route to
                                                     │    run_lamb_assistant()
                                                     ▼
                                            ┌────────────────┐
                                            │  Completions   │
                                            │  Module        │
                                            │  main.py       │
                                            └───────┬────────┘
                                                    │
                    ┌───────────────────────────────┴────────────────────────────┐
                    │                                                            │
                    │ 3. Load Assistant from DB                                  │
                    │ 4. Parse plugin config from metadata                       │
                    │ 5. Load plugins (PPS, Connector, RAG)                      │
                    │                                                            │
                    └───────────────────────────────┬────────────────────────────┘
                                                    │
                                    ┌───────────────┼───────────────┐
                                    │               │               │
                                    ▼               ▼               ▼
                            ┌──────────┐    ┌──────────┐    ┌──────────┐
                            │   RAG    │    │   PPS    │    │Connector │
                            │Processor │    │Processor │    │          │
                            └────┬─────┘    └────┬─────┘    └────┬─────┘
                                 │               │               │
           6. Query KB ──────────┘               │               │
              (if configured)                    │               │
                                                 │               │
           7. Process messages ──────────────────┘               │
              (augment with context)                             │
                                                                 │
           8. Call LLM ───────────────────────────────────────────┘
              (OpenAI, Ollama, etc.)
                                 │
                                 │
                                 ▼
                         ┌──────────────┐
                         │  LLM Provider│
                         └──────┬───────┘
                                │
                                │ 9. Stream/Return response
                                ▼
                         ┌──────────────┐
                         │    Client    │
                         └──────────────┘
```

### 7.1 Multimodal Support

LAMB supports multimodal interactions through OpenAI's vision-capable models, allowing users to send images alongside text messages.

#### 7.1.1 Multimodal Message Format

LAMB supports OpenAI's standard multimodal message format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg"
          }
        }
      ]
    }
  ]
}
```

#### 7.1.2 Supported Image Formats

- **HTTP/HTTPS URLs**: Direct links to publicly accessible images
- **Base64 Data URLs**: `data:image/jpeg;base64,{base64_data}`
- **File Uploads**: Images uploaded via multipart form data
- **Formats**: JPEG (.jpg, .jpeg), PNG (.png), GIF (.gif), WebP (.webp)

#### 7.1.3 Multimodal Processing Flow

```
Client Request → Main API → Completion Pipeline
    ↓
Assistant Processing (with vision capability check)
    ↓
Prompt Processor (simple_augment with multimodal support)
    ↓
LLM Connector (OpenAI with vision API fallback)
    ↓
Success → Return response
    ↓
Failure → Fallback to text-only + warning message
```

#### 7.1.4 Vision Capability Configuration

Assistants must have vision capabilities enabled in their metadata:

```json
{
  "connector": "openai",
  "llm": "gpt-4o",
  "capabilities": {
    "vision": true
  }
}
```

**Security:** Images are only processed if the assistant explicitly has `"vision": true`. Non-vision assistants receive text-only processing.

#### 7.1.5 Vision API Fallback Strategy

```python
# Pseudocode for vision processing
if has_images(message) and assistant_has_vision_capability(assistant):
    try:
        # Try vision API call
        response = await client.chat.completions.create(
            model=vision_model,
            messages=multimodal_messages
        )
        return response
    except Exception as e:
        # Fallback: extract text content and add warning
        text_only_messages = extract_text_content(multimodal_messages)
        text_only_messages[0]["content"] = (
            "Unable to send image to the base LLM, multimodality is not supported. "
            + text_only_messages[0]["content"]
        )
        response = await client.chat.completions.create(
            model=fallback_model,
            messages=text_only_messages
        )
        return response
```

#### 7.1.6 Prompt Template Integration

The `simple_augment` prompt processor handles multimodal content:

- **Text Extraction**: Combines all text parts from multimodal messages
- **Template Application**: Applies `{user_input}` and `{context}` to extracted text
- **Image Preservation**: Maintains image elements alongside augmented text
- **Backward Compatibility**: Falls back to legacy string-only processing

#### 7.1.7 Security and Scoping Fixes (November 2025)

**Vision Capability Check:** Images are only accepted if the assistant has `"vision": true` in its capabilities metadata, preventing unauthorized image processing and associated costs.

**Streaming Function Scoping:** Fixed NameError in `backend/lamb/completions/connectors/openai.py` where `_generate_vision_stream` and `_generate_original_stream` helper functions were not properly scoped within the `llm_connect` function, causing multimodal requests to fail.

**Implementation Details:**
- Added `_has_vision_capability()` helper function to check assistant metadata
- Moved streaming helper functions inside `llm_connect` to resolve scoping issues
- Enhanced error handling for vision API failures with clear user messages

### 7.2 Detailed Steps

#### Step 1: Get Assistant Details

```python
def get_assistant_details(assistant_id: int) -> Assistant:
    """
    Retrieve assistant from database
    """
    db_manager = LambDatabaseManager()
    assistant = db_manager.get_assistant_by_id(assistant_id)
    return assistant
```

#### Step 2: Parse Plugin Configuration

```python
def parse_plugin_config(assistant: Assistant) -> Dict[str, str]:
    """
    Extract plugin configuration from assistant metadata
    """
    default_config = {
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": None,
        "rag_processor": ""
    }
    
    # metadata field is mapped to api_callback column
    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
            default_config.update(metadata)
        except:
            pass
    
    return default_config
```

#### Step 3: Load Plugins

```python
def load_and_validate_plugins(plugin_config: Dict[str, str]):
    """
    Dynamically load prompt processor, connector, and RAG processor
    """
    pps = load_plugins("pps")
    connectors = load_plugins("connectors")
    rag_processors = load_plugins("rag")
    
    # Validate configured plugins exist
    if plugin_config["prompt_processor"] not in pps:
        raise ValueError(f"PPS '{plugin_config['prompt_processor']}' not found")
    
    if plugin_config["connector"] not in connectors:
        raise ValueError(f"Connector '{plugin_config['connector']}' not found")
    
    if plugin_config["rag_processor"] and plugin_config["rag_processor"] not in rag_processors:
        raise ValueError(f"RAG processor '{plugin_config['rag_processor']}' not found")
    
    return pps, connectors, rag_processors
```

**Plugin Loading:**

```python
def load_plugins(plugin_type: str) -> Dict[str, Any]:
    """
    Load all plugins of a specific type from directory
    """
    plugins = {}
    plugin_dir = os.path.join(os.path.dirname(__file__), plugin_type)
    
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    os.path.join(plugin_dir, filename)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get the main function based on plugin type
                if plugin_type == "pps":
                    func = getattr(module, "prompt_processor", None)
                elif plugin_type == "connectors":
                    func = getattr(module, "llm_connect", None)
                elif plugin_type == "rag":
                    func = getattr(module, "rag_processor", None)
                
                if func:
                    plugins[module_name] = func
            except Exception as e:
                logger.error(f"Error loading {plugin_type}/{module_name}: {e}")
    
    return plugins
```

#### Step 4: Get RAG Context (if configured)

```python
def get_rag_context(
    request: Dict[str, Any],
    rag_processors: Dict[str, Any],
    rag_processor: str,
    assistant: Assistant
) -> Any:
    """
    Execute RAG processor to get relevant context
    """
    if not rag_processor:
        return None
    
    messages = request.get('messages', [])
    rag_context = rag_processors[rag_processor](
        messages=messages,
        assistant=assistant
    )
    return rag_context
```

**Example RAG Processor (`simple_rag.py`):**

```python
def rag_processor(messages: List[Dict], assistant: Assistant = None):
    """
    Query Knowledge Base for relevant context
    """
    # Extract last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    if not last_user_message or not assistant.RAG_collections:
        return {"context": "", "sources": []}
    
    # Get organization-specific KB server configuration
    config_resolver = OrganizationConfigResolver(assistant.owner)
    kb_config = config_resolver.get_kb_server_config()
    
    kb_server_url = kb_config.get("url")
    kb_api_key = kb_config.get("api_key")
    
    # Parse collections
    collections = [c.strip() for c in assistant.RAG_collections.split(',') if c.strip()]
    top_k = getattr(assistant, 'RAG_Top_k', 3)
    
    # Query each collection
    all_results = []
    for collection_id in collections:
        response = requests.post(
            f"{kb_server_url}/api/collection/{collection_id}/query",
            json={"query": last_user_message, "top_k": top_k},
            headers={"Authorization": f"Bearer {kb_api_key}"}
        )
        if response.ok:
            data = response.json()
            all_results.extend(data.get("results", []))
    
    # Format context
    context_parts = []
    sources = []
    for i, result in enumerate(all_results):
        context_parts.append(f"[{i+1}] {result['text']}")
        sources.append({
            "index": i+1,
            "source": result.get('metadata', {}).get('source', 'Unknown'),
            "page": result.get('metadata', {}).get('page', 'N/A')
        })
    
    context = "\n\n".join(context_parts)
    
    return {
        "context": context,
        "sources": sources
    }
```

#### Step 5: Process Messages with Prompt Processor

```python
def process_completion_request(
    request: Dict[str, Any],
    assistant: Assistant,
    plugin_config: Dict[str, str],
    rag_context: Any,
    pps: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    Execute prompt processor to augment messages
    """
    pps_func = pps[plugin_config["prompt_processor"]]
    messages = pps_func(
        request=request,
        assistant=assistant,
        rag_context=rag_context
    )
    return messages
```

**Example Prompt Processor (`simple_augment.py`):**

```python
def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Augment messages with system prompt and RAG context
    """
    messages = []
    
    # Add system prompt
    if assistant and assistant.system_prompt:
        system_content = assistant.system_prompt
        
        # Inject RAG context if available
        if rag_context and rag_context.get("context"):
            system_content += f"\n\nRelevant information:\n{rag_context['context']}"
        
        messages.append({
            "role": "system",
            "content": system_content
        })
    
    # Add user messages from request
    for msg in request.get("messages", []):
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Apply prompt template to last user message if configured
    if assistant and assistant.prompt_template and messages:
        last_msg = messages[-1]
        if last_msg["role"] == "user":
            template = assistant.prompt_template
            last_msg["content"] = template.format(user_message=last_msg["content"])
    
    return messages
```

#### Step 6: Call LLM Connector

```python
async def run_lamb_assistant(
    request: Dict[str, Any],
    assistant: int,
    headers: Optional[Dict[str, str]] = None
):
    """
    Execute completion pipeline
    """
    assistant_details = get_assistant_details(assistant)
    plugin_config = parse_plugin_config(assistant_details)
    pps, connectors, rag_processors = load_and_validate_plugins(plugin_config)
    rag_context = get_rag_context(request, rag_processors, plugin_config["rag_processor"], assistant_details)
    messages = process_completion_request(request, assistant_details, plugin_config, rag_context, pps)
    stream = request.get("stream", False)
    llm = plugin_config.get("llm")
    
    # Get connector function
    connector_func = connectors[plugin_config["connector"]]
    
    # Call connector
    llm_response = await connector_func(
        messages=messages,
        stream=stream,
        body=request,
        llm=llm,
        assistant_owner=assistant_details.owner
    )
    
    if stream:
        # Return async generator for streaming
        return StreamingResponse(llm_response, media_type="text/event-stream")
    else:
        # Return JSON response
        return JSONResponse(content=llm_response)
```

**Example Connector (`openai.py`):**

```python
async def llm_connect(
    messages: list,
    stream: bool = False,
    body: Dict[str, Any] = None,
    llm: str = None,
    assistant_owner: Optional[str] = None
):
    """
    Connect to OpenAI API (organization-aware)
    """
    # Get organization-specific configuration
    api_key = None
    base_url = None
    default_model = "gpt-4o-mini"
    
    if assistant_owner:
        config_resolver = OrganizationConfigResolver(assistant_owner)
        openai_config = config_resolver.get_provider_config("openai")
        
        if openai_config:
            api_key = openai_config.get("api_key")
            base_url = openai_config.get("base_url")
            default_model = openai_config.get("default_model", "gpt-4o-mini")
    
    # Fallback to environment variables
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        default_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    if not api_key:
        raise ValueError("No OpenAI API key found")
    
    # Model resolution
    resolved_model = llm or default_model
    
    # Create client
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    # Prepare parameters
    params = body.copy() if body else {}
    params["model"] = resolved_model
    params["messages"] = messages
    params["stream"] = stream
    
    if stream:
        # Return async generator
        async def generate_stream():
            stream_obj = await client.chat.completions.create(**params)
            async for chunk in stream_obj:
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        
        return generate_stream()
    else:
        # Return completion
        response = await client.chat.completions.create(**params)
        return response.model_dump()
```

### 7.3 Organization-Specific Configuration Resolution

The `OrganizationConfigResolver` class handles organization-specific settings:

```python
class OrganizationConfigResolver:
    def __init__(self, user_email: str):
        """
        Initialize with user email to determine organization
        """
        self.db_manager = LambDatabaseManager()
        self.user = self.db_manager.get_creator_user_by_email(user_email)
        
        if not self.user:
            raise ValueError(f"User not found: {user_email}")
        
        self.organization = self.db_manager.get_user_organization(self.user['id'])
        
        if not self.organization:
            # Fallback to system organization
            self.organization = self.db_manager.get_organization_by_slug("lamb")
    
    def get_provider_config(self, provider_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific provider (openai, ollama, etc.)
        """
        config = self.organization.get('config', {})
        setups = config.get('setups', {})
        default_setup = setups.get('default', {})
        providers = default_setup.get('providers', {})
        return providers.get(provider_name)

    def get_global_default_model_config(self) -> Dict[str, str]:
        """
        Get global default model configuration (organization-wide)
        Returns: {"provider": str, "model": str}
        """
        config = self.organization.get('config', {})
        setups = config.get('setups', {})
        default_setup = setups.get('default', {})
        return default_setup.get('global_default_model', {"provider": "", "model": ""})

    def get_small_fast_model_config(self) -> Dict[str, str]:
        """
        Get small-fast-model configuration (for auxiliary operations)
        Returns: {"provider": str, "model": str}
        """
        config = self.organization.get('config', {})
        setups = config.get('setups', {})
        default_setup = setups.get('default', {})
        return default_setup.get('small_fast_model', {"provider": "", "model": ""})

    def resolve_model_for_completion(self, requested_model: Optional[str] = None,
                                     requested_provider: Optional[str] = None) -> Dict[str, str]:
        """
        Resolve model using hierarchy: explicit > global default > provider default > first available
        """
        # Implementation follows hierarchy for model resolution

    def get_kb_server_config(self) -> Dict:
        """
        Get Knowledge Base server configuration
        """
        config = self.organization.get('config', {})
        kb_config = config.get('kb_server', {})

        # Fallback to environment variables
        if not kb_config.get('url'):
            kb_config = {
                'url': os.getenv('KB_SERVER_URL', 'http://localhost:9090'),
                'api_key': os.getenv('KB_API_KEY', '')
            }

        return kb_config
```

**Usage in Connectors and RAG Processors:**

```python
# In openai.py connector
config_resolver = OrganizationConfigResolver(assistant_owner)
openai_config = config_resolver.get_provider_config("openai")
api_key = openai_config.get("api_key")

# In simple_rag.py processor
config_resolver = OrganizationConfigResolver(assistant.owner)
kb_config = config_resolver.get_kb_server_config()
kb_server_url = kb_config.get("url")

# Using small-fast-model for auxiliary operations
from lamb.completions.small_fast_model_helper import invoke_small_fast_model, is_small_fast_model_configured

if is_small_fast_model_configured(assistant.owner):
    response = await invoke_small_fast_model(
        messages=[{"role": "user", "content": "Rewrite this query: ..."}],
        assistant_owner=assistant.owner
    )
```

### 7.4 Model Resolution Hierarchy

When resolving which model to use for completions:

1. **Explicit model/provider** in request → use that
2. **Global default model** configured → use that
3. **Per-provider default model** → use that
4. **First available model** from provider → use that

For auxiliary plugin operations using small-fast-model:

1. **Small-fast-model** configured → use that
2. **Fallback to plugin's default behavior**

**Environment Variables:**
```bash
# Global default model (organization-wide)
GLOBAL_DEFAULT_MODEL_PROVIDER=openai
GLOBAL_DEFAULT_MODEL_NAME=gpt-4o

# Small fast model (auxiliary operations)
SMALL_FAST_MODEL_PROVIDER=openai
SMALL_FAST_MODEL_NAME=gpt-4o-mini
```

---

## 8. Organization & Multi-Tenancy

### 8.1 Organization Structure

Organizations provide:
- **Isolation:** Each organization has independent data and configuration
- **Configuration:** LLM providers, API keys, KB server settings
- **User Management:** Users belong to organizations with specific roles
- **Resource Isolation:** Assistants, Knowledge Bases scoped to organization

### 8.2 System Organization

The "lamb" system organization is special:

- Created during database initialization
- `is_system = true`
- Cannot be deleted
- System admins are members with admin role
- Fallback configuration source

### 8.3 Organization Configuration

Organizations store configuration in JSON:

```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "name": "Default Setup",
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "base_url": "https://api.openai.com/v1",
          "default_model": "gpt-4o-mini",
          "models": ["gpt-4o", "gpt-4o-mini", "gpt-4"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "default_model": "llama3.1:latest",
          "models": ["llama3.1:latest", "mistral:latest"]
        },
        "anthropic": {
          "enabled": false,
          "api_key": "",
          "default_model": "claude-3-5-sonnet-20241022",
          "models": []
        }
      }
    }
  },
  "kb_server": {
    "url": "http://localhost:9090",
    "api_key": "kb-api-key"
  },
  "assistant_defaults": {
    "prompt_template": "User: {user_message}\nAssistant:",
    "system_prompt": "You are a helpful educational assistant."
  },
  "features": {
    "signup_enabled": false,
    "signup_key": "org-specific-key-2024"
  },
  "metadata": {
    "description": "Engineering Department Organization",
    "contact_email": "admin@engineering.edu"
  }
}
```

### 8.4 Organization Signup

Organizations can enable signup with unique keys:

1. Admin creates organization with `signup_enabled: true` and `signup_key: "unique-key"`
2. User visits signup form and enters email, name, password, and signup key
3. System checks if signup key matches any organization
4. If match found, user is created in that organization with "member" role
5. If no match and `SIGNUP_ENABLED=true`, user created in system organization

**Implementation:**

```python
async def signup(email: str, name: str, password: str, secret_key: str):
    # Try organization-specific signup
    target_org = db_manager.get_organization_by_signup_key(secret_key)
    
    if target_org:
        # Create user in organization
        user_creator = UserCreatorManager()
        result = await user_creator.create_user(
            email=email,
            name=name,
            password=password,
            organization_id=target_org['id']
        )
        if result["success"]:
            db_manager.assign_organization_role(
                target_org['id'],
                result['user_id'],
                "member"
            )
        return result
    
    # Fallback to system organization if enabled
    elif SIGNUP_ENABLED and secret_key == SIGNUP_SECRET_KEY:
        system_org = db_manager.get_organization_by_slug("lamb")
        # ... create user in system org
```

### 8.5 Organization Management APIs

**List Organizations (Admin):**

```http
GET /creator/admin/organizations
Authorization: Bearer {admin_token}
```

**Create Organization (Admin):**

```http
POST /creator/admin/organizations/enhanced
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "slug": "engineering",
  "name": "Engineering Department",
  "admin_user_id": 2,
  "signup_enabled": true,
  "signup_key": "eng-dept-2024",
  "use_system_baseline": true
}
```

**Update Organization Config (Admin/Org Admin):**

```http
PUT /creator/admin/organizations/{slug}/config
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "setups": {
    "default": {
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "new-key",
          "models": ["gpt-4o"]
        }
      }
    }
  }
}
```

---

## 9. Knowledge Base Integration

### 9.1 Architecture

```
┌──────────────┐                 ┌──────────────────┐
│              │  1. Create      │                  │
│   Frontend   │  Collection     │   LAMB Backend   │
│              ├────────────────►│                  │
└──────────────┘                 └────────┬─────────┘
                                          │
                                          │ 2. Forward request
                                          │    with user/org info
                                          ▼
                                 ┌──────────────────┐
                                 │                  │
                                 │  KB Server       │
                                 │  :9090           │
                                 │                  │
                                 └────────┬─────────┘
                                          │
                                          │ 3. Store metadata
                                          ▼
                                 ┌──────────────────┐
                                 │   ChromaDB       │
                                 │   Collections    │
                                 └──────────────────┘
```

### 9.2 Collection Management

**Create Collection:**

```http
POST /creator/knowledgebases/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "collection_name": "CS101 Lectures",
  "description": "Computer Science 101 lecture materials"
}
```

**Backend forwards to KB Server:**

```python
async def create_knowledgebase(name: str, description: str, request: Request):
    creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
    
    # Forward to KB server with user and organization info
    kb_response = await kb_server_manager.create_collection(
        collection_name=name,
        description=description,
        user_email=creator_user['email'],
        organization_slug=creator_user['organization_slug']
    )
    
    return kb_response
```

**KB Server creates collection with metadata:**

```python
collection = chroma_client.create_collection(
    name=f"{organization_slug}_{user_email}_{collection_name}",
    metadata={
        "user_email": user_email,
        "organization": organization_slug,
        "description": description,
        "created_at": int(time.time())
    }
)
```

### 9.3 Document Upload

**Upload Document:**

```http
POST /creator/knowledgebases/{collection_id}/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file=@document.pdf
```

**Processing Flow:**

1. Extract text from document (PDF, Word, etc.)
2. Split into chunks (configurable size, overlap)
3. Generate embeddings for each chunk (sentence-transformers)
4. Store chunks in ChromaDB collection with metadata:
   - `source`: filename
   - `page`: page number (if applicable)
   - `user_email`: uploader
   - `organization`: org slug
   - `chunk_index`: position in document

### 9.4 Query/Retrieval

**Test Query:**

```http
GET /creator/knowledgebases/{collection_id}/query?q={query}&top_k=5
Authorization: Bearer {token}
```

**Response:**

```json
{
  "results": [
    {
      "text": "Chunk content...",
      "metadata": {
        "source": "lecture1.pdf",
        "page": 3,
        "user_email": "prof@university.edu",
        "organization": "cs_department"
      },
      "distance": 0.234
    }
  ]
}
```

### 9.5 RAG Integration in Completions

During completion request:

1. Last user message extracted as query
2. RAG processor queries associated collections
3. Top K chunks retrieved and formatted
4. Context injected into system prompt
5. Citations provided in response (if supported by frontend)

### 9.6 Knowledge Base Sharing

LAMB supports organization-level Knowledge Base sharing, allowing users within the same organization to share KBs with each other. This feature follows the same pattern as Prompt Templates sharing.

#### 9.6.1 Overview

**Key Features:**
- KBs can be shared within an organization
- Shared KBs are visible to all organization members
- Users can use shared KBs in their assistants (read-only access)
- KB owners maintain full control (edit, delete, share/unshare)
- Protection mechanism prevents unsharing when KB is in use by other users' assistants

#### 9.6.2 Database Schema

**KB Registry Table (`kb_registry`):**

```sql
CREATE TABLE kb_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL UNIQUE,
    kb_name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL,
    is_shared BOOLEAN DEFAULT FALSE,
    metadata JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
)

-- Indexes for performance
CREATE INDEX idx_kb_registry_owner ON kb_registry(owner_user_id)
CREATE INDEX idx_kb_registry_org_shared ON kb_registry(organization_id, is_shared)
CREATE INDEX idx_kb_registry_kb_id ON kb_registry(kb_id)
```

**Purpose:**
- Tracks KB metadata in LAMB database (KB Server only stores documents)
- Enables organization-scoped sharing
- Maintains ownership and access control
- Stores creation timestamps for sorting

#### 9.6.3 Auto-Registration & Lazy Cleanup

**Auto-Registration:**
- When a user accesses their KBs, LAMB checks the KB Server
- KBs found in KB Server but not in `kb_registry` are automatically registered
- `created_at` is preserved from KB Server if available
- Ensures registry stays in sync with KB Server

**Lazy Cleanup (Self-Healing):**
- When fetching KB details, if KB Server returns 404, the registry entry is automatically removed
- Prevents stale registry entries from out-of-band deletions
- No manual cleanup required

#### 9.6.4 API Endpoints

**Get Owned KBs:**
```http
GET /creator/knowledgebases/user
Authorization: Bearer {token}

Response:
{
  "knowledge_bases": [
    {
      "id": "kb_uuid_1",
      "name": "CS101 Lectures",
      "is_owner": true,
      "is_shared": false,
      "created_at": 1761815586,
      ...
    }
  ]
}
```

**Get Shared KBs:**
```http
GET /creator/knowledgebases/shared
Authorization: Bearer {token}

Response:
{
  "knowledge_bases": [
    {
      "id": "kb_uuid_2",
      "name": "Shared Research Papers",
      "is_owner": false,
      "is_shared": true,
      "shared_by": "John Doe",
      "created_at": 1761816138,
      ...
    }
  ]
}
```

**Toggle Sharing:**
```http
PUT /creator/knowledgebases/kb/{kb_id}/share
Authorization: Bearer {token}
Content-Type: application/json

{
  "is_shared": true
}

Response:
{
  "kb_id": "kb_uuid_1",
  "is_shared": true,
  "message": "KB is now shared with organization"
}
```

**Error Response (KB in use):**
```http
Status: 409 Conflict

{
  "detail": "Cannot unshare KB: It is currently used by 2 assistant(s): Assistant A (by User 1), Assistant B (by User 2). Please ask users to remove this KB from their assistants first."
}
```

#### 9.6.5 Access Control

**Access Levels:**

| Action | Owner | Shared User |
|--------|-------|-------------|
| View KB | ✅ | ✅ |
| Query KB | ✅ | ✅ |
| Use in Assistant | ✅ | ✅ |
| Edit KB Name | ✅ | ❌ |
| Upload Documents | ✅ | ❌ |
| Delete Documents | ✅ | ❌ |
| Delete KB | ✅ | ❌ |
| Toggle Sharing | ✅ | ❌ |

**Implementation:**

```python
def user_can_access_kb(kb_id: str, user_id: int) -> Tuple[bool, str]:
    """
    Check if user can access KB and return access level.
    
    Returns:
        (can_access: bool, access_type: 'owner' | 'shared' | 'none')
    """
    entry = get_kb_registry_entry(kb_id)
    if not entry:
        return (False, 'none')
    
    # Owner has full access
    if entry['owner_user_id'] == user_id:
        return (True, 'owner')
    
    # Shared KBs accessible to organization members
    user = get_creator_user_by_id(user_id)
    if user and entry['is_shared'] and entry['organization_id'] == user['organization_id']:
        return (True, 'shared')
    
    return (False, 'none')
```

#### 9.6.6 Protection Against Unsharing

**Prevention Logic:**

When a KB owner attempts to unshare (`is_shared = false`), the system checks if any assistants owned by other users reference this KB:

```python
def check_kb_used_by_other_users(kb_id: str, kb_owner_user_id: int) -> List[Dict]:
    """
    Check if KB is used by assistants owned by other users.
    
    Returns:
        List of assistants using this KB (owned by other users).
        Empty list if KB can be safely unshared.
    """
    # Query assistants table for RAG_collections containing kb_id
    # Filter out assistants owned by the KB owner
    # Return list of matching assistants with owner info
```

**Behavior:**
- ✅ **Can Share:** No restrictions, owner can share at any time
- ❌ **Cannot Unshare:** If KB is used by other users' assistants, unshare is blocked
- 📋 **Error Message:** Lists assistants using the KB (up to 3, then "and X more")
- 🔒 **Protection:** Prevents breaking other users' assistants

**SQL Query Pattern:**

```sql
SELECT a.id, a.name, a.owner, u.user_name as owner_name
FROM assistants a
JOIN Creator_users u ON a.owner = u.user_email
WHERE a.RAG_collections LIKE '%kb_id%'
  AND a.owner != kb_owner_email
  AND u.id != kb_owner_user_id
```

The query uses `LIKE '%kb_id%'` for initial matching, then verifies exact match by parsing comma-separated `RAG_collections` values.

#### 9.6.7 Frontend Implementation

**Tabbed Interface:**

The frontend displays KBs in separate tabs:
- **"My Knowledge Bases"**: Shows owned KBs from `/creator/knowledgebases/user`
- **"Shared Knowledge Bases"**: Shows shared KBs from `/creator/knowledgebases/shared`

**Sharing Toggle UI:**

```svelte
<!-- Owner can toggle sharing -->
{#if kb.is_owner}
  <button onclick={() => handleToggleSharing(kb)}>
    {kb.is_shared ? '🔓 Unshare' : '🔒 Share'}
  </button>
{/if}

<!-- Status badge -->
{#if kb.is_owner && kb.is_shared}
  <span class="badge">Shared</span>
{:else if kb.is_owner}
  <span class="badge">Private</span>
{:else}
  <span class="badge">Read-Only</span>
  <span class="text-sm text-gray-500">Shared by {kb.shared_by}</span>
{/if}
```

**Assistant Form Integration:**

When selecting KBs for an assistant, shared KBs are displayed in a separate section:

```svelte
{#if ownedKnowledgeBases.length > 0}
  <h5>My Knowledge Bases</h5>
  {#each ownedKnowledgeBases as kb}
    <!-- Checkbox for KB selection -->
  {/each}
{/if}

{#if sharedKnowledgeBases.length > 0}
  <h5>Shared Knowledge Bases</h5>
  {#each sharedKnowledgeBases as kb}
    <!-- Checkbox with owner indicator -->
    <span>{kb.name} (Shared by {kb.shared_by})</span>
  {/each}
{/if}
```

#### 9.6.8 Usage Flow

**Sharing a KB:**

1. KB owner creates KB (registered in `kb_registry` with `is_shared = false`)
2. Owner clicks "Share" button in KB list
3. Frontend calls `PUT /creator/knowledgebases/kb/{kb_id}/share` with `is_shared: true`
4. Backend updates `kb_registry.is_shared = true`
5. KB appears in "Shared Knowledge Bases" for all organization members

**Using a Shared KB:**

1. User views "Shared Knowledge Bases" tab
2. User selects shared KB when creating/editing assistant
3. KB ID added to assistant's `RAG_collections`
4. Assistant can query shared KB during completions

**Unsharing Attempt (Protected):**

1. KB owner clicks "Unshare" button
2. Backend checks `check_kb_used_by_other_users()`
3. If KB is in use:
   - Returns HTTP 409 with error message listing blocking assistants
   - Frontend displays error message
   - KB remains shared
4. If KB is not in use:
   - Updates `is_shared = false`
   - KB removed from shared list
   - KB remains accessible to owner

### 9.7 Assistant Sharing

LAMB supports organization-level Assistant sharing, allowing users within the same organization to share their assistants with specific colleagues. This feature provides fine-grained access control through a two-level permission system.

#### 9.7.1 Overview

**Key Features:**
- Assistants can be shared with specific users within an organization
- Two-level permission system (organization + user level)
- Shared assistants provide read-only access (view properties and chat)
- Assistant owners maintain full control (edit, delete, manage sharing)
- Modal-based UI for managing shared users
- Real-time permission checks

#### 9.7.2 Permission System

**Two-Level Permissions:**

For a user to have sharing capabilities, **BOTH** conditions must be true:

1. **Organization Level**: `config.features.sharing_enabled = true`
2. **User Level**: `user_config.can_share = true` (default: true)

**Permission Matrix:**

| Org Sharing | User Can Share | Result |
|-------------|----------------|--------|
| ✅ Enabled  | ✅ True       | ✅ User can share |
| ✅ Enabled  | ❌ False      | ❌ User cannot share |
| ❌ Disabled | ✅ True       | ❌ User cannot share |
| ❌ Disabled | ❌ False      | ❌ User cannot share |

**Rationale:** Organization admins control the feature at org level, then can selectively enable/disable sharing for individual users.

#### 9.7.3 Database Schema

**Assistant Shares Table (`assistant_shares`):**

```sql
CREATE TABLE assistant_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    shared_with_user_id INTEGER NOT NULL,
    shared_by_user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_by_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(assistant_id, shared_with_user_id)
)

-- Indexes for performance
CREATE INDEX idx_shares_assistant ON assistant_shares(assistant_id)
CREATE INDEX idx_shares_user ON assistant_shares(shared_with_user_id)
```

**Purpose:**
- Tracks which assistants are shared with which users
- Maintains who initiated the share (for audit/display)
- Ensures no duplicate shares (UNIQUE constraint)
- Cascading deletes clean up shares when assistants or users are removed

**User Config Schema (Can Share Permission):**

```json
{
  "can_share": true,
  "preferences": {
    "language": "en"
  }
}
```

Stored in `Creator_users.user_config` JSON column.

#### 9.7.4 API Endpoints

**Check Sharing Permission:**
```http
GET /lamb/v1/assistant-sharing/check-permission
Authorization: Bearer {token}

Response:
{
  "can_share": true,
  "message": "User has sharing permission"
}
```

**Get Organization Users (for Sharing UI):**
```http
GET /lamb/v1/assistant-sharing/organization-users
Authorization: Bearer {token}

Response:
[
  {
    "user_id": 2,
    "user_name": "Jane Smith",
    "user_email": "jane@example.com"
  }
]
```

**Get Shared Users for Assistant:**
```http
GET /lamb/v1/assistant-sharing/shares/{assistant_id}
Authorization: Bearer {token}

Response:
[
  {
    "user_id": 2,
    "user_name": "Jane Smith",
    "user_email": "jane@example.com",
    "shared_by_name": "John Doe",
    "created_at": 1730908800
  }
]
```

**Update Assistant Shares (Atomic):**
```http
PUT /lamb/v1/assistant-sharing/shares/{assistant_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "user_ids": [2, 3, 5]
}

Response:
{
  "success": true,
  "shared_with": [2, 3, 5],
  "added": [5],
  "removed": [4]
}
```

This endpoint accepts the **desired final state** of shared users. Backend calculates additions and removals automatically.

**Update User Sharing Permission (Admin Only):**
```http
PUT /lamb/v1/assistant-sharing/user-permission/{user_id}?can_share=true
Authorization: Bearer {admin_token}

Response:
{
  "success": true,
  "user_id": 2,
  "can_share": true
}
```

#### 9.7.5 Access Control

**Access Levels:**

| Action | Owner | Shared User |
|--------|-------|-------------|
| View Assistant Properties | ✅ | ✅ |
| Chat with Assistant | ✅ | ✅ |
| Edit Assistant | ✅ | ❌ |
| Delete Assistant | ✅ | ❌ |
| Publish Assistant | ✅ | ❌ |
| Manage Sharing | ✅ | ❌ |

**Implementation:**

```python
def user_can_access_assistant(assistant_id: int, user_id: int) -> Tuple[bool, str]:
    """
    Check if user can access assistant and return access level.
    
    Returns:
        (can_access: bool, access_type: 'owner' | 'shared' | 'none')
    """
    assistant = get_assistant_by_id(assistant_id)
    if not assistant:
        return (False, 'none')
    
    # Owner has full access
    user = get_creator_user_by_id(user_id)
    if assistant.owner == user['email']:
        return (True, 'owner')
    
    # Check if assistant is shared with this user
    if is_assistant_shared_with_user(assistant_id, user_id):
        return (True, 'shared')
    
    return (False, 'none')
```

**Backend Enforcement:**

In `backend/creator_interface/assistant_router.py`:

```python
# Verify Ownership OR Sharing
is_owner = assistant_data.get('owner') == creator_user['email']
is_shared = db_check.is_assistant_shared_with_user(assistant_id, creator_user['id'])

if not is_owner and not is_shared:
    raise HTTPException(status_code=404, detail="Assistant not found")
```

In `backend/creator_interface/learning_assistant_proxy.py`:

```python
# Enhanced verify_assistant_access
is_owner = assistant.owner == user['email']
if not is_owner:
    is_shared = db_check.is_assistant_shared_with_user(assistant_id, user['id'])
    if not is_shared:
        return False
return True
```

#### 9.7.6 Frontend Implementation

**Sharing UI:**

The frontend provides a modal-based interface for managing shared users, similar to the "Manage Ollama Models" modal:

```svelte
<!-- AssistantSharingModal.svelte -->
<div class="modal-container">
  <div class="dual-panel">
    <!-- Left Panel: Shared Users -->
    <div class="panel">
      <h3>Shared Users ({sharedUsers.length})</h3>
      <input type="search" bind:value={searchShared} placeholder="Search...">
      <div class="user-list">
        {#each filteredSharedUsers as user}
          <label class="user-item">
            <input type="checkbox" 
                   bind:group={selectedShared} 
                   value={user.user_id}>
            <span>{user.user_name}</span>
            <span class="email">{user.user_email}</span>
          </label>
        {/each}
      </div>
    </div>
    
    <!-- Center: Move Buttons -->
    <div class="move-buttons">
      <button onclick={moveAllToShared} disabled={!canMoveAllRight}>≪</button>
      <button onclick={moveToShared} disabled={!canMoveRight}><</button>
      <button onclick={moveToAvailable} disabled={!canMoveLeft}>></button>
      <button onclick={moveAllToAvailable} disabled={!canMoveAllLeft}>≫</button>
    </div>
    
    <!-- Right Panel: Available Users -->
    <div class="panel">
      <h3>Available Users ({availableUsers.length})</h3>
      <input type="search" bind:value={searchAvailable} placeholder="Search...">
      <div class="user-list">
        {#each filteredAvailableUsers as user}
          <label class="user-item">
            <input type="checkbox" 
                   bind:group={selectedAvailable} 
                   value={user.user_id}>
            <span>{user.user_name}</span>
            <span class="email">{user.user_email}</span>
          </label>
        {/each}
      </div>
    </div>
  </div>
  
  <div class="modal-actions">
    <button class="btn-primary" onclick={saveChanges}>Save Changes</button>
    <button class="btn-secondary" onclick={onClose}>Cancel</button>
  </div>
</div>
```

**Save Logic:**

```javascript
async function saveChanges() {
    saving = true;
    errorMessage = '';
    
    const userIds = sharedUsers.map(u => u.user_id);
    
    try {
        const response = await fetch(
            `http://localhost:9099/lamb/v1/assistant-sharing/shares/${assistant.id}`,
            {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_ids: userIds })
            }
        );
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save changes');
        }
        
        onSaved();  // Refresh parent view
        onClose();  // Close modal
    } catch (error) {
        errorMessage = error.message;
        // Modal stays open, error displayed
    } finally {
        saving = false;
    }
}
```

**Tab Visibility:**

The "Share" tab only appears if the user has sharing permission:

```javascript
// Check permission when viewing assistant details
async function checkSharingPermission() {
    const response = await fetch(
        'http://localhost:9099/lamb/v1/assistant-sharing/check-permission',
        { headers: { 'Authorization': `Bearer ${userToken}` } }
    );
    
    if (response.ok) {
        const data = await response.json();
        canShare = data.can_share || false;
    }
}

// In template - conditional tab
{#if canShare}
  <button onclick={() => detailSubView = 'share'}>Share</button>
{/if}
```

#### 9.7.7 Admin UI for User Permissions

Organization administrators can manage sharing permissions at `/org-admin?view=users`:

**Toggle Switch UI:**

```svelte
<table>
  <thead>
    <tr>
      <th>Username</th>
      <th>Email</th>
      <th>Role</th>
      <th>Can Share</th>
    </tr>
  </thead>
  <tbody>
    {#each orgUsers as user}
      <tr>
        <td>{user.name}</td>
        <td>{user.email}</td>
        <td>{user.organization_role}</td>
        <td class="text-center">
          <label class="toggle-switch">
            <input type="checkbox" 
                   checked={getUserCanShare(user)}
                   onchange={(e) => toggleUserSharingPermission(user, e.target.checked)}>
            <span class="slider"></span>
          </label>
        </td>
      </tr>
    {/each}
  </tbody>
</table>
```

**Permission Toggle Logic:**

```javascript
function getUserCanShare(user) {
    const config = user.user_config || {};
    const userConfig = typeof config === 'string' ? JSON.parse(config) : config;
    return userConfig.can_share !== false; // Default to true
}

async function toggleUserSharingPermission(user, canShare) {
    try {
        const token = getAuthToken();
        const response = await axios.put(
            `http://localhost:9099/lamb/v1/assistant-sharing/user-permission/${user.id}?can_share=${canShare}`,
            {},
            { headers: { 'Authorization': `Bearer ${token}` } }
        );
        
        // Update local user object
        const userIndex = orgUsers.findIndex(u => u.id === user.id);
        if (userIndex !== -1) {
            const userConfig = orgUsers[userIndex].user_config || {};
            userConfig.can_share = canShare;
            orgUsers[userIndex].user_config = userConfig;
            orgUsers = [...orgUsers]; // Trigger reactivity
        }
    } catch (err) {
        console.error('Error updating sharing permission:', err);
        await fetchUsers(); // Revert on error
    }
}
```

#### 9.7.8 OWI Group Synchronization

Unlike Knowledge Base sharing (which is LAMB-only), Assistant sharing integrates with Open WebUI:

**Integration Pattern:**

When shares are updated, LAMB synchronizes with the corresponding OWI group:

```python
@router.put("/v1/assistant-sharing/shares/{assistant_id}")
async def update_assistant_shares(assistant_id: int, request: UpdateSharesRequest, current_user_id: int):
    """
    Update shares and sync with OWI group
    """
    # Calculate additions and removals
    current_shares = db.get_assistant_shares(assistant_id)
    current_user_ids = {share['shared_with_user_id'] for share in current_shares}
    desired_user_ids = set(request.user_ids)
    
    to_add = desired_user_ids - current_user_ids
    to_remove = current_user_ids - desired_user_ids
    
    # Update LAMB database
    for user_id in to_add:
        db.share_assistant(assistant_id, user_id, current_user_id)
    
    for user_id in to_remove:
        db.unshare_assistant(assistant_id, user_id)
    
    # Sync with OWI group (one operation after all changes)
    assistant = db.get_assistant_by_id(assistant_id)
    if assistant.get('group_id'):
        owi_group_manager = OwiGroupManager()
        all_user_ids = [current_user_id] + list(desired_user_ids)
        owi_users = [db.get_owi_user_by_creator_id(uid) for uid in all_user_ids]
        owi_user_ids = [u['id'] for u in owi_users if u]
        owi_group_manager.update_group_members(assistant['group_id'], owi_user_ids)
    
    return updated_shares_list
```

**Why Sync?** Shared users need access to the assistant in Open WebUI for chat functionality.

#### 9.7.9 Viewing Shared Assistants

**Shared Assistants View (`/assistants?view=shared`):**

Users can view all assistants shared with them:

```javascript
// Fetch shared assistants
async function fetchSharedAssistants() {
    const response = await fetch(
        'http://localhost:9099/creator/assistant/shared',
        { headers: { 'Authorization': `Bearer ${token}` } }
    );
    
    if (response.ok) {
        sharedAssistants = await response.json();
    }
}
```

**Display:**
- Grid/list view of shared assistants
- Shows owner name and sharing date
- View and Chat actions available
- Read-only badge indicator

#### 9.7.10 Usage Flow

**Sharing an Assistant:**

1. Assistant owner opens assistant details
2. Clicks "Share" tab (visible only if user has permission)
3. Views current shared users list
4. Clicks "Manage Shared Users" button
5. Modal opens with dual-panel interface:
   - Left: Currently shared users (with search)
   - Right: Available organization users (with search)
   - Center: Move buttons (<<, <, >, >>)
6. Owner adds/removes users using buttons
7. Clicks "Save Changes"
8. Backend:
   - Calculates additions and removals
   - Updates `assistant_shares` table
   - Syncs OWI group membership
9. Modal closes, share tab refreshes with new list

**Accessing Shared Assistant:**

1. User navigates to "Shared Assistants" view
2. Sees list of assistants shared with them
3. Clicks "View" to see details (read-only)
4. Clicks "Chat" to open chat interface
5. Backend verifies access:
   - Checks ownership OR sharing
   - Allows chat and view operations
   - Blocks edit/delete/publish operations

**Permission Denial:**

If user tries to access sharing features without permission:
- "Share" tab is hidden (frontend check)
- API returns 403 if called directly (backend check)
- User sees clear error message

#### 9.7.11 Security Model

**Authorization Checks:**

Every sharing operation verifies:
1. User is authenticated (valid JWT token)
2. User has sharing permission (org + user level)
3. User owns the assistant being shared
4. Target users are in same organization

**Audit Trail:**

Sharing operations are logged with:
- Sharer's email
- Affected assistant ID
- User IDs added/removed
- Timestamp
- Success/failure status

**Data Isolation:**

Sharing operates within organization boundaries:
- Users can only share with organization members
- Cross-organization sharing is not supported
- System organization users cannot be shared with

#### 9.7.12 Differences from KB Sharing

| Feature | KB Sharing | Assistant Sharing |
|---------|-----------|-------------------|
| Scope | Organization-wide (all or none) | Specific users |
| Protection | Cannot unshare if in use | No protection needed |
| OWI Integration | None | Group synchronization |
| UI Pattern | Simple toggle | Dual-panel modal |
| Permission System | None | Two-level (org + user) |

**Design Rationale:**

Knowledge Bases are documents that multiple assistants might reference, so organization-wide sharing makes sense. Assistants are more personal and specialized, so user-specific sharing provides better control.

---

## 10. LTI Integration

### 10.1 Publishing Flow

```
┌──────────┐                ┌──────────────┐              ┌────────────┐
│ Educator │                │     LAMB     │              │    OWI     │
│          │                │              │              │            │
└────┬─────┘                └──────┬───────┘              └─────┬──────┘
     │                             │                            │
     │ Publish Assistant           │                            │
     ├────────────────────────────►│                            │
     │                             │                            │
     │                             │ Create OWI Group           │
     │                             ├───────────────────────────►│
     │                             │                            │
     │                             │ Register Assistant as Model│
     │                             ├───────────────────────────►│
     │                             │                            │
     │                             │ Update Assistant in DB     │
     │                             │ (published=true, group_id) │
     │                             │                            │
     │ Return LTI Config           │                            │
     │◄────────────────────────────┤                            │
     │ (consumer key, secret)      │                            │
```

### 10.2 LTI Launch Flow

```
┌─────────┐            ┌─────────┐           ┌──────────┐         ┌────────┐
│ Student │            │   LMS   │           │   LAMB   │         │  OWI   │
│         │            │         │           │          │         │        │
└────┬────┘            └────┬────┘           └─────┬────┘         └───┬────┘
     │                      │                      │                  │
     │ Click LTI Activity   │                      │                  │
     ├─────────────────────►│                      │                  │
     │                      │                      │                  │
     │                      │ LTI Launch POST      │                  │
     │                      │ (OAuth signed)       │                  │
     │                      ├─────────────────────►│                  │
     │                      │                      │                  │
     │                      │                      │ Validate OAuth   │
     │                      │                      │ Signature        │
     │                      │                      │                  │
     │                      │                      │ Create/Get User  │
     │                      │                      ├─────────────────►│
     │                      │                      │                  │
     │                      │                      │ Generate Token   │
     │                      │                      │◄─────────────────┤
     │                      │                      │                  │
     │                      │ Redirect to OWI Chat │                  │
     │                      │ with Token           │                  │
     │◄─────────────────────┴──────────────────────┤                  │
     │                                             │                  │
     │                         Open Chat Interface │                  │
     ├──────────────────────────────────────────────────────────────►│
     │                                             │                  │
     │                     Interact with Assistant │                  │
     │◄────────────────────────────────────────────────────────────────┤
```

### 10.3 LTI Configuration

When assistant is published, generate LTI parameters:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<cartridge_basiclti_link xmlns="http://www.imsglobal.org/xsd/imslticc_v1p0"
    xmlns:blti = "http://www.imsglobal.org/xsd/imsbasiclti_v1p0"
    xmlns:lticm ="http://www.imsglobal.org/xsd/imslticm_v1p0"
    xmlns:lticp ="http://www.imsglobal.org/xsd/imslticp_v1p0"
    xmlns:xsi = "http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation = "http://www.imsglobal.org/xsd/imslticc_v1p0 http://www.imsglobal.org/xsd/lti/ltiv1p0/imslticc_v1p0.xsd
    http://www.imsglobal.org/xsd/imsbasiclti_v1p0 http://www.imsglobal.org/xsd/lti/ltiv1p0/imsbasiclti_v1p0.xsd
    http://www.imsglobal.org/xsd/imslticm_v1p0 http://www.imsglobal.org/xsd/lti/ltiv1p0/imslticm_v1p0.xsd
    http://www.imsglobal.org/xsd/imslticp_v1p0 http://www.imsglobal.org/xsd/lti/ltiv1p0/imslticp_v1p0.xsd">
    <blti:title>CS101 Assistant</blti:title>
    <blti:description>Learning Assistant for Computer Science 101</blti:description>
    <blti:launch_url>https://lamb.university.edu/lamb/simple_lti/launch</blti:launch_url>
    <blti:custom>
        <lticm:property name="assistant_id">42</lticm:property>
    </blti:custom>
</cartridge_basiclti_link>
```

**Consumer Credentials:**
- **Consumer Key:** `{oauth_consumer_name}`
- **Shared Secret:** Generated and stored securely

### 10.4 LTI User Mapping

When LTI launch occurs:

1. Extract user info from LTI parameters (`lis_person_contact_email_primary`, `lis_person_name_full`)
2. Check if OWI user exists with email
3. If not, create OWI user:
   - Use LTI email
   - Generate random password (user won't use it)
   - Create user in OWI auth and user tables
4. Add user to assistant's OWI group
5. Generate JWT token for user
6. Store LTI user record in LAMB database
7. Redirect to OWI chat with token

**Implementation:**

```python
@router.post("/simple_lti/launch")
async def lti_launch(request: Request):
    # Parse LTI parameters
    form_data = await request.form()
    user_email = form_data.get("lis_person_contact_email_primary")
    user_name = form_data.get("lis_person_name_full")
    assistant_id = form_data.get("custom_assistant_id")
    
    # Validate OAuth signature
    if not validate_oauth_signature(form_data):
        raise HTTPException(status_code=401, detail="Invalid OAuth signature")
    
    # Get or create OWI user
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_by_email(user_email)
    
    if not owi_user:
        # Create new OWI user
        password = secrets.token_urlsafe(32)
        owi_user = user_manager.create_user(
            email=user_email,
            name=user_name,
            password=password,
            role="user"
        )
    
    # Get assistant and group
    db_manager = LambDatabaseManager()
    assistant = db_manager.get_assistant_by_id(assistant_id)
    group_id = assistant['group_id']
    
    # Add user to group
    group_manager = OwiGroupManager()
    group_manager.add_user_to_group(group_id, owi_user['id'])
    
    # Generate token
    token = user_manager.get_auth_token(user_email, password)
    
    # Store LTI user record
    db_manager.create_lti_user(
        assistant_id=assistant_id,
        assistant_name=assistant['name'],
        group_id=group_id,
        user_email=user_email,
        user_name=user_name
    )
    
    # Redirect to OWI chat
    owi_url = f"{OWI_PUBLIC_BASE_URL}/?token={token}&model=lamb_assistant.{assistant_id}"
    return RedirectResponse(url=owi_url)
```

---

## 11. Plugin Architecture

### 11.1 Plugin Types

LAMB supports three plugin types:

1. **Prompt Processors (PPS):** Transform and augment messages before LLM
2. **Connectors:** Connect to LLM providers (OpenAI, Ollama, etc.)
3. **RAG Processors:** Retrieve and format context from Knowledge Bases

### 11.2 Plugin Structure

**Location:** `/backend/lamb/completions/{plugin_type}/`

**Naming Convention:**
- File: `{plugin_name}.py`
- Function: Specific to plugin type (see below)

### 11.3 Prompt Processor Plugin

**Function Signature:**

```python
def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Process and augment messages
    
    Args:
        request: Original completion request
        assistant: Assistant configuration
        rag_context: Retrieved context from RAG processor
    
    Returns:
        List of message dicts with 'role' and 'content'
    """
    pass
```

**Example (`simple_augment.py`):**

```python
def prompt_processor(request, assistant=None, rag_context=None):
    messages = []
    
    # Add system prompt
    if assistant and assistant.system_prompt:
        system_content = assistant.system_prompt
        
        # Inject RAG context
        if rag_context and rag_context.get("context"):
            system_content += f"\n\nRelevant information:\n{rag_context['context']}"
        
        messages.append({"role": "system", "content": system_content})
    
    # Add user messages
    for msg in request.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    return messages
```

### 11.4 Connector Plugin

**Function Signature:**

```python
async def llm_connect(
    messages: list,
    stream: bool = False,
    body: Dict[str, Any] = None,
    llm: str = None,
    assistant_owner: Optional[str] = None
):
    """
    Connect to LLM provider
    
    Args:
        messages: Processed messages from PPS
        stream: Whether to stream response
        body: Original request body
        llm: Specific model to use
        assistant_owner: Email of assistant owner (for org config)
    
    Returns:
        AsyncGenerator[str] if stream=True (SSE format)
        Dict if stream=False (OpenAI format)
    """
    pass
```

**Example (`openai.py`):** (See section 7.2 for full implementation)

### 11.5 RAG Processor Plugin

**Function Signature:**

```python
def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None
) -> Dict[str, Any]:
    """
    Retrieve context from Knowledge Base
    
    Args:
        messages: User messages
        assistant: Assistant configuration (has RAG_collections, RAG_Top_k)
    
    Returns:
        Dict with:
            - "context": str (formatted context)
            - "sources": List[Dict] (source citations)
    """
    pass
```

**Example (`simple_rag.py`):** (See section 7.2 for full implementation)

### 11.6 Creating Custom Plugins

**Step 1: Create Plugin File**

```bash
# For prompt processor
touch /opt/lamb/backend/lamb/completions/pps/my_processor.py

# For connector
touch /opt/lamb/backend/lamb/completions/connectors/my_connector.py

# For RAG processor
touch /opt/lamb/backend/lamb/completions/rag/my_rag.py
```

**Step 2: Implement Plugin Function**

```python
# my_processor.py
def prompt_processor(request, assistant=None, rag_context=None):
    # Custom logic here
    messages = []
    # ... process messages
    return messages
```

**Step 3: Plugin is Auto-Loaded**

Plugins are dynamically loaded at runtime. No registration needed.

**Step 4: Configure Assistant to Use Plugin**

Update assistant metadata:

```json
{
  "prompt_processor": "my_processor",
  "connector": "openai",
  "llm": "gpt-4o",
  "rag_processor": "simple_rag"
}
```

### 11.7 Available Plugins

**Prompt Processors:**
- `simple_augment`: Adds system prompt and RAG context

**Connectors:**
- `openai`: OpenAI API (organization-aware)
- `ollama`: Ollama local models (organization-aware)
- `banana_img`: Google Gen AI (Gemini) image generation with intelligent routing (organization-aware)
- `bypass`: Testing connector (returns messages as-is)

**RAG Processors:**
- `simple_rag`: Queries KB server and formats context
- `single_file_rag`: Retrieves from single file
- `no_rag`: No retrieval (returns empty context)

### 11.8 Banana Image Connector (`banana_img`)

The `banana_img` connector provides intelligent image generation using Google Gen AI SDK (Gemini) with automatic request routing.

#### 11.8.1 Overview

**Purpose:** Generate images from text prompts while gracefully handling chat interface metadata requests (titles, tags).

**Key Features:**
- Automatic request type detection (title generation vs image generation)
- Intelligent routing: text requests → GPT-4o-mini, image requests → Google Gen AI (Gemini)
- File-based image storage with markdown responses
- Organization-aware configuration for both OpenAI and Google Gen AI
- Support for multiple image formats (JPEG, PNG, WebP)
- Configurable aspect ratios and image counts
- Uses the unified Google Gen AI SDK (`google-genai`) for all Google generative AI models

#### 11.8.2 Request Routing Logic

The connector uses pattern matching to detect title/tags generation requests:

```python
# Title generation patterns (routed to GPT-4o-mini)
patterns = [
    "generate.*title",
    "create.*title", 
    "suggest.*title",
    "generate.*tags",
    "categorizing.*themes",
    "chat history",
    "conversation title",
    "summarize.*conversation"
]
```

**Routing Behavior:**
- **Title Request Detected** → Use GPT-4o-mini for text generation
- **Image Request** → Use Vertex AI Imagen for image generation

#### 11.8.3 Image Storage Strategy

Generated images are stored in the backend filesystem:

```
/backend/static/public/{user_id}/img/{filename}
```

**Path Components:**
- `{user_id}`: **Database ID** from `Creator_users.id` field (e.g., `1`, `42`, `123`)
  - Retrieved by looking up `assistant_owner` email in `Creator_users` table
  - Falls back to `"default"` if user not found
- `{filename}`: `img_{timestamp}_{uuid}.{format}` (e.g., `img_1701234567890_a1b2c3d4.jpeg`)

**Storage Creation:**
- Directories created automatically on first use
- Permissions inherit from parent directories
- Images accessible via `/static/public/{user_id}/img/{filename}` URL

**User ID Resolution:**

```python
# Code flow:
1. Get assistant_owner email (e.g., "admin@owi.com")
2. Query Creator_users table: SELECT id FROM Creator_users WHERE user_email = ?
3. Use returned id (e.g., 1) as user_id
4. Create directory: /backend/static/public/1/img/
5. Save image: /backend/static/public/1/img/img_1701234567890_abc123.jpeg
```

**Example Directory Structure:**

```
backend/static/public/
├── 1/                    # User ID 1
│   └── img/
│       ├── img_1701234567890_abc123.jpeg
│       └── img_1701234568123_def456.png
├── 2/                    # User ID 2
│   └── img/
│       └── img_1701234568901_ghi789.jpeg
└── default/              # Fallback for unknown users
    └── img/
        └── img_1701234569012_jkl012.jpeg
```

#### 11.8.4 Response Format

**For Image Generation:**

Returns OpenAI-compatible chat completion with markdown image links:

```json
{
  "id": "chatcmpl-img_1701234567",
  "object": "chat.completion",
  "created": 1701234567,
  "model": "gemini-2.0-flash-preview-image-generation",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "![Generated Image](/static/public/1/img/img_1701234567890_a1b2c3d4.jpeg)"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 0,
    "total_tokens": 10
  }
}
```

**Note:** The URL uses the numeric user ID (`1`) from the `Creator_users.id` field, not a sanitized email address.

**For Title Generation:**

Returns standard OpenAI chat completion format from GPT-4o-mini.

#### 11.8.5 Configuration

**Organization Config (Google Gen AI):**

```json
{
  "google": {
    "enabled": true,
    "api_key": "your-gemini-api-key"
  },
  "openai": {
    "enabled": true,
    "api_key": "sk-...",
    "models": ["gpt-4o-mini", "gpt-4o"]
  }
}
```

**Environment Variables Fallback:**

```bash
# For Google Gen AI (Gemini)
GEMINI_API_KEY=your-gemini-api-key
# or
GOOGLE_API_KEY=your-gemini-api-key

# For title generation (GPT-4o-mini)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
```

#### 11.8.5.1 Google Gen AI Authentication Setup

**Simplified Authentication:** The Google Gen AI SDK uses API key authentication, which is simpler than the previous Vertex AI service account approach.

**Getting Your API Key:**

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API Key" or navigate to API Keys section
4. Create a new API key or copy an existing one
5. Store the key securely

**Configuration Options:**

**Option A: Environment Variable (Recommended)**

```bash
export GEMINI_API_KEY=your-api-key-here
# or
export GOOGLE_API_KEY=your-api-key-here
```

**Option B: Docker Compose**

```yaml
services:
  backend:
    environment:
      - GEMINI_API_KEY=your-api-key-here
      # For title generation (GPT-4o-mini)
      - OPENAI_API_KEY=sk-...
```

**Option C: Organization Config**

Store the API key in organization settings for multi-tenant deployments:

```json
{
  "setups": {
    "default": {
      "providers": {
        "google": {
          "enabled": true,
          "api_key": "your-gemini-api-key"
        }
      }
    }
  }
}
```

**Testing Configuration:**

```python
# Test script: test_genai_auth.py
import os
from google import genai

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
print(f"API Key configured: {'Yes' if api_key else 'No'}")

try:
    client = genai.Client(api_key=api_key)
    print("✅ Google Gen AI client initialized successfully")
except Exception as e:
    print(f"❌ Error: {e}")
```

**Security Best Practices:**

1. **Never commit API keys to git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment variables** instead of hardcoding keys

3. **Rotate keys regularly** via Google AI Studio

4. **Use organization config** for multi-tenant deployments where each organization has their own API key

**Troubleshooting:**

**Error: `API key not valid`**

- ✅ Verify API key is correct and not expired
- ✅ Check for extra whitespace in the key
- ✅ Ensure the key has access to Gemini image generation models

**Error: `Model not found`**

- ✅ Verify model name is correct (e.g., `gemini-2.0-flash-preview-image-generation`)
- ✅ Check if your API key has access to image generation models
- ✅ Some models may require specific API tier access

**Error: `Quota exceeded`**

- ✅ Check your usage limits in Google AI Studio
- ✅ Consider upgrading your API tier for higher limits

#### 11.8.6 Generation Parameters

**Supported Parameters (via request body):**

- `number_of_images`: 1-4 images (default: 1)
- `aspect_ratio`: "1:1", "3:4", "4:3", "16:9", "9:16" (default: "16:9")
- `output_mime_type`: "image/jpeg", "image/png", "image/webp" (default: "image/jpeg")

**Example Request:**

```json
{
  "model": "lamb_assistant.123",
  "messages": [
    {
      "role": "user",
      "content": "Generate an image of a sunset over mountains"
    }
  ],
  "number_of_images": 2,
  "aspect_ratio": "16:9",
  "output_mime_type": "image/png"
}
```

#### 11.8.7 Assistant Configuration

To use `banana_img` connector in an assistant:

```json
{
  "connector": "banana_img",
  "llm": "imagen-4.0-generate-001",
  "prompt_processor": "simple_augment",
  "rag_processor": ""
}
```

**Available Models (MUST use exact names):**

**Gemini Models (uses `generate_content` API - may work with free tier):**
- `gemini-2.5-flash-image-preview`: Gemini 2.5 Flash preview (cheapest, recommended for free tier)
- `gemini-2.5-flash-image`: Gemini 2.5 Flash with image generation

**Imagen Models (uses `generate_images` API - requires billing):**
- `imagen-4.0-fast-generate-001`: Imagen 4 Fast - faster generation, good quality
- `imagen-4.0-generate-001`: Imagen 4 - high quality image generation

**⚠️ Important:** 
- Gemini models use a different API (`generate_content`) and may work with free tier accounts
- Imagen models require billing to be enabled in Google Cloud Console
- The model name must match exactly. Invalid model names will be rejected with a clear error message listing available options.

#### 11.8.8 Error Handling

**Common Errors:**

- **No Google Gen AI API Key**: Check organization config and environment variables (GEMINI_API_KEY or GOOGLE_API_KEY)
- **No OpenAI API Key**: Required for title generation fallback
- **Image Generation Failed**: Check API key validity and quota
- **No Prompt Found**: Ensure messages contain user content

**Graceful Degradation:**
- Title requests always fallback to GPT-4o-mini
- Image generation errors return descriptive error messages
- Organization config failures fallback to environment variables

#### 11.8.9 Performance Considerations

**Image Storage:**
- Images stored permanently until manually deleted
- No automatic cleanup implemented
- Consider implementing TTL or cleanup policies for production

**File System Impact:**
- Each user gets separate directory (`/public/{user_id}/img/`)
- No size limits enforced (monitor disk usage)
- Images served directly by backend static file handler

**API Costs:**
- Google Gen AI (Gemini) charges per image generation
- GPT-4o-mini charges for title generation (minimal)
- Organization-specific API keys allow cost tracking per org

#### 11.8.10 Testing

**Manual Test (Title Generation):**

```bash
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lamb_assistant.123",
    "messages": [
      {
        "role": "user",
        "content": "Generate a title for this conversation about machine learning"
      }
    ]
  }'
```

**Manual Test (Image Generation):**

```bash
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lamb_assistant.123",
    "messages": [
      {
        "role": "user",
        "content": "A beautiful sunset over mountains with vibrant colors"
      }
    ],
    "aspect_ratio": "16:9"
  }'
```

**Expected Response:** Markdown with image link that displays in Open WebUI chat interface.

#### 11.8.11 Integration with Open WebUI

**Chat Interface Behavior:**

1. User sends image generation prompt
2. Backend detects it's not a title request
3. Backend resolves user ID from `assistant_owner` email via `Creator_users` table
4. Google Gen AI (Gemini) generates image
5. Image saved to `/backend/static/public/{user_id}/img/` (where `{user_id}` is the numeric ID)
6. Markdown response sent to Open WebUI with image URL
7. Open WebUI renders markdown → displays image inline

**Title/Tags Requests:**

1. Open WebUI requests conversation title/tags
2. Backend detects title generation pattern
3. Routes to GPT-4o-mini for text generation
4. Returns JSON/text response as expected by Open WebUI

---

## 12. Frontend Architecture

### 12.1 SvelteKit Structure

```
/frontend/svelte-app/
├── src/
│   ├── routes/              # Page routes
│   │   ├── +layout.svelte   # Root layout
│   │   ├── +page.svelte     # Home (redirects to /assistants)
│   │   ├── assistants/
│   │   │   └── +page.svelte # Assistants list
│   │   ├── knowledgebases/
│   │   │   └── +page.svelte # Knowledge Bases list
│   │   ├── admin/
│   │   │   └── +page.svelte # Admin panel
│   │   └── org-admin/
│   │       └── +page.svelte # Organization admin panel
│   ├── lib/
│   │   ├── components/      # Reusable UI components
│   │   ├── services/        # API service modules
│   │   ├── stores/          #Svelte stores for state
│   │   │   ├── utils/           # Utility functions
│   │   │   ├── locales/         # i18n translations
│   │   │   ├── config.js        # Runtime configuration
│   │   │   └── i18n.js          # i18n setup
│   │   ├── app.html             # HTML template
│   │   └── app.css              # Global styles
├── static/
│   ├── config.js.sample         # Config template
│   └── favicon.png
├── package.json
├── vite.config.js
└── svelte.config.js
```

### 12.2 Routing

**Key Routes:**
- `/` - Home (redirects to /assistants)
- `/assistants` - Assistants list
- `/knowledgebases` - Knowledge Bases
- `/admin` - Admin panel (admin only)
- `/org-admin` - Organization admin

### 12.3 Configuration

**Runtime Config (`static/config.js`):**
```javascript
window.LAMB_CONFIG = {
    api: {
        lambServer: 'http://localhost:9099',
        owebuiServer: 'http://localhost:8080'
    }
};
```

---

## 13. Deployment Architecture

See `/docker-compose.yaml` for complete configuration. All services run on `lamb` Docker network.

**Production Checklist:**
- Change `LAMB_BEARER_TOKEN`
- Configure SSL/TLS
- Set up backups
- Configure organization LLM keys

---

## 14. Development Workflow

```bash
export LAMB_PROJECT_PATH=$(pwd)
docker-compose up -d
```

**Access:**
- Frontend: http://localhost:5173
- Backend: http://localhost:9099  
- OWI: http://localhost:8080

---

## 15. End User Feature

### 15.1 Overview

The end_user feature provides a streamlined login experience for users who only need to interact with published assistants without accessing the creator interface.

### 15.2 Implementation Details

**Database Schema:**
- `user_type` column in `Creator_users` table
- CHECK constraint: `user_type IN ('creator', 'end_user')`
- Default value: `'creator'` for backward compatibility
- Automatic migration on database initialization

**Login Flow Differences:**

| Step | Creator User | End User |
|------|--------------|----------|
| 1. Login credentials | Verified | Verified |
| 2. Backend response | Returns user_type='creator' | Returns user_type='end_user' |
| 3. Frontend action | Store token, navigate to / | Redirect to launch_url |
| 4. User sees | LAMB creator interface | Open WebUI only |

**Backend Changes:**
- `get_creator_user_by_email()` - SELECTs and returns user_type
- `create_creator_user()` - Accepts user_type parameter
- `/creator/login` - Returns user_type in response
- `/creator/admin/users/create` - Accepts user_type parameter
- `/creator/admin/org-admin/users` - Org admins can create end_users

**Frontend Changes:**
- `Login.svelte` - Detects user_type and redirects end_users
- `admin/+page.svelte` - User Type dropdown for system admins
- `org-admin/+page.svelte` - User Type dropdown for org admins
- `Nav.svelte` - Hides Org Admin link from non-admins

**Migration:**
```python
def run_migrations(self):
    """Run database migrations for schema updates"""
    # Add user_type column if it doesn't exist
    cursor.execute(f"PRAGMA table_info({self.table_prefix}Creator_users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'user_type' not in columns:
        cursor.execute(f"""
            ALTER TABLE {self.table_prefix}Creator_users 
            ADD COLUMN user_type TEXT NOT NULL DEFAULT 'creator' 
            CHECK(user_type IN ('creator', 'end_user'))
        """)
```

### 15.3 URL Configuration

**Important:** End users are redirected using `OWI_PUBLIC_BASE_URL`:
- `OWI_BASE_URL` - Internal Docker network URL (e.g., `http://openwebui:8080`)
- `OWI_PUBLIC_BASE_URL` - Public browser-accessible URL (e.g., `http://localhost:8080`)

The `launch_url` returned by login uses `OWI_PUBLIC_BASE_URL` to ensure browsers can access Open WebUI.

### 15.4 Testing

Comprehensive Playwright test suite in `/testing/playwright/end_user_tests/`:
- `test_end_user_creation.js` - Test admin creating end_users
- `test_end_user_login.js` - Test end_user login and redirect
- `test_creator_vs_enduser.js` - Compare both user types
- `test_end_user_full_suite.js` - Complete test suite
- `run_end_user_tests.sh` - Automated test runner

---

## 16. User Blocking Feature

### 16.1 Overview

The user blocking feature allows system administrators and organization administrators to disable user accounts, preventing login while preserving all user-created resources. This feature is essential for:
- Handling security incidents
- Managing inactive accounts
- Enforcing organizational policies
- Temporary suspensions

**Key Principle:** Disabled users cannot login, but their published assistants, shared Knowledge Bases, templates, and rubrics remain fully functional and accessible to others.

### 16.2 Database Schema

#### 16.2.1 Enabled Column

Added to `Creator_users` table:

```sql
ALTER TABLE Creator_users 
ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1;

CREATE INDEX idx_creator_users_enabled ON Creator_users(enabled);
```

**Field Details:**
- **Type:** BOOLEAN (SQLite: INTEGER 0/1)
- **Default:** 1 (enabled/TRUE)
- **Indexed:** Yes, for performance
- **Migration:** Automatic on backend startup
- **Backward Compatible:** All existing users default to enabled

### 16.3 Database Manager Methods

**File:** `backend/lamb/database_manager.py`

#### Single User Operations

```python
def disable_user(self, user_id: int) -> bool:
    """
    Disable a user account
    
    Returns:
        bool: True if successful, False if already disabled or not found
    """
    
def enable_user(self, user_id: int) -> bool:
    """
    Enable a user account
    
    Returns:
        bool: True if successful, False if already enabled or not found
    """
    
def is_user_enabled(self, user_id: int) -> bool:
    """
    Check if user account is enabled
    
    Returns:
        bool: True if enabled, False if disabled or not found
    """
```

#### Bulk Operations

```python
def disable_users_bulk(self, user_ids: List[int]) -> Dict[str, Any]:
    """
    Disable multiple user accounts in a single transaction
    
    Returns:
        Dict with keys: success, failed, already_disabled (lists of user IDs)
    """
    
def enable_users_bulk(self, user_ids: List[int]) -> Dict[str, Any]:
    """
    Enable multiple user accounts in a single transaction
    
    Returns:
        Dict with keys: success, failed, already_enabled (lists of user IDs)
    """
```

**Transaction Safety:** Bulk operations use database transactions to ensure all-or-nothing semantics within the loop.

### 16.4 Authentication & Login Flow

**File:** `backend/lamb/creator_user_router.py`

Login check added in `verify_creator_user()`:

```python
# Check if user account is enabled
if not user.get('enabled', True):
    logger.warning(f"Disabled user {user_data.email} attempted login")
    raise HTTPException(
        status_code=403,
        detail="Account has been disabled. Please contact your administrator."
    )
```

**Behavior:**
- Disabled users receive HTTP 403 (Forbidden)
- Clear error message displayed to user
- Login attempt logged for audit trail
- Credential verification happens before enabled check (prevents information leakage)

### 16.5 Admin API Endpoints

**File:** `backend/creator_interface/main.py`

#### Individual Operations

**Disable User:**
```http
PUT /creator/admin/users/{user_id}/disable
Authorization: Bearer {admin_token}

Response 200:
{
  "success": true,
  "message": "User user@example.com has been disabled"
}
```

**Enable User:**
```http
PUT /creator/admin/users/{user_id}/enable
Authorization: Bearer {admin_token}

Response 200:
{
  "success": true,
  "message": "User user@example.com has been enabled"
}
```

#### Bulk Operations

**Bulk Disable:**
```http
POST /creator/admin/users/disable-bulk
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "user_ids": [1, 2, 3]
}

Response 200:
{
  "success": true,
  "disabled": 3,
  "failed": 0,
  "already_disabled": 0,
  "details": {
    "success": [1, 2, 3],
    "failed": [],
    "already_disabled": []
  }
}
```

**Bulk Enable:**
```http
POST /creator/admin/users/enable-bulk
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "user_ids": [1, 2, 3]
}

Response 200:
{
  "success": true,
  "enabled": 3,
  "failed": 0,
  "already_enabled": 0,
  "details": {
    "success": [1, 2, 3],
    "failed": [],
    "already_enabled": []
  }
}
```

### 16.6 Security Features

**Authorization:**
- ✅ Only system admins can disable/enable users
- ✅ Organization admins can manage users in their organization
- ✅ Checked via `is_admin_user()` helper

**Self-Protection:**
- ✅ Users cannot disable themselves
- ✅ Bulk operations automatically remove current user from list
- ✅ Clear error message if self-disable attempted

**Audit Trail:**
- ✅ All enable/disable operations logged with admin email
- ✅ Includes user ID, action, and timestamp
- ✅ Failed attempts logged with reason

**Example Log Entries:**
```
INFO: Admin admin@example.com disabled user 123
WARNING: Removed self (1) from bulk disable list
INFO: Bulk disable: 3 successful, 0 failed
```

### 16.7 User List Updates

**File:** `backend/lamb/database_manager.py`

Updated `get_creator_users()` to include enabled status:

```sql
SELECT u.id, u.user_email, u.user_name, u.user_config, u.organization_id,
       o.name as org_name, o.slug as org_slug, o.is_system,
       COALESCE(r.role, 'member') as org_role, u.user_type, u.enabled
FROM Creator_users u
LEFT JOIN organizations o ON u.organization_id = o.id
LEFT JOIN organization_roles r ON u.id = r.user_id AND r.organization_id = u.organization_id
ORDER BY u.id
```

**API Response Structure:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "email": "user@example.com",
      "name": "Test User",
      "role": "user",
      "enabled": true,
      "user_type": "creator",
      "organization": {
        "name": "Engineering",
        "slug": "engineering",
        "is_system": false
      },
      "organization_role": "member"
    }
  ]
}
```

### 16.8 Frontend Service Layer

**File:** `frontend/svelte-app/src/lib/services/adminService.js` (NEW)

```javascript
/**
 * Disable a user account
 */
export async function disableUser(token, userId) {
  const response = await fetch(getApiUrl(`/admin/users/${userId}/disable`), {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
}

/**
 * Enable a user account
 */
export async function enableUser(token, userId) { /* ... */ }

/**
 * Disable multiple user accounts
 */
export async function disableUsersBulk(token, userIds) { /* ... */ }

/**
 * Enable multiple user accounts
 */
export async function enableUsersBulk(token, userIds) { /* ... */ }
```

### 16.9 Frontend UI Patterns

**Status Display:**

```svelte
<td>
  {#if user.enabled}
    <span class="badge badge-success">Active</span>
  {:else}
    <span class="badge badge-error">Disabled</span>
  {/if}
</td>
```

**Action Buttons:**

```svelte
<td>
  {#if user.enabled}
    <button class="btn btn-sm btn-warning" onclick={() => showDisableDialog(user)}>
      Disable
    </button>
  {:else}
    <button class="btn btn-sm btn-success" onclick={() => showEnableDialog(user)}>
      Enable
    </button>
  {/if}
</td>
```

**Bulk Selection:**

```svelte
{#if selectedUsers.length > 0}
  <div class="bulk-actions-toolbar bg-base-200 p-4 rounded-lg mb-4">
    <span>{selectedUsers.length} user(s) selected</span>
    <button class="btn btn-sm btn-warning" onclick={handleBulkDisable}>
      Disable Selected
    </button>
    <button class="btn btn-sm btn-success" onclick={handleBulkEnable}>
      Enable Selected
    </button>
  </div>
{/if}
```

### 16.10 Resource Preservation

**What Continues Working:**
- ✅ Published assistants remain accessible via LTI
- ✅ Shared Knowledge Bases remain accessible
- ✅ Templates remain available to other users
- ✅ Rubrics remain accessible
- ✅ All data preserved in database
- ✅ Organization membership maintained

**What Stops Working:**
- ❌ User cannot login to creator interface
- ❌ User cannot login as end_user to Open WebUI
- ❌ User cannot create new resources
- ❌ User cannot modify existing resources
- ❌ User cannot access any LAMB features

**Technical Reason:** The `enabled` check only affects authentication. All database relationships and foreign keys remain intact, allowing other users to continue using shared resources.

### 16.11 Testing Strategy

**Unit Tests:**
```python
def test_disable_user():
    """Test disabling a user"""
    db = LambDatabaseManager()
    user_id = create_test_user()
    
    result = db.disable_user(user_id)
    assert result is True
    assert db.is_user_enabled(user_id) is False

def test_disabled_user_login():
    """Test that disabled users cannot login"""
    # Create and disable user
    user = create_test_user(email="test@example.com")
    db.disable_user(user['id'])
    
    # Attempt login
    response = client.post("/creator/login", data={
        "email": "test@example.com",
        "password": "testpass"
    })
    
    assert response.status_code == 403
    assert "disabled" in response.json()['detail'].lower()
```

**Integration Tests:**
- Verify admin can disable users
- Verify non-admin cannot disable users
- Verify self-disable prevention
- Verify published assistants work with disabled owner
- Verify bulk operations

**E2E Tests (Playwright):**
- Admin UI workflow for disabling users
- Disabled user login attempt
- Bulk selection and disable
- Status badges display correctly

### 16.12 Migration Process

**Automatic Migration:**
1. Backend starts up
2. `run_migrations()` checks for `enabled` column
3. If not exists:
   - Add column with DEFAULT 1
   - Create index
   - Log success
4. All existing users remain enabled

**Rollback Plan:**
```sql
-- Remove feature without data loss
ALTER TABLE Creator_users DROP COLUMN enabled;
DROP INDEX idx_creator_users_enabled;
```

### 16.13 Performance Considerations

**Index Usage:**
- `idx_creator_users_enabled` allows fast filtering of disabled users
- Login check uses indexed column (minimal overhead)
- Bulk operations use transactions (consistent performance)

**Query Performance:**
```sql
-- Fast query using index
SELECT * FROM Creator_users WHERE enabled = 1;

-- Login check (indexed)
SELECT enabled FROM Creator_users WHERE id = ?;
```

**Load Impact:**
- Negligible impact on login (one additional WHERE clause)
- Bulk operations scale linearly with user count
- No impact on completions or assistant operations

### 16.14 Future Enhancements

**Audit Log Table:**
```sql
CREATE TABLE user_status_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL, -- 'disable' or 'enable'
    admin_email TEXT NOT NULL,
    reason TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Creator_users(id)
);
```

**Scheduled Re-enablement:**
- Add `disabled_until` timestamp column
- Background job to auto-enable after timeout
- Useful for temporary suspensions

**Email Notifications:**
- Notify users when disabled
- Notify users when re-enabled
- Configurable templates

**Grace Period:**
- Warning before disable
- Read-only mode for X days
- Full disable after grace period

---

## 17. Chat Analytics Feature

### 17.1 Overview

The Chat Analytics feature provides assistant owners with insights into how their learning assistants are being used. It queries the Open WebUI database to extract and analyze chat conversations.

**Key Features:**
- View chat conversations for specific assistants
- Usage statistics (total chats, unique users, messages)
- Activity timeline visualization
- Date range filtering
- Privacy-respecting anonymization (configurable)

**Added:** December 27, 2025

### 17.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Creator Interface                         │
│  GET /creator/analytics/assistant/{id}/chats                │
│  GET /creator/analytics/assistant/{id}/stats                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  ChatAnalyticsService                        │
│  backend/lamb/services/chat_analytics_service.py            │
│  - get_chats_for_assistant()                                │
│  - get_chat_detail()                                        │
│  - get_assistant_stats()                                    │
│  - get_assistant_timeline()                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Open WebUI Database (webui.db)                  │
│  - chat table (conversations with JSON messages)            │
│  - user table (user info for anonymization)                 │
└─────────────────────────────────────────────────────────────┘
```

### 17.3 OWI Chat Table Structure

The chat analytics service queries the Open WebUI `chat` table:

```sql
CREATE TABLE "chat" (
    "id" VARCHAR(255) NOT NULL,
    "user_id" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL,
    "share_id" VARCHAR(255),
    "archived" INTEGER NOT NULL,
    "created_at" DATETIME NOT NULL,
    "updated_at" DATETIME NOT NULL,
    chat JSON,
    pinned BOOLEAN,
    meta JSON DEFAULT '{}' NOT NULL,
    folder_id TEXT
);
```

**Chat JSON Structure:**
```json
{
  "models": ["lamb_assistant.{assistant_id}"],
  "history": {
    "messages": {
      "msg-uuid-1": {
        "id": "msg-uuid-1",
        "role": "user",
        "content": "User message text",
        "timestamp": 1735300000
      },
      "msg-uuid-2": {
        "id": "msg-uuid-2", 
        "role": "assistant",
        "content": "Assistant response text",
        "timestamp": 1735300005
      }
    }
  }
}
```

### 17.4 API Endpoints

#### 17.4.1 List Chats

```http
GET /creator/analytics/assistant/{assistant_id}/chats
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| start_date | datetime | No | Filter from date (ISO format) |
| end_date | datetime | No | Filter until date (ISO format) |
| page | int | No | Page number (default: 1) |
| per_page | int | No | Items per page (default: 20, max: 100) |

**Response:**
```json
{
  "chats": [
    {
      "id": "493b9867-ce4d-497a-a174-8034065b3e1b",
      "title": "Math Help",
      "user_id": "User_001",
      "user_name": "User_001",
      "user_email": null,
      "message_count": 8,
      "created_at": "2025-12-27T10:30:00",
      "updated_at": "2025-12-27T10:45:00"
    }
  ],
  "total": 247,
  "page": 1,
  "per_page": 20,
  "total_pages": 13
}
```

#### 17.4.2 Get Chat Detail

```http
GET /creator/analytics/assistant/{assistant_id}/chats/{chat_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "493b9867-ce4d-497a-a174-8034065b3e1b",
  "title": "Math Help",
  "user": {
    "id": "User_001",
    "name": "User_001",
    "email": null
  },
  "created_at": "2025-12-27T10:30:00",
  "updated_at": "2025-12-27T10:45:00",
  "messages": [
    {
      "id": "f498e761-6bb2-4fc4-9f63-4543ffb54cec",
      "role": "user",
      "content": "Can you help me understand quadratic equations?",
      "timestamp": "2025-12-27T10:30:00"
    },
    {
      "id": "ceefb82e-5154-4c32-b738-4b31a5cb90aa",
      "role": "assistant",
      "content": "Of course! Quadratic equations are...",
      "timestamp": "2025-12-27T10:30:05"
    }
  ]
}
```

#### 17.4.3 Get Statistics

```http
GET /creator/analytics/assistant/{assistant_id}/stats
Authorization: Bearer {token}
```

**Response:**
```json
{
  "assistant_id": 1,
  "period": {
    "start": null,
    "end": null
  },
  "stats": {
    "total_chats": 247,
    "unique_users": 89,
    "total_messages": 1456,
    "avg_messages_per_chat": 5.9
  }
}
```

#### 17.4.4 Get Timeline

```http
GET /creator/analytics/assistant/{assistant_id}/timeline
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| period | string | No | Aggregation: "day", "week", "month" (default: day) |
| start_date | datetime | No | Timeline from date |
| end_date | datetime | No | Timeline until date |

**Response:**
```json
{
  "assistant_id": 1,
  "period": "day",
  "data": [
    {"date": "2025-12-20", "chat_count": 12, "message_count": 67},
    {"date": "2025-12-21", "chat_count": 15, "message_count": 89}
  ]
}
```

### 17.5 Privacy & Anonymization

**Default Behavior:** User data is anonymized by default for privacy protection.

**Anonymization:**
- User IDs replaced with sequential identifiers ("User_001", "User_002", etc.)
- User names follow same anonymization pattern
- User email set to `null`
- Chat content remains accessible (for quality assurance)

**Organization Configuration:**
Organizations can configure anonymization via `config.analytics.anonymize_users`:

```json
{
  "config": {
    "analytics": {
      "anonymize_users": true
    }
  }
}
```

### 17.6 Authorization

**Access Control:**
- Only assistant **owners** can view analytics
- Checked via `assistant.owner == user.email`
- Shared users cannot view analytics
- Organization admins cannot override (by design)

### 17.7 Frontend Integration

**Location:** `frontend/svelte-app/src/lib/components/analytics/ChatAnalytics.svelte`

**Features:**
- Stats cards displaying key metrics
- Simple bar chart for activity timeline (last 14 days)
- Date range filter
- Paginated chat list table
- Chat detail modal with conversation view

**Tab Integration:**
The Analytics tab appears in the assistant detail view for owners:
- Tabs: Properties | Edit | Share | Chat | **Analytics**
- Only visible to assistant owners (`isOwner` check)

### 17.8 Service Layer

**File:** `backend/lamb/services/chat_analytics_service.py`

**Class:** `ChatAnalyticsService`

**Methods:**
| Method | Purpose |
|--------|---------|
| `get_chats_for_assistant()` | List chats with pagination and filtering |
| `get_chat_detail()` | Get full conversation with messages |
| `get_assistant_stats()` | Calculate usage statistics |
| `get_assistant_timeline()` | Aggregate activity over time |
| `get_unique_models()` | List models used in chats |

### 17.9 Security Notes

**Removed Endpoints (Dec 2025):**
The `/lamb/v1/OWI/*` endpoints were removed as they posed a security risk by exposing internal OWI database operations. Chat analytics functionality is now properly secured through:
- User authentication (JWT token validation)
- Ownership verification
- Anonymization by default

---

## 18. Centralized Logging System

### 18.1 Overview

The LAMB backend implements a centralized logging system that eliminates code duplication, removes legacy utilities, and provides unified environment-based configuration for all logging operations.

**Key Benefits:**
- **Single Point of Control:** One environment variable controls all logging by default
- **Fine-Grained Control:** Optional component-specific overrides for targeted debugging
- **Container-Friendly:** All logs go to stdout for proper container log aggregation

### 18.2 Architecture

#### 18.2.1 Centralized Logging Module

**Location:** `backend/lamb/logging_config.py`

This module serves as the single source of truth for all logging configuration. It handles:

```python
from lamb.logging_config import get_logger

# Get a logger for the current module, categorized as a specific component
logger = get_logger(__name__, component="MAIN")

# Use standard Python logging
logger.debug("Detailed debugging information")
logger.info("General informational message")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error")
```

**Global Configuration:**
The module reads the `GLOBAL_LOG_LEVEL` environment variable at import time and configures the root logger once using:

```python
logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)
```

The `force=True` parameter ensures this configuration overrides any prior logging configurations in the application.

#### 18.2.2 Component-Based Log Levels

Six components are supported with fine-grained log level control:

| Component | Environment Variable | Purpose |
|-----------|----------------------|---------|
| MAIN | `MAIN_LOG_LEVEL` | Main application logic |
| API | `API_LOG_LEVEL` | API endpoints and routers |
| DB | `DB_LOG_LEVEL` | Database operations |
| RAG | `RAG_LOG_LEVEL` | RAG (Retrieval-Augmented Generation) operations |
| EVALUATOR | `EVALUATOR_LOG_LEVEL` | Evaluation and grading components |
| OWI | `OWI_LOG_LEVEL` | Open WebUI integration |

**Fallback Behavior:**
If a component-specific log level is not set, the logger falls back to `GLOBAL_LOG_LEVEL`. This allows:
- Global control with `GLOBAL_LOG_LEVEL` for all components
- Selective override of specific components while others use the global level

#### 18.2.3 get_logger() Function

```python
def get_logger(name: str, component: str = "MAIN") -> logging.Logger:
    """
    Return a module logger configured for the given component.
    
    Args:
        name: Logger name (typically __name__ for module-level loggers)
        component: Component category (MAIN, API, DB, RAG, EVALUATOR, OWI)
    
    Returns:
        logging.Logger: Properly configured logger instance
    
    The component level is taken from SRC_LOG_LEVELS; defaults to GLOBAL_LOG_LEVEL.
    """
    logger = logging.getLogger(name)
    level = SRC_LOG_LEVELS.get(component, GLOBAL_LOG_LEVEL)
    logger.setLevel(level)
    return logger
```

**Key Features:**
- Creates or retrieves a logger with the specified name
- Sets the level based on the component type
- Returns a properly configured logger instance
- Supports inheritance from root logger configuration

### 18.3 Environment Variables

**Global Default Level:**
```bash
# Global log level - applied to all components that don't have specific overrides
GLOBAL_LOG_LEVEL=WARNING  # Default: WARNING
# Supported values: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Component-Specific Levels (Optional):**
```bash
# Each component can have its own log level
MAIN_LOG_LEVEL=INFO        # Optional: Controls main application logging
API_LOG_LEVEL=WARNING      # Optional: Controls API endpoint logging
DB_LOG_LEVEL=DEBUG         # Optional: Controls database operation logging
RAG_LOG_LEVEL=INFO         # Optional: Controls RAG pipeline logging
EVALUATOR_LOG_LEVEL=WARNING # Optional: Controls evaluator logging
OWI_LOG_LEVEL=WARNING      # Optional: Controls OWI integration logging
```
### 18.5 Usage Examples

#### 18.5.1 Basic Setup

**In any module:**
```python
from lamb.logging_config import get_logger

# For main application logic
logger = get_logger(__name__, component="MAIN")

# For database operations
logger = get_logger(__name__, component="DB")

# For API endpoints
logger = get_logger(__name__, component="API")
```

#### 18.5.2 Common Logging Patterns

**Debug Information:**
```python
logger.debug(f"Processing request for user {user_id}")
logger.debug(f"Database query: {query}")
```

**Operational Events:**
```python
logger.info(f"Assistant created: {assistant_name}")
logger.info(f"Knowledge base collection created: {collection_id}")
```

**Warnings:**
```python
logger.warning(f"Fallback model used for user {user_id}")
logger.warning(f"Knowledge base query returned no results")
```

**Errors:**
```python
logger.error(f"Failed to connect to KB server: {error}")
logger.error(f"LLM API error: {error}", exc_info=True)
```

#### 18.5.3 Environment Configuration Examples

**Development (All DEBUG):**
```bash
GLOBAL_LOG_LEVEL=DEBUG
```

**Development (Selective Debugging):**
```bash
GLOBAL_LOG_LEVEL=INFO
DB_LOG_LEVEL=DEBUG        # Only database logs at DEBUG
RAG_LOG_LEVEL=DEBUG       # Only RAG logs at DEBUG
```

**Production (Clean Logs):**
```bash
GLOBAL_LOG_LEVEL=WARNING
```

**Production (Monitor Specific Issues):**
```bash
GLOBAL_LOG_LEVEL=WARNING
API_LOG_LEVEL=INFO        # Watch API operations
OWI_LOG_LEVEL=DEBUG       # Debug OWI integration issues
```

### 18.6 Implementation Details

#### 18.6.1 Core Configuration Module

**Source Code Reference:**
```python
# backend/lamb/logging_config.py
import os
import sys
import logging

# Supported log levels
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}

# Global level from environment (default: WARNING)
GLOBAL_LOG_LEVEL = os.environ.get("GLOBAL_LOG_LEVEL", "WARNING").upper()
if GLOBAL_LOG_LEVEL not in _LOG_LEVELS:
    GLOBAL_LOG_LEVEL = "WARNING"

# Configure root logging once to stdout; force=True to override prior configs
logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)

# Component-specific levels (override via env)
_LOG_SOURCES = ["MAIN", "API", "DB", "RAG", "EVALUATOR", "OWI"]

SRC_LOG_LEVELS: dict[str, str] = {}
for source in _LOG_SOURCES:
    env_var = f"{source}_LOG_LEVEL"
    level = os.environ.get(env_var, "").upper()
    if level not in _LOG_LEVELS:
        level = GLOBAL_LOG_LEVEL
    SRC_LOG_LEVELS[source] = level

def get_logger(name: str, component: str = "MAIN") -> logging.Logger:
    """Return a module logger configured for the given component.

    The component level is taken from SRC_LOG_LEVELS; defaults to GLOBAL.
    """
    logger = logging.getLogger(name)
    level = SRC_LOG_LEVELS.get(component, GLOBAL_LOG_LEVEL)
    logger.setLevel(level)
    return logger
```

#### 18.6.2 Recent Changes (Issue #149)

**Pull Request #153** implemented centralized logging configuration and removed the legacy Timelog utility:

**Changes Made:**
- ✅ Added `backend/lamb/logging_config.py` - Centralized logging configuration module
- ✅ Removed `backend/utils/timelog.py` - Legacy Timelog utility completely removed
- ✅ Updated all backend modules to use `get_logger()` from centralized config
- ✅ Updated documentation to reflect new logging system

**Migration Pattern:**
```python
# Before (Legacy Timelog - REMOVED)
from utils.timelog import Timelog
Timelog("Processing message", 1)

# After (New Centralized Logging)
from lamb.logging_config import get_logger
logger = get_logger(__name__, component="MAIN")
logger.info("Processing message")
```

### 18.7 Troubleshooting

#### 18.7.1 Common Issues

**Logs Not Appearing:**
```bash
# Check environment variable is set correctly
echo $GLOBAL_LOG_LEVEL

# Verify logger creation
logger = get_logger(__name__, component="MAIN")
logger.info("Test message")  # Should appear in stdout
```

**Component Logs Not Working:**
```bash
# Check component-specific variable
echo $DB_LOG_LEVEL  # Should be DEBUG/INFO/etc. if set

# Verify component name is correct
logger = get_logger(__name__, component="DB")  # Not "DATABASE"
```

**Invalid Log Level:**
```bash
# These are valid: DEBUG, INFO, WARNING, ERROR, CRITICAL
GLOBAL_LOG_LEVEL=INVALID  # Will fallback to WARNING
```

#### 18.7.2 Container Deployment

**Docker Compose Logging:**
```yaml
# docker-compose.yaml
services:
  lamb-backend:
    environment:
      - GLOBAL_LOG_LEVEL=INFO
      - DB_LOG_LEVEL=DEBUG
      - API_LOG_LEVEL=DEBUG
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**View Container Logs:**
```bash
# View all backend logs
docker-compose logs -f lamb-backend

# View specific service logs
docker logs lamb-backend-1
```

### 18.8 Integration Examples

#### 18.8.1 Database Operations
```python
# backend/lamb/database_manager.py
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="DB")

def execute_query(query, params=None):
    logger.debug(f"Executing query: {query}")
    try:
        result = self.db.execute(query, params)
        logger.debug(f"Query returned {len(result)} rows")
        return result
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise
```

#### 18.8.2 API Endpoints
```python
# backend/creator_interface/main.py
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")

@app.get("/assistants")
async def list_assistants(request: Request):
    logger.info("Listing assistants for user")
    try:
        assistants = await get_user_assistants(request)
        logger.debug(f"Found {len(assistants)} assistants")
        return assistants
    except Exception as e:
        logger.error(f"Failed to list assistants: {e}")
        raise
```

#### 18.8.3 RAG Pipeline
```python
# backend/lamb/completions/rag/simple_rag.py
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")

def retrieve_documents(query, collection_id):
    logger.debug(f"RAG retrieval for query: {query[:50]}...")
    try:
        docs = self.vector_store.search(query, limit=10)
        logger.info(f"Retrieved {len(docs)} documents for RAG")
        return docs
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        raise
```

## 19. Frontend UX Patterns & Best Practices

### 19.1 Form Dirty State Tracking

**Problem:** Svelte 5's reactivity system can cause component props to change references frequently, even when the underlying data hasn't changed. In forms that react to prop changes by repopulating fields, this creates a critical UX issue where user edits are lost.

**Symptom:** Users edit a form field (dropdown, text input, etc.) and their change is immediately reverted to the original value.

**Root Cause:**
1. Svelte 5 wraps reactive objects with proxies
2. Parent component updates can trigger child prop reference changes
3. Effects watching props trigger on reference changes, not just value changes
4. Form repopulation logic overwrites user input with prop data

**Standard Solution: Form Dirty State Tracking**

This is the **recommended pattern** for all LAMB forms that display and edit data:

```javascript
// Add dirty state tracking
let formDirty = $state(false);

// Mark form as dirty when user makes any change
function handleFieldChange() {
    formDirty = true;
}

// Modify reactive effect to respect dirty state
$effect(() => {
    // Only repopulate if form is clean (no unsaved changes)
    if (assistant && !formDirty) {
        // Check for meaningful changes (ID change, null status change)
        if (assistant?.id !== previousId) {
            populateFormFields(assistant);
        }
    }
});

// Reset dirty state on explicit actions
async function handleSave() {
    await saveChanges();
    formDirty = false; // Changes committed
}

function handleCancel() {
    populateFormFields(initialData); // Revert
    formDirty = false; // Reset to clean state
}

// Reset when loading different entity
$effect(() => {
    if (assistant?.id !== previousId) {
        formDirty = false; // New entity, start clean
        previousId = assistant?.id;
    }
});
```

**Key Principles:**

1. **Dirty State:** Track whether user has made any changes
2. **Preserve User Intent:** Never overwrite user edits unless explicitly requested
3. **Explicit Resets:** Only reset form on:
   - User clicks Cancel (intentional revert)
   - Save succeeds (changes committed)
   - Loading different entity (clear ID change)
4. **All Fields Protected:** Dirty state protects ALL fields, not selective preservation

**When to Use:**

- ✅ Any form editing existing data
- ✅ Forms with reactive prop updates
- ✅ Multi-field configuration forms
- ✅ Forms in modal dialogs
- ✅ Forms with auto-save functionality

**When NOT to Use:**

- ❌ Read-only display components
- ❌ Single-field inline editors (handle differently)
- ❌ Forms that don't receive props

**Implementation Checklist:**

- [ ] Add `formDirty = $state(false)` state variable
- [ ] Add `handleFieldChange()` to all input events
- [ ] Modify `$effect()` to check `formDirty` before repopulating
- [ ] Reset `formDirty = false` on save success
- [ ] Reset `formDirty = false` on cancel
- [ ] Reset `formDirty = false` on entity ID change

**Example Implementation:**

See `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` for the reference implementation.

**Related Issues:**

- GitHub Issue #62: Language Model selection bug (fixed with this pattern)
- See also Section 17.3 for complementary ID-based repopulation pattern

### 19.2 Async Data Loading Race Conditions ⚠️ CRITICAL

**⚠️ WARNING:** Async data loading with Svelte 5's reactivity creates dangerous race conditions that can silently break user-facing functionality. This is a **critical pattern** that ALL developers must understand before implementing forms or components with async data dependencies.

#### 19.2.1 The Problem

When restoring saved selections (checkboxes, multi-selects, etc.) that depend on a list fetched asynchronously, setting the selections **before** the list is loaded causes Svelte's binding directives (`bind:group`, `bind:value`) to fail silently.

**Real-World Example (Issue #96):**

```javascript
// BUGGY CODE - DO NOT REPLICATE
function populateFormFields(data) {
    // Set selections FIRST (from saved data)
    selectedKnowledgeBases = data.RAG_collections?.split(',').filter(Boolean) || [];
    // → selectedKnowledgeBases = ["abc123", "def456"]
    
    // Trigger async fetch SECOND
    if (selectedRagProcessor === 'simple_rag') {
        tick().then(fetchKnowledgeBases);  // ⚠️ Async - happens LATER
    }
}

// Meanwhile, in the template:
{#each ownedKnowledgeBases as kb}  <!-- ⚠️ Empty array initially -->
    <input type="checkbox" bind:group={selectedKnowledgeBases} value={kb.id}>
    <!-- ⚠️ Can't match selections to empty list -->
{/each}
```

**What Happens:**
1. `selectedKnowledgeBases = ["abc123", "def456"]` is set
2. Checkboxes render with `bind:group` but `ownedKnowledgeBases` is still `[]`
3. Svelte's `bind:group` can't match "abc123" to any checkbox (list is empty)
4. Later, `fetchKnowledgeBases()` completes and populates the list
5. Checkboxes re-render, but Svelte **DOES NOT retroactively apply the bindings**
6. Result: Checkboxes appear unchecked even though data says they should be checked

#### 19.2.2 Why This Is Dangerous

**Silent Failure:**
- No console errors
- No exceptions thrown
- UI appears to work (checkboxes render)
- Data appears to be loaded (API calls succeed)
- Only the **binding reconciliation** fails

**User Impact:**
- Saved data appears lost
- Users unknowingly overwrite correct data with empty selections
- Data corruption occurs silently
- Trust in the application is destroyed

**Testing Difficulty:**
- Works fine on fast networks (race window is tiny)
- Only fails on slow networks or when multiple effects interact
- Network throttling required to reproduce reliably
- Intermittent failures in production are the worst kind

#### 19.2.3 Affected Svelte Directives

The following Svelte directives are vulnerable to async race conditions:

| Directive | Vulnerability | Risk Level |
|-----------|---------------|------------|
| `bind:group` | Multi-select checkboxes/radios | **CRITICAL** |
| `bind:value` (select multiple) | Multi-select dropdowns | **CRITICAL** |
| `bind:value` (select single) | Single-select dropdowns | **HIGH** |
| `bind:checked` (dynamic list) | Checkbox lists | **HIGH** |

**Common Pattern:**
```svelte
<!-- DANGER ZONE: Options loaded async, selection set before options ready -->
<select bind:value={selected} multiple>
    {#each asyncLoadedOptions as option}
        <option value={option.id}>{option.name}</option>
    {/each}
</select>
```

#### 19.2.4 The Correct Pattern: Load-Then-Select

**Golden Rule:** **ALWAYS load the selectable options BEFORE setting the selected values.**

```javascript
// ✅ CORRECT PATTERN
async function populateFormFields(data) {
    if (!data) return;
    
    // ... populate basic fields first ...
    
    // For async-dependent fields:
    if (configInitialized && selectedRagProcessor === 'simple_rag') {
        // 1. WAIT for options to load FIRST
        if (!kbFetchAttempted) {
            await fetchKnowledgeBases();  // ✅ Await the async operation
        }
        
        // 2. THEN set selections when options are ready
        selectedKnowledgeBases = data.RAG_collections?.split(',').filter(Boolean) || [];
        // ✅ Now bind:group can match selections to available options
    }
}
```

**Key Requirements:**
1. Make the populate function `async`
2. Use `await` to ensure options are loaded
3. Set selections **after** await completes
4. Handle loading states in UI

#### 19.2.5 Alternative Pattern: Deferred Selection

If making the populate function async is not feasible, use a pending state:

```javascript
// Pending selections that will be applied when options are ready
let pendingSelections = $state(null);

// In populateFormFields (sync):
function populateFormFields(data) {
    // Store selections to be applied later
    pendingSelections = data.RAG_collections?.split(',').filter(Boolean) || [];
    
    // Trigger fetch
    if (!kbFetchAttempted) {
        fetchKnowledgeBases();
    }
}

// Effect to apply selections when options become available
$effect(() => {
    if (pendingSelections && ownedKnowledgeBases.length > 0) {
        selectedKnowledgeBases = pendingSelections;
        pendingSelections = null;  // Clear pending state
    }
});
```

**Pros:**
- Doesn't require async populate function
- Clear separation of concerns

**Cons:**
- More state variables to manage
- More complex effect logic
- Harder to reason about timing

#### 19.2.6 Preemptive Loading Pattern

For forms that frequently need certain data, preload it:

```javascript
onMount(() => {
    // Preload common dependencies immediately
    if (configInitialized) {
        fetchKnowledgeBases();  // Load before user needs it
        fetchRubricsList();
        fetchUserFiles();
    }
});
```

**Pros:**
- Data ready when needed
- Better perceived performance
- Avoids race conditions entirely

**Cons:**
- Unnecessary API calls if data not needed
- Slower initial page load
- Higher server load

**When to Use:**
- Data is small and cheap to fetch
- Data is needed in >80% of use cases
- User experience demands instant interactions

#### 19.2.7 Implementation Checklist

When implementing forms with async data dependencies:

**Before Writing Code:**
- [ ] Identify all async data dependencies (API calls, file loads, etc.)
- [ ] Map which form fields depend on which async data
- [ ] Choose pattern: Load-Then-Select, Deferred Selection, or Preemptive Loading
- [ ] Consider network latency (test with throttling)

**During Implementation:**
- [ ] Ensure options load **before** selections are set
- [ ] Add loading states to UI (`loadingKnowledgeBases`, etc.)
- [ ] Implement "attempted" flags to prevent duplicate fetches (`kbFetchAttempted`)
- [ ] Handle errors gracefully (empty arrays, error messages)
- [ ] Add console logging for debugging timing issues

**Testing:**
- [ ] Test with Chrome DevTools network throttling (Slow 3G)
- [ ] Test editing existing records with saved selections
- [ ] Test rapid form state changes (create → edit → create)
- [ ] Verify selections persist through form repopulation
- [ ] Check browser console for timing-related logs

**Code Review Checklist:**
- [ ] No selections set before async data loads
- [ ] All async operations use `await` or proper effect ordering
- [ ] Loading states prevent user interaction until ready
- [ ] Error states handled (empty lists, failed fetches)
- [ ] No race conditions between multiple effects

#### 19.2.8 Warning Signs in Code

**🚨 RED FLAGS - These patterns indicate potential race conditions:**

```javascript
// ❌ BAD: Setting selections before triggering fetch
selectedItems = data.items.split(',');
tick().then(fetchItems);  // Race condition!

// ❌ BAD: Fire-and-forget async call
fetchOptions();
selectedOption = data.option;  // Options not loaded yet!

// ❌ BAD: Assuming fetch will complete before next line
loadData();
useData();  // Data not ready!

// ❌ BAD: Multiple effects that might run in different orders
$effect(() => { selectedItems = data.items.split(','); });
$effect(() => { fetchItems(); });  // Order not guaranteed!
```

**✅ SAFE PATTERNS:**

```javascript
// ✅ GOOD: Await before using data
await fetchOptions();
selectedOption = data.option;

// ✅ GOOD: Use deferred pattern with pending state
pendingSelection = data.option;
// ... later in effect when options ready ...
if (pendingSelection && options.length > 0) {
    selectedOption = pendingSelection;
}

// ✅ GOOD: Single effect with explicit ordering
$effect(() => {
    if (needsOptions && !optionsLoaded) {
        fetchOptions().then(() => {
            selectedOption = data.option;
        });
    }
});
```

#### 19.2.9 Real-World Incident Report

**Issue #96: Knowledge Base Selection Race Condition**

**Date Discovered:** November 2025  
**Severity:** P1 Critical  
**Root Cause:** KB selections restored before KB list fetched  
**Impact:** All editing workflows for assistants with RAG broken  
**Affected Users:** All users editing existing assistants  
**Workaround:** Delete and recreate assistant (data loss)  
**Detection Time:** Months (silent failure)  

**What Went Wrong:**
1. `AssistantForm.svelte` set `selectedKnowledgeBases` from saved data
2. Then triggered async `fetchKnowledgeBases()` via `tick().then(...)`
3. Checkboxes rendered before KB list loaded
4. Svelte's `bind:group` couldn't match selections to empty list
5. When KB list finally loaded, bindings were not retroactively applied
6. Users saw unchecked boxes even though data was correct

**Lessons Learned:**
- Silent failures are the most dangerous
- Race conditions are hard to spot in code review
- Network throttling essential for testing
- Async operations need explicit ordering
- Svelte 5's reactivity doesn't retroactively bind

**Prevention:**
- This architecture section added
- Code review checklist updated
- Testing procedures documented
- Example implementation in `AssistantForm.svelte` (post-fix)

#### 19.2.10 Key Takeaways

**For Developers:**
1. **Never assume async operations complete instantly**
2. **Always use `await` or explicit sequencing for data dependencies**
3. **Test with network throttling to expose race conditions**
4. **Document async dependencies in code comments**
5. **When in doubt, preload data or use deferred patterns**

**For Reviewers:**
1. **Question every async operation's timing**
2. **Look for selections set before options loaded**
3. **Check for `tick().then()` without proper sequencing**
4. **Verify loading states in UI**
5. **Ensure error handling for failed fetches**

**For Testers:**
1. **Always test with network throttling (Slow 3G)**
2. **Test edit flows, not just create flows**
3. **Verify saved data appears correctly after reload**
4. **Check selections persist through form repopulation**
5. **Test rapid state transitions**

---

**⚠️ CRITICAL REMINDER:** If you're implementing a form with checkboxes, multi-selects, or any binding that depends on async data, **STOP** and re-read this section. The bug you prevent is better than the bug you fix.

---

### 19.3 Preventing Spurious Form Repopulation ⚠️ CRITICAL

**⚠️ WARNING:** Even with form dirty state tracking, calling `populateFormFields()` on every prop reference change can cause dropdown selections and other fields to be unexpectedly reset. This is a **critical pattern** that complements Section 17.1.

#### 19.3.1 The Problem

Svelte 5's proxy-based reactivity causes prop references to change frequently, even when the underlying data hasn't changed. A naive `$effect` that repopulates on every reference change will overwrite user selections continuously.

**Real-World Examples:**
- **Issue #62 (original):** Language Model dropdown reset when editing
- **November 2025:** Knowledge Base selections lost (Issue #96)  
- **November 2025:** LLM dropdown reset AGAIN despite dirty state tracking

**What Happens:**

```javascript
// ❌ BAD PATTERN - Causes spurious resets
$effect(() => {
    if (assistant && !formDirty) {
        // This looks safe because of formDirty check, but it's NOT!
        // Svelte 5 can trigger this on reference-only changes
        populateFormFields(assistant); // ⚠️ Overwrites ALL fields
    }
});
```

**The Trap:**
1. User opens assistant for editing (LLM = `gpt-4o`)
2. Form populates correctly, `formDirty = false`
3. Parent component re-renders (for any reason)
4. `assistant` prop gets new proxy reference (Svelte 5 reactivity)
5. Effect sees reference change + `formDirty === false`
6. Effect calls `populateFormFields()` 
7. **All dropdowns reset**, including LLM selection
8. User sees their selection disappear

**Why Dirty State Alone Isn't Enough:**

Dirty state tracking (`formDirty`) protects against overwrites **while the user is editing**. However, when `formDirty === false` (initial load, after save, after cancel), the form is still vulnerable to spurious repopulation from reference-only changes.

#### 19.3.2 The Correct Pattern: ID-Based Repopulation

**Golden Rule:** Only repopulate when there's a **meaningful change**, not just a reference change.

```javascript
// ✅ CORRECT PATTERN - Only repopulates on actual data changes
let previousAssistantId = $state(null);

$effect(() => {
    const assistantIdChanged = assistant?.id !== previousAssistantId;
    const nullStatusChanged = (assistant === null && previousAssistantId !== null) || 
                              (assistant !== null && previousAssistantId === null);
    
    if (assistantIdChanged || nullStatusChanged) {
        // Real change - safe to repopulate
        if (assistant) {
            populateFormFields(assistant);
            previousAssistantId = assistant.id;
            formDirty = false; // Reset dirty state for new assistant
        } else {
            resetFormToDefaults();
            previousAssistantId = null;
            formDirty = false;
        }
    } else {
        // Reference-only change - SKIP repopulation
        // This protects user selections from spurious resets
        console.log('[Form] Skipping repopulation - no meaningful change');
    }
});
```

**Key Principles:**

1. **Track Previous Identity:** Store `previousId` to detect actual changes
2. **Check Meaningful Changes:** ID change, null ↔ non-null transitions
3. **Skip Reference Changes:** Don't repopulate on proxy reference updates
4. **Explicit Reverts Only:** User must explicitly cancel to trigger repopulation

#### 19.3.3 When to Repopulate

| Scenario | Should Repopulate? | Reason |
|----------|-------------------|--------|
| Assistant ID changes | ✅ YES | Loading different assistant |
| User clicks Cancel | ✅ YES | Explicit user action |
| User saves successfully | ❌ NO | Form already has current values |
| Prop reference changes only | ❌ NO | No actual data change |
| Parent component re-renders | ❌ NO | Unrelated to this form |
| User switches away and back | ❌ NO | Form should retain state |

#### 19.3.4 What Fields Are Affected

Spurious repopulation affects **all bound form fields**, but is most visible in:

| Field Type | Symptom | User Impact |
|------------|---------|-------------|
| **Dropdowns** (select) | Selection resets to default | Very noticeable, frustrating |
| **Checkboxes** (multi-select) | Selections cleared | Data loss, critical |
| **Radio buttons** | Selection resets | Noticeable |
| **Text inputs** | Value resets | Moderate (if typing slowly) |
| **Textareas** | Content replaced | Critical if actively editing |

#### 19.3.5 Implementation Checklist

When implementing forms with prop-based data loading:

**Setup:**
- [ ] Add `let previousId = $state(null)` to track identity
- [ ] Add `let formDirty = $state(false)` for user edit tracking
- [ ] Add `handleFieldChange()` handlers on all inputs

**Effect Logic:**
- [ ] Calculate `idChanged` using previous ID comparison
- [ ] Calculate `nullStatusChanged` for creation/deletion
- [ ] Only call `populateFormFields()` if ID or null status changed
- [ ] Skip repopulation on reference-only changes
- [ ] Reset `previousId` and `formDirty` on actual changes

**Testing:**
- [ ] Open form, wait 5 seconds, verify selections persist
- [ ] Navigate away and back, verify selections persist
- [ ] Trigger parent re-renders, verify selections persist
- [ ] Open different item, verify form repopulates correctly
- [ ] Click Cancel, verify form reverts to saved state

#### 19.3.6 Warning Signs in Code

**🚨 RED FLAGS - These patterns indicate potential spurious repopulation:**

```javascript
// ❌ BAD: Repopulates on any prop change
$effect(() => {
    if (data) {
        populateAllFields(data);
    }
});

// ❌ BAD: Dirty check alone isn't enough
$effect(() => {
    if (data && !formDirty) {
        populateAllFields(data); // Still triggers on reference changes!
    }
});

// ❌ BAD: Repopulating after save
async function handleSave() {
    await saveData();
    formDirty = false;
    populateFormFields(data); // Unnecessary - form already has values!
}
```

**✅ SAFE PATTERNS:**

```javascript
// ✅ GOOD: ID-based repopulation
$effect(() => {
    if (data?.id !== previousId) {
        populateAllFields(data);
        previousId = data.id;
        formDirty = false;
    }
});

// ✅ GOOD: Explicit revert only
function handleCancel() {
    populateFormFields(initialData); // Explicit user action
    formDirty = false;
}

// ✅ GOOD: Skip repopulation after save
async function handleSave() {
    await saveData();
    formDirty = false; // Just reset dirty flag
    // Don't repopulate - form already has current values!
}
```

#### 19.3.7 Relationship to Other Patterns

This pattern **complements** but is **distinct** from:

| Pattern | Purpose | When to Use |
|---------|---------|-------------|
| **Form Dirty Tracking** (17.1) | Protect unsaved changes | All editable forms |
| **Async Race Conditions** (17.2) | Handle async data deps | Forms with async selectors |
| **Spurious Repopulation** (17.3) | Prevent reference-change resets | Forms with prop-based data |

**All Three Together:**

```javascript
// Complete pattern combining all three
let formDirty = $state(false);           // 17.1: Dirty tracking
let previousId = $state(null);            // 17.3: ID tracking
let pendingSelections = $state(null);     // 17.2: Async pattern

$effect(() => {
    // 17.3: Only on meaningful changes
    if (data?.id !== previousId) {
        // 17.1: Check dirty state
        if (!formDirty) {
            // 17.2: Handle async deps correctly
            await loadOptionsFirst();
            populateFields(data);
            previousId = data.id;
            formDirty = false;
        }
    }
});
```

#### 19.3.8 Real-World Incident Reports

**November 2025: Double Repopulation Bug**

Even after implementing dirty state tracking (Issue #62 fix), the AssistantForm component continued to lose LLM selections because:

1. Dirty state prevented overwrites **during editing** ✅
2. But when `formDirty === false`, Svelte 5 reference changes triggered repopulation ❌
3. Every parent re-render caused dropdown selections to reset
4. Fix: Skip repopulation on reference-only changes (ID-based pattern)

**Lessons Learned:**
- Dirty state tracking is necessary but not sufficient
- Must also check for meaningful data changes (ID, null status)
- Svelte 5's reactivity is more aggressive than Svelte 4
- Always test with deliberate delays to expose timing issues

#### 19.3.9 Example Implementation

See `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`:

```javascript
// Lines 203-253: Complete implementation
$effect(() => {
    const idChanged = assistant?.id !== initialAssistantData?.id;
    const nullChanged = (assistant === null && initialAssistantData !== null) || 
                        (assistant !== null && initialAssistantData === null);
    
    if (idChanged || nullChanged) {
        // Real change - repopulate
        if (assistant) {
            populateFormFields(assistant);
            previousAssistantId = assistant.id;
            formDirty = false;
        }
    } else {
        // Reference-only change - protect selections
        console.log('[Form] Skipping repopulation - protecting user selections');
    }
});
```

#### 19.3.10 Key Takeaways

**For Developers:**
1. **Reference changes ≠ data changes** in Svelte 5
2. **Always track previous ID** for comparison
3. **Skip repopulation** unless ID or null status changes
4. **Test with delays** to expose spurious updates
5. **Combine all three patterns** (17.1, 17.2, 17.3) for robust forms

**For Reviewers:**
1. **Question every populateFormFields() call**
2. **Require ID-based change detection**
3. **Reject naive prop-watching effects**
4. **Verify testing includes delay scenarios**
5. **Check that reference changes are ignored**

**For Testers:**
1. **Open form and wait** (5-10 seconds) before interacting
2. **Navigate away and back** to trigger re-renders
3. **Verify all selections persist** through navigation
4. **Test rapid switching** between items
5. **Use React DevTools** to observe re-renders

---

**⚠️ CRITICAL REMINDER:** If you're implementing a form that loads data from props and uses dropdowns or multi-selects, **STOP** and re-read this section. The pattern you use here will determine whether your form is stable or frustrating to use.

---

### 19.4 Other Frontend Best Practices

#### 19.4.1 Svelte 5 Reactivity Guidelines

- Use `$state()` for component-local reactive values
- Use `$derived()` for computed values
- Use `$effect()` sparingly and only for side effects
- Prefer event handlers over reactive effects when possible
- Always check if effect should run (guard conditions)

#### 19.4.2 API Service Patterns

- Centralize API calls in service modules (`lib/services/`)
- Include authorization headers in all authenticated requests
- Handle loading/error states consistently
- Return structured responses: `{success, data?, error?}`

#### 19.4.3 Store Management

- Use stores for shared state across components
- Keep stores minimal and focused
- Provide clear update methods, don't expose raw state
- Document store contracts and update patterns

---

## 20. API Reference

See PRD document and sections 5.1-5.3 for complete API documentation.

---

## 21. File Structure Summary

```
/backend/
├── main.py
├── lamb/ (core API with completions plugins)
├── creator_interface/ (creator API)
└── utils/

/frontend/svelte-app/
├── src/routes/ (pages)
├── src/lib/components/ (UI)
├── src/lib/services/ (API clients)
└── src/lib/stores/ (state management)
```

---

## Conclusion

This document provides comprehensive technical documentation for the LAMB platform, designed for developers, DevOps engineers, and AI agents working with the codebase.

**Support:**
- GitHub: https://github.com/Lamb-Project/lamb
- Website: https://lamb-project.org

---

**Maintainers:** LAMB Development Team
**Last Updated:** December 17, 2025
**Version:** 2.9 (Added Section 17: Centralized Logging System - Unified environment-based configuration, removed legacy Timelog utility)