from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Depends, BackgroundTasks, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import os
import uuid
import datetime
from dotenv import load_dotenv
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.database_manager import LambDatabaseManager
from typing import Optional, List, Dict, Any, Union
import logging
import json
import time
from pydantic import BaseModel, Field
from .assistant_router import get_creator_user_from_token
from io import BytesIO
from .knowledgebase_classes import (
    KnowledgeBaseMetadata, KnowledgeBaseCreate, KnowledgeBaseUpdate,
    KnowledgeBaseQuery, KnowledgeBaseFile, KnowledgeBaseResponse,
    KnowledgeBaseListResponse
)
from .kb_server_manager import KBServerManager

# --- Pydantic Models for Knowledges Router --- #

class KnowledgeBaseServerOfflineResponse(BaseModel):
    status: str = "error"
    message: str = "Knowledge Base server offline"
    kb_server_available: bool = False

class KnowledgeBaseCreateResponse(BaseModel):
    # Assuming the response from kb_server_manager.create_knowledge_base
    # Adjust fields based on actual implementation
    kb_id: str
    name: str
    status: str = "success"
    message: str = "Knowledge base created successfully"

class KnowledgeBaseDetailsResponse(BaseModel):
    # Response from kb_server_manager.get_knowledge_base_details enhanced with LAMB metadata
    id: str
    name: str
    description: Optional[str]
    files: Optional[List[Dict]] = [] # Or use a more specific File model if defined
    # LAMB-specific metadata fields
    is_owner: Optional[bool] = None
    can_modify: Optional[bool] = None
    is_shared: Optional[bool] = None
    shared_by: Optional[str] = None

class KnowledgeBaseUpdateResponse(BaseModel):
    # Assuming the response from kb_server_manager.update_knowledge_base
    kb_id: str
    status: str = "success"
    message: str = "Knowledge base updated successfully"

class KnowledgeBaseDeleteResponse(BaseModel):
    # Assuming the response from kb_server_manager.delete_knowledge_base
    kb_id: str
    status: str = "success"
    message: str = "Knowledge base deleted successfully"
    deleted_embeddings: Optional[int] = None
    removed_files: Optional[List[Any]] = None
    collection_name: Optional[str] = None

# Define the structure for a single query result item
class QueryResultItem(BaseModel):
    similarity: Optional[float] = None
    data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class KnowledgeBaseQueryResponse(BaseModel):
    # Assuming the response from kb_server_manager.query_knowledge_base
    # Define based on the actual structure returned by the KB server query
    results: List[QueryResultItem] # Use the specific item model
    status: str = "success"
    # Add other fields if the manager returns them (like kb_id, query, debug_info)
    kb_id: Optional[str] = None
    query: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None

class FileUploadItemResponse(BaseModel):
    filename: str
    status: str # e.g., "success", "error"
    message: Optional[str] = None
    file_id: Optional[str] = None

class FileUploadKBResponse(BaseModel):
    # Assuming response from kb_server_manager.upload_files_to_kb
    uploaded_files: List[FileUploadItemResponse]
    status: str = "success"

class DeleteFileKBResponse(BaseModel):
    # Assuming response from kb_server_manager.delete_file_from_kb
    kb_id: str
    file_id: str
    status: str = "success"
    message: str = "File deleted successfully"

class IngestionPluginParam(BaseModel):
    name: str
    type: str
    required: bool
    default: Optional[Any] = None
    description: Optional[str] = None

# --- Updated Pydantic Models for Ingestion Plugins ---

# Define the inner structure for a parameter description based on logged data
class IngestionParameterDetail(BaseModel):
    type: str
    description: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False
    enum: Optional[List[str]] = None # Seen in logged data for 'chunk_unit'

# Update IngestionPlugin to use the correct key 'parameters' and its Dict structure
class IngestionPlugin(BaseModel):
    name: str
    description: str
    kind: str
    supported_file_types: Optional[List[str]] = [] # Add field based on logged data
    parameters: Dict[str, IngestionParameterDetail] = {} # Use correct key and type

class GetIngestionPluginsResponse(BaseModel):
    plugins: List[IngestionPlugin] # Relies on the updated IngestionPlugin model

# --- End Updated Ingestion Plugin Models ---

class PluginIngestFileResponse(BaseModel):
    # Assuming response from kb_server_manager.plugin_ingest_file
    status: str

class KBShareToggle(BaseModel):
    """Request model for toggling KB sharing"""
    is_shared: bool = Field(..., description="New sharing status")

class KBShareToggleResponse(BaseModel):
    """Response model for KB sharing toggle"""
    kb_id: str
    is_shared: bool
    message: str

