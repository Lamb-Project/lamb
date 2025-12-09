# Multi-Tool Assistant System: Backend Specification

**Version:** 1.2  
**Date:** December 9, 2025  
**Updated:** December 9, 2025 - Migrate-on-access strategy  
**Related Documents:**  
- `Documentation/MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md` (Frontend specification)
- `Documentation/TOOL_ASSISTANTS_ANALYSIS_REPORT.md` (Tool Assistants design)
- `Documentation/lamb_architecture.md` (System architecture)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Backend Architecture](#2-current-backend-architecture)
3. [Proposed Changes Overview](#3-proposed-changes-overview)
4. [Directory Structure Changes](#4-directory-structure-changes)
5. [Tool Plugin Architecture](#5-tool-plugin-architecture)
6. [Data Model Changes](#6-data-model-changes)
7. [Completion Pipeline Refactoring](#7-completion-pipeline-refactoring)
8. [Tool Registry System](#8-tool-registry-system)
9. [API Changes](#9-api-changes)
10. [Migration Strategy](#10-migration-strategy)
11. [Implementation Tasks](#11-implementation-tasks)
12. [Testing Strategy](#12-testing-strategy)

---

## 1. Executive Summary

This document specifies the backend changes required to support a **multi-tool assistant system** where:

1. An assistant can use **multiple tools simultaneously** in a single pipeline execution
2. Each tool outputs to a **specific placeholder** (`{context}`, `{rubric}`, `{file}`, etc.)
3. Tools are **plugins** with a standardized interface receiving the full request
4. Tool configurations are **encoded in the assistant metadata** as JSON
5. The current `lamb/completions/rag/` directory is **renamed to `lamb/completions/tools/`**

### Key Design Principles

- **Backward Compatibility:** Existing assistants with `rag_processor` continue to work
- **Plugin-Based Architecture:** Tools are dynamically loaded plugins with a common interface
- **Full Request Access:** Each tool receives the complete request object for flexibility
- **Parallel-Ready:** Architecture supports future parallel tool execution
- **Dynamic Placeholders:** Each tool defines its own placeholder name; the prompt processor receives all `{placeholder: content}` pairs dynamically and performs substitution without hardcoded knowledge of specific placeholders

---

## 2. Current Backend Architecture

### 2.1 Directory Structure (Current)

```

**Verbose flag:** `verbose: true` enables pipeline tracing (redacted) including tool inputs (sans secrets), output lengths, and prompt-after-substitution. Default `false`; traces must exclude API keys, tokens, PII, and tool contents.
lamb/completions/
├── main.py                    # Main completion router & pipeline orchestrator
├── org_config_resolver.py     # Organization-aware configuration
├── connectors/                # LLM provider connectors
│   ├── openai.py
│   ├── ollama.py
│   ├── bypass.py
│   └── banana_img.py
├── pps/                       # Prompt Processors
│   └── simple_augment.py
└── rag/                       # RAG processors (to be renamed → tools)
    ├── no_rag.py
    ├── simple_rag.py
    ├── rubric_rag.py
    └── single_file_rag.py
```

### 2.2 Current Completion Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CURRENT PIPELINE (SEQUENTIAL)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Request → get_assistant_details() → parse_plugin_config()              │
│                                              │                           │
│                                              ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │ SINGLE RAG Call │                  │
│                                    │ rag_processor() │                  │
│                                    └────────┬────────┘                  │
│                                              │                           │
│                                              ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │ Prompt Processor│                  │
│                                    │ Replaces only   │                  │
│                                    │ {context}       │                  │
│                                    └────────┬────────┘                  │
│                                              │                           │
│                                              ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │   Connector     │                  │
│                                    │   (LLM call)    │                  │
│                                    └─────────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Current RAG Processor Interface

```python
# Current interface (lamb/completions/rag/simple_rag.py)
def rag_processor(
    messages: List[Dict[str, Any]], 
    assistant: Assistant = None
) -> Dict[str, Any]:
    """
    Returns:
        {
            "context": str,    # Content for {context} placeholder
            "sources": list    # Source citations
        }
    """
```

**Problems with Current Design:**
1. Only one RAG processor can run per request
2. Limited parameter access (only messages and assistant)
3. All processors output to the same `{context}` placeholder
4. No way to combine multiple context sources

### 2.4 Current Assistant Metadata Structure

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "rag_processor": "simple_rag",
    "file_path": "/path/to/file",
    "rubric_id": 123,
    "capabilities": {
        "vision": false,
        "image_generation": false
    }
}
```

---

## 3. Proposed Changes Overview

### 3.1 Key Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| Directory | `lamb/completions/rag/` | `lamb/completions/tools/` |
| Config Key | `rag_processor` (single) | `tools` (array) |
| Interface | `rag_processor(messages, assistant)` | `tool_processor(request, assistant, tool_config)` |
| Output | Single `{context}` | Multiple: `{context}`, `{rubric}`, `{file}`, etc. |
| Execution | Sequential single | Sequential multi (future: parallel) |

### 3.2 New Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED PIPELINE (MULTI-TOOL)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Request → get_assistant_details() → parse_plugin_config()              │
│                                              │                           │
│                                              ▼                           │
│                               ┌──────────────────────────┐              │
│                               │   Tool Orchestrator      │              │
│                               │   load_enabled_tools()   │              │
│                               └───────────┬──────────────┘              │
│                                           │                              │
│            ┌──────────────────────────────┼──────────────────────────┐  │
│            │                              │                          │  │
│            ▼                              ▼                          ▼  │
│   ┌─────────────────┐          ┌─────────────────┐        ┌──────────────┐
│   │ simple_rag      │          │ rubric_rag      │        │ single_file  │
│   │ → {context}     │          │ → {rubric}      │        │ → {file}     │
│   └────────┬────────┘          └────────┬────────┘        └──────┬───────┘
│            │                            │                        │       │
│            └──────────────────────────┬─┴────────────────────────┘       │
│                                       │                                  │
│                                       ▼                                  │
│                            ┌─────────────────────┐                      │
│                            │   Merge Results     │                      │
│                            │   tool_contexts = { │                      │
│                            │     "context": ..., │                      │
│                            │     "rubric": ...,  │                      │
│                            │     "file": ...     │                      │
│                            │   }                 │                      │
│                            └──────────┬──────────┘                      │
│                                       │                                  │
│                                       ▼                                  │
│                            ┌─────────────────────┐                      │
│                            │  Prompt Processor   │                      │
│                            │  Replace ALL        │                      │
│                            │  placeholders       │                      │
│                            └──────────┬──────────┘                      │
│                                       │                                  │
│                                       ▼                                  │
│                            ┌─────────────────────┐                      │
│                            │     Connector       │                      │
│                            │     (LLM call)      │                      │
│                            └─────────────────────┘                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Directory Structure Changes

### 4.1 Proposed Structure

```
lamb/completions/
├── main.py                        # Modified: multi-tool pipeline
├── org_config_resolver.py         # Unchanged
├── tool_orchestrator.py           # NEW: Tool execution coordinator
├── tool_registry.py               # NEW: Tool discovery and metadata
├── connectors/                    # Unchanged
│   ├── openai.py
│   ├── ollama.py
│   ├── bypass.py
│   └── banana_img.py
├── pps/                           # Modified: multi-placeholder support
│   └── simple_augment.py
└── tools/                         # RENAMED from rag/
    ├── __init__.py
    ├── base.py                    # NEW: Base tool interface
    ├── no_tool.py                 # Renamed from no_rag.py
    ├── simple_rag.py              # Modified interface
    ├── rubric.py                  # Renamed from rubric_rag.py
    ├── single_file.py             # Renamed from single_file_rag.py
    └── README.md                  # Tool development guide
```

### 4.2 Migration File Mapping

| Old Path | New Path | Changes |
|----------|----------|---------|
| `rag/__init__.py` | `tools/__init__.py` | Same |
| `rag/no_rag.py` | `tools/no_tool.py` | Renamed + new interface |
| `rag/simple_rag.py` | `tools/simple_rag.py` | New interface |
| `rag/rubric_rag.py` | `tools/rubric.py` | Renamed + new interface + new placeholder |
| `rag/single_file_rag.py` | `tools/single_file.py` | Renamed + new interface + new placeholder |
| N/A | `tools/base.py` | New file |
| N/A | `tool_orchestrator.py` | New file |
| N/A | `tool_registry.py` | New file |

---

## 5. Tool Plugin Architecture

### 5.1 Base Tool Interface

```python
# lamb/completions/tools/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from lamb.lamb_classes import Assistant

@dataclass
class ToolResult:
    """Standard result from tool execution"""
    placeholder: str                      # Placeholder name this tool outputs to (e.g., "context")
    content: str                          # Content for the placeholder
    sources: List[Dict[str, Any]]        # Source citations
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
    error: Optional[str] = None           # Error message if failed

@dataclass 
class ToolDefinition:
    """Tool metadata for registry and UI"""
    name: str                             # Unique identifier
    display_name: str                     # Human-readable name
    description: str                      # Description for UI
    placeholder: str                      # Template placeholder (e.g., "context")
    config_schema: Dict[str, Any]         # JSON Schema for tool config
    version: str = "1.0"
    category: str = "rag"                 # Category: rag, rubric, file, custom

class BaseTool(ABC):
    """Abstract base class for all tools"""
    
    @classmethod
    @abstractmethod
    def get_definition(cls) -> ToolDefinition:
        """Return tool metadata and configuration schema"""
        pass
    
    @abstractmethod
    def process(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_config: Dict[str, Any]
    ) -> ToolResult:
        """
        Execute the tool and return results.
        
        Args:
            request: Full completion request (messages, stream, etc.)
            assistant: Assistant object with metadata
            tool_config: Tool-specific configuration from assistant.metadata.tools
            
        Returns:
            ToolResult with content for the placeholder
        """
        pass
    
    def validate_config(self, tool_config: Dict[str, Any]) -> List[str]:
        """
        Validate tool configuration against schema.
        
        Returns:
            List of validation errors (empty if valid)
        """
        return []
```

### 5.2 Tool Implementation Example: Simple RAG

```python
# lamb/completions/tools/simple_rag.py

from typing import Dict, Any, List
from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver
import requests
import json
import logging

logger = logging.getLogger(__name__)

class SimpleRagTool(BaseTool):
    """RAG tool that queries knowledge base collections"""
    
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="simple_rag",
            display_name="Knowledge Base RAG",
            description="Retrieves relevant context from knowledge base collections",
            placeholder="context",  # Outputs to {context}
            category="rag",
            config_schema={
                "type": "object",
                "properties": {
                    "collections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of collection IDs to query"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of results to retrieve"
                    },
                    "threshold": {
                        "type": "number",
                        "default": 0.0,
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Similarity threshold"
                    }
                },
                "required": ["collections"]
            }
        )
    
    def process(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_config: Dict[str, Any]
    ) -> ToolResult:
        """Execute RAG query against knowledge base"""
        
        # Extract configuration
        collections = tool_config.get("collections", [])
        top_k = tool_config.get("top_k", 3)
        threshold = tool_config.get("threshold", 0.0)
        
        # Validate
        if not collections:
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error="No collections configured"
            )
        
        # Get last user message for query
        messages = request.get("messages", [])
        query = self._extract_query(messages)
        
        if not query:
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error="No user message found for query"
            )
        
        # Get KB configuration for organization
        try:
            config_resolver = OrganizationConfigResolver(assistant.owner)
            kb_config = config_resolver.get_knowledge_base_config()
            kb_url = kb_config.get("server_url")
            kb_token = kb_config.get("api_token")
        except Exception as e:
            logger.error(f"Failed to get KB config: {e}")
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error=f"KB configuration error: {e}"
            )
        
        # Query collections
        all_contexts = []
        all_sources = []
        
        for collection_id in collections:
            try:
                result = self._query_collection(
                    kb_url, kb_token, collection_id, query, top_k, threshold
                )
                all_contexts.extend(result.get("contexts", []))
                all_sources.extend(result.get("sources", []))
            except Exception as e:
                logger.error(f"Error querying collection {collection_id}: {e}")
        
        return ToolResult(
            placeholder=self.get_definition().placeholder,  # "context"
            content="\n\n".join(all_contexts),
            sources=all_sources,
            metadata={
                "collections_queried": len(collections),
                "documents_retrieved": len(all_contexts)
            }
        )
    
    def _extract_query(self, messages: List[Dict]) -> str:
        """Extract last user message as query"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Multimodal: extract text
                    texts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    return " ".join(texts)
                return content
        return ""
    
    def _query_collection(
        self, kb_url: str, kb_token: str, 
        collection_id: str, query: str, top_k: int, threshold: float
    ) -> Dict[str, Any]:
        """Query a single collection"""
        url = f"{kb_url}/collections/{collection_id}/query"
        headers = {
            "Authorization": f"Bearer {kb_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "query_text": query,
            "top_k": top_k,
            "threshold": threshold
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        documents = data.get("documents", [])
        
        contexts = [doc.get("data", "") for doc in documents]
        sources = [
            {
                "title": doc.get("metadata", {}).get("filename", "Unknown"),
                "url": f"{kb_url}{doc.get('metadata', {}).get('file_url', '')}",
                "similarity": doc.get("similarity", 0)
            }
            for doc in documents
        ]
        
        return {"contexts": contexts, "sources": sources}


# Legacy compatibility function
def tool_processor(
    request: Dict[str, Any],
    assistant: Assistant,
    tool_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Legacy function interface for plugin loading"""
    tool = SimpleRagTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,  # Include placeholder in dict result
        "content": result.content,
        "sources": result.sources,
        "error": result.error,
        "metadata": result.metadata
    }


# Also export get_definition for registry discovery
def get_definition() -> ToolDefinition:
    return SimpleRagTool.get_definition()
```

### 5.3 Tool Implementation: Rubric

```python
# lamb/completions/tools/rubric.py

from typing import Dict, Any
from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
from lamb.lamb_classes import Assistant
import json
import logging

logger = logging.getLogger(__name__)

class RubricTool(BaseTool):
    """Tool that injects rubric content for assessment"""
    
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="rubric",
            display_name="Assessment Rubric",
            description="Injects a rubric for assessment-based responses",
            placeholder="rubric",  # Outputs to {rubric}
            category="rubric",
            config_schema={
                "type": "object",
                "properties": {
                    "rubric_id": {
                        "type": "integer",
                        "description": "ID of the rubric to use"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "default": "markdown",
                        "description": "Output format for the rubric"
                    }
                },
                "required": ["rubric_id"]
            }
        )
    
    def process(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_config: Dict[str, Any]
    ) -> ToolResult:
        """Load and format rubric"""
        
        rubric_id = tool_config.get("rubric_id")
        output_format = tool_config.get("format", "markdown")
        
        if not rubric_id:
            return ToolResult(
                placeholder=self.get_definition().placeholder,  # "rubric"
                content="",
                sources=[],
                error="No rubric_id configured"
            )
        
        try:
            from lamb.evaluaitor.rubric_database import RubricDatabaseManager
            from lamb.evaluaitor.rubrics import format_rubric_as_markdown
            
            db = RubricDatabaseManager()
            rubric = db.get_rubric_by_id(rubric_id, assistant.owner)
            
            if not rubric:
                return ToolResult(
                    placeholder=self.get_definition().placeholder,
                    content="",
                    sources=[],
                    error=f"Rubric {rubric_id} not found or not accessible"
                )
            
            rubric_data = rubric.get("rubric_data")
            if isinstance(rubric_data, str):
                rubric_data = json.loads(rubric_data)
            
            # Format output
            if output_format == "json":
                content = json.dumps(rubric_data, indent=2)
            else:
                content = format_rubric_as_markdown(rubric_data)
            
            return ToolResult(
                placeholder=self.get_definition().placeholder,  # "rubric"
                content=content,
                sources=[{
                    "type": "rubric",
                    "rubric_id": rubric_id,
                    "title": rubric.get("title", "Unknown"),
                    "format": output_format
                }]
            )
            
        except Exception as e:
            logger.error(f"Error loading rubric: {e}")
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error=f"Failed to load rubric: {e}"
            )


def tool_processor(request, assistant, tool_config):
    """Legacy function interface"""
    tool = RubricTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }


def get_definition() -> ToolDefinition:
    return RubricTool.get_definition()
```

### 5.4 Tool Implementation: Single File

```python
# lamb/completions/tools/single_file.py

from typing import Dict, Any
from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
from lamb.lamb_classes import Assistant
import os
import logging

logger = logging.getLogger(__name__)

class SingleFileTool(BaseTool):
    """Tool that injects contents of a single file"""
    
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="single_file",
            display_name="Single File Context",
            description="Injects the contents of a file as context",
            placeholder="file",  # Outputs to {file}
            category="file",
            config_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file (relative to static/public)"
                    },
                    "max_chars": {
                        "type": "integer",
                        "default": 50000,
                        "description": "Maximum characters to read"
                    }
                },
                "required": ["file_path"]
            }
        )
    
    def process(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_config: Dict[str, Any]
    ) -> ToolResult:
        """Read and return file contents"""
        
        file_path = tool_config.get("file_path")
        max_chars = tool_config.get("max_chars", 50000)
        
        if not file_path:
            return ToolResult(
                placeholder=self.get_definition().placeholder,  # "file"
                content="",
                sources=[],
                error="No file_path configured"
            )
        
        # Security: prevent path traversal
        if ".." in file_path:
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error="Invalid file path"
            )
        
        base_path = os.path.join("static", "public")
        full_path = os.path.join(base_path, file_path)
        
        # Verify path is within base directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error="Invalid file path"
            )
        
        if not os.path.exists(full_path):
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error=f"File not found: {file_path}"
            )
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read(max_chars)
            
            return ToolResult(
                placeholder=self.get_definition().placeholder,  # "file"
                content=content,
                sources=[{
                    "type": "file",
                    "path": file_path,
                    "chars": len(content)
                }],
                metadata={
                    "truncated": len(content) >= max_chars
                }
            )
            
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return ToolResult(
                placeholder=self.get_definition().placeholder,
                content="",
                sources=[],
                error=f"Failed to read file: {e}"
            )


