import json
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional
import time
import logging
import os
# import openai
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from utils.timelog import Timelog
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_available_llms(assistant_owner: Optional[str] = None):
    """
    Return list of available LLMs for this connector
    
    Args:
        assistant_owner: Optional assistant owner email to get org-specific models
    """
    # If no assistant owner provided, fall back to env vars (for backward compatibility)
    if not assistant_owner:
        if os.getenv("OPENAI_ENABLED", "true").lower() != "true":
            logger.info("OPENAI_ENABLED is false, skipping model list fetch")
            return []
        
        import config
        models = os.getenv("OPENAI_MODELS") or config.OPENAI_MODEL
        if not models:
            return [os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL]
        return [model.strip() for model in models.split(",") if model.strip()]
    
    # Use organization-specific configuration
    try:
        config_resolver = OrganizationConfigResolver(assistant_owner)
        openai_config = config_resolver.get_provider_config("openai")
        
        if not openai_config or not openai_config.get("enabled", True):
            logger.info(f"OpenAI disabled for organization of user {assistant_owner}")
            return []
            
        models = openai_config.get("models", [])
        if not models:
            import config
            models = [openai_config.get("default_model") or config.OPENAI_MODEL]
            
        return models
    except Exception as e:
        logger.error(f"Error getting OpenAI models for {assistant_owner}: {e}")
        # Fallback to env vars
        return get_available_llms(None)

def format_debug_response(messages: list, body: Dict[str, Any]) -> str:
    """Format debug response showing messages and body"""
    return f"Messages:\n{json.dumps(messages, indent=2)}\n\nBody:\n{json.dumps(body, indent=2)}"

def format_simple_response(messages: list) -> str:
    """Get the last message content"""
    return messages[-1]["content"] if messages else "No messages provided"

def format_conversation_response(messages: list) -> str:
    """Format all messages as a conversation"""
    return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

