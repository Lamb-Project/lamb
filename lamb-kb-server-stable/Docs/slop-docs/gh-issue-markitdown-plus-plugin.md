# Feature: MarkItDown Plus Ingestion Plugin

## Summary

New enhanced document ingestion plugin (`markitdown_plus_ingest`) that provides LLM-powered image descriptions, multiple chunking strategies, and proper image extraction with accessible URLs.

## ⚠️ Privacy Notice

This plugin includes a **privacy warning** for end users:

> **EXTERNAL API WARNING**: This plugin may transmit document content and images to external third-party services (OpenAI, Microsoft) for processing. Do NOT use for documents containing personal, sensitive, confidential, or regulated data (PII, PHI, GDPR, HIPAA). Use `simple_ingest` for sensitive documents.

The plugin exposes this warning via:
- `_privacy_warning` parameter in `get_parameters()` output
- `privacy_warning` class attribute
- Updated `help_text` for `image_descriptions` parameter

API clients **should display this warning** to users before file upload when using LLM features.

## Problem

The existing `markitdown_ingest` plugin has limitations:
- Images embedded in PDFs/DOCX files are either lost or left as broken references
- Only one chunking strategy (character-based) is available
- No way to generate meaningful descriptions for images
- Image files are not stored and cannot be viewed by clients

## Solution

### New Plugin: `markitdown_plus_ingest`

A drop-in replacement for `markitdown_ingest` with enhanced features while maintaining full backwards compatibility.

### Key Features

| Feature | Description |
|---------|-------------|
| **Image Extraction** | Extracts images from documents and stores them in accessible folders |
| **Image Descriptions** | Three modes: `none`, `basic` (filename-based), `llm` (AI-generated using OpenAI Vision) |
| **Multiple Chunking Strategies** | `standard`, `by_page`, `by_section` |
| **OpenAI Integration** | Automatically uses collection's OpenAI API key for LLM features |
| **Progress Reporting** | 5-stage progress tracking integrated with Ingestion Status API |
| **Full URL Metadata** | Chunks include URLs for original file, markdown file, and images folder |

### Image Storage Structure

```
static/{owner}/{collection}/
├── {uuid}.pdf                  # Original uploaded file
├── {uuid}.md                   # Converted markdown
└── {uuid}/                     # Images folder (subfolder named after file)
    ├── image_001.png
    ├── image_002.jpg
    └── image_003.gif
```

### Chunk Metadata

Each chunk now includes comprehensive URL references:

```json
{
  "original_file_url": "http://localhost:9090/static/user/collection/abc123.pdf",
  "markdown_file_url": "http://localhost:9090/static/user/collection/abc123.md",
  "images_folder_url": "http://localhost:9090/static/user/collection/abc123/",
  "images_extracted": 5,
  "image_description_mode": "basic",
  "chunking_strategy": "by_section",
  "chunk_index": 0,
  "chunk_count": 25
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_descriptions` | string | `"basic"` | `"none"`, `"basic"`, or `"llm"` |
| `chunking_mode` | string | `"standard"` | `"standard"`, `"by_page"`, `"by_section"` |
| `chunk_size` | integer | 1000 | Target chunk size (characters) |
| `chunk_overlap` | integer | 200 | Overlap between chunks |
| `pages_per_chunk` | integer | 1 | Pages per chunk (for `by_page` mode) |
| `max_heading_level` | integer | 3 | Max heading level for section splitting (1-6) |
| `max_section_size` | integer | 0 | Max section size before sub-splitting |
| `description` | string | - | Optional document description |
| `citation` | string | - | Optional citation reference |

### OpenAI API Key Flow

The plugin automatically retrieves the OpenAI API key from the collection's embeddings configuration:

```
Collection (embeddings_model.vendor == "openai")
    │
    └── apikey ──► Background Task ──► Plugin (openai_api_key param)
                                            │
                                            └── Used for LLM image descriptions
```

If the collection doesn't use OpenAI embeddings, the plugin gracefully falls back to `basic` image descriptions.

### Graceful Degradation

| Condition | Behavior |
|-----------|----------|
| `image_descriptions="llm"` but no OpenAI key | Falls back to `"basic"` |
| `chunking_mode="by_page"` on non-paged format | Falls back to `"standard"` |
| `chunking_mode="by_section"` but no headings | Falls back to `"standard"` |
| Image extraction fails | Continues processing, logs warning |

## Usage Example

```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@annual-report.pdf' \
  -F 'plugin_name=markitdown_plus_ingest' \
  -F 'plugin_params={
    "image_descriptions": "llm",
    "chunking_mode": "by_section",
    "max_heading_level": 2,
    "description": "Annual Report 2025"
  }'
```

## Files Changed

- `backend/plugins/markitdown_plus_ingest.py` - New plugin implementation
- `backend/routers/collections.py` - Wired OpenAI API key and collection context to background tasks
- `Docs/ingestion-api-client-guide.md` - New comprehensive API client documentation
- `Docs/markitdown-plus-plugin-spec.md` - Original specification

## Backwards Compatibility

✅ **Fully backwards compatible** with existing integrations:
- All `markitdown_ingest` parameters work unchanged
- Legacy `file_url` metadata field still available
- New URL fields are additive

## Testing Checklist

- [ ] Ingest PDF with images using `image_descriptions="basic"`
- [ ] Ingest PDF with images using `image_descriptions="llm"` (requires OpenAI collection)
- [ ] Verify images are accessible via URL
- [ ] Test `chunking_mode="by_page"` on multi-page PDF
- [ ] Test `chunking_mode="by_section"` on document with headings
- [ ] Verify fallback behavior when features aren't available
- [ ] Test with Ollama collection (should fallback gracefully)
- [ ] Verify progress reporting via Ingestion Status API
- [ ] Verify `_privacy_warning` is returned in plugin parameters via `GET /ingestion/plugins`

## Labels

`enhancement`, `plugin`, `backend`, `documentation`, `privacy`

