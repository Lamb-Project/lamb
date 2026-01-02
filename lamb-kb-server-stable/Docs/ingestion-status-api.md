# Ingestion Status API Documentation

**Version:** 1.1.0  
**Last Updated:** January 2, 2026  
**Target Audience:** Frontend Developers, API Integrators

---

## Table of Contents

1. [Overview](#1-overview)
2. [Status Model](#2-status-model)
3. [API Endpoints](#3-api-endpoints)
4. [Response Models](#4-response-models)
5. [Client Integration Guide](#5-client-integration-guide)
6. [Error Handling](#6-error-handling)
7. [Best Practices](#7-best-practices)

---

## 1. Overview

The Ingestion Status API provides comprehensive tracking for document ingestion jobs. When a file is uploaded or a URL is ingested, the system creates an **ingestion job** that processes the content asynchronously in the background.

### Key Features

| Feature | Description |
|---------|-------------|
| **Real-time Status** | Poll job status to track processing progress |
| **Progress Tracking** | See current/total chunks and percentage complete |
| **Error Details** | Get detailed error information for failed jobs |
| **Timing Information** | Track processing duration |
| **Retry Capability** | Retry failed jobs with optional parameter overrides |
| **Cancellation** | Cancel pending or processing jobs |

### Job Lifecycle

```
┌─────────┐     ┌────────────┐     ┌───────────┐
│ PENDING │────►│ PROCESSING │────►│ COMPLETED │
└─────────┘     └────────────┘     └───────────┘
                      │
                      ├────────────►┌────────┐
                      │             │ FAILED │◄──── Can be retried
                      │             └────────┘
                      │
                      └────────────►┌───────────┐
                                    │ CANCELLED │
                                    └───────────┘
```

---

## 2. Status Model

### Status Values

| Status | Description | Terminal? | Can Retry? |
|--------|-------------|-----------|------------|
| `pending` | Job created, waiting to start | No | No |
| `processing` | Job is currently running | No | No |
| `completed` | Job finished successfully | Yes | No |
| `failed` | Job failed with error | Yes | **Yes** |
| `cancelled` | Job was cancelled by user | Yes | No |
| `deleted` | Soft-deleted (file may exist) | Yes | No |

### Status Transitions

```
Valid transitions:
  pending → processing
  processing → completed
  processing → failed
  processing → cancelled
  pending → cancelled
  any → deleted (soft delete)
  failed → pending (via retry)
```

---

## 3. API Endpoints

All endpoints require Bearer token authentication:
```
Authorization: Bearer 0p3n-w3bu!
```

### 3.1 List Ingestion Jobs

```http
GET /collections/{collection_id}/ingestion-jobs
```

List all ingestion jobs for a collection with filtering and pagination.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status (`pending`, `processing`, `completed`, `failed`, `cancelled`, `deleted`) |
| `limit` | integer | 50 | Max items to return (1-200) |
| `offset` | integer | 0 | Items to skip |
| `sort_by` | string | `created_at` | Sort field (`created_at`, `updated_at`, `status`, `original_filename`, `file_size`) |
| `sort_order` | string | `desc` | Sort order (`asc`, `desc`) |

#### Example Request

```bash
# List all jobs
curl 'http://localhost:9090/collections/1/ingestion-jobs' \
  -H 'Authorization: Bearer 0p3n-w3bu!'

# List failed jobs only
curl 'http://localhost:9090/collections/1/ingestion-jobs?status=failed' \
  -H 'Authorization: Bearer 0p3n-w3bu!'

# List processing jobs, oldest first
curl 'http://localhost:9090/collections/1/ingestion-jobs?status=processing&sort_by=created_at&sort_order=asc' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

#### Example Response

```json
{
  "total": 25,
  "items": [
    {
      "id": 5,
      "job_id": 5,
      "collection_id": 1,
      "collection_name": "my-knowledge-base",
      "original_filename": "annual_report.pdf",
      "file_path": "/app/static/user@example.com/my-kb/abc123.pdf",
      "file_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.pdf",
      "file_size": 2456789,
      "content_type": "application/pdf",
      "plugin_name": "markitdown_ingest",
      "plugin_params": {"chunk_size": 1000, "chunk_overlap": 200},
      "status": "completed",
      "document_count": 45,
      "created_at": "2025-12-30T10:30:00Z",
      "updated_at": "2025-12-30T10:32:15Z",
      "processing_started_at": "2025-12-30T10:30:01Z",
      "processing_completed_at": "2025-12-30T10:32:15Z",
      "processing_duration_seconds": 134.5,
      "progress": {
        "current": 45,
        "total": 45,
        "percentage": 100.0,
        "message": "Completed: 45 chunks added"
      },
      "error_message": null,
      "error_details": null,
      "owner": "user@example.com"
    }
  ],
  "limit": 50,
  "offset": 0,
  "has_more": false
}
```

---

### 3.2 Get Single Job Status

```http
GET /collections/{collection_id}/ingestion-jobs/{job_id}
```

Get detailed status of a specific ingestion job. **Use this for polling.**

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_id` | integer | Collection ID |
| `job_id` | integer | Job ID (same as file_registry.id) |

#### Example Request

```bash
curl 'http://localhost:9090/collections/1/ingestion-jobs/5' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

#### Example Response (Processing)

```json
{
  "id": 5,
  "job_id": 5,
  "collection_id": 1,
  "collection_name": "my-knowledge-base",
  "original_filename": "large_document.pdf",
  "file_path": "/app/static/user@example.com/my-kb/abc123.pdf",
  "file_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.pdf",
  "file_size": 15000000,
  "content_type": "application/pdf",
  "plugin_name": "markitdown_ingest",
  "plugin_params": {"chunk_size": 1000},
  "status": "processing",
  "document_count": 0,
  "created_at": "2025-12-30T10:30:00Z",
  "updated_at": "2025-12-30T10:30:45Z",
  "processing_started_at": "2025-12-30T10:30:01Z",
  "processing_completed_at": null,
  "processing_duration_seconds": null,
  "progress": {
    "current": 67,
    "total": 150,
    "percentage": 44.67,
    "message": "Adding 150 chunks to collection..."
  },
  "error_message": null,
  "error_details": null,
  "owner": "user@example.com"
}
```

#### Example Response (Failed)

```json
{
  "id": 6,
  "job_id": 6,
  "collection_id": 1,
  "collection_name": "my-knowledge-base",
  "original_filename": "corrupted.pdf",
  "status": "failed",
  "document_count": 0,
  "created_at": "2025-12-30T10:25:00Z",
  "updated_at": "2025-12-30T10:25:05Z",
  "processing_started_at": "2025-12-30T10:25:01Z",
  "processing_completed_at": "2025-12-30T10:25:05Z",
  "processing_duration_seconds": 4.2,
  "progress": {
    "current": 0,
    "total": 0,
    "percentage": 0.0,
    "message": "Failed: Document conversion failed: Invalid PDF format"
  },
  "error_message": "Document conversion failed: Invalid PDF format - Unable to extract text from encrypted PDF",
  "error_details": {
    "exception_type": "ValueError",
    "traceback": "Traceback (most recent call last):\n  File ...",
    "file_path": "/app/static/user@example.com/my-kb/def456.pdf",
    "plugin_name": "markitdown_ingest",
    "stage": "unknown"
  },
  "owner": "user@example.com"
}
```

---

### 3.3 Get Status Summary

```http
GET /collections/{collection_id}/ingestion-status
```

Get a summary of ingestion job statuses for quick overview.

#### Example Request

```bash
curl 'http://localhost:9090/collections/1/ingestion-status' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

#### Example Response

```json
{
  "collection_id": 1,
  "collection_name": "my-knowledge-base",
  "total_jobs": 25,
  "by_status": {
    "pending": 0,
    "processing": 2,
    "completed": 21,
    "failed": 2,
    "cancelled": 0,
    "deleted": 0
  },
  "currently_processing": 2,
  "recent_failures": [
    {
      "id": 24,
      "original_filename": "bad_file.docx",
      "status": "failed",
      "error_message": "Document conversion failed: Corrupted file",
      "created_at": "2025-12-30T10:20:00Z"
    }
  ],
  "oldest_processing_job": {
    "id": 22,
    "original_filename": "huge_report.pdf",
    "status": "processing",
    "processing_started_at": "2025-12-30T10:15:00Z",
    "progress": {
      "current": 500,
      "total": 1200,
      "percentage": 41.67,
      "message": "Adding 1200 chunks to collection..."
    }
  }
}
```

**Use Case:** Display this summary on a dashboard to show collection health at a glance.

---

### 3.4 Retry Failed Job

```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/retry
```

Retry a failed ingestion job. Only jobs with `status: "failed"` can be retried.

#### Request Body (Optional)

```json
{
  "override_params": {
    "chunk_size": 500,
    "chunk_overlap": 100
  }
}
```

If `override_params` is not provided, the original parameters are used.

#### Example Request

```bash
# Retry with original parameters
curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/6/retry' \
  -H 'Authorization: Bearer 0p3n-w3bu!'

# Retry with different parameters
curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/6/retry' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{"override_params": {"chunk_size": 500}}'
```

#### Example Response

```json
{
  "id": 6,
  "job_id": 6,
  "status": "pending",
  "progress": {
    "current": 0,
    "total": 0,
    "percentage": 0.0,
    "message": "Queued for retry"
  },
  "error_message": null,
  "error_details": null
}
```

---

### 3.5 Cancel Job

```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/cancel
```

Cancel a pending or processing job. This is **best-effort** - the current processing step may complete.

#### Example Request

```bash
curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/5/cancel' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

#### Example Response

```json
{
  "id": 5,
  "job_id": 5,
  "status": "cancelled",
  "progress": {
    "current": 67,
    "total": 150,
    "percentage": 44.67,
    "message": "Cancelled by user"
  }
}
```

---

## 4. Response Models

### 4.1 IngestionJobResponse

The main model for job status:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Job ID (same as file_registry.id) |
| `job_id` | integer | Alias for id |
| `collection_id` | integer | Parent collection ID |
| `collection_name` | string | Parent collection name |
| `original_filename` | string | Original uploaded filename |
| `file_path` | string | Server-side storage path |
| `file_url` | string | Public URL to access file |
| `file_size` | integer | File size in bytes |
| `content_type` | string | MIME type |
| `plugin_name` | string | Ingestion plugin used |
| `plugin_params` | object | Parameters passed to plugin |
| `status` | string | Current status |
| `document_count` | integer | Chunks created (0 if not complete) |
| `created_at` | datetime | Job creation time |
| `updated_at` | datetime | Last update time |
| `processing_started_at` | datetime | When processing began |
| `processing_completed_at` | datetime | When processing finished |
| `processing_duration_seconds` | float | Duration in seconds |
| `progress` | object | Progress information |
| `error_message` | string | Error message (if failed) |
| `error_details` | object | Detailed error info |
| `processing_stats` | object | Detailed processing statistics (see 4.4) |
| `owner` | string | Owner identifier |

### 4.2 IngestionProgress

Progress tracking object:

| Field | Type | Description |
|-------|------|-------------|
| `current` | integer | Current progress value |
| `total` | integer | Total expected value |
| `percentage` | float | Completion percentage (0-100) |
| `message` | string | Human-readable status message |

### 4.3 StatusCount

Status breakdown object:

| Field | Type | Description |
|-------|------|-------------|
| `pending` | integer | Jobs waiting to start |
| `processing` | integer | Jobs currently running |
| `completed` | integer | Successfully completed |
| `failed` | integer | Failed with error |
| `cancelled` | integer | Cancelled by user |
| `deleted` | integer | Soft-deleted |

### 4.4 ProcessingStats (Added Jan 2026)

Comprehensive statistics collected during document processing. Only available for completed jobs processed with `markitdown_plus_ingest` plugin.

| Field | Type | Description |
|-------|------|-------------|
| `content_length` | integer | Total characters in processed content |
| `images_extracted` | integer | Number of images extracted from document |
| `images_with_llm_descriptions` | integer | Images that received LLM-generated descriptions |
| `llm_calls` | array | Details of individual LLM API calls (see below) |
| `total_llm_duration_ms` | integer | Total time spent on LLM API calls (milliseconds) |
| `chunking_strategy` | string | Strategy used (e.g., "by_section", "standard_recursivecharactertextsplitter") |
| `chunk_stats` | object | Statistics about chunks (see below) |
| `stage_timings` | array | Timing breakdown by processing stage (see below) |
| `output_files` | object | URLs to generated output files (see below) |
| `markdown_preview` | string | First ~2000 characters of converted markdown |

#### LLMCallDetail (within `llm_calls` array)

| Field | Type | Description |
|-------|------|-------------|
| `image` | string | Image filename that was processed |
| `duration_ms` | integer | Time taken for this API call (milliseconds) |
| `success` | boolean | Whether the call succeeded |
| `tokens_used` | integer | Tokens used (if available from API response) |
| `error` | string | Error message if call failed |

#### ChunkStats (within `chunk_stats`)

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Total number of chunks created |
| `avg_size` | float | Average chunk size in characters |
| `min_size` | integer | Smallest chunk size |
| `max_size` | integer | Largest chunk size |

#### StageTiming (within `stage_timings` array)

| Field | Type | Description |
|-------|------|-------------|
| `stage` | string | Stage name (conversion, image_extraction, llm_descriptions, chunking, finalization) |
| `duration_ms` | integer | Duration of this stage (milliseconds) |
| `message` | string | Human-readable description of what happened |
| `timestamp` | string | ISO timestamp when stage completed |

#### OutputFiles (within `output_files`)

| Field | Type | Description |
|-------|------|-------------|
| `markdown_url` | string | URL to the converted markdown file |
| `images_folder_url` | string | URL to the folder containing extracted images |
| `original_file_url` | string | URL to the original uploaded file |

#### Example ProcessingStats

```json
{
  "processing_stats": {
    "content_length": 45230,
    "images_extracted": 12,
    "images_with_llm_descriptions": 12,
    "llm_calls": [
      {
        "image": "image_001.png",
        "duration_ms": 1234,
        "tokens_used": 150,
        "success": true
      },
      {
        "image": "image_002.png",
        "duration_ms": 987,
        "tokens_used": 142,
        "success": true
      }
    ],
    "total_llm_duration_ms": 15800,
    "chunking_strategy": "by_section",
    "chunk_stats": {
      "count": 45,
      "avg_size": 1005.1,
      "min_size": 234,
      "max_size": 1499
    },
    "stage_timings": [
      {
        "stage": "conversion",
        "duration_ms": 2300,
        "message": "PDF → Markdown (45,230 chars)",
        "timestamp": "2026-01-02T10:30:03Z"
      },
      {
        "stage": "image_extraction",
        "duration_ms": 1200,
        "message": "Extracted 12 images",
        "timestamp": "2026-01-02T10:30:04Z"
      },
      {
        "stage": "llm_descriptions",
        "duration_ms": 15800,
        "message": "12 LLM API calls (12 successful)",
        "timestamp": "2026-01-02T10:30:20Z"
      },
      {
        "stage": "chunking",
        "duration_ms": 500,
        "message": "45 chunks (by_section)",
        "timestamp": "2026-01-02T10:30:20Z"
      },
      {
        "stage": "finalization",
        "duration_ms": 150,
        "message": "Saved markdown and prepared 45 chunks",
        "timestamp": "2026-01-02T10:30:21Z"
      }
    ],
    "output_files": {
      "markdown_url": "http://localhost:9090/static/user@example.com/my-kb/document.md",
      "images_folder_url": "http://localhost:9090/static/user@example.com/my-kb/document/",
      "original_file_url": "http://localhost:9090/static/user@example.com/my-kb/document.pdf"
    },
    "markdown_preview": "# Chapter 1: Introduction\n\nThis document provides an overview of...\n\n## 1.1 Background\n\nThe field of artificial intelligence has...\n\n... [truncated]"
  }
}
```

> **Note:** `processing_stats` is only populated for jobs processed with `markitdown_plus_ingest` plugin (version 1.3.0+). Jobs processed with other plugins or older versions will have `processing_stats: null`.

---

## 5. Client Integration Guide

### 5.1 Polling for Job Status

When you start an ingestion (file upload or URL ingest), the response includes a `file_registry_id`. Use this to poll for status:

```javascript
// JavaScript/TypeScript example
async function pollJobStatus(collectionId, jobId, onProgress, onComplete, onError) {
  const pollInterval = 1500; // 1.5 seconds
  
  const poll = async () => {
    try {
      const response = await fetch(
        `${API_BASE}/collections/${collectionId}/ingestion-jobs/${jobId}`,
        { headers: { 'Authorization': `Bearer ${API_KEY}` } }
      );
      const job = await response.json();
      
      // Call progress callback
      onProgress(job);
      
      // Check if terminal state
      if (['completed', 'failed', 'cancelled', 'deleted'].includes(job.status)) {
        if (job.status === 'completed') {
          onComplete(job);
        } else if (job.status === 'failed') {
          onError(job);
        }
        return; // Stop polling
      }
      
      // Continue polling
      setTimeout(poll, pollInterval);
      
    } catch (err) {
      onError({ error_message: err.message });
    }
  };
  
  poll();
}

// Usage
pollJobStatus(
  1, 
  5,
  (job) => updateProgressBar(job.progress.percentage),
  (job) => showSuccess(`Added ${job.document_count} chunks!`),
  (job) => showError(job.error_message)
);
```

### 5.2 React Hook Example

```tsx
// useIngestionJob.ts
import { useState, useEffect, useCallback } from 'react';

interface IngestionJob {
  id: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: {
    current: number;
    total: number;
    percentage: number;
    message: string;
  };
  document_count: number;
  error_message?: string;
}

export function useIngestionJob(collectionId: number, jobId: number | null) {
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;
    
    try {
      const res = await fetch(
        `/api/collections/${collectionId}/ingestion-jobs/${jobId}`
      );
      const data = await res.json();
      setJob(data);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [collectionId, jobId]);

  useEffect(() => {
    if (!jobId) return;
    
    setLoading(true);
    
    const poll = async () => {
      const data = await fetchJob();
      
      if (data && !['completed', 'failed', 'cancelled'].includes(data.status)) {
        setTimeout(poll, 1500);
      } else {
        setLoading(false);
      }
    };
    
    poll();
  }, [jobId, fetchJob]);

  const retry = async () => {
    if (!jobId || job?.status !== 'failed') return;
    
    await fetch(
      `/api/collections/${collectionId}/ingestion-jobs/${jobId}/retry`,
      { method: 'POST' }
    );
    
    setLoading(true);
    await fetchJob();
  };

  const cancel = async () => {
    if (!jobId || !['pending', 'processing'].includes(job?.status || '')) return;
    
    await fetch(
      `/api/collections/${collectionId}/ingestion-jobs/${jobId}/cancel`,
      { method: 'POST' }
    );
    
    await fetchJob();
  };

  return { job, loading, error, retry, cancel, refetch: fetchJob };
}
```

### 5.3 Progress Bar Component

```tsx
// IngestionProgress.tsx
interface Props {
  job: IngestionJob;
  onRetry?: () => void;
  onCancel?: () => void;
}

export function IngestionProgress({ job, onRetry, onCancel }: Props) {
  const { status, progress, error_message, document_count } = job;
  
  const statusColors = {
    pending: 'bg-gray-400',
    processing: 'bg-blue-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    cancelled: 'bg-yellow-500',
  };
  
  return (
    <div className="p-4 border rounded-lg">
      {/* Status Badge */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`px-2 py-1 rounded text-white text-sm ${statusColors[status]}`}>
          {status.toUpperCase()}
        </span>
        <span className="text-sm text-gray-600">{job.original_filename}</span>
      </div>
      
      {/* Progress Bar */}
      {(status === 'processing' || status === 'pending') && (
        <div className="mb-2">
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progress.percentage}%` }}
            />
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {progress.message} ({progress.percentage.toFixed(1)}%)
          </p>
        </div>
      )}
      
      {/* Success Message */}
      {status === 'completed' && (
        <p className="text-green-600">
          ✓ Successfully added {document_count} chunks
        </p>
      )}
      
      {/* Error Message */}
      {status === 'failed' && (
        <div className="mt-2">
          <p className="text-red-600 mb-2">✗ {error_message}</p>
          {onRetry && (
            <button 
              onClick={onRetry}
              className="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
            >
              Retry
            </button>
          )}
        </div>
      )}
      
      {/* Cancel Button */}
      {(status === 'pending' || status === 'processing') && onCancel && (
        <button 
          onClick={onCancel}
          className="mt-2 px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
```

---

## 6. Error Handling

### 6.1 HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Check API key |
| 404 | Not Found | Collection or job doesn't exist |
| 500 | Server Error | Retry or contact support |

### 6.2 Error Response Format

```json
{
  "detail": "Error message here"
}
```

### 6.3 Common Error Scenarios

| Error | Cause | Solution |
|-------|-------|----------|
| "Collection not found" | Invalid collection_id | Verify collection exists |
| "Job not found" | Invalid job_id | Verify job_id from ingestion response |
| "Only failed jobs can be retried" | Trying to retry non-failed job | Check job status first |
| "Only pending or processing jobs can be cancelled" | Trying to cancel completed job | Check job status first |

---

## 7. Best Practices

### 7.1 Polling Recommendations

- **Poll Interval:** 1-2 seconds for active jobs
- **Stop Condition:** Stop when status is `completed`, `failed`, or `cancelled`
- **Timeout:** Consider a maximum poll time (e.g., 30 minutes) with user notification
- **Error Recovery:** If a poll request fails, retry with exponential backoff

### 7.2 UI/UX Recommendations

1. **Show Progress**
   - Display progress bar with percentage
   - Show current status message
   - Display elapsed time for long-running jobs

2. **Handle Failures Gracefully**
   - Show clear error message
   - Provide "Retry" button for failed jobs
   - Optionally show technical details in expandable section

3. **Allow Cancellation**
   - Show "Cancel" button for pending/processing jobs
   - Confirm before cancelling
   - Handle partial results appropriately

4. **Dashboard Summary**
   - Use the `/ingestion-status` endpoint for overview
   - Highlight active jobs and recent failures
   - Alert on jobs stuck in "processing" for too long

### 7.3 Performance Tips

- **Batch Polling:** If monitoring multiple jobs, consider fetching list with status filter instead of individual requests
- **Caching:** Cache completed job details (they won't change)
- **WebSocket Alternative:** For high-volume scenarios, consider implementing WebSocket notifications (future enhancement)

---

## Appendix: Database Schema

The ingestion job data is stored in the `file_registry` table:

```sql
CREATE TABLE file_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_url VARCHAR(255) NOT NULL,
    file_size INTEGER DEFAULT 0,
    content_type VARCHAR(100),
    plugin_name VARCHAR(100) NOT NULL,
    plugin_params JSON,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed, cancelled, deleted
    document_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_started_at DATETIME,
    processing_completed_at DATETIME,
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    progress_message VARCHAR(255),
    error_message TEXT,
    error_details JSON,
    owner VARCHAR(255) NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
);
```

---

**Document Version:** 1.1.0  
**Last Updated:** January 2, 2026  
**Maintainers:** LAMB Development Team

