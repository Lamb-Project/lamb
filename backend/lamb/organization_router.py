"""
Organization management router for LAMB multi-organization support

IMPORTANT: Admin Authentication in LAMB
Due to the evolution of the system, we have a dual admin requirement:
1. System admin must have 'admin' role in OpenWebUI (OWI)
2. System admin must have 'admin' role in the 'lamb' organization

This ensures backward compatibility while providing proper organization-based access control.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from .database_manager import LambDatabaseManager
import logging
import json
from datetime import datetime
from lamb.logging_config import get_logger

# Initialize router
router = APIRouter()
logger = get_logger(__name__, component="API")

# Initialize database manager
db_manager = LambDatabaseManager()

# Pydantic models for API requests/responses
class OrganizationCreate(BaseModel):
    slug: str = Field(..., description="URL-friendly unique identifier")
    name: str = Field(..., description="Organization display name")
    config: Optional[Dict[str, Any]] = Field(None, description="Organization configuration")

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Organization display name")
    status: Optional[str] = Field(None, description="Organization status")
    config: Optional[Dict[str, Any]] = Field(None, description="Organization configuration")

class OrganizationConfigUpdate(BaseModel):
    config: Dict[str, Any] = Field(..., description="Organization configuration")

class OrganizationRoleAssignment(BaseModel):
    user_id: int = Field(..., description="User ID")
    role: str = Field(..., description="Role to assign", pattern="^(owner|admin|member)$")

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

# Dependencies for authentication/authorization
from fastapi import Header
from typing import Optional

async def get_current_user_email(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user email from authorization header"""
    # TODO: Implement proper JWT token parsing
    # For now, return the admin email for testing
    import config
    return config.OWI_ADMIN_EMAIL

async def verify_system_admin(user_email: str = Depends(get_current_user_email)):
    """Verify that the user is a system admin"""
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not db_manager.is_system_admin(user_email):
        raise HTTPException(status_code=403, detail="System admin access required")
    
    return user_email

async def verify_org_admin(slug: str, user_email: str = Depends(get_current_user_email)):
    """Verify that the user is an admin of the organization"""
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # System admins can manage all organizations
    if db_manager.is_system_admin(user_email):
        return user_email
    
    # Check organization-specific admin rights
    org = db_manager.get_organization_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
    
    if not db_manager.is_organization_admin(user_email, org['id']):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    
    return user_email

# API Endpoints

