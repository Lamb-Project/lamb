# Tool Calling Proof of Concept for LAMB Assistants

## Overview

This proof of concept demonstrates how to provide tools (functions) to LLMs used by LAMB assistants. The implementation follows OpenAI's function calling API format.

## Files Created

1. **`/backend/lamb/completions/tools/__init__.py`** - Tools module package
2. **`/backend/lamb/completions/tools/weather.py`** - Weather tool implementation
3. **`/backend/lamb/completions/connectors/openai_tools.py`** - Tool-enabled OpenAI connector

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Calling Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. User asks: "What's the temperature in Paris?"                │
│                      │                                            │
│                      ▼                                            │
│  2. LAMB sends message to LLM with tool definitions              │
│     (tools: [get_weather])                                       │
│                      │                                            │
│                      ▼                                            │
│  3. LLM decides to use tool and returns:                         │
│     tool_calls: [{name: "get_weather", arguments: {city:"Paris"}}]│
│                      │                                            │
│                      ▼                                            │
│  4. LAMB executes get_weather("Paris")                           │
│     Returns: {"temperature_celsius": 8.2, ...}                   │
│                      │                                            │
│                      ▼                                            │
│  5. LAMB sends tool result back to LLM                           │
│                      │                                            │
│                      ▼                                            │
│  6. LLM generates final response:                                │
│     "The current temperature in Paris is 8.2°C..."               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## How to Test

### Step 1: Create or Modify an Assistant

Configure an assistant to use the `openai_tools` connector. Update the assistant's metadata (stored in `api_callback` column):

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai_tools",
    "llm": "gpt-4o-mini",
    "rag_processor": "no_rag"
}
```

### Step 2: Test via API

```bash
# Using the completions API directly
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer YOUR_LAMB_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lamb_assistant.YOUR_ASSISTANT_ID",
    "messages": [
      {"role": "user", "content": "What is the current temperature in Paris?"}
    ],
    "stream": false
  }'
```

### Step 3: Expected Response

The assistant should return something like:

```
The current temperature in Paris, France is 8.2°C with mainly clear skies.
```

## Supported Cities

The weather tool currently supports:
- Paris (default)
- London
- New York
- Tokyo
- Sydney
- Berlin
- Madrid
- Rome
- Amsterdam
- Singapore

## How to Add New Tools

### 1. Create a new tool file

Create `/backend/lamb/completions/tools/my_tool.py`:

```python
import json
from typing import Dict, Any

# Tool specification (OpenAI format)
MY_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Description of what the tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1"
                }
            },
            "required": ["param1"]
        }
    }
}

async def my_tool(param1: str) -> str:
    """Execute the tool and return result as JSON string."""
    result = {"output": f"Processed {param1}"}
    return json.dumps(result)
```

### 2. Register the tool in the connector

Edit `/backend/lamb/completions/connectors/openai_tools.py`:

```python
from lamb.completions.tools.my_tool import my_tool, MY_TOOL_SPEC

# Add to AVAILABLE_TOOLS
AVAILABLE_TOOLS = [WEATHER_TOOL_SPEC, MY_TOOL_SPEC]

# Add to TOOL_FUNCTIONS
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "my_tool": my_tool
}
```

### 3. Export from package (optional)

Update `/backend/lamb/completions/tools/__init__.py`:

```python
from .weather import get_weather, WEATHER_TOOL_SPEC
from .my_tool import my_tool, MY_TOOL_SPEC

__all__ = ['get_weather', 'WEATHER_TOOL_SPEC', 'my_tool', 'MY_TOOL_SPEC']
```

## Future Enhancements

### 1. Per-Assistant Tool Configuration

Store tools in assistant metadata:

```json
{
    "connector": "openai_tools",
    "tools": ["get_weather", "search_web", "calculate"],
    "tool_config": {
        "get_weather": {
            "default_city": "Paris"
        }
    }
}
```

### 2. Dynamic Tool Loading

Load tools from a database or configuration file instead of hardcoding.

### 3. UI for Tool Management

Add a Tools section in the Creator Interface where educators can:
- Browse available tools
- Enable/disable tools per assistant
- Configure tool parameters
- Create simple tools without coding (e.g., API call tools)

### 4. Tool Permissions

Add organization-level tool permissions to control which tools are available to which users/organizations.

### 5. Streaming Optimization

The current streaming implementation buffers the response to detect tool calls. A more sophisticated approach could stream partial responses while tool calls are pending.

## Limitations

1. **Non-Streaming Tool Calls**: When tools are called during streaming, there's a delay while tools execute
2. **Max Iterations**: Limited to 5 tool call iterations to prevent infinite loops
3. **Hardcoded Tools**: Tools are currently hardcoded in the connector
4. **No Tool Authentication**: Tools don't have per-user authentication (e.g., for API keys)

## Dependencies

The weather tool uses:
- `httpx` for async HTTP requests (should already be installed)
- Open-Meteo API (free, no API key required)

If `httpx` is not installed:
```bash
pip install httpx
```
