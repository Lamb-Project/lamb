# Parent-Child Chunking Strategy

## Overview

The parent-child chunking strategy is designed to improve RAG performance on **structural queries** like:
- "How many steps does X have?"
- "List all the steps"
- "What is included in section Y?"

This strategy addresses the fundamental limitation of fixed-size chunking: relevant information is often distributed across multiple chunks, making it difficult for the LLM to understand document structure.

## How It Works

### Two-Level Chunking

1. **Child Chunks** (small, specific sections)
   - Size: ~400 characters (configurable)
   - Purpose: Embedded and used for semantic search
   - Optimized for precision and relevance

2. **Parent Chunks** (larger contexts)
   - Size: ~2000 characters (configurable)
   - Purpose: Returned to the LLM as context
   - Optimized for comprehension and structural understanding

### Workflow

```
Document → Split by Headers → Parent Chunks → Split Further → Child Chunks
                                     ↓                              ↓
                              Store as metadata              Embed & Index
                                                                     ↓
User Query → Semantic Search → Match Child Chunks → Return Parent Context → LLM
```

## Usage

### 1. Ingesting Documents with Hierarchical Chunking

Use the `hierarchical_ingest` plugin when uploading Markdown documents:

```bash
POST /collections/{collection_id}/ingest-file
```

**Plugin Parameters:**

```json
{
  "plugin_name": "hierarchical_ingest",
  "plugin_params": {
    "parent_chunk_size": 2000,
    "child_chunk_size": 400,
    "child_chunk_overlap": 50,
    "split_by_headers": true
  }
}
```

**Parameter Details:**

- `parent_chunk_size` (default: 2000): Maximum size of parent chunks in characters
- `child_chunk_size` (default: 400): Maximum size of child chunks in characters
- `child_chunk_overlap` (default: 50): Overlap between child chunks for context continuity
- `split_by_headers` (default: true): Split parent chunks by Markdown headers (##, ###)

### 2. Querying with Parent-Child Support

Use the `parent_child_query` plugin when querying:

```bash
POST /collections/{collection_id}/query
```

**Query Parameters:**

```json
{
  "query_text": "How many steps does the setup have?",
  "top_k": 5,
  "threshold": 0.0,
  "plugin_params": {
    "return_parent_context": true
  }
}
```

**Parameter Details:**

- `return_parent_context` (default: true): Return parent chunk text instead of child chunk

## Document Structure Requirements

### Recommended Format: Markdown with Headers

```markdown
# Document Title

Introduction text...

## Section 1: First Topic

Content for section 1...

### Subsection 1.1

Detailed content...

## Section 2: Second Topic

Content for section 2...
```

### Best Practices

1. **Use hierarchical headers** (##, ###) to structure your documents
2. **Keep sections focused** - each section should cover one topic
3. **Use descriptive headers** - they become section titles in metadata
4. **Aim for 500-2000 characters per section** for optimal parent chunk size

## Metadata Structure

Each child chunk stores the following metadata:

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
  "chunking_strategy": "hierarchical_parent_child",
  "filename": "setup-guide.md",
  "source": "/path/to/file.md"
}
```

## Benefits

### For Structural Queries

✅ **Better context understanding**
- LLM receives full sections instead of fragments
- Can count steps, list items, understand sequences

✅ **Improved accuracy**
- Relationships between items are preserved
- Document structure is maintained

### Technical Advantages

✅ **No performance penalty**
- Child chunks embedded → fast semantic search
- Parent context stored in metadata → no extra DB storage
- Query-time substitution → no added latency

✅ **Backward compatible**
- Works with existing RAG processors
- Falls back gracefully if parent_text not available

## Comparison with Standard Chunking

| Aspect | Standard Chunking | Parent-Child Chunking |
|--------|------------------|---------------------|
| Search precision | Good | Good (uses child chunks) |
| Context richness | Limited by chunk size | Rich (returns parent chunks) |
| Structural queries | Poor | Excellent |
| Storage overhead | Base | +0% (metadata only) |
| Query latency | Base | +0% (no extra lookups) |

## Example Use Case

### Document: "5-Step Setup Guide"

**Query:** "How many steps does the setup have?"

#### With Standard Chunking (fails)

```
Chunks returned to LLM:
1. "...dependencies using pip. Run the following..."  [no mention of "5 steps"]
2. "...configure your environment variables..."        [no mention of "5 steps"]
3. "...initialize the database with alembic..."        [no mention of "5 steps"]
```

**Result:** LLM cannot determine the total number of steps.

#### With Parent-Child Chunking (succeeds)

```
Chunks returned to LLM:
1. "## Step 1: Install Dependencies\nFirst, ensure you have Python..."  [clear "Step 1"]
2. "## Step 2: Configure Environment Variables\nCreate a .env file..."   [clear "Step 2"]
3. "## Step 3: Initialize Database\nRun the migration scripts..."       [clear "Step 3"]
```

**Result:** LLM can count "Step 1", "Step 2", "Step 3" and infer there are more steps.

## Limitations

1. **Markdown-focused**: Optimized for Markdown documents with headers
2. **Header-dependent**: Works best with well-structured documents
3. **Single-file scope**: Parent chunks don't span multiple files

## Future Enhancements

- Support for other document formats (reStructuredText, AsciiDoc)
- Cross-document parent chunks
- Dynamic parent size based on content
- Hierarchical levels beyond 2 (grandparent chunks)

## Testing

Run the test suite to verify the implementation:

```bash
# Test hierarchical ingestion
python test_files/test_hierarchical_chunking.py

# Test full integration
python test_files/test_integration_parent_child.py
```

## Troubleshooting

### Parent text not returned

**Symptom:** Query returns child chunks instead of parent chunks

**Solution:** 
- Ensure you're using `parent_child_query` plugin (not `simple_query`)
- Check that `return_parent_context` is true in plugin_params

### Poor section splitting

**Symptom:** Parent chunks are too large or too small

**Solution:**
- Adjust `parent_chunk_size` parameter
- Ensure document has proper Markdown headers (##, ###)
- Set `split_by_headers: true` for header-based splitting

### Missing metadata

**Symptom:** `parent_text` field not in metadata

**Solution:**
- Verify document was ingested with `hierarchical_ingest` plugin
- Re-ingest the document if it was ingested with a different plugin
