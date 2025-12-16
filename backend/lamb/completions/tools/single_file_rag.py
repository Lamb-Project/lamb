from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
import os
import json
import logging
from typing import Dict, Any, List
from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)


class SingleFileRagTool(BaseTool):
    """Tool for injecting the contents of a single file as context"""

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="single_file_rag",
            display_name="Single File Context",
            description="Injects the contents of a file as context",
            placeholder="file",  # Outputs to {file}
            category="file",
            config_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 50000}
                },
                "required": ["file_path"]
            }
        )

    def process(self, request: Dict[str, Any], assistant: Assistant, tool_config: Dict[str, Any]) -> ToolResult:
        """Read and return file contents as context"""

        try:
            # Extract configuration from tool_config
            file_path = tool_config.get("file_path")
            max_chars = tool_config.get("max_chars", 50000)

            if not file_path:
                return ToolResult(
                    placeholder="file",
                    content="Error: No file_path specified",
                    sources=[],
                    error="No file_path specified in tool configuration"
                )

            # Construct absolute path from project's static/public folder
            base_path = os.path.join('static', 'public')
            full_path = os.path.join(base_path, file_path)

            # Ensure the path doesn't escape the static/public directory
            if '..' in file_path or not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
                return ToolResult(
                    placeholder="file",
                    content="Error: Invalid file path",
                    sources=[],
                    error="Path attempts to escape base directory"
                )

            # Check if file exists
            if not os.path.exists(full_path):
                return ToolResult(
                    placeholder="file",
                    content=f"Error: File not found: {file_path}",
                    sources=[],
                    error=f"File not found: {file_path}"
                )

            # Read the file content
            with open(full_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Apply max_chars limit if specified
            if max_chars > 0 and len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[Content truncated at {max_chars} characters]"

            # Prepare source citation
            sources = [{
                "source": file_path,
                "content": content,
                "score": 1.0,
                "file_size": len(content)
            }]

            logger.debug(f"Successfully read {len(content)} characters from file: {file_path}")

            return ToolResult(
                placeholder="file",
                content=content,
                sources=sources
            )

        except Exception as e:
            logger.error(f"Error in SingleFileRagTool.process: {e}", exc_info=True)
            return ToolResult(
                placeholder="file",
                content=f"Error processing file: {str(e)}",
                sources=[],
                error=str(e)
            )


# Function interface for orchestrator
def tool_processor(request, assistant, tool_config):
    tool = SingleFileRagTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }


def get_definition():
    return SingleFileRagTool.get_definition()