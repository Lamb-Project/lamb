from .setup_translations import setup_translations
from fastapi import APIRouter, Request, Form, Response, HTTPException, File, UploadFile, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pathlib import Path
import gettext
import os
from fastapi.staticfiles import StaticFiles
import httpx
from dotenv import load_dotenv
from typing import Optional
from .user_creator import UserCreatorManager
from .assistant_router import is_admin_user
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from .assistant_router import router as assistant_router, get_creator_user_from_token
from .knowledges_router import router as knowledges_router
import json
import logging
import shutil
from pydantic import BaseModel, EmailStr
from fastapi import Body  # Import Body for request body definitions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Get environment variables
SIGNUP_ENABLED = os.getenv('SIGNUP_ENABLED', 'false').lower() == 'true'
SIGNUP_SECRET_KEY = os.getenv('SIGNUP_SECRET_KEY')
PIPELINES_HOST = os.getenv('PIPELINES_HOST')
PIPELINES_BEARER_TOKEN = os.getenv('PIPELINES_BEARER_TOKEN')

# Initialize managers
db_manager = LambDatabaseManager()


# Import the setup_translations function

# Set up the router
router = APIRouter()

# Include the assistant router
router.include_router(assistant_router, prefix="/assistant")

# Include the knowledges router
router.include_router(knowledges_router, prefix="/knowledgebases")

# Include the organization management router
from .organization_router import router as organization_router
router.include_router(organization_router, prefix="/admin")

# Include the learning assistant proxy router
from .learning_assistant_proxy import router as learning_assistant_proxy_router
router.include_router(learning_assistant_proxy_router)



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

# --- End Pydantic Models ---





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
    "role": "user"
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
                "role": result["data"]["role"]
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
            # Get OWI role information for the user
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    owi_response = await client.get(
                        f"{user_creator.pipelines_host}/lamb/v1/OWI/users/email/{user['email']}",
                        headers={
                            "Authorization": f"Bearer {user_creator.pipelines_bearer_token}",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    owi_role = 'user'  # Default
                    if owi_response.status_code == 200:
                        owi_user = owi_response.json()
                        owi_role = owi_user.get('role', 'user')
            except:
                owi_role = 'user'  # Default on error
            
            # Get enabled status from OWI auth system
            enabled_status = owi_manager.get_user_status(user['email'])
            if enabled_status is None:
                enabled_status = True  # Default to enabled if status can't be determined
                logger.warning(f"Could not determine enabled status for user {user['email']}, defaulting to enabled")
            
            user_data = {
                "id": user.get("id"),
                "email": user.get("email"), 
                "name": user.get("name"),
                "role": owi_role,
                "enabled": enabled_status,
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
            logging.info(f"Creating user in organization '{target_org['slug']}' using signup key")
            
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
                    logging.info(f"Assigned member role to user {email} in organization {target_org['slug']}")
                else:
                    logging.warning(f"Failed to assign role to user {email} in organization {target_org['slug']}")
                
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
            logging.info("Creating user in system organization using legacy signup key")
            
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
                    logging.info(f"Assigned member role to user {email} in system organization")
                else:
                    logging.warning(f"Failed to assign role to user {email} in system organization")
                
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
        logging.error(f"Signup error: {str(e)}")
        return {
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }

@router.get(
    "/admin/organizations/list",
    tags=["Admin - Organization Management"],
    summary="List Organizations for User Assignment (Admin Only)",
    description="""Retrieves a simplified list of organizations for user assignment dropdowns. Requires admin privileges.

Example Request (Admin):
```bash
curl -X GET 'http://localhost:8000/creator/admin/organizations/list' \\
-H 'Authorization: Bearer <admin_token>'
```

Example Success Response:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "LAMB System Organization",
      "slug": "lamb",
      "is_system": true
    },
    {
      "id": 2,
      "name": "Engineering Department",
      "slug": "engineering",
      "is_system": false
    }
  ]
}
```
    """,
    dependencies=[Depends(security)],
    responses={
        200: {"description": "Successfully retrieved organizations list."},
    },
)
async def list_organizations_for_users(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List organizations for user assignment (admin only)"""
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
    
    try:
        # Use the database_manager directly
        from lamb.database_manager import LambDatabaseManager
        db_manager = LambDatabaseManager()
        
        organizations = db_manager.list_organizations()
        
        # Format for dropdown use
        org_list = []
        for org in organizations:
            org_list.append({
                "id": org["id"],
                "name": org["name"],
                "slug": org["slug"],
                "is_system": org["is_system"]
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": org_list
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
    organization_id: int = Form(None)
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
    
    # User is admin, proceed with creating a new user
    try:
        user_creator = UserCreatorManager()
        # Pass the role and organization_id parameters to create_user method
        result = await user_creator.create_user(email, name, password, role, organization_id)

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
            logger.error("Invalid authentication or user not found in creator database")
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
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


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
        result = user_manager.update_user_role_by_email(role_update.email, new_role)
            
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
        logger.info(f"[ROLE_UPDATE] Attempting to update role for user ID {user_id}")
        
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
                warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")
                
                # Import the OwiUserManager class directly
                from lamb.owi_bridge.owi_users import OwiUserManager
                
                # Create an instance
                user_manager = OwiUserManager()
                
                # Update the user's role directly by email
                # This eliminates the need to find the OWI user ID, simplifying the process
                # and reducing potential points of failure
                result = user_manager.update_user_role_by_email(user_email, new_role)
                
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
                logger.error(f"[ROLE_UPDATE] Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while updating user role: {str(db_error)}"
                )
                
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"[ROLE_UPDATE] Error in update_user_role_admin: {str(e)}")
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
        if current_user and current_user.get('email') == user.get('email') and not enabled:
            raise HTTPException(
                status_code=403,
                detail="You cannot disable your own account. Please ask another administrator to disable your account if needed."
            )
        
        # Update user status in OWI auth system
        owi_manager = OwiUserManager()
        if not owi_manager.update_user_status(user['email'], enabled):
            raise HTTPException(
                status_code=500,
                detail="Failed to update user status"
            )
        
        status_text = "enabled" if enabled else "disabled"
        logger.info(f"Admin updated user {user['email']} (ID: {user_id}) status to {status_text}")
        
        return {
            "success": True,
            "message": f"User has been {status_text}",
            "data": {
                "user_id": user_id,
                "email": user['email'],
                "enabled": enabled
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
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
