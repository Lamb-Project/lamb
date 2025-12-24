# LAMB Database Schema Documentation

**Version:** 1.0  
**Last Updated:** November 2025  
**Database Type:** SQLite (Two separate databases)  
**Target Audience:** Developers, Database Administrators, AI Agents

---

## Table of Contents

1. [Overview](#overview)
2. [Database Architecture](#database-architecture)
3. [LAMB Database Tables](#lamb-database-tables)
4. [Open WebUI Database Tables](#open-webui-database-tables)
5. [Cross-Database Integration](#cross-database-integration)
6. [Relationships Summary](#relationships-summary)
7. [JSON Field Structures](#json-field-structures)
8. [Indexes and Performance](#indexes-and-performance)

---

## Overview

The LAMB platform uses **two separate SQLite databases**:

1. **LAMB Database** (`lamb_v4.db`) - Core platform data
2. **Open WebUI Database** (`webui.db`) - Authentication and chat interface

This separation allows for:
- Independent scaling and maintenance
- Clear separation of concerns
- Flexibility in deployment architectures
- Integration with existing Open WebUI installations

---

## Database Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAMB DATABASE STRUCTURE                      │
└─────────────────────────────────────────────────────────────────┘

1. ORGANIZATIONS (Multi-tenancy root)
   ├── organization_roles (User roles in orgs)
   ├── Creator_users (User accounts)
   ├── assistants (Learning assistants)
   ├── rubrics (Evaluation criteria)
   ├── prompt_templates (Reusable prompts)
   ├── kb_registry (Knowledge Base metadata)
   └── usage_logs (System usage tracking)

2. ASSISTANTS (Core feature)
   ├── assistant_publish (Publishing info)
   ├── assistant_shares (Sharing relationships)
   └── lti_users (LTI access tracking)

3. STANDALONE
   ├── model_permissions (User-model access)
   └── (indexes and constraints)
```

---

## LAMB Database Tables

### 1. organizations

**Purpose:** Multi-tenant organizational units with independent configurations

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
)
```

**Fields:**
- `id` - Primary key
- `slug` - Unique identifier (e.g., "engineering", "lamb")
- `name` - Display name (e.g., "Engineering Department")
- `is_system` - Special flag for "lamb" system organization
- `status` - Organization status: active, suspended, or trial
- `config` - JSON configuration (see JSON structures section)
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_organizations_slug` (UNIQUE)
- `idx_organizations_status`
- `idx_organizations_is_system`

**Relationships:**
- Contains: organization_roles, Creator_users, assistants, rubrics, prompt_templates, kb_registry, usage_logs

---

### 2. Creator_users

**Purpose:** User accounts with type differentiation (creator vs end_user)

```sql
CREATE TABLE Creator_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    user_email TEXT NOT NULL UNIQUE,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'creator' CHECK(user_type IN ('creator', 'end_user')),
    user_config JSON,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
)
```

**Fields:**
- `id` - Primary key
- `organization_id` - Foreign key to organizations
- `user_email` - Unique email address
- `user_name` - Display name
- `user_type` - User type: creator (full access) or end_user (OWI only)
- `user_config` - JSON configuration (preferences, permissions)
- `enabled` - Account status (1=active, 0=disabled)
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_creator_users_org` (organization_id)
- `idx_creator_users_type` (user_type)
- `idx_creator_users_enabled` (enabled)

**User Types:**
- **creator** - Full creator interface access, can create/manage assistants
- **end_user** - Auto-redirect to Open WebUI, no creator interface access

**Relationships:**
- Belongs to: organizations
- Has roles in: organization_roles
- Creates: assistants (via email reference)
- Shares: assistant_shares (as sharer and recipient)
- Owns: rubrics, prompt_templates, kb_registry

---

### 3. organization_roles

**Purpose:** User roles within organizations (owner/admin/member)

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
)
```

**Fields:**
- `id` - Primary key
- `organization_id` - Foreign key to organizations (CASCADE DELETE)
- `user_id` - Foreign key to Creator_users (CASCADE DELETE)
- `role` - Role type: owner, admin, or member
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_org_roles_org` (organization_id)
- `idx_org_roles_user` (user_id)
- `idx_org_roles_role` (role)

**Roles:**
- **owner** - Full control over organization
- **admin** - Manage settings and members
- **member** - Create assistants within organization

---

### 4. assistants

**Purpose:** Learning assistant definitions with plugin configurations

```sql
CREATE TABLE assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    owner TEXT NOT NULL,
    api_callback TEXT,
    system_prompt TEXT,
    prompt_template TEXT,
    RAG_endpoint TEXT,
    RAG_Top_k INTEGER,
    RAG_collections TEXT,
    pre_retrieval_endpoint TEXT,
    post_retrieval_endpoint TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    published BOOLEAN DEFAULT FALSE,
    published_at INTEGER,
    group_id TEXT,
    group_name TEXT,
    oauth_consumer_name TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE(organization_id, name, owner)
)
```

**Fields:**
- `id` - Primary key
- `organization_id` - Foreign key to organizations
- `name` - Assistant name
- `description` - Assistant description
- `owner` - Creator email (TEXT reference, not FK)
- `api_callback` - **CRITICAL:** Stores metadata JSON (connector, llm, processors)
- `system_prompt` - System instructions for LLM
- `prompt_template` - Message formatting template
- `RAG_endpoint` - DEPRECATED (always empty)
- `RAG_Top_k` - Number of chunks to retrieve from KB
- `RAG_collections` - Comma-separated Knowledge Base IDs
- `pre_retrieval_endpoint` - DEPRECATED (always empty)
- `post_retrieval_endpoint` - DEPRECATED (always empty)
- `published` - Publication status
- `published_at` - UNIX timestamp of publication
- `group_id` - Open WebUI group ID for access control
- `group_name` - Group display name
- `oauth_consumer_name` - LTI consumer key for published assistant
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_assistants_org` (organization_id)
- `idx_assistants_owner` (owner)
- `idx_assistants_published` (published)

**CRITICAL NOTE:** The `api_callback` field stores the assistant's metadata as JSON. In code, this is accessed as `assistant.metadata`, but in the database it's stored in the `api_callback` column to avoid schema changes.

**Relationships:**
- Belongs to: organizations
- Created by: Creator_users (via email)
- Published as: assistant_publish
- Shared via: assistant_shares
- Accessed by LTI: lti_users
- Tracked in: usage_logs

---

### 5. assistant_publish

**Purpose:** Publishing metadata for LTI integration

```sql
CREATE TABLE assistant_publish (
    assistant_id INTEGER PRIMARY KEY,
    assistant_name TEXT NOT NULL,
    assistant_owner TEXT NOT NULL,
    group_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    oauth_consumer_name TEXT UNIQUE,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE
)
```

**Fields:**
- `assistant_id` - Primary key and foreign key to assistants
- `assistant_name` - Assistant name (denormalized)
- `assistant_owner` - Owner email (denormalized)
- `group_id` - Open WebUI group ID
- `group_name` - Group display name
- `oauth_consumer_name` - Unique LTI consumer key
- `created_at` - UNIX timestamp

**Unique Constraints:**
- `assistant_id` (PRIMARY KEY)
- `oauth_consumer_name` (UNIQUE)

**Purpose:** Tracks published assistants for LTI integration. One-to-one relationship with assistants.

---

### 6. assistant_shares

**Purpose:** Assistant sharing relationships within organizations

```sql
CREATE TABLE assistant_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    shared_with_user_id INTEGER NOT NULL,
    shared_by_user_id INTEGER NOT NULL,
    shared_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_by_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(assistant_id, shared_with_user_id)
)
```

**Fields:**
- `id` - Primary key
- `assistant_id` - Foreign key to assistants (CASCADE DELETE)
- `shared_with_user_id` - Recipient user ID (CASCADE DELETE)
- `shared_by_user_id` - Sharer user ID (CASCADE DELETE)
- `shared_at` - UNIX timestamp

**Indexes:**
- `idx_assistant_shares_assistant` (assistant_id)
- `idx_assistant_shares_shared_with` (shared_with_user_id)

**Unique Constraints:**
- `(assistant_id, shared_with_user_id)` - Prevent duplicate shares

**Purpose:** NEW FEATURE - Organization-level assistant sharing. Synchronized with OWI groups for actual access control.

---

### 7. lti_users

**Purpose:** Track LTI launches and map LMS users to OWI users

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
    lti_context_id TEXT NOT NULL,
    lti_app_id TEXT,
    user_role TEXT DEFAULT 'student',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(user_email, assistant_id)
)
```

**Fields:**
- `id` - Primary key
- `assistant_id` - Assistant identifier (TEXT)
- `assistant_name` - Assistant name
- `group_id` - OWI group ID
- `group_name` - Group display name
- `assistant_owner` - Owner email
- `user_email` - LTI user email
- `user_name` - LTI user name
- `user_display_name` - Display name from LMS
- `lti_context_id` - LMS course/context ID
- `lti_app_id` - LTI application identifier
- `user_role` - LTI role (e.g., 'student', 'instructor')
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Unique Constraints:**
- `(user_email, assistant_id)` - One record per user per assistant

---

### 8. rubrics

**Purpose:** Evaluation rubrics for AI assessment

```sql
CREATE TABLE rubrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rubric_id TEXT UNIQUE NOT NULL,
    organization_id INTEGER NOT NULL,
    owner_email TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    rubric_data JSON NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    is_showcase BOOLEAN DEFAULT FALSE,
    parent_rubric_id TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_rubric_id) REFERENCES rubrics(rubric_id) ON DELETE SET NULL
)
```

**Fields:**
- `id` - Primary key
- `rubric_id` - Unique UUID identifier
- `organization_id` - Foreign key to organizations (CASCADE DELETE)
- `owner_email` - Creator email
- `title` - Rubric title
- `description` - Rubric description
- `rubric_data` - JSON structure (criteria, levels, points)
- `is_public` - Public visibility flag
- `is_showcase` - Showcase flag
- `parent_rubric_id` - Self-reference for forking (SET NULL on delete)
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_rubrics_org` (organization_id)
- `idx_rubrics_owner` (owner_email)
- `idx_rubrics_public` (is_public)

**Special Feature:** Self-referencing `parent_rubric_id` allows rubric forking/inheritance.

---

### 9. prompt_templates

**Purpose:** Reusable prompt templates shareable within organizations

```sql
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    owner_email TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    prompt_template TEXT,
    is_shared BOOLEAN DEFAULT FALSE,
    metadata JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_email) REFERENCES Creator_users(user_email) ON DELETE CASCADE,
    UNIQUE(organization_id, owner_email, name)
)
```

**Fields:**
- `id` - Primary key
- `organization_id` - Foreign key to organizations (CASCADE DELETE)
- `owner_email` - Foreign key to Creator_users email (CASCADE DELETE)
- `name` - Template name
- `description` - Template description
- `system_prompt` - System instructions template
- `prompt_template` - Message formatting template
- `is_shared` - Sharing flag within organization
- `metadata` - Additional JSON metadata
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_prompt_templates_org` (organization_id)
- `idx_prompt_templates_owner` (owner_email)
- `idx_prompt_templates_shared` (is_shared)

**Unique Constraints:**
- `(organization_id, owner_email, name)` - Unique per user per org

---

### 10. kb_registry

**Purpose:** Knowledge Base metadata registry (actual documents in ChromaDB)

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
```

**Fields:**
- `id` - Primary key
- `kb_id` - Unique ChromaDB collection ID
- `kb_name` - Knowledge Base display name
- `owner_user_id` - Foreign key to Creator_users (CASCADE DELETE)
- `organization_id` - Foreign key to organizations (CASCADE DELETE)
- `is_shared` - Sharing flag within organization
- `metadata` - Additional JSON metadata
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Indexes:**
- `idx_kb_registry_owner` (owner_user_id)
- `idx_kb_registry_org_shared` (organization_id, is_shared)
- `idx_kb_registry_kb_id` (kb_id)

**Special Features:**
- **Auto-Registration:** KBs found in KB Server but not in registry are automatically registered
- **Lazy Cleanup:** If KB Server returns 404, registry entry is automatically removed (self-healing)

---

### 11. usage_logs

**Purpose:** Analytics and usage tracking

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
)
```

**Fields:**
- `id` - Primary key
- `organization_id` - Foreign key to organizations
- `user_id` - Foreign key to Creator_users (nullable)
- `assistant_id` - Foreign key to assistants (nullable)
- `usage_data` - JSON structure (event, tokens, model, duration)
- `created_at` - UNIX timestamp

**Indexes:**
- `idx_usage_logs_org_date` (organization_id, created_at)
- `idx_usage_logs_user_date` (user_id, created_at)

---

### 12. model_permissions

**Purpose:** Fine-grained model access control per user

```sql
CREATE TABLE model_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    model_name TEXT NOT NULL,
    access_type TEXT NOT NULL CHECK(access_type IN ('include', 'exclude')),
    UNIQUE(user_email, model_name)
)
```

**Fields:**
- `id` - Primary key
- `user_email` - User email (TEXT reference)
- `model_name` - Model/assistant name
- `access_type` - Access type: include or exclude

**Unique Constraints:**
- `(user_email, model_name)` - One permission per user per model

---

## Open WebUI Database Tables

### OWI: user

**Purpose:** User accounts for Open WebUI authentication

```sql
CREATE TABLE user (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    profile_image_url TEXT,
    api_key TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_active_at INTEGER NOT NULL,
    settings TEXT,
    info TEXT,
    oauth_sub TEXT
)
```

**Fields:**
- `id` - Primary key (UUID)
- `name` - Display name
- `email` - Unique email address
- `role` - User role: admin or user
- `profile_image_url` - Profile image URL
- `api_key` - Unique API key
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp
- `last_active_at` - Last activity timestamp
- `settings` - JSON string (user preferences)
- `info` - JSON string (additional info)
- `oauth_sub` - OAuth subject identifier

**Unique Constraints:**
- `email` (UNIQUE)
- `api_key` (UNIQUE)

**Linked to LAMB:** via email (Creator_users.user_email)

---

### OWI: auth

**Purpose:** Password storage and authentication

```sql
CREATE TABLE auth (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    active INTEGER NOT NULL
)
```

**Fields:**
- `id` - Primary key (UUID, matches user.id)
- `email` - Unique email address
- `password` - bcrypt hashed password
- `active` - Account active status (0 or 1)

**Unique Constraints:**
- `id` (PRIMARY KEY, UNIQUE)
- `email` (UNIQUE)

**Password Hashing:** bcrypt with cost factor 12

---

### OWI: group

**Purpose:** User groups for access control to published assistants

```sql
CREATE TABLE group (
    id TEXT NOT NULL,
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
)
```

**Fields:**
- `id` - Primary key (UUID)
- `user_id` - Foreign key to user (group owner)
- `name` - Group display name
- `description` - Group description
- `data` - Additional JSON data
- `meta` - Metadata JSON
- `permissions` - JSON structure (read/write access lists)
- `user_ids` - JSON array of user UUIDs with access
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Linked to LAMB:** via group_id (assistants.group_id, assistant_publish.group_id)

**Purpose:** Controls access to published assistants. LAMB syncs assistant sharing with OWI groups.

---

### OWI: model

**Purpose:** Published assistants appear as OWI models

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
)
```

**Fields:**
- `id` - Primary key (format: `lamb_assistant.{id}`)
- `user_id` - Foreign key to user (model owner)
- `base_model_id` - LAMB backend URL
- `name` - Model display name
- `params` - JSON configuration (assistant settings)
- `meta` - Additional metadata JSON
- `created_at` - UNIX timestamp
- `updated_at` - UNIX timestamp

**Linked to LAMB:** via id pattern `lamb_assistant.{assistant_id}`

**Purpose:** Published LAMB assistants appear as models in Open WebUI chat interface.

---

## Cross-Database Integration

### Integration Points

```
LAMB Database              ←→   Open WebUI Database
─────────────────────────────────────────────────────
Creator_users.user_email   ←→   user.email / auth.email
assistants.group_id        ←→   group.id
assistants.id              ←→   model.id (as lamb_assistant.{id})
assistant_publish.group_id ←→   group.id
```

### Integration Flow

1. **User Creation:**
   - LAMB creates Creator_users record
   - LAMB creates OWI user and auth records
   - Email links the two databases

2. **Assistant Publishing:**
   - LAMB creates assistant_publish record
   - LAMB creates/updates OWI group
   - LAMB creates OWI model with id `lamb_assistant.{id}`
   - Group ID stored in both databases

3. **Assistant Sharing:**
   - LAMB creates assistant_shares records
   - LAMB updates OWI group membership
   - Users added to group.user_ids JSON array

4. **LTI Launch:**
   - LMS user launches via LTI
   - LAMB creates/finds OWI user
   - LAMB adds user to OWI group
   - LAMB creates lti_users record
   - User redirected to OWI chat

---

## Relationships Summary

### Organizations (Multi-tenant root)

```
organizations (1) ─────────── (*) organization_roles
organizations (1) ─────────── (*) Creator_users
organizations (1) ─────────── (*) assistants
organizations (1) ─────────── (*) rubrics
organizations (1) ─────────── (*) prompt_templates
organizations (1) ─────────── (*) kb_registry
organizations (1) ─────────── (*) usage_logs
```

### Users

```
Creator_users (1) ─────────── (*) organization_roles
Creator_users (1) ─────────── (*) assistants (as creator, via email)
Creator_users (1) ─────────── (*) assistant_shares (as sharer)
Creator_users (1) ─────────── (*) assistant_shares (as recipient)
Creator_users (1) ─────────── (*) rubrics
Creator_users (1) ─────────── (*) prompt_templates
Creator_users (1) ─────────── (*) kb_registry
Creator_users (1) ─────────── (*) usage_logs
```

### Assistants

```
assistants (1) ────────────── (0..1) assistant_publish
assistants (1) ────────────── (*) assistant_shares
assistants (1) ────────────── (*) lti_users
assistants (1) ────────────── (*) usage_logs
```

### Special Relationships

```
rubrics (*) ───────────────── (0..1) rubrics (parent_rubric_id)
   └─ Self-referencing for forking rubrics
```

### Cross-Database

```
Creator_users.user_email ←→ user.email (OWI)
Creator_users.user_email ←→ auth.email (OWI)
assistants.group_id ←→ group.id (OWI)
assistants.id ←→ model.id (OWI, as lamb_assistant.{id})
```

---

## JSON Field Structures

### organizations.config

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
    "system_prompt": "You are a helpful assistant."
  },
  "features": {
    "signup_enabled": false,
    "signup_key": "org-signup-key",
    "sharing_enabled": true
  }
}
```

### Creator_users.user_config

```json
{
  "preferences": {
    "language": "en",
    "theme": "light"
  },
  "can_share": true
}
```

### assistants.api_callback (metadata)

**CRITICAL:** This field stores the plugin configuration that determines how the assistant processes requests.

```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag"
}
```

**Available Plugins:**

**Connectors:**
- `openai` - OpenAI API (organization-aware)
- `ollama` - Ollama local models (organization-aware)
- `anthropic` - Anthropic Claude models
- `bypass` - Testing connector (returns messages as-is)

**Prompt Processors:**
- `simple_augment` - Adds system prompt and RAG context

**RAG Processors:**
- `simple_rag` - Queries KB server and formats context
- `single_file_rag` - Retrieves from single file
- `no_rag` - No retrieval (returns empty context)

### usage_logs.usage_data

```json
{
  "event": "completion",
  "tokens_used": 150,
  "model": "gpt-4o-mini",
  "duration_ms": 1234,
  "user_agent": "Mozilla/5.0...",
  "ip_address": "192.168.1.1"
}
```

### rubrics.rubric_data

```json
{
  "criteria": [
    {
      "name": "Content Quality",
      "description": "Accuracy and relevance of content",
      "levels": [
        {"name": "Excellent", "points": 5, "description": "..."},
        {"name": "Good", "points": 4, "description": "..."},
        {"name": "Fair", "points": 3, "description": "..."}
      ]
    }
  ]
}
```

### group.permissions (OWI)

```json
{
  "read": {
    "group_ids": [],
    "user_ids": ["uuid-1", "uuid-2", "uuid-3"]
  },
  "write": {
    "group_ids": [],
    "user_ids": []
  }
}
```

---

## Indexes and Performance

### LAMB Database Indexes

**organizations:**
- `idx_organizations_slug` (UNIQUE) - Fast lookup by slug
- `idx_organizations_status` - Filter by status
- `idx_organizations_is_system` - Identify system org

**organization_roles:**
- `idx_org_roles_org` - Lookup users in org
- `idx_org_roles_user` - Lookup user's orgs
- `idx_org_roles_role` - Filter by role type

**Creator_users:**
- `idx_creator_users_org` - Users in organization
- `idx_creator_users_type` - Filter by user type
- `idx_creator_users_enabled` - Filter active/disabled users

**assistants:**
- `idx_assistants_org` - Assistants in organization
- `idx_assistants_owner` - Assistants by creator
- `idx_assistants_published` - Filter published assistants

**assistant_shares:**
- `idx_assistant_shares_assistant` - Shares for assistant
- `idx_assistant_shares_shared_with` - Assistants shared with user

**rubrics:**
- `idx_rubrics_org` - Rubrics in organization
- `idx_rubrics_owner` - Rubrics by creator
- `idx_rubrics_public` - Public rubrics

**prompt_templates:**
- `idx_prompt_templates_org` - Templates in organization
- `idx_prompt_templates_owner` - Templates by creator
- `idx_prompt_templates_shared` - Shared templates

**kb_registry:**
- `idx_kb_registry_owner` - KBs by owner
- `idx_kb_registry_org_shared` - Shared KBs in org (composite)
- `idx_kb_registry_kb_id` - Lookup by KB ID

**usage_logs:**
- `idx_usage_logs_org_date` - Usage by org and date (composite)
- `idx_usage_logs_user_date` - Usage by user and date (composite)

### Query Optimization Tips

1. **Use indexed columns in WHERE clauses**
   ```sql
   -- Good: Uses index
   SELECT * FROM assistants WHERE organization_id = ? AND published = 1;
   
   -- Bad: No index on name alone
   SELECT * FROM assistants WHERE name LIKE '%test%';
   ```

2. **Leverage composite indexes**
   ```sql
   -- Good: Uses composite index efficiently
   SELECT * FROM usage_logs 
   WHERE organization_id = ? AND created_at > ?
   ORDER BY created_at DESC;
   ```

3. **Avoid SELECT * when possible**
   ```sql
   -- Good: Only fetch needed columns
   SELECT id, name, description FROM assistants WHERE owner = ?;
   ```

4. **Use EXPLAIN QUERY PLAN to verify index usage**
   ```sql
   EXPLAIN QUERY PLAN
   SELECT * FROM assistants WHERE organization_id = 1 AND published = 1;
   ```

---

## Migration Notes

### Adding enabled Column (User Blocking Feature)

The `enabled` column was added to `Creator_users` via automatic migration:

```sql
-- Migration runs on startup if column doesn't exist
ALTER TABLE Creator_users 
ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1;

CREATE INDEX idx_creator_users_enabled ON Creator_users(enabled);
```

**Backward Compatibility:** All existing users default to `enabled = 1` (active).

### Adding assistant_shares Table (Sharing Feature)

The `assistant_shares` table was added for the assistant sharing feature:

```sql
CREATE TABLE assistant_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    shared_with_user_id INTEGER NOT NULL,
    shared_by_user_id INTEGER NOT NULL,
    shared_at INTEGER NOT NULL,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_by_user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(assistant_id, shared_with_user_id)
);
```

### Adding kb_registry Table (KB Sharing Feature)

The `kb_registry` table was added to track Knowledge Base sharing:

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
);
```

---

## Data Integrity Considerations

### Soft References (EMAIL-based)

Some relationships use email addresses instead of foreign keys:

**Advantages:**
- Flexibility across database systems
- Easier data export/import
- Human-readable references

**Disadvantages:**
- No automatic CASCADE actions
- Must manually maintain referential integrity
- Email changes require updates in multiple places

**Tables Using Email References:**
- `assistants.owner` → Creator_users.user_email
- `rubrics.owner_email` → Creator_users.user_email
- `prompt_templates.owner_email` → Creator_users.user_email (has FK)
- `model_permissions.user_email` → Creator_users.user_email

### Cascade Delete Behavior

**ON DELETE CASCADE:**
- Organization deletion → Deletes all org resources
- User deletion → Deletes user's assistants, shares, KBs
- Assistant deletion → Deletes shares and publish records

**ON DELETE SET NULL:**
- Parent rubric deletion → Sets child's parent_rubric_id to NULL

### Unique Constraints

Critical unique constraints prevent data corruption:

- `(organization_id, user_id)` in organization_roles
- `(assistant_id, shared_with_user_id)` in assistant_shares
- `(user_email, assistant_id)` in lti_users
- `(organization_id, owner_email, name)` in prompt_templates
- `(user_email, model_name)` in model_permissions

---

## Security Considerations

### Password Storage

- Passwords stored in OWI `auth` table only
- bcrypt hashing with cost factor 12
- LAMB never stores plain-text passwords

### API Keys

- Organization LLM API keys stored in `organizations.config` JSON
- KB server API keys stored in `organizations.config` JSON
- User API keys stored in OWI `user.api_key` (for OWI API access)

### Data Isolation

- Multi-tenancy enforced via `organization_id`
- All queries must filter by organization
- Cross-organization data access prevented

### Enabled/Disabled Accounts

- `Creator_users.enabled` flag controls login access
- Disabled users cannot authenticate
- All user resources remain intact (no data loss)

---

## Backup and Maintenance

### Database Files

```
LAMB Database:     $LAMB_DB_PATH/lamb_v4.db
Open WebUI DB:     $OWI_PATH/webui.db
Knowledge Base:    $OWI_PATH/vector_db/ (ChromaDB)
```

### Backup Strategy

1. **SQLite Databases:**
   ```bash
   # Backup LAMB database
   sqlite3 $LAMB_DB_PATH/lamb_v4.db ".backup backup_lamb_$(date +%Y%m%d).db"
   
   # Backup OWI database
   sqlite3 $OWI_PATH/webui.db ".backup backup_owi_$(date +%Y%m%d).db"
   ```

2. **Vector Database:**
   ```bash
   # Backup ChromaDB directory
   tar -czf backup_chromadb_$(date +%Y%m%d).tar.gz $OWI_PATH/vector_db/
   ```

### Vacuum and Optimize

```sql
-- Reclaim space and optimize
VACUUM;
ANALYZE;

-- Rebuild indexes
REINDEX;
```

### Database Integrity Check

```sql
-- Check database integrity
PRAGMA integrity_check;

-- Check foreign keys
PRAGMA foreign_key_check;
```

---

## Troubleshooting

### Common Issues

**Issue: Foreign key constraint failed**
- Ensure `PRAGMA foreign_keys = ON;` is set
- Check that referenced records exist
- Verify cascade delete behavior

**Issue: Unique constraint violation**
- Check for existing records before insert
- Use `INSERT OR REPLACE` for upserts
- Verify unique constraint definitions

**Issue: Slow queries**
- Run `EXPLAIN QUERY PLAN` to check index usage
- Add missing indexes
- Consider denormalization for frequently accessed data

---

## Appendix: SQL Quick Reference

### Get All Tables

```sql
SELECT name FROM sqlite_master WHERE type='table';
```

### Get Table Schema

```sql
PRAGMA table_info(assistants);
```

### Get All Indexes

```sql
SELECT name, tbl_name FROM sqlite_master WHERE type='index';
```

### Get Foreign Keys

```sql
PRAGMA foreign_key_list(assistants);
```

### Get Database Size

```sql
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();
```

---

**Document Maintainers:** LAMB Development Team  
**Last Updated:** November 2025  
**Version:** 1.0

