from fastapi import APIRouter, Request, HTTPException, Security, Depends, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ValidationError
import httpx
import os
from dotenv import load_dotenv
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.owi_bridge.owi_group import OwiGroupManager
from lamb.owi_bridge.owi_database import OwiDatabaseManager
from lamb.owi_bridge.owi_model import OWIModel
from creator_interface.openai_connect import OpenAIConnector
from lamb.database_manager import LambDatabaseManager
# Replaced HTTP endpoint imports with service layer
from lamb.services.assistant_service import AssistantService
from lamb.services.organization_service import OrganizationService
from typing import Optional, List, Dict, Any, Tuple, Union
import re
from .openai_connect import OpenAIConnector
import json
import aiohttp
import time
from fastapi.responses import JSONResponse
import unicodedata
from lamb.lamb_classes import Assistant
from datetime import datetime
import config
from utils.name_sanitizer import sanitize_assistant_name_with_prefix
from lamb.logging_config import get_logger

# Configuration
# Use LAMB_BACKEND_HOST for internal server-to-server requests
PIPELINES_HOST = config.LAMB_BACKEND_HOST
LAMB_BEARER_TOKEN = config.LAMB_BEARER_TOKEN

# --- Pydantic Models for Assistant Router --- #

class AssistantCreateBody(BaseModel):
    name: str
    description: Optional[str] = ""
    instructions: Optional[str] = "" # Fallback for system_prompt
    system_prompt: Optional[str] = ""
    prompt_template: Optional[str] = ""
    api_callback: Optional[str] = ""  # Kept for backward compatibility
    metadata: Optional[str] = ""  # New field - source of truth
    # Removed unused fields: pre_retrieval_endpoint, post_retrieval_endpoint, RAG_endpoint
    RAG_Top_k: Optional[int] = 3
    RAG_collections: Optional[str] = ""

class AssistantPublishResponse(BaseModel):
    message: str
    group_id: str
    model_id: str

    model_config = {
        'protected_namespaces': (),
    }

class AssistantCreateResponse(BaseModel):
    assistant_id: int
    name: str
    description: Optional[str]
    owner: str
    publish_status: Optional[AssistantPublishResponse] = None

class AssistantGetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner: str
    organization_id: Optional[int] = None
    api_callback: Optional[str]  # Kept for backward compatibility
    metadata: Optional[str]  # New field - source of truth for frontend
    system_prompt: Optional[str]
    prompt_template: Optional[str]
    RAG_Top_k: Optional[int]
    RAG_collections: Optional[str]
    # Removed unused fields: RAG_endpoint, pre_retrieval_endpoint, post_retrieval_endpoint
    group_id: Optional[str]
    group_name: Optional[str]
    oauth_consumer_name: Optional[str]
    published_at: Optional[int]
    published: bool # Existing field
    created_at: Optional[int] = None  # Unix timestamp in seconds
    updated_at: Optional[int] = None  # Unix timestamp in seconds
    # Access control metadata (populated by get_assistant_proxy)
    access_level: Optional[str] = None  # 'full', 'read_only', 'shared', or None
    is_owner: Optional[bool] = None  # Whether the requesting user owns this assistant


class GenerateDescriptionRequest(BaseModel):
    # Define fields expected by openai_connector.generate_assistant_description
    # Assuming it needs assistant context like name, instructions etc.
    name: Optional[str] = None
    instructions: Optional[str] = None
    # Add other fields as needed based on OpenAIConnector implementation
    pass

class GenerateDescriptionResponse(BaseModel):
    description: str
    status: str

class AssistantUpdateResponse(BaseModel):
    assistant_id: int
    # ... other fields returned by the backend update endpoint ...
    message: str # Assuming a confirmation message



class FileUploadStatus(BaseModel):
    filename: str
    file_id: Optional[str] = None
    status: str
    error: Optional[str] = None

class FileUploadResponse(BaseModel):
    message: str
    files: List[FileUploadStatus]


class AssistantListPaginatedResponse(BaseModel):
    """Response model for paginated list of assistants for the creator interface."""
    assistants: List[AssistantGetResponse]
    total_count: int

class ErrorResponseDetail(BaseModel):
    detail: Union[str, Dict[str, Any]] # Allow string or detailed validation error

class SoftDeleteResponse(BaseModel):
    message: str

class PublishRequest(BaseModel):
    publish_status: bool

# --- End Pydantic Models --- #

# Set up logger for assistant router
logger = get_logger(__name__, component="API")

# Load environment variables
load_dotenv()

# Get environment variables
LAMB_HOST = config.LAMB_WEB_HOST
# Note: LAMB_BEARER_TOKEN is configured in config.py and imported at the top
router = APIRouter()

# Initialize security context for dependency injection
security = HTTPBearer()

owi_user_manager = OwiUserManager()
db_manager = LambDatabaseManager()
# Add OWI Manager instances
owi_group_manager = OwiGroupManager()
owi_db_manager = OwiDatabaseManager() # Assuming connection details are handled internally
owi_model_manager = OWIModel(owi_db_manager) # Pass the OWI DB manager
# --- End OWI Manager instances ---
openai_connector = OpenAIConnector()


def get_creator_user_from_token(auth_header: str) -> Optional[Dict[str, Any]]:
    """
    Get creator user from authentication token

    Args:
        auth_header: The authorization header containing the token

    Returns:
        Optional[Dict[str, Any]]: Creator user object if found and valid, None otherwise
        Includes full organization data in 'organization' field for access control

    Raises:
        HTTPException(403): If the user account has been disabled by an admin
    """
    try:
        if not auth_header:
            logger.error("No authorization header provided")
            return None

        user_auth = owi_user_manager.get_user_auth(auth_header)
        if not user_auth:
            logger.error("Invalid authentication token")
            return None

        user_email = user_auth.get("email", "")
        if not user_email:
            logger.error("No email found in authentication token")
            return None

        creator_user = db_manager.get_creator_user_by_email(user_email)
        if not creator_user:
            logger.error(f"No creator user found for email: {user_email}")
            return None

        # Check if the user account is disabled
        if not creator_user.get('enabled', True):
            logger.warning(f"Disabled user {user_email} attempted API access with valid token")
            raise HTTPException(
                status_code=403,
                detail="Account disabled. Your account has been disabled by an administrator."
            )

        # Enrich with OWI role so callers (e.g. is_admin_user) can check
        # admin status without a separate OWI query.  user_auth was already
        # fetched above from the OWI /auths/ endpoint.
        creator_user['role'] = user_auth.get('role', 'user')

        # Fetch full organization data for access control
        organization_id = creator_user.get('organization_id')
        if organization_id:
            organization = db_manager.get_organization_by_id(organization_id)
            if organization:
                creator_user['organization'] = organization
                logger.debug(f"Added organization data for user {user_email}: {organization.get('name', 'Unknown')}")
            else:
                logger.warning(f"Organization {organization_id} not found for user {user_email}")
                creator_user['organization'] = {}
        else:
            logger.warning(f"No organization_id found for user {user_email}")
            creator_user['organization'] = {}

        return creator_user

    except HTTPException:
        raise  # Re-raise HTTPException (e.g. 403 for disabled accounts) without catching it
    except Exception as e:
        logger.error(f"Error getting creator user from token: {str(e)}")
        return None


