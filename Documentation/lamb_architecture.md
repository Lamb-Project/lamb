# LAMB Architecture Documentation

**Version:** 2.0  
**Last Updated:** January 2025  
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
10. [LTI Integration](#10-lti-integration)
11. [Plugin Architecture](#11-plugin-architecture)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Deployment Architecture](#13-deployment-architecture)
14. [Development Workflow](#14-development-workflow)
15. [API Reference](#15-api-reference)
16. [File Structure](#16-file-structure)

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
| assistant_router | `/v1/assistant` | Assistant CRUD | `assistant_router.py` |
| lti_users_router | `/v1/lti_users` | LTI user management | `lti_users_router.py` |
| owi_router | `/v1/OWI` | OWI integration | `owi_bridge/owi_router.py` |
| simple_lti_router | `/simple_lti` | LTI launch handling | `simple_lti/simple_lti_main.py` |
| creator_user_router | `/v1/creator_user` | Creator user management | `creator_user_router.py` |
| completions_router | `/v1/completions` | Completion generation | `completions/main.py` |
| config_router | `/v1/config` | System configuration | `config_router.py` |
| mcp_router | `/v1/mcp` | MCP endpoints | `mcp_router.py` |
| organization_router | `/v1` | Organization management | `organization_router.py` |

#### 3.1.4 Creator Interface API (`/backend/creator_interface/main.py`)

**Mounted Routers:**

| Router | Prefix | Purpose | File |
|--------|--------|---------|------|
| assistant_router | `/creator/assistant` | Assistant operations (proxied) | `assistant_router.py` |
| knowledges_router | `/creator/knowledgebases` | Knowledge Base operations | `knowledges_router.py` |
| organization_router | `/creator/admin` | Organization management | `organization_router.py` |
| learning_assistant_proxy_router | `/creator` | Learning assistant proxy | `learning_assistant_proxy.py` |

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
      "owned_by": "lamb_v4"
    }
  ]
}
```

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
- `bypass`: Testing connector (returns messages as-is)

**RAG Processors:**
- `simple_rag`: Queries KB server and formats context
- `single_file_rag`: Retrieves from single file
- `no_rag`: No retrieval (returns empty context)

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

## 15. API Reference

See PRD document and sections 5.1-5.3 for complete API documentation.

---

## 16. File Structure Summary

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
**Last Updated:** Oct 2025  
**Version:** 2.0