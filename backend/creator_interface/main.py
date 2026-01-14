from .chats_router import router as chats_router
from .analytics_router import router as analytics_router
from .prompt_templates_router import router as prompt_templates_router
from .evaluaitor_router import router as evaluaitor_router
from .learning_assistant_proxy import router as learning_assistant_proxy_router
from .organization_router import router as organization_router
from .setup_translations import setup_translations
from fastapi import APIRouter, Request, Form, Response, HTTPException, File, UploadFile, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pathlib import Path
import gettext
import os
from fastapi.staticfiles import StaticFiles
import httpx
from dotenv import load_dotenv
from typing import Optional, List
from .user_creator import UserCreatorManager
from .assistant_router import is_admin_user
from .organization_router import is_organization_admin
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from .assistant_router import router as assistant_router, get_creator_user_from_token
from .knowledges_router import router as knowledges_router
import json
import shutil
from pydantic import BaseModel, EmailStr
from fastapi import Body  # Import Body for request body definitions
from lamb.logging_config import get_logger
import time
import asyncio

# Set up logger for creator interface
logger = get_logger(__name__, component="API")

# Load environment variables
load_dotenv()

# Get environment variables
SIGNUP_ENABLED = os.getenv('SIGNUP_ENABLED', 'false').lower() == 'true'
SIGNUP_SECRET_KEY = os.getenv('SIGNUP_SECRET_KEY')
LAMB_NEWS_HOME = os.getenv('LAMB_NEWS_HOME', 'https://lamb-project.org/news/')
LAMB_NEWS_DEFAULT_LANG = os.getenv('LAMB_NEWS_DEFAULT_LANG', 'en')

# Cache configuration
NEWS_CACHE_DIR = Path(__file__).parent.parent / 'static' / 'cache' / 'news'
NEWS_CACHE_TIMEOUT = 5.0  # Timeout in seconds for fetching from origin
NEWS_CACHE_REFRESH_INTERVAL = 3600  # Refresh cache every hour (in seconds)
# Supported languages for news
NEWS_SUPPORTED_LANGUAGES = ['en', 'es', 'ca', 'eu']

# Note: LAMB_WEB_HOST, LAMB_BACKEND_HOST, and LAMB_BEARER_TOKEN are configured in config.py
# Other modules import from config module instead of reading these directly

# Initialize managers
db_manager = LambDatabaseManager()


# Import the setup_translations function

# Set up the router
router = APIRouter()

# Background task state
_news_refresh_task = None


async def start_news_cache_refresh_loop():
    """Start the background task loop to refresh news cache hourly."""
    global _news_refresh_task
    if _news_refresh_task is not None:
        logger.warning("News cache refresh loop already running")
        return

    async def refresh_loop():
        """Periodically refresh the news cache."""
        logger.info("News cache refresh loop started")
        # Initial cache population
        await refresh_news_cache_background()

        # Periodic refresh
        while True:
            try:
                await asyncio.sleep(NEWS_CACHE_REFRESH_INTERVAL)
                await refresh_news_cache_background()
            except asyncio.CancelledError:
                logger.info("News cache refresh loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in news cache refresh loop: {e}")
                # Continue despite errors

    _news_refresh_task = asyncio.create_task(refresh_loop())
    logger.info("News cache refresh task created")


async def stop_news_cache_refresh_loop():
    """Stop the background news cache refresh loop."""
    global _news_refresh_task
    if _news_refresh_task is not None:
        _news_refresh_task.cancel()
        try:
            await _news_refresh_task
        except asyncio.CancelledError:
            pass
        _news_refresh_task = None
        logger.info("News cache refresh loop stopped")

# Include the assistant router
router.include_router(assistant_router, prefix="/assistant")

# Include the knowledges router
router.include_router(knowledges_router, prefix="/knowledgebases")

# Include the organization management router
router.include_router(organization_router, prefix="/admin")

# Include the learning assistant proxy router
router.include_router(learning_assistant_proxy_router)

# Include the evaluaitor router
router.include_router(evaluaitor_router, prefix="/rubrics")

# Include the prompt templates router
router.include_router(prompt_templates_router, prefix="/prompt-templates")

# Include the analytics router
router.include_router(analytics_router, prefix="/analytics")

# Include the chats router for internal chat persistence
router.include_router(chats_router, prefix="/chats")

# REMOVED: assistant_sharing_router - functionality moved to services, accessed via /creator/lamb/* proxy


# Configuration Endpoints

@router.get("/config/ingestion")
async def get_ingestion_config():
    """Get ingestion configuration values.
    
    Returns configuration such as:
    - refresh_rate: How often (in seconds) the frontend should poll job status
    
    Returns:
        Dictionary with configuration values
    """
    return {
        "refresh_rate": int(os.getenv("INGESTION_JOB_REFRESH_RATE", "3"))
    }


# Initialize security
security = HTTPBearer()

# Set up translations
LOCALE_DIR = Path(__file__).parent / "locales"

# Create a fallback translation
fallback = gettext.NullTranslations()

# --- Pydantic Models for Request/Response Schemas ---


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginSuccessResponse(BaseModel):
    success: bool = True
    data: dict


class LoginErrorResponse(BaseModel):
    success: bool = False
    error: str


class SignupRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    secret_key: str


class SignupSuccessResponse(BaseModel):
    success: bool = True
    message: str


class SignupErrorResponse(BaseModel):
    success: bool = False
    error: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    user_config: dict


class ListUsersResponse(BaseModel):
    success: bool = True
    data: list[UserResponse]


class CreateUserAdminRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "user"
    user_type: str = "creator"  # 'creator' or 'end_user'
    organization_id: Optional[int] = None


class CreateUserAdminResponse(BaseModel):
    success: bool = True
    message: str


class UpdatePasswordAdminRequest(BaseModel):
    email: EmailStr
    new_password: str


class UpdatePasswordAdminResponse(BaseModel):
    success: bool = True
    message: str


class FileInfo(BaseModel):
    name: str
    path: str


class ListFilesResponse(BaseModel):
    files: list[FileInfo]


class UploadFileResponse(BaseModel):
    path: str
    name: str


class DeleteFileResponse(BaseModel):
    success: bool = True
    message: str


class LambHelperRequest(BaseModel):
    question: str


class LambHelperResponse(BaseModel):
    success: bool = True
    response: str


class EmailRoleUpdateRequest(BaseModel):
    email: EmailStr
    role: str


class EmailRoleUpdateResponse(BaseModel):
    success: bool = True
    message: str
    data: dict


class RoleUpdateRequest(BaseModel):
    role: str


class RoleUpdateResponse(BaseModel):
    success: bool = True
    message: str
    data: dict


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


class NewsResponse(BaseModel):
    success: bool = True
    content: str
    lang: str


