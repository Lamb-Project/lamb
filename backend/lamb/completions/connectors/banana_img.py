import json
import os
import base64
import time
import uuid
import re
from typing import Dict, Any, Optional, List
from io import BytesIO
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
from openai import AsyncOpenAI
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.database_manager import LambDatabaseManager
import config
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MAIN")

def get_available_llms(assistant_owner: Optional[str] = None):
    """
    Return available image generation models for this connector

    Args:
        assistant_owner: Optional assistant owner email to get org-specific models
    """
    # Google Gen AI image generation models (as of Dec 2024)
    # Gemini models use generate_content API (may work with free tier)
    # Imagen models use generate_images API (requires billing)
    return [
        "gemini-2.5-flash-image-preview",    # Gemini 2.5 Flash preview (cheapest, uses generate_content)
        "gemini-2.5-flash-image",            # Gemini 2.5 Flash with image generation (uses generate_content)
        "imagen-4.0-fast-generate-001",      # Imagen 4 Fast - requires billing (uses generate_images)
        "imagen-4.0-generate-001",           # Imagen 4 - requires billing (uses generate_images)
    ]

def _maybe_stream_response(response_dict: Dict[str, Any], stream: bool):
    """
    Return either a dict or streaming response based on stream flag.
    
    Args:
        response_dict: OpenAI-compatible response dictionary
        stream: Whether to return streaming format
        
    Returns:
        Either the dict directly or an async generator for streaming
    """
    if stream:
        return _dict_to_streaming_response(response_dict)
    return response_dict


async def _dict_to_streaming_response(response_dict: Dict[str, Any]):
    """
    Convert a dict response to SSE streaming format.
    
    This is needed because the caller expects an async generator when stream=True,
    but image generation returns a dict. We convert the dict to a single SSE event.
    
    Args:
        response_dict: OpenAI-compatible response dictionary
        
    Yields:
        SSE formatted strings
    """
    import json
    
    # Extract the content from the response
    content = ""
    if "choices" in response_dict and response_dict["choices"]:
        content = response_dict["choices"][0].get("message", {}).get("content", "")
    
    # Create a streaming chunk with the full content
    chunk = {
        "id": response_dict.get("id", f"chatcmpl-{int(time.time())}"),
        "object": "chat.completion.chunk",
        "created": response_dict.get("created", int(time.time())),
        "model": response_dict.get("model", "banana_img"),
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }
        ]
    }
    
    yield f"data: {json.dumps(chunk)}\n\n"
    
    # Send finish chunk
    finish_chunk = {
        "id": response_dict.get("id", f"chatcmpl-{int(time.time())}"),
        "object": "chat.completion.chunk",
        "created": response_dict.get("created", int(time.time())),
        "model": response_dict.get("model", "banana_img"),
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }
        ]
    }
    
    yield f"data: {json.dumps(finish_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def _is_title_generation_request(messages: List[Dict[str, Any]]) -> bool:
    """
    Detect if the request is asking for a chat title/tags instead of image generation
    
    Args:
        messages: List of message dictionaries (may have prompt template applied)
        
    Returns:
        bool: True if this is a title/tags generation request
    """
    if not messages:
        return False
    
    # Get the last user message
    last_message = messages[-1] if messages else None
    if not last_message:
        return False
    
    content = last_message.get("content", "")
    if isinstance(content, list):
        # Multimodal format - extract text
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = " ".join(text_parts)
    
    # Log the content for debugging (trimmed)
    content_preview = content[:200] if len(content) > 200 else content
    logger.debug(f"🔍 Checking title detection on content: {content_preview}...")
    
    # Look for title/tags generation patterns
    # Note: Content may have prompt template wrapper like " --- {content} --- "
    # OpenWebUI sends: "### Task:\nGenerate 1-3 broad tags..."
    
    content_lower = content.lower()
    
    # Quick check for OpenWebUI title format (starts with "### Task:")
    if content_lower.strip().startswith("### task:") or "### task:" in content_lower:
        logger.info(f"🎯 Detected title generation request: OpenWebUI format (### Task:)")
        return True
    
    title_patterns = [
        r"generate.*title",
        r"create.*title",
        r"suggest.*title",
        r"generate.*tags",
        r"categorizing.*themes",
        r"chat history",
        r"conversation title",
        r"summarize.*conversation",
        r"task:\s*generate",  # "Task: Generate..." pattern
        r"output:\s*json\s*format",  # "Output: JSON format" pattern
        r"broad tags",  # "Generate 1-3 broad tags"
        r"subtopic tags",  # "more specific subtopic tags"
        r"guidelines:",  # OpenWebUI title requests have "### Guidelines:"
        r"use the chat's primary language",  # OpenWebUI specific text
    ]
    
    for pattern in title_patterns:
        if re.search(pattern, content_lower):
            logger.info(f"🎯 Detected title generation request: matched pattern '{pattern}'")
            logger.debug(f"   Content snippet: {content_lower[:150]}...")
            return True
    
    logger.debug(f"❌ Not a title request - no patterns matched")
    return False

