# LAMB Project Release Notes - Developer Guide

**Period:** October 2025 - January 2026  
**Document Version:** 1.0  
**Last Updated:** January 13, 2026

---

## Overview

This document provides technical details for developers working on or integrating with LAMB. It covers API changes, architecture updates, new services, configuration changes, and development practices implemented between October 2025 and January 2026.

---

## Table of Contents

1. [Architecture Changes](#1-architecture-changes)
2. [New API Endpoints](#2-new-api-endpoints)
3. [Database Schema Changes](#3-database-schema-changes)
4. [Backend Implementation](#4-backend-implementation)
5. [Frontend Changes](#5-frontend-changes)
6. [Configuration & Environment](#6-configuration--environment)
7. [Testing Infrastructure](#7-testing-infrastructure)
8. [DevOps & Deployment](#8-devops--deployment)
9. [Security Updates](#9-security-updates)
10. [Breaking Changes](#10-breaking-changes)
11. [Merged Pull Requests](#11-merged-pull-requests)
12. [Closed Issues (Technical)](#12-closed-issues-technical)

---

## 1. Architecture Changes

### 1.1 Major Refactoring (December 2025)

**Issue #82, #43 - Service Layer Implementation**

The creator interface was refactored to use direct Python function calls instead of HTTP calls to the `/lamb` API.

```
BEFORE:
┌─────────────┐     HTTP      ┌─────────────┐
│  Creator    │ ────────────► │   /lamb     │
│  Interface  │               │    API      │
└─────────────┘               └─────────────┘

AFTER:
┌─────────────┐   Direct Call  ┌─────────────┐
│  Creator    │ ─────────────► │   Service   │
│  Interface  │                │   Layer     │
└─────────────┘                └─────────────┘
```

**Benefits:**
- Reduced network overhead
- Better error handling
- Improved performance
- Cleaner code structure

### 1.2 Centralized Logging System (December 2025)

**Issue #149, #159**

Implemented centralized logging configuration replacing the legacy Timelog utility.

**File:** `backend/lamb/logging_config.py`

```python
import logging
from lamb.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Using centralized logging")
```

**Key Changes:**
- Replaced all `logging.` references with `logger.`
- Configurable log levels per module
- Standardized log format across all components
- Removed legacy `Timelog` utility

### 1.3 Global Model Configuration (December 2025)

Organizations can now define default models globally.

```python
# Organization config structure
{
    "default_model": "gpt-4o",
    "fallback_model": "gpt-4o-mini",
    "allowed_models": ["gpt-4o", "gpt-4o-mini", "gpt-5"]
}
```

**Features:**
- API key change detection
- Model resolution with fallback
- Per-organization configuration

---

## 2. New API Endpoints

### 2.1 Evaluaitor / Rubrics API

**Base URL:** `/creator/rubrics`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creator/rubrics` | List user's rubrics |
| GET | `/creator/rubrics/accessible` | Rubrics available for assistant attachment |
| GET | `/creator/rubrics/{id}` | Get rubric by ID |
| POST | `/creator/rubrics` | Create new rubric |
| PUT | `/creator/rubrics/{id}` | Update rubric |
| DELETE | `/creator/rubrics/{id}` | Delete rubric |
| POST | `/creator/rubrics/{id}/ai-generate` | AI-powered rubric generation |

### 2.2 Prompt Templates API

**Base URL:** `/creator/prompt-templates`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/list` | List user's templates (paginated) |
| GET | `/shared` | List shared templates in organization |
| GET | `/{id}` | Get template by ID |
| POST | `/create` | Create new template |
| PUT | `/{id}` | Update template |
| DELETE | `/{id}` | Delete template |
| POST | `/{id}/duplicate` | Clone a template |
| PUT | `/{id}/share` | Toggle sharing |
| POST | `/export` | Export templates as JSON |

### 2.3 User Management API

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/creator/admin/users/{id}/disable` | Disable user |
| PUT | `/creator/admin/users/{id}/enable` | Enable user |
| POST | `/creator/admin/users/disable-bulk` | Bulk disable |
| POST | `/creator/admin/users/enable-bulk` | Bulk enable |
| DELETE | `/creator/admin/users/{id}` | Delete user (with dependency check) |

### 2.4 Knowledge Base Sharing API

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/creator/knowledgebases/kb/{id}/share` | Toggle KB sharing |
| GET | `/creator/knowledgebases/accessible` | Get accessible KBs (owned + shared) |

### 2.5 Assistant Sharing API (Restored)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creator/assistant/{id}/sharing` | Get sharing settings |
| POST | `/creator/assistant/{id}/share` | Share with users |
| DELETE | `/creator/assistant/{id}/share/{user_id}` | Remove share |

### 2.6 Analytics API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creator/analytics/assistants` | Assistant usage stats |
| GET | `/creator/analytics/chats` | Chat analytics |

### 2.7 Models Endpoint Update

**Issue #187**

The `/v1/models` endpoint now filters to return only published assistants.

```python
# GET /v1/models
# Returns only assistants where published=True
{
    "data": [
        {"id": "assistant-123", "name": "Published Assistant", ...}
    ]
}
```

---

## 3. Database Schema Changes

### 3.1 Creator_users Table

**New Columns:**

```sql
-- User blocking feature (Issue #81)
ALTER TABLE Creator_users 
ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1;

CREATE INDEX idx_creator_users_enabled 
ON Creator_users(enabled);

-- User type feature
ALTER TABLE Creator_users 
ADD COLUMN user_type TEXT NOT NULL DEFAULT 'creator' 
CHECK(user_type IN ('creator', 'end_user'));
```

### 3.2 Prompt Templates Table (New)

```sql
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    owner_email TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    prompt_template TEXT,
    is_shared BOOLEAN DEFAULT 0,
    metadata JSON,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE(organization_id, owner_email, name)
);

CREATE INDEX idx_prompt_templates_org_shared 
ON prompt_templates(organization_id, is_shared);
CREATE INDEX idx_prompt_templates_owner 
ON prompt_templates(owner_email);
CREATE INDEX idx_prompt_templates_name 
ON prompt_templates(name);
```

### 3.3 KB Registry Table (New)

```sql
CREATE TABLE kb_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL UNIQUE,
    kb_name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL,
    is_shared BOOLEAN DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES Creator_users(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE INDEX idx_kb_registry_org_shared 
ON kb_registry(organization_id, is_shared);
CREATE INDEX idx_kb_registry_owner 
ON kb_registry(owner_user_id);
```

### 3.4 Rubrics Tables

```sql
CREATE TABLE rubrics (
    rubric_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    owner_email TEXT NOT NULL,
    organization_id INTEGER,
    is_public BOOLEAN DEFAULT 0,
    is_showcase BOOLEAN DEFAULT 0,
    rubric_data JSON NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX idx_rubrics_org_public 
ON rubrics(organization_id, is_public);
CREATE INDEX idx_rubrics_owner 
ON rubrics(owner_email);
```

### 3.5 Migrations

All migrations run automatically on startup via `database_manager.run_migrations()`.

---

## 4. Backend Implementation

### 4.1 New RAG Processors

**Rubric RAG Processor**

**File:** `backend/lamb/completions/rag/rubric_rag.py`

```python
def rag_processor(messages: List[Dict], assistant=None) -> Dict:
    """
    Retrieve rubric and format as context
    
    Returns:
        {
            "context": str (formatted rubric),
            "sources": List[Dict] (rubric metadata)
        }
    """
```

**Context-Aware RAG Processor**

**File:** `backend/lamb/completions/rag/context_aware_rag.py`

Uses full conversation history for better context retrieval.

### 4.2 New Connectors

#### Banana Image Connector (Gemini Image Generation)

**File:** `backend/lamb/completions/connectors/banana_img.py`

A comprehensive image generation connector using Google Gemini models.

**Capabilities:**
```python
CONNECTOR_METADATA = {
    "id": "banana_img",
    "name": "Gemini Image",
    "description": "Google Gemini image generation connector",
    "capabilities": {
        "text_generation": False,
        "image_generation": True,
        "vision_input": True,  # Supports image-to-image
    }
}
```

**Features:**
- **Text-to-Image:** Generate images from text descriptions
- **Image-to-Image:** Modify existing images (style transfer, edits)
- **Automatic Title Routing:** Title generation requests routed to GPT-4o-mini
- **SSE Streaming Support:** Converts dict responses to streaming format
- **User-specific Storage:** Images saved to `/backend/static/public/{user_id}/img/`

**Configuration:**
```bash
# Environment variables
GEMINI_MODELS=gemini-2.5-flash-image-preview,gemini-3-pro-image-preview
GEMINI_DEFAULT_MODEL=gemini-2.5-flash-image-preview
GEMINI_API_KEY=your_key  # or GOOGLE_API_KEY
```

**Key Functions:**
```python
async def llm_connect(messages, stream=False, body=None, llm=None, assistant_owner=None):
    """Main connector entry point - routes to image gen or title gen"""

def has_images_in_messages(messages) -> bool:
    """Detect image content for image-to-image generation"""

def extract_images_from_messages(messages) -> List[Dict]:
    """Extract image URLs/data URIs from messages"""

async def _load_image_for_gemini(image_info) -> types.Part:
    """Convert image URL/base64 to Gemini Part format"""
```

#### OpenAI Connector - Vision/Multimodal Support

**File:** `backend/lamb/completions/connectors/openai.py`

Enhanced with full multimodal support for vision-capable models.

**New Functions:**
```python
def has_images_in_messages(messages) -> bool:
    """Check if any message contains image content"""

def transform_multimodal_to_vision_format(messages) -> List[Dict]:
    """Transform LAMB multimodal format to OpenAI Vision API format"""

def extract_text_from_multimodal_messages(messages) -> List[Dict]:
    """Fallback: extract text only when vision fails"""

def validate_image_urls(messages) -> List[str]:
    """Validate image URLs before sending to API"""
```

**Multimodal Message Format:**
```python
# LAMB multimodal format
{
    "role": "user",
    "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
}
```

**Graceful Fallback:**
- If vision API fails, automatically falls back to text-only mode
- Prepends warning message: "Unable to send image to the base LLM, multimodality is not supported."

**Google Gemini SDK Update**

**Issue:** Replaced `google-generativeai` with `google-genai` SDK.

```python
# requirements.txt
google-genai>=0.8.0  # Previously google-generativeai
```

### 4.3 LangSmith Integration (January 2026)

**File:** `backend/lamb/langsmith_tracing.py`

```python
from lamb.langsmith_tracing import trace_llm_call

@trace_llm_call
async def generate_completion(messages, model):
    # Automatically traced in LangSmith
    pass
```

**Configuration:**
```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=lamb
```

### 4.4 KB Server Enhancements

**Features Added:**
- Enhanced availability checks
- Configuration resolution improvements
- PDF image extraction with pymupdf
- Comprehensive processing statistics
- Async ingestion API

**New Plugin:** `markitdown_plus_ingest`

- Real-time processing logs
- PDF image extraction
- Enhanced metadata

### 4.5 Service Layer Methods

**File:** `backend/lamb/database_manager.py`

New methods added:

```python
# User blocking
def disable_user(user_id: int) -> bool
def enable_user(user_id: int) -> bool
def is_user_enabled(user_id: int) -> bool
def disable_users_bulk(user_ids: List[int]) -> Dict
def enable_users_bulk(user_ids: List[int]) -> Dict

# Prompt templates
def create_prompt_template(...) -> int
def get_prompt_template_by_id(id: int, user_email: str) -> Dict
def get_user_prompt_templates(...) -> List[Dict]
def get_organization_shared_templates(...) -> List[Dict]
def update_prompt_template(...) -> bool
def delete_prompt_template(...) -> bool
def duplicate_prompt_template(...) -> int
def toggle_template_sharing(...) -> bool

# KB Registry
def register_kb(...) -> int
def toggle_kb_sharing(...) -> bool
def get_accessible_kbs(...) -> List[Dict]
def user_can_access_kb(...) -> Tuple[bool, str]
def delete_kb_registry_entry(...) -> bool
```

---

## 5. Frontend Changes

### 5.1 Svelte 5 Compatibility

**Issue #72**

Fixed Firefox compatibility issues:
- Replaced `on:` event handlers with proper Svelte 5 syntax
- Removed inline arrow functions
- Implemented data-attribute pattern

**Before:**
```svelte
<button on:click={() => handleClick(item)}>Click</button>
```

**After:**
```svelte
<button data-item-id={item.id} onclick={handleClick}>Click</button>

<script>
function handleClick(event) {
    const itemId = event.target.dataset.itemId;
    // ...
}
</script>
```

### 5.2 New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `PromptTemplates.svelte` | `/routes/prompt-templates/` | Template management |
| `TemplateForm.svelte` | `/lib/components/templates/` | Create/edit templates |
| `RubricSelector.svelte` | `/lib/components/rubrics/` | Select rubrics for assistants |
| `ChatAnalytics.svelte` | `/routes/analytics/` | Usage dashboard |
| `ConfirmModal.svelte` | `/lib/components/ui/` | Confirmation dialogs |

### 5.3 New Services

**File:** `frontend/svelte-app/src/lib/services/`

```javascript
// adminService.js
export async function disableUser(token, userId) { ... }
export async function enableUser(token, userId) { ... }
export async function disableUsersBulk(token, userIds) { ... }
export async function enableUsersBulk(token, userIds) { ... }
export async function deleteUser(token, userId) { ... }

// templateService.js
export async function fetchTemplates(token) { ... }
export async function createTemplate(token, data) { ... }
export async function updateTemplate(token, id, data) { ... }
export async function deleteTemplate(token, id) { ... }
export async function duplicateTemplate(token, id, newName) { ... }

// rubricService.js
export async function fetchAccessibleRubrics(token) { ... }
export async function fetchRubricById(token, id) { ... }
```

### 5.4 Vite Configuration Updates

**File:** `vite.config.js`

```javascript
export default defineConfig({
    // SSR configuration
    ssr: {
        noExternal: ['certain-packages']
    },
    // Build optimization
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    vendor: ['svelte', 'other-deps']
                }
            }
        }
    }
});
```

### 5.5 Styling Changes

- Removed inline CSS across components
- Centralized styles in `app.css`
- Applied consistent brand blue color
- Widened form layouts (80% increase)

---

## 6. Configuration & Environment

### 6.1 New Environment Variables

```bash
# LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=lamb

# Google Gemini
GOOGLE_GENAI_API_KEY=your_key
GEMINI_MODEL=gemini-2.0-flash-exp

# Logging Levels
LAMB_LOG_LEVEL=INFO
KB_SERVER_LOG_LEVEL=INFO

# Ollama (defaults improved)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2

# Firecrawl (URL ingestion)
FIRECRAWL_API_URL=http://firecrawl:3002
FIRECRAWL_API_KEY=your_key
```

### 6.2 Removed/Changed Variables

```bash
# REMOVED - Issue #30
LLM_CONNECTOR  # Use connector in assistant metadata instead

# CHANGED - Issue #31
PIPELINES_HOST  # Split into LAMB_WEB_HOST and LAMB_BACKEND_HOST
```

### 6.3 Organization-Specific Configuration

KB server configuration per organization:

```python
# Organization config structure
{
    "kb_server_url": "https://kb.example.com",
    "kb_server_api_key": "encrypted_key",
    "embedding_model": "text-embedding-3-small"
}
```

---

## 7. Testing Infrastructure

### 7.1 Playwright Test Suite

**Location:** `testing/playwright/`

**New Test Files:**
- `admin-flow-tests.spec.js` - Admin user/org management
- `assistant-sharing-flow.spec.js` - Sharing functionality
- `moodle-lti-tests.spec.js` - LTI integration
- `knowledge-base-tests.spec.js` - KB CRUD operations
- `chat-response-tests.spec.js` - Assistant responses

**Configuration:**
```javascript
// playwright.config.js
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

export default {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:9099'
};
```

### 7.2 Running Tests

```bash
cd testing/playwright
npm install
cp .env.sample .env.local
# Edit .env.local with your credentials
npx playwright test
```

### 7.3 Remote Test Deployment

**Workflow:** `.github/workflows/remote-deploy.yml`

Automatically deploys and runs Playwright tests on push to dev branch.

---

## 8. DevOps & Deployment

### 8.1 Docker Compose Updates

**File:** `docker-compose.prod.yaml`

- Improved service dependencies
- Caching configuration
- Health checks

**File:** `docker-compose.firecrawl.yaml` (New)

Local Firecrawl server for URL ingestion.

### 8.2 Reverse Proxy Configurations

**Caddy:** Updated `Caddyfile` with URI strip prefix for `/lamb` and `/kb` routes.

**Nginx:** Added example configuration for multi-domain setups.

**Apache:** Complete configuration for LAMB + OpenWebUI.

### 8.3 GitHub Actions

**New Workflow:** Remote deployment on push

```yaml
# .github/workflows/remote-deploy.yml
on:
  push:
    branches: [dev]
jobs:
  deploy:
    - Playwright test execution
    - Report deployment
    - Cleanup old reports (7 days)
```

### 8.4 Monitoring

**New Script:** `scripts/monitor-docker-logs.sh`

```bash
./scripts/monitor-docker-logs.sh [service_name]
```

---

## 9. Security Updates

### 9.1 API Key Exposure Fix (January 2026)

**Commit:** `57ec34b`

Fixed API keys being exposed in frontend responses.

**Before:**
```json
{
    "config": {
        "api_key": "sk-xxxxx..."  // EXPOSED
    }
}
```

**After:**
```json
{
    "config": {
        "api_key": "***configured***"  // MASKED
    }
}
```

### 9.2 Hardcoded API Keys Fix (Issue #168)

Removed hardcoded OpenAI API keys from collection metadata.

### 9.3 Login Security

- User blocking prevents disabled users from logging in
- Returns 403 with message: "Account has been disabled"
- Self-disable prevention for admins

---

## 10. Breaking Changes

### 10.1 Environment Variable Changes

| Old | New | Action Required |
|-----|-----|-----------------|
| `PIPELINES_HOST` | `LAMB_WEB_HOST` + `LAMB_BACKEND_HOST` | Update `.env` |
| `LLM_CONNECTOR` | Removed | Use assistant metadata |

### 10.2 API Changes

| Endpoint | Change | Impact |
|----------|--------|--------|
| `GET /v1/models` | Now filters published only | May return fewer models |
| `PUT /creator/admin/users/{id}/enabled` | Renamed to `/disable` and `/enable` | Update API calls |

### 10.3 Package Changes

| Old Package | New Package | Notes |
|-------------|-------------|-------|
| `google-generativeai` | `google-genai` | Update imports |
| `httpx>=0.28` | `httpx<0.28` | Pinned for compatibility |

---

## 11. Merged Pull Requests

| PR # | Title | Merged Date |
|------|-------|-------------|
| #153 | Centralize logging configuration | Dec 18, 2025 |
| #148 | Add Google Gemini API key configuration | Dec 24, 2025 |
| #146 | Fix OpenWebUI group handling and sync | Dec 10, 2025 |
| #145 | **AI Image Generation (banana_img connector)** | Dec 4, 2025 |
| #141 | Add markdown rendering toggle to chat | Dec 3, 2025 |
| #139 | Fix broken doc links | Dec 3, 2025 |
| #133 | Fix broken documentation links | Dec 3, 2025 |
| #121 | URL ingestion plugin with Firecrawl | Dec 15, 2025 |
| #120 | Fix YouTube filename generation | Nov 21, 2025 |
| #93 | Fix AssistantsList delete update | Nov 11, 2025 |
| #89 | Organization migration feature | Oct 30, 2025 |
| #51 | Fix infinite loop in Org Admin | Oct 10, 2025 |
| #49 | Add GenAI issue labeller | Oct 10, 2025 |
| #44 | Fix server error when disabling users | Oct 9, 2025 |
| #42 | Organization features and bugfixes | Oct 9, 2025 |

---

## 12. Closed Issues (Technical)

### Backend Issues

| Issue # | Title | Resolution |
|---------|-------|------------|
| #187 | Filter /v1/models for published only | Implemented |
| #184 | Adapt to KB server enhancements | Complete |
| #182 | Markitdown plus plugin | Implemented |
| #177 | Use KB server ingestion API | Integrated |
| #176 | KB Server ingestion status API | Implemented |
| #159 | Migrate hardcoded loggers | Complete |
| #149 | Centralize logging | Complete |
| #138 | Tool use assistants | Research complete |
| #137 | Assistant as a Tool | Analyzed |
| #128 | httpx package version conflict | Pinned version |
| #127 | Sharing groups not working | Fixed |
| #105 | Multi-KB org management | Implemented |
| #82 | Internal API refactoring | Complete |
| #43 | Replace HTTP calls with direct calls | Complete |
| #30 | Remove LLM connector | Removed |
| #28 | TransferEncodingError | Fixed |

### Frontend Issues

| Issue # | Title | Resolution |
|---------|-------|------------|
| #193 | Share assistant missing | Restored |
| #189 | API config UX | Improved |
| #155 | Cannot change RAG Processor | Fixed |
| #140 | Context-aware augment | Implemented |
| #132 | Broken documentation links | Fixed |
| #123 | Multimodality support | Complete |
| #106 | Missing markdown in chat | Toggle added |
| #96 | KB selections fail to restore | Fixed |
| #95 | Auto-sanitize invalid names | Implemented |
| #91 | Settings disappearing | Fixed |
| #76 | Frontend styling inconsistencies | Addressed |
| #72 | Prompt templates | Complete |
| #62 | Cannot change model | Fixed |
| #55 | Graceful failures | Implemented |
| #35 | Cannot edit RAG Processor | Fixed |

### Infrastructure Issues

| Issue # | Title | Resolution |
|---------|-------|------------|
| #163 | Docker Compose for Firecrawl | Added |
| #149 | Centralized logging | Complete |
| #119 | Add favicon | Added |
| #115 | Set DEBUG to false | Fixed |
| #113 | Hardcoded env variables | Removed |
| #90 | Service race conditions | Fixed |
| #38 | Docker BuildKit cache | Implemented |
| #31 | Split PIPELINES_HOST | Complete |
| #2 | Config.js distribution | Improved |
| #1 | Docker Compose .env docs | Clarified |

---

## Migration Guide

### From v0.2 to v0.4

1. **Update environment variables:**
   ```bash
   # Add new variables
   LANGSMITH_TRACING=false
   LAMB_LOG_LEVEL=INFO
   
   # Update if using Gemini
   GOOGLE_GENAI_API_KEY=your_key
   ```

2. **Update requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database migrations:**
   Migrations run automatically on startup.

4. **KB Registry Migration:**
   If upgrading from v0.2, run the KB registry migration:
   ```bash
   python scripts/migrate_kb_registry.py
   ```

5. **Frontend rebuild:**
   ```bash
   cd frontend/svelte-app
   npm install
   npm run build
   ```

---

## Development Recipes

### Adding a New RAG Processor

1. Create file in `backend/lamb/completions/rag/`
2. Implement `rag_processor(messages, assistant)` function
3. Return `{"context": str, "sources": list}`
4. Register in `rag/__init__.py`

### Adding a New Connector

1. Create file in `backend/lamb/completions/connectors/`
2. Implement `connector(messages, assistant, stream)` function
3. Register in `connectors/__init__.py`

### Creating Playwright Tests

```javascript
// testing/playwright/tests/my-test.spec.js
import { test, expect } from '@playwright/test';
import { login, logout } from '../utils/auth';

test.describe('My Feature', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('should do something', async ({ page }) => {
        await page.goto('/my-feature');
        await expect(page.locator('.element')).toBeVisible();
    });
});
```

---

## Resources

- [Architecture Documentation](./lamb_architecture_v2.md)
- [API Documentation](./small-context/backend_authentication.md)
- [Frontend Guidelines](./small-context/frontend_architecture.md)
- [Deployment Guide](./deployment.md)
- [LangSmith Tracing](./langsmith_tracing.md)
- [Logging Procedures](./slop-docs/LOGGING_PROCEDURES.md)

---

**Document maintained by:** LAMB Development Team  
**Last technical review:** January 13, 2026

