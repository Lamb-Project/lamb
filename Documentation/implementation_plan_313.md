# Profiles System for LAMB — Full Implementation Plan

**Issue:** #313
**Version:** 1.0
**Date:** March 21, 2026
**Status:** Design Proposal

---

## Table of Contents

1. [Context & Motivation](#1-context--motivation)
2. [Prerequisites & Assumptions](#2-prerequisites--assumptions)
3. [Profile Categories](#3-profile-categories)
4. [Architecture Decision: Where Profiles Live](#4-architecture-decision-where-profiles-live)
5. [Data Model](#5-data-model)
6. [Profile Resolution (Completion Pipeline)](#6-profile-resolution-completion-pipeline)
7. [API Design](#7-api-design)
8. [Frontend Design](#8-frontend-design)
9. [Backwards Compatibility & Migration](#9-backwards-compatibility--migration)
10. [Profile Limits](#10-profile-limits)
11. [Implementation Phases](#11-implementation-phases)
12. [Critical Files Reference](#12-critical-files-reference)
13. [Verification & Testing](#13-verification--testing)

---

## 1. Context & Motivation

### The Problem

LAMB's plugin architecture offers multiple independent configuration dimensions — RAG processor, chunking strategy, LLM connector, prompt template — but currently **all settings are stored inline** in each assistant's `metadata` JSON field (the `api_callback` column in the database).

Current assistant metadata example:
```json
{
  "prompt_processor": "simple_augment",
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "rag_processor": "simple_rag",
  "file_path": "",
  "capabilities": { "vision": false, "image_generation": false }
}
```

This inline approach causes several problems:

| Problem | Impact |
|---------|--------|
| **No reusability** | Identical configurations are duplicated across assistants. An org with 30 assistants using the same RAG+LLM combo has 30 copies of the same config. |
| **No centralized management** | Changing a setting (e.g., upgrading all assistants from `gpt-4o-mini` to `gpt-4o`) requires editing each assistant individually. |
| **No org-wide consistency** | Admins cannot enforce or recommend standard configurations for their department. |
| **Cognitive overload** | Educators face a complex form with many technical knobs (RAG processor, top_k, connector, model, prompt processor, capabilities) and no guidance about which combinations work well. |
| **No quality comparison** | Different plugin combinations produce different quality results, but there's no way to name, save, and compare these combinations. |

### The Solution

Introduce a **Profiles system** — first-class, reusable, org-scoped configuration entities across 4 independent categories. Users mix and match one profile from each category when building assistants or knowledge bases.

**Example:** A teacher selects:
- Retrieval Profile: "Context-Aware, Top 5"
- LLM Profile: "GPT-4o Creative"
- Prompt Profile: "Socratic Tutor"
- (KB was already created with) Chunking Profile: "Hierarchical Large Parents"

Each profile is a named, saved, shareable configuration that can be reused across multiple assistants or KBs.

---

## 2. Prerequisites & Assumptions

This plan assumes **issue #235 (KB-Server Plugin Architecture v2.1)** is implemented before this work begins. Key assumptions from #235:

| #235 Feature | Impact on Profiles |
|--------------|-------------------|
| **Three-stage pipeline** (PARTITION → CHUNK → STORE) | Chunking is a clean, independent stage that maps perfectly to a profile. |
| **Ingestion strategy locked per KB** at creation time | Chunking Profile is selected at KB creation. The strategy field is immutable after that. |
| **Strategy params can change** (only affect future ingestions) | A KB's chunking profile can be updated — new files use new params, old files keep their original chunks. |
| **Query plugins auto-paired** with ingestion strategies | No need for a separate "query plugin selection" profile. `simple_ingest` → `simple_query`, `hierarchical_ingest` → `parent_child_query` automatically. |
| **`KnowledgeStoreSetup`** handles storage backend selection | Database plugin selection (ChromaDB, etc.) is already its own first-class entity from #229. Not part of the profiles system. |
| **`FileRegistry`** tracks `plugin_name` and `plugin_params` per ingestion job | Full traceability of which params were used for each file, even when profiles change. |

---

## 3. Profile Categories

The profiles system has **4 independent categories**:

| Category | ID | Scope | Where Configured | What It Controls |
|----------|----|-------|------------------|------------------|
| **Retrieval** | `retrieval` | Per-assistant | Assistant form | Which RAG processor runs, how many results to retrieve, similarity threshold |
| **Chunking** | `chunking` | Per-KB | KB creation + later updates | Ingestion strategy (locked at creation), chunk sizes, overlap, splitter type |
| **LLM** | `llm` | Per-assistant | Assistant form | Which connector (OpenAI, Ollama, etc.), which model, vision/image capabilities |
| **Prompt** | `prompt` | Per-assistant | Assistant form | System prompt, prompt template, prompt processor (extends existing `PromptTemplate`) |

### Why These 4 Categories?

Each category maps to an **independent dimension** of the completion pipeline:

```
User Message
    ↓
[1] RETRIEVAL PROFILE → Which RAG processor? How many results? What threshold?
    ↓
[2] CHUNKING PROFILE → (already applied at ingestion time — determines chunk structure in KB)
    ↓
[3] PROMPT PROFILE → How to format the system prompt? How to inject RAG context?
    ↓
[4] LLM PROFILE → Which provider? Which model? What capabilities?
    ↓
Response
```

### Why Not More Categories?

**Knowledge Graph / Query Enhancement**: Issue #165 proposed a semantic graph layer for the KB server, which would introduce query-time parameters like `use_graph`, `expansion_depth`, `graph_weight`. Whether #165 will be implemented is uncertain. If it is implemented in the future, a 5th "Query Enhancement" profile category can be added at that time as an independent profile controlling KB-server-side query behavior. The current 4-category design does not preclude this — the `profiles` table uses a `category` discriminator that can be extended with a new value.

**Database / Storage Backend**: Already handled by `KnowledgeStoreSetup` (from issues #203 and #229). Not duplicated in the profiles system.

### Category Details

#### A. Retrieval Profile

Controls LAMB-side RAG behavior during the completion pipeline.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rag_processor` | string | `"no_rag"` | Which RAG plugin to use: `no_rag`, `simple_rag`, `context_aware_rag`, `hierarchical_rag`, `rubric_rag`, `single_file_rag` |
| `RAG_Top_k` | integer (1-10) | `3` | Number of top results to retrieve from KB |
| `threshold` | float (0.0-1.0) | `0.0` | Minimum similarity score to include a result |

**Current hardcoded values that this profile replaces:**
- `simple_rag.py` line 155: `"threshold": 0.0` (hardcoded)
- `context_aware_rag.py`: similar hardcoded threshold
- `assistant.RAG_Top_k`: stored on assistant object, would come from profile instead

**RAG-processor-specific parameters:** Some RAG processors have unique requirements (e.g., `rubric_rag` needs `rubric_id` and `rubric_format`; `single_file_rag` needs `file_path`). These remain on the assistant's inline metadata since they're assistant-specific, not profile-worthy.

#### B. Chunking Profile

Controls how documents are split during ingestion on the KB server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ingestion_strategy` | string | `"simple_ingest"` | Which ingestion strategy plugin. **Locked at KB creation.** |
| `strategy_params` | JSON object | varies | Strategy-specific parameters (see below) |

**Parameters for `simple_ingest`:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `chunk_size` | integer | `1000` | 100-10000 | Target chunk size in characters |
| `chunk_overlap` | integer | `200` | 0-500 | Overlap between consecutive chunks |
| `splitter_type` | string | `"recursive"` | `"recursive"`, `"character"`, `"token"` | Text splitting algorithm |

**Parameters for `hierarchical_ingest`:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `parent_chunk_size` | integer | `2000` | 500-10000 | Size of parent (context) chunks |
| `child_chunk_size` | integer | `400` | 100-2000 | Size of child (search) chunks |
| `child_chunk_overlap` | integer | `50` | 0-500 | Overlap between child chunks |
| `split_by_headers` | boolean | `true` | - | Split by Markdown headers |

**Behavior when updating a KB's chunking profile:**
- The `ingestion_strategy` field CANNOT change (locked at creation, per #235).
- The `strategy_params` CAN change. New file ingestions use the new params.
- Previously ingested files keep their original chunks untouched.
- `FileRegistry` records the actual `plugin_params` used per ingestion job, providing full traceability.

**Technical validation:** Analysis of the KB server confirmed that mixed chunk params within a collection work correctly:
- ChromaDB similarity scoring uses cosine distance, which is agnostic to chunk size.
- `parent_child_query` gracefully handles chunks with or without `parent_text` metadata (checks `"parent_text" in metadata` before using it).
- `simple_query` is completely agnostic to chunk structure.
- No re-ranking algorithms assume uniform chunk sizes.

#### C. LLM Profile

Controls LLM provider and model selection.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connector` | string | `"openai"` | Which connector plugin: `openai`, `ollama`, `bypass`, `banana_img` |
| `llm` | string | `"gpt-4o-mini"` | Which model to use (validated against connector's available models) |
| `capabilities.vision` | boolean | `false` | Enable vision/image input |
| `capabilities.image_generation` | boolean | `false` | Enable image generation output |

#### D. Prompt Profile

Extends the existing `PromptTemplate` system — no new table needed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system_prompt` | string | `""` | System instruction for the assistant |
| `prompt_template` | string | `""` | Template with `{context}` and `{user_input}` placeholders |
| `prompt_processor` | string | `"simple_augment"` | Which prompt processor plugin to use |

The existing `PromptTemplate` model (`backend/lamb/lamb_classes.py` lines 107-126) already has `system_prompt`, `prompt_template`, and a `metadata` JSON field. The `prompt_processor` value will be stored in the `metadata` field. The existing `prompt_templates` table, CRUD methods, and router are reused directly.

---

## 4. Architecture Decision: Where Profiles Live

### The Question

Chunking profiles control KB-server-side behavior (ingestion). Should they be stored in the KB server's database (requiring a "proxy" pattern) or in LAMB's database?

### Option A: KB Server Storage + LAMB Proxy (REJECTED)

```
Frontend                    LAMB Backend                    KB Server
   │                            │                               │
   │ GET /creator/kb-profiles   │                               │
   │   /chunking                │                               │
   │───────────────────────────►│                               │
   │                            │ GET /organizations/{org}/     │
   │                            │   chunking-profiles           │
   │                            │──────────────────────────────►│
   │                            │◄──────────────────────────────│
   │◄───────────────────────────│                               │
```

**How it works:**
- A new `chunking_profiles` table is added to the KB server's database (`lamb-kb-server.db`).
- New CRUD endpoints are added to the KB server (`/organizations/{org_id}/chunking-profiles`).
- New "proxy" endpoints are added to the LAMB backend (`/creator/kb-profiles/chunking`) that receive the frontend request, authenticate the user, resolve their org, then forward the request to the KB server via `KBServerManager`.
- The response from the KB server is forwarded back to the frontend.

**Pros:**
- KB server "owns" all chunking-related data (conceptual separation of concerns).
- If KB server were used standalone without LAMB, profiles would be available.

**Cons:**
- **Double the work**: new table + routes in KB server, AND proxy routes in LAMB backend. Every CRUD operation requires code in both repos.
- **Two HTTP calls per operation**: Frontend → LAMB → KB server. Double the latency, double the failure points.
- **Complex error handling**: LAMB must translate KB server errors into user-friendly responses. Network issues between LAMB and KB server cause profile management failures.
- **Code duplication**: Pydantic models must exist in both LAMB and KB server schemas.
- **Profile management fails if KB server is offline**: Can't even list or edit profiles without the KB server running.
- **Unnecessary**: The KB server already accepts `plugin_name` and `plugin_params` as parameters in its ingestion API. It doesn't need to know about "profiles" — that's a user-facing abstraction.

### Option B: LAMB-Only Storage (CHOSEN)

```
Frontend                    LAMB Backend                    KB Server
   │                            │                               │
   │ GET /creator/profiles      │                               │
   │   ?category=chunking       │                               │
   │───────────────────────────►│                               │
   │                            │ (reads from LAMB's own DB)    │
   │◄───────────────────────────│                               │
   │                            │                               │
   │ POST /creator/kb/          │                               │
   │   {id}/ingest-file         │                               │
   │───────────────────────────►│                               │
   │                            │ 1. Resolve chunking profile   │
   │                            │ 2. Extract plugin_name +      │
   │                            │    plugin_params from profile  │
   │                            │ 3. POST /collections/{id}/    │
   │                            │    ingest-file                │
   │                            │    body: { plugin_name,       │
   │                            │            plugin_params }    │
   │                            │──────────────────────────────►│
   │                            │◄──────────────────────────────│
   │◄───────────────────────────│                               │
```

**How it works:**
- ALL profiles (including chunking) are stored in LAMB's `profiles` table with `category='chunking'`.
- When creating a KB, the LAMB backend resolves the chunking profile and passes `ingestion_strategy` to the KB server's collection creation endpoint.
- When ingesting a file, the LAMB backend resolves the KB's current chunking profile and passes `plugin_name` + `plugin_params` to the KB server's ingestion endpoint.
- **The KB server doesn't know about profiles at all.** It receives `plugin_name` and `plugin_params` exactly as it does today. Zero KB server code changes for profile support.

**Pros:**
- **Much simpler**: Single database, single API layer, single set of Pydantic models.
- **No KB server changes**: The KB server already accepts `plugin_name` and `plugin_params` in its ingestion API.
- **Profile management works offline**: Can create, list, edit profiles even if KB server is temporarily down.
- **Consistent**: All 4 profile categories use the same storage mechanism, same API pattern, same frontend components.
- **Less code**: Estimated ~8 files instead of ~15. No proxy router, no KB server router, no KB server schemas, no KB server models.
- **Faster**: No intermediate HTTP call for profile CRUD.

**Cons:**
- If KB server is used standalone (without LAMB), no profile support. But this isn't a real use case — LAMB IS the user-facing layer.
- LAMB must validate that profile params match the KB's locked strategy. This is straightforward validation logic.

### Why Option B is Clearly Superior

The key insight is that **"profiles" are a user-facing abstraction**. The KB server doesn't need to understand profiles — it just needs to receive `plugin_name` and `plugin_params` when ingesting files, which it already does. Adding profile tables and CRUD to the KB server would be adding user-facing features to what should be a backend service. The existing `KBServerManager` already handles the translation between user-facing concepts and KB server API calls.

This is consistent with how the rest of LAMB works: the LAMB backend stores user-facing concepts (assistants, organizations, sharing, templates) and translates them into KB server API calls when needed.

---

## 5. Data Model

### 5.1 Unified Profiles Table (LAMB Backend)

A single `profiles` table with a `category` discriminator stores Retrieval, Chunking, and LLM profiles. Prompt profiles reuse the existing `prompt_templates` table.

```sql
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    owner_email TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('retrieval', 'llm', 'chunking')),
    name TEXT NOT NULL,
    description TEXT,
    is_shared BOOLEAN DEFAULT FALSE,
    config JSON NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE(organization_id, owner_email, category, name)
);

CREATE INDEX idx_profiles_org_cat ON profiles(organization_id, category);
CREATE INDEX idx_profiles_shared ON profiles(organization_id, category, is_shared);
```

### 5.2 Config JSON Schemas

**Retrieval Profile (`category='retrieval'`):**
```json
{
  "rag_processor": "context_aware_rag",
  "RAG_Top_k": 5,
  "threshold": 0.1
}
```

**Chunking Profile (`category='chunking'`):**
```json
{
  "ingestion_strategy": "simple_ingest",
  "strategy_params": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "splitter_type": "recursive"
  }
}
```

```json
{
  "ingestion_strategy": "hierarchical_ingest",
  "strategy_params": {
    "parent_chunk_size": 2000,
    "child_chunk_size": 400,
    "child_chunk_overlap": 50,
    "split_by_headers": true
  }
}
```

**LLM Profile (`category='llm'`):**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "capabilities": {
    "vision": false,
    "image_generation": false
  }
}
```

### 5.3 Assistant Table Changes

Add nullable profile reference columns:

```sql
ALTER TABLE assistants ADD COLUMN retrieval_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE assistants ADD COLUMN llm_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE assistants ADD COLUMN prompt_template_id INTEGER REFERENCES prompt_templates(id) ON DELETE SET NULL;
```

When a `profile_id` is set, it takes precedence over inline metadata values. When all profile columns are NULL, the assistant uses its inline `metadata` JSON exactly as today — **zero behavior change for existing assistants**.

### 5.4 KB-Assistant Chunking Profile Link

Knowledge bases (collections) need to reference their chunking profile. Since KBs are stored in the KB server's database but we chose to store profiles in LAMB's database, we store this link in LAMB:

```sql
CREATE TABLE kb_chunking_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id TEXT NOT NULL UNIQUE,
    chunking_profile_id INTEGER NOT NULL,
    ingestion_strategy TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (chunking_profile_id) REFERENCES profiles(id) ON DELETE SET NULL
);
```

The `ingestion_strategy` column is stored redundantly (it's also in the profile) so that when a KB's profile is updated, we can validate the new profile has the same strategy (since strategy is locked per KB). This also serves as the source of truth for the locked strategy even if the profile is deleted.

### 5.5 Organization Default Profiles

```sql
CREATE TABLE profile_defaults (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('retrieval', 'llm', 'chunking', 'prompt')),
    profile_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE(organization_id, category)
);
```

Admins can set a default profile per category for their org. New assistants/KBs pre-select this default in the form.

### 5.6 Pydantic Models

In `backend/lamb/lamb_classes.py`:

```python
class Profile(BaseModel):
    id: int = Field(default=0)
    organization_id: int
    owner_email: str
    category: str  # 'retrieval', 'llm', 'chunking'
    name: str
    description: Optional[str] = None
    is_shared: bool = False
    config: Dict[str, Any]
    created_at: int
    updated_at: int
```

---

## 6. Profile Resolution (Completion Pipeline)

When a completion request arrives, the pipeline resolves configuration through a priority cascade:

```
1. Assistant's profile reference (retrieval_profile_id, llm_profile_id, etc.)
   ↓ (if NULL)
2. Organization default profile for that category
   ↓ (if NULL)
3. Assistant's inline metadata (existing behavior, backwards-compatible)
   ↓ (if empty/missing keys)
4. System defaults (hardcoded: no_rag, openai, gpt-4, simple_augment)
```

### Implementation

New function in `backend/lamb/completions/main.py`:

```python
def resolve_assistant_config(assistant_details) -> Dict[str, str]:
    """
    Resolve the full plugin configuration for an assistant.

    Priority cascade:
    1. Profile references (retrieval_profile_id, llm_profile_id)
    2. Organization default profiles
    3. Inline metadata (existing behavior)
    4. System defaults
    """
    # Start with inline config (existing parse_plugin_config behavior)
    config = parse_plugin_config(assistant_details)

    # Override with profile values if profile references exist
    if assistant_details.retrieval_profile_id:
        profile = db_manager.get_profile_by_id(assistant_details.retrieval_profile_id)
        if profile:
            config["rag_processor"] = profile.config.get("rag_processor", config["rag_processor"])
            # RAG_Top_k is on the assistant object, override from profile
            assistant_details.RAG_Top_k = profile.config.get("RAG_Top_k", assistant_details.RAG_Top_k)
            # threshold stored for RAG processors to read
            config["threshold"] = profile.config.get("threshold", 0.0)

    if assistant_details.llm_profile_id:
        profile = db_manager.get_profile_by_id(assistant_details.llm_profile_id)
        if profile:
            config["connector"] = profile.config.get("connector", config["connector"])
            config["llm"] = profile.config.get("llm", config["llm"])
            # capabilities handling
            if "capabilities" in profile.config:
                config["capabilities"] = profile.config["capabilities"]

    # Prompt profile: already handled via prompt_template_id → PromptTemplate

    return config
```

This function wraps the existing `parse_plugin_config()` (line 198 of `main.py`). The existing function continues to work unchanged for assistants with no profile references, ensuring perfect backwards compatibility.

### How RAG Processors Use Profile Values

Currently, `threshold` is hardcoded to `0.0` in RAG processors. With profiles:

**`simple_rag.py` (line 152-157) — before:**
```python
payload = {
    "query_text": last_user_message,
    "top_k": top_k,
    "threshold": 0.0,
    "plugin_params": {}
}
```

**After:**
```python
payload = {
    "query_text": last_user_message,
    "top_k": top_k,
    "threshold": request.get("__profile_threshold", 0.0),
    "plugin_params": {}
}
```

The `resolve_assistant_config()` function injects `__profile_threshold` into the request dict before passing it to the RAG processor.

### How Chunking Profiles Are Resolved at Ingestion Time

When a file is uploaded to a KB:

1. LAMB backend receives the upload request.
2. Looks up the KB's `chunking_profile_id` from `kb_chunking_profiles` table.
3. Loads the profile's `config` JSON.
4. Passes `config.ingestion_strategy` as `plugin_name` and `config.strategy_params` as `plugin_params` to the KB server's `/collections/{id}/ingest-file` endpoint.
5. KB server ingests normally — it doesn't know a profile was involved.

This is handled in `KBServerManager.upload_file_to_kb()` (`backend/creator_interface/kb_server_manager.py`).

---

## 7. API Design

### 7.1 Profile CRUD (`backend/creator_interface/profiles_router.py`)

Following the exact pattern of `prompt_templates_router.py`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/creator/profiles?category={cat}` | List user's own + shared profiles for a category |
| `GET` | `/creator/profiles/{id}` | Get profile by ID (includes `usage_count`: how many assistants/KBs reference it) |
| `POST` | `/creator/profiles` | Create a new profile |
| `PUT` | `/creator/profiles/{id}` | Update profile. Response includes `affected_count` (number of assistants/KBs that will be affected). |
| `DELETE` | `/creator/profiles/{id}` | Delete profile. Returns 409 if assistants/KBs still reference it, with list of affected entities. User must reassign them first or confirm forced deletion (sets references to NULL). |
| `POST` | `/creator/profiles/{id}/duplicate` | Duplicate profile with a new name |
| `PUT` | `/creator/profiles/{id}/share` | Toggle `is_shared` flag |
| `GET` | `/creator/profiles/defaults` | Get org default profile IDs for all categories |
| `PUT` | `/creator/profiles/defaults` | Set org default profile for a category (admin/owner only) |

### 7.2 Request/Response Models

```python
class ProfileCreate(BaseModel):
    category: str = Field(..., pattern="^(retrieval|llm|chunking)$")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_shared: bool = Field(default=False)
    config: Dict[str, Any]

class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_shared: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

class ProfileResponse(BaseModel):
    id: int
    organization_id: int
    owner_email: str
    category: str
    name: str
    description: Optional[str]
    is_shared: bool
    config: Dict[str, Any]
    usage_count: int  # Number of assistants/KBs referencing this profile
    created_at: int
    updated_at: int

class ProfileUpdateResponse(ProfileResponse):
    affected_assistants: List[Dict[str, Any]]  # [{id, name}, ...] of affected assistants
    affected_kbs: List[Dict[str, Any]]  # [{id, name}, ...] of affected KBs

class ProfileDeleteResponse(BaseModel):
    success: bool
    message: str
    affected_assistants: List[Dict[str, Any]]
    affected_kbs: List[Dict[str, Any]]
```

### 7.3 Config Validation

The API validates the `config` JSON based on the `category`:

- **Retrieval**: `rag_processor` must be in the list of available RAG processors. `RAG_Top_k` must be 1-10. `threshold` must be 0.0-1.0.
- **Chunking**: `ingestion_strategy` must be a valid strategy plugin name. `strategy_params` must match the strategy's parameter schema (obtained from the plugin's `get_parameters()` method, fetched from KB server at `/ingestion/plugins`).
- **LLM**: `connector` must be available. `llm` must be a valid model for the connector. Capabilities must be supported by the connector/model.

### 7.4 Modified Assistant Endpoints

**`POST /creator/assistant/create_assistant`** — enhanced request body:
```json
{
  "name": "My Tutor",
  "description": "...",
  "retrieval_profile_id": 5,
  "llm_profile_id": 3,
  "prompt_template_id": 12,
  "RAG_collections": "kb-uuid-1,kb-uuid-2",
  "system_prompt": "...",
  "prompt_template": "...",
  "metadata": "{...}"
}
```

If profile IDs are provided, they take precedence. If not provided (null), the assistant uses inline metadata as today.

**`GET /creator/assistant/{id}`** — enhanced response:
```json
{
  "id": 42,
  "name": "My Tutor",
  "retrieval_profile_id": 5,
  "retrieval_profile": { "id": 5, "name": "Context-Aware, Top 5", "config": {...} },
  "llm_profile_id": 3,
  "llm_profile": { "id": 3, "name": "GPT-4o Creative", "config": {...} },
  "prompt_template_id": 12,
  "prompt_template_profile": { "id": 12, "name": "Socratic Tutor", ... },
  "metadata": "{...}",
  "..."
}
```

### 7.5 Modified KB Creation Endpoint

**`POST /creator/knowledge-base/create`** — enhanced request body adds `chunking_profile_id`:
```json
{
  "name": "Course Materials",
  "description": "...",
  "chunking_profile_id": 7
}
```

LAMB resolves the profile, passes `ingestion_strategy` to the KB server.

### 7.6 Fetching Available Plugin Capabilities

The frontend needs to know which plugins exist and what parameters they accept, to populate the profile creation form dynamically.

**`GET /creator/profiles/capabilities`** — returns:
```json
{
  "retrieval": {
    "rag_processors": ["no_rag", "simple_rag", "context_aware_rag", "hierarchical_rag", "rubric_rag", "single_file_rag"],
    "parameters": {
      "RAG_Top_k": { "type": "integer", "min": 1, "max": 10, "default": 3 },
      "threshold": { "type": "number", "min": 0.0, "max": 1.0, "default": 0.0 }
    }
  },
  "chunking": {
    "strategies": {
      "simple_ingest": {
        "description": "Fixed-size chunking with overlap",
        "parameters": {
          "chunk_size": { "type": "integer", "default": 1000, "min": 100, "max": 10000 },
          "chunk_overlap": { "type": "integer", "default": 200, "min": 0, "max": 500 },
          "splitter_type": { "type": "string", "default": "recursive", "enum": ["recursive", "character", "token"] }
        }
      },
      "hierarchical_ingest": {
        "description": "Parent-child chunking for structure-aware queries",
        "parameters": {
          "parent_chunk_size": { "type": "integer", "default": 2000, "min": 500, "max": 10000 },
          "child_chunk_size": { "type": "integer", "default": 400, "min": 100, "max": 2000 },
          "child_chunk_overlap": { "type": "integer", "default": 50, "min": 0, "max": 500 },
          "split_by_headers": { "type": "boolean", "default": true }
        }
      }
    }
  },
  "llm": {
    "connectors": {
      "openai": { "models": ["gpt-4o", "gpt-4o-mini", "gpt-4"], "capabilities": ["vision_input"] },
      "ollama": { "models": ["llama3.1", "mistral"], "capabilities": [] },
      "banana_img": { "models": ["gemini-2.0-flash-exp"], "capabilities": ["image_generation"] }
    }
  }
}
```

This endpoint aggregates data from:
- `load_plugins('rag')` for retrieval processors
- KB server's `/ingestion/plugins` for chunking strategies (proxied via existing `KBServerManager`)
- `load_plugins('connectors')` + org config for LLM capabilities

---

## 8. Frontend Design

### 8.1 Profile Management Section

New route at `/profiles` accessible from the main navigation. Tabbed interface with one tab per active category.

```
┌──────────────────────────────────────────────────────────────────┐
│  PROFILES                                                         │
│                                                                    │
│  [Retrieval] [Chunking] [LLM]                                    │
│  ═══════════                                                       │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ MY PROFILES                                          [+ New] │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │ Context-Aware, Top 5                    [Edit] [⋮]  │   │   │
│  │  │ RAG: context_aware_rag | Top K: 5 | Threshold: 0.1  │   │   │
│  │  │ Used by: 3 assistants                    🔒 Shared   │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │ Simple RAG, Default                     [Edit] [⋮]  │   │   │
│  │  │ RAG: simple_rag | Top K: 3 | Threshold: 0.0         │   │   │
│  │  │ Used by: 7 assistants                    🔓 Private  │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  │ SHARED WITH ME                                               │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │ Org Default (by admin@upc.edu)          [Duplicate]  │   │   │
│  │  │ RAG: context_aware_rag | Top K: 3 | Threshold: 0.05 │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

Each profile card always shows the full configuration values — never just a name.

### 8.2 ProfileSelector Component

Reusable dropdown component used in AssistantForm and KB creation. Shows profile name AND preview of its configuration.

```
┌─────────────────────────────────────────────────────────┐
│ Retrieval Profile: [▼ Context-Aware, Top 5            ] │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ● Context-Aware, Top 5                              │ │
│ │   RAG: context_aware_rag | Top K: 5 | Thr: 0.1     │ │
│ │ ○ Simple RAG, Default                               │ │
│ │   RAG: simple_rag | Top K: 3 | Thr: 0.0            │ │
│ │ ○ No RAG                                            │ │
│ │   RAG: no_rag                                       │ │
│ │ ───────────────────────────────────────────────────  │ │
│ │ + Create Custom Profile                             │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

Key behaviors:
1. **Preview**: Every option shows its full configuration inline. No "Profile X" without context.
2. **Custom creation**: "Create Custom Profile" opens a modal/inline form where the user sets all parameters freely and saves a new named profile.
3. **Org default indicator**: If the org has a default profile for this category, it's marked with a badge.

### 8.3 Cascading Change Warning

When a user edits a shared profile (or any profile used by multiple assistants/KBs), before saving:

```
┌──────────────────────────────────────────────────────────┐
│  ⚠ WARNING: This profile is used by other assistants     │
│                                                           │
│  Changing "Context-Aware, Top 5" will affect:             │
│                                                           │
│  • My Tutor Assistant                                     │
│  • Course Q&A Bot                                         │
│  • Lab Helper                                             │
│                                                           │
│  All 3 assistants will use the updated configuration      │
│  immediately.                                             │
│                                                           │
│  [Cancel]                    [Update Profile for All]     │
└──────────────────────────────────────────────────────────┘
```

The list of affected assistants comes from the `PUT /creator/profiles/{id}` response's `affected_assistants` field.

### 8.4 AssistantForm Integration

In `AssistantForm.svelte`, the current inline dropdowns are augmented with ProfileSelector components:

```
┌──────────────────────────────────────────────────────────┐
│ ASSISTANT CONFIGURATION                                    │
│                                                            │
│ Name: [My Tutor Assistant                               ]  │
│ Description: [A helpful tutor for ML course             ]  │
│                                                            │
│ ── Retrieval ────────────────────────────────────────────  │
│ [ProfileSelector: Retrieval]                               │
│ Knowledge Bases: [☑ ML Papers  ☑ Lecture Notes  ☐ FAQ]    │
│                                                            │
│ ── Language Model ───────────────────────────────────────  │
│ [ProfileSelector: LLM]                                     │
│                                                            │
│ ── Prompt ───────────────────────────────────────────────  │
│ [ProfileSelector: Prompt (uses existing Templates)]        │
│ System Prompt: [editable textarea, pre-filled from profile]│
│ Prompt Template: [editable textarea, pre-filled]           │
│                                                            │
│                              [Cancel]  [Save Assistant]    │
└──────────────────────────────────────────────────────────┘
```

**Interaction with existing Advanced Mode**: The current "Advanced Mode" toggle in create mode shows `prompt_processor` and `connector` dropdowns. With profiles, these are absorbed into LLM and Prompt profiles. Advanced mode could show the raw profile config for power users, but most users just pick a profile.

**Prompt Profile specifics**: When a prompt profile is selected, its `system_prompt` and `prompt_template` fill the text areas. The user can edit them — edits are stored on the assistant, overriding the profile values. A visual indicator (e.g., "Modified from profile") shows when the user has customized the values.

### 8.5 KB Creation Integration

```
┌──────────────────────────────────────────────────────────┐
│ CREATE KNOWLEDGE BASE                                      │
│                                                            │
│ Name: [Course Materials                                 ]  │
│ Description: [ML course lecture materials               ]  │
│                                                            │
│ ── Chunking Strategy ────────────────────────────────────  │
│ [ProfileSelector: Chunking]                                │
│ Preview:                                                   │
│   Strategy: simple_ingest (locked after creation)          │
│   Chunk size: 1000 chars                                   │
│   Overlap: 200 chars                                       │
│   Splitter: recursive                                      │
│                                                            │
│ ── Storage Backend ──────────────────────────────────────  │
│ [KnowledgeStoreSetup selector (existing from #229)]        │
│                                                            │
│                               [Cancel]  [Create KB]        │
└──────────────────────────────────────────────────────────┘
```

After creation, the strategy is locked. If the user navigates to KB settings, they can change the chunking profile to another profile **with the same strategy** (or update params), but the strategy selector is read-only/disabled with an explanation: "Strategy is locked at creation and cannot be changed."

### 8.6 New Frontend Files

| File | Purpose | Pattern to Follow |
|------|---------|-------------------|
| `frontend/svelte-app/src/lib/services/profileService.js` | API calls for profile CRUD | `assistantService.js` |
| `frontend/svelte-app/src/lib/stores/profileStore.js` | Svelte store for profiles per category | `assistantConfigStore.js` |
| `frontend/svelte-app/src/lib/components/profiles/ProfileSelector.svelte` | Reusable dropdown with preview + custom creation | — |
| `frontend/svelte-app/src/lib/components/profiles/ProfileForm.svelte` | Create/edit form (adapts fields based on category) | — |
| `frontend/svelte-app/src/lib/components/profiles/ProfileWarningModal.svelte` | Cascading change confirmation dialog | — |
| `frontend/svelte-app/src/lib/components/profiles/ProfileCard.svelte` | Profile display card with config preview | — |
| `frontend/svelte-app/src/routes/profiles/+page.svelte` | Profile management page | `routes/assistants/+page.svelte` |
| I18n entries in `en.json`, `es.json`, `ca.json`, `eu.json` | Translation strings for all profile UI | existing i18n patterns |

---

## 9. Backwards Compatibility & Migration

### 9.1 Zero Breaking Changes

The migration is designed so that **no existing functionality changes**:

1. All new columns (`retrieval_profile_id`, `llm_profile_id`, `prompt_template_id`) are **nullable**.
2. When all profile columns are NULL, the pipeline uses the inline `metadata` JSON exactly as today.
3. The `resolve_assistant_config()` function defaults to `parse_plugin_config()` when no profiles are referenced.
4. No existing API endpoints change their behavior. New fields are additive.
5. The frontend shows profile selectors but defaults to "No profile selected" for existing assistants.

### 9.2 Migration Phases

**Phase 1: Schema Only**
- Add `profiles`, `kb_chunking_profiles`, and `profile_defaults` tables.
- Add nullable profile columns to `assistants` table.
- All existing assistants continue working via inline metadata. Zero behavior change.

**Phase 2: System Default Profiles (Seed Data)**
- Create read-only system profiles for each category:

| Category | Profile Name | Config |
|----------|-------------|--------|
| Retrieval | "Simple RAG" | `simple_rag`, top_k=3, threshold=0.0 |
| Retrieval | "Context-Aware RAG" | `context_aware_rag`, top_k=5, threshold=0.1 |
| Retrieval | "No RAG" | `no_rag` |
| Chunking | "Standard Text" | `simple_ingest`, chunk_size=1000, overlap=200, recursive |
| Chunking | "Small Chunks" | `simple_ingest`, chunk_size=500, overlap=100, recursive |
| Chunking | "Large Chunks" | `simple_ingest`, chunk_size=2000, overlap=400, recursive |
| Chunking | "Hierarchical" | `hierarchical_ingest`, parent=2000, child=400, overlap=50 |
| LLM | "GPT-4o-mini" | `openai`, `gpt-4o-mini`, no vision |
| LLM | "GPT-4o" | `openai`, `gpt-4o`, vision enabled |

System profiles are owned by a special system user, shared by default, and cannot be edited or deleted by regular users. They can be duplicated.

**Phase 3: Opt-in Adoption**
- Users adopt profiles at their own pace.
- The assistant form shows both inline controls AND profile selectors.
- Selecting a profile fills the inline controls with the profile's values.
- Users can create custom profiles from the assistant form via the "Create Custom Profile" button.

---

## 10. Profile Limits

**Maximum: 25 profiles per category per organization.**

**Rationale:** A university department like UPC (Universitat Politècnica de Catalunya) typically has:
- ~20-50 faculty members
- Each might create 1-3 specialized profiles (e.g., "My ML Course RAG", "My Intro Course RAG")
- ~5-10 org-wide shared defaults set by the department admin
- Total realistic usage: 15-20 profiles per category

25 provides comfortable room for growth without allowing unbounded proliferation. This can be made org-configurable later if needed.

**Counting rules:**
- Shared profiles count toward the **org total**, not the individual user.
- System default profiles (seed data) do NOT count toward the org limit.
- The limit is enforced per category: 25 retrieval + 25 chunking + 25 LLM = up to 75 total profiles per org.

**Enforcement:** The `POST /creator/profiles` endpoint checks the count before creating and returns HTTP 409 with a clear message if the limit is exceeded.

---

## 11. Implementation Phases

### Phase 1: Backend Foundation

No frontend changes. Build the complete backend infrastructure.

| Step | Description | Files |
|------|-------------|-------|
| 1.1 | DB migration: `profiles`, `kb_chunking_profiles`, `profile_defaults` tables | `backend/lamb/database_manager.py` |
| 1.2 | Add `Profile` Pydantic model | `backend/lamb/lamb_classes.py` |
| 1.3 | Add profile CRUD methods to database manager | `backend/lamb/database_manager.py` |
| 1.4 | Create `profiles_router.py` with full CRUD (pattern: `prompt_templates_router.py`) | `backend/creator_interface/profiles_router.py` (NEW) |
| 1.5 | Register router in creator interface | `backend/creator_interface/main.py` |
| 1.6 | Seed system default profiles | `backend/lamb/database_manager.py` (in migrations) |

### Phase 2: Completion Pipeline Integration

Wire profiles into the completion flow so they actually affect assistant behavior.

| Step | Description | Files |
|------|-------------|-------|
| 2.1 | Create `resolve_assistant_config()` function | `backend/lamb/completions/main.py` |
| 2.2 | Modify `parse_plugin_config()` to use resolved config | `backend/lamb/completions/main.py` |
| 2.3 | Update RAG processors to read `threshold` from resolved config (replace hardcoded `0.0`) | `backend/lamb/completions/rag/simple_rag.py`, `context_aware_rag.py`, `hierarchical_rag.py` |
| 2.4 | Add profile columns to `assistants` table (nullable) | `backend/lamb/database_manager.py` |
| 2.5 | Update `assistant_router.py` to accept/return profile IDs | `backend/creator_interface/assistant_router.py` |
| 2.6 | Update `KBServerManager` to resolve chunking profile when ingesting files | `backend/creator_interface/kb_server_manager.py` |

### Phase 3: Frontend — Core Components

Build reusable profile components and the management page.

| Step | Description | Files |
|------|-------------|-------|
| 3.1 | Create `profileService.js` (API layer) | `frontend/svelte-app/src/lib/services/profileService.js` (NEW) |
| 3.2 | Create `profileStore.js` (state management) | `frontend/svelte-app/src/lib/stores/profileStore.js` (NEW) |
| 3.3 | Create `ProfileSelector.svelte` (dropdown with preview + custom creation) | `frontend/svelte-app/src/lib/components/profiles/ProfileSelector.svelte` (NEW) |
| 3.4 | Create `ProfileForm.svelte` (create/edit form, category-adaptive) | `frontend/svelte-app/src/lib/components/profiles/ProfileForm.svelte` (NEW) |
| 3.5 | Create `ProfileWarningModal.svelte` (cascading change warning) | `frontend/svelte-app/src/lib/components/profiles/ProfileWarningModal.svelte` (NEW) |
| 3.6 | Create `ProfileCard.svelte` (display with config preview) | `frontend/svelte-app/src/lib/components/profiles/ProfileCard.svelte` (NEW) |
| 3.7 | Create profile management page | `frontend/svelte-app/src/routes/profiles/+page.svelte` (NEW) |
| 3.8 | Add i18n strings | `frontend/svelte-app/src/lib/locales/{en,es,ca,eu}.json` |

### Phase 4: Frontend — Integration

Connect profile components to the assistant and KB creation flows.

| Step | Description | Files |
|------|-------------|-------|
| 4.1 | Integrate `ProfileSelector` into `AssistantForm.svelte` for Retrieval and LLM | `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` |
| 4.2 | Integrate Prompt profile selector (uses existing Templates) | `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` |
| 4.3 | Integrate Chunking `ProfileSelector` into KB creation flow | KB creation component (path TBD based on #235 implementation) |
| 4.4 | Add profile info to assistant detail view | `frontend/svelte-app/src/routes/assistants/+page.svelte` |
| 4.5 | Add navigation link to profiles page | Navigation component |

### Phase 5: Prompt Profile Enhancement

Extend the existing `PromptTemplate` to serve as the Prompt Profile.

| Step | Description | Files |
|------|-------------|-------|
| 5.1 | Add `prompt_processor` to PromptTemplate metadata | `backend/lamb/lamb_classes.py`, `backend/lamb/database_manager.py` |
| 5.2 | Add `prompt_template_id` column to assistants table | `backend/lamb/database_manager.py` |
| 5.3 | Update completion pipeline to resolve prompt profile | `backend/lamb/completions/main.py` |
| 5.4 | Integrate prompt profile into `ProfileSelector` in AssistantForm | Frontend files |

### Dependency Graph

```
Phase 1 (Backend CRUD) ──────┐
                              ├──→ Phase 3 (Frontend Components)
Phase 2 (Pipeline Integration)┘           │
                                          ↓
                              Phase 4 (Frontend Integration)

Phase 1 ──→ Phase 5 (Prompt Enhancement, can be parallel with 3+4)
```

Phases 1 and 2 are sequential (2 depends on 1). Phase 3 can start as soon as Phase 1 is done (it only needs the API). Phase 4 needs both Phase 2 (pipeline) and Phase 3 (components). Phase 5 is independent and can be done in parallel with 3+4.

---

## 12. Critical Files Reference

### Backend — Existing Files to Modify

| File | What Changes | Current Lines of Interest |
|------|-------------|--------------------------|
| `backend/lamb/database_manager.py` | New tables in `run_migrations()`, new CRUD methods | Migrations: lines 627-776. PromptTemplate CRUD (pattern to follow): lines 5485-5927 |
| `backend/lamb/lamb_classes.py` | Add `Profile` model | `Assistant` model: lines 38-80. `PromptTemplate` model: lines 107-126 |
| `backend/lamb/completions/main.py` | Add `resolve_assistant_config()`, modify pipeline entry | `parse_plugin_config()`: line 198. `get_assistant_details()`: line 188 |
| `backend/lamb/completions/rag/simple_rag.py` | Read threshold from config, not hardcoded | Hardcoded `"threshold": 0.0`: line 155 |
| `backend/lamb/completions/rag/context_aware_rag.py` | Same threshold change | Similar hardcoded threshold |
| `backend/lamb/completions/rag/hierarchical_rag.py` | Same threshold change | Similar hardcoded threshold |
| `backend/creator_interface/assistant_router.py` | Accept/return profile IDs | Create: lines 437-765. GET: lines 766-839. Update: lines 1089-1201 |
| `backend/creator_interface/main.py` | Register profiles router | Router registration section |
| `backend/creator_interface/kb_server_manager.py` | Resolve chunking profile before sending to KB server | `upload_file_to_kb()` method |
| `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` | Add ProfileSelector components | 2114 lines, metadata construction: lines 1080-1107 |
| `frontend/svelte-app/src/lib/stores/assistantConfigStore.js` | Fetch profile capabilities alongside system capabilities | |
| `frontend/svelte-app/src/lib/locales/en.json` (+ es, ca, eu) | Add profile-related translation strings | |

### Backend — New Files to Create

| File | Purpose |
|------|---------|
| `backend/creator_interface/profiles_router.py` | Profile CRUD API endpoints |
| `backend/lamb/services/profile_service.py` | Business logic (validation, affected count, limit enforcement) |

### Frontend — New Files to Create

| File | Purpose |
|------|---------|
| `frontend/svelte-app/src/lib/services/profileService.js` | API calls |
| `frontend/svelte-app/src/lib/stores/profileStore.js` | State management |
| `frontend/svelte-app/src/lib/components/profiles/ProfileSelector.svelte` | Dropdown with preview |
| `frontend/svelte-app/src/lib/components/profiles/ProfileForm.svelte` | Create/edit form |
| `frontend/svelte-app/src/lib/components/profiles/ProfileWarningModal.svelte` | Change warning |
| `frontend/svelte-app/src/lib/components/profiles/ProfileCard.svelte` | Profile display |
| `frontend/svelte-app/src/routes/profiles/+page.svelte` | Management page |

---

## 13. Verification & Testing

### Unit Tests

| Test | Description |
|------|-------------|
| Profile CRUD | Create, read, update, delete, duplicate, share — all categories |
| Config validation | Reject invalid RAG processor names, out-of-range top_k, invalid connector/model combos |
| Profile limit enforcement | Creating 26th profile returns 409 |
| Resolution cascade | Profile → org default → inline → system default |
| Affected count | Updating a profile returns correct count of affected assistants/KBs |
| Backwards compat | Assistant with NULL profile refs uses inline metadata identically to before |
| Chunking strategy lock | Updating a KB's profile to a different strategy returns 400 |

### Integration Tests

| Test | Description |
|------|-------------|
| End-to-end retrieval | Create retrieval profile → assign to assistant → send completion → verify RAG processor and params used |
| End-to-end chunking | Create KB with chunking profile → ingest file → verify chunks use profile's params → update profile → ingest another file → verify new params used, old chunks unchanged |
| End-to-end LLM | Create LLM profile → assign to assistant → send completion → verify correct connector/model used |
| Profile deletion | Delete profile → verify assistants fall back to org default or inline metadata |
| Cascading update | Update shared profile → verify all referencing assistants use new config |

### Manual Testing Checklist

- [ ] Create profile of each category with custom params
- [ ] Profile preview shows full config in dropdown
- [ ] "Create Custom Profile" from assistant form works
- [ ] Cascading change warning appears with affected assistant names
- [ ] KB creation with chunking profile works
- [ ] Strategy is read-only in KB settings after creation
- [ ] Updating KB's chunking profile (same strategy, different params) works
- [ ] System default profiles appear and can be duplicated but not edited
- [ ] Profile limit message appears at 25 profiles
- [ ] Existing assistants with no profiles work identically to before
- [ ] I18n: all profile UI strings are translated in all 4 languages
