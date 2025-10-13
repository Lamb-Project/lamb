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

from .assistant_router import get_creator_user_from_token
from .user_creator import UserCreatorManager

# Initialize security context for dependency injection
security = HTTPBearer()

# Initialize router
router = APIRouter()

# Get configuration for LAMB backend URL
import os
LAMB_BACKEND_URL = os.getenv("LAMB_BACKEND_HOST", "http://localhost:9099")


# Dependency functions
def get_current_creator_user(auth_header: str) -> Dict[str, Any]:
    """Get current authenticated creator user"""
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

    # For lamb core API endpoints, pass auth_header as query parameter
    if endpoint.startswith("/lamb/"):
        if params is None:
            params = {}
        params["auth_header"] = auth_token
        logging.error(f"Setting auth_header param: {auth_token}")
        headers = {
            "Content-Type": "application/json" if not files else None
        }
    else:
        headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json" if not files else None
        }

    # Remove None values from headers
    headers = {k: v for k, v in headers.items() if v is not None}

    # Remove None values from params
    if params:
        params = {k: v for k, v in params.items() if v is not None}
        logging.error(f"Filtered params: {params}")

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
            logging.error(f"Error proxying request to {url}: {e}")
            raise HTTPException(status_code=502, detail="Backend service unavailable")


async def handle_response(response: aiohttp.ClientResponse) -> Any:
    """Handle response from backend"""
    if response.status >= 400:
        try:
            error_data = await response.json()
            logging.error(f"Backend error {response.status}: {error_data}")
            raise HTTPException(status_code=response.status, detail=error_data.get("detail", "Backend error"))
        except Exception as e:
            logging.error(f"Failed to parse backend error: {e}")
            raise HTTPException(status_code=response.status, detail="Backend error")

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
    subject: str = Form(...),
    gradeLevel: str = Form(...),
    scoringType: str = Form("points"),
    maxScore: float = Form(100.0),
    criteria: str = Form(...)  # JSON string
):
    """
    Create a new rubric (enhanced proxy)

    POST /creator/evaluaitor/rubrics
    """
    try:
        # Authenticate user
        auth_header = request.headers.get("Authorization")
        logging.error(f"Auth header: {auth_header}")
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
        logging.error(f"Auth token: {auth_token}")

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
        logging.error(f"Error creating rubric: {e}")
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
        logging.error(f"Error listing rubrics: {e}")
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
        logging.error(f"Error listing public rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public rubrics")


@router.get("/{rubric_id}")
async def get_rubric(
    rubric_id: str,
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Get a specific rubric

    GET /creator/evaluaitor/rubrics/{rubric_id}
    """
    try:
        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "GET",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_token
        )

        return result

    except Exception as e:
        logging.error(f"Error getting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rubric")


@router.put("/{rubric_id}")
async def update_rubric(
    rubric_id: str,
    title: str = Form(...),
    description: str = Form(""),
    subject: str = Form(...),
    gradeLevel: str = Form(...),
    scoringType: str = Form("points"),
    maxScore: float = Form(100.0),
    criteria: str = Form(...),  # JSON string
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Update an existing rubric

    PUT /creator/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Parse criteria JSON
        criteria_data = json.loads(criteria)

        # Prepare request data
        request_data = {
            "rubricId": rubric_id,
            "title": title,
            "description": description,
            "metadata": {
                "subject": subject,
                "gradeLevel": gradeLevel,
                "modifiedAt": datetime.now().isoformat()
            },
            "scoringType": scoringType,
            "maxScore": maxScore,
            "criteria": criteria_data
        }

        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_token,
            data=request_data
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid criteria JSON")
    except Exception as e:
        logging.error(f"Error updating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric")


@router.put("/{rubric_id}/visibility")
async def update_rubric_visibility(
    rubric_id: str,
    is_public: bool = Form(...),
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Update rubric visibility

    PUT /creator/evaluaitor/rubrics/{rubric_id}/visibility
    """
    try:
        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/visibility",
            auth_token,
            data={"is_public": is_public}
        )

        return result

    except Exception as e:
        logging.error(f"Error updating rubric visibility {rubric_id}: {e}")
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
        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "PUT",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/showcase",
            auth_token,
            data={"is_showcase": is_showcase}
        )

        return result

    except Exception as e:
        logging.error(f"Error updating rubric showcase {rubric_id}: {e}")
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
        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "DELETE",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}",
            auth_token
        )

        return result

    except Exception as e:
        logging.error(f"Error deleting rubric {rubric_id}: {e}")
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
        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "POST",
            f"/lamb/v1/evaluaitor/rubrics/{rubric_id}/duplicate",
            auth_token
        )

        return result

    except Exception as e:
        logging.error(f"Error duplicating rubric {rubric_id}: {e}")
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
        auth_token = request.headers.get("Authorization")

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
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Export rubric as JSON file download

    GET /creator/evaluaitor/rubrics/{rubric_id}/export/json
    """
    try:
        auth_token = request.headers.get("Authorization")

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
                content = await response.read()
                filename = response.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')

                return Response(
                    content=content,
                    media_type="application/json",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Content-Type": "application/json"
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error exporting rubric {rubric_id} as JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to export rubric")


@router.get("/{rubric_id}/export/markdown")
async def export_rubric_markdown(
    rubric_id: str,
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Export rubric as Markdown file download

    GET /creator/evaluaitor/rubrics/{rubric_id}/export/markdown
    """
    try:
        auth_token = request.headers.get("Authorization")

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
                content = await response.read()
                filename = response.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')

                return Response(
                    content=content,
                    media_type="text/markdown",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Content-Type": "text/markdown"
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error exporting rubric {rubric_id} as Markdown: {e}")
        raise HTTPException(status_code=500, detail="Failed to export rubric")


# AI Integration Endpoints

@router.post("/ai-generate")
async def ai_generate_rubric(
    request: Request,
    prompt: str = Form(..., min_length=10, max_length=2000)
):
    """
    Generate a rubric using AI

    POST /creator/evaluaitor/rubrics/ai-generate
    """
    try:
        # Authenticate user
        creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
        if not creator_user:
            raise HTTPException(status_code=401, detail="Invalid authentication or user not found")

        auth_token = request.headers.get("Authorization")

        result = await proxy_request(
            "POST",
            "/lamb/v1/evaluaitor/rubrics/ai-generate",
            auth_token,
            data={"prompt": prompt}
        )

        return result

    except Exception as e:
        logging.error(f"Error generating rubric with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate rubric with AI")


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
        auth_token = request.headers.get("Authorization")

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
