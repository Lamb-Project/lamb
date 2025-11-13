import uuid
from passlib.context import CryptContext
import logging
from typing import Optional, Dict
import time
from .owi_database import OwiDatabaseManager
import requests
import os
import warnings
import config

# Suppress the specific passlib warning about bcrypt version
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

# Use LAMB_WEB_HOST for profile image URLs (browsers need to access these)
PIPELINES_HOST = config.LAMB_WEB_HOST


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# If not already configured elsewhere, add this:
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Password hashing configuration
# Using bcrypt with settings that work with newer bcrypt 4.x versions
# The warning occurs because passlib tries to detect bcrypt version in a way
# that's incompatible with bcrypt 4.x, but the functionality still works correctly
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=12
)


class OwiUserManager:
    def __init__(self):
        import config
        self.db = OwiDatabaseManager()
        self.OWI_BASE_URL = config.OWI_BASE_URL
        self.OWI_API_BASE_URL = self.OWI_BASE_URL+"/api/v1"
        # Public-facing base URL to hand back to browsers. Falls back to internal base if not provided.
        self.OWI_PUBLIC_BASE_URL = config.OWI_PUBLIC_BASE_URL
        self.OWI_PUBLIC_API_BASE_URL = self.OWI_PUBLIC_BASE_URL+"/api/v1"
        # this will ensure that the admin user is created
        self.admin_token = self.get_admin_user_token()

    def create_user(self, name: str, email: str, password: str, role: str = "user") -> Optional[Dict]:
        """
        Create a new user with authentication

        Args:
            name (str): User's name
            email (str): User's email
            password (str): User's password
            role (str): User's role (default: "user")

        Returns:
            Optional[Dict]: Created user data or None if creation fails
        """
        try:
            # get admin token
            # we will not use the admin token for this operation
            # but we will ensure the admin user is created
            #

            if self.db.get_user_by_email(email):
                logger.error(f"User with email {email} already exists")
                return None

            # Generate user ID and hash password
            user_id = str(uuid.uuid4())
            hashed_password = pwd_context.hash(password)
            current_time = int(time.time())

            profile_image_url = f"{PIPELINES_HOST}/static/img/lamb_icon.png"
            # Create user entry
            user_query = """
                INSERT INTO user (id, name, email, role, profile_image_url, 
                                created_at, updated_at, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            user_params = (
                user_id, name, email, role, profile_image_url,  # Empty profile image URL
                current_time, current_time, current_time
            )

            # Create auth entry
            auth_query = """
                INSERT INTO auth (id, email, password, active)
                VALUES (?, ?, ?, ?)
            """
            auth_params = (user_id, email, hashed_password, 1)  # 1 = active

            # Execute both queries
            conn = self.db.get_connection()
            if not conn:
                return None

            try:
                cursor = conn.cursor()
                cursor.execute(user_query, user_params)
                cursor.execute(auth_query, auth_params)
                conn.commit()

                # Return the created user
                return self.db.get_user_by_id(user_id)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error creating user: {e}")
                return None
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in create_user: {e}")
            return None

    def get_login_url(self, email: str, name: str) -> str:
        token = self.get_auth_token(email, name)
        # Return a public URL suitable for clients, even if the backend uses an internal host for service-to-service calls
        return f"{self.OWI_PUBLIC_API_BASE_URL}/auths/complete?token={token}"

    def get_admin_user_token(self) -> str:
        import config
        admin_email = config.OWI_ADMIN_EMAIL
        admin_name = config.OWI_ADMIN_NAME
        admin_password = config.OWI_ADMIN_PASSWORD
        # check if the admin user exists
        user = self.get_user_by_email(admin_email)
        if not user:
            logger.error(f"Admin user {admin_email} not found, creating...")
            self.create_user(admin_name, admin_email, admin_password, "admin")

        return self.get_auth_token(admin_email, admin_name)

    def get_auth_token(self, email: str, name: str) -> str:

        try:

            response = requests.post(
                f"{self.OWI_API_BASE_URL}/auths/signin",
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-User-Email': email,
                    'X-User-Name': name
                },
                json={
                    'email': '',
                    'password': ''
                }
            )

            if response.status_code != 200:
                logger.error(
                    f"Auth request failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return None

            return response.json()['token']

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting auth token: {str(e)}")
            return None

    def verify_user(self, email: str, password: str) -> Optional[Dict]:
        """
        Verify user credentials

        Args:
            email (str): User's email
            password (str): User's password

        Returns:
            Optional[Dict]: User data if verification succeeds, None otherwise
        """
        try:
            # Get auth record
            query = "SELECT id, password FROM auth WHERE email = ? AND active = 1"
            result = self.db.execute_query(query, (email,), fetch_one=True)

            if not result:
                return None

            user_id, hashed_password = result

            # Check if the hash is in a valid format
            if not hashed_password or not hashed_password.startswith('$2'):
                return None

            # Verify password
            verification_result = pwd_context.verify(password, hashed_password)

            if not verification_result:
                return None

            # Get and return user data
            user_data = self.db.get_user_by_id(user_id)

            return user_data

        except Exception as e:
            logger.error(f"Unexpected error in verify_user: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get a user by their ID

        Args:
            user_id (str): The user ID to look up

        Returns:
            Optional[Dict]: User data if found, None otherwise
        """
        try:
            return self.db.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get a user by their email address

        Args:
            email (str): The email address to look up

        Returns:
            Optional[Dict]: User data if found, None otherwise
        """
        try:
            return self.db.get_user_by_email(email)
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    def update_user_password(self, email: str, new_password: str) -> bool:
        """
        Update a user's password in the authentication database

        Args:
            email (str): User's email
            new_password (str): New password to set

        Returns:
            bool: True if password was updated successfully, False otherwise
        """
        try:
            # Check if user exists
            user = self.db.get_user_by_email(email)
            if not user:
                logger.error(f"User with email {email} not found")
                return False

            # Hash the new password
            hashed_password = pwd_context.hash(new_password)

            # Update the password in the auth table
            query = "UPDATE auth SET password = ? WHERE email = ?"
            params = (hashed_password, email)

            # Execute the query
            conn = self.db.get_connection()
            if not conn:
                logger.error("Failed to connect to database")
                return False

            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    return True
                else:
                    logger.error(f"No auth record found for user {email}")
                    return False
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating password: {e}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in update_user_password: {e}")
            return False

    def update_user_status(self, email: str, enabled: bool) -> bool:
        """
        Enable or disable a user by updating their active status

        Args:
            email (str): User's email
            enabled (bool): True to enable user, False to disable

        Returns:
            bool: True if status was updated successfully, False otherwise
        """
        try:
            # Check if user exists
            user = self.db.get_user_by_email(email)
            if not user:
                logger.error(f"User with email {email} not found")
                return False

            # Update the active status in the auth table
            active_value = 1 if enabled else 0
            query = "UPDATE auth SET active = ? WHERE email = ?"
            params = (active_value, email)

            # Execute the query
            conn = self.db.get_connection()
            if not conn:
                logger.error("Failed to connect to database")
                return False

            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    status_text = "enabled" if enabled else "disabled"
                    logger.info(f"User {email} has been {status_text}")
                    return True
                else:
                    logger.error(f"No auth record found for user {email}")
                    return False

            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating user status: {e}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error updating user status: {e}")
            return False

    def get_user_status(self, email: str) -> Optional[bool]:
        """
        Get the enabled/disabled status of a user

        Args:
            email (str): User's email

        Returns:
            Optional[bool]: True if enabled, False if disabled, None if user not found
        """
        try:
            query = "SELECT active FROM auth WHERE email = ?"
            result = self.db.execute_query(query, (email,), fetch_one=True)

            if result:
                return bool(result[0])
            else:
                logger.error(f"No auth record found for user {email}")
                return None

        except Exception as e:
            logger.error(f"Error getting user status: {e}")
            return None

    def delete_user(self, email: str) -> bool:
        """
        Delete a user from the database (user and auth tables)

        Args:
            email (str): User's email

        Returns:
            bool: True if user was deleted successfully or didn't exist, False on error
        """
        try:
            # Check if user exists in OWI database
            user = self.db.get_user_by_email(email)
            if not user:
                logger.warning(f"User with email {email} not found in OWI database (may only exist in LAMB)")
                # Return True since there's nothing to delete in OWI - the user may only exist in LAMB
                return True

            user_id = user.get('id')
            
            # Prevent deletion of admin user (user ID 1)
            if user_id == "1":
                logger.error(f"Cannot delete admin user (ID 1)")
                return False

            # Delete from both auth and user tables
            conn = self.db.get_connection()
            if not conn:
                logger.error("Failed to connect to database")
                return False

            try:
                cursor = conn.cursor()
                
                # Delete from auth table first (may or may not exist)
                cursor.execute("DELETE FROM auth WHERE email = ?", (email,))
                auth_deleted = cursor.rowcount
                
                # Delete from user table
                cursor.execute("DELETE FROM user WHERE id = ?", (user_id,))
                user_deleted = cursor.rowcount
                
                conn.commit()

                if user_deleted > 0:
                    logger.info(f"User {email} has been deleted successfully from OWI (auth: {auth_deleted > 0}, user: {user_deleted > 0})")
                    return True
                else:
                    logger.warning(f"User {email} record was not deleted (may have already been removed)")
                    return True  # Return True anyway since the goal is achieved

            except Exception as e:
                conn.rollback()
                logger.error(f"Error deleting user: {e}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error deleting user: {e}")
            return False

    def update_user_role(self, user_id: str, new_role: str) -> bool:
        """
        Update a user's role in the database

        Args:
            user_id (str): User's ID
            new_role (str): New role to set (e.g., 'admin', 'user')

        Returns:
            bool: True if role was updated successfully, False otherwise
        """
        try:
            logger.error(
                f"[ROLE_DEBUG] Starting update_user_role for user_id={user_id}, new_role={new_role}")

            # Check if user exists
            logger.error(f"[ROLE_DEBUG] Checking if user {user_id} exists")
            user = self.db.get_user_by_id(user_id)
            logger.error(f"[ROLE_DEBUG] User lookup result: {user}")

            if not user:
                logger.error(f"[ROLE_DEBUG] User with ID {user_id} not found")
                return False

            # Check if this is user ID 1, which must always remain admin
            if user_id == "1":
                logger.error(
                    f"[ROLE_DEBUG] Cannot change role for user ID 1, must remain admin")
                return False

            # Validate the new role
            if new_role not in ['admin', 'user']:
                logger.error(
                    f"[ROLE_DEBUG] Invalid role: {new_role}. Must be 'admin' or 'user'")
                return False

            # Check current schema
            try:
                logger.error(f"[ROLE_DEBUG] Checking database schema")
                conn_check = self.db.get_connection()
                if conn_check:
                    cursor_check = conn_check.cursor()
                    try:
                        # Check if role column exists in user table
                        cursor_check.execute("PRAGMA table_info(user)")
                        columns = cursor_check.fetchall()
                        logger.error(
                            f"[ROLE_DEBUG] User table schema: {columns}")

                        has_role_column = any(
                            col[1] == 'role' for col in columns)
                        logger.error(
                            f"[ROLE_DEBUG] Has role column: {has_role_column}")

                        if not has_role_column:
                            logger.error(
                                f"[ROLE_DEBUG] 'role' column doesn't exist in user table")
                            # Try to add the column
                            try:
                                logger.error(
                                    f"[ROLE_DEBUG] Attempting to add 'role' column to user table")
                                cursor_check.execute(
                                    "ALTER TABLE user ADD COLUMN role TEXT DEFAULT 'user'")
                                conn_check.commit()
                                logger.error(
                                    f"[ROLE_DEBUG] Successfully added 'role' column")
                            except Exception as schema_error:
                                logger.error(
                                    f"[ROLE_DEBUG] Failed to add role column: {schema_error}")
                    except Exception as schema_check_error:
                        logger.error(
                            f"[ROLE_DEBUG] Error checking schema: {schema_check_error}")
                    finally:
                        conn_check.close()
            except Exception as conn_error:
                logger.error(
                    f"[ROLE_DEBUG] Error connecting to database for schema check: {conn_error}")

            # Update the role in the user table
            query = "UPDATE user SET role = ? WHERE id = ?"
            params = (new_role, user_id)
            logger.error(
                f"[ROLE_DEBUG] *** CRITICAL DEBUG POINT *** Preparing to execute query: {query} with params {params}")

            # Log the database type and connection details
            logger.error(
                f"[ROLE_DEBUG] Database manager: {type(self.db).__name__}")
            logger.error(
                f"[ROLE_DEBUG] Database path (if SQLite): {getattr(self.db, 'db_path', 'Not available')}")

            # Execute the query
            try:
                conn = self.db.get_connection()
                logger.error(
                    f"[ROLE_DEBUG] Database connection result: {conn is not None}")
                logger.error(
                    f"[ROLE_DEBUG] Connection type: {type(conn).__name__ if conn else 'None'}")
            except Exception as conn_error:
                logger.error(
                    f"[ROLE_DEBUG] Exception while getting DB connection: {type(conn_error).__name__}: {str(conn_error)}")
                import traceback
                logger.error(
                    f"[ROLE_DEBUG] Connection error traceback:\n{traceback.format_exc()}")
                return False

            if not conn:
                logger.error("[ROLE_DEBUG] Failed to connect to database")
                return False

            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.error(
                        f"[ROLE_DEBUG] Role updated successfully for user {user_id} to {new_role}")
                    return True
                else:
                    logger.error(
                        f"[ROLE_DEBUG] No user record found for user {user_id}")
                    return False
            except Exception as e:
                conn.rollback()
                logger.error(f"[ROLE_DEBUG] Error updating role: {e}")
                logger.error(f"[ROLE_DEBUG] Query: {query}, Params: {params}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(
                f"[ROLE_DEBUG] Unexpected error in update_user_role: {e}")
            import traceback
            logger.error(f"[ROLE_DEBUG] Traceback: {traceback.format_exc()}")
            return False

    def update_user_role_by_email(self, email: str, new_role: str) -> bool:
        """
        Update a user's role in the database using their email address

        Args:
            email (str): User's email address
            new_role (str): New role to set (e.g., 'admin', 'user')

        Returns:
            bool: True if role was updated successfully, False otherwise
        """
        try:
            # Check if user exists
            user = self.db.get_user_by_email(email)

            if not user:
                logger.error(f"User with email {email} not found")
                return False

            # Check if this is the primary admin user (ID 1) which must remain admin
            if user.get('id') == "1":
                logger.error(
                    "Cannot change role for primary admin user (ID 1)")
                return False

            # Validate the new role
            if new_role not in ['admin', 'user']:
                logger.error(
                    f"Invalid role: {new_role}. Must be 'admin' or 'user'")
                return False

            # Ensure role column exists in schema
            self._ensure_role_column_exists()

            # Update the role in the user table directly by email
            query = "UPDATE user SET role = ? WHERE email = ?"
            params = (new_role, email)

            # Execute the query
            conn = self.db.get_connection()
            if not conn:
                logger.error("Failed to connect to database")
                return False

            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()

                # Note: rowcount may be 0 if the role was already set to the requested value
                # This is still considered a success since no error occurred
                if cursor.rowcount >= 0:
                    logger.error(
                        f"Role updated successfully for user {email} to {new_role}")
                    return True
                else:
                    logger.error(f"No user record found for email {email}")
                    return False
            except Exception as e:
                conn.rollback()
                logger.error(f"Error executing query: {e}")
                return False
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Unexpected error in update_user_role_by_email: {e}")
            return False

    def _ensure_role_column_exists(self):
        """
        Helper method to ensure the role column exists in the user table
        If it doesn't exist, it will be added with a default value of 'user'
        """
        try:
            conn = self.db.get_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    # Check if role column exists in user table
                    cursor.execute("PRAGMA table_info(user)")
                    columns = cursor.fetchall()

                    has_role_column = any(col[1] == 'role' for col in columns)

                    if not has_role_column:
                        logger.warning(
                            "'role' column doesn't exist in user table, adding it")
                        # Add the column
                        cursor.execute(
                            "ALTER TABLE user ADD COLUMN role TEXT DEFAULT 'user'")
                        conn.commit()
                except Exception as e:
                    logger.error(f"Error checking or modifying schema: {e}")
                finally:
                    conn.close()
        except Exception as e:
            logger.error(f"Error connecting to database for schema check: {e}")

    def get_user_auth(self, token) -> Optional[Dict]:
        """
        Get user authentication details using a token

        Args:
            token: Authentication token, can be a string or a dictionary with Bearer token

        Returns:
            Optional[Dict]: User auth data if authentication succeeds, None otherwise
        """
        try:
            # Handle different token formats
            if isinstance(token, dict):
                # If it's a dictionary, extract the token
                if 'token' in token:
                    clean_token = token['token']
                elif 'access_token' in token:
                    clean_token = token['access_token']
                else:
                    logger.error(
                        f"Could not extract token from dictionary: {token}")
                    return None
            else:
                # If it's a string (traditional format), process it
                clean_token = str(token).replace('Bearer ', '')

            headers = {
                'Authorization': f'Bearer {clean_token}',
                'Content-Type': 'application/json'
            }

            url = f"{self.OWI_API_BASE_URL}/auths/"

            response = requests.get(
                url,
                headers=headers
            )

            if response.status_code != 200:
                logger.error(
                    f"Auth request failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                logger.error(f"Request URL: {response.request.url}")
                logger.error(f"Request headers: {response.request.headers}")
                return None

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_user_auth: {e}")
            return None