class BasePluginIngestRequest(BaseModel):
    """Request body for plugin base ingestion (no direct file upload from client).

    The frontend sends JSON with the plugin name and arbitrary parameters.
    We create a synthetic in-memory file so we can re-use the existing file
    ingestion pipeline (KB server currently only exposes ingest-file).
    """
    plugin_name: str = Field(..., description="Name of the ingestion plugin to run")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Plugin parameters")

class ErrorResponseDetail(BaseModel):
    detail: Union[str, Dict[str, Any]]

# --- End Pydantic Models --- #

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set specific loggers to a higher level to reduce verbosity
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Get environment variables
LAMB_HOST = os.getenv('LAMB_HOST', 'http://localhost:9099')
# Note: LAMB_BEARER_TOKEN is configured in config.py
LAMB_KB_SERVER = os.getenv('LAMB_KB_SERVER', None)
LAMB_KB_SERVER_TOKEN = os.getenv('LAMB_KB_SERVER_TOKEN', '0p3n-w3bu!')

# Check if KB server is configured
KB_SERVER_CONFIGURED = LAMB_KB_SERVER is not None and LAMB_KB_SERVER.strip() != ''

router = APIRouter()
security = HTTPBearer()

owi_user_manager = OwiUserManager()
db_manager = LambDatabaseManager()
kb_server_manager = KBServerManager()