def tool_processor(request, assistant, tool_config):
    """Legacy function interface"""
    tool = SingleFileTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }


def get_definition() -> ToolDefinition:
    return SingleFileTool.get_definition()
```

---

## 6. Data Model Changes

### 6.1 New Assistant Metadata Structure

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "capabilities": {
        "vision": false,
        "image_generation": false
    },
    "verbose": false,
    
    "tools": [
        {
            "type": "simple_rag",
            "enabled": true,
            "config": {
                "collections": ["col-123", "col-456"],
                "top_k": 5,
                "threshold": 0.3
            }
        },
        {
            "type": "rubric",
            "enabled": true,
            "config": {
                "rubric_id": 42,
                "format": "markdown"
            }
        },
        {
            "type": "single_file",
            "enabled": false,
            "config": {
                "file_path": "documents/guide.md"
            }
        }
    ],
    
    "rag_processor": "simple_rag"
}
```

### 6.2 Backward Compatibility Layer

```python
def normalize_tool_config(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert legacy metadata to new format.
    Handles backward compatibility with existing assistants.
    """
    if "tools" in metadata:
        # Already new format
        return metadata
    
    # Convert legacy rag_processor to tools array
    tools = []
    rag_processor = metadata.get("rag_processor", "")
    
    if rag_processor and rag_processor != "no_rag":
        tool_entry = {
            "type": rag_processor,
            "enabled": True,
            "config": {}
        }
        
        # Migrate legacy config fields
        if rag_processor == "simple_rag":
            # Collections are in assistant.RAG_collections
            pass  # Will be populated from assistant object
        elif rag_processor == "rubric_rag":
            if "rubric_id" in metadata:
                tool_entry["config"]["rubric_id"] = metadata["rubric_id"]
                tool_entry["config"]["format"] = metadata.get("rubric_format", "markdown")
        elif rag_processor == "single_file_rag":
            if "file_path" in metadata:
                tool_entry["config"]["file_path"] = metadata["file_path"]
        
        # Map old names to new
        type_mapping = {
            "simple_rag": "simple_rag",
            "rubric_rag": "rubric",
            "single_file_rag": "single_file"
        }
        tool_entry["type"] = type_mapping.get(rag_processor, rag_processor)
        
        tools.append(tool_entry)
    
    metadata["tools"] = tools
    return metadata
```

