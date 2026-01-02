# MarkItDown Plus Plugin Specification

**Version:** 1.0.0 (Draft)  
**Last Updated:** December 30, 2025  
**Status:** Specification / Planning  
**Target:** `backend/plugins/markitdown_plus_ingest.py`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Dependencies](#3-dependencies)
4. [User-Facing Parameters](#4-user-facing-parameters)
5. [Internal Pipeline](#5-internal-pipeline)
6. [Image Handling](#6-image-handling)
7. [Chunking Strategies](#7-chunking-strategies)
8. [Output Format](#8-output-format)
9. [Defaults & Guardrails](#9-defaults--guardrails)
10. [UI Integration Guidelines](#10-ui-integration-guidelines)
11. [Implementation Tasks](#11-implementation-tasks)
12. [Testing Plan](#12-testing-plan)

---

## 1. Overview

### 1.1 Purpose

**MarkItDown Plus** is an enhanced version of the existing `markitdown_ingest` plugin that leverages new features from Microsoft's [MarkItDown](https://github.com/microsoft/markitdown) library, specifically:

- **LLM-powered image descriptions** using OpenAI vision models
- **Multiple chunking strategies** (length-based, page-based, section-based)
- **Cleaner output** (single `.md` file, no intermediate HTML/JSON)

### 1.2 Key Differences from v1

| Feature | v1 (`markitdown_ingest`) | v2 (`markitdown_plus_ingest`) |
|---------|--------------------------|-------------------------------|
| Image descriptions | ❌ None | ✅ Optional (LLM or basic OCR) |
| Chunking modes | Length-based only | Length, Page, Section |
| Output files | `.html` + `.json` | Single `.md` only |
| Progress reporting | Basic | ✅ Detailed stages |
| OpenAI integration | ❌ | ✅ For image descriptions |

### 1.3 Supported File Types

Same as v1:
```
pdf, pptx, docx, xlsx, xls, mp3, wav, html, csv, json, xml, zip, epub
```

**Page-aware formats** (support page-based chunking):
```
pdf, pptx, docx
```

---

## 2. Goals & Non-Goals

### 2.1 Goals

- ✅ Provide richer image descriptions using LLM when available
- ✅ Offer multiple chunking strategies suited to different document types
- ✅ Output self-contained Markdown with image URLs pointing to `static/`
- ✅ Provide clear parameter metadata for UI integration
- ✅ Gracefully degrade when features aren't available (no OpenAI key, no page structure)

### 2.2 Non-Goals

- ❌ Replace the existing `markitdown_ingest` plugin (keep both)
- ❌ Require OpenAI API key for basic operation
- ❌ Support real-time streaming of conversion progress
- ❌ Implement custom OCR engine (rely on MarkItDown's capabilities)

---

## 3. Dependencies

### 3.1 Required

```
markitdown>=0.1.0
langchain-text-splitters>=0.0.1
```

### 3.2 Optional (for LLM image descriptions)

```
openai>=1.0.0
```

### 3.3 MarkItDown LLM Integration

MarkItDown supports LLM-powered image descriptions via constructor parameters:

```python
from markitdown import MarkItDown
from openai import OpenAI

# With LLM support
client = OpenAI(api_key="sk-...")
md = MarkItDown(llm_client=client, llm_model="gpt-4o")

# Without LLM (default)
md = MarkItDown()
```

---

## 4. User-Facing Parameters

### 4.1 Parameter Schema

```python
def get_parameters(self) -> Dict[str, Dict[str, Any]]:
    return {
        # === IMAGE HANDLING ===
        "image_descriptions": {
            "type": "string",
            "description": "How to handle images in the document",
            "enum": ["none", "basic", "llm"],
            "enum_labels": {
                "none": "Keep image links only (fastest)",
                "basic": "Add basic descriptions (filename, EXIF)",
                "llm": "Generate rich descriptions using AI (requires OpenAI key)"
            },
            "default": "none",
            "required": False,
            "ui_hint": "select",
            "help_text": "LLM descriptions provide the best context but require an OpenAI API key configured in the collection."
        },
        
        # === CHUNKING MODE ===
        "chunking_mode": {
            "type": "string",
            "description": "Strategy for splitting document into chunks",
            "enum": ["standard", "by_page", "by_section"],
            "enum_labels": {
                "standard": "Standard (character/token-based)",
                "by_page": "By page (PDF, Word, PowerPoint only)",
                "by_section": "By sections (split on headings)"
            },
            "default": "standard",
            "required": False,
            "ui_hint": "select",
            "help_text": "Page-based chunking is only available for PDF, DOCX, and PPTX files."
        },
        
        # === STANDARD CHUNKING OPTIONS ===
        "chunk_size": {
            "type": "integer",
            "description": "Target size for each chunk (characters)",
            "default": 1000,
            "min": 100,
            "max": 10000,
            "required": False,
            "visible_when": {"chunking_mode": ["standard", "by_section"]},
            "ui_hint": "slider",
            "help_text": "Larger chunks preserve more context but may exceed LLM token limits."
        },
        "chunk_overlap": {
            "type": "integer",
            "description": "Overlap between consecutive chunks (characters)",
            "default": 200,
            "min": 0,
            "max": 500,
            "required": False,
            "visible_when": {"chunking_mode": ["standard"]},
            "ui_hint": "slider",
            "help_text": "Overlap helps maintain context across chunk boundaries."
        },
        "splitter_type": {
            "type": "string",
            "description": "Text splitting algorithm",
            "enum": ["RecursiveCharacterTextSplitter", "CharacterTextSplitter", "TokenTextSplitter"],
            "default": "RecursiveCharacterTextSplitter",
            "required": False,
            "visible_when": {"chunking_mode": ["standard"]},
            "ui_hint": "select"
        },
        
        # === PAGE-BASED CHUNKING OPTIONS ===
        "pages_per_chunk": {
            "type": "integer",
            "description": "Number of pages to include in each chunk",
            "default": 1,
            "min": 1,
            "max": 10,
            "required": False,
            "visible_when": {"chunking_mode": ["by_page"]},
            "applicable_to": ["pdf", "docx", "pptx"],
            "ui_hint": "number",
            "help_text": "Combine multiple pages into single chunks for shorter documents."
        },
        
        # === SECTION-BASED CHUNKING OPTIONS ===
        "max_heading_level": {
            "type": "integer",
            "description": "Maximum heading level to split on (1=H1 only, 3=H1-H3)",
            "default": 3,
            "min": 1,
            "max": 6,
            "required": False,
            "visible_when": {"chunking_mode": ["by_section"]},
            "ui_hint": "number",
            "help_text": "Lower values create fewer, larger sections. Falls back to standard chunking if no headings found."
        },
        "max_section_size": {
            "type": "integer",
            "description": "Maximum size per section before sub-splitting (0 = no limit)",
            "default": 0,
            "min": 0,
            "max": 50000,
            "required": False,
            "visible_when": {"chunking_mode": ["by_section"]},
            "ui_hint": "number",
            "help_text": "Large sections will be sub-split using standard chunking if they exceed this size."
        },
        
        # === OUTPUT OPTIONS ===
        "include_chunk_separators": {
            "type": "boolean",
            "description": "Add '---' separators between chunks in the output Markdown",
            "default": False,
            "required": False,
            "ui_hint": "checkbox"
        },
        
        # === METADATA ===
        "description": {
            "type": "long-string",
            "description": "Optional description for the ingested content",
            "required": False,
            "ui_hint": "textarea"
        },
        "citation": {
            "type": "long-string",
            "description": "Optional citation/source reference",
            "required": False,
            "ui_hint": "textarea"
        }
    }
```

### 4.2 Parameter Metadata Fields

New metadata fields for UI integration:

| Field | Type | Description |
|-------|------|-------------|
| `visible_when` | dict | Conditions for showing this parameter |
| `applicable_to` | list | File extensions this parameter applies to |
| `ui_hint` | string | Suggested UI control (`select`, `slider`, `number`, `checkbox`, `textarea`) |
| `enum_labels` | dict | Human-readable labels for enum values |
| `help_text` | string | Explanatory text for users |
| `min` / `max` | number | Value constraints |

---

## 5. Internal Pipeline

### 5.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MarkItDown Plus Pipeline                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐                                                   │
│  │ 1. CONVERT   │  MarkItDown converts file to Markdown             │
│  │              │  - If LLM mode: pass llm_client to MarkItDown     │
│  │              │  - Extract raw Markdown text                       │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ 2. IMAGES    │  Process embedded images                          │
│  │              │  - Extract images to static/{owner}/{collection}/ │
│  │              │  - Generate descriptions (none/basic/llm)         │
│  │              │  - Replace image refs with ![desc](url)           │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ 3. CHUNK     │  Apply selected chunking strategy                 │
│  │              │  - Standard: LangChain text splitters             │
│  │              │  - By page: Split on page markers                 │
│  │              │  - By section: Split on heading structure         │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ 4. OUTPUT    │  Generate final output                            │
│  │              │  - Save combined .md file                         │
│  │              │  - Return chunk list with metadata                │
│  └──────────────┘                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Progress Reporting

| Stage | Progress | Message |
|-------|----------|---------|
| Start | 0/5 | "Starting document conversion..." |
| Convert | 1/5 | "Converting {filename} to Markdown..." |
| Images | 2/5 | "Processing {n} images..." |
| Chunk | 3/5 | "Applying {mode} chunking..." |
| Finalize | 4/5 | "Finalizing {n} chunks..." |
| Complete | 5/5 | "Completed: {n} chunks from {filename}" |

---

## 6. Image Handling

### 6.1 Image Description Modes

#### Mode: `none` (Default)
- Keep existing image references as-is
- No image extraction or description generation
- Fastest option

#### Mode: `basic`
- Extract images to `static/{owner}/{collection}/images/`
- Generate descriptions from:
  - Filename (cleaned up)
  - EXIF metadata (if available)
  - Alt text (if present in source)
- Insert `![description](image_url)` into Markdown

#### Mode: `llm`
- Requires OpenAI API key (from collection's `embeddings_model.apikey`)
- Use MarkItDown's built-in LLM support
- Generate rich, contextual descriptions
- Falls back to `basic` mode if no API key available

### 6.2 Image URL Structure

```
{HOME_URL}/static/{owner}/{collection_name}/images/{uuid}_{original_name}.{ext}
```

Example:
```
http://localhost:9090/static/user@example.com/my-kb/images/a1b2c3d4_diagram.png
```

### 6.3 Getting OpenAI Key

The plugin should retrieve the OpenAI API key from the collection's embedding configuration:

```python
def _get_openai_key(self, collection_id: int, db: Session) -> Optional[str]:
    """Get OpenAI API key from collection's embeddings config."""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        return None
    
    embeddings_config = collection.embeddings_model
    if isinstance(embeddings_config, str):
        embeddings_config = json.loads(embeddings_config)
    
    # Only return if vendor is OpenAI
    if embeddings_config.get("vendor") == "openai":
        return embeddings_config.get("apikey")
    
    return None
```

---

## 7. Chunking Strategies

### 7.1 Standard Chunking

Uses LangChain text splitters (same as v1):

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap
)
chunks = splitter.split_text(content)
```

### 7.2 Page-Based Chunking

For PDF, DOCX, PPTX files that have page structure:

```python
def _chunk_by_page(self, content: str, pages_per_chunk: int = 1) -> List[str]:
    """Split content by page markers.
    
    MarkItDown inserts page markers like:
    - PDF: <!-- Page N --> or [Page N]
    - PPTX: <!-- Slide N --> or --- (slide separator)
    - DOCX: <!-- Page Break --> or similar
    """
    # Split on page markers
    page_pattern = r'(?:<!-- Page \d+ -->|<!-- Slide \d+ -->|\n---\n(?=# ))'
    pages = re.split(page_pattern, content)
    
    # Group pages into chunks
    chunks = []
    for i in range(0, len(pages), pages_per_chunk):
        chunk_pages = pages[i:i + pages_per_chunk]
        chunks.append('\n\n'.join(chunk_pages))
    
    return chunks
```

**Fallback:** If no page markers found, fall back to standard chunking.

### 7.3 Section-Based Chunking

Split on Markdown headings:

```python
def _chunk_by_section(self, content: str, max_level: int = 3, 
                      max_size: int = 0, chunk_size: int = 1000) -> List[str]:
    """Split content by heading structure.
    
    Args:
        content: Markdown content
        max_level: Max heading level to split on (1-6)
        max_size: Max section size before sub-splitting (0 = no limit)
        chunk_size: Size for sub-splitting large sections
    """
    # Build heading pattern: # through max_level
    heading_pattern = r'^(#{1,' + str(max_level) + r'})\s+(.+)$'
    
    sections = []
    current_section = []
    current_heading = None
    
    for line in content.split('\n'):
        match = re.match(heading_pattern, line, re.MULTILINE)
        if match:
            # Save previous section
            if current_section:
                sections.append({
                    'heading': current_heading,
                    'content': '\n'.join(current_section)
                })
            current_heading = line
            current_section = [line]
        else:
            current_section.append(line)
    
    # Don't forget last section
    if current_section:
        sections.append({
            'heading': current_heading,
            'content': '\n'.join(current_section)
        })
    
    # Sub-split large sections if max_size specified
    if max_size > 0:
        sections = self._subsplit_large_sections(sections, max_size, chunk_size)
    
    return [s['content'] for s in sections]
```

**Fallback:** If no headings found, fall back to standard chunking with warning.

---

## 8. Output Format

### 8.1 Single Markdown File

Output a single `.md` file containing the processed content:

```
static/{owner}/{collection}/
├── {uuid}.md                    # Combined output
└── images/
    ├── {uuid}_image1.png
    └── {uuid}_image2.jpg
```

### 8.2 Chunk Separator (Optional)

If `include_chunk_separators=True`:

```markdown
# Introduction

This is the first section...

---

# Chapter 1

This is chapter one...

---

# Chapter 2

This is chapter two...
```

### 8.3 Chunk Metadata

Each chunk includes metadata:

```python
{
    "text": "chunk content...",
    "metadata": {
        # Source info
        "source": "/path/to/original.pdf",
        "filename": "report.pdf",
        "extension": "pdf",
        "file_size": 1234567,
        "file_url": "http://localhost:9090/static/.../output.md",
        
        # Chunk info
        "chunk_index": 0,
        "chunk_count": 25,
        "chunking_strategy": "by_section",  # or "standard", "by_page"
        
        # Strategy-specific
        "chunk_size": 1000,           # for standard
        "chunk_overlap": 200,          # for standard
        "pages_per_chunk": 1,          # for by_page
        "section_heading": "# Intro",  # for by_section
        "page_numbers": [1, 2],        # for by_page (if available)
        
        # Image info
        "image_description_mode": "llm",
        "images_extracted": 5,
        
        # User metadata
        "description": "Annual report 2024",
        "citation": "Company XYZ"
    }
}
```

---

## 9. Defaults & Guardrails

### 9.1 Safe Defaults

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `image_descriptions` | `none` | No API key required |
| `chunking_mode` | `standard` | Works for all file types |
| `chunk_size` | 1000 | Good balance of context vs size |
| `chunk_overlap` | 200 | Standard overlap |
| `pages_per_chunk` | 1 | One page = one chunk |
| `max_heading_level` | 3 | H1-H3 section splits |
| `max_section_size` | 0 | No limit (trust document structure) |

### 9.2 Guardrails

| Condition | Behavior |
|-----------|----------|
| `image_descriptions=llm` but no OpenAI key | Fall back to `basic` mode, log warning |
| `chunking_mode=by_page` on non-paged format | Fall back to `standard`, log warning |
| `chunking_mode=by_section` but no headings | Fall back to `standard`, log warning |
| Section exceeds `max_section_size` | Sub-split using standard chunking |
| File conversion fails | Raise ValueError with details |
| Image extraction fails | Continue without image, log warning |

### 9.3 Validation

```python
def _validate_params(self, file_extension: str, **kwargs):
    """Validate parameters and warn about incompatibilities."""
    warnings = []
    
    chunking_mode = kwargs.get('chunking_mode', 'standard')
    image_mode = kwargs.get('image_descriptions', 'none')
    
    # Check page-based chunking compatibility
    if chunking_mode == 'by_page' and file_extension not in ['pdf', 'docx', 'pptx']:
        warnings.append(
            f"Page-based chunking not available for .{file_extension} files. "
            f"Falling back to standard chunking."
        )
        kwargs['chunking_mode'] = 'standard'
    
    # Check LLM image descriptions
    if image_mode == 'llm' and not self._has_openai_key():
        warnings.append(
            "LLM image descriptions requested but no OpenAI key available. "
            "Falling back to basic descriptions."
        )
        kwargs['image_descriptions'] = 'basic'
    
    return kwargs, warnings
```

---

## 10. UI Integration Guidelines

### 10.1 Parameter Visibility

Use `visible_when` to conditionally show parameters:

```javascript
// Pseudocode for UI
function shouldShowParameter(param, currentValues) {
    if (!param.visible_when) return true;
    
    for (const [field, allowedValues] of Object.entries(param.visible_when)) {
        if (!allowedValues.includes(currentValues[field])) {
            return false;
        }
    }
    return true;
}
```

### 10.2 File Type Warnings

Use `applicable_to` to show warnings:

```javascript
// When user selects chunking_mode = "by_page"
if (param.applicable_to && !param.applicable_to.includes(fileExtension)) {
    showWarning(`This option is only available for: ${param.applicable_to.join(', ')}`);
}
```

### 10.3 Suggested UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  MarkItDown Plus Ingestion                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Image Handling                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ [▼] Keep image links only (fastest)                         ││
│  │     Add basic descriptions (filename, EXIF)                 ││
│  │     Generate rich descriptions using AI ⚠️ Requires OpenAI  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Chunking Mode                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ [▼] Standard (character-based)                              ││
│  │     By page (PDF, Word, PowerPoint only) ⚠️                 ││
│  │     By sections (split on headings)                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ─── Standard Chunking Options ─────────────────────────────── │
│                                                                  │
│  Chunk Size (characters)                                         │
│  [═══════════●═══════] 1000                                     │
│  ℹ️ Larger chunks preserve more context                         │
│                                                                  │
│  Overlap (characters)                                            │
│  [════●══════════════] 200                                      │
│                                                                  │
│  ─── Metadata ───────────────────────────────────────────────── │
│                                                                  │
│  Description (optional)                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Citation (optional)                                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│                              [ Cancel ]  [ Ingest Document ]     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Implementation Tasks

### 11.1 Phase 1: Core Plugin

- [ ] Create `backend/plugins/markitdown_plus_ingest.py`
- [ ] Implement base conversion with MarkItDown
- [ ] Implement standard chunking (port from v1)
- [ ] Add progress reporting
- [ ] Add parameter schema with UI metadata

### 11.2 Phase 2: Image Handling

- [ ] Implement image extraction from converted content
- [ ] Implement `basic` description mode (filename, EXIF)
- [ ] Create image storage in `static/.../images/`
- [ ] Update Markdown with image URLs

### 11.3 Phase 3: LLM Integration

- [ ] Implement OpenAI key retrieval from collection
- [ ] Integrate MarkItDown's `llm_client` parameter
- [ ] Implement fallback to `basic` mode
- [ ] Test with various image types

### 11.4 Phase 4: Advanced Chunking

- [ ] Implement page detection patterns
- [ ] Implement `by_page` chunking
- [ ] Implement heading detection
- [ ] Implement `by_section` chunking
- [ ] Implement large section sub-splitting
- [ ] Add fallback logic

### 11.5 Phase 5: Testing & Documentation

- [ ] Unit tests for each chunking mode
- [ ] Integration tests with sample files
- [ ] Update architecture documentation
- [ ] Create user guide

---

## 12. Testing Plan

### 12.1 Test Files

| File Type | Test Cases |
|-----------|------------|
| PDF | Multi-page, images, headings, no headings |
| DOCX | Multi-page, images, headings, tables |
| PPTX | Multi-slide, images, speaker notes |
| HTML | Images (relative/absolute URLs), headings |
| Markdown | Already formatted, various heading levels |
| Plain text | No structure, long content |

### 12.2 Test Scenarios

```python
# Test matrix
test_scenarios = [
    # Basic conversion
    ("simple.pdf", {"chunking_mode": "standard"}),
    ("simple.docx", {"chunking_mode": "standard"}),
    
    # Page-based chunking
    ("multipage.pdf", {"chunking_mode": "by_page", "pages_per_chunk": 1}),
    ("multipage.pdf", {"chunking_mode": "by_page", "pages_per_chunk": 3}),
    ("slides.pptx", {"chunking_mode": "by_page"}),
    
    # Section-based chunking
    ("report.pdf", {"chunking_mode": "by_section", "max_heading_level": 2}),
    ("report.pdf", {"chunking_mode": "by_section", "max_section_size": 2000}),
    ("no_headings.txt", {"chunking_mode": "by_section"}),  # Should fallback
    
    # Image handling
    ("with_images.pdf", {"image_descriptions": "none"}),
    ("with_images.pdf", {"image_descriptions": "basic"}),
    ("with_images.pdf", {"image_descriptions": "llm"}),  # Requires OpenAI
    
    # Edge cases
    ("empty.pdf", {}),  # Empty document
    ("huge.pdf", {"chunk_size": 500}),  # Very large document
    ("corrupted.pdf", {}),  # Should fail gracefully
]
```

### 12.3 Expected Outputs

For each test:
1. Verify chunk count is reasonable
2. Verify metadata is complete
3. Verify images are extracted (if applicable)
4. Verify fallback behavior works
5. Verify progress callbacks are called

---

## Appendix A: MarkItDown API Reference

### Constructor

```python
from markitdown import MarkItDown
from openai import OpenAI

# Basic usage
md = MarkItDown()

# With LLM support for image descriptions
client = OpenAI(api_key="sk-...")
md = MarkItDown(llm_client=client, llm_model="gpt-4o")
```

### Convert Method

```python
result = md.convert(file_path)

# Result object
result.text_content  # str: Markdown content
result.title         # str: Document title (if available)
```

### Supported Formats

From MarkItDown documentation:
- PDF (`.pdf`)
- PowerPoint (`.pptx`)
- Word (`.docx`)
- Excel (`.xlsx`, `.xls`)
- Images (`.jpg`, `.png`, `.gif`, etc.) - with LLM descriptions
- Audio (`.mp3`, `.wav`) - transcription via speech-to-text
- HTML (`.html`, `.htm`)
- Various text formats (`.txt`, `.csv`, `.json`, `.xml`)
- ZIP archives (processes contained files)
- EPUB e-books

---

## Appendix B: Migration from v1

Users can migrate from `markitdown_ingest` to `markitdown_plus_ingest`:

| v1 Parameter | v2 Equivalent |
|--------------|---------------|
| `chunk_size` | `chunk_size` (same) |
| `chunk_overlap` | `chunk_overlap` (same) |
| `splitter_type` | `splitter_type` (same) |
| `description` | `description` (same) |
| `citation` | `citation` (same) |

New parameters have safe defaults, so v1 configurations work unchanged.

---

**Document Status:** Draft Specification  
**Next Steps:** Review, then begin Phase 1 implementation  
**Maintainers:** LAMB Development Team

