"""
Prompt Templates Router for LAMB Creator Interface

This module handles CRUD operations for prompt templates, including:
- Creating, updating, and deleting templates
- Listing user's own templates and shared organization templates
- Duplicating templates
- Exporting templates as JSON
- Toggling sharing status
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import logging
import json
import time
from pydantic import BaseModel, Field
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import PromptTemplate
from .assistant_router import get_creator_user_from_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["Prompt Templates"])

# Security
security = HTTPBearer()

# ========== Pydantic Models ==========

class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    system_prompt: Optional[str] = None
    prompt_template: Optional[str] = None
    is_shared: bool = Field(default=False)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    system_prompt: Optional[str] = None
    prompt_template: Optional[str] = None
    is_shared: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class PromptTemplateResponse(BaseModel):
    id: int
    organization_id: int
    owner_email: str
    name: str
    description: Optional[str]
    system_prompt: Optional[str]
    prompt_template: Optional[str]
    is_shared: bool
    metadata: Dict[str, Any]
    created_at: int
    updated_at: int
    owner_name: Optional[str]
    is_owner: bool

class PromptTemplateListResponse(BaseModel):
    templates: List[PromptTemplateResponse]
    total: int
    page: int
    limit: int

class PromptTemplateDuplicate(BaseModel):
    new_name: Optional[str] = None

class PromptTemplateShareToggle(BaseModel):
    is_shared: bool

class PromptTemplateExportRequest(BaseModel):
    template_ids: List[int]

class PromptTemplateExportResponse(BaseModel):
    export_version: str = "1.0"
    exported_at: str
    templates: List[Dict[str, Any]]

# ========== Helper Functions ==========

def get_user_organization(creator_user: Dict[str, Any]) -> Dict[str, Any]:
    """Get organization for a creator user"""
    db_manager = LambDatabaseManager()
    
    # Get user's organization
    if creator_user.get('organization_id'):
        org = db_manager.get_organization_by_id(creator_user['organization_id'])
        if org:
            return org
    
    # Fallback to system organization
    return db_manager.get_organization_by_slug("lamb")

# ========== Endpoints ==========

@router.get("/list", response_model=PromptTemplateListResponse)
async def list_user_templates(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    List prompt templates owned by the current user.
    
    Args:
        limit: Number of templates to return (default 50)
        offset: Offset for pagination (default 0)
    
    Returns:
        List of user's templates with pagination info
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get user's organization
        organization = get_user_organization(creator_user)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get templates from database
        db_manager = LambDatabaseManager()
        templates, total = db_manager.get_user_prompt_templates(
            owner_email=creator_user['email'],
            organization_id=organization['id'],
            limit=limit,
            offset=offset
        )
        
        page = (offset // limit) + 1 if limit > 0 else 1
        
        return PromptTemplateListResponse(
            templates=[PromptTemplateResponse(**t) for t in templates],
            total=total,
            page=page,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing user templates: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing templates: {str(e)}")

@router.get("/shared", response_model=PromptTemplateListResponse)
async def list_shared_templates(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    List shared prompt templates in the user's organization (excluding user's own).
    
    Args:
        limit: Number of templates to return (default 50)
        offset: Offset for pagination (default 0)
    
    Returns:
        List of shared templates with pagination info
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get user's organization
        organization = get_user_organization(creator_user)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get shared templates from database
        db_manager = LambDatabaseManager()
        templates, total = db_manager.get_organization_shared_templates(
            organization_id=organization['id'],
            requester_email=creator_user['email'],
            limit=limit,
            offset=offset
        )
        
        page = (offset // limit) + 1 if limit > 0 else 1
        
        return PromptTemplateListResponse(
            templates=[PromptTemplateResponse(**t) for t in templates],
            total=total,
            page=page,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing shared templates: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing shared templates: {str(e)}")

@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_template(
    template_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get a specific prompt template by ID.
    
    Args:
        template_id: Template ID
    
    Returns:
        Template details
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get template from database
        db_manager = LambDatabaseManager()
        template = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Check access permissions (must be owner or template must be shared in same org)
        organization = get_user_organization(creator_user)
        if template['owner_email'] != creator_user['email']:
            # Not the owner, check if it's shared in same org
            if not template['is_shared'] or template['organization_id'] != organization['id']:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return PromptTemplateResponse(**template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting template: {str(e)}")

@router.post("/create", response_model=PromptTemplateResponse, status_code=201)
async def create_template(
    template_data: PromptTemplateCreate,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a new prompt template.
    
    Args:
        template_data: Template creation data
    
    Returns:
        Created template
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get user's organization
        organization = get_user_organization(creator_user)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Create template
        db_manager = LambDatabaseManager()
        template_dict = template_data.model_dump()
        template_dict['organization_id'] = organization['id']
        template_dict['owner_email'] = creator_user['email']
        
        template_id = db_manager.create_prompt_template(template_dict)
        
        if not template_id:
            raise HTTPException(status_code=400, detail="Failed to create template. Name may already exist.")
        
        # Get created template
        template = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        return PromptTemplateResponse(**template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_template(
    template_id: int,
    template_data: PromptTemplateUpdate,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update a prompt template (only owner can update).
    
    Args:
        template_id: Template ID
        template_data: Fields to update
    
    Returns:
        Updated template
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get existing template to verify ownership
        db_manager = LambDatabaseManager()
        existing = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        if not existing:
            raise HTTPException(status_code=404, detail="Template not found")
        
        if existing['owner_email'] != creator_user['email']:
            raise HTTPException(status_code=403, detail="Only the owner can update this template")
        
        # Update template
        updates = {k: v for k, v in template_data.model_dump(exclude_unset=True).items() if v is not None}
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        success = db_manager.update_prompt_template(
            template_id=template_id,
            updates=updates,
            owner_email=creator_user['email']
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update template")
        
        # Get updated template
        template = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        return PromptTemplateResponse(**template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Delete a prompt template (only owner can delete).
    
    Args:
        template_id: Template ID
    
    Returns:
        No content on success
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Delete template (database manager checks ownership)
        db_manager = LambDatabaseManager()
        success = db_manager.delete_prompt_template(
            template_id=template_id,
            owner_email=creator_user['email']
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Template not found or not authorized")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")

@router.post("/{template_id}/duplicate", response_model=PromptTemplateResponse, status_code=201)
async def duplicate_template(
    template_id: int,
    duplicate_data: PromptTemplateDuplicate,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Duplicate a prompt template (create a copy for current user).
    
    Args:
        template_id: Template ID to duplicate
        duplicate_data: Optional new name
    
    Returns:
        New template
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get user's organization
        organization = get_user_organization(creator_user)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Verify user can access the template
        db_manager = LambDatabaseManager()
        original = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        if not original:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Check access (must be owner or shared in same org)
        if original['owner_email'] != creator_user['email']:
            if not original['is_shared'] or original['organization_id'] != organization['id']:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Duplicate template
        new_id = db_manager.duplicate_prompt_template(
            template_id=template_id,
            new_owner_email=creator_user['email'],
            new_organization_id=organization['id'],
            new_name=duplicate_data.new_name
        )
        
        if not new_id:
            raise HTTPException(status_code=400, detail="Failed to duplicate template")
        
        # Get new template
        template = db_manager.get_prompt_template_by_id(
            template_id=new_id,
            requester_email=creator_user['email']
        )
        
        return PromptTemplateResponse(**template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error duplicating template: {str(e)}")

@router.put("/{template_id}/share", response_model=PromptTemplateResponse)
async def toggle_template_sharing(
    template_id: int,
    share_data: PromptTemplateShareToggle,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Toggle sharing status of a template (only owner can change).
    
    Args:
        template_id: Template ID
        share_data: New sharing status
    
    Returns:
        Updated template
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Toggle sharing
        db_manager = LambDatabaseManager()
        success = db_manager.toggle_template_sharing(
            template_id=template_id,
            owner_email=creator_user['email'],
            is_shared=share_data.is_shared
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Template not found or not authorized")
        
        # Get updated template
        template = db_manager.get_prompt_template_by_id(
            template_id=template_id,
            requester_email=creator_user['email']
        )
        
        return PromptTemplateResponse(**template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling sharing for template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error toggling sharing: {str(e)}")

@router.post("/export", response_model=PromptTemplateExportResponse)
async def export_templates(
    export_request: PromptTemplateExportRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Export prompt templates as JSON.
    
    Args:
        export_request: List of template IDs to export
    
    Returns:
        JSON export data
    """
    try:
        # Get authenticated user
        auth_header = f"Bearer {credentials.credentials}"
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get user's organization for access control
        organization = get_user_organization(creator_user)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get templates
        db_manager = LambDatabaseManager()
        exported_templates = []
        
        for template_id in export_request.template_ids:
            template = db_manager.get_prompt_template_by_id(
                template_id=template_id,
                requester_email=creator_user['email']
            )
            
            if template:
                # Check access
                if template['owner_email'] == creator_user['email'] or \
                   (template['is_shared'] and template['organization_id'] == organization['id']):
                    # Export only relevant fields
                    exported_templates.append({
                        "name": template['name'],
                        "description": template['description'],
                        "system_prompt": template['system_prompt'],
                        "prompt_template": template['prompt_template'],
                        "metadata": template['metadata']
                    })
        
        if not exported_templates:
            raise HTTPException(status_code=404, detail="No templates found to export")
        
        return PromptTemplateExportResponse(
            export_version="1.0",
            exported_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            templates=exported_templates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting templates: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting templates: {str(e)}")

