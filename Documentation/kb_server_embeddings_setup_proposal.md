# KB-Server Embeddings Setup Design Proposal

**Version:** 1.0  
**Date:** January 17, 2026  
**Status:** Draft for Review  
**Author:** Development Team

---

## 1. Executive Summary

This document proposes a redesign of how the KB-Server manages embeddings configurations to support:

1. **Organization-level management** of embeddings providers and API keys
2. **Reusable "Embeddings Setups"** that collections reference (not copy)
3. **Seamless API key rotation** affecting all collections using a setup
4. **Provider migration** (e.g., OpenAI → OpenRouter) without recreating collections
5. **User choice** of embeddings model at collection creation time

### Key Concept: Embeddings Setup

An **Embeddings Setup** is an organization-level configuration that defines:
- Which provider/vendor to use (OpenAI, Ollama, OpenRouter, etc.)
- The API endpoint URL
- The API key for authentication
- The model name (as the provider expects it)

Collections **reference** a setup rather than storing their own configuration. When the setup is updated (e.g., API key rotation), all collections using it automatically use the new configuration.

---

## 2. Problem Statement

### Current Architecture

```
Collection
├── embeddings_model (JSON):
│   ├── model: "text-embedding-3-small"
│   ├── vendor: "openai"
│   ├── api_endpoint: "https://api.openai.com/v1/embeddings"
│   └── apikey: "sk-xxx..."  ← Duplicated across every collection
```

### Issues

| Problem | Impact |
|---------|--------|
| API key stored per collection | Key rotation requires updating every collection |
| No organization concept | Can't manage setups at org level |
| Duplication | Same config copied N times |
| Provider migration | Changing from OpenAI to OpenRouter requires manual updates |
| No choice for users | Can't offer multiple setups to choose from |

---

## 3. Proposed Solution

### 3.1 New Entity: Embeddings Setup

An **Embeddings Setup** is a named, reusable embeddings configuration belonging to an organization.

```
┌─────────────────────────────────────────────────────────────┐
│                    Embeddings Setup                          │
├─────────────────────────────────────────────────────────────┤
│  id: 1                                                       │
│  organization_id: "org_123"                                  │
│  name: "OpenAI Production"                                   │
│  setup_key: "openai-prod"                                    │
│                                                              │
│  vendor: "openai"                                            │
│  api_endpoint: "https://api.openai.com/v1/embeddings"        │
│  api_key: "sk-proj-xxx..."                                   │
│  model_name: "text-embedding-3-small"                        │
│                                                              │
│  embedding_dimensions: 1536  ← For validation                │
│  is_default: true                                            │
│  is_active: true                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Collections Reference Setups

```
┌─────────────────────────────────────────────────────────────┐
│                      Collection                              │
├─────────────────────────────────────────────────────────────┤
│  id: 42                                                      │
│  name: "Research Papers KB"                                  │
│  organization_id: "org_123"                                  │
│  owner: "user_456"                                           │
│                                                              │
│  embeddings_setup_id: 1  ← References setup, not a copy      │
│  embedding_dimensions: 1536  ← Locked at creation            │
│                                                              │
│  (No api_key stored here!)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 How It Works

#### Collection Creation

```
1. User creates collection, chooses from available setups
2. System records:
   - embeddings_setup_id = chosen setup's ID
   - embedding_dimensions = setup's current dimensions (locked)
3. Collection uses setup's current config for embedding operations
```

#### API Key Rotation

```
1. Org admin updates setup's api_key
2. All collections referencing this setup automatically use new key
3. No per-collection updates needed
```

#### Provider Migration (e.g., OpenAI → OpenRouter)

```
Before:
  vendor: "openai"
  api_endpoint: "https://api.openai.com/v1/embeddings"
  model_name: "text-embedding-3-small"

After:
  vendor: "openrouter"
  api_endpoint: "https://openrouter.ai/api/v1/embeddings"
  model_name: "openai/text-embedding-3-small"

Same underlying model, different provider → Safe migration
```

