"""
Creator User Service

Encapsulates all business logic for creator user management.
This service is used by both the creator_interface API and internal operations.
"""

import logging
from typing import Any, Dict, List, Optional
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="SERVICE")


class CreatorUserService:
    """Service layer for creator user operations"""
    
    def __init__(self):
        self.db_manager = LambDatabaseManager()
        self.owi_user_manager = OwiUserManager()
    
    def create_user(
        self, 
        email: str, 
        name: str, 
        password: str, 
        organization_id: Optional[int] = None,
        user_type: str = "creator"
    ) -> Optional[int]:
        """
        Create a new creator user
        
        Args:
            email: User's email address
            name: User's full name
            password: User's password
            organization_id: Optional organization ID to assign user to
            user_type: Type of user ('creator' or 'end_user')
            
        Returns:
            User ID if successful, None if user already exists
            
        Raises:
            ValueError: If creation fails
        """
        try:
            # Check if user already exists
            existing_user = self.db_manager.get_creator_user_by_email(email)
            if existing_user:
                logger.warning(f"User with email {email} already exists")
                return None
            
            # Create new user (this also creates OWI user)
            user_id = self.db_manager.create_creator_user(
                user_email=email,
                user_name=name,
                password=password,
                organization_id=organization_id,
                user_type=user_type
            )
            
            if not user_id:
                raise ValueError("Failed to create creator user")
            
            logger.info(f"Created creator user {email} with ID {user_id}")
            return user_id
            
        except Exception as e:
            logger.error(f"Error creating creator user {email}: {str(e)}")
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def verify_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify creator user credentials
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            User info dict with token, name, email, role, id, user_type
            None if credentials are invalid
            
        Raises:
            ValueError: If account is disabled
        """
        try:
            logger.info(f"Verifying creator user: {email}")
            
            # Get creator user from database
            user = self.db_manager.get_creator_user_by_email(email)
            
            if not user:
                logger.warning(f"Creator user not found: {email}")
                return None
            
            # Check if user account is enabled
            if not user.get('enabled', True):
                logger.warning(f"Disabled user {email} attempted login")
                raise ValueError("Account has been disabled. Please contact your administrator.")
            
            # Verify password via OWI
            owi_user = self.owi_user_manager.verify_user(
                email=email,
                password=password
            )
            
            if not owi_user:
                logger.warning(f"Invalid password for user: {email}")
                return None
            
            # Get auth token from OWI
            auth_token = self.owi_user_manager.get_auth_token(email, user["name"])
            if not auth_token:
                raise ValueError("Failed to get authentication token")
            
            # Get user's role
            user_role = "admin" if user.get("is_admin") else "user"
            
            # Also check OWI role
            if owi_user and "role" in owi_user:
                owi_role = owi_user["role"]
                if owi_role == "admin":
                    user_role = "admin"
                logger.debug(f"Got role '{owi_role}' from OWI for user {email}")
            
            logger.info(f"User {email} verified successfully with role: {user_role}")
            
            # Return user info
            return {
                "token": auth_token,
                "name": user["name"],
                "email": user["email"],
                "role": user_role,
                "id": user["id"],
                "user_type": user.get("user_type", "creator")
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error verifying creator user {email}: {str(e)}")
            raise ValueError(f"Failed to verify user: {str(e)}")
    
    def check_user_exists(self, email: str) -> Optional[int]:
        """
        Check if a creator user exists by email
        
        Args:
            email: User's email address
            
        Returns:
            User ID if exists, None otherwise
        """
        try:
            user = self.db_manager.get_creator_user_by_email(email)
            if user:
                return user['id']
            return None
            
        except Exception as e:
            logger.error(f"Error checking creator user {email}: {str(e)}")
            raise ValueError(f"Failed to check user: {str(e)}")
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        Get a list of all creator users
        
        Returns:
            List of user dicts with id, email, name, user_config
            
        Raises:
            ValueError: If retrieval fails
        """
        try:
            users = self.db_manager.get_creator_users()
            if users is None:
                raise ValueError("Failed to retrieve creator users")
            return users
            
        except Exception as e:
            logger.error(f"Error listing creator users: {str(e)}")
            raise ValueError(f"Failed to list users: {str(e)}")
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get creator user by email
        
        Args:
            email: User's email address
            
        Returns:
            User dict if found, None otherwise
        """
        try:
            return self.db_manager.get_creator_user_by_email(email)
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get creator user by ID
        
        Args:
            user_id: User's ID
            
        Returns:
            User dict if found, None otherwise
        """
        try:
            # Note: database_manager doesn't have get_creator_user_by_id,
            # so we get all users and filter (or add the method to db_manager)
            users = self.db_manager.get_creator_users()
            if users:
                for user in users:
                    if user.get('id') == user_id:
                        return user
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {str(e)}")
            return None

