# LAMB Evaluaitor - Educational Rubrics Feature

**Version:** 1.0  
**Last Updated:** October 2025  
**Status:** Design Phase  
**Feature Owner:** LAMB Development Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Objectives](#2-goals--objectives)
3. [User Stories](#3-user-stories)
4. [Functional Requirements](#4-functional-requirements)
5. [Data Architecture](#5-data-architecture)
6. [API Architecture](#6-api-architecture)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Integration with LAMB](#8-integration-with-lamb)
9. [LLM Integration](#9-llm-integration)
10. [Export Formats](#10-export-formats)
11. [Implementation Plan](#11-implementation-plan)
12. [Future Enhancements](#12-future-enhancements)
13. [Open Questions](#13-open-questions)

---

## 1. Overview

### 1.1 Purpose

The **Evaluaitor** feature adds educational rubric management to LAMB, enabling educators to create, manage, and maintain assessment rubrics alongside their AI learning assistants. This feature provides a structured way to define assessment criteria and performance levels for educational activities.

### 1.2 Scope

**In Scope (Phase 1 - MVP):**
- Rubric CRUD operations (Create, Read, Update, Delete)
- JSON-based rubric data format
- User-scoped rubric storage with privacy controls
- Organization-aware rubric management
- Export to JSON and Markdown formats
- Import from JSON format
- Web-based rubric editor with table visualization
- AI chat interface for rubric creation and modification
- Rubric templates (any accessible rubric can be template)
- Showcase rubrics (org admin curated templates)
- Save as new version functionality
- API endpoints for programmatic access

**Out of Scope (Phase 1):**
- AI-assisted grading/evaluation of student work
- Rubric application to actual student submissions
- RAG integration (JSON/MD exports support future use)
- PDF export generation
- Real-time collaborative editing
- Rubric marketplace beyond organization

### 1.3 Key Features

1. **Rubric Management:** Full CRUD for educational rubrics
2. **Flexible Format:** JSON-based structure supporting various rubric types (analytic, holistic, single-point, checklist)
3. **Visual Editor:** Table-based interface for intuitive rubric creation and editing
4. **Multi-Format Export:** JSON and Markdown export capabilities
5. **Organization Integration:** Rubrics scoped to users within organizations
6. **Future-Ready:** Architecture supports future AI-assisted editing and grading

---

## 2. Goals & Objectives

### 2.1 Primary Goals

1. **Enable Structured Assessment:** Provide educators with tools to create clear, consistent assessment criteria
2. **AI-Assisted Creation:** Use LLM chat to help educators create and refine rubrics
3. **Integrate with LAMB Workflow:** Seamlessly fit into existing assistant creation and management workflow
4. **Support Educational Best Practices:** Implement rubric format aligned with educational standards
5. **Prepare for AI Grading:** Lay foundation for future AI-assisted evaluation features via JSON/MD exports
6. **Maintain Privacy & Control:** Keep rubrics private by default with optional public sharing

### 2.2 Success Criteria

- Educators can create a complete rubric in under 10 minutes
- Rubric data is stored in LLM-friendly JSON format
- Export functionality produces usable Markdown documents
- API supports programmatic rubric management
- Integration follows existing LAMB patterns (authentication, organization scope, etc.)

---

## 3. User Stories

### 3.1 Creator User Stories

**As a creator user, I want to:**
- Create new rubrics for my courses and assignments (manually or via AI chat)
- Chat with an LLM to generate rubrics from natural language descriptions
- Ask an LLM to modify my rubrics ("make it suitable for 6th graders")
- Edit existing rubrics by modifying individual cells or criteria
- View all my rubrics in a list (private and public)
- Make my rubrics public for others to use as templates
- Use any accessible rubric (mine or public) as a template
- Save modified rubrics as new versions
- Delete rubrics I no longer need
- Export rubrics as JSON for backup or sharing
- Import rubrics from JSON files
- Export rubrics as Markdown for inclusion in course documents
- Search and filter my rubrics by title, subject, or grade level

### 3.2 Organization Admin Stories

**As an organization admin, I want to:**
- View all public rubrics in my organization
- Mark high-quality rubrics as "showcase" templates for my organization
- Unmark showcase rubrics if they're no longer relevant
- Create my own rubrics (with AI assistance)
- See which rubrics are most used as templates (future enhancement)

### 3.3 System Admin Stories

**As a system admin, I want to:**
- Ensure rubric data is properly backed up with other LAMB data
- Monitor system-wide rubric storage and performance
- Mark system-wide showcase rubrics available to all organizations
- Import/export rubrics for migration purposes

---

## 4. Functional Requirements

### 4.1 Rubric Management

#### 4.1.1 Create Rubric
- **FR-RUB-001:** Users shall create new rubrics with title, description, and metadata
- **FR-RUB-002:** System shall auto-generate unique rubricId for each rubric
- **FR-RUB-003:** Rubrics shall belong to a specific user (owner) and organization
- **FR-RUB-004:** New rubrics shall include default criteria and levels structure
- **FR-RUB-005:** System shall validate rubric structure before saving
- **FR-RUB-006:** Created rubrics shall store timestamps (created_at, modified_at)
- **FR-RUB-007:** Rubrics shall be private by default
- **FR-RUB-008:** Users shall optionally make rubrics public within their organization

#### 4.1.2 Read/List Rubrics
- **FR-RUB-009:** Users shall list all rubrics they own (private and public)
- **FR-RUB-010:** Users shall list all public rubrics in their organization
- **FR-RUB-011:** Users shall see showcase rubrics prominently in template selection
- **FR-RUB-012:** List shall support pagination (limit/offset)
- **FR-RUB-013:** Users shall retrieve individual rubric by ID (if they own it or it's public)
- **FR-RUB-014:** List shall support filtering by subject, grade level, tags, visibility
- **FR-RUB-015:** List shall support search by title and description
- **FR-RUB-016:** System shall return rubrics in full JSON format

#### 4.1.3 Update Rubric
- **FR-RUB-017:** Users shall update entire rubric structure (only their own rubrics)
- **FR-RUB-018:** Users shall update individual criterion properties
- **FR-RUB-019:** Users shall update individual level descriptions (cell edits)
- **FR-RUB-020:** Users shall add/remove criteria
- **FR-RUB-021:** Users shall add/remove performance levels
- **FR-RUB-022:** Users shall toggle rubric visibility (private/public)
- **FR-RUB-023:** System shall update modified_at timestamp on every change
- **FR-RUB-024:** System shall validate updates before saving

#### 4.1.4 Delete Rubric
- **FR-RUB-025:** Users shall delete their own rubrics
- **FR-RUB-026:** System shall require confirmation for deletion
- **FR-RUB-027:** Deletion shall be permanent (no soft delete in Phase 1)
- **FR-RUB-028:** System admins shall delete any rubric

#### 4.1.5 Versioning & Templates
- **FR-RUB-029:** Users shall clone/duplicate any accessible rubric as a starting point
- **FR-RUB-030:** Users shall explicitly "Save as New Version" when modifying a rubric
- **FR-RUB-031:** New versions shall receive new rubricId
- **FR-RUB-032:** System shall optionally track parent rubric reference
- **FR-RUB-033:** Organization admins shall mark public rubrics as "showcase" templates
- **FR-RUB-034:** System admins shall mark system-wide showcase rubrics

### 4.2 Rubric Structure & Validation

#### 4.2.1 JSON Format Support
- **FR-RUB-024:** System shall store rubrics in JSON format as defined in specification
- **FR-RUB-025:** System shall support analytic rubrics (multiple criteria with levels)
- **FR-RUB-026:** System shall support different scoring types (points, percentage, holistic, single-point, checklist)
- **FR-RUB-027:** System shall validate required fields (rubricId, title, description, metadata, criteria, scoringType, maxScore)
- **FR-RUB-028:** Each criterion shall have unique ID within rubric
- **FR-RUB-029:** Each level shall have unique ID within criterion

#### 4.2.2 Metadata Requirements
- **FR-RUB-030:** Rubrics shall include subject field
- **FR-RUB-031:** Rubrics shall include gradeLevel field
- **FR-RUB-032:** Rubrics shall include created_at and modified_at timestamps
- **FR-RUB-033:** Rubrics shall support optional author, version, and tags fields

### 4.3 Import/Export Functionality

#### 4.3.1 JSON Export
- **FR-RUB-035:** Users shall export rubrics as JSON files
- **FR-RUB-036:** Exported JSON shall be valid and re-importable
- **FR-RUB-037:** Export shall include all rubric data including metadata

#### 4.3.2 JSON Import
- **FR-RUB-038:** Users shall import rubrics from JSON files
- **FR-RUB-039:** System shall validate imported JSON structure
- **FR-RUB-040:** System shall generate new rubricId for imported rubrics
- **FR-RUB-041:** Imported rubrics shall be private by default
- **FR-RUB-042:** System shall report validation errors clearly

#### 4.3.3 Markdown Export
- **FR-RUB-043:** Users shall export rubrics as Markdown documents
- **FR-RUB-044:** Markdown shall render as readable table format
- **FR-RUB-045:** Markdown shall include rubric title, description, and metadata
- **FR-RUB-046:** Markdown shall be suitable for inclusion in course documentation
- **FR-RUB-047:** Markdown export enables future RAG integration (out of scope Phase 1)

### 4.4 User Interface

#### 4.4.1 Rubric List View
- **FR-RUB-048:** UI shall display paginated list of user's rubrics
- **FR-RUB-049:** UI shall display public rubrics from organization (separate tab or filter)
- **FR-RUB-050:** Showcase rubrics shall be visually distinguished (badge/icon)
- **FR-RUB-051:** Each rubric shall show title, subject, grade level, visibility, last modified date
- **FR-RUB-052:** List shall provide quick actions: view, edit, duplicate, delete, export, toggle visibility
- **FR-RUB-053:** UI shall include "Create New Rubric" and "Import Rubric" buttons
- **FR-RUB-054:** List shall support search and filter controls
- **FR-RUB-055:** List shall indicate rubric ownership (mine vs. public template)

#### 4.4.2 Rubric Editor
- **FR-RUB-056:** Editor shall display rubric as visual table (criteria as rows, levels as columns)
- **FR-RUB-057:** Cells shall be editable inline (contenteditable or textarea)
- **FR-RUB-058:** Editor shall support adding/removing criteria (rows)
- **FR-RUB-059:** Editor shall support adding/removing levels (columns)
- **FR-RUB-060:** Editor shall allow editing metadata (title, description, subject, grade level)
- **FR-RUB-061:** Editor shall show save/cancel actions
- **FR-RUB-062:** Editor shall show "Save as New Version" button
- **FR-RUB-063:** Editor shall validate before saving
- **FR-RUB-064:** Editor shall include AI chat panel for modifications

#### 4.4.3 AI Chat Interface
- **FR-RUB-065:** UI shall include chat panel for AI-assisted rubric creation/editing
- **FR-RUB-066:** Chat shall accept natural language prompts for rubric generation
- **FR-RUB-067:** Chat shall accept modification requests ("make this for 6th graders")
- **FR-RUB-068:** Chat shall show preview of proposed changes before applying
- **FR-RUB-069:** User shall explicitly accept or reject AI suggestions
- **FR-RUB-070:** Chat shall maintain conversation context during editing session

#### 4.4.4 Navigation
- **FR-RUB-071:** Main navigation shall include "Evaluaitor" tab/link
- **FR-RUB-072:** Evaluaitor section shall be accessible to creator users, admins, and org admins
- **FR-RUB-073:** Navigation shall indicate current active section

---

## 5. Data Architecture

### 5.1 Database Schema

#### 5.1.1 Rubrics Table

```sql
CREATE TABLE rubrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rubric_id TEXT UNIQUE NOT NULL,           -- UUID or slug for external references
    organization_id INTEGER NOT NULL,          -- Organization this rubric belongs to
    owner_email TEXT NOT NULL,                 -- Email of creator
    title TEXT NOT NULL,                       -- Rubric title
    description TEXT,                          -- Rubric description
    rubric_data JSON NOT NULL,                 -- Full rubric JSON structure
    is_public BOOLEAN DEFAULT FALSE,           -- Whether rubric is visible to org
    is_showcase BOOLEAN DEFAULT FALSE,         -- Whether marked as org showcase template
    parent_rubric_id TEXT,                     -- Optional: reference to template/parent
    created_at INTEGER NOT NULL,               -- Unix timestamp
    updated_at INTEGER NOT NULL,               -- Unix timestamp
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_rubric_id) REFERENCES rubrics(rubric_id) ON DELETE SET NULL
);

CREATE INDEX idx_rubrics_owner ON rubrics(owner_email);
CREATE INDEX idx_rubrics_org ON rubrics(organization_id);
CREATE INDEX idx_rubrics_rubric_id ON rubrics(rubric_id);
CREATE INDEX idx_rubrics_public ON rubrics(is_public);
CREATE INDEX idx_rubrics_showcase ON rubrics(is_showcase);
```

**Field Descriptions:**
- `id`: Internal database primary key
- `rubric_id`: External identifier (UUID), used in API calls
- `organization_id`: Links rubric to organization for multi-tenancy
- `owner_email`: Creator user's email (matches Creator_users.user_email)
- `title`: Rubric title (denormalized for quick list queries)
- `description`: Rubric description (denormalized for search)
- `rubric_data`: Full JSON rubric structure as defined in specification
- `is_public`: Boolean flag - if TRUE, visible to all users in organization
- `is_showcase`: Boolean flag - if TRUE, marked as featured template by org/system admin
- `parent_rubric_id`: Optional reference to rubric this was cloned from (for tracking)
- `created_at`: Creation timestamp (Unix epoch)
- `updated_at`: Last modification timestamp (Unix epoch)

**Privacy Model:**
- **Private (default):** Only owner can see/edit (`is_public=FALSE`)
- **Public:** All users in organization can see and use as template (`is_public=TRUE`)
- **Showcase:** Public rubrics promoted by admins (`is_public=TRUE, is_showcase=TRUE`)

#### 5.1.2 Rubric JSON Structure (stored in rubric_data)

The `rubric_data` column contains the complete rubric JSON:

```json
{
  "rubricId": "string",
  "title": "string",
  "description": "string",
  "metadata": {
    "subject": "string",
    "gradeLevel": "string",
    "createdAt": "ISO8601 timestamp",
    "modifiedAt": "ISO8601 timestamp",
    "author": "string",
    "version": "string",
    "tags": ["string"]
  },
  "criteria": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "weight": number,
      "order": number,
      "levels": [
        {
          "id": "string",
          "score": number,
          "label": "string",
          "description": "string",
          "order": number
        }
      ]
    }
  ],
  "scoringType": "points|percentage|holistic|single-point|checklist",
  "maxScore": number
}
```

**Note:** The `title` and `description` are stored both in the JSON and as separate columns for efficient querying without parsing JSON.

### 5.2 Database Manager

**File:** `/backend/lamb/evaluaitor/rubric_database.py`

**Class:** `RubricDatabaseManager`

**Methods:**
- `create_rubric(rubric_data: dict, owner_email: str, organization_id: int) -> dict`
- `get_rubric_by_id(rubric_id: str, requesting_user_email: str) -> dict | None`
- `get_rubrics_by_owner(owner_email: str, limit: int, offset: int, filters: dict) -> list[dict]`
- `get_public_rubrics(organization_id: int, limit: int, offset: int, filters: dict) -> list[dict]`
- `get_showcase_rubrics(organization_id: int) -> list[dict]`
- `update_rubric(rubric_id: str, rubric_data: dict, owner_email: str) -> dict`
- `toggle_rubric_visibility(rubric_id: str, is_public: bool, owner_email: str) -> bool`
- `set_showcase_status(rubric_id: str, is_showcase: bool, admin_email: str) -> bool`
- `delete_rubric(rubric_id: str, owner_email: str) -> bool`
- `count_rubrics(owner_email: str, filters: dict) -> int`
- `duplicate_rubric(rubric_id: str, new_owner_email: str) -> dict`

### 5.3 Data Validation

**File:** `/backend/lamb/evaluaitor/rubric_validator.py`

**Functions:**
- `validate_rubric_structure(rubric_data: dict) -> tuple[bool, str | None]`
- `validate_criterion(criterion: dict) -> tuple[bool, str | None]`
- `validate_level(level: dict) -> tuple[bool, str | None]`
- `validate_metadata(metadata: dict) -> tuple[bool, str | None]`

**Validation Rules:**
- Required fields present
- Unique IDs within rubric
- Valid scoring type
- Numeric fields are numbers
- Weights sum appropriately
- At least one criterion
- At least two levels per criterion

---

## 6. API Architecture

### 6.1 Core API Endpoints (LAMB Core)

**Base Path:** `/lamb/v1/evaluaitor/rubrics`

**File:** `/backend/lamb/evaluaitor/rubrics.py`

#### 6.1.1 Rubric CRUD Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/lamb/v1/evaluaitor/rubrics` | Create new rubric | Required |
| GET | `/lamb/v1/evaluaitor/rubrics` | List user's rubrics | Required |
| GET | `/lamb/v1/evaluaitor/rubrics/public` | List public rubrics in org | Required |
| GET | `/lamb/v1/evaluaitor/rubrics/showcase` | List showcase templates | Required |
| GET | `/lamb/v1/evaluaitor/rubrics/{rubric_id}` | Get rubric by ID | Required |
| PUT | `/lamb/v1/evaluaitor/rubrics/{rubric_id}` | Update rubric | Required |
| PUT | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/visibility` | Toggle public/private | Required |
| PUT | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/showcase` | Set showcase status | Admin |
| DELETE | `/lamb/v1/evaluaitor/rubrics/{rubric_id}` | Delete rubric | Required |
| POST | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/duplicate` | Duplicate rubric | Required |

#### 6.1.2 Import/Export Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/lamb/v1/evaluaitor/rubrics/import` | Import rubric from JSON | Required |
| GET | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/export/json` | Export as JSON | Required |
| GET | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/export/markdown` | Export as Markdown | Required |

#### 6.1.3 AI Assistance Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/lamb/v1/evaluaitor/rubrics/ai-generate` | Generate rubric from prompt | Required |
| POST | `/lamb/v1/evaluaitor/rubrics/{rubric_id}/ai-modify` | Modify rubric via AI | Required |

### 6.2 Creator Interface API

**Base Path:** `/creator/evaluaitor`

**File:** `/backend/creator_interface/evaluaitor_router.py`

The Creator Interface API acts as a proxy to the LAMB Core API, adding:
- User authentication via JWT token
- Organization context resolution
- Enhanced error messages
- File download handling for exports

#### 6.2.1 Proxied Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/creator/evaluaitor/rubrics` | Create rubric (proxied) |
| GET | `/creator/evaluaitor/rubrics` | List user's rubrics (proxied) |
| GET | `/creator/evaluaitor/rubrics/public` | List public rubrics (proxied) |
| GET | `/creator/evaluaitor/rubrics/showcase` | List showcase templates (proxied) |
| GET | `/creator/evaluaitor/rubrics/{rubric_id}` | Get rubric (proxied) |
| PUT | `/creator/evaluaitor/rubrics/{rubric_id}` | Update rubric (proxied) |
| PUT | `/creator/evaluaitor/rubrics/{rubric_id}/visibility` | Toggle visibility (proxied) |
| PUT | `/creator/evaluaitor/rubrics/{rubric_id}/showcase` | Set showcase (admin only) |
| DELETE | `/creator/evaluaitor/rubrics/{rubric_id}` | Delete rubric (proxied) |
| POST | `/creator/evaluaitor/rubrics/{rubric_id}/duplicate` | Duplicate rubric (proxied) |
| POST | `/creator/evaluaitor/rubrics/import` | Import JSON (with file upload) |
| GET | `/creator/evaluaitor/rubrics/{rubric_id}/export/json` | Export JSON (download headers) |
| GET | `/creator/evaluaitor/rubrics/{rubric_id}/export/markdown` | Export MD (download headers) |
| POST | `/creator/evaluaitor/rubrics/ai-generate` | AI generate (proxied) |
| POST | `/creator/evaluaitor/rubrics/{rubric_id}/ai-modify` | AI modify (proxied) |

### 6.3 API Request/Response Examples

#### 6.3.1 Create Rubric

**Request:**
```http
POST /creator/evaluaitor/rubrics
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Essay Writing Rubric",
  "description": "Rubric for argumentative essays",
  "metadata": {
    "subject": "English",
    "gradeLevel": "9-12"
  },
  "criteria": [
    {
      "name": "Thesis Statement",
      "description": "Quality of main argument",
      "weight": 25,
      "levels": [
        {
          "score": 4,
          "label": "Exemplary",
          "description": "Clear and compelling thesis"
        },
        {
          "score": 3,
          "label": "Proficient",
          "description": "Clear thesis"
        },
        {
          "score": 2,
          "label": "Developing",
          "description": "Unclear thesis"
        },
        {
          "score": 1,
          "label": "Beginning",
          "description": "Missing thesis"
        }
      ]
    }
  ],
  "scoringType": "points",
  "maxScore": 100
}
```

**Response:**
```json
{
  "success": true,
  "rubric": {
    "id": 1,
    "rubricId": "rubric-550e8400-e29b-41d4-a716-446655440000",
    "organizationId": 1,
    "ownerEmail": "prof@university.edu",
    "title": "Essay Writing Rubric",
    "description": "Rubric for argumentative essays",
    "rubricData": { /* full JSON structure with generated IDs */ },
    "createdAt": 1697212800,
    "updatedAt": 1697212800
  }
}
```

#### 6.3.2 List Rubrics

**Request:**
```http
GET /creator/evaluaitor/rubrics?limit=10&offset=0&subject=English
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "rubrics": [
    {
      "id": 1,
      "rubricId": "rubric-550e8400-...",
      "title": "Essay Writing Rubric",
      "description": "Rubric for argumentative essays",
      "subject": "English",
      "gradeLevel": "9-12",
      "createdAt": 1697212800,
      "updatedAt": 1697212800
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

#### 6.3.3 Export as Markdown

**Request:**
```http
GET /creator/evaluaitor/rubrics/{rubric_id}/export/markdown
Authorization: Bearer {token}
```

**Response Headers:**
```
Content-Type: text/markdown
Content-Disposition: attachment; filename="essay-writing-rubric.md"
```

**Response Body:**
```markdown
# Essay Writing Rubric

**Description:** Rubric for argumentative essays

**Subject:** English  
**Grade Level:** 9-12  
**Scoring Type:** points  
**Maximum Score:** 100

---

## Criteria and Performance Levels

| Criterion | Exemplary (4) | Proficient (3) | Developing (2) | Beginning (1) |
|-----------|---------------|----------------|----------------|---------------|
| **Thesis Statement** (25 pts)<br>Quality of main argument | Clear and compelling thesis | Clear thesis | Unclear thesis | Missing thesis |

---

*Created: 2024-10-13*  
*Last Modified: 2024-10-13*
```

---

## 7. Frontend Architecture

### 7.1 Component Structure

**Location:** `/frontend/svelte-app/src/lib/components/evaluaitor/`

#### 7.1.1 Main Components

| Component | File | Purpose |
|-----------|------|---------|
| `RubricsList.svelte` | `RubricsList.svelte` | List view with tabs (My Rubrics / Templates) |
| `RubricEditor.svelte` | `RubricEditor.svelte` | Main rubric editing interface |
| `RubricTable.svelte` | `RubricTable.svelte` | Table visualization of rubric |
| `RubricMetadataForm.svelte` | `RubricMetadataForm.svelte` | Edit title, description, metadata |
| `CriterionRow.svelte` | `CriterionRow.svelte` | Single criterion row in table |
| `LevelCell.svelte` | `LevelCell.svelte` | Editable level description cell |
| `RubricAIChat.svelte` | `RubricAIChat.svelte` | AI chat panel for creation/modification |
| `RubricChangePreview.svelte` | `RubricChangePreview.svelte` | Preview AI-suggested changes |
| `RubricExportModal.svelte` | `RubricExportModal.svelte` | Export/Import modal |
| `RubricTemplateCard.svelte` | `RubricTemplateCard.svelte` | Display template in gallery |

### 7.2 Services

**Location:** `/frontend/svelte-app/src/lib/services/`

#### 7.2.1 Rubric Service

**File:** `rubricService.js`

```javascript
/**
 * Rubric API service
 */

/**
 * Fetch all rubrics for current user
 * @param {number} limit
 * @param {number} offset
 * @param {Object} filters
 * @returns {Promise<{rubrics: Array, total: number}>}
 */
export async function fetchRubrics(limit = 10, offset = 0, filters = {}) {}

/**
 * Fetch single rubric by ID
 * @param {string} rubricId
 * @returns {Promise<Object>}
 */
export async function fetchRubric(rubricId) {}

/**
 * Create new rubric
 * @param {Object} rubricData
 * @returns {Promise<Object>}
 */
export async function createRubric(rubricData) {}

/**
 * Update existing rubric
 * @param {string} rubricId
 * @param {Object} rubricData
 * @returns {Promise<Object>}
 */
export async function updateRubric(rubricId, rubricData) {}

/**
 * Delete rubric
 * @param {string} rubricId
 * @returns {Promise<boolean>}
 */
export async function deleteRubric(rubricId) {}

/**
 * Duplicate rubric
 * @param {string} rubricId
 * @returns {Promise<Object>}
 */
export async function duplicateRubric(rubricId) {}

/**
 * Export rubric as JSON
 * @param {string} rubricId
 * @returns {Promise<Blob>}
 */
export async function exportRubricJSON(rubricId) {}

/**
 * Export rubric as Markdown
 * @param {string} rubricId
 * @returns {Promise<Blob>}
 */
export async function exportRubricMarkdown(rubricId) {}

/**
 * Import rubric from JSON file
 * @param {File} file
 * @returns {Promise<Object>}
 */
export async function importRubric(file) {}

/**
 * Toggle rubric visibility (public/private)
 * @param {string} rubricId
 * @param {boolean} isPublic
 * @returns {Promise<Object>}
 */
export async function toggleRubricVisibility(rubricId, isPublic) {}

/**
 * Set showcase status (admin only)
 * @param {string} rubricId
 * @param {boolean} isShowcase
 * @returns {Promise<Object>}
 */
export async function setShowcaseStatus(rubricId, isShowcase) {}

/**
 * Fetch public rubrics in organization
 * @param {number} limit
 * @param {number} offset
 * @param {Object} filters
 * @returns {Promise<{rubrics: Array, total: number}>}
 */
export async function fetchPublicRubrics(limit = 10, offset = 0, filters = {}) {}

/**
 * Fetch showcase templates
 * @returns {Promise<Array>}
 */
export async function fetchShowcaseRubrics() {}

/**
 * Generate rubric via AI from prompt
 * @param {string} prompt
 * @returns {Promise<{rubric: Object, explanation: string}>}
 */
export async function aiGenerateRubric(prompt) {}

/**
 * Modify rubric via AI
 * @param {string} rubricId
 * @param {string} prompt
 * @returns {Promise<{rubric: Object, explanation: string}>}
 */
export async function aiModifyRubric(rubricId, prompt) {}
```

### 7.3 Stores

**Location:** `/frontend/svelte-app/src/lib/stores/`

#### 7.3.1 Rubric Store

**File:** `rubricStore.svelte.js`

```javascript
/**
 * Svelte 5 store for rubric state management
 */

class RubricStore {
  #rubric = $state(null);
  #history = $state([]);
  #historyIndex = $state(-1);
  
  // Methods for state management, undo/redo, validation
  loadRubric(rubric) {}
  updateCell(criterionId, levelId, field, value) {}
  updateCriterion(criterionId, updates) {}
  addCriterion(criterion) {}
  removeCriterion(criterionId) {}
  addLevel(levelData) {}
  removeLevel(levelId) {}
  replaceRubric(newRubric) {}
  toggleVisibility(isPublic) {}
  undo() {}
  redo() {}
  getChanges(proposedRubric) {}
  reset() {}
}

export const rubricStore = new RubricStore();
```

### 7.4 Routes

**Location:** `/frontend/svelte-app/src/routes/`

#### 7.4.1 New Route

**Directory:** `evaluaitor/`

**Files:**
- `evaluaitor/+page.svelte` - Main Evaluaitor page (rubrics list)
- `evaluaitor/[rubricId]/+page.svelte` - Rubric editor page

### 7.5 Navigation Integration

**File:** `/frontend/svelte-app/src/lib/components/Nav.svelte`

**Changes:**
- Add "Evaluaitor" navigation link/tab
- Active state highlighting for Evaluaitor section
- Icon for Evaluaitor (e.g., checklist or document icon)

---

## 8. Integration with LAMB

### 8.1 Authentication & Authorization

**Pattern:** Follow existing LAMB authentication patterns

1. **Creator Interface:** Use JWT token authentication
2. **User Resolution:** Extract user from token via `get_creator_user_from_token()`
3. **Organization Context:** Resolve user's organization for multi-tenancy
4. **Ownership Check:** Verify user owns rubric before allowing edit/delete

### 8.2 Multi-Tenancy

**Pattern:** Follow assistant model

- Rubrics belong to a user (owner_email) and organization (organization_id)
- Users can only see/edit their own rubrics
- Organization admins have enhanced visibility (optional - see Open Questions)
- System admins can manage all rubrics

### 8.3 Database Integration

**Pattern:** Use existing database manager pattern

- Extend database initialization to create rubrics table
- Use parameterized queries for SQL injection prevention
- Use transactions for data consistency
- Follow table_prefix pattern for multi-instance deployments

### 8.4 Error Handling

**Pattern:** Follow LAMB error response format

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- 200: Success
- 201: Created
- 400: Bad request (validation error)
- 401: Unauthorized (missing/invalid token)
- 403: Forbidden (not owner)
- 404: Not found
- 422: Unprocessable entity (invalid JSON structure)
- 500: Internal server error

---

## 9. LLM Integration

### 9.1 AI-Assisted Rubric Creation and Editing

**Note:** This is a Phase 1 (MVP) feature based on user requirements.

#### 9.1.1 Generate Rubric from Scratch

**Endpoint:**
```http
POST /creator/evaluaitor/rubrics/ai-generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "prompt": "Create a rubric for evaluating 5-paragraph essays in 8th grade English"
}
```

#### 9.1.2 Modify Existing Rubric

**Endpoint:**
```http
POST /creator/evaluaitor/rubrics/{rubric_id}/ai-modify
Authorization: Bearer {token}
Content-Type: application/json

{
  "prompt": "Make this rubric appropriate for 6th graders"
}
```

#### 9.1.3 System Prompt Template (Generation)

```
You are an expert educational assessment specialist helping an educator create a rubric.

The educator's request: "{user_prompt}"

Instructions:
1. Analyze the educator's request and create an appropriate rubric
2. Use educational best practices for rubric design
3. Include 3-5 criteria appropriate to the task
4. Include 4 performance levels (Exemplary, Proficient, Developing, Beginning) with scores 4-1
5. Write clear, specific, observable descriptors for each level
6. Assign appropriate weights to each criterion (should sum to 100)
7. Return the COMPLETE rubric in valid JSON format matching the schema
8. Provide a brief explanation of your design choices

Respond in this format:
{
  "rubric": { /* complete rubric JSON matching schema */ },
  "explanation": "Brief explanation of the rubric design and rationale"
}
```

#### 9.1.4 System Prompt Template (Modification)

```
You are an expert educational assessment specialist helping an educator modify their rubric.

Current rubric (in JSON format):
{rubric_json}

The educator's request: "{user_prompt}"

Instructions:
1. Analyze the current rubric structure and the educator's request
2. Make appropriate modifications that maintain educational validity
3. Preserve the rubric structure unless explicitly asked to change it
4. Return the COMPLETE modified rubric in valid JSON format
5. Provide a brief explanation of what you changed and why
6. If the request is ambiguous, make reasonable assumptions but note them

Examples of modifications:
- "Make it for 6th graders" → simplify language and expectations
- "Add a creativity criterion" → add new criterion with levels
- "Make it more specific" → enhance descriptors with concrete examples
- "Convert to a 5-point scale" → adjust scores and potentially add a level

Respond in this format:
{
  "rubric": { /* complete modified rubric JSON */ },
  "explanation": "Brief explanation of changes made",
  "changes_summary": {
    "criteria_added": ["list of new criteria"],
    "criteria_modified": ["list of modified criteria"],
    "criteria_removed": ["list of removed criteria"],
    "other_changes": "description of other modifications"
  }
}
```

#### 9.1.5 Implementation Notes

**LLM Configuration:**
- Use organization-specific LLM configuration (follows assistant pattern)
- Use `OrganizationConfigResolver` to get provider settings
- Support OpenAI, Anthropic, Ollama (any configured provider)
- Default to organization's default model

**Response Handling:**
- Stream response for better UX (optional Phase 1, recommended Phase 2)
- Parse JSON from LLM response
- Validate rubric structure before presenting to user
- Handle LLM errors gracefully (invalid JSON, incomplete rubric, etc.)

**User Experience:**
- Show preview/diff of proposed changes before applying
- Allow user to accept, reject, or further modify AI suggestions
- Maintain conversation context during editing session
- Show loading state during LLM processing

**Validation:**
- Validate LLM output against rubric JSON schema
- Ensure all required fields present
- Check for unique IDs
- Verify scoring consistency
- Reject invalid responses with clear error messages

---

## 10. Export Formats

### 10.1 JSON Export

**Purpose:** Backup, sharing, programmatic access

**Format:** Exact rubric JSON structure

**Filename Convention:** `{slug-from-title}-{timestamp}.json`

**Example:** `essay-writing-rubric-20251013.json`

### 10.2 Markdown Export

**Purpose:** Course documentation, printing, LMS integration

**Structure:**
```markdown
# {Rubric Title}

**Description:** {description}

**Subject:** {subject}  
**Grade Level:** {gradeLevel}  
**Scoring Type:** {scoringType}  
**Maximum Score:** {maxScore}

---

## Criteria and Performance Levels

| Criterion | {Level 1 Label} ({score}) | {Level 2 Label} ({score}) | ... |
|-----------|---------------------------|---------------------------|-----|
| **{Criterion Name}** ({weight} pts)<br>{criterion description} | {level description} | {level description} | ... |

---

*Created: {createdAt}*  
*Last Modified: {modifiedAt}*
```

**Filename Convention:** `{slug-from-title}-{timestamp}.md`

**Example:** `essay-writing-rubric-20251013.md`

### 10.3 Import Format

**JSON Import:**
- Accept JSON files with valid rubric structure
- Validate against schema before import
- Generate new `rubric_id` for imported rubric
- Set imported rubric as private by default
- Import creates new rubric (does not overwrite existing)
- Support drag-and-drop file upload in UI

**Error Handling:**
- Invalid JSON: Show parse error with line number
- Schema validation failure: Show specific validation errors
- Missing required fields: List missing fields
- Provide example of valid format

### 10.4 Future Export/Import Formats

**Phase 2+:**
- PDF export (formatted for printing)
- CSV export (spreadsheet-compatible)
- HTML export (embeddable in web pages)
- Common Cartridge format (for LMS integration)
- Import from CSV/Excel
- Import from Word tables

---

## 11. Implementation Plan

### 11.1 Phase 1: Core Rubric Management (MVP)

**Goal:** Basic CRUD operations for rubrics

#### 11.1.1 Backend Tasks

1. **Database Schema** (2 hours)
   - Create rubrics table migration
   - Add table to database initialization
   - Test table creation

2. **Database Manager** (4 hours)
   - Implement `RubricDatabaseManager` class
   - Implement all CRUD methods
   - Add unit tests

3. **Validation Module** (3 hours)
   - Implement `rubric_validator.py`
   - Add validation functions
   - Add validation tests

4. **LAMB Core API** (4 hours)
   - Create `/backend/lamb/evaluaitor/rubrics.py`
   - Implement all CRUD endpoints
   - Add error handling

5. **Creator Interface Router** (3 hours)
   - Create `/backend/creator_interface/evaluaitor_router.py`
   - Implement proxy endpoints
   - Add authentication/authorization

6. **Export Functionality** (4 hours)
   - Implement JSON export
   - Implement Markdown export
   - Add export endpoints
   - Test download functionality

**Backend Subtotal:** ~20 hours

#### 11.1.2 Frontend Tasks

9. **Services Layer** (5 hours)
   - Implement `rubricService.js`
   - Add all API client functions (CRUD, import/export, AI, visibility)
   - Add file upload handling
   - Add error handling

10. **Store Implementation** (5 hours)
    - Implement `rubricStore.svelte.js`
    - Add state management with Svelte 5 runes
    - Add undo/redo functionality
    - Add visibility toggle support

11. **Rubrics List View** (6 hours)
    - Create `RubricsList.svelte` with tabs (My Rubrics / Templates)
    - Create `RubricTemplateCard.svelte` for template display
    - Implement list rendering with visibility badges
    - Add pagination
    - Add search/filter
    - Add showcase indicators

12. **Rubric Editor - Basic** (8 hours)
    - Create `RubricEditor.svelte`
    - Create `RubricTable.svelte`
    - Create `RubricMetadataForm.svelte`
    - Implement basic editing
    - Add visibility toggle

13. **Rubric Editor - Advanced** (6 hours)
    - Implement inline cell editing
    - Add/remove criteria
    - Add/remove levels
    - Validation and save
    - "Save as New Version" button

14. **AI Chat Interface** (8 hours)
    - Create `RubricAIChat.svelte`
    - Create `RubricChangePreview.svelte`
    - Implement chat UI with message history
    - Implement AI generation from scratch
    - Implement AI modification of existing rubric
    - Show diff/preview of changes
    - Accept/reject functionality

15. **Import/Export UI** (4 hours)
    - Create `RubricExportModal.svelte`
    - Implement import file upload (drag-and-drop)
    - Implement JSON export download
    - Implement Markdown export download
    - Add export/import buttons
    - Error handling for invalid imports

16. **Navigation & Routing** (2 hours)
    - Add "Evaluaitor" to navigation
    - Create routes
    - Add route guards

17. **Styling & Polish** (5 hours)
    - Apply TailwindCSS styles
    - Responsive design
    - Icons and visual feedback
    - Loading states
    - Animations for chat interface
    - Showcase badge styling

**Frontend Subtotal:** ~49 hours

#### 11.1.3 Testing & Documentation

18. **Backend Testing** (6 hours)
    - Unit tests for database manager
    - API endpoint tests
    - Validation tests
    - AI integration tests (mocked LLM responses)
    - Import validation tests

19. **Frontend Testing** (5 hours)
    - Component tests
    - Store tests
    - Integration tests
    - E2E tests (Playwright) for full workflow

20. **Documentation** (4 hours)
    - API documentation
    - User guide for AI features
    - Developer notes
    - Rubric JSON schema documentation

**Testing/Docs Subtotal:** ~15 hours

**Phase 1 Total:** ~92 hours

### 11.2 Phase 2: Enhanced Features (Future)

**Goal:** Advanced features and integrations

**Features:**
- PDF export with professional formatting
- Streaming AI responses for better UX
- Conversation history for AI chat sessions
- Rubric analytics (usage stats, popular templates)
- Full versioning with history view and rollback
- Collaborative editing (real-time)
- Link rubrics to assistants
- Standards alignment (Common Core, state standards)

**Estimated:** 50-70 hours additional

### 11.3 Phase 3: Grading Integration (Future)

**Goal:** Use rubrics to evaluate student work

**Features:**
- Store evaluation results
- Link rubrics to assignments
- AI-assisted grading using rubric criteria
- Student feedback generation
- Analytics and reporting

**Estimated:** 80-120 hours additional

### 11.4 Implementation Order (Recommended)

**Sprint 1: Backend Foundation (Week 1)**
1. Database schema and migrations
2. Backend database manager (all methods)
3. Backend validation module

**Sprint 2: Backend API (Week 2)**
4. LAMB Core API - CRUD endpoints
5. LAMB Core API - visibility and showcase
6. LAMB Core API - import/export
7. Creator Interface router (basic proxying)

**Sprint 3: Backend AI Integration (Week 2-3)**
8. LAMB Core API - AI generation
9. LAMB Core API - AI modification
10. Creator Interface - AI endpoint proxying
11. Backend testing

**Sprint 4: Frontend Foundation (Week 3-4)**
12. Frontend services layer (all API functions)
13. Frontend store implementation
14. Navigation and routing
15. Rubrics list view (basic)

**Sprint 5: Frontend Editor (Week 4-5)**
16. Rubric editor - basic functionality
17. Rubric editor - advanced features (add/remove criteria/levels)
18. Import/export UI

**Sprint 6: Frontend AI & Polish (Week 5-6)**
19. AI chat interface
20. Change preview and accept/reject
21. Template gallery view
22. Styling and polish
23. Frontend testing

**Sprint 7: Integration & Documentation (Week 6)**
24. End-to-end testing
25. Bug fixes
26. Documentation
27. User guide

**Total: 6-7 weeks for full Phase 1 implementation**

---

## 12. Future Enhancements

### 12.1 Near-Term (3-6 months)

1. **Enhanced AI Features**
   - Streaming responses
   - Conversation history
   - AI suggestions based on common patterns
   - Standards-aligned rubric generation

2. **Advanced Search & Discovery**
   - Full-text search across rubrics
   - Advanced filters (date range, author, tags, standards)
   - Saved searches
   - Recommended templates based on usage

3. **Import/Export Enhancements**
   - Import from CSV, Excel, Word tables
   - PDF export with professional formatting
   - Print-friendly view
   - Batch export/import

4. **Analytics**
   - Rubric usage statistics
   - Most popular templates
   - Clone/usage tracking
   - User engagement metrics

### 12.2 Mid-Term (6-12 months)

5. **Enhanced Versioning**
   - Full version history with diffs
   - Rollback to any previous version
   - Compare versions side-by-side
   - Version branching

6. **Collaborative Features**
   - Real-time collaborative editing
   - Comments and suggestions
   - Change tracking and approval workflows
   - Shared editing sessions

7. **Assistant Integration**
   - Link rubrics to learning assistants
   - Use rubrics for AI-assisted grading
   - Automatic feedback generation
   - RAG integration for rubric-aware responses

### 12.3 Long-Term (12+ months)

9. **Analytics & Reporting**
   - Rubric usage statistics
   - Inter-rater reliability analysis
   - Performance trends

10. **Advanced Rubric Types**
    - Standards-aligned rubrics
    - Competency-based rubrics
    - Portfolio assessment rubrics

11. **LMS Deep Integration**
    - Direct LMS gradebook integration
    - Assignment-rubric linking in LMS
    - LTI rubric service

12. **AI Grading Engine**
    - Automated scoring of student work
    - Confidence scores
    - Human review workflow

---

## 13. Questions Answered & Design Decisions

### 13.1 Scope & Permissions ✅

**Q1:** Should rubrics be organization-scoped (like assistants) or purely user-scoped?
- **DECISION:** Organization-scoped with ownership. Org admins can mark rubrics as "showcase" templates.

**Q2:** Should organization admins be able to view/edit rubrics from users in their organization?
- **DECISION:** Org admins can view public rubrics and mark them as showcase. Users' rubrics are private by default unless made public.

**Q3:** Should system admins have full access to all rubrics?
- **DECISION:** Yes, for support and maintenance purposes.

### 13.2 Features & Priorities ✅

**Q4:** Should AI-assisted editing be in Phase 1 (MVP) or Phase 2?
- **DECISION:** Phase 1 (MVP) - Core feature for differentiation. Users can chat with LLM to create and modify rubrics.

**Q5:** Should rubrics have templates/starters in Phase 1?
- **DECISION:** Yes - any accessible rubric (user's own or public rubrics) can be used as a template.

**Q6:** Should rubrics be shareable/publishable like assistants?
- **DECISION:** Yes, Phase 1 - users can make rubrics public within their organization.

### 13.3 Technical Decisions ✅

**Q7:** File/module naming: "evaluaitor" (with typo) or "evaluator" (correct spelling)?
- **DECISION:** "evaluaitor" is intentional (internal pun) - use throughout codebase.

**Q8:** Should rubric versioning be built into Phase 1 database schema?
- **DECISION:** Add `parent_rubric_id` to track lineage. User explicitly clicks "Save as New Version" to create new rubric.

**Q9:** Should duplicate operation create full copy or linked reference?
- **DECISION:** Full copy with new rubric_id, optionally track parent via parent_rubric_id.

**Q10:** Should we validate uniqueness of rubric titles per user?
- **DECISION:** No, allow duplicate titles (use rubric_id as unique key).

### 13.4 Integration Questions ✅

**Q11:** Should rubrics be linkable to assistants in the database schema?
- **DECISION:** Not in Phase 1. JSON/MD exports will support future RAG integration, but don't plan for it yet.

**Q12:** Should rubrics be exportable via the existing `/v1/models` endpoint?
- **DECISION:** No, keep rubrics separate from assistant/model concept.

**Q13:** Should rubric operations be logged in the usage_logs table?
- **DECISION:** Not in Phase 1. Can add in Phase 2 for analytics.

**Q14:** PDF export?
- **DECISION:** No PDF export in Phase 1. JSON and Markdown only.

**Q15:** Import functionality?
- **DECISION:** Yes, Phase 1 - Import rubrics from JSON format with validation.

**Q16:** Evaluation records storage?
- **DECISION:** Not at this point. Only rubric templates, not applied evaluations.

---

## Appendices

### Appendix A: Rubric JSON Schema (JSON Schema Format)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["rubricId", "title", "description", "metadata", "criteria", "scoringType", "maxScore"],
  "properties": {
    "rubricId": {
      "type": "string",
      "description": "Unique identifier for the rubric"
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "maxLength": 200
    },
    "description": {
      "type": "string",
      "maxLength": 2000
    },
    "metadata": {
      "type": "object",
      "required": ["subject", "gradeLevel", "createdAt", "modifiedAt"],
      "properties": {
        "subject": {"type": "string"},
        "gradeLevel": {"type": "string"},
        "createdAt": {"type": "string", "format": "date-time"},
        "modifiedAt": {"type": "string", "format": "date-time"},
        "author": {"type": "string"},
        "version": {"type": "string"},
        "tags": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "criteria": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "name", "description", "weight", "levels"],
        "properties": {
          "id": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string"},
          "weight": {"type": "number", "minimum": 0},
          "order": {"type": "number", "minimum": 0},
          "levels": {
            "type": "array",
            "minItems": 2,
            "items": {
              "type": "object",
              "required": ["id", "score", "label", "description"],
              "properties": {
                "id": {"type": "string"},
                "score": {"type": "number"},
                "label": {"type": "string"},
                "description": {"type": "string"},
                "order": {"type": "number", "minimum": 0}
              }
            }
          }
        }
      }
    },
    "scoringType": {
      "type": "string",
      "enum": ["points", "percentage", "holistic", "single-point", "checklist"]
    },
    "maxScore": {
      "type": "number",
      "minimum": 0
    }
  }
}
```

### Appendix B: Example Markdown Export

See Section 10.2 for full example.

### Appendix C: Database Migration Script

```python
def create_rubrics_table(cursor, table_prefix=""):
    """Create rubrics table in LAMB database"""
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_prefix}rubrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric_id TEXT UNIQUE NOT NULL,
            organization_id INTEGER NOT NULL,
            owner_email TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            rubric_data JSON NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES {table_prefix}organizations(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_rubrics_owner 
        ON {table_prefix}rubrics(owner_email)
    """)
    
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_rubrics_org 
        ON {table_prefix}rubrics(organization_id)
    """)
    
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_rubrics_rubric_id 
        ON {table_prefix}rubrics(rubric_id)
    """)
```

---

**Document Status:** Ready for Review  
**Next Steps:** 
1. Review and answer open questions
2. Approve implementation plan
3. Begin Phase 1 development

**Revision History:**
- v1.0 (2025-10-13): Initial draft


