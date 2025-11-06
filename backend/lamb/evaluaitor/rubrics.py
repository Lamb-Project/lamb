"""
LAMB Core API for Rubrics
Provides REST endpoints for rubric CRUD operations, import/export, and AI assistance.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..owi_bridge.owi_users import OwiUserManager
from .rubric_database import RubricDatabaseManager
from .rubric_validator import RubricValidator


# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Helper functions

def ensure_criterion_ids(criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure all criteria and levels have unique IDs.
    Generates IDs if missing.
    
    Args:
        criteria: List of criterion dictionaries
        
    Returns:
        List of criteria with IDs assigned
    """
    import uuid
    import time
    
    for i, criterion in enumerate(criteria):
        # Ensure criterion has an ID
        if 'id' not in criterion or not criterion['id']:
            criterion['id'] = f"criterion_{int(time.time())}_{i}_{str(uuid.uuid4())[:8]}"
        
        # Ensure levels have IDs
        if 'levels' in criterion and isinstance(criterion['levels'], list):
            for j, level in enumerate(criterion['levels']):
                if 'id' not in level or not level['id']:
                    level['id'] = f"level_{int(time.time())}_{i}_{j}_{str(uuid.uuid4())[:8]}"
    
    return criteria

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


# Authentication functions


# FastAPI dependency wrapper
async def get_current_user_dependency(authorization: str = Header(None)) -> Dict[str, Any]:
    """FastAPI dependency for getting current user"""
    logger.info(f"get_current_user_dependency called with authorization header: {authorization[:50] if authorization else None}")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    result = get_current_user_from_token(authorization)
    logger.info(f"get_current_user_dependency returning: {result}")
    return result


def get_current_user_from_token(auth_header: str) -> Dict[str, Any]:
    """Get current authenticated user from auth_header token"""
    try:
        # For MVP, trust the creator interface authentication
        # Extract email from auth_header (format: "Bearer {token}")
        # In production, this should validate the JWT token properly
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            logger.info(f"Authenticating with token: {token[:50]}...")
            try:
                import jwt
                # Decode token without verification for MVP (trust creator interface)
                payload = jwt.decode(token, options={"verify_signature": False})
                logger.info(f"Token payload: {payload}")
                user_id = payload.get("id") or payload.get("sub")
                logger.info(f"Extracted user_id: {user_id}")
                if not user_id:
                    logger.error("No id in token payload")
                    raise HTTPException(status_code=401, detail="No user id in token")
            except Exception as e:
                logger.error(f"Token decode error: {e}")
                raise HTTPException(status_code=401, detail="Invalid token format")
        else:
            logger.error(f"Invalid auth_header format: {auth_header}")
            raise HTTPException(status_code=401, detail="Invalid auth_header format")

        # Look up OWI user to get email
        from ..owi_bridge.owi_users import OwiUserManager
        owi_user_manager = OwiUserManager()
        owi_user = owi_user_manager.get_user_by_id(user_id)

        if not owi_user:
            logger.error(f"OWI user {user_id} not found")
            raise HTTPException(status_code=401, detail="User not found in authentication system")

        user_email = owi_user['email']

        # Look up creator user in LAMB database by email
        from ..database_manager import LambDatabaseManager
        db_manager = LambDatabaseManager()
        creator_user = db_manager.get_creator_user_by_email(user_email)

        if not creator_user:
            logger.error(f"LAMB creator user {user_email} not found")
            raise HTTPException(status_code=401, detail="User not registered in LAMB system")

        return creator_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