@router.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    admin_email: str = Depends(verify_system_admin)
):
    """Create a new organization (system admin only)"""
    try:
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
        return OrganizationResponse(**org)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    status: Optional[str] = Query(None, description="Filter by status"),
    admin_email: str = Depends(verify_system_admin)
):
    """List all organizations (system admin only)"""
    try:
        organizations = db_manager.list_organizations(status=status)
        return [OrganizationResponse(**org) for org in organizations]
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{slug}", response_model=OrganizationResponse)
async def get_organization(slug: str):
    """Get organization by slug"""
    try:
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        return OrganizationResponse(**org)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/organizations/{slug}", response_model=OrganizationResponse)
async def update_organization(
    slug: str,
    update_data: OrganizationUpdate,
    current_user: str = Depends(get_current_user_email)
):
    """Update organization (system admin or org admin)"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # Check permissions
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # System admins can update any org, org admins can update their own org
        if not db_manager.is_system_admin(current_user):
            if not db_manager.is_organization_admin(current_user, org['id']):
                raise HTTPException(status_code=403, detail="Organization admin access required")
        
        # Check if it's a system organization
        if org['is_system'] and update_data.status:
            raise HTTPException(status_code=400, detail="Cannot change status of system organization")
        
        # Update organization
        success = db_manager.update_organization(
            org_id=org['id'],
            name=update_data.name,
            status=update_data.status,
            config=update_data.config
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update organization")
        
        # Get updated organization
        updated_org = db_manager.get_organization_by_id(org['id'])
        return OrganizationResponse(**updated_org)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/organizations/{slug}")
async def delete_organization(
    slug: str,
    admin_email: str = Depends(verify_system_admin)
):
    """Delete organization (system admin only, cannot delete system org)"""
    try:
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
        logger.error(f"Error deleting organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration Management Endpoints

@router.get("/organizations/{slug}/config")
async def get_organization_config(slug: str):
    """Get organization configuration"""
    try:
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        return org['config']
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/organizations/{slug}/config")
async def update_organization_config(
    slug: str,
    config_update: OrganizationConfigUpdate,
    current_user: str = Depends(get_current_user_email)
):
    """Update organization configuration"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # Check permissions
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        if not db_manager.is_system_admin(current_user):
            if not db_manager.is_organization_admin(current_user, org['id']):
                raise HTTPException(status_code=403, detail="Organization admin access required")
        
        # Update config
        success = db_manager.update_organization_config(org['id'], config_update.config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
        
        return {"message": "Configuration updated successfully", "config": config_update.config}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/organizations/{slug}/config")
async def patch_organization_config(
    slug: str,
    patches: List[Dict[str, Any]] = Body(..., description="JSON Patch operations")
):
    """Apply JSON Patch to organization configuration"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check for org admin
        # TODO: Implement JSON Patch application
        
        raise HTTPException(status_code=501, detail="JSON Patch not yet implemented")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error patching organization config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Import/Export Endpoints

@router.get("/organizations/{slug}/export")
async def export_organization(slug: str):
    """Export organization configuration"""
    try:
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check
        
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
        logger.error(f"Error exporting organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/organizations/{slug}/import")
async def import_organization(
    slug: str,
    import_data: Dict[str, Any] = Body(..., description="Organization import data")
):
    """Import organization configuration"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check for org admin
        
        # Validate import data
        if import_data.get("export_version") != "1.0":
            raise HTTPException(status_code=400, detail="Unsupported export version")
        
        if "organization" not in import_data or "config" not in import_data["organization"]:
            raise HTTPException(status_code=400, detail="Invalid import data structure")
        
        # Update config
        new_config = import_data["organization"]["config"]
        success = db_manager.update_organization_config(org['id'], new_config)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to import configuration")
        
        return {"message": "Configuration imported successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# User & Role Management Endpoints

@router.get("/organizations/{slug}/users", response_model=List[UserWithRole])
async def get_organization_users(slug: str):
    """Get all users in an organization with their roles"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check
        
        users = db_manager.get_organization_users(org['id'])
        return [UserWithRole(**user) for user in users]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/organizations/{slug}/users/assign-role")
async def assign_user_role(
    slug: str,
    assignment: OrganizationRoleAssignment
):
    """Assign a role to a user in the organization"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check for org admin
        
        # Assign role
        success = db_manager.assign_organization_role(
            organization_id=org['id'],
            user_id=assignment.user_id,
            role=assignment.role
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to assign role")
        
        # Update user's organization if needed
        db_manager.update_user_organization(assignment.user_id, org['id'])
        
        return {"message": f"Role '{assignment.role}' assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning user role: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Usage Tracking Endpoints

@router.get("/organizations/{slug}/usage")
async def get_organization_usage(slug: str):
    """Get current usage statistics for an organization"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check
        
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
        logger.error(f"Error getting organization usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{slug}/usage/logs")
async def get_organization_usage_logs(
    slug: str,
    limit: int = Query(100, description="Number of logs to return"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get usage logs for an organization"""
    try:
        # Get organization
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
        
        # TODO: Add permission check
        # TODO: Implement usage log retrieval
        
        return {
            "logs": [],  # TODO: Get actual logs
            "total": 0,
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System organization sync endpoint
@router.post("/organizations/system/sync")
async def sync_system_organization(
    admin_email: str = Depends(verify_system_admin)
):
    """Sync system organization with environment variables (system admin only)"""
    try:
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
            "organization": OrganizationResponse(**updated_org)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing system organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organizations/{slug}/assistant-defaults")
async def get_organization_assistant_defaults(slug: str):
    """Get assistant defaults for an organization"""
    try:
        db_manager = LambDatabaseManager()
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get assistant_defaults from org config
        config = org.get('config', {})
        assistant_defaults = config.get('assistant_defaults', {})
        
        return assistant_defaults
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assistant defaults for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/organizations/{slug}/assistant-defaults")
async def update_organization_assistant_defaults(slug: str, request: Request):
    """Update assistant defaults for an organization"""
    try:
        db_manager = LambDatabaseManager()
        org = db_manager.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get current config
        config = org.get('config', {})
        
        # Get request body
        body = await request.json()
        
        # Update assistant_defaults - body should contain the assistant_defaults object directly
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Request body must be an object")
        
        # Extract assistant_defaults from the body (frontend sends the full parsed JSON)
        new_defaults = body.get('assistant_defaults', body)
        if not isinstance(new_defaults, dict):
            raise HTTPException(status_code=400, detail="assistant_defaults must be an object")
        
        config['assistant_defaults'] = new_defaults
        
        # Save updated config
        db_manager.update_organization_config(org['id'], config)
        
        return {"message": "Assistant defaults updated successfully", "assistant_defaults": new_defaults}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assistant defaults for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))