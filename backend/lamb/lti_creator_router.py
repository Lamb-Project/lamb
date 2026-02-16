"""
LTI Creator Router

Handles LTI-based creator user authentication and provisioning.
This allows educators to log into the Creator Interface via LTI from their LMS.

Key differences from student LTI (lti_users_router.py):
- Creates/authenticates 'creator' users (not end_users)
- Uses org-specific consumer keys (not assistant-specific)
- Redirects to Creator UI (not OWI chat)
- Users can create assistants, not just chat with them
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger
import hmac
import hashlib
import base64
import urllib.parse
import os
import re

logger = get_logger(__name__, component="LTI_CREATOR")

router = APIRouter()
db_manager = LambDatabaseManager()


def generate_oauth_signature(params: dict, http_method: str, base_url: str, 
                              consumer_secret: str, token_secret: str = "") -> str:
    """
    Generate OAuth 1.0 signature for LTI validation.
    
    Args:
        params: All POST parameters including oauth_* fields
        http_method: HTTP method (POST)
        base_url: Full URL of the endpoint
        consumer_secret: The OAuth consumer secret
        token_secret: Token secret (empty for LTI)
        
    Returns:
        Base64-encoded HMAC-SHA1 signature
    """
    # Remove oauth_signature if present
    params_copy = params.copy()
    if "oauth_signature" in params_copy:
        del params_copy["oauth_signature"]

    # Sort parameters alphabetically
    sorted_params = sorted(params_copy.items())

    # Encode parameters
    encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

    # Create signature base string
    base_string = "&".join([
        http_method.upper(),
        urllib.parse.quote(base_url, safe=''),
        urllib.parse.quote(encoded_params, safe='')
    ])

    # Create signing key (consumer_secret&token_secret)
    signing_key = f"{consumer_secret}&{token_secret}"

    # Calculate HMAC-SHA1 signature
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_signature = base64.b64encode(hashed.digest()).decode()

    return computed_signature


def sanitize_lti_user_id(lti_user_id: str, max_length: int = 120) -> str:
    """
    Sanitize LTI user_id for safe email local-part usage.

    Keeps alphanumerics plus '.', '_', '-' and replaces others with '_'.
    """
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", lti_user_id.strip())
    if not sanitized:
        return "lti_user"
    return sanitized[:max_length]


@router.post("/launch")
async def lti_creator_launch(request: Request):
    """
    LTI launch endpoint for Creator Interface access.
    
    Flow:
    1. Validate OAuth signature using org-specific consumer secret
    2. Resolve organization from consumer key
    3. Create or fetch LTI creator user
    4. Generate JWT token
    5. Redirect to Creator UI with token
    
    Required LTI parameters:
    - oauth_consumer_key: Organization's LTI consumer key
    - user_id: Stable user identifier from LMS
    - lis_person_name_full (optional): User's display name
    - ext_user_username (optional): Username fallback
    """
    try:
        form_data = await request.form()
        post_data = dict(form_data)
        
        # Extract OAuth consumer key
        oauth_consumer_key = post_data.get("oauth_consumer_key")
        if not oauth_consumer_key:
            logger.error("Missing oauth_consumer_key in LTI launch")
            raise HTTPException(status_code=400, detail="Missing oauth_consumer_key")
        
        logger.info(f"LTI creator launch attempt with consumer key: {oauth_consumer_key}")
        
        # Look up organization by consumer key
        org = db_manager.get_organization_by_lti_consumer_key(oauth_consumer_key)
        if not org:
            logger.error(f"No organization found for consumer key: {oauth_consumer_key}")
            raise HTTPException(status_code=401, detail="Invalid consumer key")
        
        # Reject system org
        if org.get('is_system'):
            logger.error("LTI creator launch attempted for system organization")
            raise HTTPException(status_code=403, detail="LTI creator access not allowed for system organization")
        
        # Get consumer secret for OAuth validation
        consumer_secret = org.get('lti_creator', {}).get('oauth_consumer_secret')
        if not consumer_secret:
            logger.error(f"No consumer secret configured for org {org['slug']}")
            raise HTTPException(status_code=500, detail="LTI not properly configured")
        
        # Construct base URL for signature validation
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("Host", request.url.hostname)
        prefix = request.headers.get('X-Forwarded-Prefix', '')
        base_url = f"{proto}://{host}{prefix}{request.url.path}"
        
        logger.debug(f"LTI creator launch URL: {base_url}")
        
        # Validate OAuth signature
        computed_signature = generate_oauth_signature(
            post_data, "POST", base_url, consumer_secret
        )
        received_signature = post_data.get("oauth_signature")
        
        if computed_signature != received_signature:
            logger.error(f"OAuth signature mismatch. Computed: {computed_signature}, Received: {received_signature}")
            raise HTTPException(status_code=401, detail="Invalid OAuth signature")
        
        logger.debug("OAuth signature validated successfully")
        
        # Extract user identity from LTI
        lti_user_id = post_data.get("user_id")
        if not lti_user_id:
            logger.error("Missing user_id in LTI launch")
            raise HTTPException(status_code=400, detail="Missing user_id")
        
        # Get user display name (with fallbacks)
        user_name = (
            post_data.get("lis_person_name_full") or 
            post_data.get("ext_user_username") or 
            post_data.get("user_id") or 
            "LTI User"
        )
        
        # Generate email for this LTI creator user
        # Format: lti_creator_{org_slug}_{user_id}@lamb-lti.local
        sanitized_lti_user_id = sanitize_lti_user_id(lti_user_id)
        user_email = f"lti_creator_{org['slug']}_{sanitized_lti_user_id}@lamb-lti.local"
        
        logger.info(f"LTI creator user: {user_email}, name: {user_name}, org: {org['slug']}")
        
        # Get or create LTI creator user
        creator_user = db_manager.get_creator_user_by_lti(org['id'], lti_user_id)
        
        if not creator_user:
            logger.info(f"Creating new LTI creator user for {lti_user_id} in org {org['slug']}")
            user_id = db_manager.create_lti_creator_user(
                organization_id=org['id'],
                lti_user_id=lti_user_id,
                user_email=user_email,
                user_name=user_name
            )
            
            if not user_id:
                logger.error(f"Failed to create LTI creator user for {lti_user_id}")
                raise HTTPException(status_code=500, detail="Failed to create user")
            
            creator_user = db_manager.get_creator_user_by_lti(org['id'], lti_user_id)
        else:
            logger.info(f"Found existing LTI creator user: {creator_user['email']}")
            user_email = creator_user['email']
        
        # Check if user is enabled
        if not creator_user.get('enabled', True):
            logger.warning(f"Disabled LTI creator user attempted login: {user_email}")
            raise HTTPException(status_code=403, detail="Account has been disabled")
        
        # Generate LAMB JWT for creator interface
        from lamb import auth as lamb_auth
        auth_token = lamb_auth.create_token({
            "sub": str(creator_user['id']),
            "email": user_email,
            "role": creator_user.get('role', 'user')
        })
        if not auth_token:
            logger.error(f"Failed to generate LAMB JWT for LTI creator user: {user_email}")
            raise HTTPException(status_code=500, detail="Failed to generate authentication token")
        
        logger.info(f"LTI creator login successful for {user_email}")
        
        # Get the public base URL for redirect
        # Use LAMB_PUBLIC_BASE_URL if set, otherwise construct from request
        public_base_url = os.getenv("LAMB_PUBLIC_BASE_URL")
        if not public_base_url:
            public_base_url = f"{proto}://{host}{prefix}"
        
        # Redirect to Creator UI with token
        # The frontend will store this token and use it for API calls
        redirect_url = f"{public_base_url}/assistants?token={auth_token}"
        
        logger.debug(f"Redirecting to Creator UI: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in LTI creator launch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LTI launch failed: {str(e)}")


@router.get("/info")
async def lti_creator_info():
    """
    Return information about the LTI creator launch endpoint.
    Useful for LMS administrators configuring the LTI tool.
    """
    return JSONResponse({
        "name": "LAMB Creator Interface",
        "description": "LTI launch for LAMB Creator Interface - allows educators to create AI learning assistants",
        "launch_url": "/lamb/v1/lti_creator/launch",
        "required_parameters": [
            "oauth_consumer_key",
            "user_id"
        ],
        "optional_parameters": [
            "lis_person_name_full",
            "ext_user_username"
        ],
        "notes": [
            "Consumer key and secret are configured per-organization in LAMB admin settings",
            "Users are identified by user_id across LTI instances",
            "LTI creator users are created as members by default but can be promoted to org admin by a system admin"
        ]
    })
