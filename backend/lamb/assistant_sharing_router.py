from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List
import logging

from .database_manager import LambDatabaseManager
from .owi_bridge.owi_group import OwiGroupManager
from .owi_bridge.owi_users import OwiUserManager

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class UpdateSharesRequest(BaseModel):
    """Request to update the complete share list"""
    user_ids: List[int]

class ShareResponse(BaseModel):
    """Response format for a single share"""
    user_id: int
    user_name: str
    user_email: str
    shared_at: int
    shared_by_name: str

class UserResponse(BaseModel):
    """Response format for a user in organization"""
    id: int
    name: str
    email: str
    user_type: str

# --- Dependencies ---
def get_current_user_id(request: Request):
    """Extract user ID from authorization header"""
    authorization = request.headers.get('Authorization')
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split("Bearer ")[1]
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_auth(token)
    
    if not owi_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db_manager = LambDatabaseManager()
    creator_user = db_manager.get_creator_user_by_email(owi_user['email'])
    
    if not creator_user:
        raise HTTPException(status_code=404, detail="User not found in LAMB database")
    
    return creator_user['id']

# --- Helper Functions ---
def check_sharing_permission(user_id: int) -> bool:
    """
    Check if user can share assistants.
    Requires BOTH:
    1. Organization has sharing_enabled = true (org-level)
    2. User has can_share = true in their config (user-level)
    
    Defaults to True if not explicitly set.
    """
    import json as json_lib
    
    db_manager = LambDatabaseManager()
    user = db_manager.get_creator_user_by_id(user_id)
    
    if not user:
        return False
    
    # Check user-level permission (stored in user_config JSON)
    user_config = user.get('user_config', {})
    if isinstance(user_config, str):
        try:
            user_config = json_lib.loads(user_config) if user_config else {}
        except:
            user_config = {}
    
    user_can_share = user_config.get('can_share', True)  # Default to True
    
    if not user_can_share:
        return False  # User explicitly blocked from sharing
    
    # Check organization-level permission
    orgs = db_manager.get_user_organizations(user_id)
    if not orgs or len(orgs) == 0:
        return True  # Default to enabled if no org
    
    # Use the first organization (users typically belong to one org)
    org = orgs[0]
    
    # Get organization config
    org_data = db_manager.get_organization_by_id(org['id'])
    if not org_data:
        return True  # Default to enabled
    
    config = org_data.get('config', {})
    features = config.get('features', {})
    org_sharing_enabled = features.get('sharing_enabled', True)
    
    # Both must be true
    return org_sharing_enabled

def sync_assistant_to_owi_group(assistant_id: int, db_manager: LambDatabaseManager):
    """Sync users from LAMB_assistant_shares to the assistant_X group in OWI"""
    assistant = db_manager.get_assistant_by_id(assistant_id)
    if not assistant:
        return
    
    group_manager = OwiGroupManager()
    
    # Get all users who should have access (owner + shared users from LAMB_assistant_shares)
    shares = db_manager.get_assistant_shares(assistant_id)
    user_emails = [assistant.owner]  # Owner always has access
    
    for share in shares:
        user = db_manager.get_creator_user_by_id(share['shared_with_user_id'])
        if user:
            user_emails.append(user['user_email'])
    
    # Use the ORIGINAL assistant group (assistant_X, not assistant_X_shared)
    group_name = f"assistant_{assistant_id}"
    
    # Check if group exists
    existing_groups = group_manager.get_all_groups()
    group_id = None
    
    for group in existing_groups:
        if group.get('name') == group_name:
            group_id = group['id']
            break
    
    if not group_id:
        # Create new group if it doesn't exist
        owner_manager = OwiUserManager()
        owner_user = owner_manager.get_user_by_email(assistant.owner)
        if owner_user:
            result = group_manager.create_group(
                name=group_name,
                description=f"Shared access for assistant {assistant.name}",
                user_id=owner_user['id']
            )
            # create_group returns the group dict directly (not wrapped in status)
            group_id = result.get('id') if result else None
    
    if group_id:
        # Add all users to the assistant_X group
        add_users_to_owi_group(group_id, user_emails)

def add_users_to_owi_group(group_id: str, user_emails: List[str]):
    """Add users to OWI group by email"""
    group_manager = OwiGroupManager()
    
    for email in user_emails:
        try:
            result = group_manager.add_user_to_group_by_email(group_id, email)
            if result.get('status') != 'success':
                logger.warning(f"Failed to add user {email} to group {group_id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error adding user {email} to group {group_id}: {e}")

def remove_users_from_owi_group(group_id: str, user_emails: List[str]):
    """Remove users from OWI group by email"""
    group_manager = OwiGroupManager()
    
    for email in user_emails:
        try:
            result = group_manager.remove_user_from_group_by_email(group_id, email)
            if result.get('status') != 'success':
                logger.warning(f"Failed to remove user {email} from group {group_id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error removing user {email} from group {group_id}: {e}")

# --- Endpoints ---

@router.get("/v1/assistant-sharing/check-permission")
async def check_sharing_permission_endpoint(current_user_id: int = Depends(get_current_user_id)):
    """Check if sharing is enabled for current user's organization"""
    can_share = check_sharing_permission(current_user_id)
    return {"can_share": can_share}

