from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from lamb.lamb_classes import Assistant


@dataclass
class ToolResult:
    """Standard result from tool execution"""
    placeholder: str                      # Placeholder name (e.g., "context")
    content: str                          # Content for the placeholder
    sources: List[Dict[str, Any]]         # Source citations
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ToolDefinition:
    """Tool metadata for registry and UI"""
    name: str                             # Unique identifier
    display_name: str                     # Human-readable name
    description: str                      # Description for UI
    placeholder: str                      # Template placeholder
    config_schema: Dict[str, Any]         # JSON Schema for tool config
    version: str = "1.0"
    category: str = "rag"                 # Category: rag, rubric, file, custom


class BaseTool(ABC):
    """Abstract base class for all tools"""

    @classmethod
    @abstractmethod
    def get_definition(cls) -> ToolDefinition:
        """Return tool metadata and configuration schema"""
        pass

    @abstractmethod
    def process(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_config: Dict[str, Any]
    ) -> ToolResult:
        """Execute the tool and return results"""
        pass

    def validate_config(self, tool_config: Dict[str, Any]) -> List[str]:
        """Validate tool configuration. Returns list of errors."""
        return []