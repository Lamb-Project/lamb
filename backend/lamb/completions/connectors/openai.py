import json
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional, List
import time
import logging
import os
import re
import base64
# import openai
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from lamb.logging_config import get_logger
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = get_logger(__name__, component="API")

# Set up multimodal logging using centralized config
multimodal_logger = get_logger('multimodal.openai', component="API")

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


def has_images_in_messages(messages: List[Dict[str, Any]]) -> bool:
    """
    Check if any message contains image content

    Args:
        messages: List of message dictionaries

    Returns:
        bool: True if any message contains images
    """
    multimodal_logger.debug(f"Checking {len(messages)} messages for images")

    for i, message in enumerate(messages):
        content = message.get('content', [])
        multimodal_logger.debug(f"Message {i}: role={message.get('role')}, content_type={type(content).__name__}")

        if isinstance(content, list):
            # Multimodal format
            multimodal_logger.debug(f"Message {i} has list content with {len(content)} items")
            for j, item in enumerate(content):
                item_type = item.get('type')
                multimodal_logger.debug(f"Item {j}: type={item_type}")
                if item_type == 'image_url':
                    multimodal_logger.info(f"Found image_url in message {i}, item {j}")
                    return True
                elif item_type == 'image':
                    multimodal_logger.info(f"Found image in message {i}, item {j}")
                    return True
        elif isinstance(content, str):
            # Legacy text format - no images
            multimodal_logger.debug(f"Message {i} has string content (legacy format)")
            continue

    multimodal_logger.debug("No images detected in any messages")
    return False


def transform_multimodal_to_vision_format(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform multimodal messages to OpenAI Vision API format

    Args:
        messages: Messages in LAMB multimodal format

    Returns:
        Messages in OpenAI Vision format
    """
    transformed_messages = []

    for message in messages:
        content = message.get('content', [])

        if isinstance(content, list):
            # Multimodal format - transform to vision format
            vision_content = []
            for item in content:
                if item.get('type') == 'text':
                    vision_content.append({
                        'type': 'text',
                        'text': item.get('text', '')
                    })
                elif item.get('type') == 'image_url':
                    vision_content.append({
                        'type': 'image_url',
                        'image_url': item.get('image_url', {})
                    })

            transformed_message = {
                'role': message.get('role', 'user'),
                'content': vision_content
            }
        else:
            # Legacy text format - keep as is
            transformed_message = message.copy()

        transformed_messages.append(transformed_message)

    return transformed_messages


def extract_text_from_multimodal_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract only text content from multimodal messages for fallback

    Args:
        messages: Messages in multimodal format

    Returns:
        Messages with only text content, first message prefixed with warning
    """
    text_only_messages = []

    for i, message in enumerate(messages):
        content = message.get('content', [])

        if isinstance(content, list):
            # Multimodal format - extract text only
            text_parts = []
            for item in content:
                if item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))

            text_content = ' '.join(text_parts)

            # Add warning to first user message
            if i == 0 and message.get('role') == 'user':
                text_content = f"Unable to send image to the base LLM, multimodality is not supported. {text_content}"

            text_only_message = {
                'role': message.get('role', 'user'),
                'content': text_content
            }
        else:
            # Legacy text format - keep as is, but add warning to first message
            text_content = content
            if i == 0 and message.get('role') == 'user':
                text_content = f"Unable to send image to the base LLM, multimodality is not supported. {text_content}"

            text_only_message = {
                'role': message.get('role', 'user'),
                'content': text_content
            }

        text_only_messages.append(text_only_message)

    return text_only_messages


def validate_image_urls(messages: List[Dict[str, Any]]) -> List[str]:
    """
    Validate image URLs in messages

    Args:
        messages: Messages to validate

    Returns:
        List of validation error messages (empty if all valid)
    """
    errors = []

    for message in messages:
        content = message.get('content', [])
        if isinstance(content, list):
            for item in content:
                if item.get('type') == 'image_url':
                    image_url = item.get('image_url', {})
                    url = image_url.get('url', '')

                    # Basic URL validation
                    if not url:
                        errors.append("Empty image URL found")
                        continue

                    # Check if it's a data URL or HTTP URL
                    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('data:')):
                        errors.append(f"Invalid image URL format: {url[:50]}...")

                    # Basic size check for data URLs (rough estimate)
                    if url.startswith('data:'):
                        # Extract base64 part after comma
                        try:
                            base64_part = url.split(',')[1]
                            # Each base64 char represents ~6 bits, rough size check
                            estimated_bytes = len(base64_part) * 6 // 8
                            if estimated_bytes > 20 * 1024 * 1024:  # 20MB limit
                                errors.append("Image data too large (>20MB)")
                        except:
                            errors.append("Invalid base64 image data")

    return errors

