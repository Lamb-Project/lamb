"""
Organization management router for creator interface
Provides admin endpoints to manage organizations through the creator interface
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import httpx
import json
import time
from datetime import datetime
from .assistant_router import get_creator_user_from_token, is_admin_user
import config
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.services import OrganizationService
from schemas import BulkImportRequest, BulkUserActionRequest

# Initialize router
router = APIRouter()
security = HTTPBearer()

# Initialize database manager
db_manager = LambDatabaseManager()

# Set up logger for organization router
logger = get_logger(__name__, component="API")

# Get configuration
# Use LAMB_BACKEND_HOST for internal server-to-server requests
PIPELINES_HOST = config.LAMB_BACKEND_HOST
LAMB_BEARER_TOKEN = config.LAMB_BEARER_TOKEN

# Organization Admin Authorization Helpers
def get_user_organization_admin_info(auth_header: str) -> Optional[Dict[str, Any]]:
    """
    Get user information and check if they are an organization admin
    Returns user info with organization admin details if authorized, None otherwise
    """
    try:
        creator_user = get_creator_user_from_token(auth_header)
        if not creator_user:
            return None
        
        user_id = creator_user.get('id')
        if not user_id:
            return None
        
        # Get user's organization and role
        user_details = db_manager.get_creator_user_by_id(user_id)
        if not user_details or not user_details.get('organization_id'):
            return None
        
        org_id = user_details['organization_id']
        org_role = db_manager.get_user_organization_role(user_id, org_id)
        
        if org_role != "admin":
            return None
        
        # Get organization details
        organization = db_manager.get_organization_by_id(org_id)
        if not organization:
            return None
        
        return {
            'user_id': user_id,
            'user_email': user_details['user_email'],
            'user_name': user_details['user_name'],
            'organization_id': org_id,
            'organization': organization,
            'role': 'admin'
        }
    except Exception as e:
        logger.error(f"Error checking organization admin authorization: {e}")
        return None

def is_organization_admin(auth_header: str, organization_id: Optional[int] = None) -> bool:
    """
    Check if user is an admin of their organization (or specific organization if provided)
    """
    admin_info = get_user_organization_admin_info(auth_header)
    if not admin_info:
        return False
    
    if organization_id and admin_info['organization_id'] != organization_id:
        return False
    
    return True

async def verify_organization_admin_access(request: Request, organization_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Verify that the user has organization admin access
    Returns admin info if authorized, raises HTTPException otherwise
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header required")
        
        # First, check if user is a system administrator
        from .assistant_router import is_admin_user
        if is_admin_user(auth_header):
            # System admin can access any organization
            creator_user = get_creator_user_from_token(auth_header)
            if not creator_user:
                raise HTTPException(status_code=403, detail="Invalid authentication token")
            
            # If organization_id is specified, get that organization, otherwise use system org
            target_org_id = organization_id if organization_id else 1  # Default to system org
            organization = db_manager.get_organization_by_id(target_org_id)
            if not organization:
                raise HTTPException(status_code=404, detail="Organization not found")
            
            return {
                'user_id': creator_user.get('id'),
                'user_email': creator_user.get('email'),
                'user_name': creator_user.get('name'),
                'organization_id': target_org_id,
                'organization': organization,
                'role': 'system_admin'  # Indicate this is a system admin
            }
        
        # If not system admin, check for regular organization admin
        admin_info = get_user_organization_admin_info(auth_header)
        if not admin_info:
            raise HTTPException(status_code=403, detail="Organization admin privileges required")
        
        if organization_id and admin_info['organization_id'] != organization_id:
            raise HTTPException(status_code=403, detail="Access denied for this organization")
        
        return admin_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying organization admin access: {e}")
        raise HTTPException(status_code=500, detail="Authorization check failed")

# Pydantic models for API requests/responses
class OrganizationCreate(BaseModel):
    slug: str = Field(..., description="URL-friendly unique identifier")
    name: str = Field(..., description="Organization display name")
    config: Optional[Dict[str, Any]] = Field(None, description="Organization configuration")

class OrganizationCreateEnhanced(BaseModel):
    slug: str = Field(..., description="URL-friendly unique identifier")
    name: str = Field(..., description="Organization display name")
    admin_user_id: int = Field(..., description="ID of user from system org to become org admin")
    signup_enabled: bool = Field(False, description="Whether signup is enabled for this organization")
    signup_key: Optional[str] = Field(None, description="Unique signup key for organization-specific signup")
    use_system_baseline: bool = Field(True, description="Whether to copy system org config as baseline")
    config: Optional[Dict[str, Any]] = Field(None, description="Custom configuration (overrides system baseline)")

class SystemOrgUser(BaseModel):
    id: int
    email: str
    name: str
    role: str
    joined_at: int

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Organization display name")
    status: Optional[str] = Field(None, description="Organization status")
    config: Optional[Dict[str, Any]] = Field(None, description="Organization configuration")

class OrganizationResponse(BaseModel):
    id: int
    slug: str
    name: str
    is_system: bool
    status: str
    config: Dict[str, Any]
    created_at: int
    updated_at: int

class UserWithRole(BaseModel):
    id: int
    email: str
    name: str
    role: str
    joined_at: int

class OrganizationUsage(BaseModel):
    limits: Dict[str, Any]
    current: Dict[str, Any]
    organization: Dict[str, Any]

class ErrorResponse(BaseModel):
    detail: str

# Helper function to verify admin privileges
async def verify_admin_access(request: Request) -> str:
    """Verify that the current user has admin access"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    creator_user = get_creator_user_from_token(auth_header)
    if not creator_user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    if not is_admin_user(creator_user):
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    
    return auth_header


def sanitize_org_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    SECURITY: Remove sensitive API keys from organization config before sending to frontend.
    
    Transforms API key fields to boolean indicators:
        "api_key": "sk-xxx" -> "api_key_configured": true
        "apikey": "xxx" -> "apikey_configured": true
    
    Args:
        config: Raw organization configuration dict
        
    Returns:
        Sanitized config dict with API keys replaced by boolean indicators
    """
    import copy
    
    if not config or not isinstance(config, dict):
        return config
    
    safe_config = copy.deepcopy(config)
    
    # Sanitize provider API keys in setups
    if 'setups' in safe_config:
        for setup_name, setup in safe_config['setups'].items():
            if not isinstance(setup, dict):
                continue
            providers = setup.get('providers', {})
            if not isinstance(providers, dict):
                continue
            for provider_name, provider_config in providers.items():
                if not isinstance(provider_config, dict):
                    continue
                # Handle 'api_key' field
                if 'api_key' in provider_config:
                    provider_config['api_key_configured'] = bool(provider_config['api_key'])
                    del provider_config['api_key']
                # Handle 'apikey' field (alternate spelling)
                if 'apikey' in provider_config:
                    provider_config['apikey_configured'] = bool(provider_config['apikey'])
                    del provider_config['apikey']
    
    # Sanitize KB server API key
    if 'kb_server' in safe_config and isinstance(safe_config['kb_server'], dict):
        kb_server = safe_config['kb_server']
        if 'api_key' in kb_server:
            kb_server['api_key_configured'] = bool(kb_server['api_key'])
            del kb_server['api_key']
        if 'apikey' in kb_server:
            kb_server['apikey_configured'] = bool(kb_server['apikey'])
            del kb_server['apikey']
        # Also handle 'api_token' for KB server
        if 'api_token' in kb_server:
            kb_server['api_token_configured'] = bool(kb_server['api_token'])
            del kb_server['api_token']
    
    # Sanitize features signup key (sensitive for organization access)
    if 'features' in safe_config and isinstance(safe_config['features'], dict):
        features = safe_config['features']
        if 'signup_key' in features:
            features['signup_key_configured'] = bool(features['signup_key'])
            del features['signup_key']
    
    return safe_config


def sanitize_organization(org: Dict[str, Any]) -> Dict[str, Any]:
    """
    SECURITY: Sanitize a full organization object before sending to frontend.
    
    Args:
        org: Raw organization dict with config field
        
    Returns:
        Organization dict with sanitized config
    """
    import copy
    
    if not org or not isinstance(org, dict):
        return org
    
    safe_org = copy.deepcopy(org)
    
    if 'config' in safe_org:
        safe_org['config'] = sanitize_org_config(safe_org['config'])
    
    return safe_org


def sanitize_organizations_list(orgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    SECURITY: Sanitize a list of organization objects.
    
    Args:
        orgs: List of raw organization dicts
        
    Returns:
        List of organization dicts with sanitized configs
    """
    return [sanitize_organization(org) for org in orgs]


# Organization CRUD endpoints

