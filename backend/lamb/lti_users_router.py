from fastapi import APIRouter, HTTPException, Request, Depends
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import LTIUser
from typing import Optional
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from utils.pipelines.auth import get_current_user
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.owi_bridge.owi_group import OwiGroupManager
from lamb.logging_config import get_logger
from urllib.parse import unquote
import os
import hmac
import hashlib
import base64
import urllib.parse
import config

# Create logger instance using centralized logging with LTI component
logger = get_logger(__name__, component="LTI")

router = APIRouter()
db_manager = LambDatabaseManager()
owi_user_manager = OwiUserManager()
owi_group_manager = OwiGroupManager()


@router.get("/")
async def read_lti_users():
    return FileResponse("lamb/templates/lti_users.html")


@router.post("/lti_user/", response_model=LTIUser)
async def create_lti_user(request: Request, current_user: str = Depends(get_current_user)):
    try:
        request_data = await request.json()

        # Create LTIUser object with all required fields
        lti_user = LTIUser(
            assistant_id=request_data.get("assistant_id"),
            assistant_name=request_data.get("assistant_name"),
            group_id=request_data.get("group_id"),
            group_name=request_data.get("group_name"),
            assistant_owner=request_data.get("assistant_owner"),
            user_email=request_data.get("user_email"),
            user_name=request_data.get("user_name"),
            user_display_name=request_data.get("user_display_name"),
            user_id=request_data.get("user_id"),
            lti_context_id=request_data.get("lti_context_id"),
            lti_app_id=request_data.get("lti_app_id")
        )

        # First check if OWI user already exists
        existing_user = owi_user_manager.get_user_by_email(lti_user.user_email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="OWI user already exists"
            )
        if not existing_user:
            # Create OWI user if doesn't exist
            owi_user = owi_user_manager.create_user(
                name=lti_user.user_display_name,
                email=lti_user.user_email,
                password=lti_user.assistant_id,  # Using assistant_id as password
                role="user"
            )

            if not owi_user:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to create OWI user"
                )
        else:
            owi_user = existing_user

        # Add user to OWI group
        add_to_group_result = owi_group_manager.add_user_to_group_by_email(
            group_id=lti_user.group_id,
            user_email=lti_user.user_email
        )

        if add_to_group_result.get("status") != "success":
            raise HTTPException(
                status_code=400,
                detail=f"Failed to add user to group: {add_to_group_result.get('error', 'Unknown error')}"
            )

        # Create LTI user in database
        created_id = db_manager.create_lti_user(lti_user)
        if created_id:
            lti_user.id = created_id
            return lti_user
        else:
            raise HTTPException(
                status_code=400, detail="Failed to create LTI user")
    except Exception as e:
        logger.error(f"Error creating LTI user: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Error processing request: {str(e)}")


@router.get("/lti_user/{user_email}", response_model=Optional[LTIUser])
async def get_lti_user(user_email: str, current_user: str = Depends(get_current_user)):
    try:
        user = db_manager.get_lti_user_by_email(user_email)
        if user:
            return user
        raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without changing them
        raise
    except Exception as e:
        logger.error(f"Error retrieving LTI user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/lti_users/assistant/{assistant_id}", response_model=list[LTIUser])
async def get_lti_users_by_assistant(assistant_id: str, current_user: str = Depends(get_current_user)):
    try:
        users = db_manager.get_lti_users_by_assistant_id(assistant_id)
        if users:
            return users
        return []
    except Exception as e:
        logger.error(
            f"Error retrieving LTI users for assistant {assistant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sign_in_lti_user")