async def llm_connect(messages: list, stream: bool = False, body: Dict[str, Any] = None, llm: str = None, assistant_owner: Optional[str] = None, use_small_fast_model: bool = False):
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
    assistant_owner (str, optional): Email of assistant owner for org config resolution.
    use_small_fast_model (bool, optional): If True, use organization's small-fast-model instead of default.
                                           Defaults to False.

Returns:
    Generator: If `stream=True`, a generator yielding SSE formatted chunks
               of the LLM's response as they arrive.
    Dict: If `stream=False`, the complete LLM response as a dictionary.
    """

    # --- Helper function for VISION stream generation ---
    async def _generate_vision_stream(vision_client: AsyncOpenAI, vision_params: dict):
        """Generate streaming response for vision API calls"""
        logger.debug(f"Vision Stream created")

        try:
            stream_obj = await vision_client.chat.completions.create(**vision_params)

            async for chunk in stream_obj:
                yield f"data: {chunk.model_dump_json()}\n\n"

            yield "data: [DONE]\n\n"
            logger.debug(f"Vision Stream completed successfully")

        except Exception as e:
            # If vision streaming fails, we can't easily fallback here
            # The stream has already started, so we need to handle this differently
            logger.error(f"Vision streaming failed: {str(e)}")
            # For now, yield an error message (this might not be ideal for streaming)
            error_chunk = {
                "id": "chatcmpl-error",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": vision_params.get("model", "unknown"),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": f"Unable to send image to the base LLM, multimodality is not supported. {str(e)}"
                    },
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"

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
            
            # Handle small-fast-model logic
            if use_small_fast_model:
                small_fast_config = config_resolver.get_small_fast_model_config()
                
                if small_fast_config.get('provider') == 'openai' and small_fast_config.get('model'):
                    llm = small_fast_config['model']
                    logger.info(f"Using small-fast-model: {llm}")
                    multimodal_logger.info(f"🚀 Using small-fast-model: {llm}")
                else:
                    logger.warning("Small-fast-model requested but not configured for OpenAI, using default")
            
            openai_config = config_resolver.get_provider_config("openai")
            
            if openai_config:
                api_key = openai_config.get("api_key")
                base_url = openai_config.get("base_url")
                import config
                default_model = openai_config.get("default_model") or config.OPENAI_MODEL
                config_source = "organization"
                multimodal_logger.info(f"Using organization: '{org_name}' (owner: {assistant_owner})")
                logger.info(f"Using organization config for {assistant_owner} (org: {org_name})")
            else:
                multimodal_logger.warning(f"No config found for organization '{org_name}', falling back to environment variables")
                logger.warning(f"No OpenAI config found for {assistant_owner} (org: {org_name}), falling back to env vars")
        except Exception as e:
            multimodal_logger.error(f"Error getting organization config for {assistant_owner}: {e}")
            logger.error(f"Error getting org config for {assistant_owner}: {e}, falling back to env vars")

    # Fallback to environment variables if no org config
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        import config
        default_model = os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL
        if not assistant_owner:
            multimodal_logger.info("Using environment variable configuration (no assistant owner provided)")
        else:
            multimodal_logger.info(f"Using environment variable configuration (fallback for {assistant_owner})")
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
                    multimodal_logger.warning(f"Model '{original_model}' not enabled, using org default: '{resolved_model}'")

                # If org default is also not available, use first available model
                elif available_models:
                    resolved_model = available_models[0]
                    fallback_used = True
                    logger.warning(f"Model '{original_model}' and default '{org_default_model}' not available for org '{org_name}', using first available: '{resolved_model}'")
                    multimodal_logger.warning(f"Model '{original_model}' not enabled, using first available: '{resolved_model}'")

                else:
                    # No models available - this should not happen if provider is enabled
                    logger.error(f"No models available for OpenAI provider in org '{org_name}'")
                    raise ValueError(f"No OpenAI models are enabled for organization '{org_name}'")
        
        except Exception as e:
            logger.error(f"Error during model resolution for {assistant_owner}: {e}")
            # Continue with original model if resolution fails

    multimodal_logger.info(f"Model: {resolved_model}{' (fallback)' if fallback_used else ''} | Config: {config_source} | Organization: {org_name}")

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

    # Check for multimodal content and prepare messages accordingly
    multimodal_logger.debug(f"About to check for images in {len(messages)} messages")
    has_images = has_images_in_messages(messages)
    multimodal_supported = False

    multimodal_logger.info(f"Image detection result: has_images={has_images}")

    if has_images:
        multimodal_logger.info("=== MULTIMODAL REQUEST DETECTED ===")
        multimodal_logger.debug(f"Messages structure: {json.dumps(messages, indent=2)}")

        # Validate image URLs
        validation_errors = validate_image_urls(messages)
        if validation_errors:
            multimodal_logger.warning(f"Image validation errors: {validation_errors}")
            logger.warning(f"Image validation errors: {validation_errors}")
            # For now, continue anyway and let the vision API handle invalid images
            # In the future, we might want to return an error response instead

        # Transform messages to vision format for initial attempt
        vision_messages = transform_multimodal_to_vision_format(messages)
        multimodal_logger.debug("Transformed messages to vision format")

        # Try vision API call first
        try:
            multimodal_logger.info(f"Attempting vision API call with model: {resolved_model}")

            # Prepare request parameters for vision API call
            vision_params = body.copy() if body else {}
            vision_params["model"] = resolved_model
            vision_params["messages"] = vision_messages
            vision_params["stream"] = stream

            # Create client for vision attempt
            vision_client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )

            logger.debug(f"OpenAI vision client created")

            # Try the vision API call
            if stream:
                return _generate_vision_stream(vision_client, vision_params)
            else:
                response = await vision_client.chat.completions.create(**vision_params)
                logger.debug(f"OpenAI vision response created")
                multimodal_logger.info("Vision API call successful")
                multimodal_supported = True
                return response.model_dump()

        except Exception as vision_error:
            error_msg = str(vision_error)
            multimodal_logger.error(f"Vision API call failed: {error_msg}")
            logger.warning(f"Vision API call failed: {error_msg}")

            # Check if this is a streaming request - need to handle differently
            if stream:
                multimodal_logger.warning("Streaming vision failed, will send error in stream")
                # For streaming, we'll handle the error in the streaming generator
                # Just continue with fallback messages
            else:
                multimodal_logger.info("Falling back to text-only mode with warning message")

            # Fallback to text-only with warning
            fallback_messages = extract_text_from_multimodal_messages(messages)
            messages = fallback_messages
    else:
        multimodal_logger.info("No images detected, using standard text mode")

    # Standard text-only processing (or fallback from vision failure)
    if not multimodal_supported and has_images:
        multimodal_logger.warning("Using text-only fallback for multimodal request")

    # Prepare request parameters for OpenAI API call (text-only or fallback)
    params = body.copy() if body else {}
    params["model"] = resolved_model
    params["messages"] = messages
    params["stream"] = stream

    # client = openai.OpenAI(
    client = AsyncOpenAI( # Use AsyncOpenAI
        api_key=api_key,
        base_url=base_url
    )

    logger.debug(f"OpenAI client created")

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
            logger.debug(f"Attempting API call with model: {current_model}")
            return await client.chat.completions.create(**params_to_use)
        
        except (APIError, APIConnectionError, RateLimitError, AuthenticationError) as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Log the failure
            logger.error(f"OpenAI API error with model '{current_model}': [{error_type}] {error_msg}")

            # Check if we should attempt fallback
            if attempt_fallback and org_default_for_fallback and current_model != org_default_for_fallback:
                logger.warning(f"Attempting fallback to organization default model: '{org_default_for_fallback}'")

                # Retry with org default model
                fallback_params = params_to_use.copy()
                fallback_params["model"] = org_default_for_fallback

                try:
                    result = await _make_api_call_with_fallback(fallback_params, attempt_fallback=False)
                    logger.info(f"✅ Fallback to '{org_default_for_fallback}' succeeded")
                    return result

                except Exception as fallback_error:
                    fallback_error_type = type(fallback_error).__name__
                    fallback_error_msg = str(fallback_error)
                    logger.error(f"Fallback to '{org_default_for_fallback}' also failed: [{fallback_error_type}] {fallback_error_msg}")
                    
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

    # --- Helper function for ORIGINAL stream generation --- (moved inside llm_connect)
    async def _generate_original_stream():
        response_id = None
        created_time = None
        model_name = None
        sent_initial_role = False # Track if the initial chunk with role/refusal has been sent
        logger.debug(f"Original Stream created")

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
        logger.debug(f"Original Stream completed")

    # --- Helper function for EXPERIMENTAL stream generation ---
    async def _generate_experimental_stream():
        logger.debug(f"Experimental Stream created")
        # Create a streaming response
        stream_obj = await _make_api_call_with_fallback(params) # Use helper with fallback

        # Iterate through the stream and yield the JSON representation of each chunk
        async for chunk in stream_obj: # Changed to async for
            yield f"data: {chunk.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"
        logger.debug(f"Experimental Stream completed")

    # --- Main logic for llm_connect ---
    if stream:
        # --- CHOOSE IMPLEMENTATION HERE ---
        # return _generate_original_stream()
        return _generate_experimental_stream()
    else:
        # Non-streaming call with fallback
        response = await _make_api_call_with_fallback(params) # Use helper with fallback
        logger.debug(f"Direct response created")
        return response.model_dump()