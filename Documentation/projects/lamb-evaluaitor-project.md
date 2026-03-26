# LAMB Evaluaitor Project Proposal

---

## 0. Product Requirements Document (PRD)

### 0.1 Product Vision

**Evaluaitor** is a dedicated microservice that provides AI-powered automatic evaluation of educational tasks within the LAMB ecosystem. It enables institutions to leverage sophisticated AI evaluation strategies without coupling evaluation logic to LMS integration code.

**Vision Statement:** *"Enable any educational platform to access powerful, extensible AI evaluation capabilities through a simple, reliable API."*

### 0.2 Goals & Objectives

| Goal | Objective | Metric |
|------|-----------|--------|
| **Decouple evaluation from LMS** | Extract evaluation logic from LAMBA into a dedicated service | LAMBA evaluation code reduced by 80% |
| **Enable extensibility** | Support multiple evaluation strategies via plugins | MVP: 1 plugin, Architecture supports N plugins |
| **Provide reliability** | Async job processing with status tracking | 99.9% job completion rate |
| **Support multi-tenancy** | Organization-level isolation following LAMB patterns | Full data isolation per organization |
| **Enable analytics** | Store evaluation results for future analysis | All evaluations persisted with metadata |

### 0.3 Target Users

| User Type | Description | Primary Interaction |
|-----------|-------------|---------------------|
| **LAMBA (System)** | LTI Tool Provider for Moodle | API client - submits jobs, retrieves results |
| **LAMB Admins** | Organization administrators | Configure evaluation setups via LAMB UI |
| **Future: Other LTI Tools** | Third-party educational platforms | API client |

**Note:** Evaluaitor has no direct end-user interface. Teachers and students interact via LAMBA's UI.

### 0.4 User Stories

#### LAMBA Integration (MVP)

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-01 | LAMBA system | submit a student file for evaluation | I can offload AI processing |
| US-02 | LAMBA system | receive a job code immediately | I don't block on long evaluations |
| US-03 | LAMBA system | check evaluation status | I can show progress to teachers |
| US-04 | LAMBA system | retrieve evaluation results | I can display scores and feedback |
| US-05 | LAMBA system | include my submission ID as reference | I can correlate results with my data |

#### Organization Management

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-06 | LAMB system | register organizations in Evaluaitor | evaluations are properly isolated |
| US-07 | LAMB admin | see evaluation statistics per org | I can monitor usage |

#### Plugin System (Extensibility)

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-08 | Developer | list available evaluation plugins | I know what strategies are supported |
| US-09 | LAMBA system | specify which plugin to use | I can choose the evaluation strategy |
| US-10 | Developer | add new evaluation plugins | I can extend capabilities |

### 0.5 Scope

#### In Scope (MVP)

- [x] REST API for job submission, status, and result retrieval
- [x] Async job processing with background tasks
- [x] Multi-tenant organization support
- [x] Plugin architecture for evaluation strategies
- [x] MVP plugin: `rubric_eval` (uses LAMB assistants)
- [x] Document extraction: PDF, DOCX, TXT, code files
- [x] Result storage in SQLite
- [x] Bearer token authentication
- [x] Docker container integration

#### Out of Scope (Future)

- [ ] Web UI (managed via LAMB)
- [ ] Batch evaluation (multiple files per request)
- [ ] Webhooks/callbacks to LAMBA
- [ ] Advanced plugins (`code_judge`, `agentic_eval`)
- [ ] Analytics dashboard
- [ ] Result caching for re-evaluation
- [ ] Automatic retry on failures

### 0.6 Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| **LAMB Backend** | Required | Provides AI assistants via `/v1/chat/completions` |
| **LAMBA** | Client | Primary consumer of Evaluaitor API |
| **Docker** | Infrastructure | Container orchestration |
| **SQLite** | Database | Job and result storage |

### 0.7 Assumptions & Constraints

#### Assumptions

1. LAMB assistants are pre-configured with appropriate rubrics/prompts
2. LAMBA handles all LTI/Moodle complexity; Evaluaitor only sees files
3. One evaluation per job (no batch processing in MVP)
4. Polling-based status checks (no webhooks in MVP)

#### Constraints

1. Must follow LAMB ecosystem patterns (kb-server architecture)
2. Must support existing LAMBA evaluation flow (backward compatible scoring)
3. Single API key authentication (like kb-server)
4. No direct database access to LAMB (API-only integration)

### 0.8 Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| LAMBA can submit evaluations | 100% | Integration test passes |
| Evaluations complete successfully | >95% | Job completion rate |
| Score extraction works | >90% | Scores parsed correctly |
| API response time (submit) | <500ms | P95 latency |
| API response time (status/result) | <200ms | P95 latency |
| Multi-tenant isolation | 100% | Security audit |

### 0.9 Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LAMB API unavailable | High | Low | Retry with backoff, clear error messages |
| Large files cause timeouts | Medium | Medium | File size limits, async processing |
| Score parsing fails | Medium | Medium | Store raw response, manual review possible |
| Plugin complexity grows | Low | Medium | Clear plugin interface, documentation |

