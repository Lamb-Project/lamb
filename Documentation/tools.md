# LAMB Tool Support - Development Roadmap

## Overview

This document outlines the implementation plan for adding tool/function calling support to LAMB assistants. The goal is to allow LLMs to call external functions (tools) during conversations, enabling dynamic data retrieval and actions.

## Context

- **LAMB Architecture**: See [lamb_architecture.md](./lamb_architecture.md) for full system documentation
- **Initial POC**: See [TOOL_CALLING_POC.md](./TOOL_CALLING_POC.md) for the proof-of-concept implementation

### Current State (POC Completed)

A working proof-of-concept has been implemented with:

1. **Tools Module** (`/backend/lamb/completions/tools/`)
   - `weather.py` - Get current temperature for cities using Open-Meteo API
   - Modular structure for adding new tools

2. **Tool-Enabled Connector** (`/backend/lamb/completions/connectors/openai_tools.py`)
   - Handles tool calling loop (LLM → tool execution → result → LLM)
   - Supports both streaming and non-streaming responses
   - Max 5 iterations to prevent infinite loops

3. **Test Assistant** (`lamb_assistant.6` - `tool_testing_assistant`)
   - Configured with `openai_tools` connector
   - Successfully calls `get_weather` tool when asked about weather

---

## Phase 1: Backend Tool Registry ✅ COMPLETED

**Completed on:** December 3, 2025

### 1. Tool Registry (`/backend/lamb/completions/tools/__init__.py`)

Created a centralized `TOOL_REGISTRY` dictionary that maps tool names to their specifications and functions:

```python
TOOL_REGISTRY = {
    "weather": {
        "spec": WEATHER_TOOL_SPEC,
        "function": get_weather,
        "description": "Get current temperature for a city",
        "category": "utilities"
    },
    "moodle": {
        "spec": MOODLE_TOOL_SPEC,
        "function": get_moodle_courses,
        "description": "Get user's enrolled courses from Moodle LMS",
        "category": "lms"
    }
}
```

Added helper functions:
- `get_tool_specs(tool_names)` - Get OpenAI-compatible tool specs by names
- `get_tool_function(tool_name)` - Get a specific tool's function
- `list_available_tools()` - List tools with metadata for the UI

### 2. Moodle Tool (`/backend/lamb/completions/tools/moodle.py`)

Implemented to use Moodle Web Services:
- `MOODLE_TOOL_SPEC` - OpenAI function specification
- `get_moodle_courses(user_id)` - Calls Moodle API using `MOODLE_API_URL` + `MOODLE_TOKEN`
- `get_moodle_courses_real()` - Helper that implements the actual API call

### 3. API Endpoint (`/backend/lamb/completions/main.py`)

Added `GET /lamb/v1/completions/tools` endpoint:

```bash
curl http://localhost:9099/lamb/v1/completions/tools
```

Response:
```json
{
  "tools": [
    {"name": "weather", "description": "Get current temperature for a city", "category": "utilities", "function_name": "get_weather"},
    {"name": "moodle", "description": "Get user's enrolled courses from Moodle LMS", "category": "lms", "function_name": "get_moodle_courses"}
  ],
  "count": 2
}
```

---

## Phase 2: Unified Connector ✅ COMPLETED

**Completed on:** December 3, 2025

### Changes Made:

#### 1. `/backend/lamb/completions/connectors/openai.py`

**Added import for tool registry:**
```python
from lamb.completions.tools import TOOL_REGISTRY, get_tool_specs, get_tool_function
```

**Added `get_tools_for_assistant(assistant)` helper function:**
- Reads `tools` array from assistant's metadata JSON
- Returns list of OpenAI-compatible tool specs from the registry

**Added `execute_tool(tool_name, arguments)` async function:**
- Looks up tool by function name in registry
- Executes the tool function (sync or async)
- Returns JSON result

**Updated `llm_connect()` signature:**
```python
async def llm_connect(messages, stream=False, body=None, llm=None, assistant_owner=None, assistant=None):
```
- Added optional `assistant=None` parameter
- Updated docstring with tool calling documentation

