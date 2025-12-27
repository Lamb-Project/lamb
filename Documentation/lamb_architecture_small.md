# LAMB Architecture Documentation - Essential Guide

**Version:** 2.9
**Last Updated:** December 27, 2025  
**Target Audience:** Developers, DevOps Engineers, AI Agents, Technical Architects

> **Note:** This is a condensed version of the full architecture documentation. For detailed schemas, code examples, and implementation details, see [lamb_architecture.md](./lamb_architecture.md).

---

## What This Document Covers

This essential guide provides:

✅ **Complete architectural overview** - All major components and their interactions  
✅ **Key concepts and patterns** - Design principles, data models, API structures  
✅ **Critical implementation details** - Plugin architecture, authentication, multi-tenancy  
✅ **Quick reference material** - Common tasks, file locations, best practices  
✅ **References to extended docs** - Every section links to detailed documentation

**What's NOT included here (but in the full doc):**
- Complete SQL schemas and migrations
- Full code examples and implementations
- Detailed API request/response bodies
- Step-by-step integration guides
- Extensive troubleshooting scenarios

**Reading Time:** ~20 minutes | **Full Doc Reading Time:** ~90 minutes

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
13. [Deployment & Development](#13-deployment--development)
14. [Special Features](#14-special-features)
15. [Frontend UX Patterns](#15-frontend-ux-patterns)

---

## 1. System Overview

### High-Level Architecture

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

### Service Responsibilities

| Service | Purpose | Technology | Port |
|---------|---------|------------|------|
| **Frontend** | Creator UI, Admin panels | Svelte 5, SvelteKit | 5173 (dev) / served by backend (prod) |
| **Backend** | Core API, Assistant management, Completions | FastAPI, Python 3.11 | 9099 |
| **Open WebUI** | Authentication, Model management, Chat UI | FastAPI, Python | 8080 |
| **Knowledge Base Server** | Document processing, Vector search | FastAPI, ChromaDB | 9090 |

> 📖 **Extended:** See [Section 1](./lamb_architecture.md#1-system-overview) for detailed service interactions and communication patterns.

---

## 2. Architecture Principles

### Design Principles

1. **Privacy-First:** All user data and assistant configurations remain within institutional control
2. **Modular:** Components can be updated or replaced independently
3. **Extensible:** Plugin architecture for LLM connectors, prompt processors, and RAG
4. **Multi-Tenant:** Organizations isolated with independent configurations
5. **Standards-Compliant:** OpenAI API compatibility, LTI 1.1 compliance
6. **Educator-Centric:** Non-technical users can create sophisticated AI assistants

### Architectural Patterns

- **Layered Architecture:** Creator Interface API → LAMB Core API → Database/External Services
- **Proxy Pattern:** Creator Interface acts as enhanced proxy to LAMB Core
- **Plugin Architecture:** Dynamically loaded processors and connectors
- **Repository Pattern:** Database managers encapsulate data access
- **Service Layer:** Business logic separated from HTTP layer

---

## 3. System Components

### Dual API Design

LAMB employs a **two-tier API architecture**:

```
Frontend (Browser)
        ↓
Creator Interface API (/creator)
  - User authentication & session management
  - File operations (upload/download)
  - Enhanced request validation
  - Acts as proxy with additional logic
  Location: /backend/creator_interface/
        ↓ (Internal HTTP calls)
LAMB Core API (/lamb/v1)
  - Direct database access
  - Core business logic
  - Assistant, user, organization management
  - Completions processing
  Location: /backend/lamb/
        ↓
  Database/OWI
```

**Why Dual API?**
- **Separation of Concerns:** User-facing logic separated from core operations
- **Flexibility:** Creator Interface can add features without modifying core
- **Security:** Additional validation layer before core operations

### Main Entry Point (`/backend/main.py`)

**Key Mounts:**
- `/lamb` → LAMB Core API
- `/creator` → Creator Interface API
- `/static` → Static file serving
- `/{path:path}` → SPA catch-all (serves frontend)

**Key Endpoints:**
- `GET /v1/models` - List assistants as OpenAI models
- `POST /v1/chat/completions` - Generate completions
- `GET /status` - Health check

### LAMB Core API Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| lti_users_router | `/v1/lti_users` | LTI user management |
| simple_lti_router | `/simple_lti` | LTI launch handling |
| completions_router | `/v1/completions` | Completion generation |
| mcp_router | `/v1/mcp` | MCP endpoints |

> **Note:** OWI router endpoints (`/v1/OWI/*`) were removed in Dec 2025 for security. OWI operations are now internal services only.

### Creator Interface API Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| assistant_router | `/creator/assistant` | Assistant operations |
| knowledges_router | `/creator/knowledgebases` | Knowledge Base operations |
| organization_router | `/creator/admin` | Organization management |
| analytics_router | `/creator/analytics` | Chat analytics and usage insights |
| learning_assistant_proxy_router | `/creator` | Learning assistant proxy |
| evaluaitor_router | `/creator/rubrics` | Rubric management |
| prompt_templates_router | `/creator/prompt-templates` | Prompt template management |

**Key Direct Endpoints:**
- `POST /creator/login` - User login
- `POST /creator/signup` - User signup
- `GET /creator/users` - List users (admin)
- `GET /creator/user/current` - Get current user info
- `POST /creator/files/upload` - Upload files

### Open WebUI Integration

LAMB integrates with Open WebUI for:
- **Authentication:** User/password management, session tokens
- **Model Management:** LLM provider configuration
- **Chat UI:** End-user interface for published assistants

**Integration Points:**
- Backend validates tokens against OWI database
- Assistants published to OWI appear as chat models
- LTI launches map to OWI sessions

> 📖 **Extended:** See [Section 3](./lamb_architecture.md#3-system-components) for detailed router configurations, endpoint specifications, and integration patterns.

---

## 4. Data Architecture

### LAMB Database (SQLite)

**Location:** `$LAMB_DB_PATH/lamb_v4.db`

**Core Tables:**

1. **organizations** - Organization/tenant records with JSON config
   - Fields: id, slug, name, is_system, status, config, timestamps
   - Config includes: provider setups, KB server, features, defaults

2. **organization_roles** - User-organization membership
   - Roles: owner, admin, member
   - Links users to organizations with permissions

3. **Creator_users** - User accounts
   - Types: creator (can build assistants), end_user (can only use them)
   - Fields: email, name, type, organization_id, config, is_enabled, timestamps
   - user_config JSON: can_share, preferences

4. **assistants** - Assistant definitions
   - Fields: name, description, model, system_prompt, temperature, metadata (JSON), sharing rules, timestamps
   - Metadata includes: plugins (RAG, PPS, connector), KB assignments, API keys

5. **assistant_shares** - Assistant sharing within organizations
   - Fields: assistant_id, shared_with_user_id, shared_by_user_id, timestamps
   - Enables user-to-user assistant sharing

6. **KB_registry** - Knowledge Base metadata
   - Links collections to creators/organizations
   - Fields: collection_id, name, creator_email, organization_slug, sharing rules

7. **shared_prompt_templates** - Reusable prompt templates
   - Fields: name, template, variables, description, organization_id

8. **lti_users** - LTI launch user mappings
   - Maps LMS users to OWI sessions

9. **user_assistant_interactions** - Usage tracking and analytics

### Open WebUI Database (SQLite)

**Location:** `$OWI_DATA_PATH/webui.db`

**Key Tables:**
- **user** - End-user accounts (username/password)
  - Fields: id, name, email, role, profile_image_url, api_key, timestamps
- **auth** - Session tokens and password hashes (bcrypt)
  - Fields: id, email, password, active
- **model** - LLM models (includes published assistants)
  - Published assistants: id = `lamb_assistant.{assistant_id}`
- **group** - User groups and permissions (JSON)
- **chat** - Chat history and conversations

### Knowledge Base Storage (ChromaDB)

**Vector Database for RAG:**
- Collections named: `{org_slug}_{user_email}_{collection_name}`
- Metadata: user_email, organization, description, created_at
- Documents include: source, page, chunk_index metadata

> 📖 **Extended:** See [Section 4](./lamb_architecture.md#4-data-architecture) for complete SQL schemas, JSON config structures, migration history, and data relationships.

---

## 5. API Architecture

### RESTful Design

**Conventions:**
- Base URLs: `/lamb/v1/*` (core), `/creator/*` (interface)
- JSON request/response bodies
- Standard HTTP methods: GET, POST, PUT, DELETE
- HTTP status codes: 200 (success), 201 (created), 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 500 (server error)

### OpenAI API Compatibility

LAMB implements OpenAI-compatible endpoints:

```http
POST /v1/chat/completions
Authorization: Bearer {assistant_api_key}

{
  "model": "assistant_id",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**Response:** Streaming or complete chat completion following OpenAI format

### Error Handling

**Standard Error Response:**
```json
{
  "error": {
    "message": "Human-readable error message",
    "type": "invalid_request_error",
    "code": "assistant_not_found"
  }
}
```

> 📖 **Extended:** See [Section 5](./lamb_architecture.md#5-api-architecture) for complete API specifications, request/response examples, and error codes.

---

## 6. Authentication & Authorization

### Authentication Flow

1. **User Login:** POST `/creator/login` with email/password
2. **Token Validation:** Validate against OWI database
3. **Session Management:** Token stored in frontend, sent in Authorization header
4. **User Context:** Extract user info from token for all requests

### Token Validation

```python
def get_creator_user_from_token(authorization_header: str):
    # Extract token, validate against OWI, fetch user from LAMB DB
    # Returns: user dict with email, organization, role, permissions
```

### Admin Check

**Organization Admin Detection:**
- Check organization_roles table for admin/owner role
- Used for: user management, org settings, model configuration

### API Key Authentication (for Completions)

**Assistant API Keys:**
- Each assistant has unique API key in metadata
- Used for: `/v1/chat/completions` endpoint
- Format: `Bearer {assistant_api_key}`

> 📖 **Extended:** See [Section 6](./lamb_architecture.md#6-authentication--authorization) for complete authentication flows, security considerations, and implementation details.

---

## 7. Completion Pipeline

### Request Flow

```
Client → Backend main.py → Completions Module
  1. Validate API key (assistant lookup)
  2. Load assistant config from database
  3. Parse plugin config from assistant.metadata
  4. Load plugins (RAG, PPS, Connector)
  5. RAG Processor: Query KB if configured
  6. PPS Processor: Process/augment messages
  7. Connector: Call LLM (OpenAI, Ollama, etc.)
  8. Stream/return response to client
```

### Multimodal Support

**Supported Formats:**
- HTTP/HTTPS image URLs
- Base64 Data URLs: `data:image/jpeg;base64,{data}`
- Supported types: JPEG, PNG, GIF, WebP

**Message Format:**
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What's in this image?"},
    {"type": "image_url", "image_url": {"url": "https://..."}}
  ]
}
```

### Plugin Processing Stages

1. **RAG Processor** (`before_completion`):
   - Query knowledge base with user message
   - Inject relevant context into system prompt or messages

2. **Prompt Processor (PPS)** (`before_completion`):
   - Transform/augment messages
   - Apply prompt templates
   - Add specialized instructions

3. **Connector** (`run_completion`):
   - Route to appropriate LLM provider
   - Handle streaming responses
   - Format according to provider API

4. **Post-Processing** (`after_completion`):
   - Log interactions
   - Apply response filters
   - Track usage metrics

### Organization-Specific Configuration

**Resolution Order:**
1. Assistant-level settings (metadata.provider_override)
2. Organization setup (from org config)
3. System defaults

> 📖 **Extended:** See [Section 7](./lamb_architecture.md#7-completion-pipeline) for detailed plugin architecture, code examples, multimodal implementation, and configuration resolution logic.

---

## 8. Organization & Multi-Tenancy

### Organization Structure

**System Organization:**
- Slug: `system`
- is_system: true
- Contains default models and shared resources

**Custom Organizations:**
- Unique slug (URL-friendly identifier)
- Independent LLM provider configurations
- Isolated user and assistant namespaces
- Custom feature flags (signup, LTI, etc.)

### Organization Configuration

**Config JSON Structure:**
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
    "signup_key": "org-specific-key-2024",
    "sharing_enabled": false
  },
  "metadata": {
    "description": "Organization description",
    "contact_email": "admin@example.edu"
  }
}
```

### Organization Signup

**Signup Flow:**
1. Admin creates org with `signup_enabled: true` and unique `signup_key`
2. User enters email, name, password, and signup key
3. System checks if key matches any organization
4. If match: user created in that org with "member" role
5. If no match and `SIGNUP_ENABLED=true`: user created in system org

### Organization Management

**Key Operations:**
- Create organization (system admin only)
- Update organization config (org admin)
- Add/remove users (org admin)
- Assign roles: owner, admin, member
- Enable/disable organizations (system admin)
- Manage signup keys and feature flags

**API Endpoints:**
- GET `/lamb/v1/organizations` - List organizations
- POST `/lamb/v1/organizations` - Create organization
- PUT `/lamb/v1/organizations/{slug}` - Update config
- GET `/lamb/v1/organizations/{slug}/members` - List members
- POST `/lamb/v1/organization-roles` - Assign roles

> 📖 **Extended:** See [Section 8](./lamb_architecture.md#8-organization--multi-tenancy) for complete signup flows, API specifications, permission models, and migration strategies.

---

## 9. Knowledge Base Integration

### Architecture

```
Frontend → LAMB Backend → KB Server → ChromaDB
  - Create collection
  - Upload documents
  - Query for relevant chunks
  - Manage sharing permissions
```

### Collection Management

**Create Collection:**
- POST `/creator/knowledgebases/create`
- Backend adds user/org metadata
- KB Server creates ChromaDB collection

**Naming Convention:**
- Format: `{org_slug}_{user_email}_{collection_name}`
- Ensures isolation and trackability

### Document Upload & Processing

1. **Upload:** POST `/creator/knowledgebases/{collection_id}/upload`
2. **Extract:** Text extraction from PDF, Word, etc.
3. **Chunk:** Split into overlapping chunks
4. **Embed:** Generate vectors (sentence-transformers)
5. **Store:** Save to ChromaDB with metadata

### RAG Integration in Completions

**Flow:**
1. User sends message to assistant (with KB configured)
2. RAG processor queries KB with message text
3. Top-K relevant chunks retrieved
4. Context injected into system prompt or messages
5. LLM generates response with augmented context

### Knowledge Base Sharing

**Sharing Levels:**
- `private`: Only creator
- `organization`: All org members
- `public`: All system users (not yet implemented)

**Assistant KB Assignment:**
- Assistants can reference multiple KBs
- Stored in assistant.metadata.rag_config
- Only accessible KBs are queried

### Assistant Sharing (9.7)

**Organization-Level Sharing:**
- Share assistants with specific users in same organization
- Two-level permission system (org + user level)
- Shared users get read-only access (view & chat)
- Owner retains full control (edit, delete, manage shares)

**Permission Requirements:**
- Organization: `config.features.sharing_enabled = true`
- User: `user_config.can_share = true` (default)
- Both must be true for sharing capabilities

**Database:**
- `assistant_shares` table tracks sharing relationships
- Atomic updates via PUT endpoint
- Cascading deletes on assistant/user removal

> 📖 **Extended:** See [Section 9](./lamb_architecture.md#9-knowledge-base-integration) for detailed API specifications, chunking strategies, embedding models, query algorithms, sharing implementations, and complete assistant sharing workflows.

---

## 10. LTI Integration

### LTI Flow Overview

```
LMS → LTI Launch → LAMB → OWI Session → Chat UI
  1. LMS initiates LTI launch
  2. LAMB validates LTI signature
  3. Create/update LTI user in database
  4. Create OWI session
  5. Redirect to chat interface with assistant
```

### Publishing Flow

**Creator publishes assistant:**
1. Configure LTI settings (consumer key, secret)
2. Generate LTI launch URL
3. Add to LMS as External Tool
4. Students click tool → auto-login → assistant chat

### LTI Configuration

**Required Parameters:**
- `lti_consumer_key`: Identifies LMS/course
- `lti_shared_secret`: For signature verification
- `assistant_id`: Which assistant to launch

**LTI User Mapping:**
- LTI users stored in separate `lti_users` table
- Automatic account creation on first launch
- Mapped to OWI users for chat access

> 📖 **Extended:** See [Section 10](./lamb_architecture.md#10-lti-integration) for complete LTI 1.1 implementation, signature verification, user provisioning, and LMS integration guides.

---

## 11. Plugin Architecture

### Plugin Types

1. **Prompt Processor (PPS):** Transform messages before LLM
2. **Connector:** Interface with LLM providers
3. **RAG Processor:** Retrieve and inject context

### Plugin Structure

**Base Class Pattern:**
```python
class PluginBase:
    async def before_completion(self, messages, config):
        # Pre-processing
        return messages
    
    async def run_completion(self, messages, config):
        # Main execution
        return response
    
    async def after_completion(self, response, config):
        # Post-processing
        return response
```

### Plugin Configuration

**In Assistant Metadata:**
```json
{
  "plugins": {
    "pps": {"name": "default_pps", "config": {...}},
    "connector": {"name": "openai", "config": {"model": "gpt-4o"}},
    "rag": {"name": "chroma_rag", "config": {"kb_ids": [...]}}
  }
}
```

### Available Plugins

**Connectors:**
- `openai`: OpenAI API
- `ollama`: Local Ollama models
- `anthropic`: Anthropic Claude API
- `banana_img`: Banana image generation (custom image models)

**RAG Processors:**
- `chroma_rag`: ChromaDB vector search
- `default_rag`: Basic context injection
- `simple_rag`: Lightweight RAG implementation

**Prompt Processors:**
- `default_pps`: Template-based processing
- `learning_rag`: Educational context augmentation
- `simple_augment`: Basic message augmentation

### Creating Custom Plugins

**Location:** `/backend/lamb/completions/{plugin_type}/`

**Steps:**
1. Create `{plugin_name}.py` in appropriate directory
2. Implement required function signature
3. Handle config from assistant metadata
4. Return expected format (messages/response/context)
5. Test with assistant configuration

> 📖 **Extended:** See [Section 11](./lamb_architecture.md#11-plugin-architecture) for plugin development guide, lifecycle hooks, configuration schemas, complete function signatures, and custom plugin examples.

---

## 12. Frontend Architecture

### SvelteKit Structure

```
/frontend/svelte-app/
├── src/
│   ├── routes/              # Pages (file-based routing)
│   │   ├── +page.svelte     # Home
│   │   ├── assistants/      # Assistant management
│   │   ├── knowledge-bases/ # KB management
│   │   ├── admin/           # Admin panel
│   │   └── login/           # Authentication
│   ├── lib/
│   │   ├── components/      # Reusable UI components
│   │   ├── services/        # API client layer
│   │   └── stores/          # Svelte stores (state)
│   └── app.html             # HTML template
└── vite.config.js           # Build configuration
```

### Routing

**Convention:**
- File-based routing: `src/routes/path/+page.svelte` → `/path`
- Server endpoints: `+server.js` for API routes
- Layout files: `+layout.svelte` for shared UI

### Key Services

**API Clients (in `src/lib/services/`):**
- `assistantService.js`: Assistant CRUD
- `knowledgeBaseService.js`: KB operations
- `authService.js`: Login/logout
- `adminService.js`: User/org management

**Configuration:**
- API base URL from environment
- Token management in localStorage
- Automatic token injection in requests

> 📖 **Extended:** See [Section 12](./lamb_architecture.md#12-frontend-architecture) for component patterns, state management strategies, build configuration, and deployment setup.

---

## 13. Deployment & Development

### Development Setup

**Quick Start:**
```bash
# Clone and setup
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
./scripts/setup.sh

# Start all services
docker-compose up -d

# Access
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:9099
# - Open WebUI: http://localhost:8080
# - KB Server: http://localhost:9090
```

### Production Deployment

**Using Docker Compose:**
```bash
docker-compose -f docker-compose.prod.yaml up -d
```

**Environment Variables:**
- `LAMB_DB_PATH`: Database directory
- `OWI_DATA_PATH`: Open WebUI data
- `KB_SERVER_URL`: Knowledge Base server
- `OPENAI_API_KEY`: Default LLM provider

### Development Workflow

**Backend Development:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 9099
```

**Frontend Development:**
```bash
cd frontend/svelte-app
npm install
npm run dev
```

> 📖 **Extended:** See [Section 13-14](./lamb_architecture.md#13-deployment-architecture) for Docker configuration, reverse proxy setup, monitoring, backup strategies, and CI/CD pipelines.

---

## 14. Special Features

### Chat Analytics Feature

**Purpose:** Provide assistant owners with insights into how their assistants are being used

**Implementation:**
- Service: `ChatAnalyticsService` in `/backend/lamb/services/`
- Router: `/creator/analytics/*` endpoints
- Frontend: Analytics tab in assistant detail view

**API Endpoints:**
- `GET /creator/analytics/assistant/{id}/chats` - List chats with filtering
- `GET /creator/analytics/assistant/{id}/chats/{chat_id}` - Chat detail with messages
- `GET /creator/analytics/assistant/{id}/stats` - Usage statistics
- `GET /creator/analytics/assistant/{id}/timeline` - Activity timeline

**Privacy:**
- Organization-configurable anonymization (default: enabled)
- User identifiers anonymized as "User_001", "User_002", etc.
- Chat content always accessible to assistant owners
- Only assistant owners can view analytics

**Frontend Features:**
- Stats cards (total chats, unique users, messages, avg/chat)
- Activity timeline visualization (last 14 days)
- Filterable chat list with pagination
- Chat detail modal with full conversation view

> 📖 **Extended:** See [Chat Analytics Project](./chat_analytics_project.md) for detailed implementation documentation.

### End User Feature

**Purpose:** Restrict users to only consuming assistants (no creation)

**Implementation:**
- User type: `end_user` in Creator_users table
- Cannot access creator interface routes
- Can only use published assistants via OWI chat UI
- Managed by organization admins

### User Blocking Feature

**Purpose:** Disable user accounts without deletion

**Implementation:**
- `is_enabled` (or `enabled`) field in Creator_users table (default: true)
- Blocked users cannot login (403 error with message)
- Sessions terminated on status change
- Resources (assistants, KBs) preserved and remain accessible to others

**Key Principle:** Disabled users' published assistants, shared KBs, templates, and rubrics remain fully functional

**Admin Endpoints:**
- `PUT /creator/admin/users/{id}/status` - Enable/disable single user
- Bulk operations: `disable_users_bulk()`, `enable_users_bulk()`
- Transaction-safe bulk operations
- Audit trail via updated_at timestamp

**Database Methods:**
- `disable_user(user_id)` - Disable single user
- `enable_user(user_id)` - Enable single user
- `is_user_enabled(user_id)` - Check status
- Indexed field for performance

> 📖 **Extended:** See [Section 15-16](./lamb_architecture.md#15-end-user-feature) for complete implementation details, UI patterns, testing strategies, and migration guides.

---

## 15. Frontend UX Patterns

### Form Dirty State Tracking

**Pattern:** Track unsaved changes and warn users

```javascript
let dirtyFields = new Set();
let originalData = {...};

function markDirty(field) {
  dirtyFields.add(field);
}

function isDirty() {
  return dirtyFields.size > 0;
}

// Warn on navigation
onMount(() => {
  window.addEventListener('beforeunload', handleBeforeUnload);
});
```

### Async Data Loading Race Conditions ⚠️ CRITICAL

**Problem:** Async data loading with Svelte 5's reactivity creates dangerous race conditions, especially with bind directives

**The Race Condition:**
```javascript
// ❌ BUGGY: Setting selections BEFORE options load
function populateForm(data) {
  selectedKnowledgeBases = ["abc123", "def456"]; // Set first
  fetchKnowledgeBases(); // Load async - happens later
  // Result: bind:group can't match selections to empty list
}
```

**Why Dangerous:**
- Silently fails (no errors)
- Works on fast networks, fails on slow ones
- Affects: `bind:group`, `bind:value`, multi-selects, checkboxes

**Solution: Load-Then-Select Pattern**
```javascript
// ✅ CORRECT: Load options FIRST, then set selections
async function populateForm(data) {
  await fetchKnowledgeBases(); // Wait for options
  selectedKnowledgeBases = ["abc123", "def456"]; // Then set selections
}
```

**Alternative: Request Tracking**
```javascript
let currentRequestId = 0;

async function loadData() {
  const requestId = ++currentRequestId;
  const data = await fetchData();
  if (requestId !== currentRequestId) return; // Stale request
  updateUI(data);
}
```

### Preventing Spurious Form Repopulation

**Problem:** Form re-populates with old data after save

**Solution:** Clear dirty state, block reactive updates during save
```javascript
let isSaving = false;

$: if (!isSaving && assistant) {
  populateForm(assistant); // Only update when not saving
}

async function save() {
  isSaving = true;
  await saveData();
  dirtyFields.clear();
  isSaving = false;
}
```

### Other Best Practices

- **Loading States:** Show spinners during async operations
- **Error Boundaries:** Graceful error display
- **Optimistic Updates:** Update UI before server confirmation
- **Toast Notifications:** Non-blocking feedback
- **Accessibility:** ARIA labels, keyboard navigation

> 📖 **Extended:** See [Section 17](./lamb_architecture.md#17-frontend-ux-patterns--best-practices) for complete pattern implementations, code examples, edge cases, and testing approaches.

---

## Quick Reference

### Key File Locations

```
/backend/
├── main.py                          # Main entry point
├── lamb/
│   ├── main.py                      # Core API
│   ├── assistant_router.py          # Assistant CRUD
│   ├── completions/main.py          # Completion pipeline
│   └── owi_bridge/                  # OWI integration
├── creator_interface/
│   ├── main.py                      # Creator API
│   ├── assistant_router.py          # Proxied assistant ops
│   └── knowledges_router.py         # KB operations
└── utils/
    ├── db_manager.py                # Database access
    └── owi_manager.py               # OWI communication

/frontend/svelte-app/
├── src/routes/                      # Pages
├── src/lib/components/              # UI components
└── src/lib/services/                # API clients
```

### Common Tasks

**Create Assistant:**
1. POST `/creator/assistant/create`
2. Configure model, system prompt, temperature
3. Optionally assign knowledge bases
4. Publish to OWI if needed

**Add Knowledge Base:**
1. POST `/creator/knowledgebases/create`
2. POST `/creator/knowledgebases/{id}/upload` (files)
3. Assign to assistant in metadata.rag_config

**Manage Users:**
1. POST `/creator/admin/users/create` (org admin)
2. PUT `/creator/admin/users/update-role-by-email`
3. PUT `/creator/admin/users/{id}/status` (enable/disable)

**Query Assistant:**
1. POST `/v1/chat/completions`
2. Authorization: Bearer {assistant_api_key}
3. Stream or complete response

---

## Important Architectural Notes

### Service Communication
- **Frontend ↔ Backend:** REST API (HTTP/JSON)
- **Backend ↔ OWI:** Direct database access (SQLite)
- **Backend ↔ KB Server:** REST API (HTTP/JSON)
- **Backend ↔ LLM Providers:** Provider-specific APIs (OpenAI, Ollama)

### Data Flow Patterns
1. **User Creation:** Frontend → Creator API → LAMB DB → OWI DB (sync)
2. **Assistant Creation:** Frontend → Creator API → LAMB DB
3. **Publishing:** LAMB DB → OWI DB (assistant as model)
4. **Completion:** Client → Backend → Plugins → LLM Provider
5. **RAG:** Completion Pipeline → KB Server → ChromaDB → Plugin

### Security Considerations
- JWT tokens validated against OWI database
- Assistant API keys for completion endpoints
- Organization isolation enforced at data layer
- Role-based access control (owner/admin/member)
- LTI signature verification for LMS launches

### Performance Patterns
- SQLite with WAL mode for concurrency
- Indexed foreign keys and common queries
- Streaming responses for completions
- Async I/O throughout backend
- ChromaDB caching for vector search

---

## Additional Resources

- **Full Architecture:** [lamb_architecture.md](./lamb_architecture.md)
- **PRD:** [prd.md](./prd.md) - Product requirements and user stories
- **Chat Analytics:** [chat_analytics_project.md](./chat_analytics_project.md) - Detailed analytics implementation
- **Multi-Tool Specs:** 
  - [MULTI_TOOL_DEV_PLAN.md](./MULTI_TOOL_DEV_PLAN.md)
  - [MULTI_TOOL_ASSISTANT_BACKEND_SPEC.md](./MULTI_TOOL_ASSISTANT_BACKEND_SPEC.md)
  - [MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md](./MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md)
  - [TOOL_ASSISTANTS_ANALYSIS_REPORT.md](./TOOL_ASSISTANTS_ANALYSIS_REPORT.md)
- **Contributing:** [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines

**Support:**
- GitHub: https://github.com/Lamb-Project/lamb
- Website: https://lamb-project.org

---

**Version History:**
- 2.9 (Dec 27, 2025): Added Chat Analytics feature (Section 14), updated routers
- 2.8 (Dec 9, 2025): Essential guide created from full documentation
- See full architecture document for complete version history

**Maintainers:** LAMB Development Team