# Helper function to authenticate creator user
async def authenticate_creator_user(request: Request) -> Dict[str, Any]:
    """
    Helper function to authenticate creator user from request
    
    Args:
        request: FastAPI request object
    
    Returns:
        Dict with creator user information
    
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    logger.info(f"Auth header present: {auth_header is not None}")
    
    try:
        creator_user = get_creator_user_from_token(auth_header)
        logger.info(f"Creator user authentication result: {creator_user is not None}")
    except Exception as auth_err:
        logger.error(f"Exception during authentication: {str(auth_err)}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication error: {str(auth_err)}"
        )
        
    if not creator_user:
        logger.error("Failed to get creator user from token")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication or user not found in creator database"
        )
    
    logger.info(f"Creator user authenticated: {creator_user.get('email')}")
    return creator_user


@router.get(
    "/user",
    response_model=Union[KnowledgeBaseListResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Get User's Owned Knowledge Bases",
    description="""Get all knowledge bases owned by the authenticated user.
    Includes auto-registration of missing KBs and lazy cleanup of stale entries.
    Returns only KBs owned by the user (not shared ones).
    
    If the KB server is unavailable, returns a status message instead of throwing an error.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/knowledgebases/user' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "knowledge_bases": [
    {
      "id": "kb_uuid_1",
      "name": "My KB",
      "description": "My knowledge base",
      "is_owner": true,
      "is_shared": false,
      "can_modify": true
    }
  ]
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Knowledge bases retrieved successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X GET 'http://localhost:8000/creator/knowledgebases/user' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def get_user_knowledge_bases(request: Request):
    """
    Get user's OWNED knowledge bases only.
    If the KB server is unavailable, returns a status message instead of throwing an error.
    """
    logger.info("Retrieving user's owned knowledge bases from KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        
        # Get owned knowledge bases from the KB server
        knowledge_bases = await kb_server_manager.get_user_knowledge_bases(creator_user)
        
        # Return knowledge bases to the client
        logger.info(f"Returning {len(knowledge_bases)} owned knowledge bases to client")
        return {"knowledge_bases": knowledge_bases}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error retrieving user's knowledge bases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/shared",
    response_model=Union[KnowledgeBaseListResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Get Organization Shared Knowledge Bases",
    description="""Get all knowledge bases shared in the user's organization (excluding user's own).
    Includes lazy cleanup of stale entries.
    Returns only KBs shared by other users in the organization.
    
    If the KB server is unavailable, returns a status message instead of throwing an error.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/knowledgebases/shared' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "knowledge_bases": [
    {
      "id": "kb_uuid_2",
      "name": "Shared KB",
      "description": "Shared knowledge base",
      "is_owner": false,
      "is_shared": true,
      "can_modify": false,
      "shared_by": "John Doe"
    }
  ]
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Shared knowledge bases retrieved successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X GET 'http://localhost:8000/creator/knowledgebases/shared' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def get_shared_knowledge_bases(request: Request):
    """
    Get organization shared knowledge bases (excluding user's own).
    If the KB server is unavailable, returns a status message instead of throwing an error.
    """
    logger.info("Retrieving shared knowledge bases from KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        
        # Get shared knowledge bases from the KB server
        knowledge_bases = await kb_server_manager.get_org_shared_knowledge_bases(creator_user)
        
        # Return knowledge bases to the client
        logger.info(f"Returning {len(knowledge_bases)} shared knowledge bases to client")
        return {"knowledge_bases": knowledge_bases}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error retrieving shared knowledge bases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "",
    response_model=Union[KnowledgeBaseCreateResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Create Knowledge Base",
    description="""Create a new knowledge base by connecting to the configured KB server.
    Requires KB server to be available.

Example Request Body:
```json
{
  "name": "New Research KB",
  "description": "Knowledge base for ongoing research project.",
  "access_control": "private"
}
```

Example Success Response:
```json
{
  "kb_id": "kb_uuid_new",
  "name": "New Research KB",
  "status": "success",
  "message": "Knowledge base created successfully"
}
```
Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response (KB Server Failure):
```json
{
  "detail": "Failed to create knowledge base on KB server: {'detail': 'Collection name already exists'}"
}
```
    """,
    dependencies=[Depends(security)],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": KnowledgeBaseCreate.schema()
                }
            }
        },
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X POST 'http://localhost:8000/creator/knowledgebases' \\
-H 'Authorization: Bearer <user_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "name": "New Research KB",
  "description": "Knowledge base for ongoing research project.",
  "access_control": "private"
}'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    request: Request
):
    """
    Create a new knowledge base by connecting to the KB server
    """
    logger.info("Creating knowledge base via KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        
        # Create the knowledge base using the KB server manager
        result = await kb_server_manager.create_knowledge_base(
            kb_data=kb_data,
            creator_user=creator_user
        )
        logger.info(f"Knowledge base creation result: {result}")
        
        # Check if the result message indicates success regardless of status field
        if result and isinstance(result, dict):
            if "message" in result and "Knowledge base created successfully" in result.get("message", ""):
                # Fix the response to match KnowledgeBaseCreateResponse model
                # Ensure kb_id and name are included
                return {
                    "kb_id": result.get("kb_id", ""),
                    "name": result.get("name", kb_data.name),
                    "status": "success",
                    "message": result.get("message", "Knowledge base created successfully")
                }
        
        # Return original result if no fixing needed
        return result
                
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating knowledge base: {str(e)}"
        )


@router.get(
    "/kb/{kb_id}",
    response_model=Union[KnowledgeBaseDetailsResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Get Knowledge Base Details",
    description="""Get details of a specific knowledge base, including its files, by connecting to the KB server.
    Requires KB server to be available.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "id": "kb_uuid_1",
  "name": "CS101 Readings",
  "description": "Required readings for the course.",
  "files": [
    {
       "id": "file_abc",
       "filename": "chapter1.pdf"
       # ... other file details from KB server ...
    }
  ]
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response (Not Found):
```json
{
  "detail": "Knowledge base kb_uuid_nonexistent not found on KB server"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Successfully retrieved knowledge base details or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X GET 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def get_knowledge_base(kb_id: str, request: Request):
    """
    Get details of a specific knowledge base by connecting to the KB server.
    If the KB server is unavailable, returns a status message instead of throwing an error.
    """
    logger.info(f"Getting knowledge base details for ID: {kb_id} from KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access (owner OR shared can view)
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(
                status_code=404, 
                detail="Knowledge base not found or not accessible"
            )
        
        logger.info(f"User {creator_user['id']} accessing KB {kb_id} with access type: {access_type}")

        # Get knowledge base details from KB server
        # Pass access_type to skip ownership check for shared KBs
        result = await kb_server_manager.get_knowledge_base_details(kb_id, creator_user, access_type=access_type)
        
        # Enhance with LAMB metadata
        if isinstance(result, dict):
            entry = db_manager.get_kb_registry_entry(kb_id)
            # Always set can_modify based on access_type, regardless of entry existence
            result['is_owner'] = (access_type == 'owner')
            result['can_modify'] = (access_type == 'owner')
            if entry:
                result['is_shared'] = entry.get('is_shared', False)
                if access_type == 'shared':
                    result['shared_by'] = entry.get('owner_name') or entry.get('owner_email', 'Unknown')
            else:
                # If no entry, assume not shared
                result['is_shared'] = False
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting knowledge base details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.patch(
    "/kb/{kb_id}",
    response_model=Union[KnowledgeBaseUpdateResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Update Knowledge Base",
    description="""Update properties of a knowledge base (name, description, etc.) by connecting to the KB server.
    Requires KB server to be available.

Example Request Body:
```json
{
  "description": "Updated description for the research project KB.",
  "access_control": "public"
}
```

Example Success Response:
```json
{
  "kb_id": "kb_uuid_new",
  "status": "success",
  "message": "Knowledge base updated successfully"
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response:
```json
{
  "detail": "Failed to update knowledge base on KB server: {'detail': 'Update error...'}"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Knowledge base updated successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": KnowledgeBaseUpdate.schema()
                }
            }
        },
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X PATCH 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_new' \\
-H 'Authorization: Bearer <user_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "description": "Updated description for the research project KB.",
  "access_control": "public"
}'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def update_knowledge_base(
    kb_id: str,
    kb_data: KnowledgeBaseUpdate,
    request: Request
):
    """
    Update a knowledge base by connecting to the KB server
    """
    logger.info(f"Updating knowledge base {kb_id} via KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access (owner only)
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can update KB settings"
            )
        
        # Update the knowledge base using the KB server manager
        result = await kb_server_manager.update_knowledge_base(
            kb_id=kb_id,
            kb_data=kb_data,
            creator_user=creator_user
        )
        
        # Update cached name in registry if changed
        if kb_data.name is not None and isinstance(result, dict):
            db_manager.update_kb_registry_name(kb_id, kb_data.name)
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating knowledge base: {str(e)}"
        )


@router.put(
    "/kb/{kb_id}/share",
    response_model=KBShareToggleResponse,
    tags=["Knowledge Base Management"],
    summary="Toggle KB Sharing",
    description="""Toggle knowledge base sharing within organization.
    Only the KB owner can change sharing settings.
    
    Example Request:
```bash
    curl -X PUT 'http://localhost:9099/creator/knowledgebases/kb/kb_uuid_1/share' \\
    -H 'Authorization: Bearer <user_token>' \\
    -H 'Content-Type: application/json' \\
    -d '{"is_shared": true}'
```
    """,
    dependencies=[Depends(security)]
)
async def toggle_kb_sharing(
    kb_id: str,
    share_data: KBShareToggle,
    request: Request
):
    """
    Toggle KB sharing status (exactly like prompt templates).
    Only owner can change sharing settings.
    """
    logger.info(f"Toggling KB {kb_id} sharing to {share_data.is_shared}")
    
    try:
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Get registry entry
        entry = db_manager.get_kb_registry_entry(kb_id)
        if not entry:
            raise HTTPException(
                status_code=404, 
                detail="Knowledge base not found"
            )
        
        # Verify ownership
        if entry['owner_user_id'] != creator_user['id']:
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can change sharing settings"
            )
        
        # Check if sharing is enabled for the user's organization (only when sharing, not unsharing)
        if share_data.is_shared:
            org = db_manager.get_user_organization(creator_user['id'])
            if org:
                config = org.get('config', {})
                features = config.get('features', {})
                sharing_enabled = features.get('sharing_enabled', True)
                
                if not sharing_enabled:
                    raise HTTPException(
                        status_code=403,
                        detail="Sharing is not enabled for your organization"
                    )
        
        # If trying to unshare, check if KB is used by other users' assistants
        if not share_data.is_shared:
            using_assistants = db_manager.check_kb_used_by_other_users(kb_id, creator_user['id'])
            if using_assistants:
                # Build list of assistant names for error message
                assistant_names = [f"{a['name']} (by {a['owner_name']})" for a in using_assistants]
                assistant_list = ", ".join(assistant_names[:3])  # Show first 3
                if len(using_assistants) > 3:
                    assistant_list += f" and {len(using_assistants) - 3} more"
                
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot unshare KB: It is currently used by {len(using_assistants)} assistant(s): {assistant_list}. Please ask users to remove this KB from their assistants first."
                )
        
        # Toggle sharing
        success = db_manager.toggle_kb_sharing(kb_id, share_data.is_shared)
        
        if not success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to update sharing status"
            )
        
        return {
            "kb_id": kb_id,
            "is_shared": share_data.is_shared,
            "message": f"KB is now {'shared with organization' if share_data.is_shared else 'private'}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling KB sharing: {e}")
        raise HTTPException(status_code=500, detail=f"Error toggling sharing: {str(e)}")


@router.delete(
    "/kb/{kb_id}",
    response_model=Union[KnowledgeBaseDeleteResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Delete Knowledge Base",
    description="""Delete a knowledge base and its associated data by connecting to the KB server.
    Requires KB server to be available.

Example Request:
```bash
curl -X DELETE 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_new' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "kb_id": "kb_uuid_new",
  "status": "success",
  "message": "Knowledge base deleted successfully"
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response (Not Found):
```json
{
  "detail": "Knowledge base kb_uuid_nonexistent not found on KB server"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Knowledge base deleted successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X DELETE 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_new' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def delete_knowledge_base(kb_id: str, request: Request):
    """
    Delete a knowledge base by connecting to the KB server
    """
    logger.info(f"Deleting knowledge base {kb_id} via KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access (owner only)
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can delete KB"
            )
        
        # Delete the knowledge base using the KB server manager
        result = await kb_server_manager.delete_knowledge_base(
            kb_id=kb_id,
            creator_user=creator_user
        )
        
        # Delete from registry
        db_manager.delete_kb_registry_entry(kb_id)
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting knowledge base: {str(e)}"
        )


@router.post(
    "/kb/{kb_id}/query",
    response_model=Union[KnowledgeBaseQueryResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Query Knowledge Base",
    description="""Query a specific knowledge base using the configured KB server.
    Requires KB server to be available.

Example Request Body:
```json
{
  "query_text": "What were the main findings?",
  "plugin_name": "simple_query",
  "plugin_params": {
    "top_k": 5,
    "threshold": 0.6
  }
}
```

Example Success Response:
```json
{
  "results": [
    {
      "document_id": "doc1",
      "text": "The main finding was...",
      "score": 0.85
    },
    {
      "document_id": "doc2",
      "text": "Further analysis showed...",
      "score": 0.72
    }
  ],
  "status": "success"
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response:
```json
{
  "detail": "Error querying KB server: {'detail': 'Invalid plugin parameters'}"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Query executed successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": KnowledgeBaseQuery.schema()
                }
            }
        },
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X POST 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/query' \\
-H 'Authorization: Bearer <user_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "query_text": "What were the main findings?",
  "plugin_name": "simple_query",
  "plugin_params": {
    "top_k": 5,
    "threshold": 0.6
  }
}'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def query_knowledge_base(
    kb_id: str,
    query_data: KnowledgeBaseQuery,
    request: Request
):
    """
    Query a knowledge base by connecting to the KB server
    """
    logger.info(f"Querying knowledge base {kb_id} via KB server with: {query_data.query_text}")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access (owner OR shared can query)
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(
                status_code=404, 
                detail="KB not found or not accessible"
            )
        
        logger.info(f"User {creator_user['id']} querying KB {kb_id} with access type: {access_type}")
        
        # Both owner and shared users can query
        # Pass access_type to skip ownership check for shared KBs
        result = await kb_server_manager.query_knowledge_base(
            kb_id=kb_id,
            query_data=query_data.dict(),
            creator_user=creator_user,
            access_type=access_type
        )
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error querying knowledge base: {str(e)}"
        )


@router.post(
    "/kb/{kb_id}/files",
    response_model=Union[FileUploadKBResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Upload Files To Knowledge Base",
    description="""Upload one or more files to a specific knowledge base via the KB server.
    Requires multipart/form-data with one or more 'files' parts.
    Requires KB server to be available.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/files' \\
-H 'Authorization: Bearer <user_token>' \\
-F 'files=@/path/to/report.pdf' \\
-F 'files=@/path/to/data.csv'
```

Example Success Response:
```json
{
  "uploaded_files": [
    {
      "filename": "report.pdf",
      "status": "success",
      "message": "File uploaded and ingested.",
      "file_id": "file_xyz"
    },
    {
      "filename": "data.csv",
      "status": "success",
      "message": "File uploaded and ingested.",
      "file_id": "file_123"
    }
  ],
  "status": "success"
}
```
Example Response with Errors:
```json
{
  "uploaded_files": [
    {
      "filename": "report.pdf",
      "status": "success",
      "message": "File uploaded and ingested.",
      "file_id": "file_xyz"
    },
    {
      "filename": "unsupported.zip",
      "status": "error",
      "message": "Unsupported file type",
      "file_id": null
    }
  ],
  "status": "partial_success"
}
```
Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Files processed (check individual statuses) or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"}
                            }
                        },
                        "required": ["files"]
                    }
                }
            }
        },
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X POST 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/files' \\
-H 'Authorization: Bearer <user_token>' \\
-F 'files=@/path/to/report.pdf' \\
-F 'files=@/path/to/data.csv'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def upload_files_to_kb(
    request: Request,
    kb_id: str,
    files: List[UploadFile] = File(...)
):
    """
    Upload files to a knowledge base by connecting to the KB server
    """
    logger.info(f"Uploading files to knowledge base {kb_id} via KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        # Only owner can upload
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can upload files. You have read-only access to this shared KB."
            )
        
        # Upload files to the knowledge base using the KB server manager
        result = await kb_server_manager.upload_files_to_kb(
            kb_id=kb_id,
            files=files,
            creator_user=creator_user
        )
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error uploading files to knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files to knowledge base: {str(e)}"
        )


