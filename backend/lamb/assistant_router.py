from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import ValidationError, BaseModel
from utils.pipelines.auth import get_current_user
import os
from fastapi.responses import FileResponse, JSONResponse
from .database_manager import LambDatabaseManager
from fastapi import File, UploadFile
from .lamb_classes import Assistant
from fastapi.templating import Jinja2Templates
from pathlib import Path
from config import API_KEY  # Import API_KEY from config
import config
from lamb.logging_config import get_logger
from .owi_bridge.owi_group import OwiGroupManager
from .owi_bridge.owi_users import OwiUserManager
from .owi_bridge.owi_model import OWIModel
from .owi_bridge.owi_database import OwiDatabaseManager
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import time  # Add this import for the timestamp

# --- Pydantic Models (Moved to Top) --- #

class AssistantGetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner: str
    api_callback: Optional[str]  # Kept for backward compatibility
    metadata: Optional[str]  # New field - source of truth
    system_prompt: Optional[str]
    prompt_template: Optional[str]
    RAG_endpoint: Optional[str]
    RAG_Top_k: Optional[int]
    RAG_collections: Optional[str]
    pre_retrieval_endpoint: Optional[str]
    post_retrieval_endpoint: Optional[str]
    group_id: Optional[str]
    group_name: Optional[str]
    oauth_consumer_name: Optional[str]
    published_at: Optional[int]
    published: bool = False # Added field with default
    created_at: Optional[int] = None  # Unix timestamp in seconds
    updated_at: Optional[int] = None  # Unix timestamp in seconds

class AssistantListResponse(BaseModel):
    """Response model for paginated list of assistants."""
    assistants: List[AssistantGetResponse]
    total_count: int

# --- End Pydantic Models --- #

# Note: LAMB host and bearer token configuration moved to config.py
# These variables are not used in this module

db_manager = LambDatabaseManager()

# Set up logger for assistant router
logger = get_logger(__name__, component="API")

assistant_router = APIRouter(tags=["Assistants"])
templates = Jinja2Templates(directory="lamb/templates")

# Dependency for API key authentication
async def verify_token(request: Request):
    # Check API Key
    # api_key = request.headers.get("X-API-KEY")
    # if api_key != API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid API Key")

    # Check Bearer Token (replace with actual validation logic if needed)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header") # Use logger
        # Allow request if API key is valid or no auth is strictly required for this endpoint
        # For now, let's assume some endpoints might not need a bearer token if API Key is primary
        # If Bearer token is mandatory, raise HTTPException here.
        # raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")
        pass # Temporarily allowing pass-through if Bearer token is missing

    # Placeholder for actual token verification logic if needed
    # token = auth_header.split(" ")[1]
    # if not verify_actual_token(token):
    #     raise HTTPException(status_code=401, detail="Invalid Bearer token")

    return True


@assistant_router.post("/create_assistant")
async def create_assistant(request: Request, current_user: str = Depends(get_current_user)):
    try:
        logging.info("Starting create_assistant endpoint")
        assistant_data = await request.json()
        logging.debug(f"Received assistant data: {assistant_data}")
        assistant_data.pop('id', None)
        logging.debug(f"Assistant data after removing id: {assistant_data}")

        # Create the Assistant object
        logging.info("Creating Assistant object")
        try:
            assistant = Assistant(**assistant_data)
            logging.debug(f"Created Assistant object: {assistant}")
        except Exception as e:
            logging.error(f"Error creating Assistant object: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Error creating Assistant object: {str(e)}"
            )

        # Check for whitespace and special characters in the assistant name
        import re
        if not re.match("^[a-zA-Z0-9_-]*$", assistant_data['name']):
            logging.warning(
                f"Invalid assistant name: {assistant_data['name']}")
            raise HTTPException(
                status_code=422,
                detail="Assistant name can only contain letters, numbers, underscores and hyphens. No spaces or special characters allowed."
            )

        logging.info("Adding assistant to database")
        try:
            logging.debug(
                f"Assistant object before database insert: {assistant.dict()}")
            assistant_id = db_manager.add_assistant(assistant)
            logging.debug(
                f"Database operation completed. Returned ID: {assistant_id}")
            if assistant_id is None:
                logging.error(
                    "Database operation returned None for assistant_id")
                raise HTTPException(
                    status_code=409,
                    detail=f"An assistant named '{assistant.name}' already exists for this owner. Please choose a different name."
                )
            logging.debug(f"Added assistant with ID: {assistant_id}")
        except Exception as e:
            logging.error(f"Error adding assistant to database: {str(e)}")
            logging.error("Database error details:", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error adding assistant to database: {str(e)}"
            )



        if assistant_id:
            logging.info(
                f"Successfully created assistant with ID: {assistant_id}")
            return {"assistant_id": assistant_id}
        else:
            logging.error("Failed to create assistant - no ID returned")
            raise HTTPException(
                status_code=500, detail="Failed to create assistant")
    except ValidationError as ve:
        logging.error(f"Validation error: {str(ve)}")
        raise HTTPException(
            status_code=422, detail=f"Validation error: {str(ve)}")
    except Exception as e:
        logging.error(
            f"Unexpected error in create_assistant: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")