# Assistant Sharing Models
class UpdateSharesRequest(BaseModel):
    """Request body for updating assistant shares"""
    user_emails: List[str]


class ShareUserResponse(BaseModel):
    """Response model for a shared user"""
    user_email: str
    user_name: str
    shared_at: int
    shared_by_name: str


class OrganizationUserResponse(BaseModel):
    """Response model for organization user in sharing UI"""
    email: str
    name: str
    user_type: str


class SharingPermissionResponse(BaseModel):
    """Response model for sharing permission check"""
    can_share: bool
    message: str = ""

# --- End Pydantic Models ---


# --- Cache Utility Functions ---

def get_cache_file_path(lang: str) -> Path:
    """Get the cache file path for a specific language."""
    return NEWS_CACHE_DIR / f"{lang}.md"


def get_cache_timestamp_path(lang: str) -> Path:
    """Get the cache timestamp file path for a specific language."""
    return NEWS_CACHE_DIR / f"{lang}.timestamp"


def read_from_cache(lang: str) -> Optional[str]:
    """Read cached news content for a language."""
    cache_file = get_cache_file_path(lang)
    try:
        if cache_file.exists():
            logger.info(f"Reading cached news for language '{lang}'")
            return cache_file.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Failed to read cache for language '{lang}': {e}")
    return None


def get_cache_age(lang: str) -> Optional[float]:
    """Get the age of cached content in seconds. Returns None if no cache exists."""
    timestamp_file = get_cache_timestamp_path(lang)
    try:
        if timestamp_file.exists():
            cache_time = float(timestamp_file.read_text(
                encoding='utf-8').strip())
            return time.time() - cache_time
    except Exception as e:
        logger.warning(
            f"Failed to read cache timestamp for language '{lang}': {e}")
    return None


def is_cache_fresh(lang: str) -> bool:
    """Check if cached content is fresh (less than refresh interval old)."""
    age = get_cache_age(lang)
    if age is None:
        return False
    return age < NEWS_CACHE_REFRESH_INTERVAL


def write_to_cache(lang: str, content: str) -> bool:
    """Write news content to cache for a language with timestamp."""
    try:
        NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Write content
        cache_file = get_cache_file_path(lang)
        cache_file.write_text(content, encoding='utf-8')

        # Write timestamp
        timestamp_file = get_cache_timestamp_path(lang)
        timestamp_file.write_text(str(time.time()), encoding='utf-8')

        logger.info(f"Cached news for language '{lang}'")
        return True
    except Exception as e:
        logger.error(f"Failed to write cache for language '{lang}': {e}")
        return False


async def fetch_and_cache_news(lang: str) -> Optional[str]:
    """Fetch news from origin and cache it. Returns content or None on failure."""
    try:
        news_url = f"{LAMB_NEWS_HOME.rstrip('/')}/news_{lang}.md"
        logger.info(f"Fetching news from origin: {news_url}")

        async with httpx.AsyncClient(timeout=NEWS_CACHE_TIMEOUT) as client:
            response = await client.get(news_url)

            if response.is_success and response.text and response.text.strip():
                content = response.text
                write_to_cache(lang, content)
                logger.info(
                    f"Successfully fetched and cached news for language '{lang}' ({len(content)} characters)")
                return content
            else:
                logger.warning(
                    f"Failed to fetch news for language '{lang}': HTTP {response.status_code}")
                return None

    except Exception as e:
        logger.warning(f"Error fetching news for language '{lang}': {e}")
        return None


async def refresh_news_cache_background():
    """Background task to refresh news cache for all supported languages."""
    logger.info("Starting background news cache refresh")
    for lang in NEWS_SUPPORTED_LANGUAGES:
        try:
            await fetch_and_cache_news(lang)
        except Exception as e:
            logger.error(f"Error refreshing cache for language '{lang}': {e}")
    logger.info("Completed background news cache refresh")


@router.post(
    "/login",
    tags=["Authentication"],
    summary="User Login",
    description="""Handles creator user login by verifying email and password against the OWI backend.

Example:
```bash
curl -X POST 'http://localhost:8000/creator/login' \\
-H 'Content-Type: application/x-www-form-urlencoded' \\
--data-urlencode 'email=user@example.com' \\
--data-urlencode 'password=yourpassword'
```

Example Success Response:
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOi...",
    "name": "Test User",
    "email": "user@example.com",
    "launch_url": "http://localhost:3000/?token=...",
    "user_id": "some-uuid",
    "role": "user",
    "user_type": "creator",
    "organization_role": "admin"
  }
}
```

Example Error Response:
```json
{
  "success": false,
  "error": "Invalid email or password"
}
```
    """,
    responses={
        200: {"model": LoginSuccessResponse, "description": "Login successful"},
        400: {"model": LoginErrorResponse, "description": "Login failed"},
    },
)
async def login(email: str = Form(...), password: str = Form(...)):
    """Handle login form submission"""
    user_creator = UserCreatorManager()
    result = await user_creator.verify_user(email, password)

    if result["success"]:
        return {
            "success": True,
            "data": {
                "token": result["data"]["token"],
                "name": result["data"]["name"],
                "email": result["data"]["email"],
                "launch_url": result["data"]["launch_url"],
                "user_id": result["data"]["user_id"],
                "role": result["data"]["role"],
                # Include user_type
                "user_type": result["data"].get("user_type", "creator"),
                # Include organization role
                "organization_role": result["data"].get("organization_role")
            }
        }
    else:
        return {
            "success": False,
            "error": result["error"]
        }


# Initialize security for token authentication
security = HTTPBearer()


