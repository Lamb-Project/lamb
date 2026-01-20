# Comprehensive Commit: Enhanced Ingestion Status Reporting & Processing Statistics

**Date:** January 2, 2026  
**Author:** LAMB Development Team  
**Type:** Feature Enhancement  
**Scope:** KB Server, LAMB Backend, Frontend

---

## Summary

This commit introduces comprehensive processing statistics tracking for document ingestion in the LAMB Knowledge Base system. It provides detailed visibility into what happens during document processing, including stage-by-stage timing, LLM API call tracking, chunk statistics, and output artifact links.

**Key Features:**
- 📊 Detailed processing statistics with stage timings
- 🤖 Individual LLM API call tracking (duration, tokens, success/failure)
- 📈 Chunk statistics (count, avg/min/max size)
- 📁 Output artifact links (markdown, images folder, original file)
- 👁️ Markdown content preview
- 🔄 Manual refresh button for job status
- 🎛️ Dynamic plugin parameter UI with conditional visibility

---

## Files Changed (18 files, +3,761 / -1,130 lines)

### LAMB KB Server - Database Layer

#### `lamb-kb-server-stable/database/models.py` (+190 lines)
- Added `processing_stats` JSON column to `FileRegistry` model
- Comprehensive schema documentation for the JSON structure:
  ```python
  processing_stats = Column(JSON, nullable=True, default=None)
  # Schema:
  # {
  #     "content_length": int,
  #     "images_extracted": int,
  #     "images_with_llm_descriptions": int,
  #     "llm_calls": [{"image": str, "duration_ms": int, "tokens_used": int, "success": bool}],
  #     "total_llm_duration_ms": int,
  #     "chunking_strategy": str,
  #     "chunk_stats": {"count": int, "avg_size": float, "min_size": int, "max_size": int},
  #     "stage_timings": [{"stage": str, "duration_ms": int, "message": str, "timestamp": str}],
  #     "output_files": {"markdown_url": str, "images_folder_url": str, "original_file_url": str},
  #     "markdown_preview": str
  # }
  ```
- Updated `to_dict()` and `to_job_dict()` methods to include `processing_stats`

#### `lamb-kb-server-stable/database/connection.py` (+73 lines)
- Added `run_migrations()` function for automatic schema migrations at startup
- Implemented migration for `processing_stats` column (Jan 2026)
- Uses SQLAlchemy's `text()` for raw SQL execution
- Integrated into `init_databases()` with proper logging
- Safe migration: checks if column exists before adding

### LAMB KB Server - API Schema

#### `lamb-kb-server-stable/schemas/files.py` (+611 lines)
- Added comprehensive Pydantic models for processing statistics:

| Model | Description |
|-------|-------------|
| `LLMCallDetail` | Individual LLM API call tracking (image, duration_ms, tokens_used, success, error) |
| `ChunkStats` | Chunk statistics (count, avg_size, min_size, max_size) |
| `StageTiming` | Processing stage timing (stage, duration_ms, message, timestamp) |
| `OutputFiles` | URLs to generated artifacts (markdown_url, images_folder_url, original_file_url) |
| `ProcessingStats` | Main container combining all statistics |

- Updated `IngestionJobResponse` to include `processing_stats: Optional[ProcessingStats]`
- Added comprehensive JSON schema examples for API documentation

### LAMB KB Server - Routers

#### `lamb-kb-server-stable/routers/collections.py` (+567 lines, significant refactoring)
- Added `stats_callback` mechanism in `process_file_in_background_enhanced()`
- Background processor now:
  - Creates `stats_callback` closure to capture processing stats
  - Passes callback to plugin via `params_with_callback`
  - Saves `processing_stats` to `file_registry` on job completion
- Key code addition:
  ```python
  # Create a stats callback to capture processing statistics
  captured_stats = {}
  def stats_callback(stats: dict):
      nonlocal captured_stats
      captured_stats = stats
  
  # ... later on completion:
  if captured_stats:
      file_reg.processing_stats = captured_stats
  ```

