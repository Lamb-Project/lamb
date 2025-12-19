"""
Creator Interface Router for Evaluaitor (Rubrics)
Acts as a proxy between frontend and LAMB Core API with enhanced features.
"""

import logging
import json
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse, Response

from creator_interface.assistant_router import get_creator_user_from_token
from .user_creator import UserCreatorManager
import config
from lamb.logging_config import get_logger

# Initialize security context for dependency injection
security = HTTPBearer()

# Initialize router
router = APIRouter()
logger = get_logger(__name__, component="API")

# Get configuration for LAMB backend URL
LAMB_BACKEND_URL = config.LAMB_BACKEND_HOST


# Dependency functions
async def get_current_creator_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """Get current authenticated creator user"""
    auth_header = f"Bearer {credentials.credentials}"
    creator_user = get_creator_user_from_token(auth_header)
    if not creator_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return creator_user


async def proxy_request(
    method: str,
    endpoint: str,
    auth_token: str,
    data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Proxy request to LAMB backend

    Args:
        method: HTTP method
        endpoint: API endpoint (without base URL)
        auth_token: Authorization token
        data: Request data
        files: File uploads
        params: Query parameters

    Returns:
        Response from backend
    """
    url = f"{LAMB_BACKEND_URL}{endpoint}"
    logger.debug(f"Proxying {method} request to: {url}")

    # For lamb core API endpoints, pass auth_header as query parameter
    if endpoint.startswith("/lamb/"):
        if params is None:
            params = {}
        params["auth_header"] = auth_token
        logger.debug(f"Setting auth_header param: {auth_token}")
        headers = {
            "Content-Type": "application/json" if not files else None
        }
    else:
        headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json" if not files else None
        }

    logger.debug(f"Final URL: {url}")
    logger.debug(f"Headers: {headers}")
    logger.debug(f"Params: {params}")
    logger.debug(f"Data: {data}")

    # Remove None values from headers
    headers = {k: v for k, v in headers.items() if v is not None}

    # Remove None values from params and convert all values to strings
    if params:
        params = {k: str(v) for k, v in params.items() if v is not None}
        logger.debug(f"Filtered params: {params}")

    async with aiohttp.ClientSession() as session:
        try:
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    return await handle_response(response)
            elif method.upper() == "POST":
                if files:
                    # Handle multipart/form-data for file uploads
                    form_data = aiohttp.FormData()
                    for field_name, file_obj in files.items():
                        form_data.add_field(field_name, file_obj, filename=getattr(file_obj, 'filename', 'file'))

                    async with session.post(url, headers={"Authorization": auth_token}, data=form_data) as response:
                        return await handle_response(response)
                else:
                    async with session.post(url, headers=headers, json=data, params=params) as response:
                        return await handle_response(response)
            elif method.upper() == "PUT":
                async with session.put(url, headers=headers, json=data, params=params) as response:
                    return await handle_response(response)
            elif method.upper() == "DELETE":
                async with session.delete(url, headers=headers, params=params) as response:
                    return await handle_response(response)
            else:
                raise HTTPException(status_code=405, detail=f"Method {method} not supported")

        except aiohttp.ClientError as e:
            logger.error(f"Error proxying request to {url}: {e}")
            raise HTTPException(status_code=502, detail=f"Backend service unavailable: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error proxying request to {url}: {e}")
            raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")


async def handle_response(response: aiohttp.ClientResponse) -> Any:
    """Handle response from backend"""
    logger.debug(f"Response status: {response.status}")
    logger.debug(f"Response headers: {response.headers}")
    
    if response.status >= 400:
        try:
            error_data = await response.json()
            logger.error(f"Backend error {response.status}: {error_data}")
            raise HTTPException(status_code=response.status, detail=error_data.get("detail", "Backend error"))
        except Exception as e:
            logger.error(f"Failed to parse backend error: {e}")
            error_text = await response.text()
            logger.error(f"Raw error response: {error_text}")
            raise HTTPException(status_code=response.status, detail=f"Backend error: {error_text}")

    content_type = response.headers.get('content-type', '')

    if 'application/json' in content_type:
        return await response.json()
    elif 'text/markdown' in content_type or 'text/plain' in content_type:
        return await response.text()
    else:
        # For file downloads, return the response object to be handled specially
        return response


# Rubric CRUD Endpoints (Proxied)

@router.post("")
async def create_rubric(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    subject: str = Form(""),
    gradeLevel: str = Form(""),
    scoringType: str = Form("points"),
    maxScore: float = Form(10.0),
    criteria: str = Form(...)  # JSON string
):
    """
    Create a new rubric (enhanced proxy)

    POST /creator/evaluaitor/rubrics
    """
    try:
        # Authenticate user
        auth_header = request.headers.get("Authorization")
        logger.debug(f"Auth header: {auth_header}")
        creator_user = get_creator_user_from_token(auth_header)
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        # Parse criteria JSON
        criteria_data = json.loads(criteria)

        # Prepare request data
        request_data = {
            "title": title,
            "description": description,
            "metadata": {
                "subject": subject,
                "gradeLevel": gradeLevel
            },
            "scoringType": scoringType,
            "maxScore": maxScore,
            "criteria": criteria_data
        }

        # Get auth token from request header
        auth_token = request.headers.get("Authorization")
        logger.debug(f"Auth token: {auth_token}")

        # Proxy to backend
        result = await proxy_request(
            "POST",
            "/lamb/v1/evaluaitor/rubrics",
            auth_token,
            data=request_data
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid criteria JSON")
    except Exception as e:
        logger.error(f"Error creating rubric: {e}")
        raise HTTPException(status_code=500, detail="Failed to create rubric")


@router.get("")
async def list_rubrics(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subject: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tab: str = Query("my", description="Tab: 'my' or 'templates'")
):
    """
    List user's rubrics with enhanced filtering

    GET /creator/evaluaitor/rubrics
    """
    try:
        # Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        auth_token = request.headers.get("Authorization")

        if tab == "templates":
            # Get public rubrics from organization
            result = await proxy_request(
                "GET",
                "/lamb/v1/evaluaitor/rubrics/public",
                auth_token,
                params={
                    "limit": limit,
                    "offset": offset,
                    "subject": subject,
                    "grade_level": grade_level,
                    "search": search
                }
            )
        else:
            # Get user's own rubrics
            result = await proxy_request(
                "GET",
                "/lamb/v1/evaluaitor/rubrics",
                auth_token,
                params={
                    "limit": limit,
                    "offset": offset,
                    "subject": subject,
                    "grade_level": grade_level,
                    "search": search
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error listing rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list rubrics")


@router.get("/public")
async def list_public_rubrics(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subject: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    List public rubrics in user's organization

    GET /creator/rubrics/public
    """
    try:
        # Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        # Build filters
        filters = {}
        if subject:
            filters["subject"] = subject
        if grade_level:
            filters["grade_level"] = grade_level
        if search:
            filters["search"] = search

        # Get organization ID
        organization_id = creator_user.get('organization_id')
        if not organization_id:
            raise HTTPException(status_code=400, detail="User not associated with an organization")

        # Call LAMB core API
        response = await proxy_request(
            method="GET",
            endpoint=f"/lamb/v1/evaluaitor/rubrics",
            auth_token=f"Bearer {creator_user.get('token', '')}",
            params={
                "organization_id": organization_id,
                "is_public": True,
                "limit": limit,
                "offset": offset,
                **filters
            }
        )

        return response

    except Exception as e:
        logger.error(f"Error listing public rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public rubrics")


@router.get("/{rubric_id}")
async def get_rubric(
    rubric_id: str,
    request: Request
):
    """
    Get a specific rubric

    GET /creator/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Authenticate user
        auth_header = request.headers.get("Authorization")
        creator_user = get_creator_user_from_token(auth_header)
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        result = await proxy_request(
            "GET",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_header
        )

        return result

    except Exception as e:
        logger.error(f"Error getting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rubric")


@router.put("/{rubric_id}")
async def update_rubric(
    rubric_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    subject: str = Form(""),
    gradeLevel: str = Form(""),
    scoringType: str = Form("points"),
    maxScore: float = Form(10.0),
    criteria: str = Form(...)  # JSON string
):
    """
    Update an existing rubric

    PUT /creator/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Authenticate user
        auth_header = request.headers.get("Authorization")
        creator_user = get_creator_user_from_token(auth_header)
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        # Parse criteria JSON
        criteria_data = json.loads(criteria)

        # First, get the existing rubric to preserve createdAt
        existing_result = await proxy_request(
            "GET",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_header
        )
        
        # Extract existing metadata
        existing_metadata = {}
        if existing_result and 'rubric_data' in existing_result:
            rubric_data = existing_result['rubric_data']
            if isinstance(rubric_data, str):
                rubric_data = json.loads(rubric_data)
            existing_metadata = rubric_data.get('metadata', {})

        # Prepare request data, preserving createdAt
        request_data = {
            "rubricId": rubric_id,
            "title": title,
            "description": description,
            "metadata": {
                "subject": subject,
                "gradeLevel": gradeLevel,
                "createdAt": existing_metadata.get("createdAt", datetime.now().isoformat()),
                "modifiedAt": datetime.now().isoformat()
            },
            "scoringType": scoringType,
            "maxScore": maxScore,
            "criteria": criteria_data
        }

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_header,
            data=request_data
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid criteria JSON")
    except Exception as e:
        logger.error(f"Error updating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric")


@router.put("/{rubric_id}/visibility")
async def update_rubric_visibility(
    rubric_id: str,
    request: Request,
    is_public: bool = Form(...)
):
    """
    Update rubric visibility

    PUT /creator/evaluaitor/rubrics/{rubric_id}/visibility
    """
    try:
        # Authenticate user and get original auth header
        auth_header = request.headers.get("Authorization")
        creator_user = get_creator_user_from_token(auth_header)
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/visibility",
            auth_header,
            data={"is_public": is_public}
        )

        return result

    except Exception as e:
        logger.error(f"Error updating rubric visibility {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric visibility")