def get_user_organization(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get user's organization"""
    from ..database_manager import LambDatabaseManager
    db = LambDatabaseManager()

    # For MVP: if user has organization_id, use it; otherwise use system org
    if user.get('organization_id'):
        org = db.get_organization_by_id(user['organization_id'])
    else:
        # Use system organization
        org = db.get_organization_by_slug('lamb')  # Assuming 'lamb' is the system org slug

    if not org:
        # For MVP: return a mock organization if none found
        logger.warning(f"No organization found for user {user['id']}, using mock org")
        org = {
            'id': 1,
            'slug': 'lamb',
            'name': 'LAMB System Organization',
            'is_system': True,
            'status': 'active',
            'config': {}
        }

    return org


# CRUD Endpoints

@router.post("/rubrics", response_model=Dict[str, Any])
async def create_rubric(
    rubric_data: RubricCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
        
        # Ensure criteria have IDs (auto-generate if missing)
        criteria_with_ids = ensure_criterion_ids(rubric_data.criteria)
        
        full_rubric_data = {
            "rubricId": rubric_data.title.lower().replace(" ", "-") + "-" + str(int(datetime.now().timestamp())),
            "title": rubric_data.title,
            "description": rubric_data.description,
            "metadata": {
                **rubric_data.metadata,
                "createdAt": now,
                "modifiedAt": now
            },
            "criteria": criteria_with_ids,
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
    search: Optional[str] = Query(None)
    # Temporarily disabled: user: Dict[str, Any] = Depends(get_current_user_dependency)
):
    """
    List user's rubrics with optional filtering

    GET /lamb/v1/evaluaitor/rubrics
    """
    try:
        # For testing, use hardcoded admin user
        owner_email = "admin@owi.com"
        logger.info(f"Listing rubrics for hardcoded user: {owner_email}")

        # Build filters
        filters = {}
        if subject:
            filters['subject'] = subject
        if grade_level:
            filters['grade_level'] = grade_level

        # Get rubrics
        rubrics = db_manager.get_rubrics_by_owner(
            owner_email=owner_email,
            limit=limit,
            offset=offset,
            filters=filters
        )
        logger.info(f"Found {len(rubrics)} rubrics")

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            rubrics = [
                r for r in rubrics
                if search_lower in r['title'].lower() or search_lower in r['description'].lower()
            ]

        # Get total count
        total = db_manager.count_rubrics(owner_email, filters)

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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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

        # Get public rubrics (includes user's org + system org)
        rubrics = db_manager.get_public_rubrics(
            organization_id=org['id'],
            limit=limit,
            offset=offset,
            filters=filters,
            include_system_org=True
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


@router.get("/rubrics/accessible")
async def get_accessible_rubrics(
    auth_header: str = Query(None, alias="auth_header")
):
    """
    Get list of rubrics accessible to user for assistant attachment
    Returns user's own rubrics + public rubrics in organization
    
    Response format optimized for dropdown selector:
    {
      "success": true,
      "rubrics": [
        {
          "rubric_id": "rubric-123",
          "title": "Essay Writing Rubric",
          "description": "...",
          "is_mine": true,
          "is_showcase": false,
          "is_public": false
        }
      ],
      "total": 1
    }
    
    GET /lamb/v1/evaluaitor/rubrics/accessible
    """
    try:
        # Get user from auth_header
        user = get_current_user_from_token(auth_header)
        
        # Get user's organization
        org = get_user_organization(user)
        
        user_email = user.get('email')  # Note: LambDatabaseManager returns 'email', not 'user_email'
        organization_id = org.get('id')
        
        logging.info(f"Getting accessible rubrics for user: {user_email}, org: {organization_id}")
        
        # Get user's own rubrics
        my_rubrics = db_manager.get_rubrics_by_owner(
            owner_email=user_email,
            limit=1000,  # Get all
            offset=0,
            filters={}
        )
        
        logging.info(f"Found {len(my_rubrics)} rubrics owned by user")
        
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
        raise HTTPException(status_code=500, detail=f"Failed to get accessible rubrics: {str(e)}")


@router.get("/rubrics/showcase", response_model=List[Dict[str, Any]])
async def list_showcase_rubrics(
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    auth_header: str = Query(None, alias="auth_header")  # Optional for backward compatibility
):
    """
    Get a specific rubric by ID

    GET /lamb/v1/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # For testing, use hardcoded admin user
        owner_email = "admin@owi.com"
        logger.info(f"Getting rubric {rubric_id} for hardcoded user: {owner_email}")

        # Get rubric with access control (simplified for testing)
        rubric = db_manager.get_rubric_by_id(rubric_id, owner_email)

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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
):
    """
    Update an existing rubric

    PUT /lamb/v1/evaluaitor/rubrics/{rubric_id}
    """
    try:
        # Verify rubric_id matches
        if rubric_data.rubricId != rubric_id:
            raise HTTPException(status_code=400, detail="Rubric ID mismatch")

        # Ensure criteria have IDs (auto-generate if missing)
        criteria_with_ids = ensure_criterion_ids(rubric_data.criteria)
        
        # Prepare full rubric data with updated timestamp
        full_rubric_data = {
            "rubricId": rubric_data.rubricId,
            "title": rubric_data.title,
            "description": rubric_data.description,
            "metadata": {
                **rubric_data.metadata,
                "modifiedAt": datetime.now().isoformat()
            },
            "criteria": criteria_with_ids,
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
):
    """
    Update rubric visibility (public/private)

    PUT /lamb/v1/evaluaitor/rubrics/{rubric_id}/visibility
    """
    try:
        # Check if sharing is enabled for the user's organization (only when making public, not private)
        if visibility_data.is_public:
            org = db_manager.get_user_organization(user['id'])
            if org:
                config = org.get('config', {})
                features = config.get('features', {})
                sharing_enabled = features.get('sharing_enabled', True)
                
                if not sharing_enabled:
                    raise HTTPException(
                        status_code=403,
                        detail="Sharing is not enabled for your organization"
                    )
        
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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
    user: Dict[str, Any] = Depends(get_current_user_dependency)
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

    # Get all unique level labels/scores from first criterion
    if criteria:
        first_criterion = criteria[0]
        levels = first_criterion.get('levels', [])

        # Table header
        header_parts = ["Criterion"]
        header_parts.extend([f"{level.get('label', '')} ({level.get('score', '')})" for level in levels])

        lines.append("| " + " | ".join(header_parts) + " |")
        lines.append("| " + " | ".join(["---"] * len(header_parts)) + " |")

        # Table rows
        for criterion in criteria:
            row_parts = []

            # Criterion cell: Name (weight pts)
            name = criterion.get('name', '')
            weight = criterion.get('weight', '')
            criterion_cell = f"**{name}**"
            if weight:
                criterion_cell += f" ({weight} pts)"
            row_parts.append(criterion_cell)

            # Level cells
            criterion_levels = criterion.get('levels', [])
            for i, level in enumerate(levels):
                level_desc = ""
                if i < len(criterion_levels):
                    level_desc = criterion_levels[i].get('description', '')
                row_parts.append(level_desc)

            lines.append("| " + " | ".join(row_parts) + " |")

        # Add criterion descriptions as a separate section
        lines.append("")
        lines.append("### Criterion Descriptions")
        lines.append("")
        for criterion in criteria:
            name = criterion.get('name', '')
            description = criterion.get('description', '')
            if description:
                lines.append(f"**{name}**: {description}")
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
    language: Optional[str] = Field(default='en', description="Language code for prompt template (en, es, eu, ca)")
    model: Optional[str] = Field(default=None, description="Optional specific model override")


class AIModifyRequest(BaseModel):
    """Request model for AI rubric modification"""
    prompt: str = Field(..., min_length=10, max_length=1000, description="Natural language description of desired changes")


@router.post("/rubrics/ai-generate")
async def ai_generate_rubric(
    request_data: AIGenerateRequest,
    auth_header: str = Query(None, alias="auth_header")
):
    """
    Generate a new rubric using AI from natural language description.
    
    NOTE: This endpoint returns the generated rubric for preview but does NOT save it.
    The frontend will display a preview with Accept/Reject options.
    Saving happens when user explicitly accepts the rubric.

    POST /lamb/v1/evaluaitor/rubrics/ai-generate
    
    Request:
        {
            "prompt": "User's natural language request",
            "language": "en" (optional: en, es, eu, ca),
            "model": "gpt-4o-mini" (optional override)
        }
    
    Response:
        {
            "success": true,
            "rubric": { ... complete rubric JSON ... },
            "markdown": "# Rubric Title\n\n...",
            "explanation": "AI's explanation of design choices",
            "prompt_used": "Complete prompt sent to LLM (for debugging)"
        }
    """
    try:
        # Authenticate user
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header required")
        
        user = get_current_user_from_token(auth_header)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        logger.info(f"AI generate rubric called by user {user['email']}, language={request_data.language}")
        logger.debug(f"User prompt: {request_data.prompt[:200]}...")

        # Import AI generator
        from .ai_generator import generate_rubric_ai
        
        # Generate rubric (does not save to database)
        result = generate_rubric_ai(
            user_prompt=request_data.prompt,
            user_email=user['email'],
            language=request_data.language or 'en',
            model=request_data.model
        )
        
        if result.get('success'):
            logger.info(f"Rubric generated successfully: {result.get('rubric', {}).get('title', 'Unknown')}")
        else:
            logger.warning(f"Rubric generation failed: {result.get('error', 'Unknown error')}")
        
        return result

    except Exception as e:
        logger.error(f"Error generating rubric with AI: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error generating rubric: {str(e)}",
            "allow_manual_edit": False
        }


@router.post("/rubrics/{rubric_id}/ai-modify")
async def ai_modify_rubric(
    rubric_id: str,
    request_data: AIModifyRequest,
    auth_header: str = Query(None, alias="auth_header")
):
    """
    Modify an existing rubric using AI

    POST /lamb/v1/evaluaitor/rubrics/{rubric_id}/ai-modify
    """
    try:
        # Authenticate user
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header required")
        
        user = get_current_user_from_token(auth_header)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
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
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    import uuid
    import json
    from datetime import datetime

    logger.info(f"generate_rubric_with_ai called with prompt: {prompt[:100]}..., org_id: {organization_id}, user: {user_email}")

    # Get organization-specific OpenAI configuration
    try:
        logger.info(f"Getting organization config for user {user_email}")
        config_resolver = OrganizationConfigResolver(user_email)
        openai_config = config_resolver.get_provider_config("openai")
        logger.info(f"OpenAI config retrieved: enabled={openai_config.get('enabled', True) if openai_config else False}")

        if not openai_config or not openai_config.get("enabled", True):
            logger.warning(f"OpenAI not enabled for user {user_email}, falling back to default rubric")
            return RubricValidator.generate_default_rubric("AI Generated Rubric")

        api_key = openai_config.get("api_key")
        base_url = openai_config.get("base_url", "https://api.openai.com/v1")
        model = openai_config.get("default_model", "gpt-4o-mini")
        logger.info(f"Using OpenAI config: base_url={base_url}, model={model}, has_api_key={bool(api_key)}")

        if not api_key:
            logger.warning(f"No OpenAI API key found for user {user_email}, falling back to default rubric")
            return RubricValidator.generate_default_rubric("AI Generated Rubric")

    except Exception as e:
        logger.error(f"Error getting OpenAI config for {user_email}: {e}, falling back to default rubric", exc_info=True)
        return RubricValidator.generate_default_rubric("AI Generated Rubric")

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
        logger.info("Creating OpenAI client and preparing API call")

        # Import OpenAI client
        from openai import AsyncOpenAI

        # Create OpenAI client with organization config
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        # Prepare messages for OpenAI API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a rubric based on this request: {prompt}"}
        ]

        logger.info(f"Calling OpenAI API with model {model} for rubric generation")
        logger.info(f"System prompt length: {len(system_prompt)} characters")
        logger.info(f"User message: {messages[1]['content'][:200]}...")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )

        logger.info("OpenAI API call completed successfully")

        # Extract response content
        content = response.choices[0].message.content.strip()
        logger.info(f"AI response length: {len(content)} characters")
        logger.info(f"AI response preview: {content[:200]}...")

        # Try to parse as JSON - be more robust with AI responses
        try:
            # First try to parse the entire response
            rubric_data = json.loads(content)
            logger.info("Successfully parsed AI-generated rubric JSON")
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            # Look for JSON object start and end
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_content = content[start_idx:end_idx]
                try:
                    rubric_data = json.loads(json_content)
                    logger.info("Successfully parsed AI-generated rubric JSON (extracted from response)")
                except json.JSONDecodeError as e2:
                    logger.error(f"Failed to parse extracted JSON: {e2}")
                    logger.error(f"Extracted content: {json_content[:500]}...")
                    raise ValueError("AI response contained invalid JSON structure")
            else:
                logger.error("No JSON object found in AI response")
                raise ValueError("AI response did not contain valid JSON")

            # Generate proper IDs and timestamps
            rubric_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Update the rubric with proper IDs and timestamps
            rubric_data['rubricId'] = rubric_id
            rubric_data['metadata']['createdAt'] = now
            rubric_data['metadata']['modifiedAt'] = now

            # Generate unique IDs for criteria and levels
            for i, criterion in enumerate(rubric_data.get('criteria', [])):
                criterion['id'] = f"criterion-{i+1}"
                for j, level in enumerate(criterion.get('levels', [])):
                    level['id'] = f"criterion-{i+1}-level-{j+1}"

            # Validate the generated rubric
            is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data)
            if not is_valid:
                logger.warning(f"AI-generated rubric validation failed: {error_msg}, attempting to fix")
                # Try to sanitize and validate again
                rubric_data = RubricValidator.sanitize_rubric_data(rubric_data)
                is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data)
                if not is_valid:
                    logger.error(f"Failed to fix AI-generated rubric: {error_msg}")
                    raise ValueError(f"Generated rubric is invalid: {error_msg}")

            return rubric_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"AI response content: {content[:500]}...")
            raise ValueError("AI response was not valid JSON")

    except Exception as e:
        logger.error(f"Error calling LLM for rubric generation: {e}")
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
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    import uuid
    import json
    from datetime import datetime

    # Get organization-specific OpenAI configuration
    try:
        config_resolver = OrganizationConfigResolver(user_email)
        openai_config = config_resolver.get_provider_config("openai")

        if not openai_config or not openai_config.get("enabled", True):
            logger.warning(f"OpenAI not enabled for user {user_email}, returning original rubric")
            return existing_rubric

        api_key = openai_config.get("api_key")
        base_url = openai_config.get("base_url", "https://api.openai.com/v1")
        model = openai_config.get("default_model", "gpt-4o-mini")

        if not api_key:
            logger.warning(f"No OpenAI API key found for user {user_email}, returning original rubric")
            return existing_rubric

    except Exception as e:
        logger.error(f"Error getting OpenAI config for {user_email}: {e}, returning original rubric")
        return existing_rubric

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
6. Update the modifiedAt timestamp
7. Ensure all criteria and levels have proper unique IDs

Respond with ONLY valid JSON matching the original rubric format.
""".format(existing_rubric=json.dumps(existing_rubric, indent=2), prompt=prompt)

    try:
        # Import OpenAI client
        from openai import AsyncOpenAI

        # Create OpenAI client with organization config
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        # Prepare messages for OpenAI API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Modify this rubric based on this request: {prompt}"}
        ]

        logger.info(f"Calling OpenAI API with model {model} for rubric modification")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )

        # Extract response content
        content = response.choices[0].message.content.strip()

        # Try to parse as JSON
        try:
            modified_rubric = json.loads(content)
            logger.info("Successfully parsed AI-modified rubric JSON")

            # Preserve original rubric ID and creation timestamp
            modified_rubric['rubricId'] = existing_rubric['rubricId']
            modified_rubric['metadata']['createdAt'] = existing_rubric['metadata']['createdAt']
            modified_rubric['metadata']['modifiedAt'] = datetime.now().isoformat()

            # Ensure proper IDs for criteria and levels
            for i, criterion in enumerate(modified_rubric.get('criteria', [])):
                criterion['id'] = f"criterion-{i+1}"
                for j, level in enumerate(criterion.get('levels', [])):
                    level['id'] = f"criterion-{i+1}-level-{j+1}"

            # Validate the modified rubric
            is_valid, error_msg = RubricValidator.validate_rubric_structure(modified_rubric)
            if not is_valid:
                logger.warning(f"AI-modified rubric validation failed: {error_msg}, attempting to fix")
                # Try to sanitize and validate again
                modified_rubric = RubricValidator.sanitize_rubric_data(modified_rubric)
                is_valid, error_msg = RubricValidator.validate_rubric_structure(modified_rubric)
                if not is_valid:
                    logger.error(f"Failed to fix AI-modified rubric: {error_msg}")
                    raise ValueError(f"Modified rubric is invalid: {error_msg}")

            return modified_rubric

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"AI response content: {content[:500]}...")
            raise ValueError("AI response was not valid JSON")

    except Exception as e:
        logger.error(f"Error calling LLM for rubric modification: {e}")
        # Return original rubric unchanged
        return existing_rubric




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