# Add more assistant-related endpoints as needed

@assistant_router.get("/get_assistant_by_id/{assistant_id}")
async def get_assistant(assistant_id: int, current_user: str = Depends(get_current_user)):
 #   logging.debug(f"Getting assistant {assistant_id} for user: {current_user}")
    try:
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if assistant:
            # Create an Assistant object from the retrieved data
            return {"assistant": assistant.dict()}
        else:
            raise HTTPException(status_code=404, detail="Assistant not found")
    except Exception as e:
        logging.error(f"Error getting assistant: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get assistant: {str(e)}")

@assistant_router.get("/get_assistant_by_name/{assistant_name}")
async def get_assistant_by_name(assistant_name: str, owner: str, current_user: str = Depends(get_current_user)):
    #    logging.debug(f"Getting assistant {assistant_name} for user: {current_user}")
    try:
        assistant = db_manager.get_assistant_by_name(assistant_name, owner)
        if assistant:
            return {"assistant": assistant.dict()}
        else:
            raise HTTPException(status_code=404, detail="Assistant not found")
    except Exception as e:
        logging.error(f"Error getting assistant: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get assistant: {str(e)}")

@assistant_router.get("/get_list_of_assistants/{owner}")
async def get_list_of_assistants(owner: str, current_user: str = Depends(get_current_user)):
    logging.debug(f"Getting list of assistants for user: {current_user}")
    try:
        assistants = db_manager.get_list_of_assistants(owner)
        # Return empty list if no assistants found instead of raising 404
        return {"assistants": assistants or []}
    except Exception as e:
        logging.error(f"Error getting assistants: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get assistants: {str(e)}")

@assistant_router.get("/get_list_of_all_assistants")
async def get_list_of_all_assistants(current_user: str = Depends(get_current_user)):
    logging.debug(f"Getting list of all assistants for user: {current_user}")
    try:
        # Get all assistants with publication data in one query
        assistants = db_manager.get_all_assistants_with_publication()
        
        # The get_all_assistants_with_publication method handles the correct 'published' flag calculation
        # and returns a list of dictionaries with publication data merged, so there's no need
        # for manual merging of data from different tables anymore.
        
        # If there are no assistants, return an empty list
        return {"assistants": assistants or []}
    except Exception as e:
        logging.error(f"Error getting assistants: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get assistants: {str(e)}")

@assistant_router.delete("/delete_assistant/{assistant_id}")
async def delete_assistant(assistant_id: int, owner: str, current_user: str = Depends(get_current_user)):
    logging.debug(
        f"Deleting assistant {assistant_id} for user: {current_user}")
    try:
        # First verify that the assistant exists and belongs to the owner
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
            
        if assistant.owner != owner:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this assistant"
            )
            
        success = db_manager.delete_assistant(assistant_id, owner)
        if success:
            # Clean up associated OWI group
            from .owi_bridge.owi_group import OwiGroupManager
            try:
                group_manager = OwiGroupManager()
                group_name = f"assistant_{assistant_id}"
                groups = group_manager.get_all_groups()
                for group in groups:
                    if group.get('name') == group_name:
                        group_manager.delete_group(group['id'])
                        logging.info(f"Deleted OWI group {group_name} for assistant {assistant_id}")
                        break
            except Exception as e:
                logging.warning(f"Could not delete OWI group for assistant {assistant_id}: {e}")
            
            return {"message": "Assistant deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete assistant")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting assistant: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete assistant: {str(e)}")