@router.delete(
    "/kb/{kb_id}/files/{file_id}",
    response_model=Union[DeleteFileKBResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "kb-server-connection"],
    summary="Delete File From Knowledge Base",
    description="""Delete a specific file from a knowledge base via the KB server.
    Requires KB server to be available.

Example Request:
```bash
curl -X DELETE 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/files/file_xyz' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "kb_id": "kb_uuid_1",
  "file_id": "file_xyz",
  "status": "success",
  "message": "File deleted successfully"
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response (Not Found):
```json
{
  "detail": "File file_nonexistent not found in knowledge base kb_uuid_1 on KB server"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "File deleted successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base or File not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X DELETE 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/files/file_xyz' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def delete_file_from_kb(kb_id: str, file_id: str, request: Request):
    """
    Delete a file from a knowledge base by connecting to the KB server
    """
    logger.info(f"Deleting file {file_id} from knowledge base {kb_id} via KB server")
    try:
        # Check if KB server is available
        kb_available = await kb_server_manager.is_kb_server_available()
        if not kb_available:
            logger.warning("Knowledge Base server is offline or not configured")
            return {
                "status": "error",
                "message": "Knowledge Base server offline",
                "kb_server_available": False
            }
            
        # Authenticate creator user
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        # Only owner can delete files
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can delete files. You have read-only access to this shared KB."
            )
        
        # Delete the file using the KB server manager
        result = await kb_server_manager.delete_file_from_kb(
            kb_id=kb_id,
            file_id=file_id,
            creator_user=creator_user
        )
        
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting file from knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting file from knowledge base: {str(e)}"
        )


@router.get(
    "/ingestion-plugins",
    response_model=Union[GetIngestionPluginsResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "Plugins", "kb-server-connection"],
    summary="Get Ingestion Plugins",
    description="""Get a list of available ingestion plugins and their parameters from the KB server.
    Requires KB server to be available.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/knowledgebases/ingestion-plugins' \\
-H 'Authorization: Bearer <user_token>' # May not be needed if KB server doesn't require auth for this
```

Example Success Response:
```json
{
  "plugins": [
    {
      "name": "markitdown_ingest",
      "description": "Ingest various file formats by converting to Markdown...",
      "kind": "file_ingestion",
      "supported_file_types": ["json", "xml", "pdf", ...],
      "parameters": {
        "chunk_size": {
          "type": "integer",
          "description": "Size of each chunk",
          "default": 1000,
          "required": false
        },
        "chunk_overlap": {
          "type": "integer",
          "description": "Number of units to overlap between chunks",
          "default": 200,
          "required": false
        }
        # ... other parameters ...
      }
    },
    {
      "name": "simple_ingest",
      "description": "Ingest text files...",
      "supported_file_types": ["md", "txt", ...],
      "parameters": {
        "chunk_size": {
          "type": "integer",
          "description": "Size of each chunk",
          "default": 1000,
          "required": false
        }
        # ... other parameters ...
      }
    }
    # ... other plugins ...
  ]
}
```
Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
    """,
    dependencies=[Depends(security)], # Added dependency for consistency, adjust if not needed
    responses={
        200: {"description": "Successfully retrieved ingestion plugins or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed (if required)"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X GET 'http://localhost:8000/creator/knowledgebases/ingestion-plugins' \\
-H 'Authorization: Bearer <user_token>' # Include if required by KB server
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def get_ingestion_plugins(request: Request):
    """
    Get a list of available ingestion plugins and their parameters
    """
    logger.info("Getting available ingestion plugins")
    
    try:
        # First check if KB server is available
        if not await kb_server_manager.is_kb_server_available():
            logger.error("KB server is not available")
            raise HTTPException(
                status_code=503,
                detail="KB server is not available"
            )
            
        # Get the plugins
        plugins = await kb_server_manager.get_ingestion_plugins()
        logger.info(f"KB-router: Plugins: {plugins}")
        # Return the plugins wrapped in a dictionary matching the response model
        return {"plugins": plugins}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ingestion plugins: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting ingestion plugins: {str(e)}"
        )

@router.post(
    "/kb/{kb_id}/plugin-ingest-file",
    response_model=Union[PluginIngestFileResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "Plugins", "kb-server-connection"],
    summary="Ingest File with Plugin",
    description="""Upload and ingest a file to a specific knowledge base using a named plugin and its parameters via the KB server.
    Requires multipart/form-data with 'file', 'plugin_name', and optionally plugin-specific parameters.
    Requires KB server to be available.

Example Request (using simple_file_processor):
```bash
curl -X POST 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/plugin-ingest-file' \\
  -H 'Authorization: Bearer <user_token>' \\
  -F 'plugin_name=simple_file_processor' \\
  -F 'file=@/path/to/document.pdf' \\
  -F 'chunk_size=1200' \\
  -F 'chunk_overlap=250'
```

Example Success Response:
```json
{
  "status": "success",
  "message": "File ingestion started successfully.",
  "task_id": "ingest_task_123" # Optional, if KB server returns a task ID
}
```

Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
Example Error Response (Invalid Plugin):
```json
{
  "detail": "Plugin 'invalid_plugin' not found on KB server"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "File ingestion started successfully or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base or Plugin not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "plugin_name": {"type": "string"},
                            "file": {"type": "string", "format": "binary"},
                            # Plugin parameters are dynamic, cannot be strictly defined here
                            # Indicate that other form fields are possible
                        },
                        "required": ["plugin_name", "file"]
                    }
                }
            }
        },
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X POST 'http://localhost:8000/creator/knowledgebases/kb/kb_uuid_1/plugin-ingest-file' \\
  -H 'Authorization: Bearer <user_token>' \\
  -F 'plugin_name=simple_file_processor' \\
  -F 'file=@/path/to/document.pdf' \\
  -F 'chunk_size=1200' \\
  -F 'chunk_overlap=250'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def plugin_ingest_file(
    kb_id: str,
    plugin_name: str = Form(...),
    file: UploadFile = File(...),
    request: Request = None,
):
    """
    Upload and ingest a file to a knowledge base using a specific plugin
    """
    logger.info(f"Ingesting file to knowledge base {kb_id} using plugin {plugin_name}")
    
    try:
        # First check if KB server is available
        if not await kb_server_manager.is_kb_server_available():
            logger.error("KB server is not available")
            raise HTTPException(
                status_code=503,
                detail="KB server is not available"
            )
            
        # Get creator user from the request
        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        # Only owner can ingest
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can ingest files. You have read-only access to this shared KB."
            )
        
        # Verify plugin name is not an index but a valid plugin name
        plugins = await kb_server_manager.get_ingestion_plugins()
        plugin_map = {}
        
        # Create a map of indices to plugin names
        if isinstance(plugins, list):
            for i, plugin in enumerate(plugins):
                plugin_map[str(i)] = plugin.get('name')
        elif isinstance(plugins, dict) and 'plugins' in plugins:
            for i, plugin in enumerate(plugins['plugins']):
                plugin_map[str(i)] = plugin.get('name')
        
        # If plugin_name is a number, try to convert it to the actual name
        if plugin_name.isdigit() and plugin_name in plugin_map:
            original_plugin_name = plugin_name
            plugin_name = plugin_map[plugin_name]
            logger.info(f"Converting plugin index {original_plugin_name} to actual plugin name: {plugin_name}")
        
        # Extract plugin parameters from form data
        form_data = await request.form()
        plugin_params = {}
        
        # Log the raw form data received
        logger.info(f"Raw form data received for plugin ingest: {form_data}")
        
        # Extract all form fields that aren't the file or plugin_name as potential plugin parameters
        for key, value in form_data.items():
            if key not in ["file", "plugin_name"]:
                # Try to parse numbers and booleans
                if value.isdigit():
                    plugin_params[key] = int(value)
                elif value.lower() in ["true", "false"]:
                    plugin_params[key] = value.lower() == "true"
                else:
                    plugin_params[key] = value
        
        # Log the extracted plugin parameters
        logger.info(f"Extracted plugin parameters: {plugin_params}")
        logger.info(f"Using actual plugin name: {plugin_name}")

        # Call the plugin ingest file method
        result = await kb_server_manager.plugin_ingest_file(
            kb_id=kb_id,
            file=file,
            plugin_name=plugin_name,
            plugin_params=plugin_params,
            creator_user=creator_user
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting file with plugin: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error ingesting file with plugin: {str(e)}"
        )


