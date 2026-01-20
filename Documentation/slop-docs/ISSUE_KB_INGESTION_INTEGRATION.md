# KB Server Ingestion Integration - Support New Async API and markitdown_plus_ingest Plugin

## Summary

The KB Server has been updated with new features that LAMB needs to integrate:
1. **New `markitdown_plus_ingest` plugin** with enhanced capabilities (LLM image descriptions, multiple chunking strategies, progress reporting)
2. **Async Ingestion Status API** for tracking background processing jobs
3. **New metadata fields** in document chunks for better source attribution

This issue tracks the implementation of full support for these features while maintaining backward compatibility with existing plugins.

## Background

### What's New in KB Server

#### 1. `markitdown_plus_ingest` Plugin

| Feature | Description |
|---------|-------------|
| **Image Descriptions** | `none`, `basic`, `llm` modes - LLM mode uses OpenAI Vision |
| **Chunking Modes** | `standard`, `by_page`, `by_section` |
| **New Metadata Fields** | `original_file_url`, `markdown_file_url`, `images_folder_url`, `images_extracted`, `chunking_strategy` |
| **Progress Reporting** | Real-time progress updates via `supports_progress = True` |
| **Privacy Warning** | LLM mode sends data to OpenAI - must surface warning |

#### 2. Ingestion Status API (New Endpoints)

| Endpoint | Purpose |
|----------|---------|
| `GET /collections/{id}/ingestion-jobs` | List all ingestion jobs |
| `GET /collections/{id}/ingestion-jobs/{job_id}` | Poll single job status |
| `GET /collections/{id}/ingestion-status` | Get summary of all jobs |
| `POST /collections/{id}/ingestion-jobs/{job_id}/retry` | Retry failed job |
| `POST /collections/{id}/ingestion-jobs/{job_id}/cancel` | Cancel in-progress job |

#### 3. Async Processing Model

- **Before:** KB server processed files synchronously (LAMB waits up to 300s)
- **Now:** Returns `file_registry_id` immediately, processes in background with progress tracking

### Current LAMB Implementation Gaps

**Backend:**
- No handling of `file_registry_id` in ingestion response
- No status polling endpoints exposed to frontend
- No retry/cancel functionality
- RAG processors only use `file_url` metadata (missing new fields)
- 300s blocking timeout for ingestion requests

**Frontend:**
- No progress bar/percentage display during ingestion
- No job status tracking after upload starts
- No visibility into processing failures
- No retry UI for failed jobs
- No privacy warning for LLM image description mode

## Tasks

### Phase 1: Backend Foundation

- [ ] **1.1 Add Ingestion Status Endpoints to LAMB**
  - Add `GET /creator/knowledgebases/kb/{kb_id}/ingestion-jobs` - list jobs with filtering
  - Add `GET /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}` - get single job status
  - Add `POST /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/retry` - retry failed
  - Add `POST /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/cancel` - cancel job
  - Add `GET /creator/knowledgebases/kb/{kb_id}/ingestion-status` - get summary
  - Files: `backend/creator_interface/knowledges_router.py`

- [ ] **1.2 Update KBServerManager with New Methods**
  - Add `get_ingestion_job_status(kb_id, job_id, creator_user)`
  - Add `list_ingestion_jobs(kb_id, creator_user, status=None, limit=50)`
  - Add `retry_ingestion_job(kb_id, job_id, creator_user, override_params=None)`
  - Add `cancel_ingestion_job(kb_id, job_id, creator_user)`
  - Add `get_ingestion_status_summary(kb_id, creator_user)`
  - Files: `backend/creator_interface/kb_server_manager.py`

- [ ] **1.3 Return file_registry_id from Upload Endpoints**
  - Update `plugin_ingest_file()` to return `file_registry_id` from KB server response
  - Update `upload_files_to_kb()` similarly
  - Include `status: "processing"` in response when async
  - Files: `backend/creator_interface/kb_server_manager.py`

- [ ] **1.4 Update RAG Processors for New Metadata**
  - Use `original_file_url` with fallback to `file_url` (backward compatible)
  - Extract `markdown_file_url` and `images_folder_url` when available
  - Include `chunking_strategy` and `images_extracted` in source info
  - Files: `backend/lamb/completions/rag/simple_rag.py`, `backend/lamb/completions/rag/context_aware_rag.py`

### Phase 2: Frontend Service Layer