async def _generate_title_with_gpt(
    messages: List[Dict[str, Any]],
    assistant_owner: Optional[str],
    api_key: str = None
) -> Dict[str, Any]:
    """
    Use GPT-4o-mini to generate a title/tags response
    
    Args:
        messages: Original messages
        assistant_owner: Assistant owner email for org config
        api_key: Optional API key (for consistency)
        
    Returns:
        OpenAI-compatible response dictionary
    """
    logger.info("📝 Generating title using GPT-4o-mini")
    
    # Get organization-specific OpenAI configuration
    openai_api_key = None
    base_url = None
    model = "gpt-4o-mini"
    
    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            openai_config = config_resolver.get_provider_config("openai")
            
            if openai_config:
                openai_api_key = openai_config.get("api_key")
                base_url = openai_config.get("base_url")
                # Use gpt-4o-mini or the smallest available model
                available_models = openai_config.get("models", [])
                if "gpt-4o-mini" in available_models:
                    model = "gpt-4o-mini"
                elif available_models:
                    model = available_models[0]  # Use first available
        except Exception as e:
            logger.warning(f"Error getting OpenAI config: {e}")
    
    # Fallback to environment variables
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
    
    if not openai_api_key:
        raise ValueError("No OpenAI API key found for title generation")
    
    # Create OpenAI client
    client = AsyncOpenAI(api_key=openai_api_key, base_url=base_url)
    
    # Call GPT-4o-mini
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )
    
    logger.info(f"✅ Title generated successfully with {model}")
    
    # Return OpenAI-compatible format
    return response.model_dump()