@router.get(
    "/users",
    tags=["Admin - User Management"],
    summary="List All Creator Users (Admin Only)",
    description="""Retrieves a list of all creator users. Requires admin privileges.

Example Request (Admin):
```bash
curl -X GET 'http://localhost:8000/creator/users' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "email": "admin@example.com",
      "name": "Admin User",  
      "role": "admin",
      "user_config": {},
      "organization": {
        "name": "LAMB System Organization",
        "slug": "lamb",  
        "is_system": true
      },
      "organization_role": "admin"
    },
    {
      "id": 2,
      "email": "creator@example.com",
      "name": "Creator User",
      "role": "user",
      "user_config": {},
      "organization": {
        "name": "Engineering Department",
        "slug": "engineering",
        "is_system": false
      },
      "organization_role": "member"
    }
  ]
}
```

Example Forbidden Response:
```json
{
  "success": false,
  "error": "Access denied. Admin privileges required."
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"model": ListUsersResponse, "description": "Successfully retrieved users."},
    },
)
async def list_users(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """List all creator users (admin only) as JSON"""
    # Extract the authorization header
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # User is admin, proceed with fetching the list of users
    try:
        # Use the database_manager directly to get users with organization info
        from lamb.database_manager import LambDatabaseManager
        db_manager = LambDatabaseManager()

        users = db_manager.get_creator_users()

        if users is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Failed to retrieve users"
                }
            )

        # Get OWI roles and enabled status for each user
        user_creator = UserCreatorManager()
        owi_manager = OwiUserManager()
        users_with_roles = []

        for user in users:
            # Get OWI role information for the user using direct OWI bridge call
            try:
                owi_user = owi_manager.get_user_by_email(user['email'])
                owi_role = owi_user.get('role', 'user') if owi_user else 'user'
            except Exception as e:
                logger.warning(
                    f"Could not get OWI role for user {user['email']}: {e}")
                owi_role = 'user'  # Default on error

            # Get enabled status from user data (LAMB database stores this)
            enabled_status = user.get('enabled', True)

            user_data = {
                "id": user.get("id"),
                "email": user.get("email"),
                "name": user.get("name"),
                "role": owi_role,
                "enabled": enabled_status,
                "user_type": user.get("user_type", "creator"),
                "user_config": user.get("user_config", {}),
                "organization": user.get("organization"),
                "organization_role": user.get("organization_role")
            }
            users_with_roles.append(user_data)

        return {
            "success": True,
            "data": users_with_roles
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error retrieving users: {str(e)}"
            }
        )


@router.post(
    "/signup",
    tags=["Authentication"],
    summary="User Signup",
    description="""Handles new user signup if enabled via environment variables and requires a secret key.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/signup' \\
-H 'Content-Type: application/x-www-form-urlencoded' \\
--data-urlencode 'email=newuser@example.com' \\
--data-urlencode 'name=New User' \\
--data-urlencode 'password=newpassword123' \\
--data-urlencode 'secret_key=thesecretkey'
```

Example Success Response:
```json
{
  "success": true,
  "message": "Account created successfully"
}
```

Example Error Response (Wrong Key):
```json
{
  "success": false,
  "error": "Invalid secret key"
}
```
    """,
    responses={
        200: {"model": SignupSuccessResponse, "description": "Signup successful"},
        400: {"model": SignupErrorResponse, "description": "Signup failed (e.g., disabled, wrong key, user exists)"},
    },
)
async def signup(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    secret_key: str = Form(...)
):
    """Handle signup form submission with organization-specific support"""
    try:
        # Step 1: Try to find organization with the provided signup key
        target_org = db_manager.get_organization_by_signup_key(secret_key)

        if target_org:
            # Organization-specific signup found
            logger.info(
                f"Creating user in organization '{target_org['slug']}' using signup key")

            user_creator = UserCreatorManager()
            result = await user_creator.create_user(
                email=email,
                name=name,
                password=password,
                organization_id=target_org['id']
            )

            if result["success"]:
                # Assign member role to user in the organization
                if db_manager.assign_organization_role(target_org['id'], result.get('user_id'), "member"):
                    logger.info(
                        f"Assigned member role to user {email} in organization {target_org['slug']}")
                else:
                    logger.warning(
                        f"Failed to assign role to user {email} in organization {target_org['slug']}")

                return {
                    "success": True,
                    "message": f"Account created successfully in {target_org['name']}"
                }
            else:
                return {
                    "success": False,
                    "error": result["error"]
                }

        # Step 2: Fallback to system organization signup
        elif SIGNUP_ENABLED and secret_key == SIGNUP_SECRET_KEY:
            # Legacy system signup
            logger.info(
                "Creating user in system organization using legacy signup key")

            # Get system organization
            system_org = db_manager.get_organization_by_slug("lamb")
            if not system_org:
                return {
                    "success": False,
                    "error": "System organization not found"
                }

            user_creator = UserCreatorManager()
            result = await user_creator.create_user(
                email=email,
                name=name,
                password=password,
                organization_id=system_org['id']
            )

            if result["success"]:
                # Assign member role to user in the system organization
                if db_manager.assign_organization_role(system_org['id'], result.get('user_id'), "member"):
                    logger.info(
                        f"Assigned member role to user {email} in system organization")
                else:
                    logger.warning(
                        f"Failed to assign role to user {email} in system organization")

                return {
                    "success": True,
                    "message": "Account created successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result["error"]
                }

        # Step 3: No valid signup method found
        else:
            if not SIGNUP_ENABLED:
                return {
                    "success": False,
                    "error": "Signup is currently disabled. Please contact your administrator or use a valid organization signup key."
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid signup key. Please check your signup key or contact your organization administrator."
                }

    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return {
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }

# Add these constants after the other constants
ALLOWED_EXTENSIONS = {'.txt', '.json', '.md'}
STATIC_DIR = Path(__file__).parent.parent / 'static' / 'public'

# Add these new routes after the existing routes


@router.post(
    "/admin/users/create",
    tags=["Admin - User Management"],
    summary="Create New User (Admin Only)",
    description="""Allows an admin user to create a new creator user with a specified role (default 'user').

Example Request (Admin):
```bash
curl -X POST 'http://localhost:8000/creator/admin/users/create' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/x-www-form-urlencoded' \\
--data-urlencode 'email=anotheruser@example.com' \\
--data-urlencode 'name=Another User' \\
--data-urlencode 'password=securepass' \\
--data-urlencode 'role=user'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User anotheruser@example.com created successfully"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"model": CreateUserAdminResponse, "description": "User created successfully."},
    },
)
async def create_user_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    organization_id: int = Form(None),
    user_type: str = Form("creator")  # 'creator' or 'end_user'
):
    """Create a new user (admin only)"""
    # Extract the authorization header
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # Ensure admin users have user_type='creator' (admins are always creators)
    if role == "admin":
        user_type = "creator"

    # User is admin, proceed with creating a new user
    try:
        user_creator = UserCreatorManager()
        # Pass the role, organization_id, and user_type parameters to create_user method
        result = await user_creator.create_user(email, name, password, role, organization_id, user_type)

        if result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"User {email} created successfully"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result["error"]
                }
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Server error"
            }
        )


@router.post(
    "/admin/users/update-password",
    tags=["Admin - User Management"],
    summary="Update User Password (Admin Only)",
    description="""Allows an admin user to update the password for any creator user, identified by email.

Example Request (Admin):
```bash
curl -X POST 'http://localhost:8000/creator/admin/users/update-password' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/x-www-form-urlencoded' \\
--data-urlencode 'email=user@example.com' \\
--data-urlencode 'new_password=newStrongPassword123'
```

Example Success Response:
```json
{
  "success": true,
  "message": "Password for user user@example.com updated successfully"
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"model": UpdatePasswordAdminResponse, "description": "Password updated successfully."},
    },
)
async def update_user_password_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    email: str = Form(...),
    new_password: str = Form(...)
):
    """Update a user's password (admin only)"""
    # Extract the authorization header
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # User is admin, proceed with updating the password
    try:
        user_creator = UserCreatorManager()
        result = await user_creator.update_user_password(email, new_password)

        if result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"Password for user {email} updated successfully"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result["error"]
                }
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Server error"
            }
        )


