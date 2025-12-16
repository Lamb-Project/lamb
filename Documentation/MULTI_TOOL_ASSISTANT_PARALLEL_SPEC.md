# Multi-Tool Assistant System: Parallel Implementation Strategy

**Version:** 1.3
**Date:** December 11, 2025  
**Strategy:** Parallel Implementation (No Migration)  
**Key Architectural Changes:**
- v1.1: Plugin-based Orchestrator (eliminates separate PPS layer)
- v1.2: Sequential chained context, numbered placeholders (`{1_context}`), multiple tool instances, UI mockups  
**Related Documents:**  
- `Documentation/lamb_architecture.md` (System architecture)

> **🔄 v1.1 Architecture Update:** The orchestrator is now **plugin-based**. Strategy plugins (e.g., `parallel`, `sequential`) handle both tool execution AND placeholder replacement. The separate `multi-tool-pps/` layer has been eliminated. See Section 2.2 and 3.4 for details.

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

### 1.4 Key Design Decisions (CONFIRMED - Updated Dec 10, 2025)

| Decision | Choice |
|----------|--------|
| Classic code | **KEEP UNCHANGED** |
| Multi-tool code | **NEW PARALLEL IMPLEMENTATION** |
| Old RAG processors | `completions/rag/` (unchanged) |
| Old prompt processors | `completions/pps/` (unchanged) |
| New tool plugins | `completions/tools/` (new) |
| ~~New prompt processors~~ | ~~`completions/multi-tool-pps/`~~ → **REMOVED** (see below) |
| New orchestrator plugins | `completions/orchestrators/` (new) ← **REPLACES PPS** |
| Assistant type field | `metadata.assistant_type: "multi_tool"` ✓ |
| Orchestrator strategy field | `metadata.orchestrator: "sequential"` (default) |
| Placeholder naming | `{order}_{type}` format (e.g., `{1_context}`, `{2_rubric}`) ✓ |
| Multiple tool instances | **ALLOWED** - same tool can appear multiple times ✓ |
| Frontend routes | `/multi-tool-assistants/` for creator ✓ |
| Tool naming | **Same as classic** (`simple_rag`, `rubric_rag`, `single_file_rag`) ✓ |
| Classic → Multi-Tool conversion | **NOT IN MVP** ✓ |

> **Architecture Updates (Dec 11, 2025):**
> 1. **Plugin-based orchestrator:** Eliminates separate `multi-tool-pps/` layer
> 2. **Sequential as default:** Enables chained context where each tool sees previous outputs
> 3. **Numbered placeholders:** `{1_context}`, `{2_context}` allows multiple instances of same tool
> 4. **Drag-to-reorder UI:** Tools can be reordered; placeholders auto-renumber
> 5. **Streaming tool invocations:** Real-time progress messages during tool execution
> 6. **VERBOSE mode:** Detailed markdown execution reports for debugging and monitoring

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

> **⚠️ UPDATED ARCHITECTURE (Dec 10, 2025):** The original design had a separate "Multi-Tool PPS" layer for placeholder replacement. The new design consolidates all multi-tool logic into a **plugin-based orchestrator**, making it more flexible and eliminating the separate PPS layer.

```
MULTI-TOOL ASSISTANT PIPELINE (NEW - Plugin-Based Orchestrator)
────────────────────────────────────────────────────────────────

Request → get_assistant_details() → check assistant_type
                                          │
                        ┌─────────────────┴─────────────────┐
                        │ assistant_type == "multi_tool"?   │
                        └─────────────────┬─────────────────┘
                                          │ YES
                                          ▼
                   ┌───────────────────────────────────────────┐
                   │       PLUGIN-BASED ORCHESTRATOR           │  ← NEW
                   │  ┌─────────────────────────────────────┐  │
                   │  │ Orchestrator Strategy Plugin        │  │
                   │  │ (e.g., "parallel", "sequential",    │  │
                   │  │  "dependency", "conditional")       │  │
                   │  └─────────────────────────────────────┘  │
                   │                    │                      │
                   │                    ▼                      │
                   │  ┌─────────────────────────────────────┐  │
                   │  │     Execute Tool Plugins            │  │
                   │  │   (based on strategy)               │  │
                   │  └─────────────────────────────────────┘  │
                   └───────────────────┬───────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────┐         ┌─────────────────┐         ┌──────────────────┐
│ simple_rag      │         │ rubric_rag      │         │ single_file_rag  │
│ placeholder:    │         │ placeholder:    │         │ placeholder:     │
│   "context"     │         │   "rubric"      │         │   "file"         │
└────────┬────────┘         └────────┬────────┘         └──────┬───────────┘
          │                          │                         │
          └──────────────────────────┼─────────────────────────┘
                                     │
                                     ▼
                   ┌───────────────────────────────────────────┐
                   │       ORCHESTRATOR (continued)            │
                   │  ┌─────────────────────────────────────┐  │
                   │  │  Merge Results + Replace Placeholders│  │
                   │  │  in prompt_template:                 │  │
                   │  │    {context} → RAG content           │  │
                   │  │    {rubric}  → Rubric content        │  │
                   │  │    {file}    → File content          │  │
                   │  │    {user_input} → User message       │  │
                   │  └─────────────────────────────────────┘  │
                   └───────────────────┬───────────────────────┘
                                       │
                                       ▼
                           ┌─────────────────────┐
                           │     Connector       │
                           │     (LLM call)      │
                           └─────────────────────┘
```

#### Key Insight: Orchestrator Plugins vs. Separate PPS

**Original Design (Removed):**
- Tool Orchestrator → Multi-Tool PPS → Connector
- PPS was a separate layer just for placeholder replacement

**New Design (Plugin-Based Orchestrator):**
- Orchestrator Strategy Plugins handle BOTH tool execution AND placeholder replacement
- Orchestrator can have different strategies (parallel, sequential, dependency-based, etc.)
- Each tool plugin declares its placeholder in metadata
- Eliminates the separate `multi-tool-pps/` directory

**Benefits of New Design:**
| Aspect | Original (PPS separate) | New (Plugin-based Orchestrator) |
|--------|------------------------|--------------------------------|
| Complexity | Two separate systems | Single unified system |
| Flexibility | Fixed replacement logic | Strategy-specific replacement |
| Configuration | Split between orchestrator & PPS | All in orchestrator |
| Future extensibility | Limited | Can add new strategies as plugins |

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
├── orchestrators/                   # NEW - Orchestrator strategy plugins
│   ├── __init__.py
│   ├── base.py                      # Base orchestrator interface
│   ├── parallel.py                  # Execute all tools in parallel
│   ├── sequential.py                # Execute tools one by one
│   └── dependency.py                # Execute based on tool dependencies
│
├── tool_orchestrator.py             # NEW - Orchestrator engine (loads strategy plugins)
└── tool_registry.py                 # NEW - Tool discovery and metadata
```

> **Note:** The `multi-tool-pps/` directory is **NOT needed** in the new design. Placeholder replacement is handled directly by orchestrator strategy plugins.

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
    Uses completions/tools/* and completions/orchestrators/*
    
    NOTE: No separate PPS call! The orchestrator handles:
    - Tool execution (via strategy plugin)
    - Placeholder replacement
    - Message building
    """
    # Set up streaming and verbose options
    verbose = metadata.get("verbose", False)
    stream_mode = request.get("stream", False)

    # Set up stream callback if streaming is enabled
    stream_callback = None
    if stream_mode and verbose:
        # For streaming verbose mode, we'll collect progress messages
        progress_messages = []

        def progress_callback(message: str):
            progress_messages.append(message)
            # In streaming mode, we could send these as SSE events
            # For now, we'll collect them and include in the final verbose report

        stream_callback = progress_callback

    # Orchestrator handles everything: tools + placeholders
    orchestrator = ToolOrchestrator()
    result = orchestrator.orchestrate(request, assistant, metadata, verbose=verbose, stream_callback=stream_callback)

    if result.error:
        logger.error(f"Multi-tool orchestration failed: {result.error}")
        # Return error message in a user message format
        return [{
            "role": "user",
            "content": f"Error in multi-tool processing: {result.error}"
        }], []

    # In verbose mode, return the verbose report instead of processed messages
    if verbose and result.verbose_report:
        return [{
            "role": "user",
            "content": result.verbose_report
        }], result.sources

    # Result contains processed messages ready for LLM
    # - result.processed_messages: Messages with placeholders replaced
    # - result.sources: Aggregated sources from all tools
    # - result.tool_results: Raw tool outputs (for debugging/logging)

    # Call LLM connector with processed messages
    connector = metadata.get("connector", "openai")
    return call_connector(connector, result.processed_messages, metadata, result.sources)
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

### 3.4 Plugin-Based Tool Orchestrator

> **⚠️ UPDATED (Dec 10, 2025):** The orchestrator is now plugin-based. Strategy plugins handle both tool execution sequencing AND placeholder replacement.

#### 3.4.1 Orchestrator Strategy Base Interface

```python
# lamb/completions/orchestrators/base.py (NEW FILE)

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from lamb.lamb_classes import Assistant

