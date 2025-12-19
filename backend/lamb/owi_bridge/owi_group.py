import uuid
import json
import logging
import time
from typing import Optional, Dict, List, Any
from .owi_database import OwiDatabaseManager
from .owi_users import OwiUserManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="OWI")

OWI_GROUP_PERMISSIONS = {
    "workspace": {
        "models": False,
        "knowledge": False, 
        "prompts": False,
        "tools": False
    },
    "chat": {
        "file_upload": False,
        "delete": True,
        "edit": True,
        "temporary": False
    }
}


class OwiGroupManager:
    def __init__(self):
        self.db = OwiDatabaseManager()

    def create_group(
        self,
        name: str,
        user_id: str,
        description: str = "",
        data: Dict = None,
        meta: Dict = None,
        permissions: Dict = OWI_GROUP_PERMISSIONS,
        user_ids: List[str] = None
    ) -> Optional[Dict]:
        """
        Create a new group
        
        Args:
            name (str): Group name
            user_id (str): Creator's user ID
            description (str): Group description
            data (Dict): Additional data for the group
            meta (Dict): Metadata for the group
            permissions (Dict): Group permissions
            user_ids (List[str]): List of user IDs in the group
            
        Returns:
            Optional[Dict]: Created group data or None if creation fails
        """
        try:
            # Check if group with this name already exists (prevent duplicates)
            existing_group = self.get_group_by_name(name)
            if existing_group:
                logger.warning(f"Group with name '{name}' already exists. Returning existing group.")
                return existing_group
            
            group_id = str(uuid.uuid4())
            current_time = int(time.time())

            # Prepare JSON fields
            data = json.dumps(data) if data else "{}"
            meta = json.dumps(meta) if meta else "{}"
            permissions = json.dumps(permissions) if permissions else "{}"
            user_ids = json.dumps(user_ids) if user_ids else "[]"

            query = """
                INSERT INTO "group" (
                    id, user_id, name, description, data, meta, 
                    permissions, user_ids, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                group_id, user_id, name, description, data, meta,
                permissions, user_ids, current_time, current_time
            )

            conn = self.db.get_connection()
            if not conn:
                return None

            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return self.get_group_by_id(group_id)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error creating group: {e}")
                return None
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in create_group: {e}")
            return None

    def get_group_by_id(self, group_id: str) -> Optional[Dict]:
        """Get group by ID"""
        try:
            query = 'SELECT * FROM "group" WHERE id = ?'
            result = self.db.execute_query(query, (group_id,), fetch_one=True)
            
            if result:
                return self._row_to_dict(result)
            return None

        except Exception as e:
            logger.error(f"Error in get_group_by_id: {e}")
            return None

    def get_group_by_name(self, group_name: str) -> Optional[Dict]:
        """Get group by name"""
        try:
            query = 'SELECT * FROM "group" WHERE name = ?'
            result = self.db.execute_query(query, (group_name,), fetch_one=True)
            return self._row_to_dict(result) if result else None
        except Exception as e:
            logger.error(f"Error in get_group_by_name: {e}")
            return None

    def get_user_groups(self, user_id: str) -> List[Dict]:
        """Get all groups where user is a member"""
        try:
            # First get groups where user is owner
            query = 'SELECT * FROM "group" WHERE user_id = ?'
            owned_groups = self.db.execute_query(query, (user_id,))

            # Then get groups where user is a member
            query = 'SELECT * FROM "group" WHERE json_array_contains(user_ids, ?)'
            member_groups = self.db.execute_query(query, (user_id,))

            groups = []
            if owned_groups:
                groups.extend([self._row_to_dict(row) for row in owned_groups])
            if member_groups:
                groups.extend([self._row_to_dict(row) for row in member_groups])

            return groups

        except Exception as e:
            logger.error(f"Error in get_user_groups: {e}")
            return []

    def update_group(
        self,
        group_id: str,
        name: str = None,
        description: str = None,
        data: Dict = None,
        meta: Dict = None,
        permissions: Dict = None,
        user_ids: List[str] = None
    ) -> Optional[Dict]:
        """Update group information"""
        try:
            current_time = int(time.time())
            updates = []
            params = []

            # Build dynamic update query
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if data is not None:
                updates.append("data = ?")
                params.append(json.dumps(data))
            if meta is not None:
                updates.append("meta = ?")
                params.append(json.dumps(meta))
            if permissions is not None:
                updates.append("permissions = ?")
                params.append(json.dumps(permissions))
            if user_ids is not None:
                updates.append("user_ids = ?")
                params.append(json.dumps(user_ids))

            updates.append("updated_at = ?")
            params.append(current_time)

            # Add group_id to params
            params.append(group_id)

            query = f'''
                UPDATE "group" 
                SET {", ".join(updates)}
                WHERE id = ?
            '''

            conn = self.db.get_connection()
            if not conn:
                return None

            try:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                conn.commit()
                return self.get_group_by_id(group_id)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating group: {e}")
                return None
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in update_group: {e}")
            return None

    def delete_group(self, group_id: str) -> bool:
        """Delete a group"""
        try:
            query = 'DELETE FROM "group" WHERE id = ?'
            
            conn = self.db.get_connection()
            if not conn:
                return False

            try:
                cursor = conn.cursor()
                cursor.execute(query, (group_id,))
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Error deleting group: {e}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in delete_group: {e}")
            return False

    def add_user_to_group(self, group_id: str, user_id: str) -> Dict:
        """
        Add a user to a group
        
        Args:
            group_id (str): ID of the group
            user_id (str): ID of the user to add
            
        Returns:
            Dict: Response containing success/error status and message
        """
        try:
            group = self.get_group_by_id(group_id)
            if not group:
                return {
                    "status": "error",
                    "error": f"Group with id {group_id} not found"
                }

            try:
                # Handle both string and list cases for user_ids
                if isinstance(group['user_ids'], str):
                    user_ids = json.loads(group['user_ids'])
                else:
                    user_ids = group['user_ids']
            except (json.JSONDecodeError, TypeError):
                user_ids = []

            if user_id in user_ids:
                return {
                    "status": "error",
                    "error": "User is already a member of this group"
                }

            user_ids.append(user_id)
            updated_group = self.update_group(group_id, user_ids=user_ids)
            
            if updated_group:
                return {
                    "status": "success",
                    "data": updated_group
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to update group with new user"
                }

        except Exception as e:
            logger.error(f"Error in add_user_to_group: {e}")
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }

    def remove_user_from_group(self, group_id: str, user_id: str) -> bool:
        """Remove a user from a group"""
        try:
            group = self.get_group_by_id(group_id)
            if not group:
                return False

            # user_ids is already a list from _row_to_dict, not a JSON string
            user_ids = group.get('user_ids', [])
            if not isinstance(user_ids, list):
                # In case it's still a string, parse it
                user_ids = json.loads(user_ids) if isinstance(user_ids, str) else []
            
            logger.info(f"Current user_ids: {user_ids}, removing user: {user_id}")
            
            if user_id in user_ids:
                user_ids.remove(user_id)
                logger.info(f"User {user_id} removed, updated user_ids: {user_ids}")
                return self.update_group(group_id, user_ids=user_ids) is not None

            return True

        except Exception as e:
            logger.error(f"Error in remove_user_from_group: {e}", exc_info=True)
            return False

    def add_user_to_group_by_email(self, group_id: str, user_email: str) -> Dict:
        """
        Add a user to a group using their email
        
        Args:
            group_id (str): ID of the group to add the user to
            user_email (str): Email of the user to add
            
        Returns:
            Dict: Response containing success/error status and data/error message
        """
        try:
            # First validate the group exists
            group = self.get_group_by_id(group_id)
            if not group:
                return {
                    "status": "error",
                    "error": f"Group with id {group_id} not found"
                }

            # Get user by email using OwiUserManager
            user_manager = OwiUserManager()
            user = user_manager.get_user_by_email(user_email)
            
            if not user:
                return {
                    "status": "error", 
                    "error": f"User with email {user_email} not found"
                }

            # Use existing add_user_to_group method
            result = self.add_user_to_group(group_id, user['id'])
            
            # Just pass through the result since it's already in the right format
            return result

        except Exception as e:
            logger.error(f"Error in add_user_to_group_by_email: {e}")
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }

    def remove_user_from_group_by_email(self, group_id: str, user_email: str) -> Dict:
        """
        Remove a user from a group using their email
        
        Args:
            group_id (str): ID of the group to remove the user from
            user_email (str): Email of the user to remove
            
        Returns:
            Dict: Response containing success/error status and message
        """
        try:
            # First validate the group exists
            group = self.get_group_by_id(group_id)
            if not group:
                return {
                    "status": "error",
                    "error": f"Group with id {group_id} not found"
                }

            # Get user by email using OwiUserManager
            user_manager = OwiUserManager()
            user = user_manager.get_user_by_email(user_email)
            
            if not user:
                return {
                    "status": "error", 
                    "error": f"User with email {user_email} not found"
                }

            # Use existing remove_user_from_group method
            success = self.remove_user_from_group(group_id, user['id'])
            
            if success:
                return {
                    "status": "success",
                    "message": f"User {user_email} removed from group"
                }
            else:
                return {
                    "status": "error",
                    "error": f"Failed to remove user from group"
                }

        except Exception as e:
            logger.error(f"Error in remove_user_from_group_by_email: {e}")
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }

    def _row_to_dict(self, row: tuple) -> Dict:
        """Convert a database row to a dictionary"""
        try:
            columns = [
                'id', 'user_id', 'name', 'description', 'data', 'meta',
                'permissions', 'user_ids', 'created_at', 'updated_at'
            ]
            
            group_dict = dict(zip(columns, row))
            
            # Parse JSON fields
            for field in ['data', 'meta', 'permissions', 'user_ids']:
                if group_dict[field]:
                    try:
                        parsed = json.loads(group_dict[field])
                        group_dict[field] = parsed
                    except json.JSONDecodeError:
                        # If it's user_ids, default to empty list; otherwise empty dict
                        group_dict[field] = [] if field == 'user_ids' else {}
                else:
                    # If it's user_ids, default to empty list; otherwise empty dict
                    group_dict[field] = [] if field == 'user_ids' else {}
                    
            return group_dict

        except Exception as e:
            logger.error(f"Error in _row_to_dict: {e}")
            return {}

    def get_group_users(self, group_id: str) -> List[Dict]:
        """Get all users in a group
        
        Args:
            group_id (str): The ID of the group
            
        Returns:
            List[Dict]: List of users with their details
        """
        try:
            # First verify the group exists
            group = self.db.get_group_by_id(group_id)
            if not group:
                return None
               
            # Get all users in the group
            users = self.db.get_users_in_group(group_id)
            
            # Format the response
            return [
                {
                    "id": user["id"],
                    "name": user["display_name"],
                    "email": user["email"]
                }
                for user in users
            ]
            
        except Exception as e:
            logger.error(f"Error getting group users: {e}")
            return None

    def get_all_groups(self) -> List[Dict]:
        """Get all groups
        
        Returns:
            List[Dict]: List of all groups
        """
        try:
            query = "SELECT * FROM \"group\" WHERE is_active = 1"
            groups = self.db.execute_query(query)
            
            if not groups:
                return []
            
            return [self._row_to_dict(group) for group in groups]
            
        except Exception as e:
            logger.error(f"Error getting all groups: {e}")
            return []
    
    def add_users_to_group(self, group_id: str, user_emails: List[str]) -> Dict[str, Any]:
        """
        Add multiple users to a group by their email addresses
        
        Args:
            group_id: ID of the group
            user_emails: List of user email addresses to add
            
        Returns:
            Dict with status and results
        """
        try:
            results = {
                "added": [],
                "already_member": [],
                "not_found": [],
                "errors": []
            }
            
            for email in user_emails:
                result = self.add_user_to_group_by_email(group_id, email)
                
                if result.get("status") == "success":
                    results["added"].append(email)
                elif result.get("status") == "error":
                    error_msg = result.get("error", "")
                    if "already a member" in error_msg.lower():
                        results["already_member"].append(email)
                    elif "not found" in error_msg.lower():
                        results["not_found"].append(email)
                    else:
                        results["errors"].append({"email": email, "error": error_msg})
            
            return {
                "status": "success",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error adding users to group: {e}")
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }
    
    def remove_users_from_group(self, group_id: str, user_emails: List[str]) -> Dict[str, Any]:
        """
        Remove multiple users from a group by their email addresses
        
        Args:
            group_id: ID of the group
            user_emails: List of user email addresses to remove
            
        Returns:
            Dict with status and results
        """
        try:
            user_manager = OwiUserManager()
            results = {
                "removed": [],
                "not_found": [],
                "errors": []
            }
            
            for email in user_emails:
                try:
                    # Get user by email
                    user = user_manager.get_user_by_email(email)
                    if not user:
                        results["not_found"].append(email)
                        continue
                    
                    # Remove user from group
                    success = self.remove_user_from_group(group_id, user['id'])
                    if success:
                        results["removed"].append(email)
                    else:
                        results["errors"].append({"email": email, "error": "Failed to remove from group"})
                        
                except Exception as e:
                    results["errors"].append({"email": email, "error": str(e)})
            
            return {
                "status": "success",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error removing users from group: {e}")
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }
    
    def get_group_users_by_emails(self, group_id: str) -> List[str]:
        """
        Get list of user emails in a group
        
        Args:
            group_id: ID of the group
            
        Returns:
            List of user email addresses
        """
        try:
            users = self.get_group_users(group_id)
            if users:
                return [user.get('email') for user in users if user.get('email')]
            return []
            
        except Exception as e:
            logger.error(f"Error getting group user emails: {e}")
            return []

    def clean_duplicate_assistant_groups(self) -> None:
        """
        Remove duplicate assistant groups, keeping only the first one created.
        This helps clean up any duplicate groups that may have been created.
        """
        try:
            # Get all groups with names like "assistant_X"
            query = 'SELECT * FROM "group" WHERE name LIKE "assistant_%" AND name NOT LIKE "assistant_%_%" ORDER BY created_at ASC'
            groups = self.db.execute_query(query, fetch_one=False)
            
            if not groups:
                logger.info("No duplicate assistant groups found")
                return
            
            # Group by name to find duplicates
            groups_by_name = {}
            for group in groups:
                group_dict = self._row_to_dict(group)
                name = group_dict.get('name')
                if name not in groups_by_name:
                    groups_by_name[name] = []
                groups_by_name[name].append(group_dict)
            
            # Delete duplicates, keeping the first (oldest) one
            deleted_count = 0
            for name, group_list in groups_by_name.items():
                if len(group_list) > 1:
                    logger.info(f"Found {len(group_list)} duplicate groups with name '{name}', keeping the first one")
                    # Keep the first one (oldest), delete the rest
                    for duplicate_group in group_list[1:]:
                        try:
                            self.delete_group(duplicate_group['id'])
                            deleted_count += 1
                            logger.info(f"Deleted duplicate group '{name}' with ID {duplicate_group['id']}")
                        except Exception as e:
                            logger.error(f"Error deleting duplicate group {duplicate_group['id']}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Successfully cleaned up {deleted_count} duplicate assistant groups")
                
        except Exception as e:
            logger.error(f"Error in clean_duplicate_assistant_groups: {e}")