async def sign_in_lti_user(request: Request, current_user: str = Depends(get_current_user)):
    """
    Sign in LTI user.

    Flow:
    1. Check if user exists in LTI users
        - If yes:
            - Verify oauth_consumer_name matches
            - If matches, return auth token
            - If doesn't match, return error
        - If no:
            - Get published assistant by oauth_consumer_name
            - Create new LTI user with assistant details
            - Check if OWI user exists, if not create new OWI user
            - Add user to OWI group
            - Return auth token
    """
    try:
        request_data = await request.json()
        email = request_data.get("email")
        username = request_data.get("username")
        oauth_consumer_name = request_data.get("oauth_consumer_name")

        if not all([email, username, oauth_consumer_name]):
            raise HTTPException(
                status_code=400, detail="Missing required fields")

        # Check if user exists in LTI users
        existing_user = db_manager.get_lti_user_by_email(email)

        if existing_user:
            # Verify oauth_consumer_name matches
            if existing_user['lti_context_id'] != oauth_consumer_name:
                raise HTTPException(
                    status_code=403,
                    detail="User exists but oauth_consumer_name doesn't match"
                )

            # Get auth token for existing user
            user_token = owi_user_manager.get_auth_token(email, username)
            if not user_token:
                raise HTTPException(
                    status_code=500, detail="Failed to get user token")

            return {"token": user_token}

        else:
            # Get published assistant by oauth_consumer_name
            published_assistant = db_manager.get_published_assistant_by_oauth_consumer(
                oauth_consumer_name)
            if not published_assistant:
                raise HTTPException(
                    status_code=404,
                    detail="No published assistant found for this oauth_consumer_name"
                )

            logger.info(f"published assistant {published_assistant}")

            # Create new LTI user
            lti_user = LTIUser(
                assistant_id=str(published_assistant['assistant_id']),
                assistant_name=published_assistant['assistant_name'],
                group_id=published_assistant['group_id'],
                group_name=published_assistant['group_name'],
                assistant_owner=published_assistant['assistant_owner'],
                user_email=email,
                user_name=username,
                user_display_name=username,
                lti_context_id=oauth_consumer_name,
                lti_app_id=oauth_consumer_name
            )

            # Check if OWI user already exists
            existing_owi_user = owi_user_manager.get_user_by_email(email)

            if not existing_owi_user:
                logger.info(f"Creating new OWI user for email: {email}")
                # Create OWI user
                owi_user = owi_user_manager.create_user(
                    name=username,
                    email=email,
                    password=str(published_assistant['assistant_id']),
                    role="user"
                )

                if not owi_user:
                    raise HTTPException(
                        status_code=500, detail="Failed to create OWI user")
            else:
                logger.info(
                    f"OWI user with email {email} already exists, skipping creation")

            # Add user to OWI group

            group_name = published_assistant.get('group_id')
            group_obj = owi_group_manager.get_group_by_name(group_name)
            if not group_obj:
                logger.error(f"Group not found in OWI for group name: {group_name}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to find group '{group_name}' in OWI")

            group_id = group_obj.get('id')
            if not group_id:
                logger.error(f"Group found but missing id for group name: {group_name} - group_obj: {group_obj}")
                raise HTTPException(
                    status_code=500, detail="Failed to get group id")

            add_to_group_result = owi_group_manager.add_user_to_group_by_email(
                group_id=group_id,
                user_email=email
            )

            if add_to_group_result.get("status") != "success":
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to add user to group: {add_to_group_result.get('error', 'Unknown error')}"
                )

            # Create LTI user in database
            created_id = db_manager.create_lti_user(lti_user)
            if not created_id:
                raise HTTPException(
                    status_code=500, detail="Failed to create LTI user")

            # Get auth token for new user
            user_token = owi_user_manager.get_auth_token(email, username)
            if not user_token:
                raise HTTPException(
                    status_code=500, detail="Failed to get user token")

            return {"token": user_token}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sign_in_lti_user: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


def generate_signature(params, http_method, base_url, consumer_secret, token_secret=""):

    # logging.info(f"params: {params}")
    # logging.info(f"http_method: {http_method}")
    # logging.info(f"consumer_secret: {consumer_secret}")
    # logging.info(f"token_secret: {token_secret}")
    # logging.info(f"Base URL for signature: {base_url}")

    # Remove oauth_signature if present
    params_copy = params.copy()
    if "oauth_signature" in params_copy:
        del params_copy["oauth_signature"]

    # Sort parameters
    sorted_params = sorted(params_copy.items())

    # Encode parameters
    encoded_params = urllib.parse.urlencode(
        sorted_params, quote_via=urllib.parse.quote)

    # Create base string
    base_string = "&".join([
        http_method.upper(),
        urllib.parse.quote(base_url, safe=''),
        urllib.parse.quote(encoded_params, safe='')
    ])

    # Create signing key (consumer_secret&token_secret)
    signing_key = f"{consumer_secret}&"

    # logging.info(f"Base string: {base_string}")
    # logging.info(f"Signing key: {consumer_secret}&")


    # Calculate signature
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_signature = base64.b64encode(hashed.digest()).decode()

    return computed_signature, base_string, encoded_params