---

## 1. Project Title

**"Evaluaitor: Extensible AI-Powered Evaluation Microservice for the LAMB Educational Platform"**

### 1.1 Abstract

Evaluaitor is a new microservice in the LAMB ecosystem designed to provide AI-enhanced automatic evaluation of educational tasks. It follows the architectural patterns established by `lamb-kb-server`: a headless FastAPI service with plugin-based extensibility, asynchronous job processing, and multi-tenant organization support. The primary client is LAMBA (the LTI Tool Provider for Moodle), which offloads evaluation processing to Evaluaitor while maintaining its role as the LMS integration layer. Evaluaitor uses LAMB's AI assistants via the OpenAI-compatible completions API to perform evaluations, creating a clean separation of concerns: LAMBA handles LTI/student interaction, Evaluaitor handles evaluation orchestration, and LAMB provides AI capabilities.

---

## 2. Project Description

### 2.1 Context

The LAMB ecosystem currently consists of:

| Component | Purpose | Port |
|-----------|---------|------|
| **LAMB** | Multi-tenant AI assistant platform with completions API | 9099 |
| **lamb-kb-server** | Knowledge base management with RAG support | 9090 |
| **Open WebUI** | Chat interface for end users | 8080 |
| **LAMBA** | LTI 1.1 Tool Provider for Moodle integration | (external) |

LAMBA currently handles AI evaluation internally by:
1. Extracting text from student submissions (PDF, DOCX, etc.)
2. Calling LAMB's `/chat/completions` with an assistant/rubric
3. Parsing responses to extract scores using regex patterns
4. Storing results in its own database

This approach has limitations:
- Evaluation logic is tightly coupled with LTI handling
- No separation between submission management and evaluation processing
- Difficult to implement advanced evaluation strategies (agentic, multi-step)
- No centralized evaluation analytics
- Each evaluation strategy requires changes to LAMBA's codebase

### 2.2 Problem Statement

**Current LAMBA Evaluation Flow (Problematic):**

```
┌─────────────────────────────────────────────────────────────────┐
│                         LAMBA                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────┐                                          │
│   │ LTI Integration  │  ← Core responsibility                   │
│   │ Student UI       │                                          │
│   │ Teacher UI       │                                          │
│   └────────┬─────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │ File Extraction  │  ← Should be delegated                   │
│   │ (PDF, DOCX, TXT) │                                          │
│   └────────┬─────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │ LAMB API Call    │  ← Should be delegated                   │
│   │ (completions)    │                                          │
│   └────────┬─────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │ Score Parsing    │  ← Should be delegated                   │
│   │ (regex-based)    │                                          │
│   └──────────────────┘                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Issues:**

| Problem | Impact |
|---------|--------|
| Coupled evaluation logic | Changes to evaluation require LAMBA updates |
| No plugin system | New evaluation strategies need code changes |
| No centralized storage | Analytics requires accessing LAMBA's database |
| Synchronous-ish processing | Timeouts managed by LAMBA |
| Single evaluation strategy | Only rubric-based evaluation supported |

### 2.3 Proposed Solution

**Evaluaitor as Dedicated Evaluation Service:**

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│     LAMBA       │      │   Evaluaitor    │      │      LAMB       │
│                 │      │                 │      │                 │
│ LTI Integration │      │ Job Management  │      │ AI Assistants   │
│ Student/Teacher │─────►│ Plugin System   │─────►│ Completions API │
│ UI              │      │ Result Storage  │      │ Rubrics         │
│                 │◄─────│                 │◄─────│                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
     (B)                       (C)                      (A)

  A <-> C <- B
```

**Clean Separation:**
- **LAMBA (B)**: LTI/Moodle integration, student submission, teacher grading UI
- **Evaluaitor (C)**: Evaluation orchestration, job management, result storage
- **LAMB (A)**: AI capabilities via assistants and completions API

---

## 3. Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        evaluaitor (Port 9091)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Application                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │   │
│  │  │   System    │  │ Evaluations │  │    Jobs     │  │  Plugins   │   │   │
│  │  │   Router    │  │   Router    │  │   Router    │  │  Router    │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                          Service Layer                               │   │
│  │  ┌──────────────────┐  ┌────────┴────────┐  ┌─────────────────────┐  │   │
│  │  │EvaluationsService│  │   JobsService   │  │   PluginOrchestrator│  │   │
│  │  └──────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                          Plugin System                               │   │
│  │  ┌──────────────────┐  ┌────────────────┐  ┌─────────────────────┐  │   │
│  │  │ rubric_eval      │  │ code_judge     │  │ agentic_eval        │  │   │
│  │  │ (MVP)            │  │ (future)       │  │ (future)            │  │   │
│  │  └──────────────────┘  └────────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                    Background Job Processing                         │   │
│  │  ┌──────────────────┐  ┌────────────────┐  ┌─────────────────────┐  │   │
│  │  │ Job Queue        │  │ Status Tracker │  │ Result Storage      │  │   │
│  │  │ (BackgroundTasks)│  │                │  │                     │  │   │
│  │  └──────────────────┘  └────────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────┐     ┌─────────────────┐    ┌───────────────────┐     │
│  │     SQLite       │     │   File Storage  │    │  LAMB API Client  │     │
│  │ (Jobs/Results)   │     │  (Submissions)  │    │  (Completions)    │     │
│  │ evaluaitor.db    │     │  static/        │    │                   │     │
│  └──────────────────┘     └─────────────────┘    └───────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Request Flow

