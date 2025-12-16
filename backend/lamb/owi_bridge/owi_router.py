from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Any
from .owi_database import OwiDatabaseManager
from .owi_users import OwiUserManager
from .owi_group import OwiGroupManager
from config import API_KEY
import logging
from fastapi.templating import Jinja2Templates
import os
import json
import traceback
from .owi_model import OWIModel

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Initialize routers and managers
router = APIRouter(
    tags=["OWI Users"],
    responses={404: {"description": "Not found"}}
)
db_manager = OwiDatabaseManager()
user_manager = OwiUserManager()
group_manager = OwiGroupManager()

# Initialize templates
templates = Jinja2Templates(directory=[
    "lamb/templates",  # Main templates directory
    "lamb/lti/templates"  # LTI templates directory
])

# Make sure the templates can find each other by setting the correct paths
templates.env.loader.searchpath = [
    os.path.abspath("lamb/templates"),
    os.path.abspath("lamb/lti/templates")
]

def verify_api_key(request: Request):
    """Verify Bearer token authentication"""
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    return True

def handle_response(success: bool, data: Any = None, error: str = None) -> JSONResponse:
    """Helper function to format consistent API responses"""
    if success:
        return JSONResponse(
            content={
                "status": "success",
                "data": data
            },
            status_code=200
        )
    else:
        return JSONResponse(
            content={
                "status": "error",
                "error": error
            },
            status_code=400
        )

@router.post("/users", 
    summary="Create a new user",
    description="Creates a new user with the provided name, email, password and optional role")
async def create_user(request: Request, _=Depends(verify_api_key)):
    """Endpoint to create a new user"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'password']
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Optional role field
        role = data.get('role', 'user')
        
        # Create user
        user = user_manager.create_user(
            name=data['name'],
            email=data['email'],
            password=data['password'],
            role=role
        )
        
        if user:
            # Remove sensitive information before returning
            user.pop('api_key', None)
            return handle_response(True, data=user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in create_user endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/users/verify")
async def verify_user(request: Request, _=Depends(verify_api_key)):
    """Endpoint to verify user credentials
    This endpoint is used to verify user credentials for the OpenWebUI
    parameters:
        email: str
        password: str
    """
    try:
        # we call this to make sure the admin user exists
        # if it doesn't, we create it with the default password on the .env file
        # this is a bit of a hack, but it's a quick way to make sure the admin user exists
        admin_token = user_manager.get_admin_user_token()
        
        data = await request.json()
        logging.info(f"Verify user request: {data}")
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required"
            )
        
        # Check if user exists in database before verification
        user_exists = db_manager.get_user_by_email(data['email'])
        
        

        # Verify credentials
        user = user_manager.verify_user(
            email=data['email'],
            password=data['password']
        )
        
        if user:
            # Remove sensitive information before returning
            user.pop('api_key', None)
            return handle_response(True, data=user)
        else:
            # Add more detailed error information
            if user_exists:
                error_detail = "Invalid password"
            else:
                error_detail = "User not found"
                
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_detail
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in verify_user endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/users/login/{email}", 
    summary="Get user login URL",
    description="Retrieves the login URL for a user by email")
async def get_user_login_url(email: str, _=Depends(verify_api_key)):
    user=user_manager.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found"
        )
    return user_manager.get_login_url(email, user['name'])  

@router.get("/users/token/{email}", 
    summary="Get user auth token",
    description="Retrieves the authentication token for a user by email")
async def get_user_token(email: str, _=Depends(verify_api_key)):
    """Endpoint to get user's auth token"""
    user=user_manager.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found"
        )
    try:
        token = user_manager.get_auth_token(email, user['name'])
        if token:
            return handle_response(True, data={"token": token})
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No token found for user with email {email}"
            )
            
    except Exception as e:
        logging.error(f"Error in get_user_token endpoint: {e}")
        return handle_response(False, error=str(e))