@router.get("/v1/assistant-sharing/organization-users")
async def get_organization_users_endpoint(current_user_id: int = Depends(get_current_user_id)):
    """
    Get list of users in current user's organization for sharing UI.
    Requires sharing permission to access.
    """
    # Check if user has sharing permission
    if not check_sharing_permission(current_user_id):
        raise HTTPException(
            status_code=403, 
            detail="Sharing is not enabled for your organization"
        )
    
    db_manager = LambDatabaseManager()
    
    # Get current user's organization
    current_user = db_manager.get_creator_user_by_id(current_user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    org_id = current_user.get('organization_id')
    if not org_id:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    # Get users in same organization (excluding current user)
    users = db_manager.get_organization_users(org_id)
    
    # Filter out current user, format response, and sort alphabetically
    result = []
    for user in users:
        if user['id'] != current_user_id:
            result.append(UserResponse(
                id=user['id'],
                name=user['name'],
                email=user['email'],
                user_type=user.get('user_type', 'creator')
            ))
    
    # Sort alphabetically by name
    result.sort(key=lambda u: u.name.lower())
    
    return result

@router.get("/v1/assistant-sharing/shares/{assistant_id}")
async def get_assistant_shares_endpoint(assistant_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get list of users an assistant is shared with (sorted alphabetically)"""
    db_manager = LambDatabaseManager()
    
    # Check if assistant exists
    assistant = db_manager.get_assistant_by_id(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    # Get shares
    shares = db_manager.get_assistant_shares(assistant_id)
    
    # Format response
    result = []
    for share in shares:
        user = db_manager.get_creator_user_by_id(share['shared_with_user_id'])
        shared_by_user = db_manager.get_creator_user_by_id(share['shared_by_user_id'])
        
        if user and shared_by_user:
            result.append(ShareResponse(
                user_id=user['id'],
                user_name=user['user_name'],
                user_email=user['user_email'],
                shared_at=share['shared_at'],
                shared_by_name=shared_by_user['user_name']
            ))
    
    # Sort alphabetically by name
    result.sort(key=lambda s: s.user_name.lower())
    
    return result

@router.put("/v1/assistant-sharing/shares/{assistant_id}")
async def update_assistant_shares(
    assistant_id: int,
    request: UpdateSharesRequest,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Update the complete share list for an assistant.
    Backend calculates additions and removals, then syncs to OWI group.
    Accepts the desired final state of shared user IDs.
    """
    db_manager = LambDatabaseManager()
    
    # Check if assistant exists
    assistant = db_manager.get_assistant_by_id(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    # Check permissions (owner or admin)
    current_user = db_manager.get_creator_user_by_id(current_user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="Current user not found")
    
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_by_email(current_user['user_email'])
    
    is_owner = assistant.owner == current_user['user_email']
    is_admin = owi_user and owi_user.get('role') == 'admin'
    
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Only owner or admin can manage assistant sharing"
        )
    
    # Check if sharing is enabled for organization (only when adding shares)
    if len(request.user_ids) > 0 and not check_sharing_permission(current_user_id):
        raise HTTPException(
            status_code=403, 
            detail="Sharing is not enabled for your organization"
        )
    
    # Get current shares
    current_shares = db_manager.get_assistant_shares(assistant_id)
    current_user_ids = {share['shared_with_user_id'] for share in current_shares}
    
    # Calculate diff
    desired_user_ids = set(request.user_ids)
    to_add = desired_user_ids - current_user_ids
    to_remove = current_user_ids - desired_user_ids
    
    # Apply changes
    added = 0
    removed = 0
    
    for user_id in to_add:
        try:
            db_manager.share_assistant(assistant_id, user_id, current_user_id)
            added += 1
        except Exception as e:
            logger.error(f"Error sharing assistant {assistant_id} with user {user_id}: {e}")
    
    for user_id in to_remove:
        try:
            db_manager.unshare_assistant(assistant_id, user_id)
            removed += 1
        except Exception as e:
            logger.error(f"Error unsharing assistant {assistant_id} from user {user_id}: {e}")
    
    # Sync to OWI group once (single atomic operation)
    sync_assistant_to_owi_group(assistant_id, db_manager)
    
    logger.info(f"Updated shares for assistant {assistant_id}: +{added}, -{removed}")
    
    # Return updated shares list
    return await get_assistant_shares_endpoint(assistant_id, current_user_id)

@router.get("/v1/assistant-sharing/shared-with-me")
async def get_shared_assistants(current_user_id: int = Depends(get_current_user_id)):
    """Get list of assistants shared with current user"""
    db_manager = LambDatabaseManager()
    assistants = db_manager.get_assistants_shared_with_user(current_user_id)
    
    return {"assistants": assistants, "count": len(assistants)}

@router.put("/v1/assistant-sharing/user-permission/{user_id}")
async def update_user_sharing_permission(
    user_id: int,
    can_share: bool = Query(..., description="Whether user can share assistants"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Admin endpoint: Toggle a user's ability to share assistants.
    Requires admin role.
    """
    import json as json_lib
    
    db_manager = LambDatabaseManager()
    
    # Check if current user is admin
    current_user = db_manager.get_creator_user_by_id(current_user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="Current user not found")
    
    user_manager = OwiUserManager()
    owi_user = user_manager.get_user_by_email(current_user['user_email'])
    
    if not owi_user or owi_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get target user
    target_user = db_manager.get_creator_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user config
    user_config = target_user.get('user_config', {})
    if isinstance(user_config, str):
        try:
            user_config = json_lib.loads(user_config) if user_config else {}
        except:
            user_config = {}
    
    user_config['can_share'] = can_share
    
    # Save updated config
    success = db_manager.update_user_config(user_id, user_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user permission")
    
    return {
        "success": True,
        "user_id": user_id,
        "can_share": can_share
    }