@router.put(
    "/admin/users/{user_id}/disable",
    tags=["Admin - User Management"],
    summary="Disable User Account (Admin Only)",
    description="""Disables a user account preventing login. The user's published assistants and shared resources remain available.

Example Request (Admin):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/users/123/disable' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User user@example.com has been disabled"
}
```
    """,
    dependencies=[Depends(security)],
)
async def disable_user(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Disable a user account (admin only)"""
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # Get current user to prevent self-disable
    creator_user = get_creator_user_from_token(auth_header)
    if creator_user and creator_user['id'] == user_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Cannot disable your own account"
            }
        )

    # Check if user exists
    db_manager = LambDatabaseManager()
    target_user = db_manager.get_creator_user_by_id(user_id)

    if not target_user:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "User not found"
            }
        )

    # Disable user
    success = db_manager.disable_user(user_id)

    if not success:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Unable to disable user (may already be disabled)"
            }
        )

    logger.info(f"Admin {creator_user['email']} disabled user {user_id}")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": f"User {target_user['user_email']} has been disabled"
        }
    )


@router.put(
    "/admin/users/{user_id}/enable",
    tags=["Admin - User Management"],
    summary="Enable User Account (Admin Only)",
    description="""Enables a previously disabled user account allowing them to login again.

Example Request (Admin):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/users/123/enable' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User user@example.com has been enabled"
}
```
    """,
    dependencies=[Depends(security)],
)
async def enable_user(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Enable a user account (admin only)"""
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # Check if user exists
    db_manager = LambDatabaseManager()
    target_user = db_manager.get_creator_user_by_id(user_id)

    if not target_user:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "User not found"
            }
        )

    # Enable user
    success = db_manager.enable_user(user_id)

    if not success:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Unable to enable user (may already be enabled)"
            }
        )

    creator_user = get_creator_user_from_token(auth_header)
    logger.info(f"Admin {creator_user['email']} enabled user {user_id}")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": f"User {target_user['user_email']} has been enabled"
        }
    )


@router.post(
    "/admin/users/disable-bulk",
    tags=["Admin - User Management"],
    summary="Disable Multiple Users (Admin Only)",
    description="""Disable multiple user accounts in a single operation.

Example Request (Admin):
```bash
curl -X POST 'http://localhost:8000/creator/admin/users/disable-bulk' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{"user_ids": [1, 2, 3]}'
```

Example Success Response:
```json
{
  "success": true,
  "disabled": 3,
  "failed": 0,
  "already_disabled": 0,
  "details": {
    "success": [1, 2, 3],
    "failed": [],
    "already_disabled": []
  }
}
```
    """,
    dependencies=[Depends(security)],
)
async def disable_users_bulk(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Disable multiple users (admin only)"""
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # Get user IDs from request body
    body = await request.json()
    user_ids = body.get('user_ids', [])

    if not user_ids:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "No users specified"
            }
        )

    # Remove current user from list to prevent self-disable
    creator_user = get_creator_user_from_token(auth_header)
    if creator_user and creator_user['id'] in user_ids:
        user_ids.remove(creator_user['id'])
        logger.warning(
            f"Removed self ({creator_user['id']}) from bulk disable list")

    if not user_ids:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "No valid users to disable"
            }
        )

    # Bulk disable
    db_manager = LambDatabaseManager()
    results = db_manager.disable_users_bulk(user_ids)

    logger.info(
        f"Admin {creator_user['email']} bulk disabled users: "
        f"{len(results['success'])} successful, {len(results['failed'])} failed"
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "disabled": len(results["success"]),
            "failed": len(results["failed"]),
            "already_disabled": len(results.get("already_disabled", [])),
            "details": results
        }
    )


@router.post(
    "/admin/users/enable-bulk",
    tags=["Admin - User Management"],
    summary="Enable Multiple Users (Admin Only)",
    description="""Enable multiple user accounts in a single operation.

Example Request (Admin):
```bash
curl -X POST 'http://localhost:8000/creator/admin/users/enable-bulk' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{"user_ids": [1, 2, 3]}'
```

Example Success Response:
```json
{
  "success": true,
  "enabled": 3,
  "failed": 0,
  "already_enabled": 0,
  "details": {
    "success": [1, 2, 3],
    "failed": [],
    "already_enabled": []
  }
}
```
    """,
    dependencies=[Depends(security)],
)
async def enable_users_bulk(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Enable multiple users (admin only)"""
    auth_header = f"Bearer {credentials.credentials}"

    # Check if the user has admin privileges
    if not is_admin_user(auth_header):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Access denied. Admin privileges required."
            }
        )

    # Get user IDs from request body
    body = await request.json()
    user_ids = body.get('user_ids', [])

    if not user_ids:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "No users specified"
            }
        )

    # Bulk enable
    db_manager = LambDatabaseManager()
    results = db_manager.enable_users_bulk(user_ids)

    creator_user = get_creator_user_from_token(auth_header)
    logger.info(
        f"Admin {creator_user['email']} bulk enabled users: "
        f"{len(results['success'])} successful, {len(results['failed'])} failed"
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "enabled": len(results["success"]),
            "failed": len(results["failed"]),
            "already_enabled": len(results.get("already_enabled", [])),
            "details": results
        }
    )


@router.get(
    "/files/list",
    tags=["File Management"],
    summary="List User Files",
    description="""Lists files (txt, json, md) in the authenticated user's dedicated directory.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/files/list' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
[
  {
    "name": "document1.txt",
    "path": "1/document1.txt"
  },
  {
    "name": "notes.md",
    "path": "1/notes.md"
  }
]
```
    """,
    dependencies=[Depends(security)],
    response_model=list[FileInfo],
    responses={
    },
)
async def list_user_files(request: Request):
    """List files in user's directory"""
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        # Create user directory path
        user_dir = STATIC_DIR / str(creator_user['id'])

        # Create directory if it doesn't exist
        user_dir.mkdir(parents=True, exist_ok=True)

        # List files in user directory
        files = []
        for file_path in user_dir.glob('*'):
            if file_path.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append({
                    'name': file_path.name,
                    'path': str(file_path.relative_to(STATIC_DIR))
                })

        return files

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/files/upload",
    tags=["File Management"],
    summary="Upload File",
    description="""Uploads a file (txt, json, md) to the authenticated user's dedicated directory.

Example Request:
```bash
curl -X POST 'http://localhost:8000/creator/files/upload' \\
-H 'Authorization: Bearer <user_token>' \\
-F 'file=@/path/to/your/local/file.txt'
```

Example Success Response:
```json
{
  "path": "1/file.txt",
  "name": "file.txt"
}
```
    """,
    dependencies=[Depends(security)],
    response_model=UploadFileResponse,
    responses={
    },
)
async def upload_file(
    request: Request,
    file: UploadFile = File(...)
):
    """Upload a file to user's directory"""
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        # Validate file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Create user directory path
        user_dir = STATIC_DIR / str(creator_user['id'])
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create file path and save file
        file_path = user_dir / file.filename

        # Save the uploaded file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Return the relative path for the file
        relative_path = str(file_path.relative_to(STATIC_DIR))

        return {
            "path": relative_path,
            "name": file.filename
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/files/delete/{path:path}",
    tags=["File Management"],
    summary="Delete File",
    description="""Deletes a specific file belonging to the authenticated user.

Example Request:
```bash
# Assuming the file '1/document1.txt' exists and belongs to the user
curl -X DELETE 'http://localhost:8000/creator/files/delete/1/document1.txt' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "success": true,
  "message": "File deleted successfully"
}
```
    """,
    dependencies=[Depends(security)],
    response_model=DeleteFileResponse,
    responses={
    },
)
async def delete_file(request: Request, path: str):
    """Delete a file from the user's directory"""
    try:
        logger.debug(f"Received request to delete file: {path}")

        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error(
                "Invalid authentication or user not found in creator database")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        # Create user directory path
        user_dir = STATIC_DIR / str(creator_user['id'])

        # Full file path
        file_path = user_dir / path

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        # Delete the file
        file_path.unlink()

        return {"success": True, "message": "File deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting file: {str(e)}")


