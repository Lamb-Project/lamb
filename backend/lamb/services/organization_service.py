"""
Organization Service Layer
Encapsulates all organization-related business logic.

This service layer is used by:
- /creator/admin/* endpoints (via creator_interface/organization_router.py)
- Organization management operations
- Multi-tenant configuration

This consolidates logic for organization operations.
"""

from typing import Optional, Dict, Any, List
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="SERVICE")


class OrganizationService:
    """Service for organization operations"""
    
    def __init__(self):
        self.db_manager = LambDatabaseManager()
    
    def get_organization_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get organization by slug
        
        Args:
            slug: Organization slug (URL-friendly identifier)
            
        Returns:
            Optional[Dict]: Organization data with config, or None
        """
        return self.db_manager.get_organization_by_slug(slug)
    
    def get_organization_by_id(self, org_id: int) -> Optional[Dict[str, Any]]:
        """
        Get organization by ID
        
        Args:
            org_id: Organization ID
            
        Returns:
            Optional[Dict]: Organization data, or None
        """
        return self.db_manager.get_organization_by_id(org_id)
    
    def list_organizations(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all organizations
        
        Args:
            status: Optional status filter
            
        Returns:
            List of organization dicts
        """
        return self.db_manager.list_organizations(status=status)
    
    def create_organization(
        self, 
        slug: str, 
        name: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Create a new organization
        
        Args:
            slug: URL-friendly identifier
            name: Display name
            config: Organization configuration
            
        Returns:
            Organization ID if successful, None otherwise
        """
        return self.db_manager.create_organization(slug, name, config)
    
    def update_organization(
        self,
        org_id: int,
        name: Optional[str] = None,
        status: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update organization
        
        Args:
            org_id: Organization ID
            name: New name (optional)
            status: New status (optional)
            config: New config (optional)
            
        Returns:
            bool: True if successful
        """
        return self.db_manager.update_organization(org_id, name, status, config)
    
    def update_organization_config(self, org_id: int, config: Dict[str, Any]) -> bool:
        """
        Update organization configuration
        
        Args:
            org_id: Organization ID
            config: New configuration dict
            
        Returns:
            bool: True if successful
        """
        return self.db_manager.update_organization_config(org_id, config)
    
    def delete_organization(self, org_id: int) -> bool:
        """
        Delete organization (cannot delete system org)
        
        Args:
            org_id: Organization to delete
            
        Returns:
            bool: True if successful
        """
        return self.db_manager.delete_organization(org_id)
    
    def get_organization_users(self, org_id: int) -> List[Dict[str, Any]]:
        """
        Get all users in an organization with their roles
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of user dicts with role information
        """
        return self.db_manager.get_organization_users(org_id)
    
    def assign_organization_role(
        self, 
        organization_id: int, 
        user_id: int, 
        role: str
    ) -> bool:
        """
        Assign a role to a user in the organization
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            role: Role to assign (owner/admin/member)
            
        Returns:
            bool: True if successful
        """
        return self.db_manager.assign_organization_role(organization_id, user_id, role)
    
    def is_system_admin(self, user_email: str) -> bool:
        """
        Check if user is a system admin
        
        Args:
            user_email: User email
            
        Returns:
            bool: True if user is system admin
        """
        return self.db_manager.is_system_admin(user_email)
    
    def is_organization_admin(self, user_email: str, org_id: int) -> bool:
        """
        Check if user is an admin of the organization
        
        Args:
            user_email: User email
            org_id: Organization ID
            
        Returns:
            bool: True if user is org admin
        """
        return self.db_manager.is_organization_admin(user_email, org_id)
    
    def get_assistant_defaults(self, slug: str) -> Dict[str, Any]:
        """
        Get assistant defaults for an organization
        
        Args:
            slug: Organization slug
            
        Returns:
            Dict with assistant_defaults config
            
        Raises:
            HTTPException: If organization not found
            
        Used By:
            - /creator/admin/organizations/{slug}/assistant-defaults
        """
        from fastapi import HTTPException
        
        org = self.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        config = org.get('config', {})
        assistant_defaults = config.get('assistant_defaults', {})
        
        return assistant_defaults
    
    def update_assistant_defaults(
        self, 
        slug: str, 
        assistant_defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update assistant defaults for an organization
        
        Args:
            slug: Organization slug
            assistant_defaults: New assistant defaults config
            
        Returns:
            Dict with success message and updated defaults
            
        Raises:
            HTTPException: If organization not found or update fails
            
        Used By:
            - PUT /creator/admin/organizations/{slug}/assistant-defaults
        """
        from fastapi import HTTPException
        
        org = self.get_organization_by_slug(slug)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get current config
        config = org.get('config', {})
        
        # Validate assistant_defaults is a dict
        if not isinstance(assistant_defaults, dict):
            raise HTTPException(
                status_code=400, 
                detail="assistant_defaults must be an object"
            )
        
        # Update assistant_defaults
        config['assistant_defaults'] = assistant_defaults
        
        # Save updated config
        success = self.update_organization_config(org['id'], config)
        
        if not success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to update assistant defaults"
            )
        
        return {
            "message": "Assistant defaults updated successfully",
            "assistant_defaults": assistant_defaults
        }