### 6.3 Dynamic Placeholder System

**Key Design: Placeholders are defined by each tool, not hardcoded.**

Each tool's `ToolDefinition` declares its `placeholder` attribute, and the `ToolResult` includes the placeholder name. The prompt processor dynamically iterates over all `{placeholder: content}` pairs.

**Current Tool Placeholders (examples):**

| Tool Name | Placeholder | Template Example |
|-----------|-------------|------------------|
| `simple_rag` | `{context}` | `Based on this context: {context}` |
| `rubric` | `{rubric}` | `Use this rubric: {rubric}` |
| `single_file` | `{file}` | `Reference document: {file}` |
| `assistant_tool` | `{tool_result}` | Future: Tool assistant results |

**Custom Tools Can Define Any Placeholder:**

```python
# Example: A custom "glossary" tool
class GlossaryTool(BaseTool):
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="glossary",
            placeholder="glossary",  # Custom placeholder!
            # ...
        )
```

Template using custom tool:
```
{user_input}

Glossary of terms:
{glossary}

Context from knowledge base:
{context}
```

**Cleanup Rule:** Any `{placeholder}` tags remaining after tool substitution are removed (tools not enabled or not providing content).

---

## 7. Completion Pipeline Refactoring

### 7.1 Tool Orchestrator