# Update the QuestionRequest model


class QuestionRequest(BaseModel):
    question: str


# Pydantic model for role update by email
class EmailRoleUpdate(BaseModel):
    email: EmailStr
    role: str


@router.put(
    "/admin/users/update-role-by-email",
    tags=["Admin - User Management"],
    summary="Update User Role by Email (Admin Only)",
    description="""Allows an admin user to update the role ('admin' or 'user') of any user, identified by their email address. This directly modifies the OWI database record.

Example Request (Promote to Admin):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/users/update-role-by-email' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{"email": "user@example.com", "role": "admin"}'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User role updated to admin",
  "data": {
    "email": "user@example.com",
    "role": "admin"
  }
}
```
    """,
    dependencies=[Depends(security)],
    response_model=EmailRoleUpdateResponse,
    responses={
    },
)
async def update_user_role_by_email(
    role_update: EmailRoleUpdate,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a user's role (admin or user) directly using their email address.
    This endpoint provides a more direct way to update roles in the OWI system."""
    try:
        # Get token from authorization header and retrieve creator user
        token = credentials.credentials
        creator_user = get_creator_user_from_token(token)

        if not creator_user:
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Invalid or expired token."
            )

        # Check if user is an admin
        is_admin = is_admin_user(creator_user)

        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Administrator privileges required"
            )

        # Validation check for role
        new_role = role_update.role
        if new_role not in ["admin", "user"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {new_role}. Must be 'admin' or 'user'"
            )

        # Import the OwiUserManager class and update the role directly
        from lamb.owi_bridge.owi_users import OwiUserManager
        user_manager = OwiUserManager()
        result = user_manager.update_user_role_by_email(
            role_update.email, new_role)

        if result:
            return {
                "success": True,
                "message": f"User role updated to {new_role}",
                "data": {"email": role_update.email, "role": new_role}
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update user role in database. User may not exist."
            )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error importing OwiUserManager: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.put(
    "/admin/users/{user_id}/update-role",
    tags=["Admin - User Management"],
    summary="Update User Role by ID (Admin Only)",
    description="""Allows an admin user to update the role ('admin' or 'user') of any user, identified by their LAMB creator user ID. **Note:** The primary admin (ID 1) role cannot be changed. This involves looking up the user's email and then updating the role in OWI.

Example Request (Update user ID 2 to Admin):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/users/2/update-role' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{"role": "admin"}'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User role updated to admin",
  "data": {
    "user_id": "2",
    "role": "admin"
  }
}
```
    """,
    dependencies=[Depends(security)],
    response_model=RoleUpdateResponse,
    responses={
    },
)
async def update_user_role_admin(
    user_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a user's role (admin or user).
    Note: User ID 1 cannot have its role changed from admin."""
    try:
        # Enhanced logging for debugging
        logger.info(
            f"[ROLE_UPDATE] Attempting to update role for user ID {user_id}")

        # Check if the requester is an admin
        token = credentials.credentials

        auth_header = f"Bearer {token}"

        creator_user = get_creator_user_from_token(auth_header)

        if not creator_user:
            raise HTTPException(
                status_code=403,
                detail="Authentication failed. Invalid or expired token."
            )

        # Check if user is an admin
        is_admin = is_admin_user(creator_user)

        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Administrator privileges required"
            )

        # Get the request body to extract the new role
        data = await request.json()
        new_role = data.get('role')

        if not new_role:
            raise HTTPException(
                status_code=400,
                detail="Role is required in request body"
            )

        if new_role not in ['admin', 'user']:
            raise HTTPException(
                status_code=400,
                detail="Role must be either 'admin' or 'user'"
            )

        # Call the OWI bridge API to update the user's role
        user_manager = UserCreatorManager()

        # We're no longer using httpx since we're calling the database directly
        # but keeping the async client context for backward compatibility
        async with httpx.AsyncClient() as client:
            # Direct database update approach

            # Special case - prevent changing user ID 1 (admin)
            if str(user_id) == "1":
                raise HTTPException(
                    status_code=403,
                    detail="Cannot change role for primary admin user (ID 1)"
                )

            # Validation check for role
            if new_role not in ["admin", "user"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid role: {new_role}. Must be 'admin' or 'user'"
                )

            # First, we need to get the user's email from the creator user database
            # Using the database manager directly instead of importing a non-existent function
            from lamb.database_manager import LambDatabaseManager

            # Get the user from the creator database using their creator user ID
            db_manager = LambDatabaseManager()

            # Query the database directly for the user with this ID
            try:
                conn = db_manager.get_connection()
                if not conn:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to connect to database"
                    )

                cursor = conn.cursor()
                # Get the table prefix from the database manager
                table_prefix = db_manager.table_prefix

                # Use the correct table name with proper prefix and capitalization
                table_name = f"{table_prefix}Creator_users"
                query = f"SELECT id, user_email, user_name, user_config FROM {table_name} WHERE id = ?"

                cursor.execute(query, (user_id,))
                user_record = cursor.fetchone()

                if not user_record:
                    conn.close()
                    raise HTTPException(
                        status_code=404,
                        detail=f"Creator user not found with ID: {user_id}"
                    )

                # Create a dictionary with the known column names since we used specific fields in SELECT
                creator_user_info = {
                    'id': user_record[0],
                    'email': user_record[1],
                    'name': user_record[2],
                    'user_config': json.loads(user_record[3]) if user_record[3] else {}
                }

                conn.close()
            except Exception as db_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error: {str(db_error)}"
                )

            if not creator_user_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Creator user not found with ID: {user_id}"
                )

            # Get the email from the creator user
            user_email = creator_user_info.get('email')

            if not user_email:
                raise HTTPException(
                    status_code=400,
                    detail="Creator user has no email address"
                )

            # Import directly
            try:
                # Suppress any potential passlib/bcrypt warnings
                import warnings
                warnings.filterwarnings(
                    "ignore", message=".*error reading bcrypt version.*")

                # Import the OwiUserManager class directly
                from lamb.owi_bridge.owi_users import OwiUserManager

                # Create an instance
                user_manager = OwiUserManager()

                # Update the user's role directly by email
                # This eliminates the need to find the OWI user ID, simplifying the process
                # and reducing potential points of failure
                result = user_manager.update_user_role_by_email(
                    user_email, new_role)

                if result:
                    return {
                        "success": True,
                        "message": f"User role updated to {new_role}",
                        "data": {"user_id": user_id, "role": new_role}
                    }
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to update user role in database. User may not exist."
                    )
            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error importing OwiUserManager: {str(e)}"
                )
            except Exception as db_error:
                import traceback
                logger.error(
                    f"[ROLE_UPDATE] Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while updating user role: {str(db_error)}"
                )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"[ROLE_UPDATE] Error in update_user_role_admin: {str(e)}")
        import traceback
        logger.error(f"[ROLE_UPDATE] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.put(
    "/admin/users/{user_id}/status",
    tags=["Admin - User Management"],
    summary="Enable/Disable User (Admin Only)",
    description="""Allows an admin user to enable or disable any user by their LAMB creator user ID.
    Disabled users will not be able to log in to the system.

Example Request (Disable user ID 2):
```bash
curl -X PUT 'http://localhost:8000/creator/admin/users/2/status' \\
-H 'Authorization: Bearer <admin_token>' \\
-H 'Content-Type: application/json' \\
-d '{"enabled": false}'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User has been disabled",
  "data": {
    "user_id": "2",
    "email": "user@example.com",
    "enabled": false
  }
}
```
    """,
    dependencies=[Depends(security)]
)
async def update_user_status_admin(
    user_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Enable or disable a user (admin only)"""
    try:
        # Check if the requester is an admin
        auth_header = f"Bearer {credentials.credentials}"

        if not is_admin_user(auth_header):
            raise HTTPException(
                status_code=403,
                detail="Administrator privileges required"
            )

        # Get the request body to extract the enabled status
        data = await request.json()
        enabled = data.get('enabled')

        if enabled is None:
            raise HTTPException(
                status_code=400,
                detail="'enabled' field is required in request body (true/false)"
            )

        if not isinstance(enabled, bool):
            raise HTTPException(
                status_code=400,
                detail="'enabled' field must be a boolean (true/false)"
            )

        # Get the user from LAMB database to get their email
        db_manager = LambDatabaseManager()
        user = db_manager.get_creator_user_by_id(int(user_id))

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found"
            )

        # Prevent users from disabling themselves
        current_user = get_creator_user_from_token(auth_header)
        if current_user and current_user.get('email') == user.get('user_email') and not enabled:
            raise HTTPException(
                status_code=403,
                detail="You cannot disable your own account. Please ask another administrator to disable your account if needed."
            )

        # Update user status in OWI auth system
        owi_manager = OwiUserManager()
        if not owi_manager.update_user_status(user.get('user_email'), enabled):
            raise HTTPException(
                status_code=500,
                detail="Failed to update user status"
            )

        status_text = "enabled" if enabled else "disabled"
        logger.info(
            f"Admin updated user {user.get('user_email')} (ID: {user_id}) status to {status_text}")

        return {
            "success": True,
            "message": f"User has been {status_text}",
            "data": {
                "user_id": user_id,
                "email": user.get('user_email'),
                "enabled": enabled
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.delete(
    "/admin/users/{user_id}",
    tags=["User Management"],
    summary="Delete Disabled User",
    description="""Delete a user account (admin only). For safety, the user must:
1. Be disabled (enabled=false) before deletion
2. Have no assistants or knowledge bases

This prevents accidental deletion and ensures resources are properly handled.

Example Request (Delete disabled user ID 2):
```bash
curl -X DELETE 'http://localhost:8000/creator/admin/users/2' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "success": true,
  "message": "User deleted successfully",
  "data": {
    "user_id": "2"
  }
}
```

Example Error (User not disabled):
```json
{
  "detail": "User must be disabled before deletion"
}
```

Example Error (User has dependencies):
```json
{
  "detail": "User has dependencies: 3 assistant(s), 2 knowledge base(s). Please delete or reassign these resources first."
}
```
    """,
    dependencies=[Depends(security)]
)
async def delete_user_admin(
    user_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a disabled user with no dependencies (admin only)"""
    try:
        # Check if the requester is an admin
        auth_header = f"Bearer {credentials.credentials}"

        if not is_admin_user(auth_header):
            raise HTTPException(
                status_code=403,
                detail="Administrator privileges required"
            )

        # Prevent users from deleting themselves
        current_user = get_creator_user_from_token(auth_header)
        if current_user and str(current_user.get('id')) == user_id:
            raise HTTPException(
                status_code=403,
                detail="You cannot delete your own account"
            )

        # Attempt safe deletion
        db_manager = LambDatabaseManager()
        success, error_message = db_manager.delete_user_safe(int(user_id))

        if not success:
            raise HTTPException(
                status_code=400,
                detail=error_message or "Failed to delete user"
            )

        logger.info(f"Admin successfully deleted user ID: {user_id}")

        return {
            "success": True,
            "message": "User deleted successfully",
            "data": {
                "user_id": user_id
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get(
    "/admin/users/{user_id}/dependencies",
    tags=["User Management"],
    summary="Check User Dependencies",
    description="""Check if a user has any dependencies (assistants or knowledge bases).
Useful for determining if a user can be safely deleted.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/admin/users/2/dependencies' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Response (User has dependencies):
```json
{
  "has_dependencies": true,
  "assistant_count": 3,
  "kb_count": 2,
  "assistants": [
    {"id": 1, "name": "Math Tutor"},
    {"id": 2, "name": "Writing Assistant"},
    {"id": 3, "name": "Science Helper"}
  ],
  "kbs": [
    {"id": "uuid-123", "name": "Course Materials"},
    {"id": "uuid-456", "name": "Research Papers"}
  ]
}
```

Example Response (User has no dependencies):
```json
{
  "has_dependencies": false,
  "assistant_count": 0,
  "kb_count": 0,
  "assistants": [],
  "kbs": []
}
```
    """,
    dependencies=[Depends(security)]
)
async def check_user_dependencies_admin(
    user_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Check if a user has any dependencies (admin only)"""
    try:
        # Check if the requester is an admin
        auth_header = f"Bearer {credentials.credentials}"

        if not is_admin_user(auth_header):
            raise HTTPException(
                status_code=403,
                detail="Administrator privileges required"
            )

        # Check dependencies
        db_manager = LambDatabaseManager()
        dependencies = db_manager.check_user_dependencies(int(user_id))

        return dependencies

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking user dependencies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get(
    "/user/current",
    tags=["User Management"],
    summary="Get Current User Info",
    description="""Retrieves basic information (ID, email, name) for the currently authenticated user based on the provided token.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/user/current' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Test User"
}
```
    """,
    dependencies=[Depends(security)],
    response_model=CurrentUserResponse,
    responses={
    },
)
async def get_current_user(request: Request):
    """Get current user information from authentication token"""
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        # Return user information
        return {
            "id": creator_user["id"],
            "email": creator_user["email"],
            "name": creator_user["name"]
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/news/{lang}",
    tags=["News"],
    summary="Get News Content by Language",
    description="""Fetches news content from cache or remote markdown file based on the specified language.