@dataclass
class OrchestrationResult:
    """Result from orchestrator after all tools executed and placeholders replaced"""
    processed_messages: List[Dict[str, str]]  # Messages ready for LLM
    sources: List[Dict[str, Any]]             # Aggregated sources from all tools
    tool_results: Dict[str, Any]              # Raw results from each tool (for debugging)
    error: Optional[str] = None
    verbose_report: Optional[str] = None      # Detailed markdown report when verbose=True

@dataclass
class ToolConfig:
    """Tool configuration from assistant metadata"""
    plugin: str           # Tool plugin name (e.g., "simple_rag")
    placeholder: str      # Placeholder this tool fills (e.g., "context")
    enabled: bool = True
    config: Dict[str, Any] = None  # Tool-specific configuration

class BaseOrchestrator(ABC):
    """
    Abstract base class for orchestrator strategy plugins.
    
    Orchestrators are responsible for:
    1. Executing tool plugins (in strategy-specific order)
    2. Collecting results from each tool
    3. Replacing placeholders in the prompt template
    4. Preparing final messages for the LLM connector
    """
    
    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """Return unique identifier for this orchestrator strategy"""
        pass
    
    @classmethod
    def get_description(cls) -> str:
        """Return human-readable description"""
        return "Base orchestrator strategy"
    
    @abstractmethod
    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> OrchestrationResult:
        """
        Execute all tools and prepare messages for LLM.

        Args:
            request: The completion request
            assistant: The assistant object
            tool_configs: List of tool configurations
            verbose: If True, return detailed markdown report instead of processed messages
            stream_callback: Optional callback function for streaming progress updates

        This method should:
        1. Execute enabled tools according to the strategy
        2. Collect tool outputs with their placeholders
        3. Replace placeholders in assistant.prompt_template
        4. Return processed messages ready for the connector (or verbose report)
        """
        pass
    
    def _replace_placeholders(
        self, 
        template: str, 
        tool_results: Dict[str, str],
        user_input: str
    ) -> str:
        """
        Common placeholder replacement logic.
        Subclasses can override for custom behavior.
        """
        result = template
        
        # Replace tool placeholders
        for placeholder, content in tool_results.items():
            tag = "{" + placeholder + "}"
            if tag in result:
                result = result.replace(tag, "\n\n" + content + "\n\n" if content else "")
        
        # Replace user input
        result = result.replace("{user_input}", "\n\n" + user_input + "\n\n")
        
        # Clean up unreplaced placeholders
        import re
        result = re.sub(r'\{[a-z_]+\}', '', result)
        
        return result

    def _generate_verbose_report(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        tool_results: Dict[str, Any],
        all_sources: List[Dict[str, Any]],
        final_messages: List[Dict[str, str]]
    ) -> str:
        """Generate a detailed markdown report for verbose mode."""

        import json
        from datetime import datetime

        report_lines = [
            "# Multi-Tool Orchestration Report",
            f"**Timestamp:** {datetime.now().isoformat()}",
            f"**Orchestrator:** {self.get_name()}",
            f"**Assistant:** {assistant.name if hasattr(assistant, 'name') else 'Unknown'}",
            "",
            "## Request Summary",
            f"- **User Message:** {self._extract_user_text(request.get('messages', [{}])[-1].get('content', ''))[:200]}{'...' if len(self._extract_user_text(request.get('messages', [{}])[-1].get('content', ''))) > 200 else ''}",
            f"- **Stream Mode:** {request.get('stream', False)}",
            "",
            "## Tool Configuration",
        ]

        for i, tool_config in enumerate(tool_configs, 1):
            report_lines.extend([
                f"### Tool {i}: {tool_config.plugin}",
                f"- **Placeholder:** `{tool_config.placeholder}`",
                f"- **Enabled:** {tool_config.enabled}",
                f"- **Configuration:**",
                "```json",
                json.dumps(tool_config.config or {}, indent=2),
                "```",
                ""
            ])

        report_lines.extend([
            "## Tool Execution Results",
        ])

        for placeholder, result in tool_results.items():
            tool_name = placeholder.split('_', 1)[1] if '_' in placeholder else placeholder
            report_lines.extend([
                f"### {placeholder} ({tool_name})",
                f"- **Content Length:** {len(result) if result else 0} characters",
                f"- **Has Sources:** {bool(result)}",
                f"- **Content Preview:**",
                "```",
                (result[:500] + "..." if result and len(result) > 500 else result or "No content") if result else "No content",
                "```",
                ""
            ])

        report_lines.extend([
            "## Sources Summary",
            f"- **Total Sources:** {len(all_sources)}",
        ])

        if all_sources:
            for i, source in enumerate(all_sources[:10], 1):  # Show first 10 sources
                report_lines.extend([
                    f"### Source {i}",
                    f"- **Title:** {source.get('title', 'Unknown')}",
                    f"- **URL:** {source.get('url', 'N/A')}",
                    f"- **Similarity:** {source.get('similarity', 'N/A')}",
                    ""
                ])

            if len(all_sources) > 10:
                report_lines.append(f"*... and {len(all_sources) - 10} more sources*\n")

        report_lines.extend([
            "## Final Messages Sent to LLM",
        ])

        for i, msg in enumerate(final_messages):
            role = msg.get('role', 'unknown')
            content_preview = msg.get('content', '')[:300] + ('...' if len(msg.get('content', '')) > 300 else '')
            report_lines.extend([
                f"### Message {i+1} ({role})",
                f"```\n{content_preview}\n```",
                ""
            ])

        return "\n".join(report_lines)

    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)
```

#### 3.4.2 Parallel Orchestrator Strategy

```python
# lamb/completions/orchestrators/parallel.py (NEW FILE)

import asyncio
from typing import Dict, Any, List
from lamb.completions.orchestrators.base import BaseOrchestrator, OrchestrationResult, ToolConfig
from lamb.completions.tool_registry import tool_registry
from lamb.lamb_classes import Assistant
import logging

logger = logging.getLogger(__name__)