async def llm_connect(messages: list, stream: bool = False, body: Dict[str, Any] = None, llm: str = None, assistant_owner: Optional[str] = None):
    """
Connects to the specified Large Language Model (LLM) using the OpenAI API.

This function serves as the primary interface for interacting with the LLM.
It handles both standard (non-streaming) and streaming requests.

**Current Behavior and Future Strategy:**

- When `stream=False`, it makes a standard synchronous API call to OpenAI
  and returns the complete response as a dictionary. This maintains
  the original synchronous behavior of the function.

- When `stream=True`, it leverages OpenAI's true streaming API. To maintain
  the function's return type as a generator (similar to the previous
  fake streaming implementation) and avoid breaking existing calling code,
  it internally creates an *asynchronous* generator (`generate_real_stream`).
  This internal generator iterates over the asynchronous stream of chunks
  received from OpenAI and yields each chunk formatted as a Server-Sent
  Event (`data: ...\n\n`), mimicking the structure of the previous
  simulated streaming output. Finally, it yields the `data: [DONE]\n\n`
  marker to signal the end of the stream.

**Future Considerations:**

- Callers of this function, when `stream=True`, will need to be aware that
  they are now consuming a generator that yields real-time chunks from OpenAI.
  If the calling code was written expecting the exact timing and content
  of the fake stream, minor adjustments might be necessary. However, the
  overall format of the yielded data should remain consistent.

- For optimal performance and non-blocking behavior in the calling
  application when `stream=True`, it is recommended that the caller
  uses `async for` to iterate over the returned generator, as the underlying
  OpenAI streaming is asynchronous.

Args:
    messages (list): A list of message dictionaries representing the conversation history.
                     Each dictionary should have 'role' (e.g., 'user', 'assistant') and
                     'content' keys.
    stream (bool, optional): If True, enables streaming of the LLM's response.
                              Defaults to False.
    body (Dict, optional): A dictionary containing additional parameters to pass
                           to the OpenAI API (e.g., 'temperature', 'top_p').
                           Defaults to None.
    llm (str, optional): The specific LLM model to use (e.g., 'gpt-4o').
                         If None, it defaults to the value of the OPENAI_MODEL
                         environment variable or OPENAI_MODEL env var. Defaults to None.

Returns:
    Generator: If `stream=True`, a generator yielding SSE formatted chunks
               of the LLM's response as they arrive.
    Dict: If `stream=False`, the complete LLM response as a dictionary.
    """
    # Get organization-specific configuration
    api_key = None
    base_url = None
    import config
    default_model = config.OPENAI_MODEL
    org_name = "Unknown"
    config_source = "env_vars"
    
    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            org_name = config_resolver.organization.get('name', 'Unknown')
            openai_config = config_resolver.get_provider_config("openai")
            
            if openai_config:
                api_key = openai_config.get("api_key")
                base_url = openai_config.get("base_url")
                import config
                default_model = openai_config.get("default_model") or config.OPENAI_MODEL
                config_source = "organization"
                print(f"🏢 [OpenAI] Using organization: '{org_name}' (owner: {assistant_owner})")
                logger.info(f"Using organization config for {assistant_owner} (org: {org_name})")
            else:
                print(f"⚠️  [OpenAI] No config found for organization '{org_name}', falling back to environment variables")
                logger.warning(f"No OpenAI config found for {assistant_owner} (org: {org_name}), falling back to env vars")
        except Exception as e:
            print(f"❌ [OpenAI] Error getting organization config for {assistant_owner}: {e}")
            logger.error(f"Error getting org config for {assistant_owner}: {e}, falling back to env vars")
    
    # Fallback to environment variables if no org config
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        import config
        default_model = os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL
        if not assistant_owner:
            print(f"🔧 [OpenAI] Using environment variable configuration (no assistant owner provided)")
        else:
            print(f"🔧 [OpenAI] Using environment variable configuration (fallback for {assistant_owner})")
        logger.info("Using environment variable configuration")
    
    if not api_key:
        raise ValueError("No OpenAI API key found in organization config or environment variables")

    # Phase 3: Model resolution and fallback logic
    resolved_model = llm or default_model
    fallback_used = False
    
    if assistant_owner and config_source == "organization":
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            openai_config = config_resolver.get_provider_config("openai")
            available_models = openai_config.get("models", [])
            org_default_model = openai_config.get("default_model")
            
            # Check if requested model is available
            if resolved_model not in available_models:
                original_model = resolved_model
                
                # Try organization's default model first
                if org_default_model and org_default_model in available_models:
                    resolved_model = org_default_model
                    fallback_used = True
                    logger.warning(f"Model '{original_model}' not available for org '{org_name}', using org default: '{resolved_model}'")
                    print(f"⚠️  [OpenAI] Model '{original_model}' not enabled, using org default: '{resolved_model}'")
                
                # If org default is also not available, use first available model
                elif available_models:
                    resolved_model = available_models[0]
                    fallback_used = True
                    logger.warning(f"Model '{original_model}' and default '{org_default_model}' not available for org '{org_name}', using first available: '{resolved_model}'")
                    print(f"⚠️  [OpenAI] Model '{original_model}' not enabled, using first available: '{resolved_model}'")
                
                else:
                    # No models available - this should not happen if provider is enabled
                    logger.error(f"No models available for OpenAI provider in org '{org_name}'")
                    raise ValueError(f"No OpenAI models are enabled for organization '{org_name}'")
        
        except Exception as e:
            logger.error(f"Error during model resolution for {assistant_owner}: {e}")
            # Continue with original model if resolution fails

    print(f"🚀 [OpenAI] Model: {resolved_model}{' (fallback)' if fallback_used else ''} | Config: {config_source} | Organization: {org_name}")

    # Store original model and get org default for potential runtime fallback
    original_requested_model = resolved_model
    org_default_for_fallback = None
    if assistant_owner and config_source == "organization":
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            openai_config = config_resolver.get_provider_config("openai")
            org_default_for_fallback = openai_config.get("default_model")
        except:
            pass

    # Prepare request parameters for OpenAI API call.
    params = body.copy() if body else {}
    params["model"] = resolved_model
    params["messages"] = messages
    params["stream"] = stream # Pass the stream parameter correctly

    # client = openai.OpenAI(
    client = AsyncOpenAI( # Use AsyncOpenAI
        api_key=api_key,
        base_url=base_url
    )

    Timelog(f"OpenAI client created", 2)

    # Helper function to make API call with runtime fallback
    async def _make_api_call_with_fallback(params_to_use: dict, attempt_fallback: bool = True):
        """
        Make OpenAI API call with fallback to org default model on failure.
        
        Args:
            params_to_use: Parameters for the API call
            attempt_fallback: Whether to attempt fallback on error (False for retry attempts)
            
        Returns:
            API response or stream object
            
        Raises:
            ValueError: With comprehensive error message if all attempts fail
        """
        current_model = params_to_use["model"]
        
        try:
            Timelog(f"Attempting API call with model: {current_model}", 2)
            return await client.chat.completions.create(**params_to_use)
        
        except (APIError, APIConnectionError, RateLimitError, AuthenticationError) as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Log the failure
            logger.error(f"OpenAI API error with model '{current_model}': [{error_type}] {error_msg}")
            print(f"❌ [OpenAI] API call failed for model '{current_model}': [{error_type}] {error_msg}")
            
            # Check if we should attempt fallback
            if attempt_fallback and org_default_for_fallback and current_model != org_default_for_fallback:
                logger.warning(f"Attempting fallback to organization default model: '{org_default_for_fallback}'")
                print(f"🔄 [OpenAI] Retrying with organization default model: '{org_default_for_fallback}'")
                
                # Retry with org default model
                fallback_params = params_to_use.copy()
                fallback_params["model"] = org_default_for_fallback
                
                try:
                    result = await _make_api_call_with_fallback(fallback_params, attempt_fallback=False)
                    logger.info(f"✅ Fallback to '{org_default_for_fallback}' succeeded")
                    print(f"✅ [OpenAI] Fallback successful with model: '{org_default_for_fallback}'")
                    return result
                    
                except Exception as fallback_error:
                    fallback_error_type = type(fallback_error).__name__
                    fallback_error_msg = str(fallback_error)
                    logger.error(f"Fallback to '{org_default_for_fallback}' also failed: [{fallback_error_type}] {fallback_error_msg}")
                    print(f"❌ [OpenAI] Fallback also failed: [{fallback_error_type}] {fallback_error_msg}")
                    
                    # Both attempts failed - raise comprehensive error
                    comprehensive_error = (
                        f"OpenAI API failure for organization '{org_name}':\n"
                        f"  • Requested model '{current_model}' failed: [{error_type}] {error_msg}\n"
                        f"  • Fallback to default model '{org_default_for_fallback}' also failed: [{fallback_error_type}] {fallback_error_msg}\n"
                        f"Please contact your organization administrator to verify:\n"
                        f"  - API key has access to the configured models\n"
                        f"  - Models are correctly configured in organization settings\n"
                        f"  - API key has sufficient permissions and quota"
                    )
                    raise ValueError(comprehensive_error)
            
            else:
                # No fallback available or this is already a fallback attempt
                if not org_default_for_fallback:
                    reason = "No organization default model configured"
                elif current_model == org_default_for_fallback:
                    reason = "Already using organization default model"
                else:
                    reason = "Fallback not available"
                
                comprehensive_error = (
                    f"OpenAI API failure for organization '{org_name}':\n"
                    f"  • Model '{current_model}' failed: [{error_type}] {error_msg}\n"
                    f"  • {reason}\n"
                    f"Please contact your organization administrator to verify:\n"
                    f"  - API key is valid and has access to model '{current_model}'\n"
                    f"  - Model exists and is available in your OpenAI organization\n"
                    f"  - API key has sufficient permissions and quota"
                )
                raise ValueError(comprehensive_error)
        
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error during OpenAI API call: {type(e).__name__}: {str(e)}", exc_info=True)
            raise ValueError(f"Unexpected error calling OpenAI API with model '{current_model}': {str(e)}")

    # --- Helper function for ORIGINAL stream generation --- (This one also needs await)
    async def _generate_original_stream():
        response_id = None
        created_time = None
        model_name = None
        sent_initial_role = False # Track if the initial chunk with role/refusal has been sent
        Timelog(f"Original Stream created", 2)

        stream_obj = await _make_api_call_with_fallback(params) # Use helper with fallback

        async for chunk in stream_obj: # Use async for with the async generator
            if not response_id:
                response_id = chunk.id
                created_time = chunk.created
                model_name = chunk.model

            if chunk.choices:
                choice = chunk.choices[-1]
                delta = choice.delta
                finish_reason = choice.finish_reason

                # Prepare the base data structure for the chunk
                current_choice = {
                    "index": 0,
                    "delta": {}, # Initialize delta
                    "logprobs": None, # Assuming no logprobs needed for now
                    "finish_reason": finish_reason # finish_reason goes in choice, not delta
                }
                data = {
                    "id": response_id or "chatcmpl-123",
                    "object": "chat.completion.chunk",
                    "created": created_time or int(time.time()),
                    "model": model_name or params["model"],
                    "choices": [current_choice]
                    # Removed 'usage' field as it's not in OpenAI streaming chunks
                    # "system_fingerprint": chunk.system_fingerprint, # Can be added if needed
                }

                # Populate delta more carefully
                current_delta = {} # Reset delta payload for this chunk
                is_chunk_to_yield = False

                # Role: Only include in the very first message chunk
                if delta.role is not None and not sent_initial_role:
                    current_delta["role"] = delta.role
                    # refusal is typically omitted unless present, not added as null
                    # current_delta["refusal"] = None
                    sent_initial_role = True
                    is_chunk_to_yield = True

                # Content: Include if present
                if delta.content is not None:
                    current_delta["content"] = delta.content
                    is_chunk_to_yield = True

                # Other fields (tool_calls, function_call): Include ONLY if present in delta
                if hasattr(delta, 'tool_calls') and delta.tool_calls is not None:
                     current_delta['tool_calls'] = delta.tool_calls
                     is_chunk_to_yield = True
                if hasattr(delta, 'function_call') and delta.function_call is not None:
                     current_delta['function_call'] = delta.function_call
                     is_chunk_to_yield = True

                # Handle the final chunk specifically (where finish_reason is not None)
                if finish_reason is not None:
                    # Final chunk delta might be empty or contain final details if needed.
                    # OpenAI often sends an empty delta in the final chunk.
                    current_delta = {} # Ensure delta is empty unless specific fields need to be sent
                    is_chunk_to_yield = True

                # Only yield if there's something to send (content, role, finish_reason, etc.)
                if is_chunk_to_yield:
                    current_choice["delta"] = current_delta # Assign the constructed delta
                    yield f"data: {json.dumps(data)}\\n\\n"

        yield "data: [DONE]\\n\\n"
        Timelog(f"Original Stream completed", 2)

    # --- Helper function for EXPERIMENTAL stream generation ---
    async def _generate_experimental_stream():
        Timelog(f"Experimental Stream created", 2)
        # Create a streaming response
        stream_obj = await _make_api_call_with_fallback(params) # Use helper with fallback

        # Iterate through the stream and yield the JSON representation of each chunk
        async for chunk in stream_obj: # Changed to async for
            yield f"data: {chunk.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"
        Timelog(f"Experimental Stream completed", 2)

    # --- Main logic for llm_connect ---
    if stream:
        # --- CHOOSE IMPLEMENTATION HERE ---
        # return _generate_original_stream()
        return _generate_experimental_stream()
    else:
        # Non-streaming call with fallback
        response = await _make_api_call_with_fallback(params) # Use helper with fallback
        Timelog(f"Direct response created", 2)
        return response.model_dump()