---

## 4. Data Model

### 4.1 Database Schema

```sql
-- ═══════════════════════════════════════════════════════════════
-- Organizations (new table in KB-Server)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,     -- LAMB organization ID/slug
    name TEXT NOT NULL,
    config JSON,                           -- Future extensibility
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_external_id ON organizations(external_id);


-- ═══════════════════════════════════════════════════════════════
-- Embeddings Setups (the core new entity)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE embeddings_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    
    -- Identity
    name TEXT NOT NULL,                    -- Human-friendly: "OpenAI Production"
    setup_key TEXT NOT NULL,               -- Machine key: "openai-prod"
    description TEXT,                      -- Optional description
    
    -- Provider Configuration (CAN be updated)
    vendor TEXT NOT NULL,                  -- "openai", "ollama", "openrouter", etc.
    api_endpoint TEXT,                     -- Full endpoint URL
    api_key TEXT,                          -- API key (encrypted at rest ideally)
    model_name TEXT NOT NULL,              -- Model name as provider expects it
    
    -- Embedding Model Identity (for validation)
    embedding_dimensions INTEGER NOT NULL, -- Vector dimensions (e.g., 1536, 768)
    
    -- Status
    is_default BOOLEAN DEFAULT FALSE,      -- Default for new collections
    is_active BOOLEAN DEFAULT TRUE,        -- Can be disabled without deletion
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE(organization_id, setup_key)
);

CREATE INDEX idx_embeddings_setups_org ON embeddings_setups(organization_id);
CREATE INDEX idx_embeddings_setups_org_default ON embeddings_setups(organization_id, is_default);


-- ═══════════════════════════════════════════════════════════════
-- Modified Collections Table
-- ═══════════════════════════════════════════════════════════════
-- Add new columns to existing collections table:

ALTER TABLE collections ADD COLUMN organization_id INTEGER 
    REFERENCES organizations(id);

ALTER TABLE collections ADD COLUMN embeddings_setup_id INTEGER 
    REFERENCES embeddings_setups(id);

ALTER TABLE collections ADD COLUMN embedding_dimensions INTEGER;

-- Keep existing embeddings_model column for backward compatibility during migration
-- Will be deprecated and removed in future version

CREATE INDEX idx_collections_org ON collections(organization_id);
CREATE INDEX idx_collections_setup ON collections(embeddings_setup_id);
```

### 4.2 Entity Relationships

```
┌──────────────────┐
│   Organization   │
│  (from LAMB)     │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────▼─────────┐
│ Embeddings Setup │ ◄─── Org admin manages these
│                  │
│ - OpenAI Prod    │
│ - OpenAI Dev     │
│ - Ollama Local   │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────▼─────────┐
│   Collection     │ ◄─── Users create these, choose a setup
│                  │
│ - Research KB    │
│ - Course Materials│
└──────────────────┘
```

---

## 5. API Design

### 5.1 Organization Endpoints

These are called by LAMB to sync organization data.

```http
# Register/update organization (called by LAMB)
POST /organizations
Authorization: Bearer {kb_server_token}
Content-Type: application/json

{
  "external_id": "org_123",
  "name": "University of Example"
}

Response 201:
{
  "id": 1,
  "external_id": "org_123",
  "name": "University of Example",
  "created_at": "2026-01-17T10:00:00Z"
}
```

```http
# Get organization by external ID
GET /organizations/{external_id}
Authorization: Bearer {kb_server_token}

Response 200:
{
  "id": 1,
  "external_id": "org_123",
  "name": "University of Example",
  "setups_count": 3,
  "collections_count": 47
}
```

### 5.2 Embeddings Setup Endpoints

These are the core management endpoints for org admins.