async def llm_connect(messages: list, stream: bool = False, body: Dict[str, Any] = None, llm: str = None, assistant_owner: Optional[str] = None):
    """
    Banana Image connector for Google Gen AI (Gemini) image generation
    
    This connector intelligently routes requests:
    - Title/tags requests → GPT-4o-mini for text generation
    - Image prompts → Google Gen AI (Gemini) for image generation
    
    For image generation, it saves images to /backend/static/public/{user_id}/img/
    and returns markdown with the image link.

    Args:
        messages: List of message dictionaries (expects last user message to contain prompt)
        stream: Not supported for image generation (always False)
        body: Original request body with generation parameters
        llm: Model to use (defaults to gemini-2.0-flash-preview-image-generation)
        assistant_owner: Email of assistant owner for org config

    Returns:
        Dict: OpenAI-compatible response with either text or markdown image link
    """
    # Log entry point for debugging
    logger.info(f"🍌 banana_img.llm_connect called - llm={llm}, stream={stream}, owner={assistant_owner}")
    logger.info(f"🍌 Message count: {len(messages) if messages else 0}")
    if messages:
        last_msg = messages[-1] if messages else {}
        content = last_msg.get('content', '')
        preview = content[:100] if isinstance(content, str) else str(content)[:100]
        logger.info(f"🍌 Last message preview: {preview}...")
    
    # Track if streaming was originally requested - we need to return correct format
    original_stream = stream
    
    # Image generation doesn't support streaming internally, but we need to
    # return the correct format based on what was requested
    if stream:
        logger.info("🔄 Streaming requested - will convert response to SSE format")
    
    # Check if this is a title generation request
    if _is_title_generation_request(messages):
        logger.info("🔀 Routing to GPT-4o-mini for title generation")
        # Use GPT-4o-mini to generate title
        title_response = await _generate_title_with_gpt(messages, assistant_owner)
        logger.info(f"📤 Returning title generation response: {type(title_response)}, stream_requested={original_stream}")
        
        # If streaming was requested, convert to SSE format
        if original_stream:
            return _dict_to_streaming_response(title_response)
        return title_response
    
    logger.info("🖼️ NOT a title request - proceeding with IMAGE GENERATION")
    
    # Validate model name early
    available_models = get_available_llms(assistant_owner)
    model = llm or "gemini-2.5-flash-image-preview"  # Default to cheapest Gemini model
    logger.info(f"🖼️ Model validation: requested='{model}', available={available_models}")
    
    if model not in available_models:
        error_msg = (
            f"Invalid model '{model}' for image generation.\n\n"
            f"Available models:\n"
            + "\n".join(f"  • {m}" for m in available_models) +
            f"\n\nPlease update your assistant configuration to use one of the available models."
        )
        logger.error(f"❌ {error_msg}")
        error_response = {
            "id": f"chatcmpl-error_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"❌ Configuration Error: {error_msg}"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        return _maybe_stream_response(error_response, original_stream)
    
    logger.info(f"✅ Model '{model}' validated successfully")
    logger.info(f"🔧 Getting organization config for owner: {assistant_owner}")

    # Get organization-specific configuration
    api_key = None
    org_name = "Unknown"
    config_source = "env_vars"

    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            org_name = config_resolver.organization.get('name', 'Unknown')
            google_config = config_resolver.get_provider_config("google")

            if google_config and google_config.get("enabled", True):
                api_key = google_config.get("api_key")
                config_source = "organization"
                logger.info(f"Using organization: '{org_name}' (owner: {assistant_owner})")
            else:
                logger.warning(f"Google Gen AI disabled for organization of user {assistant_owner}")
        except Exception as e:
            logger.error(f"Error getting Google Gen AI config for {assistant_owner}: {e}")

    # Fallback to environment variables
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not assistant_owner:
            logger.info("Using environment variable configuration (no assistant owner provided)")
        else:
            logger.info(f"Using environment variable configuration (fallback for {assistant_owner})")

    if not api_key:
        error_msg = (
            "Image generation requires Google Gen AI API key configuration. "
            "Please configure one of the following:\n"
            "1. Organization config: Set 'google.api_key' in organization settings\n"
            "2. Environment variable: Set GEMINI_API_KEY or GOOGLE_API_KEY\n\n"
            f"Current status: Google Gen AI disabled for organization '{org_name}' (owner: {assistant_owner or 'N/A'})"
        )
        logger.error(f"❌ {error_msg}")
        # Return a proper error response instead of raising
        error_response = {
            "id": f"chatcmpl-error_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"❌ Configuration Error: {error_msg}"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        return _maybe_stream_response(error_response, original_stream)

    # Extract prompt from messages
    prompt = _extract_prompt_from_messages(messages)
    if not prompt:
        error_msg = "No prompt found in messages for image generation. Please provide a text description of the image you want to generate."
        logger.error(f"❌ {error_msg}")
        # Return a proper error response instead of raising
        error_response = {
            "id": f"chatcmpl-error_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"❌ Error: {error_msg}"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        return _maybe_stream_response(error_response, original_stream)

    # Extract generation parameters from body
    generation_config = _extract_generation_config(body)
    
    # Get user_id for file storage (use Creator_users.id from database)
    user_id = "default"
    if assistant_owner:
        try:
            db_manager = LambDatabaseManager()
            creator_user = db_manager.get_creator_user_by_email(assistant_owner)
            if creator_user and creator_user.get('id'):
                user_id = str(creator_user['id'])
                logger.info(f"👤 Using creator user ID: {user_id} for owner: {assistant_owner}")
            else:
                logger.warning(f"⚠️ Creator user not found for email: {assistant_owner}, using default")
        except Exception as e:
            logger.error(f"❌ Error getting creator user ID: {e}, using default")
            user_id = "default"
    
    # Create image storage directory
    # Use absolute path resolution - go from banana_img.py location to backend root
    # banana_img.py is at: backend/lamb/completions/connectors/banana_img.py
    # We need: backend/static/public/{user_id}/img/
    backend_root = Path(__file__).parent.parent.parent.parent
    static_dir = backend_root / "static" / "public" / user_id / "img"
    
    # Verify backend_root exists and contains 'static'
    if not backend_root.exists():
        logger.error(f"❌ Backend root does not exist: {backend_root}")
        raise ValueError(f"Backend root directory not found: {backend_root}")
    
    static_base = backend_root / "static"
    if not static_base.exists():
        logger.error(f"❌ Static directory does not exist: {static_base}")
        raise ValueError(f"Static directory not found: {static_base}")
    
    # Create directory with error handling
    try:
        static_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Image storage directory: {static_dir} (absolute: {static_dir.resolve()})")
        
        # Verify directory was created and is writable
        if not static_dir.exists():
            raise ValueError(f"Failed to create directory: {static_dir}")
        if not os.access(static_dir, os.W_OK):
            raise ValueError(f"Directory is not writable: {static_dir}")
    except Exception as e:
        logger.error(f"❌ Failed to create image storage directory: {e}")
        raise ValueError(f"Cannot create image storage directory: {e}")

    try:
        logger.info(f"🍌 === STARTING IMAGE GENERATION ===")
        logger.info(f"🍌 Model: {model}")
        logger.info(f"🍌 Prompt: {prompt[:200]}..." if len(prompt) > 200 else f"🍌 Prompt: {prompt}")
        logger.info(f"🍌 Config: {generation_config}")

        # Initialize Google Gen AI client
        try:
            client = genai.Client(api_key=api_key)
        except Exception as init_error:
            error_type = type(init_error).__name__
            error_msg = (
                f"Failed to initialize Google Gen AI client: {error_type}: {str(init_error)}\n\n"
                "Please ensure:\n"
                "1. Google Gen AI API key is valid\n"
                "2. API key has access to image generation models"
            )
            logger.error(f"❌ {error_msg}")
            error_response = {
                "id": f"chatcmpl-error_{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"❌ Authentication Error: {error_msg}"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            return _maybe_stream_response(error_response, original_stream)

        # Generate images using Google Gen AI
        # Two different APIs:
        # - Imagen models (imagen-*) use generate_images()
        # - Gemini image models (gemini-*-image*) use generate_content()
        try:
            is_gemini_model = 'gemini' in model.lower() and 'image' in model.lower()
            
            if is_gemini_model:
                # Gemini image models use generate_content API
                logger.info(f"🔄 Using generate_content API for Gemini model: {model}")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                # Extract images from response
                generated_images = []
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data'):
                                    generated_images.append(part.inline_data)
                
                if not generated_images:
                    raise ValueError("No images generated by Gemini model - response contained no image data")
                
                # Create a mock response object with generated_images attribute
                class MockResponse:
                    def __init__(self, images):
                        self.generated_images = images
                
                response = MockResponse(generated_images)
            else:
                # Imagen models use generate_images API
                logger.info(f"🔄 Using generate_images API for Imagen model: {model}")
                image_config = types.GenerateImagesConfig(
                    number_of_images=generation_config["number_of_images"],
                    aspect_ratio=generation_config["aspect_ratio"],
                    output_mime_type=generation_config["output_mime_type"],
                )
                
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=image_config,
                )
        except Exception as gen_error:
            error_type = type(gen_error).__name__
            error_msg = (
                f"Failed to generate image with Google Gen AI: {error_type}: {str(gen_error)}\n\n"
                "Please ensure:\n"
                "1. Model name is correct (e.g., 'gemini-2.0-flash-preview-image-generation')\n"
                "2. API key has permissions for image generation\n"
                "3. Prompt follows content safety guidelines"
            )
            logger.error(f"❌ {error_msg}")
            error_response = {
                "id": f"chatcmpl-error_{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"❌ Generation Error: {error_msg}"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            return _maybe_stream_response(error_response, original_stream)

        # Process generated images
        if not hasattr(response, 'generated_images') or not response.generated_images:
            logger.error(f"❌ No images in response. Response type: {type(response)}, attributes: {dir(response)}")
            raise ValueError("No images generated by Google Gen AI - response.generated_images is empty or missing")
        
        logger.info(f"📸 Processing {len(response.generated_images)} generated image(s)")
        image_urls = []
        
        for i, generated_image in enumerate(response.generated_images):
            try:
                # Skip None images
                if generated_image is None:
                    logger.warning(f"⚠️  Image {i+1} is None, skipping")
                    continue
                
                # Get mime type early (needed for output format)
                mime_type = 'image/png'  # default
                
                # Handle two different response formats:
                # 1. Imagen: generated_image.image (has .image attribute)
                # 2. Gemini: generated_image is inline_data (has .data and .mime_type)
                pil_image = None
                
                # Get mime type if available
                if hasattr(generated_image, 'mime_type'):
                    mime_type = generated_image.mime_type
                
                # Check if there's a helper method to get the image directly (Gemini format)
                if hasattr(generated_image, 'as_image') and callable(getattr(generated_image, 'as_image')):
                    logger.debug(f"Using as_image() method for image {i+1}")
                    try:
                        image_result = generated_image.as_image()
                        # as_image() might return google.genai.types.Image or PIL Image
                        if isinstance(image_result, Image.Image):
                            pil_image = image_result
                            logger.debug(f"✅ Successfully got PIL Image via as_image()")
                        else:
                            # It's a google.genai.types.Image wrapper, will convert later
                            pil_image = image_result
                            logger.debug(f"✅ Got image object via as_image(), will convert to PIL")
                    except Exception as e:
                        logger.warning(f"as_image() failed: {e}, trying data attribute")
                
                if pil_image is None:
                    # Try using data attribute or image attribute
                    if hasattr(generated_image, 'image'):
                        # Imagen format
                        image_data = generated_image.image
                        if hasattr(image_data, '_pil_image'):
                            pil_image = image_data._pil_image
                        elif hasattr(image_data, 'data'):
                            # Decode base64 image data
                            image_bytes = base64.b64decode(image_data.data)
                            pil_image = Image.open(BytesIO(image_bytes))
                        else:
                            # Try to use as_image() method if available
                            pil_image = image_data
                    elif hasattr(generated_image, 'data'):
                        # Gemini format (inline_data) - fallback to manual decoding
                        logger.debug(f"Processing Gemini inline_data format (manual decode)")
                        data_value = generated_image.data
                        
                        # Handle different data types
                        if isinstance(data_value, bytes):
                            # Already bytes, use directly
                            image_bytes = data_value
                        elif isinstance(data_value, str):
                            # Try base64 decode
                            try:
                                image_bytes = base64.b64decode(data_value)
                            except Exception as decode_error:
                                logger.error(f"Failed to decode base64: {decode_error}")
                                raise ValueError(f"Cannot decode image data: {decode_error}")
                        else:
                            raise ValueError(f"Unknown data type: {type(data_value)}")
                        
                        pil_image = Image.open(BytesIO(image_bytes))
                    else:
                        raise ValueError(f"Unknown image format: {type(generated_image)}")
                
                # Verify we have a valid PIL Image
                if pil_image is None:
                    logger.error(f"❌ Failed to extract image data for image {i+1}")
                    continue
                
                # Check if it's actually a PIL Image
                if not isinstance(pil_image, Image.Image):
                    logger.debug(f"Image object is not standard PIL Image: {type(pil_image)}, attempting conversion")
                    converted = False
                    
                    # Try to convert google.genai.types.Image to PIL Image
                    if hasattr(pil_image, '_pil_image'):
                        pil_image = pil_image._pil_image
                        converted = True
                        logger.debug(f"✅ Converted via _pil_image attribute")
                    elif hasattr(pil_image, 'data'):
                        # google.genai.types.Image might have data attribute
                        try:
                            if isinstance(pil_image.data, bytes):
                                pil_image = Image.open(BytesIO(pil_image.data))
                                converted = True
                            elif isinstance(pil_image.data, str):
                                image_bytes = base64.b64decode(pil_image.data)
                                pil_image = Image.open(BytesIO(image_bytes))
                                converted = True
                            else:
                                logger.warning(f"Unknown data type in google.genai.types.Image.data: {type(pil_image.data)}")
                        except Exception as conv_error:
                            logger.warning(f"Failed to convert via data attribute: {conv_error}")
                    elif hasattr(pil_image, 'as_bytes') or hasattr(pil_image, 'bytes'):
                        # Try to get bytes and convert
                        try:
                            image_bytes = pil_image.as_bytes() if hasattr(pil_image, 'as_bytes') else pil_image.bytes()
                            pil_image = Image.open(BytesIO(image_bytes))
                            converted = True
                            logger.debug(f"✅ Converted image to PIL Image via bytes")
                        except Exception as conv_error:
                            logger.warning(f"Failed to convert via bytes: {conv_error}")
                    
                    if not converted:
                        # If conversion failed but object might still be saveable (duck typing)
                        # Log warning but continue - PIL.save() might accept it
                        logger.warning(f"⚠️  Could not convert {type(pil_image)} to PIL Image, but will attempt to save anyway")
                        # Don't continue - let it try to save, might work via duck typing
                
                logger.debug(f"Image {i+1}: type={type(pil_image)}")

                # Convert to RGB if necessary (for JPEG compatibility)
                if hasattr(pil_image, 'mode') and pil_image.mode != 'RGB':
                    logger.debug(f"Converting from {pil_image.mode} to RGB")
                    pil_image = pil_image.convert('RGB')
                    logger.debug(f"Converted image {i+1} to RGB")

                # Determine output format from mime type or generation config
                if 'jpeg' in mime_type or 'jpg' in mime_type:
                    output_format = 'JPEG'
                    extension = 'jpg'
                elif 'png' in mime_type:
                    output_format = 'PNG'
                    extension = 'png'
                elif 'webp' in mime_type:
                    output_format = 'WEBP'
                    extension = 'webp'
                else:
                    # Fallback to generation_config
                    output_format = generation_config.get("output_format", "JPEG")
                    extension = output_format.lower()

                # Generate unique filename
                timestamp = int(time.time() * 1000)
                unique_id = str(uuid.uuid4())[:8]
                filename = f"img_{timestamp}_{unique_id}.{extension}"
                file_path = static_dir / filename
                
                logger.info(f"💾 Saving image {i+1} to: {file_path}")
                
                # Save image to file with error handling
                # Try with format parameter first, fallback to extension-based if it fails
                try:
                    pil_image.save(str(file_path), format=output_format)
                except TypeError:
                    # Fallback: let PIL detect format from extension
                    logger.debug(f"Format parameter failed, using extension-based detection")
                    pil_image.save(str(file_path))
                
                # Verify file was created
                if not file_path.exists():
                    raise ValueError(f"File was not created: {file_path}")
                
                file_size = file_path.stat().st_size
                logger.info(f"✅ Image {i+1} saved successfully: {file_path} ({file_size} bytes)")
                
                # Generate public URL
                # Format: {LAMB_WEB_HOST}/static/public/{user_id}/img/{filename}
                static_path = f"/static/public/{user_id}/img/{filename}"
                image_url = f"{config.LAMB_WEB_HOST.rstrip('/')}{static_path}"
                image_urls.append(image_url)
                logger.debug(f"Generated URL for image {i+1}: {image_url}")
                    
            except Exception as img_error:
                logger.error(f"❌ Error processing image {i+1}: {img_error}")
                import traceback
                logger.debug(traceback.format_exc())
                # Continue with other images if one fails
                continue
                
            except Exception as img_error:
                logger.error(f"❌ Error processing image {i+1}: {img_error}")
                # Continue with other images if one fails
                continue
        
        if not image_urls:
            error_msg = "Failed to save any images - all save operations failed"
            logger.error(f"❌ {error_msg}")
            error_response = {
                "id": f"chatcmpl-error_{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"❌ Error: {error_msg}"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": 0,
                    "total_tokens": len(prompt.split())
                }
            }
            return _maybe_stream_response(error_response, original_stream)
        
        # Generate markdown response with image(s)
        if len(image_urls) == 1:
            markdown_content = f"![Generated Image]({image_urls[0]})"
        else:
            # Multiple images - show them all
            markdown_parts = [f"![Generated Image {i+1}]({url})" for i, url in enumerate(image_urls)]
            markdown_content = "\n\n".join(markdown_parts)
        
        logger.info(f"✅ Generated {len(image_urls)} image(s) with markdown: {markdown_content[:100]}...")
        
        # Return OpenAI-compatible chat completion format
        response_data = {
            "id": f"chatcmpl-img_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": markdown_content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 0,
                "total_tokens": len(prompt.split())
            }
        }
        
        logger.info(f"📤 Returning response with {len(image_urls)} image URL(s), stream_requested={original_stream}")
        
        # If streaming was requested, convert to SSE format
        if original_stream:
            return _dict_to_streaming_response(response_data)
        return response_data

    except ValueError as ve:
        # Return proper error response instead of raising
        error_msg = str(ve)
        logger.error(f"❌ Image Generation ValueError: {error_msg}")
        logger.error(f"   Prompt: {prompt[:100] if prompt else 'N/A'}...")
        logger.error(f"   Model: {model}")
        logger.error(f"   User ID: {user_id}")
        logger.error(f"   Static Dir: {static_dir}")
        error_response = {
            "id": f"chatcmpl-error_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"❌ Error: {error_msg}"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()) if prompt else 0,
                "completion_tokens": 0,
                "total_tokens": len(prompt.split()) if prompt else 0
            }
        }
        return _maybe_stream_response(error_response, original_stream)
    except Exception as e:
        # Log full exception details and return proper error response
        import traceback
        error_trace = traceback.format_exc()
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else f"{error_type} occurred"
        logger.error(f"❌ Image Generation Exception: {error_type}: {error_msg}")
        logger.error(f"   Full traceback:\n{error_trace}")
        logger.error(f"   Prompt: {prompt[:100] if prompt else 'N/A'}...")
        logger.error(f"   Model: {model}")
        logger.error(f"   User ID: {user_id}")
        logger.error(f"   Static Dir: {static_dir}")
        error_response = {
            "id": f"chatcmpl-error_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"❌ Image Generation Failed: {error_type}: {error_msg}\n\nPlease check:\n1. Google Gen AI API key is valid\n2. API key has access to image generation models\n3. Prompt follows content safety guidelines"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()) if prompt else 0,
                "completion_tokens": 0,
                "total_tokens": len(prompt.split()) if prompt else 0
            }
        }
        return _maybe_stream_response(error_response, original_stream)