def is_admin_user(user_or_auth_header) -> bool:
    """
    Check if a user has admin privileges.

    Accepts either:
      - A user dictionary (as returned by get_creator_user_from_token, which
        now always includes a 'role' field enriched from OWI).
      - An authorization header string, in which case OWI is queried directly.

    Args:
        user_or_auth_header: Either a user dictionary or authorization header containing the token

    Returns:
        bool: True if the user is an admin, False otherwise
    """
    try:
        # --- Dict path (from get_creator_user_from_token) ---
        if isinstance(user_or_auth_header, dict):
            user_role = user_or_auth_header.get("role", "")
            if not user_role:
                # Defensive: dict without role field — should not happen if
                # the caller used get_creator_user_from_token(), but log it.
                logger.warning(
                    f"User dictionary has no 'role' field for user id={user_or_auth_header.get('id')}. "
                    "Denying admin access. Ensure get_creator_user_from_token() is the source of this dict."
                )
                return False
            logger.info(f"User role from dictionary: {user_role} (user id={user_or_auth_header.get('id')})")
            return user_role == "admin"

        # --- String path (raw auth header) ---
        if not user_or_auth_header:
            logger.error("No authorization header provided")
            return False

        user_auth = owi_user_manager.get_user_auth(user_or_auth_header)
        if not user_auth:
            logger.error("Invalid authentication token")
            return False

        user_role = user_auth.get("role", "")
        logger.info(f"User role from token: {user_role}")
        return user_role == "admin"

    except Exception as e:
        logger.error(f"Error checking admin status: {str(e)}")
        return False


def try_parse_rag_top_k(value: Any) -> int:
    """Helper function to parse RAG_Top_k value with proper validation"""
    try:
        if isinstance(value, str) and not value.strip():
            return 3  # Default for empty string
        parsed = int(value)
        if parsed < 1:
            return 3  # Default for invalid values
        return parsed
    except (ValueError, TypeError):
        return 3  # Default for any parsing errors


def sanitize_filename(filename: str) -> str:
    """Removes or replaces characters unsafe for filenames."""
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    # Remove characters other than letters, numbers, underscore, hyphen, period
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    # Replace multiple underscores/hyphens with a single one
    filename = re.sub(r'[_.-]+', '_', filename)
    # Remove leading/trailing underscores/hyphens/periods
    filename = filename.strip('_.- ')
    # Limit length (optional)
    return filename[:100] if filename else "assistant_export"