```http
# List setups for an organization
GET /organizations/{org_external_id}/embeddings-setups
Authorization: Bearer {kb_server_token}

Response 200:
{
  "setups": [
    {
      "id": 1,
      "name": "OpenAI Production",
      "setup_key": "openai-prod",
      "vendor": "openai",
      "model_name": "text-embedding-3-small",
      "embedding_dimensions": 1536,
      "is_default": true,
      "is_active": true,
      "collections_count": 42,
      "api_key_configured": true,  // Never expose actual key
      "api_key_last_updated": "2026-01-15T10:00:00Z"
    },
    {
      "id": 2,
      "name": "Ollama Local",
      "setup_key": "ollama-local",
      "vendor": "ollama",
      "model_name": "nomic-embed-text",
      "embedding_dimensions": 768,
      "is_default": false,
      "is_active": true,
      "collections_count": 5,
      "api_key_configured": false
    }
  ],
  "total": 2
}
```

```http
# Create a new setup
POST /organizations/{org_external_id}/embeddings-setups
Authorization: Bearer {kb_server_token}
Content-Type: application/json

{
  "name": "OpenRouter Production",
  "setup_key": "openrouter-prod",
  "description": "OpenAI models via OpenRouter",
  "vendor": "openrouter",
  "api_endpoint": "https://openrouter.ai/api/v1/embeddings",
  "api_key": "sk-or-xxx...",
  "model_name": "openai/text-embedding-3-small",
  "embedding_dimensions": 1536,
  "is_default": false
}

Response 201:
{
  "id": 3,
  "name": "OpenRouter Production",
  "setup_key": "openrouter-prod",
  ...
}
```

```http
# Update a setup (e.g., rotate API key, migrate provider)
PUT /organizations/{org_external_id}/embeddings-setups/{setup_key}
Authorization: Bearer {kb_server_token}
Content-Type: application/json

{
  "api_key": "sk-new-key...",
  // Or for provider migration:
  "vendor": "openrouter",
  "api_endpoint": "https://openrouter.ai/api/v1/embeddings",
  "model_name": "openai/text-embedding-3-small"
}

Response 200:
{
  "id": 1,
  "message": "Setup updated successfully",
  "collections_affected": 42
}
```

```http
# Delete a setup
DELETE /organizations/{org_external_id}/embeddings-setups/{setup_key}
Authorization: Bearer {kb_server_token}

# If setup has collections using it:
Response 409:
{
  "error": "setup_in_use",
  "message": "Cannot delete setup with active collections",
  "collections_count": 42,
  "suggestion": "Migrate collections to another setup first or use force=true with replacement_setup_key"
}

# Force delete with migration:
DELETE /organizations/{org_external_id}/embeddings-setups/{setup_key}?force=true&replacement_setup_key=openai-prod
```

```http
# Get available setups for collection creation (user-facing)
GET /organizations/{org_external_id}/embeddings-setups/available
Authorization: Bearer {kb_server_token}

Response 200:
{
  "setups": [
    {
      "setup_key": "openai-prod",
      "name": "OpenAI Production",
      "description": "High-quality embeddings via OpenAI",
      "model_name": "text-embedding-3-small",
      "embedding_dimensions": 1536,
      "is_default": true
    },
    {
      "setup_key": "ollama-local",
      "name": "Ollama Local",
      "description": "Local embeddings, no external API calls",
      "model_name": "nomic-embed-text",
      "embedding_dimensions": 768,
      "is_default": false
    }
  ]
}
```

### 5.3 Modified Collection Endpoints

```http
# Create collection with setup reference
POST /collections
Authorization: Bearer {kb_server_token}
Content-Type: application/json

{
  "name": "Research Papers",
  "description": "Academic papers collection",
  "owner": "user_456",
  "organization_external_id": "org_123",
  "embeddings_setup_key": "openai-prod",  // Or omit to use default
  "visibility": "private"
}

Response 201:
{
  "id": 42,
  "name": "Research Papers",
  "organization_id": 1,
  "embeddings_setup": {
    "id": 1,
    "name": "OpenAI Production",
    "setup_key": "openai-prod",
    "model_name": "text-embedding-3-small",
    "embedding_dimensions": 1536
  },
  "embedding_dimensions": 1536
}
```

