# LAMB Knowledge Base Server - Architecture Documentation

**Version:** 1.0.0  
**Last Updated:** December 22, 2025  
**Target Audience:** Developers, System Integrators, DevOps Engineers

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Core Components](#3-core-components)
4. [Data Models](#4-data-models)
5. [API Reference](#5-api-reference)
6. [Plugin System](#6-plugin-system)
7. [Embedding Configuration](#7-embedding-configuration)
8. [Ownership & Access Control](#8-ownership--access-control)
9. [File Storage](#9-file-storage)
10. [Integration with LAMB](#10-integration-with-lamb)
11. [Configuration](#11-configuration)
12. [Deployment](#12-deployment)

---

## 1. Overview

### 1.1 Purpose

The **lamb-kb-server** is a dedicated knowledge base server designed to provide:

- **Vector Database Services**: Store and retrieve document embeddings using ChromaDB
- **RAG Support**: Enable Retrieval-Augmented Generation for LAMB Learning Assistants
- **Document Processing**: Ingest various file formats via a plugin architecture
- **MCP Compatibility**: Serve as a Model Context Protocol server (partial implementation)

### 1.2 Key Features

| Feature | Description |
|---------|-------------|
| **Multi-format Ingestion** | PDF, Word, Excel, PowerPoint, HTML, Markdown, JSON, YouTube transcripts |
| **Flexible Embeddings** | Support for OpenAI, Ollama, and local embedding models |
| **Plugin Architecture** | Extensible ingestion and query strategies |
| **Background Processing** | Asynchronous file processing with status tracking |
| **Collection Management** | Full CRUD operations for knowledge bases |
| **Ownership Tracking** | Per-collection and per-file ownership |

### 1.3 Technology Stack

| Component | Technology |
|-----------|------------|
| **Web Framework** | FastAPI (Python 3.11+) |
| **Vector Database** | ChromaDB |
| **Metadata Storage** | SQLite with SQLAlchemy ORM |
| **ASGI Server** | Uvicorn |
| **Text Splitters** | LangChain |
| **Document Conversion** | MarkItDown |

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        lamb-kb-server (Port 9090)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Application                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │   │
│  │  │   System    │  │ Collections │  │  Ingestion  │  │   Query    │   │   │
│  │  │   Router    │  │   Router    │  │  Endpoints  │  │  Endpoints │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                          Service Layer                               │   │
│  │  ┌──────────────────┐  ┌────────┴────────┐  ┌─────────────────────┐  │   │
│  │  │CollectionsService│  │IngestionService │  │    QueryService     │  │   │
│  │  └──────────────────┘  └─────────────────┘  └─────────────────────   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                        Data Access Layer                             │   │
│  │  ┌─────────────────┐  ┌────────┴────────┐                            │   │
│  │  │CollectionService│  │    Connection   │                            │   │
│  │  │   (database/)   │  │   Management    │                            │   │
│  │  └─────────────────┘  └─────────────────┘                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌──────────────────┐     ┌────────┴────────┐    ┌───────────────────┐      │
│  │     SQLite       │     │    ChromaDB     │    │   File System     │      │
│  │   (Metadata)     │◄────┤   (Vectors)     │    │   (Documents)     │      │
│  │ lamb-kb-server.db│     │    chromadb/    │    │     static/       │      │
│  └──────────────────┘     └─────────────────┘    └───────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow

```
Client Request
      │
      ▼
┌─────────────────┐
│  Bearer Token   │──── Invalid ──► 401 Unauthorized
│  Validation     │
└────────┬────────┘
         │ Valid
         ▼
┌─────────────────┐
│     Router      │
│   (FastAPI)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Service Layer  │◄── Business Logic
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│SQLite │ │ChromaDB│
└───────┘ └───────┘
```

### 2.3 Directory Structure

```
backend/
├── main.py                      # Application entry point
├── dependencies.py              # Auth & dependency injection
├── database/
│   ├── __init__.py
│   ├── connection.py            # DB connections & embedding functions
│   ├── models.py                # SQLAlchemy models
│   └── service.py               # Low-level data operations
├── routers/
│   ├── __init__.py
│   ├── system.py                # System endpoints (health, status)
│   └── collections.py           # Collection CRUD & operations
├── services/
│   ├── __init__.py
│   ├── collections.py           # Collection business logic
│   ├── ingestion.py             # Document ingestion logic
│   └── query.py                 # Query processing logic
├── schemas/
│   ├── __init__.py
│   ├── collection.py            # Collection request/response models
│   ├── ingestion.py             # Ingestion request/response models
│   ├── query.py                 # Query request/response models
│   ├── files.py                 # File registry models
│   └── system.py                # System response models
├── plugins/
│   ├── __init__.py
│   ├── base.py                  # Plugin base classes & registry
│   ├── simple_ingest.py         # Text file ingestion
│   ├── markitdown-ingest-plugin.py  # Multi-format ingestion
│   ├── mockai_json_ingest.py    # Pre-chunked JSON ingestion
│   ├── youtube_transcript_ingest.py # YouTube transcript ingestion
│   └── simple_query.py          # Similarity search query
├── static/                      # Uploaded files storage
│   └── {owner}/
│       └── {collection_name}/
│           └── {uuid}.{ext}
└── data/
    ├── lamb-kb-server.db        # SQLite database
    └── chromadb/                # ChromaDB vector storage
```

---

## 3. Core Components

### 3.1 FastAPI Application (`main.py`)

The main entry point initializes:
- Database connections (SQLite + ChromaDB)
- Plugin discovery
- Route mounting
- CORS middleware
- Static file serving

**Key Initialization:**
```python
@app.on_event("startup")
async def startup_event():
    init_databases()           # SQLite + ChromaDB
    discover_plugins("plugins") # Load all plugins
    IngestionService._ensure_dirs() # Create static directories
```

### 3.2 Authentication (`dependencies.py`)

Simple Bearer token authentication:

```python
API_KEY = os.getenv("LAMB_API_KEY", "0p3n-w3bu!")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials
```

**Usage:**
```bash
curl -H "Authorization: Bearer 0p3n-w3bu!" http://localhost:9090/collections
```

### 3.3 Database Connection (`database/connection.py`)

Manages connections to both databases:

| Function | Purpose |
|----------|---------|
| `get_db()` | Yields SQLAlchemy session |
| `get_chroma_client()` | Returns ChromaDB persistent client |
| `get_embedding_function()` | Creates embedding function from collection config |
| `get_embedding_function_by_params()` | Creates embedding function from explicit params |
| `init_databases()` | Initializes both databases |

---

## 4. Data Models

### 4.1 Collection Model

**SQLite Table: `collections`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | VARCHAR(255) | Collection name (indexed) |
| `description` | TEXT | Optional description |
| `creation_date` | DATETIME | Creation timestamp |
| `owner` | VARCHAR(255) | Owner identifier (indexed) |
| `visibility` | ENUM | `private` or `public` |
| `embeddings_model` | JSON | Embedding configuration |
| `chromadb_uuid` | VARCHAR(36) | ChromaDB collection UUID |

**Unique Constraint:** `(name, owner)` - same user cannot have duplicate collection names

**Embeddings Model JSON Structure:**
```json
{
  "vendor": "openai",
  "model": "text-embedding-3-small",
  "api_endpoint": "https://api.openai.com/v1/embeddings",
  "apikey": "sk-..."
}
```

### 4.2 File Registry Model

**SQLite Table: `file_registry`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `collection_id` | INTEGER | Foreign key to collections |
| `original_filename` | VARCHAR(255) | Original file name |
| `file_path` | VARCHAR(255) | Server file path |
| `file_url` | VARCHAR(255) | Public URL to access file |
| `file_size` | INTEGER | File size in bytes |
| `content_type` | VARCHAR(100) | MIME type |
| `plugin_name` | VARCHAR(100) | Ingestion plugin used |
| `plugin_params` | JSON | Plugin parameters used |
| `status` | ENUM | `completed`, `processing`, `failed`, `deleted` |
| `document_count` | INTEGER | Number of chunks created |
| `created_at` | DATETIME | Creation timestamp |
| `updated_at` | DATETIME | Last update timestamp |
| `owner` | VARCHAR(255) | File owner |

### 4.3 Visibility Enum

```python
class Visibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
```

### 4.4 File Status Enum

```python
class FileStatus(str, Enum):
    COMPLETED = "completed"
    PROCESSING = "processing"
    FAILED = "failed"
    DELETED = "deleted"
```

---

## 5. API Reference

### 5.1 System Endpoints

#### Health Check (No Auth Required)
```http
GET /health
```
**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

#### Database Status
```http
GET /database/status
Authorization: Bearer {token}
```
**Response:**
```json
{
  "sqlite_status": {
    "initialized": true,
    "schema_valid": true,
    "errors": []
  },
  "chromadb_status": {
    "initialized": true,
    "collections_count": 5
  },
  "collections_count": 5
}
```

### 5.2 Collection Endpoints

#### Create Collection
```http
POST /collections/
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "my-knowledge-base",
  "description": "My first knowledge base",
  "owner": "user@example.com",
  "visibility": "private",
  "embeddings_model": {
    "model": "text-embedding-3-small",
    "vendor": "openai",
    "api_endpoint": "https://api.openai.com/v1/embeddings",
    "apikey": "sk-your-key-here"
  }
}
```

**Using Defaults:**
```json
{
  "name": "my-kb",
  "owner": "user@example.com",
  "embeddings_model": {
    "model": "default",
    "vendor": "default",
    "api_endpoint": "default",
    "apikey": "default"
  }
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "my-knowledge-base",
  "description": "My first knowledge base",
  "owner": "user@example.com",
  "visibility": "private",
  "creation_date": "2025-12-22T10:30:00",
  "embeddings_model": {
    "model": "text-embedding-3-small",
    "vendor": "openai",
    "api_endpoint": "https://api.openai.com/v1/embeddings",
    "apikey": "sk-..."
  }
}
```

#### List Collections
```http
GET /collections/?owner={owner}&visibility={visibility}&skip={skip}&limit={limit}
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `owner` | string | - | Filter by owner |
| `visibility` | string | - | Filter by visibility (`private`/`public`) |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Max results (1-1000) |

**Response:**
```json
{
  "total": 25,
  "items": [
    {
      "id": 1,
      "name": "my-kb",
      "description": "...",
      "owner": "user@example.com",
      "visibility": "private",
      "creation_date": "2025-12-22T10:30:00",
      "embeddings_model": {...}
    }
  ]
}
```

#### Get Collection
```http
GET /collections/{collection_id}
Authorization: Bearer {token}
```

#### Delete Collection
```http
DELETE /collections/{collection_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": 1,
  "name": "my-kb",
  "deleted_embeddings": 150,
  "chroma_collection": "my-kb",
  "removed_files": ["/path/to/file1.pdf", "/path/to/file2.txt"],
  "status": "deleted"
}
```

### 5.3 Ingestion Endpoints

#### List Ingestion Plugins
```http
GET /ingestion/plugins
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "name": "simple_ingest",
    "kind": "file-ingest",
    "description": "Ingest text files with configurable chunking options",
    "supported_file_types": ["*.txt", "*.md"],
    "parameters": {
      "chunk_size": {"type": "integer", "default": 1000},
      "chunk_overlap": {"type": "integer", "default": 200},
      "splitter_type": {"type": "string", "default": "RecursiveCharacterTextSplitter"}
    }
  }
]
```

#### Ingest File (Combined Upload + Process)
```http
POST /collections/{collection_id}/ingest-file
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | File to upload |
| `plugin_name` | string | Yes | Ingestion plugin name |
| `plugin_params` | JSON string | No | Plugin parameters |

**Example:**
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_ingest' \
  -F 'plugin_params={"chunk_size": 1000, "chunk_overlap": 200}'
```

**Response:**
```json
{
  "collection_id": 1,
  "collection_name": "my-kb",
  "documents_added": 0,
  "success": true,
  "file_path": "/path/to/file.pdf",
  "file_url": "http://localhost:9090/static/owner/collection/uuid.pdf",
  "original_filename": "document.pdf",
  "plugin_name": "markitdown_ingest",
  "file_registry_id": 5,
  "status": "processing"
}
```

#### Ingest URL
```http
POST /collections/{collection_id}/ingest-url
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "urls": ["https://example.com/page1", "https://example.com/page2"],
  "plugin_name": "url_ingest",
  "plugin_params": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```

#### Ingest Base (No File Upload)
```http
POST /collections/{collection_id}/ingest-base
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body (YouTube Example):**
```json
{
  "plugin_name": "youtube_transcript_ingest",
  "plugin_params": {
    "video_url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
    "language": "en",
    "chunk_duration": 60
  }
}
```

#### Add Documents Directly
```http
POST /collections/{collection_id}/documents
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "documents": [
    {
      "text": "Document content here...",
      "metadata": {
        "source": "manual",
        "chunk_index": 0
      }
    }
  ]
}
```

### 5.4 Query Endpoints

#### Query Collection
```http
POST /collections/{collection_id}/query?plugin_name=simple_query
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "query_text": "What is machine learning?",
  "top_k": 5,
  "threshold": 0.5,
  "plugin_params": {}
}
```

**Response:**
```json
{
  "results": [
    {
      "similarity": 0.89,
      "data": "Machine learning is a subset of artificial intelligence...",
      "metadata": {
        "source": "/path/to/file.pdf",
        "filename": "intro.pdf",
        "chunk_index": 3,
        "chunk_count": 25,
        "embedding_vendor": "openai",
        "embedding_model": "text-embedding-3-small"
      }
    }
  ],
  "count": 5,
  "timing": {
    "total_seconds": 0.234,
    "total_ms": 234
  },
  "query": "What is machine learning?",
  "embedding_info": {
    "vendor": "openai",
    "model": "text-embedding-3-small"
  }
}
```

### 5.5 File Management Endpoints

#### List Files in Collection
```http
GET /collections/{collection_id}/files?status={status}
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (`completed`, `processing`, `failed`, `deleted`) |

#### Delete File
```http
DELETE /collections/{collection_id}/files/{file_id}?hard=true
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hard` | bool | true | `true` = delete DB row, `false` = mark as deleted |

**Response:**
```json
{
  "file_id": 5,
  "collection_id": 1,
  "deleted_embeddings": 15,
  "removed_files": ["/path/to/file.pdf", "/path/to/file.html"],
  "status": "deleted"
}
```

#### Update File Status
```http
PUT /collections/files/{file_id}/status?status={new_status}
Authorization: Bearer {token}
```

#### Get File Content
```http
GET /files/{file_id}/content
Authorization: Bearer {token}
```

**Response:**
```json
{
  "file_id": 5,
  "original_filename": "document.pdf",
  "content": "Reconstructed content from all chunks...",
  "content_type": "markdown",
  "chunk_count": 15,
  "timestamp": "2025-12-22T10:30:00"
}
```

---

## 6. Plugin System

### 6.1 Plugin Architecture

The plugin system provides extensible ingestion and query capabilities.

```
plugins/
├── base.py              # Base classes & registry
├── simple_ingest.py     # IngestPlugin implementation
├── simple_query.py      # QueryPlugin implementation
└── ...
```

**Plugin Base Classes:**

```python
class IngestPlugin(abc.ABC):
    name: str = "base"
    kind: str = "base"
    description: str = "Base plugin interface"
    supported_file_types: Set[str] = set()
    
    @abc.abstractmethod
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        pass
    
    @abc.abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        pass

class QueryPlugin(abc.ABC):
    name: str = "base_query"
    description: str = "Base query plugin interface"
    
    @abc.abstractmethod
    def query(self, collection_id: int, query_text: str, **kwargs) -> List[Dict[str, Any]]:
        pass
    
    @abc.abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        pass
```

### 6.2 Plugin Registration

Plugins are auto-registered using decorators:

```python
@PluginRegistry.register
class MyPlugin(IngestPlugin):
    name = "my_plugin"
    ...
```

**Environment Toggle:**
```bash
# Disable a plugin
export PLUGIN_MY_PLUGIN=DISABLE
```

### 6.3 Available Ingestion Plugins

#### 6.3.1 simple_ingest

**Purpose:** Ingest plain text and markdown files with configurable chunking.

| Property | Value |
|----------|-------|
| **Name** | `simple_ingest` |
| **Kind** | `file-ingest` |
| **Supported Types** | `*.txt`, `*.md` |

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | integer | 1000 | Size of each chunk |
| `chunk_overlap` | integer | 200 | Overlap between chunks |
| `splitter_type` | string | `RecursiveCharacterTextSplitter` | LangChain splitter type |

**Splitter Types:**
- `RecursiveCharacterTextSplitter` - Smart recursive splitting (recommended)
- `CharacterTextSplitter` - Simple character-based splitting
- `TokenTextSplitter` - Token-based splitting

**Example:**
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@readme.md' \
  -F 'plugin_name=simple_ingest' \
  -F 'plugin_params={"chunk_size": 500, "splitter_type": "RecursiveCharacterTextSplitter"}'
```

**Output Artifacts:**
- Saves chunks to `{file_path}.json`

---

#### 6.3.2 markitdown_ingest

**Purpose:** Convert various file formats to Markdown, then chunk for embedding.

| Property | Value |
|----------|-------|
| **Name** | `markitdown_ingest` |
| **Kind** | `file-ingest` |
| **Supported Types** | `pdf`, `pptx`, `docx`, `xlsx`, `xls`, `mp3`, `wav`, `html`, `csv`, `json`, `xml`, `zip`, `epub` |

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | integer | 1000 | Size of each chunk |
| `chunk_overlap` | integer | 200 | Overlap between chunks |
| `splitter_type` | string | `RecursiveCharacterTextSplitter` | LangChain splitter type |
| `description` | string | - | Optional description metadata |
| `citation` | string | - | Optional citation metadata |

**Features:**
- Uses Microsoft's MarkItDown library for document conversion
- Generates HTML preview files with professional CSS styling
- Preserves document structure in Markdown format

**Example:**
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@report.pdf' \
  -F 'plugin_name=markitdown_ingest' \
  -F 'plugin_params={"chunk_size": 800, "description": "Annual Report 2024"}'
```

**Output Artifacts:**
- Converts file to `{file_path}.html` (styled HTML preview)
- Saves chunks to `{file_path}.json`

---

#### 6.3.3 youtube_transcript_ingest

**Purpose:** Ingest YouTube video transcripts with time-based chunking.

| Property | Value |
|----------|-------|
| **Name** | `youtube_transcript_ingest` |
| **Kind** | `remote-ingest` |
| **Supported Types** | `txt` (URL list file) |

**Parameters:**

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `video_url` | string | - | No* | YouTube video URL |
| `language` | string | `en` | No | Preferred subtitle language (ISO 639-1) |
| `chunk_duration` | number | 60 | No | Target chunk duration in seconds |
| `proxy_url` | string | - | No | Proxy URL for API calls |

*Either `video_url` or upload a text file with URLs (one per line)

**Features:**
- Uses yt-dlp for robust subtitle extraction
- Supports both manual and auto-generated captions
- Time-based chunking preserves temporal context
- Includes timestamp metadata for source navigation

**Example (Single Video):**
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-base' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "plugin_name": "youtube_transcript_ingest",
    "plugin_params": {
      "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "language": "en",
      "chunk_duration": 90
    }
  }'
```

**Example (Multiple Videos via File):**
```bash
# Create urls.txt with:
# https://www.youtube.com/watch?v=video1
# https://www.youtube.com/watch?v=video2

curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@urls.txt' \
  -F 'plugin_name=youtube_transcript_ingest' \
  -F 'plugin_params={"chunk_duration": 60}'
```

**Chunk Metadata:**
```json
{
  "source_url": "https://youtube.com/watch?v=xxx&t=120",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "start_time": 120.5,
  "end_time": 180.3,
  "start_timestamp": "00:02:00,500",
  "end_timestamp": "00:03:00,300",
  "chunk_duration_target": 60,
  "original_text_sample": "First 200 chars of raw text..."
}
```

---

#### 6.3.4 mockai_json_ingest

**Purpose:** Ingest pre-chunked JSON data with full metadata preservation.

| Property | Value |
|----------|-------|
| **Name** | `mockai_json_ingest` |
| **Kind** | `file-ingest` |
| **Supported Types** | `json`, `zip` |

**Parameters:** None (data is pre-chunked)

**Expected JSON Format:**
```json
[
  {
    "text": "The main content to be embedded",
    "title": "Document Title",
    "category": "science",
    "author": "John Doe",
    "any_other_field": "Becomes metadata"
  }
]
```

**Features:**
- Each JSON object = one chunk (no additional splitting)
- All fields except `text` become metadata
- Supports ZIP archives containing multiple JSON files
- Handles complex nested objects by flattening

**Example:**
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@data.json' \
  -F 'plugin_name=mockai_json_ingest'
```

---

### 6.4 Available Query Plugins

#### 6.4.1 simple_query

**Purpose:** Perform similarity search on collection embeddings.

| Property | Value |
|----------|-------|
| **Name** | `simple_query` |

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_k` | integer | 5 | Number of results to return |
| `threshold` | number | 0.0 | Minimum similarity threshold (0-1) |

**Features:**
- Uses ChromaDB's native similarity search
- Converts distance to similarity score (1 - distance)
- Applies threshold filtering after retrieval
- Uses same embedding function as ingestion

**Example:**
```bash
curl -X POST 'http://localhost:9090/collections/1/query?plugin_name=simple_query' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "query_text": "Explain neural networks",
    "top_k": 10,
    "threshold": 0.7
  }'
```

### 6.5 Creating Custom Plugins

**Step 1:** Create plugin file in `plugins/` directory

```python
# plugins/my_custom_ingest.py
from typing import Dict, List, Any
from .base import IngestPlugin, PluginRegistry

@PluginRegistry.register
class MyCustomPlugin(IngestPlugin):
    name = "my_custom_ingest"
    kind = "file-ingest"
    description = "My custom ingestion plugin"
    supported_file_types = {"csv", "tsv"}
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "delimiter": {
                "type": "string",
                "default": ",",
                "description": "Field delimiter"
            }
        }
    
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        delimiter = kwargs.get("delimiter", ",")
        # Process file and return chunks
        return [
            {
                "text": "chunk content",
                "metadata": {
                    "source": file_path,
                    "chunk_index": 0,
                    "chunk_count": 1
                }
            }
        ]
```

**Step 2:** Plugin is auto-discovered on server startup

**Step 3:** Verify registration
```bash
curl http://localhost:9090/ingestion/plugins -H 'Authorization: Bearer 0p3n-w3bu!'
```

---

## 7. Embedding Configuration

### 7.1 Supported Providers

| Vendor | Model Examples | Requires API Key |
|--------|----------------|------------------|
| `openai` | `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002` | Yes |
| `ollama` | `nomic-embed-text`, `all-minilm`, `mxbai-embed-large` | No |
| `local` | Same as ollama | No |

### 7.2 Configuration at Collection Creation

**Full Configuration:**
```json
{
  "embeddings_model": {
    "vendor": "openai",
    "model": "text-embedding-3-small",
    "api_endpoint": "https://api.openai.com/v1/embeddings",
    "apikey": "sk-your-api-key"
  }
}
```

**Using Defaults:**
```json
{
  "embeddings_model": {
    "vendor": "default",
    "model": "default",
    "api_endpoint": "default",
    "apikey": "default"
  }
}
```

### 7.3 Environment Variables for Defaults

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDINGS_VENDOR` | Default embedding vendor | `ollama` |
| `EMBEDDINGS_MODEL` | Default model name | `nomic-embed-text` |
| `EMBEDDINGS_ENDPOINT` | Default API endpoint | `http://localhost:11434/api/embeddings` |
| `EMBEDDINGS_APIKEY` | Default API key | `""` |

### 7.4 Embedding Consistency

**Critical Design Decision:** The embedding model CANNOT be changed after collection creation.

This ensures:
- Consistent vector dimensions across all documents
- Valid similarity comparisons
- No dimension mismatch errors

**If you need different embeddings:**
1. Create a new collection with desired configuration
2. Re-ingest all documents

### 7.5 Embedding Flow

```
Collection Creation:
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ API Request     │────►│ Resolve Defaults│────►│ Validate Config │
│ embeddings_model│     │ from env vars   │     │ (test embedding)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ Store in SQLite │
                                               │ embeddings_model│
                                               └─────────────────┘

Document Ingestion/Query:
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Get Collection  │────►│ Load embeddings │────►│ Create Embedding│
│ from SQLite     │     │ config from JSON│     │ Function        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ Use for Ingest/ │
                                               │ Query Operations│
                                               └─────────────────┘
```

---

## 8. Ownership & Access Control

### 8.1 Ownership Model

**Owner is a string identifier** (typically email address):
- Set at collection creation
- Set at file upload
- Used for filtering and organization

**Storage Locations:**
- `Collection.owner` - Collection owner
- `FileRegistry.owner` - File owner (may differ from collection)

### 8.2 Ownership-Based Directory Structure

```
static/
├── user1@example.com/
│   ├── project-docs/
│   │   ├── abc123.pdf
│   │   └── def456.md
│   └── research-papers/
│       └── ghi789.pdf
└── user2@example.com/
    └── my-kb/
        └── jkl012.txt
```

### 8.3 Filtering by Owner

```http
GET /collections/?owner=user@example.com
```

### 8.4 ⚠️ Access Control Limitations

**Current Implementation:**
- Single shared API key for all users
- No per-user authentication
- No permission checks on collection access

**Security Model:**
```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│   Client     │────►│ LAMB Backend  │────►│ lamb-kb-server   │
│              │     │ (Auth/AuthZ)  │     │ (Trusted)        │
└──────────────┘     └───────────────┘     └──────────────────┘
```

**Assumption:** lamb-kb-server is accessed through LAMB backend, which handles:
- User authentication
- Permission validation
- Owner filtering

---

## 9. File Storage

### 9.1 Storage Structure

Files are stored in a hierarchical structure:

```
backend/static/{owner}/{collection_name}/{uuid}.{extension}
```

**Example:**
```
backend/static/user@example.com/research-papers/a1b2c3d4e5f6.pdf
```

### 9.2 File Naming

Files are renamed with UUID to prevent:
- Filename collisions
- Path traversal vulnerabilities
- Unicode/special character issues

**Original filename preserved in:**
- `FileRegistry.original_filename`
- Document metadata (`source`, `filename`)

### 9.3 File URL Access

Files are served via FastAPI's static file mounting:

```
http://localhost:9090/static/{owner}/{collection_name}/{uuid}.{extension}
```

**Configuration:**
```python
STATIC_URL_PREFIX = os.getenv("HOME_URL", "http://localhost:9090") + "/static"
```

### 9.4 Derived Files

Some plugins generate additional files:

| Plugin | Original | Generated |
|--------|----------|-----------|
| `markitdown_ingest` | `abc.pdf` | `abc.html` (styled preview) |
| `simple_ingest` | `abc.md` | `abc.md.json` (chunks) |

---

## 10. Integration with LAMB

### 10.1 Architecture Integration

```
┌────────────────────────────────────────────────────────────────┐
│                        LAMB Platform                            │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                    ┌──────────────┐          │
│  │   Frontend   │                    │  Open WebUI  │          │
│  │   (Svelte)   │                    │   (Chat UI)  │          │
│  └──────┬───────┘                    └──────────────┘          │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │   Creator    │────────►│ lamb-kb-server│                    │
│  │  Interface   │         │   :9090      │                     │
│  │   /creator   │         │              │                     │
│  └──────────────┘         └──────────────┘                     │
│         │                        ▲                              │
│         ▼                        │                              │
│  ┌──────────────┐                │                              │
│  │ LAMB Core API│                │ RAG Queries                 │
│  │  Completions │────────────────┘                              │
│  └──────────────┘                                               │
└────────────────────────────────────────────────────────────────┘
```

### 10.2 Configuration in LAMB

**Organization Config:**
```json
{
  "kb_server": {
    "url": "http://localhost:9090",
    "api_key": "0p3n-w3bu!"
  }
}
```

**Environment Variables:**
```bash
LAMB_KB_SERVER=http://localhost:9090
LAMB_KB_SERVER_TOKEN=0p3n-w3bu!
```

### 10.3 Collection Naming Convention

For LAMB integration, collections are named:
```
{org_slug}_{user_email}_{collection_name}
```

This ensures:
- Organization isolation
- User ownership tracking
- Unique names across the system

### 10.4 RAG Flow in Completions

```
1. User sends message to assistant (with KB configured)
2. LAMB extracts KB collection IDs from assistant.metadata.rag_config
3. LAMB queries lamb-kb-server for each collection
4. Retrieved chunks are injected into system prompt
5. LLM generates response with augmented context
```

---

## 11. Configuration

### 11.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LAMB_API_KEY` | Authentication token | `0p3n-w3bu!` |
| `HOME_URL` | Base URL for file URLs | `http://localhost:9090` |
| `EMBEDDINGS_VENDOR` | Default embedding vendor | `ollama` |
| `EMBEDDINGS_MODEL` | Default embedding model | `nomic-embed-text` |
| `EMBEDDINGS_ENDPOINT` | Default embedding endpoint | `http://localhost:11434/api/embeddings` |
| `EMBEDDINGS_APIKEY` | Default embedding API key | `""` |
| `PLUGIN_{NAME}` | Enable/disable plugin | `ENABLE` |

### 11.2 Database Paths

Configured in `database/connection.py`:

```python
DATA_DIR = Path("backend/data")
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"
CHROMA_DB_PATH = DATA_DIR / "chromadb"
```

### 11.3 ChromaDB Settings

```python
chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH),
    settings=ChromaSettings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)
```

---

## 12. Deployment

### 12.1 Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 9090
```

### 12.2 Production

```bash
uvicorn main:app --host 0.0.0.0 --port 9090 --workers 4
```

### 12.3 Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 9090
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9090"]
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  kb-server:
    build:
      context: .
      dockerfile: Dockerfile.server
    ports:
      - "9090:9090"
    environment:
      - LAMB_API_KEY=your-secure-key
      - EMBEDDINGS_VENDOR=openai
      - EMBEDDINGS_MODEL=text-embedding-3-small
      - EMBEDDINGS_APIKEY=sk-your-key
    volumes:
      - ./data:/app/data
      - ./static:/app/static
```

### 12.4 Health Monitoring

```bash
# Health check (no auth required)
curl http://localhost:9090/health

# Database status
curl -H "Authorization: Bearer $API_KEY" http://localhost:9090/database/status
```

---

## Appendix A: Error Codes

| Status | Code | Description |
|--------|------|-------------|
| 200 | OK | Successful operation |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Invalid or missing token |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 422 | Validation Error | Request validation failed |
| 500 | Internal Error | Server-side error |

---

## Appendix B: Quick Reference

### Create Collection with OpenAI
```bash
curl -X POST 'http://localhost:9090/collections/' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my-kb",
    "owner": "user@example.com",
    "embeddings_model": {
      "vendor": "openai",
      "model": "text-embedding-3-small",
      "apikey": "sk-..."
    }
  }'
```

### Ingest PDF
```bash
curl -X POST 'http://localhost:9090/collections/1/ingest-file' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -F 'file=@document.pdf' \
  -F 'plugin_name=markitdown_ingest' \
  -F 'plugin_params={"chunk_size": 1000}'
```

### Query Collection
```bash
curl -X POST 'http://localhost:9090/collections/1/query' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{"query_text": "search query", "top_k": 5}'
```

---

**Document Version:** 1.0.0  
**Last Updated:** December 22, 2025  
**Maintainers:** LAMB Development Team

