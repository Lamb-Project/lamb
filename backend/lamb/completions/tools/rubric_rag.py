from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
import json
import logging
from typing import Dict, Any, List
from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)


class RubricRagTool(BaseTool):
    """Tool for injecting assessment rubrics as context"""

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="rubric_rag",
            display_name="Assessment Rubric",
            description="Injects a rubric for assessment-based responses",
            placeholder="rubric",  # Outputs to {rubric}
            category="rubric",
            config_schema={
                "type": "object",
                "properties": {
                    "rubric_id": {"type": "integer"},
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "default": "markdown"
                    }
                },
                "required": ["rubric_id"]
            }
        )

    def process(self, request: Dict[str, Any], assistant: Assistant, tool_config: Dict[str, Any]) -> ToolResult:
        """Load and format rubric as context"""

        try:
            # Extract configuration from tool_config
            rubric_id = tool_config.get("rubric_id")
            rubric_format = tool_config.get("format", "markdown")

            if not rubric_id:
                return ToolResult(
                    placeholder="rubric",
                    content="Error: No rubric_id specified",
                    sources=[],
                    error="No rubric_id specified in tool configuration"
                )

            # Validate format
            if rubric_format not in ['markdown', 'json']:
                logger.warning(f"Invalid rubric_format '{rubric_format}', defaulting to markdown")
                rubric_format = 'markdown'

            # Get owner for permission check
            owner_email = getattr(assistant, 'owner', None)
            if not owner_email:
                return ToolResult(
                    placeholder="rubric",
                    content="Error: Assistant has no owner",
                    sources=[],
                    error="Assistant has no owner"
                )

            # Get rubric from database
            from backend.lamb.evaluaitor.rubric_database import RubricDatabaseManager
            from backend.lamb.evaluaitor.rubrics import format_rubric_as_markdown

            db_manager = RubricDatabaseManager()
            rubric = db_manager.get_rubric_by_id(rubric_id, owner_email)

            if not rubric:
                return ToolResult(
                    placeholder="rubric",
                    content="ERROR: Rubric not found or not accessible",
                    sources=[],
                    error=f"Rubric {rubric_id} not found or not accessible"
                )

            # Extract rubric data
            rubric_data = rubric.get('rubric_data')
            if isinstance(rubric_data, str):
                rubric_data = json.loads(rubric_data)

            # Format according to user preference
            if rubric_format == 'json':
                # Format as JSON string
                content = json.dumps(rubric_data, indent=2)
            else:
                # Format as markdown (default)
                content = format_rubric_as_markdown(rubric_data)

            # Prepare source citation
            sources = [{
                "type": "rubric",
                "rubric_id": rubric_id,
                "title": rubric.get('title', 'Unknown Rubric'),
                "description": rubric.get('description', ''),
                "format": rubric_format
            }]

            logger.info(f"Successfully retrieved rubric {rubric_id} as {rubric_format} context")

            return ToolResult(
                placeholder="rubric",
                content=content,
                sources=sources
            )

        except Exception as e:
            logger.error(f"Error in RubricRagTool.process: {e}", exc_info=True)
            return ToolResult(
                placeholder="rubric",
                content=f"ERROR: Failed to load rubric - {str(e)}",
                sources=[],
                error=str(e)
            )


# Function interface for orchestrator
def tool_processor(request, assistant, tool_config):
    tool = RubricRagTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }


def get_definition():
    return RubricRagTool.get_definition()