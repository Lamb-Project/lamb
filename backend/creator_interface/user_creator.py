import httpx
import os
from typing import Optional, Dict, Any
import config
from lamb.database_manager import LambDatabaseManager
from lamb.creator_user_router import create_creator_user as core_create_creator_user, verify_creator_user as core_verify_creator_user, list_creator_users as core_list_creator_users


class UserCreatorManager:
    def __init__(self):
        # Use LAMB_BACKEND_HOST for internal server-to-server requests
        self.pipelines_host = config.LAMB_BACKEND_HOST
        self.pipelines_bearer_token = config.API_KEY
        if not self.pipelines_host or not self.pipelines_bearer_token:
            raise ValueError(
                "LAMB_BACKEND_HOST and API_KEY environment variables are required")

    async def update_user_password(self, email: str, new_password: str) -> Dict[str, Any]:
        """
        Update an existing user's password
        
        Args:
            email: User's email address
            new_password: User's new password
            
        Returns:
            Dict[str, Any]: Response containing success status and error information if any
        """
        try:
            # Call OWI bridge to update password
            async with httpx.AsyncClient() as client:
                # First try with PUT method
                response = await client.put(
                    f"{self.pipelines_host}/lamb/v1/OWI/users/update_password",
                    headers={
                        "Authorization": f"Bearer {self.pipelines_bearer_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": email,
                        "new_password": new_password
                    },
                    timeout=30.0  # Add a reasonable timeout
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "Password updated successfully",
                        "error": None
                    }
                # If PUT fails with method not allowed, try alternative endpoint
                elif response.status_code == 405:
                    print(f"PUT method not allowed for update_password. Trying alternative endpoint.")
                    
                    # Try with an alternative endpoint that might be available
                    alt_response = await client.post(
                        f"{self.pipelines_host}/lamb/v1/OWI/users/password",
                        headers={
                            "Authorization": f"Bearer {self.pipelines_bearer_token}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "email": email,
                            "new_password": new_password
                        },
                        timeout=30.0
                    )
                    
                    if alt_response.status_code == 200:
                        return {
                            "success": True,
                            "message": "Password updated successfully via alternative endpoint",
                            "error": None
                        }
                    error_detail = alt_response.json().get('detail', 'Failed to update password via alternative endpoint')
                    return {"success": False, "error": error_detail, "data": None}
                else:
                    error_detail = response.json().get('detail', 'Failed to update password')
                    return {"success": False, "error": error_detail, "data": None}
                    
        except Exception as e:
            import traceback
            print(f"Error updating password: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": None}

    async def create_user(self, email: str, name: str, password: str, role: str = "user", organization_id: int = None, user_type: str = "creator") -> Dict[str, Any]:
        """
        Create a new creator user through the API
        
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
            # First, create the creator user in LAMB
            async with httpx.AsyncClient() as client:
                payload = {
                    "email": email,
                    "name": name,
                    "password": password,
                    "user_type": user_type
                }
                
                # Add organization_id if provided
                if organization_id is not None:
                    payload["organization_id"] = organization_id
                    
                response = await client.post(
                    f"{self.pipelines_host}/lamb/v1/creator_user/create",
                    headers={
                        "Authorization": f"Bearer {self.pipelines_bearer_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                if response.status_code != 200:
                    error_detail = response.json().get('detail', 'unknown_error')
                    return {"success": False, "error": error_detail}
                
                # Extract user_id from response
                user_id = response.json()
                
                # If role needs to be set to admin, we need to update the OWI user
                if role == "admin":
                    # Create or update the OWI user with admin role
                    owi_response = await client.post(
                        f"{self.pipelines_host}/lamb/v1/OWI/users",
                        headers={
                            "Authorization": f"Bearer {self.pipelines_bearer_token}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "name": name,
                            "email": email,
                            "password": password,
                            "role": "admin"
                        }
                    )
                    
                    if owi_response.status_code != 200:
                        print(f"Warning: User created but failed to set admin role: {owi_response.text}")
                        return {
                            "success": True, 
                            "warning": "User created but failed to set admin role",
                            "error": None,
                            "user_id": user_id
                        }
                
                return {"success": True, "error": None, "user_id": user_id}

        except Exception as e:
            print(f"Error during user creation: {e}")
            return {"success": False, "error": "server_error"}

    async def verify_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Verify user credentials and return user info with token and OWI launch URL
        
        Special handling for admin user:
        If the user is the admin (as defined in OWI system) but not yet a creator user,
        they will be automatically added as a creator user.
        """
        try:
            # First verify the user normally
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.pipelines_host}/lamb/v1/creator_user/verify",
                    headers={
                        "Authorization": f"Bearer {self.pipelines_bearer_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": email,
                        "password": password
                    }
                )

                # If verification failed, check if this is the admin user trying to log in
                if response.status_code != 200:
                    # Check if this is the admin user from OWI
                    admin_email = os.getenv("OWI_ADMIN_EMAIL", "admin@owi.com")
                    
                    if email == admin_email:
                        print(f"Admin user {email} attempted login but is not a creator user. Checking OWI credentials...")
                        
                        # Verify against OWI directly to confirm admin credentials
                        owi_verify_response = await client.post(
                            f"{self.pipelines_host}/lamb/v1/OWI/users/verify",
                            headers={
                                "Authorization": f"Bearer {self.pipelines_bearer_token}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "email": email,
                                "password": password
                            }
                        )
                        
                        if owi_verify_response.status_code == 200:
                            owi_user_data = owi_verify_response.json().get('data', {})
                            
                            # Confirm this is actually the admin user
                            if owi_user_data and owi_user_data.get('role') == 'admin':
                                print(f"Verified admin user {email}. Creating creator user account...")
                                
                                # Create a creator user for the admin
                                create_response = await client.post(
                                    f"{self.pipelines_host}/lamb/v1/creator_user/create",
                                    headers={
                                        "Authorization": f"Bearer {self.pipelines_bearer_token}",
                                        "Content-Type": "application/json"
                                    },
                                    json={
                                        "email": email,
                                        "name": owi_user_data.get('name', 'Admin User'),
                                        "password": password
                                    }
                                )
                                
                                # If user creation succeeded or user already exists (409), try verification
                                if create_response.status_code == 200:
                                    print(f"Successfully created creator user for admin {email}")
                                elif create_response.status_code == 409:
                                    print(f"Creator user for admin {email} already exists, proceeding with verification")
                                else:
                                    print(f"Failed to create creator user for admin: {create_response.text}")
                                
                                # Try to verify (works for both new and existing users)
                                if create_response.status_code in [200, 409]:
                                    response = await client.post(
                                        f"{self.pipelines_host}/lamb/v1/creator_user/verify",
                                        headers={
                                            "Authorization": f"Bearer {self.pipelines_bearer_token}",
                                            "Content-Type": "application/json"
                                        },
                                        json={
                                            "email": email,
                                            "password": password
                                        }
                                    )

                # Process the verification response (either original or after admin handling)
                if response.status_code == 200:
                    data = response.json()

                    # Get OWI launch URL
                    owi_response = await client.get(
                        f"{self.pipelines_host}/lamb/v1/OWI/users/login/{email}",
                        headers={
                            "Authorization": f"Bearer {self.pipelines_bearer_token}"
                        }
                    )

                    launch_url = None
                    if owi_response.status_code == 200:
                        # The URL is returned directly as text
                        launch_url = owi_response.text.strip('"')
                    print(f"Launch URL: {launch_url}")
                    
                    # Fetch organization role if user belongs to an organization
                    organization_role = None
                    db_manager = LambDatabaseManager()
                    creator_user = db_manager.get_creator_user_by_email(email)
                    
                    if creator_user and creator_user.get('organization_id'):
                        organization_role = db_manager.get_user_organization_role(
                            user_id=creator_user['id'],
                            organization_id=creator_user['organization_id']
                        )
                        print(f"User {email} has organization role: {organization_role}")
                    
                    data_to_return = {
                        "success": True,
                        "data": {
                            "token": data.get("token"),
                            "name": data.get("name"),
                            "email": data.get("email"),
                            "launch_url": launch_url,
                            "user_id": data.get("id"),
                            "role": data.get("role", "user"),  # Include role from response, default to 'user'
                            "user_type": data.get("user_type", "creator"),  # Include user_type from response
                            "organization_role": organization_role  # Include organization role
                        },
                        "error": None
                    }
                    print(f"Data to return: {data_to_return}")
                    return data_to_return
                else:
                    error_detail = response.json().get('detail', 'Invalid credentials')
                    return {"success": False, "error": error_detail, "data": None}

        except Exception as e:
            print(f"Error during login: {e}")
            return {"success": False, "error": "server_error", "data": None}
    
    async def list_all_creator_users(self) -> Dict[str, Any]:
        """
        Get a list of all creator users from the LAMB API and enrich with OWI role information
        
        Returns:
            Dict[str, Any]: Response containing list of users or error information
        """
        try:
            async with httpx.AsyncClient() as client:
                # Get basic creator user list from LAMB API
                response = await client.get(
                    f"{self.pipelines_host}/lamb/v1/creator_user/list",
                    headers={
                        "Authorization": f"Bearer {self.pipelines_bearer_token}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    creator_users = response.json()
                    print(f"Raw creator users from LAMB API: {creator_users}")
                    
                    # Now get each user's role from OWI for each creator user
                    for user in creator_users:
                        try:
                            # Get OWI user info to determine role
                            owi_response = await client.get(
                                f"{self.pipelines_host}/lamb/v1/OWI/users/email/{user['email']}",
                                headers={
                                    "Authorization": f"Bearer {self.pipelines_bearer_token}",
                                    "Content-Type": "application/json"
                                }
                            )
                            
                            if owi_response.status_code == 200:
                                owi_user = owi_response.json()
                                # Get role and ID from OWI user and add to creator user data
                                user['role'] = owi_user.get('role', 'user')
                                user['owi_id'] = owi_user.get('id', None)
                                print(f"Found OWI user with role '{user['role']}' and ID '{user['owi_id']}' for email {user['email']}")
                            else:
                                # No OWI user found or other error
                                user['role'] = 'user'  # Default role
                                user['owi_id'] = None
                                print(f"No OWI user found for email {user['email']}, using default role 'user'")
                        except Exception as e:
                            # Handle errors when fetching OWI user info
                            user['role'] = 'user'  # Default role
                            user['owi_id'] = None
                            print(f"Error fetching OWI role for user {user['email']}: {e}")
                    
                    # Debug log to see the enhanced structure
                    print(f"Users list with roles being returned: {creator_users}")
                    
                    return {
                        "success": True,
                        "data": creator_users,
                        "error": None
                    }
                else:
                    error_detail = response.json().get("detail", "Failed to retrieve users")
                    return {"success": False, "error": error_detail, "data": None}
                    
        except Exception as e:
            print(f"Error listing creator users: {e}")
            return {"success": False, "error": "server_error", "data": None}