@assistant_router.get("/")
async def read_assistant(request: Request):
    return templates.TemplateResponse("assistants.html", {"request": request, "api_key": API_KEY})

@assistant_router.get("/get_published_assistants")
async def get_published_assistants(current_user: str = Depends(get_current_user)):
    """Get list of published assistants"""
    try:
        # Add debug logging
        logging.debug("Getting published assistants from database")
        published_assistants = db_manager.get_published_assistants()
        logging.debug(f"Published assistants from DB: {published_assistants}")

        if published_assistants:
            return published_assistants
        else:
            return []

    except Exception as e:
        logging.error(f"Error getting published assistants: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@assistant_router.get("/get_assistant_with_publication/{assistant_id}")
async def get_assistant_with_publication(assistant_id: int, current_user: str = Depends(get_current_user)):
    """Get a specific assistant with publication status and correctly calculated 'published' field"""
    try:
        # Get assistant with publication data
        assistant = db_manager.get_assistant_by_id_with_publication(assistant_id)
        
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
            
        # The assistant data already includes all needed fields and the correctly calculated 'published' flag
        return {"assistant": assistant}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error getting assistant with publication: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get assistant: {str(e)}")

@assistant_router.delete("/unpublish_assistant/{assistant_id}/{group_id}")
async def unpublish_assistant(
    assistant_id: int,
    group_id: str,
    user_email: str,
    current_user: str = Depends(get_current_user)
):
    """Unpublish an assistant from a group"""
    try:
        # First verify that the assistant belongs to the current user
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        if assistant.owner != user_email:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to unpublish this assistant"
            )

        # Delete the group using OWI bridge
        group_manager = OwiGroupManager()
        group_deleted = group_manager.delete_group(group_id)

        if not group_deleted:
            raise HTTPException(
                status_code=500, detail="Failed to delete group")

        # Remove the publish record from our database
        success = db_manager.unpublish_assistant(assistant_id, group_id)

        if success:
            return {"message": "Assistant unpublished successfully"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to unpublish assistant")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error unpublishing assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@assistant_router.put("/update_assistant/{assistant_id}")
async def update_assistant(assistant_id: int, request: Request, current_user: str = Depends(get_current_user)):
    try:
        logging.info(
            f"Starting update_assistant endpoint for ID: {assistant_id}")
        assistant_data = await request.json()
        logging.debug(f"Received assistant data: {assistant_data}")

        # Create the Assistant object
        logging.info("Creating Assistant object")
        try:
            assistant = Assistant(**assistant_data)
            logging.debug(f"Created Assistant object: {assistant}")
        except Exception as e:
            logging.error(f"Error creating Assistant object: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Error creating Assistant object: {str(e)}"
            )

        # Check for whitespace and special characters in the assistant name
        import re
        if not re.match("^[a-zA-Z0-9_-]*$", assistant_data['name']):
            logging.warning(
                f"Invalid assistant name: {assistant_data['name']}")
            raise HTTPException(
                status_code=422,
                detail="Assistant name can only contain letters, numbers, underscores and hyphens. No spaces or special characters allowed."
            )

        logging.info("Updating assistant in database")
        try:
            logging.debug(
                f"Assistant object before database update: {assistant.dict()}")
            success = db_manager.update_assistant(assistant_id, assistant)
            if not success:
                logging.error("Failed to update assistant")
                raise HTTPException(
                    status_code=404,
                    detail=f"Assistant with ID {assistant_id} not found or could not be updated"
                )
            logging.debug(f"Updated assistant with ID: {assistant_id}")
        except Exception as e:
            logging.error(f"Error updating assistant: {str(e)}")
            logging.error("Database error details:", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error updating assistant: {str(e)}"
            )

        # Reload pipelines
       
        return {"success": True, "message": "Assistant updated successfully"}
    except ValidationError as ve:
        logging.error(f"Validation error: {str(ve)}")
        raise HTTPException(
            status_code=422, detail=f"Validation error: {str(ve)}")
    except Exception as e:
        logging.error(
            f"Unexpected error in update_assistant: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")

@assistant_router.delete("/soft_delete_assistant/{assistant_id}")
async def soft_delete_assistant(
    assistant_id: int,
    current_user: str = Depends(get_current_user)
):
    """
    Soft delete an assistant by:
    1. Changing owner to deleted_assistant@owi.com
    2. If published, removing all users from associated group
    """
    try:
        admin_email = config.OWI_ADMIN_EMAIL
        # First get the assistant to verify it exists
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(
                status_code=404,
                detail="Assistant not found"
            )

        # Get published info if exists
        published_info = db_manager.get_published_assistants()
        published_record = next(
            (p for p in published_info if p['assistant_id'] == assistant_id),
            None
        ) if published_info else None

        # If assistant is published, remove all users from group
        if published_record:
            group_id = published_record['group_id']
            group_manager = OwiGroupManager()

            # Get all users in group
            group_users = group_manager.get_group_users(group_id)
            if group_users:
                for user in group_users:
                    group_manager.remove_user_from_group(
                        group_id, user['id'])

        # Update assistant owner to admin and make name unique to avoid conflicts
        import time
        unique_suffix = f"_deleted_{int(time.time())}"
        deleted_name = f"{assistant.name}{unique_suffix}"
        
        success = db_manager.update_assistant(assistant_id, Assistant(
            name=deleted_name,  # Make name unique to avoid UNIQUE constraint violations
            description=assistant.description or "",
            owner="deleted_assistant@owi.com",  # Change owner to deleted_assistant@owi.com
            api_callback=assistant.api_callback or "",
            system_prompt=assistant.system_prompt or "",
            prompt_template=assistant.prompt_template or "",
            RAG_endpoint=assistant.RAG_endpoint or "",
            RAG_Top_k=assistant.RAG_Top_k or 5,
            RAG_collections=assistant.RAG_collections or "",
            pre_retrieval_endpoint=assistant.pre_retrieval_endpoint or "",
            post_retrieval_endpoint=assistant.post_retrieval_endpoint or ""
        ))

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update assistant owner"
            )

        return {"message": "Assistant soft deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error soft deleting assistant: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error soft deleting assistant: {str(e)}"
        )