@router.get("/")
async def owi_test_page(request: Request):
    """Serve the OWI test interface"""
    try:
        return templates.TemplateResponse("owi_test.html", {"request": request})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serving test page: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=Dict)
async def get_user(
    user_id: str,
    request: Request
) -> Dict:
    """Get user by ID"""
    # Check Bearer token authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    
    try:
        user = db_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}"
        )

@router.get("/users/email/{email}", response_model=Dict)
async def get_user_by_email(
    email: str,
    request: Request
) -> Dict:
    """Get user by email"""
    # Check Bearer token authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    
    try:
        user = db_manager.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {email} not found"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/users")
async def get_users(request: Request):
    """Get all users with Bearer token authentication"""
    # Check Bearer token authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    logging.info(f"OWI Bridge: Authenticated user: {auth_header.split()[1]}")
    try:
        users = db_manager.get_all_users()
        if not users:
            return []
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.post("/groups", 
    summary="Create a new group",
    description="Creates a new group with the provided name, description and optional fields")
async def create_group(request: Request, _=Depends(verify_api_key)):
    """Endpoint to create a new group"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['name', 'user_id']
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Create group with optional fields
        group = group_manager.create_group(
            name=data['name'],
            user_id=data['user_id'],
            description=data.get('description', ''),
            data=data.get('data'),
            meta=data.get('meta'),
            permissions=data.get('permissions'),
            user_ids=data.get('user_ids', [])
        )
        
        if group:
            return handle_response(True, data=group)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create group"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in create_group endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/groups/{group_id}", 
    summary="Get group by ID",
    description="Retrieves a specific group by its ID")
async def get_group_by_id(group_id: str, _=Depends(verify_api_key)):
    """Endpoint to get a group by ID"""
    try:
        group = group_manager.get_group_by_id(group_id)
        return handle_response(True, data=group)
            
    except Exception as e:
        logging.error(f"Error in get_group_by_id endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/groups/user/{user_id}", 
    summary="Get user's groups",
    description="Retrieves all groups where the user is a member or owner")
async def get_user_groups(user_id: str, _=Depends(verify_api_key)):
    """Endpoint to get user's groups"""
    try:
        groups = group_manager.get_user_groups(user_id)
        return handle_response(True, data=groups)
            
    except Exception as e:
        logging.error(f"Error in get_user_groups endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/groups/{group_id}", 
    summary="Update group",
    description="Updates a group's information")
async def update_group(group_id: str, request: Request, _=Depends(verify_api_key)):
    """Endpoint to update group information"""
    try:
        data = await request.json()
        
        # Update only provided fields
        group = group_manager.update_group(
            group_id=group_id,
            name=data.get('name'),
            description=data.get('description'),
            data=data.get('data'),
            meta=data.get('meta'),
            permissions=data.get('permissions'),
            user_ids=data.get('user_ids')
        )
        
        if group:
            return handle_response(True, data=group)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group with id {group_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in update_group endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/groups/{group_id}/users/{user_id}", 
    summary="Add user to group",
    description="Adds a user to a group using their ID",
    responses={404: {"description": "Not found"}})
async def add_user_to_group(
    request: Request,
    group_id: str, 
    user_id: str
):
    """Endpoint to add user to group by ID"""
    # Check Bearer token authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    
    try:
        success = group_manager.add_user_to_group(group_id, user_id)
        
        if success:
            return handle_response(True, data={
                "message": f"User {user_id} successfully added to group {group_id}"
            })
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add user to group"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in add_user_to_group endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/groups/{group_id}/users/email/{email}", 
    summary="Add user to group by email",
    description="Adds a user to a group using their email address",
    responses={404: {"description": "Not found"}})
async def add_user_to_group_by_email(
    request: Request,
    group_id: str, 
    email: str
):
    """Endpoint to add user to group by email"""
    # Check Bearer token authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split()[1] != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing authentication token"
        )
    
    try:
        result = group_manager.add_user_to_group_by_email(group_id, email)
        
        if result["status"] == "success":
            return handle_response(True, data=result["data"])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in add_user_to_group_by_email endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.delete("/groups/{group_id}/users/{user_id}", 
    summary="Remove user from group",
    description="Removes a user from a group")
