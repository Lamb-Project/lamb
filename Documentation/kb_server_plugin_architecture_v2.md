# KB-Server Plugin Architecture v2.0

**Version:** 2.0 Draft  
**Date:** February 3, 2026  
**Status:** Design Proposal  
**Authors:** Development Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Proposed Architecture](#3-proposed-architecture)
4. [Content Object Model](#4-content-object-model)
5. [Plugin Layer 1: Format Import Plugins](#5-plugin-layer-1-format-import-plugins)
6. [Plugin Layer 2: Ingestion Strategy Plugins](#6-plugin-layer-2-ingestion-strategy-plugins)
7. [Query Plugins & Strategy Pairing](#7-query-plugins--strategy-pairing)
8. [Linkable Content & Permalinks](#8-linkable-content--permalinks)
9. [Shared Content Across Knowledge Bases](#9-shared-content-across-knowledge-bases)
10. [Deletion Semantics & Reference Management](#10-deletion-semantics--reference-management)
11. [Database Schema](#11-database-schema)
12. [API Design](#12-api-design)
13. [Migration Strategy](#13-migration-strategy)
14. [Trade-offs & Alternatives Considered](#14-trade-offs--alternatives-considered)
15. [Open Questions](#15-open-questions)

---

## 1. Executive Summary

This document proposes a significant evolution of the lamb-kb-server plugin architecture to address three interconnected challenges:

1. **Separation of Concerns**: Split monolithic ingestion plugins into two layers:
   - **Format Import Plugins**: Convert source files to standardized content bundles
   - **Ingestion Strategy Plugins**: Implement chunking strategies (simple, hierarchical, semantic, etc.)

2. **Linkable Content**: Every piece of content should have stable, resolvable permalinks that can be cited in LLM responses and traced back to source material.

3. **Shared Content**: Enable multiple Knowledge Bases to reference the same underlying content without duplication, while maintaining clear deletion semantics.

### Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Source Once, Chunk Many** | Import content once, apply different chunking strategies per KB |
| **Stable Identifiers** | Content objects and chunks have permanent, linkable IDs |
| **Reference Transparency** | Clear tracking of what KBs use what content |
| **Safe Deletion** | Understand impact before removing shared content |
| **Strategy Lock-in** | KB's ingestion strategy is fixed at creation (like embedding dimensions) |

---

## 2. Current State Analysis

### Current Plugin Model (Monolithic)

```
┌─────────────────────────────────────────────────────────────────┐
│                   markitdown_ingest Plugin                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Receive file (PDF, DOCX, etc.)                              │
│  2. Convert to Markdown (format handling)                        │
│  3. Split into chunks (chunking strategy)                        │
│  4. Generate embeddings                                          │
│  5. Store in ChromaDB                                            │
│  6. Create file_registry entry                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Problems with Current Model

| Problem | Impact |
|---------|--------|
| **Mixed responsibilities** | Can't use hierarchical chunking with PDF import |
| **No content reuse** | Same PDF imported 5 times = 5 copies |
| **No stable links** | Can't create permalinks to chunks |
| **Strategy coupling** | Changing chunking strategy requires re-import |
| **Deletion complexity** | Deleting a file only affects one KB |

---

## 3. Proposed Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         lamb-kb-server v2.0                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 1: Format Import                               │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │  PDF Import  │ │ DOCX Import  │ │  URL Import  │ │YouTube Import│   │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │ │
│  │         │                │                │                │           │ │
│  │         └────────────────┴────────────────┴────────────────┘           │ │
│  │                                   │                                     │ │
│  │                                   ▼                                     │ │
│  │                    ┌──────────────────────────┐                         │ │
│  │                    │    Content Object        │ ← Stored once           │ │
│  │                    │    (Source + Text)       │   Shared across KBs     │ │
│  │                    └──────────────────────────┘                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                   │                                          │
│                                   │ Reference                                │
│                                   ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 2: Ingestion Strategy                          │ │
│  │                                                                         │ │
│  │  Knowledge Base A              Knowledge Base B          Knowledge Base C│ │
│  │  (Simple Chunking)             (Hierarchical)            (Semantic)     │ │
│  │  ┌─────────────────┐          ┌─────────────────┐       ┌─────────────┐ │ │
│  │  │ simple_ingest   │          │hierarchical_    │       │semantic_    │ │ │
│  │  │                 │          │ingest           │       │ingest       │ │ │
│  │  │ Chunk: 1000/200 │          │ Parent: 4000    │       │ By meaning  │ │ │
│  │  │                 │          │ Child: 500      │       │             │ │ │
│  │  └────────┬────────┘          └────────┬────────┘       └──────┬──────┘ │ │
│  │           │                            │                       │        │ │
│  │           ▼                            ▼                       ▼        │ │
│  │  ┌─────────────────┐          ┌─────────────────┐       ┌─────────────┐ │ │
│  │  │ ChromaDB Coll A │          │ ChromaDB Coll B │       │ChromaDB C   │ │ │
│  │  │ 150 chunks      │          │ 50 parents +    │       │ 80 chunks   │ │ │
│  │  │                 │          │ 200 children    │       │             │ │ │
│  │  └─────────────────┘          └─────────────────┘       └─────────────┘ │ │
│  │                                                                         │ │
│  │  Paired Query Plugins:                                                  │ │
│  │  simple_query              parent_child_query           semantic_query  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
                        ┌─────────────────────┐
                        │   Source File       │
                        │   (PDF, URL, etc.)  │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Format Import Plugin       │
                    │  (e.g., markitdown_import)  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Content Object          │
                    │  ┌────────────────────────┐ │
                    │  │ id: "co_abc123"        │ │
                    │  │ source_url: "..."      │ │
                    │  │ source_file: "..."     │ │
                    │  │ extracted_text: "..."  │ │
                    │  │ metadata: {...}        │ │
                    │  │ permalink: "/content/  │ │
                    │  │   co_abc123"           │ │
                    │  └────────────────────────┘ │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │   KB Alpha      │  │   KB Beta       │  │   KB Gamma      │
     │   (simple)      │  │  (hierarchical) │  │   (simple)      │
     │                 │  │                 │  │                 │
     │ Chunks:         │  │ Parent chunks:  │  │ Chunks:         │
     │ - ch_001        │  │ - pc_001        │  │ - ch_101        │
     │ - ch_002        │  │ - pc_002        │  │ - ch_102        │
     │ - ch_003        │  │ Child chunks:   │  │                 │
     │                 │  │ - cc_001..010   │  │                 │
     └─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 4. Content Object Model

### What is a Content Object?

A **Content Object** represents imported source material before any chunking occurs. It's the canonical representation of a document, URL, or media file.

### Content Object Structure

```json
{
  "id": "co_7f3a8b2c",
  "organization_id": "org_123",
  "owner_id": "user_456",
  
  "source": {
    "type": "file",
    "original_filename": "research_paper.pdf",
    "content_type": "application/pdf",
    "file_path": "/storage/org_123/files/7f3a8b2c.pdf",
    "file_size": 2048576,
    "file_hash": "sha256:abc123...",
    "source_url": null
  },
  
  "extracted": {
    "text": "Full extracted text content...",
    "text_format": "markdown",
    "text_hash": "sha256:def456...",
    "extraction_plugin": "markitdown_import",
    "extraction_params": {},
    "html_preview_path": "/storage/org_123/previews/7f3a8b2c.html"
  },
  
  "metadata": {
    "title": "Research Paper Title",
    "author": "Dr. Smith",
    "page_count": 15,
    "language": "en",
    "custom": {}
  },
  
  "permalinks": {
    "content": "/content/co_7f3a8b2c",
    "source": "/content/co_7f3a8b2c/source",
    "preview": "/content/co_7f3a8b2c/preview",
    "text": "/content/co_7f3a8b2c/text"
  },
  
  "usage": {
    "knowledge_bases": ["kb_001", "kb_002", "kb_003"],
    "total_chunk_count": 450,
    "first_used": "2026-01-15T10:00:00Z",
    "last_used": "2026-02-03T14:30:00Z"
  },
  
  "visibility": "organization",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-02-03T14:30:00Z"
}
```

### Content Object Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Content Object Lifecycle                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │ UPLOADED │ ───► │EXTRACTING│ ───► │  READY   │ ───► │ ARCHIVED │        │
│  └──────────┘      └──────────┘      └──────────┘      └──────────┘        │
│       │                 │                 │                 │               │
│       │                 │                 │                 ▼               │
│       │                 │                 │           ┌──────────┐          │
│       │                 │                 └─────────► │ DELETED  │          │
│       │                 │                             └──────────┘          │
│       │                 │                                  ▲                │
│       │                 ▼                                  │                │
│       │           ┌──────────┐                             │                │
│       └─────────► │  FAILED  │ ────────────────────────────┘                │
│                   └──────────┘                                              │
│                                                                              │
│  State Descriptions:                                                         │
│  - UPLOADED: File received, awaiting extraction                             │
│  - EXTRACTING: Format import plugin is processing                           │
│  - READY: Text extracted, available for chunking into KBs                   │
│  - ARCHIVED: Soft-deleted, can be restored                                  │
│  - DELETED: Hard-deleted (only if no KB references)                         │
│  - FAILED: Extraction failed, can retry                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Content Deduplication

Content Objects are deduplicated by `file_hash` within an organization:

```python
def get_or_create_content_object(org_id: str, file: UploadFile) -> ContentObject:
    file_hash = compute_sha256(file)
    
    # Check if content already exists
    existing = db.query(ContentObject).filter(
        ContentObject.organization_id == org_id,
        ContentObject.source_file_hash == file_hash
    ).first()
    
    if existing and existing.status == "ready":
        return existing  # Reuse existing content
    
    # Create new content object
    return create_new_content_object(org_id, file, file_hash)
```

---

## 5. Plugin Layer 1: Format Import Plugins

### Purpose

Format Import Plugins are responsible for:
1. Receiving source files/URLs
2. Extracting text content
3. Creating Content Objects
4. Generating preview files (HTML)
5. Extracting metadata (title, author, pages, etc.)

### Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ImportResult:
    """Result of a format import operation."""
    success: bool
    extracted_text: str
    text_format: str  # "markdown", "plain", "html"
    metadata: Dict[str, Any]
    preview_html: Optional[str]
    error_message: Optional[str] = None
    error_details: Optional[Dict] = None

class FormatImportPlugin(ABC):
    """Base class for format import plugins."""
    
    name: str = "base_import"
    description: str = "Base import plugin"
    supported_types: set = set()  # MIME types or extensions
    
    @abstractmethod
    def can_import(self, source: str, content_type: Optional[str] = None) -> bool:
        """Check if this plugin can handle the given source."""
        pass
    
    @abstractmethod
    def import_file(self, file_path: str, **kwargs) -> ImportResult:
        """
        Import a local file.
        
        Args:
            file_path: Path to the file
            **kwargs: Plugin-specific parameters
            
        Returns:
            ImportResult with extracted text and metadata
        """
        pass
    
    @abstractmethod
    def import_url(self, url: str, **kwargs) -> ImportResult:
        """
        Import content from a URL.
        
        Args:
            url: Source URL
            **kwargs: Plugin-specific parameters
            
        Returns:
            ImportResult with extracted text and metadata
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Return plugin parameters schema."""
        pass
```

### Available Format Import Plugins

#### 5.1 `markitdown_import`

Converts office documents and PDFs to Markdown using Microsoft's MarkItDown library.

```python
@PluginRegistry.register
class MarkItDownImportPlugin(FormatImportPlugin):
    name = "markitdown_import"
    description = "Import PDF, DOCX, PPTX, XLSX using MarkItDown"
    supported_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
        "text/markdown"
    }
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "extract_images": {
                "type": "boolean",
                "default": False,
                "description": "Extract and store images from document"
            },
            "ocr_enabled": {
                "type": "boolean", 
                "default": False,
                "description": "Use OCR for scanned documents"
            }
        }
```

#### 5.2 `url_import`

Fetches and extracts content from web URLs.

```python
@PluginRegistry.register
class URLImportPlugin(FormatImportPlugin):
    name = "url_import"
    description = "Import content from web URLs"
    supported_types = {"text/html", "application/xhtml+xml"}
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "follow_redirects": {
                "type": "boolean",
                "default": True
            },
            "extract_main_content": {
                "type": "boolean",
                "default": True,
                "description": "Use readability to extract main content"
            },
            "include_links": {
                "type": "boolean",
                "default": False,
                "description": "Preserve hyperlinks in extracted text"
            }
        }
```

#### 5.3 `youtube_import`

Extracts transcripts from YouTube videos.

```python
@PluginRegistry.register
class YouTubeImportPlugin(FormatImportPlugin):
    name = "youtube_import"
    description = "Import YouTube video transcripts"
    supported_types = {"video/youtube"}
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "language": {
                "type": "string",
                "default": "en",
                "description": "Preferred subtitle language (ISO 639-1)"
            },
            "include_auto_captions": {
                "type": "boolean",
                "default": True,
                "description": "Fall back to auto-generated captions"
            }
        }
```

#### 5.4 `plain_text_import`

Handles plain text and markdown files directly.

```python
@PluginRegistry.register
class PlainTextImportPlugin(FormatImportPlugin):
    name = "plain_text_import"
    description = "Import plain text and markdown files"
    supported_types = {"text/plain", "text/markdown", "text/x-markdown"}
    
    def import_file(self, file_path: str, **kwargs) -> ImportResult:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return ImportResult(
            success=True,
            extracted_text=text,
            text_format="markdown" if file_path.endswith('.md') else "plain",
            metadata={"char_count": len(text), "line_count": text.count('\n')},
            preview_html=self._render_preview(text)
        )
```

---

## 6. Plugin Layer 2: Ingestion Strategy Plugins

### Purpose

Ingestion Strategy Plugins are responsible for:
1. Taking a Content Object's extracted text
2. Applying a chunking strategy
3. Generating embeddings for chunks
4. Storing chunks in ChromaDB
5. Creating chunk metadata with permalinks

### Key Concept: Strategy Lock-in

> **A Knowledge Base's ingestion strategy is FIXED at creation time.**

This is analogous to how embedding dimensions are locked. The reason:
- Different strategies produce incompatible chunk structures
- Hierarchical chunks have parent-child relationships
- Semantic chunks have meaning-based boundaries
- Mixing strategies in one KB would break query consistency

### Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class Chunk:
    """A single chunk produced by an ingestion strategy."""
    id: str
    text: str
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None  # For hierarchical strategies
    children_ids: Optional[List[str]] = None  # For hierarchical strategies

@dataclass  
class IngestionResult:
    """Result of an ingestion operation."""
    success: bool
    chunks: List[Chunk]
    chunk_count: int
    strategy_metadata: Dict[str, Any]  # Strategy-specific data for queries
    error_message: Optional[str] = None

class IngestionStrategyPlugin(ABC):
    """Base class for ingestion strategy plugins."""
    
    name: str = "base_strategy"
    description: str = "Base ingestion strategy"
    paired_query_plugin: str = "base_query"  # Which query plugin to use
    
    @abstractmethod
    def ingest(
        self, 
        content_object: ContentObject,
        embedding_function: callable,
        **kwargs
    ) -> IngestionResult:
        """
        Ingest a content object into chunks.
        
        Args:
            content_object: The content to chunk
            embedding_function: Function to generate embeddings
            **kwargs: Strategy-specific parameters
            
        Returns:
            IngestionResult with chunks and metadata
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Return strategy parameters schema."""
        pass
    
    def supports_progress(self) -> bool:
        """Whether this strategy can report progress."""
        return False
```

### Available Ingestion Strategy Plugins

#### 6.1 `simple_ingest` (Current Default)

Classic fixed-size chunking with overlap.

```python
@PluginRegistry.register
class SimpleIngestionStrategy(IngestionStrategyPlugin):
    name = "simple_ingest"
    description = "Fixed-size chunking with overlap"
    paired_query_plugin = "simple_query"
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "chunk_size": {
                "type": "integer",
                "default": 1000,
                "min": 100,
                "max": 10000,
                "description": "Target chunk size in characters"
            },
            "chunk_overlap": {
                "type": "integer",
                "default": 200,
                "min": 0,
                "max": 500,
                "description": "Overlap between chunks"
            },
            "splitter_type": {
                "type": "string",
                "default": "recursive",
                "enum": ["recursive", "character", "token"],
                "description": "Text splitting algorithm"
            }
        }
    
    def ingest(self, content_object, embedding_function, **kwargs) -> IngestionResult:
        chunk_size = kwargs.get("chunk_size", 1000)
        chunk_overlap = kwargs.get("chunk_overlap", 200)
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        texts = splitter.split_text(content_object.extracted_text)
        chunks = []
        
        for i, text in enumerate(texts):
            chunk_id = generate_chunk_id()
            chunks.append(Chunk(
                id=chunk_id,
                text=text,
                metadata={
                    "content_object_id": content_object.id,
                    "chunk_index": i,
                    "chunk_count": len(texts),
                    "permalink": f"/chunks/{chunk_id}",
                    "source_permalink": content_object.permalinks["content"]
                }
            ))
        
        return IngestionResult(
            success=True,
            chunks=chunks,
            chunk_count=len(chunks),
            strategy_metadata={"chunk_size": chunk_size, "overlap": chunk_overlap}
        )
```

#### 6.2 `hierarchical_ingest` (Parent-Child)

Two-level chunking for structure-aware retrieval.

```python
@PluginRegistry.register
class HierarchicalIngestionStrategy(IngestionStrategyPlugin):
    name = "hierarchical_ingest"
    description = "Parent-child chunking for structure-aware queries"
    paired_query_plugin = "parent_child_query"
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "parent_chunk_size": {
                "type": "integer",
                "default": 4000,
                "description": "Size of parent (context) chunks"
            },
            "child_chunk_size": {
                "type": "integer",
                "default": 500,
                "description": "Size of child (search) chunks"
            },
            "child_overlap": {
                "type": "integer",
                "default": 100,
                "description": "Overlap between child chunks"
            }
        }
    
    def ingest(self, content_object, embedding_function, **kwargs) -> IngestionResult:
        parent_size = kwargs.get("parent_chunk_size", 4000)
        child_size = kwargs.get("child_chunk_size", 500)
        child_overlap = kwargs.get("child_overlap", 100)
        
        # Create parent chunks
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_size,
            chunk_overlap=0
        )
        parent_texts = parent_splitter.split_text(content_object.extracted_text)
        
        chunks = []
        
        for p_idx, parent_text in enumerate(parent_texts):
            parent_id = generate_chunk_id()
            
            # Create child chunks from this parent
            child_splitter = RecursiveCharacterTextSplitter(
                chunk_size=child_size,
                chunk_overlap=child_overlap
            )
            child_texts = child_splitter.split_text(parent_text)
            
            children_ids = []
            for c_idx, child_text in enumerate(child_texts):
                child_id = generate_chunk_id()
                children_ids.append(child_id)
                
                chunks.append(Chunk(
                    id=child_id,
                    text=child_text,
                    parent_id=parent_id,
                    metadata={
                        "content_object_id": content_object.id,
                        "chunk_type": "child",
                        "parent_id": parent_id,
                        "child_index": c_idx,
                        "permalink": f"/chunks/{child_id}",
                        "parent_permalink": f"/chunks/{parent_id}"
                    }
                ))
            
            # Parent chunk (stored but not embedded, or embedded separately)
            chunks.append(Chunk(
                id=parent_id,
                text=parent_text,
                children_ids=children_ids,
                metadata={
                    "content_object_id": content_object.id,
                    "chunk_type": "parent",
                    "parent_index": p_idx,
                    "children_count": len(children_ids),
                    "permalink": f"/chunks/{parent_id}",
                    "source_permalink": content_object.permalinks["content"]
                }
            ))
        
        return IngestionResult(
            success=True,
            chunks=chunks,
            chunk_count=len(chunks),
            strategy_metadata={
                "parent_count": len(parent_texts),
                "child_count": len(chunks) - len(parent_texts),
                "parent_size": parent_size,
                "child_size": child_size
            }
        )
```

#### 6.3 `semantic_ingest` (Future)

Chunks based on semantic boundaries (topic shifts).

```python
@PluginRegistry.register
class SemanticIngestionStrategy(IngestionStrategyPlugin):
    name = "semantic_ingest"
    description = "Chunk by semantic boundaries and topic shifts"
    paired_query_plugin = "semantic_query"
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "min_chunk_size": {
                "type": "integer",
                "default": 200,
                "description": "Minimum chunk size"
            },
            "max_chunk_size": {
                "type": "integer",
                "default": 2000,
                "description": "Maximum chunk size"
            },
            "similarity_threshold": {
                "type": "number",
                "default": 0.5,
                "description": "Threshold for detecting topic boundary"
            }
        }
```

#### 6.4 `sliding_window_ingest` (Future)

Overlapping windows for maximum context capture.

```python
@PluginRegistry.register  
class SlidingWindowIngestionStrategy(IngestionStrategyPlugin):
    name = "sliding_window_ingest"
    description = "Heavily overlapping chunks for maximum recall"
    paired_query_plugin = "simple_query"  # Can use simple query
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "window_size": {
                "type": "integer",
                "default": 1000
            },
            "stride": {
                "type": "integer",
                "default": 200,
                "description": "Step size (smaller = more overlap)"
            }
        }
```

---

## 7. Query Plugins & Strategy Pairing

### The Pairing Principle

Each Ingestion Strategy has a **paired Query Plugin** that knows how to retrieve from that strategy's chunks:

| Ingestion Strategy | Paired Query Plugin | Retrieval Behavior |
|-------------------|--------------------|--------------------|
| `simple_ingest` | `simple_query` | Return matching chunks directly |
| `hierarchical_ingest` | `parent_child_query` | Search children, return parents |
| `semantic_ingest` | `semantic_query` | Cluster-aware retrieval |
| `sliding_window_ingest` | `simple_query` | Return matching chunks (dedupe) |

### Query Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class QueryResult:
    """A single query result."""
    chunk_id: str
    text: str
    similarity: float
    metadata: Dict[str, Any]
    permalink: str

@dataclass
class QueryResponse:
    """Response from a query operation."""
    results: List[QueryResult]
    count: int
    timing_ms: float
    query: str
    strategy_info: Dict[str, Any]

class QueryPlugin(ABC):
    """Base class for query plugins."""
    
    name: str = "base_query"
    description: str = "Base query plugin"
    compatible_strategies: List[str] = []  # Which ingestion strategies this works with
    
    @abstractmethod
    def query(
        self,
        collection,  # ChromaDB collection
        query_text: str,
        embedding_function: callable,
        top_k: int = 5,
        threshold: float = 0.0,
        **kwargs
    ) -> QueryResponse:
        """Execute a query against the collection."""
        pass
```

### Parent-Child Query Plugin

```python
@PluginRegistry.register
class ParentChildQueryPlugin(QueryPlugin):
    name = "parent_child_query"
    description = "Query children, return parent context"
    compatible_strategies = ["hierarchical_ingest"]
    
    def query(
        self,
        collection,
        query_text: str,
        embedding_function: callable,
        top_k: int = 5,
        threshold: float = 0.0,
        return_parent: bool = True,
        **kwargs
    ) -> QueryResponse:
        # 1. Search child chunks (they have the embeddings)
        child_results = collection.query(
            query_embeddings=embedding_function([query_text]),
            n_results=top_k * 3,  # Over-fetch to handle deduplication
            where={"chunk_type": "child"}
        )
        
        if not return_parent:
            # Return children directly
            return self._format_results(child_results)
        
        # 2. Collect unique parent IDs
        parent_ids = set()
        for metadata in child_results['metadatas'][0]:
            parent_ids.add(metadata['parent_id'])
        
        # 3. Fetch parent chunks
        parent_results = collection.get(
            ids=list(parent_ids)[:top_k],
            include=['documents', 'metadatas']
        )
        
        # 4. Return parents with original similarity scores
        return self._format_parent_results(
            parent_results, 
            child_results,
            threshold
        )
```

### Automatic Query Plugin Selection

The KB-Server automatically selects the correct query plugin based on the KB's strategy:

```python
async def query_knowledge_base(kb_id: int, query_text: str, top_k: int = 5):
    # Get KB with its strategy
    kb = await get_knowledge_base(kb_id)
    
    # Get the ingestion strategy's paired query plugin
    strategy_plugin = PluginRegistry.get_strategy(kb.ingestion_strategy)
    query_plugin_name = strategy_plugin.paired_query_plugin
    query_plugin = PluginRegistry.get_query_plugin(query_plugin_name)
    
    # Get embedding function from KB's setup
    embedding_fn = get_embedding_function(kb.embeddings_setup_id)
    
    # Execute query with the correct plugin
    return await query_plugin.query(
        collection=get_chroma_collection(kb),
        query_text=query_text,
        embedding_function=embedding_fn,
        top_k=top_k
    )
```

---

## 8. Linkable Content & Permalinks

### Design Goals

1. **Every piece of content has a stable URL**
2. **URLs resolve to useful content** (not just raw data)
3. **Citations in LLM responses can link back to sources**
4. **Support for highlighting specific chunks within documents**

### Permalink Structure

```
https://kb-server.example.com/
├── /content/{content_object_id}           # Content Object landing page
│   ├── /content/{id}/source               # Original file download
│   ├── /content/{id}/preview              # HTML preview
│   ├── /content/{id}/text                 # Extracted text (markdown/plain)
│   └── /content/{id}/metadata             # JSON metadata
│
├── /chunks/{chunk_id}                     # Individual chunk
│   ├── /chunks/{chunk_id}/text            # Chunk text only
│   └── /chunks/{chunk_id}/context         # Chunk with surrounding context
│
└── /kb/{kb_id}/search?q={query}           # Search within KB
```

### Permalink Resolution

```python
@app.get("/content/{content_id}")
async def get_content_page(content_id: str, format: str = "html"):
    """Resolve a content object permalink."""
    content = await get_content_object(content_id)
    
    if format == "html":
        # Return rich HTML page with:
        # - Document preview
        # - Metadata
        # - List of KBs using this content
        # - Download links
        return render_content_page(content)
    
    elif format == "json":
        return content.to_dict()
    
    elif format == "text":
        return PlainTextResponse(content.extracted_text)

@app.get("/chunks/{chunk_id}")
async def get_chunk_page(chunk_id: str, highlight: bool = True):
    """Resolve a chunk permalink."""
    chunk = await get_chunk(chunk_id)
    content = await get_content_object(chunk.content_object_id)
    
    # Return HTML page showing:
    # - The chunk text (highlighted)
    # - Surrounding context from the document
    # - Link to full document
    # - Which KBs contain this chunk
    return render_chunk_page(chunk, content, highlight=highlight)
```

### Embedding Permalinks in LLM Responses

When RAG retrieves chunks, the permalinks are available in metadata:

```python
# In LAMB's RAG processor
def augment_with_sources(chunks: List[QueryResult], response: str) -> str:
    """Add source citations to LLM response."""
    
    sources = []
    for i, chunk in enumerate(chunks):
        sources.append(f"[{i+1}] {chunk.permalink}")
    
    return f"{response}\n\n**Sources:**\n" + "\n".join(sources)
```

### Chunk Context View

For educational use, seeing a chunk in context is valuable:

```html
<!-- /chunks/ch_abc123 -->
<div class="chunk-context-view">
  <div class="document-title">
    <a href="/content/co_xyz789">Research Paper on Machine Learning</a>
  </div>
  
  <div class="context-before" style="opacity: 0.5">
    ...previous paragraph text...
  </div>
  
  <div class="chunk-highlight" style="background: yellow">
    <!-- The actual chunk that was retrieved -->
    Machine learning is a subset of artificial intelligence that enables
    systems to learn and improve from experience without being explicitly
    programmed...
  </div>
  
  <div class="context-after" style="opacity: 0.5">
    ...following paragraph text...
  </div>
  
  <div class="chunk-metadata">
    <span>Chunk 3 of 45</span>
    <span>Used in: KB Alpha, KB Beta</span>
  </div>
</div>
```

---

## 9. Shared Content Across Knowledge Bases

### The Sharing Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Content Sharing Model                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                      ┌─────────────────────┐                                │
│                      │   Content Object    │                                │
│                      │   "research.pdf"    │                                │
│                      │   co_abc123         │                                │
│                      └──────────┬──────────┘                                │
│                                 │                                            │
│                    ┌────────────┼────────────┐                              │
│                    │            │            │                              │
│                    ▼            ▼            ▼                              │
│           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│           │ KB: Course A │ │ KB: Course B │ │ KB: Research │               │
│           │ (simple)     │ │ (hierarchical)│ │ (simple)     │               │
│           │              │ │              │ │              │               │
│           │ 50 chunks    │ │ 10 parents   │ │ 50 chunks    │               │
│           │ from co_abc  │ │ 40 children  │ │ from co_abc  │               │
│           │              │ │ from co_abc  │ │              │               │
│           └──────────────┘ └──────────────┘ └──────────────┘               │
│                                                                              │
│  STORAGE:                                                                    │
│  - Content Object: 1 copy (source file + extracted text)                    │
│  - Chunks: Generated per-KB (different strategies = different chunks)       │
│  - Embeddings: Generated per-KB (same embedding dimensions required)        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Reference Tracking

```python
# When adding content to a KB
async def add_content_to_kb(kb_id: int, content_object_id: str):
    kb = await get_knowledge_base(kb_id)
    content = await get_content_object(content_object_id)
    
    # Validate embedding compatibility
    if kb.embedding_dimensions != content.embedding_dimensions:
        raise IncompatibleDimensionsError()
    
    # Create KB-Content relationship
    await create_kb_content_link(
        kb_id=kb_id,
        content_object_id=content_object_id,
        added_at=datetime.utcnow()
    )
    
    # Generate chunks using KB's strategy
    strategy = PluginRegistry.get_strategy(kb.ingestion_strategy)
    result = await strategy.ingest(
        content_object=content,
        embedding_function=kb.get_embedding_function()
    )
    
    # Store chunks in KB's ChromaDB collection
    await store_chunks(kb, result.chunks)
    
    # Update content object usage stats
    await update_content_usage(content_object_id, kb_id)
```

### Visibility & Access Control

Content Objects have visibility levels:

| Visibility | Who Can Use |
|------------|-------------|
| `private` | Only the owner |
| `organization` | Any user in the organization |
| `public` | Any user in the system (future) |

```python
async def list_available_content(user_id: str, org_id: str) -> List[ContentObject]:
    """List content objects a user can add to their KBs."""
    return await db.query(ContentObject).filter(
        or_(
            ContentObject.owner_id == user_id,  # Own content
            and_(
                ContentObject.organization_id == org_id,
                ContentObject.visibility == "organization"
            )
        ),
        ContentObject.status == "ready"
    ).all()
```

### Content Discovery UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Add Content to Knowledge Base: "Course Materials"                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ [Upload New File]  [Import from URL]  [Browse Organization Content]          │
│                                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│ Organization Content Library:                                    🔍 Search   │
│                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 📄 research_paper.pdf                                          [+ Add]  │ │
│ │    Uploaded by: Dr. Smith  •  Used in: 3 KBs  •  150 potential chunks   │ │
│ │    "Research Paper on Machine Learning Fundamentals"                    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 🎬 YouTube: "Intro to Neural Networks"                         [+ Add]  │ │
│ │    Imported by: Prof. Lee  •  Used in: 5 KBs  •  45 min transcript      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 📄 lecture_notes.md                                    [Already Added]  │ │
│ │    Uploaded by: You  •  Used in: 1 KB  •  Added to this KB              │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Deletion Semantics & Reference Management

### The Deletion Challenge

When content is shared across KBs, deletion becomes complex:

```
Scenario: User wants to delete "research.pdf" (co_abc123)
          But it's used in 3 Knowledge Bases owned by different people!

Options:
A) Refuse deletion (content is in use)
B) Delete from all KBs (dangerous!)
C) Delete only from user's KBs, orphan the content object
D) Soft-delete, hide from user, keep for others
```

### Proposed Solution: Layered Deletion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Deletion Model                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LEVEL 1: Remove from KB (Safe, Always Allowed)                             │
│  ─────────────────────────────────────────────────────────                  │
│  User removes content from THEIR Knowledge Base                              │
│  - Deletes chunks from that KB's ChromaDB collection                        │
│  - Removes KB-Content link                                                   │
│  - Content Object remains (may still be used by other KBs)                  │
│                                                                              │
│  LEVEL 2: Archive Content Object (Owner Only)                               │
│  ─────────────────────────────────────────────────────────                  │
│  Owner archives a Content Object they uploaded                               │
│  - Sets status to "archived"                                                │
│  - Content hidden from "Add to KB" listings                                 │
│  - Existing KB usages continue working                                      │
│  - Can be restored by owner                                                 │
│                                                                              │
│  LEVEL 3: Request Deletion (Owner Only, With Warnings)                      │
│  ─────────────────────────────────────────────────────────                  │
│  Owner requests permanent deletion                                           │
│  - System shows impact: "Used in 3 KBs by 2 other users"                    │
│  - If other users' KBs are affected:                                        │
│    • Require confirmation                                                   │
│    • Notify affected users (optional)                                       │
│    • OR refuse if org policy prohibits                                      │
│  - Deletes: source file, extracted text, all chunks everywhere             │
│                                                                              │
│  LEVEL 4: Admin Force Delete (Org Admin Only)                               │
│  ─────────────────────────────────────────────────────────                  │
│  Organization admin can force-delete any content                             │
│  - Used for: policy violations, legal requirements                          │
│  - Audit logged                                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
async def remove_content_from_kb(
    kb_id: int, 
    content_object_id: str,
    user_id: str
) -> RemovalResult:
    """Level 1: Remove content from a specific KB."""
    
    kb = await get_knowledge_base(kb_id)
    
    # Verify user owns the KB
    if kb.owner_id != user_id:
        raise PermissionDeniedError("You don't own this Knowledge Base")
    
    # Delete chunks from ChromaDB
    chunk_ids = await get_chunk_ids_for_content(kb_id, content_object_id)
    await delete_chunks_from_collection(kb, chunk_ids)
    
    # Remove KB-Content link
    await delete_kb_content_link(kb_id, content_object_id)
    
    # Update content usage stats
    await update_content_usage(content_object_id)
    
    return RemovalResult(
        success=True,
        chunks_deleted=len(chunk_ids),
        content_object_deleted=False,
        message="Content removed from Knowledge Base"
    )


async def archive_content_object(
    content_object_id: str,
    user_id: str
) -> ArchiveResult:
    """Level 2: Archive a content object."""
    
    content = await get_content_object(content_object_id)
    
    # Verify ownership
    if content.owner_id != user_id:
        raise PermissionDeniedError("You don't own this content")
    
    # Archive (soft delete)
    content.status = "archived"
    content.archived_at = datetime.utcnow()
    await content.save()
    
    return ArchiveResult(
        success=True,
        still_used_in=len(content.usage.knowledge_bases),
        message="Content archived. It will continue working in existing KBs."
    )


async def delete_content_object(
    content_object_id: str,
    user_id: str,
    force: bool = False
) -> DeletionResult:
    """Level 3: Request permanent deletion."""
    
    content = await get_content_object(content_object_id)
    
    # Verify ownership
    if content.owner_id != user_id:
        raise PermissionDeniedError("You don't own this content")
    
    # Check impact
    affected_kbs = await get_kbs_using_content(content_object_id)
    other_users_kbs = [kb for kb in affected_kbs if kb.owner_id != user_id]
    
    if other_users_kbs and not force:
        return DeletionResult(
            success=False,
            requires_confirmation=True,
            impact={
                "total_kbs_affected": len(affected_kbs),
                "your_kbs": len(affected_kbs) - len(other_users_kbs),
                "other_users_kbs": len(other_users_kbs),
                "other_users": list(set(kb.owner_id for kb in other_users_kbs)),
                "total_chunks_to_delete": await count_all_chunks(content_object_id)
            },
            message="This content is used by other users. Confirm to proceed."
        )
    
    # Proceed with deletion
    # 1. Delete all chunks from all KBs
    for kb in affected_kbs:
        chunk_ids = await get_chunk_ids_for_content(kb.id, content_object_id)
        await delete_chunks_from_collection(kb, chunk_ids)
    
    # 2. Delete all KB-Content links
    await delete_all_kb_content_links(content_object_id)
    
    # 3. Delete source files
    await delete_source_files(content.source.file_path)
    if content.extracted.html_preview_path:
        await delete_file(content.extracted.html_preview_path)
    
    # 4. Delete content object record
    await content.delete()
    
    return DeletionResult(
        success=True,
        kbs_affected=len(affected_kbs),
        chunks_deleted=await count_all_chunks(content_object_id),
        message="Content permanently deleted"
    )
```

### Deletion Confirmation UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⚠️  Delete Content: "research_paper.pdf"                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ This content is currently used in multiple Knowledge Bases:                  │
│                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ YOUR Knowledge Bases:                                                   │ │
│ │   • "Course Materials" - 45 chunks will be deleted                      │ │
│ │   • "Research Archive" - 45 chunks will be deleted                      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️  OTHER USERS' Knowledge Bases (will be affected!):                   │ │
│ │   • Prof. Lee's "AI Fundamentals" - 50 chunks                           │ │
│ │   • Dr. Smith's "Graduate Seminar" - 50 chunks                          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ IMPACT SUMMARY:                                                              │
│   • 4 Knowledge Bases affected                                              │
│   • 190 chunks will be deleted                                              │
│   • 2 other users will lose access to this content                          │
│                                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│ Alternatives:                                                                │
│   • [Archive Instead] - Hide from listings but keep working in existing KBs │
│   • [Remove from My KBs Only] - Keep available for other users              │
│                                                                              │
│                              [Cancel]  [Delete Permanently]                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Reference Counting & Cleanup

```python
# Background job: Clean up orphaned content
async def cleanup_orphaned_content():
    """Delete content objects with no KB references and archived > 30 days."""
    
    orphaned = await db.query(ContentObject).filter(
        ContentObject.status == "archived",
        ContentObject.archived_at < datetime.utcnow() - timedelta(days=30),
        ~ContentObject.id.in_(
            select(KBContentLink.content_object_id)
        )
    ).all()
    
    for content in orphaned:
        await delete_content_object_permanent(content.id)
        logger.info(f"Cleaned up orphaned content: {content.id}")
```

---

## 11. Database Schema

### Complete Schema

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- ORGANIZATIONS (synced from LAMB)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    config JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════════════════════
-- EMBEDDINGS SETUPS (from Issue #203)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE embeddings_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    setup_key TEXT NOT NULL,
    description TEXT,
    vendor TEXT NOT NULL,
    api_endpoint TEXT,
    api_key TEXT,  -- Encrypted
    model_name TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, setup_key)
);

-- ═══════════════════════════════════════════════════════════════════════════
-- CONTENT OBJECTS (new - stores imported content before chunking)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE content_objects (
    id TEXT PRIMARY KEY,  -- "co_" + nanoid
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    owner_id TEXT NOT NULL,
    
    -- Source information
    source_type TEXT NOT NULL,  -- "file", "url", "youtube", etc.
    original_filename TEXT,
    content_type TEXT,  -- MIME type
    file_path TEXT,  -- Local storage path
    file_size INTEGER,
    file_hash TEXT,  -- SHA256 for deduplication
    source_url TEXT,  -- Original URL if applicable
    
    -- Extracted content
    extracted_text TEXT,
    text_format TEXT DEFAULT 'markdown',  -- "markdown", "plain", "html"
    text_hash TEXT,
    extraction_plugin TEXT,
    extraction_params JSON,
    html_preview_path TEXT,
    
    -- Metadata
    title TEXT,
    metadata JSON,
    
    -- Status
    status TEXT DEFAULT 'uploaded',  -- uploaded, extracting, ready, archived, failed
    error_message TEXT,
    error_details JSON,
    
    -- Visibility
    visibility TEXT DEFAULT 'private',  -- private, organization, public
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME
);

CREATE INDEX idx_content_objects_org ON content_objects(organization_id);
CREATE INDEX idx_content_objects_owner ON content_objects(owner_id);
CREATE INDEX idx_content_objects_hash ON content_objects(organization_id, file_hash);
CREATE INDEX idx_content_objects_status ON content_objects(status);

-- ═══════════════════════════════════════════════════════════════════════════
-- KNOWLEDGE BASES (enhanced collections)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE knowledge_bases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    owner_id TEXT NOT NULL,
    
    -- Embeddings configuration (reference to setup)
    embeddings_setup_id INTEGER NOT NULL REFERENCES embeddings_setups(id),
    embedding_dimensions INTEGER NOT NULL,  -- Locked at creation
    
    -- Ingestion configuration (LOCKED at creation)
    ingestion_strategy TEXT NOT NULL DEFAULT 'simple_ingest',
    ingestion_params JSON,  -- Strategy-specific defaults
    
    -- ChromaDB reference
    chromadb_collection_name TEXT UNIQUE,
    
    -- Stats (cached, updated periodically)
    content_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    
    -- Visibility
    visibility TEXT DEFAULT 'private',
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(organization_id, owner_id, name)
);

CREATE INDEX idx_kb_org ON knowledge_bases(organization_id);
CREATE INDEX idx_kb_owner ON knowledge_bases(owner_id);
CREATE INDEX idx_kb_setup ON knowledge_bases(embeddings_setup_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- KB-CONTENT LINKS (many-to-many between KBs and Content Objects)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE kb_content_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    content_object_id TEXT NOT NULL REFERENCES content_objects(id),
    
    -- Ingestion info for this KB
    chunk_count INTEGER DEFAULT 0,
    ingestion_status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    ingestion_error TEXT,
    
    -- Timestamps
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ingested_at DATETIME,
    
    UNIQUE(kb_id, content_object_id)
);

CREATE INDEX idx_kb_content_kb ON kb_content_links(kb_id);
CREATE INDEX idx_kb_content_content ON kb_content_links(content_object_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- CHUNKS (metadata only - actual vectors in ChromaDB)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,  -- "ch_" + nanoid for child, "pc_" + nanoid for parent
    kb_id INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    content_object_id TEXT NOT NULL REFERENCES content_objects(id),
    
    -- Chunk info
    chunk_type TEXT DEFAULT 'standard',  -- standard, parent, child
    chunk_index INTEGER,
    parent_chunk_id TEXT REFERENCES chunks(id),
    
    -- Text (duplicated from ChromaDB for permalinks)
    text TEXT NOT NULL,
    text_start_char INTEGER,  -- Position in original text
    text_end_char INTEGER,
    
    -- Metadata
    metadata JSON,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_kb ON chunks(kb_id);
CREATE INDEX idx_chunks_content ON chunks(content_object_id);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);
CREATE INDEX idx_chunks_type ON chunks(kb_id, chunk_type);

-- ═══════════════════════════════════════════════════════════════════════════
-- INGESTION JOBS (for tracking async processing)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE ingestion_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id INTEGER NOT NULL REFERENCES knowledge_bases(id),
    content_object_id TEXT NOT NULL REFERENCES content_objects(id),
    
    -- Job status
    status TEXT DEFAULT 'queued',  -- queued, processing, completed, failed, cancelled
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    progress_message TEXT,
    
    -- Error handling
    error_message TEXT,
    error_details JSON,
    retry_count INTEGER DEFAULT 0,
    
    -- Timing
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    
    UNIQUE(kb_id, content_object_id)
);

CREATE INDEX idx_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_jobs_kb ON ingestion_jobs(kb_id);
```

---

## 12. API Design

### Content Object Endpoints

```http
# ═══════════════════════════════════════════════════════════════
# CONTENT OBJECT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# Upload and import a file
POST /content/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: <binary>
import_plugin: "markitdown_import"  # Optional, auto-detected if omitted
import_params: {"ocr_enabled": true}  # Optional
visibility: "organization"  # Optional, default "private"

Response 202:
{
  "id": "co_7f3a8b2c",
  "status": "extracting",
  "message": "Content uploaded, extraction in progress"
}

# Import from URL
POST /content/import-url
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://example.com/article",
  "import_plugin": "url_import",
  "import_params": {"extract_main_content": true},
  "visibility": "organization"
}

# List content objects
GET /content?visibility=organization&status=ready&limit=50
Authorization: Bearer {token}

# Get content object details
GET /content/{content_id}
Authorization: Bearer {token}

# Get content preview (HTML)
GET /content/{content_id}/preview
Authorization: Bearer {token}

# Download source file
GET /content/{content_id}/source
Authorization: Bearer {token}

# Get extracted text
GET /content/{content_id}/text
Authorization: Bearer {token}

# Archive content
POST /content/{content_id}/archive
Authorization: Bearer {token}

# Delete content
DELETE /content/{content_id}?force=true
Authorization: Bearer {token}
```

### Knowledge Base Endpoints

```http
# ═══════════════════════════════════════════════════════════════
# KNOWLEDGE BASE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# Create KB (with strategy selection)
POST /kb
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Course Materials",
  "description": "Materials for AI 101",
  "embeddings_setup_key": "openai-prod",
  "ingestion_strategy": "hierarchical_ingest",
  "ingestion_params": {
    "parent_chunk_size": 4000,
    "child_chunk_size": 500
  },
  "visibility": "organization"
}

Response 201:
{
  "id": 42,
  "name": "Course Materials",
  "ingestion_strategy": "hierarchical_ingest",
  "paired_query_plugin": "parent_child_query",
  "embedding_dimensions": 1536,
  "message": "Strategy locked. Cannot be changed after creation."
}

# Add content to KB
POST /kb/{kb_id}/content
Authorization: Bearer {token}
Content-Type: application/json

{
  "content_object_id": "co_7f3a8b2c",
  "ingestion_params": {}  # Optional override
}

Response 202:
{
  "job_id": 101,
  "status": "queued",
  "message": "Content queued for ingestion"
}

# List content in KB
GET /kb/{kb_id}/content
Authorization: Bearer {token}

# Remove content from KB
DELETE /kb/{kb_id}/content/{content_id}
Authorization: Bearer {token}

# Query KB (auto-selects query plugin)
POST /kb/{kb_id}/query
Authorization: Bearer {token}
Content-Type: application/json

{
  "query_text": "What are the main steps?",
  "top_k": 5,
  "threshold": 0.5
}

Response:
{
  "results": [...],
  "query_plugin_used": "parent_child_query",
  "strategy": "hierarchical_ingest"
}
```

### Permalink Endpoints

```http
# ═══════════════════════════════════════════════════════════════
# PERMALINKS (public-ish, may require auth based on visibility)
# ═══════════════════════════════════════════════════════════════

# Content landing page
GET /content/{content_id}
Accept: text/html  # Returns rich HTML page
Accept: application/json  # Returns JSON

# Chunk permalink
GET /chunks/{chunk_id}
Accept: text/html  # Returns chunk-in-context view
Accept: application/json  # Returns chunk data

# Chunk with context
GET /chunks/{chunk_id}/context?lines=10
```

---

## 13. Migration Strategy

### Phase 1: Schema Evolution (Non-Breaking)

1. Create new tables alongside existing ones
2. Keep `file_registry` and `collections` working
3. Add backward-compatible columns

### Phase 2: Dual-Path Support

```python
# Support both old and new paths during migration
async def ingest_file(kb_id: int, file: UploadFile, plugin_name: str):
    kb = await get_knowledge_base(kb_id)
    
    if kb.uses_new_architecture:
        # New path: Content Object → Ingestion Strategy
        content = await create_or_get_content_object(file)
        return await ingest_content_to_kb(kb, content)
    else:
        # Old path: Direct ingestion (existing behavior)
        return await legacy_ingest_file(kb, file, plugin_name)
```

### Phase 3: Data Migration

```python
async def migrate_kb_to_new_architecture(kb_id: int):
    """Migrate an existing KB to the new architecture."""
    kb = await get_knowledge_base(kb_id)
    
    # 1. Get all files from file_registry
    files = await get_files_for_collection(kb.chromadb_collection_name)
    
    for file in files:
        # 2. Create Content Object for each file
        content = await create_content_object_from_file_registry(file)
        
        # 3. Create KB-Content link
        await create_kb_content_link(kb_id, content.id)
        
        # 4. Update chunk metadata with content_object_id
        await update_chunks_with_content_id(kb_id, file.id, content.id)
    
    # 5. Mark KB as migrated
    kb.uses_new_architecture = True
    await kb.save()
```

### Phase 4: Deprecation

1. New KBs always use new architecture
2. Old KBs can be migrated on-demand or in batch
3. Eventually remove legacy code paths

---

## 14. Trade-offs & Alternatives Considered

### Alternative A: Full Deduplication (Shared Chunks)

**Approach:** Store chunks once, have KBs reference them.

```
Content Object
    └── Chunks (stored once)
            └── Referenced by multiple KBs
```

**Pros:**
- Maximum storage efficiency
- Single embedding per chunk

**Cons:**
- Different KBs can't use different chunking strategies
- Deletion is extremely complex
- Embedding dimension lock-in across all KBs using the content

**Decision:** Rejected. Strategy flexibility is more important than storage savings.

---

### Alternative B: No Sharing (Current Model, Enhanced)

**Approach:** Each KB has completely independent copies.

**Pros:**
- Simple deletion
- Complete independence

**Cons:**
- Storage duplication
- No way to trace "this PDF is used in 5 KBs"
- Can't offer content library/reuse

**Decision:** Rejected. Content reuse is a valuable feature for educational institutions.

---

### Alternative C: Hybrid (Proposed)

**Approach:** Share Content Objects, generate chunks per-KB.

**Pros:**
- Source deduplication (files stored once)
- Strategy flexibility (each KB chunks differently)
- Clear deletion semantics
- Content library/discovery

**Cons:**
- More complex than alternatives
- Chunks are duplicated (but text, not files)
- Need to track Content-KB relationships

**Decision:** Accepted. Best balance of features and complexity.

---

### Alternative for Permalinks: External URL Generation

**Approach:** Generate permalinks pointing to original sources.

**Pros:**
- No need to host content

**Cons:**
- External sources may disappear
- No control over presentation
- Can't highlight specific chunks

**Decision:** Rejected. Self-hosted permalinks provide better reliability and UX.

---

## 15. Open Questions

### Technical Questions

1. **Chunk Text Storage:** Should chunk text be duplicated in SQLite for permalinks, or fetched from ChromaDB on demand?
   - *Proposal:* Store in SQLite for fast permalink resolution

2. **Embedding Dimension Validation:** When adding content to a KB, should we re-verify dimensions match?
   - *Proposal:* Yes, validate on every add operation

3. **Cross-Organization Content:** Should content ever be shareable across organizations?
   - *Proposal:* Not in v1. Keep organization as hard boundary.

4. **Chunk ID Format:** How to generate stable, unique chunk IDs?
   - *Proposal:* `{type}_{nanoid}` e.g., `ch_7f3a8b2c`, `pc_9d2e4f1a`

### Policy Questions

5. **Deletion Notification:** Should users be notified when shared content they use is deleted?
   - *Needs team decision*

6. **Content Ownership Transfer:** Can content ownership be transferred?
   - *Proposal:* Yes, between users in same organization (admin action)

7. **Archival Period:** How long should archived content be kept before permanent deletion?
   - *Proposal:* 30 days, configurable per organization

### UX Questions

8. **Default Visibility:** Should new content default to `private` or `organization`?
   - *Proposal:* `private` for safety, with easy toggle to `organization`

9. **Strategy Recommendation:** Should we recommend strategies based on content type?
   - *Proposal:* Yes. E.g., "This looks like a structured document. Hierarchical strategy recommended."

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Content Object** | Imported source material before chunking (file + extracted text) |
| **Chunk** | A piece of text generated by an ingestion strategy |
| **Parent Chunk** | In hierarchical strategy, a large context chunk |
| **Child Chunk** | In hierarchical strategy, a small searchable chunk |
| **Ingestion Strategy** | Algorithm for splitting content into chunks |
| **Query Plugin** | Algorithm for retrieving chunks, paired with a strategy |
| **Permalink** | Stable URL that resolves to content or a chunk |
| **KB-Content Link** | Relationship between a Knowledge Base and a Content Object |

---

## Appendix B: Migration Checklist

- [ ] Create new database tables
- [ ] Implement Content Object CRUD
- [ ] Implement Format Import plugin interface
- [ ] Migrate existing ingestion plugins to new interface
- [ ] Implement Ingestion Strategy plugin interface
- [ ] Create `simple_ingest` strategy (equivalent to current)
- [ ] Create `hierarchical_ingest` strategy
- [ ] Implement query plugin auto-selection
- [ ] Create permalink endpoints
- [ ] Build content library UI
- [ ] Build deletion confirmation UI
- [ ] Create migration scripts for existing KBs
- [ ] Update LAMB integration layer
- [ ] Documentation and testing

---

**Document Version:** 2.0 Draft  
**Last Updated:** February 3, 2026  
**Status:** Proposal for Review  
**Next Steps:** Team review, address open questions, prioritize implementation phases