**Added `_handle_non_streaming_with_tools(tool_specs)`:**
- Implements tool calling loop for non-streaming requests
- Max 5 iterations to prevent infinite loops
- Executes tools and adds results to conversation

**Added `_handle_streaming_with_tools(tool_specs)`:**
- Implements tool calling loop for streaming requests
- Collects stream chunks to detect tool calls
- Executes tools and continues until final response

**Updated main logic:**
```python
# Check if assistant has tools configured
tool_specs = get_tools_for_assistant(assistant)

if tool_specs:
    if stream:
        return _handle_streaming_with_tools(tool_specs)
    else:
        return await _handle_non_streaming_with_tools(tool_specs)
# ... standard path (no tools)
```

#### 2. `/backend/lamb/completions/main.py`

**Updated `create_completion()`:**
- Now passes `assistant=assistant_details` to connector

**Updated `run_lamb_assistant()`:**
- Now passes `assistant=assistant_details` to connector

### How It Works:

1. When an assistant has `{"tools": ["weather", "moodle"]}` in its metadata
2. The connector detects this via `get_tools_for_assistant(assistant)`
3. Tool specs are included in the OpenAI API call with `tool_choice: "auto"`
4. If the LLM wants to use a tool, the connector:
   - Executes the tool via `execute_tool()`
   - Adds results to the conversation
   - Calls the LLM again
5. This continues until the LLM gives a final response (max 5 iterations)

### Migration Note:

The separate `openai_tools` connector is now deprecated. Assistants can use the standard `openai` connector with tools configured in metadata. Existing assistants using `openai_tools` will continue to work but should be migrated.

---

## Phase 3: Frontend UI ✅ COMPLETED

**Completed on:** December 3, 2025

### Changes Made:

#### `/frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`

**Added Tools State Variables:**
```javascript
// Tools State
let availableTools = $state([]); // Array of tool objects from API
let selectedTools = $state([]);  // Array of selected tool names
let loadingTools = $state(false);
let toolsError = $state('');
let toolsFetchAttempted = $state(false);
```

**Added `fetchAvailableTools()` Function:**
- Calls `GET /lamb/v1/completions/tools` endpoint
- Populates `availableTools` array with tool metadata
- Handles loading states and errors

**Added Tools UI Section:**
- Located after the Vision Capability toggle in Configuration fieldset
- Only visible when OpenAI connector is selected AND (Advanced Mode OR Edit Mode)
- Displays checkboxes for each available tool with:
  - Tool name (capitalized)
  - Category badge
  - Description text
- Shows summary of selected tools below the list

**Updated Metadata Handling:**
- `handleSubmit()`: Includes `tools` array in metadata when saving
- `populateFormFields()`: Loads selected tools from metadata when editing
- `resetFormFieldsToDefaults()`: Resets `selectedTools` to empty array
- Import validation: Logs imported tools count
- Import population: Applies imported tools to form

### UI Requirements Met:
- ☑️ Tools section after "Enable Vision Capability" toggle
- ☑️ Multi-select checkbox list for available tools
- ☑️ Displays Weather and Moodle tools with descriptions
- ☑️ Only shows for OpenAI connector (tool calling requirement)
- ☑️ Only shows in Advanced Mode or Edit Mode

### Data Model:
Tools are stored in assistant metadata:
```json
{
  "prompt_processor": "simple_augment",
  "connector": "openai",
  "llm": "gpt-4.1",
  "rag_processor": "no_rag",
  "tools": ["weather", "moodle"],
  "capabilities": {
    "vision": false
  }
}
```

---

## Phase 4: Moodle Augment Processor ✅ COMPLETED

**Completed on:** December 3, 2025

### New Files Created:

#### `/backend/lamb/completions/pps/moodle_augment.py`

A Moodle-aware prompt processor that extends `simple_augment` functionality with automatic Moodle course information injection.

### Key Features:

**1. User Identification (`_extract_user_id()`)**
Extracts user identifier from multiple sources in priority order:
- `__openwebui_headers__.x-openwebui-user-email` - OpenWebUI user email (optionally resolved to Moodle numeric ID)
- `__openwebui_headers__.x-openwebui-user-id` - OpenWebUI user ID
- `request.metadata.user_id` - Explicitly provided in metadata
- `request.metadata.lti_user_id` - LTI launch user ID
- `request.metadata.lis_person_sourcedid` - LTI person source ID
- `request.metadata.email` - User email in metadata
- Falls back to "default" if none found