- [ ] **2.1 Add Ingestion Status Service Methods**
  - Add `getIngestionJobStatus(kbId, jobId)`
  - Add `listIngestionJobs(kbId, status = null)`
  - Add `retryIngestionJob(kbId, jobId, overrideParams = null)`
  - Add `cancelIngestionJob(kbId, jobId)`
  - Add `getIngestionStatusSummary(kbId)`
  - Files: `frontend/svelte-app/src/lib/services/knowledgeBaseService.js`

- [ ] **2.2 Update uploadFileWithPlugin Response Handling**
  - Handle `file_registry_id` in response
  - Return job info for progress tracking
  - Files: `frontend/svelte-app/src/lib/services/knowledgeBaseService.js`

### Phase 3: Frontend UI Components

- [ ] **3.1 Create IngestionProgress Component**
  - Poll job status using `getIngestionJobStatus()`
  - Display progress bar with percentage
  - Show status message from API
  - Handle completion/failure states
  - Files: `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/IngestionProgress.svelte` (new)

- [ ] **3.2 Add Privacy Warning for LLM Image Mode**
  - Show warning banner when `image_descriptions: "llm"` is selected
  - Include in plugin parameter UI
  - Files: `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte`

- [ ] **3.3 Update KnowledgeBaseDetail for Progress Tracking**
  - Track active ingestion jobs after upload
  - Show `IngestionProgress` component for each active job
  - Handle job completion (reload file list)
  - Handle job failure (show retry option)
  - Files: `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte`

### Phase 4: Enhanced File Display

- [ ] **4.1 Show Processing Status in File List**
  - Display processing/completed/failed badges
  - Show progress percentage for processing files
  - Add retry button for failed files
  - Files: `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte`

- [ ] **4.2 Display Enhanced File Metadata**
  - Show link to markdown file when `markdown_file_url` available
  - Show link to images folder when `images_folder_url` available
  - Display chunk count and chunking strategy
  - Files: `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte`

### Phase 5: Optional Enhancements

- [ ] **5.1 Add Dedicated Ingestion Jobs View** (Lower Priority)
  - New tab or page showing all ingestion jobs
  - Filter by status (processing, completed, failed)
  - Bulk retry/cancel operations
  - Files: New component

- [ ] **5.2 Add i18n Keys for New UI Elements**
  - Add translation keys for progress messages
  - Add translation keys for status badges
  - Add translation keys for privacy warning
  - Files: `frontend/svelte-app/src/lib/i18n/`

## API Design

### New LAMB Endpoints

```
GET /creator/knowledgebases/kb/{kb_id}/ingestion-jobs
  Query params: status, limit, offset, sort_by, sort_order
  Response: { total, items: [...], has_more }

GET /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}
  Response: { id, status, progress: {current, total, percentage, message}, ... }

POST /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/retry
  Body: { override_params?: {...} }
  Response: { id, status: "pending", ... }

POST /creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/cancel
  Response: { id, status: "cancelled", ... }

GET /creator/knowledgebases/kb/{kb_id}/ingestion-status
  Response: { total_jobs, by_status: {...}, recent_failures: [...] }
```

### Updated Upload Response

```json
{
  "status": "processing",
  "file_registry_id": 123,
  "collection_id": 1,
  "original_filename": "document.pdf",
  "plugin_name": "markitdown_plus_ingest"
}
```

## Acceptance Criteria

1. [ ] Users can upload files and see real-time progress percentage
2. [ ] Users see clear warning when using LLM image description mode
3. [ ] Failed ingestion jobs can be retried from the UI
4. [ ] Processing jobs can be cancelled from the UI
5. [ ] File list shows processing status for each file
6. [ ] Existing plugins (simple_ingest, markitdown_ingest) continue to work
7. [ ] RAG processors use new metadata fields when available
8. [ ] All new endpoints properly authenticate and authorize users

## Related Documentation

- KB Server Ingestion API Client Guide: `lamb-kb-server-stable/Docs/ingestion-api-client-guide.md`
- KB Server Ingestion Status API: `lamb-kb-server-stable/Docs/ingestion-status-api.md`
- markitdown_plus_ingest Plugin: `lamb-kb-server-stable/plugins/markitdown_plus_ingest.py`
- LAMB Architecture: `Documentation/lamb_architecture_v2.md`

## Labels

- `enhancement`
- `kb-server`
- `frontend`
- `backend`