#### `lamb-kb-server-stable/routers/ingestion_status.py` (NEW FILE)
- New router for ingestion status API endpoints
- Endpoints:
  - `GET /collections/{id}/ingestion-jobs` - List jobs with filtering/pagination
  - `GET /collections/{id}/ingestion-jobs/{job_id}` - Get single job status
  - `GET /collections/{id}/ingestion-status` - Get status summary
  - `POST /collections/{id}/ingestion-jobs/{job_id}/retry` - Retry failed job
  - `POST /collections/{id}/ingestion-jobs/{job_id}/cancel` - Cancel job
- Helper function `_file_registry_to_job_response()` handles `processing_stats` parsing

### LAMB KB Server - Plugins

#### `lamb-kb-server-stable/plugins/markitdown_plus_ingest.py` (NEW FILE, 1033 lines)
- **Version 1.3.0** - Enhanced plugin with comprehensive stats tracking

**New `ProcessingStatsTracker` class (lines 50-153):**
```python
class ProcessingStatsTracker:
    """Helper class to track detailed processing statistics during ingestion."""
    
    def start_stage(self, stage_name: str): ...
    def end_stage(self, message: str) -> int: ...
    def record_llm_call(self, image, duration_ms, success, error, tokens_used): ...
    def calculate_chunk_stats(self, chunks: List[str]): ...
    def set_markdown_preview(self, content: str, max_length: int = 2000): ...
    def to_dict(self) -> Dict[str, Any]: ...
```

**Statistics tracked during ingestion:**

| Stage | What's Tracked |
|-------|----------------|
| `conversion` | Document → Markdown conversion time |
| `image_extraction` | Image extraction count and time |
| `llm_descriptions` | Individual LLM API calls with timing |
| `chunking` | Chunk creation with strategy and stats |
| `finalization` | Markdown save and URL generation |

**Updated methods:**
- `_generate_image_description()` - Now tracks LLM call timing, tokens, success/failure
- `_extract_and_process_images()` - Accepts `stats_tracker` parameter
- `ingest()` - Full stats tracking with `stats_callback` support

#### `lamb-kb-server-stable/plugins/base.py` (+55 lines)
- Enhanced `IngestPlugin` base class
- Added `get_parameters()` method for plugin parameter introspection
- Added `report_progress()` helper for progress callback support
- New parameter metadata fields:
  - `ui_hint`: Rendering hint (select, slider, number, textarea, info)
  - `visible_when`: Conditional visibility based on other parameter values
  - `enum_labels`: Human-readable labels for enum values
  - `help_text`: Additional help text for UI
  - `applicable_to`: File types this parameter applies to

#### `lamb-kb-server-stable/plugins/markitdown-ingest-plugin.py` (+22 lines)
- Updated to use new parameter specification format

#### `lamb-kb-server-stable/plugins/url_ingest.py` (+13 lines)
- Updated to use new parameter specification format

#### `lamb-kb-server-stable/plugins/youtube_transcript_ingest.py` (+27 lines)
- Updated to use new parameter specification format

### LAMB Backend - Proxy Layer

#### `backend/creator_interface/knowledges_router.py` (+441 lines)
- **Added `processing_stats` to `IngestionJobResponse` model** (critical fix!)
  ```python
  class IngestionJobResponse(BaseModel):
      # ... existing fields ...
      processing_stats: Optional[Dict[str, Any]] = None  # Added Jan 2026
  ```
- New ingestion status API proxy endpoints
- Plugin parameter introspection endpoints
- File ingestion with progress tracking

#### `backend/creator_interface/kb_server_manager.py` (+330 lines)
- Added methods for ingestion job management:
  - `list_ingestion_jobs()`
  - `get_ingestion_job_status()`
  - `get_ingestion_status_summary()`
  - `retry_ingestion_job()`
  - `cancel_ingestion_job()`
- Plugin parameter fetching from KB server

### Frontend - Svelte Application

