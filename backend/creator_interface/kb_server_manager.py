import httpx
import os
import logging
import json
import time
import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from fastapi import HTTPException
from .knowledgebase_classes import KnowledgeBaseCreate, KnowledgeBaseUpdate

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Get environment variables
LAMB_KB_SERVER = os.getenv('LAMB_KB_SERVER', None)
LAMB_KB_SERVER_TOKEN = os.getenv('LAMB_KB_SERVER_TOKEN', '0p3n-w3bu!')

# Check if KB server is configured
KB_SERVER_CONFIGURED = LAMB_KB_SERVER is not None and LAMB_KB_SERVER.strip() != ''


class KBServerManager:
    """Class to manage interactions with the Knowledge Base server"""
    
    def __init__(self):
        self.kb_server_url = LAMB_KB_SERVER
        self.kb_server_token = LAMB_KB_SERVER_TOKEN
        self.kb_server_configured = KB_SERVER_CONFIGURED
        
    async def is_kb_server_available(self):
        """Check if KB server is available by making a simple request"""
        if not self.kb_server_configured:
            logger.warning("KB server not configured (LAMB_KB_SERVER env var missing or empty)")
            return False
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.kb_server_url}/health")
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(f"KB server returned non-200 status: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"KB server connectivity check failed: {str(e)}")
            return False
            
    def get_auth_headers(self):
        """Return standard authorization headers for KB server requests"""
        return {
            "Authorization": f"Bearer {self.kb_server_token}"
        }
        
    def get_content_type_headers(self):
        """Return headers with Authorization and Content-Type"""
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        return headers
        
    async def get_user_knowledge_bases(self, creator_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get all knowledge bases for a user from the KB server
        
        Args:
            creator_user: Authenticated user information
            
        Returns:
            List of knowledge base objects
        """
        # Filter collections by owner (user ID instead of email for privacy)
        params = {
            "owner": str(creator_user.get('id'))  # Convert to string as KB server expects string
        }
        
        kb_server_url = f"{self.kb_server_url}/collections"
        logger.info(f"Requesting collections from KB server at {kb_server_url}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    kb_server_url, 
                    headers=self.get_auth_headers(), 
                    params=params
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Get the response data
                    response_data = response.json()
                    logger.info(f"Retrieved response from KB server: {type(response_data)}")
                    
                    # Handle different response formats
                    collections_data = []
                    if isinstance(response_data, list):
                        collections_data = response_data
                    elif isinstance(response_data, dict) and 'collections' in response_data:
                        collections_data = response_data['collections']
                    elif isinstance(response_data, dict) and 'items' in response_data:
                        collections_data = response_data['items']
                    else:
                        logger.warning(f"Unexpected response format from KB server: {type(response_data)}")
                        # Try to extract collections if response is a dict
                        if isinstance(response_data, dict):
                            # Log the keys to help debugging
                            logger.info(f"Response keys: {list(response_data.keys())}")
                            # Try to find a key that might contain collections
                            for key, value in response_data.items():
                                if isinstance(value, list):
                                    collections_data = value
                                    logger.info(f"Using key '{key}' which contains a list of {len(collections_data)} items")
                                    break
                    
                    logger.info(f"Processing {len(collections_data)} collections")
                    
                    # Format the collections properly for frontend
                    knowledge_bases = []
                    
                    for collection in collections_data:
                        # Skip if collection is not a dict
                        if not isinstance(collection, dict):
                            logger.warning(f"Skipping non-dict collection: {collection}")
                            continue
                            
                        # Extract collection data
                        collection_id = str(collection.get('id', ''))
                        collection_name = collection.get('name', '')
                        
                        if not collection_id or not collection_name:
                            logger.warning(f"Skipping collection with missing ID or name: {collection}")
                            continue
                        
                        logger.info(f"Processing collection ID={collection_id}, Name={collection_name}")
                        
                        # Create metadata structure
                        metadata = {
                            'description': collection.get('description', ''),
                            'access_control': collection.get('visibility', 'private')
                        }
                        
                        # Create a properly formatted entry for the frontend
                        kb_entry = {
                            'id': collection_id,
                            'name': collection_name,
                            'owner': collection.get('owner', str(creator_user.get('id', 'unknown'))),
                            'created_at': collection.get('created_at', int(time.time())),
                            'metadata': metadata
                        }
                        knowledge_bases.append(kb_entry)
                        logger.info(f"Successfully processed collection: {collection_name}")
                    
                    logger.info(f"Found {len(knowledge_bases)} knowledge bases for user")
                    return knowledge_bases
                    
                else:
                    logger.error(f"KB server returned non-200 status: {response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"KB server error: {error_detail}"
                    )
            
            except httpx.RequestError as req_err:
                logger.error(f"Error connecting to KB server: {str(req_err)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Unable to connect to KB server: {str(req_err)}"
                )
                
    async def create_knowledge_base(self, kb_data: KnowledgeBaseCreate, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new knowledge base in the KB server
        
        Args:
            kb_data: Knowledge base creation data
            creator_user: Authenticated user information
            
        Returns:
            Dict with created knowledge base information
        """
        logger.info(f"Creating knowledge base via KB server: {kb_data.name}")
        
        # Validate required fields
        if not kb_data.name:
            logger.error("Name is required but not provided")
            raise HTTPException(
                status_code=400,
                detail="Name is required"
            )

   
        # Create collection in KB server
        async with httpx.AsyncClient() as client:
            kb_server_url = f"{self.kb_server_url}/collections"
            logger.info(f"Creating collection in KB server at {kb_server_url}: {kb_data.name}")
            
            # Check if there's metadata with a description field
            # The frontend might send the description in metadata.description rather than directly
            description = kb_data.description or ""
            try:
                # Attempt to extract metadata from the request data
                if hasattr(kb_data, 'metadata') and kb_data.metadata:
                    if isinstance(kb_data.metadata, dict) and 'description' in kb_data.metadata:
                        # Use metadata.description if it's not empty and root description is empty
                        if not description and kb_data.metadata['description']:
                            description = kb_data.metadata['description']
                            logger.info(f"Using description from metadata: {description}")
            except Exception as md_err:
                logger.warning(f"Error extracting metadata description: {str(md_err)}")
                
            # Prepare collection data according to KB server API
            collection_data = {
                "name": kb_data.name,
                "description": description,
                "owner": str(creator_user.get('id')),  # Use ID instead of email for privacy (as string)
                "visibility": kb_data.access_control or "private",
                "embeddings_model": {
                    "model": "default",
                    "vendor": "default",
                    "api_endpoint": "default",
                    "apikey": "default"
                }
            }
            
            # Log the final data being sent to the KB server
            logger.info(f"Sending collection data to KB server: {collection_data}")
            
            try:
                # Send request to KB server
                response = await client.post(
                    kb_server_url, 
                    headers=self.get_content_type_headers(), 
                    json=collection_data
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 201:
                    # Successfully created
                    
                    collection_response = response.json()
                    logger.info(f"KB server created collection with ID: {collection_response.get('id')}")
                    
                    return {
                        "message": "Knowledge base created successfully",
                        "id": collection_response.get('id'),
                        "name": kb_data.name
                    }
                else:
                    # Handle error
                    logger.error(f"KB server returned non-201 status: {response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = response.text or "Unknown error"
                    
                    # Map common errors
                    if response.status_code == 409:
                        error_msg = f"A knowledge base with name '{kb_data.name}' already exists"
                    else:
                        error_msg = f"KB server error: {error_detail}"
                    
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_msg
                    )
            
            except httpx.RequestError as req_err:
                logger.error(f"Error connecting to KB server: {str(req_err)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Unable to connect to KB server: {str(req_err)}"
                )

    async def get_knowledge_base_details(self, kb_id: str, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get details of a specific knowledge base from the KB server
        
        Args:
            kb_id: ID of the knowledge base to retrieve
            creator_user: Authenticated user information
            
        Returns:
            Dict with knowledge base details
        """
        logger.info(f"Getting knowledge base details for ID: {kb_id} from KB server")
        
        async with httpx.AsyncClient() as client:
            # Request collection details
            kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
            logger.info(f"Requesting collection from KB server at {kb_server_url}")
            
            try:
                # Send request to KB server
                response = await client.get(
                    kb_server_url, 
                    headers=self.get_auth_headers()
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Successfully retrieved
                    collection_data = response.json()
                    logger.info(f"Retrieved collection data from KB server for ID: {kb_id}")
                    
                    # Check if collection belongs to the authenticated user
                    if collection_data.get('owner') != str(creator_user.get('id')):
                        # Check if collection is public
                        if collection_data.get('visibility') != 'public':
                            logger.warning(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) tried to access collection {kb_id} owned by {collection_data.get('owner')}")
                            raise HTTPException(
                                status_code=403,
                                detail="You do not have permission to access this knowledge base"
                            )
                    
                    # Get files associated with this collection
                    files_url = f"{self.kb_server_url}/collections/{kb_id}/files"
                    files_response = await client.get(files_url, headers=self.get_auth_headers())
                    
                    files = []
                    if files_response.status_code == 200:
                        files_data = files_response.json()
                        logger.info(f"DEBUG: Raw files data from KB server: {files_data}")
                        for file in files_data:
                            # Skip files that are marked as deleted
                            if file.get('status') == 'deleted':
                                logger.info(f"Skipping deleted file: {file.get('original_filename')} (ID: {file.get('id')})")
                                continue
                                
                            # Improved mapping with fallbacks for different field names
                            file_id = str(file.get('id'))
                            filename = file.get('original_filename', file.get('filename', ''))
                            size = file.get('file_size', file.get('size', 0))
                            content_type = file.get('content_type', file.get('mime_type', 'application/octet-stream'))
                            
                            # Get file URL and combine with base URL if it's a relative path
                            file_url = file.get('file_url', '')
                            if file_url and file_url.startswith('/'):
                                # It's a relative URL, combine with KB server base URL
                                base_url = self.kb_server_url.rstrip('/')
                                file_url = f"{base_url}{file_url}"
                            logger.info(f"DEBUG: File URL: {file_url}")
                            
                            # Handle the created_at field which might be in different formats
                            created_at = None
                            if 'created_at' in file:
                                # If it's a string, try to convert to timestamp
                                if isinstance(file['created_at'], str):
                                    try:
                                        # Remove microseconds if present
                                        created_at_str = file['created_at'].split('.')[0]
                                        # Parse datetime and convert to timestamp
                                        dt = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                                        created_at = int(dt.timestamp())
                                    except Exception as e:
                                        logger.warning(f"Failed to parse created_at: {e}")
                                        created_at = int(time.time())
                                else:
                                    created_at = file['created_at']
                            else:
                                created_at = int(time.time())
                            
                            # Add the file with all the mapped fields
                            files.append({
                                "id": file_id,
                                "filename": filename,
                                "size": size,
                                "content_type": content_type,
                                "created_at": created_at,
                                "file_url": file_url
                            })
                            
                            logger.info(f"DEBUG: Mapped file data: id={file_id}, filename={filename}, size={size}")
                        logger.info(f"Retrieved {len(files)} files for collection {kb_id}")
                    else:
                        logger.warning(f"Failed to retrieve files for collection {kb_id}, status: {files_response.status_code}")
                    
                    # Format the response for the frontend
                    result = {
                        "id": kb_id,
                        "name": collection_data.get('name', ''),
                        "description": collection_data.get('description', ''),
                        "files": files,
                        "metadata": {
                            "description": collection_data.get('description', ''),
                            "access_control": collection_data.get('visibility', 'private')
                        },
                        "owner": collection_data.get('owner', ''),
                        "created_at": collection_data.get('created_at', int(time.time()))
                    }
                    
                    return result
                
                elif response.status_code == 404:
                    logger.error(f"Collection with ID {kb_id} not found in KB server")
                    raise HTTPException(
                        status_code=404,
                        detail=f"Knowledge base with ID {kb_id} not found"
                    )
                else:
                    # Handle other errors
                    logger.error(f"KB server returned non-200 status: {response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"KB server error: {error_detail}"
                    )
            
            except httpx.RequestError as req_err:
                logger.error(f"Error connecting to KB server: {str(req_err)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Unable to connect to KB server: {str(req_err)}"
                )

    async def update_knowledge_base(self, kb_id: str, kb_data: KnowledgeBaseUpdate, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a knowledge base in the KB server
        
        Args:
            kb_id: ID of the knowledge base to update
            kb_data: Knowledge base update data
            creator_user: Authenticated user information
            
            
        Returns:
            Dict with updated knowledge base information
        """
        logger.info(f"Updating knowledge base {kb_id} via KB server")
        
        # Connect to KB server and update the collection
        async with httpx.AsyncClient() as client:
            kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
            logger.info(f"Connecting to KB server at: {kb_server_url} to update collection")
            
            # Log the received data for debugging
            logger.info(f"Received knowledge base update data: {kb_data.dict()}")
            
            # Prepare update data for KB server
            update_data = {}
            if kb_data.name is not None:
                update_data["name"] = kb_data.name
                
            # Handle description field - check both root and metadata
            description = None
            if kb_data.description is not None:
                description = kb_data.description
            
            # Check if we have metadata with a description
            try:
                if hasattr(kb_data, 'metadata') and kb_data.metadata:
                    if isinstance(kb_data.metadata, dict) and 'description' in kb_data.metadata:
                        # Use metadata.description if root description is empty or None
                        if (description is None or description == "") and kb_data.metadata['description']:
                            description = kb_data.metadata['description']
                            logger.info(f"Using description from metadata for update: {description}")
            except Exception as md_err:
                logger.warning(f"Error extracting metadata description during update: {str(md_err)}")
                
            # Set description in update data if we have it
            if description is not None:
                update_data["description"] = description
                    
            # Handle access control/visibility
            if kb_data.access_control is not None:
                update_data["visibility"] = kb_data.access_control
            
            logger.info(f"Updating knowledge base {kb_id} with data: {update_data}")
            
            try:
                # Get current collection data to verify ownership
                get_response = await client.get(kb_server_url, headers=self.get_auth_headers())
                
                if get_response.status_code == 200:
                    collection_data = get_response.json()
                    
                    # Check ownership
                    if collection_data.get('owner') != str(creator_user.get('id')):
                        logger.error(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) is not the owner of knowledge base {kb_id}")
                        raise HTTPException(
                            status_code=403,
                            detail="You don't have permission to update this knowledge base"
                        )
                    
                    # Store original collection name for response
                    collection_name = collection_data.get('name', '')
                    
                    # Send update request to KB server
                    response = await client.patch(
                        kb_server_url, 
                        headers=self.get_content_type_headers(), 
                        json=update_data
                    )
                    logger.info(f"KB server update response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        # Successfully updated
                        updated_data = response.json()
                        logger.info(f"Successfully updated knowledge base {kb_id} in KB server")
                        
                        
                        # Return successful response
                        return {
                            "message": "Knowledge base updated successfully",
                            "id": kb_id,
                            "name": kb_data.name if kb_data.name is not None else collection_name
                        }
                    elif response.status_code == 404:
                        logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                        raise HTTPException(
                            status_code=404,
                            detail="Knowledge base not found"
                        )
                    else:
                        # Handle other errors
                        logger.error(f"KB server returned non-200 status: {response.status_code}")
                        error_detail = "Unknown error"
                        try:
                            error_data = response.json()
                            error_detail = error_data.get('detail', str(error_data))
                        except Exception:
                            error_detail = response.text or "Unknown error"
                        
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"KB server error: {error_detail}"
                        )
                elif get_response.status_code == 404:
                    logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                    raise HTTPException(
                        status_code=404,
                        detail="Knowledge base not found"
                    )
                else:
                    logger.error(f"KB server returned non-200 status when getting collection: {get_response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = get_response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = get_response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=get_response.status_code,
                        detail=f"KB server error: {error_detail}"
                    )
                    
            except httpx.RequestError as req_err:
                logger.error(f"Error connecting to KB server: {str(req_err)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Unable to connect to KB server: {str(req_err)}"
                )

    async def delete_knowledge_base(self, kb_id: str, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a knowledge base from the KB server
        
        Args:
            kb_id: The ID of the knowledge base to delete
            creator_user: The authenticated creator user
            
        Returns:
            Dict with deletion status
        """
        logger.info(f"Deleting knowledge base {kb_id} for user {creator_user.get('email')}")
        
        # Ensure kb_id is properly formatted for the KB server
        try:
            # Try to convert to int if kb_id is a string representing a number
            if kb_id.isdigit():
                numeric_id = int(kb_id)
                logger.info(f"Converting string ID '{kb_id}' to numeric ID {numeric_id}")
                kb_id = str(numeric_id)  # Keep as string for URL but ensure it's a valid number
        except (ValueError, AttributeError):
            # If conversion fails, keep original id
            logger.info(f"Using original ID format: {kb_id}")
        
        kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
        
        try:
            # Try to get collection details from KB server to verify ownership
            async with httpx.AsyncClient() as client:
                logger.info(f"Getting collection details from KB server: {kb_server_url}")
                headers = {
                    "Authorization": f"Bearer {self.kb_server_token}"
                }
                
                get_response = await client.get(kb_server_url, headers=headers)
                
                if get_response.status_code == 200:
                    collection_data = get_response.json()
                    logger.info(f"KB server collection data: {json.dumps(collection_data)}")
                    
                    # Check ownership
                    if collection_data.get('owner') != str(creator_user.get('id')):
                        logger.error(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) is not the owner of knowledge base {kb_id}")
                        raise HTTPException(
                            status_code=403,
                            detail="You don't have permission to delete this knowledge base"
                        )
                    
                    collection_name = collection_data.get('name', '')
                    logger.info(f"Found knowledge base to delete: {collection_name}")
                    
                    # Use PATCH request with status=deleted
                    headers["Content-Type"] = "application/json"
                    logger.info(f"Attempting to mark collection as deleted using PATCH to {kb_server_url}")
                    update_data = {"status": "deleted"}
                    delete_response = await client.patch(kb_server_url, headers=headers, json=update_data)
                    
                    # If PATCH doesn't work, try a special DELETE endpoint as fallback
                    if delete_response.status_code >= 400 and delete_response.status_code != 404:
                        delete_url = f"{self.kb_server_url}/collections/{kb_id}/status"
                        logger.info(f"PATCH failed, trying PUT to update status via {delete_url}")
                        delete_response = await client.put(delete_url, headers=headers, params={"status": "deleted"})
                    
                    logger.info(f"KB server delete response status: {delete_response.status_code}")
                    
                    if delete_response.status_code in [200, 204, 202]:
                        # Successfully deleted from KB server
                        logger.info(f"Successfully deleted knowledge base {kb_id} from KB server")
                        
                        
                        return {
                        "message": "Knowledge base deleted",
                        "id": kb_id
                    }
        
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )

    async def query_knowledge_base(self, kb_id: str, query_data: Dict[str, Any], creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query a knowledge base from the KB server
        
        Args:
            kb_id: The ID of the knowledge base to query
            query_data: The query data including query_text and optional parameters
            creator_user: The authenticated creator user
            
        Returns:
            Dict with query results
        """
        logger.info(f"Querying knowledge base {kb_id} with: {query_data.get('query_text', '')}")
        
        kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                # First check if the user has access to this collection
                logger.info(f"Checking collection access at KB server: {kb_server_url}")
                
                headers = self.get_content_type_headers()
                
                get_response = await client.get(kb_server_url, headers=headers)
                
                if get_response.status_code != 200:
                    if get_response.status_code == 404:
                        logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                        raise HTTPException(
                            status_code=404,
                            detail="Knowledge base not found"
                        )
                    else:
                        logger.error(f"KB server returned error status: {get_response.status_code}")
                        error_detail = "Unknown error"
                        try:
                            error_data = get_response.json()
                            error_detail = error_data.get('detail', str(error_data))
                        except Exception:
                            error_detail = get_response.text or "Unknown error"
                        
                        raise HTTPException(
                            status_code=get_response.status_code,
                            detail=f"KB server error: {error_detail}"
                        )
                
                # Verify ownership or access permission
                collection_data = get_response.json()
                if collection_data.get('owner') != str(creator_user.get('id')):
                    # For queries, we might allow read-only access if the KB has public visibility
                    if collection_data.get('visibility') != 'public':
                        logger.error(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) is not the owner of knowledge base {kb_id}")
                        raise HTTPException(
                            status_code=403,
                            detail="You don't have permission to query this knowledge base"
                        )
                
                # Execute the query against the KB server
                query_url = f"{self.kb_server_url}/collections/{kb_id}/query"
                if query_data.get('plugin_name'):
                    query_url += f"?plugin_name={query_data.get('plugin_name')}"
                
                query_payload = {
                    "query_text": query_data.get('query_text', ''),
                    "plugin_params": query_data.get('plugin_params', {})
                }
                
                logger.info(f"Sending query to KB server: {query_url}")
                query_response = await client.post(query_url, headers=headers, json=query_payload)
                
                if query_response.status_code == 200:
                    # Successfully queried
                    query_result = query_response.json()
                    logger.info(f"Query executed successfully against KB server")
                    
                    # Log the actual response content for debugging
                    logger.info(f"Query response content: {query_result}")

                    # Check if the 'results' key exists and contains data
                    actual_results = query_result.get('results', [])
                    if isinstance(actual_results, list) and actual_results:
                        logger.info(f"Found {len(actual_results)} results in response under 'results' key")
                    else:
                        logger.warning(f"No results found in query response under 'results' key. Response structure: {list(query_result.keys())}")

                    # Return the query results, extracting the list from the 'results' key
                    return {
                        "status": "success",
                        "kb_id": kb_id,
                        "query": query_data.get('query_text', ''),
                        "results": actual_results, # Return the list directly
                        "debug_info": {
                            "response_keys": list(query_result.keys()),
                            "plugin_params": query_data.get('plugin_params', {})
                        }
                    }
                else:
                    # Handle query error
                    logger.error(f"KB server returned error status during query: {query_response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = query_response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = query_response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=query_response.status_code,
                        detail=f"KB server query error: {error_detail}"
                    )
        
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )

    async def upload_files_to_kb(self, kb_id: str, files: List[Any], creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload files to a knowledge base in the KB server
        
        Args:
            kb_id: The ID of the knowledge base to upload files to
            files: List of FastAPI UploadFile objects
            creator_user: The authenticated creator user
            
        Returns:
            Dict with upload results
        """
        logger.info(f"Uploading files to knowledge base {kb_id} via KB server")
        
        kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
        logger.info(f"Checking collection access at KB server: {kb_server_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                # First verify collection exists and user has access
                headers = self.get_auth_headers()
                
                # Get collection details to verify ownership
                get_response = await client.get(kb_server_url, headers=headers)
                
                if get_response.status_code != 200:
                    if get_response.status_code == 404:
                        logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                        raise HTTPException(
                            status_code=404,
                            detail="Knowledge base not found"
                        )
                    else:
                        logger.error(f"KB server returned error status: {get_response.status_code}")
                        error_detail = "Unknown error"
                        try:
                            error_data = get_response.json()
                            error_detail = error_data.get('detail', str(error_data))
                        except Exception:
                            error_detail = get_response.text or "Unknown error"
                        
                        raise HTTPException(
                            status_code=get_response.status_code,
                            detail=f"KB server error: {error_detail}"
                        )
                
                # Verify ownership
                collection_data = get_response.json()
                if collection_data.get('owner') != str(creator_user.get('id')):
                    logger.error(f"User {creator_user.get('email')} is not the owner of knowledge base {kb_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to upload files to this knowledge base"
                    )
                
                collection_name = collection_data.get('name', '')
                logger.info(f"Found knowledge base for upload: {collection_name}")
                
                # Process and upload files to KB server
                uploaded_files = []
                
                # Ensure we have the owner ID as string in the collection data
                if 'owner' in collection_data and collection_data['owner'] != str(creator_user.get('id')):
                    logger.info("Correcting owner field in collection data for KB server")
                    collection_data['owner'] = str(creator_user.get('id'))
                
                for file in files:
                    try:
                        # Prepare the file data
                        content = await file.read()
                        file.file.seek(0)  # Reset file pointer for future read
                        
                        logger.info(f"Uploading file {file.filename} to KB server for collection {kb_id}")
                        
                        # Create multipart/form-data for file upload
                        upload_files = {
                            'file': (file.filename, content, file.content_type or 'application/octet-stream')
                        }
                        
                        # Add collection_id and plugin parameters for file processing
                        form_data = {
                            'collection_id': str(kb_id),  # Explicitly include collection_id as string in the form data
                            'plugin_name': 'simple_ingest',  # Default plugin for processing
                            'chunk_size': '100',
                            'chunk_unit': 'char',
                            'chunk_overlap': '20',
                            'owner': str(creator_user.get('id'))  # Explicitly include owner as string
                        }
                        logger.info(f"Including explicit collection_id={kb_id} and plugin params in form data")
                        
                        # Use ingest-file endpoint instead of upload for proper file registration
                        # This endpoint combines upload, processing and registering in one operation
                        ingest_url = f"{self.kb_server_url}/collections/{str(kb_id)}/ingest-file"
                        
                        # Add detailed debug logging
                        logger.info(f"Ingesting file to collection ID: {kb_id}")
                        logger.info(f"Ingest URL: {ingest_url}")
                        
                        # Make sure headers are defined before use
                        upload_headers = self.get_auth_headers()  # No Content-Type for multipart/form-data
                        
                        # --- Construct and log equivalent curl command ---
                        curl_headers = " ".join([f"-H '{k}: {v}'" for k, v in upload_headers.items()])
                        # Represent file part - NOTE: This assumes the file exists at a path, which isn't true here.
                        # We only have content. Representing with filename as placeholder.
                        file_part_key = list(upload_files.keys())[0] # Should be 'file'
                        file_name_for_curl = upload_files[file_part_key][0]
                        curl_file_part = f"-F '{file_part_key}=@{file_name_for_curl}' # NOTE: File content sent, not path"
                        # Represent other form data parts
                        curl_form_parts = " ".join([f"-F '{k}={v}'" for k, v in form_data.items()])

                        equivalent_curl = f"curl -X POST '{ingest_url}' {curl_headers} {curl_file_part} {curl_form_parts}"
                        logger.info(f"Equivalent curl command:\n{equivalent_curl}")
                        # --- End curl command logging ---

                        # Use a much longer timeout for the ingestion request to prevent timeouts
                        # Create a new client with extended timeout for just this request
                        async with httpx.AsyncClient(timeout=300.0) as ingestion_client:  # 5 minutes timeout
                            logger.info(f"Sending ingestion request with extended timeout (300s)")
                            ingest_response = await ingestion_client.post(
                                ingest_url, 
                                headers=upload_headers, 
                                files=upload_files,
                                data=form_data  # Include the form data with collection_id and plugin params
                            )
                        
                        if ingest_response.status_code == 200 or ingest_response.status_code == 201:
                            # Successfully uploaded
                            file_data = ingest_response.json()
                            logger.info(f"File {file.filename} ingested successfully to KB server with ID {file_data.get('id')}")
                            logger.info(f"Response data: {file_data}")
                            
                            # Add to list of successfully uploaded files
                            uploaded_files.append({
                                "id": str(file_data.get('id')),
                                "filename": file.filename,
                                "size": len(content),
                                "content_type": file.content_type or 'application/octet-stream'
                            })
                        else:
                            # Handle upload error
                            logger.error(f"KB server returned error status during file ingestion: {ingest_response.status_code}")
                            error_detail = "Unknown error"
                            try:
                                error_data = ingest_response.json()
                                error_detail = error_data.get('detail', str(error_data))
                            except Exception:
                                error_detail = ingest_response.text or "Unknown error"
                            
                            raise HTTPException(
                                status_code=ingest_response.status_code,
                                detail=f"KB server file ingestion error: {error_detail}"
                            )
                            
                    except HTTPException as he:
                        # Re-raise HTTP exceptions
                        raise he
                    except Exception as e:
                        error_msg = f"Error processing file {file.filename}: {str(e)}"
                        logger.error(error_msg)
                        raise HTTPException(
                            status_code=500,
                            detail=error_msg
                        )
                
                return {
                    "message": f"Successfully uploaded {len(uploaded_files)} files to knowledge base",
                    "knowledge_base_id": kb_id,
                    "uploaded_files": uploaded_files
                }
                
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )

    async def delete_file_from_kb(self, kb_id: str, file_id: str, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a file from a knowledge base in the KB server
        
        Args:
            kb_id: The ID of the knowledge base containing the file
            file_id: The ID of the file to delete
            creator_user: The authenticated creator user
            
        Returns:
            Dict with deletion status
        """
        logger.info(f"Deleting file {file_id} from knowledge base {kb_id} via KB server")
        
        kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
        logger.info(f"Checking collection access at KB server: {kb_server_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                # First verify collection exists and user has access
                headers = self.get_auth_headers()
                
                # Get collection details to verify ownership
                get_response = await client.get(kb_server_url, headers=headers)
                
                if get_response.status_code != 200:
                    if get_response.status_code == 404:
                        logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                        raise HTTPException(
                            status_code=404,
                            detail="Knowledge base not found"
                        )
                    else:
                        logger.error(f"KB server returned error status: {get_response.status_code}")
                        error_detail = "Unknown error"
                        try:
                            error_data = get_response.json()
                            error_detail = error_data.get('detail', str(error_data))
                        except Exception:
                            error_detail = get_response.text or "Unknown error"
                        
                        raise HTTPException(
                            status_code=get_response.status_code,
                            detail=f"KB server error: {error_detail}"
                        )
                
                # Verify ownership
                collection_data = get_response.json()
                if collection_data.get('owner') != str(creator_user.get('id')):
                    logger.error(f"User {creator_user.get('email')} is not the owner of knowledge base {kb_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to delete files from this knowledge base"
                    )
                
                # Now mark the file as deleted in KB server using the correct endpoint
                status_url = f"{self.kb_server_url}/collections/files/{file_id}/status?status=deleted"
                logger.info(f"Marking file as deleted in KB server at: {status_url}")
                
                status_response = await client.put(status_url, headers=headers)
                logger.info(f"KB server status update response status: {status_response.status_code}")
                
                if status_response.status_code == 200:
                    # Successfully marked file as deleted
                    logger.info(f"Successfully marked file {file_id} as deleted in knowledge base {kb_id}")
                    
                    return {
                        "message": "File deleted successfully",
                        "knowledge_base_id": kb_id,
                        "file_id": file_id
                    }
                elif status_response.status_code == 404:
                    logger.error(f"File {file_id} not found in knowledge base {kb_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"File not found in knowledge base"
                    )
                else:
                    # Handle other errors
                    logger.error(f"KB server returned error status during file deletion: {status_response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = status_response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = status_response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=status_response.status_code,
                        detail=f"KB server file deletion error: {error_detail}"
                    )
                
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )

    async def get_ingestion_plugins(self) -> Dict[str, Any]:
        """
        Get a list of available ingestion plugins and their parameters
        
        Returns:
            Dict with plugin information including supported file extensions and parameters
        """
        logger.info("Getting available ingestion plugins from KB server")
        
        plugins_url = f"{self.kb_server_url}/ingestion/plugins"
        
        try:
            async with httpx.AsyncClient() as client:
                headers = self.get_auth_headers()
                
                response = await client.get(plugins_url, headers=headers)
                
                if response.status_code == 200:
                    plugins_data = response.json()
                    logger.info(f"Successfully retrieved {len(plugins_data)} ingestion plugins")
                    return plugins_data
                else:
                    logger.error(f"KB server returned error status: {response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"KB server error fetching plugins: {error_detail}"
                    )
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )

    async def plugin_ingest_file(self, kb_id: str, file: Any, plugin_name: str, plugin_params: Dict[str, Any], creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload and ingest a file using a specific plugin
        
        Args:
            kb_id: The ID of the knowledge base
            file: FastAPI UploadFile object
            plugin_name: Name of the ingestion plugin to use
            plugin_params: Parameters for the ingestion plugin
            creator_user: The authenticated creator user
            
        Returns:
            Dict with ingestion results
        """
        logger.info(f"Ingesting file {file.filename} to knowledge base {kb_id} using plugin {plugin_name}")
        
        # First check if user has access to the knowledge base
        kb_server_url = f"{self.kb_server_url}/collections/{kb_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                # Verify collection exists and user has access
                headers = self.get_auth_headers()
                
                # Check ownership
                get_response = await client.get(kb_server_url, headers=headers)
                
                if get_response.status_code != 200:
                    if get_response.status_code == 404:
                        logger.error(f"Knowledge base with ID {kb_id} not found in KB server")
                        raise HTTPException(
                            status_code=404,
                            detail="Knowledge base not found"
                        )
                    else:
                        logger.error(f"KB server returned error status: {get_response.status_code}")
                        error_detail = "Unknown error"
                        try:
                            error_data = get_response.json()
                            error_detail = error_data.get('detail', str(error_data))
                        except Exception:
                            error_detail = get_response.text or "Unknown error"
                        
                        raise HTTPException(
                            status_code=get_response.status_code,
                            detail=f"KB server error: {error_detail}"
                        )
                
                # Verify ownership
                collection_data = get_response.json()
                if collection_data.get('owner') != str(creator_user.get('id')):
                    logger.error(f"User {creator_user.get('email')} is not the owner of knowledge base {kb_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to upload files to this knowledge base"
                    )
                
                # Prepare the file data
                content = await file.read()
                file.file.seek(0)  # Reset file pointer for future read
                
                # Create multipart/form-data for file upload
                upload_files = {
                    'file': (file.filename, content, file.content_type or 'application/octet-stream')
                }
                
                logger.info(f"Using plugin {plugin_name} with parameters: {plugin_params}")
                
                # Use ingest-file endpoint instead of ingest (same as in upload_files_to_kb method)
                ingest_url = f"{self.kb_server_url}/collections/{kb_id}/ingest-file"
                logger.info(f"Ingesting file to KB server at: {ingest_url}")
                
                # Add owner and collection_id to form data - match format used in upload_files_to_kb
                form_data = {
                    'collection_id': str(kb_id),
                    'owner': str(creator_user.get('id')),
                    'plugin_name': plugin_name
                }

                # The 'plugin_params' dictionary contains parameters specific to the selected
                # 'plugin_name'. These parameters are dynamically extracted from the incoming
                # request form data by the knowledges_router.
                # The KB server's '/ingest-file' endpoint documentation specifies that these
                # variable parameters must be sent as a single JSON string within a form
                # field named 'plugin_params'. Therefore, we serialize the dictionary here.
                if plugin_params:
                    try:
                        form_data['plugin_params'] = json.dumps(plugin_params)
                        logger.info(f"Serialized plugin_params: {form_data['plugin_params']}")
                    except TypeError as json_err:
                        logger.error(f"Could not serialize plugin_params to JSON: {json_err}")
                        # Decide how to handle: raise error, send empty, or skip? Let's skip for now.
                        pass # Or raise an appropriate HTTPException

                # Log the exact parameters being sent to debug the plugin name issue
                logger.info(f"Sending plugin_name: '{plugin_name}' (type: {type(plugin_name)})")
                logger.info(f"Form data: {form_data}")

                # Make sure headers are defined before use
                upload_headers = self.get_auth_headers()  # No Content-Type for multipart/form-data
                logger.info(f"Final Form data being sent: {form_data}") # Log final form data

                # --- Construct and log equivalent curl command ---
                curl_headers = " ".join([f"-H '{k}: {v}'" for k, v in upload_headers.items()])
                # Represent file part - NOTE: This assumes the file exists at a path, which isn't true here.
                # We only have content. Representing with filename as placeholder.
                file_part_key = list(upload_files.keys())[0] # Should be 'file'
                file_name_for_curl = upload_files[file_part_key][0]
                curl_file_part = f"-F '{file_part_key}=@{file_name_for_curl}' # NOTE: File content sent, not path"
                # Represent other form data parts
                curl_form_parts = " ".join([f"-F '{k}={v}'" for k, v in form_data.items()])

                equivalent_curl = f"curl -X POST '{ingest_url}' {curl_headers} {curl_file_part} {curl_form_parts}"
                logger.info(f"Equivalent curl command:\n{equivalent_curl}")
                # --- End curl command logging ---

                # Make a direct single call to the ingest-file endpoint
                ingest_response = await client.post(
                    ingest_url,
                    headers=upload_headers,
                    files=upload_files,
                    data=form_data
                )
                
                if ingest_response.status_code in [200, 201]:
                    # Successfully ingested
                    ingest_data = ingest_response.json()
                    logger.info(f"File {file.filename} ingested successfully using plugin {plugin_name}")
                    logger.info(f"Ingest response: {ingest_data}")
                    
                    # Build the result response
                    result = {
                        "status": "success",
                        "message": f"File successfully ingested using plugin {plugin_name}",
                        "file": {
                            "id": str(ingest_data.get('id', 'unknown')),
                            "filename": file.filename,
                            "size": len(content),
                            "content_type": file.content_type or 'application/octet-stream',
                            "plugin_used": plugin_name
                        }
                    }
                    
                    # Add any additional data from the ingest response
                    if isinstance(ingest_data, dict):
                        if 'documents' in ingest_data:
                            result['document_count'] = len(ingest_data.get('documents', []))
                        if 'chunks' in ingest_data:
                            result['chunk_count'] = len(ingest_data.get('chunks', []))
                    
                    return result
                else:
                    # Handle ingestion error
                    logger.error(f"KB server returned error status during file ingestion: {ingest_response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = ingest_response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = ingest_response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=ingest_response.status_code,
                        detail=f"KB server file ingestion error: {error_detail}"
                    )
                    
        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to connect to KB server: {str(req_err)}"
            )
