from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from .database_manager import LambDatabaseManager
import os
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from config import API_KEY  # Import API_KEY from config
from lamb.logging_config import get_logger

# Set up logger for creator user router
logger = get_logger(__name__, component="API")

router = APIRouter()
db_manager = LambDatabaseManager()
security = HTTPBearer()

# Initialize templates
templates = Jinja2Templates(directory="lamb/templates")


@router.get("")
async def get_creator_users_page(request: Request):
    """Serve the creator users management page"""
    return templates.TemplateResponse("creator_users.html", {"request": request, "api_key": API_KEY})


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the bearer token against LAMB_BEARER_TOKEN
    """
    token = credentials.credentials
    # Use centralized config token (has a default and trims whitespace)
    expected_token = API_KEY

    if not expected_token:
        logger.error("LAMB_BEARER_TOKEN not configured")
        raise HTTPException(
            status_code=500,
            detail="API authentication not properly configured"
        )

    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return token


class CreatorUserSignin(BaseModel):
    email: EmailStr
    password: str


class CreatorUserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    organization_id: Optional[int] = None
    user_type: str = "creator"  # 'creator' or 'end_user'


class CreatorUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str


class CreatorUserList(BaseModel):
    id: int
    email: str
    name: str
    user_config: dict


class TokenVerify(BaseModel):
    token: str


@router.post("/create", response_model=Optional[int])
async def create_creator_user(
    user_data: CreatorUserCreate,
    token: str = Depends(verify_api_key)
):
    """
    Create a new creator user
    """
    try:
        # Check if user already exists
        existing_user = db_manager.get_creator_user_by_email(user_data.email)
        if existing_user:
            logger.warning(f"User with email {user_data.email} already exists. Returning 409 Conflict.")
            raise HTTPException(status_code=409, detail=f"User with email {user_data.email} already exists")

        # Create new user
        user_id = db_manager.create_creator_user(
            user_email=user_data.email,
            user_name=user_data.name,
            password=user_data.password,
            organization_id=user_data.organization_id,
            user_type=user_data.user_type
        )

        if not user_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create creator user"
            )

        return user_id

    except Exception as e:
        logger.error(f"Error creating creator user: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/verify")
async def verify_creator_user(
    user_data: CreatorUserSignin,
    token: str = Depends(verify_api_key)
):
    """
    Verify creator user credentials and return token from OWI
    """
    try:
        # First verify the user exists in our database
        user = db_manager.get_creator_user_by_email(user_data.email)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Check if user account is enabled
        if not user.get('enabled', True):
            logger.warning(f"Disabled user {user_data.email} attempted login")
            raise HTTPException(
                status_code=403,
                detail="Account has been disabled. Please contact your administrator."
            )

        # Initialize OWI user manager
        from .owi_bridge.owi_users import OwiUserManager
        owi_manager = OwiUserManager()

        # Verify credentials and get token from OWI
        owi_user = owi_manager.verify_user(user_data.email, user_data.password)
        if not owi_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        # Get auth token from OWI
        auth_token = owi_manager.get_auth_token(user_data.email, user["name"])
        if not auth_token:
            raise HTTPException(
                status_code=500,
                detail="Failed to get authentication token"
            )
        
        # Get the user role from OWI user
        user_role = "user"  # Default role
        if owi_user and "role" in owi_user:
            user_role = owi_user["role"]
            logger.debug(f"Got role '{user_role}' for user {user_data.email}")

        return {
            "token": auth_token,
            "name": user["name"],
            "email": user["email"],
            "role": user_role,
            "id": user["id"],
            "user_type": user.get("user_type", "creator")  # Include user_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying creator user: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/check/{email}")
async def check_creator_user(
    email: EmailStr,
    token: str = Depends(verify_api_key)
) -> Optional[int]:
    """
    Check if a creator user exists by email
    """
    try:
        user = db_manager.get_creator_user_by_email(email)

        if user:
            return user['id']

        return None

    except Exception as e:
        logger.error(f"Error checking creator user: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/list", response_model=List[CreatorUserList])
async def list_creator_users(
    token: str = Depends(verify_api_key)
) -> List[CreatorUserList]:
    """
    Get a list of all creator users
    """
    try:
        users = db_manager.get_creator_users()
        if users is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve creator users"
            )
        return users

    except Exception as e:
        logger.error(f"Error listing creator users: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