class ParallelOrchestrator(BaseOrchestrator):
    """
    Execute all tools in parallel (concurrently).
    Best for independent tools that don't depend on each other.

    ADDITIONAL FEATURES:
    - Streaming: Emits progress messages during parallel tool execution
    - VERBOSE mode: Returns detailed markdown report instead of processed messages
    """

    @classmethod
    def get_name(cls) -> str:
        return "parallel"

    @classmethod
    def get_description(cls) -> str:
        return "Execute all tools concurrently for maximum speed"

    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """Execute all enabled tools in parallel, then replace placeholders."""
        
        # Filter enabled tools
        enabled_tools = [t for t in tool_configs if t.enabled]
        
        # Execute all tools concurrently
        tool_results = {}
        all_sources = []
        
        # Use asyncio.gather for parallel execution
        async def run_all():
            tasks = []
            for tool_config in enabled_tools:
                tasks.append(self._execute_tool(request, assistant, tool_config))
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = asyncio.run(run_all())
        
        # Collect results
        for tool_config, result in zip(enabled_tools, results):
            if isinstance(result, Exception):
                logger.error(f"Tool {tool_config.plugin} failed: {result}")
                continue
            
            placeholder = tool_config.placeholder
            tool_results[placeholder] = result.get("content", "")
            if result.get("sources"):
                all_sources.extend(result["sources"])
        
        # Build processed messages
        messages = request.get('messages', [])
        processed_messages = self._build_messages(
            assistant, messages, tool_results
        )
        
        return OrchestrationResult(
            processed_messages=processed_messages,
            sources=all_sources,
            tool_results=tool_results
        )
    
    async def _execute_tool(self, request, assistant, tool_config: ToolConfig):
        """Execute a single tool plugin."""
        tool = tool_registry.get_tool(tool_config.plugin)
        if not tool:
            raise ValueError(f"Tool plugin '{tool_config.plugin}' not found")
        
        module = tool["module"]
        return module.tool_processor(request, assistant, tool_config.config or {})
    
    def _build_messages(
        self, 
        assistant: Assistant, 
        messages: List[Dict], 
        tool_results: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Build final messages with placeholders replaced."""
        
        processed = []
        
        # Add system prompt
        if assistant.system_prompt:
            processed.append({
                "role": "system",
                "content": assistant.system_prompt
            })
        
        # Add conversation history (all but last)
        if len(messages) > 1:
            processed.extend(messages[:-1])
        
        # Process last message with template
        if messages:
            last_message = messages[-1]
            user_input = self._extract_user_text(last_message.get("content", ""))
            
            if assistant.prompt_template:
                content = self._replace_placeholders(
                    assistant.prompt_template,
                    tool_results,
                    user_input
                )
            else:
                content = user_input
            
            processed.append({
                "role": last_message.get("role", "user"),
                "content": content
            })
        
        return processed
    
    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)


# Module-level function for orchestrator registry
def get_orchestrator():
    return ParallelOrchestrator()

def get_name():
    return ParallelOrchestrator.get_name()

def get_description():
    return ParallelOrchestrator.get_description()
```

#### 3.4.3 Sequential Orchestrator Strategy (with Chained Context)

```python
# lamb/completions/orchestrators/sequential.py (NEW FILE)

from typing import Dict, Any, List
from lamb.completions.orchestrators.base import BaseOrchestrator, OrchestrationResult, ToolConfig
from lamb.completions.tool_registry import tool_registry
from lamb.lamb_classes import Assistant
import logging
import re

logger = logging.getLogger(__name__)

class SequentialOrchestrator(BaseOrchestrator):
    """
    Execute tools one after another in order defined in metadata.

    KEY FEATURE: Each tool sees the prompt with PREVIOUS placeholders already replaced.
    This enables chained context where later tools can see earlier tool outputs.

    ADDITIONAL FEATURES:
    - Streaming: Emits progress messages during tool execution when stream_callback provided
    - VERBOSE mode: Returns detailed markdown report instead of processed messages
    """

    @classmethod
    def get_name(cls) -> str:
        return "sequential"

    @classmethod
    def get_description(cls) -> str:
        return "Execute tools in order; each tool sees previous outputs (chained context)"

    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """
        Execute tools sequentially with chained context.
        
        For each tool:
        1. Build current context (template with previous placeholders filled)
        2. Execute tool with this context visible
        3. Replace this tool's placeholder
        4. Move to next tool
        """
        
        tool_results = {}
        all_sources = []
        
        # Start with the original template
        current_template = assistant.prompt_template or ""
        user_input = self._extract_user_text(
            request.get('messages', [{}])[-1].get('content', '')
        )
        
        for tool_config in tool_configs:
            if not tool_config.enabled:
                continue

            try:
                tool = tool_registry.get_tool(tool_config.plugin)
                if not tool:
                    logger.warning(f"Tool plugin '{tool_config.plugin}' not found")
                    continue

                module = tool["module"]

                # Stream progress: tool starting
                if stream_callback:
                    stream_callback(f"🔄 Executing tool: {tool_config.plugin} → {tool_config.placeholder}")

                # CHAINED CONTEXT: Pass current template state to tool
                # Tool can see previous placeholders already filled
                augmented_request = {
                    **request,
                    "_current_context": current_template,  # Template with previous fills
                    "_accumulated_results": tool_results.copy()
                }

                result = module.tool_processor(
                    augmented_request, assistant, tool_config.config or {}
                )

                placeholder = tool_config.placeholder  # e.g., "2_context"
                content = result.get("content", "")
                tool_results[placeholder] = content

                # Stream progress: tool completed
                if stream_callback:
                    content_length = len(content) if content else 0
                    stream_callback(f"✅ Tool completed: {tool_config.plugin} → {content_length} chars to {placeholder}")

                # Replace THIS tool's placeholder in the running template
                placeholder_tag = "{" + placeholder + "}"
                if placeholder_tag in current_template:
                    current_template = current_template.replace(
                        placeholder_tag,
                        "\n\n" + content + "\n\n" if content else ""
                    )

                if result.get("sources"):
                    all_sources.extend(result["sources"])

            except Exception as e:
                logger.error(f"Tool {tool_config.plugin} failed: {e}")
                if stream_callback:
                    stream_callback(f"❌ Tool failed: {tool_config.plugin} - {str(e)}")
                # Continue with other tools rather than failing completely
        
        # Final step: replace {user_input} and clean up
        current_template = current_template.replace(
            "{user_input}", "\n\n" + user_input + "\n\n"
        )
        current_template = re.sub(r'\{[a-z0-9_]+\}', '', current_template)  # Clean unused
        
        # Build final messages
        processed_messages = self._build_final_messages(
            assistant, request.get('messages', []), current_template
        )

        # Generate verbose report if requested
        verbose_report = None
        if verbose:
            verbose_report = self._generate_verbose_report(
                request, assistant, tool_configs, tool_results, all_sources, processed_messages
            )

        return OrchestrationResult(
            processed_messages=processed_messages,
            sources=all_sources,
            tool_results=tool_results,
            verbose_report=verbose_report
        )
    
    def _build_final_messages(
        self, 
        assistant: Assistant, 
        messages: List[Dict],
        final_content: str
    ) -> List[Dict[str, str]]:
        """Build messages with the fully processed template."""
        
        processed = []
        
        # Add system prompt
        if assistant.system_prompt:
            processed.append({
                "role": "system",
                "content": assistant.system_prompt
            })
        
        # Add conversation history (all but last)
        if len(messages) > 1:
            processed.extend(messages[:-1])
        
        # Add final processed message
        if messages:
            processed.append({
                "role": messages[-1].get("role", "user"),
                "content": final_content
            })
        
        return processed
    
    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)


def get_orchestrator():
    return SequentialOrchestrator()

def get_name():
    return SequentialOrchestrator.get_name()

def get_description():
    return SequentialOrchestrator.get_description()
```

### 3.4.4 Streaming Tool Invocations

**Purpose:** Provide real-time feedback during tool execution, especially useful for long-running tools or debugging.

**How it works:**
- When `stream=true` in the completion request, orchestrators emit progress messages via `stream_callback`
- Messages show tool start/completion status with content length
- Format: `🔄 Executing tool: {plugin} → {placeholder}` and `✅ Tool completed: {plugin} → {chars} chars to {placeholder}`

**Sequential Orchestrator Streaming:**
```python
# During execution:
if stream_callback:
    stream_callback(f"🔄 Executing tool: {tool_config.plugin} → {tool_config.placeholder}")
# ... tool execution ...
if stream_callback:
    stream_callback(f"✅ Tool completed: {tool_config.plugin} → {content_length} chars to {placeholder}")
```

**Parallel Orchestrator Streaming:**
```python
# At start:
if stream_callback:
    stream_callback(f"🚀 Starting parallel execution of {len(enabled_tools)} tools")

# Per tool:
if stream_callback:
    stream_callback(f"🔄 Starting tool: {tool_config.plugin} → {tool_config.placeholder}")
# ... execution ...
if stream_callback:
    stream_callback(f"✅ Completed tool: {tool_config.plugin} → {content_length} chars to {tool_config.placeholder}")
```

### 3.4.5 VERBOSE Mode

**Purpose:** Return detailed execution information instead of processed messages for debugging and monitoring.

**Activation:** Set `"verbose": true` in assistant metadata.

**What VERBOSE mode returns:** A comprehensive markdown report containing:

```markdown
# Multi-Tool Orchestration Report
**Timestamp:** 2025-12-10T10:30:00
**Orchestrator:** sequential
**Assistant:** My Multi-Tool Assistant

## Request Summary
- **User Message:** What is the capital of France?
- **Stream Mode:** false

## Tool Configuration
### Tool 1: simple_rag
- **Placeholder:** `1_context`
- **Enabled:** true
- **Configuration:**
```json
{
  "collections": ["geography-facts"]
}
```

## Tool Execution Results
### 1_context (context)
- **Content Length:** 245 characters
- **Has Sources:** true
- **Content Preview:**
```
Paris is the capital and most populous city of France...
```

## Sources Summary
- **Total Sources:** 3
### Source 1
- **Title:** Geography of France
- **URL:** https://example.com/geo-france
- **Similarity:** 0.89

## Final Messages Sent to LLM
### Message 1 (system)
```
You are a helpful geography assistant.
```
### Message 2 (user)
```
Context: Paris is the capital...

Question: What is the capital of France?
```
```

**Usage in Assistant Metadata:**
```json
{
  "assistant_type": "multi_tool",
  "orchestrator": "sequential",
  "verbose": true,
  "tools": [...]
}
```
```

**Chained Context Example:**

```
Template: "Context A: {1_context}\nContext B: {2_context}\nQuestion: {user_input}"

Step 1: Tool 1 (simple_rag) executes
        - Sees template as-is
        - Returns: "Found: Article about Python..."
        - Template becomes: "Context A: Found: Article about Python...\nContext B: {2_context}\n..."

Step 2: Tool 2 (simple_rag with different KB) executes
        - Sees: "Context A: Found: Article about Python...\nContext B: {2_context}\n..."
        - Can use Context A content to inform its query (future enhancement)
        - Returns: "Related: Tutorial on data structures..."
        - Template becomes: "Context A: Found: Article...\nContext B: Related: Tutorial...\n..."

Step 3: Replace {user_input}, clean up, send to LLM
```

#### 3.4.4 Orchestrator Engine (Loads Strategy Plugins)

```python
# lamb/completions/tool_orchestrator.py (UPDATED)

from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
from lamb.completions.orchestrators.base import OrchestrationResult, ToolConfig
import importlib
import logging

logger = logging.getLogger(__name__)

class ToolOrchestrator:
    """
    Orchestrator engine that loads and delegates to strategy plugins.
    
    The orchestrator:
    1. Reads the orchestrator strategy from metadata
    2. Loads the appropriate strategy plugin
    3. Delegates tool execution and placeholder replacement to the plugin
    """
    
    def __init__(self):
        self._strategy_cache = {}
    
    def orchestrate(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        metadata: Dict[str, Any],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """
        Main entry point for multi-tool orchestration.

        Args:
            request: The completion request
            assistant: The assistant object
            metadata: Parsed assistant metadata containing orchestrator and tools config
            verbose: If True, return detailed markdown report instead of processed messages
            stream_callback: Optional callback function for streaming progress updates

        Returns:
            OrchestrationResult with processed messages ready for LLM (or verbose report)
        """
        # Get orchestrator strategy (default: parallel)
        strategy_name = metadata.get("orchestrator", "parallel")
        
        # Load strategy plugin
        strategy = self._load_strategy(strategy_name)
        if not strategy:
            logger.error(f"Orchestrator strategy '{strategy_name}' not found, falling back to parallel")
            strategy = self._load_strategy("parallel")
        
        # Parse tool configs from metadata
        tool_configs = self._parse_tool_configs(metadata.get("tools", []))
        
        # Delegate to strategy plugin
        return strategy.execute(request, assistant, tool_configs)
    
    def _load_strategy(self, strategy_name: str):
        """Load orchestrator strategy plugin from completions/orchestrators/"""
        if strategy_name in self._strategy_cache:
            return self._strategy_cache[strategy_name]
        
        try:
            module = importlib.import_module(
                f"lamb.completions.orchestrators.{strategy_name}"
            )
            orchestrator = module.get_orchestrator()
            self._strategy_cache[strategy_name] = orchestrator
            return orchestrator
        except ImportError as e:
            logger.error(f"Failed to load orchestrator strategy '{strategy_name}': {e}")
            return None
    
    def _parse_tool_configs(self, tools_list: List[Dict]) -> List[ToolConfig]:
        """Convert raw tool config dicts to ToolConfig objects."""
        configs = []
        for tool_dict in tools_list:
            configs.append(ToolConfig(
                plugin=tool_dict.get("plugin", tool_dict.get("type", "")),
                placeholder=tool_dict.get("placeholder", "context"),
                enabled=tool_dict.get("enabled", True),
                config=tool_dict.get("config", {})
            ))
        return configs
    
    @staticmethod
    def get_available_strategies() -> List[Dict[str, str]]:
        """List all available orchestrator strategies (for API/UI)."""
        import os
        import glob
        
        strategies = []
        orchestrators_dir = os.path.join(
            os.path.dirname(__file__), "orchestrators"
        )
        
        for filepath in glob.glob(os.path.join(orchestrators_dir, "*.py")):
            filename = os.path.basename(filepath)
            if filename.startswith("__") or filename == "base.py":
                continue
            
            module_name = filename[:-3]
            try:
                module = importlib.import_module(
                    f"lamb.completions.orchestrators.{module_name}"
                )
                strategies.append({
                    "name": module.get_name(),
                    "description": getattr(module, 'get_description', lambda: "")()
                })
            except Exception as e:
                logger.warning(f"Failed to load orchestrator {module_name}: {e}")
        
        return strategies


# Global instance
tool_orchestrator = ToolOrchestrator()
```

### 3.5 ~~Multi-Tool Prompt Processor~~ (DEPRECATED)

> **⚠️ DEPRECATED (Dec 10, 2025):** The separate Multi-Tool PPS layer has been removed. Placeholder replacement is now handled directly by **Orchestrator Strategy Plugins** (see Section 3.4).

**Why removed?**
- The PPS layer was only doing placeholder replacement
- Having a separate PPS created an unnecessary abstraction
- Different orchestration strategies may need different replacement logic
- Consolidating into the orchestrator makes the architecture cleaner

**Where did the functionality go?**
- Placeholder replacement is now in `BaseOrchestrator._replace_placeholders()`
- Message building is now in each orchestrator strategy (e.g., `ParallelOrchestrator._build_messages()`)
- Orchestrator strategies can override replacement logic if needed

**Code location change:**
- ~~`completions/multi-tool-pps/multi_augment.py`~~ → Removed
- New: `completions/orchestrators/base.py` (contains `_replace_placeholders`)
- New: `completions/orchestrators/parallel.py` (contains `_build_messages`)

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


@router.get("/orchestrators")
async def list_available_orchestrators(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    List all available orchestrator strategies for multi-tool assistants.
    """
    from lamb.completions.tool_orchestrator import ToolOrchestrator
    return {"orchestrators": ToolOrchestrator.get_available_strategies()}
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
    // Format: array of { name: '1_context', display: '{1_context}', order: 1, type: 'context' }
    let availablePlaceholders = $derived(() => {
        const toolPlaceholders = tools
            .filter(t => t.enabled && t.placeholder)
            .map((t, index) => ({
                name: t.placeholder,
                display: `{${t.placeholder}}`,
                order: index + 1,
                type: TOOL_PLUGINS[t.plugin]?.placeholderType || 'unknown'
            }));
        
        // Always add {user_input} at the end
        return [
            ...toolPlaceholders,
            { name: 'user_input', display: '{user_input}', order: null, type: 'input' }
        ];
    });
    
    function handleToolsChange(newTools) {
        tools = newTools;
    }
    
    // State for orchestrator strategy
    let orchestrator = $state('parallel');  // Default strategy
    
    async function handleSubmit() {
        const metadata = {
            assistant_type: "multi_tool",  // KEY: Identifies as multi-tool
            orchestrator,                   // Orchestrator strategy plugin
            connector,
            llm,
            tools: tools.map(t => ({
                plugin: t.type,            // Tool plugin name
                placeholder: t.placeholder, // Explicit placeholder
                enabled: t.enabled,
                config: t.config
            }))
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
    
    <!-- Orchestrator Strategy Selection (NEW) -->
    <section class="orchestrator-config">
        <h2>⚙️ Orchestration Strategy</h2>
        <label>
            <select bind:value={orchestrator}>
                <option value="parallel">Parallel - Execute all tools concurrently (fastest)</option>
                <option value="sequential">Sequential - Execute tools one by one (ordered)</option>
            </select>
            <small class="hint">
                Choose how tools are executed. Parallel is faster; Sequential preserves order.
            </small>
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

### 4.5 UI Mockups: Tool Sequencing & Placeholder Management

#### 4.5.1 Main Tools Configuration Panel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🔧 TOOLS PIPELINE                                                          │
│  ─────────────────                                                          │
│  Orchestrator: [Sequential ▼]  ℹ️ Tools execute in order; each sees previous│
│                                                                             │
│  ┌─ TOOL PIPELINE (drag to reorder) ───────────────────────────────────────┐│
│  │                                                                          ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │ ≡  1  🗂️ Knowledge Base RAG                           [✓] [⚙️] [✕] │ ││
│  │  │      Placeholder: {1_context}                                      │ ││
│  │  │      KB: "Course Materials" | Top-K: 5                             │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                              ↓                                          ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │ ≡  2  🗂️ Knowledge Base RAG                           [✓] [⚙️] [✕] │ ││
│  │  │      Placeholder: {2_context}                                      │ ││
│  │  │      KB: "Research Papers" | Top-K: 3                              │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                              ↓                                          ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │ ≡  3  📋 Rubric                                       [✓] [⚙️] [✕] │ ││
│  │  │      Placeholder: {3_rubric}                                       │ ││
│  │  │      Rubric: "Essay Evaluation Rubric"                             │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                                                                          ││
│  │                    [ + Add Tool ▼ ]                                     ││
│  │                                                                          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key UI Elements:**
- `≡` Drag handle for reordering
- Number badge shows execution order
- Checkbox `[✓]` to enable/disable without removing
- `[⚙️]` opens detailed config modal
- `[✕]` removes tool from pipeline
- Arrow `↓` indicates sequential flow

#### 4.5.2 Add Tool Dropdown

```
┌─────────────────────────────────────────────────┐
│  + Add Tool ▼                                   │
├─────────────────────────────────────────────────┤
│  🗂️ Knowledge Base RAG                         │
│     Query KB collections → {N_context}          │
│                                                 │
│  📋 Rubric                                      │
│     Include grading rubric → {N_rubric}         │
│                                                 │
│  📄 Single File                                 │
│     Include file contents → {N_file}            │
│                                                 │
│  ─────────────────────────────────────────────  │
│  ⚡ No Processing (passthrough)                 │
│     For testing/debugging                       │
└─────────────────────────────────────────────────┘
```

#### 4.5.3 Tool Configuration Modal (Example: Knowledge Base RAG)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⚙️ Configure: Knowledge Base RAG (Tool #2)                           [✕]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Placeholder: {2_context}                                                   │
│  ────────────────────────────                                               │
│                                                                             │
│  Select Knowledge Bases:                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [✓] Course Materials                    📚 156 documents            │   │
│  │ [ ] Research Papers                     📚 42 documents             │   │
│  │ [ ] Student Examples                    📚 28 documents             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Retrieval Settings:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Top-K Results:  [5 ▼]   (1-20)                                     │   │
│  │                                                                      │   │
│  │  Similarity Threshold: [0.7 ────●────── 1.0]                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                                             [ Cancel ]  [ Save Changes ]    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.5.4 Prompt Template Editor with Placeholder Buttons

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📝 PROMPT TEMPLATE                                                         │
│  ──────────────────                                                         │
│                                                                             │
│  Insert Placeholder:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [{1_context}] [{2_context}] [{3_rubric}] [{user_input}]             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ℹ️ Click a button to insert placeholder at cursor position                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ You are an academic assistant helping students with their essays.   │   │
│  │                                                                      │   │
│  │ ## Course Context:                                                   │   │
│  │ {1_context}                                                          │   │
│  │                                                                      │   │
│  │ ## Research Context:                                                 │   │
│  │ {2_context}                                                          │   │
│  │                                                                      │   │
│  │ ## Grading Rubric:                                                   │   │
│  │ {3_rubric}                                                           │   │
│  │                                                                      │   │
│  │ ## Student's Question:                                               │   │
│  │ {user_input}                                                         │   │
│  │                                                                      │   │
│  │ Please provide feedback based on the rubric criteria.               │   │
│  │ █                                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ⚠️ Warning: {2_context} is defined but not used in template              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Placeholder Button Behavior:**
- Buttons are **dynamically generated** based on enabled tools
- Clicking a button **inserts at cursor position** in textarea
- **Validation warnings** show unused placeholders or missing ones
- **Color coding:** Green = used, Orange = defined but unused, Red = used but undefined

#### 4.5.4b Placeholder Validation States

```
GOOD STATE (all placeholders used correctly):
┌─────────────────────────────────────────────────────────────────────────────┐
│  Insert Placeholder:                                                        │
│  [🟢{1_context}] [🟢{2_context}] [🟢{3_rubric}] [🟢{user_input}]           │
│  ✓ All placeholders are used in template                                   │
└─────────────────────────────────────────────────────────────────────────────┘

WARNING STATE (placeholder defined but not used):
┌─────────────────────────────────────────────────────────────────────────────┐
│  Insert Placeholder:                                                        │
│  [🟢{1_context}] [🟠{2_context}] [🟢{3_rubric}] [🟢{user_input}]           │
│  ⚠️ {2_context} is defined but not used in template (click to insert)      │
└─────────────────────────────────────────────────────────────────────────────┘

ERROR STATE (placeholder used but tool disabled/removed):
┌─────────────────────────────────────────────────────────────────────────────┐
│  Insert Placeholder:                                                        │
│  [🟢{1_context}] [🟢{3_rubric}] [🟢{user_input}]                           │
│  🔴 Template contains {2_context} but no tool provides it                  │
│     → Either re-enable Tool #2 or remove {2_context} from template          │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.5.5 Drag-and-Drop Reordering Interaction

```
Before drag:                          During drag:
┌──────────────────────┐              ┌──────────────────────┐
│ ≡ 1 🗂️ KB: Course    │              │ ≡ 1 🗂️ KB: Course    │
├──────────────────────┤              ├──────────────────────┤
│ ≡ 2 🗂️ KB: Research  │  ←dragging  │      ↕ drop zone     │  ← highlighted
├──────────────────────┤              ├──────────────────────┤
│ ≡ 3 📋 Rubric        │              │ ≡ 2 📋 Rubric        │  ← renumbered
└──────────────────────┘              ├──────────────────────┤
                                      │ ≡ 3 🗂️ KB: Research  │  ← ghost
                                      └──────────────────────┘

After drop:
┌──────────────────────┐
│ ≡ 1 🗂️ KB: Course    │
├──────────────────────┤
│ ≡ 2 📋 Rubric        │  ← was #3, now #2
├──────────────────────┤
│ ≡ 3 🗂️ KB: Research  │  ← was #2, now #3
└──────────────────────┘

⚠️ Placeholders auto-update:
   {3_rubric} → {2_rubric}  (renumbered from position 3 to 2)
   {2_context} → {3_context} (renumbered from position 2 to 3)
   
   Template auto-updated:
   Before: "{1_context}...{2_context}...{3_rubric}"
   After:  "{1_context}...{3_context}...{2_rubric}"
```

#### 4.5.5b Reorder Confirmation Dialog (Optional UX)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⚠️ Reorder will update template placeholders                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Moving "Rubric" from position 3 to position 2 will:                       │
│                                                                             │
│  • Rename {3_rubric} → {2_rubric}                                          │
│  • Rename {2_context} → {3_context}                                        │
│                                                                             │
│  Your template will be automatically updated:                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ - Context A: {2_context}    + Context A: {3_context}               │    │
│  │ - Rubric: {3_rubric}        + Rubric: {2_rubric}                   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                   [ Cancel ]  [ Apply Reorder ]            │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.5.6 Orchestrator Strategy Selection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⚙️ Orchestration Strategy                                                  │
│  ─────────────────────────                                                  │
│                                                                             │
│  ○ Sequential (Recommended)                                                 │
│    Execute tools in order. Each tool sees previous outputs.                │
│    Best for: Chained context, ordered processing                           │
│    ┌───────────────────────────────────────────────────────┐               │
│    │  Tool 1 → {1_context} filled → Tool 2 → {2_rubric} → ... → LLM      │               │
│    └───────────────────────────────────────────────────────┘               │
│                                                                             │
│  ○ Parallel                                                                 │
│    Execute all tools simultaneously for speed.                             │
│    Tools don't see each other's outputs.                                   │
│    Best for: Independent tools, maximum performance                        │
│    ┌───────────────────────────────────────────────────────┐               │
│    │  Tool 1 ─┐                                                            │               │
│    │  Tool 2 ─┼─→ Merge all → LLM                                          │               │
│    │  Tool 3 ─┘                                                            │               │
│    └───────────────────────────────────────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.5.7 Full Form Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Create Multi-Tool Assistant                                         [Save]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─ BASIC INFO ─────────────────────────────────────────────────────────┐  │
│  │ Name: [Essay Feedback Assistant                                    ] │  │
│  │ Description: [Provides structured feedback on student essays...    ] │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ MODEL ──────────────────────────────────────────────────────────────┐  │
│  │ Provider: [OpenAI ▼]     Model: [gpt-4o-mini ▼]                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ TOOLS PIPELINE ─────────────────────────────────────────────────────┐  │
│  │ (see mockup 4.5.1)                                                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ SYSTEM PROMPT ──────────────────────────────────────────────────────┐  │
│  │ [You are an educational assistant that helps students improve...   ] │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ PROMPT TEMPLATE ────────────────────────────────────────────────────┐  │
│  │ (see mockup 4.5.4)                                                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 ToolsManager Component

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
        const pluginDef = TOOL_PLUGINS[toolType];
        if (!pluginDef) return;
        
        // Calculate next order number
        const nextOrder = tools.length + 1;
        
        const newTool = {
            type: toolType,              // For frontend component lookup
            plugin: toolType,            // For backend (matches tool plugin name)
            placeholder: generatePlaceholder(toolType, nextOrder),  // e.g., "3_context"
            enabled: true,
            config: { ...pluginDef.defaultConfig }
        };
        
        onchange([...tools, newTool]);
    }
    
    function handleReorder(newOrder) {
        // Get old placeholders before renumbering
        const oldPlaceholders = tools.map(t => t.placeholder);
        
        // Renumber all tools based on new order
        const reorderedTools = renumberPlaceholders(newOrder);
        const newPlaceholders = reorderedTools.map(t => t.placeholder);
        
        // Notify parent to update template
        onchange(reorderedTools, { 
            templateUpdate: { oldPlaceholders, newPlaceholders } 
        });
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
    // NOTE: Base placeholder type; actual placeholder is "{order}_{type}"
    simple_rag: {
        component: SimpleRagToolConfig,
        name: 'Knowledge Base RAG',
        icon: '🗂️',
        description: 'Query knowledge bases for relevant context',
        placeholderType: 'context',    // Base type; becomes {1_context}, {2_context}, etc.
        defaultConfig: {
            collections: [],
            top_k: 3
        },
        allowMultiple: true           // ✅ Can add multiple instances
    },
    rubric_rag: {
        component: RubricRagToolConfig,
        name: 'Rubric',
        icon: '📋',
        description: 'Include assessment rubric in context',
        placeholderType: 'rubric',
        defaultConfig: {
            rubric_id: null,
            format: 'markdown'
        },
        allowMultiple: true           // ✅ Can add multiple rubrics
    },
    single_file_rag: {
        component: SingleFileRagToolConfig,
        name: 'Single File',
        icon: '📄',
        description: 'Include contents of a single file',
        placeholderType: 'file',
        defaultConfig: {
            file_path: ''
        },
        allowMultiple: true           // ✅ Can add multiple files
    },
    no_rag: {
        component: null,              // No config needed
        name: 'No Processing',
        icon: '⚡',
        description: 'Passthrough for testing',
        placeholderType: 'none',
        defaultConfig: {},
        allowMultiple: false
    }
};

/**
 * Generate placeholder string for a tool at given order position
 * Format: {order}_{placeholderType}
 * Example: {1_context}, {2_rubric}, {3_context}
 */
export function generatePlaceholder(toolType, order) {
    const plugin = TOOL_PLUGINS[toolType];
    if (!plugin || plugin.placeholderType === 'none') return null;
    return `${order}_${plugin.placeholderType}`;
}

/**
 * Get placeholder with braces for display
 */
export function getPlaceholderDisplay(placeholder) {
    return placeholder ? `{${placeholder}}` : '';
}

/**
 * Renumber all placeholders after reordering
 * Returns updated tools array with correct placeholder values
 */
export function renumberPlaceholders(tools) {
    return tools.map((tool, index) => ({
        ...tool,
        placeholder: generatePlaceholder(tool.plugin, index + 1)
    }));
}

/**
 * Update template when placeholders change (after reorder)
 * @param template - Current prompt template
 * @param oldPlaceholders - Array of old placeholder strings
 * @param newPlaceholders - Array of new placeholder strings (same length)
 */
export function updateTemplatePlaceholders(template, oldPlaceholders, newPlaceholders) {
    let result = template;
    // Replace in reverse order to avoid conflicts (e.g., {1_context} before {10_context})
    const pairs = oldPlaceholders.map((old, i) => [old, newPlaceholders[i]])
        .sort((a, b) => b[0].length - a[0].length);
    
    for (const [oldPh, newPh] of pairs) {
        if (oldPh !== newPh) {
            result = result.replace(new RegExp(`\\{${oldPh}\\}`, 'g'), `{${newPh}}`);
        }
    }
    return result;
}

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
    
    // Ensure assistant_type and orchestrator are set
    let metadata = assistantData.metadata;
    if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata);
    }
    metadata.assistant_type = 'multi_tool';
    metadata.orchestrator = metadata.orchestrator || 'parallel';  // Default strategy
    // NOTE: prompt_processor is NOT set - orchestrator handles placeholder replacement
    
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
 * Get available orchestrator strategies from backend
 */
export async function getAvailableOrchestrators() {
    if (!browser) return [];
    
    const token = localStorage.getItem('userToken');
    if (!token) throw new Error('Not authenticated');
    
    try {
        const response = await fetch(getApiUrl('/completions/orchestrators'), {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch orchestrators');
        }
        
        const data = await response.json();
        return data.orchestrators || [];
    } catch (error) {
        console.error('Error fetching orchestrators:', error);
        // Return default strategies if API fails
        return [
            { name: 'parallel', description: 'Execute all tools concurrently' },
            { name: 'sequential', description: 'Execute tools one by one' }
        ];
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

### 4.8 Frontend Implementation Details

#### 4.8.1 Service Layer

**`multiToolAssistantService.js`** - API communication for multi-tool assistants:

```javascript
// Core functions
export async function createMultiToolAssistant(assistantData)
export async function updateMultiToolAssistant(assistantId, assistantData)
export function parseMultiToolMetadata(assistant)
export function validateMultiToolConfig(metadata)
export async function getAvailableTools()
export async function getAvailableOrchestrators()
```

**Key Features:**
- Handles `assistant_type: "multi_tool"` metadata parsing
- Validates tool configurations before submission
- Provides type-safe API communication
- Error handling with detailed console logging

#### 4.8.2 State Management

**`multiToolStore.js`** - Reactive state management with Svelte 5 runes:

```javascript
// Reactive state variables
let name = $derived(currentState?.name || '');
let tools = $derived(currentState?.tools || []);
let orchestrator = $derived(currentState?.orchestrator || 'sequential');
let verbose = $derived(currentState?.verbose || false);

// Action functions
export const multiToolStoreActions = {
    reset: () => { /* reset state */ },
    updateField: (field, value) => { /* update single field */ },
    addTool: (pluginName) => { /* add tool to pipeline */ },
    removeTool: (index) => { /* remove tool */ },
    reorderTools: (fromIndex, toIndex) => { /* reorder tools */ },
    setAvailableTools: (tools) => { /* set available tools */ }
};
```

**Features:**
- Reactive state updates with Svelte 5 `$derived`
- Tool pipeline management (add/remove/reorder)
- Placeholder auto-numbering on reorder
- Validation state tracking

#### 4.8.3 Component Registry

**`plugins/index.js`** - Dynamic component loading system:

```javascript
// Tool component mapping
export const TOOL_PLUGIN_COMPONENTS = {
    'simple_rag': SimpleRagToolConfig,
    'rubric_rag': RubricRagToolConfig,
    'single_file_rag': SingleFileRagToolConfig
};

// Utility functions
export function getToolComponent(pluginName)
export function hasToolComponent(pluginName)
export function getAvailableToolComponents()
```

**Benefits:**
- Extensible plugin architecture
- Easy addition of new tool types
- Centralized component management

#### 4.8.4 Tool Configuration Components

**`SimpleRagToolConfig.svelte`** - Knowledge base selection:
```svelte
<!-- Collections selection with checkboxes -->
<!-- Top-K slider with number input -->
<!-- Real-time validation -->
```

**`RubricRagToolConfig.svelte`** - Assessment rubric selection:
```svelte
<!-- Rubric dropdown -->
<!-- Format selection (Markdown/JSON) -->
<!-- Rubric preview -->
```

**`SingleFileRagToolConfig.svelte`** - File selection:
```svelte
<!-- File dropdown -->
<!-- Character limit controls -->
<!-- File metadata display -->
```

**Common Features:**
- Real-time validation with error display
- Accessible form controls with proper labels
- Responsive design for mobile/tablet
- Loading states and error handling

#### 4.8.5 Core Components

**`ToolsManager.svelte`** - Main pipeline management:
```svelte
<!-- Tool pipeline display -->
<!-- Add tool selection -->
<!-- Drag-to-reorder (UI buttons) -->
<!-- Tool enable/disable toggles -->
<!-- Pipeline summary -->
```

**Features:**
- Visual tool pipeline representation
- Accordion-style tool configuration
- Real-time validation feedback
- Pipeline execution flow diagram

**`ToolConfigCard.svelte`** - Individual tool configuration:
```svelte
<!-- Tool header with enable/disable -->
<!-- Expandable configuration section -->
<!-- Move up/down controls -->
<!-- Remove tool button -->
<!-- Validation error display -->
```

**Accessibility Features:**
- ARIA roles and keyboard navigation
- Screen reader friendly
- Focus management
- Keyboard event handlers

**`MultiToolAssistantForm.svelte`** - Complete form interface:
```svelte
<!-- Basic information fields -->
<!-- Orchestrator selection -->
<!-- VERBOSE mode toggle -->
<!-- LLM settings -->
<!-- ToolsManager integration -->
<!-- Prompt template with placeholders -->
<!-- Template insertion buttons -->
<!-- Form validation and submission -->
```

**`MultiToolAssistantView.svelte`** - Read-only assistant display:
```svelte
<!-- Assistant header with actions -->
<!-- Configuration summary -->
<!-- Tool pipeline visualization -->
<!-- Execution flow diagram -->
<!-- Statistics dashboard -->
```

#### 4.8.6 Routing Implementation

**Routes Structure:**
```
frontend/svelte-app/src/routes/
├── multi-tool-assistants/
│   ├── +page.svelte              # List/overview page
│   ├── create/+page.svelte       # Create form
│   └── [id]/+page.svelte         # View/edit page
```

**Route Features:**
- Modal-based creation flow
- Unified view/edit page with mode switching
- Proper error handling and loading states
- Breadcrumb navigation

#### 4.8.7 Navigation Integration

**Updated `Nav.svelte`:**
```svelte
<!-- Assistants dropdown menu -->
<div class="relative assistants-menu">
    <button onclick={() => assistantsMenuOpen = !assistantsMenuOpen}>
        Learning Assistants
        <!-- Dropdown arrow -->
    </button>
    <!-- Dropdown content with links -->
</div>
```

**Features:**
- Dropdown navigation for assistant types
- Direct links to create multi-tool assistants
- Active state indication
- Keyboard accessibility

#### 4.8.8 Assistant List Integration

**Updated `AssistantsList.svelte`:**
```svelte
<!-- Type badges in table rows -->
{#if assistant.metadata}
    {@const callback = parseMetadata(assistant.metadata)}
    {#if callback.assistant_type === 'multi_tool'}
        <span class="badge multi-tool">🔧 Multi-Tool</span>
    {/if}
{/if}

<!-- Smart routing based on assistant type -->
function handleView(id) {
    const assistant = allAssistants.find(a => a.id === id);
    if (assistant?.metadata && parseMetadata(assistant.metadata).assistant_type === 'multi_tool') {
        goto(`${base}/multi-tool-assistants/${id}`);
    } else {
        goto(`${base}/assistants?view=detail&id=${id}`);
    }
}
```

#### 4.8.9 Template Integration

**Prompt Template Features:**
```svelte
<!-- Template insertion buttons -->
<button onclick={() => handleInsertTemplate('system_prompt')}>
    Use Template
</button>

<!-- Placeholder buttons in template editor -->
{#each availablePlaceholders as placeholder}
    <button onclick={() => insertPlaceholder(placeholder)}>
        {placeholder}
    </button>
{/each}
```

**Integration:**
- System prompt template selection
- Prompt template with numbered placeholders
- Template validation and insertion
- Existing template modal compatibility

#### 4.8.10 Technical Implementation

**Svelte 5 Runes Mode:**
- `$state` for reactive component state
- `$derived` for computed values
- `$effect` for side effects
- Modern event handlers (`onclick`, `onchange`)

**Accessibility Compliance:**
- ARIA roles and properties
- Keyboard navigation support
- Screen reader compatibility
- Focus management
- Error announcements

**Performance Optimizations:**
- Efficient reactive updates
- Lazy loading where appropriate
- Minimal DOM manipulation
- Optimized bundle size

**Error Handling:**
- Comprehensive validation
- User-friendly error messages
- Console logging for debugging
- Graceful fallback states

#### 4.8.11 Testing & Quality Assurance

**Build Quality:**
- ✅ Zero accessibility warnings
- ✅ Zero build errors
- ✅ Svelte 5 compatibility
- ✅ Cross-browser compatibility
- ✅ Mobile responsive

**Code Quality:**
- ✅ JSDoc documentation
- ✅ Consistent naming conventions
- ✅ Modular component architecture
- ✅ Separation of concerns
- ✅ Reusable utilities

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

### 5.2 Multi-Tool Assistant Metadata (NEW - Updated Dec 10, 2025)

> **⚠️ UPDATED:** Metadata now includes `orchestrator` field for strategy plugin selection. The `prompt_processor` field is no longer needed for multi-tool assistants (placeholder replacement is handled by the orchestrator).

```json
{
    "assistant_type": "multi_tool",
    "orchestrator": "sequential",            // ← Orchestrator strategy plugin (sequential = chained context)
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "capabilities": {
        "vision": false,
        "image_generation": false
    },
    "verbose": false,                        // NEW: Enable verbose markdown reporting mode
    "tools": [
        {
            "plugin": "simple_rag",
            "placeholder": "1_context",      // ← Numbered: {1_context}
            "enabled": true,
            "config": {
                "collections": ["course-materials"],
                "top_k": 5
            }
        },
        {
            "plugin": "simple_rag",          // ← Same plugin, different config
            "placeholder": "2_context",      // ← Numbered: {2_context}
            "enabled": true,
            "config": {
                "collections": ["research-papers"],
                "top_k": 3
            }
        },
        {
            "plugin": "rubric_rag",
            "placeholder": "3_rubric",       // ← Numbered: {3_rubric}
            "enabled": true,
            "config": {
                "rubric_id": 42,
                "format": "markdown"
            }
        },
        {
            "plugin": "single_file_rag",
            "placeholder": "4_file",         // ← Numbered: {4_file}
            "enabled": false,
            "config": {
                "file_path": "documents/guide.md"
            }
        }
    ]
}
```

### 5.3 Available Orchestrator Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `parallel` | Execute all tools concurrently | Independent tools, maximum speed |
| `sequential` | Execute tools one by one; each tool sees previous outputs | **Default**; ordered pipelines, chained context |
| `conditional` | Run tools based on conditions | Context-aware tool execution (future) |

> **Key Insight (Dec 10, 2025):** In `sequential` mode, when Tool A precedes Tool B in the list, Tool B receives the prompt with Tool A's placeholder **already replaced**. This enables chained context where later tools can "see" earlier tool outputs.

### 5.4 Key Differences

| Field | Classic | Multi-Tool |
|-------|---------|------------|
| `assistant_type` | absent or `"classic"` | `"multi_tool"` |
| `orchestrator` | absent | `"parallel"`, `"sequential"`, etc. |
| `prompt_processor` | `"simple_augment"` | **NOT USED** (handled by orchestrator) |
| `rag_processor` | `"simple_rag"`, etc. | absent |
| `tools` | absent | array of tool configs with `plugin` + `placeholder` |

### 5.5 Tool Config Schema

Each tool in the `tools` array follows this schema:

```json
{
    "plugin": "string",      // Required: Tool plugin name (e.g., "simple_rag")
    "placeholder": "string", // Auto-generated: "{order}_{type}" (e.g., "1_context")
    "enabled": true,         // Optional: Whether to execute (default: true)
    "config": {}             // Optional: Tool-specific configuration
}
```

### 5.6 Placeholder Naming Convention

Placeholders follow a **numbered prefix** pattern to support:
- Multiple instances of the same tool
- Clear sequencing indication

**Format:** `{order}_{tooltype}`

**Examples:**
| Tool Order | Tool Plugin | Placeholder |
|------------|-------------|-------------|
| 1st | simple_rag | `{1_context}` |
| 2nd | rubric_rag | `{2_rubric}` |
| 3rd | simple_rag (2nd KB) | `{3_context}` |
| 4th | single_file_rag | `{4_file}` |

### 5.7 Multiple Tool Instances Example

A user wants to query TWO different knowledge bases and include a rubric:

```json
{
    "assistant_type": "multi_tool",
    "orchestrator": "sequential",
    "tools": [
        {
            "plugin": "simple_rag",
            "placeholder": "1_context",
            "config": {
                "collections": ["course-materials"],
                "top_k": 5
            }
        },
        {
            "plugin": "simple_rag",
            "placeholder": "2_context",
            "config": {
                "collections": ["research-papers"],
                "top_k": 3
            }
        },
        {
            "plugin": "rubric_rag",
            "placeholder": "3_rubric",
            "config": {
                "rubric_id": 42
            }
        }
    ]
}
```

**Corresponding Prompt Template:**
```
You are an academic assistant.

## Course Materials Context:
{1_context}

## Research Papers Context:
{2_context}

## Grading Rubric:
{3_rubric}

## Student Question:
{user_input}

Please answer based on the above context and rubric.
```

### 5.8 Sequential Execution with Chained Context

In `sequential` orchestrator mode, **each tool sees the prompt with previous placeholders already replaced**:

```
Step 1: Execute tool 1 (simple_rag for course-materials)
        → Replace {1_context} with results

Step 2: Execute tool 2 (simple_rag for research-papers)
        → Tool 2 can "see" {1_context} content in the prompt
        → Replace {2_context} with results

Step 3: Execute tool 3 (rubric_rag)
        → Tool 3 can "see" both {1_context} and {2_context}
        → Replace {3_rubric} with results

Step 4: Replace {user_input} → Send to LLM
```

**Why this matters:** A future tool could use the accumulated context to make smarter queries (e.g., a summarization tool that reads previous RAG outputs).

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
| B9 | Create `orchestrators/` directory | HIGH | 1h |
| B10 | Implement `orchestrators/base.py` (interface) | HIGH | 2h |
| B11 | Implement `orchestrators/parallel.py` | HIGH | 4h |
| B12 | Implement `orchestrators/sequential.py` | MED | 2h |
| B13 | Update `tool_orchestrator.py` (engine) | HIGH | 3h |
| B14 | Add type-based routing to `main.py` | HIGH | 3h |
| B15 | Add `/tools` API endpoint | HIGH | 2h |
| B16 | Add `/orchestrators` API endpoint | MED | 1h |

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
| ~~Tool Ordering~~ | ~~Allow users to specify tool execution order~~ | ✅ **DONE** (sequential orchestrator) |
| ~~Parallel Execution~~ | ~~Execute independent tools in parallel~~ | ✅ **DONE** (parallel orchestrator - default) |
| Dependency Orchestrator | `dependency` strategy - Tool B waits for Tool A | MED |
| Conditional Orchestrator | `conditional` strategy - Run tools based on conditions | MED |
| Custom Orchestrator Plugins | Allow users to create custom orchestration strategies | LOW |
| Custom Tool Plugins | Allow users to create custom tool plugins | MED |
| Tool Templates | Pre-defined tool + orchestrator combinations | LOW |
| Classic → Multi-Tool Conversion | Optional user-initiated conversion | POST-MVP |

### 9.2 Tool Extension Points

**Adding new Tool Plugins:**

1. Create a new file in `completions/tools/`
2. Implement `BaseTool` interface
3. Define `get_definition()` with placeholder, config schema
4. Add entry to frontend plugin registry
5. Create frontend config component

**Adding new Orchestrator Strategies:**

1. Create a new file in `completions/orchestrators/`
2. Extend `BaseOrchestrator` interface
3. Implement `execute()` method with custom sequencing logic
4. Optionally override `_replace_placeholders()` for custom replacement
5. Add `get_orchestrator()`, `get_name()`, `get_description()` module functions
6. Update frontend to show new strategy option

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
| `completions/orchestrators/__init__.py` | Package init |
| `completions/orchestrators/base.py` | Base orchestrator interface |
| `completions/orchestrators/parallel.py` | Parallel execution strategy |
| `completions/orchestrators/sequential.py` | Sequential execution strategy |
| `completions/orchestrators/dependency.py` | Dependency-based execution (future) |
| `completions/tool_orchestrator.py` | Orchestrator engine (loads strategy plugins) |
| `completions/tool_registry.py` | Tool discovery |

> **Note:** `completions/multi-tool-pps/` is NOT created - functionality moved to orchestrator plugins.

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
| **Multi-Tool Assistant** | Assistant using multiple tools (`completions/tools/*`) with an orchestrator |
| **Tool Plugin** | A backend module that retrieves/generates content for a placeholder |
| **Orchestrator** | Engine that loads strategy plugins and coordinates tool execution |
| **Orchestrator Strategy Plugin** | A plugin defining how tools are executed and placeholders replaced (e.g., `parallel`, `sequential`) |
| **Placeholder** | Template variable (e.g., `{context}`) replaced with tool output |
| **Tool Registry** | Backend system for discovering and loading tool plugins |
| **Plugin Registry** | Frontend mapping of tool types to config components |
| **OrchestrationResult** | Result object containing processed messages, sources, and tool outputs |

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
| 1.1 | Dec 10, 2025 | **Major architecture update:** Eliminated `multi-tool-pps/` layer. Introduced plugin-based orchestrator with strategy plugins (`parallel`, `sequential`, etc.). Orchestrator now handles both tool execution AND placeholder replacement. Updated metadata schema to include `orchestrator` field and explicit `placeholder` per tool. |
| 1.2 | Dec 10, 2025 | **Sequential chained context:** Sequential orchestrator now passes accumulated context to each tool. **Numbered placeholders:** Format changed to `{order}_{type}` (e.g., `{1_context}`, `{2_rubric}`). **Multiple tool instances:** Same tool can be added multiple times with different configs. **UI Mockups:** Added detailed mockups for tool pipeline management, drag-to-reorder, placeholder buttons, and orchestrator selection. |
