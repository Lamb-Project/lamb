# Parent-Child Chunking Feature

This directory contains the implementation of a parent-child chunking strategy for LAMB's RAG system, addressing the issue of structural queries failing due to information being distributed across multiple chunks.

## Quick Start

### 1. Ingest a Document with Hierarchical Chunking

When uploading a Markdown document to the Knowledge Base Server, use the `hierarchical_ingest` plugin:

```bash
curl -X POST "http://kb-server:9090/collections/{collection_id}/ingest-file" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@setup-guide.md" \
  -F "plugin_name=hierarchical_ingest" \
  -F 'plugin_params={"parent_chunk_size": 2000, "child_chunk_size": 400, "split_by_headers": true}'
```

**Optional:** Add a document outline for better structural queries:

```bash
curl -X POST "http://kb-server:9090/collections/{collection_id}/ingest-file" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@setup-guide.md" \
  -F "plugin_name=hierarchical_ingest" \
  -F 'plugin_params={"parent_chunk_size": 2000, "child_chunk_size": 400, "split_by_headers": true, "include_outline": true}'
```

### 2. Query with Parent-Child Support

When querying the collection, use the `parent_child_query` plugin:

```bash
curl -X POST "http://kb-server:9090/collections/{collection_id}/query" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "How many steps does the setup have?",
    "top_k": 5,
    "plugin_name": "parent_child_query",
    "plugin_params": {
      "return_parent_context": true
    }
  }'
```

## Files Added

### Core Implementation

- **`lamb-kb-server-stable/backend/plugins/hierarchical_ingest.py`**
  - Ingestion plugin that creates parent-child chunk hierarchies
  - Splits documents by headers (for Markdown) or character count
  - Stores full parent text in child chunk metadata

- **`lamb-kb-server-stable/backend/plugins/parent_child_query.py`**
  - Query plugin that returns parent context for child matches
  - Extracts parent_text from metadata when available
  - Falls back gracefully to child text if not hierarchical

### Tests

- **`lamb-kb-server-stable/backend/test_files/test_hierarchical_chunking.py`**
  - Unit tests for the hierarchical ingestion plugin
  - Validates parent-child relationships
  - Verifies metadata structure

- **`lamb-kb-server-stable/backend/test_files/test_integration_parent_child.py`**
  - Integration test demonstrating the complete workflow
  - Shows benefits for structural queries
  - Validates context improvement

### Documentation

- **`Documentation/parent-child-chunking.md`**
  - Comprehensive guide to the parent-child chunking feature
  - Usage examples and API documentation
  - Troubleshooting and best practices

## How It Works

### Problem Addressed

Traditional fixed-size chunking fails on structural queries like:
- "How many steps does the installation have?"
- "List all configuration options"
- "What is included in section 3?"

This happens because relevant information is split across multiple small chunks, and the LLM doesn't receive enough context to understand the document structure.

### Solution: Two-Level Chunking

1. **Child Chunks** (~400 chars)
   - Small, specific text segments
   - Embedded and used for semantic search
   - Optimized for search precision

2. **Parent Chunks** (~2000 chars)
   - Larger context containing multiple child chunks
   - Stored in child metadata
   - Returned to LLM for better comprehension

### Workflow

```
User Query
    ↓
Semantic Search (using child chunks) → Fast & Precise
    ↓
Match Found → Extract parent_text from metadata
    ↓
Return Parent Context to LLM → Rich Context
    ↓
Better Answer
```

## Key Features

✅ **Zero Storage Overhead** - Parent text stored in metadata, no duplicate embeddings

✅ **Zero Performance Penalty** - No extra database queries or embeddings

✅ **Backward Compatible** - Works with existing RAG processors, falls back gracefully

✅ **Configurable** - Adjust parent/child sizes, enable/disable header splitting