def format_rubric_as_markdown(rubric_data: dict) -> str:
    """
    Convert rubric JSON to markdown format for LLM context

    Args:
        rubric_data: Full rubric JSON structure

    Returns:
        Formatted markdown string
    """
    md = []

    # Header
    md.append(f"# {rubric_data.get('title', 'Rubric')}\n")
    md.append(f"**Description:** {rubric_data.get('description', '')}\n")

    # Metadata
    metadata = rubric_data.get('metadata', {})
    md.append(f"**Subject:** {metadata.get('subject', 'N/A')}")
    md.append(f"**Grade Level:** {metadata.get('gradeLevel', 'N/A')}")
    md.append(f"**Scoring Type:** {rubric_data.get('scoringType', 'points')}")
    md.append(f"**Maximum Score:** {rubric_data.get('maxScore', 100)}\n")
    md.append("---\n")

    # Criteria table
    md.append("## Assessment Criteria\n")

    criteria = rubric_data.get('criteria', [])
    if not criteria:
        md.append("*No criteria defined*\n")
        return "\n".join(md)

    # Sort criteria by order
    sorted_criteria = sorted(criteria, key=lambda c: c.get('order', 0))

    # Build table header
    # Get all unique levels across criteria (assume same levels for all)
    if sorted_criteria and sorted_criteria[0].get('levels'):
        first_criterion_levels = sorted(
            sorted_criteria[0]['levels'],
            key=lambda l: l.get('order', 0),
            reverse=True  # Higher scores first
        )

        header = "| Criterion |"
        for level in first_criterion_levels:
            label = level.get('label', 'Level')
            score = level.get('score', '')
            header += f" {label} ({score}) |"
        md.append(header)

        # Table separator
        separator = "|-----------|"
        for _ in first_criterion_levels:
            separator += "-------------|"
        md.append(separator)

    # Table rows (one per criterion)
    for criterion in sorted_criteria:
        name = criterion.get('name', 'Criterion')
        description = criterion.get('description', '')
        weight = criterion.get('weight', 0)

        # Start row with criterion name
        row = f"| **{name}**<br>*{description}*<br>({weight} points) |"

        # Add level descriptions
        levels = sorted(
            criterion.get('levels', []),
            key=lambda l: l.get('order', 0),
            reverse=True
        )
        for level in levels:
            desc = level.get('description', '')
            row += f" {desc} |"

        md.append(row)

    md.append("\n---\n")
    md.append("*Created: {created_at}*")
    md.append("*Last Modified: {modified_at}*\n")
    md.append("*Use the criteria and level descriptions above to guide assessment and feedback.*")

    return "\n".join(md)