```python
# lamb/completions/tool_orchestrator.py

from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
from lamb.completions.tools.base import ToolResult
import importlib
import logging

logger = logging.getLogger(__name__)

class ToolOrchestrator:
    """Coordinates execution of multiple tools for an assistant"""
    
    def __init__(self):
        self._tool_cache = {}
    
    def execute_tools(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[Dict[str, Any]]
    ) -> Dict[str, ToolResult]:
        """
        Execute all enabled tools and return results keyed by placeholder.
        
        Args:
            request: Full completion request
            assistant: Assistant object
            tool_configs: List of tool configurations from metadata
            
        Returns:
            Dict mapping placeholder names to ToolResults
        """
        results = {}
        
        for tool_config in tool_configs:
            if not tool_config.get("enabled", True):
                continue
            
            tool_type = tool_config.get("type")
            if not tool_type:
                continue
            
            try:
                # Load tool module
                tool_module = self._load_tool(tool_type)
                if not tool_module:
                    logger.warning(f"Tool {tool_type} not found")
                    continue
                
                # Execute tool
                config = tool_config.get("config", {})
                result = tool_module.tool_processor(request, assistant, config)
                
                # Convert dict result to ToolResult if needed (legacy support)
                if isinstance(result, dict):
                    # Legacy tools output to "context" by default
                    placeholder = result.get("placeholder", "context")
                    result = ToolResult(
                        placeholder=placeholder,
                        content=result.get("content", ""),
                        sources=result.get("sources", []),
                        error=result.get("error"),
                        metadata=result.get("metadata")
                    )
                
                # Use placeholder from the result itself (dynamic!)
                results[result.placeholder] = result
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_type}: {e}")
                results[tool_type] = ToolResult(
                    content="",
                    sources=[],
                    error=str(e)
                )
        
        return results
    
    def _load_tool(self, tool_type: str):
        """Load tool module with caching"""
        if tool_type in self._tool_cache:
            return self._tool_cache[tool_type]
        
        try:
            module = importlib.import_module(f"lamb.completions.tools.{tool_type}")
            self._tool_cache[tool_type] = module
            return module
        except ImportError:
            # Try legacy path
            try:
                module = importlib.import_module(f"lamb.completions.rag.{tool_type}")
                self._tool_cache[tool_type] = module
                return module
            except ImportError:
                return None
    
    def get_all_sources(self, results: Dict[str, ToolResult]) -> List[Dict[str, Any]]:
        """Aggregate sources from all tool results"""
        all_sources = []
        for result in results.values():
            if result.sources:
                all_sources.extend(result.sources)
        return all_sources
```

