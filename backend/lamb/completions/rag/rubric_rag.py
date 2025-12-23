"""
Rubric RAG Processor
Retrieves rubric and injects as context for assessment-focused assistants
Supports both markdown and JSON formats for LLM context
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
    Retrieve rubric and format as context (markdown or JSON)

    Args:
        messages: List of conversation messages
        assistant: Assistant object with metadata
        request: Optional original request payload (unused by this processor)

    Returns:
        Dict with:
            - "context": str (formatted rubric as markdown or JSON)
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
        from lamb.evaluaitor.rubric_service import generate_rubric_markdown

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

        # Format according to user preference
        if rubric_format == 'json':
            # Format as JSON string
            context = json.dumps(rubric_data, indent=2)
        else:
            # Format as markdown (default)
            context = generate_rubric_markdown(rubric_data)

        # Prepare source citation
        sources = [{
            "type": "rubric",
            "rubric_id": rubric_id,
            "title": rubric.get('title', 'Unknown Rubric'),
            "description": rubric.get('description', ''),
            "format": rubric_format
        }]

        logger.info(f"Successfully retrieved rubric {rubric_id} as {rubric_format} context")

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
