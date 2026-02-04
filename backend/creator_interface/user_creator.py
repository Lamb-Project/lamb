import httpx
import os
from typing import Optional, Dict, Any
import config
from lamb.database_manager import LambDatabaseManager
from lamb.services import CreatorUserService
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")


class UserCreatorManager:
    def __init__(self):
        # Use LAMB_BACKEND_HOST for internal server-to-server requests
        self.pipelines_host = config.LAMB_BACKEND_HOST
        self.pipelines_bearer_token = config.API_KEY
        
        # Initialize services
        self.creator_user_service = CreatorUserService()
        self.owi_user_manager = OwiUserManager()
        
        if not self.pipelines_host or not self.pipelines_bearer_token:
            raise ValueError(
                "LAMB_BACKEND_HOST and API_KEY environment variables are required")

    async def update_user_password(self, email: str, new_password: str) -> Dict[str, Any]:
        """
        Update an existing user's password using OWI user manager directly
        
        Args:
            email: User's email address
            new_password: User's new password
            
        Returns:
            Dict[str, Any]: Response containing success status and error information if any
            
        Note:
            LTI creator users cannot have their password changed.
        """
        try:
            # Check if user is an LTI creator user (password changes not allowed)
            db_manager = LambDatabaseManager()
            creator_user = db_manager.get_creator_user_by_email(email)
            
            if creator_user and creator_user.get('auth_provider') == 'lti_creator':
                logger.warning(f"Attempted to change password for LTI creator user: {email}")
                return {
                    "success": False,
                    "error": "Password changes are not allowed for LTI users",
                    "data": None
                }
            
            # Update password using OWI manager directly
            success = self.owi_user_manager.update_user_password(email, new_password)
            
            if success:
                return {
                    "success": True,
                    "message": "Password updated successfully",
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to update password",
                    "data": None
                }
                    
        except Exception as e:
            import traceback
            logger.error(f"Error updating password: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e), "data": None}

    async def create_user(self, email: str, name: str, password: str, role: str = "user", organization_id: int = None, user_type: str = "creator") -> Dict[str, Any]:
        """
        Create a new creator user using the service layer
        
        Args:
            email: User's email address
            name: User's display name
            password: User's password
            role: User's role, either 'user' or 'admin' (default: 'user')
            organization_id: Organization ID to assign user to (optional, defaults to system org)
            user_type: Type of user - 'creator' (default) or 'end_user'
            
        Returns:
            Dict[str, Any]: Response containing success status and error information if any
        """
        try:
            # Create the creator user using service layer
            user_id = self.creator_user_service.create_user(
                email=email,
                name=name,
                password=password,
                organization_id=organization_id,
                user_type=user_type
            )
            
            if user_id is None:
                return {"success": False, "error": "User already exists"}
            
            # If role needs to be set to admin, update the OWI user role
            if role == "admin":
                # Get the OWI user and update their role
                owi_user = self.owi_user_manager.get_user_by_email(email)
                if owi_user:
                    success = self.owi_user_manager.update_user_role(owi_user['id'], 'admin')
                    if not success:
                        logger.warning(f"User created but failed to set admin role for {email}")
                        return {
                            "success": True, 
                            "warning": "User created but failed to set admin role",
                            "error": None,
                            "user_id": user_id
                        }
                else:
                    logger.warning(f"User created but OWI user not found for {email}")
            
            return {"success": True, "error": None, "user_id": user_id}
            
        except ValueError as e:
            logger.error(f"Error during user creation: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error during user creation: {str(e)}")
            return {"success": False, "error": "server_error"}

    async def verify_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Verify user credentials and return user info with token and OWI launch URL using service layer
        
        Special handling for admin user:
        If the user is the admin (as defined in OWI system) but not yet a creator user,
        they will be automatically added as a creator user.
        """
        try:
            # Try to verify using the service
            user_info = self.creator_user_service.verify_user(email, password)
            
            # If verification failed, check if this is the admin user trying to log in
            if not user_info:
                import config
                admin_email = config.OWI_ADMIN_EMAIL
                
                if email == admin_email:
                    logger.info(f"Admin user {email} attempted login but is not a creator user. Checking OWI credentials...")
                    
                    # Verify against OWI directly
                    owi_user = self.owi_user_manager.verify_user(email, password)
                    
                    if owi_user and owi_user.get('role') == 'admin':
                        logger.info(f"Verified admin user {email}. Creating creator user account...")
                        
                        # Create a creator user for the admin
                        user_id = self.creator_user_service.create_user(
                            email=email,
                            name=owi_user.get('name', 'Admin User'),
                            password=password
                        )
                        
                        if user_id:
                            logger.info(f"Successfully created creator user for admin {email}")
                            # Try verification again
                            user_info = self.creator_user_service.verify_user(email, password)
                        else:
                            logger.error(f"Failed to create creator user for admin {email}")
            
            if user_info:
                # Get OWI launch URL using manager directly
                launch_url = self.owi_user_manager.get_login_url(email, user_info.get("name"))
                logger.debug(f"Launch URL: {launch_url}")
                
                # Fetch organization role if user belongs to an organization
                organization_role = None
                db_manager = LambDatabaseManager()
                creator_user = db_manager.get_creator_user_by_email(email)
                
                if creator_user and creator_user.get('organization_id'):
                    organization_role = db_manager.get_user_organization_role(
                        user_id=creator_user['id'],
                        organization_id=creator_user['organization_id']
                    )
                    logger.debug(f"User {email} has organization role: {organization_role}")
                
                data_to_return = {
                    "success": True,
                    "data": {
                        "token": user_info.get("token"),
                        "name": user_info.get("name"),
                        "email": user_info.get("email"),
                        "launch_url": launch_url,
                        "user_id": user_info.get("id"),
                        "role": user_info.get("role", "user"),
                        "user_type": user_info.get("user_type", "creator"),
                        "organization_role": organization_role
                    },
                    "error": None
                }
                logger.debug(f"Data to return: {data_to_return}")
                return data_to_return
            else:
                return {"success": False, "error": "Invalid credentials", "data": None}
        
        except ValueError as e:
            # Account disabled
            logger.error(f"ValueError during login: {str(e)}")
            return {"success": False, "error": str(e), "data": None}
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return {"success": False, "error": "server_error", "data": None}
    
    async def list_all_creator_users(self) -> Dict[str, Any]:
        """
        Get a list of all creator users using service layer and enrich with OWI role information
        
        Returns:
            Dict[str, Any]: Response containing list of users or error information
        """
        try:
            # Get creator users from service
            creator_users = self.creator_user_service.list_users()
            
            if creator_users is None:
                return {"success": False, "error": "Failed to retrieve users", "data": None}
            
            logger.debug(f"Raw creator users from service: {creator_users}")
            
            # Enrich with OWI role information using manager directly
            for user in creator_users:
                try:
                    # Get OWI user info to determine role
                    owi_user = self.owi_user_manager.get_user_by_email(user['email'])
                    
                    if owi_user:
                        user['role'] = owi_user.get('role', 'user')
                        user['owi_id'] = owi_user.get('id', None)
                        logger.debug(f"Found OWI user with role '{user['role']}' and ID '{user['owi_id']}' for email {user['email']}")
                    else:
                        user['role'] = 'user'
                        user['owi_id'] = None
                        logger.debug(f"No OWI user found for email {user['email']}, using default role 'user'")
                except Exception as e:
                    user['role'] = 'user'
                    user['owi_id'] = None
                    logger.error(f"Error fetching OWI role for user {user['email']}: {e}")
            
            logger.debug(f"Users list with roles being returned: {creator_users}")
            
            return {
                "success": True,
                "data": creator_users,
                "error": None
            }
            
        except ValueError as e:
            logger.error(f"Error listing creator users: {str(e)}")
            return {"success": False, "error": str(e), "data": None}
        except Exception as e:
            logger.error(f"Unexpected error listing creator users: {e}")
            return {"success": False, "error": "server_error", "data": None}