@router.post("/lti")
async def process_lti_connection(request: Request):
    """
    Process an LTI connection request.

    This endpoint accepts LTI parameters via POST and validates the OAuth signature
    before processing the LTI launch request.

    The email is generated as username-oauth_consumer_name@lamb-project.org
    So we avoid using the email from the LTI request, adding a layer of privacy
    """
    try:
        form_data = await request.form()
        post_data = dict(form_data)

        lti_secret = os.getenv("LTI_SECRET")
        if not lti_secret:
            logger.error("LTI_SECRET environment variable not set")
            raise HTTPException(
                status_code=500, detail="LTI secret not configured"
            )

        # Get protocol from X-Forwarded-Proto header, or use actual request scheme
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("Host", request.url.hostname)
        
        ## Use the full path from the request without prepending anything
        ## since the path already contains the complete route
        base_url = f"{proto}://{host}{request.url.path}"

        # Debug logging to match consumer format
        logger.debug(f"DEBUG: Constructed launch_url: {base_url}")
        logger.debug(f"DEBUG: Building LTI params for launch_url = {base_url}")
        logger.debug(f"DEBUG: Consumer key = {post_data.get('oauth_consumer_key', 'N/A')}")
        logger.debug(f"DEBUG: Timestamp = {post_data.get('oauth_timestamp', 'N/A')}, Nonce = {post_data.get('oauth_nonce', 'N/A')}")

        computed_signature, base_string, encoded_params = generate_signature(
            post_data,
            "POST",
            base_url,
            lti_secret
        )

        # Log OAuth signature details
        logger.debug(f"DEBUG OAuth - Method: POST")
        logger.debug(f"DEBUG OAuth - URL: {base_url}")
        logger.debug(f"DEBUG OAuth - Signature Base String (first 500 chars): {base_string[:500]}")
        logger.debug(f"DEBUG OAuth - Generated Signature: {computed_signature}")
        logger.debug(f"DEBUG OAuth - Received Signature: {post_data.get('oauth_signature', 'N/A')}")

        # Compare computed signature with provided signature
        if computed_signature != post_data.get("oauth_signature"):
            logger.error(
                f"Invalid OAuth signature. Computed: {computed_signature}, Received: {post_data.get('oauth_signature')}")
            raise HTTPException(
                status_code=401, detail="Invalid OAuth signature")

        # Extract relevant LTI parameters
        #email = post_data.get("lis_person_contact_email_primary", "")
        # URL decode the email if needed
        #email = unquote(email) if email else ""

        username = post_data.get("ext_user_username", "")
        if not username:
            # Fallback to user_id if ext_user_username is not provided
            username = post_data.get("user_id", "")


        # Use oauth_consumer_key instead of context_id for oauth_consumer_name
        oauth_consumer_name = post_data.get("oauth_consumer_key", "")
        email = f"{username}-{oauth_consumer_name}@lamb-project.org"

        logger.info(
            f"LTI connection attempt for email: {email}, username: {username}, oauth_consumer_key: {oauth_consumer_name}")

        # Check if user already exists
        existing_user = db_manager.get_lti_user_by_email(email)

        if existing_user:
            logger.info(
                f"User with email {email} already exists, getting token directly")
            # User exists, just get the token
            user_token = owi_user_manager.get_auth_token(email, username)
            if not user_token:
                logger.error(
                    f"Failed to get token for existing user: {email}")
                raise HTTPException(
                    status_code=500, detail="Failed to get user token")

            logger.info(
                f"Successfully retrieved token for existing user: {email}")

            # Get the OWI PUBLIC base URL for browser redirects (falls back to internal URL if not set)
            owi_public_base_url = os.getenv("OWI_PUBLIC_BASE_URL") or os.getenv("OWI_BASE_URL") or config.OWI_PUBLIC_BASE_URL
            owi_public_api_base_url = f"{owi_public_base_url}/api/v1"

            # Redirect to the completion URL with the token
            redirect_url = f"{owi_public_api_base_url}/auths/complete?token={user_token}"
            logger.info(f"Redirecting to: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=303)
        else:
            logger.info(
                f"User with email {email} does not exist, creating new user")
            # User doesn't exist, proceed with normal flow
            # Prepare data for sign_in_lti_user
            lti_user_data = {
                "email": email,
                "username": username,
                "oauth_consumer_name": oauth_consumer_name
            }

            # Create a JSON-compatible request for sign_in_lti_user
            class MockRequest:
                async def json(self):
                    return lti_user_data

            mock_request = MockRequest()

            # Get the current user (admin for this case)
            current_user = "admin"  # Default admin user for LTI connections

            # Call the sign_in_lti_user function
            logger.info(f"Calling sign_in_lti_user for new user: {email}")
            result = await sign_in_lti_user(mock_request, current_user)

            token = result.get("token")
            logger.info(
                f"Successfully created new user and retrieved token: {email}")

            # Get the OWI PUBLIC base URL for browser redirects (falls back to internal URL if not set)
            owi_public_base_url = os.getenv("OWI_PUBLIC_BASE_URL") or os.getenv("OWI_BASE_URL") or config.OWI_PUBLIC_BASE_URL
            owi_public_api_base_url = f"{owi_public_base_url}/api/v1"

            # Redirect to the completion URL with the token
            redirect_url = f"{owi_public_api_base_url}/auths/complete?token={token}"
            logger.info(f"Redirecting to: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.error(f"Error in process_lti_connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add more endpoints as needed, such as update and delete
