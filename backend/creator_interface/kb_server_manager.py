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
from utils.name_sanitizer import sanitize_name

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
        # Keep global fallback values but don't store as instance variables
        self.global_kb_server_url = LAMB_KB_SERVER
        self.global_kb_server_token = LAMB_KB_SERVER_TOKEN
        self.kb_server_configured = KB_SERVER_CONFIGURED
    
    def _get_kb_config_for_user(self, creator_user: Dict[str, Any]) -> Dict[str, str]:
        """
        Resolve KB server configuration based on user's organization.
        Uses organization-specific config if available, falls back to environment variables.
        
        Args:
            creator_user: Dict containing user information with 'email' and 'organization_id'
            
        Returns:
            Dict with 'url' and 'token' keys for KB server connection
        """
        from lamb.completions.org_config_resolver import OrganizationConfigResolver
        
        user_email = creator_user.get('email')
        if not user_email:
            logger.warning("No email in creator_user, falling back to global KB config")
            return {
                'url': self.global_kb_server_url or 'http://localhost:9090',
                'token': self.global_kb_server_token or '0p3n-w3bu!'
            }
        
        try:
            # Resolve organization-specific configuration
            config_resolver = OrganizationConfigResolver(user_email)
            kb_config = config_resolver.get_knowledge_base_config()
            
            if kb_config and kb_config.get('server_url'):
                org_name = config_resolver.organization.get('name', 'Unknown')
                logger.info(f"Using organization-specific KB config for user {user_email} (org: {org_name})")
                return {
                    'url': kb_config.get('server_url'),
                    'token': kb_config.get('api_token', '0p3n-w3bu!')
                }
            else:
                logger.info(f"No organization KB config for {user_email}, using global config")
                
        except Exception as e:
            logger.warning(f"Error resolving organization KB config for {user_email}: {e}, falling back to global")
        
        # Fallback to global environment variables
        return {
            'url': self.global_kb_server_url or 'http://localhost:9090',
            'token': self.global_kb_server_token or '0p3n-w3bu!'
        }
        
    async def is_kb_server_available(self, creator_user: Dict[str, Any] = None):
        """Check if KB server is available by making a simple request"""
        if not self.kb_server_configured:
            logger.warning("KB server not configured (LAMB_KB_SERVER env var missing or empty)")
            return False
        
        # Get KB config for user (or use global if no user provided)
        if creator_user:
            kb_config = self._get_kb_config_for_user(creator_user)
            kb_server_url = kb_config['url']
        else:
            kb_server_url = self.global_kb_server_url
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{kb_server_url}/health")
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(f"KB server returned non-200 status: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"KB server connectivity check failed: {str(e)}")
            return False
            
    def _get_auth_headers(self, kb_token: str):
        """Return standard authorization headers for KB server requests"""
        return {
            "Authorization": f"Bearer {kb_token}"
        }
        
    def _get_content_type_headers(self, kb_token: str):
        """Return headers with Authorization and Content-Type"""
        headers = self._get_auth_headers(kb_token)
        headers["Content-Type"] = "application/json"
        return headers
        
    async def get_user_knowledge_bases(self, creator_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get user's OWNED knowledge bases only.
        Includes auto-registration of missing KBs and lazy cleanup of stale entries.
        
        Args:
            creator_user: Authenticated user information
            
        Returns:
            List of owned knowledge base objects with LAMB metadata (is_owner=true, is_shared, can_modify=true)
        """
        from lamb.database_manager import LambDatabaseManager
        
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        db_manager = LambDatabaseManager()
        user_id = creator_user.get('id')
        org_id = creator_user.get('organization_id')
        
        # Step 1: Fetch user's owned KBs from KB Server (for auto-registration)
        owned_kbs = await self._fetch_owned_kbs_from_kb_server(creator_user)
        
        # Step 2: Auto-register missing KBs
        for kb in owned_kbs:
            kb_id = str(kb.get('id', ''))
            kb_name = kb.get('name', '')
            if kb_id and kb_name:
                if not db_manager.get_kb_registry_entry(kb_id):
                    logger.info(f"Auto-registering KB {kb_id} ('{kb_name}') on first access")
                    # Try to preserve original creation date from KB server if available
                    creation_date = None
                    if 'creation_date' in kb:
                        # KB server might return ISO format date string
                        try:
                            from datetime import datetime
                            if isinstance(kb['creation_date'], str):
                                # Parse ISO format: "2025-10-20T14:07:40.163492"
                                dt = datetime.fromisoformat(kb['creation_date'].replace('Z', '+00:00'))
                                creation_date = int(dt.timestamp())
                            elif isinstance(kb['creation_date'], (int, float)):
                                # Already a timestamp
                                creation_date = int(kb['creation_date'])
                        except Exception as e:
                            logger.warning(f"Could not parse creation_date from KB server: {e}")
                            creation_date = None
                    
                    db_manager.register_kb(
                        kb_id=kb_id,
                        kb_name=kb_name,
                        owner_user_id=user_id,
                        organization_id=org_id,
                        is_shared=False,
                        metadata={'original_creation_date': creation_date} if creation_date else None
                    )
                    # If we have a creation date from KB server, update the registry entry
                    if creation_date:
                        # Update the created_at timestamp to match KB server's creation date
                        db_manager.update_kb_registry_created_at(kb_id, creation_date)
                        logger.info(f"Updated created_at for KB {kb_id} to match KB server creation date")
        
        # Step 3: Get owned KB registry entries only
        kb_registry_entries = db_manager.get_owned_kbs(user_id, org_id)
        
        logger.info(f"Found {len(kb_registry_entries)} owned KB registry entries for user {user_id}")
        
        # Step 4: Fetch KB details from KB Server for each registry entry
        # Handle stale entries gracefully (lazy cleanup)
        owned_kbs_list = []
        async with httpx.AsyncClient() as client:
            for entry in kb_registry_entries:
                kb_id = entry.get('kb_id')
                if not kb_id:
                    continue
                    
                try:
                    response = await client.get(
                        f"{kb_server_url}/collections/{kb_id}",
                        headers=self._get_auth_headers(kb_token)
                    )
                    
                    if response.status_code == 200:
                        kb_data = response.json()
                        
                        # CRITICAL FIX: Use the kb_id from LAMB registry, not from KB server
                        # The KB server may return a different ID format (UUID vs integer)
                        # We must use the LAMB registry ID for consistency with RAG_collections
                        kb_data['id'] = kb_id
                        
                        # Enhance with LAMB metadata - all owned KBs
                        kb_data['is_owner'] = True
                        kb_data['is_shared'] = entry.get('is_shared', False)
                        kb_data['can_modify'] = True
                        kb_data['shared_by'] = None
                        # Use created_at from registry (LAMB database) instead of KB server
                        # If not in registry, fallback to current time
                        registry_created_at = entry.get('created_at')
                        if registry_created_at:
                            kb_data['created_at'] = registry_created_at
                        elif 'creation_date' in kb_data:
                            # Fallback: try to parse KB server's creation_date
                            try:
                                from datetime import datetime as dt
                                creation_date = kb_data.get('creation_date')
                                if isinstance(creation_date, str):
                                    dt_obj = dt.fromisoformat(creation_date.replace('Z', '+00:00'))
                                    kb_data['created_at'] = int(dt_obj.timestamp())
                                else:
                                    kb_data['created_at'] = int(time.time())
                            except:
                                kb_data['created_at'] = int(time.time())
                        else:
                            kb_data['created_at'] = int(time.time())
                        kb_data['updated_at'] = entry.get('updated_at', int(time.time()))
                        
                        owned_kbs_list.append(kb_data)
                        logger.info(f"Fetched owned KB {kb_id}: is_shared={kb_data['is_shared']}")
                        
                    elif response.status_code == 404:
                        # Stale entry - KB deleted from KB Server
                        logger.warning(f"Stale registry entry: KB {kb_id} not found in KB Server, removing from registry")
                        db_manager.delete_kb_registry_entry(kb_id)
                    else:
                        logger.warning(f"KB Server returned {response.status_code} for KB {kb_id}, skipping")
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Stale entry cleanup
                        logger.warning(f"Stale registry entry detected: KB {kb_id} not found")
                        db_manager.delete_kb_registry_entry(kb_id)
                    else:
                        logger.warning(f"HTTP error fetching KB {kb_id}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to fetch KB {kb_id} from KB Server: {e}")
                    continue
        
        logger.info(f"Returning {len(owned_kbs_list)} owned KBs to user {user_id}")
        return owned_kbs_list
    
    async def get_org_shared_knowledge_bases(self, creator_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get knowledge bases SHARED in organization (excluding user's own).
        Includes lazy cleanup of stale entries.
        
        Args:
            creator_user: Authenticated user information
            
        Returns:
            List of shared knowledge base objects with LAMB metadata (is_owner=false, is_shared=true, can_modify=false, shared_by)
        """
        from lamb.database_manager import LambDatabaseManager
        
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        db_manager = LambDatabaseManager()
        user_id = creator_user.get('id')
        org_id = creator_user.get('organization_id')
        
        # Get shared KB registry entries (excluding user's own)
        kb_registry_entries = db_manager.get_shared_kbs(user_id, org_id)
        
        logger.info(f"Found {len(kb_registry_entries)} shared KB registry entries for user {user_id}")
        
        # Fetch KB details from KB Server for each registry entry
        # Handle stale entries gracefully (lazy cleanup)
        shared_kbs_list = []
        async with httpx.AsyncClient() as client:
            for entry in kb_registry_entries:
                kb_id = entry.get('kb_id')
                if not kb_id:
                    continue
                    
                try:
                    response = await client.get(
                        f"{kb_server_url}/collections/{kb_id}",
                        headers=self._get_auth_headers(kb_token)
                    )
                    
                    if response.status_code == 200:
                        kb_data = response.json()
                        
                        # CRITICAL FIX: Use the kb_id from LAMB registry, not from KB server
                        # The KB server may return a different ID format (UUID vs integer)
                        # We must use the LAMB registry ID for consistency with RAG_collections
                        kb_data['id'] = kb_id
                        
                        # Enhance with LAMB metadata - all shared KBs
                        kb_data['is_owner'] = False
                        kb_data['is_shared'] = True
                        kb_data['can_modify'] = False
                        kb_data['shared_by'] = entry.get('owner_name') or entry.get('owner_email', 'Unknown')
                        # Use created_at from registry (LAMB database) instead of KB server
                        # If not in registry, fallback to current time
                        registry_created_at = entry.get('created_at')
                        if registry_created_at:
                            kb_data['created_at'] = registry_created_at
                        elif 'creation_date' in kb_data:
                            # Fallback: try to parse KB server's creation_date
                            try:
                                from datetime import datetime as dt
                                creation_date = kb_data.get('creation_date')
                                if isinstance(creation_date, str):
                                    dt_obj = dt.fromisoformat(creation_date.replace('Z', '+00:00'))
                                    kb_data['created_at'] = int(dt_obj.timestamp())
                                else:
                                    kb_data['created_at'] = int(time.time())
                            except:
                                kb_data['created_at'] = int(time.time())
                        else:
                            kb_data['created_at'] = int(time.time())
                        kb_data['updated_at'] = entry.get('updated_at', int(time.time()))
                        
                        shared_kbs_list.append(kb_data)
                        logger.info(f"Fetched shared KB {kb_id}: shared_by={kb_data['shared_by']}")
                        
                    elif response.status_code == 404:
                        # Stale entry - KB deleted from KB Server
                        logger.warning(f"Stale registry entry: KB {kb_id} not found in KB Server, removing from registry")
                        db_manager.delete_kb_registry_entry(kb_id)
                    else:
                        logger.warning(f"KB Server returned {response.status_code} for KB {kb_id}, skipping")
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Stale entry cleanup
                        logger.warning(f"Stale registry entry detected: KB {kb_id} not found")
                        db_manager.delete_kb_registry_entry(kb_id)
                    else:
                        logger.warning(f"HTTP error fetching KB {kb_id}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to fetch KB {kb_id} from KB Server: {e}")
                    continue
        
        logger.info(f"Returning {len(shared_kbs_list)} shared KBs to user {user_id}")
        return shared_kbs_list
    
    async def _fetch_owned_kbs_from_kb_server(self, creator_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Helper: Fetch user's owned KBs from KB Server using owner parameter.
        
        Args:
            creator_user: Authenticated user information
            
        Returns:
            List of KB dictionaries from KB Server
        """
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        params = {
            "owner": str(creator_user.get('id'))  # Convert to string as KB server expects string
        }
        
        kb_server_collections_url = f"{kb_server_url}/collections"
        logger.info(f"Requesting user's owned collections from KB server at {kb_server_collections_url}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    kb_server_collections_url, 
                    headers=self._get_auth_headers(kb_token), 
                    params=params
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    
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
                        if isinstance(response_data, dict):
                            for key, value in response_data.items():
                                if isinstance(value, list):
                                    collections_data = value
                                    logger.info(f"Using key '{key}' which contains a list of {len(collections_data)} items")
                                    break
                    
                    logger.info(f"Found {len(collections_data)} owned KBs from KB Server")
                    return collections_data
                    
                else:
                    logger.error(f"KB server returned non-200 status: {response.status_code}")
                    return []
            
            except httpx.RequestError as req_err:
                logger.error(f"Error connecting to KB server: {str(req_err)}")
                return []
            except Exception as e:
                logger.error(f"Unexpected error fetching owned KBs: {e}")
                return []
                
    async def create_knowledge_base(self, kb_data: KnowledgeBaseCreate, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new knowledge base in the KB server.
        Automatically sanitizes KB names to conform to naming rules.
        
        Args:
            kb_data: Knowledge base creation data
            creator_user: Authenticated user information
            
        Returns:
            Dict with created knowledge base information
        """
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        original_name = kb_data.name
        logger.info(f"Creating knowledge base via KB server: {original_name}")
        
        # Validate required fields
        if not original_name or not original_name.strip():
            logger.error("Name is required but not provided")
            raise HTTPException(
                status_code=400,
                detail="Knowledge Base name is required"
            )

        # Sanitize name (lowercase, spaces to underscores, remove special chars)
        sanitized_name, was_modified = sanitize_name(original_name, max_length=50, to_lowercase=True)
        
        if was_modified:
            logger.info(f"KB name sanitized: '{original_name}' → '{sanitized_name}'")
        
        # Update kb_data with sanitized name
        kb_data.name = sanitized_name
   
        # Create collection in KB server
        async with httpx.AsyncClient() as client:
            kb_server_collections_url = f"{kb_server_url}/collections"
            logger.info(f"Creating collection in KB server at {kb_server_collections_url}: {sanitized_name}")
            
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
                    kb_server_collections_url, 
                    headers=self._get_content_type_headers(kb_token), 
                    json=collection_data
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 201:
                    # Successfully created
                    
                    collection_response = response.json()
                    kb_id = collection_response.get('id')
                    logger.info(f"KB server created collection with ID: {kb_id}")
                    
                    # Register in LAMB registry for sharing
                    try:
                        from lamb.database_manager import LambDatabaseManager
                        db_manager = LambDatabaseManager()
                        db_manager.register_kb(
                            kb_id=kb_id,
                            kb_name=kb_data.name,
                            owner_user_id=creator_user.get('id'),
                            organization_id=creator_user.get('organization_id'),
                            is_shared=False  # Default to private
                        )
                        logger.info(f"KB registered in LAMB registry: {kb_id}")
                    except Exception as reg_err:
                        # Log but don't fail - KB exists in KB Server even if registry fails
                        logger.error(f"Failed to register KB in LAMB registry: {reg_err}")
                    
                    return {
                        "message": "Knowledge base created successfully",
                        "id": kb_id,
                        "kb_id": kb_id,  # Include both for compatibility
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

    async def get_knowledge_base_details(self, kb_id: str, creator_user: Dict[str, Any], access_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get details of a specific knowledge base from the KB server
        
        Args:
            kb_id: ID of the knowledge base to retrieve
            creator_user: Authenticated user information
            access_type: Optional access type ('owner' or 'shared') if access has been verified at LAMB level
            
        Returns:
            Dict with knowledge base details
        """
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Getting knowledge base details for ID: {kb_id} from KB server")
        
        async with httpx.AsyncClient() as client:
            # Request collection details
            kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
            logger.info(f"Requesting collection from KB server at {kb_server_collection_url}")
            
            try:
                # Send request to KB server
                response = await client.get(
                    kb_server_collection_url, 
                    headers=self._get_auth_headers(kb_token)
                )
                logger.info(f"KB server response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Successfully retrieved
                    collection_data = response.json()
                    logger.info(f"Retrieved collection data from KB server for ID: {kb_id}")
                    
                    # Check if collection belongs to the authenticated user
                    # Skip ownership check if access has been verified at LAMB level (shared access)
                    if access_type != 'shared' and collection_data.get('owner') != str(creator_user.get('id')):
                        # Check if collection is public
                        if collection_data.get('visibility') != 'public':
                            logger.warning(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) tried to access collection {kb_id} owned by {collection_data.get('owner')}")
                            raise HTTPException(
                                status_code=403,
                                detail="You do not have permission to access this knowledge base"
                            )
                    
                    # Get files associated with this collection
                    files_url = f"{kb_server_url}/collections/{kb_id}/files"
                    files_response = await client.get(files_url, headers=self._get_auth_headers(kb_token))
                    
                    files = []
                    if files_response.status_code == 200:
                        files_data = files_response.json()
                        logger.info(f"DEBUG: Raw files data from KB server: {files_data}")
                        for file in files_data:
                            # Improved mapping with fallbacks for different field names
                            file_id = str(file.get('id'))
                            filename = file.get('original_filename', file.get('filename', ''))
                            size = file.get('file_size', file.get('size', 0))
                            content_type = file.get('content_type', file.get('mime_type', 'application/octet-stream'))
                            
                            # Get file URL and combine with base URL if it's a relative path
                            file_url = file.get('file_url', '')
                            if file_url and file_url.startswith('/'):
                                # It's a relative URL, combine with KB server base URL
                                base_url = kb_server_url.rstrip('/')
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
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Updating knowledge base {kb_id} via KB server")
        
        # Connect to KB server and update the collection
        async with httpx.AsyncClient() as client:
            kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
            logger.info(f"Connecting to KB server at: {kb_server_collection_url} to update collection")
            
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
                get_response = await client.get(kb_server_collection_url, headers=self._get_auth_headers(kb_token))
                
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
                        kb_server_collection_url, 
                        headers=self._get_content_type_headers(kb_token), 
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
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Deleting knowledge base {kb_id} for user {creator_user.get('email')}")

        # Normalize kb_id (allow numeric strings)
        try:
            if isinstance(kb_id, str) and kb_id.isdigit():
                kb_id = str(int(kb_id))
        except Exception:
            pass

        collection_url = f"{kb_server_url}/collections/{kb_id}"
        headers = self._get_auth_headers(kb_token)

        try:
            async with httpx.AsyncClient() as client:
                # 1. Retrieve collection to verify existence & ownership
                logger.info(f"Verifying ownership before hard delete: {collection_url}")
                get_resp = await client.get(collection_url, headers=headers)

                if get_resp.status_code == 404:
                    logger.error(f"Knowledge base with ID {kb_id} not found in KB server (already deleted?)")
                    raise HTTPException(status_code=404, detail="Knowledge base not found")
                if get_resp.status_code != 200:
                    try:
                        _d = get_resp.json()
                        detail = _d.get('detail') if isinstance(_d, dict) else str(_d)
                    except Exception:
                        detail = get_resp.text or f"HTTP {get_resp.status_code}"
                    raise HTTPException(status_code=get_resp.status_code, detail=f"KB server error fetching collection: {detail}")

                collection_data = get_resp.json()
                owner_id = str(creator_user.get('id'))
                if collection_data.get('owner') != owner_id:
                    logger.error(f"Ownership mismatch: user {owner_id} != collection owner {collection_data.get('owner')}")
                    raise HTTPException(status_code=403, detail="You don't have permission to delete this knowledge base")

                # 2. Perform HARD DELETE via new endpoint
                logger.info(f"Issuing HARD DELETE to KB server: {collection_url}")
                delete_resp = await client.delete(collection_url, headers=headers)
                logger.info(f"Hard delete status: {delete_resp.status_code}")

                if delete_resp.status_code in (200, 202, 204):
                    # Some implementations may return body only on 200/202
                    body = {}
                    try:
                        if delete_resp.content:
                            body = delete_resp.json()
                    except Exception:
                        body = {}

                    response_payload = {
                        "kb_id": str(kb_id),
                        "status": "success",
                        "message": "Knowledge base deleted successfully",
                    }
                    # Map optional metrics if present from KB server response
                    if isinstance(body, dict):
                        if 'deleted_embeddings' in body:
                            response_payload['deleted_embeddings'] = body.get('deleted_embeddings')
                        if 'removed_files' in body:
                            response_payload['removed_files'] = body.get('removed_files')
                        if 'name' in body:
                            response_payload['collection_name'] = body.get('name')
                    return response_payload

                if delete_resp.status_code == 404:
                    # Treat as idempotent (already deleted after initial fetch)
                    logger.warning(f"DELETE returned 404 after GET succeeded; treating as already deleted")
                    return {
                        "kb_id": str(kb_id),
                        "status": "success",
                        "message": "Knowledge base already deleted"
                    }

                try:
                    _dd = delete_resp.json()
                    detail = _dd.get('detail') if isinstance(_dd, dict) else str(_dd)
                except Exception:
                    detail = delete_resp.text or f"HTTP {delete_resp.status_code}"
                raise HTTPException(status_code=delete_resp.status_code, detail=f"KB server deletion error: {detail}")

        except httpx.RequestError as req_err:
            logger.error(f"Error connecting to KB server: {str(req_err)}")
            raise HTTPException(status_code=503, detail=f"Unable to connect to KB server: {str(req_err)}")

    async def query_knowledge_base(self, kb_id: str, query_data: Dict[str, Any], creator_user: Dict[str, Any], access_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Query a knowledge base from the KB server
        
        Args:
            kb_id: The ID of the knowledge base to query
            query_data: The query data including query_text and optional parameters
            creator_user: The authenticated creator user
            access_type: Optional access type ('owner' or 'shared') if access has been verified at LAMB level
            
        Returns:
            Dict with query results
        """
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Querying knowledge base {kb_id} with: {query_data.get('query_text', '')}")
        
        kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                # First check if the user has access to this collection
                logger.info(f"Checking collection access at KB server: {kb_server_collection_url}")
                
                headers = self._get_content_type_headers(kb_token)
                
                get_response = await client.get(kb_server_collection_url, headers=headers)
                
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
                # Skip ownership check if access has been verified at LAMB level (shared access)
                collection_data = get_response.json()
                if access_type != 'shared' and collection_data.get('owner') != str(creator_user.get('id')):
                    # For queries, we might allow read-only access if the KB has public visibility
                    if collection_data.get('visibility') != 'public':
                        logger.error(f"User {creator_user.get('email')} (ID: {creator_user.get('id')}) is not the owner of knowledge base {kb_id}")
                        raise HTTPException(
                            status_code=403,
                            detail="You don't have permission to query this knowledge base"
                        )
                
                # Execute the query against the KB server
                query_url = f"{kb_server_url}/collections/{kb_id}/query"
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
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Uploading files to knowledge base {kb_id} via KB server")
        
        kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
        logger.info(f"Checking collection access at KB server: {kb_server_collection_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                # First verify collection exists and user has access
                headers = self._get_auth_headers(kb_token)
                
                # Get collection details to verify ownership
                get_response = await client.get(kb_server_collection_url, headers=headers)
                
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
                        ingest_url = f"{kb_server_url}/collections/{str(kb_id)}/ingest-file"
                        
                        # Add detailed debug logging
                        logger.info(f"Ingesting file to collection ID: {kb_id}")
                        logger.info(f"Ingest URL: {ingest_url}")
                        
                        # Make sure headers are defined before use
                        upload_headers = self._get_auth_headers(kb_token)  # No Content-Type for multipart/form-data
                        
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
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Deleting file {file_id} from knowledge base {kb_id} via KB server")
        
        kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
        logger.info(f"Checking collection access at KB server: {kb_server_collection_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                # First verify collection exists and user has access
                headers = self._get_auth_headers(kb_token)
                
                # Get collection details to verify ownership
                get_response = await client.get(kb_server_collection_url, headers=headers)
                
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
                
                # Now delete the file from KB server
                delete_url = f"{kb_server_url}/collections/{kb_id}/files/{file_id}"
                logger.info(f"Deleting file from KB server at: {delete_url}")
                
                delete_response = await client.delete(delete_url, headers=headers)
                logger.info(f"KB server delete file response status: {delete_response.status_code}")
                
                if delete_response.status_code == 200 or delete_response.status_code == 204:
                    # Successfully deleted file
                    logger.info(f"Successfully deleted file {file_id} from knowledge base {kb_id}")
                    
                    return {
                        "message": "File deleted successfully",
                        "knowledge_base_id": kb_id,
                        "file_id": file_id
                    }
                elif delete_response.status_code == 404:
                    logger.error(f"File {file_id} not found in knowledge base {kb_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"File not found in knowledge base"
                    )
                else:
                    # Handle other errors
                    logger.error(f"KB server returned error status during file deletion: {delete_response.status_code}")
                    error_detail = "Unknown error"
                    try:
                        error_data = delete_response.json()
                        error_detail = error_data.get('detail', str(error_data))
                    except Exception:
                        error_detail = delete_response.text or "Unknown error"
                    
                    raise HTTPException(
                        status_code=delete_response.status_code,
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
        Get a list of available ingestion plugins and their parameters.
        Note: Uses global KB server config since no user context is available.
        
        Returns:
            Dict with plugin information including supported file extensions and parameters
        """
        logger.info("Getting available ingestion plugins from KB server (using global config)")
        
        # Use global config since no user context
        plugins_url = f"{self.global_kb_server_url}/ingestion/plugins"
        
        try:
            async with httpx.AsyncClient() as client:
                headers = self._get_auth_headers(self.global_kb_server_token)
                
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
        # Get organization-specific KB config
        kb_config = self._get_kb_config_for_user(creator_user)
        kb_server_url = kb_config['url']
        kb_token = kb_config['token']
        
        logger.info(f"Ingesting file {file.filename} to knowledge base {kb_id} using plugin {plugin_name}")
        
        # First check if user has access to the knowledge base
        kb_server_collection_url = f"{kb_server_url}/collections/{kb_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                # Verify collection exists and user has access
                headers = self._get_auth_headers(kb_token)
                
                # Check ownership
                get_response = await client.get(kb_server_collection_url, headers=headers)
                
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
                ingest_url = f"{kb_server_url}/collections/{kb_id}/ingest-file"
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
                upload_headers = self._get_auth_headers(kb_token)  # No Content-Type for multipart/form-data
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
