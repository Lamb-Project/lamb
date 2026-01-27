"""
Rubric RAG Processor
Retrieves rubric and injects as context for assessment-focused assistants
Supports both markdown and JSON formats for LLM context

Uses evaluation-optimized formats that include:
- Scoring instructions explaining how level scores (4,3,2,1) work
- Weight explanations (percentages summing to 100%)
- Score calculation formula
- Expected output format for the evaluation
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def rag_processor(
    messages: List[Dict[str, Any]],
    assistant=None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retrieve rubric and format as evaluation context (markdown or JSON)
    
    Uses evaluation-optimized formats that help the LLM understand:
    - How to interpret performance level scores
    - How to apply criterion weights (percentages)
    - How to calculate the final weighted score
    - What output format to use for the evaluation

    Args:
        messages: List of conversation messages
        assistant: Assistant object with metadata
        request: Optional original request payload (unused by this processor)

    Returns:
        Dict with:
            - "context": str (formatted rubric with evaluation instructions)
            - "sources": List[Dict] (rubric metadata for citation)
    """
    try:
        # Extract rubric_id and format from assistant metadata
        rubric_id = None
        rubric_format = "markdown"  # Default format

        metadata = None
        if assistant and hasattr(assistant, 'metadata'):
            metadata_str = assistant.metadata
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse assistant metadata")

        # Also check api_callback field (where metadata is actually stored)
        if not metadata and assistant and hasattr(assistant, 'api_callback'):
            metadata_str = assistant.api_callback
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse assistant api_callback")

        if metadata:
            rubric_id = metadata.get('rubric_id')
            rubric_format = metadata.get('rubric_format', 'markdown')

        if not rubric_id:
            logger.warning("No rubric_id found in assistant metadata")
            return {
                "context": "",
                "sources": []
            }

        # Validate format
        if rubric_format not in ['markdown', 'json']:
            logger.warning(f"Invalid rubric_format '{rubric_format}', defaulting to markdown")
            rubric_format = 'markdown'

        # Get rubric from database
        from lamb.evaluaitor.rubric_database import RubricDatabaseManager
        from lamb.evaluaitor.rubric_service import (
            generate_rubric_evaluation_markdown,
            generate_rubric_evaluation_json
        )

        db_manager = RubricDatabaseManager()

        # Get rubric by ID
        # Note: We need owner_email for permission check, use assistant owner
        owner_email = getattr(assistant, 'owner', None)
        if not owner_email:
            logger.error("Assistant has no owner")
            return {"context": "", "sources": []}

        rubric = db_manager.get_rubric_by_id(rubric_id, owner_email)

        if not rubric:
            logger.error(f"Rubric {rubric_id} not found or not accessible")
            return {
                "context": "ERROR: Rubric not found or not accessible",
                "sources": []
            }

        # Extract rubric data
        rubric_data = rubric.get('rubric_data')
        if isinstance(rubric_data, str):
            rubric_data = json.loads(rubric_data)

        # Format according to user preference using evaluation-optimized formats
        if rubric_format == 'json':
            # Format as JSON with evaluation instructions wrapper
            context = generate_rubric_evaluation_json(rubric_data)
        else:
            # Format as markdown with scoring instructions (default)
            context = generate_rubric_evaluation_markdown(rubric_data)

        # Prepare source citation
        sources = [{
            "type": "rubric",
            "rubric_id": rubric_id,
            "title": rubric.get('title', 'Unknown Rubric'),
            "description": rubric.get('description', ''),
            "format": rubric_format
        }]

        logger.info(f"Successfully retrieved rubric {rubric_id} as {rubric_format} evaluation context")

        return {
            "context": context,
            "sources": sources
        }

    except Exception as e:
        logger.error(f"Error in rubric_rag processor: {e}", exc_info=True)
        return {
            "context": f"ERROR: Failed to load rubric - {str(e)}",
            "sources": []
        }