async def query_rag(collection_name: str, query: str, k: int = 5) -> Dict[str, Any]:
    """
    Query OpenWebUI's RAG endpoint for relevant documents

    Args:
        collection_name: The collection to query
        query: The search query
        k: Number of results to return

    Returns:
        Dict containing context and sources
    """
    OWI_BASE_URL = config.OWI_BASE_URL
    user_manager = OwiUserManager()
    api_token = user_manager.get_admin_user_token()

    if not api_token:
        raise HTTPException(
            status_code=500,
            detail="Failed to get admin token for RAG query"
        )

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        url = f"{OWI_BASE_URL}/api/v1/retrieval/query/doc"

        payload = {
            "collection_name": collection_name,
            "query": query,
            "k": k
        }

        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                logging.error(
                    f"RAG query failed. Status: {response.status}, Response: {error_text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"RAG query failed: {error_text}"
                )

            result = await response.json()

            # Format the response to match expected RAG context format
            context = ""
            sources = []

            # Process each document and its metadata
            for i in range(len(result.get("documents", [[]])[0])):
                doc = result["documents"][0][i]
                metadata = result["metadatas"][0][i] if result.get(
                    "metadatas") else {}
                distance = result["distances"][0][i] if result.get(
                    "distances") else 1.0

                # Add document content to context
                context += f"\n{doc}"

                # Add source information
                sources.append({
                    "source": metadata.get("source", "unknown"),
                    "content": doc,
                    "score": 1 - distance  # Convert distance to similarity score
                })

            return {
                "context": context.strip(),
                "sources": sources
            }