```
LAMBA                          Evaluaitor                         LAMB
  │                                │                                │
  │ POST /evaluations              │                                │
  │ {evaluator_id, file}           │                                │
  │───────────────────────────────►│                                │
  │                                │                                │
  │ {job_code: "abc123"}           │                                │
  │◄───────────────────────────────│                                │
  │                                │                                │
  │                                │  Background Processing:        │
  │                                │  1. Store file                 │
  │                                │  2. Load plugin                │
  │                                │  3. Extract text               │
  │                                │                                │
  │                                │  POST /v1/chat/completions     │
  │                                │  {model: "lamb_assistant.X"}   │
  │                                │───────────────────────────────►│
  │                                │                                │
  │                                │  {content: "NOTA FINAL: 8.5"}  │
  │                                │◄───────────────────────────────│
  │                                │                                │
  │                                │  4. Parse response             │
  │                                │  5. Store result               │
  │                                │  6. Update status              │
  │                                │                                │
  │ GET /evaluations/abc123/status │                                │
  │───────────────────────────────►│                                │
  │                                │                                │
  │ {status: "completed"}          │                                │
  │◄───────────────────────────────│                                │
  │                                │                                │
  │ GET /evaluations/abc123/result │                                │
  │───────────────────────────────►│                                │
  │                                │                                │
  │ {score: 8.5, feedback: "..."}  │                                │
  │◄───────────────────────────────│                                │
```

### 3.3 Directory Structure

```
evaluaitor/
├── backend/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Environment configuration
│   ├── dependencies.py              # Auth & dependency injection
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # SQLite connection management
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── service.py               # Low-level data operations
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── system.py                # Health, status endpoints
│   │   ├── evaluations.py           # Evaluation CRUD & job submission
│   │   ├── organizations.py         # Organization management (multi-tenant)
│   │   └── plugins.py               # Plugin listing & info
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── evaluations.py           # Evaluation business logic
│   │   ├── jobs.py                  # Job queue management
│   │   └── lamb_client.py           # LAMB API client
│   │
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── base.py                  # Plugin base classes & registry
│   │   └── rubric_eval.py           # MVP: Rubric-based evaluation
│   │
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py                  # Extractor interface
│   │   ├── pdf.py                   # PDF text extraction
│   │   ├── docx.py                  # Word document extraction
│   │   └── text.py                  # Plain text handling
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── evaluation.py            # Evaluation request/response models
│   │   ├── job.py                   # Job status models
│   │   ├── organization.py          # Organization models
│   │   └── system.py                # System response models
│   │
│   ├── static/                      # Uploaded submission files
│   │   └── {org_id}/
│   │       └── {job_code}/
│   │           └── submission.{ext}
│   │
│   ├── data/
│   │   └── evaluaitor.db            # SQLite database
│   │
│   ├── requirements.txt
│   └── .env.example
│
└── Docs/
    └── evaluaitor_architecture.md
```

---

## 4. Data Model

### 4.1 Database Schema