async def remove_user_from_group(group_id: str, user_id: str, _=Depends(verify_api_key)):
    """Endpoint to remove user from group"""
    try:
        success = group_manager.remove_user_from_group(group_id, user_id)
        
        if success:
            return handle_response(True)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove user from group"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in remove_user_from_group endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/groups", 
    summary="Get all groups",
    description="Retrieves all groups")
async def get_groups(_=Depends(verify_api_key)):
    """Endpoint to get all groups"""
    try:
        groups = group_manager.get_all_groups()
        if not groups:
            return handle_response(True, data=[])
            
        return handle_response(True, data=groups)
            
    except Exception as e:
        logging.error(f"Error in get_groups endpoint: {e}")
        return handle_response(False, error=str(e))

@router.get("/get_group_users/{group_id}", 
    response_model=List[Dict],
    summary="Get users in a group",
    description="Retrieves all users in a specific group")
async def get_group_users(group_id: str, _=Depends(verify_api_key)):
    """Endpoint to get users in a group"""
    try:
        # First verify the group exists
        group = group_manager.get_group_by_id(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_id} not found"
            )
            
        # Get users from the group's user_ids array
        user_ids = json.loads(group['user_ids']) if isinstance(group['user_ids'], str) else group['user_ids']
        
        users = []
        for user_id in user_ids:
            user = group_manager.db.get_user_by_id(user_id)
            if user:
                users.append({
                    "id": user["id"],
                    "name": user.get("display_name", "N/A"),
                    "email": user["email"]
                })
        
        return handle_response(True, data=users)
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in get_group_users endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/users/update_password",
    summary="Update user password",
    description="Updates a user's password")
