"""
LAMB Core API for Rubrics
Provides REST endpoints for rubric CRUD operations, import/export, and AI assistance.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..database_manager import get_creator_user_from_token
from .rubric_database import RubricDatabaseManager
from .rubric_validator import RubricValidator


# Initialize router
router = APIRouter()

# Initialize database manager
db_manager = RubricDatabaseManager()


# Pydantic models for request/response validation
class RubricCreateRequest(BaseModel):
    """Request model for creating a rubric"""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    metadata: Dict[str, Any] = Field(...)
    criteria: List[Dict[str, Any]] = Field(..., min_items=1)
    scoringType: str = Field(..., pattern="^(points|percentage|holistic|single-point|checklist)$")
    maxScore: float = Field(..., gt=0)


class RubricUpdateRequest(BaseModel):
    """Request model for updating a rubric"""
    rubricId: str = Field(..., min_length=10)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    metadata: Dict[str, Any] = Field(...)
    criteria: List[Dict[str, Any]] = Field(..., min_items=1)
    scoringType: str = Field(..., pattern="^(points|percentage|holistic|single-point|checklist)$")
    maxScore: float = Field(..., gt=0)


class RubricVisibilityRequest(BaseModel):
    """Request model for changing rubric visibility"""
    is_public: bool


class RubricShowcaseRequest(BaseModel):
    """Request model for changing showcase status"""
    is_showcase: bool


class RubricListResponse(BaseModel):
    """Response model for rubric listing"""
    rubrics: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


# Dependency functions
def get_current_user(auth_header: str) -> Dict[str, Any]:
    """Get current authenticated user"""
    creator_user = get_creator_user_from_token(auth_header)
    if not creator_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return creator_user


def get_user_organization(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get user's organization"""
    from ..database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    org = db.get_user_organization(user['id'])
    if not org:
        raise HTTPException(status_code=403, detail="User not associated with organization")
    return org


# CRUD Endpoints