@router.post(
    "/kb/{kb_id}/plugin-ingest-base",
    response_model=Union[PluginIngestFileResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "Plugins", "kb-server-connection"],
    summary="Run base (no-file) ingestion plugin",
    description="""Run an ingestion plugin that does not require a user-uploaded file (e.g. remote resource ingestion).\n\nThis endpoint fabricates a tiny in-memory placeholder file so it can leverage the existing file-based ingestion path in the KB server (`/collections/{id}/ingest-file`). For plugins like `youtube_transcript_ingest` that can optionally read a local file of URLs, we embed the provided `video_url` (if any) as the file content so either code path works.\n\nExample Request:\n```bash\ncurl -X POST 'http://localhost:8000/creator/knowledgebases/kb/1/plugin-ingest-base' \\n  -H 'Authorization: Bearer <user_token>' \\n  -H 'Content-Type: application/json' \\n  -d '{\n    "plugin_name": "youtube_transcript_ingest",\n    "parameters": {"video_url": "https://www.youtube.com/watch?v=XXXX", "language": "es"}\n  }'\n```\n""",
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Base ingestion started successfully"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        404: {"model": ErrorResponseDetail, "description": "Knowledge Base or Plugin not found"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    }
)
async def plugin_ingest_base(
    kb_id: str,
    body: BasePluginIngestRequest,
    request: Request
):
    """Run an ingestion plugin without a direct file upload from the user.\n\nCreates an in-memory placeholder text file (optionally containing URL lines if helpful) and then reuses the existing `plugin_ingest_file` pipeline so we do not need to duplicate ownership / permission checks or low-level multipart handling logic in the KB server layer."""
    logger.info(f"Base ingestion requested for KB {kb_id} using plugin {body.plugin_name} with params: {body.parameters}")
    try:
        if not await kb_server_manager.is_kb_server_available():
            logger.error("KB server is not available for base ingestion")
            raise HTTPException(status_code=503, detail="KB server is not available")

        creator_user = await authenticate_creator_user(request)
        db_manager = LambDatabaseManager()
        
        # Check access
        can_access, access_type = db_manager.user_can_access_kb(kb_id, creator_user['id'])
        
        if not can_access:
            raise HTTPException(status_code=404, detail="KB not found")
        
        # Only owner can ingest
        if access_type != 'owner':
            raise HTTPException(
                status_code=403,
                detail="Only KB owner can ingest files. You have read-only access to this shared KB."
            )

        # Build placeholder file content (embed video_url if present so plugin can fallback to file parsing)
        content_bytes = b""
        if isinstance(body.parameters, dict):
            video_url = body.parameters.get("video_url")
            if video_url:
                try:
                    content_bytes = (str(video_url).strip() + "\n").encode("utf-8")
                except Exception:
                    content_bytes = b""

        # Create a minimal in-memory file object compatible with kb_server_manager expectations
        import io as _io

        class InMemoryUploadFile:
            def __init__(self, filename: str, data: bytes, content_type: str = "text/plain"):
                self.filename = filename
                self._data = data
                self.file = _io.BytesIO(data)
                self.content_type = content_type

            async def read(self):  # Matches UploadFile.read signature
                return self._data

        placeholder_file = InMemoryUploadFile(
            filename="base_ingest_placeholder.txt",
            data=content_bytes,
            content_type="text/plain"
        )

        result = await kb_server_manager.plugin_ingest_file(
            kb_id=kb_id,
            file=placeholder_file,
            plugin_name=body.plugin_name,
            plugin_params=body.parameters or {},
            creator_user=creator_user
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running base ingestion plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Error running base ingestion plugin: {e}")


# --- Query Plugins Endpoint ---

# Reuse the IngestionPlugin model for individual query plugins if structure matches
# Define the response model for the list of query plugins
class GetQueryPluginsResponse(BaseModel):
    plugins: List[IngestionPlugin]

@router.get(
    "/query-plugins",
    response_model=Union[GetQueryPluginsResponse, KnowledgeBaseServerOfflineResponse],
    tags=["Knowledge Base Management", "Plugins", "kb-server-connection"],
    summary="Get Query Plugins",
    description="""Get a list of available query plugins and their parameters from the KB server.
    Requires KB server to be available.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/knowledgebases/query-plugins' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "plugins": [
    {
      "name": "simple_query",
      "description": "Performs a simple vector search.",
      "parameters": {
        "top_k": {
          "type": "integer",
          "description": "Number of results to return.",
          "default": 5,
          "required": false
        },
        "threshold": {
          "type": "float",
          "description": "Similarity threshold.",
          "default": 0.7,
          "required": false
        }
        # ... other parameters ...
      }
    }
    # ... other plugins ...
  ]
}
```
Example Response (KB Server Offline):
```json
{
  "status": "error",
  "message": "Knowledge Base server offline",
  "kb_server_available": false
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Successfully retrieved query plugins or KB server status"},
        401: {"model": ErrorResponseDetail, "description": "Authentication failed"},
        500: {"model": ErrorResponseDetail, "description": "Internal server error or KB server communication failure"},
        503: {"model": KnowledgeBaseServerOfflineResponse, "description": "Knowledge Base server is offline or not configured"}
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "curl",
                "source": """
curl -X GET 'http://localhost:8000/creator/knowledgebases/query-plugins' \\
-H 'Authorization: Bearer <user_token>'
                """,
                "description": "Example cURL request"
            }
        ]
    }
)
async def get_query_plugins(request: Request):
    """
    Get a list of available query plugins and their parameters
    """
    logger.info("Getting available query plugins")

    try:
        # Check if KB server is available
        if not await kb_server_manager.is_kb_server_available():
            logger.warning("KB server is not available for query plugins")
            # Return the standard offline response object
            return KnowledgeBaseServerOfflineResponse()

        # Authenticate user (assuming it's needed for query plugins too)
        _ = await authenticate_creator_user(request) # We don't need the user info here, just auth

        # Get the plugins from the manager - this method needs to be added
        plugins = await kb_server_manager.get_query_plugins()
        logger.info(f"KB-router: Query Plugins received: {len(plugins) if isinstance(plugins, list) else 'Invalid format'}")

        # Return the plugins wrapped in a dictionary matching the response model
        if isinstance(plugins, list):
             return {"plugins": plugins}
        else:
            # Log error if the manager returned something unexpected
            logger.error(f"Unexpected response type from kb_server_manager.get_query_plugins: {type(plugins)}")
            raise HTTPException(status_code=500, detail="Unexpected response format from KB server manager for query plugins.")

    except HTTPException as he:
        # Re-raise HTTPExceptions (like 401, 503 from manager)
        raise he
    except Exception as e:
        logger.error(f"Error getting query plugins: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error getting query plugins: {str(e)}"
        )