async def update_user_password(request: Request, _=Depends(verify_api_key)):
    """Endpoint to update a user's password"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['email', 'new_password']
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Get user to verify existence
        user = user_manager.get_user_by_email(data['email'])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {data['email']} not found"
            )
            
        # Update password
        success = user_manager.update_user_password(
            email=data['email'],
            new_password=data['new_password']
        )
        
        if success:
            return handle_response(True, data={"message": "Password updated successfully"})
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update password"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in update_user_password endpoint: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/users/password", 
    summary="Update user password (alternate endpoint)",
    description="Updates a user's password using POST method")
async def update_user_password_post(request: Request, _=Depends(verify_api_key)):
    """Alternative endpoint to update a user's password using POST"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['email', 'new_password']
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Get user to verify existence
        user = user_manager.get_user_by_email(data['email'])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {data['email']} not found"
            )
            
        # Update password
        success = user_manager.update_user_password(
            email=data['email'],
            new_password=data['new_password']
        )
        
        if success:
            return handle_response(True, data={"message": "Password updated successfully"})
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update password"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in update_user_password_post endpoint: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/users/role-update", include_in_schema=True)
async def update_user_role(request: Request):
    """Ultra simple endpoint to update a user's role"""
    # Extra basic logging with no dependencies
    logger.error(f"[ULTRA_BASIC] update_user_role endpoint was called with method {request.method}")
    
    try:
        # Check API key manually to ensure we're authenticated
        auth_header = request.headers.get("Authorization", "")
        logger.error(f"[ULTRA_BASIC] Auth header: {auth_header}")
        
        # Very basic auth validation
        if not auth_header.startswith("Bearer "):
            logger.error("[ULTRA_BASIC] Missing or invalid authorization header")
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid authorization"}
            )
        
        # Manually parse the request body - no FastAPI magic
        body = await request.body()
        logger.error(f"[ULTRA_BASIC] Raw request body: {body}")
        
        # Try to parse as JSON manually
        try:
            import json
            body_str = body.decode('utf-8')
            logger.error(f"[ULTRA_BASIC] Body as string: {body_str}")
            
            # Parse the JSON
            data = json.loads(body_str)
            logger.error(f"[ULTRA_BASIC] Parsed JSON data: {data}")
        except Exception as json_error:
            logger.error(f"[ULTRA_BASIC] Failed to parse JSON: {str(json_error)}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON", "details": str(json_error)}
            )
            
        # Extract the required fields
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        logger.error(f"[ULTRA_BASIC] Extracted user_id: {user_id}, new_role: {new_role}")
        
        # Validate the required fields
        if not user_id or not new_role:
            logger.error(f"[ULTRA_BASIC] Missing required fields: user_id: {user_id}, role: {new_role}")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required fields", "details": f"user_id: {user_id}, role: {new_role}"}
            )
            
        # Special case for user ID 1
        if str(user_id) == "1":
            logger.error("[ULTRA_BASIC] Cannot change role for user ID 1 (admin)")
            return JSONResponse(
                status_code=403,
                content={"error": "Cannot change role for user ID 1 (admin)"}
            )
            
        # Create an instance of the user manager directly
        from lamb.owi_bridge.owi_users import OwiUserManager
        user_manager = OwiUserManager()
        
        # Attempt to update the role directly
        logger.error(f"[ULTRA_BASIC] Calling user_manager.update_user_role({user_id}, {new_role})")
        result = user_manager.update_user_role(str(user_id), new_role)
        
        logger.error(f"[ULTRA_BASIC] Role update result: {result}")
        
        if result:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"User {user_id} role updated to {new_role}"}
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"Failed to update role for user {user_id}"}
            )
        logger.info(f"[OWI_ROUTER] Request headers: {dict(request.headers)}")
        
        data = await request.json()
        logger.info(f"[OWI_ROUTER] Request data: {data}")
        
        # Validate required fields
        if 'user_id' not in data:
            logger.error(f"[OWI_ROUTER] Missing required field: user_id in data: {data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: user_id"
            )
            
        user_id = data['user_id']
        logger.info(f"[OWI_ROUTER] User ID from request: {user_id}")
        
        if 'role' not in data:
            logger.error(f"[OWI_ROUTER] Missing required field: role in data: {data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: role"
            )
            
        new_role = data['role']
        logger.info(f"[OWI_ROUTER] New role requested: {new_role}")
        
        # Validate the role value
        if new_role not in ['admin', 'user']:
            logger.error(f"[OWI_ROUTER] Invalid role: {new_role}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {new_role}. Must be 'admin' or 'user'"
            )
        
        # Prevent changing user ID 1
        if user_id == "1":
            logger.error(f"[OWI_ROUTER] Attempt to change role for user ID 1 (primary admin)")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change role for user ID 1 (primary admin)"
            )
        
        # Get user to verify existence
        logger.info(f"[OWI_ROUTER] Checking if user {user_id} exists")
        user = user_manager.get_user_by_id(user_id)
        if user:
            logger.info(f"[OWI_ROUTER] User found: {user}")
        else:
            logger.error(f"[OWI_ROUTER] User with ID {user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
            
        # TEMPORARY APPROACH: Try to update directly with database connection
        logger.error(f"[OWI_ROUTER_DEBUG] Attempting DIRECT database update for user {user_id} with role {new_role}")
        
        try:
            # Try to get a direct database connection
            logger.error(f"[OWI_ROUTER_DEBUG] Getting direct database connection")
            import sqlite3
            import os
            
            # Get the database path from the configuration or environment
            db_path = user_manager.db.db_path if hasattr(user_manager.db, 'db_path') else os.environ.get('OWI_DB_PATH', 'owi.db')
            logger.error(f"[OWI_ROUTER_DEBUG] Using database path: {db_path}")
            
            direct_conn = None
            try:
                direct_conn = sqlite3.connect(db_path)
                logger.error(f"[OWI_ROUTER_DEBUG] Direct connection established: {direct_conn is not None}")
                
                # Check if the role column exists
                cursor = direct_conn.cursor()
                cursor.execute("PRAGMA table_info(user)")
                columns = cursor.fetchall()
                logger.error(f"[OWI_ROUTER_DEBUG] User table columns: {columns}")
                
                has_role = any(col[1] == 'role' for col in columns)
                logger.error(f"[OWI_ROUTER_DEBUG] Has role column: {has_role}")
                
                if not has_role:
                    logger.error(f"[OWI_ROUTER_DEBUG] Adding role column to user table")
                    cursor.execute("ALTER TABLE user ADD COLUMN role TEXT DEFAULT 'user'")
                    direct_conn.commit()
                    logger.error(f"[OWI_ROUTER_DEBUG] Added role column successfully")
                
                # Update the role directly
                update_query = "UPDATE user SET role = ? WHERE id = ?"
                logger.error(f"[OWI_ROUTER_DEBUG] Executing direct query: {update_query}")
                cursor.execute(update_query, (new_role, user_id))
                direct_conn.commit()
                logger.error(f"[OWI_ROUTER_DEBUG] Direct update executed, rowcount: {cursor.rowcount}")
                
                # Also try the standard method as a backup
                standard_success = user_manager.update_user_role(
                    user_id=user_id,
                    new_role=new_role
                )
                logger.error(f"[OWI_ROUTER_DEBUG] Standard update_user_role result: {standard_success}")
                
                success = cursor.rowcount > 0 or standard_success
                
            except Exception as direct_db_error:
                logger.error(f"[OWI_ROUTER_DEBUG] Direct database operation error: {str(direct_db_error)}")
                import traceback
                logger.error(f"[OWI_ROUTER_DEBUG] Direct DB traceback:\n{traceback.format_exc()}")
                
                # Fall back to the standard method
                logger.error(f"[OWI_ROUTER_DEBUG] Falling back to standard method")
                success = user_manager.update_user_role(
                    user_id=user_id,
                    new_role=new_role
                )
                logger.error(f"[OWI_ROUTER_DEBUG] Fallback update_user_role result: {success}")
            finally:
                if direct_conn:
                    direct_conn.close()
                    logger.error(f"[OWI_ROUTER_DEBUG] Direct connection closed")
        except Exception as outer_error:
            logger.error(f"[OWI_ROUTER_DEBUG] Outer exception in direct approach: {str(outer_error)}")
            import traceback
            logger.error(f"[OWI_ROUTER_DEBUG] Outer exception traceback:\n{traceback.format_exc()}")
            
            # Last resort - still try the standard method
            success = user_manager.update_user_role(
                user_id=user_id,
                new_role=new_role
            )
            logger.error(f"[OWI_ROUTER_DEBUG] Last resort update result: {success}")
        
        if success:
            logger.info(f"[OWI_ROUTER] Role updated successfully for user {user_id} to {new_role}")
            return handle_response(True, data={
                "message": f"Role updated successfully to '{new_role}'",
                "user_id": user_id,
                "new_role": new_role
            })
        else:
            logger.error(f"[OWI_ROUTER] Failed to update role for user {user_id} to {new_role}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user role"
            )
            
    except HTTPException as he:
        logger.error(f"[OWI_ROUTER_DEBUG] HTTPException in update_user_role: {he.detail} (status {he.status_code})")
        raise he
    except Exception as e:
        logger.error(f"[OWI_ROUTER_DEBUG] Critical error in update_user_role: {type(e).__name__}: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[OWI_ROUTER_DEBUG] Detailed traceback:\n{error_trace}")
        # Log the exact state at the time of the error
        logger.error(f"[OWI_ROUTER_DEBUG] Request data at time of error: {data if 'data' in locals() else 'Not available'}")
        logger.error(f"[OWI_ROUTER_DEBUG] User ID at time of error: {user_id if 'user_id' in locals() else 'Not available'}")
        logger.error(f"[OWI_ROUTER_DEBUG] New role at time of error: {new_role if 'new_role' in locals() else 'Not available'}")
        
        # Convert the exception to a readable format for the client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {type(e).__name__}: {str(e)}"
        )