```http
# List collections with setup info
GET /collections?organization_external_id=org_123

Response 200:
{
  "items": [
    {
      "id": 42,
      "name": "Research Papers",
      "embeddings_setup": {
        "name": "OpenAI Production",
        "setup_key": "openai-prod"
      }
    }
  ]
}
```

### 5.4 Bulk Operations

```http
# Migrate collections from one setup to another
POST /organizations/{org_external_id}/migrate-collections
Authorization: Bearer {kb_server_token}
Content-Type: application/json

{
  "from_setup_key": "openai-dev",
  "to_setup_key": "openai-prod",
  "collection_ids": [1, 2, 3]  // Optional: specific collections, or all if omitted
}

Response 200:
{
  "migrated": 3,
  "skipped": 0,
  "errors": []
}
```

---

## 6. Validation Rules

### 6.1 Setup Updates

When updating a setup, the system validates:

| Field | Can Update? | Validation |
|-------|-------------|------------|
| `name` | Yes | Max 255 chars |
| `description` | Yes | - |
| `vendor` | Yes | Must be valid vendor |
| `api_endpoint` | Yes | Must be valid URL |
| `api_key` | Yes | - |
| `model_name` | Yes | - |
| `embedding_dimensions` | **No** | Immutable after creation |
| `is_default` | Yes | Only one default per org |
| `is_active` | Yes | - |

**Why `embedding_dimensions` is immutable:**
- Vector compatibility depends on dimensions
- Changing dimensions would make existing vectors unusable
- If you need different dimensions, create a new setup

### 6.2 Setup Deletion

A setup can only be deleted if:
1. No collections reference it, OR
2. Force delete is requested with a valid replacement setup of the same dimensions

### 6.3 Collection-Setup Compatibility

When migrating a collection to a different setup:
- Both setups must have the same `embedding_dimensions`
- If dimensions differ, migration is rejected

---

## 7. LAMB Integration

### 7.1 Organization Sync

When LAMB needs to interact with KB-Server for an organization:

```python
# In LAMB: Ensure organization exists in KB-Server
async def ensure_org_in_kb_server(organization: dict):
    response = await kb_client.post("/organizations", json={
        "external_id": str(organization['id']),  # or slug
        "name": organization['name']
    })
    return response.json()
```

### 7.2 Setup Management Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   LAMB UI   │────▶│ LAMB Backend│────▶│  KB-Server  │
│ (Org Admin) │     │   (Proxy)   │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │
      │ 1. List setups     │                   │
      │───────────────────▶│                   │
      │                    │ GET /organizations│
      │                    │  /{id}/emb-setups │
      │                    │──────────────────▶│
      │                    │◀──────────────────│
      │◀───────────────────│                   │
      │                    │                   │
      │ 2. Update API key  │                   │
      │───────────────────▶│                   │
      │                    │ PUT /organizations│
      │                    │ /{id}/emb-setups/x│
      │                    │──────────────────▶│
      │                    │◀──────────────────│
      │◀───────────────────│                   │
```

### 7.3 LAMB Endpoint Updates

**Note on naming:** 
- `{org_id}` in LAMB = organization ID or slug from LAMB database
- `{org_external_id}` in KB-Server = the same value, passed from LAMB

#### Organization Router (creator_interface/organization_router.py)

Prefix: `/creator/admin` (existing router)

```python
# List embeddings setups for org admin
# Full path: /creator/admin/organizations/{org_id}/embeddings-setups
@router.get("/organizations/{org_id}/embeddings-setups")
async def list_embeddings_setups(request: Request, org_id: str):
    # Verify user is admin of org_id
    # Proxy to KB-Server: GET /organizations/{org_id}/embeddings-setups
    pass