**Streaming status messages:** When `stream=True` on the completion request, the orchestrator emits markdown-formatted status events per tool step in execution order, e.g.:
- `querying knowledge base {collection_id}`
- `generating rubric {rubric_id}`
- `reading file {file_path}`
- `merging tool outputs`

These events must avoid leaking secrets and should include only safe identifiers. Downstream connectors should stream them before/while sending model tokens.

### 7.2 Modified Main Pipeline

```python
# lamb/completions/main.py (modifications)

from lamb.completions.tool_orchestrator import ToolOrchestrator

# ... existing imports ...

tool_orchestrator = ToolOrchestrator()

def get_tool_contexts(
    request: Dict[str, Any],
    assistant: Assistant,
    plugin_config: Dict[str, str]
) -> Dict[str, Any]:
    """
    Execute all enabled tools and return contexts for placeholders.
    
    Replaces the old get_rag_context() function.
    """
    # Normalize config to ensure tools array exists
    metadata = normalize_tool_config(plugin_config)
    tool_configs = metadata.get("tools", [])
    
    # Handle legacy assistants without tools array
    if not tool_configs:
        # Fall back to legacy single RAG behavior
        rag_processor = plugin_config.get("rag_processor", "")
        if rag_processor and rag_processor != "no_rag":
            tool_configs = [{
                "type": rag_processor,
                "enabled": True,
                "config": _extract_legacy_config(assistant, rag_processor)
            }]
    
    # Execute tools
    results = tool_orchestrator.execute_tools(request, assistant, tool_configs)
    
    # Convert to context dict for prompt processor
    contexts = {}
    sources = []
    
    for placeholder, result in results.items():
        contexts[placeholder] = result.content
        if result.sources:
            sources.extend(result.sources)
    
    return {
        "contexts": contexts,
        "sources": sources
    }


def _extract_legacy_config(assistant: Assistant, rag_processor: str) -> Dict[str, Any]:
    """Extract tool config from legacy assistant fields"""
    config = {}
    
    if rag_processor == "simple_rag":
        if assistant.RAG_collections:
            config["collections"] = [c.strip() for c in assistant.RAG_collections.split(",")]
        config["top_k"] = assistant.RAG_Top_k or 3
        
    # Other configs extracted from metadata field
    try:
        metadata = json.loads(assistant.metadata) if assistant.metadata else {}
        if rag_processor == "rubric_rag":
            config["rubric_id"] = metadata.get("rubric_id")
            config["format"] = metadata.get("rubric_format", "markdown")
        elif rag_processor == "single_file_rag":
            config["file_path"] = metadata.get("file_path")
    except:
        pass
    
    return config
```

**Verbose propagation:** `assistant.metadata.verbose` (default `false`) is propagated through the request context to control emission of redacted pipeline traces (tool inputs sans secrets, output lengths, prompt after substitution). When `verbose` is off, traces are suppressed; errors still log without sensitive payloads.

### 7.3 Modified Prompt Processor

```python
# lamb/completions/pps/simple_augment.py (modifications)

def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None  # Now contains multi-tool results
) -> List[Dict[str, str]]:
    """
    Enhanced prompt processor supporting multiple placeholders.
    
    rag_context structure (new):
    {
        "contexts": {
            "context": "...",     # From simple_rag
            "rubric": "...",      # From rubric tool
            "file": "..."         # From single_file tool
        },
        "sources": [...]
    }
    """
    messages = request.get('messages', [])
    if not messages:
        return messages
    
    last_message = messages[-1]['content']
    processed_messages = []
    
    if assistant:
        if assistant.system_prompt:
            processed_messages.append({
                "role": "system",
                "content": assistant.system_prompt
            })
        
        processed_messages.extend(messages[:-1])
        
        if assistant.prompt_template:
            # Process user input
            user_input_text = _extract_user_text(last_message, assistant)
            
            # Start with template
            prompt = assistant.prompt_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")
            
            # DYNAMIC PLACEHOLDER REPLACEMENT
            # Each tool defines its own placeholder - we iterate over all pairs
            if rag_context:
                contexts = rag_context.get("contexts", {})
                
                # Dynamically replace ALL placeholders from tool results
                # No hardcoded list - tools define their own placeholders!
                for placeholder_name, content in contexts.items():
                    placeholder_tag = "{" + placeholder_name + "}"
                    if placeholder_tag in prompt:
                        if content:
                            prompt = prompt.replace(placeholder_tag, "\n\n" + content + "\n\n")
                        else:
                            # Remove empty placeholder
                            prompt = prompt.replace(placeholder_tag, "")
                
                # Clean up any remaining unreplaced placeholders
                # (tools that weren't enabled but template has placeholder)
                import re
                prompt = re.sub(r'\{[a-z_]+\}', '', prompt)
            
            processed_messages.append({
                "role": messages[-1]['role'],
                "content": prompt
            })
        else:
            processed_messages.append(messages[-1])
        
        return processed_messages
    
    return messages


def _extract_user_text(last_message, assistant) -> str:
    """Extract text from potentially multimodal message"""
    if isinstance(last_message, list):
        texts = [p.get("text", "") for p in last_message if p.get("type") == "text"]
        return " ".join(texts)
    return str(last_message)
```

---

## 8. Tool Registry System

### 8.1 Tool Registry

