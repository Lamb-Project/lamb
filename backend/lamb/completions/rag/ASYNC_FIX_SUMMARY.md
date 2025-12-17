# Async RAG Processor Fix

## Problem

The `context_aware_rag.py` processor was implemented as an async function:

```python
async def rag_processor(messages, assistant, request):
    # Uses await for small-fast-model calls
    ...
```

However, the completion pipeline was calling RAG processors synchronously, causing this error:

```
TypeError: Object of type coroutine is not JSON serializable
RuntimeWarning: coroutine 'rag_processor' was never awaited
```

## Root Cause

The `get_rag_context()` function in `main.py` was synchronous and called RAG processors without checking if they were async:

```python
# OLD CODE (synchronous)
def get_rag_context(request, rag_processors, rag_processor, assistant_details):
    rag_context = rag_processors[rag_processor](messages=messages, ...)  # ❌ No await
    return rag_context
```

## Solution

Made `get_rag_context()` async and added support for both sync and async RAG processors:

```python
# NEW CODE (async-aware)
async def get_rag_context(request, rag_processors, rag_processor, assistant_details):
    rag_func = rag_processors[rag_processor]
    
    # Check if the RAG processor is async
    if asyncio.iscoroutinefunction(rag_func):
        rag_context = await rag_func(messages=messages, ...)  # ✅ Await if async
    else:
        rag_context = rag_func(messages=messages, ...)  # ✅ Call directly if sync
    
    return rag_context
```

## Changes Made

### File: `/opt/lamb/backend/lamb/completions/main.py`

#### Change 1: Made `get_rag_context()` async (Line ~208)

**Before:**
```python
def get_rag_context(request, rag_processors, rag_processor, assistant_details):
    if rag_processor:
        messages = request.get('messages', [])
        rag_context = rag_processors[rag_processor](messages=messages, ...)
        return rag_context
    return None
```

**After:**
```python
async def get_rag_context(request, rag_processors, rag_processor, assistant_details):
    if rag_processor:
        messages = request.get('messages', [])
        rag_func = rag_processors[rag_processor]
        
        # Check if the RAG processor is async
        if asyncio.iscoroutinefunction(rag_func):
            rag_context = await rag_func(messages=messages, ...)
        else:
            rag_context = rag_func(messages=messages, ...)
        
        return rag_context
    return None
```

#### Change 2: Updated call in `create_completion()` (Line ~112)

**Before:**
```python
rag_context = get_rag_context(request, rag_processors, ...)
```

**After:**
```python
rag_context = await get_rag_context(request, rag_processors, ...)
```

#### Change 3: Updated call in `run_lamb_assistant()` (Line ~287)

**Before:**
```python
rag_context = get_rag_context(request, rag_processors, ...)
```

**After:**
```python
rag_context = await get_rag_context(request, rag_processors, ...)
```

## Why This Works

1. **Backward Compatible:** Existing sync RAG processors (`simple_rag`, `no_rag`, etc.) continue to work
2. **Forward Compatible:** New async RAG processors (`context_aware_rag`) now work correctly
3. **No Breaking Changes:** The calling functions (`create_completion`, `run_lamb_assistant`) were already async
4. **Proper Async Handling:** Uses `asyncio.iscoroutinefunction()` to detect async functions

## Testing

### Verify Sync RAG Processors Still Work
- ✅ `no_rag` - Should work (sync)
- ✅ `simple_rag` - Should work (sync)
- ✅ `single_file_rag` - Should work (sync)
- ✅ `rubric_rag` - Should work (sync)

### Verify Async RAG Processor Works
- ✅ `context_aware_rag` - Should now work (async)

## Benefits

1. **Enables Async RAG Processors:** Can now use async operations (LLM calls, API requests, etc.)
2. **Maintains Compatibility:** Existing sync processors work without changes
3. **Clean Implementation:** Uses Python's built-in async detection
4. **Future-Proof:** Easy to add more async RAG processors

## Example: How context_aware_rag Now Works

```
User Request
    ↓
create_completion() [async]
    ↓
await get_rag_context() [async]
    ↓
Detects context_aware_rag is async
    ↓
await rag_processor() [async]
    ↓
    await _generate_optimal_query() [async]
        ↓
        await invoke_small_fast_model() [async]
            ↓
            await openai.llm_connect() [async]
    ↓
Returns optimized query
    ↓
Queries knowledge base
    ↓
Returns context
    ↓
Continues with completion
```

## No Other Changes Needed

- ✅ No changes to other RAG processors
- ✅ No changes to connectors
- ✅ No changes to prompt processors
- ✅ No changes to frontend
- ✅ No changes to database

## Summary

The fix enables async RAG processors in the LAMB completion pipeline while maintaining full backward compatibility with existing sync processors. This allows `context_aware_rag` to use async operations like calling the small-fast-model for query optimization.

**Status:** ✅ Fixed and Ready for Testing
