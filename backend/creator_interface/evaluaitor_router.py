"""
Creator Interface Router for Evaluaitor (Rubrics)
Direct business logic layer - no HTTP proxying.
"""

import logging
import json
import io
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Note: Security is kept for backward compat but get_current_creator_user now uses AuthContext
from fastapi.responses import StreamingResponse, JSONResponse, Response

from .user_creator import UserCreatorManager

# Import business logic functions
from lamb.evaluaitor import rubric_service
from lamb.evaluaitor.ai_generator import generate_rubric_ai
from lamb.auth_context import AuthContext, get_auth_context

# Initialize security context for dependency injection
security = HTTPBearer()

# Initialize router
router = APIRouter()

# Set up logger
logger = logging.getLogger(__name__)


# Dependency functions — now delegates to AuthContext
async def get_current_creator_user(auth: AuthContext = Depends(get_auth_context)) -> Dict[str, Any]:
    """Get current authenticated creator user via AuthContext"""
    return auth.user


# Rubric CRUD Endpoints

@router.post("")
async def create_rubric(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    subject: str = Form(""),
    gradeLevel: str = Form(""),
    scoringType: str = Form("points"),
    maxScore: float = Form(10.0),
    criteria: str = Form(...),  # JSON string
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Create a new rubric

    POST /creator/rubrics
    """
    try:
        creator_user = auth.user

        # Parse criteria JSON
        criteria_data = json.loads(criteria)

        # Prepare metadata
        metadata = {
            "subject": subject,
            "gradeLevel": gradeLevel
        }

        # Call business logic function
        result = rubric_service.create_rubric_logic(
            title=title,
            description=description,
            metadata=metadata,
            criteria=criteria_data,
            scoring_type=scoringType,
            max_score=maxScore,
            user_email=creator_user['email'],
            organization_id=creator_user.get('organization_id', 1)
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid criteria JSON")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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
    tab: str = Query("my", description="Tab: 'my' or 'templates'"),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    List rubrics (my rubrics or public templates)

    GET /creator/rubrics?tab=my|templates
    """
    try:
        creator_user = auth.user

        if tab == "templates":
            # Get public rubrics from organization
            result = rubric_service.list_public_rubrics_logic(
                organization_id=creator_user.get('organization_id', 1),
                limit=limit,
                offset=offset,
                subject=subject,
                grade_level=grade_level,
                search=search
            )
        else:
            # Get user's own rubrics
            result = rubric_service.list_rubrics_logic(
                user_email=creator_user['email'],
                limit=limit,
                offset=offset,
                subject=subject,
                grade_level=grade_level,
                search=search
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
    search: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    List public rubrics (templates)

    GET /creator/rubrics/public
    """
    try:
        creator_user = auth.user

        # Get user's organization
        organization_id = creator_user.get('organization_id')
        if not organization_id:
            raise HTTPException(status_code=400, detail="User not associated with an organization")

        # Call business logic
        result = rubric_service.list_public_rubrics_logic(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            subject=subject,
            grade_level=grade_level,
            search=search
        )

        return result

    except Exception as e:
        logger.error(f"Error listing public rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public rubrics")


@router.get("/accessible")
async def get_accessible_rubrics(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get all rubrics accessible to the user (owned + public in org)
    Used for assistant rubric selection.

    GET /creator/rubrics/accessible
    """
    try:
        creator_user = auth.user

        # Get user's rubrics (empty list if none)
        try:
            my_rubrics = rubric_service.list_rubrics_logic(
                user_email=creator_user['email'],
                limit=limit,
                offset=0,
                search=search
            )
        except Exception as e:
            logger.warning(f"Error listing user rubrics: {e}")
            my_rubrics = {"rubrics": [], "total": 0}

        # Get public rubrics (empty list if none)
        try:
            public_rubrics = rubric_service.list_public_rubrics_logic(
                organization_id=creator_user.get('organization_id', 1),
                limit=limit,
                offset=0,
                search=search
            )
        except Exception as e:
            logger.warning(f"Error listing public rubrics: {e}")
            public_rubrics = {"rubrics": [], "total": 0}

        # Combine and deduplicate by rubric_id
        all_rubrics = my_rubrics.get('rubrics', [])
        seen_ids = {r.get('rubric_id') for r in all_rubrics if r.get('rubric_id')}
        
        for rubric in public_rubrics.get('rubrics', []):
            rubric_id = rubric.get('rubric_id')
            if rubric_id and rubric_id not in seen_ids:
                all_rubrics.append(rubric)
                seen_ids.add(rubric_id)

        return {
            "rubrics": all_rubrics,
            "total": len(all_rubrics)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting accessible rubrics: {e}", exc_info=True)
        # Return empty list instead of error for better UX
        return {
            "rubrics": [],
            "total": 0
        }


@router.get("/{rubric_id}")
async def get_rubric(
    rubric_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get a specific rubric

    GET /creator/rubrics/{rubric_id}
    """
    try:
        creator_user = auth.user

        result = rubric_service.get_rubric_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    criteria: str = Form(...),  # JSON string
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Update an existing rubric

    PUT /creator/rubrics/{rubric_id}
    """
    try:
        creator_user = auth.user

        # Parse criteria JSON
        criteria_data = json.loads(criteria)

        # First, get the existing rubric to preserve createdAt
        existing_rubric = rubric_service.get_rubric_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )
        
        # Extract existing metadata
        existing_metadata = {}
        if existing_rubric and 'rubric_data' in existing_rubric:
            rubric_data_obj = existing_rubric['rubric_data']
            if isinstance(rubric_data_obj, str):
                rubric_data_obj = json.loads(rubric_data_obj)
            existing_metadata = rubric_data_obj.get('metadata', {})

        # Prepare metadata, preserving createdAt
        metadata = {
            "subject": subject,
            "gradeLevel": gradeLevel,
            "createdAt": existing_metadata.get("createdAt", datetime.now().isoformat())
        }

        # Call business logic
        result = rubric_service.update_rubric_logic(
            rubric_id=rubric_id,
            title=title,
            description=description,
            metadata=metadata,
            criteria=criteria_data,
            scoring_type=scoringType,
            max_score=maxScore,
            user_email=creator_user['email']
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid criteria JSON")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric")


@router.put("/{rubric_id}/visibility")
async def update_rubric_visibility(
    rubric_id: str,
    request: Request,
    is_public: bool = Form(...),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Update rubric visibility

    PUT /creator/rubrics/{rubric_id}/visibility
    """
    try:
        creator_user = auth.user

        result = rubric_service.update_rubric_visibility_logic(
            rubric_id=rubric_id,
            is_public=is_public,
            user_email=creator_user['email'],
            user_id=creator_user['id']
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
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

    PUT /creator/rubrics/{rubric_id}/showcase
    """
    try:
        # Check admin status
        from lamb.database_manager import LambDatabaseManager
        db = LambDatabaseManager()
        system_org = db.get_organization_by_slug("lamb")
        if not system_org:
            raise HTTPException(status_code=403, detail="Admin access required")

        admin_role = db.get_user_organization_role(system_org['id'], creator_user['id'])
        if admin_role != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")

        # Update showcase status
        from lamb.evaluaitor.rubric_database import RubricDatabaseManager
        db_manager = RubricDatabaseManager()
        success = db_manager.set_showcase_status(
            rubric_id=rubric_id,
            is_showcase=is_showcase,
            admin_email=creator_user['email']
        )

        if not success:
            raise HTTPException(status_code=404, detail="Rubric not found")

        return {"success": True, "is_showcase": is_showcase}

    except HTTPException:
        raise
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

    DELETE /creator/rubrics/{rubric_id}
    """
    try:
        rubric_service.delete_rubric_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )

        return {"success": True}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete rubric")


@router.post("/{rubric_id}/duplicate")
async def duplicate_rubric(
    rubric_id: str,
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Duplicate a rubric as template

    POST /creator/rubrics/{rubric_id}/duplicate
    """
    try:
        result = rubric_service.duplicate_rubric_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email'],
            organization_id=creator_user.get('organization_id', 1)
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    Import a rubric from JSON file

    POST /creator/rubrics/import
    """
    try:
        # Read file content
        content = await file.read()

        result = rubric_service.import_rubric_logic(
            file_content=content,
            filename=file.filename,
            user_email=creator_user['email'],
            organization_id=creator_user.get('organization_id', 1)
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing rubric: {e}")
        raise HTTPException(status_code=500, detail="Failed to import rubric")


@router.get("/{rubric_id}/export/json")
async def export_rubric_json(
    rubric_id: str,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Export rubric as JSON file

    GET /creator/rubrics/{rubric_id}/export/json
    """
    try:
        creator_user = auth.user

        rubric_data, filename = rubric_service.export_rubric_json_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )

        # Return JSON response with file headers
        return JSONResponse(
            content=rubric_data,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export rubric: {str(e)}")


@router.get("/{rubric_id}/export/markdown")
async def export_rubric_markdown(
    rubric_id: str,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Export rubric as Markdown document

    GET /creator/rubrics/{rubric_id}/export/markdown
    """
    try:
        creator_user = auth.user

        markdown_content, filename = rubric_service.export_rubric_markdown_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )

        # Return Markdown response
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/markdown"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as markdown: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export rubric: {str(e)}")


# AI Integration Endpoints

@router.post("/ai-generate")
async def ai_generate_rubric(request: Request, auth: AuthContext = Depends(get_auth_context)):
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
        creator_user = auth.user

        # Parse JSON body
        body = await request.json()
        prompt = body.get('prompt')
        language = body.get('language', 'en')
        model = body.get('model')
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")

        # Call AI generator directly
        result = generate_rubric_ai(
            user_prompt=prompt,
            user_email=creator_user['email'],
            language=language,
            model=model
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating rubric with AI: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate rubric with AI: {str(e)}")


@router.post("/{rubric_id}/ai-modify")
async def ai_modify_rubric(
    rubric_id: str,
    prompt: str = Form(..., min_length=10, max_length=1000),
    creator_user: Dict[str, Any] = Depends(get_current_creator_user)
):
    """
    Modify an existing rubric using AI

    POST /creator/rubrics/{rubric_id}/ai-modify
    """
    try:
        # Get existing rubric
        rubric = rubric_service.get_rubric_logic(
            rubric_id=rubric_id,
            user_email=creator_user['email']
        )

        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        # Import AI modifier
        from lamb.evaluaitor.ai_generator import modify_rubric_ai
        
        # Modify rubric with AI
        result = modify_rubric_ai(
            rubric_id=rubric_id,
            modification_prompt=prompt,
            user_email=creator_user['email']
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error modifying rubric {rubric_id} with AI: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to modify rubric with AI: {str(e)}")

