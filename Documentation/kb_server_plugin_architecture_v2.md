# KB-Server Plugin Architecture v2.1

**Version:** 2.1
**Date:** March 15, 2026
**Status:** Design Proposal (Updated)
**Authors:** Development Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State (Post #203 + #229)](#2-current-state-post-203--229)
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
15. [Open Questions & Recommendations](#15-open-questions--recommendations)

---

## 1. Executive Summary

This document proposes the next evolution of the lamb-kb-server architecture, **building on the foundation laid by Issues #203 and #229**. Those issues delivered:

- **Organization-level management** of retrieval backend configurations (#203)
- **Knowledge Store Plugin abstraction** enabling technology-agnostic retrieval backends (#229)
- **Per-collection backend selection** via `KnowledgeStoreSetup` records
- **Full service-layer decoupling** from ChromaDB internals

This v2.1 proposal extends that foundation to address three remaining challenges:

1. **Separation of Concerns**: Split monolithic ingestion plugins into two layers:
   - **Format Import Plugins**: Convert source files to standardized content bundles
   - **Ingestion Strategy Plugins**: Implement chunking strategies (simple, hierarchical, semantic, etc.)

2. **Linkable Content**: Every piece of content should have stable, resolvable permalinks that can be cited in LLM responses and traced back to source material.

3. **Shared Content**: Enable multiple Knowledge Bases to reference the same underlying content without duplication, while maintaining clear deletion semantics.

### Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Partition → Chunk → Store** | Three-stage pipeline following Unstructured.io / LangChain best practices |
| **Source Once, Chunk Many** | Import content once, apply different chunking strategies per KB |
| **Stable Identifiers** | Nanoid primary keys + content hashes for deduplication |
| **Reference Transparency** | Clear tracking of what KBs use what content |
| **Safe Deletion** | Soft delete + reference counting; "remove reference" vs "delete canonical" |
| **Strategy Lock-in** | KB's ingestion strategy is fixed at creation (like embedding dimensions) |
| **Backend Agnosticism** | Services work with chunks + metadata only, never touching backend internals |

### Relationship to Completed Work

| Foundation (Done) | This Proposal (New) |
|-------------------|---------------------|
| `KnowledgeStorePlugin` interface (11 methods) | `FormatImportPlugin` interface |
| `ChromaDBPlugin` implementation | `IngestionStrategyPlugin` interface |
| `KnowledgeStoreSetup` model with `plugin_type` + `plugin_config` | `ContentObject` model |
| `resolve_plugin_for_collection()` helper | `ContentObject` model + `file_registry` enhanced with `content_object_id` |
| Query plugins receive `ks_plugin` + `backend_collection` | Automatic query plugin selection via strategy pairing |
| Dual-mode backward compat (OLD/NEW MODE) | Content deduplication by file hash |

---

## 2. Current State (Post #203 + #229)

### Architecture as Implemented

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         lamb-kb-server (current)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Organizations                                                              │
│      ↓ 1:N                                                                  │
│  KnowledgeStore Setups (plugin_type + plugin_config)                        │
│    Setup 1: ChromaDB + OpenAI (plugin_type: "chromadb")                     │
│    Setup 2: ChromaDB + Ollama (plugin_type: "chromadb")                     │
│      ↓ 1:N                                                                  │
│  Collections (reference setup_id)                                           │
│      ↓                                                                      │
│  Service Layer (technology-agnostic: chunks + metadata only)                │
│      ↓                                                                      │
│  KnowledgeStorePlugin Interface (11 abstract methods)                       │
│      ↓                                                                      │
│  ┌──────────┐                                                               │
│  │ ChromaDB │  (only implementation today)                                  │
│  │ Plugin   │                                                               │
│  └──────────┘                                                               │
│                                                                              │
│  Ingestion Plugins (monolithic: format + chunking combined)                 │
│  ┌────────────────┬──────────────┬──────────────┬────────────┐              │
│  │markitdown_ingest│ url_ingest   │youtube_ingest│srt_ingest  │              │
│  └────────────────┴──────────────┴──────────────┴────────────┘              │
│                                                                              │
│  Query Plugins (receive ks_plugin + backend_collection)                     │
│  ┌──────────────┬───────────────────────┐                                   │
│  │ simple_query │ parent_child_query    │                                   │
│  └──────────────┴───────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What's Already Solved

| Capability | How |
|-----------|-----|
| Technology-agnostic storage | `KnowledgeStorePlugin` interface + `resolve_plugin_for_collection()` |
| Per-collection backend selection | `Collection.knowledge_store_setup_id` FK |
| API key rotation | Update `KnowledgeStoreSetup.plugin_config` once, all collections affected |
| Plugin discovery | `KnowledgeStoreRegistry.register` decorator + `list_knowledge_store_plugins()` |
| Config validation | `KnowledgeStorePlugin.validate_plugin_config()` + `/knowledge-store-plugins/{type}/validate-config` endpoint |
| Backward compatibility | `resolve_plugin_for_collection()` handles both OLD MODE (inline config) and NEW MODE (setup reference) |

### Remaining Problems

| Problem | Impact |
|---------|--------|
| **Mixed responsibilities in ingestion** | Can't use hierarchical chunking with PDF import |
| **No content reuse** | Same PDF imported 5 times = 5 copies stored |
| **No stable links** | Can't create permalinks to chunks for citations |
| **Strategy coupling** | Changing chunking strategy requires re-import of source files |
| **No cross-KB content visibility** | Can't see "this PDF is used in 5 KBs" |

---

## 3. Proposed Architecture

### Three-Stage Pipeline

Following industry best practices (Unstructured.io, LangChain, Haystack), the ingestion pipeline is split into three independently cacheable stages:

```
Raw Source → [PARTITION] → Content Object → [CHUNK] → Chunks → [STORE] → Backend
               Layer 1                       Layer 2              Layer 3 (done)
         Format Import Plugin         Ingestion Strategy    KnowledgeStorePlugin
                                          Plugin            (already implemented)
```

**Stage 1 — Partition (Format Import)**: Understands file formats. Converts PDF/DOCX/URL/YouTube to extracted text + metadata. Output is a **Content Object** stored once.

**Stage 2 — Chunk (Ingestion Strategy)**: Understands text structure. Splits extracted text into chunks using a configurable strategy. Each KB can apply a different strategy to the same content.

**Stage 3 — Store (Knowledge Store)**: Already implemented (#229). Stores chunks in the backend via `ks_plugin.add_chunks()`. Backend handles embeddings, indexing, graph construction, etc. internally.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         lamb-kb-server v2.1                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 1: Format Import                               │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │  PDF Import  │ │ DOCX Import  │ │  URL Import  │ │YouTube Import│   │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │ │
│  │         └────────────────┴────────────────┴────────────────┘           │ │
│  │                                   │                                     │ │
│  │                                   ▼                                     │ │
│  │                    ┌──────────────────────────┐                         │ │
│  │                    │    Content Object        │ ← Stored once           │ │
│  │                    │    (Source + Text)       │   Shared across KBs     │ │
│  │                    │    Deduplicated by hash  │                         │ │
│  │                    └──────────────────────────┘                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                   │                                          │
│                                   │ Reference (many-to-many)                │
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
│  └───────────┼───────────────────────────┼──────────────────────┼────────┘ │
│              │                            │                       │          │
│  ┌───────────┼───────────────────────────┼──────────────────────┼────────┐ │
│  │           ▼          LAYER 3: Knowledge Store (DONE)         ▼        │ │
│  │  KnowledgeStorePlugin.add_chunks() / query_chunks()                  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │ │
│  │  │ ChromaDB │  │  Qdrant  │  │  Neo4j   │  │ElasticSch│             │ │
│  │  │ Plugin   │  │  Plugin  │  │  Plugin  │  │  Plugin  │             │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
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
                    │  │ id: "co_abc123"        │ │  ← nanoid (stable)
                    │  │ file_hash: "sha256:…"  │ │  ← for deduplication
                    │  │ extracted_text: "…"    │ │
                    │  │ metadata: {…}          │ │
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

A **Content Object** represents imported source material before any chunking occurs. It's the canonical representation of a document, URL, or media file. Content Objects are:

- **Stored once** per organization (deduplicated by `file_hash`)
- **Shared** across multiple Knowledge Bases via `file_registry.content_object_id`
- **Immutable** after extraction (if the source changes, a new Content Object is created)
- **Addressable** via stable nanoid-based permalinks

### Content Object Structure

```json
{
  "id": "co_7f3a8b2c",
  "organization_id": 1,
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

  "usage": {
    "knowledge_bases": ["kb_001", "kb_002", "kb_003"],
    "total_chunk_count": 450,
    "first_used": "2026-01-15T10:00:00Z",
    "last_used": "2026-02-03T14:30:00Z"
  },

  "visibility": "organization",
  "status": "ready",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-02-03T14:30:00Z"
}
```

### Content Object Lifecycle

```
  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
  │ UPLOADED │ ───► │EXTRACTING│ ───► │  READY   │ ───► │ ARCHIVED │
  └──────────┘      └──────────┘      └──────────┘      └──────────┘
       │                 │                 │                 │
       │                 │                 │                 ▼
       │                 │                 │           ┌──────────┐
       │                 │                 └─────────► │ DELETED  │
       │                 │                             └──────────┘
       │                 ▼                                  ▲
       │           ┌──────────┐                             │
       └─────────► │  FAILED  │ ────────────────────────────┘
                   └──────────┘
```

### Content Deduplication

Content Objects are deduplicated by `file_hash` within an organization:

```python
def get_or_create_content_object(org_id: int, file: UploadFile) -> ContentObject:
    file_hash = compute_sha256(file)

    existing = db.query(ContentObject).filter(
        ContentObject.organization_id == org_id,
        ContentObject.file_hash == file_hash
    ).first()

    if existing and existing.status == "ready":
        return existing  # Reuse existing content

    return create_new_content_object(org_id, file, file_hash)
```

### ID Strategy

Following industry best practices, Content Objects and Chunks use a **hybrid ID approach**:

- **Primary key**: `{type_prefix}_{nanoid}` (e.g., `co_7f3a8b2c`, `ch_9d2e4f1a`, `pc_3b7c1d5e`)
  - Stable across content changes
  - No coordination needed for distributed generation
  - Human-readable type prefix aids debugging
- **Content hash**: Stored separately as `file_hash` / `text_hash` for deduplication
  - Used at ingestion time to detect "this exact content was already indexed"
  - Never used as a primary key (would change when content is updated)

---

## 5. Plugin Layer 1: Format Import Plugins

### Purpose

Format Import Plugins implement Stage 1 of the pipeline (Partition). They are responsible for:
1. Receiving source files/URLs
2. Extracting text content in a standardized format
3. Creating Content Objects
4. Generating preview files (HTML)
5. Extracting metadata (title, author, pages, etc.)

### Design Note: Relationship to Existing Ingest Plugins

Today's `IngestPlugin` classes (e.g., `markitdown_ingest`) combine format conversion AND chunking in a single plugin. The v2.1 migration path:

1. Extract the format-conversion code from each `IngestPlugin` into a `FormatImportPlugin`
2. The chunking code becomes part of `IngestionStrategyPlugin` (Section 6)
3. Existing `IngestPlugin` remains functional during migration (dual-path support)

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
    """Base class for format import plugins.

    Responsibility: Convert raw source material into extracted text.
    Does NOT chunk, embed, or store. Only extracts.
    """

    name: str = "base_import"
    description: str = "Base import plugin"
    supported_types: set = set()  # MIME types or extensions

    @abstractmethod
    def can_import(self, source: str, content_type: Optional[str] = None) -> bool:
        """Check if this plugin can handle the given source."""

    @abstractmethod
    def import_file(self, file_path: str, **kwargs) -> ImportResult:
        """Import a local file. Returns extracted text and metadata."""

    @abstractmethod
    def import_url(self, url: str, **kwargs) -> ImportResult:
        """Import content from a URL. Returns extracted text and metadata."""

    @abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Return plugin parameters schema."""
```

### Available Format Import Plugins

| Plugin | Handles | Library |
|--------|---------|---------|
| `markitdown_import` | PDF, DOCX, PPTX, XLSX, HTML | MarkItDown |
| `url_import` | Web pages | requests + readability |
| `youtube_import` | YouTube video transcripts | youtube-transcript-api |
| `plain_text_import` | TXT, MD files | built-in |
| `srt_import` | Subtitle files (.srt) | built-in |

---

## 6. Plugin Layer 2: Ingestion Strategy Plugins

### Purpose

Ingestion Strategy Plugins implement Stage 2 of the pipeline (Chunk). They:
1. Take a Content Object's extracted text
2. Apply a chunking strategy
3. Return a list of chunks with metadata (including permalinks)

**They do NOT embed or store.** The Knowledge Store Plugin (Layer 3) handles that.

### Strategy Lock-in

> **A Knowledge Base's ingestion strategy is FIXED at creation time.**

This is analogous to how embedding dimensions are locked. Different strategies produce incompatible chunk structures — mixing them in one KB would break query consistency.

### Parameter History

When a KB's `ingestion_params` are changed, the change only affects future ingestions. Each `file_registry` entry records the actual params used at ingestion time in its `plugin_params` JSON field. This means:
- `collections.ingestion_params` = the **current default** for new ingestions
- `file_registry.plugin_params` = the **actual params** used for each past ingestion

This preserves full traceability: you can always determine exactly what parameters were used to chunk any given file.

### Plugin Interface

```python
@dataclass
class Chunk:
    """A single chunk produced by an ingestion strategy."""
    id: str                                    # nanoid-based: "ch_xxx" or "pc_xxx"
    text: str                                  # Chunk text — passed to KnowledgeStorePlugin.add_chunks()
    text_start_char: int                       # Offset into content_objects.extracted_text
    text_end_char: int                         # End offset — persisted to SQLite chunks table
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None            # For hierarchical strategies
    children_ids: Optional[List[str]] = None   # For hierarchical strategies

@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    success: bool
    chunks: List[Chunk]
    chunk_count: int
    strategy_metadata: Dict[str, Any]
    error_message: Optional[str] = None

class IngestionStrategyPlugin(ABC):
    """Base class for ingestion strategy plugins."""

    name: str = "base_strategy"
    description: str = "Base ingestion strategy"
    paired_query_plugin: str = "simple_query"  # Which query plugin to use

    @abstractmethod
    def ingest(self, content_text: str, content_object_id: str, **kwargs) -> IngestionResult:
        """Split text into chunks. Does NOT embed or store."""

    @abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Return strategy parameters schema."""
```

### Available Strategies

| Strategy | Paired Query | Description |
|----------|-------------|-------------|
| `simple_ingest` | `simple_query` | Fixed-size chunking with overlap (current default) |
| `hierarchical_ingest` | `parent_child_query` | Two-level parent-child chunking |
| `semantic_ingest` (future) | `semantic_query` | Chunks by semantic/topic boundaries |
| `sliding_window_ingest` (future) | `simple_query` | Heavily overlapping windows |

---

## 7. Query Plugins & Strategy Pairing

### The Pairing Principle

Each Ingestion Strategy has a **paired Query Plugin** that knows how to retrieve from that strategy's chunks. The KB-Server automatically selects the correct query plugin based on the KB's strategy.

| Ingestion Strategy | Paired Query Plugin | Retrieval Behavior |
|-------------------|--------------------|--------------------|
| `simple_ingest` | `simple_query` | Return matching chunks directly |
| `hierarchical_ingest` | `parent_child_query` | Search children, return parents |
| `semantic_ingest` | `semantic_query` | Cluster-aware retrieval |

### Current Query Plugin Interface (Already Implemented)

Query plugins already receive `ks_plugin` and `backend_collection` from the service layer (implemented in #229). The v2.1 change is minimal — add automatic plugin selection:

```python
async def query_knowledge_base(kb_id: int, query_text: str, top_k: int = 5):
    kb = await get_knowledge_base(kb_id)

    # Auto-select query plugin from KB's ingestion strategy
    strategy = StrategyRegistry.get(kb.ingestion_strategy)
    query_plugin = PluginRegistry.get_query_plugin(strategy.paired_query_plugin)

    # Resolve backend (already implemented)
    ks_plugin, plugin_config, col_name = resolve_plugin_for_collection(kb, db)
    backend_collection = ks_plugin.get_collection(col_name, plugin_config)

    return query_plugin.query(
        collection_id=kb_id,
        query_text=query_text,
        ks_plugin=ks_plugin,
        backend_collection=backend_collection,
        top_k=top_k
    )
```

---

## 8. Linkable Content & Permalinks

### Design Principle: Separation of Concerns

The permalink system spans two services with clear responsibilities:

| Responsibility | Owner | Why |
|----------------|-------|-----|
| Store content & chunk data | **KB-Server** | KB-server is the source of truth for content |
| Serve data via bearer-token API | **KB-Server** | Simple auth — if you have the API key, you're in |
| Generate signed URLs for external sharing | **LAMB** | LAMB owns user identity and auth |
| Verify signed URLs and render HTML pages | **LAMB** | LAMB is the user-facing gateway |
| Manage link expiration and org scoping | **LAMB** | LAMB knows about organizations, roles, policies |

**The KB-server doesn't change its auth model.** It continues to use bearer-token authentication for all requests. LAMB handles everything related to external sharing.

### Design Goals

1. Every piece of content has a stable, shareable URL
2. Citations in LLM responses can include clickable source links
3. Links work without requiring the recipient to have a LAMB account
4. Links expire after a configurable period (default: 7 days)
5. Organization boundary is enforced — links can't leak content across orgs

### How It Works: Two Access Paths

**Path A — Internal (logged-in users):**
```
User (logged in) → LAMB frontend → LAMB backend (bearer token) → KB-server (API key) → data
```
Normal authenticated flow. User sees content inline in the LAMB UI. No signed URLs needed.

**Path B — External (shared links):**
```
External person → clicks signed URL → LAMB /share/ endpoint → verifies JWT
                                          → proxies to KB-server (API key) → renders HTML page
```
The signed URL bypasses LAMB's login requirement but still goes through LAMB (never directly to KB-server).

### Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────┐
│  External User  │     │           LAMB               │     │    KB-Server     │
│  (no account)   │     │                              │     │                  │
└────────┬────────┘     │  ┌────────────────────────┐  │     │  Auth: bearer    │
         │              │  │ /share/chunk/{id}       │  │     │  token only      │
         │ GET /share/  │  │   ?sig=eyJ...           │  │     │                  │
         │ chunk/ch_abc │  │                        │  │     │  Endpoints:      │
         │ ?sig=eyJ...  │  │ 1. Verify JWT          │  │     │  GET /chunks/{id}│
         │─────────────►│  │ 2. Check expiration    │  │     │  GET /content/{id│
         │              │  │ 3. Check org scope     │  │     │                  │
         │              │  │ 4. Proxy to KB-server  │──┼────►│  Returns data    │
         │              │  │    with API key         │  │     │  with bearer     │
         │              │  │ 5. Render HTML page    │◄─┼─────│  token auth      │
         │◄─────────────│  └────────────────────────┘  │     │                  │
         │ Rendered HTML │                              │     │                  │
         │ with chunk    │  ┌────────────────────────┐  │     │                  │
         │ in context    │  │ /creator/permalinks/   │  │     │                  │
         │              │  │   generate             │  │     │                  │
         │              │  │                        │  │     │                  │
         │              │  │ Authenticated endpoint  │  │     │                  │
         │              │  │ for generating signed  │  │     │                  │
         │              │  │ URLs on demand         │  │     │                  │
         │              │  └────────────────────────┘  │     │                  │
         │              └──────────────────────────────┘     └──────────────────┘
```

### KB-Server: What It Provides (No Changes to Auth Model)

The KB-server exposes content and chunk data through its existing bearer-token API. These endpoints are used by LAMB to serve permalink content:

```http
# Get chunk data (bearer-token authenticated, called by LAMB)
GET /chunks/{chunk_id}
Authorization: Bearer {kb_api_key}

Response:
{
  "id": "ch_abc123",
  "collection_id": 42,
  "content_object_id": "co_xyz789",
  "chunk_type": "standard",
  "chunk_index": 3,
  "text_start_char": 4200,
  "text_end_char": 5200,
  "metadata": {...}
}

# Get content object with extracted text (for offset resolution)
GET /content/{content_id}
Authorization: Bearer {kb_api_key}

Response:
{
  "id": "co_xyz789",
  "title": "Research Paper",
  "extracted_text": "Full document text...",
  "source": {...},
  "metadata": {...}
}
```

### LAMB: Signed URL Generation & Verification

LAMB owns the signed URL lifecycle. It generates JWTs signed with LAMB's own secret key.

**Signed URL format:**
```
https://lamb.example.com/share/chunk/ch_abc123?sig=eyJ...
https://lamb.example.com/share/content/co_xyz789?sig=eyJ...
```

**Generation (LAMB backend):**

```python
import jwt
from datetime import datetime, timedelta

# LAMB's secret key (NOT the KB-server API key)
PERMALINK_SECRET = os.getenv("PERMALINK_SECRET_KEY", SECRET_KEY)

def generate_signed_url(resource_type: str, resource_id: str,
                         user_id: str, org_id: int,
                         expires_in: timedelta = timedelta(days=7)) -> str:
    """Generate a signed URL for external sharing. Called by LAMB only."""
    payload = {
        "sub": resource_id,
        "type": resource_type,       # "chunk" or "content"
        "uid": user_id,              # who generated the link (audit trail)
        "org": org_id,               # organization boundary
        "exp": datetime.utcnow() + expires_in,
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, PERMALINK_SECRET, algorithm="HS256")
    base_url = os.getenv("LAMB_BASE_URL", "")
    return f"{base_url}/share/{resource_type}/{resource_id}?sig={token}"
```

**Verification and rendering (LAMB backend):**

```python
@router.get("/share/{resource_type}/{resource_id}")
async def resolve_shared_link(resource_type: str, resource_id: str, sig: str):
    """Public endpoint — no login required. Verifies JWT signature."""
    try:
        payload = jwt.decode(sig, PERMALINK_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(410, "This link has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid link.")

    if payload["sub"] != resource_id or payload["type"] != resource_type:
        raise HTTPException(401, "Invalid link.")

    # Proxy to KB-server using the org's KB API key
    org_id = payload["org"]
    kb_config = get_kb_config_for_org(org_id)

    if resource_type == "chunk":
        chunk = await kb_client.get(f"/chunks/{resource_id}", kb_config)
        content = await kb_client.get(f"/content/{chunk['content_object_id']}", kb_config)
        # Reconstruct chunk text from content using offsets
        chunk_text = content["extracted_text"][chunk["text_start_char"]:chunk["text_end_char"]]
        # Render context (surrounding text)
        context_margin = 500  # chars before and after
        context_start = max(0, chunk["text_start_char"] - context_margin)
        context_end = min(len(content["extracted_text"]), chunk["text_end_char"] + context_margin)
        return render_chunk_page(chunk, chunk_text, content, context_start, context_end, payload)
    elif resource_type == "content":
        content = await kb_client.get(f"/content/{resource_id}", kb_config)
        return render_content_page(content, payload)
```

**Design Parameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Default expiration | 7 days | Long enough for course discussions, short enough for security |
| Scope | Per-resource (chunk or content object) | Granular control |
| Signing secret | LAMB's own key (not KB-server API key) | KB-server never sees or validates JWTs |
| Revocability | Stateless (no revocation) | Simplicity; expiration handles it. Add blocklist later if needed |
| Org boundary | `org_id` in JWT payload; verified on access | Prevents cross-org leakage |
| Audit trail | `uid` in JWT payload | Know who generated each link |

### Integration with RAG Responses

When LAMB's RAG processor retrieves chunks, it generates signed URLs automatically:

```python
# In LAMB's completion pipeline (backend/lamb/completions/rag/)
def augment_with_sources(chunks, response, user_id, org_id):
    sources = []
    for i, chunk in enumerate(chunks):
        signed_url = generate_signed_url(
            "chunk", chunk["id"],
            user_id, org_id, expires_in=timedelta(days=7)
        )
        sources.append(f"[{i+1}] {signed_url}")
    return f"{response}\n\n**Sources:**\n" + "\n".join(sources)
```

### Chunk Context View

When an external user clicks a signed URL, LAMB renders a self-contained HTML page:

```
┌─────────────────────────────────────────────────────────────┐
│ 📄 Source: research_paper.pdf                                │
│ Chunk 3 of 45                                                │
│ Shared by: Dr. Smith · Expires: March 22, 2026              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ [dimmed] ...previous paragraph text...                       │
│                                                              │
│ [highlighted] Machine learning is a subset of artificial     │
│ intelligence that enables systems to learn and improve       │
│ from experience without being explicitly programmed...       │
│                                                              │
│ [dimmed] ...following paragraph text...                       │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ Powered by LAMB · Log in for full access                     │
└─────────────────────────────────────────────────────────────┘
```

The chunk text is reconstructed from `content_objects.extracted_text` using the `text_start_char` / `text_end_char` offsets stored in the `chunks` table. Context (surrounding text) is sliced from the same source with a configurable margin.

### Use Cases for Signed URLs

| Scenario | Who generates | Who receives | Example |
|----------|--------------|-------------|---------|
| RAG citation | LAMB RAG pipeline (automatic) | Student viewing chat | "See source [1]" in assistant response |
| Professor shares source | Professor (on-demand via UI) | Students in LMS forum | Pastes link in Moodle discussion |
| Export to slides | Professor (on-demand via API) | Conference audience | QR code on a presentation slide |
| Email reference | Creator (via "Copy link" button) | External colleague | Link in an email body |

### What the KB-Server Does NOT Do

- Does NOT generate signed URLs (that's LAMB's job)
- Does NOT verify JWTs (LAMB does that before proxying)
- Does NOT serve public/unauthenticated endpoints (bearer-token only)
- Does NOT render HTML pages (LAMB renders the context view)
- Does NOT know about individual users (only org-level API keys)

---

## 9. Shared Content Across Knowledge Bases

### The Sharing Model

```
                      ┌─────────────────────┐
                      │   Content Object    │
                      │   "research.pdf"    │
                      │   co_abc123         │
                      └──────────┬──────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │ KB: Course A │ │ KB: Course B │ │ KB: Research │
           │ (simple)     │ │ (hierarchical)│ │ (simple)     │
           │              │ │              │ │              │
           │ 50 chunks    │ │ 10 parents + │ │ 50 chunks    │
           │ from co_abc  │ │ 40 children  │ │ from co_abc  │
           └──────────────┘ └──────────────┘ └──────────────┘
```

**What's Shared:** Source files, extracted text, metadata, stable resource IDs (for signed URL generation)
**What's Per-KB:** Chunks, embeddings, ingestion strategy, query plugin

### Visibility & Access Control

| Visibility | Who Can Use |
|------------|-------------|
| `private` | Only the owner |
| `organization` | Any user in the organization |

---

## 10. Deletion Semantics & Reference Management

### Layered Deletion Model

Following best practices from Notion (synced blocks), Google Cloud (soft delete), and Confluence (orphan management):

| Level | Action | Who | Impact |
|-------|--------|-----|--------|
| 1 | Remove from MY KB | Any KB owner | Only that KB's chunks deleted; Content Object untouched |
| 2 | Archive Content Object | Content owner | Hidden from "Add to KB" listings; existing KB usages continue |
| 3 | Delete with confirmation | Content owner | Shows impact first; deletes all chunks everywhere |
| 4 | Admin force delete | Org admin | For policy/legal; audit logged |

### Reference Counting

Before hard-deleting a Content Object, the system checks reference count:

```python
async def delete_content_object(content_id, user_id, force=False):
    content = await get_content_object(content_id)
    # Find all KBs using this content via file_registry
    affected_entries = db.query(FileRegistry).filter(
        FileRegistry.content_object_id == content_id
    ).all()
    affected_collection_ids = set(e.collection_id for e in affected_entries)
    # ... impact analysis continues
```

### Background Cleanup

```python
async def cleanup_orphaned_content():
    """Delete content objects with no KB references, archived > 30 days."""
    orphaned = await db.query(ContentObject).filter(
        ContentObject.status == "archived",
        ContentObject.archived_at < datetime.utcnow() - timedelta(days=30),
        ~ContentObject.id.in_(select(FileRegistry.content_object_id))
    ).all()

    for content in orphaned:
        await delete_content_object_permanent(content.id)
```

---

## 11. Database Schema

### New Tables (additions to existing schema)

```sql
-- ═══════════════════════════════════════════════════════════════
-- CONTENT OBJECTS (new — stores imported content before chunking)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE content_objects (
    id TEXT PRIMARY KEY,                    -- "co_" + nanoid
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    owner_id TEXT NOT NULL,

    -- Source information
    source_type TEXT NOT NULL,              -- "file", "url", "youtube"
    original_filename TEXT,
    content_type TEXT,                      -- MIME type
    file_path TEXT,
    file_size INTEGER,
    file_hash TEXT,                         -- SHA256 for deduplication
    source_url TEXT,

    -- Extracted content
    extracted_text TEXT,
    text_format TEXT DEFAULT 'markdown',
    text_hash TEXT,
    extraction_plugin TEXT,
    extraction_params JSON,
    html_preview_path TEXT,

    -- Metadata
    title TEXT,
    metadata JSON,

    -- Status
    status TEXT DEFAULT 'uploaded',         -- uploaded/extracting/ready/archived/failed
    error_message TEXT,
    error_details JSON,

    -- Visibility
    visibility TEXT DEFAULT 'private',      -- private/organization

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME
);

CREATE INDEX idx_content_objects_org ON content_objects(organization_id);
CREATE INDEX idx_content_objects_owner ON content_objects(owner_id);
CREATE INDEX idx_content_objects_hash ON content_objects(organization_id, file_hash);


-- ═══════════════════════════════════════════════════════════════
-- CHUNKS (metadata — actual vectors in backend via KnowledgeStorePlugin)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,                    -- "ch_" / "pc_" / "cc_" + nanoid
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    content_object_id TEXT NOT NULL REFERENCES content_objects(id),

    chunk_type TEXT DEFAULT 'standard',     -- standard/parent/child
    chunk_index INTEGER,
    parent_chunk_id TEXT REFERENCES chunks(id),

    -- Chunk text is NOT duplicated here. It is reconstructed from
    -- content_objects.extracted_text using text_start_char/text_end_char offsets.
    -- The backend (via KnowledgeStorePlugin) stores the actual chunk text
    -- alongside embeddings.
    text_start_char INTEGER,
    text_end_char INTEGER,

    metadata JSON,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_collection ON chunks(collection_id);
CREATE INDEX idx_chunks_content ON chunks(content_object_id);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);


-- ═══════════════════════════════════════════════════════════════
-- MODIFICATIONS TO EXISTING TABLES
-- ═══════════════════════════════════════════════════════════════

-- Add ingestion_strategy to collections (LOCKED at creation)
ALTER TABLE collections ADD COLUMN ingestion_strategy TEXT DEFAULT 'simple_ingest';
ALTER TABLE collections ADD COLUMN ingestion_params JSON;

-- Add content_object_id to file_registry (serves as BOTH ingestion job tracker
-- AND KB-content relationship, replacing the need for a separate kb_content_links table)
ALTER TABLE file_registry ADD COLUMN content_object_id TEXT REFERENCES content_objects(id);
CREATE INDEX idx_file_registry_content ON file_registry(content_object_id);
```

### Existing Tables (Unchanged from #203/#229)

- `organizations` — already exists
- `knowledge_store_setups` — already exists with `plugin_type` + `plugin_config`
- `collections` — already has `knowledge_store_setup_id`, `organization_id`, `embedding_dimensions`
- `file_registry` — enhanced with `content_object_id` FK; serves as both ingestion job tracker and KB-content link (replaces the need for a separate `kb_content_links` table)

---

## 12. API Design

### Content Object Endpoints

```http
# Upload and import a file
POST /content/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: <binary>
import_plugin: "markitdown_import"     # Optional, auto-detected
import_params: {"ocr_enabled": true}   # Optional
visibility: "organization"             # Optional, default "private"

Response 202:
{
  "id": "co_7f3a8b2c",
  "status": "extracting",
  "message": "Content uploaded, extraction in progress"
}


# Import from URL
POST /content/import-url
{
  "url": "https://example.com/article",
  "import_plugin": "url_import",
  "visibility": "organization"
}


# List content objects (for content library)
GET /content?visibility=organization&status=ready&limit=50

# Get content object details
GET /content/{content_id}

# Archive content
POST /content/{content_id}/archive

# Delete content (with impact check)
DELETE /content/{content_id}?force=true
```

### Knowledge Base Endpoints (Modified)

```http
# Create KB with strategy selection
POST /collections
{
  "name": "Course Materials",
  "organization_external_id": "org_123",
  "knowledge_store_setup_key": "chromadb-openai",
  "ingestion_strategy": "hierarchical_ingest",
  "ingestion_params": {
    "parent_chunk_size": 4000,
    "child_chunk_size": 500
  }
}

Response 201:
{
  "id": 42,
  "name": "Course Materials",
  "ingestion_strategy": "hierarchical_ingest",
  "paired_query_plugin": "parent_child_query",
  "message": "Strategy locked. Cannot be changed after creation."
}


# Add content to KB (by content object reference)
POST /collections/{id}/content
{
  "content_object_id": "co_7f3a8b2c",
  "ingestion_params": {}
}

Response 202:
{
  "job_id": 101,
  "status": "queued"
}


# List content in KB
GET /collections/{id}/content

# Remove content from KB (Level 1 deletion)
DELETE /collections/{id}/content/{content_id}

# Query KB (auto-selects query plugin)
POST /collections/{id}/query
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

### KB-Server: Chunk & Content Data Endpoints (Bearer-Token Auth)

```http
# Get chunk metadata (used by LAMB to resolve permalinks)
GET /chunks/{chunk_id}
Authorization: Bearer {kb_api_key}

Response:
{
  "id": "ch_abc123",
  "collection_id": 42,
  "content_object_id": "co_xyz789",
  "chunk_type": "standard",
  "chunk_index": 3,
  "text_start_char": 4200,
  "text_end_char": 5200,
  "metadata": {...}
}


# Get content object with text (used by LAMB for offset resolution)
GET /content/{content_id}
Authorization: Bearer {kb_api_key}

Response:
{
  "id": "co_xyz789",
  "title": "Research Paper",
  "extracted_text": "Full document text...",
  "source": {...},
  "metadata": {...}
}
```

### LAMB: Permalink Endpoints (Signed URL Generation & Resolution)

```http
# Generate signed URL (authenticated LAMB user)
POST /creator/permalinks/generate
Authorization: Bearer {user_token}
{
  "resource_type": "chunk",
  "resource_id": "ch_abc123",
  "expires_in_hours": 168
}

Response:
{
  "url": "https://lamb.example.com/share/chunk/ch_abc123?sig=eyJ...",
  "expires_at": "2026-03-22T14:00:00Z"
}


# Resolve signed URL (NO auth needed — public endpoint)
GET /share/chunk/ch_abc123?sig=eyJ...
→ Returns rendered HTML page with chunk in context

GET /share/content/co_xyz789?sig=eyJ...
→ Returns rendered HTML page with content overview

# If JWT is expired:
→ 410 Gone: "This link has expired."

# If JWT is invalid:
→ 401 Unauthorized: "Invalid link."
```

---

## 13. Migration Strategy

### Phase 1: Schema Evolution (Non-Breaking)

1. Create `content_objects` and `chunks` tables alongside existing ones; add `content_object_id` FK to `file_registry`
2. Add `ingestion_strategy` column to `collections` (default `'simple_ingest'`)
3. Keep `file_registry` working — it continues to serve as the job tracker
4. All existing functionality preserved

### Phase 2: Format Import Plugin Extraction

1. Implement `FormatImportPlugin` base class
2. Extract format-conversion code from existing `IngestPlugin` implementations
3. Support dual paths: old (direct ingest) and new (Content Object → strategy)

### Phase 3: Ingestion Strategy Plugins

1. Implement `IngestionStrategyPlugin` base class
2. Create `simple_ingest` strategy (equivalent to current chunking)
3. Create `hierarchical_ingest` strategy (from existing parent-child plugin)
4. Wire up automatic query plugin selection

### Phase 4: Content Library & Sharing

1. Implement Content Object CRUD endpoints
2. Implement content library UI (browse, add to KB)
3. Implement deletion confirmation with impact analysis

### Phase 5: Permalinks

1. Create permalink resolution endpoints
2. Add chunk-in-context view
3. Integrate permalinks into RAG response augmentation

### Phase 6: Data Migration

```python
async def migrate_kb_to_new_architecture(kb_id: int):
    """Migrate an existing KB to the new architecture."""
    kb = await get_knowledge_base(kb_id)

    for file in await get_files_for_collection(kb.id):
        # Create Content Object from existing file_registry
        content = await create_content_object_from_file_registry(file)
        # Link content to KB via file_registry
        await update_file_registry_content_link(file.id, content.id)
        # Update chunk metadata
        await update_chunks_with_content_id(kb.id, file.id, content.id)

    kb.ingestion_strategy = 'simple_ingest'  # Current behavior
    await kb.save()
```

---

## 14. Trade-offs & Alternatives Considered

### Content Sharing Model

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Full deduplication** (share chunks) | Max storage savings | Can't use different strategies per KB | Rejected |
| **No sharing** (current model) | Simple | File duplication, no content library | Rejected |
| **Hybrid** (share sources, chunk per-KB) | Flexibility + dedup | More complex schema | **Accepted** |

### Chunk Text Storage

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Duplicate text in SQLite `chunks` table | Fast permalink resolution | 2x text storage, data drift risk | Rejected |
| On-demand from backend only | No duplication | Requires backend call, slow | Rejected |
| **Character offsets** into `content_objects.extracted_text` | No duplication, fast resolution (~5ms), enables context window | Requires content object to exist | **Accepted** |

### Permalink Auth & Ownership

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| KB-server generates signed URLs | Single service handles everything | Breaks KB-server's simple auth model; KB-server would need to know about users | Rejected |
| Public KB-server endpoints (no auth) | Simple | Exposes all content without protection | Rejected |
| **LAMB generates signed URLs, KB-server stays bearer-only** | Clean separation; KB-server unchanged; LAMB owns user identity and sharing | Two-hop for external access (LAMB proxies) | **Accepted** |

The two-hop cost is negligible (LAMB and KB-server are co-located) and the architectural clarity is worth it: the KB-server never has to know about individual users, JWTs, or link expiration.

### Strategy Mutability

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Mutable (can change strategy) | Flexibility | Requires re-chunking + re-embedding all content | Rejected |
| Locked at creation | Consistency guaranteed | Must create new KB to try different strategy | **Accepted** |

---

## 15. Open Questions & Recommendations

### Q1: Deletion Notifications — Should users be notified when shared content they use gets deleted?

**Recommendation: Yes, via in-app notification (not email).**

Rationale: In an educational context, a professor removing shared course material could break a colleague's knowledge base without warning. Notion's model (synced block deletion notifies viewers) is the right UX pattern. Implementation: when Level 3 deletion affects other users' KBs, create a notification record visible in the LAMB dashboard. Email is unnecessary overhead for a same-organization action.

### Q2: Default Visibility — Should uploaded content default to `private` or `organization`?

**Recommendation: Default to `private`, with a prominent toggle.**

Rationale: Privacy-first is a core LAMB principle. Users should explicitly opt into sharing. Google Drive defaults to private for the same reason. However, the upload UI should prominently feature a "Share with organization" toggle — not bury it in settings — to encourage content reuse.

### Q3: Strategy Recommendations — Should we auto-suggest strategies based on content type?

**Recommendation: Yes, as non-blocking suggestions.**

Rationale: Most educators won't understand the difference between chunking strategies. Show a recommendation badge: "Structured document detected — hierarchical chunking recommended" for PDFs with clear heading structure, "Short document — simple chunking recommended" for < 5 pages. Never auto-select; always let the user confirm.

Implementation approach: the Format Import Plugin can return a `recommended_strategy` field in its `ImportResult.metadata` based on heuristics (heading density, document length, content type).

### Q4: Chunk Text Storage — How should chunk text be stored for permalink resolution?

**Decision: Use character offsets into `content_objects.extracted_text`.**

Rationale: Rather than duplicating chunk text in the SQLite `chunks` table (which doubles text storage and risks data drift), we store `text_start_char` and `text_end_char` offsets. Permalink resolution reconstructs the chunk text by slicing `content_objects.extracted_text[start:end]`, which is fast (~5ms) and guarantees consistency. This approach also enables context windows — surrounding text can be sliced from the same source with a configurable margin. The backend (via KnowledgeStorePlugin) stores the actual chunk text alongside embeddings for retrieval purposes.

### Q5: Cross-Organization Content — Should content ever be shareable across organizations?

**Recommendation: Not in v2.1. Keep organization as a hard boundary.**

Rationale: Cross-org sharing introduces complex permission models (who can modify? who pays for embeddings?). The organization boundary is a clean security model. If needed in the future, implement it as a "content marketplace" — a separate mechanism where org admins explicitly publish content to a shared catalog.

### Q6: Content Ownership Transfer — Can content ownership be transferred?

**Recommendation: Yes, within the same organization, as an admin action.**

Rationale: When a faculty member leaves, their content should be transferable to a colleague. Implement as an admin-only API endpoint, not a self-service feature. Log the transfer for audit.

### Q7: Archival Period — How long should archived content be kept before permanent deletion?

**Recommendation: 30 days, configurable per organization.**

Rationale: 30 days matches Google Cloud's soft-delete default and is long enough for accidental deletions to be caught. Make it configurable at the organization level for institutions with specific retention policies.

### Q8: Where should signed URL logic live — KB-server or LAMB?

**Decision: LAMB generates and verifies signed URLs. KB-server stays bearer-token only.**

Rationale: The KB-server's auth model is simple by design — if you have the API key, you're trusted. It doesn't know about individual users, sessions, or link expiration. Adding signed URL logic to the KB-server would violate this principle and introduce user-awareness where none is needed.

LAMB already handles all user-facing auth, knows about organizations, roles, and policies. Signed URLs are a user-facing sharing feature — they belong in the user-facing layer. LAMB generates the JWT (signed with its own secret), serves the public `/share/` endpoint, verifies the JWT on access, and proxies to the KB-server using the normal API key. The two-hop latency is negligible since both services are co-located.

This keeps the KB-server focused on knowledge base operations and makes it trivially replaceable or scalable without affecting the sharing system.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Content Object** | Imported source material before chunking (file + extracted text) |
| **Chunk** | A piece of text generated by an ingestion strategy |
| **Parent Chunk** | In hierarchical strategy, a large context chunk |
| **Child Chunk** | In hierarchical strategy, a small searchable chunk |
| **Format Import Plugin** | Converts raw files to Content Objects (Stage 1) |
| **Ingestion Strategy Plugin** | Splits Content Object text into chunks (Stage 2) |
| **Knowledge Store Plugin** | Stores/retrieves chunks in a backend (Stage 3, already implemented) |
| **Query Plugin** | Retrieves chunks using strategy-specific logic |
| **Permalink / Signed URL** | Time-limited JWT-based URL generated by LAMB that grants access to a chunk or content object without requiring login. LAMB verifies the JWT and proxies to KB-server. Expires after a configurable period (default: 7 days) |
| **Content-KB Reference** | Relationship between a KB and a Content Object, tracked via `file_registry.content_object_id` |
| **KnowledgeStoreSetup** | Organization-level config for a retrieval backend |

---

## Appendix B: Implementation Checklist

### Already Done (Issues #203 + #229)
- [x] Organization model and CRUD
- [x] KnowledgeStoreSetup with plugin_type + plugin_config
- [x] KnowledgeStorePlugin interface (11 methods)
- [x] ChromaDB plugin implementation
- [x] resolve_plugin_for_collection() dual-mode helper
- [x] Services fully decoupled from ChromaDB
- [x] Query plugins receive ks_plugin + backend_collection
- [x] Plugin discovery and validation endpoints
- [x] LAMB proxy endpoints for setup management
- [x] Frontend setup management UI
- [x] E2E and Playwright tests passing

### To Do (This Proposal)
- [ ] Create content_objects and chunks tables; add content_object_id FK to file_registry
- [ ] Add ingestion_strategy to collections
- [ ] Implement FormatImportPlugin base class and registry
- [ ] Extract format code from existing ingest plugins
- [ ] Implement IngestionStrategyPlugin base class
- [ ] Create simple_ingest strategy
- [ ] Create hierarchical_ingest strategy
- [ ] Implement automatic query plugin selection
- [ ] Content Object CRUD endpoints
- [ ] Content deduplication by file hash
- [ ] file_registry content_object_id link management
- [ ] KB-server: chunk and content data endpoints (`GET /chunks/{id}`, `GET /content/{id}`)
- [ ] LAMB: signed URL generation endpoint (`POST /creator/permalinks/generate`)
- [ ] LAMB: public share endpoint (`GET /share/{type}/{id}?sig=...`)
- [ ] LAMB: chunk context HTML renderer
- [ ] LAMB: auto-generate signed URLs in RAG response augmentation
- [ ] Content library browse UI
- [ ] Deletion confirmation with impact analysis
- [ ] Migration scripts for existing KBs

---

**Document Version:** 2.1
**Last Updated:** March 15, 2026
**Status:** Proposal for Review
**Prerequisites:** Issues #203 and #229 (completed)
**Next Steps:** Team review, address open questions, prioritize implementation phases
