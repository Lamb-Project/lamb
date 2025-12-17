# Context-Aware RAG Processor

## Overview

The `context_aware_rag.py` processor is an enhanced version of `simple_rag.py` that leverages the full conversation history to generate optimal queries for RAG (Retrieval-Augmented Generation) retrieval.

## Key Features

### 1. **Full Conversation Context Analysis**
Unlike `simple_rag.py` which only uses the last user message, this processor:
- Analyzes the entire conversation history (up to last 10 messages)
- Understands multi-turn context and references
- Tracks conversation flow and topic evolution

### 2. **AI-Powered Query Optimization**
Uses the organization's configured `small-fast-model` to:
- Generate semantically rich queries from conversation context
- Incorporate relevant keywords and concepts from previous turns
- Create focused, specific queries optimized for vector search

### 3. **Intelligent Fallback**
Gracefully handles edge cases:
- Falls back to last user message if small-fast-model is not configured
- Falls back if query optimization fails
- Handles multimodal content (extracts text from image messages)

### 4. **Cost-Effective**
- Uses small-fast-model (e.g., gpt-4o-mini) for query optimization
- Significantly cheaper than using main model for this task
- Typically 98% cost reduction for auxiliary operations

## How It Works

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Receive Full Conversation History                       │
│     - System messages                                        │
│     - Previous user/assistant turns                          │
│     - Current user message                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Check Small-Fast-Model Configuration                    │
│     - Is it configured for this organization?               │
│     - If NO → Use last user message as query                │
│     - If YES → Continue to optimization                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Build Conversation Summary                              │
│     - Extract last 10 messages (to save tokens)             │
│     - Handle multimodal content (extract text)              │
│     - Truncate very long messages (>500 chars)              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Invoke Small-Fast-Model for Query Optimization          │
│     - Send conversation summary                             │
│     - Request optimal search query                          │
│     - Extract optimized query from response                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Use Optimized Query for RAG Retrieval                   │
│     - Query each configured knowledge base collection       │
│     - Retrieve relevant documents                           │
│     - Combine contexts and sources                          │
└─────────────────────────────────────────────────────────────┘
```

### Query Optimization Process

The processor sends this prompt to the small-fast-model:

```
System: You are a query optimization assistant for a RAG system.
Analyze the conversation history and generate an optimal search query.

Guidelines:
1. Consider the full conversation context, not just the last message
2. Identify the core information need
3. Include relevant keywords and concepts
4. If the conversation references previous topics, incorporate them
5. Make the query specific and focused
6. Keep the query concise (1-3 sentences max)
7. Return ONLY the optimized query, nothing else

User: [Conversation history]
```

**Example:**

Input conversation:
```
USER: What is photosynthesis?
ASSISTANT: Photosynthesis is the process by which plants convert light energy...
USER: How does it work in detail?
```

Optimized query:
```
detailed explanation of photosynthesis process mechanism light energy conversion chlorophyll
```

## Configuration

### Prerequisites

1. **Small-Fast-Model Configuration** (Recommended)
   - Configure in Organization Admin Settings
   - Example: `openai/gpt-4o-mini` or `ollama/llama3.2:latest`
   - See: [Small Fast Model Implementation Guide](../../../Documentation/small_fast_model_implementation.md)

2. **Knowledge Base Collections**
   - Assistant must have `RAG_collections` configured
   - Collections must exist in the Knowledge Base server

### Assistant Configuration

Set the `rag_processor` in assistant metadata:

```json
{
  "connector": "openai",
  "llm": "gpt-4o",
  "prompt_processor": "simple_augment",
  "rag_processor": "context_aware_rag"
}
```

## Usage

### Via API

The processor is automatically invoked during completion generation:

```python
POST /v1/chat/completions
{
  "model": "assistant-id",
  "messages": [
    {"role": "user", "content": "What is machine learning?"},
    {"role": "assistant", "content": "Machine learning is..."},
    {"role": "user", "content": "How does it differ from deep learning?"}
  ]
}
```

The processor will:
1. Analyze the full conversation
2. Generate query: "difference between machine learning and deep learning comparison"
3. Retrieve relevant documents
4. Return context to completion pipeline

### Programmatic Usage

```python
from lamb.completions.rag.context_aware_rag import rag_processor

# Full conversation history
messages = [
    {"role": "user", "content": "Explain neural networks"},
    {"role": "assistant", "content": "Neural networks are..."},
    {"role": "user", "content": "What about convolutional ones?"}
]