def prepare_assistant_body(
    original_body: Dict[str, Any], 
    creator_user: Dict[str, Any], 
    sanitized_prefixed_name: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Prepare the assistant body with proper formatting and validation

    Args:
        original_body: The original request body
        creator_user: The creator user object
        sanitized_prefixed_name: Optional pre-sanitized and prefixed name (if None, will create from original)

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (prepared body, error message if any)
    """
    try:
        # Validate and get original name
        original_name = original_body.get("name", "")
        if not original_name:
            return None, "Assistant name is required"

        # Use provided sanitized name or create prefixed name
        if sanitized_prefixed_name:
            prefixed_name = sanitized_prefixed_name
        else:
            # Fallback: create prefixed name (for backward compatibility)
            prefixed_name = f"{creator_user['id']}_{original_name}"

        # Build the body according to Assistant class structure
        new_body = {
            "name": prefixed_name,  # Use prefixed name
            "description": original_body.get("description", ""),
            # Use email from creator user object
            "owner": creator_user['email'],
            # Handle metadata as source of truth, copy to api_callback for backward compatibility
            "metadata": original_body.get("metadata", original_body.get("api_callback", "")),
            "api_callback": original_body.get("metadata", original_body.get("api_callback", "")),
            # Check for system_prompt first, then instructions as fallback
            "system_prompt": original_body.get("system_prompt", original_body.get("instructions", "")),
            "prompt_template": original_body.get("prompt_template", ""),
            # Removed unused fields: pre_retrieval_endpoint, post_retrieval_endpoint, RAG_endpoint
            # These are still expected by the backend but we'll pass empty strings
            "pre_retrieval_endpoint": "",
            "post_retrieval_endpoint": "",
            "RAG_endpoint": "",
            # Validate and convert RAG_Top_k
            "RAG_Top_k": try_parse_rag_top_k(original_body.get("RAG_Top_k", 3)),
            "RAG_collections": original_body.get("RAG_collections", "")
        }

        # Remove None values
        new_body = {k: v for k, v in new_body.items() if v is not None}

        return new_body, None

    except Exception as e:
        logger.error(f"Error preparing assistant body: {str(e)}")
        return None, f"Error preparing assistant body: {str(e)}"


@router.post(
    "/create_assistant",
    tags=["Assistant Management"],
    summary="Create and Publish Assistant",
    description="""Endpoint to create a new assistant and immediately publish it.
    It automatically prefixes the assistant name with the creator's ID,
    creates the assistant in the database, and sets up the publication record.

Example curl Request:
```bash
curl -X POST 'http://localhost:9099/creator/assistant/create_assistant' \
-H 'Authorization: Bearer <user_token>' \
-H 'Content-Type: application/json' \
-d '{
  "name": "My_Course_Helper",
  "description": "Assists students with course materials.",
  "system_prompt": "You are a helpful assistant...",
  "RAG_Top_k": 5,
  "RAG_collections": "kb_uuid_1"
}'
```

Example Success Response (Returns the full state of the created+published assistant):
```json
{
  "id": 123,
  "name": "1_My_Course_Helper",
  "description": "Assists students with course materials.",
  "owner": "creator@example.com",
  "api_callback": null,
  "system_prompt": "You are a helpful assistant...",
  "prompt_template": null,

  "RAG_Top_k": 5,
  "RAG_collections": "kb_uuid_1",
  "group_id": "assistant_123",
  "group_name": "assistant_123",
  "oauth_consumer_name": "1_My_Course_Helper",
  "published_at": 1678886400,
  "published": true
}
```
Example Error Response (Validation):
```json
{
  "detail": "Assistant name can only contain letters, numbers, underscores and hyphens. No spaces or special characters allowed."
}
```
Example Error Response (Conflict):
```json
{
  "detail": "An assistant named 'My_Course_Helper' already exists for this owner. Please choose a different name."
}
```
Example Error Response (Publish Conflict):
```json
{
  "detail": "Assistant created but automatic publish failed: OAuth Consumer Name '1_My_Course_Helper' is already in use."
}
```
    """,
    response_model=AssistantCreateResponse,
    status_code=201,
    dependencies=[Depends(security)],
    responses={
        400: {"model": ErrorResponseDetail, "description": "Invalid input data"},
        401: {"model": ErrorResponseDetail, "description": "Invalid authentication"},
        409: {"model": ErrorResponseDetail, "description": "Conflict (Assistant name or OAuth Consumer Name already exists)"},
        422: {"model": ErrorResponseDetail, "description": "Validation Error (e.g., invalid name format)"},
        500: {"model": ErrorResponseDetail, "description": "Internal Server Error"}
    }
)
async def create_assistant_directly(request: Request):
    """
    Creates an assistant and publishes it directly using the database manager.
    Automatically sanitizes assistant names to conform to naming rules.
    """
    try:
        # 1. Get original request body
        original_body = await request.json()
        original_name = original_body.get("name", "") # Store original name for error messages

        # 2. Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        # 3. Validate that name is provided
        if not original_name or not original_name.strip():
            raise HTTPException(status_code=400, detail="Assistant name is required")

        # 4. Sanitize name with duplicate checking
        # Create a function to check if prefixed name exists
        def check_assistant_exists(prefixed_name: str) -> bool:
            """Check if an assistant with this name exists for this owner"""
            try:
                existing = db_manager.get_assistant_by_name_and_owner(
                    prefixed_name, 
                    creator_user['email']
                )
                return existing is not None
            except Exception as e:
                logger.warning(f"Error checking assistant existence: {e}")
                return False
        
        # Sanitize and handle duplicates
        sanitized_prefixed_name, sanitized_base_name, was_modified = sanitize_assistant_name_with_prefix(
            user_name=original_name,
            user_id=creator_user['id'],
            check_exists_fn=check_assistant_exists,
            max_length=50
        )
        
        # Log sanitization
        if was_modified:
            logger.info(
                f"Assistant name sanitized: '{original_name}' → '{sanitized_base_name}' "
                f"(prefixed: '{sanitized_prefixed_name}')"
            )
        
        assistant_name = sanitized_prefixed_name

        # 5. Prepare assistant data with sanitized name
        new_body, error = prepare_assistant_body(
            original_body, 
            creator_user, 
            sanitized_prefixed_name=sanitized_prefixed_name
        )
        if error:
            raise HTTPException(status_code=400, detail=error)

        # 6. Create Assistant in DB
        assistant_id = None
        try:
            # Add organization_id from creator_user
            new_body['organization_id'] = creator_user.get('organization_id')
            assistant_object = Assistant(**new_body) # Validate against Pydantic model
            logger.info(f"Attempting direct DB create for assistant: {assistant_object.name}")
            logger.info(f"Assistant object: {assistant_object}")
            assistant_id = db_manager.add_assistant(assistant_object)
            if assistant_id is None:
                logger.error(f"DB create failed for '{original_name}' - likely already exists.")
                raise HTTPException(
                    status_code=409, # Conflict
                    detail=f"An assistant named '{original_name}' already exists for this owner. Please choose a different name."
                )
            logger.info(f"Successfully created assistant {assistant_id} via direct DB call.")
        except ValidationError as ve:
            logger.error(f"Validation error creating Assistant object: {str(ve)}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(ve)}")
        except Exception as e:
            logger.error(f"Error during direct DB create: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error during assistant creation: {str(e)}")

        # --- Start OWI Integration ---
        logger.info(f"Starting OWI integration for assistant {assistant_id}")
        try:
            # Get admin token for OWI operations
            admin_token = owi_user_manager.get_admin_user_token()
            if not admin_token:
                logger.error("Failed to get OWI admin token during assistant creation.")
                # Don't fail the whole process, but log the error. Assistant is created locally.
                # We might want to raise an error or have a retry mechanism later.
                raise HTTPException(status_code=500, detail="Internal configuration error: OWI admin token unavailable.")

            # Get OWI user details for the creator
            owi_owner_user = owi_user_manager.get_user_by_email(creator_user['email'])
            if not owi_owner_user or 'id' not in owi_owner_user:
                logger.error(f"Could not find OWI user for email {creator_user['email']}")
                # Don't fail, proceed with local publish but log issue.
                raise HTTPException(status_code=404, detail=f"OWI User not found for owner email {creator_user['email']}. Cannot complete OWI setup.")

            owi_owner_id = owi_owner_user['id']

            # Define OWI group and model names
            owi_group_name = f"assistant_{assistant_id}" # Use assistant ID for uniqueness
            owi_model_id = str(assistant_id) # Use assistant ID for OWI model ID
            owi_model_name = f"LAMB:{assistant_name}" # Use prefixed assistant name for display

            # Create or get OWI group
            owi_group = owi_group_manager.get_group_by_name(owi_group_name)
            if not owi_group:
                logger.info(f"OWI Group '{owi_group_name}' not found, creating...")
                owi_group = owi_group_manager.create_group(
                    name=owi_group_name,
                    user_id=owi_owner_id,
                    description=f"Group for assistant: {assistant_name}"
                )
                if not owi_group:
                    logger.error(f"Failed to create OWI group '{owi_group_name}' for assistant {assistant_id}.")
                    raise HTTPException(status_code=500, detail="Failed to create OWI group for assistant.")
                logger.info(f"Successfully created OWI Group '{owi_group_name}' with ID: {owi_group.get('id')}")
            else:
                 logger.info(f"Found existing OWI Group '{owi_group_name}' with ID: {owi_group.get('id')}")

            owi_group_id = owi_group.get('id')
            if not owi_group_id:
                 logger.error(f"OWI Group ID is missing for group '{owi_group_name}'.")
                 raise HTTPException(status_code=500, detail="Failed to obtain OWI group ID.")

            # Add creator user to the OWI group
            add_user_success = owi_group_manager.add_user_to_group_by_email(owi_group_id, creator_user['email'])
            if not add_user_success:
                # Log error but proceed - maybe user was already added?
                logger.warning(f"Failed to add user {creator_user['email']} to OWI group {owi_group_id}. User might already be a member.")

            # Create or update OWI model with group permissions
            created_at_ts = int(time.time())
            
            # Extract capabilities from assistant metadata
            owi_capabilities = {"vision": False, "citations": True}  # Defaults
            try:
                metadata_str = new_body.get("metadata") or new_body.get("api_callback", "")
                if metadata_str:
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                    assistant_capabilities = metadata.get("capabilities", {})
                    # Map assistant capabilities to OWI model capabilities
                    owi_capabilities["vision"] = assistant_capabilities.get("vision", False)
                    # Include image_generation if the assistant has it enabled
                    if assistant_capabilities.get("image_generation", False):
                        owi_capabilities["image_generation"] = True
                    logger.info(f"Extracted capabilities for OWI model: {owi_capabilities}")
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Could not parse assistant metadata for capabilities: {e}. Using defaults.")
            
            model_created = owi_model_manager.create_model_api(
                token=admin_token,
                model_id=owi_model_id,
                name=owi_model_name,
                group_id=owi_group_id,
                created_at=created_at_ts,
                owned_by="lamb_v4", # System owner
                description=new_body.get("description", ""),
                suggestion_prompts=None,
                capabilities=owi_capabilities,
                params={}
            )

            if model_created:
                logger.info(f"Successfully created OWI model '{owi_model_name}' ({owi_model_id}) linked to group {owi_group_id}.")
            else:
                logger.info(f"OWI model '{owi_model_name}' ({owi_model_id}) may already exist or failed to create via API. Attempting to update permissions.")
                # If model creation failed, try adding the group to the existing model
                model_updated = owi_model_manager.add_group_to_model_by_name(
                    user_id=owi_owner_id, # Use owner's ID for permission check context? Old code used this.
                    model_name=owi_model_name,
                    group_id=owi_group_id,
                    permission_type="read"
                )
                if not model_updated:
                    logger.error(f"Failed to add group {owi_group_id} to existing OWI model '{owi_model_name}'. Manual intervention might be needed.")
                    # Don't fail the entire process, but log the significant issue.
                    # raise HTTPException(status_code=500, detail="Failed to update existing OWI model permissions.")
                else:
                    logger.info(f"Successfully added group {owi_group_id} permissions to existing OWI model '{owi_model_name}'.")

        except Exception as owi_error:
            logger.exception(f"Error during OWI integration for assistant {assistant_id}: {str(owi_error)}")
            # Allow process to continue to local publish, but raise an error indicating partial success.
            raise HTTPException(status_code=500, detail=f"Assistant created locally, but failed during OWI integration: {str(owi_error)}")
        # --- End OWI Integration ---


        # 6. Publish Assistant in DB (Local Record)
        # Use the OWI group ID obtained above
        # group_id = f"assistant_{assistant_id}" # Old way
        local_group_id = owi_group_id # Use OWI group ID for local publish record consistency
        local_group_name = owi_group_name # Use OWI group name
        oauth_consumer_name = "" # create the assitant as unpublished 

        logger.info(f"Attempting direct DB publish for assistant {assistant_id} using OWI Group ID {local_group_id}")
        try:
            publish_success = db_manager.publish_assistant(
                assistant_id=assistant_id,
                assistant_name=assistant_name, # This seems correct based on old code's usage
                assistant_owner=creator_user['email'],
                group_id=local_group_id,
                group_name=local_group_name,
                oauth_consumer_name=None # This is used for the OAuth mapping in OWI
            )
            if not publish_success:
                # Check if it failed due to existing OAuth name conflict
                existing_pub = db_manager.get_published_assistant_by_oauth_consumer(oauth_consumer_name)
                if existing_pub:
                     error_detail = f"Assistant created and OWI setup possibly done, but local publish failed: OAuth Consumer Name '{oauth_consumer_name}' is already in use locally."
                     logger.error(error_detail)
                     # Return a 409 conflict, but the assistant IS created.
                     # Maybe return the created assistant ID with an error message?
                     # For now, stick to raising 409.
                     raise HTTPException(status_code=409, detail=error_detail) # Conflict
                else:
                     error_detail = f"Assistant created and OWI setup possibly done, but local publish failed: Database error during publish for assistant {assistant_id}."
                     logger.error(error_detail)
                     raise HTTPException(status_code=500, detail=error_detail)
            logger.info(f"Successfully published assistant {assistant_id} via direct DB call.")
        except Exception as e:
            logger.exception(f"Error during direct DB publish for assistant {assistant_id} (after OWI setup): {str(e)}")
            # The assistant and OWI parts are likely done, but the final local publish failed.
            raise HTTPException(status_code=500, detail=f"Assistant created and OWI setup possibly done, but database error during final local publish step: {str(e)}")

        # 7. Fetch Final State from DB
        logger.info(f"Fetching final state for assistant {assistant_id} directly from DB.")
        final_assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
        if not final_assistant_data:
             logger.error(f"Failed to fetch final state for assistant {assistant_id} after create/publish.")
             raise HTTPException(status_code=500, detail="Failed to confirm final assistant state after creation.")

        # 8. Construct and Return the required format
        # Create a dictionary with the required data
        return {
            "assistant_id": final_assistant_data.get('id'),
            "name": final_assistant_data.get('name'),
            "description": final_assistant_data.get('description'),
            "owner": final_assistant_data.get('owner'),
            "publish_status": {
                "message": "Assistant published successfully",
                "group_id": final_assistant_data.get('group_id'),
                "model_id": str(final_assistant_data.get('id'))
            }
        }

    except HTTPException as he:
        # Log known HTTP exceptions before re-raising
        logger.error(f"HTTPException in create_assistant_directly: Status={he.status_code}, Detail={he.detail}")
        raise he
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected internal server error in create_assistant_directly: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/get_assistant/{assistant_id}",
    tags=["Assistant Management"],
    summary="Get Assistant Details",
    description="""Retrieves a specific assistant owned by the authenticated user,
including its publication status, directly from the database.

Example Request:
```bash
cURL -X GET 'http://localhost:8000/creator/assistant/get_assistant/123' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response (Published Assistant):
```json
{
  "id": 123,
  "name": "1_My Course Helper",
  "description": "Assists students with course materials.",
  "owner": "creator@example.com",
  "api_callback": null,
  "system_prompt": "You are a helpful assistant...",
  "prompt_template": null,

  "RAG_Top_k": 5,
  "RAG_collections": "kb_uuid_1",
  "group_id": "group_uuid_abc",
  "group_name": "assistant_123",
  "oauth_consumer_name": "null",
  "published_at": 1678886400,
  "published": true
}
```
Example Success Response (Unpublished Assistant):
```json
{
  "id": 124,
  "name": "1_Draft Helper",
  "description": "Draft assistant.",
  "owner": "creator@example.com",
  "api_callback": null,
  "system_prompt": "Draft instructions...",
  "prompt_template": null,

  "RAG_Top_k": 3,
  "RAG_collections": null,
  "group_id": null,
  "group_name": null,
  "oauth_consumer_name": null,
  "published_at": null,
  "published": false
}
```
Example Error Response (Not Found):
```json
{
  "detail": "Assistant not found"
}
```
Example Error Response (Forbidden):
```json
{
  "detail": "Assistant not found" 
}
```
    """,
    response_model=AssistantGetResponse,
    dependencies=[Depends(security)],
    responses={
        401: {"description": "Invalid authentication"},
        404: {"description": "Assistant not found or access denied"},
        500: {"description": "Internal server error or database error"}
    }
)
async def get_assistant_proxy(assistant_id: int, request: Request, response: Response):
    """Gets a specific assistant with its publication info directly from the database."""
    logger.info(f"Received request to get assistant ID: {assistant_id} directly from DB.")
    
    # Add cache-control headers to prevent caching of assistant data
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error(f"Unauthorized attempt to get assistant {assistant_id}.")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )
        logger.info(f"User {creator_user.get('email')} requesting assistant {assistant_id}.")

        # Get assistant data directly from the database
        logger.info(f"Fetching assistant {assistant_id} directly from database.")
        assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)

        # Handle assistant not found
        if not assistant_data:
            logger.warning(f"Assistant {assistant_id} not found in database.")
            raise HTTPException(
                status_code=404,
                detail="Assistant not found"
            )

        # --- Verify Access: Ownership, Admin, Org Admin, or Sharing ---
        # User has access if they:
        # 1. Own the assistant (full access)
        # 2. Are a System Admin (read-only access to any assistant)
        # 3. Are an Org Admin for the assistant's organization (read-only access)
        # 4. Assistant is shared with them (limited access)
        is_owner = assistant_data.get('owner') == creator_user['email']
        is_admin = is_admin_user(creator_user)
        access_level = 'full' if is_owner else None
        
        if not is_owner:
            if is_admin:
                # System admin can view any assistant (read-only)
                access_level = 'read_only'
                logger.info(f"System admin {creator_user['email']} viewing assistant {assistant_id} (read-only)")
            else:
                # Check if user is org admin for this assistant's organization
                assistant_org_id = assistant_data.get('organization_id')
                user_org_id = creator_user.get('organization_id')
                if assistant_org_id and user_org_id == assistant_org_id:
                    user_org_role = db_manager.get_user_organization_role(
                        creator_user['id'], assistant_org_id)
                    if user_org_role in ('admin', 'owner'):
                        access_level = 'read_only'
                        logger.info(f"Org admin {creator_user['email']} viewing assistant {assistant_id} in their org (read-only)")
                
                # Check if assistant is shared with user
                if not access_level:
                    from lamb.database_manager import LambDatabaseManager
                    db_check = LambDatabaseManager()
                    is_shared = db_check.is_assistant_shared_with_user(assistant_id, creator_user['id'])
                    if is_shared:
                        access_level = 'shared'
        
        if not access_level:
            # Log potential security/data issue but return 404 to the user for security
            logger.warning(f"Access denied: User {creator_user['email']} attempted to access assistant {assistant_id} owned by {assistant_data.get('owner')}")
            raise HTTPException(
                status_code=404, # Treat as not found for this user
                detail="Assistant not found"
            )
        # --- End Access Verification ---
        
        # Add access metadata to response so frontend can adjust UI
        assistant_data['access_level'] = access_level
        assistant_data['is_owner'] = is_owner

        # The 'published' field is correctly calculated by the DB function
        # Ensure metadata is populated from api_callback if empty
        if not assistant_data.get('metadata') and assistant_data.get('api_callback'):
            assistant_data['metadata'] = assistant_data['api_callback']
            logger.info(f"Populated metadata from api_callback for assistant {assistant_id}")
        
        # Pydantic validation against AssistantGetResponse happens automatically
        logger.info(f"Successfully retrieved assistant {assistant_id} data for user {creator_user['email']}. Returning.")
        return assistant_data

    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions (like 401, 404 from checks)
    except Exception as e:
        # Catch potential database errors or other issues
        logger.error(f"Error getting assistant {assistant_id} directly from DB: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/get_assistants",
    tags=["Assistant Management"],
    summary="Get Assistants Proxy",
    description="""Proxy endpoint that retrieves a paginated list of assistants owned by the authenticated user,
including their publication status (merged from the backend).

Example Request with Pagination:
```bash
cURL -X GET 'http://localhost:8000/creator/assistant/get_assistants?limit=5&offset=10' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "assistants": [
    {
      "id": 123,
      "name": "1_My Course Helper",
      "description": "Assists students with course materials.",
      "owner": "creator@example.com",
      "api_callback": null,
      "system_prompt": "You are a helpful assistant...",
      "prompt_template": null,
    
      "RAG_Top_k": 5,
      "RAG_collections": "kb_uuid_1",
      "pre_retrieval_endpoint": null,
      "post_retrieval_endpoint": null,
      "group_id": "group_uuid_abc",
      "group_name": "assistant_123",
      "oauth_consumer_name": "null",
      "published_at": 1678886400,
      "published": true
    },
    {
      "id": 124,
      "name": "1_Draft Helper",
      "description": "Draft assistant.",
      "owner": "creator@example.com",
      "api_callback": null,
      "system_prompt": "Draft instructions...",
      "prompt_template": null,
    
      "RAG_Top_k": 3,
      "RAG_collections": null,
      "pre_retrieval_endpoint": null,
      "post_retrieval_endpoint": null,
      "group_id": null,
      "group_name": null,
      "oauth_consumer_name": null,
      "published_at": null,
      "published": false
    }
  ],
  "total_count": 25
}
```
    """,
    response_model=AssistantListPaginatedResponse,
    dependencies=[Depends(security)],
    responses={
})
async def get_assistants_proxy(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Number of assistants per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Proxy endpoint that forwards request to get assistants for the authenticated user with pagination.
    """
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )
        
        # DEBUG: Log the user information
        logger.info(f"[DEBUG] get_assistants_proxy: Creator user: {creator_user}")
        logger.info(f"[DEBUG] get_assistants_proxy: User email: {creator_user.get('email')}")

        # BYPASS INTERNAL API - Direct database access
        logger.info(f"[DEBUG] get_assistants_proxy: BYPASSING internal API, using direct database access")
        
        # Initialize database manager
        db_manager = LambDatabaseManager()
        
        # Get assistants directly from database
        owner_email = creator_user.get('email')
        logger.info(f"[DEBUG] get_assistants_proxy: Fetching assistants for owner: {owner_email}")
        
        assistants_list, total_count = db_manager.get_assistants_by_owner_paginated(
            owner=owner_email,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"[DEBUG] get_assistants_proxy: Database returned {len(assistants_list)} assistants, total count: {total_count}")
        
        # Format the response to match expected structure
        paginated_data = {
            "assistants": assistants_list,
            "total_count": total_count
        }
        
        logger.info(f"[DEBUG] get_assistants_proxy: Formatted response data: {paginated_data}")
        
        # Ensure metadata is populated from api_callback if empty for each assistant
        if 'assistants' in paginated_data:
            for assistant in paginated_data['assistants']:
                if not assistant.get('metadata') and assistant.get('api_callback'):
                    assistant['metadata'] = assistant['api_callback']
                    logger.info(f"Populated metadata from api_callback for assistant {assistant.get('id')}")

        # Pydantic validation against AssistantListPaginatedResponse happens automatically
        return paginated_data

    except httpx.RequestError as e:
        logger.error(f"Error forwarding request to get assistants: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error forwarding request: {str(e)}")
    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Internal server error in get_assistants_proxy: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/generate_assistant_description",
    tags=["Assistant Management", "AI Utilities"],
    summary="Generate Assistant Description",
    description="""Generate a description for an assistant using the configured LLM (via OpenAIConnector).
    The request body should contain context about the assistant (e.g., name, instructions).

Example Request Body:
```json
{
  "name": "Math Tutor Bot",
  "instructions": "You are a friendly and patient tutor that helps high school students understand algebra concepts. Explain concepts clearly and provide step-by-step examples."
}
```

Example Success Response:
```json
{
  "description": "A friendly and patient AI Math Tutor designed to help high school students grasp algebra concepts through clear explanations and step-by-step examples.",
  "status": "success"
}
```
Example Error Response:
```json
{
  "detail": "Error generating description: API key not valid, or quota exceeded."
}
```
    """,
    response_model=GenerateDescriptionResponse,
    dependencies=[Depends(security)], # Assuming generation requires knowing the user or some auth
    responses={
})
async def generate_assistant_description(request: Request):
    """
    Generate a description for an assistant using the configured OpenAI model
    """
    try:
        body = await request.json()
        description = await openai_connector.generate_assistant_description(body)
        return {
            "description": description,
            "status": "success"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Error in generate_assistant_description endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating description: {str(e)}"
        )


@router.put(
    "/update_assistant/{assistant_id}",
    tags=["Assistant Management"],
    summary="Update Assistant Proxy",
    description="""Proxy endpoint that forwards assistant update requests to the lamb assistant router.
    The assistant name prefix (creator ID) is handled automatically.

Example Request Body:
```json
{
  "name": "My Updated Course Helper",
  "description": "Updated description.",
  "instructions": "Updated instructions...",
  "RAG_Top_k": 3,
  "RAG_collections": "kb_uuid_1"
}
```

Example Success Response:
```json
{
  "assistant_id": 123,
  "message": "Assistant updated successfully"
  # ... potentially other fields returned by the backend ...
}
```
Example Error Response:
```json
{
  "detail": "Failed to update assistant: Assistant not found"
}
```
    """,
    response_model=AssistantUpdateResponse,
    dependencies=[Depends(security)],
    responses={
})
async def update_assistant_proxy(assistant_id: int, request: Request):
    """
    Update assistant using direct function call to core assistant router
    """
    logger.info(f"Received update request for assistant ID: {assistant_id}")
    try:
        # Get the original request body
        original_body = await request.json()
        logger.info(f"Original request body for update: {original_body}")

        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error(f"Unauthorized attempt to update assistant {assistant_id}.")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )
        logger.info(f"User {creator_user.get('email')} attempting to update assistant {assistant_id}.")

        # Prepare the assistant body
        new_body, error = prepare_assistant_body(original_body, creator_user)
        if error:
            logger.error(f"Error preparing update body for assistant {assistant_id}: {error}")
            raise HTTPException(status_code=400, detail=error)
        logger.info(f"Prepared body for update (Assistant ID {assistant_id}): {new_body}")

        # Create a mock request object with the prepared body
        from fastapi import Request as FastAPIRequest
        from unittest.mock import Mock
        import json

        # Create a mock request with the JSON body
        # The json() method must be async since core function does await request.json()
        mock_request = Mock()
        
        async def async_json():
            return new_body
        
        mock_request.json = async_json

        logger.info(f"Using AssistantService to update assistant {assistant_id}")
        
        # Initialize service
        assistant_service = AssistantService()
        
        # Convert prepared body to Assistant object
        from lamb.lamb_classes import Assistant
        assistant_obj = Assistant(**new_body)
        
        # Update via service layer
        success = assistant_service.update_assistant(assistant_id, assistant_obj)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found or update failed")

        logger.info(f"Successfully updated assistant {assistant_id} via service layer.")
        # Construct the response according to the AssistantUpdateResponse model
        return {
            "assistant_id": assistant_id,
            "message": "Assistant updated successfully"
        }

    except HTTPException as he:
        # Log specific HTTP exceptions raised within the proxy logic
        logger.error(f"HTTPException during update for assistant {assistant_id}: Status={he.status_code}, Detail={he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during update for assistant {assistant_id}: {str(e)}") # Use logger.exception to include traceback
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete(
    "/delete_assistant/{assistant_id}",
    tags=["Assistant Management"],
    summary="Delete Assistant Proxy (Soft Delete)",
    description="""Proxy endpoint that forwards assistant soft-delete requests to the lamb assistant router.
    Verifies ownership or admin privileges before proceeding.

Example Request:
```bash
curl -X DELETE 'http://localhost:9099/creator/assistant/delete_assistant/123' \
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "message": "Assistant soft deleted successfully"
}
```
Example Error Response (Not Found):
```json
{
  "detail": "Assistant not found"
}
```
Example Error Response (Forbidden):
```json
{
  "detail": "User does not have permission to delete this assistant"
}
```
    """,
    response_model=SoftDeleteResponse,
    dependencies=[Depends(security)],
    responses={
        401: {"description": "Invalid authentication"},
        403: {"description": "Permission denied"},
        404: {"description": "Assistant not found"},
        500: {"description": "Internal server error or core API error"}
    }
)
async def delete_assistant_proxy(assistant_id: int, request: Request):
    """
    Proxy endpoint that forwards assistant soft-delete requests to the lamb assistant router.
    Verifies ownership before proceeding.
    """
    logger.info(f"Received soft delete request for assistant ID: {assistant_id}")
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error(f"Unauthorized attempt to delete assistant {assistant_id}.")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )
        logger.info(f"User {creator_user.get('email')} attempting to soft delete assistant {assistant_id}.")

        # 1. Get assistant details to verify ownership using direct database call
        assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)
        if not assistant_data:
            logger.warning(f"Assistant {assistant_id} not found during delete pre-check.")
            raise HTTPException(
                status_code=404,
                detail="Assistant not found"
            )

        # 2. Verify ownership or admin role
        is_owner = assistant_data.get('owner') == creator_user['email']
        is_admin = is_admin_user(creator_user) # Check if the user is admin

        if not is_owner and not is_admin:
            logger.warning(f"Permission denied: User {creator_user['email']} (Admin: {is_admin}) attempted to delete assistant {assistant_id} owned by {assistant_data.get('owner')}")
            raise HTTPException(
                status_code=403,
                detail="User does not have permission to delete this assistant"
            )
        logger.info(f"User {creator_user['email']} authorized to delete assistant {assistant_id} (Is Owner: {is_owner}, Is Admin: {is_admin}).")

        # 3. Call the core soft delete function directly
        logger.info(f"Using AssistantService to soft delete assistant {assistant_id}")
        
        # Initialize service  
        assistant_service = AssistantService()
        
        # Soft delete via service layer
        result = assistant_service.soft_delete_assistant_by_id(assistant_id)

        logger.info(f"Successfully soft deleted assistant {assistant_id} via service layer.")
        # Return the success message
        return result

    except httpx.RequestError as e:
        logger.error(f"HTTPX error forwarding delete request for assistant {assistant_id}: {str(e)}")
        raise HTTPException(
            status_code=502, detail=f"Error communicating with core service: {str(e)}")
    except HTTPException as he:
        # Log specific HTTP exceptions raised within the proxy logic
        logger.error(f"HTTPException during delete for assistant {assistant_id}: Status={he.status_code}, Detail={he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during delete for assistant {assistant_id}: {str(e)}") # Use logger.exception to include traceback
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/upload_files",
    tags=["Knowledge Base Management"],
    summary="Upload Files",
    description="""Upload files to a specified knowledge base in OpenWebUI using admin credentials.
    Requires multipart/form-data with 'files' (one or more file uploads) and 'kb_id' fields.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/assistant/upload_files' \\
  -H 'Authorization: Bearer <user_token>' \\
  -F 'kb_id=kb_uuid_xyz' \\
  -F 'files=@/path/to/document1.pdf' \\
  -F 'files=@/path/to/document2.txt'
```