@router.get(
    "/organizations/list",
    tags=["Organization Management"],
    summary="List Organizations for User Assignment (Admin Only)",
    description="""Retrieves a simplified list of organizations for user assignment dropdowns. Requires admin privileges.""",
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Successfully retrieved organizations list."},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"}
    }
)
async def list_organizations_for_users(request: Request):
    """List organizations for user assignment (admin only)"""
    try:
        await verify_admin_access(request)
        
        organizations = db_manager.list_organizations()
        
        # Format for dropdown use
        org_list = []
        for org in organizations:
            org_list.append({
                "id": org["id"],
                "name": org["name"],
                "slug": org["slug"],
                "is_system": org.get("is_system", False)
            })
        
        return {
            "success": True,
            "data": org_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing organizations for users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/organizations/system/users",
    tags=["Organization Management"],
    summary="List System Organization Users (Admin Only)",
    description="""List all users from the system organization ('lamb') for admin assignment to new organizations.
    
Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/system/users' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
[
  {
    "id": 1,
    "email": "admin@lamb.com",
    "name": "System Admin",
    "role": "admin",
    "joined_at": 1678886400
  },
  {
    "id": 2,
    "email": "user@lamb.com", 
    "name": "John Doe",
    "role": "member",
    "joined_at": 1678886500
  }
]
```
    """,
    response_model=List[SystemOrgUser],
    dependencies=[Depends(security)],
    responses={
        200: {"model": List[SystemOrgUser], "description": "List of system organization users"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_system_org_users(request: Request):
    """List all users from the system organization for admin assignment"""
    try:
        await verify_admin_access(request)
        
        users = db_manager.get_system_org_users()
        return [
            SystemOrgUser(
                id=user['id'],
                email=user['email'],
                name=user['name'],
                role=user['role'],
                joined_at=user['joined_at']
            )
            for user in users
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing system org users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/organizations",
    tags=["Organization Management"],
    summary="List All Organizations (Admin Only)",
    description="""List all organizations in the system. Requires admin privileges.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
[
  {
    "id": 1,
    "slug": "lamb",
    "name": "LAMB System Organization",
    "is_system": true,
    "status": "active",
    "config": {
      "version": "1.0",
      "setups": {
        "default": {
          "name": "System Default",
          "providers": {...}
        }
      }
    },
    "created_at": 1678886400,
    "updated_at": 1678886400
  }
]
```
    """,
    response_model=List[OrganizationResponse],
    dependencies=[Depends(security)],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_organizations(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List all organizations (admin only)"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Listing organizations with status filter: {status}")
        organizations = db_manager.list_organizations(status=status)
        # SECURITY: Sanitize all organization configs before sending to frontend
        return sanitize_organizations_list(organizations)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing organizations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/organizations",
    tags=["Organization Management"],
    summary="Create Organization (Admin Only)",
    description="""Create a new organization. Requires admin privileges.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/organizations' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "slug": "engineering",
  "name": "Engineering Department",
  "config": {
    "version": "1.0",
    "setups": {
      "default": {
        "name": "Default Setup",
        "providers": {}
      }
    },
    "features": {
      "rag_enabled": true
    }
  }
}'
```

Example Success Response:
```json
{
  "id": 2,
  "slug": "engineering",
  "name": "Engineering Department",
  "is_system": false,
  "status": "active",
  "config": {...},
  "created_at": 1678886400,
  "updated_at": 1678886400
}
```
    """,
    response_model=OrganizationResponse,
    dependencies=[Depends(security)],
    responses={
        201: {"model": OrganizationResponse, "description": "Organization created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input or organization already exists"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_organization(
    request: Request,
    org_data: OrganizationCreate
):
    """Create a new organization (admin only)"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Creating organization: {org_data.slug}")

        # Check if slug already exists
        existing = db_manager.get_organization_by_slug(org_data.slug)
        if existing:
            raise HTTPException(status_code=400, detail=f"Organization with slug '{org_data.slug}' already exists")

        # Create organization
        org_id = db_manager.create_organization(
            slug=org_data.slug,
            name=org_data.name,
            config=org_data.config
        )

        if not org_id:
            raise HTTPException(status_code=500, detail="Failed to create organization")

        # Get created organization
        org = db_manager.get_organization_by_id(org_id)
        # SECURITY: Sanitize config before sending to frontend
        return sanitize_organization(org)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/organizations/enhanced",
    tags=["Organization Management"],
    summary="Create Organization with Admin Assignment (Admin Only)",
    description="""Create a new organization with admin user assignment and signup configuration.
    This endpoint copies the system organization configuration as baseline and assigns a user from 
    the system organization as the new organization's admin.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/organizations/enhanced' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "slug": "engineering",
  "name": "Engineering Department", 
  "admin_user_id": 2,
  "signup_enabled": true,
  "signup_key": "eng-dept-2024",
  "use_system_baseline": true
}'
```

Example Success Response:
```json
{
  "id": 3,
  "slug": "engineering",
  "name": "Engineering Department",
  "is_system": false,
  "status": "active",
  "config": {
    "version": "1.0",
    "metadata": {
      "admin_user_id": 2,
      "admin_user_email": "john@lamb.com",
      "created_by_system_admin": true
    },
    "features": {
      "signup_enabled": true,
      "signup_key": "eng-dept-2024"
    }
  },
  "created_at": 1678886400,
  "updated_at": 1678886400
}
```
    """,
    response_model=OrganizationResponse,
    dependencies=[Depends(security)],
    responses={
        201: {"model": OrganizationResponse, "description": "Organization created successfully with admin assigned"},
        400: {"model": ErrorResponse, "description": "Invalid input, signup key exists, or user not in system org"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_organization_enhanced(
    request: Request,
    org_data: OrganizationCreateEnhanced
):
    """Create a new organization with admin user assignment and signup configuration"""
    try:
        await verify_admin_access(request)
        
        # Validate signup key if provided
        if org_data.signup_key:
            is_valid, error_msg = db_manager.validate_signup_key_format(org_data.signup_key)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid signup key: {error_msg}")
            
            if not db_manager.validate_signup_key_uniqueness(org_data.signup_key):
                raise HTTPException(status_code=400, detail=f"Signup key '{org_data.signup_key}' already exists")
        
        # Check if organization slug already exists
        existing = db_manager.get_organization_by_slug(org_data.slug)
        if existing:
            raise HTTPException(status_code=400, detail=f"Organization with slug '{org_data.slug}' already exists")
        
        # Check if the selected user is a system admin (not eligible)
        admin_user = db_manager.get_creator_user_by_id(org_data.admin_user_id)
        if admin_user:
            system_org = db_manager.get_organization_by_slug("lamb")
            if system_org:
                current_role = db_manager.get_user_organization_role(org_data.admin_user_id, system_org['id'])
                if current_role == "admin":
                    raise HTTPException(
                        status_code=400, 
                        detail="System administrators cannot be assigned to new organizations. They must remain in the system organization to manage it."
                    )
        
        # Create organization with admin assignment
        org_id = db_manager.create_organization_with_admin(
            slug=org_data.slug,
            name=org_data.name,
            admin_user_id=org_data.admin_user_id,
            signup_enabled=org_data.signup_enabled,
            signup_key=org_data.signup_key,
            use_system_baseline=org_data.use_system_baseline,
            config=org_data.config
        )
        
        if not org_id:
            raise HTTPException(status_code=500, detail="Failed to create organization")
        
        # Get created organization and return
        org = db_manager.get_organization_by_id(org_id)
        if not org:
            raise HTTPException(status_code=500, detail="Organization created but could not retrieve details")
        
        # SECURITY: Sanitize config before sending to frontend
        return OrganizationResponse(
            id=org['id'],
            slug=org['slug'],
            name=org['name'],
            is_system=org['is_system'],
            status=org['status'],
            config=sanitize_org_config(org['config']),
            created_at=org['created_at'],
            updated_at=org['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating enhanced organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/organizations/{slug}",
    tags=["Organization Management"],
    summary="Get Organization Details",
    description="""Get details of a specific organization by slug.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/engineering' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "id": 2,
  "slug": "engineering",
  "name": "Engineering Department",
  "is_system": false,
  "status": "active",
  "config": {
    "version": "1.0",
    "setups": {...},
    "features": {...},
    "limits": {...}
  },
  "created_at": 1678886400,
  "updated_at": 1678886400
}
```
    """,
    response_model=OrganizationResponse,
    dependencies=[Depends(security)],
    responses={
        200: {"model": OrganizationResponse, "description": "Organization details retrieved"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_organization(
    request: Request,
    slug: str
):
    """Get organization details by slug"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Getting organization by slug: {slug}")
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # SECURITY: Sanitize config before sending to frontend
        return sanitize_organization(org)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/organizations/{slug}",
    tags=["Organization Management"],
    summary="Update Organization",
    description="""Update an organization's details. Requires admin privileges.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/organizations/engineering' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "name": "Updated Engineering Department",
  "status": "active"
}'
```

Example Success Response:
```json
{
  "id": 2,
  "slug": "engineering",
  "name": "Updated Engineering Department",
  "is_system": false,
  "status": "active",
  "config": {...},
  "created_at": 1678886400,
  "updated_at": 1678887000
}
```
    """,
    response_model=OrganizationResponse,
    dependencies=[Depends(security)],
    responses={
        200: {"model": OrganizationResponse, "description": "Organization updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_organization(
    request: Request,
    slug: str,
    update_data: OrganizationUpdate
):
    """Update organization details (admin only)"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (similar to core function)
        logger.info(f"Updating organization: {slug}")

        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # Check if it's a system organization
        if org['is_system'] and update_data.status:
            raise HTTPException(status_code=400, detail="Cannot change status of system organization")

        # Update organization (only send non-None fields)
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        success = db_manager.update_organization(
            org_id=org['id'],
            name=update_dict.get('name'),
            status=update_dict.get('status'),
            config=update_dict.get('config')
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update organization")

        # Get updated organization
        updated_org = db_manager.get_organization_by_id(org['id'])
        # SECURITY: Sanitize config before sending to frontend
        return sanitize_organization(updated_org)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/organizations/{slug}",
    tags=["Organization Management"],
    summary="Delete Organization",
    description="""Delete an organization. Cannot delete system organization. Requires admin privileges.

Example Request:
```bash
curl -X DELETE 'http://localhost:8000/creator/admin/organizations/engineering' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "message": "Organization 'engineering' deleted successfully"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Organization deleted successfully"},
        400: {"model": ErrorResponse, "description": "Cannot delete system organization"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_organization(
    request: Request,
    slug: str
):
    """Delete organization (admin only, cannot delete system org)"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Deleting organization: {slug}")

        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # Check if it's a system organization
        if org['is_system']:
            raise HTTPException(status_code=400, detail="Cannot delete system organization")

        # Delete organization
        success = db_manager.delete_organization(org['id'])
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete organization")

        return {"message": f"Organization '{slug}' deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Organization Migration Endpoints

class MigrationValidateRequest(BaseModel):
    target_organization_slug: str = Field(..., description="Target organization slug")

class MigrationRequest(BaseModel):
    target_organization_slug: str = Field(..., description="Target organization slug")
    conflict_strategy: str = Field(default="rename", description="Conflict resolution strategy: 'rename', 'skip', or 'fail'")
    preserve_admin_roles: bool = Field(default=False, description="Keep old organization admins as admins in target organization")
    delete_source: bool = Field(default=False, description="Delete source organization after successful migration")

@router.post(
    "/organizations/{slug}/migration/validate",
    tags=["Organization Management"],
    summary="Validate Organization Migration",
    description="""Validate migration feasibility before execution. Checks for conflicts and returns resource counts.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/organizations/engineering/migration/validate' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "target_organization_slug": "main-org"
}'
```

Example Success Response:
```json
{
  "can_migrate": true,
  "conflicts": {
    "assistants": [
      {
        "id": 123,
        "name": "Math_Tutor",
        "owner": "teacher@school.edu",
        "conflict_reason": "Target org already has assistant with same name and owner"
      }
    ],
    "templates": []
  },
  "resources": {
    "users": 10,
    "assistants": 25,
    "templates": 5,
    "kbs": 8,
    "usage_logs": 1500
  },
  "source_org_slug": "engineering",
  "estimated_time_seconds": 45
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Migration validation completed"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def validate_organization_migration(
    request: Request,
    slug: str,
    validation_data: MigrationValidateRequest
):
    """Validate organization migration feasibility"""
    try:
        await verify_admin_access(request)
        
        # Get source organization
        source_org = db_manager.get_organization_by_slug(slug)
        if not source_org:
            raise HTTPException(status_code=404, detail=f"Source organization '{slug}' not found")
        
        if source_org['is_system']:
            raise HTTPException(status_code=400, detail="Cannot migrate system organization")
        
        # Get target organization
        target_org = db_manager.get_organization_by_slug(validation_data.target_organization_slug)
        if not target_org:
            raise HTTPException(status_code=404, detail=f"Target organization '{validation_data.target_organization_slug}' not found")
        
        # Validate migration
        validation_result = db_manager.validate_migration(source_org['id'], target_org['id'])
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating migration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/organizations/{slug}/migrate",
    tags=["Organization Management"],
    summary="Migrate Organization",
    description="""Migrate all resources from source organization to target organization.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/organizations/engineering/migrate' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "target_organization_slug": "main-org",
  "conflict_strategy": "rename",
  "preserve_admin_roles": false,
  "delete_source": false
}'
```

Example Success Response:
```json
{
  "success": true,
  "resources_migrated": {
    "users": 10,
    "roles": 10,
    "assistants": 25,
    "templates": 5,
    "kbs": 8,
    "usage_logs": 1500
  },
  "conflicts_resolved": {
    "assistants_renamed": 2,
    "templates_renamed": 0
  },
  "warnings": [
    "2 assistants were renamed due to conflicts"
  ]
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Migration completed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request or validation failed"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def migrate_organization(
    request: Request,
    slug: str,
    migration_data: MigrationRequest
):
    """Migrate organization to target organization"""
    try:
        await verify_admin_access(request)
        
        # Get source organization
        source_org = db_manager.get_organization_by_slug(slug)
        if not source_org:
            raise HTTPException(status_code=404, detail=f"Source organization '{slug}' not found")
        
        if source_org['is_system']:
            raise HTTPException(status_code=400, detail="Cannot migrate system organization")
        
        # Get target organization
        target_org = db_manager.get_organization_by_slug(migration_data.target_organization_slug)
        if not target_org:
            raise HTTPException(status_code=404, detail=f"Target organization '{migration_data.target_organization_slug}' not found")
        
        # Validate before migration
        validation_result = db_manager.validate_migration(source_org['id'], target_org['id'])
        if not validation_result.get('can_migrate'):
            raise HTTPException(
                status_code=400,
                detail=validation_result.get('error', 'Migration validation failed')
            )
        
        # Execute migration
        migration_report = db_manager.migrate_organization_comprehensive(
            source_org_id=source_org['id'],
            target_org_id=target_org['id'],
            source_org_slug=source_org['slug'],
            conflict_strategy=migration_data.conflict_strategy,
            preserve_admin_roles=migration_data.preserve_admin_roles
        )
        
        if not migration_report.get('success'):
            raise HTTPException(
                status_code=500,
                detail=migration_report.get('error', 'Migration failed')
            )
        
        # Add warnings for renamed resources
        warnings = []
        assistants_renamed = migration_report.get('conflicts_resolved', {}).get('assistants_renamed', 0)
        templates_renamed = migration_report.get('conflicts_resolved', {}).get('templates_renamed', 0)
        
        if assistants_renamed > 0:
            warnings.append(f"{assistants_renamed} assistant(s) were renamed due to conflicts")
        if templates_renamed > 0:
            warnings.append(f"{templates_renamed} template(s) were renamed due to conflicts")
        
        migration_report['warnings'] = warnings
        
        # Optionally delete source organization
        if migration_data.delete_source:
            delete_success = db_manager.delete_organization(source_org['id'])
            if not delete_success:
                warnings.append(f"Migration succeeded but failed to delete source organization '{slug}'")
                migration_report['warnings'] = warnings
            else:
                logger.info(f"Source organization '{slug}' deleted after successful migration")
        
        return migration_report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration management endpoints

@router.get(
    "/organizations/{slug}/config",
    tags=["Organization Management"],
    summary="Get Organization Configuration",
    description="""Get the full configuration of an organization.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/engineering/config' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "name": "Production Setup",
      "providers": {
        "openai": {
          "api_key": "encrypted:...",
          "models": ["gpt-4o-mini"]
        }
      }
    }
  },
  "features": {
    "rag_enabled": true,
    "mcp_enabled": true
  },
  "limits": {
    "usage": {
      "tokens_per_month": 1000000
    }
  }
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Organization configuration retrieved"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_organization_config(
    request: Request,
    slug: str
):
    """Get organization configuration"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Getting organization config for: {slug}")
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # SECURITY: Sanitize config to remove API keys before sending to frontend
        return sanitize_org_config(org['config'])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/organizations/{slug}/config",
    tags=["Organization Management"],
    summary="Update Organization Configuration",
    description="""Update the full configuration of an organization.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/organizations/engineering/config' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "config": {
    "version": "1.0",
    "setups": {
      "default": {
        "name": "Updated Setup",
        "providers": {
          "openai": {
            "api_key": "sk-new-key",
            "models": ["gpt-4o-mini", "gpt-4o"]
          }
        }
      }
    }
  }
}'
```

Example Success Response:
```json
{
  "message": "Configuration updated successfully",
  "config": {...}
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Configuration updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_organization_config(
    request: Request,
    slug: str,
    config_data: Dict[str, Any]
):
    """Update organization configuration"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Updating organization config for: {slug}")

        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # Update config
        success = db_manager.update_organization_config(org['id'], config_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration")

        # SECURITY: Do not echo back the full config with API keys
        # Return sanitized version instead
        return {"message": "Configuration updated successfully", "config": sanitize_org_config(config_data)}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Usage and export endpoints

@router.get(
    "/organizations/{slug}/usage",
    tags=["Organization Management"],
    summary="Get Organization Usage",
    description="""Get current usage statistics for an organization.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/engineering/usage' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "limits": {
    "tokens_per_month": 1000000,
    "max_assistants": 100,
    "storage_gb": 10
  },
  "current": {
    "tokens_this_month": 150000,
    "storage_used_gb": 2.5,
    "last_reset": "2024-01-01T00:00:00Z"
  },
  "organization": {
    "id": 2,
    "slug": "engineering",
    "name": "Engineering Department"
  }
}
```
    """,
    response_model=OrganizationUsage,
    dependencies=[Depends(security)],
    responses={
        200: {"model": OrganizationUsage, "description": "Usage statistics retrieved"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_organization_usage(
    request: Request,
    slug: str
):
    """Get organization usage statistics"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Getting organization usage for: {slug}")

        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # Get usage from config
        usage_limits = org['config'].get('limits', {}).get('usage', {})
        current_usage = org['config'].get('limits', {}).get('current_usage', {})

        return {
            "limits": usage_limits,
            "current": current_usage,
            "organization": {
                "id": org['id'],
                "slug": org['slug'],
                "name": org['name']
            }
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/organizations/{slug}/export",
    tags=["Organization Management"],
    summary="Export Organization Configuration",
    description="""Export organization configuration as JSON.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/engineering/export' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "export_version": "1.0",
  "export_date": "2024-01-15T10:00:00Z",
  "organization": {
    "slug": "engineering",
    "name": "Engineering Department",
    "config": {...}
  },
  "statistics": {
    "users_count": 25,
    "assistants_count": 150,
    "collections_count": 30
  }
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Organization configuration exported"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def export_organization(
    request: Request,
    slug: str
):
    """Export organization configuration"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info(f"Exporting organization: {slug}")

        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")

        # Get user and assistant counts
        # TODO: Implement counting logic

        export_data = {
            "export_version": "1.0",
            "export_date": datetime.now().isoformat(),
            "organization": {
                "slug": org['slug'],
                "name": org['name'],
                "config": org['config']
            },
            "statistics": {
                "users_count": 0,  # TODO: Get actual count
                "assistants_count": 0,  # TODO: Get actual count
                "collections_count": 0  # TODO: Get actual count
            }
        }

        return export_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/organizations/system/sync",
    tags=["Organization Management"],
    summary="Sync System Organization",
    description="""Sync the system organization ('lamb') with environment variables.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/organizations/system/sync' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "message": "System organization synced successfully",
  "organization": {
    "id": 1,
    "slug": "lamb",
    "name": "LAMB System Organization",
    "config": {...}
  }
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "System organization synced successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        404: {"model": ErrorResponse, "description": "System organization not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def sync_system_organization(
    request: Request
):
    """Sync system organization with environment variables"""
    try:
        await verify_admin_access(request)
        
        # Call database manager directly (same as core function)
        logger.info("Syncing system organization with environment variables")

        # Get system organization
        system_org = db_manager.get_organization_by_slug("lamb")
        if not system_org:
            raise HTTPException(status_code=404, detail="System organization not found")

        # Sync with environment
        db_manager.sync_system_org_with_env(system_org['id'])

        # Get updated organization
        updated_org = db_manager.get_organization_by_id(system_org['id'])

        return {
            "message": "System organization synced successfully",
            "organization": updated_org
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing system organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ORGANIZATION ADMIN ENDPOINTS
# These endpoints are for organization admins to manage their own organizations
# ============================================================================

# Pydantic models for organization admin endpoints
class OrgAdminUserCreate(BaseModel):
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")
    password: str = Field(..., description="User password")
    enabled: bool = Field(True, description="Whether user is enabled")
    user_type: str = Field('creator', description="User type: 'creator' or 'end_user'")

class OrgAdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, description="User display name")
    enabled: Optional[bool] = Field(None, description="Whether user is enabled")

class OrgAdminPasswordChange(BaseModel):
    new_password: str = Field(..., description="New password for the user")

class OrgAdminSignupSettings(BaseModel):
    signup_enabled: bool = Field(..., description="Whether organization signup is enabled")
    signup_key: Optional[str] = Field(None, description="Organization signup key (required if signup_enabled is True)")

class OrgAdminApiSettings(BaseModel):
    model_config = {"protected_namespaces": ()}

    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_base_url: Optional[str] = Field(None, description="OpenAI API base URL (from OPENAI_BASE_URL env var)")
    ollama_base_url: Optional[str] = Field(None, description="Ollama server base URL (from OLLAMA_BASE_URL env var)")
    available_models: Optional[List[str]] = Field(None, description="List of available models (deprecated)")
    model_limits: Optional[Dict[str, Any]] = Field(None, description="Model usage limits")
    selected_models: Optional[Dict[str, List[str]]] = Field(None, description="Selected models per provider")
    default_models: Optional[Dict[str, str]] = Field(None, description="Default model per provider")
    global_default_model: Optional[Dict[str, str]] = Field(None, description="Global default model for the organization")
    small_fast_model: Optional[Dict[str, str]] = Field(None, description="Small fast model for auxiliary operations")

class OrgAdminKBSettings(BaseModel):
    url: str = Field(..., description="Knowledge Base server URL")
    api_key: Optional[str] = Field(None, description="Knowledge Base server API key (leave empty to keep existing)")
    embedding_model: Optional[str] = Field(None, description="Default embedding model")
    collection_defaults: Optional[Dict[str, Any]] = Field(None, description="Default settings for new collections")

class KBTestRequest(BaseModel):
    url: str = Field(..., description="KB server URL to test")
    api_key: str = Field(..., description="API key to test")

class OrgUserResponse(BaseModel):
    id: int
    email: str
    name: str
    enabled: bool
    created_at: int
    role: str = "member"

# Organization Admin Dashboard endpoint
@router.get(
    "/org-admin/dashboard",
    tags=["Organization Admin"],
    summary="Get Organization Dashboard Info",
    description="""Get dashboard information for organization admin including organization details, user count, and settings summary.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/dashboard' \\
-H 'Authorization: Bearer <org_admin_token>'
```

Example Success Response:
```json
{
  "organization": {
    "id": 2,
    "name": "Engineering Department", 
    "slug": "engineering",
    "status": "active"
  },
  "stats": {
    "total_users": 15,
    "active_users": 12,
    "disabled_users": 3
  },
  "settings": {
    "signup_enabled": true,
    "api_configured": true,
    "total_assistants": 8
  }
}
```
    """,
    dependencies=[Depends(security)]
)
async def get_organization_dashboard(request: Request, org: Optional[str] = None):
    """Get organization admin dashboard information"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        organization = admin_info['organization']
        
        # Get organization statistics
        org_users = db_manager.get_organization_users(org_id)
        
        active_users = len([u for u in org_users if u.get('enabled', True)])
        disabled_users = len(org_users) - active_users
        
        # Get organization configuration
        config = organization.get('config', {})
        features = config.get('features', {})
        
        # Check API status
        from .api_status_checker import check_organization_api_status
        try:
            api_status = await check_organization_api_status(config)
        except Exception as e:
            logger.error(f"Error checking API status: {e}")
            api_status = {
                "overall_status": "error",
                "providers": {},
                "summary": {"configured_count": 0, "working_count": 0, "total_models": 0}
            }

        # Get enabled models for each provider
        setups = config.get('setups', {})
        default_setup = setups.get('default', {})
        providers = default_setup.get('providers', {})

        for provider_name in api_status.get("providers", {}):
            if provider_name in providers:
                provider_config = providers[provider_name]
                enabled_models = provider_config.get('models', [])
                api_status["providers"][provider_name]["enabled_models"] = enabled_models
                api_status["providers"][provider_name]["default_model"] = provider_config.get('default_model', '')
        
        dashboard_info = {
            "organization": {
                "id": organization['id'],
                "name": organization['name'],
                "slug": organization['slug'],
                "status": organization['status']
            },
            "stats": {
                "total_users": len(org_users),
                "active_users": active_users,
                "disabled_users": disabled_users
            },
            "settings": {
                "signup_enabled": features.get('signup_enabled', False),
                "api_configured": api_status["overall_status"] in ["working", "partial"],
                "signup_key_set": bool(features.get('signup_key'))
            },
            "api_status": api_status
        }
        
        return dashboard_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Organization User Management endpoints
@router.get(
    "/org-admin/users",
    tags=["Organization Admin - User Management"], 
    summary="List Organization Users",
    description="""List all users in the organization. Only accessible by organization admins.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/users' \\
-H 'Authorization: Bearer <org_admin_token>'
```
    """,
    dependencies=[Depends(security)],
    response_model=List[OrgUserResponse]
)
async def list_organization_users(request: Request, org: Optional[str] = None):
    """List all users in the organization"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        users = db_manager.get_organization_users(org_id)
        owi_manager = OwiUserManager()
        
        # Get enabled status for each user from OWI auth system
        user_responses = []
        for user in users:
            enabled_status = owi_manager.get_user_status(user['email'])
            if enabled_status is None:
                enabled_status = True  # Default to enabled if status can't be determined
                logger.warning(f"Could not determine enabled status for user {user['email']}, defaulting to enabled")
            
            user_responses.append(OrgUserResponse(
                id=user['id'],
                email=user['email'],
                name=user['name'],
                enabled=enabled_status,
                created_at=user.get('joined_at', 0),
                role=user.get('role', 'member')
            ))
        
        return user_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing organization users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/org-admin/users",
    tags=["Organization Admin - User Management"],
    summary="Create Organization User",
    description="""Create a new user in the organization. Only accessible by organization admins.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "email": "newuser@example.com",
  "name": "New User",
  "password": "securepassword123",
  "enabled": true
}'
```
    """,
    dependencies=[Depends(security)],
    response_model=OrgUserResponse
)
async def create_organization_user(request: Request, user_data: OrgAdminUserCreate):
    """Create a new user in the organization"""
    try:
        admin_info = await verify_organization_admin_access(request)
        org_id = admin_info['organization_id']
        
        # Create user with organization assignment
        user_id = db_manager.create_creator_user(
            user_email=user_data.email,
            user_name=user_data.name,
            password=user_data.password,
            organization_id=org_id,
            user_type=user_data.user_type
        )
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        # Assign member role
        if not db_manager.assign_organization_role(org_id, user_id, "member"):
            logger.warning(f"Failed to assign member role to user {user_id}")
        
        # Set enabled status if needed
        if not user_data.enabled:
            # Disable the user in OWI auth system
            owi_manager = OwiUserManager()
            if not owi_manager.update_user_status(user_data.email, False):
                logger.warning(f"Failed to disable user {user_data.email} after creation")
                # Note: We don't fail the entire operation since the user was created successfully
        
        return OrgUserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            enabled=user_data.enabled,
            created_at=int(time.time()),
            role="member"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating organization user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/org-admin/users/{user_id}",
    tags=["Organization Admin - User Management"],
    summary="Update Organization User",
    description="""Update a user in the organization. Only accessible by organization admins.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/users/123' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "name": "Updated Name",
  "enabled": false
}'
```
    """,
    dependencies=[Depends(security)]
)
async def update_organization_user(request: Request, user_id: int, user_data: OrgAdminUserUpdate):
    """Update a user in the organization"""
    try:
        admin_info = await verify_organization_admin_access(request)
        org_id = admin_info['organization_id']
        
        # Verify user belongs to this organization
        user = db_manager.get_creator_user_by_id(user_id)
        if not user or user.get('organization_id') != org_id:
            raise HTTPException(status_code=404, detail="User not found in this organization")
        
        # Update user name if provided
        if user_data.name:
            # TODO: Implement update_creator_user_name method
            pass
        
        # Update enabled status if provided
        if user_data.enabled is not None:
            # Prevent users from disabling themselves
            current_user_email = admin_info.get('email')
            if user.get('user_email') == current_user_email and not user_data.enabled:
                raise HTTPException(
                    status_code=403, 
                    detail="You cannot disable your own account. Please ask another administrator to disable your account if needed."
                )
            
            # Update user status in OWI auth system
            owi_manager = OwiUserManager()
            if not owi_manager.update_user_status(user.get('user_email'), user_data.enabled):
                logger.error(f"Failed to update enabled status for user {user.get('user_email')}")
                raise HTTPException(status_code=500, detail="Failed to update user status")
        
        return {"message": "User updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/org-admin/users/{user_id}/password",
    tags=["Organization Admin - User Management"],
    summary="Change User Password",
    description="""Change password for a user in the organization. Only accessible by organization admins.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users/123/password' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "new_password": "newsecurepassword123"
}'
```
    """,
    dependencies=[Depends(security)]
)
async def change_user_password(request: Request, user_id: int, password_data: OrgAdminPasswordChange):
    """Change password for a user in the organization"""
    try:
        admin_info = await verify_organization_admin_access(request)
        org_id = admin_info['organization_id']
        
        # Verify user belongs to this organization
        user = db_manager.get_creator_user_by_id(user_id)
        if not user or user.get('organization_id') != org_id:
            raise HTTPException(status_code=404, detail="User not found in this organization")
        
        # Change password using UserCreatorManager (same as system admin)
        from .user_creator import UserCreatorManager
        user_creator = UserCreatorManager()
        user_email = user.get('user_email')  # Fix: use 'user_email' key from database
        result = await user_creator.update_user_password(user_email, password_data.new_password)
        
        if not result["success"]:
            logger.error(f"Failed to update password for user {user_email}: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to update user password'))
        
        logger.info(f"Organization admin {admin_info.get('email')} changed password for user {user_email}")
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing user password: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/org-admin/users/{user_id}",
    tags=["Organization Admin - User Management"],
    summary="Delete Organization User",
    description="""Delete a user from the organization. Only accessible by organization admins.
    
    This permanently removes the user from both the LAMB database and the authentication system.
    The user cannot be an organization admin/owner, and admins cannot delete themselves.

Example Request:
```bash
curl -X DELETE 'http://localhost:8000/creator/admin/org-admin/users/123' \\
-H 'Authorization: Bearer <org_admin_token>'
```
    """,
    dependencies=[Depends(security)]
)
async def delete_organization_user(request: Request, user_id: int, org: Optional[str] = None):
    """Delete a user from the organization"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        # Verify user belongs to this organization
        user = db_manager.get_creator_user_by_id(user_id)
        if not user or user.get('organization_id') != org_id:
            raise HTTPException(status_code=404, detail="User not found in this organization")
        
        user_email = user.get('user_email')
        
        # Prevent users from deleting themselves
        current_user_email = admin_info.get('email')
        if user_email == current_user_email:
            raise HTTPException(
                status_code=403, 
                detail="You cannot delete your own account. Please ask another administrator to delete your account if needed."
            )
        
        # Check if the user is an admin/owner of this organization
        user_role = db_manager.get_user_organization_role(user_id, org_id)
        if user_role in ['owner', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete an organization admin or owner. Please remove their admin privileges first."
            )
        
        # Delete user from OWI auth system (if exists)
        owi_manager = OwiUserManager()
        owi_deleted = owi_manager.delete_user(user_email)
        if not owi_deleted:
            logger.warning(f"User {user_email} was not found in OWI auth system (may only exist in LAMB)")
        
        # Delete user from LAMB database
        if not db_manager.delete_creator_user(user_id):
            logger.error(f"Failed to delete user {user_email} from LAMB database")
            raise HTTPException(status_code=500, detail="Failed to delete user from LAMB database")
        
        logger.info(f"Organization admin {current_user_email} deleted user {user_email} (ID: {user_id}) from organization {org_id}")
        return {"message": f"User {user_email} has been permanently deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting organization user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Bulk User Management Endpoints
# ============================================================================

@router.post(
    "/org-admin/users/bulk-import/validate",
    tags=["Organization Admin - Bulk Operations"],
    summary="Validate Bulk User Import File",
    description="""Validate a JSON file for bulk user import. Returns validation results 
    with detailed error information for each user.
    
    The JSON file should follow this structure:
    ```json
    {
      "version": "1.0",
      "users": [
        {
          "email": "user@example.com",
          "name": "User Name",
          "user_type": "creator",  // or "end_user"
          "enabled": false
        }
      ]
    }
    ```
    
    Maximum 500 users per file, maximum file size 5MB.
    
Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users/bulk-import/validate' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-F 'file=@users_import.json'
```
    """,
    dependencies=[Depends(security)]
)
async def validate_bulk_user_import(
    request: Request, 
    file: UploadFile = File(...),
    org: Optional[str] = None
):
    """Validate bulk user import JSON file"""
    from .bulk_operations import validate_bulk_import_file
    
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        # Validate file extension
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400,
                detail="Only JSON files are allowed"
            )
        
        # Validate and return results
        validation_result = await validate_bulk_import_file(
            file=file,
            organization_id=org_id,
            max_file_size_mb=5
        )
        
        logger.info(
            f"Bulk import validation by {admin_info['user_email']}: "
            f"{validation_result.get('summary', {}).get('total', 0)} users, "
            f"{validation_result.get('summary', {}).get('valid', 0)} valid"
        )
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating bulk import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/org-admin/users/bulk-import/execute",
    tags=["Organization Admin - Bulk Operations"],
    summary="Execute Bulk User Import",
    description="""Create multiple users from validated import data.
    
    Users are created with random secure passwords (admins should communicate
    these separately). Users can be created in disabled state and activated later.
    
    The operation continues on individual failures (partial success).
    
Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users/bulk-import/execute' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "users": [
    {
      "email": "user1@example.com",
      "name": "User One",
      "user_type": "creator",
      "enabled": false
    }
  ]
}'
```
    """,
    dependencies=[Depends(security)]
)
async def execute_bulk_user_import(
    request: Request,
    import_data: BulkImportRequest,
    org: Optional[str] = None
):
    """Execute bulk user creation"""
    from .bulk_operations import BulkUserCreator, log_bulk_operation
    from schemas import BulkImportRequest
    
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        admin_user_id = admin_info['user_id']
        admin_email = admin_info['user_email']
        
        # Validate request
        if not import_data.users or len(import_data.users) == 0:
            raise HTTPException(status_code=400, detail="No users provided")
        
        if len(import_data.users) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 users per import")
        
        # Execute bulk creation
        creator = BulkUserCreator(
            organization_id=org_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email
        )
        
        users_data = [user.dict() for user in import_data.users]
        result = await creator.create_users(users_data)
        
        # Log the operation
        log_id = log_bulk_operation(
            db_manager=db_manager,
            organization_id=org_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            operation_type='user_creation',
            total_count=result['summary']['total'],
            success_count=result['summary']['created'],
            failure_count=result['summary']['failed'],
            details={
                "filename": import_data.filename or "direct_api",
                "results": result['results']
            }
        )
        
        result['log_id'] = log_id
        
        logger.info(
            f"Bulk user creation by {admin_email}: "
            f"{result['summary']['created']} created, "
            f"{result['summary']['failed']} failed"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing bulk import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/org-admin/users/bulk-import/template",
    tags=["Organization Admin - Bulk Operations"],
    summary="Download Bulk Import Template",
    description="""Download a JSON template file with examples for bulk user import.
    
Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/users/bulk-import/template' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-o template.json
```
    """,
    dependencies=[Depends(security)]
)
async def download_bulk_import_template(request: Request, org: Optional[str] = None):
    """Download bulk import template"""
    from .bulk_operations import generate_import_template
    from fastapi.responses import JSONResponse
    
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        await verify_organization_admin_access(request, target_org_id)
        
        template = generate_import_template()
        
        return JSONResponse(
            content=template,
            headers={
                "Content-Disposition": "attachment; filename=lamb_bulk_import_template.json"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/org-admin/users/enable-bulk",
    tags=["Organization Admin - Bulk Operations"],
    summary="Bulk Enable Users",
    description="""Enable multiple user accounts at once. Only affects users 
    in the admin's organization.
    
Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users/enable-bulk' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "user_ids": [1, 2, 3, 4, 5]
}'
```
    """,
    dependencies=[Depends(security)]
)
async def org_admin_bulk_enable_users(
    request: Request,
    action_data: BulkUserActionRequest,
    org: Optional[str] = None
):
    """Bulk enable users (org-admin version)"""
    from schemas import BulkUserActionRequest
    from .bulk_operations import log_bulk_operation
    
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        admin_user_id = admin_info['user_id']
        admin_email = admin_info['user_email']
        
        # Validate request
        if not action_data.user_ids or len(action_data.user_ids) == 0:
            raise HTTPException(status_code=400, detail="No user IDs provided")
        
        if len(action_data.user_ids) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 users per operation")
        
        # Filter to only users in same organization
        valid_user_ids = []
        for user_id in action_data.user_ids:
            user = db_manager.get_creator_user_by_id(user_id)
            if user and user['organization_id'] == org_id:
                valid_user_ids.append(user_id)
        
        if not valid_user_ids:
            raise HTTPException(
                status_code=400,
                detail="No valid users found in your organization"
            )
        
        # Execute bulk enable
        result = db_manager.enable_users_bulk(valid_user_ids)
        
        # Log the operation
        log_bulk_operation(
            db_manager=db_manager,
            organization_id=org_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            operation_type='user_activation',
            total_count=len(valid_user_ids),
            success_count=len(result['success']),
            failure_count=len(result['failed']),
            details={
                "user_ids": valid_user_ids,
                "results": result
            }
        )
        
        logger.info(
            f"Bulk enable by {admin_email}: "
            f"{len(result['success'])} enabled, "
            f"{len(result['failed'])} failed"
        )
        
        return {
            "success": True,
            "enabled": len(result['success']),
            "failed": len(result['failed']),
            "already_enabled": len(result['already_enabled']),
            "details": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk enable: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/org-admin/users/disable-bulk",
    tags=["Organization Admin - Bulk Operations"],
    summary="Bulk Disable Users",
    description="""Disable multiple user accounts at once. Only affects users 
    in the admin's organization. Admin cannot disable themselves.
    
Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/users/disable-bulk' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "user_ids": [1, 2, 3, 4, 5]
}'
```
    """,
    dependencies=[Depends(security)]
)
async def org_admin_bulk_disable_users(
    request: Request,
    action_data: BulkUserActionRequest,
    org: Optional[str] = None
):
    """Bulk disable users (org-admin version)"""
    from schemas import BulkUserActionRequest
    from .bulk_operations import log_bulk_operation
    
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        admin_user_id = admin_info['user_id']
        admin_email = admin_info['user_email']
        
        # Validate request
        if not action_data.user_ids or len(action_data.user_ids) == 0:
            raise HTTPException(status_code=400, detail="No user IDs provided")
        
        if len(action_data.user_ids) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 users per operation")
        
        # Remove self from list (prevent self-disable)
        user_ids_to_disable = [uid for uid in action_data.user_ids if uid != admin_user_id]
        
        if len(user_ids_to_disable) != len(action_data.user_ids):
            logger.warning(f"Removed self ({admin_user_id}) from bulk disable list")
        
        if not user_ids_to_disable:
            raise HTTPException(
                status_code=400,
                detail="Cannot disable yourself"
            )
        
        # Filter to only users in same organization
        valid_user_ids = []
        for user_id in user_ids_to_disable:
            user = db_manager.get_creator_user_by_id(user_id)
            if user and user['organization_id'] == org_id:
                valid_user_ids.append(user_id)
        
        if not valid_user_ids:
            raise HTTPException(
                status_code=400,
                detail="No valid users found in your organization"
            )
        
        # Execute bulk disable
        result = db_manager.disable_users_bulk(valid_user_ids)
        
        # Log the operation
        log_bulk_operation(
            db_manager=db_manager,
            organization_id=org_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            operation_type='user_deactivation',
            total_count=len(valid_user_ids),
            success_count=len(result['success']),
            failure_count=len(result['failed']),
            details={
                "user_ids": valid_user_ids,
                "results": result
            }
        )
        
        logger.info(
            f"Bulk disable by {admin_email}: "
            f"{len(result['success'])} disabled, "
            f"{len(result['failed'])} failed"
        )
        
        return {
            "success": True,
            "disabled": len(result['success']),
            "failed": len(result['failed']),
            "already_disabled": len(result['already_disabled']),
            "details": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk disable: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Organization Settings Management
# ============================================================================
@router.get(
    "/org-admin/settings/signup", 
    tags=["Organization Admin - Settings"],
    summary="Get Signup Settings",
    description="Get current signup settings for the organization",
    dependencies=[Depends(security)]
)
async def get_signup_settings(request: Request, org: Optional[str] = None):
    """Get organization signup settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        organization = admin_info['organization']
        
        config = organization.get('config', {})
        features = config.get('features', {})
        
        return {
            "signup_enabled": features.get('signup_enabled', False),
            "signup_key": features.get('signup_key', ''),
            "signup_key_masked": bool(features.get('signup_key'))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signup settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/org-admin/settings/signup",
    tags=["Organization Admin - Settings"],
    summary="Update Signup Settings", 
    description="""Update signup settings for the organization.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/settings/signup' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "signup_enabled": true,
  "signup_key": "my-org-signup-key-2024"
}'
```
    """,
    dependencies=[Depends(security)]
)
async def update_signup_settings(request: Request, settings: OrgAdminSignupSettings, org: Optional[str] = None):
    """Update organization signup settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        organization = admin_info['organization']
        
        # Validate signup key if signup is enabled
        if settings.signup_enabled:
            if not settings.signup_key or len(settings.signup_key.strip()) == 0:
                raise HTTPException(status_code=400, detail="Signup key is required when signup is enabled")
            
            # Validate signup key format
            is_valid, error_msg = db_manager.validate_signup_key_format(settings.signup_key)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid signup key: {error_msg}")
            
            # Check uniqueness (excluding current organization)
            if not db_manager.validate_signup_key_uniqueness(settings.signup_key, exclude_org_id=org_id):
                raise HTTPException(status_code=400, detail="Signup key already exists in another organization")
        
        # Update organization configuration
        config = organization.get('config', {})
        if 'features' not in config:
            config['features'] = {}
        
        config['features']['signup_enabled'] = settings.signup_enabled
        if settings.signup_enabled and settings.signup_key:
            config['features']['signup_key'] = settings.signup_key.strip()
        elif 'signup_key' in config['features']:
            del config['features']['signup_key']
        
        # Save configuration
        if not db_manager.update_organization_config(org_id, config):
            raise HTTPException(status_code=500, detail="Failed to update signup settings")
        
        return {"message": "Signup settings updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating signup settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/org-admin/settings/api",
    tags=["Organization Admin - Settings"], 
    summary="Get API Settings",
    description="Get current API configuration for the organization",
    dependencies=[Depends(security)]
)
async def get_api_settings(request: Request, org: Optional[str] = None):
    """Get organization API settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        organization = admin_info['organization']
        
        config = organization.get('config', {})
        setups = config.get('setups', {})
        default_setup = setups.get('default', {})
        providers = default_setup.get('providers', {})
        
        # Get API status to show available models
        from .api_status_checker import check_organization_api_status
        try:
            api_status = await check_organization_api_status(config)
        except Exception as e:
            logger.error(f"Error checking API status for settings: {e}")
            api_status = {"providers": {}}
        
        # Get currently selected models and default models for each provider
        selected_models = {}
        default_models = {}
        available_models = {}

        for provider_name, provider_status in api_status.get("providers", {}).items():
            if provider_status.get("status") == "working":
                available_models[provider_name] = provider_status.get("models", [])

                # Get selected models from provider config
                provider_config = providers.get(provider_name, {})
                selected_models[provider_name] = provider_config.get("models", [])

                # If no models are explicitly selected, default to all available
                if not selected_models[provider_name] and available_models[provider_name]:
                    selected_models[provider_name] = available_models[provider_name].copy()

                # Get default model from provider config
                default_models[provider_name] = provider_config.get("default_model", "")

        # Get global model configurations
        global_default_model = default_setup.get('global_default_model', {})
        small_fast_model = default_setup.get('small_fast_model', {})

        return {
            "openai_api_key_set": bool(providers.get('openai', {}).get('api_key')),
            "openai_base_url": providers.get('openai', {}).get('base_url') or config.OPENAI_BASE_URL,
            "ollama_base_url": providers.get('ollama', {}).get('base_url') or config.OLLAMA_BASE_URL,
            "available_models": available_models,
            "selected_models": selected_models,
            "default_models": default_models,
            "global_default_model": global_default_model,
            "small_fast_model": small_fast_model,
            "api_status": api_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/org-admin/settings/api",
    tags=["Organization Admin - Settings"],
    summary="Update API Settings",
    description="""Update API configuration for the organization.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/settings/api' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "openai_api_key": "sk-...",
  "available_models": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
  "model_limits": {
    "gpt-4": {"daily_limit": 100, "per_user_limit": 10},
    "gpt-3.5-turbo": {"daily_limit": 1000, "per_user_limit": 50}
  }
}'
```
    """,
    dependencies=[Depends(security)]
)
async def update_api_settings(request: Request, settings: OrgAdminApiSettings, org: Optional[str] = None):
    """Update organization API settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        organization = admin_info['organization']
        
        # Update organization configuration
        config = organization.get('config', {})
        
        # Ensure setups structure exists
        if 'setups' not in config:
            config['setups'] = {}
        if 'default' not in config['setups']:
            config['setups']['default'] = {}
        if 'providers' not in config['setups']['default']:
            config['setups']['default']['providers'] = {}
        
        providers = config['setups']['default']['providers']
        
        # Update OpenAI configuration
        if settings.openai_api_key:
            if 'openai' not in providers:
                providers['openai'] = {}
            providers['openai']['api_key'] = settings.openai_api_key
        
        if settings.openai_base_url:
            if 'openai' not in providers:
                providers['openai'] = {}
            providers['openai']['base_url'] = settings.openai_base_url.rstrip('/')
            logger.info(f"Updated OpenAI base URL to: {settings.openai_base_url}")
        
        # Update Ollama configuration
        if settings.ollama_base_url:
            if 'ollama' not in providers:
                providers['ollama'] = {}
            providers['ollama']['base_url'] = settings.ollama_base_url.rstrip('/')
            logger.info(f"Updated Ollama base URL to: {settings.ollama_base_url}")
        
        # Update selected models per provider
        if settings.selected_models is not None:
            for provider_name, model_list in settings.selected_models.items():
                if provider_name not in providers:
                    providers[provider_name] = {}
                providers[provider_name]['models'] = model_list
                logger.info(f"Updated {provider_name} enabled models: {len(model_list)} models selected")

        # Update default models per provider
        if settings.default_models is not None:
            for provider_name, default_model in settings.default_models.items():
                if provider_name not in providers:
                    providers[provider_name] = {}
                providers[provider_name]['default_model'] = default_model
                logger.info(f"Updated {provider_name} default model: {default_model}")

            # Auto-manage default models: ensure default model is in enabled models list
            for provider_name, default_model in settings.default_models.items():
                if default_model and provider_name in settings.selected_models:
                    enabled_models = settings.selected_models[provider_name]
                    if default_model not in enabled_models:
                        if enabled_models:
                            # Auto-select first enabled model as default
                            new_default = enabled_models[0]
                            providers[provider_name]['default_model'] = new_default
                            settings.default_models[provider_name] = new_default
                            logger.info(f"Auto-corrected {provider_name} default model from '{default_model}' to '{new_default}' (not in enabled models)")
                        else:
                            # No models enabled, clear default
                            providers[provider_name]['default_model'] = ""
                            settings.default_models[provider_name] = ""
                            logger.info(f"Cleared {provider_name} default model (no models enabled)")

            # Auto-update assistant_defaults if current default model is not in enabled list
            if 'assistant_defaults' not in config:
                config['assistant_defaults'] = {}

            assistant_defaults = config['assistant_defaults']
            current_connector = assistant_defaults.get('connector')
            current_llm = assistant_defaults.get('llm')

            # Check if current connector's default model is still valid
            if current_connector and current_connector in settings.selected_models:
                enabled_models_for_connector = settings.selected_models[current_connector]

                # If current llm is not in the newly enabled models list
                if current_llm and current_llm not in enabled_models_for_connector:
                    if enabled_models_for_connector:  # If there are models enabled
                        # Update to first enabled model
                        new_default_llm = enabled_models_for_connector[0]
                        assistant_defaults['llm'] = new_default_llm
                        config['assistant_defaults'] = assistant_defaults
                        logger.info(f"Auto-updated assistant_defaults.llm from '{current_llm}' to '{new_default_llm}' (not in enabled models for {current_connector})")
                    else:
                        # No models enabled for this connector - clear the default
                        logger.warning(f"No models enabled for connector '{current_connector}', clearing assistant_defaults.llm")
                        assistant_defaults['llm'] = ''
                        config['assistant_defaults'] = assistant_defaults
        
        # Legacy support: Update available models (deprecated)
        if settings.available_models is not None:
            if 'models' not in config:
                config['models'] = {}
            config['models']['available'] = settings.available_models
        
        # Update model limits
        if settings.model_limits is not None:
            if 'models' not in config:
                config['models'] = {}
            config['models']['limits'] = settings.model_limits

        # Update global-default-model configuration
        if settings.global_default_model is not None:
            provider = settings.global_default_model.get('provider', '')
            model = settings.global_default_model.get('model', '')
            
            # Validate that the provider exists and is enabled
            if provider and model:
                if provider not in providers:
                    logger.warning(f"Global-default-model provider '{provider}' not configured, ignoring")
                else:
                    # Validate that the model is in the enabled models list
                    enabled_models = providers.get(provider, {}).get('models', [])
                    if model not in enabled_models:
                        logger.warning(f"Global-default-model '{model}' not in enabled models for {provider}, auto-correcting")
                        if enabled_models:
                            # Auto-select first enabled model
                            model = enabled_models[0]
                            settings.global_default_model['model'] = model
                            logger.info(f"Auto-corrected global-default-model to '{model}'")
                        else:
                            # No models enabled, clear the configuration
                            settings.global_default_model = {"provider": "", "model": ""}
                            logger.warning(f"No models enabled for {provider}, clearing global-default-model")
                    
                    # Save to config
                    if 'default' not in config['setups']:
                        config['setups']['default'] = {}
                    
                    config['setups']['default']['global_default_model'] = {
                        "provider": settings.global_default_model.get('provider', ''),
                        "model": settings.global_default_model.get('model', '')
                    }
                    logger.info(f"Updated global-default-model: {settings.global_default_model}")
            else:
                # Clear global-default-model if empty
                if 'default' in config['setups']:
                    config['setups']['default']['global_default_model'] = {"provider": "", "model": ""}
                logger.info("Cleared global-default-model configuration")

        # Update small-fast-model configuration
        if settings.small_fast_model is not None:
            provider = settings.small_fast_model.get('provider', '')
            model = settings.small_fast_model.get('model', '')
            
            # Validate that the provider exists and is enabled
            if provider and model:
                if provider not in providers:
                    logger.warning(f"Small-fast-model provider '{provider}' not configured, ignoring")
                else:
                    # Validate that the model is in the enabled models list
                    enabled_models = providers.get(provider, {}).get('models', [])
                    if model not in enabled_models:
                        logger.warning(f"Small-fast-model '{model}' not in enabled models for {provider}, auto-correcting")
                        if enabled_models:
                            # Auto-select first enabled model
                            model = enabled_models[0]
                            settings.small_fast_model['model'] = model
                            logger.info(f"Auto-corrected small-fast-model to '{model}'")
                        else:
                            # No models enabled, clear the configuration
                            settings.small_fast_model = {"provider": "", "model": ""}
                            logger.warning(f"No models enabled for {provider}, clearing small-fast-model")
                    
                    # Save to config
                    if 'default' not in config['setups']:
                        config['setups']['default'] = {}
                    
                    config['setups']['default']['small_fast_model'] = {
                        "provider": settings.small_fast_model.get('provider', ''),
                        "model": settings.small_fast_model.get('model', '')
                    }
                    logger.info(f"Updated small-fast-model: {settings.small_fast_model}")
            else:
                # Clear small-fast-model if empty
                if 'default' in config['setups']:
                    config['setups']['default']['small_fast_model'] = {"provider": "", "model": ""}
                logger.info("Cleared small-fast-model configuration")

        # Save configuration
        if not db_manager.update_organization_config(org_id, config):
            raise HTTPException(status_code=500, detail="Failed to update API settings")

        return {"message": "API settings updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# KNOWLEDGE BASE SERVER SETTINGS MANAGEMENT
# ============================================================================

@router.get(
    "/org-admin/settings/kb",
    tags=["Organization Admin - Settings"],
    summary="Get KB Server Settings",
    description="""Get Knowledge Base server configuration for the organization.
    
Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/settings/kb' \\
-H 'Authorization: Bearer <org_admin_token>'
```

Example Success Response:
```json
{
  "url": "http://kb:9090",
  "api_key_set": true,
  "embedding_model": "all-MiniLM-L6-v2",
  "collection_defaults": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```
    """,
    dependencies=[Depends(security)]
)
async def get_kb_settings(request: Request, org: Optional[str] = None):
    """Get organization KB server settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        organization = admin_info['organization']
        
        config = organization.get('config', {})
        kb_server = config.get('kb_server', {})
        
        return {
            "url": kb_server.get('url', ''),
            "api_key_set": bool(kb_server.get('api_key')),
            "embedding_model": kb_server.get('embedding_model', ''),
            "collection_defaults": kb_server.get('collection_defaults', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting KB settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/org-admin/settings/kb/test",
    tags=["Organization Admin - Settings"],
    summary="Test KB Server Connection",
    description="""Test connection to Knowledge Base server before saving configuration.
    
Tests both the health endpoint and API authentication.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/admin/org-admin/settings/kb/test' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "url": "http://kb:9090",
  "api_key": "your-api-key"
}'
```

Example Success Response:
```json
{
  "success": true,
  "message": "Successfully connected to KB server",
  "version": "1.0.0",
  "collections_count": 5
}
```

Example Error Response:
```json
{
  "success": false,
  "message": "Connection timeout - check if KB server is running and URL is correct"
}
```
    """,
    dependencies=[Depends(security)]
)
async def test_kb_connection(
    request: Request,
    test_data: KBTestRequest,
    org: Optional[str] = None
):
    """Test connection to KB server"""
    try:
        # Verify admin access and get organization config
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        organization = admin_info['organization']
        
        # Get existing KB config to use existing API key if requested
        config = organization.get('config', {})
        existing_kb_config = config.get('kb_server', {})
        
        # Use existing API key if placeholder is sent
        api_key_to_test = test_data.api_key
        if test_data.api_key == 'USE_EXISTING':
            api_key_to_test = existing_kb_config.get('api_key', '')
            if not api_key_to_test:
                return {
                    "success": False,
                    "message": "No existing API key found. Please enter one to test."
                }
        
        # Validate URL format
        url = test_data.url.rstrip('/')
        if not url.startswith(('http://', 'https://')):
            return {
                "success": False,
                "message": "URL must start with http:// or https://"
            }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Test 1: Health endpoint
                health_response = await client.get(f"{url}/health")
                
                if health_response.status_code != 200:
                    return {
                        "success": False,
                        "message": f"KB server health check failed (status: {health_response.status_code})"
                    }
                
                health_data = health_response.json()
                
                # Test 2: Collections endpoint (verifies API key)
                # Use an endpoint that requires authentication to properly validate the API key
                # Try /api/collections first, if that doesn't work, try /database/status
                collections_response = await client.get(
                    f"{url}/api/collections",
                    headers={"Authorization": f"Bearer {api_key_to_test}"}
                )
                
                # If collections endpoint returns 404, try database/status as alternative auth test
                if collections_response.status_code == 404:
                    # Try alternative endpoint that requires auth
                    db_status_response = await client.get(
                        f"{url}/database/status",
                        headers={"Authorization": f"Bearer {api_key_to_test}"}
                    )
                    
                    if db_status_response.status_code == 401:
                        return {
                            "success": False,
                            "message": "API key authentication failed - invalid key"
                        }
                    elif db_status_response.status_code == 403:
                        return {
                            "success": False,
                            "message": "API key authentication failed - insufficient permissions"
                        }
                    elif db_status_response.status_code != 200:
                        return {
                            "success": False,
                            "message": f"API key validation failed (status: {db_status_response.status_code})"
                        }
                    # If database/status returns 200, API key is valid
                    # Collections endpoint might not exist or return 404 for empty collections
                elif collections_response.status_code == 401:
                    return {
                        "success": False,
                        "message": "API key authentication failed - invalid key"
                    }
                elif collections_response.status_code == 403:
                    return {
                        "success": False,
                        "message": "API key authentication failed - insufficient permissions"
                    }
                elif collections_response.status_code != 200:
                    return {
                        "success": False,
                        "message": f"API endpoint test failed (status: {collections_response.status_code})"
                    }
                
                # Success - extract info (only if collections endpoint returned 200)
                collections_data = {}
                if collections_response.status_code == 200:
                    try:
                        collections_data = collections_response.json()
                    except:
                        pass
                
                return {
                    "success": True,
                    "message": "Successfully connected to KB server",
                    "version": health_data.get('version', 'unknown')
                }
                
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": "Connection timeout - check if KB server is running and URL is correct"
            }
        except httpx.ConnectError:
            return {
                "success": False,
                "message": "Connection refused - check if KB server is running at this URL"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing KB connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/org-admin/settings/kb",
    tags=["Organization Admin - Settings"],
    summary="Update KB Server Settings",
    description="""Update Knowledge Base server configuration.
    
Connection is tested before saving. If test fails, update is rejected.

Example Request:
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/settings/kb' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "url": "http://kb:9090",
  "api_key": "new-api-key",
  "embedding_model": "all-MiniLM-L6-v2",
  "collection_defaults": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}'
```

Example Success Response:
```json
{
  "message": "KB server settings updated successfully"
}
```
    """,
    dependencies=[Depends(security)]
)
async def update_kb_settings(
    request: Request,
    settings: OrgAdminKBSettings,
    org: Optional[str] = None
):
    """Update organization KB server settings"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        organization = admin_info['organization']
        
        # Validate URL format
        url = settings.url.rstrip('/')
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
        
        # Get existing config to preserve API key if not provided
        config = organization.get('config', {})
        existing_kb_config = config.get('kb_server', {})
        api_key_to_test = settings.api_key if settings.api_key else existing_kb_config.get('api_key', '')
        
        # Mandatory connection test before saving
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Test health endpoint
                health_response = await client.get(f"{url}/health")
                
                if health_response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"KB server health check failed (status: {health_response.status_code})"
                    )
                
                # Test collections endpoint (verifies API key)
                # Use an endpoint that requires authentication to properly validate the API key
                collections_response = await client.get(
                    f"{url}/api/collections",
                    headers={"Authorization": f"Bearer {api_key_to_test}"}
                )
                
                # If collections endpoint returns 404, try database/status as alternative auth test
                if collections_response.status_code == 404:
                    # Try alternative endpoint that requires auth
                    db_status_response = await client.get(
                        f"{url}/database/status",
                        headers={"Authorization": f"Bearer {api_key_to_test}"}
                    )
                    
                    if db_status_response.status_code == 401:
                        raise HTTPException(
                            status_code=400,
                            detail="API key authentication failed - invalid key"
                        )
                    elif db_status_response.status_code == 403:
                        raise HTTPException(
                            status_code=400,
                            detail="API key authentication failed - insufficient permissions"
                        )
                    elif db_status_response.status_code != 200:
                        raise HTTPException(
                            status_code=400,
                            detail=f"API key validation failed (status: {db_status_response.status_code})"
                        )
                    # If database/status returns 200, API key is valid
                elif collections_response.status_code == 401:
                    raise HTTPException(
                        status_code=400,
                        detail="API key authentication failed - invalid key"
                    )
                elif collections_response.status_code == 403:
                    raise HTTPException(
                        status_code=400,
                        detail="API key authentication failed - insufficient permissions"
                    )
                elif collections_response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"API endpoint test failed (status: {collections_response.status_code})"
                    )
                    
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=400,
                detail="Connection timeout - check if KB server is running and URL is correct"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=400,
                detail="Connection refused - check if KB server is running at this URL"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {str(e)}")
        
        # Connection test passed - update configuration
        if 'kb_server' not in config:
            config['kb_server'] = {}
        
        config['kb_server']['url'] = url
        
        # Update API key only if provided
        if settings.api_key:
            config['kb_server']['api_key'] = settings.api_key
        
        # Update embedding model if provided
        if settings.embedding_model:
            config['kb_server']['embedding_model'] = settings.embedding_model
        
        # Update collection defaults if provided
        if settings.collection_defaults:
            config['kb_server']['collection_defaults'] = settings.collection_defaults
        
        # Save configuration
        if not db_manager.update_organization_config(org_id, config):
            raise HTTPException(status_code=500, detail="Failed to update KB settings")
        
        logger.info(f"Organization admin {admin_info['user_email']} updated KB server settings")
        return {"message": "KB server settings updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating KB settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ORGANIZATION ADMIN ASSISTANT MANAGEMENT ENDPOINTS
# These endpoints allow organization admins to view and manage access to 
# assistants within their organization
# ============================================================================

class AssistantAccessUpdate(BaseModel):
    user_emails: List[str] = Field(..., description="List of user emails to grant/revoke access")
    action: str = Field(..., description="Action to perform: 'grant' or 'revoke'")

class AssistantListItem(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner: str
    published: bool
    group_id: Optional[str]
    created_at: int

class AssistantAccessInfo(BaseModel):
    assistant: AssistantListItem
    users_with_access: List[str]  # emails
    organization_users: List[Dict[str, Any]]  # all org users for selection

@router.get(
    "/org-admin/assistants",
    tags=["Organization Admin - Assistant Management"],
    summary="List All Organization Assistants",
    description="""List all assistants in the organization admin's organization.
    
Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/assistants' \\
-H 'Authorization: Bearer <org_admin_token>'
```

Example Response:
```json
{
  "assistants": [
    {
      "id": 1,
      "name": "Math_Tutor",
      "description": "Helps with math problems",
      "owner": "prof@university.edu",
      "published": true,
      "group_id": "assistant_1",
      "created_at": 1678886400
    }
  ]
}
```
    """,
    dependencies=[Depends(security)]
)
async def list_organization_assistants(request: Request, org: Optional[str] = None):
    """List all assistants in the organization"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        # Get all assistants in organization
        assistants = db_manager.get_assistants_by_organization(org_id)
        
        # Format response
        assistants_list = []
        for asst in assistants:
            assistants_list.append(AssistantListItem(
                id=asst['id'],
                name=asst['name'],
                description=asst.get('description'),
                owner=asst['owner'],
                published=asst.get('published', False),
                group_id=asst.get('group_id'),
                created_at=asst.get('created_at', 0)
            ))
        
        return {"assistants": assistants_list}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing organization assistants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/org-admin/assistants/{assistant_id}/access",
    tags=["Organization Admin - Assistant Management"],
    summary="Get Assistant Access Info",
    description="""Get information about who has access to an assistant and all organization users.
    
Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/org-admin/assistants/123/access' \\
-H 'Authorization: Bearer <org_admin_token>'
```

Example Response:
```json
{
  "assistant": {
    "id": 123,
    "name": "Math_Tutor",
    "owner": "prof@university.edu",
    "published": true,
    "group_id": "assistant_123"
  },
  "users_with_access": [
    "prof@university.edu",
    "student1@university.edu"
  ],
  "organization_users": [
    {
      "id": 1,
      "email": "prof@university.edu",
      "name": "Professor Smith",
      "user_type": "creator",
      "is_owner": true
    },
    {
      "id": 2,
      "email": "student1@university.edu",
      "name": "Student One",
      "user_type": "end_user",
      "is_owner": false
    }
  ]
}
```
    """,
    dependencies=[Depends(security)],
    response_model=AssistantAccessInfo
)
async def get_assistant_access(request: Request, assistant_id: int, org: Optional[str] = None):
    """Get access information for an assistant"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        # Get assistant and verify it belongs to this organization
        assistants = db_manager.get_assistants_by_organization(org_id)
        assistant = next((a for a in assistants if a['id'] == assistant_id), None)
        
        if not assistant:
            raise HTTPException(
                status_code=404, 
                detail="Assistant not found in this organization"
            )
        
        # Get users with access (from OWI group)
        users_with_access = []
        if assistant.get('group_id'):
            from lamb.owi_bridge.owi_group import OwiGroupManager
            group_manager = OwiGroupManager()
            users_with_access = group_manager.get_group_users_by_emails(assistant['group_id'])
        
        # Get all organization users
        org_users = db_manager.get_organization_users(org_id)
        organization_users = []
        for user in org_users:
            organization_users.append({
                "id": user['id'],
                "email": user['email'],
                "name": user['name'],
                "user_type": user.get('user_type', 'creator'),
                "is_owner": user['email'] == assistant['owner']
            })
        
        return AssistantAccessInfo(
            assistant=AssistantListItem(
                id=assistant['id'],
                name=assistant['name'],
                description=assistant.get('description'),
                owner=assistant['owner'],
                published=assistant.get('published', False),
                group_id=assistant.get('group_id'),
                created_at=assistant.get('created_at', 0)
            ),
            users_with_access=users_with_access,
            organization_users=organization_users
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assistant access info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/org-admin/assistants/{assistant_id}/access",
    tags=["Organization Admin - Assistant Management"],
    summary="Update Assistant Access",
    description="""Grant or revoke access to an assistant for multiple users.
    The owner cannot be removed from access.
    
Example Request (Grant Access):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/assistants/123/access' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "user_emails": ["student1@university.edu", "student2@university.edu"],
  "action": "grant"
}'
```

Example Request (Revoke Access):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/org-admin/assistants/123/access' \\
-H 'Authorization: Bearer <org_admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{
  "user_emails": ["student1@university.edu"],
  "action": "revoke"
}'
```

Example Success Response:
```json
{
  "message": "Access updated successfully",
  "results": {
    "added": ["student1@university.edu", "student2@university.edu"],
    "removed": [],
    "already_member": [],
    "not_found": [],
    "errors": []
  }
}
```
    """,
    dependencies=[Depends(security)]
)
async def update_assistant_access(
    request: Request, 
    assistant_id: int, 
    access_update: AssistantAccessUpdate,
    org: Optional[str] = None
):
    """Grant or revoke access to an assistant for users"""
    try:
        # If org parameter is provided, get organization by slug
        target_org_id = None
        if org:
            target_organization = db_manager.get_organization_by_slug(org)
            if not target_organization:
                raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
            target_org_id = target_organization['id']
        
        admin_info = await verify_organization_admin_access(request, target_org_id)
        org_id = admin_info['organization_id']
        
        # Validate action
        if access_update.action not in ['grant', 'revoke']:
            raise HTTPException(
                status_code=400, 
                detail="Action must be 'grant' or 'revoke'"
            )
        
        # Get assistant and verify it belongs to this organization
        assistants = db_manager.get_assistants_by_organization(org_id)
        assistant = next((a for a in assistants if a['id'] == assistant_id), None)
        
        if not assistant:
            raise HTTPException(
                status_code=404, 
                detail="Assistant not found in this organization"
            )
        
        # Check if assistant has a group
        if not assistant.get('group_id'):
            raise HTTPException(
                status_code=400,
                detail="Assistant does not have an OWI group. Only published assistants can have access managed."
            )
        
        # Prevent owner from being removed
        if access_update.action == 'revoke' and assistant['owner'] in access_update.user_emails:
            raise HTTPException(
                status_code=403,
                detail="Cannot remove the assistant owner from access"
            )
        
        # Verify all users belong to the organization
        org_users = db_manager.get_organization_users(org_id)
        org_user_emails = {user['email'] for user in org_users}
        
        for email in access_update.user_emails:
            if email not in org_user_emails:
                raise HTTPException(
                    status_code=400,
                    detail=f"User {email} does not belong to this organization"
                )
        
        # Perform the action
        from lamb.owi_bridge.owi_group import OwiGroupManager
        group_manager = OwiGroupManager()
        
        if access_update.action == 'grant':
            result = group_manager.add_users_to_group(
                assistant['group_id'], 
                access_update.user_emails
            )
        else:  # revoke
            result = group_manager.remove_users_from_group(
                assistant['group_id'], 
                access_update.user_emails
            )
        
        if result.get('status') == 'error':
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update access: {result.get('error')}"
            )
        
        return {
            "message": "Access updated successfully",
            "results": result.get('results', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assistant access: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Assistant Defaults Management Endpoints

@router.get("/organizations/{slug}/assistant-defaults")
async def get_organization_assistant_defaults(
    slug: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get assistant defaults for a specific organization
    
    This endpoint retrieves the assistant_defaults configuration for the specified organization.
    Only accessible by organization admins or system admins.
    
    Args:
        slug: Organization slug identifier
        credentials: Bearer token for authentication
    
    Returns:
        Dict containing the assistant_defaults object
    
    Raises:
        HTTPException: 401 if unauthorized, 404 if organization not found, 500 on server error
    """
    try:
        # Get authorization header
        auth_header = f"Bearer {credentials.credentials}"
        
        # Check admin authorization
        user_info = get_user_organization_admin_info(auth_header)
        if not user_info:
            raise HTTPException(status_code=401, detail="Admin access required")
        
        # Use OrganizationService instead of HTTP call
        org_service = OrganizationService()
        defaults = org_service.get_assistant_defaults(slug)
        
        if defaults is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        return defaults
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching assistant defaults for {slug}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/organizations/{slug}/assistant-defaults")
async def update_organization_assistant_defaults(
    slug: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update assistant defaults for a specific organization
    
    This endpoint updates the assistant_defaults configuration for the specified organization.
    Only accessible by organization admins or system admins.
    
    Args:
        slug: Organization slug identifier
        request: Request containing the assistant_defaults JSON in body
        credentials: Bearer token for authentication
    
    Returns:
        Dict with success message
    
    Raises:
        HTTPException: 401 if unauthorized, 404 if organization not found, 500 on server error
    """
    try:
        # Get authorization header
        auth_header = f"Bearer {credentials.credentials}"
        
        # Check admin authorization
        user_info = get_user_organization_admin_info(auth_header)
        if not user_info:
            raise HTTPException(status_code=401, detail="Admin access required")
        
        # Get request body
        body = await request.json()
        
        # Use OrganizationService instead of HTTP call
        org_service = OrganizationService()
        updated_defaults = org_service.update_assistant_defaults(slug, body)
        
        if updated_defaults is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        return {"success": True, "assistant_defaults": updated_defaults}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assistant defaults for {slug}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# System Statistics Response Model
class SystemStatsResponse(BaseModel):
    users: Dict[str, int] = Field(..., description="User statistics")
    organizations: Dict[str, int] = Field(..., description="Organization statistics")
    assistants: Dict[str, int] = Field(..., description="Assistant statistics")
    knowledge_bases: Dict[str, int] = Field(..., description="Knowledge base statistics")
    rubrics: Dict[str, int] = Field(..., description="Rubric statistics")
    templates: Dict[str, int] = Field(..., description="Prompt template statistics")


@router.get(
    "/system-stats",
    tags=["System Administration"],
    summary="Get System-Wide Statistics",
    description="""Get comprehensive statistics for the entire LAMB system including counts
of users, organizations, assistants, knowledge bases, rubrics, and prompt templates.

**Requires:** System administrator privileges

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/system-stats' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "users": {
    "total": 150,
    "enabled": 145,
    "disabled": 5,
    "creators": 50,
    "end_users": 100
  },
  "organizations": {
    "total": 10,
    "active": 8,
    "inactive": 2
  },
  "assistants": {
    "total": 250,
    "published": 120,
    "unpublished": 130
  },
  "knowledge_bases": {
    "total": 80,
    "shared": 25
  },
  "rubrics": {
    "total": 45,
    "public": 15
  },
  "templates": {
    "total": 60,
    "shared": 20
  }
}
```
    """,
    response_model=SystemStatsResponse,
    dependencies=[Depends(security)],
    responses={
        200: {"model": SystemStatsResponse, "description": "System statistics retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin privileges required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_system_stats(request: Request):
    """Get system-wide statistics for admin dashboard"""
    try:
        # Verify admin access
        await verify_admin_access(request)
        
        connection = db_manager.get_connection()
        if not connection:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            cursor = connection.cursor()
            table_prefix = db_manager.table_prefix
            
            # User statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}Creator_users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}Creator_users WHERE enabled = 1")
            enabled_users = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}Creator_users WHERE user_type = 'creator'")
            creator_users = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}Creator_users WHERE user_type = 'end_user'")
            end_users = cursor.fetchone()[0]
            
            # Organization statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}organizations")
            total_orgs = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}organizations WHERE status = 'active'")
            active_orgs = cursor.fetchone()[0]
            
            # Assistant statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}assistants")
            total_assistants = cursor.fetchone()[0]
            
            # Published assistants are those with a valid entry in assistant_publish table
            cursor.execute(f"""
                SELECT COUNT(DISTINCT a.id) FROM {table_prefix}assistants a
                INNER JOIN {table_prefix}assistant_publish p ON a.id = p.assistant_id
                WHERE p.oauth_consumer_name IS NOT NULL AND p.oauth_consumer_name != 'null'
            """)
            published_assistants = cursor.fetchone()[0]
            
            # Knowledge base statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}kb_registry")
            total_kbs = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}kb_registry WHERE is_shared = 1")
            shared_kbs = cursor.fetchone()[0]
            
            # Rubric statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}rubrics")
            total_rubrics = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}rubrics WHERE is_public = 1")
            public_rubrics = cursor.fetchone()[0]
            
            # Prompt template statistics
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}prompt_templates")
            total_templates = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_prefix}prompt_templates WHERE is_shared = 1")
            shared_templates = cursor.fetchone()[0]
            
            return {
                "users": {
                    "total": total_users,
                    "enabled": enabled_users,
                    "disabled": total_users - enabled_users,
                    "creators": creator_users,
                    "end_users": end_users
                },
                "organizations": {
                    "total": total_orgs,
                    "active": active_orgs,
                    "inactive": total_orgs - active_orgs
                },
                "assistants": {
                    "total": total_assistants,
                    "published": published_assistants,
                    "unpublished": total_assistants - published_assistants
                },
                "knowledge_bases": {
                    "total": total_kbs,
                    "shared": shared_kbs
                },
                "rubrics": {
                    "total": total_rubrics,
                    "public": public_rubrics
                },
                "templates": {
                    "total": total_templates,
                    "shared": shared_templates
                }
            }
            
        finally:
            connection.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