**2. Moodle Integration (`_get_moodle_courses_sync()`)**
- Synchronous wrapper around the async Moodle tool
- Uses existing `get_moodle_courses()` from tools registry
- Uses Moodle Web Services when `MOODLE_API_URL` and `MOODLE_TOKEN` are configured

**4. Template Processing**
Supports three template variables:
- `{user_input}` - The user's message/question
- `{context}` - RAG context (if available)
- `{moodle_user}` - Best-effort user identifier (prefers Moodle numeric ID when resolvable)

### Example Usage:

**Prompt Template:**
```
You are an academic advisor helping students.

The student's Moodle identifier is:
{moodle_user}

Help answer:
{user_input}

Additional knowledge base context:
{context}
```

**Generated Prompt:**
```
You are an academic advisor helping students.

The student's Moodle identifier is:
12345

Help answer:
What electives should I take next semester?

Additional knowledge base context:
[RAG retrieved documents here]
```

### Frontend Changes:

**`/backend/static/json/defaults.json`:**
Added `{moodle_user}` to rag_placeholders array.

**`/frontend/svelte-app/src/lib/stores/assistantConfigStore.js`:**
Added `{moodle_user}` to default rag_placeholders.

### How to Use:

1. Create or edit an assistant
2. Select `moodle_augment` as the Prompt Processor
3. In the Prompt Template, use `{moodle_user}` where you want the Moodle user identifier
4. The placeholder button is available in the template editor UI

### Moodle Configuration

- `MOODLE_API_URL` and `MOODLE_TOKEN` must be configured on the backend.
- If configured, `moodle_augment` can resolve an OpenWebUI user email into a Moodle numeric user ID.

---

## Future Work
- Tools registry in `/backend/lamb/completions/tools/`

---

### 2. Implement Moodle Tool

**Location**: `/backend/lamb/completions/tools/moodle.py`

**Specification**:
```python
MOODLE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "get_moodle_courses",
        "description": "Get the list of courses a user is enrolled in from Moodle LMS",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The Moodle user identifier (username or ID)"
                }
            },
            "required": ["user_id"]
        }
    }
}
```

**Implementation**:
- Uses Moodle Web Services (`core_enrol_get_users_courses`) via `MOODLE_API_URL` + `MOODLE_TOKEN`.
- If Moodle is not configured, the tool returns an error response (no mock fallback).

---

### 3. Create Moodle Augment Prompt Processor

**Location**: `/backend/lamb/completions/pps/moodle_augment.py`

**Purpose**: Extends `simple_augment` to automatically inject Moodle user context into prompts.

**New Template Variable**: `{moodle_user}`

**Behavior**:
1. Extract user identifier from LTI launch or session
2. Best-effort resolve OpenWebUI email to Moodle numeric user ID (when configured)
3. Replace `{moodle_user}` in prompt template

**Example Prompt Template**:
```
You are a helpful academic assistant. 

The student's Moodle identifier is:
{moodle_user}

Based on this context, help the student with their question:
{user_input}

Additional context from knowledge base:
{context}
```

**Implementation Skeleton**:
```python
def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Moodle-aware prompt processor.
    
    Extends simple_augment with Moodle user identifier.
    """
    # Get user ID from request metadata or LTI context
    user_id = extract_user_id(request)

    # Replace {moodle_user} in template
    # Apply simple_augment logic with additional variable
    # Replace {moodle_user} in template
    ...
```

---

### 4. Unified Tool Support in OpenAI Connector

**Goal**: Eliminate the need for a separate `openai_tools` connector. The standard `openai` connector should detect when tools are configured and handle them automatically.

**Changes to `/backend/lamb/completions/connectors/openai.py`**:

