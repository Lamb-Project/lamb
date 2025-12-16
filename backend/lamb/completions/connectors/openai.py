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
from lamb.completions.tools import TOOL_REGISTRY, get_tool_specs, get_tool_function

logger = get_logger(__name__, component="MAIN")

# Set up multimodal logging
multimodal_logger = logging.getLogger('multimodal.openai')
multimodal_logger.setLevel(logging.DEBUG)

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

# --- Tool Support Functions ---

def get_tools_for_assistant(assistant) -> List[Dict]:
    """
    Get tool specifications for an assistant based on its metadata configuration.
    
    Args:
        assistant: Assistant object with metadata field containing tools config
        
    Returns:
        List of OpenAI-compatible tool specification dicts
    """
    if not assistant:
        return []
    
    try:
        metadata = json.loads(assistant.metadata or "{}")
        tool_names = metadata.get("tools", [])
        
        if not tool_names:
            return []
        
        # Get tool specs from registry
        tools = []
        for name in tool_names:
            if name in TOOL_REGISTRY:
                tools.append(TOOL_REGISTRY[name]["spec"])
            else:
                logger.warning(f"Tool '{name}' not found in registry")
        
        return tools
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse assistant metadata: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting tools for assistant: {e}")
        return []


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a tool by name with the provided arguments.
    
    Args:
        tool_name: Name of the tool to execute (function name from spec)
        arguments: Dictionary of arguments to pass to the tool
        
    Returns:
        Tool result as a JSON string
    """
    # Find the tool by function name
    tool_func = None
    for name, tool_data in TOOL_REGISTRY.items():
        if tool_data["spec"]["function"]["name"] == tool_name:
            tool_func = tool_data["function"]
            break
    
    if not tool_func:
        logger.error(f"Unknown tool: {tool_name}")
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        # Check if the function is async
        if asyncio.iscoroutinefunction(tool_func):
            result = await tool_func(**arguments)
        else:
            result = tool_func(**arguments)
            
        logger.info(f"Tool '{tool_name}' executed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        return json.dumps({"error": str(e)})


async def llm_connect(
    messages: list,
    stream: bool = False,
    body: Dict[str, Any] = None,
    llm: str = None,
    assistant_owner: Optional[str] = None,
    assistant=None,
    use_small_fast_model: bool = False,
):
    """
Connects to the specified Large Language Model (LLM) using the OpenAI API.

This function serves as the primary interface for interacting with the LLM.
It handles both standard (non-streaming) and streaming requests.
It also supports tool/function calling when tools are configured in the assistant.

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

**Tool Calling Support:**

- When an assistant has tools configured in its metadata (e.g., {"tools": ["weather", "moodle"]}),
  the connector will automatically include these tools in the API call.
- If the LLM requests tool calls, the connector executes them and continues
  the conversation until a final response is generated.