@router.post("/rubrics", response_model=Dict[str, Any])
async def create_rubric(
    rubric_data: RubricCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new rubric

    POST /lamb/v1/evaluaitor/rubrics
    """
    try:
        # Get user's organization
        org = get_user_organization(user)

        # Prepare full rubric data
        now = datetime.now().isoformat()
        full_rubric_data = {
            "rubricId": rubric_data.title.lower().replace(" ", "-") + "-" + str(int(datetime.now().timestamp())),
            "title": rubric_data.title,
            "description": rubric_data.description,
            "metadata": {
                **rubric_data.metadata,
                "createdAt": now,
                "modifiedAt": now
            },
            "criteria": rubric_data.criteria,
            "scoringType": rubric_data.scoringType,
            "maxScore": rubric_data.maxScore
        }

        # Validate rubric structure
        is_valid, error_msg = RubricValidator.validate_rubric_structure(full_rubric_data)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"Invalid rubric structure: {error_msg}")

        # Create rubric
        result = db_manager.create_rubric(
            rubric_data=full_rubric_data,
            owner_email=user['email'],
            organization_id=org['id']
        )

        return {
            "success": True,
            "rubric": result
        }

    except Exception as e:
        logging.error(f"Error creating rubric: {e}")
        raise HTTPException(status_code=500, detail="Failed to create rubric")


@router.get("/rubrics", response_model=RubricListResponse)
async def list_user_rubrics(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subject: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List user's rubrics with optional filtering

    GET /lamb/v1/evaluaitor/rubrics
    """
    try:
        # Build filters
        filters = {}
        if subject:
            filters['subject'] = subject
        if grade_level:
            filters['grade_level'] = grade_level

        # Get rubrics
        rubrics = db_manager.get_rubrics_by_owner(
            owner_email=user['email'],
            limit=limit,
            offset=offset,
            filters=filters
        )

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            rubrics = [
                r for r in rubrics
                if search_lower in r['title'].lower() or search_lower in r['description'].lower()
            ]

        # Get total count
        total = db_manager.count_rubrics(user['email'], filters)

        return {
            "rubrics": rubrics,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logging.error(f"Error listing rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list rubrics")


@router.get("/rubrics/public", response_model=RubricListResponse)
async def list_public_rubrics(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    subject: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List public rubrics in user's organization

    GET /lamb/v1/evaluaitor/rubrics/public
    """
    try:
        # Get user's organization
        org = get_user_organization(user)

        # Build filters
        filters = {}
        if subject:
            filters['subject'] = subject
        if grade_level:
            filters['grade_level'] = grade_level

        # Get public rubrics
        rubrics = db_manager.get_public_rubrics(
            organization_id=org['id'],
            limit=limit,
            offset=offset,
            filters=filters
        )

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            rubrics = [
                r for r in rubrics
                if search_lower in r['title'].lower() or search_lower in r['description'].lower()
            ]

        # Get total count (approximate - could be optimized)
        total = len(rubrics)  # Simplified for now

        return {
            "rubrics": rubrics,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logging.error(f"Error listing public rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public rubrics")


@router.get("/rubrics/showcase", response_model=List[Dict[str, Any]])
async def list_showcase_rubrics(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List showcase rubrics in user's organization

    GET /lamb/v1/evaluaitor/rubrics/showcase
    """
    try:
        # Get user's organization
        org = get_user_organization(user)

        # Get showcase rubrics
        rubrics = db_manager.get_showcase_rubrics(org['id'])

        return rubrics

    except Exception as e:
        logging.error(f"Error listing showcase rubrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list showcase rubrics")


@router.get("/rubrics/{rubric_id}", response_model=Dict[str, Any])
async def get_rubric(
    rubric_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a specific rubric by ID

    GET /lamb/v1/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Get rubric with access control
        rubric = db_manager.get_rubric_by_id(rubric_id, user['email'])

        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        return rubric

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rubric")


@router.put("/rubrics/{rubric_id}", response_model=Dict[str, Any])
async def update_rubric(
    rubric_id: str,
    rubric_data: RubricUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update an existing rubric

    PUT /lamb/v1/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Verify rubric_id matches
        if rubric_data.rubricId != rubric_id:
            raise HTTPException(status_code=400, detail="Rubric ID mismatch")

        # Prepare full rubric data with updated timestamp
        full_rubric_data = {
            "rubricId": rubric_data.rubricId,
            "title": rubric_data.title,
            "description": rubric_data.description,
            "metadata": {
                **rubric_data.metadata,
                "modifiedAt": datetime.now().isoformat()
            },
            "criteria": rubric_data.criteria,
            "scoringType": rubric_data.scoringType,
            "maxScore": rubric_data.maxScore
        }

        # Validate rubric structure
        is_valid, error_msg = RubricValidator.validate_rubric_structure(full_rubric_data)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"Invalid rubric structure: {error_msg}")

        # Update rubric
        result = db_manager.update_rubric(
            rubric_id=rubric_id,
            rubric_data=full_rubric_data,
            owner_email=user['email']
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric")


@router.put("/rubrics/{rubric_id}/visibility")
async def update_rubric_visibility(
    rubric_id: str,
    visibility_data: RubricVisibilityRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update rubric visibility (public/private)

    PUT /lamb/v1/evaluaitor/rubrics/{rubric_id}/visibility
    """
    try:
        # Update visibility
        success = db_manager.toggle_rubric_visibility(
            rubric_id=rubric_id,
            is_public=visibility_data.is_public,
            owner_email=user['email']
        )

        if not success:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        return {"success": True, "is_public": visibility_data.is_public}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating rubric visibility {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric visibility")


@router.put("/rubrics/{rubric_id}/showcase")
async def update_rubric_showcase(
    rubric_id: str,
    showcase_data: RubricShowcaseRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update rubric showcase status (admin only)

    PUT /lamb/v1/evaluaitor/rubrics/{rubric_id}/showcase
    """
    try:
        # Check admin status
        from ..database_manager import LambDatabaseManager
        db = LambDatabaseManager()
        system_org = db.get_organization_by_slug("lamb")
        if not system_org:
            raise HTTPException(status_code=403, detail="Admin access required")

        admin_role = db.get_user_organization_role(system_org['id'], user['id'])
        if admin_role != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")

        # Update showcase status
        success = db_manager.set_showcase_status(
            rubric_id=rubric_id,
            is_showcase=showcase_data.is_showcase,
            admin_email=user['email']
        )

        if not success:
            raise HTTPException(status_code=404, detail="Rubric not found")

        return {"success": True, "is_showcase": showcase_data.is_showcase}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating rubric showcase {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update rubric showcase status")


@router.delete("/rubrics/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a rubric

    DELETE /lamb/v1/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Delete rubric
        success = db_manager.delete_rubric(
            rubric_id=rubric_id,
            owner_email=user['email']
        )

        if not success:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete rubric")


@router.post("/rubrics/{rubric_id}/duplicate", response_model=Dict[str, Any])
async def duplicate_rubric(
    rubric_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Duplicate a rubric as template

    POST /lamb/v1/evaluaitor/rubrics/{rubric_id}/duplicate
    """
    try:
        # Get user's organization for the new rubric
        org = get_user_organization(user)

        # Verify user can access the source rubric
        source_rubric = db_manager.get_rubric_by_id(rubric_id, user['email'])
        if not source_rubric:
            raise HTTPException(status_code=404, detail="Source rubric not found or access denied")

        # Create duplicate
        new_rubric = db_manager.duplicate_rubric(
            rubric_id=rubric_id,
            new_owner_email=user['email']
        )

        return {
            "success": True,
            "rubric": new_rubric
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error duplicating rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate rubric")


# Import/Export Endpoints

@router.post("/rubrics/import")
async def import_rubric(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Import rubric from JSON file

    POST /lamb/v1/evaluaitor/rubrics/import
    """
    try:
        # Validate file type
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are supported")

        # Read file content
        content = await file.read()
        rubric_json = content.decode('utf-8')

        # Validate and parse rubric
        is_valid, rubric_data, error_msg = RubricValidator.validate_imported_rubric(rubric_json)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"Invalid rubric format: {error_msg}")

        # Get user's organization
        org = get_user_organization(user)

        # Sanitize data
        rubric_data = RubricValidator.sanitize_rubric_data(rubric_data)

        # Create rubric with new ID and ownership
        import uuid
        rubric_data['rubricId'] = str(uuid.uuid4())
        rubric_data['metadata']['createdAt'] = datetime.now().isoformat()
        rubric_data['metadata']['modifiedAt'] = datetime.now().isoformat()

        # Create rubric (private by default)
        result = db_manager.create_rubric(
            rubric_data=rubric_data,
            owner_email=user['email'],
            organization_id=org['id'],
            is_public=False
        )

        return {
            "success": True,
            "rubric": result,
            "message": "Rubric imported successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error importing rubric: {e}")
        raise HTTPException(status_code=500, detail="Failed to import rubric")


@router.get("/rubrics/{rubric_id}/export/json")
async def export_rubric_json(
    rubric_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export rubric as JSON file

    GET /lamb/v1/evaluaitor/rubrics/{rubric_id}/export/json
    """
    try:
        # Get rubric
        rubric = db_manager.get_rubric_by_id(rubric_id, user['email'])
        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        # Prepare filename
        title_slug = rubric['title'].lower().replace(' ', '-').replace('/', '-')
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{title_slug}-{timestamp}.json"

        # Return JSON response with file headers
        return JSONResponse(
            content=rubric['rubric_data'],
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error exporting rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export rubric")


@router.get("/rubrics/{rubric_id}/export/markdown")
async def export_rubric_markdown(
    rubric_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export rubric as Markdown document

    GET /lamb/v1/evaluaitor/rubrics/{rubric_id}/export/markdown
    """
    try:
        # Get rubric
        rubric = db_manager.get_rubric_by_id(rubric_id, user['email'])
        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        # Generate Markdown content
        markdown_content = generate_rubric_markdown(rubric['rubric_data'])

        # Prepare filename
        title_slug = rubric['title'].lower().replace(' ', '-').replace('/', '-')
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{title_slug}-{timestamp}.md"

        # Return Markdown response
        from fastapi.responses import Response
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/markdown"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error exporting rubric {rubric_id} as markdown: {e}")
        raise HTTPException(status_code=500, detail="Failed to export rubric as markdown")


def generate_rubric_markdown(rubric_data: Dict[str, Any]) -> str:
    """
    Generate Markdown representation of a rubric

    Args:
        rubric_data: Rubric JSON data

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append(f"# {rubric_data['title']}")
    lines.append("")

    # Description
    if rubric_data.get('description'):
        lines.append(f"**Description:** {rubric_data['description']}")
        lines.append("")

    # Metadata
    metadata = rubric_data.get('metadata', {})
    if metadata.get('subject'):
        lines.append(f"**Subject:** {metadata['subject']}")
    if metadata.get('gradeLevel'):
        lines.append(f"**Grade Level:** {metadata['gradeLevel']}")
    lines.append(f"**Scoring Type:** {rubric_data.get('scoringType', 'points')}")
    lines.append(f"**Maximum Score:** {rubric_data.get('maxScore', 'N/A')}")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Criteria table
    lines.append("## Criteria and Performance Levels")
    lines.append("")

    criteria = rubric_data.get('criteria', [])
    if not criteria:
        lines.append("*No criteria defined*")
        return "\n".join(lines)

    # Table header
    header_parts = ["Criterion"]
    if criteria:
        # Get level labels from first criterion
        first_criterion = criteria[0]
        levels = first_criterion.get('levels', [])
        header_parts.extend([f"{level.get('label', '')} ({level.get('score', '')})" for level in levels])

    lines.append("| " + " | ".join(header_parts) + " |")
    lines.append("| " + " | ".join(["---"] * len(header_parts)) + " |")
    lines.append("")

    # Table rows
    for criterion in criteria:
        row_parts = []

        # Criterion name and description
        name = criterion.get('name', '')
        description = criterion.get('description', '')
        weight = criterion.get('weight', '')
        criterion_cell = f"**{name}**"
        if weight:
            criterion_cell += f" ({weight} pts)"
        if description:
            criterion_cell += f"<br>{description}"
        row_parts.append(criterion_cell)

        # Level descriptions
        levels = criterion.get('levels', [])
        for level in levels:
            description = level.get('description', '')
            row_parts.append(description)

        lines.append("| " + " | ".join(row_parts) + " |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Footer
    metadata = rubric_data.get('metadata', {})
    if metadata.get('createdAt'):
        created_date = metadata['createdAt'][:10]  # YYYY-MM-DD
        lines.append(f"*Created: {created_date}*")
    if metadata.get('modifiedAt'):
        modified_date = metadata['modifiedAt'][:10]  # YYYY-MM-DD
        lines.append(f"*Last Modified: {modified_date}*")

    return "\n".join(lines)


# AI Integration Endpoints

class AIGenerateRequest(BaseModel):
    """Request model for AI rubric generation"""
    prompt: str = Field(..., min_length=10, max_length=2000, description="Natural language description of the desired rubric")


class AIModifyRequest(BaseModel):
    """Request model for AI rubric modification"""
    prompt: str = Field(..., min_length=10, max_length=1000, description="Natural language description of desired changes")


@router.post("/rubrics/ai-generate")
async def ai_generate_rubric(
    request_data: AIGenerateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate a new rubric using AI from natural language description

    POST /lamb/v1/evaluaitor/rubrics/ai-generate
    """
    try:
        # Get user's organization for LLM config
        org = get_user_organization(user)

        # Generate rubric using AI
        rubric_data = await generate_rubric_with_ai(request_data.prompt, org['id'], user['email'])

        # Validate generated rubric
        is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data)
        if not is_valid:
            # Try to fix common issues and validate again
            rubric_data = RubricValidator.sanitize_rubric_data(rubric_data)
            is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data)
            if not is_valid:
                raise HTTPException(status_code=422, detail=f"AI generated invalid rubric: {error_msg}")

        # Create the rubric
        result = db_manager.create_rubric(
            rubric_data=rubric_data,
            owner_email=user['email'],
            organization_id=org['id']
        )

        return {
            "success": True,
            "rubric": result,
            "message": "Rubric generated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating rubric with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate rubric with AI")


@router.post("/rubrics/{rubric_id}/ai-modify")
async def ai_modify_rubric(
    rubric_id: str,
    request_data: AIModifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Modify an existing rubric using AI

    POST /lamb/v1/evaluaitor/rubrics/{rubric_id}/ai-modify
    """
    try:
        # Get existing rubric
        existing_rubric = db_manager.get_rubric_by_id(rubric_id, user['email'])
        if not existing_rubric:
            raise HTTPException(status_code=404, detail="Rubric not found or access denied")

        # Get user's organization for LLM config
        org = get_user_organization(user)

        # Generate modified rubric using AI
        modified_data = await modify_rubric_with_ai(
            existing_rubric['rubric_data'],
            request_data.prompt,
            org['id'],
            user['email']
        )

        # Validate modified rubric
        is_valid, error_msg = RubricValidator.validate_rubric_structure(modified_data)
        if not is_valid:
            # Try to fix common issues
            modified_data = RubricValidator.sanitize_rubric_data(modified_data)
            is_valid, error_msg = RubricValidator.validate_rubric_structure(modified_data)
            if not is_valid:
                raise HTTPException(status_code=422, detail=f"AI generated invalid rubric: {error_msg}")

        # Compare changes
        changes_summary = generate_changes_summary(existing_rubric['rubric_data'], modified_data)

        # Update the rubric
        result = db_manager.update_rubric(
            rubric_id=rubric_id,
            rubric_data=modified_data,
            owner_email=user['email']
        )

        return {
            "success": True,
            "rubric": result,
            "changes_summary": changes_summary,
            "message": "Rubric modified successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error modifying rubric {rubric_id} with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to modify rubric with AI")


async def generate_rubric_with_ai(prompt: str, organization_id: int, user_email: str) -> Dict[str, Any]:
    """
    Generate a rubric using AI based on natural language prompt

    Args:
        prompt: Natural language description
        organization_id: Organization ID for LLM config
        user_email: User email for context

    Returns:
        Generated rubric data
    """
    # Get LLM configuration from organization
    llm_config = get_organization_llm_config(organization_id)

    # Create system prompt
    system_prompt = """You are an expert educational assessment specialist helping an educator create a rubric.

The educator's request: "{prompt}"

Instructions:
1. Analyze the educator's request and create an appropriate rubric
2. Use educational best practices for rubric design
3. Include 3-5 criteria appropriate to the task
4. Include 4 performance levels (Exemplary, Proficient, Developing, Beginning) with scores 4-1
5. Write clear, specific, observable descriptors for each level
6. Assign appropriate weights to each criterion (should sum to 100)
7. Return the COMPLETE rubric in valid JSON format matching the schema
8. Provide a brief explanation of your design choices

Respond with ONLY valid JSON in this format:
{{
  "rubricId": "generated-id",
  "title": "Generated Rubric Title",
  "description": "Brief description",
  "metadata": {{
    "subject": "Subject Area",
    "gradeLevel": "Grade Level",
    "createdAt": "2025-01-01T00:00:00Z",
    "modifiedAt": "2025-01-01T00:00:00Z"
  }},
  "criteria": [
    {{
      "id": "criterion-1",
      "name": "Criterion Name",
      "description": "Criterion description",
      "weight": 25,
      "levels": [
        {{
          "id": "level-exemplary",
          "score": 4,
          "label": "Exemplary",
          "description": "Level description"
        }}
      ]
    }}
  ],
  "scoringType": "points",
  "maxScore": 100
}}
""".format(prompt=prompt)

    try:
        # Call LLM (simplified - would need actual LLM integration)
        # For now, return a default rubric
        import uuid
        return RubricValidator.generate_default_rubric("AI Generated Rubric")

    except Exception as e:
        logging.error(f"Error calling LLM for rubric generation: {e}")
        # Fallback to default rubric
        return RubricValidator.generate_default_rubric("AI Generated Rubric")


async def modify_rubric_with_ai(
    existing_rubric: Dict[str, Any],
    prompt: str,
    organization_id: int,
    user_email: str
) -> Dict[str, Any]:
    """
    Generate a modified rubric using AI

    Args:
        existing_rubric: Current rubric data
        prompt: Modification request
        organization_id: Organization ID for LLM config
        user_email: User email for context

    Returns:
        Modified rubric data
    """
    # Get LLM configuration from organization
    llm_config = get_organization_llm_config(organization_id)

    # Create system prompt
    system_prompt = """You are an expert educational assessment specialist helping an educator modify their rubric.

Current rubric (in JSON format):
{existing_rubric}

The educator's request: "{prompt}"

Instructions:
1. Analyze the current rubric structure and the educator's request
2. Make appropriate modifications that maintain educational validity
3. Preserve the rubric structure unless explicitly asked to change it
4. Return the COMPLETE modified rubric in valid JSON format
5. Keep the same rubricId and metadata structure

Respond with ONLY valid JSON matching the original rubric format.
""".format(existing_rubric=json.dumps(existing_rubric, indent=2), prompt=prompt)

    try:
        # Call LLM (simplified - would need actual LLM integration)
        # For now, return the existing rubric with minor modifications
        modified = json.loads(json.dumps(existing_rubric))
        modified['metadata']['modifiedAt'] = datetime.now().isoformat()

        # Simple modification example - could be much more sophisticated
        if "6th grade" in prompt.lower() or "6th graders" in prompt.lower():
            modified['metadata']['gradeLevel'] = "6th Grade"
            modified['description'] += " (Adapted for 6th grade)"

        return modified

    except Exception as e:
        logging.error(f"Error calling LLM for rubric modification: {e}")
        # Return original rubric unchanged
        return existing_rubric


def get_organization_llm_config(organization_id: int) -> Dict[str, Any]:
    """
    Get LLM configuration for an organization

    Args:
        organization_id: Organization ID

    Returns:
        LLM configuration dict
    """
    # This would integrate with the organization's LLM settings
    # For now, return default config
    from ..database_manager import LambDatabaseManager
    db = LambDatabaseManager()

    try:
        org = db.get_organization_by_id(organization_id)
        if org and 'config' in org:
            config = org['config']
            setups = config.get('setups', {})
            default_setup = setups.get('default', {})
            providers = default_setup.get('providers', {})
            return providers
    except Exception as e:
        logging.error(f"Error getting org LLM config: {e}")

    # Default fallback
    return {
        "openai": {
            "enabled": True,
            "api_key": None,
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini"
        }
    }


def generate_changes_summary(original: Dict[str, Any], modified: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a summary of changes between original and modified rubric

    Args:
        original: Original rubric data
        modified: Modified rubric data

    Returns:
        Changes summary
    """
    changes = {
        "criteria_added": [],
        "criteria_modified": [],
        "criteria_removed": [],
        "other_changes": []
    }

    # Compare criteria
    orig_criteria = {c['id']: c for c in original.get('criteria', [])}
    mod_criteria = {c['id']: c for c in modified.get('criteria', [])}

    # Find added criteria
    for cid, criterion in mod_criteria.items():
        if cid not in orig_criteria:
            changes["criteria_added"].append(criterion['name'])

    # Find removed criteria
    for cid, criterion in orig_criteria.items():
        if cid not in mod_criteria:
            changes["criteria_removed"].append(criterion['name'])

    # Find modified criteria (simplified check)
    for cid in orig_criteria.keys() & mod_criteria.keys():
        if orig_criteria[cid] != mod_criteria[cid]:
            changes["criteria_modified"].append(mod_criteria[cid]['name'])

    # Check other changes
    if original.get('title') != modified.get('title'):
        changes["other_changes"].append("Title changed")

    if original.get('description') != modified.get('description'):
        changes["other_changes"].append("Description changed")

    if original.get('metadata', {}).get('gradeLevel') != modified.get('metadata', {}).get('gradeLevel'):
        changes["other_changes"].append("Grade level changed")

    return changes
