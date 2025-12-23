# Tool Assistants Analysis Report

**Version:** 1.1  
**Date:** December 4, 2025  
**Related Issues:** #137, #138, #140  
**Target Milestone:** 0.4 "Here there will be dragons"  
**Last Updated:** December 4, 2025 - Added security model, recursion rules, and streaming strategy

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [GitHub Issues Summary](#2-github-issues-summary)
3. [Current Architecture Analysis](#3-current-architecture-analysis)
4. [Proposed Tool Assistant Architecture](#4-proposed-tool-assistant-architecture)
5. [Security Model](#5-security-model)
6. [Recursion Prevention Rules](#6-recursion-prevention-rules)
7. [Streaming and User Feedback Strategy](#7-streaming-and-user-feedback-strategy)
8. [Changes Required](#8-changes-required)
9. [Viability Assessment](#9-viability-assessment)
10. [Implementation Tasks](#10-implementation-tasks)
11. [Risk Analysis](#11-risk-analysis)
12. [Recommendations](#12-recommendations)

---

## 1. Executive Summary

This report analyzes the requirements and feasibility of implementing **Tool Assistants** in LAMB - a feature that enables assistants to be used as tools by other assistants, and enables certain assistants to call and orchestrate other assistants as tools.

### Key Goals

1. **Assistants as Tools (Issue #137):** Enable existing assistants to be invoked as tools by tool-using assistants
2. **Tool Use Assistants (Issue #138):** Create assistants that can use tools (including other assistants) to accomplish goals
3. **Context-Aware Augment (Issue #140):** Improve RAG query quality using LLM-enhanced query preprocessing

### Verdict: **VIABLE with significant development effort**

The proposal is architecturally sound and aligns well with LAMB's existing plugin-based design. However, it requires:
- New prompt processors (`tool_augment.py`, `context_aware_augment.py`)
- New connectors (`openai_tool_use.py`)
- A new internal tool invocation API
- Database schema additions for tool configuration
- Frontend changes for tool configuration UI

---

## 2. GitHub Issues Summary

### Issue #137: Assistant as a Tool

**Goal:** Enable learning assistants to be used as tools by other assistants.

**Key Requirements:**
- Assistants should be callable by other assistants without using `/v1/chat/completions` WS
- Tools will NOT stream and may have different requirements
- Need a new `tool_augment.py` prompt processor family
- Must maintain LAMB internal security and access control (reason for not using MCP directly)
- Need to define how `tool_augment.py` manages its parameters

**Why NOT MCP yet:**
- Need to apply internal LAMB control and security access rules
- MCP would make these security rules hard to enforce

### Issue #138: Tool Use Assistants

**Goal:** Create assistants that can use tools to accomplish goals.

**Current Tools in LAMB:**
1. **Knowledge Bases** - Queryable but not modifiable by assistants
2. **Single Files** - Handled by create assistant form
3. **Rubrics** - Assessment tools

**Future Tools:**
- Assistants as tools (#137)
- Image generation (banana_img connector)
- Specialized tools (MCP-wrapped within LAMB security)

**Design Insight - "The Crazy Idea":**
> Tool Use Assistants only use Assistants as tools

**Rationale:** Since any LAMB simple tool can be wrapped within an assistant, the backend can standardize on assistant-as-tool invocation. The frontend can create different metaphors, but the backend implementation remains consistent.

### Issue #140: Context-Aware Augment Prompt Processor

**Goal:** Create a prompt processor that uses an LLM to improve RAG queries.

**Requirements:**
- Shape user input into problem-aware queries
- Include full conversation context in RAG queries
- Requires a "fast model" field in organization setup (e.g., `gpt-4o-nano`)

---

## 3. Current Architecture Analysis

### 3.1 Completion Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    POST /v1/chat/completions                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    run_lamb_assistant()                              │
│                    backend/lamb/completions/main.py                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  RAG Processor│     │ Prompt        │     │  Connector    │
│  (rag/)       │     │ Processor     │     │  (connectors/)│
│               │     │ (pps/)        │     │               │
│ • simple_rag  │     │ • simple_     │     │ • openai      │
│ • rubric_rag  │     │   augment     │     │ • ollama      │
│ • no_rag      │     │               │     │ • banana_img  │
│ • single_file │     │               │     │ • bypass      │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └──────── context ────┴──── messages ───────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   LLM Provider    │
                    │  (OpenAI, Ollama) │
                    └───────────────────┘
```

### 3.2 Current Plugin Architecture

**Prompt Processors (PPS):**
- Location: `/backend/lamb/completions/pps/`
- Current: `simple_augment.py`
- Function signature:
```python
def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
```

**Connectors:**
- Location: `/backend/lamb/completions/connectors/`
- Current: `openai.py`, `ollama.py`, `banana_img.py`, `bypass.py`
- Function signature:
```python
async def llm_connect(
    messages: list, 
    stream: bool = False, 
    body: Dict[str, Any] = None, 
    llm: str = None, 
    assistant_owner: Optional[str] = None
):
```

**RAG Processors:**
- Location: `/backend/lamb/completions/rag/`
- Current: `simple_rag.py`, `rubric_rag.py`, `single_file_rag.py`, `no_rag.py`
- Function signature:
```python
def rag_processor(
    messages: List[Dict[str, Any]], 
    assistant: Assistant = None
) -> Dict[str, Any]:
```

### 3.3 Assistant Metadata Structure

Stored in `api_callback` column (accessed via `.metadata` property):

```json
{
  "prompt_processor": "simple_augment",
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "rag_processor": "simple_rag",
  "capabilities": {
    "vision": false,
    "image_generation": false
  }
}
```

### 3.4 Existing MCP Foundation

LAMB already has MCP endpoints (`/lamb/v1/mcp/`) that:
- Expose assistants as MCP prompts
- Return fully crafted prompts with RAG context
- Do NOT execute the LLM (prompt templates only)

This provides a foundation for the tool assistant architecture.

---

## 4. Proposed Tool Assistant Architecture

### 4.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Tool-Using Assistant                            │
│                      (prompt_processor: tool_augment)                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Tool-Use Connector (e.g., openai_tool_use)             │
│                                                                      │
│  1. Send messages with tool definitions to LLM                       │
│  2. Receive tool_call response                                       │
│  3. Execute tool via Tool Invocation API                             │
│  4. Send tool results back to LLM                                    │
│  5. Return final response                                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │                                               │
        ▼                                               ▼
┌───────────────────┐                     ┌───────────────────────────┐
│  Tool Invocation  │                     │      LLM Provider         │
│       API         │                     │   (with function calling) │
│                   │                     │                           │
│ invoke_tool()     │                     │ • OpenAI (tools API)      │
│ • kb_query        │                     │ • Ollama (if supported)   │
│ • assistant_call  │                     │ • Claude (tools API)      │
│ • rubric_eval     │                     └───────────────────────────┘
│ • image_gen       │
└─────────┬─────────┘
          │
          ▼
┌───────────────────────────────────────────────────────────────────┐
│                     Assistant as Tool                              │
│                                                                    │
│  Non-streaming invocation of target assistant:                     │
│  • Get assistant by ID                                             │
│  • Run completion pipeline (without streaming)                     │
│  • Return result as tool output                                    │
└───────────────────────────────────────────────────────────────────┘
```

### 4.2 Tool-Using Assistant Flow

```
User Message
     │
     ▼
┌─────────────────────────────────────────┐
│ tool_augment.py (Prompt Processor)      │
│                                         │
│ 1. Add system prompt with tool context  │
│ 2. Include tool definitions in messages │
│ 3. Format: OpenAI function calling      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ openai_tool_use.py (Connector)          │
│                                         │
│ 1. Call LLM with tools enabled          │
│ 2. Handle tool_calls in response        │
│ 3. Execute tools via invoke_tool()      │
│ 4. Loop until finish_reason == "stop"   │
│ 5. Return final message                 │
└─────────────────────────────────────────┘
```

### 4.3 Assistant as Tool Invocation

```python
# Proposed: backend/lamb/completions/tool_invocation.py

async def invoke_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    caller_assistant_id: int,
    caller_owner: str
) -> Dict[str, Any]:
    """
    Invoke a LAMB tool and return the result.
    
    Tool Types:
    - assistant_call: Invoke another assistant
    - kb_query: Query a knowledge base
    - image_gen: Generate an image
    - rubric_eval: Evaluate using a rubric
    
    Returns:
        Dict with tool result (always non-streaming)
    """
    
async def invoke_assistant_as_tool(
    assistant_id: int,
    user_input: str,
    caller_owner: str
) -> str:
    """
    Invoke an assistant as a tool (non-streaming).
    
    1. Load target assistant
    2. Check access permissions
    3. Run completion pipeline (stream=False)
    4. Extract and return response content
    """
```

### 4.4 Tool Definition Schema

```json
{
  "type": "function",
  "function": {
    "name": "call_assistant_42",
    "description": "Expert in mathematics education - helps with algebra problems",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The question or task for this assistant"
        }
      },
      "required": ["query"]
    }
  }
}
```

### 4.5 Assistant Metadata Extension

```json
{
  "prompt_processor": "tool_augment",
  "connector": "openai_tool_use",
  "llm": "gpt-4o",
  "rag_processor": "",
  "capabilities": {
    "vision": false,
    "tool_use": true
  },
  "tools": [
    {
      "type": "assistant",
      "assistant_id": 42,
      "name": "math_expert",
      "description": "Expert in mathematics education"
    },
    {
      "type": "assistant",
      "assistant_id": 55,
      "name": "image_creator",
      "description": "Creates educational diagrams"
    },
    {
      "type": "knowledge_base",
      "kb_id": "abc123",
      "name": "course_materials",
      "description": "Course textbook and materials"
    }
  ]
}
```

---

## 5. Security Model

### 5.1 Core Security Principle: Execution-Time Validation

**Key Insight:** Tool descriptions can be prompt-injected, so permissions must be validated at execution time, not definition time.

**Why This Matters:**
- An LLM could be tricked into calling tools it shouldn't have access to
- Tool definitions in prompts are untrusted (they go through the LLM)
- Only the actual tool invocation is the point of truth

### 5.2 Permission Validation Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TWO-LAYER PERMISSION MODEL                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LAYER 1: Tool Definition Time (Soft Filter)                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Filter tool list to show only accessible tools               │ │
│  │ • Reduces token waste on inaccessible tools                    │ │
│  │ • NOT a security boundary (can be bypassed)                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  LAYER 2: Tool Execution Time (Hard Enforcement)                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • ALWAYS validate permissions before execution                 │ │
│  │ • Check: caller_owner owns OR is_shared_with target           │ │
│  │ • Return clear error if denied                                 │ │
│  │ • THIS IS THE SECURITY BOUNDARY                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Access Control Rules

**Who can invoke an assistant as a tool?**

| Target Assistant State | Can Invoke? | Rationale |
|------------------------|-------------|-----------|
| Owned by caller_owner | ✅ YES | Owner has full control |
| Shared with caller_owner | ✅ YES | Explicit permission granted |
| Published assistant | ✅ YES | Public access (with usage tracking) |
| Not owned, not shared, not published | ❌ NO | No permission |

### 5.4 Implementation

```python
# backend/lamb/completions/tool_invocation.py

async def validate_tool_access(
    target_assistant_id: int,
    caller_owner: str
) -> Tuple[bool, str]:
    """
    Validate if caller_owner can invoke target assistant as a tool.
    
    IMPORTANT: This is called at EXECUTION TIME, not definition time.
    
    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    db = LambDatabaseManager()
    
    # Get target assistant
    target = db.get_assistant_by_id(target_assistant_id)
    if not target:
        return (False, f"Assistant {target_assistant_id} not found")
    
    # Rule 1: Owner owns target
    if target.owner == caller_owner:
        return (True, "Owner access")
    
    # Rule 2: Target is shared with owner
    if db.is_assistant_shared_with_user(target_assistant_id, caller_owner):
        return (True, "Shared access")
    
    # Rule 3: Target is published
    if target.published:
        return (True, "Published access")
    
    # Default: Deny
    return (False, f"Access denied: {caller_owner} cannot invoke assistant {target_assistant_id}")


async def invoke_assistant_as_tool(
    assistant_id: int,
    user_input: str,
    caller_owner: str
) -> str:
    """
    Invoke an assistant as a tool (non-streaming).
    
    SECURITY: Validates access at execution time.
    """
    # ALWAYS validate at execution time
    allowed, reason = await validate_tool_access(assistant_id, caller_owner)
    if not allowed:
        logger.warning(f"Tool access denied: {reason}")
        return f"Error: {reason}"
    
    # ... proceed with invocation ...
```

### 5.5 Tool Definition Filtering (Soft Layer)

When building tool definitions for the LLM, filter to only include accessible tools:

```python
def get_accessible_tool_definitions(
    assistant: Assistant,
    caller_owner: str
) -> List[Dict]:
    """
    Get tool definitions, filtered to only those the owner can access.
    
    NOTE: This is a soft filter for efficiency, not a security boundary.
    Execution-time validation is still required.
    """
    metadata = json.loads(assistant.metadata or '{}')
    tools_config = metadata.get('tools', [])
    
    accessible_definitions = []
    for tool in tools_config:
        if tool['type'] == 'assistant':
            # Pre-check access (soft filter)
            allowed, _ = await validate_tool_access(
                tool['assistant_id'], 
                caller_owner
            )
            if allowed:
                accessible_definitions.append(build_tool_definition(tool))
            else:
                logger.debug(f"Filtering out inaccessible tool: {tool['assistant_id']}")
    
    return accessible_definitions
```

### 5.6 Connector Receives Owner Context

The connector must receive the assistant owner to perform permission checks:

```python
# Connector signature (already has assistant_owner)
async def llm_connect(
    messages: list, 
    stream: bool = False, 
    body: Dict[str, Any] = None, 
    llm: str = None, 
    assistant_owner: Optional[str] = None  # ← Used for permission checks
):
```

The `assistant_owner` is passed through the entire tool invocation chain:
1. `run_lamb_assistant()` gets owner from assistant details
2. Passes to connector via `assistant_owner` parameter
3. Connector passes to `invoke_tool()` for permission validation

---

## 6. Recursion Prevention Rules

### 6.1 The Problem

If a tool-using assistant can also be used as a tool by another tool-using assistant, we risk:
- Infinite loops (A calls B calls A)
- Exponential complexity (depth tracking, circular detection)
- Confusing debugging scenarios
- Unpredictable behavior

### 6.2 The Solution: Hard Separation

**Rule: Tool-Using Assistants CANNOT be used as Tools**

This creates two distinct categories of assistants:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ASSISTANT CATEGORIES                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐ │
│  │   ORCHESTRATOR          │    │   TOOL ASSISTANT                │ │
│  │   (Tool-Using)          │    │   (Can be used as tool)         │ │
│  ├─────────────────────────┤    ├─────────────────────────────────┤ │
│  │ • Uses tool_use         │    │ • Standard connectors           │ │
│  │   connector             │    │   (openai, ollama, banana_img)  │ │
│  │ • Can call other        │    │ • Can be configured as a tool   │ │
│  │   assistants as tools   │    │ • Cannot use tools itself       │ │
│  │ • CANNOT be a tool      │    │                                 │ │
│  │   itself                │    │                                 │ │
│  └─────────────────────────┘    └─────────────────────────────────┘ │
│                                                                      │
│           │                               ▲                          │
│           │         can invoke            │                          │
│           └───────────────────────────────┘                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Implementation

**Detection: Is this a tool-using assistant?**

```python
def is_tool_using_assistant(assistant_id: int) -> bool:
    """
    Check if an assistant uses a tool-use connector.
    
    Tool-using assistants CANNOT be used as tools themselves.
    """
    db = LambDatabaseManager()
    assistant = db.get_assistant_by_id(assistant_id)
    if not assistant:
        return False
    
    metadata = json.loads(assistant.metadata or '{}')
    connector = metadata.get('connector', '')
    
    # Any connector with 'tool_use' in the name is a tool-using connector
    return 'tool_use' in connector.lower()
```

**Enforcement at Configuration Time:**

```python
def validate_tool_configuration(
    orchestrator_assistant: Assistant,
    tool_assistant_id: int
) -> Tuple[bool, str]:
    """
    Validate that a tool assistant can be added to an orchestrator.
    
    Called when configuring tools in the UI/API.
    """
    # Check if target is a tool-using assistant
    if is_tool_using_assistant(tool_assistant_id):
        return (False, "Tool-using assistants cannot be used as tools")
    
    return (True, "OK")
```

**Enforcement at Execution Time:**

```python
async def invoke_assistant_as_tool(
    assistant_id: int,
    user_input: str,
    caller_owner: str
) -> str:
    """
    Invoke an assistant as a tool.
    
    SECURITY: Validates that target is not a tool-using assistant.
    """
    # Check recursion rule
    if is_tool_using_assistant(assistant_id):
        logger.error(f"Attempted to invoke tool-using assistant {assistant_id} as tool")
        return "Error: Tool-using assistants cannot be invoked as tools"
    
    # ... proceed with access validation and invocation ...
```

### 6.4 UI Impact

When selecting tools for a tool-using assistant:
- Filter out other tool-using assistants from the list
- Show clear explanation: "Tool-using assistants cannot be added as tools"
- Optionally show them grayed out with explanation

### 6.5 Benefits of This Approach

| Benefit | Description |
|---------|-------------|
| **Simplicity** | No depth tracking, no circular detection needed |
| **Predictability** | Clear mental model for users |
| **Safety** | Impossible to create infinite loops |
| **Performance** | Maximum depth is always 1 (orchestrator → tool) |
| **Debuggability** | Easy to trace: only one level of indirection |

### 6.6 Future Relaxation (If Needed)

If we ever need nested tool-using assistants:
1. Convert this to a depth limit (e.g., max depth = 2)
2. Add call stack tracking to detect cycles
3. Implement proper timeout handling at each level

But for MVP and likely for a long time, the hard separation is the right choice.

---

## 7. Streaming and User Feedback Strategy

### 7.1 The Challenge

During tool execution, the user experiences dead time:

```
User sends message
     │
     ▼
┌─────────────────────────────────────────┐
│ LLM decides to call tool                │  ← Quick (1-2s)
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Tool executes (another LLM call)        │  ← SLOW (3-10s) 🕐
│ User sees nothing during this time      │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ LLM generates final response            │  ← Can stream this
└─────────────────────────────────────────┘
```

### 7.2 Streaming Strategy: Phased Approach

#### Phase 1 (MVP): Stream Final Response Only

**Approach:** Tool execution is synchronous/blocking, but the final LLM response streams to the user.

```python
async def tool_use_connector(messages, stream, body, llm, assistant_owner):
    """
    Tool-use connector with final response streaming.
    """
    # Phase 1: Get tool calls (non-streaming)
    response = await client.chat.completions.create(
        model=llm,
        messages=messages,
        tools=tool_definitions,
        stream=False  # Non-streaming for tool decision
    )
    
    # Phase 2: Execute tools (blocking)
    while response.choices[0].finish_reason == "tool_calls":
        tool_results = []
        for tool_call in response.choices[0].message.tool_calls:
            result = await invoke_tool(
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
                assistant_owner
            )
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
        
        # Get next response
        messages.extend([response.choices[0].message] + tool_results)
        response = await client.chat.completions.create(
            model=llm,
            messages=messages,
            tools=tool_definitions,
            stream=False
        )
    
    # Phase 3: Stream final response
    if stream:
        final_response = await client.chat.completions.create(
            model=llm,
            messages=messages,
            stream=True  # STREAM the final response
        )
        async for chunk in final_response:
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
    else:
        return response.model_dump()
```

**Pros:**
- Simple to implement
- Final response feels responsive
- No frontend changes required

**Cons:**
- No feedback during tool execution
- User may think it's stuck

#### Phase 2 (Enhancement): Status Messages

**Approach:** Add lightweight status updates between tool calls.

```python
async def tool_use_connector_with_status(messages, stream, body, llm, assistant_owner):
    """
    Tool-use connector with status messages.
    """
    # ... tool decision phase ...
    
    while response.choices[0].finish_reason == "tool_calls":
        for tool_call in response.choices[0].message.tool_calls:
            # Send status message
            if stream:
                tool_name = tool_call.function.name
                status_msg = {
                    "type": "status",
                    "status": "tool_call",
                    "tool": tool_name,
                    "message": f"🔧 Calling {tool_name}..."
                }
                yield f"data: {json.dumps(status_msg)}\n\n"
            
            # Execute tool
            result = await invoke_tool(...)
            
            # Send completion status
            if stream:
                status_msg = {
                    "type": "status",
                    "status": "tool_complete",
                    "tool": tool_name,
                    "message": f"✅ {tool_name} completed"
                }
                yield f"data: {json.dumps(status_msg)}\n\n"
        
        # ... continue loop ...
    
    # ... stream final response ...
```

**Frontend Handling:**

```javascript
// In chat component
function handleStreamChunk(chunk) {
    const data = JSON.parse(chunk);
    
    if (data.type === 'status') {
        // Show status in UI (e.g., typing indicator with message)
        showStatus(data.message);
    } else if (data.choices) {
        // Normal content chunk
        appendContent(data.choices[0].delta.content);
    }
}
```

**Pros:**
- User knows what's happening
- Reduces perceived wait time
- Clear feedback on progress

**Cons:**
- Non-standard format (not OpenAI compatible)
- Frontend needs to handle status messages
- Slightly more complex implementation

### 7.3 Recommended Implementation Order

| Phase | Feature | Priority | Effort |
|-------|---------|----------|--------|
| **MVP** | Stream final response only | HIGH | Low |
| **v1.1** | Status messages during tool calls | MED | Medium |
| **Future** | Tool call streaming (OpenAI format) | LOW | High |

### 7.4 User Experience Guidelines

**During Tool Execution (MVP):**
- Frontend shows generic "thinking..." or spinner
- No specific tool feedback yet

**During Tool Execution (with Status):**
- Show tool name being called
- Show completion of each tool
- Optionally show elapsed time

**Final Response:**
- Always stream when `stream=True`
- User sees text appearing in real-time

---

## 8. Changes Required

### 8.1 New Files to Create

| File | Type | Description |
|------|------|-------------|
| `backend/lamb/completions/pps/tool_augment.py` | PPS | Prompt processor for tool-using assistants |
| `backend/lamb/completions/pps/context_aware_augment.py` | PPS | LLM-enhanced RAG query processor |
| `backend/lamb/completions/connectors/openai_tool_use.py` | Connector | OpenAI connector with tool calling support |
| `backend/lamb/completions/tool_invocation.py` | Core | Tool invocation API |
| `backend/lamb/completions/tool_registry.py` | Core | Registry for available tools per assistant |

### 8.2 Files to Modify

| File | Changes |
|------|---------|
| `backend/lamb/completions/main.py` | Add non-streaming tool invocation path |
| `backend/lamb/lamb_classes.py` | Add `tools` field to Assistant model |
| `backend/lamb/database_manager.py` | Handle tools JSON in metadata |
| `backend/lamb/completions/org_config_resolver.py` | Add `fast_model` config |
| `backend/creator_interface/assistant_router.py` | Handle tool configuration |
| `frontend/.../AssistantForm.svelte` | Add tool configuration UI |

### 8.3 Database Schema Changes

**Option A: Extend metadata JSON** (Recommended)
- Store tools configuration in existing `api_callback` column
- No schema migration required
- Backward compatible

**Option B: New column**
```sql
ALTER TABLE assistants ADD COLUMN tools_config JSON;
```

### 8.4 Organization Config Changes

Add to organization setup:
```json
{
  "setups": {
    "default": {
      "providers": {
        "openai": {
          "fast_model": "gpt-4o-mini",
          "tool_use_model": "gpt-4o"
        }
      }
    }
  }
}
```

---

## 9. Viability Assessment

### 9.1 Technical Feasibility: ✅ HIGH

**Strengths:**
- Plugin architecture already supports new PPS and connectors
- Existing MCP code provides templates for tool definitions
- OpenAI/Anthropic tool calling APIs are well-documented
- `run_lamb_assistant()` already supports non-streaming mode

**Challenges:**
- Recursive tool calls need depth limits
- Tool execution timeout handling
- Access control for cross-assistant calls

### 9.2 Architectural Fit: ✅ EXCELLENT

The "Assistants as Tools" approach fits perfectly with LAMB's design:
- **Modularity:** Each assistant remains independent
- **Extensibility:** New tool types via plugin pattern
- **Security:** All access through LAMB's existing auth
- **Simplicity:** One invocation pattern for all tools

### 9.3 Security Considerations: ✅ ADDRESSED

See [Section 5: Security Model](#5-security-model) for the complete security architecture including:
- Two-layer permission model (soft filter + hard enforcement)
- Execution-time validation
- Owner-based access control

See [Section 6: Recursion Prevention Rules](#6-recursion-prevention-rules) for:
- Hard separation between orchestrators and tool assistants
- Prevention of infinite loops

### 9.4 Performance Impact: ⚠️ MODERATE

**Concerns:**
- Tool calls add latency (sequential LLM calls)
- Multiple tool invocations multiply API costs
- Non-streaming tool calls may feel slower

**Mitigations:**
- Parallel tool execution where possible
- Streaming for final response
- Cost tracking and limits per organization
- Fast model for simple routing decisions

---

## 10. Implementation Tasks

### Phase 1: Foundation (Est. 2-3 weeks)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 1.1 | Create `tool_invocation.py` with `invoke_tool()` API | HIGH | M |
| 1.2 | Implement `invoke_assistant_as_tool()` | HIGH | M |
| 1.3 | Add tool access control checks | HIGH | S |
| 1.4 | Create `tool_augment.py` prompt processor | HIGH | M |
| 1.5 | Write unit tests for tool invocation | HIGH | S |

### Phase 2: Tool-Use Connector (Est. 2-3 weeks)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 2.1 | Create `openai_tool_use.py` connector | HIGH | L |
| 2.2 | Implement tool call → execute → respond loop | HIGH | M |
| 2.3 | Handle streaming for final response only | MED | M |
| 2.4 | Add tool execution timeout handling | MED | S |
| 2.5 | Implement tool-using assistant exclusion check | MED | S |
| 2.6 | Write integration tests | HIGH | M |

### Phase 3: Context-Aware Augment (Est. 1-2 weeks)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 3.1 | Add `fast_model` to organization config | MED | S |
| 3.2 | Create `context_aware_augment.py` | MED | M |
| 3.3 | Implement conversation-aware query building | MED | M |
| 3.4 | Write tests for query enhancement | MED | S |

### Phase 4: Frontend & UX (Est. 2-3 weeks)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 4.1 | Design tool configuration UI mockups | MED | S |
| 4.2 | Create ToolSelector component | MED | M |
| 4.3 | Update AssistantForm for tool config | MED | M |
| 4.4 | Add tool-using assistant template | LOW | S |
| 4.5 | Documentation and help text | LOW | S |

### Phase 5: Testing & Documentation (Est. 1-2 weeks)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 5.1 | End-to-end testing scenarios | HIGH | M |
| 5.2 | Performance benchmarking | MED | M |
| 5.3 | Update architecture documentation | MED | M |
| 5.4 | Create user guide for tool assistants | LOW | S |

**Legend:** S = Small (1-2 days), M = Medium (3-5 days), L = Large (1+ week)

---

## 11. Risk Analysis

### 11.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Infinite recursion in tool calls | ~~Medium~~ **Eliminated** | High | Tool-using assistants cannot be tools (hard rule) |
| Tool timeout causing user frustration | High | Medium | Configurable timeouts, progress indication |
| High API costs from nested calls | Medium | Medium | Cost tracking, org-level limits |
| Security bypass via tool calls | Low | Critical | Execution-time validation (Section 5) |

### 11.2 Architectural Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-complexity in tool connector | Medium | Medium | Start simple, iterate |
| Breaking existing assistants | Low | High | Separate new connectors, don't modify existing |
| Performance regression | Medium | Medium | Benchmark before/after, optimize hot paths |

### 11.3 User Experience Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Confusing tool configuration UI | Medium | Medium | Clear documentation, templates |
| Unpredictable tool behavior | Medium | Medium | Logging, debug mode |
| Long response times | High | Medium | Status messages + streaming final response (Section 7) |

---

## 12. Recommendations

### 12.1 Implementation Strategy

1. **Start with Issue #137 (Assistants as Tools)**
   - This is the foundation for everything else
   - Implement `invoke_assistant_as_tool()` first
   - Test thoroughly before proceeding

2. **Then Issue #138 (Tool Use Assistants)**
   - Build `tool_augment.py` and `openai_tool_use.py`
   - Support OpenAI models first (best tool calling support)
   - Add Ollama support later if models support it

3. **Finally Issue #140 (Context-Aware Augment)**
   - Lower priority but high value
   - Can be developed in parallel with Phase 2

### 12.2 Minimum Viable Implementation

For a quick win, focus on:
1. `invoke_assistant_as_tool()` - non-streaming assistant invocation
2. `tool_augment.py` - basic tool definition injection
3. `openai_tool_use.py` - simple tool call loop

Skip for MVP:
- Parallel tool execution
- Complex UI (use JSON config initially)
- Multiple LLM provider support

### 12.3 Future Enhancements

After MVP:
- **Tool marketplace:** Share tool-assistants across organizations
- **REACT agent patterns:** Multi-step reasoning
- **Memory/state:** Persist tool outputs across turns
- **Ollama tool support:** When models support it
- **MCP integration:** Once security model is proven

### 12.4 Success Metrics

| Metric | Target |
|--------|--------|
| Tool invocation latency | < 5s for simple tools |
| Tool-using assistant adoption | 10% of new assistants |
| API cost overhead | < 2x compared to non-tool |
| Security incidents | 0 |

---

## Appendix A: Code Sketches

### A.1 Tool Augment Prompt Processor

```python
# backend/lamb/completions/pps/tool_augment.py

def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Tool-augmented prompt processor.
    
    Adds tool definitions to messages for tool-using assistants.
    """
    messages = request.get('messages', [])
    if not messages:
        return messages

    processed_messages = []
    
    if assistant:
        # Add system prompt with tool-use instructions
        system_content = assistant.system_prompt or ""
        system_content += "\n\nYou have access to the following tools..."
        
        processed_messages.append({
            "role": "system",
            "content": system_content
        })
        
        # Add conversation history
        processed_messages.extend(messages)
    
    return processed_messages

def get_tool_definitions(assistant: Assistant) -> List[Dict]:
    """Extract tool definitions from assistant metadata"""
    metadata = json.loads(assistant.metadata or '{}')
    tools_config = metadata.get('tools', [])
    
    definitions = []
    for tool in tools_config:
        if tool['type'] == 'assistant':
            definitions.append({
                "type": "function",
                "function": {
                    "name": f"call_assistant_{tool['assistant_id']}",
                    "description": tool.get('description', ''),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The question or task"
                            }
                        },
                        "required": ["query"]
                    }
                }
            })
    
    return definitions
```

### A.2 Tool Invocation API

```python
# backend/lamb/completions/tool_invocation.py

def is_tool_using_assistant(assistant_id: int) -> bool:
    """
    Check if an assistant uses a tool-use connector.
    Tool-using assistants CANNOT be used as tools themselves.
    """
    db = LambDatabaseManager()
    assistant = db.get_assistant_by_id(assistant_id)
    if not assistant:
        return False
    
    metadata = json.loads(assistant.metadata or '{}')
    connector = metadata.get('connector', '')
    return 'tool_use' in connector.lower()


async def validate_tool_access(
    target_assistant_id: int,
    caller_owner: str
) -> Tuple[bool, str]:
    """
    Validate if caller_owner can invoke target assistant as a tool.
    Called at EXECUTION TIME, not definition time.
    """
    db = LambDatabaseManager()
    target = db.get_assistant_by_id(target_assistant_id)
    
    if not target:
        return (False, f"Assistant {target_assistant_id} not found")
    
    # Rule 0: Tool-using assistants cannot be tools
    if is_tool_using_assistant(target_assistant_id):
        return (False, "Tool-using assistants cannot be invoked as tools")
    
    # Rule 1: Owner owns target
    if target.owner == caller_owner:
        return (True, "Owner access")
    
    # Rule 2: Target is shared with owner
    if db.is_assistant_shared_with_user(target_assistant_id, caller_owner):
        return (True, "Shared access")
    
    # Rule 3: Target is published
    if target.published:
        return (True, "Published access")
    
    return (False, f"Access denied: {caller_owner} cannot invoke assistant {target_assistant_id}")


async def invoke_assistant_as_tool(
    assistant_id: int,
    user_input: str,
    caller_owner: str
) -> str:
    """
    Invoke an assistant as a tool (non-streaming).
    
    Security:
    - Validates at EXECUTION TIME (not definition time)
    - Checks tool-using assistants cannot be tools (prevents recursion)
    - Enforces owner-based access control
    """
    # ALWAYS validate at execution time
    allowed, reason = await validate_tool_access(assistant_id, caller_owner)
    if not allowed:
        logger.warning(f"Tool access denied: {reason}")
        return f"Error: {reason}"
    
    # Build request
    request = {
        "messages": [{"role": "user", "content": user_input}],
        "stream": False
    }
    
    # Run assistant (non-streaming)
    response = await run_lamb_assistant(
        request=request,
        assistant=assistant_id,
        headers={}
    )
    
    # Extract content from response
    if isinstance(response, Response):
        result = json.loads(response.body)
        return result['choices'][0]['message']['content']
    
    return str(response)
```

---

## Appendix B: References

- **Issue #137:** [Assistant as a Tool](https://github.com/Lamb-Project/lamb/issues/137)
- **Issue #138:** [Tool use assistants](https://github.com/Lamb-Project/lamb/issues/138)
- **Issue #140:** [Context aware augment prompt processor](https://github.com/Lamb-Project/lamb/issues/140)
- **OpenAI Function Calling:** https://platform.openai.com/docs/guides/function-calling
- **MCP Protocol:** https://modelcontextprotocol.io/

---

**Document Status:** Draft for Review  
**Author:** Generated by AI Analysis  
**Reviewers:** LAMB Development Team

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 4, 2025 | Initial analysis |
| 1.1 | Dec 4, 2025 | Added Security Model (Section 5), Recursion Prevention Rules (Section 6), Streaming Strategy (Section 7). Updated risk analysis to reflect eliminated recursion risk. |