- Tool calling supports both streaming and non-streaming modes.

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
    assistant (object, optional): Assistant object containing metadata with tool configuration.
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
            # Filter out OWUI-internal parameters that shouldn't be passed to OpenAI
            vision_params = {k: v for k, v in (body or {}).items() if not k.startswith('__')}
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
    # Filter out OWUI-internal parameters (like __openwebui_headers__) that shouldn't be passed to OpenAI
    params = {k: v for k, v in (body or {}).items() if not k.startswith('__')}
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

    # --- Helper functions for TOOL CALLING support ---
    async def _handle_non_streaming_with_tools(tool_specs: List[Dict]) -> Dict[str, Any]:
        """
        Handle non-streaming requests with tool calling loop.
        
        The loop:
        1. Call the LLM with tools
        2. If it wants to use tools, execute them
        3. Add tool results to messages
        4. Call the LLM again
        5. Repeat until we get a final response (max 5 iterations)
        """
        working_messages = messages.copy()
        max_tool_iterations = 5
        iteration = 0
        
        # Add tools to params
        tool_params = params.copy()
        tool_params["tools"] = tool_specs
        tool_params["tool_choice"] = "auto"
        tool_params["stream"] = False
        
        logger.info(f"Tool-enabled call with {len(tool_specs)} tools: {[t['function']['name'] for t in tool_specs]}")
        
        while iteration < max_tool_iterations:
            iteration += 1
            tool_params["messages"] = working_messages
            
            logger.info(f"Tool iteration {iteration}/{max_tool_iterations}")
            
            response = await _make_api_call_with_fallback(tool_params)
            choice = response.choices[0]
            message = choice.message
            
            # Check if the model wants to call tools
            if message.tool_calls:
                logger.info(f"Model requested {len(message.tool_calls)} tool call(s)")
                
                # Add the assistant's response with tool calls to the conversation
                working_messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })
                
                # Execute each tool and add results
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"Executing tool: {tool_name}({arguments})")
                    
                    result = await execute_tool(tool_name, arguments)
                    
                    # Add tool result to messages
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            else:
                # No tool calls - this is the final response
                logger.info("Final response received (no more tool calls)")
                Timelog(f"Tool-enabled response created", 2)
                return response.model_dump()
        
        # If we hit max iterations, return the last response
        logger.warning(f"Hit max tool iterations ({max_tool_iterations})")
        Timelog(f"Tool-enabled response created (max iterations)", 2)
        return response.model_dump()

    async def _handle_streaming_with_tools(tool_specs: List[Dict]):
        """
        Handle streaming requests with tool calling support.
        
        For tool calls during streaming:
        1. Collect the full response to detect tool calls
        2. If tools are called, execute them (not streamed)
        3. Make another call and stream that response
        """
        working_messages = messages.copy()
        max_tool_iterations = 5
        iteration = 0
        
        # Add tools to params
        tool_params = params.copy()
        tool_params["tools"] = tool_specs
        tool_params["tool_choice"] = "auto"
        
        logger.info(f"Tool-enabled streaming call with {len(tool_specs)} tools")
        
        while iteration < max_tool_iterations:
            iteration += 1
            tool_params["messages"] = working_messages
            tool_params["stream"] = True
            
            logger.info(f"Streaming tool iteration {iteration}/{max_tool_iterations}")
            
            # Collect stream to check for tool calls
            full_content = ""
            tool_calls_data = {}  # {index: {id, name, arguments}}
            finish_reason = None
            
            stream_obj = await _make_api_call_with_fallback(tool_params)
            
            async for chunk in stream_obj:
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    finish_reason = choice.finish_reason or finish_reason
                    
                    # Collect content
                    if delta.content:
                        full_content += delta.content
                    
                    # Collect tool calls
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": ""
                                }
                            if tc.id:
                                tool_calls_data[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_data[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_data[idx]["arguments"] += tc.function.arguments
            
            # Check if we have tool calls to process
            if tool_calls_data and finish_reason == "tool_calls":
                logger.info(f"Stream detected {len(tool_calls_data)} tool call(s)")
                
                # Add the assistant message with tool calls
                working_messages.append({
                    "role": "assistant",
                    "content": full_content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"]
                            }
                        }
                        for tc in tool_calls_data.values()
                    ]
                })
                
                # Execute tools and add results
                for tc_data in tool_calls_data.values():
                    try:
                        arguments = json.loads(tc_data["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"Executing tool: {tc_data['name']}({arguments})")
                    result = await execute_tool(tc_data["name"], arguments)
                    
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_data["id"],
                        "content": result
                    })
                
                # Continue the loop to get the next response
                continue
            
            else:
                # No tool calls - stream the final response
                logger.info("Streaming final response (no more tool calls)")
                
                # Make a fresh call for the actual stream output
                tool_params["messages"] = working_messages
                stream_obj = await _make_api_call_with_fallback(tool_params)
                
                async for chunk in stream_obj:
                    yield f"data: {chunk.model_dump_json()}\n\n"
                
                yield "data: [DONE]\n\n"
                Timelog(f"Tool-enabled stream completed", 2)
                return
        
        # If we hit max iterations, yield done
        logger.warning(f"Hit max tool iterations ({max_tool_iterations})")
        yield "data: [DONE]\n\n"

    # --- Main logic for llm_connect ---
    
    # Check if assistant has tools configured
    tool_specs = get_tools_for_assistant(assistant)
    
    if tool_specs:
        logger.info(f"Tools detected for assistant: {[t['function']['name'] for t in tool_specs]}")
        if stream:
            return _handle_streaming_with_tools(tool_specs)
        else:
            return await _handle_non_streaming_with_tools(tool_specs)
    
    # Standard path (no tools)
    if stream:
        # --- CHOOSE IMPLEMENTATION HERE ---
        # return _generate_original_stream()
        return _generate_experimental_stream()
    else:
        # Non-streaming call with fallback
        response = await _make_api_call_with_fallback(params) # Use helper with fallback
        logger.debug(f"Direct response created")
        return response.model_dump()