```python
# lamb/completions/tool_registry.py

from typing import Dict, Any, List, Optional
from lamb.completions.tools.base import ToolDefinition
import importlib
import os
import glob
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Central registry for available tools"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._loaded = False
        return cls._instance
    
    def discover_tools(self) -> None:
        """Scan tools directory and register all tools"""
        if self._loaded:
            return
        
        tools_dir = os.path.join(os.path.dirname(__file__), "tools")
        tool_files = glob.glob(os.path.join(tools_dir, "*.py"))
        
        for tool_file in tool_files:
            if "__init__" in tool_file or "base" in tool_file:
                continue
            
            module_name = os.path.basename(tool_file)[:-3]
            
            try:
                module = importlib.import_module(f"lamb.completions.tools.{module_name}")
                
                # Check for new-style tool
                if hasattr(module, "get_definition"):
                    definition = module.get_definition()
                    self._tools[definition.name] = {
                        "definition": definition,
                        "module": module
                    }
                    logger.info(f"Registered tool: {definition.name}")
                    
                # Check for legacy rag_processor
                elif hasattr(module, "rag_processor"):
                    # Create synthetic definition for legacy
                    self._tools[module_name] = {
                        "definition": ToolDefinition(
                            name=module_name,
                            display_name=module_name.replace("_", " ").title(),
                            description="Legacy RAG processor",
                            placeholder="context",
                            config_schema={},
                            category="legacy"
                        ),
                        "module": module
                    }
                    logger.info(f"Registered legacy tool: {module_name}")
                    
            except Exception as e:
                logger.error(f"Failed to load tool {module_name}: {e}")
        
        self._loaded = True
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Get tool by name"""
        self.discover_tools()
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered tools"""
        self.discover_tools()
        return self._tools.copy()
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get definitions for all tools (for API/UI)"""
        self.discover_tools()
        definitions = []
        
        for name, tool_data in self._tools.items():
            definition = tool_data["definition"]
            definitions.append({
                "name": definition.name,
                "display_name": definition.display_name,
                "description": definition.description,
                "placeholder": definition.placeholder,
                "category": definition.category,
                "config_schema": definition.config_schema,
                "version": definition.version
            })
        
        return definitions


# Global registry instance
tool_registry = ToolRegistry()
```

---

## 9. API Changes

### 9.1 New Endpoints

```python
# Add to lamb/completions/main.py

@router.get("/tools")
async def list_available_tools(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    List all available tools with their configuration schemas.
    
    Returns:
        List of tool definitions with config schemas
    """
    from lamb.completions.tool_registry import tool_registry
    
    return {
        "tools": tool_registry.get_tool_definitions()
    }


@router.get("/tools/{tool_name}")
async def get_tool_definition(
    tool_name: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    Get definition for a specific tool.
    """
    from lamb.completions.tool_registry import tool_registry
    
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    definition = tool["definition"]
    return {
        "name": definition.name,
        "display_name": definition.display_name,
        "description": definition.description,
        "placeholder": definition.placeholder,
        "category": definition.category,
        "config_schema": definition.config_schema
    }


@router.post("/tools/{tool_name}/validate")
async def validate_tool_config(
    tool_name: str,
    config: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(bearer_security)
):
    """
    Validate a tool configuration against its schema.
    """
    from lamb.completions.tool_registry import tool_registry
    import jsonschema
    
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    schema = tool["definition"].config_schema
    
    try:
        jsonschema.validate(config, schema)
        return {"valid": True, "errors": []}
    except jsonschema.ValidationError as e:
        return {"valid": False, "errors": [str(e)]}
```

### 9.2 Modified /list Endpoint

```python
@router.get("/list")
async def list_processors_and_connectors(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    List available Prompt Processors, Connectors, RAG processors, and Tools.
    """
    pps = load_plugins('pps')
    connectors = load_plugins('connectors')
    
    # Get tools from registry instead of legacy rag loading
    from lamb.completions.tool_registry import tool_registry
    tools = tool_registry.get_tool_definitions()
    
    # ... rest of existing code for connectors ...
    
    return {
        "prompt_processors": list(pps.keys()),
        "connectors": connector_info,
        "rag_processors": [t["name"] for t in tools],  # Backward compat
        "tools": tools  # New field
    }
```

---

## 10. Migration Strategy

### 10.1 Core Migration Principle: Migrate-on-Access

**The backend is the single source of truth.** When a legacy assistant is accessed, the backend:
1. Detects legacy format
2. Converts to new format
3. **Updates the database immediately**
4. Returns new format to frontend

**Frontend only ever sees new format** - no dual-format handling required.

### 10.2 Migration Trigger Points

| Endpoint | Triggers Migration? | Rationale |
|----------|---------------------|-----------|
| `GET /assistants/{id}` | ✅ YES | Viewing/editing single assistant |
| `POST /completions?assistant={id}` | ✅ YES | Using assistant for completion |
| `GET /assistants` (list) | ❌ NO | Performance - could be 1000s of assistants |
| `PUT /assistants/{id}` | ✅ YES | Editing always saves new format |

### 10.3 Metadata Versioning

**All metadata includes a `_format_version` field** to support future migrations:

```json
{
    "_format_version": 2,
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "tools": [
        {"type": "simple_rag", "enabled": true, "config": {...}}
    ]
}
```

**Version History:**
| Version | Description |
|---------|-------------|
| 1 (implicit) | Legacy format with `rag_processor` string |
| 2 | Multi-tool format with `tools[]` array |
| 3+ | Future migrations |

### 10.4 Legacy Database Columns: Preserve Read-Only

After migration:
- `RAG_collections` column: **PRESERVED** (not cleared)
- `RAG_Top_k` column: **PRESERVED** (not cleared)
- Source of truth: **`metadata.tools[]` ONLY**

**Rationale:** Preserving legacy columns allows emergency rollback if migration has bugs.

### 10.5 Migration Implementation