# Invoke processor
result = await rag_processor(
    messages=messages,
    assistant=assistant_object,
    request=request_dict
)

# Result contains:
# - context: Combined document contexts
# - sources: List of source documents with URLs
# - assistant_data: Assistant metadata
# - raw_responses: Raw KB server responses
```

## Comparison with Simple RAG

| Feature | Simple RAG | Context-Aware RAG |
|---------|-----------|-------------------|
| **Query Source** | Last user message only | Full conversation history |
| **Context Awareness** | Single-turn | Multi-turn |
| **Query Optimization** | None | AI-powered using small-fast-model |
| **Cost** | Lower (no extra LLM call) | Slightly higher (small-fast-model call) |
| **Retrieval Quality** | Good for simple queries | Better for complex conversations |
| **Use Case** | Single questions | Multi-turn dialogues |

## When to Use

### Use Context-Aware RAG When:
- ✅ Users engage in multi-turn conversations
- ✅ Questions reference previous context ("What about that?", "Tell me more")
- ✅ Topics evolve throughout conversation
- ✅ You want higher quality retrieval
- ✅ Small-fast-model is configured

### Use Simple RAG When:
- ✅ Single-turn Q&A scenarios
- ✅ Each query is independent
- ✅ Minimizing cost is critical
- ✅ Small-fast-model is not configured
- ✅ Low-latency is essential

## Performance Considerations

### Latency
- **Additional overhead:** ~200-500ms for query optimization
- **Total impact:** Depends on small-fast-model speed
- **Mitigation:** Use fast local models (Ollama) for small-fast-model

### Cost
- **Query optimization:** ~100-200 tokens per request
- **Example cost (gpt-4o-mini):** $0.00003 per optimization
- **Monthly cost (1000 queries/day):** ~$0.90
- **ROI:** Better retrieval often reduces main model token usage

### Token Usage
- **Input tokens:** ~50-150 (conversation summary)
- **Output tokens:** ~20-50 (optimized query)
- **Total:** ~100-200 tokens per request

## Debugging

### Enable Verbose Logging

The processor includes extensive debug output:

```python
# Console output includes:
===== MESSAGES =====
Messages count: 5
[Full message array]
=====

🧠 Analyzing conversation context for optimal query generation...

===== QUERY OPTIMIZATION =====
Conversation context: 5 messages
Optimized query: [generated query]
==============================

📝 Query for RAG retrieval: [final query]

🏢 [RAG/KB] Using organization: 'MyOrg' (owner: user@example.com)
🚀 [RAG/KB] Server: http://kb:9090 | Config: organization | Collections: 2

===== QUERYING COLLECTION: col-123 =====
URL: http://kb:9090/collections/col-123/query
Payload: {...}
Status Code: 200
Response Summary: 3 documents returned
===========================================

===== SUMMARY OF ALL QUERIES =====
Collection col-123: success - 3 documents
===================================
```

### Common Issues

#### 1. "Small-fast-model not configured"
**Solution:** Configure in Organization Admin Settings or processor will fall back to simple behavior

#### 2. "No query could be generated"
**Cause:** Empty conversation or all messages are system messages
**Solution:** Ensure at least one user message exists

#### 3. Query optimization fails
**Cause:** Small-fast-model error or timeout
**Solution:** Processor automatically falls back to last user message

## Examples

### Example 1: Multi-Turn Technical Discussion

**Conversation:**
```
USER: What is Docker?
ASSISTANT: Docker is a containerization platform...
USER: How does it compare to virtual machines?
ASSISTANT: Unlike VMs, Docker containers share the host OS...
USER: What are the performance implications?
```

**Simple RAG Query:**
```
What are the performance implications?
```

**Context-Aware RAG Query:**
```
Docker container performance comparison with virtual machines resource usage overhead
```

**Result:** Context-aware retrieves documents about Docker vs VM performance, while simple RAG might retrieve generic performance documents.

### Example 2: Follow-up Questions

**Conversation:**
```
USER: Explain gradient descent
ASSISTANT: Gradient descent is an optimization algorithm...
USER: What about the learning rate?
```

**Simple RAG Query:**
```
What about the learning rate?
```

**Context-Aware RAG Query:**
```
gradient descent learning rate hyperparameter optimization step size
```

**Result:** Context-aware understands "the learning rate" refers to gradient descent's learning rate.

### Example 3: Pronoun Resolution

**Conversation:**
```
USER: Tell me about neural networks
ASSISTANT: Neural networks are computational models...
USER: How do they learn?
```

**Simple RAG Query:**
```
How do they learn?
```

**Context-Aware RAG Query:**
```
neural network learning process training backpropagation
```

**Result:** Context-aware resolves "they" to "neural networks" and generates a specific query.

## Advanced Configuration

### Custom Query Optimization Prompt

To customize the query optimization behavior, modify the system prompt in `_generate_optimal_query()`:

```python
system_prompt = """You are a query optimization assistant...
[Your custom instructions]
"""
```

### Adjusting Conversation Window

Change the number of messages considered:

```python
# Default: last 10 messages
recent_messages = messages[-10:] if len(messages) > 10 else messages