Example Success Response:
```json
{
  "message": "Files processed",
  "files": [
    {
      "filename": "document1.pdf",
      "file_id": "file_uuid_123",
      "status": "success",
      "error": null
    },
    {
      "filename": "document2.txt",
      "file_id": "file_uuid_456",
      "status": "success",
      "error": null
    }
  ]
}
```
Example Response with Errors:
```json
{
  "message": "Files processed",
  "files": [
    {
      "filename": "document1.pdf",
      "file_id": "file_uuid_123",
      "status": "success",
      "error": null
    },
    {
      "filename": "unsupported.zip",
      "status": "error",
      "error": "Upload failed: {"detail":"File type not supported"}",
      "file_id": null
    }
  ]
}
```
    """,
    response_model=FileUploadResponse,
    dependencies=[Depends(security)],
    responses={
})
async def upload_files(request: Request):
    """
    Upload files to a knowledge base using admin credentials.
    Workflow:
    1. Authenticate user
    2. Upload files to OWI API
    3. Add files to the specified knowledge base
    """
    logger.info("Received request to upload files")
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Failed to get creator user from token")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )
        logger.info(f"Creator user authenticated: {creator_user.get('email')}")

        # FIXME: there is duplicate code in this file, we should refactor it
        # to avoid repeating the same code for the admin token and many other

        
        # Get admin token for OWI API operations
        logger.info("Getting admin token...")
        admin_token = owi_user_manager.get_admin_user_token()
        if not admin_token:
            logger.error("Failed to get admin token")
            raise HTTPException(
                status_code=500,
                detail="Failed to get admin token"
            )
        logger.info("Successfully got admin token")

        # Parse multipart form data
        form = await request.form()
        files = form.getlist('files')
        kb_id = form.get('kb_id')

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        if not kb_id:
            raise HTTPException(
                status_code=400, detail="No knowledge base ID provided")

        logger.info(f"Uploading {len(files)} files to knowledge base {kb_id}")

        # Process each file
        uploaded_files = []
        async with httpx.AsyncClient() as client:
            for file in files:
                try:
                    # Prepare the file for upload
                    file_content = await file.read()  # Read the file content
                    files_data = {
                        'file': (
                            file.filename,
                            file_content,
                            file.content_type
                        )
                    }

                    # First, upload the file to get a file ID
                    # Add trailing slash
                    file_upload_url = f"{owi_user_manager.OWI_API_BASE_URL}/files/"
                    upload_response = await client.post(
                        file_upload_url,
                        headers={
                            "Authorization": f"Bearer {admin_token}",
                            "Accept": "application/json"
                        },
                        files=files_data
                    )

                    if not upload_response.is_success:
                        logger.error(
                            f"Failed to upload file {file.filename}: {upload_response.text}")
                        uploaded_files.append({
                            'filename': file.filename,
                            'status': 'error',
                            'error': f"Upload failed: {upload_response.text}"
                        })
                        continue

                    file_data = upload_response.json()
                    # OpenWebUI returns 'id' not 'file_id'
                    file_id = file_data.get('id')

                    if not file_id:
                        error_msg = "No file ID received in response"
                        logger.error(f"{error_msg} for {file.filename}")
                        uploaded_files.append({
                            'filename': file.filename,
                            'status': 'error',
                            'error': error_msg
                        })
                        continue

                    # Add file to knowledge base
                    kb_response = await client.post(
                        f"{owi_user_manager.OWI_API_BASE_URL}/knowledge/{kb_id}/file/add",
                        headers={
                            "Authorization": f"Bearer {admin_token}",
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        },
                        json={"file_id": file_id}
                    )

                    if not kb_response.is_success:
                        error_msg = f"Failed to add to knowledge base: {kb_response.text}"
                        logger.error(f"{error_msg} for file {file_id}")
                        uploaded_files.append({
                            'filename': file.filename,
                            'file_id': file_id,
                            'status': 'error',
                            'error': error_msg
                        })
                        continue

                    uploaded_files.append({
                        'filename': file.filename,
                        'file_id': file_id,
                        'status': 'success'
                    })
                    logger.info(f"Successfully processed file {file.filename}")

                except Exception as e:
                    logger.error(
                        f"Error processing file {file.filename}: {str(e)}")
                    uploaded_files.append({
                        'filename': file.filename,
                        'status': 'error',
                        'error': str(e)
                    })

        if not uploaded_files:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload any files"
            )

        return {
            "message": "Files processed",
            "files": uploaded_files
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files: {str(e)}"
        )


@router.get(
    "/export/{assistant_id}",
    tags=["Assistant Management"],
    summary="Export Assistant Data as JSON",
    description="""Endpoint to export the full data of a specific assistant as a JSON file.
    Verifies ownership before allowing the export.