```python
# lamb/database_manager.py (additions)

import logging

migration_logger = logging.getLogger('lamb.migration')

CURRENT_METADATA_VERSION = 2

def migrate_assistant_if_needed(self, assistant_id: int) -> Optional[Assistant]:
    """
    Load assistant, migrate if legacy format, save and return.
    Called by get_assistant_by_id() and completion endpoints.
    """
    assistant = self._get_assistant_raw(assistant_id)
    if not assistant:
        return None
    
    metadata = json.loads(assistant.metadata) if assistant.metadata else {}
    
    # Check if migration needed
    current_version = metadata.get("_format_version", 1)
    
    if current_version < CURRENT_METADATA_VERSION:
        # Perform migration
        old_metadata = metadata.copy()
        new_metadata = self._migrate_metadata(metadata, assistant, current_version)
        
        # Log migration with full data
        migration_logger.info(
            f"Migrated assistant {assistant_id} from v{current_version} to v{CURRENT_METADATA_VERSION}",
            extra={
                "assistant_id": assistant_id,
                "assistant_name": assistant.name,
                "owner": assistant.owner,
                "old_metadata": old_metadata,
                "new_metadata": new_metadata,
                "from_version": current_version,
                "to_version": CURRENT_METADATA_VERSION
            }
        )
        
        # Update database
        self._update_assistant_metadata(assistant_id, json.dumps(new_metadata))
        
        # Update in-memory object
        assistant.api_callback = json.dumps(new_metadata)
    
    return assistant


def _migrate_metadata(
    self, 
    metadata: Dict[str, Any], 
    assistant: Assistant,
    from_version: int
) -> Dict[str, Any]:
    """
    Migrate metadata from one version to current.
    Handles chained migrations (v1 → v2 → v3 etc.)
    """
    result = metadata.copy()
    
    # v1 → v2: Convert rag_processor to tools[]
    if from_version < 2:
        result = self._migrate_v1_to_v2(result, assistant)
    
    # Future: v2 → v3, etc.
    # if from_version < 3:
    #     result = self._migrate_v2_to_v3(result)
    
    return result


def _migrate_v1_to_v2(
    self, 
    metadata: Dict[str, Any], 
    assistant: Assistant
) -> Dict[str, Any]:
    """
    Migrate from legacy rag_processor format to tools[] format.
    """
    result = metadata.copy()
    
    # Skip if already has tools
    if "tools" in result:
        result["_format_version"] = 2
        return result
    
    tools = []
    rag_processor = metadata.get("rag_processor", "")
    
    if rag_processor and rag_processor not in ("", "no_rag"):
        tool_entry = {
            "type": rag_processor,
            "enabled": True,
            "config": {}
        }
        
        # Extract config from legacy fields
        if rag_processor == "simple_rag":
            # Read from legacy database columns
            if assistant.RAG_collections:
                tool_entry["config"]["collections"] = [
                    c.strip() for c in assistant.RAG_collections.split(",") if c.strip()
                ]
            tool_entry["config"]["top_k"] = assistant.RAG_Top_k or 3
            
        elif rag_processor == "rubric_rag":
            tool_entry["type"] = "rubric"  # Rename
            if metadata.get("rubric_id"):
                tool_entry["config"]["rubric_id"] = metadata["rubric_id"]
            tool_entry["config"]["format"] = metadata.get("rubric_format", "markdown")
            
        elif rag_processor == "single_file_rag":
            tool_entry["type"] = "single_file"  # Rename
            if metadata.get("file_path"):
                tool_entry["config"]["file_path"] = metadata["file_path"]
        
        # Map old names to new names
        type_mapping = {
            "simple_rag": "simple_rag",
            "rubric_rag": "rubric",
            "single_file_rag": "single_file"
        }
        tool_entry["type"] = type_mapping.get(tool_entry["type"], tool_entry["type"])
        
        tools.append(tool_entry)
    
    # Build new metadata
    result["tools"] = tools
    result["_format_version"] = 2
    
    # Remove legacy fields from metadata (but NOT from database columns)
    for legacy_key in ["rag_processor", "rubric_id", "rubric_format", "file_path"]:
        result.pop(legacy_key, None)
    
    return result
```

### 10.6 Updated get_assistant_by_id

```python
def get_assistant_by_id(self, assistant_id: int) -> Optional[Assistant]:
    """
    Fetch assistant by ID with automatic migration.
    """
    # This now handles migration internally
    return self.migrate_assistant_if_needed(assistant_id)
```

### 10.7 Logging Format

All migrations logged at INFO level with structured data:

```
INFO lamb.migration: Migrated assistant 42 from v1 to v2
  assistant_id: 42
  assistant_name: "My RAG Assistant"
  owner: "user@example.com"
  old_metadata: {"rag_processor": "simple_rag", "connector": "openai", ...}
  new_metadata: {"_format_version": 2, "tools": [...], "connector": "openai", ...}
  from_version: 1
  to_version: 2
```

### 10.8 Implementation Phases

| Phase | Duration | Changes |
|-------|----------|---------|
| **Phase 1** | Week 1-2 | Add `tools/` directory, new interfaces, registry |
| **Phase 2** | Week 3 | Add migration logic to `get_assistant_by_id()` |
| **Phase 3** | Week 4 | Add migration to `/completions` endpoint |
| **Phase 4** | Week 5+ | Monitor logs, verify migrations, optimize |

### 10.9 Rollback Strategy

If migration has bugs:
1. Legacy columns (`RAG_collections`, `RAG_Top_k`) are preserved
2. Deploy hotfix that reads from legacy columns if `_format_version` missing
3. Clear `tools[]` from affected assistants
4. Re-deploy fixed migration

---

## 11. Implementation Tasks

### 11.1 Core Backend (Priority 1)

| # | Task | Est. Hours | Dependencies |
|---|------|-----------|--------------|
| B1 | Create `tools/` directory structure | 1 | - |
| B2 | Implement `tools/base.py` interfaces | 2 | B1 |
| B3 | Implement `tool_registry.py` | 3 | B2 |
| B4 | Implement `tool_orchestrator.py` | 4 | B2, B3 |
| B5 | Migrate `simple_rag.py` to new interface | 2 | B2 |
| B6 | Migrate `rubric_rag.py` → `rubric.py` | 2 | B2 |
| B7 | Migrate `single_file_rag.py` → `single_file.py` | 2 | B2 |
| B8 | Create `no_tool.py` | 1 | B2 |

### 11.2 Pipeline Integration (Priority 1)

| # | Task | Est. Hours | Dependencies |
|---|------|-----------|--------------|
| B9 | Update `main.py` with multi-tool support | 4 | B4 |
| B10 | Update `simple_augment.py` for multi-placeholder | 3 | B9 |
| B11 | Add backward compatibility layer | 3 | B9, B10 |
| B12 | Add `/tools` API endpoint | 2 | B3 |
| B13 | Update `/list` endpoint | 1 | B3 |

### 11.3 Testing & Migration (Priority 2)

| # | Task | Est. Hours | Dependencies |
|---|------|-----------|--------------|
| B14 | Unit tests for tool registry | 3 | B3 |
| B15 | Unit tests for tool orchestrator | 3 | B4 |
| B16 | Integration tests for multi-tool pipeline | 4 | B9, B10 |
| B17 | Create migration script | 3 | B11 |
| B18 | Test backward compatibility | 4 | B11 |
| B19 | Streaming status message tests | 2 | B4, B9 |
| B20 | Verbose trace redaction tests | 2 | B4, B9 |