@assistant_router.put("/update_assistant_publication/{assistant_id}")
async def update_assistant_publication(
    assistant_id: int,
    group_name: str = Query(...),
    oauth_consumer_name: str = Query(...),
    current_user: str = Depends(get_current_user)
):
    """
    Update the publication status of an assistant.
    This adds or updates a record in the LAMB_assistant_publish table.
    """
    try:
        logging.info(
            f"Updating publication for assistant {assistant_id} by user {current_user}")

        # Get the assistant details
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            logging.error(f"Assistant {assistant_id} not found")
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Log the assistant owner and current user for debugging
        logging.info(
            f"Assistant owner: {assistant.owner}, Current user: {current_user}")

        # Get existing publication info if it exists
        published_info = db_manager.get_published_assistants()
        existing_pub = next(
            (p for p in published_info if p['assistant_id'] == assistant_id),
            None
        ) if published_info else None

        # If publication exists, use its group_id, otherwise generate new one
        group_id = existing_pub['group_id'] if existing_pub else f"assistant_{assistant_id}"

        # First try to update if publication exists
        if existing_pub:
            updated = db_manager.update_assistant_publication(
                assistant_id=assistant_id,
                group_id=group_id,  # Keep existing group_id
                group_name=group_name,
                oauth_consumer_name=oauth_consumer_name
            )

            if updated:
                logging.info(
                    f"Successfully updated publication for assistant {assistant_id}")
                return {"message": "Assistant publication updated successfully"}

        # If no existing publication or update fails, create new one
        logging.info(f"Creating new publication for assistant {assistant_id}")
        published = db_manager.publish_assistant(
            assistant_id=assistant_id,
            assistant_name=assistant.name,
            assistant_owner=assistant.owner,
            group_id=group_id,
            group_name=group_name,
            oauth_consumer_name=oauth_consumer_name
        )

        if published:
            logging.info(f"Successfully published assistant {assistant_id}")
            return {"message": "Assistant published successfully"}
        else:
            logging.error(f"Failed to publish assistant {assistant_id}")
            raise HTTPException(
                status_code=500, detail="Failed to publish assistant")

    except Exception as e:
        logging.error(f"Error updating assistant publication: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error updating assistant publication: {str(e)}")

# Define the route for getting assistants by owner (using assistant_router)
@assistant_router.get(
    "/get_assistants_by_owner/{owner}",
    tags=["Assistants"],
    summary="Get Assistants by Owner with Publication Status",
    description="Retrieves a paginated list of assistants owned by a specific user, including their publication status.",
    response_model=AssistantListResponse, # Use the model defined at the top
    dependencies=[Depends(verify_token)] # Assuming verify_token handles auth
)
async def get_assistants_by_owner(
    owner: str,
    limit: int = Query(10, ge=1, le=100, description="Number of assistants per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Retrieves a paginated list of assistants for a given owner, merging with publication data."""
    try:
        # Use the new paginated database method
        assistants_list, total_count = db_manager.get_assistants_by_owner_paginated(owner, limit, offset)

        # --- Add Logging --- #
        #logger.info(f"Core API: Fetched {len(assistants_list)} assistants for owner '{owner}' from DB (total: {total_count})")
        #logger.debug(f"Core API: Assistants before validation: {assistants_list}")
        # --- End Logging --- #

        if not assistants_list and offset == 0: # Check if owner exists but has no assistants
            # Optionally check if the owner email is valid if needed
            pass # Or return 404 if owner itself is not found

        # Pydantic will automatically handle validation based on the response_model
        validated_assistants = [AssistantGetResponse(**asst) for asst in assistants_list]

        # --- Add Logging --- #
        #logger.debug(f"Core API: Assistants after validation: {validated_assistants}")
        # --- End Logging --- #

        return AssistantListResponse(assistants=validated_assistants, total_count=total_count)

    except ValidationError as e:
        logger.error(f"Data validation error for owner {owner}: {e}") # Use logger
        raise HTTPException(
            status_code=500, detail="Internal data validation error")
    except Exception as e:
        logger.error(f"Error getting assistants for owner {owner}: {e}") # Use logger
        raise HTTPException(
            status_code=500, detail=f"Error retrieving assistants: {str(e)}")