Example Request:
```bash
cURL -X GET 'http://localhost:8000/creator/assistant/export/123' \\
+-H 'Authorization: Bearer <user_token>'
```

Success Response:
*   Status Code: 200 OK
*   Content-Type: application/json
*   Content-Disposition: attachment; filename="assistant_123_My_Assistant.json"
*   Body: JSON object containing the full assistant data.

Error Responses:
*   401: Invalid authentication
*   404: Assistant not found or access denied
*   500: Internal server error or core API error
    """,
    response_class=JSONResponse, # Specify JSONResponse directly for headers
    dependencies=[Depends(security)],
    responses={
        200: {
            "description": "Assistant data exported successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object" # Representing the assistant data
                    }
                }
            },
            "headers": {
                "Content-Disposition": {
                    "description": "Specifies the filename for the download",
                    "schema": {"type": "string"}
                }
            }
        },
        401: {"description": "Invalid authentication"},
        404: {"description": "Assistant not found or access denied"},
        500: {"description": "Internal server error or core API error"}
    }
)
async def export_assistant_proxy(assistant_id: int, request: Request):
    """Proxy endpoint to fetch and return assistant data for JSON export."""
    logger.info(f"Received export request for assistant ID: {assistant_id}")
    try:
        # 1. Authenticate User
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication")

        # 2. Fetch Assistant Data using direct function call
        logger.info(f"Fetching assistant {assistant_id} details via direct call for export.")
        # Initialize service
        assistant_service = AssistantService()
        
        # Get assistant with publication data via service layer
        assistant_data = assistant_service.get_assistant_with_publication_dict(assistant_id)
        
        # Handle not found
        if not assistant_data:
            logger.warning(f"Assistant {assistant_id} not found during export.")
            raise HTTPException(status_code=404, detail="Assistant not found")
        
        result = {"assistant": assistant_data}

        assistant_data = result['assistant']

        # 4. Verify Ownership
        if assistant_data.get('owner') != creator_user['email']:
            logger.warning(f"Access denied: User {creator_user['email']} attempted export for assistant {assistant_id} owned by {assistant_data.get('owner')}")
            raise HTTPException(status_code=404, detail="Assistant not found") # Treat as not found for security

        # 5. Prepare Filename
        raw_name = assistant_data.get('name', 'export').replace(f"{creator_user['id']}_", "") # Remove prefix for filename
        sanitized_name = sanitize_filename(raw_name)
        filename = f"{sanitized_name}.json" if sanitized_name else "assistant_export.json"

        # 6. Return JSONResponse with Headers
        logger.info(f"Exporting assistant {assistant_id} data as '{filename}'")
        # Pretty print the JSON content
        pretty_json_content = json.dumps(assistant_data, indent=4)
        return JSONResponse(
            content=json.loads(pretty_json_content), # Convert back to dict/list for JSONResponse
            media_type="application/json",
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    except httpx.RequestError as e:
        logger.error(f"HTTPX error during export request for assistant {assistant_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error communicating with core service: {str(e)}")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during export for assistant {assistant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put(
    "/publish/{assistant_id}",
    tags=["Assistant Management"],
    summary="Publish or Unpublish Assistant",
    description="""Updates the publication status of a specific assistant. Requires ownership.
    - Publishing sets the oauth_consumer_name to the assistant's name.
    - Unpublishing removes the publication record or sets oauth_consumer_name to null.