Following the multi-tenant pattern from [kb-server refactoring design](https://github.com/Lamb-Project/lamb/issues/203):

```sql
-- ═══════════════════════════════════════════════════════════════
-- Organizations (synced from LAMB)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,      -- LAMB organization ID/slug
    name TEXT NOT NULL,
    config JSON,                            -- Org-specific settings
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_external_id ON organizations(external_id);


-- ═══════════════════════════════════════════════════════════════
-- Evaluation Jobs
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE evaluation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_code TEXT NOT NULL UNIQUE,          -- UUID for external reference
    organization_id INTEGER NOT NULL,
    
    -- Evaluation Configuration
    evaluator_id TEXT NOT NULL,             -- LAMB assistant ID
    plugin_name TEXT NOT NULL DEFAULT 'rubric_eval',
    plugin_params JSON,                     -- Plugin-specific parameters
    
    -- Submission File
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,                -- Path in static/
    file_size INTEGER,
    content_type TEXT,
    
    -- Job Status
    status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed, cancelled
    
    -- Progress Tracking
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    progress_message TEXT,
    
    -- Timing
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_started_at DATETIME,
    processing_completed_at DATETIME,
    
    -- Error Handling
    error_message TEXT,
    error_details JSON,
    
    -- Metadata
    client_reference TEXT,                  -- Optional: LAMBA submission ID
    metadata JSON,                          -- Extensible metadata
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_jobs_code ON evaluation_jobs(job_code);
CREATE INDEX idx_jobs_org ON evaluation_jobs(organization_id);
CREATE INDEX idx_jobs_status ON evaluation_jobs(status);
CREATE INDEX idx_jobs_created ON evaluation_jobs(created_at);


-- ═══════════════════════════════════════════════════════════════
-- Evaluation Results
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL UNIQUE,         -- One result per job
    
    -- Evaluation Output
    score REAL,                             -- Numeric score (e.g., 0-10)
    score_normalized REAL,                  -- Normalized to 0-1 for LTI
    max_score REAL DEFAULT 10.0,            -- Maximum possible score
    
    -- Feedback
    feedback TEXT,                          -- AI-generated feedback
    feedback_structured JSON,               -- Structured feedback (rubric criteria)
    
    -- Raw Response
    raw_response TEXT,                      -- Full LLM response for debugging
    
    -- Metadata
    model_used TEXT,                        -- Which LAMB assistant/model
    tokens_used INTEGER,                    -- Token consumption
    processing_time_ms INTEGER,             -- Time taken
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES evaluation_jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_results_job ON evaluation_results(job_id);


-- ═══════════════════════════════════════════════════════════════
-- Extracted Content (cached)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE extracted_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    
    -- Extracted Data
    content_text TEXT,                      -- Full extracted text
    content_preview TEXT,                   -- First N characters
    extraction_method TEXT,                 -- pdf, docx, plain, etc.
    
    -- Metadata
    page_count INTEGER,
    word_count INTEGER,
    char_count INTEGER,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES evaluation_jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_extracted_job ON extracted_content(job_id);
```

### 4.2 Job Status Enum

```python
class JobStatus(str, Enum):
    PENDING = "pending"          # Job created, waiting to process
    PROCESSING = "processing"    # Currently being evaluated
    COMPLETED = "completed"      # Successfully evaluated
    FAILED = "failed"            # Evaluation failed
    CANCELLED = "cancelled"      # Cancelled by user
```

### 4.3 Entity Relationships

```
┌──────────────────┐
│   Organization   │  (synced from LAMB)
│                  │
│ - external_id    │
│ - name           │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────▼─────────┐
│ Evaluation Job   │  (created by LAMBA)
│                  │
│ - job_code       │
│ - evaluator_id   │
│ - status         │
│ - file_path      │
└────────┬─────────┘
         │ 1
         │
         │ 1
┌────────▼─────────┐
│ Evaluation Result│  (created by plugin)
│                  │
│ - score          │
│ - feedback       │
│ - raw_response   │
└──────────────────┘
```

---

## 5. API Reference

### 5.1 System Endpoints

#### Health Check (No Auth Required)
```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "service": "evaluaitor"
}
```

#### Database Status
```http
GET /database/status
Authorization: Bearer {token}
```

**Response:**
```json
{
  "sqlite_status": {
    "initialized": true,
    "schema_valid": true
  },
  "jobs_count": 1234,
  "pending_jobs": 5,
  "organizations_count": 3
}
```

### 5.2 Organization Endpoints

Following the kb-server pattern:

#### Register/Update Organization
```http
POST /organizations
Authorization: Bearer {token}
Content-Type: application/json
```

**Request:**
```json
{
  "external_id": "org_123",
  "name": "University of Example"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "external_id": "org_123",
  "name": "University of Example",
  "created_at": "2026-01-25T10:00:00Z"
}
```

#### Get Organization
```http
GET /organizations/{external_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": 1,
  "external_id": "org_123",
  "name": "University of Example",
  "jobs_count": 1234,
  "pending_jobs": 5
}
```

### 5.3 Evaluation Endpoints

#### Submit Evaluation Job
```http
POST /evaluations
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Submission file to evaluate |
| `organization_external_id` | string | Yes | Organization ID from LAMB |
| `evaluator_id` | string | Yes | LAMB assistant ID to use |
| `plugin_name` | string | No | Evaluation plugin (default: `rubric_eval`) |
| `plugin_params` | JSON string | No | Plugin-specific parameters |
| `client_reference` | string | No | LAMBA's submission ID for correlation |
| `metadata` | JSON string | No | Additional metadata |

**Example:**
```bash
curl -X POST 'http://localhost:9091/evaluations' \
  -H 'Authorization: Bearer $TOKEN' \
  -F 'file=@student_work.pdf' \
  -F 'organization_external_id=org_123' \
  -F 'evaluator_id=lamb_assistant.eval_python_101' \
  -F 'plugin_name=rubric_eval' \
  -F 'client_reference=submission_456'
```

**Response (202 Accepted):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "pending",
  "message": "Evaluation job queued successfully",
  "created_at": "2026-01-25T10:30:00Z"
}
```

#### Get Evaluation Status
```http
GET /evaluations/{job_code}/status
Authorization: Bearer {token}
```

**Response (Processing):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "processing",
  "progress": {
    "current": 1,
    "total": 3,
    "percentage": 33.3,
    "message": "Extracting text from document..."
  },
  "created_at": "2026-01-25T10:30:00Z",
  "processing_started_at": "2026-01-25T10:30:05Z"
}
```

**Response (Completed):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "completed",
  "progress": {
    "current": 3,
    "total": 3,
    "percentage": 100.0,
    "message": "Evaluation completed"
  },
  "created_at": "2026-01-25T10:30:00Z",
  "processing_started_at": "2026-01-25T10:30:05Z",
  "processing_completed_at": "2026-01-25T10:31:15Z",
  "processing_duration_seconds": 70.0
}
```

