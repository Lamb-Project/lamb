# Ingestion API Client Guide

**Version:** 1.2.0  
**Last Updated:** January 2026  
**Target Audience:** API Clients, Frontend Developers, Integration Engineers

---

## ℹ️ Data Privacy Notice

The LAMB KB Server processes documents **locally by default**. External API calls only occur under specific conditions:

| Plugin | External API Usage | Safe for Sensitive Data? |
|--------|-------------------|--------------------------|
| `markitdown_plus_ingest` | ❌ **None** (default) / ⚠️ OpenAI (only when `image_descriptions="llm"`) | ✅ **YES** (default) / ❌ No (with `llm` mode) |
| `markitdown_ingest` | ❌ None (local processing) | ✅ **YES** |
| `simple_ingest` | ❌ None (local processing) | ✅ **YES** |
| `youtube_transcript_ingest` | ⚠️ YouTube API | ⚠️ Public content only |

**Key Point:** The `markitdown_plus_ingest` plugin only sends data to OpenAI when `image_descriptions` is explicitly set to `"llm"`. The default mode (`"none"`) is fully local.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Ingestion Workflow](#3-ingestion-workflow)
4. [Ingestion Endpoints](#4-ingestion-endpoints)
5. [Monitoring Ingestion Jobs](#5-monitoring-ingestion-jobs)
6. [Available Plugins](#6-available-plugins)
7. [Chunk Metadata Reference](#7-chunk-metadata-reference)
8. [Error Handling](#8-error-handling)
9. [Best Practices](#9-best-practices)
10. [Data Privacy Guidelines](#10-data-privacy-guidelines)

---

## 1. Overview

The LAMB Knowledge Base Server provides asynchronous document ingestion with real-time progress tracking. When you upload a file, it's processed in the background and you can poll for status updates.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Collection** | A knowledge base that stores document chunks with embeddings |
| **Ingestion Job** | A background task that processes a file into chunks |
| **Plugin** | A processor that converts files into chunks (e.g., `markitdown_plus_ingest`) |
| **Chunk** | A piece of text with metadata, stored in the vector database |

### Base URL

```
http://localhost:9090
```

---

## 2. Authentication

All API requests require Bearer token authentication:

```http
Authorization: Bearer {API_KEY}
```

**Default Key:** `0p3n-w3bu!` (configure via `LAMB_API_KEY` environment variable)

---

## 3. Ingestion Workflow

### 3.1 Standard Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION WORKFLOW                                    │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Upload File
────────────────────
POST /collections/{id}/ingest-file
     │
     ▼
┌─────────────────────────────────────┐
│ Response (immediate):               │
│ {                                   │
│   "status": "processing",           │
│   "file_registry_id": 123,  ◄────── Job ID for polling
│   "collection_id": 1,               │
│   "original_filename": "doc.pdf"    │
│ }                                   │
└─────────────────────────────────────┘

Step 2: Poll for Status (optional)
──────────────────────────────────
GET /collections/{id}/ingestion-jobs/{job_id}
     │
     ▼
┌─────────────────────────────────────┐
│ Response (while processing):        │
│ {                                   │
│   "status": "processing",           │
│   "progress": {                     │
│     "current": 2,                   │
│     "total": 5,                     │
│     "percentage": 40.0,             │
│     "message": "Processing images..." │
│   }                                 │
│ }                                   │
└─────────────────────────────────────┘

Step 3: Completion
──────────────────
┌─────────────────────────────────────┐
│ Response (completed):               │
│ {                                   │
│   "status": "completed",            │
│   "document_count": 25,             │
│   "progress": {                     │
│     "current": 25,                  │
│     "total": 25,                    │
│     "percentage": 100.0,            │
│     "message": "Completed: 25 chunks" │
│   }                                 │
│ }                                   │
└─────────────────────────────────────┘
```

### 3.2 Job Statuses

| Status | Description | Can Transition To |
|--------|-------------|-------------------|
| `processing` | Job is running | `completed`, `failed`, `cancelled` |
| `completed` | Successfully finished | - |
| `failed` | Error occurred | `processing` (via retry) |
| `cancelled` | Cancelled by user | - |

---

## 4. Ingestion Endpoints

### 4.1 Ingest File

Upload and process a file into a collection.

```http
POST /collections/{collection_id}/ingest-file
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | The file to upload |
| `plugin_name` | String | Yes | Plugin to use (e.g., `markitdown_plus_ingest`) |
| `plugin_params` | JSON String | No | Plugin parameters (default: `{}`) |

**Example - Basic:**

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_plus_ingest'
```

**Example - With Parameters:**

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={"image_descriptions": "llm", "chunking_mode": "by_section", "chunk_size": 1500}'
```

**Response:**

```json
{
  "collection_id": 1,
  "collection_name": "my-kb",
  "documents_added": 0,
  "success": true,
  "file_path": "/path/to/static/user/collection/abc123.pdf",
  "file_url": "http://localhost:9090/static/user/collection/abc123.pdf",
  "original_filename": "document.pdf",
  "plugin_name": "markitdown_plus_ingest",
  "file_registry_id": 123,
  "status": "processing"
}
```

> **Note:** `documents_added` is `0` initially because processing happens in the background. Poll the job status to get the final count.

### 4.2 Ingest URL

Process content from URLs.

```http
POST /collections/{collection_id}/ingest-url
Content-Type: application/json
Authorization: Bearer {token}
```

**Request Body:**

```json
{
  "urls": ["https://example.com/page1", "https://example.com/page2"],
  "plugin_name": "url_ingest",
  "plugin_params": {
    "chunk_size": 1000
  }
}
```

### 4.3 Ingest Base (No File)

For plugins that don't require file upload (e.g., YouTube transcripts).

```http
POST /collections/{collection_id}/ingest-base
Content-Type: application/json
Authorization: Bearer {token}
```

**Request Body:**

```json
{
  "plugin_name": "youtube_transcript_ingest",
  "plugin_params": {
    "video_url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
    "language": "en"
  }
}
```

---

## 5. Monitoring Ingestion Jobs

### 5.1 Get Job Status

Get detailed status of a specific ingestion job.

```http
GET /collections/{collection_id}/ingestion-jobs/{job_id}
Authorization: Bearer {token}
```

**Response (Processing):**

```json
{
  "id": 123,
  "collection_id": 1,
  "original_filename": "report.pdf",
  "file_path": "/path/to/file.pdf",
  "file_url": "http://localhost:9090/static/user/collection/abc123.pdf",
  "status": "processing",
  "plugin_name": "markitdown_plus_ingest",
  "plugin_params": {
    "image_descriptions": "basic",
    "chunking_mode": "standard"
  },
  "document_count": 0,
  "progress": {
    "current": 2,
    "total": 5,
    "percentage": 40.0,
    "message": "Processing images..."
  },
  "processing_started_at": "2026-01-01T10:00:05Z",
  "processing_completed_at": null,
  "processing_duration_seconds": null,
  "error_message": null,
  "created_at": "2026-01-01T10:00:00Z",
  "updated_at": "2026-01-01T10:00:10Z"
}
```

**Response (Completed):**

```json
{
  "id": 123,
  "collection_id": 1,
  "original_filename": "report.pdf",
  "status": "completed",
  "document_count": 25,
  "progress": {
    "current": 25,
    "total": 25,
    "percentage": 100.0,
    "message": "Completed: 25 chunks from report.pdf"
  },
  "processing_started_at": "2026-01-01T10:00:05Z",
  "processing_completed_at": "2026-01-01T10:02:30Z",
  "processing_duration_seconds": 145.0,
  "error_message": null
}
```

**Response (Failed):**

```json
{
  "id": 124,
  "collection_id": 1,
  "original_filename": "corrupted.pdf",
  "status": "failed",
  "document_count": 0,
  "progress": {
    "current": 1,
    "total": 5,
    "percentage": 20.0,
    "message": "Failed: Invalid PDF format"
  },
  "processing_started_at": "2026-01-01T11:00:01Z",
  "processing_completed_at": "2026-01-01T11:00:10Z",
  "processing_duration_seconds": 9.0,
  "error_message": "Document conversion failed: Invalid PDF format",
  "error_details": {
    "exception_type": "ValueError",
    "traceback": "...",
    "file_path": "/path/to/file.pdf",
    "plugin_name": "markitdown_plus_ingest"
  }
}
```

### 5.2 List Ingestion Jobs

Get all ingestion jobs for a collection.

```http
GET /collections/{collection_id}/ingestion-jobs?status=processing&limit=50&offset=0
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | String | - | Filter by status (`processing`, `completed`, `failed`, `cancelled`) |
| `limit` | Integer | 50 | Max results (1-200) |
| `offset` | Integer | 0 | Pagination offset |
| `sort_by` | String | `created_at` | Sort field |
| `sort_order` | String | `desc` | Sort order (`asc`, `desc`) |

**Response:**

```json
{
  "total": 15,
  "items": [
    {
      "id": 123,
      "original_filename": "report.pdf",
      "status": "completed",
      "document_count": 25,
      "progress": {...},
      "created_at": "2026-01-01T10:00:00Z"
    },
    {
      "id": 122,
      "original_filename": "slides.pptx",
      "status": "processing",
      "document_count": 0,
      "progress": {...},
      "created_at": "2026-01-01T09:55:00Z"
    }
  ]
}
```

### 5.3 Get Ingestion Status Summary

Get a summary of all jobs in a collection.

```http
GET /collections/{collection_id}/ingestion-status
Authorization: Bearer {token}
```

**Response:**

```json
{
  "collection_id": 1,
  "total_jobs": 15,
  "by_status": {
    "completed": 12,
    "processing": 2,
    "failed": 1,
    "cancelled": 0
  },
  "recent_failures": [
    {
      "id": 124,
      "original_filename": "corrupted.pdf",
      "error_message": "Invalid PDF format",
      "updated_at": "2026-01-01T11:00:10Z"
    }
  ]
}
```

### 5.4 Retry Failed Job

Re-queue a failed job for processing.

```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/retry
Content-Type: application/json
Authorization: Bearer {token}
```

**Request Body (Optional):**

```json
{
  "new_params": {
    "chunk_size": 1200
  }
}
```

### 5.5 Cancel Processing Job

Cancel an in-progress job.

```http
POST /collections/{collection_id}/ingestion-jobs/{job_id}/cancel
Authorization: Bearer {token}
```

---

## 6. Available Plugins

### 6.1 List Plugins

```http
GET /ingestion/plugins
Authorization: Bearer {token}
```

**Response:**

```json
[
  {
    "name": "markitdown_plus_ingest",
    "kind": "file-ingest",
    "description": "Enhanced file ingestion with LLM image descriptions and multiple chunking strategies",
    "supported_file_types": ["pdf", "pptx", "docx", "xlsx", "html", "epub", ...],
    "parameters": {...}
  },
  {
    "name": "simple_ingest",
    "kind": "file-ingest",
    "description": "Ingest text files with configurable chunking options",
    "supported_file_types": ["txt", "md"],
    "parameters": {...}
  }
]
```

### 6.2 Plugin: `markitdown_plus_ingest` (Recommended)

Enhanced plugin for document ingestion with optional image extraction and multiple chunking strategies.

> ℹ️ **PRIVACY**: This plugin processes documents **locally by default**. External API calls to OpenAI only occur when `image_descriptions="llm"` is explicitly enabled. Use `"none"` (default) or `"basic"` for sensitive documents.

**Supported File Types:**
```
pdf, pptx, docx, xlsx, xls, mp3, wav, html, csv, json, xml, zip, epub
```

**Parameters by Chunking Mode:**

#### Common Parameters (all modes)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_descriptions` | String | `"none"` | `"none"` (local), `"basic"` (local), `"llm"` (⚠️ OpenAI) |
| `chunking_mode` | String | `"standard"` | `"standard"`, `"by_page"`, `"by_section"` |
| `description` | String | - | Optional document description |
| `citation` | String | - | Optional citation reference |

#### Standard Mode Parameters (`chunking_mode: "standard"`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | Integer | 1000 | Target chunk size (characters) |
| `chunk_overlap` | Integer | 200 | Overlap between chunks |
| `splitter_type` | String | `"RecursiveCharacterTextSplitter"` | Text splitter algorithm |

#### Page Mode Parameters (`chunking_mode: "by_page"`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pages_per_chunk` | Integer | 1 | Number of pages per chunk |

*Only works with PDF, DOCX, PPTX files. Falls back to standard mode for other formats.*

#### Section Mode Parameters (`chunking_mode: "by_section"`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `split_on_heading` | Integer | 2 | Heading level to split on (1=H1, 2=H2, 3=H3) |
| `headings_per_chunk` | Integer | 1 | Number of sections per chunk |

*Sections from different parent headings are never mixed. Parent titles are preserved as context.*

**Image Description Modes:**

| Mode | Processing | External API | Safe for Sensitive Data |
|------|------------|--------------|-------------------------|
| `none` | Keep original image links, no extraction | ❌ None | ✅ **YES** (default) |
| `basic` | Extract images with filename-based descriptions | ❌ None | ✅ **YES** |
| `llm` | Extract images + AI descriptions | ⚠️ **OpenAI** | ❌ **NO** |

> **⚠️ LLM Mode Warning**: When `image_descriptions: "llm"` is enabled, images are sent to OpenAI's servers. Do NOT use for confidential documents.

**Chunking Modes Explained:**

| Mode | How It Works | Best For |
|------|--------------|----------|
| `standard` | Character-based splitting with overlap | General use, unstructured text |
| `by_page` | Split on page boundaries | PDFs, presentations with clear page structure |
| `by_section` | Split on headings, preserving hierarchy | Structured documents (reports, manuals) |

**Section Mode Example:**

Given a document with this structure:
```markdown
# Chapter 1
## Section A
### Topic 1
### Topic 2
## Section B
### Topic 3
```

With `split_on_heading: 3` and `headings_per_chunk: 2`:
- Chunk 1: `# Chapter 1` → `## Section A` → `### Topic 1` + `### Topic 2`
- Chunk 2: `# Chapter 1` (title) → `## Section B` → `### Topic 3`

Parent headings are preserved as context, but their content only appears in the first chunk.

**Example - Standard Mode:**

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={"chunk_size": 1000, "chunk_overlap": 200}'
```

**Example - Section Mode:**

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@annual-report.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={
    "chunking_mode": "by_section",
    "split_on_heading": 2,
    "headings_per_chunk": 1,
    "description": "Annual Report 2025"
  }'
```

### 6.3 Plugin: `markitdown_ingest` (Legacy)

Original MarkItDown plugin. Use `markitdown_plus_ingest` for new integrations.

### 6.4 Plugin: `simple_ingest`

Simple text/markdown ingestion.

**Supported File Types:** `txt`, `md`

**Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `chunk_size` | Integer | 1000 |
| `chunk_overlap` | Integer | 200 |
| `splitter_type` | String | `"RecursiveCharacterTextSplitter"` |

### 6.5 Plugin: `youtube_transcript_ingest`

Ingest YouTube video transcripts.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video_url` | String | Yes | YouTube video URL |
| `language` | String | No | Subtitle language (default: `"en"`) |
| `chunk_duration` | Integer | No | Target chunk duration in seconds (default: 60) |

---

## 7. Chunk Metadata Reference

Each chunk stored in the collection includes metadata. The structure varies by plugin.

### 7.1 `markitdown_plus_ingest` Metadata

```json
{
  "text": "The actual chunk content...",
  "metadata": {
    // ═══════════════════════════════════════════════════════════════════
    // FILE IDENTIFICATION
    // ═══════════════════════════════════════════════════════════════════
    "source": "/path/to/static/user/collection/abc123.pdf",
    "filename": "annual-report.pdf",
    "extension": "pdf",
    "file_size": 2456789,
    
    // ═══════════════════════════════════════════════════════════════════
    // FILE URLS (New in markitdown_plus_ingest)
    // ═══════════════════════════════════════════════════════════════════
    "original_file_url": "http://localhost:9090/static/user/collection/abc123.pdf",
    "markdown_file_url": "http://localhost:9090/static/user/collection/abc123.md",
    "images_folder_url": "http://localhost:9090/static/user/collection/abc123/",
    "file_url": "http://localhost:9090/static/user/collection/abc123.pdf",  // Legacy
    
    // ═══════════════════════════════════════════════════════════════════
    // IMAGE INFORMATION
    // ═══════════════════════════════════════════════════════════════════
    "image_description_mode": "basic",
    "images_extracted": 5,
    
    // ═══════════════════════════════════════════════════════════════════
    // CHUNKING INFORMATION
    // ═══════════════════════════════════════════════════════════════════
    "chunk_index": 0,
    "chunk_count": 25,
    "chunking_strategy": "by_section",  // or "standard_recursivecharactertextsplitter", "by_page"
    
    // Strategy-specific fields:
    "chunk_size": 1000,           // for standard mode
    "chunk_overlap": 200,          // for standard mode
    "pages_per_chunk": 1,          // for by_page mode
    "page_range": "1-2",           // for by_page mode
    "split_on_heading": 2,         // for by_section mode
    "headings_per_chunk": 1,       // for by_section mode
    "section_titles": ["## Section A"],  // for by_section mode
    "parent_path": "# Chapter 1",  // for by_section mode (parent context)
    
    // ═══════════════════════════════════════════════════════════════════
    // USER-PROVIDED METADATA
    // ═══════════════════════════════════════════════════════════════════
    "description": "Annual Report 2025",
    "citation": "Company XYZ",
    
    // ═══════════════════════════════════════════════════════════════════
    // SYSTEM METADATA (added during embedding)
    // ═══════════════════════════════════════════════════════════════════
    "document_id": "a1b2c3d4e5f6...",
    "ingestion_timestamp": "2026-01-01T10:02:30.000Z",
    "embedding_vendor": "openai",
    "embedding_model": "text-embedding-3-small"
  }
}
```

### 7.2 URL Fields Explained

| Field | Description | Example |
|-------|-------------|---------|
| `original_file_url` | URL to the uploaded file (PDF, DOCX, etc.) | `.../abc123.pdf` |
| `markdown_file_url` | URL to the converted Markdown file | `.../abc123.md` |
| `images_folder_url` | URL to the folder containing extracted images | `.../abc123/` |
| `file_url` | Legacy field (equals `original_file_url`) | `.../abc123.pdf` |

### 7.3 Accessing Extracted Images

Images are stored in a subfolder named after the file:

```
http://localhost:9090/static/{owner}/{collection}/{file_uuid}/
├── image_001.png
├── image_002.jpg
└── image_003.gif
```

Images are referenced in the Markdown with their full URLs:

```markdown
![Diagram showing system architecture](http://localhost:9090/static/user/my-kb/abc123/image_001.png)
```

### 7.4 Legacy Plugin Metadata

Older plugins (`markitdown_ingest`, `simple_ingest`) use a simpler metadata structure:

```json
{
  "text": "chunk content...",
  "metadata": {
    "source": "/path/to/file",
    "filename": "document.pdf",
    "file_url": "http://localhost:9090/static/.../file.html",
    "chunk_index": 0,
    "chunk_count": 25,
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```

---

## 8. Error Handling

### 8.1 HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (invalid token) |
| 404 | Not Found (collection/job/plugin not found) |
| 500 | Internal Server Error |

### 8.2 Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

### 8.3 Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Plugin 'xyz' not found` | Invalid plugin name | Check available plugins via `GET /ingestion/plugins` |
| `Collection not found` | Invalid collection ID | Verify collection exists |
| `Invalid JSON in plugin_params` | Malformed JSON | Validate JSON syntax |
| `Document conversion failed` | Unsupported/corrupted file | Check file format, try different plugin |

### 8.4 Graceful Degradation

The `markitdown_plus_ingest` plugin handles missing features gracefully:

| Condition | Behavior |
|-----------|----------|
| `image_descriptions="llm"` but no OpenAI key | Falls back to `"none"` mode |
| `chunking_mode="by_page"` on HTML file | Falls back to `"standard"` mode |
| `chunking_mode="by_section"` but no headings found | Falls back to `"standard"` mode |
| Image extraction fails | Continues processing, logs warning |

---

## 9. Best Practices

### 9.1 Polling Strategy

```javascript
async function waitForIngestion(collectionId, jobId, maxWaitMs = 300000) {
  const pollInterval = 2000; // 2 seconds
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitMs) {
    const response = await fetch(
      `${BASE_URL}/collections/${collectionId}/ingestion-jobs/${jobId}`,
      { headers: { 'Authorization': `Bearer ${API_KEY}` } }
    );
    
    const job = await response.json();
    
    if (job.status === 'completed') {
      return { success: true, chunks: job.document_count };
    }
    
    if (job.status === 'failed') {
      return { success: false, error: job.error_message };
    }
    
    if (job.status === 'cancelled') {
      return { success: false, error: 'Job cancelled' };
    }
    
    // Log progress
    console.log(`Progress: ${job.progress.percentage}% - ${job.progress.message}`);
    
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  return { success: false, error: 'Timeout waiting for ingestion' };
}
```

### 9.2 Choosing the Right Plugin

| File Type | Recommended Plugin | Notes |
|-----------|-------------------|-------|
| PDF, DOCX, PPTX | `markitdown_plus_ingest` | Use `by_page` or `by_section` chunking |
| Plain text, Markdown | `simple_ingest` | Fastest for simple files |
| HTML | `markitdown_plus_ingest` | Handles complex HTML well |
| YouTube videos | `youtube_transcript_ingest` | Requires video URL |
| Pre-chunked JSON | `mockai_json_ingest` | For already-processed data |

### 9.3 Optimizing Chunk Size

| Use Case | Recommended `chunk_size` |
|----------|-------------------------|
| Q&A / Chat | 500-1000 |
| Document summarization | 1500-2500 |
| Code documentation | 800-1200 |
| Legal documents | 1000-1500 |

### 9.4 Using LLM Image Descriptions

To enable AI-powered image descriptions:

1. **Create collection with OpenAI embeddings:**
```json
{
  "name": "my-kb",
  "owner": "user@example.com",
  "embeddings_model": {
    "vendor": "openai",
    "model": "text-embedding-3-small",
    "apikey": "sk-your-key-here"
  }
}
```

2. **Ingest with `image_descriptions: "llm"`:**
```json
{
  "image_descriptions": "llm",
  "chunking_mode": "by_section"
}
```

The plugin will automatically use the collection's OpenAI API key for image descriptions.

---

## 10. Data Privacy Guidelines

### 10.1 Understanding External API Usage

When you ingest documents, some plugins may send data to external services:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA FLOW - EXTERNAL API USAGE                            │
└─────────────────────────────────────────────────────────────────────────────┘

Your Document
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAMB KB Server                                                              │
│                                                                              │
│  ┌─────────────────────┐     ┌─────────────────────────────────────────┐   │
│  │  Plugin Processing   │     │  External API Calls (only if enabled)   │   │
│  │  (LOCAL by default)  │     │                                          │   │
│  │                      │     │  ⚠️ OpenAI Vision API                   │   │
│  │  • File conversion   │────►│     (ONLY for image_descriptions="llm") │   │
│  │  • Image extraction  │     │                                          │   │
│  │  • Text chunking     │     │  All other processing is LOCAL.          │   │
│  └─────────────────────┘     │  MarkItDown does NOT use external APIs.  │   │
│           │                   └─────────────────────────────────────────┘   │
│  ┌─────────────────────┐                                                    │
│  │  ChromaDB Storage    │  ◄── Only embeddings & chunks stored locally     │
│  └─────────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Data Types to Avoid

**DO NOT ingest documents containing:**

| Data Type | Examples | Regulation |
|-----------|----------|------------|
| **PII** (Personal Identifiable Information) | Names, SSN, addresses, phone numbers | GDPR, CCPA |
| **PHI** (Protected Health Information) | Medical records, diagnoses, prescriptions | HIPAA |
| **Financial Data** | Bank accounts, credit cards, tax returns | PCI-DSS, SOX |
| **Authentication Secrets** | Passwords, API keys, tokens | Security best practices |
| **Confidential Business** | Trade secrets, internal strategies | NDA compliance |

### 10.3 Safe Configuration for Sensitive Documents

If you must process documents that may contain sensitive information, use this configuration:

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer {token}' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=simple_ingest'
```

Or with `markitdown_plus_ingest` in safe mode:

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer {token}' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={"image_descriptions": "none"}'
```

### 10.4 Plugin Privacy Matrix

| Plugin | External APIs | Recommended For |
|--------|---------------|-----------------|
| `simple_ingest` | ✅ None | Sensitive documents, text files |
| `markitdown_plus_ingest` (default) | ✅ None | All documents (default is fully local) |
| `markitdown_plus_ingest` (`image_descriptions="llm"`) | ⚠️ OpenAI | Public content only |
| `markitdown_ingest` | ✅ None | Legacy - local processing |
| `youtube_transcript_ingest` | ⚠️ YouTube | Public videos only |

The MarkItDown library processes files locally. External APIs are only used when explicitly configured.

### 10.5 Client Responsibilities

API clients **MUST**:

1. **Display privacy warnings** to end users before file upload
2. **Obtain consent** for external API data transmission
3. **Filter sensitive documents** before ingestion
4. **Document data flows** for compliance audits
5. **Use safe plugin configurations** for regulated industries

### 10.6 Example: Privacy-Aware Upload UI

```javascript
async function uploadDocument(file, collectionId, pluginParams) {
  // Check if LLM mode is enabled
  if (pluginParams.image_descriptions === 'llm') {
    const confirmed = await showPrivacyWarning(
      "⚠️ External API Warning",
      "This option will send images from your document to OpenAI's servers. " +
      "Do not use this for documents containing personal, sensitive, or confidential information.\n\n" +
      "Continue with external processing?"
    );
    
    if (!confirmed) {
      // Fall back to safe mode
      pluginParams.image_descriptions = 'basic';
    }
  }
  
  // Proceed with upload
  return fetch(`${BASE_URL}/collections/${collectionId}/ingest-file`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${API_KEY}` },
    body: createFormData(file, pluginParams)
  });
}
```

---

## Appendix A: Migration from Legacy Plugins

### From `markitdown_ingest` to `markitdown_plus_ingest`

**Backwards Compatible:** Yes. All existing parameters work unchanged.

**New Features Available:**
- `image_descriptions` parameter
- `chunking_mode` parameter (`by_page`, `by_section`)
- Separate URL fields in metadata

**Migration Steps:**
1. Change `plugin_name` from `markitdown_ingest` to `markitdown_plus_ingest`
2. (Optional) Add new parameters for enhanced features
3. Update metadata parsing to use new URL fields

### Metadata Field Mapping

| Legacy Field | New Field | Notes |
|--------------|-----------|-------|
| `file_url` | `original_file_url` | Legacy field still available |
| - | `markdown_file_url` | New: URL to .md file |
| - | `images_folder_url` | New: URL to images folder |
| - | `images_extracted` | New: count of extracted images |

---

## Appendix B: Quick Reference

### Ingest File
```bash
curl -X POST 'http://localhost:9090/collections/{id}/ingest-file' \
  -H 'Authorization: Bearer {token}' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={"chunking_mode": "by_section"}'
```

### Check Job Status
```bash
curl 'http://localhost:9090/collections/{id}/ingestion-jobs/{job_id}' \
  -H 'Authorization: Bearer {token}'
```

### List All Jobs
```bash
curl 'http://localhost:9090/collections/{id}/ingestion-jobs?status=processing' \
  -H 'Authorization: Bearer {token}'
```

### Get Summary
```bash
curl 'http://localhost:9090/collections/{id}/ingestion-status' \
  -H 'Authorization: Bearer {token}'
```

### Retry Failed Job
```bash
curl -X POST 'http://localhost:9090/collections/{id}/ingestion-jobs/{job_id}/retry' \
  -H 'Authorization: Bearer {token}'
```

### Cancel Job
```bash
curl -X POST 'http://localhost:9090/collections/{id}/ingestion-jobs/{job_id}/cancel' \
  -H 'Authorization: Bearer {token}'
```

---

**Document Version:** 1.3.0  
**Last Updated:** January 2026  
**Maintainers:** LAMB Development Team