Supported languages: en, es, ca, eu (and other language codes)

The content is fetched from: LAMB_NEWS_HOME/news_{lang}.md
Cache is refreshed automatically every hour in the background.

Example Request:
```bash
curl -X GET 'http://localhost:8000/creator/news/es' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "success": true,
  "content": "# LAMB News\\n\\nWelcome to LAMB...",
  "lang": "es"
}
```
    """,
    dependencies=[Depends(security)],
    response_model=NewsResponse,
    responses={
        200: {"model": NewsResponse, "description": "News content retrieved successfully"},
        404: {"model": ErrorResponse, "description": "News file not found for specified language"},
        500: {"model": ErrorResponse, "description": "Server error while fetching news"},
    },
)
async def get_news(lang: str, background_tasks: BackgroundTasks):
    """Get news content for a specific language with cache-first strategy and background refresh"""
    try:
        # Validate language parameter (basic validation)
        if not lang or not lang.isalnum() or len(lang) > 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid language code. Must be alphanumeric and max 10 characters."
            )

        # Check if we have fresh cached content
        if is_cache_fresh(lang):
            cached_content = read_from_cache(lang)
            if cached_content is not None:
                logger.info(
                    f"Serving fresh cached news for language '{lang}' (age: {get_cache_age(lang):.0f}s)")
                return {
                    "success": True,
                    "content": cached_content,
                    "lang": lang
                }

        # Cache is stale or doesn't exist - try to fetch from origin immediately
        logger.info(
            f"Cache is stale or missing for language '{lang}', fetching from origin")
        fresh_content = await fetch_and_cache_news(lang)

        if fresh_content is not None:
            # Successfully fetched fresh content
            return {
                "success": True,
                "content": fresh_content,
                "lang": lang
            }

        # Failed to fetch from origin, try to use stale cache
        cached_content = read_from_cache(lang)
        if cached_content is not None:
            cache_age = get_cache_age(lang)
            logger.info(
                f"Using stale cached news for language '{lang}' (age: {cache_age:.0f}s)")
            return {
                "success": True,
                "content": cached_content,
                "lang": lang
            }

        # No cache and origin failed
        raise HTTPException(
            status_code=404,
            detail=f"News content not found for language '{lang}' and no cached version available."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error fetching news for language '{lang}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching news: {str(e)}"
        )


@router.get(
    "/lamb/assistant-sharing/shared-with-me",
    tags=["Assistant Sharing"],
    summary="Get Assistants Shared With Me",
    description="""Returns a list of assistants that have been shared with the authenticated user.
    
