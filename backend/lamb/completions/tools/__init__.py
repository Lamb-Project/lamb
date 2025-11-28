# LAMB Tools Module
# This module contains tools that can be provided to LLMs for function calling

from .weather import get_weather, WEATHER_TOOL_SPEC

__all__ = ['get_weather', 'WEATHER_TOOL_SPEC']