**Response (Failed):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "failed",
  "error_message": "Failed to extract text from PDF",
  "error_details": {
    "exception_type": "ExtractionError",
    "file_type": "application/pdf"
  },
  "created_at": "2026-01-25T10:30:00Z",
  "processing_started_at": "2026-01-25T10:30:05Z",
  "processing_completed_at": "2026-01-25T10:30:10Z"
}
```

#### Get Evaluation Result
```http
GET /evaluations/{job_code}/result
Authorization: Bearer {token}
```

**Response (Success):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "completed",
  "result": {
    "score": 8.5,
    "score_normalized": 0.85,
    "max_score": 10.0,
    "feedback": "Excellent work on the algorithm implementation. The code is well-structured and follows best practices. Minor improvements could be made in error handling.",
    "feedback_structured": {
      "criteria": [
        {
          "name": "Code Structure",
          "score": 9,
          "max_score": 10,
          "comment": "Well-organized code with clear function separation"
        },
        {
          "name": "Algorithm Correctness",
          "score": 8,
          "max_score": 10,
          "comment": "Correct implementation with minor edge case issues"
        }
      ]
    },
    "model_used": "lamb_assistant.eval_python_101",
    "processing_time_ms": 70123
  },
  "client_reference": "submission_456"
}
```

**Response (Not Ready):**
```json
{
  "job_code": "ev_abc123def456",
  "status": "processing",
  "result": null,
  "message": "Evaluation still in progress"
}
```

#### List Evaluation Jobs
```http
GET /evaluations?organization_external_id={org_id}&status={status}&limit={limit}&offset={offset}
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `organization_external_id` | string | Required | Filter by organization |
| `status` | string | - | Filter by status |
| `limit` | int | 50 | Max results (1-200) |
| `offset` | int | 0 | Pagination offset |
| `sort_by` | string | `created_at` | Sort field |
| `sort_order` | string | `desc` | Sort order |

**Response:**
```json
{
  "total": 150,
  "items": [
    {
      "job_code": "ev_abc123def456",
      "evaluator_id": "lamb_assistant.eval_python_101",
      "plugin_name": "rubric_eval",
      "status": "completed",
      "original_filename": "student_work.pdf",
      "created_at": "2026-01-25T10:30:00Z",
      "processing_completed_at": "2026-01-25T10:31:15Z",
      "client_reference": "submission_456"
    }
  ]
}
```

#### Cancel Evaluation Job
```http
POST /evaluations/{job_code}/cancel
Authorization: Bearer {token}
```

**Response:**
```json
{
  "job_code": "ev_abc123def456",
  "status": "cancelled",
  "message": "Job cancelled successfully"
}
```

### 5.4 Plugin Endpoints

#### List Available Plugins
```http
GET /plugins
Authorization: Bearer {token}
```

**Response:**
```json
{
  "plugins": [
    {
      "name": "rubric_eval",
      "description": "Rubric-based evaluation using LAMB AI assistants",
      "version": "1.0.0",
      "supported_file_types": ["pdf", "docx", "doc", "txt", "md"],
      "parameters": {
        "timeout_seconds": {
          "type": "integer",
          "default": 120,
          "description": "Maximum time for LLM response"
        }
      }
    }
  ]
}
```

---

## 6. Plugin System

### 6.1 Plugin Architecture

Following the kb-server pattern:

```python
# plugins/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class EvaluationInput:
    """Input data for evaluation plugins."""
    job_id: int
    job_code: str
    evaluator_id: str
    extracted_text: str
    file_path: str
    original_filename: str
    organization_id: int
    metadata: Dict[str, Any]

@dataclass
class EvaluationOutput:
    """Output from evaluation plugins."""
    score: Optional[float]
    score_normalized: Optional[float]
    max_score: float
    feedback: str
    feedback_structured: Optional[Dict[str, Any]]
    raw_response: str
    model_used: str
    tokens_used: Optional[int]

class EvaluationPlugin(ABC):
    """Base class for evaluation plugins."""
    
    name: str = "base"
    description: str = "Base evaluation plugin"
    version: str = "1.0.0"
    supported_file_types: List[str] = []
    
    @abstractmethod
    async def evaluate(
        self, 
        input: EvaluationInput,
        progress_callback: Optional[callable] = None,
        **kwargs
    ) -> EvaluationOutput:
        """
        Perform evaluation.
        
        Args:
            input: Evaluation input data
            progress_callback: Optional callback for progress updates
                               callback(current: int, total: int, message: str)
            **kwargs: Plugin-specific parameters
            
        Returns:
            EvaluationOutput with score and feedback
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Return plugin parameter definitions."""
        pass
    
    def report_progress(
        self, 
        callback: Optional[callable],
        current: int, 
        total: int, 
        message: str
    ):
        """Helper to report progress if callback is available."""
        if callback:
            callback(current, total, message)


