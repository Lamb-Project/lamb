"""
Assistant Sharing Service

Encapsulates all business logic for assistant sharing functionality.
This service handles sharing/unsharing assistants and OWI group synchronization.
"""

import logging
from typing import List, Dict, Any, Optional
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_group import OwiGroupManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="SERVICE")


class AssistantSharingService:
    """Service layer for assistant sharing operations"""

    def __init__(self):
        self.db_manager = LambDatabaseManager()
        self.group_manager = OwiGroupManager()
        self.user_manager = OwiUserManager()

    def check_sharing_permission(self, user_id: int) -> bool:
        """
        Check if user can share assistants.
        Requires BOTH:
        1. Organization has sharing_enabled = true (org-level)
        2. User has can_share = true in their config (user-level)

        Defaults to True if not explicitly set.
        """
        import json as json_lib

        user = self.db_manager.get_creator_user_by_id(user_id)

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
        orgs = self.db_manager.get_user_organizations(user_id)
        if not orgs or len(orgs) == 0:
            return True  # Default to enabled if no org

        # Use the first organization (users typically belong to one org)
        org = orgs[0]

        # Get organization config
        org_data = self.db_manager.get_organization_by_id(org['id'])
        if not org_data:
            return True  # Default to enabled

        config = org_data.get('config', {})
        features = config.get('features', {})
        org_sharing_enabled = features.get('sharing_enabled', True)

        # Both must be true
        return org_sharing_enabled

    def get_organization_users(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get list of users in current user's organization for sharing UI.
        Excludes current user, sorted alphabetically by name.
        """
        # Get current user's organization
        current_user = self.db_manager.get_creator_user_by_id(user_id)
        if not current_user:
            raise ValueError("User not found")

        org_id = current_user.get('organization_id')
        if not org_id:
            raise ValueError("User has no organization")

        # Get users in same organization (excluding current user)
        users = self.db_manager.get_organization_users(org_id)

        # Filter out current user and format response
        result = []
        for user in users:
            if user['id'] != user_id:
                result.append({
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email'],
                    'user_type': user.get('user_type', 'creator')
                })

        # Sort alphabetically by name
        result.sort(key=lambda u: u['name'].lower())

        return result

    def get_assistant_shares(self, assistant_id: int) -> List[Dict[str, Any]]:
        """
        Get list of users an assistant is shared with (sorted alphabetically)
        """
        # Check if assistant exists
        assistant = self.db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise ValueError("Assistant not found")

        # Get shares
        shares = self.db_manager.get_assistant_shares(assistant_id)

        # Format response
        result = []
        for share in shares:
            user = self.db_manager.get_creator_user_by_id(share['shared_with_user_id'])
            shared_by_user = self.db_manager.get_creator_user_by_id(share['shared_by_user_id'])

            if user and shared_by_user:
                result.append({
                    'user_id': user['id'],
                    'user_name': user['user_name'],
                    'user_email': user['user_email'],
                    'shared_at': share['shared_at'],
                    'shared_by_name': shared_by_user['user_name']
                })

        # Sort alphabetically by name
        result.sort(key=lambda s: s['user_name'].lower())

        return result

    def update_assistant_shares(self, assistant_id: int, user_ids: List[int], current_user_id: int) -> List[Dict[str, Any]]:
        """
        Update the complete share list for an assistant.
        Backend calculates additions and removals, then syncs to OWI group.
        Accepts the desired final state of shared user IDs.
        """
        # Check if assistant exists
        assistant = self.db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise ValueError("Assistant not found")

        # Check permissions (owner or admin)
        current_user = self.db_manager.get_creator_user_by_id(current_user_id)
        if not current_user:
            raise ValueError("Current user not found")

        owi_user = self.user_manager.get_user_by_email(current_user['user_email'])

        is_owner = assistant.owner == current_user['user_email']
        is_admin = owi_user and owi_user.get('role') == 'admin'

        if not is_owner and not is_admin:
            raise PermissionError("Only owner or admin can manage assistant sharing")

        # Check if sharing is enabled for organization (only when adding shares)
        if len(user_ids) > 0 and not self.check_sharing_permission(current_user_id):
            raise PermissionError("Sharing is not enabled for your organization")

        # Get current shares
        current_shares = self.db_manager.get_assistant_shares(assistant_id)
        current_user_ids = {share['shared_with_user_id'] for share in current_shares}

        # Calculate diff
        desired_user_ids = set(user_ids)
        to_add = desired_user_ids - current_user_ids
        to_remove = current_user_ids - desired_user_ids

        # Apply changes
        added = 0
        removed = 0

        for user_id in to_add:
            try:
                self.db_manager.share_assistant(assistant_id, user_id, current_user_id)
                added += 1
            except Exception as e:
                logger.error(f"Error sharing assistant {assistant_id} with user {user_id}: {e}")

        for user_id in to_remove:
            try:
                self.db_manager.unshare_assistant(assistant_id, user_id)
                removed += 1
            except Exception as e:
                logger.error(f"Error unsharing assistant {assistant_id} from user {user_id}: {e}")

        # Sync to OWI group once (single atomic operation)
        self._sync_assistant_to_owi_group(assistant_id)

        logger.info(f"Updated shares for assistant {assistant_id}: +{added}, -{removed}")

        # Return updated shares list
        return self.get_assistant_shares(assistant_id)

    def update_assistant_shares_by_email(
        self, 
        assistant_id: int, 
        user_emails: List[str], 
        current_user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Update the complete share list for an assistant using user emails.
        Backend calculates additions and removals, then syncs to OWI group.
        Accepts the desired final state of shared user emails.
        """
        # Check if assistant exists
        assistant = self.db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise ValueError("Assistant not found")

        # Resolve emails to user IDs
        user_ids = []
        not_found_emails = []
        for email in user_emails:
            user = self.db_manager.get_creator_user_by_email(email)
            if user:
                user_ids.append(user['id'])
            else:
                not_found_emails.append(email)
        
        if not_found_emails:
            logger.warning(f"Users not found for emails: {not_found_emails}")

        # Get current shares
        current_shares = self.db_manager.get_assistant_shares(assistant_id)
        current_user_ids = {share['shared_with_user_id'] for share in current_shares}

        # Calculate diff
        desired_user_ids = set(user_ids)
        to_add = desired_user_ids - current_user_ids
        to_remove = current_user_ids - desired_user_ids

        # Apply changes
        added = 0
        removed = 0

        for uid in to_add:
            try:
                self.db_manager.share_assistant(assistant_id, uid, current_user_id)
                added += 1
            except Exception as e:
                logger.error(f"Error sharing assistant {assistant_id} with user {uid}: {e}")

        for uid in to_remove:
            try:
                self.db_manager.unshare_assistant(assistant_id, uid)
                removed += 1
            except Exception as e:
                logger.error(f"Error unsharing assistant {assistant_id} from user {uid}: {e}")

        # Sync to OWI group once (single atomic operation)
        self._sync_assistant_to_owi_group(assistant_id)

        logger.info(f"Updated shares for assistant {assistant_id}: +{added}, -{removed}")

        # Return updated shares list
        return self.get_assistant_shares(assistant_id)

    def get_shared_assistants(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get list of assistants shared with current user
        """
        assistants = self.db_manager.get_assistants_shared_with_user(user_id)
        return assistants

    def update_user_sharing_permission(self, user_id: int, can_share: bool, admin_user_id: int) -> bool:
        """
        Admin endpoint: Toggle a user's ability to share assistants.
        Requires admin role.
        """
        import json as json_lib

        # Check if current user is admin
        admin_user = self.db_manager.get_creator_user_by_id(admin_user_id)
        if not admin_user:
            raise ValueError("Admin user not found")

        owi_user = self.user_manager.get_user_by_email(admin_user['user_email'])

        if not owi_user or owi_user.get('role') != 'admin':
            raise PermissionError("Admin access required")

        # Get target user
        target_user = self.db_manager.get_creator_user_by_id(user_id)
        if not target_user:
            raise ValueError("User not found")

        # Update user config
        user_config = target_user.get('user_config', {})
        if isinstance(user_config, str):
            try:
                user_config = json_lib.loads(user_config) if user_config else {}
            except:
                user_config = {}

        user_config['can_share'] = can_share

        # Save updated config
        success = self.db_manager.update_user_config(user_id, user_config)

        if not success:
            raise ValueError("Failed to update user permission")

        return True

    def _sync_assistant_to_owi_group(self, assistant_id: int):
        """Sync users from LAMB_assistant_shares to the assistant_X group in OWI"""
        assistant = self.db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            return

        # Get all users who should have access (owner + shared users from LAMB_assistant_shares)
        shares = self.db_manager.get_assistant_shares(assistant_id)
        user_emails = [assistant.owner]  # Owner always has access

        for share in shares:
            user = self.db_manager.get_creator_user_by_id(share['shared_with_user_id'])
            if user:
                user_emails.append(user['user_email'])

        # Use the ORIGINAL assistant group (assistant_X, not assistant_X_shared)
        group_name = f"assistant_{assistant_id}"

        # Create the group
        owner_user = self.user_manager.get_user_by_email(assistant.owner)

        result = self.group_manager.create_group(
            name=group_name,
            description=f"Shared access for assistant {assistant.name}",
            user_id=owner_user['id']
        )
        group_id = result.get('id')

        # Add all users to the assistant_X group
        self._add_users_to_owi_group(group_id, user_emails)

    def _add_users_to_owi_group(self, group_id: str, user_emails: List[str]):
        """Add users to OWI group by email"""
        for email in user_emails:
            try:
                result = self.group_manager.add_user_to_group_by_email(group_id, email)
                if result.get('status') != 'success':
                    logger.warning(f"Failed to add user {email} to group {group_id}: {result.get('error')}")
            except Exception as e:
                logger.error(f"Error adding user {email} to group {group_id}: {e}")

    def _remove_users_from_owi_group(self, group_id: str, user_emails: List[str]):
        """Remove users from OWI group by email"""
        for email in user_emails:
            try:
                result = self.group_manager.remove_user_from_group_by_email(group_id, email)
                if result.get('status') != 'success':
                    logger.warning(f"Failed to remove user {email} from group {group_id}: {result.get('error')}")
            except Exception as e:
                logger.error(f"Error removing user {email} from group {group_id}: {e}")