# Create embeddings setup
# Full path: /creator/admin/organizations/{org_id}/embeddings-setups
@router.post("/organizations/{org_id}/embeddings-setups")
async def create_embeddings_setup(request: Request, org_id: str, setup: EmbeddingsSetupCreate):
    # Verify user is admin of org_id
    # Proxy to KB-Server: POST /organizations/{org_id}/embeddings-setups
    pass

# Update embeddings setup (key rotation, provider migration)
# Full path: /creator/admin/organizations/{org_id}/embeddings-setups/{setup_key}
@router.put("/organizations/{org_id}/embeddings-setups/{setup_key}")
async def update_embeddings_setup(request: Request, org_id: str, setup_key: str, update: EmbeddingsSetupUpdate):
    # Verify user is admin of org_id
    # Proxy to KB-Server: PUT /organizations/{org_id}/embeddings-setups/{setup_key}
    pass

# Delete embeddings setup
# Full path: /creator/admin/organizations/{org_id}/embeddings-setups/{setup_key}
@router.delete("/organizations/{org_id}/embeddings-setups/{setup_key}")
async def delete_embeddings_setup(request: Request, org_id: str, setup_key: str):
    # Verify user is admin of org_id
    # Proxy to KB-Server: DELETE /organizations/{org_id}/embeddings-setups/{setup_key}
    pass
```

> **Note:** In the proxy implementation, LAMB's `org_id` is passed as KB-Server's `org_external_id`.

#### Knowledgebases Router (creator_interface/knowledges_router.py)

Prefix: `/creator/knowledgebases` (existing router)

```python
# Get available setups for collection creation (user-facing, not admin-only)
# Full path: /creator/knowledgebases/embeddings-setups/available
@router.get("/embeddings-setups/available")
async def get_available_embeddings_setups(request: Request):
    # Get user's organization from token
    creator_user = await authenticate_creator_user(request)
    org = get_user_organization(creator_user)
    org_id = str(org['id'])  # This becomes org_external_id for KB-Server
    
    # Proxy to KB-Server: GET /organizations/{org_external_id}/embeddings-setups/available
    pass
```

### 7.4 Endpoint Summary

| LAMB Endpoint (Full Path) | Method | Permission | KB-Server Endpoint |
|---------------------------|--------|------------|-------------------|
| `/creator/admin/organizations/{org_id}/embeddings-setups` | GET | Org Admin | `GET /organizations/{org_external_id}/embeddings-setups` |
| `/creator/admin/organizations/{org_id}/embeddings-setups` | POST | Org Admin | `POST /organizations/{org_external_id}/embeddings-setups` |
| `/creator/admin/organizations/{org_id}/embeddings-setups/{setup_key}` | PUT | Org Admin | `PUT /organizations/{org_external_id}/embeddings-setups/{setup_key}` |
| `/creator/admin/organizations/{org_id}/embeddings-setups/{setup_key}` | DELETE | Org Admin | `DELETE /organizations/{org_external_id}/embeddings-setups/{setup_key}` |
| `/creator/knowledgebases/embeddings-setups/available` | GET | Org Member | `GET /organizations/{org_external_id}/embeddings-setups/available` |
| `/creator/knowledgebases/create` | POST | Org Member | `POST /collections` (with setup_key) |

> **Note:** `{org_id}` (LAMB) and `{org_external_id}` (KB-Server) refer to the same value - the LAMB organization ID or slug.

### 7.5 Collection Creation Flow

**Location:** `creator_interface/kb_server_manager.py` → `KBServerManager.create_knowledge_base()`

```python
async def create_knowledge_base(self, kb_data, creator_user):
    # Get organization-specific KB config
    kb_config = self._get_kb_config_for_user(creator_user)
    kb_server_url = kb_config['url']
    kb_token = kb_config['token']
    
    # 1. Ensure org exists in KB-Server
    org = get_user_organization(creator_user)
    await self.ensure_org_in_kb_server(org)
    
    # 2. Get user's chosen setup (or default)
    # kb_data.embeddings_setup_key comes from frontend selection
    setup_key = kb_data.embeddings_setup_key or None  # None = use org default
    
    # 3. Create collection with setup reference
    collection_data = {
        "name": kb_data.name,
        "description": kb_data.description,
        "owner": str(creator_user['id']),
        "organization_external_id": str(org['id']),  # LAMB org ID/slug
        "embeddings_setup_key": setup_key,           # Reference to setup, not inline config
        "visibility": kb_data.access_control or "private"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{kb_server_url}/collections",
            json=collection_data,
            headers={"Authorization": f"Bearer {kb_token}"}
        )
        return response.json()
