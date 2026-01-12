"""
LangSmith Tracing Configuration for LAMB

This module provides utilities for tracing LLM calls using LangSmith.
It allows optional configuration via environment variables.

Environment Variables:
    LANGCHAIN_TRACING_V2: Set to 'true' to enable LangSmith tracing (default: false)
    LANGCHAIN_API_KEY: Your LangSmith API key
    LANGCHAIN_PROJECT: Project name in LangSmith (default: 'lamb-assistants')
    LANGCHAIN_ENDPOINT: LangSmith API endpoint (default: https://api.smith.langchain.com)

Usage:
    from utils.langsmith_config import traceable_llm_call
    from langsmith import traceable
    
    @traceable(name="my_function")
    async def my_function():
        pass
        
    # Or use the configured wrapper
    @traceable_llm_call(name="openai_completion")
    async def openai_completion():
        pass
"""

import os
import functools
from typing import Optional, Callable, Any
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="TRACING")

# Check if LangSmith tracing is enabled
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

# Try to import langsmith, but don't fail if not available
try:
    import langsmith as _langsmith

    # Some LangSmith versions expose symbols dynamically via __getattr__, so
    # `from langsmith import traceable` can fail even when traceable exists.
    traceable = getattr(_langsmith, "traceable", None)
    Client = getattr(_langsmith, "Client", None)
    _get_current_run_tree = getattr(_langsmith, "get_current_run_tree", None)

    if traceable is None or Client is None:
        raise ImportError("LangSmith is installed but required symbols are missing")

    LANGSMITH_AVAILABLE = True

    # Initialize LangSmith client if enabled
    if LANGSMITH_ENABLED:
        langsmith_client = Client()
        logger.info("✅ LangSmith tracing is ENABLED")
        logger.info(f"   Project: {os.getenv('LANGCHAIN_PROJECT', 'lamb-assistants')}")
    else:
        langsmith_client = None
        logger.info("ℹ️  LangSmith tracing is DISABLED (set LANGCHAIN_TRACING_V2=true to enable)")

except ImportError:
    LANGSMITH_AVAILABLE = False
    traceable = None
    Client = None
    _get_current_run_tree = None
    langsmith_client = None
    logger.warning("⚠️  LangSmith not installed or incompatible. Install with: pip install langsmith")


def traceable_llm_call(
    name: Optional[str] = None,
    run_type: str = "llm",
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
    **kwargs
) -> Callable:
    """Decorator for tracing LLM calls with LangSmith.

    This is a wrapper around langsmith.traceable that only applies tracing
    when LANGCHAIN_TRACING_V2 is enabled. If tracing is disabled or langsmith
    is not installed, functions execute normally without tracing overhead.

    Args:
        name: Name for the traced operation (default: function name)
        run_type: Type of run - "llm", "chain", "tool", "retriever", etc.
        metadata: Additional metadata to attach to the trace
        tags: Tags for categorizing the trace
        **kwargs: Additional arguments passed to langsmith.traceable

    Returns:
        Decorated function that traces execution when enabled

    Example:
        @traceable_llm_call(name="openai_completion", tags=["openai", "gpt-4"])
        async def call_openai(messages, model):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # If LangSmith is not available or not enabled, return original function
        if not LANGSMITH_AVAILABLE or not LANGSMITH_ENABLED or traceable is None:
            return func
        
        # Build traceable kwargs
        trace_kwargs = {
            "run_type": run_type,
            **kwargs
        }

        if name:
            trace_kwargs["name"] = name
        if metadata:
            trace_kwargs["metadata"] = metadata
        if tags:
            trace_kwargs["tags"] = tags
            
        # Apply langsmith traceable decorator
        return traceable(**trace_kwargs)(func)  # type: ignore
    
    return decorator


def get_langsmith_client() -> Optional[Any]:
    """
    Get the LangSmith client instance if available and enabled.
    
    Returns:
        LangSmith Client instance or None if not available/enabled
    """
    return langsmith_client


def is_tracing_enabled() -> bool:
    """
    Check if LangSmith tracing is currently enabled.
    
    Returns:
        True if tracing is enabled and available, False otherwise
    """
    return LANGSMITH_AVAILABLE and LANGSMITH_ENABLED


def add_trace_metadata(key: str, value: Any) -> None:
    """
    Add metadata to the current trace context (if tracing is enabled).
    
    Args:
        key: Metadata key
        value: Metadata value
    """
    if not is_tracing_enabled():
        return
        
    try:
        run = _get_current_run_tree() if _get_current_run_tree else None
        if run:
            run.metadata[key] = value
    except Exception as e:
        logger.debug(f"Failed to add trace metadata: {e}")


def add_trace_tags(*tags: str) -> None:
    """
    Add tags to the current trace context (if tracing is enabled).
    
    Args:
        *tags: Tags to add to the current trace
    """
    if not is_tracing_enabled():
        return
        
    try:
        run = _get_current_run_tree() if _get_current_run_tree else None
        if run:
            if not run.tags:
                run.tags = []
            run.tags.extend(tags)
    except Exception as e:
        logger.debug(f"Failed to add trace tags: {e}")


# Convenience function for logging trace information
def log_trace_info(message: str, **kwargs) -> None:
    """
    Log a message with trace context if available.
    
    Args:
        message: Log message
        **kwargs: Additional key-value pairs to log
    """
    if is_tracing_enabled():
        try:
            run = _get_current_run_tree() if _get_current_run_tree else None
            if run:
                logger.debug(f"[Trace {run.id}] {message}", extra=kwargs)
                return
        except Exception:
            pass
    
    logger.debug(message, extra=kwargs)