✅ **Markdown Optimized** - Intelligently splits by headers (##, ###)

## Testing

Run the test suite to verify the implementation:

```bash
# Test hierarchical ingestion
cd lamb-kb-server-stable/backend
python test_files/test_hierarchical_chunking.py

# Test full integration
python test_files/test_integration_parent_child.py
```

Expected output:
```
================================================================================
ALL TESTS COMPLETED SUCCESSFULLY
================================================================================
```

## Configuration Options

### Ingestion Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `parent_chunk_size` | 2000 | Maximum size of parent chunks (chars) |
| `child_chunk_size` | 400 | Maximum size of child chunks (chars) |
| `child_chunk_overlap` | 50 | Overlap between child chunks (chars) |
| `split_by_headers` | true | Split parent chunks by Markdown headers |
| `include_outline` | false | Append a document outline section at the end |

### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `return_parent_context` | true | Return parent text instead of child text |
| `top_k` | 5 | Number of results to return |
| `threshold` | 0.0 | Minimum similarity threshold (0-1) |

## Example Results

### Before (Standard Chunking)

**Query:** "How many steps does the setup have?"

**Chunks returned:**
- "...install dependencies with pip..."
- "...configure environment variables..."
- "...run database migrations..."

**LLM cannot determine total number of steps** ❌

### After (Parent-Child Chunking)

**Query:** "How many steps does the setup have?"

**Chunks returned:**
- "## Step 1: Install Dependencies\nFirst, ensure..."
- "## Step 2: Configure Environment\nCreate a .env..."
- "## Step 3: Initialize Database\nRun the migrations..."

**LLM can count steps and answer accurately** ✅

## Metadata Structure

Each child chunk includes:

```json
{
  "parent_chunk_id": 0,
  "child_chunk_id": 0,
  "chunk_level": "child",
  "parent_text": "Full parent chunk text...",
  "section_title": "Step 1: Install Dependencies",
  "children_in_parent": 2,
  "chunk_index": 0,
  "chunk_count": 10,
  "chunking_strategy": "hierarchical_parent_child"
}
```

## Document Outline Feature

The hierarchical ingest plugin can optionally generate and append a document outline section at the end of the ingested document. This feature enhances RAG performance by providing a comprehensive overview of the document structure.

### How It Works

When `include_outline=true` is set, the plugin:
1. Extracts all headers from the markdown document (H1, H2, H3, etc.)
2. Generates a hierarchical outline in a structured format
3. Appends the outline as a new section at the end of the document

### Example Outline Format

```
Document Outline
================

* <a>Main Title</a>
  * <a>Section 1: Introduction</a>
    * <a>1.1 Overview</a>
    * <a>1.2 Background</a>
  * <a>Section 2: Implementation</a>
    * <a>2.1 Setup</a>
    * <a>2.2 Configuration</a>
```

### Benefits

- **Better structural queries**: Questions like "How many steps does X have?" can be answered more accurately
- **Improved navigation**: The outline provides a clear map of the document structure
- **Enhanced context**: RAG systems can better understand the document's organization

### Usage

Enable the outline feature during ingestion:

```bash
curl -X POST "http://kb-server:9090/collections/{collection_id}/ingest-file" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.md" \
  -F "plugin_name=hierarchical_ingest" \
  -F 'plugin_params={"include_outline": true, "parent_chunk_size": 2000, "child_chunk_size": 400}'
```

**Note:** The outline feature is disabled by default to maintain backward compatibility.

## Limitations

- **Markdown-focused**: Optimized for documents with headers
- **Single-file scope**: Parent chunks don't span multiple files
- **Best for structured content**: Works best with well-organized documents

## Future Enhancements

- Support for other formats (reStructuredText, AsciiDoc)
- Cross-document parent chunks
- Dynamic parent sizing based on content
- Multi-level hierarchies (grandparent chunks)

## Troubleshooting

### Issue: Parent text not returned

**Solution:** Ensure you're using `parent_child_query` plugin (not `simple_query`)

### Issue: Poor section splitting

**Solution:** Adjust `parent_chunk_size` or ensure document has proper headers

### Issue: Metadata missing

**Solution:** Re-ingest document with `hierarchical_ingest` plugin

## Related Documentation

- [Parent-Child Chunking Guide](Documentation/parent-child-chunking.md) - Complete usage guide
- [KB Server API Documentation](lamb-kb-server-stable/lamb-kb-server-api.md) - API reference
- [Plugin System](lamb-kb-server-stable/backend/plugins/README.md) - Plugin architecture

## Support

For issues or questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review the [complete documentation](Documentation/parent-child-chunking.md)
3. Open an issue on GitHub with the `rag` label