### 11.4 Total Estimates

| Category | Hours |
|----------|-------|
| Core Backend | 17 |
| Pipeline Integration | 13 |
| Testing & Migration | 17 |
| **Total** | **47 hours** |

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
# testing/unit-tests/test_tool_registry.py

import pytest
from lamb.completions.tool_registry import ToolRegistry

def test_tool_discovery():
    """Verify all tools are discovered"""
    registry = ToolRegistry()
    tools = registry.get_all_tools()
    
    assert "simple_rag" in tools
    assert "rubric" in tools
    assert "single_file" in tools

def test_tool_definition():
    """Verify tool definitions are complete"""
    registry = ToolRegistry()
    tool = registry.get_tool("simple_rag")
    
    assert tool is not None
    assert tool["definition"].name == "simple_rag"
    assert tool["definition"].placeholder == "context"
    assert "collections" in tool["definition"].config_schema["properties"]
```

### 12.2 Integration Tests

```python
# testing/unit-tests/test_multi_tool_pipeline.py

import pytest
from lamb.completions.tool_orchestrator import ToolOrchestrator
from lamb.lamb_classes import Assistant

def test_single_tool_execution():
    """Test single tool execution"""
    orchestrator = ToolOrchestrator()
    
    request = {"messages": [{"role": "user", "content": "test query"}]}
    assistant = create_test_assistant()
    tools = [{"type": "no_tool", "enabled": True, "config": {}}]
    
    results = orchestrator.execute_tools(request, assistant, tools)
    
    assert "context" in results

def test_multi_tool_execution():
    """Test multiple tools execute and return to different placeholders"""
    orchestrator = ToolOrchestrator()
    
    request = {"messages": [{"role": "user", "content": "test query"}]}
    assistant = create_test_assistant()
    tools = [
        {"type": "simple_rag", "enabled": True, "config": {"collections": []}},
        {"type": "rubric", "enabled": True, "config": {"rubric_id": 1}},
    ]
    
    results = orchestrator.execute_tools(request, assistant, tools)
    
    # Each tool outputs to its placeholder
    assert "context" in results  # simple_rag
    assert "rubric" in results   # rubric

def test_streaming_status_events():
    """Streaming emits ordered markdown status messages without secrets"""
    orchestrator = ToolOrchestrator()
    request = {"messages": [{"role": "user", "content": "test query"}], "stream": True}
    assistant = create_test_assistant(verbose=False)
    tools = [{"type": "simple_rag", "enabled": True, "config": {"collections": ["kb1"]}}]
    
    statuses, _ = orchestrator.execute_with_status(request, assistant, tools)  # helper returns (status_events, results)
    assert statuses[0].startswith("querying knowledge base")
    assert "secret" not in "".join(statuses)

def test_verbose_trace_redacts():
    """Verbose traces include lengths but redact sensitive values"""
    request = {"messages": [{"role": "user", "content": "test query"}], "stream": False}
    assistant = create_test_assistant(verbose=True)
    tool_configs = [{"type": "single_file", "enabled": True, "config": {"file_path": "docs/guide.md"}}]
    
    trace = run_with_verbose_trace(request, assistant, tool_configs)  # returns trace metadata/log object
    assert "docs/guide.md" in trace["steps"][0]["input"]
    assert "api_key" not in str(trace)
```

### 12.3 Backward Compatibility Tests

```python
def test_legacy_assistant_works():
    """Verify assistants with old format still work"""
    # Create assistant with legacy metadata
    metadata = {
        "prompt_processor": "simple_augment",
        "connector": "openai",
        "llm": "gpt-4",
        "rag_processor": "simple_rag"
    }
    
    # Should auto-convert to new format
    normalized = normalize_tool_config(metadata)
    
    assert "tools" in normalized
    assert len(normalized["tools"]) == 1
    assert normalized["tools"][0]["type"] == "simple_rag"
```

---

## Appendix A: File Diffs Summary

### A.1 Files to Create

| File | Lines (Est.) |
|------|--------------|
| `lamb/completions/tools/__init__.py` | 5 |
| `lamb/completions/tools/base.py` | 80 |
| `lamb/completions/tools/simple_rag.py` | 150 |
| `lamb/completions/tools/rubric.py` | 100 |
| `lamb/completions/tools/single_file.py` | 80 |
| `lamb/completions/tools/no_tool.py` | 20 |
| `lamb/completions/tool_registry.py` | 120 |
| `lamb/completions/tool_orchestrator.py` | 100 |

### A.2 Files to Modify

| File | Changes |
|------|---------|
| `lamb/completions/main.py` | Add tool orchestration, new endpoints |
| `lamb/completions/pps/simple_augment.py` | Multi-placeholder support |
| `lamb/database_manager.py` | Metadata normalization helpers |

### A.3 Files to Deprecate (Future)

| File | Replacement |
|------|-------------|
| `lamb/completions/rag/simple_rag.py` | `tools/simple_rag.py` |
| `lamb/completions/rag/rubric_rag.py` | `tools/rubric.py` |
| `lamb/completions/rag/single_file_rag.py` | `tools/single_file.py` |
| `lamb/completions/rag/no_rag.py` | `tools/no_tool.py` |

---

## Appendix B: Related Documents

- **Frontend Spec:** `Documentation/MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md`
- **Tool Assistants:** `Documentation/TOOL_ASSISTANTS_ANALYSIS_REPORT.md`
- **Architecture:** `Documentation/lamb_architecture.md`
- **DB Schema:** `Documentation/LAMB_DATABASE_SCHEMA.md`

---

**Document Status:** Draft for Review  
**Author:** Generated by AI Analysis  
**Reviewers:** LAMB Development Team

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 9, 2025 | Initial backend specification |
| 1.1 | Dec 9, 2025 | Dynamic placeholder design: tools define their own placeholders, ToolResult includes placeholder field, prompt processor iterates dynamically over all placeholder/content pairs without hardcoding |
| 1.2 | Dec 9, 2025 | Migrate-on-access strategy: backend migrates legacy assistants on GET/completions, updates database immediately, adds `_format_version` field for future migrations, preserves legacy columns read-only, INFO logging with full data |