# Custom: last 20 messages
recent_messages = messages[-20:] if len(messages) > 20 else messages
```

### Message Truncation

Adjust truncation length for long messages:

```python
# Default: 500 characters
if len(content) > 500:
    content = content[:500] + "..."

# Custom: 1000 characters
if len(content) > 1000:
    content = content[:1000] + "..."
```

## Testing

### Unit Test Example

```python
import pytest
from lamb.completions.rag.context_aware_rag import rag_processor

@pytest.mark.asyncio
async def test_context_aware_query_generation():
    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language..."},
        {"role": "user", "content": "What about its performance?"}
    ]
    
    result = await rag_processor(
        messages=messages,
        assistant=test_assistant,
        request={}
    )
    
    assert result["context"] is not None
    assert len(result["sources"]) > 0
```

### Integration Test

```bash
# Test with real assistant
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "assistant-with-context-aware-rag",
    "messages": [
      {"role": "user", "content": "Explain transformers"},
      {"role": "assistant", "content": "Transformers are neural network architectures..."},
      {"role": "user", "content": "How do they handle attention?"}
    ]
  }'
```

## Migration from Simple RAG

To migrate an existing assistant:

1. **Update metadata:**
```python
# Before
metadata = {
    "rag_processor": "simple_rag"
}

# After
metadata = {
    "rag_processor": "context_aware_rag"
}
```

2. **Configure small-fast-model** (optional but recommended):
   - Go to Organization Admin Settings
   - Set small-fast-model (e.g., `openai/gpt-4o-mini`)

3. **Test with multi-turn conversations:**
   - Verify query optimization is working
   - Check retrieval quality improvement

4. **Monitor performance:**
   - Track latency increase
   - Monitor cost impact
   - Measure retrieval quality

## Troubleshooting

### High Latency

**Symptoms:** Completion takes longer than expected

**Solutions:**
1. Use faster small-fast-model (e.g., local Ollama model)
2. Reduce conversation window size
3. Fall back to simple_rag for latency-critical scenarios

### Poor Query Quality

**Symptoms:** Generated queries don't match conversation context

**Solutions:**
1. Adjust system prompt for query optimization
2. Increase conversation window size
3. Use more capable small-fast-model

### Cost Concerns

**Symptoms:** Unexpected increase in LLM costs

**Solutions:**
1. Use cheaper small-fast-model (e.g., gpt-4o-mini instead of gpt-4o)
2. Use local models (Ollama) for zero-cost optimization
3. Reduce conversation window size
4. Fall back to simple_rag for cost-sensitive scenarios

## Future Enhancements

Potential improvements for future versions:

1. **Caching:** Cache optimized queries for similar conversation patterns
2. **Dynamic window:** Adjust conversation window based on relevance
3. **Multi-query:** Generate multiple queries for different aspects
4. **Query refinement:** Iteratively refine query based on retrieval results
5. **Semantic deduplication:** Remove redundant context from multi-turn conversations
6. **Conversation summarization:** Use small-fast-model to summarize long conversations

## References

- [Simple RAG Processor](./simple_rag.py) - Base implementation
- [Small Fast Model Helper](../small_fast_model_helper.py) - Utility functions
- [Small Fast Model Implementation Guide](../../../Documentation/small_fast_model_implementation.md) - Configuration guide
- [LAMB Architecture](../../../Documentation/lamb_architecture.md) - System architecture

## Support

For issues or questions:
1. Check debug output in console logs
2. Verify small-fast-model configuration
3. Test with simple_rag to isolate issues
4. Review conversation history format

## License

Part of the LAMB platform. See main project license.