class PluginRegistry:
    """Registry for evaluation plugins."""
    
    _plugins: Dict[str, EvaluationPlugin] = {}
    
    @classmethod
    def register(cls, plugin_class):
        """Decorator to register a plugin."""
        instance = plugin_class()
        cls._plugins[instance.name] = instance
        return plugin_class
    
    @classmethod
    def get(cls, name: str) -> Optional[EvaluationPlugin]:
        """Get a plugin by name."""
        return cls._plugins.get(name)
    
    @classmethod
    def list_all(cls) -> List[EvaluationPlugin]:
        """List all registered plugins."""
        return list(cls._plugins.values())
```

### 6.2 MVP Plugin: rubric_eval

```python
# plugins/rubric_eval.py

import re
from typing import Dict, Any, Optional
from .base import EvaluationPlugin, EvaluationInput, EvaluationOutput, PluginRegistry
from services.lamb_client import LAMBClient

@PluginRegistry.register
class RubricEvalPlugin(EvaluationPlugin):
    """
    Rubric-based evaluation using LAMB AI assistants.
    
    This is the MVP plugin that replicates LAMBA's current evaluation flow:
    1. Send extracted text to LAMB assistant
    2. Parse response to extract score
    3. Return structured result
    """
    
    name = "rubric_eval"
    description = "Rubric-based evaluation using LAMB AI assistants"
    version = "1.0.0"
    supported_file_types = ["pdf", "docx", "doc", "txt", "md", "py", "java", "cpp", "js"]
    
    def __init__(self):
        self.lamb_client = LAMBClient()
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "timeout_seconds": {
                "type": "integer",
                "default": 120,
                "description": "Maximum time for LLM response"
            },
            "max_tokens": {
                "type": "integer", 
                "default": 4096,
                "description": "Maximum tokens in response"
            }
        }
    
    async def evaluate(
        self,
        input: EvaluationInput,
        progress_callback: Optional[callable] = None,
        **kwargs
    ) -> EvaluationOutput:
        timeout = kwargs.get("timeout_seconds", 120)
        max_tokens = kwargs.get("max_tokens", 4096)
        
        # Step 1: Prepare message for LAMB assistant
        self.report_progress(progress_callback, 1, 3, "Preparing evaluation request...")
        
        messages = [
            {
                "role": "user",
                "content": f"Evaluate the following student submission:\n\n{input.extracted_text}"
            }
        ]
        
        # Step 2: Call LAMB completions API
        self.report_progress(progress_callback, 2, 3, "Evaluating with AI assistant...")
        
        response = await self.lamb_client.chat_completion(
            model=input.evaluator_id,
            messages=messages,
            timeout=timeout,
            max_tokens=max_tokens
        )
        
        raw_response = response["choices"][0]["message"]["content"]
        tokens_used = response.get("usage", {}).get("total_tokens")
        
        # Step 3: Parse response to extract score
        self.report_progress(progress_callback, 3, 3, "Processing evaluation result...")
        
        score, feedback = self._extract_score_and_feedback(raw_response)
        
        return EvaluationOutput(
            score=score,
            score_normalized=score / 10.0 if score is not None else None,
            max_score=10.0,
            feedback=feedback,
            feedback_structured=None,  # Future: parse rubric criteria
            raw_response=raw_response,
            model_used=input.evaluator_id,
            tokens_used=tokens_used
        )
    
    def _extract_score_and_feedback(self, content: str) -> tuple[Optional[float], str]:
        """
        Extract score from LLM response using multiple patterns.
        
        Supports formats:
        - NOTA FINAL: X.X / FINAL SCORE: X.X
        - Nota: X.X, ## Nota: X.X, **Nota:** X.X
        - Score: X.X, Grade: X.X
        - X.X/10 at end of text
        """
        score = None
        
        # Pattern 1: NOTA FINAL / FINAL SCORE
        pattern1 = r'(?:NOTA\s*FINAL|FINAL\s*SCORE)\s*[:\s]*(\d+(?:[.,]\d+)?)'
        match = re.search(pattern1, content, re.IGNORECASE)
        if match:
            score = float(match.group(1).replace(',', '.'))
            return score, content
        
        # Pattern 2: Spanish/Catalan formats with markdown
        pattern2 = r'(?:\*{0,2}Nota\*{0,2}|#{1,3}\s*Nota)\s*[:\s]*(\d+(?:[.,]\d+)?)'
        match = re.search(pattern2, content, re.IGNORECASE)
        if match:
            score = float(match.group(1).replace(',', '.'))
            return score, content
        
        # Pattern 3: English formats
        pattern3 = r'(?:Score|Grade|Puntuación|Calificación)\s*[:\s]*(\d+(?:[.,]\d+)?)'
        match = re.search(pattern3, content, re.IGNORECASE)
        if match:
            score = float(match.group(1).replace(',', '.'))
            return score, content
        
        # Pattern 4: X.X/10 at end
        pattern4 = r'(\d+(?:[.,]\d+)?)\s*/\s*10\s*$'
        match = re.search(pattern4, content.strip())
        if match:
            score = float(match.group(1).replace(',', '.'))
            return score, content
        
        # No score found
        return None, content
