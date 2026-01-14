"""
Rubric Service - Business Logic Layer
Contains reusable functions for rubric operations, separate from HTTP endpoints.
"""

import json
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .rubric_database import RubricDatabaseManager
from .rubric_validator import RubricValidator
from lamb.logging_config import get_logger

# Set up logger
logger = get_logger(__name__, component="EVALUATOR")


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


# Business Logic Functions

def create_rubric_logic(
    title: str,
    description: str,
    metadata: Dict[str, Any],
    criteria: List[Dict[str, Any]],
    scoring_type: str,
    max_score: float,
    user_email: str,
    organization_id: int
) -> Dict[str, Any]:
    """
    Create a new rubric
    
    Args:
        title: Rubric title
        description: Rubric description
        metadata: Additional metadata (subject, gradeLevel, etc.)
        criteria: List of criteria with levels
        scoring_type: Type of scoring (points, percentage, etc.)
        max_score: Maximum score
        user_email: Owner's email
        organization_id: Organization ID
        
    Returns:
        Created rubric data with success flag
        
    Raises:
        ValueError: If validation fails
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Prepare full rubric data
        now = datetime.now().isoformat()
        
        # Ensure criteria have IDs (auto-generate if missing)
        criteria_with_ids = ensure_criterion_ids(criteria)
        
        full_rubric_data = {
            "rubricId": title.lower().replace(" ", "-") + "-" + str(int(datetime.now().timestamp())),
            "title": title,
            "description": description,
            "metadata": {
                **metadata,
                "createdAt": now,
                "modifiedAt": now
            },
            "criteria": criteria_with_ids,
            "scoringType": scoring_type,
            "maxScore": max_score
        }

        # Validate rubric structure
        is_valid, error_msg = RubricValidator.validate_rubric_structure(full_rubric_data)
        if not is_valid:
            raise ValueError(f"Invalid rubric structure: {error_msg}")

        # Create rubric
        result = db_manager.create_rubric(
            rubric_data=full_rubric_data,
            owner_email=user_email,
            organization_id=organization_id
        )

        return {
            "success": True,
            "rubric": result
        }

    except Exception as e:
        logger.error(f"Error creating rubric: {e}")
        raise


def update_rubric_logic(
    rubric_id: str,
    title: str,
    description: str,
    metadata: Dict[str, Any],
    criteria: List[Dict[str, Any]],
    scoring_type: str,
    max_score: float,
    user_email: str
) -> Dict[str, Any]:
    """
    Update an existing rubric
    
    Args:
        rubric_id: Rubric ID
        title: Rubric title
        description: Rubric description
        metadata: Additional metadata
        criteria: List of criteria with levels
        scoring_type: Type of scoring
        max_score: Maximum score
        user_email: Owner's email
        
    Returns:
        Updated rubric data
        
    Raises:
        ValueError: If validation fails
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Ensure criteria have IDs (auto-generate if missing)
        criteria_with_ids = ensure_criterion_ids(criteria)
        
        # Prepare full rubric data with updated timestamp
        full_rubric_data = {
            "rubricId": rubric_id,
            "title": title,
            "description": description,
            "metadata": {
                **metadata,
                "modifiedAt": datetime.now().isoformat()
            },
            "criteria": criteria_with_ids,
            "scoringType": scoring_type,
            "maxScore": max_score
        }

        # Validate rubric structure
        is_valid, error_msg = RubricValidator.validate_rubric_structure(full_rubric_data)
        if not is_valid:
            raise ValueError(f"Invalid rubric structure: {error_msg}")

        # Update rubric
        result = db_manager.update_rubric(
            rubric_id=rubric_id,
            rubric_data=full_rubric_data,
            owner_email=user_email
        )

        return result

    except Exception as e:
        logger.error(f"Error updating rubric {rubric_id}: {e}")
        raise


def get_rubric_logic(rubric_id: str, user_email: str) -> Dict[str, Any]:
    """
    Get a specific rubric by ID
    
    Args:
        rubric_id: Rubric ID
        user_email: User's email for access control
        
    Returns:
        Rubric data
        
    Raises:
        ValueError: If rubric not found
    """
    try:
        db_manager = RubricDatabaseManager()
        
        rubric = db_manager.get_rubric_by_id(rubric_id, user_email)

        if not rubric:
            raise ValueError("Rubric not found or access denied")

        return rubric

    except Exception as e:
        logger.error(f"Error getting rubric {rubric_id}: {e}")
        raise


