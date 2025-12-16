from typing import Dict, Any, List, Optional
from lamb.completions.tools.base import ToolDefinition
import importlib
import os
import glob
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for available multi-tool plugins"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._loaded = False
        return cls._instance

    def discover_tools(self) -> None:
        """Scan tools directory and register all tools"""
        if self._loaded:
            return

        tools_dir = os.path.join(os.path.dirname(__file__), "tools")
        tool_files = glob.glob(os.path.join(tools_dir, "*.py"))

        for tool_file in tool_files:
            if "__init__" in tool_file or "base" in tool_file:
                continue

            module_name = os.path.basename(tool_file)[:-3]

            try:
                module = importlib.import_module(f"lamb.completions.tools.{module_name}")

                if hasattr(module, "get_definition"):
                    definition = module.get_definition()
                    self._tools[definition.name] = {
                        "definition": definition,
                        "module": module
                    }
                    logger.info(f"Registered tool: {definition.name}")

            except Exception as e:
                logger.error(f"Failed to load tool {module_name}: {e}")

        self._loaded = True

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        self.discover_tools()
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        self.discover_tools()
        return self._tools.copy()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get definitions for all tools (for API/UI)"""
        self.discover_tools()
        definitions = []

        for name, tool_data in self._tools.items():
            definition = tool_data["definition"]
            definitions.append({
                "name": definition.name,
                "display_name": definition.display_name,
                "description": definition.description,
                "placeholder": definition.placeholder,
                "category": definition.category,
                "config_schema": definition.config_schema
            })

        return definitions


# Global instance
tool_registry = ToolRegistry()