1. **Detect Tool Configuration**:
```python
def get_tools_for_assistant(assistant: Assistant) -> List[Dict]:
    """Get tool specifications for an assistant based on its config."""
    metadata = json.loads(assistant.metadata or "{}")
    tool_names = metadata.get("tools", [])
    
    if not tool_names:
        return []
    
    # Load tool specs from registry
    return [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
```

2. **Modify `llm_connect` Function**:
```python
async def llm_connect(messages, stream, body, llm, assistant_owner, assistant=None):
    # ... existing setup code ...
    
    # Check if assistant has tools configured
    tools = get_tools_for_assistant(assistant) if assistant else []
    
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
        
        # Use tool calling loop
        return await _handle_with_tools(client, params, messages, tools)
    else:
        # Standard call without tools
        return await _standard_call(client, params)
```

3. **Tool Registry**:
```python
# /backend/lamb/completions/tools/__init__.py
from .weather import get_weather, WEATHER_TOOL_SPEC
from .moodle import get_moodle_courses, MOODLE_TOOL_SPEC

TOOL_REGISTRY = {
    "weather": {
        "spec": WEATHER_TOOL_SPEC,
        "function": get_weather
    },
    "moodle": {
        "spec": MOODLE_TOOL_SPEC,
        "function": get_moodle_courses
    }
}
```

4. **Pass Assistant to Connector**:
   - Modify completion pipeline to pass full assistant object to connector
   - Currently only passes `assistant_owner` (email)

---

## Implementation Order

1. **Phase 1: Backend Tool Registry** ✅ COMPLETED (December 3, 2025)
   - Create tool registry in `/backend/lamb/completions/tools/__init__.py`
    - Implement Moodle tool (requires backend Moodle configuration)
   - Add API endpoint to list available tools

2. **Phase 2: Unified Connector** ✅ COMPLETED (December 3, 2025)
   - Modify OpenAI connector to detect and handle tools
   - Pass assistant object through completion pipeline
   - Remove need for separate `openai_tools` connector

3. **Phase 3: Frontend UI** ✅ COMPLETED (December 3, 2025)
   - Add Tools multi-select to AssistantForm
   - Fetch available tools from API
   - Save tools selection in assistant metadata

4. **Phase 4: Moodle Augment Processor** ✅ COMPLETED (December 3, 2025)
   - Created `moodle_augment.py` prompt processor
   - Implemented user ID extraction from LTI/session
    - Added `{moodle_user}` template variable
   - Added placeholder button to frontend defaults

5. **Phase 5: Real Moodle Integration** (4-6 hours)
   - Add Moodle API configuration to organization settings
   - Implement actual Moodle Web Services calls
   - Handle authentication and error cases

---

## Prompt for AI Assistant

Use the following prompt when working on tool support implementation:

```
I'm working on LAMB, an educational AI platform. I need help implementing tool/function calling support for LLM-powered assistants.

Context:
- LAMB Architecture: /opt/lamb/Documentation/lamb_architecture.md
- Tool Support POC: /opt/lamb/Documentation/TOOL_CALLING_POC.md
- Tool Support Roadmap: /opt/lamb/Documentation/tools.md

Current state:
- POC completed with weather tool and openai_tools connector
- Test assistant (id=6, tool_testing_assistant) working with get_weather

The goal is to:
1. Add a Tools configuration UI in the assistant form
2. Support Weather and Moodle tools
3. Create moodle_augment prompt processor with {moodle_user} variable
4. Integrate tool detection into the standard openai connector (no separate openai_tools needed)

Please review the roadmap in tools.md and help me implement [SPECIFIC TASK].
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `/backend/lamb/completions/tools/__init__.py` | Tool registry |
| `/backend/lamb/completions/tools/weather.py` | Weather tool (implemented) |
| `/backend/lamb/completions/tools/moodle.py` | Moodle tool (to implement) |
| `/backend/lamb/completions/connectors/openai.py` | Main OpenAI connector (to modify) |
| `/backend/lamb/completions/connectors/openai_tools.py` | POC connector (to deprecate) |
| `/backend/lamb/completions/pps/simple_augment.py` | Base prompt processor |
| `/backend/lamb/completions/pps/moodle_augment.py` | Moodle prompt processor (to create) |
| `/frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` | Assistant config UI |