@router.put("/{rubric_id}/showcase")
async def update_rubric_showcase(
    rubric_id: str,
    is_showcase: bool = Form(...),
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Update rubric showcase status (admin only)

    PUT /creator/evaluaitor/rubrics/{rubric_id}/showcase
    """
    try:
        auth_token = f"Bearer {creator_user.get('token', '')}"

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/showcase",
            auth_token,
            data={"is_showcase": is_showcase}
        )

        return result

    except Exception as e:
        logger.error(f"Error updating rubric showcase {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric showcase status")


@router.delete("/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Delete a rubric

    DELETE /creator/evaluaitor/rubrics/{rubric_id}
    """
    try:
        auth_token = f"Bearer {creator_user.get('token', '')}"

        result = await proxy_request(
            "DELETE",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_token
        )

        return result

    except Exception as e:
        logger.error(f"Error deleting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete rubric")


@router.post("/{rubric_id}/duplicate")
async def duplicate_rubric(
    rubric_id: str,
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Duplicate a rubric

    POST /creator/evaluaitor/rubrics/{rubric_id}/duplicate
    """
    try:
        auth_token = f"Bearer {creator_user.get('token', '')}"

        result = await proxy_request(
            "POST",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/duplicate",
            auth_token
        )

        return result

    except Exception as e:
        logger.error(f"Error duplicating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate rubric")


# Import/Export Endpoints

@router.post("/import")
async def import_rubric(
    file: UploadFile = File(...),
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Import rubric from JSON file

    POST /creator/evaluaitor/rubrics/import
    """
    try:
        auth_token = f"Bearer {creator_user.get('token', '')}"

        # Read file content
        content = await file.read()
        files = {"file": content}

        # Add filename for validation
        import io
        file_obj = io.BytesIO(content)
        file_obj.filename = file.filename
        files = {"file": file_obj}

        result = await proxy_request(
            "POST",
            "/lamb/v1/evaluaitor/rubrics/import",
            auth_token,
            files=files
        )

        return result

    except Exception as e:
        logging.error(f"Error importing rubric: {e}")
        raise HTTPException(status_code=500, detail="Failed to import rubric")


@router.get("/{rubric_id}/export/json")
async def export_rubric_json(
    rubric_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Export rubric as JSON file download

    GET /creator/evaluaitor/rubrics/{rubric_id}/export/json
    """
    try:
        auth_token = f"Bearer {credentials.credentials}"
        # Get the response from backend
        async with aiohttp.ClientSession() as session:
            url = f"{LAMB_BACKEND_URL}/lamb/v1/evaluaitor/rubrics/{rubric_id}/export/json"
            headers = {"Authorization": auth_token}

            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    try:
                        error_data = await response.json()
                        raise HTTPException(status_code=response.status, detail=error_data.get("detail", "Backend error"))
                    except:
                        raise HTTPException(status_code=response.status, detail="Backend error")

                # Return file download response
                # Read as bytes to avoid encoding issues, let FastAPI handle encoding
                content_bytes = await response.read()
                filename = response.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')
                
                # FastAPI Response handles bytes directly
                from fastapi.responses import Response
                return Response(
                    content=content_bytes,
                    media_type="application/json; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Content-Type": "application/json; charset=utf-8"
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to export rubric")


@router.get("/{rubric_id}/export/markdown")
async def export_rubric_markdown(
    rubric_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Export rubric as Markdown file download

    GET /creator/evaluaitor/rubrics/{rubric_id}/export/markdown
    """
    try:
        auth_token = f"Bearer {credentials.credentials}"
        # Get the response from backend
        async with aiohttp.ClientSession() as session:
            url = f"{LAMB_BACKEND_URL}/lamb/v1/evaluaitor/rubrics/{rubric_id}/export/markdown"
            headers = {"Authorization": auth_token}

            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    try:
                        error_data = await response.json()
                        raise HTTPException(status_code=response.status, detail=error_data.get("detail", "Backend error"))
                    except:
                        raise HTTPException(status_code=response.status, detail="Backend error")

                # Return file download response
                # Read as bytes to avoid encoding issues
                content_bytes = await response.read()
                
                # Extract filename, handling encoding in filename
                content_disposition = response.headers.get("Content-Disposition", "")
                filename = "rubric.md"
                if content_disposition:
                    try:
                        # More robust filename extraction
                        if "filename=" in content_disposition:
                            filename = content_disposition.split("filename=")[-1].strip('"').strip("'")
                            # Sanitize filename to ASCII to avoid encoding issues in headers
                            filename = filename.encode('ascii', 'ignore').decode('ascii')
                            if not filename:
                                filename = f"rubric-{rubric_id}.md"
                    except:
                        filename = f"rubric-{rubric_id}.md"
                
                # Use StreamingResponse with iter to pass bytes directly
                from fastapi.responses import Response
                return Response(
                    content=content_bytes,
                    media_type="text/markdown; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Type": "text/markdown; charset=utf-8"
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as Markdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export rubric: {str(e)}")


# AI Integration Endpoints

@router.post("/ai-generate")
async def ai_generate_rubric(request: Request):
    """
    Generate a rubric using AI (preview only, does not save)

    POST /creator/rubrics/ai-generate
    
    Request body (JSON):
        {
            "prompt": "User's natural language request",
            "language": "en" (optional: en, es, eu, ca),
            "model": "gpt-4o-mini" (optional override)
        }
    
    Response:
        {
            "success": true/false,
            "rubric": { ... complete rubric JSON ... },
            "markdown": "# Rubric Title\n\n...",
            "explanation": "AI's explanation",
            "prompt_used": "Complete prompt (for debugging)",
            // OR if failed:
            "error": "Error message",
            "raw_response": "...",
            "allow_manual_edit": true/false
        }
    """
    try:
        # Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        # Parse JSON body
        body = await request.json()
        prompt = body.get('prompt')
        language = body.get('language', 'en')
        model = body.get('model')
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")

        auth_token = request.headers.get("Authorization")

        # Proxy to backend
        result = await proxy_request(
            "POST",
            "/lamb/v1/evaluaitor/rubrics/ai-generate",
            auth_token,
            data={
                "prompt": prompt,
                "language": language,
                "model": model
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating rubric with AI: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate rubric with AI: {str(e)}")


@router.post("/{rubric_id}/ai-modify")
async def ai_modify_rubric(
    rubric_id: str,
    prompt: str = Form(..., min_length=10, max_length=1000),
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Modify a rubric using AI

    POST /creator/evaluaitor/rubrics/{rubric_id}/ai-modify
    """
    try:
        auth_token = f"Bearer {creator_user.get('token', '')}"

        result = await proxy_request(
            "POST",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/ai-modify",
            auth_token,
            data={"prompt": prompt}
        )

        return result

    except Exception as e:
        logging.error(f"Error modifying rubric {rubric_id} with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to modify rubric with AI")


# Showcase templates endpoint
@router.get("/showcase",
    dependencies=[Depends(security)])
async def list_showcase_rubrics(
    request: Request
):
    """
    List showcase rubrics for quick access

    GET /creator/evaluaitor/rubrics/showcase
    """
    try:
        # Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "GET",
            "/lamb/v1/evaluaitor/rubrics/showcase",
            auth_token
        )

        return result

    except Exception as e:
        logging.error(f"Error listing showcase rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list showcase rubrics")


@router.get("/rubrics/accessible",
    dependencies=[Depends(security)])
async def get_accessible_rubrics_for_assistant(
    request: Request
):
    """
    Get list of rubrics accessible to user for assistant attachment
    Returns user's own rubrics + public rubrics in organization

    Response format optimized for dropdown selector:
    {
      "rubrics": [
        {
          "rubric_id": "rubric-123",
          "title": "Essay Writing Rubric",
          "description": "...",
          "is_mine": true,
          "is_showcase": false
        }
      ]
    }

    GET /creator/rubrics/accessible
    """
    try:
        # Get user from token
        auth_header = request.headers.get("Authorization")
        creator_user = get_creator_user_from_token(auth_header)

        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_email = creator_user.get('user_email')
        organization_id = creator_user.get('organization_id')

        # Get rubric database manager - we'll need direct database access for this
        # Import here to avoid circular imports
        from lamb.evaluaitor.rubric_database import RubricDatabaseManager

        db_manager = RubricDatabaseManager()

        # Get user's own rubrics
        my_rubrics = db_manager.get_rubrics_by_owner(
            owner_email=user_email,
            limit=1000,  # Get all
            offset=0,
            filters={}
        )

        # Get public rubrics in organization
        public_rubrics = db_manager.get_public_rubrics(
            organization_id=organization_id,
            limit=1000,
            offset=0,
            filters={}
        )

        # Format for dropdown
        accessible = []

        # Add user's rubrics (marked as mine)
        for rubric in my_rubrics:
            accessible.append({
                "rubric_id": rubric['rubric_id'],
                "title": rubric['title'],
                "description": rubric.get('description', ''),
                "is_mine": True,
                "is_showcase": rubric.get('is_showcase', False),
                "is_public": rubric.get('is_public', False)
            })

        # Add public rubrics (not already in list)
        my_rubric_ids = {r['rubric_id'] for r in my_rubrics}
        for rubric in public_rubrics:
            if rubric['rubric_id'] not in my_rubric_ids:
                accessible.append({
                    "rubric_id": rubric['rubric_id'],
                    "title": rubric['title'],
                    "description": rubric.get('description', ''),
                    "is_mine": False,
                    "is_showcase": rubric.get('is_showcase', False),
                    "is_public": True
                })

        # Sort: showcase first, then user's rubrics, then others
        accessible.sort(key=lambda r: (
            not r['is_showcase'],  # Showcase first (False < True)
            not r['is_mine'],      # Then user's rubrics
            r['title'].lower()     # Then alphabetical
        ))

        return {
            "success": True,
            "rubrics": accessible,
            "total": len(accessible)
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting accessible rubrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
