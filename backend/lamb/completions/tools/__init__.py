# LAMB Tools Module
# This module contains tools that can be provided to LLMs for function calling
#
# Tool Registry provides a centralized place to register tools for LLM function calling.
# Each tool entry contains:
#   - spec: OpenAI-compatible function specification
#   - function: The async function to execute
#   - description: Human-readable description for the UI

from .weather import get_weather, WEATHER_TOOL_SPEC
from .moodle import get_moodle_courses, MOODLE_TOOL_SPEC

# Tool Registry - maps tool names to their specs and functions
TOOL_REGISTRY = {
    "weather": {
        "spec": WEATHER_TOOL_SPEC,
        "function": get_weather,
        "description": "Get current temperature for a city",
        "category": "utilities"
    },
    "moodle": {
        "spec": MOODLE_TOOL_SPEC,
        "function": get_moodle_courses,
        "description": "Get user's enrolled courses from Moodle LMS",
        "category": "lms"
    }
}


def get_tool_specs(tool_names: list = None) -> list:
    """
    Get OpenAI-compatible tool specifications for the given tool names.
    
    Args:
        tool_names: List of tool names to get specs for. If None, returns all.
        
    Returns:
        List of tool specification dicts
    """
    if tool_names is None:
        return [tool["spec"] for tool in TOOL_REGISTRY.values()]
    
    return [
        TOOL_REGISTRY[name]["spec"] 
        for name in tool_names 
        if name in TOOL_REGISTRY
    ]


def get_tool_function(tool_name: str):
    """
    Get the function for a specific tool.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        The tool function or None if not found
    """
    if tool_name in TOOL_REGISTRY:
        return TOOL_REGISTRY[tool_name]["function"]
    return None


def list_available_tools() -> list:
    """
    List all available tools with their metadata for the UI.
    
    Returns:
        List of dicts with tool info (name, description, category)
    """
    return [
        {
            "name": name,
            "description": tool["description"],
            "category": tool.get("category", "general"),
            "function_name": tool["spec"]["function"]["name"]
        }
        for name, tool in TOOL_REGISTRY.items()
    ]


__all__ = [
    'get_weather', 
    'WEATHER_TOOL_SPEC',
    'get_moodle_courses',
    'MOODLE_TOOL_SPEC',
    'TOOL_REGISTRY',
    'get_tool_specs',
    'get_tool_function',
    'list_available_tools'
]