Example Request (Publish):
```bash
cURL -X PUT 'http://localhost:8000/creator/assistant/publish/123' \
-H 'Authorization: Bearer <user_token>' \
-H 'Content-Type: application/json' \
-d '{"publish_status": true}'
```

Example Request (Unpublish):
```bash
cURL -X PUT 'http://localhost:8000/creator/assistant/publish/123' \
-H 'Authorization: Bearer <user_token>' \
-H 'Content-Type: application/json' \
-d '{"publish_status": false}'
```

Example Success Response (Returns full updated assistant data):
```json
{
  "id": 123,
  "name": "1_My_Course_Helper",
  "description": "Assists students...",
  "owner": "creator@example.com",
  "api_callback": null,
  "system_prompt": "...",
  "prompt_template": null,

  "RAG_Top_k": 5,
  "RAG_collections": "kb_uuid_1",
  "group_id": "assistant_123",
  "group_name": "assistant_123",
  "oauth_consumer_name": "1_My_Course_Helper", // Set when published
  "published_at": 1678886400,
  "published": true // Updated based on action
}
```
    """,
    response_model=AssistantGetResponse,
    dependencies=[Depends(security)],
    responses={
        401: {"description": "Invalid authentication"},
        403: {"description": "Permission denied"},
        404: {"description": "Assistant not found"},
        500: {"description": "Internal server error or database error"}
    }
)
async def publish_assistant(assistant_id: int, publish_request: PublishRequest, request: Request):
    """
    Publish or unpublish an assistant by updating its publication record directly in the DB.
    """
    logger.info(f"Received publish request for assistant ID: {assistant_id} with status: {publish_request.publish_status}")
    try:
        # 1. Authenticate User
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            logger.error(f"Unauthorized publish attempt for assistant {assistant_id}.")
            raise HTTPException(status_code=401, detail="Invalid authentication")
        logger.info(f"User {creator_user.get('email')} attempting to publish/unpublish assistant {assistant_id}.")

        # 2. Fetch Assistant to verify ownership
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            logger.warning(f"Assistant {assistant_id} not found during publish request.")
            raise HTTPException(status_code=404, detail="Assistant not found")

        # 3. Verify Ownership
        if assistant.owner != creator_user['email']:
            logger.warning(f"Permission denied: User {creator_user['email']} attempted to modify assistant {assistant_id} owned by {assistant.owner}")
            raise HTTPException(status_code=403, detail="User does not have permission to modify this assistant")

        # 4. Perform Publish/Unpublish Action
        group_id = f"assistant_{assistant_id}"
        group_name = f"assistant_{assistant_id}"
        success = False

        if publish_request.publish_status:
            # Publish: Set oauth_consumer_name to assistant name
            logger.info(f"Publishing assistant {assistant_id}. Setting oauth_consumer_name to '{assistant.name}'")
            success = db_manager.publish_assistant(
                assistant_id=assistant_id,
                assistant_name=assistant.name,
                assistant_owner=assistant.owner,
                group_id=group_id,
                group_name=group_name,
                oauth_consumer_name=assistant.name # Use assistant name
            )
            if not success:
                 logger.error(f"Database error during publishing assistant {assistant_id}")
                 raise HTTPException(status_code=500, detail="Failed to publish assistant in database")
        else:
            # Unpublish: Call publish_assistant with oauth_consumer_name set to None
            logger.info(f"Unpublishing assistant {assistant_id} by setting oauth_consumer_name to None.")
            success = db_manager.publish_assistant(
                assistant_id=assistant_id,
                assistant_name=assistant.name, # Still need name/owner for potential upsert
                assistant_owner=assistant.owner,
                group_id=group_id,
                group_name=group_name,
                oauth_consumer_name=None # Set to None for unpublishing
            )
            if not success:
                logger.error(f"Database error during unpublishing assistant {assistant_id}")
                raise HTTPException(status_code=500, detail="Failed to unpublish assistant in database")

        # 5. Fetch Updated Assistant Data
        logger.info(f"Fetching updated data for assistant {assistant_id} after publish/unpublish operation.")
        updated_assistant_data = db_manager.get_assistant_by_id_with_publication(assistant_id)

        if not updated_assistant_data:
            logger.error(f"Failed to retrieve assistant {assistant_id} data after update.")
            # This case should ideally not happen if the assistant existed before
            raise HTTPException(status_code=500, detail="Failed to retrieve updated assistant data")

        # Add access metadata so the frontend can adjust UI correctly after publish/unpublish
        updated_assistant_data['is_owner'] = True  # Only owner can publish/unpublish (verified above)
        updated_assistant_data['access_level'] = 'full'

        logger.info(f"Successfully processed publish request for assistant {assistant_id}. Returning updated data.")
        return updated_assistant_data

    except HTTPException as he:
        # Log specific HTTP exceptions raised within the logic
        logger.error(f"HTTPException during publish/unpublish for assistant {assistant_id}: Status={he.status_code}, Detail={he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during publish/unpublish for assistant {assistant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/defaults",
    tags=["Assistant Management"],
    summary="Get assistant defaults for current user's organization",
    description="""Returns the organization-scoped assistant_defaults used to seed the assistant form.""",
    dependencies=[Depends(security)]
)
async def get_assistant_defaults_for_current_user(request: Request):
    try:
        # Identify current user/org
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_email = creator_user.get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found")

        # Get user's organization from database
        from lamb.database_manager import LambDatabaseManager
        from lamb.owi_bridge.owi_users import OwiUserManager
        
        db_manager = LambDatabaseManager()
        owi_manager = OwiUserManager()
        
        # Get user by email from OWI database (for authentication)
        owi_user = owi_manager.db.get_user_by_email(user_email)
        if not owi_user:
            raise HTTPException(status_code=404, detail="User not found in authentication system")
        
        # Get user from LAMB database (for organization lookup)
        lamb_user = db_manager.get_creator_user_by_email(user_email)
        if not lamb_user:
            # Default to system organization for users not in LAMB database
            org_slug = "lamb"
            logger.info(f"User {user_email} not found in LAMB database, defaulting to system org: {org_slug}")
        else:
            # Use the user's organization from LAMB database
            lamb_user_id = lamb_user.get('id')
            org_id = lamb_user.get('organization_id')
            logger.debug(f"LAMB User lookup: email={user_email}, lamb_user_id={lamb_user_id}, organization_id={org_id}")
            
            if org_id:
                # Get organization by ID
                org = db_manager.get_organization_by_id(org_id)
                if org:
                    org_slug = org['slug']
                    logger.debug(f"Using user's primary organization: {org_slug}")
                else:
                    org_slug = "lamb"
                    logger.warning(f"Organization ID {org_id} not found, defaulting to system org: {org_slug}")
            else:
                # Fallback to checking organization roles
                organizations = db_manager.get_user_organizations(lamb_user_id)
                logger.debug(f"Organizations for lamb_user_id {lamb_user_id}: {organizations}")
                if not organizations:
                    org_slug = "lamb"
                    logger.info(f"No organizations found, defaulting to system org: {org_slug}")
                else:
                    org_slug = organizations[0]['slug']
                    logger.debug(f"Using first organization from roles: {org_slug}")

        # Use OrganizationService to get defaults
        logger.info(f"Getting assistant defaults for organization {org_slug} via service layer")
        org_service = OrganizationService()
        result = org_service.get_assistant_defaults(org_slug)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assistant defaults: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/organizations/{slug}/assistant-defaults",
    tags=["Assistant Management"],
    summary="Update assistant defaults for an organization",
    description="""Updates the organization-scoped assistant_defaults.""",
    dependencies=[Depends(security)]
)
async def update_organization_assistant_defaults(slug: str, request: Request):
    try:
        # Call the core organization assistant defaults update function directly
        logger.info(f"Updating assistant defaults for organization {slug} via direct call")
        # Parse request body
        body = await request.json()
        assistant_defaults = body.get('assistant_defaults', body)
        
        # Use OrganizationService to update defaults
        org_service = OrganizationService()
        result = org_service.update_assistant_defaults(slug, assistant_defaults)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assistant defaults: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

