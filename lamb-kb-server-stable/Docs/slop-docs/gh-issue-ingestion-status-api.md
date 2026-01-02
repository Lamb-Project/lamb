# Feature: Ingestion Status API

## Summary

New API endpoints for monitoring the status and progress of asynchronous document ingestion jobs. This enhancement provides real-time visibility into file processing, error tracking, and progress reporting.

## Problem

Currently, when files are ingested asynchronously via `/ingest-file`, `/ingest-url`, or `/ingest-base`, clients have no way to:
- Check the current status of processing jobs
- See detailed progress during long-running ingestions
- Retrieve error messages when ingestion fails
- Get a summary of all ingestion jobs for a collection
- Retry failed jobs or cancel in-progress ones

## Solution

### New Database Fields

Added to `FileRegistry` model:

| Field | Type | Description |
|-------|------|-------------|
| `processing_started_at` | DateTime | When processing began |
| `processing_completed_at` | DateTime | When processing finished |
| `progress_current` | Integer | Current progress value |
| `progress_total` | Integer | Total expected value |
| `progress_message` | String(255) | Human-readable status message |
| `error_message` | Text | Error description if failed |
| `error_details` | JSON | Detailed error info (traceback, context) |

### New Status Value

Added `CANCELLED` to `FileStatus` enum for jobs cancelled by users.

### New API Endpoints

#### 1. List Ingestion Jobs
```http
GET /collections/{collection_id}/ingestion-jobs
```
Query params: `status`, `limit`, `offset`, `sort_by`, `sort_order`

Returns paginated list of all ingestion jobs with full status details.

#### 2. Get Ingestion Job Status
```http
GET /collections/{collection_id}/ingestion-jobs/{job_id}
```
Returns detailed status of a specific job including:
- Processing timestamps and duration
- Progress percentage and message
- Error details if failed

#### 3. Get Ingestion Status Summary
```http
GET /collections/{collection_id}/ingestion-status
```
Returns summary including:
- Total job count
- Count by status (completed, processing, failed, etc.)
- Recent failures list

#### 4. Retry Failed Job
```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/retry
```
Re-queues a failed job with same or updated parameters.

#### 5. Cancel Processing Job
```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/cancel
```
Best-effort cancellation of in-progress jobs.

### Plugin Progress Reporting

Enhanced plugin base class with optional progress callback support:

```python
class IngestPlugin(abc.ABC):
    supports_progress: bool = False
    
    def report_progress(self, kwargs, current, total, message):
        """Report progress to background task."""
        callback = kwargs.get('progress_callback')
        if callback:
            callback(current, total, message)
```

Plugins updated to report progress:
- ✅ `url_ingest` - Per-URL progress
- ✅ `youtube_transcript_ingest` - Per-video progress  
- ✅ `markitdown_ingest` - Stage-based progress (convert → HTML → chunk → complete)

## Example Response

```json
{
  "id": 101,
  "collection_id": 1,
  "original_filename": "report.pdf",
  "status": "processing",
  "progress": {
    "current": 2,
    "total": 4,
    "percentage": 50.0,
    "message": "Splitting content into chunks..."
  },
  "processing_started_at": "2025-12-30T10:00:05Z",
  "processing_completed_at": null,
  "error_message": null
}
```

## Migration

Database migration automatically adds new columns on server startup. Existing records are backfilled:
- `processing_started_at` → `created_at`
- `processing_completed_at` → `updated_at` (for completed/failed)
- `progress_message` → status-appropriate message

## Files Changed

- `backend/database/models.py` - New FileRegistry fields, CANCELLED status
- `backend/database/migrations/migration_add_ingestion_tracking.py` - Schema migration
- `backend/schemas/files.py` - New response schemas
- `backend/routers/ingestion_status.py` - New router (to be created)
- `backend/routers/collections.py` - Enhanced background tasks with progress callbacks
- `backend/plugins/base.py` - Progress callback support
- `backend/plugins/url_ingest.py` - Progress reporting
- `backend/plugins/youtube_transcript_ingest.py` - Progress reporting
- `backend/plugins/markitdown-ingest-plugin.py` - Progress reporting
- `backend/main.py` - Include new router

## Testing

- [ ] Create collection and ingest file
- [ ] Poll `/ingestion-jobs/{id}` to see progress updates
- [ ] Verify completed jobs show duration and chunk count
- [ ] Test with intentionally corrupted file to verify error capture
- [ ] Test retry endpoint on failed job
- [ ] Test cancel endpoint on long-running job

## Labels

`enhancement`, `api`, `backend`