def _extract_prompt_from_messages(messages: List[Dict[str, Any]]) -> str:
    """
    Extract prompt from the last user message

    Args:
        messages: List of message dictionaries

    Returns:
        str: The prompt text
    """
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")

            # Handle both string and multimodal format
            if isinstance(content, str):
                return content.strip()
            elif isinstance(content, list):
                # Extract text from multimodal content
                text_parts = []
                for item in content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                return " ".join(text_parts).strip()

    return ""

def _extract_generation_config(body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract image generation configuration from request body

    Args:
        body: Request body dictionary

    Returns:
        Dict: Generation configuration
    """
    # Default configuration
    config = {
        "number_of_images": 1,
        "aspect_ratio": "16:9",
        "output_mime_type": "image/jpeg",
        "output_format": "JPEG"
    }

    if not body:
        return config

    # Extract from body (extend as needed for additional parameters)
    if "number_of_images" in body:
        config["number_of_images"] = min(max(int(body["number_of_images"]), 1), 4)  # Limit to 1-4

    if "aspect_ratio" in body:
        # Validate aspect ratio
        valid_ratios = ["1:1", "3:4", "4:3", "16:9", "9:16"]
        if body["aspect_ratio"] in valid_ratios:
            config["aspect_ratio"] = body["aspect_ratio"]

    if "output_mime_type" in body:
        valid_mime_types = ["image/jpeg", "image/png", "image/webp"]
        if body["output_mime_type"] in valid_mime_types:
            config["output_mime_type"] = body["output_mime_type"]
            # Set PIL format based on mime type
            if config["output_mime_type"] == "image/png":
                config["output_format"] = "PNG"
            elif config["output_mime_type"] == "image/webp":
                config["output_format"] = "WEBP"
            else:
                config["output_format"] = "JPEG"

    return config
