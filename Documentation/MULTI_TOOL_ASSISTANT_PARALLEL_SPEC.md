# Multi-Tool Assistant System: Parallel Implementation Strategy

**Version:** 1.0  
**Date:** December 9, 2025  
**Strategy:** Parallel Implementation (No Migration)  
**Related Documents:**  
- `Documentation/MULTI_TOOL_ASSISTANT_BACKEND_SPEC.md` (Original backend spec)
- `Documentation/MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md` (Original frontend spec)
- `Documentation/lamb_architecture.md` (System architecture)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategy Overview](#2-strategy-overview)
3. [Backend Architecture](#3-backend-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Data Model](#5-data-model)
6. [Assistant Type Detection](#6-assistant-type-detection)
7. [Implementation Plan](#7-implementation-plan)
8. [Testing Strategy](#8-testing-strategy)
9. [Future Considerations](#9-future-considerations)

---

## 1. Executive Summary

### 1.1 Background

The LAMB assistant system currently allows selecting **one RAG processor** per assistant, which retrieves context and injects it into a single placeholder (`{context}`). We want to support **multiple tools** in the same pipeline execution, where each tool outputs to a **specific placeholder** (`{context}`, `{rubric}`, `{file}`, etc.).

### 1.2 New Strategy: Parallel Implementation

Instead of migrating existing assistants, we will:

1. **Keep the classic assistant implementation unchanged** - Both frontend and backend
2. **Implement multi-tool assistants in parallel** - New code paths for multi-tool functionality
3. **Let users choose** - When creating an assistant, users select "Classic" or "Multi-Tool" type
4. **Use metadata to distinguish** - A specific metadata field identifies assistant type

### 1.3 Benefits of This Approach

| Benefit | Description |
|---------|-------------|
| **Zero Migration Risk** | Existing assistants remain untouched |
| **Gradual Rollout** | Multi-tool can be tested independently |
| **Clean Separation** | No complex dual-format handling |
| **Easy Rollback** | Can disable multi-tool without affecting classic |
| **Simpler Testing** | Each path can be tested in isolation |

### 1.4 Key Design Decisions (CONFIRMED)

| Decision | Choice |
|----------|--------|
| Classic code | **KEEP UNCHANGED** |
| Multi-tool code | **NEW PARALLEL IMPLEMENTATION** |
| Old RAG processors | `completions/rag/` (unchanged) |
| Old prompt processors | `completions/pps/` (unchanged) |
| New tool plugins | `completions/tools/` (new) |
| New prompt processors | `completions/multi-tool-pps/` (new) |
| Assistant type field | `metadata.assistant_type: "multi_tool"` ✓ |
| Frontend routes | `/multi-tool-assistants/` for creator ✓ |
| Tool naming | **Same as classic** (`simple_rag`, `rubric_rag`, `single_file_rag`) ✓ |
| Classic → Multi-Tool conversion | **NOT IN MVP** ✓ |

---

## 2. Strategy Overview

### 2.1 What Stays the Same

```
CLASSIC ASSISTANT PIPELINE (UNCHANGED)
──────────────────────────────────────

Request → get_assistant_details() → parse_plugin_config()
                                          │
                                          ▼
                                ┌─────────────────┐
                                │ SINGLE RAG Call │
                                │ rag_processor() │  ← completions/rag/*
                                └────────┬────────┘
                                          │
                                          ▼
                                ┌─────────────────┐
                                │ Prompt Processor│  ← completions/pps/*
                                │ Replaces only   │
                                │ {context}       │
                                └────────┬────────┘
                                          │
                                          ▼
                                ┌─────────────────┐
                                │   Connector     │
                                │   (LLM call)    │
                                └─────────────────┘
```

### 2.2 What Gets Added (In Parallel)

```
MULTI-TOOL ASSISTANT PIPELINE (NEW)
───────────────────────────────────

Request → get_assistant_details() → check assistant_type
                                          │
                        ┌─────────────────┴─────────────────┐
                        │ assistant_type == "multi_tool"?   │
                        └─────────────────┬─────────────────┘
                                          │ YES
                                          ▼
                            ┌──────────────────────────┐
                            │   Tool Orchestrator      │  ← NEW
                            │   load_enabled_tools()   │
                            └───────────┬──────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
┌─────────────────┐          ┌─────────────────┐          ┌──────────────────┐
│ simple_rag      │          │ rubric          │          │ single_file      │
│ → {context}     │          │ → {rubric}      │          │ → {file}         │
└────────┬────────┘          └────────┬────────┘          └──────┬───────────┘
          │                           │                          │
          └───────────────────────────┼──────────────────────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │   Merge Results     │
                           │   tool_contexts = { │
                           │     "context": ..., │
                           │     "rubric": ...,  │
                           │     "file": ...     │
                           │   }                 │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │  Multi-Tool PPS     │  ← completions/multi-tool-pps/*
                           │  Replace ALL        │
                           │  placeholders       │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │     Connector       │
                           │     (LLM call)      │
                           └─────────────────────┘
```

### 2.3 Directory Structure Summary

```
lamb/completions/
├── main.py                          # Modified: route by assistant_type
├── org_config_resolver.py           # Unchanged
│
├── connectors/                      # Unchanged
│   ├── openai.py
│   ├── ollama.py
│   ├── bypass.py
│   └── banana_img.py
│
├── pps/                             # UNCHANGED - Classic prompt processors
│   └── simple_augment.py
│
├── rag/                             # UNCHANGED - Classic RAG processors
│   ├── no_rag.py
│   ├── simple_rag.py
│   ├── rubric_rag.py
│   └── single_file_rag.py
│
├── tools/                           # NEW - Multi-tool plugins
│   ├── __init__.py
│   ├── base.py                      # Base tool interface
│   ├── no_rag.py                    # No-op tool (same name as classic)
│   ├── simple_rag.py                # KB RAG tool (same name as classic)
│   ├── rubric_rag.py                # Rubric tool (same name as classic)
│   └── single_file_rag.py           # File tool (same name as classic)
│
├── multi-tool-pps/                  # NEW - Multi-tool prompt processors
│   └── multi_augment.py             # Handles multiple placeholders
│
├── tool_orchestrator.py             # NEW - Tool execution coordinator
└── tool_registry.py                 # NEW - Tool discovery and metadata
```

---

## 3. Backend Architecture

### 3.1 Main Router: Type-Based Routing

```python
# lamb/completions/main.py (MODIFIED - not replaced)

from lamb.completions.tool_orchestrator import ToolOrchestrator

def get_completion(request: CompletionRequest, assistant: Assistant):
    """
    Route completion request based on assistant type.
    """
    metadata = parse_metadata(assistant.metadata)
    assistant_type = metadata.get("assistant_type", "classic")
    
    if assistant_type == "multi_tool":
        # NEW: Multi-tool pipeline
        return get_multi_tool_completion(request, assistant, metadata)
    else:
        # UNCHANGED: Classic pipeline (existing code)
        return get_classic_completion(request, assistant, metadata)


def get_classic_completion(request, assistant, metadata):
    """
    EXISTING CODE - No changes.
    Uses completions/rag/* and completions/pps/*
    """
    # ... existing implementation unchanged ...
    rag_processor = metadata.get("rag_processor", "no_rag")
    rag_context = call_rag_processor(rag_processor, request, assistant)
    
    prompt_processor = metadata.get("prompt_processor", "simple_augment")
    processed = call_prompt_processor(prompt_processor, request, assistant, rag_context)
    
    connector = metadata.get("connector", "openai")
    return call_connector(connector, processed, metadata)


def get_multi_tool_completion(request, assistant, metadata):
    """
    NEW: Multi-tool pipeline.
    Uses completions/tools/* and completions/multi-tool-pps/*
    """
    # Execute all enabled tools
    orchestrator = ToolOrchestrator()
    tool_configs = metadata.get("tools", [])
    tool_results = orchestrator.execute_tools(request, assistant, tool_configs)
    
    # Build context dict from all tools
    contexts = {r.placeholder: r.content for r in tool_results.values()}
    sources = orchestrator.get_all_sources(tool_results)
    
    # Process prompt with multi-placeholder support
    prompt_processor = metadata.get("prompt_processor", "multi_augment")
    processed = call_multi_tool_pps(
        prompt_processor, request, assistant, 
        {"contexts": contexts, "sources": sources}
    )
    
    connector = metadata.get("connector", "openai")
    return call_connector(connector, processed, metadata)
```

### 3.2 Tool Plugin Base Interface

```python
# lamb/completions/tools/base.py (NEW FILE)

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from lamb.lamb_classes import Assistant

@dataclass
class ToolResult:
    """Standard result from tool execution"""
    placeholder: str                      # Placeholder name (e.g., "context")
    content: str                          # Content for the placeholder
    sources: List[Dict[str, Any]]         # Source citations
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@dataclass 
class ToolDefinition:
    """Tool metadata for registry and UI"""
    name: str                             # Unique identifier
    display_name: str                     # Human-readable name
    description: str                      # Description for UI
    placeholder: str                      # Template placeholder
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
        """Execute the tool and return results"""
        pass
    
    def validate_config(self, tool_config: Dict[str, Any]) -> List[str]:
        """Validate tool configuration. Returns list of errors."""
        return []
```

### 3.3 Tool Implementations

```python
# lamb/completions/tools/simple_rag.py (NEW FILE)

from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult

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
                        "maximum": 20
                    }
                },
                "required": ["collections"]
            }
        )
    
    def process(self, request, assistant, tool_config) -> ToolResult:
        # Implementation similar to existing rag/simple_rag.py
        # but using new interface
        collections = tool_config.get("collections", [])
        top_k = tool_config.get("top_k", 3)
        
        # ... query KB collections ...
        
        return ToolResult(
            placeholder="context",
            content="...",
            sources=[...]
        )


# Function interface for orchestrator
def tool_processor(request, assistant, tool_config):
    tool = SimpleRagTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }

def get_definition():
    return SimpleRagTool.get_definition()
```

```python
# lamb/completions/tools/rubric_rag.py (NEW FILE)
# Name matches classic: completions/rag/rubric_rag.py

class RubricRagTool(BaseTool):
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="rubric_rag",  # Same name as classic
            display_name="Assessment Rubric",
            description="Injects a rubric for assessment-based responses",
            placeholder="rubric",  # Outputs to {rubric}
            category="rubric",
            config_schema={
                "type": "object",
                "properties": {
                    "rubric_id": {"type": "integer"},
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "default": "markdown"
                    }
                },
                "required": ["rubric_id"]
            }
        )
    
    def process(self, request, assistant, tool_config) -> ToolResult:
        # Load and format rubric
        return ToolResult(
            placeholder="rubric",
            content="...",
            sources=[...]
        )
```

```python
# lamb/completions/tools/single_file_rag.py (NEW FILE)
# Name matches classic: completions/rag/single_file_rag.py

class SingleFileRagTool(BaseTool):
    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="single_file_rag",  # Same name as classic
            display_name="Single File Context",
            description="Injects the contents of a file as context",
            placeholder="file",  # Outputs to {file}
            category="file",
            config_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 50000}
                },
                "required": ["file_path"]
            }
        )
    
    def process(self, request, assistant, tool_config) -> ToolResult:
        # Read file contents
        return ToolResult(
            placeholder="file",
            content="...",
            sources=[...]
        )
```

### 3.4 Tool Orchestrator

```python
# lamb/completions/tool_orchestrator.py (NEW FILE)

from typing import Dict, Any, List
from lamb.lamb_classes import Assistant
from lamb.completions.tools.base import ToolResult
import importlib
import logging

logger = logging.getLogger(__name__)

class ToolOrchestrator:
    """Coordinates execution of multiple tools for a multi-tool assistant"""
    
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
        """
        results = {}
        
        for tool_config in tool_configs:
            if not tool_config.get("enabled", True):
                continue
            
            tool_type = tool_config.get("type")
            if not tool_type:
                continue
            
            try:
                # Load tool from completions/tools/
                tool_module = self._load_tool(tool_type)
                if not tool_module:
                    logger.warning(f"Tool {tool_type} not found")
                    continue
                
                # Execute tool
                config = tool_config.get("config", {})
                result = tool_module.tool_processor(request, assistant, config)
                
                # Store by placeholder
                placeholder = result.get("placeholder", "context")
                results[placeholder] = ToolResult(
                    placeholder=placeholder,
                    content=result.get("content", ""),
                    sources=result.get("sources", []),
                    error=result.get("error")
                )
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_type}: {e}")
        
        return results
    
    def _load_tool(self, tool_type: str):
        """Load tool module from completions/tools/"""
        if tool_type in self._tool_cache:
            return self._tool_cache[tool_type]
        
        try:
            module = importlib.import_module(f"lamb.completions.tools.{tool_type}")
            self._tool_cache[tool_type] = module
            return module
        except ImportError:
            return None
    
    def get_all_sources(self, results: Dict[str, ToolResult]) -> List[Dict]:
        """Aggregate sources from all tool results"""
        all_sources = []
        for result in results.values():
            if result.sources:
                all_sources.extend(result.sources)
        return all_sources
```

### 3.5 Multi-Tool Prompt Processor

```python
# lamb/completions/multi-tool-pps/multi_augment.py (NEW FILE)

import re
from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant

def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    tool_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Multi-tool prompt processor supporting dynamic placeholders.
    
    tool_context structure:
    {
        "contexts": {
            "context": "...",     # From simple_rag tool
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
        # Add system prompt
        if assistant.system_prompt:
            processed_messages.append({
                "role": "system",
                "content": assistant.system_prompt
            })
        
        # Add conversation history (all but last)
        processed_messages.extend(messages[:-1])
        
        if assistant.prompt_template:
            # Extract user text
            user_input_text = _extract_user_text(last_message)
            
            # Start with template
            prompt = assistant.prompt_template
            prompt = prompt.replace("{user_input}", "\n\n" + user_input_text + "\n\n")
            
            # DYNAMIC PLACEHOLDER REPLACEMENT
            if tool_context:
                contexts = tool_context.get("contexts", {})
                
                # Replace ALL placeholders from tool results
                for placeholder_name, content in contexts.items():
                    placeholder_tag = "{" + placeholder_name + "}"
                    if placeholder_tag in prompt:
                        if content:
                            prompt = prompt.replace(placeholder_tag, "\n\n" + content + "\n\n")
                        else:
                            prompt = prompt.replace(placeholder_tag, "")
                
                # Clean up unreplaced placeholders
                prompt = re.sub(r'\{[a-z_]+\}', '', prompt)
            
            processed_messages.append({
                "role": messages[-1]['role'],
                "content": prompt
            })
        else:
            processed_messages.append(messages[-1])
        
        return processed_messages
    
    return messages


def _extract_user_text(last_message) -> str:
    """Extract text from potentially multimodal message"""
    if isinstance(last_message, list):
        texts = [p.get("text", "") for p in last_message if p.get("type") == "text"]
        return " ".join(texts)
    return str(last_message)
```

### 3.6 Tool Registry

```python
# lamb/completions/tool_registry.py (NEW FILE)

from typing import Dict, Any, List, Optional
from lamb.completions.tools.base import ToolDefinition
import importlib
import os
import glob
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Central registry for available multi-tool plugins"""
    
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
                
                if hasattr(module, "get_definition"):
                    definition = module.get_definition()
                    self._tools[definition.name] = {
                        "definition": definition,
                        "module": module
                    }
                    logger.info(f"Registered tool: {definition.name}")
                    
            except Exception as e:
                logger.error(f"Failed to load tool {module_name}: {e}")
        
        self._loaded = True
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        self.discover_tools()
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
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
                "config_schema": definition.config_schema
            })
        
        return definitions

# Global instance
tool_registry = ToolRegistry()
```

### 3.7 New API Endpoints

```python
# Add to lamb/completions/main.py

@router.get("/tools")
async def list_available_tools(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    List all available tools for multi-tool assistants.
    """
    from lamb.completions.tool_registry import tool_registry
    return {"tools": tool_registry.get_tool_definitions()}


@router.get("/tools/{tool_name}")
async def get_tool_definition(tool_name: str):
    """Get definition for a specific tool."""
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
        "config_schema": definition.config_schema
    }
```

---

## 4. Frontend Architecture

### 4.1 Routing Strategy: Separate UI Components

The frontend will have **separate components** for classic and multi-tool assistants:

```
frontend/svelte-app/src/lib/
├── components/
│   ├── assistants/                      # UNCHANGED - Classic assistants
│   │   ├── AssistantForm.svelte         # Classic create/edit form
│   │   ├── AssistantList.svelte         # Shows all assistants
│   │   ├── AssistantCard.svelte         # Card component
│   │   └── AssistantSharing.svelte      # Sharing modal
│   │
│   └── multi-tool-assistants/           # NEW - Multi-tool assistants
│       ├── MultiToolAssistantForm.svelte    # Multi-tool create/edit form
│       ├── MultiToolAssistantView.svelte    # Multi-tool view/detail
│       ├── tools/                           # Tool management components
│       │   ├── ToolsManager.svelte
│       │   ├── ToolSelector.svelte
│       │   ├── ToolConfigList.svelte
│       │   ├── ToolConfigCard.svelte
│       │   └── plugins/                     # Tool-specific config UIs
│       │       ├── index.js
│       │       ├── SimpleRagToolConfig.svelte      # Matches simple_rag
│       │       ├── RubricRagToolConfig.svelte      # Matches rubric_rag
│       │       └── SingleFileRagToolConfig.svelte  # Matches single_file_rag
│       └── PlaceholderManager.svelte        # Dynamic placeholder UI
│
├── routes/
│   ├── assistants/                      # UNCHANGED - Classic routes
│   │   ├── +page.svelte                 # List all assistants
│   │   ├── create/+page.svelte          # Create classic assistant
│   │   └── [id]/+page.svelte            # View/edit classic assistant
│   │
│   └── multi-tool-assistants/           # NEW - Multi-tool routes
│       ├── +page.svelte                 # List multi-tool assistants
│       ├── create/+page.svelte          # Create multi-tool assistant
│       └── [id]/+page.svelte            # View/edit multi-tool assistant
│
├── stores/
│   ├── assistantConfigStore.js          # UNCHANGED - Classic config
│   └── multiToolStore.js                # NEW - Multi-tool state
│
└── services/
    ├── assistantService.js              # UNCHANGED - Classic API calls
    └── multiToolAssistantService.js     # NEW - Multi-tool API calls
```

### 4.2 Assistant Type Selection UI

When creating a new assistant, users first choose the type:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Create New Assistant                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Choose assistant type:                                             │
│                                                                      │
│   ┌─────────────────────────────────┐  ┌─────────────────────────────┐
│   │                                 │  │                             │
│   │     📚 Classic Assistant        │  │   🔧 Multi-Tool Assistant   │
│   │                                 │  │                             │
│   │  Single RAG processor           │  │  Multiple tools per request │
│   │  • Knowledge Base OR            │  │  • Knowledge Base +         │
│   │  • Rubric OR                    │  │  • Rubric +                 │
│   │  • Single File                  │  │  • Single File              │
│   │                                 │  │  • And more...              │
│   │  Best for: Simple Q&A,          │  │                             │
│   │  basic assistants               │  │  Best for: Complex tasks,   │
│   │                                 │  │  evaluation, multi-source   │
│   │         [Select]                │  │                             │
│   │                                 │  │         [Select]            │
│   └─────────────────────────────────┘  └─────────────────────────────┘
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Assistant List with Type Badge

```
┌─────────────────────────────────────────────────────────────────────┐
│  My Assistants                                         [+ Create]    │
├─────────────────────────────────────────────────────────────────────┤
│  Filter: [All ▼]  [Classic] [Multi-Tool]                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 📚 CS101 Study Helper                           [CLASSIC]     │  │
│  │ Uses: Knowledge Base                                          │  │
│  │ Created: Dec 1, 2025                           [Edit] [Chat]  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 🔧 Essay Evaluator                              [MULTI-TOOL]  │  │
│  │ Tools: simple_rag + rubric_rag                                │  │
│  │ Created: Dec 5, 2025                           [Edit] [Chat]  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 📚 Python Tutor                                 [CLASSIC]     │  │
│  │ Uses: Single File                                             │  │
│  │ Created: Dec 8, 2025                           [Edit] [Chat]  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Multi-Tool Assistant Form

```svelte
<!-- MultiToolAssistantForm.svelte -->
<script>
    import ToolsManager from './tools/ToolsManager.svelte';
    import PlaceholderManager from './PlaceholderManager.svelte';
    
    // Form state
    let name = $state('');
    let description = $state('');
    let systemPrompt = $state('');
    let promptTemplate = $state('');
    let tools = $state([]);
    let connector = $state('openai');
    let llm = $state('gpt-4o-mini');
    
    // Derived: available placeholders based on enabled tools
    let availablePlaceholders = $derived(
        tools
            .filter(t => t.enabled)
            .map(t => t.placeholder)
            .concat(['{user_input}'])
    );
    
    function handleToolsChange(newTools) {
        tools = newTools;
    }
    
    async function handleSubmit() {
        const metadata = {
            assistant_type: "multi_tool",  // KEY: Identifies as multi-tool
            prompt_processor: "multi_augment",
            connector,
            llm,
            tools
        };
        
        // Call API to create/update
        await createMultiToolAssistant({
            name,
            description,
            system_prompt: systemPrompt,
            prompt_template: promptTemplate,
            metadata: JSON.stringify(metadata)
        });
    }
</script>

<form on:submit|preventDefault={handleSubmit}>
    <h1>Create Multi-Tool Assistant</h1>
    
    <!-- Basic Info -->
    <section class="basic-info">
        <label>
            Name
            <input bind:value={name} required />
        </label>
        
        <label>
            Description
            <textarea bind:value={description} />
        </label>
    </section>
    
    <!-- Model Selection -->
    <section class="model-config">
        <label>
            Connector
            <select bind:value={connector}>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama</option>
            </select>
        </label>
        
        <label>
            Model
            <select bind:value={llm}>
                <option value="gpt-4o-mini">GPT-4o Mini</option>
                <option value="gpt-4o">GPT-4o</option>
            </select>
        </label>
    </section>
    
    <!-- Tools Configuration (NEW) -->
    <section class="tools-config">
        <h2>🔧 Tools</h2>
        <ToolsManager 
            {tools} 
            onchange={handleToolsChange} 
        />
    </section>
    
    <!-- Prompts -->
    <section class="prompts">
        <label>
            System Prompt
            <textarea bind:value={systemPrompt} />
        </label>
        
        <label>
            Prompt Template
            <PlaceholderManager 
                placeholders={availablePlaceholders} 
                ontoggle={(p) => promptTemplate += p}
            />
            <textarea bind:value={promptTemplate} />
        </label>
    </section>
    
    <button type="submit">Create Assistant</button>
</form>
```

### 4.5 ToolsManager Component

```svelte
<!-- tools/ToolsManager.svelte -->
<script>
    import ToolSelector from './ToolSelector.svelte';
    import ToolConfigCard from './ToolConfigCard.svelte';
    import { TOOL_PLUGINS, getAllPlugins } from './plugins';
    
    let {
        tools = [],
        disabled = false,
        onchange = () => {}
    } = $props();
    
    let availableTools = getAllPlugins();
    
    function handleAddTool(toolType) {
        const plugin = TOOL_PLUGINS[toolType];
        if (!plugin) return;
        
        const newTool = {
            type: toolType,
            enabled: true,
            placeholder: plugin.placeholder,
            config: { ...plugin.defaultConfig }
        };
        
        onchange([...tools, newTool]);
    }
    
    function handleRemoveTool(index) {
        const newTools = [...tools];
        newTools.splice(index, 1);
        onchange(newTools);
    }
    
    function handleUpdateTool(index, newConfig) {
        const newTools = [...tools];
        newTools[index] = { ...newTools[index], config: newConfig };
        onchange(newTools);
    }
    
    function handleToggleTool(index) {
        const newTools = [...tools];
        newTools[index] = { 
            ...newTools[index], 
            enabled: !newTools[index].enabled 
        };
        onchange(newTools);
    }
</script>

<div class="tools-manager">
    <div class="tools-header">
        <span>Configure tools for your assistant</span>
        <ToolSelector 
            {availableTools}
            activeTools={tools}
            onadd={handleAddTool}
            {disabled}
        />
    </div>
    
    {#if tools.length === 0}
        <div class="no-tools">
            <p>No tools configured. Click "Add Tool" to get started.</p>
            <p class="hint">
                Tools inject content into placeholders like {'{context}'}, 
                {'{rubric}'}, {'{file}'} in your prompt template.
            </p>
        </div>
    {:else}
        <div class="tools-list">
            {#each tools as tool, index (index)}
                <ToolConfigCard
                    {tool}
                    {index}
                    {disabled}
                    onupdate={(config) => handleUpdateTool(index, config)}
                    onremove={() => handleRemoveTool(index)}
                    ontoggle={() => handleToggleTool(index)}
                />
            {/each}
        </div>
    {/if}
</div>

<style>
    .tools-manager {
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 1rem;
    }
    
    .tools-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .no-tools {
        text-align: center;
        padding: 2rem;
        color: #64748b;
    }
    
    .hint {
        font-size: 0.875rem;
        margin-top: 0.5rem;
    }
    
    .tools-list {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
</style>
```

### 4.6 Tool Plugin Registry

```javascript
// tools/plugins/index.js
// NOTE: Tool names match classic RAG processors for consistency

import SimpleRagToolConfig from './SimpleRagToolConfig.svelte';
import RubricRagToolConfig from './RubricRagToolConfig.svelte';
import SingleFileRagToolConfig from './SingleFileRagToolConfig.svelte';

export const TOOL_PLUGINS = {
    // Names match classic RAG processors
    simple_rag: {
        component: SimpleRagToolConfig,
        name: 'Knowledge Base RAG',
        icon: '🗂️',
        description: 'Query knowledge bases for relevant context',
        placeholder: '{context}',
        defaultConfig: {
            collections: [],
            top_k: 3
        },
        allowMultiple: false
    },
    rubric_rag: {
        component: RubricRagToolConfig,
        name: 'Rubric',
        icon: '📋',
        description: 'Include assessment rubric in context',
        placeholder: '{rubric}',
        defaultConfig: {
            rubric_id: null,
            format: 'markdown'
        },
        allowMultiple: false
    },
    single_file_rag: {
        component: SingleFileRagToolConfig,
        name: 'Single File',
        icon: '📄',
        description: 'Include contents of a single file',
        placeholder: '{file}',
        defaultConfig: {
            file_path: ''
        },
        allowMultiple: false
    }
};

export function getPluginComponent(toolType) {
    return TOOL_PLUGINS[toolType]?.component || null;
}

export function getAllPlugins() {
    return Object.entries(TOOL_PLUGINS).map(([type, meta]) => ({
        type,
        ...meta
    }));
}
```

### 4.7 Multi-Tool Assistant Service

```javascript
// services/multiToolAssistantService.js

import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * Create a new multi-tool assistant
 */
export async function createMultiToolAssistant(assistantData) {
    if (!browser) return null;
    
    const token = localStorage.getItem('userToken');
    if (!token) throw new Error('Not authenticated');
    
    // Ensure assistant_type is set
    let metadata = assistantData.metadata;
    if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata);
    }
    metadata.assistant_type = 'multi_tool';
    metadata.prompt_processor = 'multi_augment';
    
    const payload = {
        ...assistantData,
        metadata: JSON.stringify(metadata)
    };
    
    const response = await fetch(getApiUrl('/assistants'), {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
        throw new Error('Failed to create multi-tool assistant');
    }
    
    return await response.json();
}

/**
 * Get available tools from backend
 */
export async function getAvailableTools() {
    if (!browser) return [];
    
    const token = localStorage.getItem('userToken');
    if (!token) throw new Error('Not authenticated');
    
    try {
        const response = await fetch(getApiUrl('/completions/tools'), {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch tools');
        }
        
        const data = await response.json();
        return data.tools || [];
    } catch (error) {
        console.error('Error fetching tools:', error);
        return [];
    }
}

/**
 * Check if an assistant is multi-tool type
 */
export function isMultiToolAssistant(assistant) {
    if (!assistant?.metadata) return false;
    
    let metadata = assistant.metadata;
    if (typeof metadata === 'string') {
        try {
            metadata = JSON.parse(metadata);
        } catch {
            return false;
        }
    }
    
    return metadata.assistant_type === 'multi_tool';
}
```

---

## 5. Data Model

### 5.1 Classic Assistant Metadata (UNCHANGED)

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "rag_processor": "simple_rag",
    "file_path": "",
    "rubric_id": "",
    "rubric_format": "markdown",
    "capabilities": {
        "vision": false,
        "image_generation": false
    }
}
```

### 5.2 Multi-Tool Assistant Metadata (NEW)

```json
{
    "assistant_type": "multi_tool",
    "prompt_processor": "multi_augment",
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
                "top_k": 5
            }
        },
        {
            "type": "rubric_rag",
            "enabled": true,
            "config": {
                "rubric_id": 42,
                "format": "markdown"
            }
        },
        {
            "type": "single_file_rag",
            "enabled": false,
            "config": {
                "file_path": "documents/guide.md"
            }
        }
    ]
}
```

### 5.3 Key Differences

| Field | Classic | Multi-Tool |
|-------|---------|------------|
| `assistant_type` | absent or `"classic"` | `"multi_tool"` |
| `prompt_processor` | `"simple_augment"` | `"multi_augment"` |
| `rag_processor` | `"simple_rag"`, etc. | absent |
| `tools` | absent | array of tool configs |

---

## 6. Assistant Type Detection

### 6.1 Backend Detection

```python
def get_assistant_type(metadata: Dict[str, Any]) -> str:
    """
    Determine assistant type from metadata.
    Returns: "classic" or "multi_tool"
    """
    assistant_type = metadata.get("assistant_type")
    
    if assistant_type == "multi_tool":
        return "multi_tool"
    
    # Default to classic for any other value or missing field
    return "classic"
```

### 6.2 Frontend Detection

```javascript
function getAssistantType(assistant) {
    if (!assistant?.metadata) return 'classic';
    
    let metadata = assistant.metadata;
    if (typeof metadata === 'string') {
        try {
            metadata = JSON.parse(metadata);
        } catch {
            return 'classic';
        }
    }
    
    return metadata.assistant_type === 'multi_tool' ? 'multi_tool' : 'classic';
}
```

### 6.3 Routing Based on Type

**Backend:**
```python
# In completion endpoint
if get_assistant_type(metadata) == "multi_tool":
    return get_multi_tool_completion(request, assistant, metadata)
else:
    return get_classic_completion(request, assistant, metadata)
```

**Frontend:**
```javascript
// In assistant list/view
if (getAssistantType(assistant) === 'multi_tool') {
    goto(`/multi-tool-assistants/${assistant.id}`);
} else {
    goto(`/assistants/${assistant.id}`);
}
```

---

## 7. Implementation Plan

### 7.1 Phase 1: Backend Core (Week 1-2)

| # | Task | Priority | Est. |
|---|------|----------|------|
| B1 | Create `completions/tools/` directory | HIGH | 1h |
| B2 | Implement `tools/base.py` with interfaces | HIGH | 2h |
| B3 | Implement `tool_registry.py` | HIGH | 3h |
| B4 | Implement `tool_orchestrator.py` | HIGH | 4h |
| B5 | Implement `tools/simple_rag.py` | HIGH | 3h |
| B6 | Implement `tools/rubric.py` | HIGH | 2h |
| B7 | Implement `tools/single_file.py` | HIGH | 2h |
| B8 | Implement `tools/no_tool.py` | MED | 1h |

### 7.2 Phase 2: Backend Pipeline (Week 2)

| # | Task | Priority | Est. |
|---|------|----------|------|
| B9 | Create `multi-tool-pps/` directory | HIGH | 1h |
| B10 | Implement `multi_augment.py` | HIGH | 4h |
| B11 | Add type-based routing to `main.py` | HIGH | 3h |
| B12 | Add `/tools` API endpoint | HIGH | 2h |
| B13 | Add `/tools/{name}` API endpoint | MED | 1h |

### 7.3 Phase 3: Frontend Core (Week 3)

| # | Task | Priority | Est. |
|---|------|----------|------|
| F1 | Create `multi-tool-assistants/` directory | HIGH | 1h |
| F2 | Implement plugin registry `plugins/index.js` | HIGH | 2h |
| F3 | Implement `ToolsManager.svelte` | HIGH | 4h |
| F4 | Implement `ToolSelector.svelte` | HIGH | 2h |
| F5 | Implement `ToolConfigCard.svelte` | HIGH | 3h |
| F6 | Implement `KnowledgeBaseToolConfig.svelte` | HIGH | 3h |
| F7 | Implement `RubricToolConfig.svelte` | HIGH | 2h |
| F8 | Implement `SingleFileToolConfig.svelte` | HIGH | 2h |

### 7.4 Phase 4: Frontend Integration (Week 4)

| # | Task | Priority | Est. |
|---|------|----------|------|
| F9 | Implement `MultiToolAssistantForm.svelte` | HIGH | 6h |
| F10 | Implement `MultiToolAssistantView.svelte` | HIGH | 4h |
| F11 | Create routes for multi-tool assistants | HIGH | 2h |
| F12 | Implement `multiToolAssistantService.js` | HIGH | 3h |
| F13 | Update `AssistantList.svelte` for type badges | MED | 2h |
| F14 | Add assistant type selection UI | HIGH | 3h |
| F15 | Implement `PlaceholderManager.svelte` | MED | 2h |

### 7.5 Phase 5: Testing & Polish (Week 5)

| # | Task | Priority | Est. |
|---|------|----------|------|
| T1 | Backend unit tests for tool registry | HIGH | 3h |
| T2 | Backend unit tests for tool orchestrator | HIGH | 3h |
| T3 | Backend integration tests for multi-tool pipeline | HIGH | 4h |
| T4 | Frontend component tests | HIGH | 4h |
| T5 | E2E tests for multi-tool flow | HIGH | 4h |
| T6 | UI polish and accessibility | MED | 4h |
| T7 | Documentation | MED | 3h |

### 7.6 Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | Week 1-2 | Tool plugins and registry |
| Phase 2 | Week 2 | Multi-tool pipeline |
| Phase 3 | Week 3 | Frontend components |
| Phase 4 | Week 4 | Full integration |
| Phase 5 | Week 5 | Testing and polish |
| **Total** | **5 weeks** | Full multi-tool system |

---

## 8. Testing Strategy

### 8.1 Backend Tests

```python
# tests/test_tool_orchestrator.py

def test_single_tool_execution():
    """Test single tool execution returns correct placeholder"""
    orchestrator = ToolOrchestrator()
    request = {"messages": [{"role": "user", "content": "test"}]}
    assistant = create_test_assistant()
    tools = [{"type": "simple_rag", "enabled": True, "config": {"collections": []}}]
    
    results = orchestrator.execute_tools(request, assistant, tools)
    
    assert "context" in results
    assert isinstance(results["context"], ToolResult)


def test_multi_tool_execution():
    """Test multiple tools execute to different placeholders"""
    orchestrator = ToolOrchestrator()
    request = {"messages": [{"role": "user", "content": "test"}]}
    assistant = create_test_assistant()
    tools = [
        {"type": "simple_rag", "enabled": True, "config": {"collections": []}},
        {"type": "rubric_rag", "enabled": True, "config": {"rubric_id": 1}}
    ]
    
    results = orchestrator.execute_tools(request, assistant, tools)
    
    assert "context" in results  # simple_rag
    assert "rubric" in results   # rubric_rag


def test_disabled_tool_skipped():
    """Test disabled tools are not executed"""
    orchestrator = ToolOrchestrator()
    tools = [
        {"type": "simple_rag", "enabled": False, "config": {}}
    ]
    
    results = orchestrator.execute_tools({}, None, tools)
    
    assert len(results) == 0


def test_type_routing_classic():
    """Test classic assistant uses classic pipeline"""
    metadata = {"rag_processor": "simple_rag"}
    assert get_assistant_type(metadata) == "classic"


def test_type_routing_multi_tool():
    """Test multi-tool assistant uses multi-tool pipeline"""
    metadata = {"assistant_type": "multi_tool", "tools": []}
    assert get_assistant_type(metadata) == "multi_tool"
```

### 8.2 Frontend Tests

```javascript
// tests/multi-tool-assistant.spec.js

test('can create multi-tool assistant with multiple tools', async ({ page }) => {
    await page.goto('/multi-tool-assistants/create');
    
    // Fill basic info
    await page.fill('[data-testid="name-input"]', 'Test Multi-Tool');
    
    // Add Knowledge Base tool
    await page.click('[data-testid="add-tool-btn"]');
    await page.click('[data-testid="tool-option-simple_rag"]');
    
    // Add Rubric tool
    await page.click('[data-testid="add-tool-btn"]');
    await page.click('[data-testid="tool-option-rubric_rag"]');
    
    // Verify both tools visible
    expect(await page.locator('[data-testid="tool-card"]').count()).toBe(2);
    
    // Save
    await page.click('[data-testid="save-btn"]');
    await expect(page.locator('.success-message')).toBeVisible();
});


test('classic assistant loads in classic UI', async ({ page }) => {
    // Load a classic assistant
    await page.goto('/assistants/123');  // Classic assistant ID
    
    // Should see RAG processor dropdown, not tools manager
    await expect(page.locator('[data-testid="rag-processor-select"]')).toBeVisible();
    await expect(page.locator('[data-testid="tools-manager"]')).not.toBeVisible();
});


test('multi-tool assistant loads in multi-tool UI', async ({ page }) => {
    // Load a multi-tool assistant
    await page.goto('/multi-tool-assistants/456');  // Multi-tool assistant ID
    
    // Should see tools manager, not RAG processor dropdown
    await expect(page.locator('[data-testid="tools-manager"]')).toBeVisible();
    await expect(page.locator('[data-testid="rag-processor-select"]')).not.toBeVisible();
});


test('assistant list shows correct type badges', async ({ page }) => {
    await page.goto('/assistants');
    
    // Should show type badges
    await expect(page.locator('[data-testid="type-badge-classic"]')).toBeVisible();
    await expect(page.locator('[data-testid="type-badge-multi_tool"]')).toBeVisible();
});
```

### 8.3 Integration Tests

```python
# tests/test_multi_tool_integration.py

async def test_full_multi_tool_completion():
    """Test complete multi-tool completion flow"""
    # Create multi-tool assistant
    assistant_data = {
        "name": "Test Multi-Tool",
        "metadata": json.dumps({
            "assistant_type": "multi_tool",
            "prompt_processor": "multi_augment",
            "connector": "openai",
            "llm": "gpt-4o-mini",
            "tools": [
                {"type": "simple_rag", "enabled": True, "config": {"collections": ["test-col"]}},
                {"type": "rubric_rag", "enabled": True, "config": {"rubric_id": 1}}
            ]
        })
    }
    
    # Create assistant
    response = await client.post("/assistants", json=assistant_data)
    assert response.status_code == 200
    assistant_id = response.json()["id"]
    
    # Send completion request
    completion_request = {
        "messages": [{"role": "user", "content": "Evaluate my essay"}]
    }
    response = await client.post(
        f"/completions?assistant_id={assistant_id}",
        json=completion_request
    )
    
    assert response.status_code == 200
    # Response should include content from both tools
```

---

## 9. Future Considerations

### 9.1 Potential Enhancements (Post-MVP)

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Tool Ordering | Allow users to specify tool execution order | LOW |
| Parallel Execution | Execute independent tools in parallel | MED |
| Tool Dependencies | Define tools that depend on other tools | LOW |
| Custom Tools | Allow users to create custom tools | MED |
| Tool Templates | Pre-defined tool combinations | LOW |
| Classic → Multi-Tool Conversion | Optional user-initiated conversion | POST-MVP |

### 9.2 Tool Extension Points

New tools can be added by:

1. Creating a new file in `completions/tools/`
2. Implementing `BaseTool` interface
3. Adding entry to frontend plugin registry
4. Creating frontend config component

---

## Appendix A: File Summary

### New Backend Files

| File | Purpose |
|------|---------|
| `completions/tools/__init__.py` | Package init |
| `completions/tools/base.py` | Base tool interface |
| `completions/tools/simple_rag.py` | KB RAG tool (same name as classic) |
| `completions/tools/rubric_rag.py` | Rubric tool (same name as classic) |
| `completions/tools/single_file_rag.py` | File tool (same name as classic) |
| `completions/tools/no_rag.py` | No-op tool (same name as classic) |
| `completions/multi-tool-pps/__init__.py` | Package init |
| `completions/multi-tool-pps/multi_augment.py` | Multi-placeholder PPS |
| `completions/tool_orchestrator.py` | Tool coordinator |
| `completions/tool_registry.py` | Tool discovery |

### Modified Backend Files

| File | Changes |
|------|---------|
| `completions/main.py` | Add type-based routing, new endpoints |

### New Frontend Files

| File | Purpose |
|------|---------|
| `components/multi-tool-assistants/MultiToolAssistantForm.svelte` | Create/edit form |
| `components/multi-tool-assistants/MultiToolAssistantView.svelte` | View/detail |
| `components/multi-tool-assistants/tools/ToolsManager.svelte` | Tool orchestrator |
| `components/multi-tool-assistants/tools/ToolSelector.svelte` | Add tool dropdown |
| `components/multi-tool-assistants/tools/ToolConfigCard.svelte` | Tool card wrapper |
| `components/multi-tool-assistants/tools/plugins/index.js` | Plugin registry |
| `components/multi-tool-assistants/tools/plugins/SimpleRagToolConfig.svelte` | KB config |
| `components/multi-tool-assistants/tools/plugins/RubricRagToolConfig.svelte` | Rubric config |
| `components/multi-tool-assistants/tools/plugins/SingleFileRagToolConfig.svelte` | File config |
| `components/multi-tool-assistants/PlaceholderManager.svelte` | Placeholder UI |
| `services/multiToolAssistantService.js` | API service |
| `stores/multiToolStore.js` | State management |
| `routes/multi-tool-assistants/+page.svelte` | List page |
| `routes/multi-tool-assistants/create/+page.svelte` | Create page |
| `routes/multi-tool-assistants/[id]/+page.svelte` | Edit page |

### Modified Frontend Files

| File | Changes |
|------|---------|
| `components/assistants/AssistantList.svelte` | Add type badges, filtering |
| `routes/assistants/+page.svelte` | Add "Create" type selection |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Classic Assistant** | Assistant using single RAG processor (`completions/rag/*`) |
| **Multi-Tool Assistant** | Assistant using multiple tools (`completions/tools/*`) |
| **Tool** | A configurable module that retrieves/generates content for a placeholder |
| **Plugin** | Frontend component rendering tool-specific configuration UI |
| **Placeholder** | Template variable (e.g., `{context}`) replaced with tool output |
| **Tool Registry** | Backend system for discovering and loading tools |
| **Plugin Registry** | Frontend mapping of tool types to config components |

---

**Document Status:** Draft for Review  
**Strategy:** Parallel Implementation (No Migration)  
**Author:** AI Analysis  
**Reviewers:** LAMB Development Team

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 9, 2025 | Initial parallel implementation specification |
