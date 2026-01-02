# LangSmith Tracing for LAMB Assistants

This guide explains how to use LangSmith to trace LLM calls in LAMB assistants.

## Overview

LAMB now supports optional LangSmith tracing for all LLM completions. When enabled, you can:
- Track all LLM calls and their inputs/outputs
- Monitor assistant performance and usage
- Debug issues with completion pipelines
- Analyze RAG retrieval quality
- View detailed traces in the LangSmith dashboard

## Setup

### 1. Install LangSmith

LangSmith is already included in `requirements.txt`. If you need to install it manually:

```bash
pip install langsmith
```

### 2. Get LangSmith API Key

1. Sign up at [https://smith.langchain.com/](https://smith.langchain.com/)
2. Create a new project (e.g., "lamb-assistants")
3. Get your API key from Settings → API Keys

### 3. Configure Environment Variables

Add these environment variables to enable tracing:

```bash
# Enable LangSmith tracing
export LANGCHAIN_TRACING_V2=true

# Your LangSmith API key
export LANGCHAIN_API_KEY=your_api_key_here

# Project name in LangSmith (optional, defaults to "lamb-assistants")
export LANGCHAIN_PROJECT=lamb-assistants

# LangSmith endpoint (optional, uses default)
export LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

For Docker deployments, add these to your `.env` file or `docker-compose.yaml`:

```yaml
environment:
  - LANGCHAIN_TRACING_V2=true
  - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}
  - LANGCHAIN_PROJECT=lamb-assistants
```

### 4. Restart Backend

```bash
# If running directly
cd backend
uvicorn main:app --reload --port 9099

# If using Docker
docker-compose restart backend
```

## What Gets Traced

When LangSmith tracing is enabled, the following operations are automatically traced:

### 1. Completion Pipeline
- **Function**: `lamb_completion_pipeline` (run_type: "chain")
- **Metadata**:
  - Assistant ID and name
  - Assistant owner
  - Connector type (openai, ollama, etc.)
  - LLM model
  - Prompt processor
  - RAG processor

### 2. OpenAI LLM Calls
- **Function**: `openai_completion` (run_type: "llm")
- **Metadata**:
  - Provider: openai
  - Model name
  - Organization name
  - Configuration source (organization vs env vars)
  - Streaming mode
  - Message count
  - Fallback usage

### 3. Ollama LLM Calls
- **Function**: `ollama_completion` (run_type: "llm")
- **Metadata**:
  - Provider: ollama
  - Model name
  - Organization name
  - Base URL
  - Configuration source
  - Streaming mode
  - Message count
  - Fallback usage

## Viewing Traces

1. Go to [https://smith.langchain.com/](https://smith.langchain.com/)
2. Select your project (e.g., "lamb-assistants")
3. View traces in the dashboard

Each trace includes:
- Input messages
- Output completions
- Latency and timing
- Metadata (model, organization, etc.)
- Nested traces (pipeline → connector → LLM)
- Error information (if any)

## Trace Structure

LAMB traces are hierarchical:

```
lamb_completion_pipeline (chain)
├── Assistant: "Math Tutor" (ID: 42)
├── Owner: user@example.edu
├── Organization: "University XYZ"
├── Connector: openai
├── LLM: gpt-4o-mini
├── RAG: chroma_rag
└── openai_completion (llm)
    ├── Model: gpt-4o-mini
    ├── Messages: 3
    ├── Stream: false
    └── Response: {...}
```

## Disabling Tracing

To disable tracing without removing the code:

```bash
# Set to false or remove the variable
export LANGCHAIN_TRACING_V2=false
```

Or simply don't set the environment variable. LAMB will work normally without tracing overhead.

## Performance Impact

LangSmith tracing has minimal performance impact:
- **Disabled**: No overhead (decorator is pass-through)
- **Enabled**: ~5-10ms per trace (async, non-blocking)
- Network calls to LangSmith are asynchronous
- No impact on streaming responses

## Advanced Usage

### Custom Metadata

You can add custom metadata to traces using the utility functions:

```python
from utils.langsmith_config import add_trace_metadata, add_trace_tags

# Add custom metadata
add_trace_metadata("custom_field", "custom_value")

# Add tags
add_trace_tags("production", "high-priority")
```

### Custom Tracing

To trace your own functions:

```python
from utils.langsmith_config import traceable_llm_call

@traceable_llm_call(name="my_custom_function", run_type="tool", tags=["custom"])
async def my_function():
    # Your code here
    pass
```

### Check if Tracing is Enabled

```python
from utils.langsmith_config import is_tracing_enabled

if is_tracing_enabled():
    # Do something only when tracing is active
    pass
```

## Troubleshooting

### Traces Not Appearing

1. Check environment variables are set correctly:
   ```bash
   echo $LANGCHAIN_TRACING_V2
   echo $LANGCHAIN_API_KEY
   ```

2. Check backend logs for tracing messages:
   ```
   ✅ LangSmith tracing is ENABLED
   ```

3. Verify API key is valid in LangSmith dashboard

### Import Errors

If you see import errors:
```bash
pip install langsmith
```

### Network Issues

LangSmith traces are sent asynchronously. If there are network issues:
- Traces may be delayed
- Check firewall/proxy settings
- Verify `LANGCHAIN_ENDPOINT` is accessible

## Privacy Considerations

**Important**: LangSmith traces contain:
- User messages and prompts
- LLM responses
- Assistant configurations
- Organization information

Recommendations:
- Use separate LangSmith projects for dev/staging/prod
- Review LangSmith's data retention policies
- Consider self-hosted LangSmith Enterprise for sensitive data
- Use metadata filters to exclude sensitive information

## Integration with Existing Observability

LAMB also supports:
- **Langfuse**: For detailed LLM observability
- **Datadog**: For APM and metrics (`ddtrace`)

These can be used alongside LangSmith for comprehensive observability.

## Example: Analyzing Assistant Performance

1. Enable tracing as described above
2. Make some completions with different assistants
3. In LangSmith dashboard:
   - Filter by `assistant_id` metadata
   - Compare latencies across models
   - Analyze token usage
   - View RAG retrieval quality
   - Debug errors with full context

## Support

For issues or questions:
- LAMB GitHub: https://github.com/Lamb-Project/lamb
- LangSmith Docs: https://docs.smith.langchain.com/
- LangChain Discord: https://discord.gg/langchain

---

**Version**: 1.0  
**Last Updated**: January 2, 2026  
**Maintainers**: LAMB Development Team
