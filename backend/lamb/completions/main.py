from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, Response
from utils.pipelines.auth import bearer_security, get_current_user
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any, Dict, Optional, Union, Tuple
import importlib
import os
import glob
import requests
import logging
from lamb.database_manager import LambDatabaseManager
import json
from utils.timelog import Timelog
import traceback
import asyncio

# Set up logger for completions module
logger = logging.getLogger('lamb.completions')
logger.setLevel(logging.INFO)

# Create handler if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

router = APIRouter(tags=["completions"])
security = HTTPBearer()
db_manager = LambDatabaseManager()

@router.get("/list")
async def list_processors_and_connectors(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """
    List available Prompt Processors, Connectors, and RAG processors with their supported features
    Organization-aware: returns models enabled for the user's organization if authenticated
    """
    pps = load_plugins('pps')
    connectors = load_plugins('connectors')
    rag_processors = load_plugins('rag')
    
    # Determine assistant_owner (user email) from credentials for organization-aware model lists
    assistant_owner = None
    if credentials:
        try:
            from lamb.owi_bridge.owi_users import OwiUserManager
            user_manager = OwiUserManager()
            owi_user = user_manager.get_user_auth(credentials.credentials)
            if owi_user:
                assistant_owner = owi_user.get('email')
                logger.info(f"Fetching capabilities for user: {assistant_owner}")
        except Exception as e:
            logger.warning(f"Could not resolve user from token for capabilities: {e}")
    
    # Get available LLMs for each connector (organization-aware if assistant_owner is set)
    connector_info = {}
    for connector_name, connector_module in connectors.items():
        module = importlib.import_module(f"lamb.completions.connectors.{connector_name}")
        available_llms = []
        if hasattr(module, 'get_available_llms'):
            get_llms_func = getattr(module, 'get_available_llms')
            
            # Call with assistant_owner if function signature supports it
            try:
                if asyncio.iscoroutinefunction(get_llms_func):
                    available_llms = await get_llms_func(assistant_owner=assistant_owner)
                else:
                    available_llms = get_llms_func(assistant_owner=assistant_owner)
            except TypeError:
                # Function doesn't accept assistant_owner parameter (e.g., bypass connector)
                if asyncio.iscoroutinefunction(get_llms_func):
                    available_llms = await get_llms_func()
                else:
                    available_llms = get_llms_func()
        
        connector_info[connector_name] = {
            "name": connector_name,
            "available_llms": available_llms
        }
    
    return {
        "prompt_processors": list(pps.keys()),
        "connectors": connector_info,
        "rag_processors": list(rag_processors.keys())
    }


@router.get("/tools")
async def list_available_tools():
    """
    List available tools that can be configured for assistant function calling.
    
    Returns a list of tools with their name, description, category, and function name.
    This endpoint is used by the frontend to populate the Tools selection in the assistant configuration.
    """
    from lamb.completions.tools import list_available_tools as get_tools_list
    
    tools = get_tools_list()
    logger.info(f"Returning {len(tools)} available tools")
    
    return {
        "tools": tools,
        "count": len(tools)
    }


@router.post("/")
async def create_completion(
    request: Dict[str, Any],
    assistant: int,  # now expect only an assistant id as int
    credentials: HTTPAuthorizationCredentials = Depends(bearer_security)
):
    """
    Create a completion using the specified assistant id.
    Retrieves the assistant from the database and applies the default prompt processor and connector.
    Returns a format compatible with OpenAI API.
    """
    try:
        logger.info("Starting completion request")
        logger.debug(f"Parameters: assistant={assistant}")
        Timelog(f"Starting completion request: assistant={assistant}",1)
        # Use helper functions to structure the process:
        assistant_details = get_assistant_details(assistant)
        Timelog(f"Assistant details: {assistant_details}",2)
        plugin_config = parse_plugin_config(assistant_details)
        Timelog(f"Plugin config: {plugin_config}",2)
        pps, connectors, rag_processors = load_and_validate_plugins(plugin_config)
        Timelog(f"Plugins loaded: {pps}, {connectors}, {rag_processors}",2)
        rag_context = await get_rag_context(request, rag_processors, plugin_config["rag_processor"], assistant_details)
        Timelog(f"RAG context: {rag_context}",2)
        messages = process_completion_request(request, assistant_details, plugin_config, rag_context, pps)
        Timelog(f"Messages: {messages}",2)
        stream = request.get("stream", False)
        Timelog(f"Stream mode: {stream}",2)
        logger.debug(f"Stream mode: {stream}")
        logger.info("Getting completion from LLM")
        if stream:
            logger.debug("Returning streaming response")
            Timelog(f"Returning streaming response",2)
            return StreamingResponse(
                connectors[plugin_config["connector"]](messages, stream=True, body=request, llm=plugin_config["llm"], assistant_owner=assistant_details.owner, assistant=assistant_details),
                media_type="text/event-stream"
            )
        else:
            logger.debug("Returning direct response")
            Timelog(f"Returning direct response",2)
            return connectors[plugin_config["connector"]](messages, stream=False, body=request, llm=plugin_config["llm"], assistant_owner=assistant_details.owner, assistant=assistant_details)
    except Exception as e:
        logger.error(f"Error in create_completion: {str(e)}", exc_info=True)
        Timelog(f"Error in create_completion: {str(e)}",2)
        stream = request.get("stream", False)
        Timelog(f"Stream mode: {stream}",2)
        error_msg = f"Error in create_completion: {str(e)}"
        Timelog(f"Error message: {error_msg}",2)
        if stream:
            Timelog(f"Returning streaming response",2)
            return StreamingResponse(
                iter([f"data: {error_msg}\n\n".encode()]),
                media_type="text/event-stream"
            )
        raise HTTPException(status_code=500, detail=error_msg)

def get_assistant_details(assistant: int) -> Any:
    """
    Fetch the assistant details from the database.
    """
    assistant_details = db_manager.get_assistant_by_id(assistant)
    if not assistant_details:
        logger.error(f"Assistant with ID '{assistant}' not found")
        raise HTTPException(status_code=404, detail=f"Assistant with ID '{assistant}' not found")
    return assistant_details

def parse_plugin_config(assistant_details) -> Dict[str, str]:
    """
    Parse the metadata field from the assistant record.
    Expects a JSON string with keys: prompt_processor, connector, llm, rag_processor.
    """
    try:
        # Handle empty string case by defaulting to an empty JSON object
        if not assistant_details.metadata or assistant_details.metadata.strip() == '':
            logger.warning(f"Empty metadata for assistant {assistant_details.id}, using default values")
            callback = {}
        else:
            callback = json.loads(assistant_details.metadata)
    except Exception as e:
        logger.error(f"Failed to parse metadata for assistant {assistant_details.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Assistant metadata cannot be parsed: {e}")

    # Set default values if keys are missing
    defaults = {
        "prompt_processor": "default",
        "connector": "openai",
        "llm": "gpt-4",
        "rag_processor": ""
    }
    
    # Apply defaults for missing keys
    for key in defaults:
        if key not in callback:
            callback[key] = defaults[key]
            logger.info(f"Using default {key}={defaults[key]} for assistant {assistant_details.id}")

    return callback

def load_and_validate_plugins(plugin_config: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Load plugin modules and verify that the requested plugins exist.
    """
    pps = load_plugins('pps')
    connectors = load_plugins('connectors')
    rag_processors = load_plugins('rag')

    if plugin_config["prompt_processor"] not in pps:
        logger.error(f"Prompt processor '{plugin_config['prompt_processor']}' not found")
        raise HTTPException(status_code=400, detail=f"Prompt processor '{plugin_config['prompt_processor']}' not found")
    if plugin_config["connector"] not in connectors:
        logger.error(f"Connector '{plugin_config['connector']}' not found")
        raise HTTPException(status_code=400, detail=f"Connector '{plugin_config['connector']}' not found")
    if plugin_config["rag_processor"] and plugin_config["rag_processor"] not in rag_processors:
        logger.error(f"RAG processor '{plugin_config['rag_processor']}' not found")
        raise HTTPException(status_code=400, detail=f"RAG processor '{plugin_config['rag_processor']}' not found")

    return pps, connectors, rag_processors

async def get_rag_context(request: Dict[str, Any], rag_processors: Dict[str, Any], rag_processor: str, assistant_details: Any) -> Any:
    """
    If a RAG processor is specified, process the RAG context using the plugin.
    Supports both sync and async RAG processors.
    """
    if rag_processor:
        logger.info("Processing RAG request")
        messages = request.get('messages', [])
        rag_func = rag_processors[rag_processor]
        
        # Check if the RAG processor is async
        if asyncio.iscoroutinefunction(rag_func):
            logger.debug(f"RAG processor '{rag_processor}' is async, awaiting...")
            rag_context = await rag_func(messages=messages, assistant=assistant_details, request=request)
        else:
            logger.debug(f"RAG processor '{rag_processor}' is sync, calling directly...")
            rag_context = rag_func(messages=messages, assistant=assistant_details, request=request)
        
        logger.debug(f"RAG context generated: {rag_context}")
        return rag_context
    logger.debug("No RAG processor requested")
    return None

def process_completion_request(request: Dict[str, Any], assistant_details: Any, plugin_config: Dict[str, str], rag_context: Any, pps: Dict[str, Any]) -> Any:
    """
    Process the prompt using the specified prompt processor and return prepared messages.
    """
    logger.info("Processing completion request")
    messages = pps[plugin_config["prompt_processor"]](request=request, assistant=assistant_details, rag_context=rag_context)
    logger.debug(f"Processed messages: {messages}")
    return messages

def load_plugins(plugin_type: str) -> Dict[str, Any]:
    """
    Dynamically load plugins from the specified directory
    plugin_type can be 'pps', 'connectors', or 'rag'
    """
    plugins = {}
    plugin_dir = os.path.join(os.path.dirname(__file__), plugin_type)
    
    # Get all .py files in the directory
    plugin_files = glob.glob(os.path.join(plugin_dir, "*.py"))
    
    for plugin_file in plugin_files:
        if "__init__" in plugin_file:
            continue
            
        module_name = os.path.basename(plugin_file)[:-3]  # Remove .py
        try:
            module = importlib.import_module(f"lamb.completions.{plugin_type}.{module_name}")
            if plugin_type == 'pps' and hasattr(module, 'prompt_processor'):
                plugins[module_name] = module.prompt_processor
            elif plugin_type == 'connectors' and hasattr(module, 'llm_connect'):
                plugins[module_name] = module.llm_connect
            elif plugin_type == 'rag' and hasattr(module, 'rag_processor'):
                plugins[module_name] = module.rag_processor
        except Exception as e:
            print(f"Error loading plugin {module_name}: {str(e)}")            
    return plugins


async def run_lamb_assistant(
    request: Dict[str, Any],
    assistant: int,  # now expect only an assistant id as int
    headers: Optional[Dict[str, str]] = None # Add optional headers argument
):
    """
    Implements a non WS version of create completion.
    Retrieves the assistant, applies plugins, and calls the connector.
    Returns a format compatible with OpenAI API, including headers.
    Assumes the connector (like openai.py) returns OpenAI-compatible output.
    """
    final_headers = headers if headers is not None else {}

    try:
        assistant_details = get_assistant_details(assistant)
        logger.debug(f"Run assistant, details: {assistant_details}")
        plugin_config = parse_plugin_config(assistant_details)
        pps, connectors, rag_processors = load_and_validate_plugins(plugin_config)
        rag_context = await get_rag_context(request, rag_processors, plugin_config["rag_processor"], assistant_details)
        messages = process_completion_request(request, assistant_details, plugin_config, rag_context, pps)
        stream = request.get("stream", False)
        llm = plugin_config.get("llm") # Get LLM from config

        logger.debug(f"Calling connector '{plugin_config['connector']}' with stream={stream}, llm={llm}")

        # Get the connector function
        connector_func = connectors[plugin_config["connector"]]

        # Call the connector function, passing all necessary arguments
        # The openai.py connector expects: messages, stream, body (original request), llm, assistant_owner, assistant
        llm_response = await connector_func( # Use await as connector is now async
            messages=messages,
            stream=stream,
            body=request, # Pass the original request dict as body
            llm=llm,
            assistant_owner=assistant_details.owner,
            assistant=assistant_details  # Pass full assistant for tool detection
        )

        if stream:
            # The openai.py connector returns an async generator yielding SSE strings
            # Wrap this directly in StreamingResponse
            logger.debug("Returning StreamingResponse for async generator from connector.")
            return StreamingResponse(
                llm_response, # llm_response is the async generator
                media_type="text/event-stream",
                headers=final_headers
            )
        else:
            # The openai.py connector returns a dictionary (result of model_dump())
            # Wrap this directly in a Response
            logger.debug("Returning Response with dictionary from connector.")
            if not isinstance(llm_response, dict):
                 logger.error(f"Non-streaming connector did not return a dict, got: {type(llm_response)}")
                 raise HTTPException(status_code=500, detail="Internal server error: Connector returned unexpected type for non-streaming response.")

            return Response(
                content=json.dumps(llm_response, indent=2), # Ensure pretty printing if desired
                media_type="application/json",
                headers=final_headers
            )

    except HTTPException as http_exc:
        # Re-raise known HTTP exceptions from helpers or connector
        logger.warning(f"HTTPException caught in run_lamb_assistant: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Error in run_lamb_assistant: {str(e)}", exc_info=True)
        stream = request.get("stream", False) # Check stream flag again for error response
        error_detail = {
             "error": {
                 "message": f"Internal server error: {str(e)}",
                 "type": "internal_server_error",
                 "param": None,
                 "code": None
                 },
             "traceback": traceback.format_exc() # Optional: include for debugging
        }
        error_status_code = 500

        if stream:
             # For streaming errors, return a SSE error message if possible
             sse_error = f"data: {json.dumps(error_detail['error'])}\\n\\n" # Only send the error part in SSE
             return StreamingResponse(
                 iter([sse_error.encode()]),
                 media_type="text/event-stream",
                 headers=final_headers, # Include headers even for errors
                 status_code=error_status_code
             )
        else:
             # For non-streaming errors, return a JSON error response
             return Response(
                 content=json.dumps(error_detail), # Send full detail for non-streaming
                 status_code=error_status_code,
                 media_type="application/json",
                 headers=final_headers # Include headers even for errors
             )