def list_rubrics_logic(
    user_email: str,
    limit: int = 10,
    offset: int = 0,
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    List user's rubrics with optional filtering
    
    Args:
        user_email: Owner's email
        limit: Maximum number of results
        offset: Pagination offset
        subject: Filter by subject
        grade_level: Filter by grade level
        search: Search term
        
    Returns:
        Dictionary with rubrics list, total, limit, offset
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Build filters
        filters = {}
        if subject:
            filters['subject'] = subject
        if grade_level:
            filters['grade_level'] = grade_level

        # Get rubrics
        rubrics = db_manager.get_rubrics_by_owner(
            owner_email=user_email,
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        logger.info(f"Found {len(rubrics)} rubrics for {user_email}")

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            rubrics = [
                r for r in rubrics
                if search_lower in r['title'].lower() or search_lower in r['description'].lower()
            ]

        # Get total count
        total = db_manager.count_rubrics(user_email, filters)

        return {
            "rubrics": rubrics,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error listing rubrics: {e}")
        raise


def list_public_rubrics_logic(
    organization_id: int,
    limit: int = 10,
    offset: int = 0,
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    List public rubrics in user's organization
    
    Args:
        organization_id: User's organization ID
        limit: Maximum number of results
        offset: Pagination offset
        subject: Filter by subject
        grade_level: Filter by grade level
        search: Search term
        
    Returns:
        Dictionary with rubrics list, total, limit, offset
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Build filters
        filters = {}
        if subject:
            filters['subject'] = subject
        if grade_level:
            filters['grade_level'] = grade_level

        # Get public rubrics (includes user's org + system org)
        rubrics = db_manager.get_public_rubrics(
            organization_id=organization_id,
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

        # Get total count
        total = len(rubrics)  # Since we're filtering after, count actual results

        return {
            "rubrics": rubrics,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error listing public rubrics: {e}")
        raise


def delete_rubric_logic(rubric_id: str, user_email: str) -> bool:
    """
    Delete a rubric
    
    Args:
        rubric_id: Rubric ID
        user_email: Owner's email
        
    Returns:
        True if successful
        
    Raises:
        ValueError: If rubric not found
    """
    try:
        db_manager = RubricDatabaseManager()
        
        success = db_manager.delete_rubric(
            rubric_id=rubric_id,
            owner_email=user_email
        )

        if not success:
            raise ValueError("Rubric not found or access denied")

        return True

    except Exception as e:
        logger.error(f"Error deleting rubric {rubric_id}: {e}")
        raise


def duplicate_rubric_logic(rubric_id: str, user_email: str, organization_id: int) -> Dict[str, Any]:
    """
    Duplicate a rubric as template
    
    Args:
        rubric_id: Source rubric ID
        user_email: New owner's email
        organization_id: User's organization ID
        
    Returns:
        New rubric data with success flag
        
    Raises:
        ValueError: If source rubric not found
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Verify user can access the source rubric
        source_rubric = db_manager.get_rubric_by_id(rubric_id, user_email)
        if not source_rubric:
            raise ValueError("Source rubric not found or access denied")

        # Create duplicate
        new_rubric = db_manager.duplicate_rubric(
            rubric_id=rubric_id,
            new_owner_email=user_email
        )

        return {
            "success": True,
            "rubric": new_rubric
        }

    except Exception as e:
        logger.error(f"Error duplicating rubric {rubric_id}: {e}")
        raise


def update_rubric_visibility_logic(rubric_id: str, is_public: bool, user_email: str, user_id: int) -> Dict[str, bool]:
    """
    Update rubric visibility (public/private)
    
    Args:
        rubric_id: Rubric ID
        is_public: True to make public, False to make private
        user_email: Owner's email
        user_id: User ID for organization check
        
    Returns:
        Success status and new visibility
        
    Raises:
        ValueError: If rubric not found or sharing not enabled
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Check if sharing is enabled for the user's organization (only when making public, not private)
        if is_public:
            from ..database_manager import LambDatabaseManager
            lamb_db = LambDatabaseManager()
            org = lamb_db.get_user_organization(user_id)
            if org:
                config = org.get('config', {})
                features = config.get('features', {})
                sharing_enabled = features.get('sharing_enabled', True)
                
                if not sharing_enabled:
                    raise ValueError("Sharing is not enabled for your organization")
        
        # Update visibility
        success = db_manager.toggle_rubric_visibility(
            rubric_id=rubric_id,
            is_public=is_public,
            owner_email=user_email
        )

        if not success:
            raise ValueError("Rubric not found or access denied")

        return {"success": True, "is_public": is_public}

    except Exception as e:
        logger.error(f"Error updating rubric visibility {rubric_id}: {e}")
        raise


def import_rubric_logic(
    file_content: bytes,
    filename: str,
    user_email: str,
    organization_id: int
) -> Dict[str, Any]:
    """
    Import rubric from JSON file
    
    Args:
        file_content: File content as bytes
        filename: Original filename
        user_email: Owner's email
        organization_id: User's organization ID
        
    Returns:
        Imported rubric data with success flag
        
    Raises:
        ValueError: If file format is invalid
    """
    try:
        # Validate file type
        if not filename.endswith('.json'):
            raise ValueError("Only JSON files are supported")

        # Read file content
        rubric_json = file_content.decode('utf-8')

        # Validate and parse rubric
        is_valid, rubric_data, error_msg = RubricValidator.validate_imported_rubric(rubric_json)
        if not is_valid:
            raise ValueError(f"Invalid rubric format: {error_msg}")

        # Sanitize data
        rubric_data = RubricValidator.sanitize_rubric_data(rubric_data)

        # Create rubric with new ID and ownership
        rubric_data['rubricId'] = str(uuid.uuid4())
        rubric_data['metadata']['createdAt'] = datetime.now().isoformat()
        rubric_data['metadata']['modifiedAt'] = datetime.now().isoformat()

        # Create rubric (private by default)
        db_manager = RubricDatabaseManager()
        result = db_manager.create_rubric(
            rubric_data=rubric_data,
            owner_email=user_email,
            organization_id=organization_id,
            is_public=False
        )

        return {
            "success": True,
            "rubric": result,
            "message": "Rubric imported successfully"
        }

    except Exception as e:
        logger.error(f"Error importing rubric: {e}")
        raise


def export_rubric_json_logic(rubric_id: str, user_email: str) -> tuple[Dict[str, Any], str]:
    """
    Export rubric as JSON
    
    Args:
        rubric_id: Rubric ID
        user_email: User's email for access control
        
    Returns:
        Tuple of (rubric_data_dict, filename)
        
    Raises:
        ValueError: If rubric not found
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Get rubric
        rubric = db_manager.get_rubric_by_id(rubric_id, user_email)
        if not rubric:
            raise ValueError("Rubric not found or access denied")

        # Prepare filename
        title_slug = rubric['title'].lower().replace(' ', '-').replace('/', '-')
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{title_slug}-{timestamp}.json"

        return (rubric['rubric_data'], filename)

    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as JSON: {e}")
        raise


def export_rubric_markdown_logic(rubric_id: str, user_email: str) -> tuple[str, str]:
    """
    Export rubric as Markdown document
    
    Args:
        rubric_id: Rubric ID
        user_email: User's email for access control
        
    Returns:
        Tuple of (markdown_content, filename)
        
    Raises:
        ValueError: If rubric not found
    """
    try:
        db_manager = RubricDatabaseManager()
        
        # Get rubric
        rubric = db_manager.get_rubric_by_id(rubric_id, user_email)
        if not rubric:
            raise ValueError("Rubric not found or access denied")

        # Generate Markdown content
        markdown_content = generate_rubric_markdown(rubric['rubric_data'])

        # Prepare filename
        title_slug = rubric['title'].lower().replace(' ', '-').replace('/', '-')
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{title_slug}-{timestamp}.md"

        return (markdown_content, filename)

    except Exception as e:
        logger.error(f"Error exporting rubric {rubric_id} as markdown: {e}")
        raise


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

        # Table rows (one row per criterion)
        for criterion in criteria:
            row_parts = [criterion.get('name', '')]
            for level in criterion.get('levels', []):
                row_parts.append(level.get('description', ''))
            lines.append("| " + " | ".join(row_parts) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)