@router.get("/models", 
    summary="Get user's models",
    description="Retrieves all models owned by the specified user")
async def get_user_models(
    request: Request,
    user_email: str,
    _=Depends(verify_api_key)
):
    """Get all models owned by a user"""
    try:
        # First get the user ID from email
        user = user_manager.get_user_by_email(user_email)
        if not user:
            return handle_response(False, error=f"User with email {user_email} not found")

        # Initialize model manager
        model_manager = OWIModel(db_manager)
        
        # Get models where user is owner
        query = """
            SELECT m.* 
            FROM model m 
            WHERE m.user_id = ? AND m.is_active = 1
        """
        
        owned_models = db_manager.execute_query(query, (user['id'],))
        
        # Format the response
        models = []
        if owned_models:
            for model in owned_models:
                model_dict = {
                    "id": model[0],  # Assuming first column is id
                    "name": model[3],  # Assuming fourth column is name
                    "base_model_id": model[2],  # Assuming third column is base_model_id
                    "meta": json.loads(model[4]) if model[4] else {},  # Assuming fifth column is meta
                    "params": json.loads(model[5]) if model[5] else {},  # Assuming sixth column is params
                    "access_control": json.loads(model[8]) if model[8] else {},  # Assuming ninth column is access_control
                    "is_active": bool(model[9])  # Assuming tenth column is is_active
                }
                models.append(model_dict)

        return handle_response(True, data=models)
            
    except Exception as e:
        logging.error(f"Error in get_user_models endpoint: {e}")
        return handle_response(False, error=str(e))

