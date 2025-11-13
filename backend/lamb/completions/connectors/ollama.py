import json
# import requests
import os
import logging
from typing import Dict, Any, AsyncGenerator, Optional
import time
import asyncio
import aiohttp # Import aiohttp
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def get_available_llms(assistant_owner: Optional[str] = None): # Make async
    """
    Return list of available LLMs from Ollama API
    
    Args:
        assistant_owner: Optional assistant owner email to get org-specific models
    """
    base_url = None
    
    # Get organization-specific configuration if available
    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            ollama_config = config_resolver.get_provider_config("ollama")
            
            if ollama_config and ollama_config.get("enabled", True):
                base_url = ollama_config.get("base_url")
                # If models are pre-configured, return them
                if "models" in ollama_config:
                    return ollama_config["models"]
            else:
                logger.info(f"Ollama disabled for organization of user {assistant_owner}")
                return []
        except Exception as e:
            logger.error(f"Error getting Ollama config for {assistant_owner}: {e}")
    
    # Fallback to environment variables
    if not base_url:
        if os.getenv("OLLAMA_ENABLED", "false").lower() != "true":
            logger.info("OLLAMA_ENABLED is false, skipping model list fetch")
            return []

        base_url = os.getenv("OLLAMA_BASE_URL")
        if not base_url:
            logger.error("OLLAMA_BASE_URL is not defined")
            return []

    try:
        async with aiohttp.ClientSession() as session: # Use aiohttp session
            async with session.get(f"{base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json() # await json()
                    models = data.get('models', [])
                    return [model['name'] for model in models]
                else:
                    logger.error(f"Failed to get models from Ollama: {response.status}")
                    return []  # Return empty list on error
    except aiohttp.ClientError as e: # Catch aiohttp errors
        logger.error(f"Error fetching Ollama models: {str(e)}")
        return []  # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error fetching Ollama models: {str(e)}")
        return []

def format_messages_for_ollama(messages: list) -> list:
    """Convert OpenAI message format to Ollama format"""
    return [
        {
            "role": msg["role"],
            "content": msg["content"]
        }
        for msg in messages
    ]

async def llm_connect(messages: list, stream: bool = False, body: Dict[str, Any] = None, llm: str = None, assistant_owner: Optional[str] = None): # Make async
    """
    Ollama connector that returns OpenAI-compatible responses
    """
    # Get organization-specific configuration
    base_url = None
    model = None
    org_name = "Unknown"
    config_source = "env_vars"
    
    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            org_name = config_resolver.organization.get('name', 'Unknown')
            ollama_config = config_resolver.get_provider_config("ollama")
            
            if ollama_config:
                base_url = ollama_config.get("base_url")
                if not llm and ollama_config.get("models"):
                    model = ollama_config["models"][0]  # Use first model as default
                config_source = "organization"
                print(f"🏢 [Ollama] Using organization: '{org_name}' (owner: {assistant_owner})")
                logger.info(f"Using organization config for {assistant_owner} (org: {org_name})")
            else:
                print(f"⚠️  [Ollama] No config found for organization '{org_name}', falling back to environment variables")
                logger.warning(f"No Ollama config found for {assistant_owner} (org: {org_name}), falling back to env vars")
        except Exception as e:
            print(f"❌ [Ollama] Error getting organization config for {assistant_owner}: {e}")
            logger.error(f"Error getting org config for {assistant_owner}: {e}, falling back to env vars")
    
    # Fallback to environment variables
    if not base_url:
        import config
        base_url = os.getenv("OLLAMA_BASE_URL") or config.OLLAMA_BASE_URL
        if not assistant_owner:
            print(f"🔧 [Ollama] Using environment variable configuration (no assistant owner provided)")
        else:
            print(f"🔧 [Ollama] Using environment variable configuration (fallback for {assistant_owner})")
        logger.info("Using environment variable configuration")
    
    if not model:
        model = llm or os.getenv("OLLAMA_MODEL", "llama3.1")

    # Phase 3: Model resolution and fallback logic
    resolved_model = model
    fallback_used = False
    
    if assistant_owner and config_source == "organization":
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            ollama_config = config_resolver.get_provider_config("ollama")
            available_models = ollama_config.get("models", [])
            org_default_model = ollama_config.get("default_model")
            
            # Check if requested model is available
            if resolved_model not in available_models and available_models:
                original_model = resolved_model
                
                # Try organization's default model first
                if org_default_model and org_default_model in available_models:
                    resolved_model = org_default_model
                    fallback_used = True
                    logger.warning(f"Model '{original_model}' not available for org '{org_name}', using org default: '{resolved_model}'")
                    print(f"⚠️  [Ollama] Model '{original_model}' not enabled, using org default: '{resolved_model}'")
                
                # If org default is also not available, use first available model
                elif available_models:
                    resolved_model = available_models[0]
                    fallback_used = True
                    logger.warning(f"Model '{original_model}' and default '{org_default_model}' not available for org '{org_name}', using first available: '{resolved_model}'")
                    print(f"⚠️  [Ollama] Model '{original_model}' not enabled, using first available: '{resolved_model}'")
                
                # Note: Unlike OpenAI, we don't raise an error if no models are configured
                # because Ollama might have models available that aren't in the config
        
        except Exception as e:
            logger.error(f"Error during model resolution for {assistant_owner}: {e}")
            # Continue with original model if resolution fails

    print(f"🚀 [Ollama] Model: {resolved_model}{' (fallback)' if fallback_used else ''} | Config: {config_source} | Organization: {org_name} | URL: {base_url}")

    # Store org default for potential runtime fallback
    org_default_for_fallback = None
    if assistant_owner and config_source == "organization":
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            ollama_config = config_resolver.get_provider_config("ollama")
            org_default_for_fallback = ollama_config.get("default_model")
        except:
            pass

    # Helper to attempt API call with fallback on model-not-found errors
    async def _attempt_ollama_call_with_fallback(model_to_use: str, ollama_params: dict, is_stream: bool, attempt_fallback: bool = True):
        """
        Attempt Ollama API call with fallback to org default on model errors.
        Returns tuple: (success: bool, content_or_error: str)
        """
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{base_url}/api/chat", json=ollama_params) as response:
                    response.raise_for_status()
                    
                    if is_stream:
                        return (True, response)  # Return response object for streaming
                    else:
                        ollama_response = await response.json()
                        content = ollama_response.get("message", {}).get("content", "")
                        if not content:
                            return (False, f"Empty response from Ollama for model {model_to_use}")
                        return (True, content)
                        
        except aiohttp.ClientResponseError as e:
            error_msg = f"API Error ({e.status}) for model {model_to_use}: {e.message}"
            logger.error(f"Ollama {error_msg}")
            
            # Check if this is a model-not-found error (404) and fallback is available
            if e.status == 404 and attempt_fallback and org_default_for_fallback and model_to_use != org_default_for_fallback:
                logger.warning(f"Model '{model_to_use}' not found, attempting fallback to '{org_default_for_fallback}'")
                print(f"🔄 [Ollama] Model not found, retrying with org default: '{org_default_for_fallback}'")
                
                # Retry with org default
                fallback_params = ollama_params.copy()
                fallback_params["model"] = org_default_for_fallback
                success, result = await _attempt_ollama_call_with_fallback(org_default_for_fallback, fallback_params, is_stream, attempt_fallback=False)
                
                if success:
                    logger.info(f"✅ Ollama fallback to '{org_default_for_fallback}' succeeded")
                    print(f"✅ [Ollama] Fallback successful with model: '{org_default_for_fallback}'")
                    return (True, result)
                else:
                    logger.error(f"Ollama fallback to '{org_default_for_fallback}' also failed")
                    comprehensive_error = (
                        f"Ollama failure for organization '{org_name}':\n"
                        f"  • Model '{model_to_use}' failed: {error_msg}\n"
                        f"  • Fallback to '{org_default_for_fallback}' also failed: {result}\n"
                        f"Please verify models are pulled in Ollama"
                    )
                    return (False, comprehensive_error)
            
            return (False, error_msg)
            
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            error_msg = f"Connection error for model {model_to_use}: {str(e)}"
            logger.error(f"Ollama {error_msg}")
            return (False, error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error for model {model_to_use}: {str(e)}"
            logger.error(f"Ollama {error_msg}", exc_info=True)
            return (False, error_msg)

    try:
        if stream:
            async def generate_stream():
                # Prepare Ollama request payload with stream=True
                ollama_params = {
                    "model": resolved_model,
                    "messages": format_messages_for_ollama(messages),
                    "stream": True # Explicitly set stream to True for Ollama
                }
                # Add any additional parameters from body
                if body:
                    for key in ["temperature", "top_p", "top_k"]:
                        if key in body:
                            ollama_params[key] = body[key]

                logger.debug(f"Initiating Ollama stream with params: {ollama_params}")

                response_id = f"ollama-{int(time.time())}" # Generate a base ID
                created_time = int(time.time())
                sent_initial_role = False

                try:
                    timeout = aiohttp.ClientTimeout(total=120) # 2 minutes timeout
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(f"{base_url}/api/chat", json=ollama_params) as response:
                            response.raise_for_status() # Check for HTTP errors immediately

                            # Process the stream line by line
                            async for line_bytes in response.content:
                                if not line_bytes:
                                    continue # Skip empty lines
                                line = line_bytes.decode('utf-8').strip()
                                logger.debug(f"Received Ollama chunk line: {line}")

                                try:
                                    ollama_chunk = json.loads(line)
                                except json.JSONDecodeError:
                                    logger.warning(f"Skipping invalid JSON chunk from Ollama: {line}")
                                    continue

                                # Prepare OpenAI formatted chunk
                                current_choice = {
                                    "index": 0,
                                    "delta": {},
                                    "logprobs": None,
                                    "finish_reason": None
                                }
                                data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": resolved_model,
                                    "choices": [current_choice]
                                }

                                # Extract content delta
                                delta_content = ollama_chunk.get("message", {}).get("content")

                                # First chunk should include the role
                                if not sent_initial_role:
                                    current_choice["delta"]["role"] = "assistant"
                                    sent_initial_role = True

                                # Add content if present
                                if delta_content:
                                    current_choice["delta"]["content"] = delta_content

                                # Check if Ollama stream is done
                                if ollama_chunk.get("done"): # Check the 'done' field from Ollama
                                    logger.debug("Ollama stream finished.")
                                    # Yield final content chunk first (if any content exists)
                                    if current_choice["delta"]:
                                        yield f"data: {json.dumps(data)}\n\n"

                                    # Then yield final empty delta chunk with finish_reason
                                    current_choice["delta"] = {} # Final delta is usually empty
                                    current_choice["finish_reason"] = "stop"
                                    yield f"data: {json.dumps(data)}\n\n"
                                    break # Exit stream processing loop
                                else:
                                    # Yield regular content chunk if delta is not empty
                                    if current_choice["delta"]:
                                        yield f"data: {json.dumps(data)}\n\n"

                            # If the loop finishes without ollama_chunk["done"] == True (unlikely but possible)
                            # Ensure a final stop message is sent.
                            # This part might need refinement based on Ollama's exact behavior for errors/abrupt ends.
                            # logger.warning("Ollama stream ended without explicit 'done' flag.")

                except asyncio.TimeoutError:
                     logger.error(f"Timeout calling Ollama API after 120 seconds")
                     # Yield an error chunk?
                     error_data = {
                         "id": response_id,
                         "object": "chat.completion.chunk",
                         "created": created_time,
                         "model": resolved_model,
                         "choices": [{"index": 0, "delta": {"content": "[Ollama Error] Timeout"}, "finish_reason": "stop"}]
                     }
                     yield f"data: {json.dumps(error_data)}\n\n"
                except aiohttp.ClientResponseError as e:
                    logger.error(f"Error in Ollama API call ({e.status}): {e.message}")
                    error_data = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": resolved_model,
                        "choices": [{"index": 0, "delta": {"content": f"[Ollama Error] API Error {e.status}"}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                except aiohttp.ClientError as e:
                    logger.error(f"Connection error calling Ollama API: {str(e)}")
                    error_data = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": resolved_model,
                        "choices": [{"index": 0, "delta": {"content": "[Ollama Error] Connection Error"}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                except Exception as e:
                    logger.error(f"Unexpected error during Ollama API stream: {str(e)}", exc_info=True)
                    error_data = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": resolved_model,
                        "choices": [{"index": 0, "delta": {"content": "[Ollama Error] Unexpected Error"}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                finally:
                    # Always send [DONE] marker, even after errors
                    logger.debug("Sending [DONE] marker.")
                    yield "data: [DONE]\n\n"

            return generate_stream()
        else:
            # Non-streaming: use aiohttp
            content = f"[Ollama Error] Failed to get response from model {resolved_model}" # Default error
            
            # Prepare Ollama request payload for non-streaming
            ollama_params = {
                "model": resolved_model,
                "messages": format_messages_for_ollama(messages),
                "stream": False  # Explicitly set stream to False for non-streaming
            }
            # Add any additional parameters from body
            if body:
                for key in ["temperature", "top_p", "top_k"]:
                    if key in body:
                        ollama_params[key] = body[key]
            
            try:
                timeout = aiohttp.ClientTimeout(total=120) # 2 minutes timeout
                async with aiohttp.ClientSession(timeout=timeout) as session:
                     # Send keepalive header - aiohttp handles this automatically for HTTP/1.1
                    async with session.post(f"{base_url}/api/chat", json=ollama_params) as response:
                        response.raise_for_status()
                        ollama_response = await response.json()
                        content = ollama_response.get("message", {}).get("content", "")
                        if not content:
                             logger.warning("Empty response from Ollama, falling back to bypass")
                             content = f"[Ollama Error] No response from model: {resolved_model}"

            except asyncio.TimeoutError:
                logger.error(f"Timeout calling Ollama API after 120 seconds")
                # Raise or return error response? Returning error for now.
                content = f"[Ollama Error] Timeout after 120s for model {resolved_model}"
            except aiohttp.ClientResponseError as e:
                 logger.error(f"Error in Ollama API call ({e.status}): {e.message}")
                 content = f"[Ollama Error] API Error ({e.status}) for model {resolved_model}: {e.message}"
            except aiohttp.ClientError as e:
                logger.error(f"Connection error calling Ollama API: {str(e)}")
                content = f"[Ollama Error] Connection error for model {resolved_model}: {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error during Ollama non-stream call: {str(e)}", exc_info=True)
                content = f"[Ollama Error] Unexpected error for model {resolved_model}: {str(e)}"

            # Create OpenAI-compatible response
            return {
                "id": f"ollama-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": resolved_model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": -1, # Ollama response doesn't provide these
                    "completion_tokens": -1,
                    "total_tokens": -1
                }
            }

    # Removed outer try/except for requests errors as they are handled internally now
    # except requests.Timeout:
    #     logger.error(f"Timeout calling Ollama API after 120 seconds")
    #     raise Exception("Ollama API timeout")
    # except requests.RequestException as e:
    #     logger.error(f"Error calling Ollama API: {str(e)}")
    #     raise Exception(f"Ollama API error: {str(e)}")
    # Keeping general exception catch
    except Exception as e:
        logger.error(f"Unexpected error in Ollama connector: {str(e)}", exc_info=True)
        raise # Re-raise the original exception 