```

### 6.3 LAMB API Client

```python
# services/lamb_client.py

import os
import httpx
from typing import Dict, Any, List

class LAMBClient:
    """Client for LAMB's OpenAI-compatible completions API."""
    
    def __init__(self):
        self.base_url = os.getenv("LAMB_API_URL", "http://localhost:9099")
        self.timeout = int(os.getenv("LAMB_TIMEOUT", "120"))
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: int = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call LAMB's /v1/chat/completions endpoint.
        
        Args:
            model: LAMB assistant ID (e.g., "lamb_assistant.eval_python_101")
            messages: Chat messages in OpenAI format
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            OpenAI-compatible completion response
        """
        timeout = timeout or self.timeout
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                headers={
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()
```

---

## 7. Document Extraction

### 7.1 Extractor Architecture

```python
# extractors/base.py

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    """Result of text extraction."""
    text: str
    preview: str
    method: str
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None

class DocumentExtractor(ABC):
    """Base class for document extractors."""
    
    supported_extensions: list[str] = []
    supported_mime_types: list[str] = []
    
    @abstractmethod
    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from document."""
        pass
    
    @staticmethod
    def get_preview(text: str, max_length: int = 500) -> str:
        """Get a preview of the text."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


class ExtractorRegistry:
    """Registry for document extractors."""
    
    _extractors: dict[str, DocumentExtractor] = {}
    
    @classmethod
    def register(cls, extractor_class):
        """Register an extractor."""
        instance = extractor_class()
        for ext in instance.supported_extensions:
            cls._extractors[ext] = instance
        return extractor_class
    
    @classmethod
    def get_for_file(cls, filename: str) -> Optional[DocumentExtractor]:
        """Get appropriate extractor for a file."""
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        return cls._extractors.get(ext)
```

### 7.2 Supported Formats (MVP)

| Format | Extensions | Library |
|--------|------------|---------|
| PDF | `.pdf` | pypdf or pdfplumber |
| Word | `.docx`, `.doc` | python-docx |
| Text | `.txt`, `.md` | Built-in |
| Code | `.py`, `.java`, `.cpp`, `.js`, `.html`, `.css`, `.json` | Built-in |

---

## 8. Multi-Tenancy

### 8.1 Organization Model

Following the [kb-server refactoring design](https://github.com/Lamb-Project/lamb/issues/203):

- Organizations are synced from LAMB
- Each organization has isolated data
- `external_id` maps to LAMB's organization ID/slug

### 8.2 Data Isolation

```sql
-- All job queries filter by organization
SELECT * FROM evaluation_jobs 
WHERE organization_id = ? 
AND job_code = ?;
```

### 8.3 File Storage Isolation

```
static/
└── {org_external_id}/
    └── {job_code}/
        └── submission.pdf
```

---

## 9. Authentication

### 9.1 Bearer Token (like kb-server)

```python
# dependencies.py

import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()
API_KEY = os.getenv("EVALUAITOR_API_KEY", "0p3n-w3bu!")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials
```

### 9.2 Usage

```bash
curl -H "Authorization: Bearer $EVALUAITOR_API_KEY" \
  http://localhost:9091/evaluations
```

---

## 10. Docker Integration

### 10.1 Docker Compose Addition

```yaml
# Add to docker-compose.yaml

  evaluaitor:
    image: python:3.11-slim
    working_dir: ${LAMB_PROJECT_PATH}/evaluaitor/backend
    environment:
      - PIP_DISABLE_PIP_VERSION_CHECK=1
      - PIP_CACHE_DIR=/root/.cache/pip
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONUNBUFFERED=1
      - GLOBAL_LOG_LEVEL=WARNING
      - LAMB_API_URL=http://backend:9099
      - EVALUAITOR_API_KEY=${EVALUAITOR_API_KEY:-0p3n-w3bu!}
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
      - pip-cache:/root/.cache/pip
    ports:
      - "9091:9091"
    depends_on:
      backend:
        condition: service_started
    command: >
      sh -lc "python -m pip install --upgrade pip && \
      pip install -r requirements.txt && \
      mkdir -p static data && \
      (test -f .env || cp .env.example .env) && \
      LOG_LEVEL=$$(echo \"$${GLOBAL_LOG_LEVEL:-WARNING}\" | tr '[:upper:]' '[:lower:]') && \
      uvicorn main:app --host 0.0.0.0 --port 9091 --reload --log-level $$LOG_LEVEL --no-access-log"
```

### 10.2 Service Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAMB Ecosystem (Docker)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   openwebui (8080)                                              │
│        │                                                         │
│        ▼                                                         │
│   backend (9099) ◄─────────── evaluaitor (9091)                 │
│        │                            │                            │
│        ▼                            │                            │
│   kb (9090)                         │                            │
│                                     │                            │
│   ────────────────────────────────────────────────────────────  │
│                                     │                            │
│                              LAMBA (external)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Environment Configuration

### 11.1 Required Variables

```env
# Authentication
EVALUAITOR_API_KEY=your-secure-key

# LAMB Integration
LAMB_API_URL=http://localhost:9099
LAMB_TIMEOUT=120
```

### 11.2 Optional Variables

```env
# Database
DATABASE_PATH=data/evaluaitor.db

# File Storage
STATIC_PATH=static
MAX_FILE_SIZE_MB=100

# Processing
DEFAULT_TIMEOUT_SECONDS=120
MAX_CONCURRENT_JOBS=10

# Logging
LOG_LEVEL=INFO
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
- [ ] Project structure setup
- [ ] Database schema implementation
- [ ] Basic FastAPI application with health endpoints
- [ ] Authentication middleware
- [ ] Organization CRUD endpoints

**Key Tasks:**
1. Create project directory structure
2. Implement SQLAlchemy models
3. Create database initialization
4. Implement bearer token authentication
5. Add organization sync endpoints

### Phase 2: Core Evaluation Flow (Weeks 3-4)

**Deliverables:**
- [ ] Job submission endpoint
- [ ] Job status endpoint
- [ ] Job result endpoint
- [ ] Background job processing
- [ ] File storage service

**Key Tasks:**
1. Implement evaluation submission endpoint
2. Create job queue with BackgroundTasks
3. Implement status tracking
4. Create file storage service
5. Implement result retrieval

### Phase 3: Plugin System & MVP Plugin (Weeks 5-6)

**Deliverables:**
- [ ] Plugin base classes
- [ ] Plugin registry
- [ ] `rubric_eval` plugin
- [ ] LAMB API client
- [ ] Document extractors (PDF, DOCX, TXT)

**Key Tasks:**
1. Design plugin interface
2. Implement plugin registry
3. Create LAMB API client
4. Implement `rubric_eval` plugin
5. Create document extractors

### Phase 4: Integration & Testing (Weeks 7-8)

**Deliverables:**
- [ ] Docker integration
- [ ] LAMBA integration guide
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation

**Key Tasks:**
1. Add to docker-compose
2. Test with LAMBA
3. Write test suite
4. Create API documentation
5. Write architecture documentation

---

## 13. Success Criteria

### MVP Requirements

- [ ] LAMBA can submit evaluation jobs via POST /evaluations
- [ ] LAMBA can check job status via GET /evaluations/{code}/status
- [ ] LAMBA can retrieve results via GET /evaluations/{code}/result
- [ ] Evaluations use LAMB assistants via completions API
- [ ] Multi-tenant organization support
- [ ] PDF, DOCX, and TXT files supported
- [ ] Evaluation results stored for analytics

### Performance Requirements

| Metric | Target |
|--------|--------|
| Job submission response | < 500ms |
| Status check response | < 100ms |
| Result retrieval response | < 200ms |
| Concurrent jobs supported | 10+ |

---

## 14. Future Enhancements (Out of Scope for MVP)

| Feature | Description |
|---------|-------------|
| `code_judge` plugin | Execute student code, compare outputs |
| `agentic_eval` plugin | Multi-step evaluation with tool use |
| Analytics dashboard | Evaluation statistics and insights |
| Batch evaluation | Submit multiple files in one request |
| Webhooks | Notify LAMBA when evaluation completes |
| Caching | Cache extracted text for re-evaluation |
| Retry mechanism | Automatic retry on transient failures |

---

## 15. Appendix

### A. API Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/database/status` | Database status |
| POST | `/organizations` | Register/update organization |
| GET | `/organizations/{id}` | Get organization |
| POST | `/evaluations` | Submit evaluation job |
| GET | `/evaluations/{code}/status` | Get job status |
| GET | `/evaluations/{code}/result` | Get evaluation result |
| GET | `/evaluations` | List jobs (with filters) |
| POST | `/evaluations/{code}/cancel` | Cancel job |
| GET | `/plugins` | List available plugins |

### B. Glossary

| Term | Definition |
|------|------------|
| **Evaluaitor** | The evaluation microservice (this project) |
| **LAMB** | Learning Assistants Manager and Builder - main AI platform |
| **LAMBA** | LTI Tool Provider for Moodle integration |
| **Job Code** | Unique identifier for an evaluation job |
| **Evaluator ID** | LAMB assistant identifier used for evaluation |
| **Plugin** | Modular evaluation strategy implementation |

### C. References

- [LAMB Architecture](../lamb_architecture_nano.md)
- [lamb-kb-server Architecture](../../lamb-kb-server-stable/Docs/lamb-kb-server_architecture.md)
- [KB-Server Multi-Tenancy Design](https://github.com/Lamb-Project/lamb/issues/203)
- [LAMBA Architecture](https://github.com/Lamb-Project/LAMBA/blob/main/Doumentation/lamba_architecture.md)

---

**Document Status:** Draft  
**Version:** 0.1.0  
**Last Updated:** January 25, 2026  
**Author:** LAMB Development Team