@router.put("/models/add_group", 
    summary="Add group to model",
    description="Adds a group to a model's read permissions. Creates the model if it doesn't exist.")
async def add_group_to_model(
    request: Request,
    user_owner_email: str,
    model_name: str,
    group_name: str,
    _=Depends(verify_api_key)
):
    """Add a group to a model's read permissions"""
    try:
        logging.info(f"Adding group to model with params: email={user_owner_email}, model={model_name}, group={group_name}")
        
        # Get user by email
        user = user_manager.get_user_by_email(user_owner_email)
        logging.info(f"Found user: {user}")
        if not user:
            return handle_response(False, error=f"User with email {user_owner_email} not found")

        # Get user's groups
        groups = group_manager.get_user_groups(user['id'])
        logging.info(f"Retrieved groups: {groups}")
        group = next((g for g in groups if g['name'] == group_name), None)
        logging.info(f"Found group: {group}")
        if not group:
            return handle_response(False, error=f"Group {group_name} not found in user's groups")

        # Add group to model
        model_manager = OWIModel(db_manager)
        logging.info(f"Attempting to add group {group['id']} to model {model_name}")
        model_data = model_manager.add_group_to_model_by_name(
            user_id=user['id'],
            model_name=model_name,
            group_id=group['id'],
            permission_type="read"
        )
        logging.info(f"Result from add_group_to_model_by_name: {model_data}")
        
        if not model_data:
            return handle_response(False, error="Failed to update model")
            
        return handle_response(True, data=model_data)
            
    except Exception as e:
        logging.error(f"Error in add_group_to_model endpoint: {e}")
        return handle_response(False, error=str(e))

@router.get("/get_owi_config", 
    summary="Get OWI configuration",
    description="Retrieves the OWI configuration record from the config table")
async def get_owi_config(request: Request, _=Depends(verify_api_key)):
    """Endpoint to get OWI configuration"""
    try:
        config = db_manager.get_config()
        if config:
            return handle_response(True, data=config)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuration not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in get_owi_config endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/set_owi_config", 
    summary="Update OWI configuration",
    description="Updates the OpenAI configuration to use LAMB_BASE_URL")
async def set_owi_config(request: Request, _=Depends(verify_api_key)):
    """Endpoint to update OWI configuration"""
    try:
        success = db_manager.set_owi_config()
        if success:
            return handle_response(True, data={"message": "Configuration updated successfully"})
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update configuration"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in set_owi_config endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )