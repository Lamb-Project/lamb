from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json
import os
from lamb.database_manager import LambDatabaseManager
from lamb.completions.main import (
    get_assistant_details, 
    parse_plugin_config,
    load_and_validate_plugins,
    get_rag_context,
    load_plugins
)
from lamb.lamb_classes import Assistant
from utils.timelog import Timelog

# Initialize router
router = APIRouter(tags=["MCP"])

# Database manager
db_manager = LambDatabaseManager()

# Get LTI secret from environment
import config
LTI_SECRET = os.getenv('LTI_SECRET') or config.SIGNUP_SECRET_KEY

logging.basicConfig(level=logging.WARNING)

# Simple authentication dependency
async def get_current_user_email(
    authorization: str = Header(None),
    x_user_email: str = Header(None)
) -> str:
    """
    Simple authentication using LTI_SECRET and user email.
    Expects:
    - Authorization: Bearer <LTI_SECRET>
    - X-User-Email: <user_email>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    
    token = authorization.replace("Bearer ", "")
    
    if token != LTI_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Email header required"
        )
    
    logging.info(f"Authenticated user: {x_user_email}")
    return x_user_email

# MCP-specific utility functions
def build_mcp_prompt(
    messages: List[Dict[str, str]],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build an MCP prompt from assistant template and user input.
    This is separate from the regular PPS system to keep MCP functionality isolated.
    
    Returns a dictionary with:
    - prompt: The fully crafted prompt with all substitutions
    - system_prompt: The system prompt from the assistant
    - original_input: The original user input
    - rag_context: The RAG context if available
    - template_used: The prompt template that was used
    """
    if not messages:
        return {
            "prompt": "",
            "system_prompt": "",
            "original_input": "",
            "rag_context": None,
            "template_used": None
        }

    # Get the last user message
    last_message = messages[-1]['content']
    
    result = {
        "original_input": last_message,
        "system_prompt": "",
        "prompt": last_message,  # Default to original if no template
        "rag_context": rag_context,
        "template_used": None
    }

    if assistant:
        # Add system prompt if available
        if assistant.system_prompt:
            result["system_prompt"] = assistant.system_prompt
        
        # Process using the prompt template if available
        if assistant.prompt_template:
            result["template_used"] = assistant.prompt_template
            
            # Replace placeholders in template
            Timelog(f"MCP Prompt Builder - User message: {last_message}", 2)
            prompt = assistant.prompt_template.replace("{user_input}", last_message)
            
            # Add RAG context if available
            if rag_context and isinstance(rag_context, dict):
                # Use the context from the RAG plugin directly
                # RAG plugins return {"context": "...", "sources": [...]}
                context = rag_context.get("context", "")
                prompt = prompt.replace("{context}", context)
            else:
                # Remove the context placeholder if no context
                prompt = prompt.replace("{context}", "")
            
            result["prompt"] = prompt
            
            # Also build the full conversation format if needed
            full_messages = []
            if assistant.system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": assistant.system_prompt
                })
            
            # Add previous messages except the last one
            full_messages.extend(messages[:-1])
            
            # Add the processed last message
            full_messages.append({
                "role": messages[-1]['role'],
                "content": prompt
            })
            
            result["full_messages"] = full_messages
    
    return result

# Pydantic models for MCP protocol
class MCPResource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None

class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPPrompt(BaseModel):
    name: str
    description: str
    arguments: Optional[List[Dict[str, Any]]] = None

class MCPServerInfo(BaseModel):
    name: str
    version: str
    protocolVersion: str = "2024-11-05"

class MCPInitializeRequest(BaseModel):
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]

class MCPListResourcesResponse(BaseModel):
    resources: List[MCPResource]

class MCPListToolsResponse(BaseModel):
    tools: List[MCPTool]

class MCPListPromptsResponse(BaseModel):
    prompts: List[MCPPrompt]

# MCP Server endpoints

@router.post("/initialize")
async def initialize_mcp_server(
    request: MCPInitializeRequest,
    user: str = Depends(get_current_user_email)
):
    """
    Initialize MCP server connection.
    
    This endpoint handles the initialization handshake for MCP protocol.
    """
    try:
        logging.info(f"MCP initialization request from user: {user}")
        
        # Validate protocol version
        if request.protocolVersion != "2024-11-05":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported protocol version: {request.protocolVersion}"
            )
        
        # Server capabilities
        capabilities = {
            "resources": {
                "subscribe": True,
                "listChanged": True
            },
            "tools": {
                "listChanged": True
            },
            "prompts": {
                "listChanged": True
            }
        }
        
        server_info = MCPServerInfo(
            name="LAMB-MCP-Server",
            version="0.1.0"
        )
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities,
            "serverInfo": server_info.model_dump()
        }
        
    except Exception as e:
        logging.error(f"Error initializing MCP server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize MCP server: {str(e)}"
        )

@router.get("/resources/list")
async def list_resources(
    user: str = Depends(get_current_user_email)
) -> MCPListResourcesResponse:
    """
    List available MCP resources.
    
    Returns a list of resources that can be accessed through this MCP server.
    Currently returns an empty list as resources are not yet implemented.
    """
    try:
        logging.info(f"Listing MCP resources for user: {user}")
        
        # Return empty list for now
        resources = []
        
        return MCPListResourcesResponse(resources=resources)
        
    except Exception as e:
        logging.error(f"Error listing MCP resources: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list resources: {str(e)}"
        )

@router.get("/tools/list")
async def list_tools(
    user: str = Depends(get_current_user_email)
) -> MCPListToolsResponse:
    """
    List available MCP tools.
    
    Returns a list of tools that can be called through this MCP server.
    Currently returns an empty list as tools are not yet implemented.
    """
    try:
        logging.info(f"Listing MCP tools for user: {user}")
        
        # Return empty list for now
        tools = []
        
        return MCPListToolsResponse(tools=tools)
        
    except Exception as e:
        logging.error(f"Error listing MCP tools: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}"
        )

@router.get("/prompts/list")
async def list_mcp_prompts(
    user_email: str = Depends(get_current_user_email)
):
    """
    List available MCP prompts.
    
    Returns LAMB assistants owned by the current user as MCP prompts.
    """
    try:
        logging.info(f"Listing MCP prompts for user: {user_email}")
        
        # Get assistants owned by the current user
        assistants = db_manager.get_list_of_assistants(owner=user_email)
        
        if not assistants:
            return {"prompts": []}
        
        # Convert assistants to MCP prompts
        prompts = []
        for assistant in assistants:
            prompt = MCPPrompt(
                name=f"assistant_{assistant['id']}",
                description=assistant.get('description', f"LAMB Assistant: {assistant.get('name', 'Unnamed')}"),
                arguments=[
                    {
                        "name": "user_input",
                        "description": "The user's input or question",
                        "required": True
                    }
                ]
            )
            prompts.append(prompt.model_dump())
        
        return {"prompts": prompts}
    except Exception as e:
        logging.error(f"Error listing MCP prompts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}"
        )

@router.post("/tools/call/{tool_name}")
async def call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    user: str = Depends(get_current_user_email)
):
    """
    Call an MCP tool.
    
    Executes the specified tool with the provided arguments.
    """
    try:
        logging.info(f"Calling MCP tool '{tool_name}' for user: {user}")
        logging.debug(f"Tool arguments: {arguments}")
        
        if tool_name == "create_assistant":
            # Create a new assistant
            assistant_data = {
                "name": arguments.get("name"),
                "description": arguments.get("description"),
                "owner": user,  # Use the authenticated user as owner
                "api_callback": arguments.get("metadata", arguments.get("api_callback", json.dumps({
                    "prompt_processor": "simple_augment",  # Use default processor
                    "connector": "openai",
                    "llm": "gpt-4",
                    "rag_processor": ""
                }))),
                "system_prompt": arguments.get("system_prompt", ""),
                "prompt_template": arguments.get("prompt_template", ""),
                "pre_retrieval_endpoint": "",
                "post_retrieval_endpoint": "",
                "RAG_endpoint": "",
                "RAG_Top_k": 5,
                "RAG_collections": ""
            }
            
            assistant_id = db_manager.add_assistant(assistant_data)
            
            result = {
                "success": True,
                "message": f"Assistant '{arguments.get('name')}' created successfully",
                "assistant_id": assistant_id
            }
            
        elif tool_name == "query_assistant":
            # Query an assistant for MCP - return the crafted prompt
            assistant_id = arguments.get("assistant_id")
            query = arguments.get("query")
            include_rag = arguments.get("include_rag", True)
            
            # Get assistant details
            assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
            if not assistant_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assistant {assistant_id} not found"
                )
            
            # Parse the metadata JSON (stored in api_callback column for backward compatibility)
            try:
                if assistant_data.get('api_callback'):
                    plugin_config = json.loads(assistant_data['api_callback'])
                else:
                    plugin_config = {"rag_processor": "no_rag"}
            except json.JSONDecodeError:
                plugin_config = {"rag_processor": "no_rag"}
            
            # Create request format
            request = {
                "messages": [
                    {"role": "user", "content": query}
                ]
            }
            
            # Get RAG context if requested
            rag_context = None
            if include_rag and plugin_config.get("rag_processor") and plugin_config["rag_processor"] != "no_rag":
                try:
                    # Load only RAG processors
                    _, _, rag_processors = load_and_validate_plugins(plugin_config)
                    
                    # Convert dictionary to Assistant object for get_rag_context compatibility
                    assistant_obj = Assistant(
                        id=assistant_data['id'],
                        name=assistant_data['name'],
                        description=assistant_data.get('description', ''),
                        owner=assistant_data['owner'],
                        api_callback=assistant_data.get('api_callback', ''),
                        system_prompt=assistant_data.get('system_prompt', ''),
                        prompt_template=assistant_data.get('prompt_template', ''),
                        RAG_endpoint=assistant_data.get('RAG_endpoint', ''),
                        RAG_Top_k=assistant_data.get('RAG_Top_k', 5),
                        RAG_collections=assistant_data.get('RAG_collections', ''),
                        pre_retrieval_endpoint=assistant_data.get('pre_retrieval_endpoint', ''),
                        post_retrieval_endpoint=assistant_data.get('post_retrieval_endpoint', '')
                    )
                    
                    rag_context = get_rag_context(
                        request, 
                        rag_processors, 
                        plugin_config["rag_processor"], 
                        assistant_obj
                    )
                except Exception as e:
                    logging.warning(f"Failed to get RAG context: {str(e)}")
            
            # Convert dictionary to Assistant object for build_mcp_prompt compatibility
            assistant = Assistant(
                id=assistant_data['id'],
                name=assistant_data['name'],
                description=assistant_data.get('description', ''),
                owner=assistant_data['owner'],
                api_callback=assistant_data.get('api_callback', ''),
                system_prompt=assistant_data.get('system_prompt', ''),
                prompt_template=assistant_data.get('prompt_template', ''),
                RAG_endpoint=assistant_data.get('RAG_endpoint', ''),
                RAG_Top_k=assistant_data.get('RAG_Top_k', 5),
                RAG_collections=assistant_data.get('RAG_collections', ''),
                pre_retrieval_endpoint=assistant_data.get('pre_retrieval_endpoint', ''),
                post_retrieval_endpoint=assistant_data.get('post_retrieval_endpoint', '')
            )
            
            # Build prompt using MCP-specific function
            result = build_mcp_prompt(
                messages=request["messages"],
                assistant=assistant, 
                rag_context=rag_context
            )
            
        elif tool_name == "update_assistant":
            # Update an existing assistant
            assistant_id = arguments.get("assistant_id")
            
            # Get current assistant data as dictionary from database
            current_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
            if not current_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assistant {assistant_id} not found"
                )
            
            # Update only provided fields
            update_data = {
                "id": assistant_id,
                "name": arguments.get("name", current_data['name']),
                "description": arguments.get("description", current_data.get('description', '')),
                "owner": current_data['owner'],
                "api_callback": current_data.get('api_callback', ''),
                "system_prompt": arguments.get("system_prompt", current_data.get('system_prompt', '')),
                "prompt_template": arguments.get("prompt_template", current_data.get('prompt_template', '')),
                "pre_retrieval_endpoint": current_data.get('pre_retrieval_endpoint', ''),
                "post_retrieval_endpoint": current_data.get('post_retrieval_endpoint', ''),
                "RAG_endpoint": current_data.get('RAG_endpoint', ''),
                "RAG_Top_k": current_data.get('RAG_Top_k', 5),
                "RAG_collections": current_data.get('RAG_collections', '')
            }
            
            # Convert to Assistant object for the update method
            assistant_obj = Assistant(
                id=update_data['id'],
                name=update_data['name'],
                description=update_data['description'],
                owner=update_data['owner'],
                api_callback=update_data['api_callback'],
                system_prompt=update_data['system_prompt'],
                prompt_template=update_data['prompt_template'],
                RAG_endpoint=update_data['RAG_endpoint'],
                RAG_Top_k=update_data['RAG_Top_k'],
                RAG_collections=update_data['RAG_collections'],
                pre_retrieval_endpoint=update_data['pre_retrieval_endpoint'],
                post_retrieval_endpoint=update_data['post_retrieval_endpoint']
            )
            
            db_manager.update_assistant(assistant_id, assistant_obj)
            
            result = {
                "success": True,
                "message": f"Assistant {assistant_id} updated successfully",
                "assistant_id": assistant_id
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error calling MCP tool '{tool_name}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call tool: {str(e)}"
        )

@router.post("/prompts/get/{prompt_name}")
async def get_mcp_prompt(
    prompt_name: str,
    arguments: Dict[str, Any],
    user: str = Depends(get_current_user_email)
):
    """
    Get a specific MCP prompt with arguments filled in.
    
    This returns the fully crafted prompt with RAG context instead of executing it.
    """
    try:
        logging.info(f"Getting MCP prompt '{prompt_name}' for user: {user}")
        
        # Extract assistant ID from prompt name (format: assistant_123)
        if not prompt_name.startswith("assistant_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid prompt name format"
            )
        
        assistant_id = int(prompt_name.split("_")[1])
        
        # Get assistant details
        assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
        if not assistant_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assistant {assistant_id} not found"
            )
        
        # Get user input from arguments
        user_input = arguments.get("user_input", "")
        if not user_input:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_input is required"
            )
        
        # Build the prompt using our utility function
        messages = [{"role": "user", "content": user_input}]
        
        # Get RAG context if configured
        rag_context = None
        
        # Parse the metadata JSON (stored in api_callback column for backward compatibility)
        try:
            if assistant_data.get('api_callback'):
                plugin_config = json.loads(assistant_data['api_callback'])
            else:
                plugin_config = {"rag_processor": "no_rag"}
        except json.JSONDecodeError:
            plugin_config = {"rag_processor": "no_rag"}
        
        # Only process RAG if there's a valid RAG processor configured
        if plugin_config.get('rag_processor') and plugin_config['rag_processor'] != 'no_rag':
            try:
                # Load and validate plugins to get rag_processors
                _, _, rag_processors = load_and_validate_plugins(plugin_config)
                
                # Create request format that matches what get_rag_context expects
                request_dict = {"messages": messages}
                
                # Convert dictionary to Assistant object for get_rag_context compatibility
                assistant_obj = Assistant(
                    id=assistant_data['id'],
                    name=assistant_data['name'],
                    description=assistant_data.get('description', ''),
                    owner=assistant_data['owner'],
                    api_callback=assistant_data.get('api_callback', ''),
                    system_prompt=assistant_data.get('system_prompt', ''),
                    prompt_template=assistant_data.get('prompt_template', ''),
                    RAG_endpoint=assistant_data.get('RAG_endpoint', ''),
                    RAG_Top_k=assistant_data.get('RAG_Top_k', 5),
                    RAG_collections=assistant_data.get('RAG_collections', ''),
                    pre_retrieval_endpoint=assistant_data.get('pre_retrieval_endpoint', ''),
                    post_retrieval_endpoint=assistant_data.get('post_retrieval_endpoint', '')
                )
                
                # Get RAG context using the correct function signature
                rag_context = get_rag_context(
                    request=request_dict,
                    rag_processors=rag_processors,
                    rag_processor=plugin_config["rag_processor"],
                    assistant_details=assistant_obj
                )
            except Exception as e:
                logging.warning(f"Failed to get RAG context: {str(e)}")
        
        # Convert dictionary to Assistant object for build_mcp_prompt compatibility
        assistant = Assistant(
            id=assistant_data['id'],
            name=assistant_data['name'],
            description=assistant_data.get('description', ''),
            owner=assistant_data['owner'],
            api_callback=assistant_data.get('api_callback', ''),
            system_prompt=assistant_data.get('system_prompt', ''),
            prompt_template=assistant_data.get('prompt_template', ''),
            RAG_endpoint=assistant_data.get('RAG_endpoint', ''),
            RAG_Top_k=assistant_data.get('RAG_Top_k', 5),
            RAG_collections=assistant_data.get('RAG_collections', ''),
            pre_retrieval_endpoint=assistant_data.get('pre_retrieval_endpoint', ''),
            post_retrieval_endpoint=assistant_data.get('post_retrieval_endpoint', '')
        )
        
        # Build the MCP prompt
        result = build_mcp_prompt(messages, assistant, rag_context)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting MCP prompt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt: {str(e)}"
        )

@router.get("/resources/read")
async def read_resource(
    uri: str,
    user: str = Depends(get_current_user_email)
):
    """
    Read an MCP resource.
    
    Returns the content of the specified resource.
    """
    try:
        logging.info(f"Reading MCP resource '{uri}' for user: {user}")
        
        if uri == "lamb://assistants":
            # Get assistants owned by the current user
            assistants = db_manager.get_list_of_assistants(owner=user)
            content = {
                "assistants": [
                    {
                        "id": assistant['id'],
                        "name": assistant['name'],
                        "description": assistant.get('description', ''),
                        "owner": assistant['owner'],
                        "system_prompt": assistant.get('system_prompt', ''),
                        "prompt_template": assistant.get('prompt_template', ''),
                        "has_rag": bool(assistant.get('RAG_endpoint') or assistant.get('RAG_collections'))
                    }
                    for assistant in assistants
                ]
            }
            
        elif uri.startswith("lamb://assistant/"):
            # Get specific assistant
            assistant_id = int(uri.split("/")[-1])
            assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
            
            if not assistant_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assistant {assistant_id} not found"
                )
            
            # Parse the metadata JSON (stored in api_callback column for backward compatibility)
            try:
                if assistant_data.get('api_callback'):
                    plugin_config = json.loads(assistant_data['api_callback'])
                else:
                    plugin_config = {"rag_processor": "no_rag"}
            except json.JSONDecodeError:
                plugin_config = {"rag_processor": "no_rag"}
            
            content = {
                "id": assistant_data['id'],
                "name": assistant_data['name'],
                "description": assistant_data.get('description', ''),
                "owner": assistant_data['owner'],
                "system_prompt": assistant_data.get('system_prompt', ''),
                "prompt_template": assistant_data.get('prompt_template', ''),
                "plugin_config": plugin_config,
                "rag_config": {
                    "endpoint": assistant_data.get('RAG_endpoint', ''),
                    "top_k": assistant_data.get('RAG_Top_k', 5),
                    "collections": assistant_data.get('RAG_collections', '')
                }
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resource '{uri}' not found"
            )
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(content, indent=2)
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error reading MCP resource '{uri}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read resource: {str(e)}"
        )

@router.get("/status")
async def get_mcp_status(
    user: str = Depends(get_current_user_email)
):
    """
    Get MCP server status.
    
    Returns the current status and capabilities of the MCP server.
    """
    try:
        logging.info(f"Getting MCP status for user: {user}")
        
        # Get counts for status
        assistants = db_manager.get_full_list_of_assistants()
        
        # Get available plugins
        pps = load_plugins('pps')
        connectors = load_plugins('connectors') 
        rag_processors = load_plugins('rag')
        
        return {
            "status": "active",
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "LAMB-MCP-Server",
                "version": "0.1.0"
            },
            "capabilities": {
                "prompts": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "tools": {"listChanged": True},
                "logging": {}
            },
            "statistics": {
                "total_assistants": len(assistants) if assistants else 0,
                "available_pps": len(pps),
                "available_connectors": len(connectors),
                "available_rag": len(rag_processors),
                "mcp_integration": "active"
            }
        }
    except Exception as e:
        logging.error(f"Error getting MCP status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        ) 