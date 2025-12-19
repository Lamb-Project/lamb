"""
Helper utilities for plugins to invoke the small-fast-model
"""

from typing import List, Dict, Any, Optional
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MAIN")


async def invoke_small_fast_model(
    messages: List[Dict[str, Any]],
    assistant_owner: str,
    stream: bool = False,
    body: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Convenience function for plugins to invoke the organization's small-fast-model
    
    Args:
        messages: List of conversation messages
        assistant_owner: Email of assistant owner (for org resolution)
        stream: Whether to stream the response
        body: Optional request body parameters
    
    Returns:
        LLM response (format depends on connector)
    
    Raises:
        ValueError: If small-fast-model is not configured
        Exception: If the connector fails
    
    Example:
        ```python
        # In a RAG processor
        response = await invoke_small_fast_model(
            messages=[{"role": "user", "content": "Rewrite this query: ..."}],
            assistant_owner=assistant.owner
        )
        ```
    """
    try:
        # Get small-fast-model configuration
        config_resolver = OrganizationConfigResolver(assistant_owner)
        small_fast_config = config_resolver.get_small_fast_model_config()
        
        provider = small_fast_config.get('provider')
        model = small_fast_config.get('model')
        
        if not provider or not model:
            raise ValueError(
                "Small-fast-model is not configured for this organization. "
                "Please configure it in the organization settings."
            )
        
        logger.info(f"Invoking small-fast-model: {provider}/{model}")
        
        # Import and call the appropriate connector
        if provider == 'openai':
            from lamb.completions.connectors import openai
            return await openai.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,  # Explicitly use the small-fast-model
                assistant_owner=assistant_owner,
                use_small_fast_model=False  # Don't trigger the flag since we're explicitly setting llm
            )
        
        elif provider == 'ollama':
            from lamb.completions.connectors import ollama
            return await ollama.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        elif provider == 'anthropic':
            from lamb.completions.connectors import anthropic
            return await anthropic.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        elif provider == 'google':
            from lamb.completions.connectors import google
            return await google.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        else:
            raise ValueError(f"Unsupported provider for small-fast-model: {provider}")
    
    except Exception as e:
        logger.error(f"Error invoking small-fast-model: {e}")
        raise


def get_small_fast_model_info(assistant_owner: str) -> Dict[str, str]:
    """
    Get information about the configured small-fast-model
    
    Args:
        assistant_owner: Email of assistant owner
    
    Returns:
        Dict with 'provider' and 'model' keys
    """
    config_resolver = OrganizationConfigResolver(assistant_owner)
    return config_resolver.get_small_fast_model_config()


def is_small_fast_model_configured(assistant_owner: str) -> bool:
    """
    Check if small-fast-model is configured for the organization
    
    Args:
        assistant_owner: Email of assistant owner
    
    Returns:
        True if configured, False otherwise
    """
    config = get_small_fast_model_info(assistant_owner)
    return bool(config.get('provider') and config.get('model'))