#### `frontend/svelte-app/src/lib/services/knowledgeBaseService.js` (+418 lines)
- **New TypeScript typedefs for processing statistics:**
  ```javascript
  /**
   * @typedef {Object} LLMCallDetail
   * @property {string} image
   * @property {number} duration_ms
   * @property {boolean} success
   * @property {number} [tokens_used]
   * @property {string} [error]
   */

  /**
   * @typedef {Object} ProcessingStats
   * @property {number} content_length
   * @property {number} images_extracted
   * @property {number} images_with_llm_descriptions
   * @property {LLMCallDetail[]} llm_calls
   * @property {number} total_llm_duration_ms
   * @property {string} [chunking_strategy]
   * @property {ChunkStats} [chunk_stats]
   * @property {StageTiming[]} stage_timings
   * @property {OutputFiles} [output_files]
   * @property {string} [markdown_preview]
   */
  ```
- Updated `IngestionJob` typedef to include `processing_stats`
- New API functions:
  - `listIngestionJobs()`
  - `getIngestionJobStatus()`
  - `retryIngestionJob()`
  - `cancelIngestionJob()`
  - `getIngestionPlugins()`

#### `frontend/svelte-app/src/lib/components/KnowledgeBaseDetail.svelte` (+1030 lines)
- **New TypeScript typedefs** for all processing stats models
- **New helper functions:**
  ```javascript
  function refreshSelectedJob()    // Refresh job status via API
  function formatMilliseconds(ms)  // Human-readable duration
  function formatNumber(num)       // Thousands separator
  ```

- **Enhanced Job Detail Modal with new sections:**

| Section | Description |
|---------|-------------|
| **Processing Statistics** | Blue-themed card showing content length, chunks, images, LLM calls |
| **LLM Call Details** | Expandable list showing each API call's image, timing, tokens, success |
| **Processing Log** | Table with stage-by-stage timing breakdown |
| **Output Artifacts** | Clickable links to markdown file, images folder, original file |
| **Markdown Preview** | Expandable code block with first 2000 chars of converted content |
| **Refresh Button** | Manual refresh of job status without closing modal |

- **Conditional rendering:**
  ```svelte
  {#if selectedJob.processing_stats}
      {@const stats = selectedJob.processing_stats}
      <!-- Processing Statistics section -->
      <!-- Processing Log section -->
      <!-- Output Artifacts section -->
      <!-- Markdown Preview section -->
  {/if}
  ```

### Documentation

#### `lamb-kb-server-stable/Docs/ingestion-status-api.md` (NEW FILE, 791 lines)
- Comprehensive API documentation for ingestion status endpoints
- Status model and lifecycle diagrams
- Request/response examples
- Client integration guide with JavaScript/React examples
- Error handling guide
- Best practices for polling and UI/UX

#### `lamb-kb-server-stable/Docs/ingestion-api-client-guide.md` (NEW FILE)
- Client guide for the ingestion API
- Plugin documentation
- Privacy notices for LLM-powered features

#### `lamb-kb-server-stable/Docs/markitdown-plus-plugin-spec.md` (NEW FILE)
- Detailed specification for markitdown_plus_ingest plugin
- Parameter documentation with UI hints

#### `lamb-kb-server-stable/Docs/lamb-kb-server_architecture.md` (+199 lines)
- Updated architecture documentation
- Added processing statistics schema
- Updated FileRegistry model documentation

### Other Changes

#### `backend/lamb/completions/rag/context_aware_rag.py` (+55 lines)
#### `backend/lamb/completions/rag/simple_rag.py` (+55 lines)
- RAG improvements (separate feature)

---

## Database Migration

The system automatically migrates the database at startup:

```sql
ALTER TABLE file_registry ADD COLUMN processing_stats TEXT DEFAULT NULL
```

**Migration is safe:**
- Checks if column exists before adding
- Logged to console: `INFO: [migration] Added processing_stats column to file_registry table`
- Existing jobs will have `processing_stats = NULL`

---

## How to Use

### For New Ingestion Jobs

1. Upload a file using `markitdown_plus_ingest` plugin
2. The plugin automatically tracks:
   - Stage timings (conversion, image extraction, chunking, finalization)
   - LLM API calls (if `image_descriptions: "llm"`)
   - Chunk statistics
   - Output file URLs
   - Markdown preview

3. View detailed stats in the job detail modal

### For Existing Jobs

- Existing completed jobs will show `processing_stats: null`
- **Retry the job** to get full statistics
- Or ingest new files

### Frontend Job Detail Modal

The modal now shows (when stats available):