```

**Key Changes from Current Implementation:**
- Removed inline `embeddings_model` with API key
- Added `organization_external_id` parameter
- Added `embeddings_setup_key` parameter (references org's setup)

---

## 8. Migration Plan

### Phase 1: Database Schema (Week 1)

1. Create new tables: `organizations`, `embeddings_setups`
2. Add new columns to `collections`: `organization_id`, `embeddings_setup_id`, `embedding_dimensions`
3. Keep existing `embeddings_model` JSON column (backward compatibility)

### Phase 2: New Endpoints (Week 2)

1. Implement organization endpoints
2. Implement embeddings setup CRUD endpoints
3. Implement setup listing for users

### Phase 3: Collection Integration (Week 3)

1. Update collection creation to accept `embeddings_setup_key`
2. Update ingestion/query to resolve API key from setup
3. Support both old (inline config) and new (setup reference) modes

### Phase 4: Data Migration (Week 4)

```python
# Migration script logic:
def migrate_collections():
    # 1. Group collections by organization (via owner → LAMB user → org)
    # 2. For each org:
    #    a. Create organization record
    #    b. Extract unique embeddings configs from collections
    #    c. Create setup for each unique config
    #    d. Update collections to reference appropriate setup
    #    e. Nullify embeddings_model.apikey (keep rest for reference)
```

### Phase 5: LAMB Integration (Week 5)

1. Update LAMB to sync organizations to KB-Server
2. Add org admin UI for managing setups
3. Update KB creation flow to use setups

### Phase 6: Deprecation (Future)

1. Remove inline `embeddings_model.apikey` support
2. Require `organization_id` and `embeddings_setup_id` for new collections
3. Clean up legacy code paths

---

## 9. Security Considerations

### 9.1 API Key Storage

- API keys in `embeddings_setups` should be encrypted at rest
- Keys are never returned in API responses (only `api_key_configured: bool`)
- Key updates are logged for audit

### 9.2 Access Control

| Operation | Required Permission |
|-----------|---------------------|
| List setups | Org member |
| Create/Update/Delete setup | Org admin |
| Create collection with setup | Org member |
| View setup details (no key) | Org member |

### 9.3 Trust Model

- KB-Server trusts LAMB for organization membership
- KB-Server validates requests via bearer token
- LAMB handles user authentication and authorization

---

## 10. UI Considerations

### 10.1 Org Admin: Embeddings Setups Management

```
┌─────────────────────────────────────────────────────────────┐
│ Embeddings Setups                              [+ Add Setup] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ⭐ OpenAI Production (DEFAULT)                    [Edit] │ │
│ │    Model: text-embedding-3-small (1536 dims)            │ │
│ │    Vendor: openai                                       │ │
│ │    API Key: sk-proj-****...****uIbNA ✓ Configured      │ │
│ │    Collections using: 42                                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Ollama Local                                      [Edit] │ │
│ │    Model: nomic-embed-text (768 dims)                   │ │
│ │    Vendor: ollama                                       │ │
│ │    API Key: Not required                                │ │
│ │    Collections using: 5                                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 User: Collection Creation