Example Request:
```bash
curl -X GET 'http://localhost:9099/creator/lamb/assistant-sharing/shared-with-me' \\
-H 'Authorization: Bearer <user_token>'
```

Example Success Response:
```json
{
  "assistants": [
    {
      "id": 123,
      "name": "1_Math Helper",
      "description": "Assists with math problems",
      "owner": "teacher@example.com",
      "shared_at": "2025-12-23T10:00:00Z",
      "shared_by_name": "John Doe",
      "metadata": {...}
    }
  ]
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        401: {"description": "Invalid authentication"},
        500: {"description": "Internal server error"}
    }
)
async def get_shared_assistants(request: Request):
    """
    Get list of assistants shared with the current user.
    """
    try:
        # Get creator user from auth header
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Unauthorized attempt to get shared assistants")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        user_id = creator_user.get('id')
        user_email = creator_user.get('email')
        logger.info(
            f"User {user_email} (ID: {user_id}) requesting shared assistants")

        # Use the assistant sharing service
        from lamb.services.assistant_sharing_service import AssistantSharingService
        sharing_service = AssistantSharingService()

        # Get shared assistants
        shared_assistants = sharing_service.get_shared_assistants(user_id)

        logger.info(
            f"Found {len(shared_assistants)} assistants shared with user {user_email}")

        return {
            "assistants": shared_assistants
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting shared assistants: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/lamb/assistant-sharing/check-permission",
    tags=["Assistant Sharing"],
    summary="Check Sharing Permission",
    description="""Check if the current user has permission to share assistants.

Sharing requires BOTH:
1. Organization has sharing_enabled = true (org-level setting)
2. User has can_share = true in their config (user-level setting, defaults to true)

Example Request:
```bash
curl -X GET 'http://localhost:9099/creator/lamb/assistant-sharing/check-permission' \\
-H 'Authorization: Bearer <user_token>'
```

Example Response (can share):
```json
{
  "can_share": true,
  "message": "User has sharing permission"
}
```

Example Response (cannot share):
```json
{
  "can_share": false,
  "message": "Sharing is disabled for your organization"
}
```
    """,
    dependencies=[Depends(security)],
    response_model=SharingPermissionResponse,
    responses={
        401: {"description": "Invalid authentication"},
        500: {"description": "Internal server error"}
    }
)
async def check_sharing_permission_endpoint(request: Request):
    """Check if sharing is enabled for current user's organization"""
    try:
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Unauthorized attempt to check sharing permission")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        user_id = creator_user.get('id')
        user_email = creator_user.get('email')
        logger.info(f"User {user_email} checking sharing permission")

        from lamb.services.assistant_sharing_service import AssistantSharingService
        sharing_service = AssistantSharingService()

        can_share = sharing_service.check_sharing_permission(user_id)

        message = "User has sharing permission" if can_share else "Sharing is disabled for your organization or user"
        logger.info(f"User {user_email} sharing permission: {can_share}")

        return SharingPermissionResponse(can_share=can_share, message=message)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error checking sharing permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/lamb/assistant-sharing/organization-users",
    tags=["Assistant Sharing"],
    summary="Get Organization Users for Sharing",
    description="""Get list of users in the current user's organization for the sharing UI.
Returns users excluding the current user, sorted alphabetically by name.

Example Request:
```bash
curl -X GET 'http://localhost:9099/creator/lamb/assistant-sharing/organization-users' \\
-H 'Authorization: Bearer <user_token>'
```

Example Response:
```json
[
  {"email": "jane@example.com", "name": "Jane Smith", "user_type": "creator"},
  {"email": "bob@example.com", "name": "Bob Wilson", "user_type": "creator"}
]
```
    """,
    dependencies=[Depends(security)],
    response_model=List[OrganizationUserResponse],
    responses={
        401: {"description": "Invalid authentication"},
        403: {"description": "Sharing not enabled for organization"},
        500: {"description": "Internal server error"}
    }
)
async def get_organization_users_endpoint(request: Request):
    """Get list of users in current user's organization for sharing UI"""
    try:
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Unauthorized attempt to get organization users")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        user_id = creator_user.get('id')
        user_email = creator_user.get('email')
        logger.info(f"User {user_email} requesting organization users for sharing")

        from lamb.services.assistant_sharing_service import AssistantSharingService
        sharing_service = AssistantSharingService()

        # Check if sharing is enabled
        if not sharing_service.check_sharing_permission(user_id):
            raise HTTPException(
                status_code=403,
                detail="Sharing is not enabled for your organization"
            )

        users = sharing_service.get_organization_users(user_id)
        logger.info(f"Found {len(users)} organization users for sharing UI")

        return users

    except HTTPException as he:
        raise he
    except ValueError as e:
        logger.error(f"Error getting organization users: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting organization users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/lamb/assistant-sharing/shares/{assistant_id}",
    tags=["Assistant Sharing"],
    summary="Get Assistant Shares",
    description="""Get list of users an assistant is shared with.
Only the assistant owner or organization admin can view this information.

Example Request:
```bash
curl -X GET 'http://localhost:9099/creator/lamb/assistant-sharing/shares/123' \\
-H 'Authorization: Bearer <user_token>'
```

Example Response:
```json
[
  {
    "user_email": "jane@example.com",
    "user_name": "Jane Smith",
    "shared_at": 1730908800,
    "shared_by_name": "John Doe"
  }
]
```
    """,
    dependencies=[Depends(security)],
    response_model=List[ShareUserResponse],
    responses={
        401: {"description": "Invalid authentication"},
        403: {"description": "Only owner or org admin can view shares"},
        404: {"description": "Assistant not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_assistant_shares_endpoint(request: Request, assistant_id: int):
    """Get list of users an assistant is shared with"""
    try:
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Unauthorized attempt to get assistant shares")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        user_id = creator_user.get('id')
        user_email = creator_user.get('email')
        logger.info(f"User {user_email} requesting shares for assistant {assistant_id}")

        # Get assistant to check ownership
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Check authorization: owner or org admin
        is_owner = assistant.owner == user_email
        auth_header = request.headers.get("Authorization")
        is_org_admin = is_organization_admin(auth_header, assistant.organization_id)

        if not is_owner and not is_org_admin:
            logger.warning(f"User {user_email} denied access to shares for assistant {assistant_id}")
            raise HTTPException(
                status_code=403,
                detail="Only the assistant owner or organization admin can view sharing settings"
            )

        from lamb.services.assistant_sharing_service import AssistantSharingService
        sharing_service = AssistantSharingService()

        shares = sharing_service.get_assistant_shares(assistant_id)
        logger.info(f"Found {len(shares)} shares for assistant {assistant_id}")

        return shares

    except HTTPException as he:
        raise he
    except ValueError as e:
        logger.error(f"Error getting assistant shares: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting assistant shares: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.put(
    "/lamb/assistant-sharing/shares/{assistant_id}",
    tags=["Assistant Sharing"],
    summary="Update Assistant Shares",
    description="""Update the list of users an assistant is shared with.
Accepts the desired final state of shared user emails. The backend calculates
additions and removals, then syncs to OWI groups.

Only the assistant owner or organization admin can update shares.

Example Request:
```bash
curl -X PUT 'http://localhost:9099/creator/lamb/assistant-sharing/shares/123' \\
-H 'Authorization: Bearer <user_token>' \\
-H 'Content-Type: application/json' \\
-d '{"user_emails": ["jane@example.com", "bob@example.com"]}'
```

Example Response:
```json
[
  {
    "user_email": "jane@example.com",
    "user_name": "Jane Smith",
    "shared_at": 1730908800,
    "shared_by_name": "John Doe"
  },
  {
    "user_email": "bob@example.com",
    "user_name": "Bob Wilson",
    "shared_at": 1730908900,
    "shared_by_name": "John Doe"
  }
]
```
    """,
    dependencies=[Depends(security)],
    response_model=List[ShareUserResponse],
    responses={
        401: {"description": "Invalid authentication"},
        403: {"description": "Only owner or org admin can manage shares / Sharing not enabled"},
        404: {"description": "Assistant not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_assistant_shares_endpoint(
    request: Request, 
    assistant_id: int, 
    shares_request: UpdateSharesRequest
):
    """Update the list of users an assistant is shared with"""
    try:
        creator_user = get_creator_user_from_token(
            request.headers.get("Authorization"))
        if not creator_user:
            logger.error("Unauthorized attempt to update assistant shares")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication or user not found in creator database"
            )

        user_id = creator_user.get('id')
        user_email = creator_user.get('email')
        logger.info(f"User {user_email} updating shares for assistant {assistant_id}")

        # Get assistant to check ownership
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Check authorization: owner or org admin
        is_owner = assistant.owner == user_email
        auth_header = request.headers.get("Authorization")
        is_org_admin = is_organization_admin(auth_header, assistant.organization_id)

        if not is_owner and not is_org_admin:
            logger.warning(f"User {user_email} denied update shares for assistant {assistant_id}")
            raise HTTPException(
                status_code=403,
                detail="Only the assistant owner or organization admin can manage sharing"
            )

        from lamb.services.assistant_sharing_service import AssistantSharingService
        sharing_service = AssistantSharingService()

        # Check if sharing is enabled (when adding shares)
        if len(shares_request.user_emails) > 0 and not sharing_service.check_sharing_permission(user_id):
            raise HTTPException(
                status_code=403,
                detail="Sharing is not enabled for your organization"
            )

        # Update shares using emails
        updated_shares = sharing_service.update_assistant_shares_by_email(
            assistant_id=assistant_id,
            user_emails=shares_request.user_emails,
            current_user_id=user_id
        )

        logger.info(f"Updated shares for assistant {assistant_id}: now shared with {len(updated_shares)} users")

        return updated_shares

    except HTTPException as he:
        raise he
    except ValueError as e:
        logger.error(f"Error updating assistant shares: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"Permission error updating assistant shares: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating assistant shares: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