```
┌─────────────────────────────────────────────┐
│ FILE INFORMATION                            │
│   Filename, Size, Content Type, Plugin      │
├─────────────────────────────────────────────┤
│ PROCESSING DETAILS                          │
│   Job ID, Documents Created, Duration, etc  │
├─────────────────────────────────────────────┤
│ 📊 PROCESSING STATISTICS (blue card)        │
│   Content Length: 45,230 characters         │
│   Chunks: 45 (avg 1005 chars)               │
│   Images Extracted: 12                      │
│   LLM API Calls: 12 (12 successful)         │
│   Total LLM Time: 15.8s                     │
│   ▶ Show LLM call details (expandable)      │
├─────────────────────────────────────────────┤
│ 📋 PROCESSING LOG (table)                   │
│   Stage      │ Duration │ Details           │
│   conversion │ 2.3s     │ PDF → Markdown    │
│   chunking   │ 0.5s     │ 45 chunks         │
│   ...                                       │
├─────────────────────────────────────────────┤
│ 📁 OUTPUT ARTIFACTS (buttons)               │
│   [Markdown] [Images (12)] [Original]       │
├─────────────────────────────────────────────┤
│ 👁️ MARKDOWN PREVIEW (expandable)            │
│   # Chapter 1...                            │
├─────────────────────────────────────────────┤
│                           [🔄] [Retry] [Close]│
└─────────────────────────────────────────────┘
```

---

## API Changes

### New Fields in `IngestionJobResponse`

```json
{
  "id": 5,
  "status": "completed",
  "document_count": 45,
  "processing_stats": {
    "content_length": 45230,
    "images_extracted": 12,
    "images_with_llm_descriptions": 12,
    "llm_calls": [
      {"image": "image_001.png", "duration_ms": 1234, "tokens_used": 150, "success": true}
    ],
    "total_llm_duration_ms": 15800,
    "chunking_strategy": "by_section",
    "chunk_stats": {"count": 45, "avg_size": 1005.1, "min_size": 234, "max_size": 1499},
    "stage_timings": [
      {"stage": "conversion", "duration_ms": 2300, "message": "PDF → Markdown", "timestamp": "2026-01-02T10:30:03Z"}
    ],
    "output_files": {
      "markdown_url": "http://localhost:9090/static/user/kb/doc.md",
      "images_folder_url": "http://localhost:9090/static/user/kb/doc/",
      "original_file_url": "http://localhost:9090/static/user/kb/doc.pdf"
    },
    "markdown_preview": "# Chapter 1\n\nThis document..."
  }
}
```

---

## Breaking Changes

None. All changes are additive and backward compatible.

- Existing jobs will have `processing_stats: null`
- API response structure unchanged (new field is optional)
- Frontend gracefully handles missing stats

---

## Testing Checklist

- [ ] Restart KB server - verify migration runs
- [ ] Restart LAMB backend - verify `processing_stats` passes through
- [ ] Restart frontend container
- [ ] Upload new PDF with `markitdown_plus_ingest`
- [ ] Verify Processing Statistics section appears
- [ ] Verify Processing Log table shows stage timings
- [ ] Verify Output Artifacts links work
- [ ] Verify Markdown Preview shows content
- [ ] Test refresh button updates job status
- [ ] Test with `image_descriptions: "llm"` to see LLM call tracking

---

## Commit Message

```
feat(kb-server): Add comprehensive processing statistics for ingestion jobs

- Add processing_stats JSON column to file_registry with auto-migration
- Create ProcessingStatsTracker class in markitdown_plus_ingest plugin
- Track stage timings, LLM calls, chunk stats, output files, markdown preview
- Add stats_callback mechanism in background processor
- Update API schemas with ProcessingStats, LLMCallDetail, ChunkStats, etc.
- Add processing_stats to LAMB backend IngestionJobResponse proxy model
- Update frontend with Processing Statistics, Log, Artifacts, Preview sections
- Add refresh button for manual job status polling
- Add comprehensive API documentation

Closes #KB-INGESTION-STATS
```

---

**Files Changed:** 18  
**Lines Added:** ~3,761  
**Lines Removed:** ~1,130  
**Net Change:** +2,631 lines