```
┌─────────────────────────────────────────────────────────────┐
│ Create Knowledge Base                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Name: [Research Papers                              ]        │
│                                                              │
│ Description: [Academic papers for AI course         ]        │
│                                                              │
│ Embeddings Model:                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ○ OpenAI Production (recommended)                       │ │
│ │   text-embedding-3-small · 1536 dimensions              │ │
│ │                                                         │ │
│ │ ○ Ollama Local                                          │ │
│ │   nomic-embed-text · 768 dimensions                     │ │
│ │   ⚠️ Smaller model, faster but less accurate            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ℹ️ The embeddings model cannot be changed after creation.   │
│                                                              │
│                                    [Cancel]  [Create]        │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Common Scenarios

### Scenario 1: API Key Rotation

```
Admin Action: Update api_key in "OpenAI Production" setup
Effect: All 42 collections using this setup immediately use the new key
No collection-level updates needed!
```

### Scenario 2: Provider Migration (OpenAI → OpenRouter)

```
Admin Action: Update setup with:
  - vendor: "openrouter"
  - api_endpoint: "https://openrouter.ai/api/v1/embeddings"
  - model_name: "openai/text-embedding-3-small"
  - api_key: "sk-or-new-key..."

Effect: All collections using this setup now go through OpenRouter
Vectors remain compatible (same underlying model, same dimensions)
```

### Scenario 3: Adding a New Provider Option

```
Admin Action: Create new setup "Azure OpenAI"
  - vendor: "azure"
  - api_endpoint: "https://mycompany.openai.azure.com/..."
  - model_name: "text-embedding-3-small"
  - embedding_dimensions: 1536

Effect: Users can now choose this option when creating new collections
Existing collections unaffected
```

### Scenario 4: Deprecating an Old Setup

```
Admin Action:
1. Set is_active=false on "Old Setup"
2. New collections can no longer use it
3. Existing collections continue working
4. Optionally migrate collections to new setup
5. Delete old setup when no collections use it
```

---

## 12. Open Questions

1. **Dimension Validation**: Should we test-embed a sample text when creating a setup to verify dimensions? Or trust the admin?

2. **Cross-Org Setups**: Should there be system-wide setups that all orgs can use (like "System Default")?

3. **Setup Templates**: Should we provide pre-configured setup templates for common providers?

4. **Audit Logging**: What level of audit logging for setup changes? (Changes are security-sensitive)

5. **Rate Limiting**: Should setups include rate limit configuration for the API?

---

## 13. Success Metrics

After implementation:

- [ ] API key rotation takes < 1 minute (vs current: update every collection)
- [ ] New organizations can be onboarded with standard setups
- [ ] Users can choose from multiple embeddings options
- [ ] Provider migration possible without recreating collections
- [ ] Zero API key exposure in collection-level API responses

---

## 14. Appendix: Example Setups

### OpenAI Direct

```json
{
  "name": "OpenAI Production",
  "setup_key": "openai-prod",
  "vendor": "openai",
  "api_endpoint": "https://api.openai.com/v1/embeddings",
  "model_name": "text-embedding-3-small",
  "embedding_dimensions": 1536
}
```

### OpenRouter (OpenAI model)

```json
{
  "name": "OpenRouter - OpenAI",
  "setup_key": "openrouter-openai",
  "vendor": "openrouter",
  "api_endpoint": "https://openrouter.ai/api/v1/embeddings",
  "model_name": "openai/text-embedding-3-small",
  "embedding_dimensions": 1536
}
```

### Ollama Local

```json
{
  "name": "Ollama Local",
  "setup_key": "ollama-local",
  "vendor": "ollama",
  "api_endpoint": "http://localhost:11434/api/embeddings",
  "model_name": "nomic-embed-text",
  "embedding_dimensions": 768
}
```

### Azure OpenAI

```json
{
  "name": "Azure OpenAI",
  "setup_key": "azure-openai",
  "vendor": "azure",
  "api_endpoint": "https://mycompany.openai.azure.com/openai/deployments/embedding/embeddings?api-version=2024-02-15-preview",
  "model_name": "text-embedding-3-small",
  "embedding_dimensions": 1536
}
```

---

**Document Status:** Draft for Review  
**Next Steps:** Review with team, address open questions, finalize design
