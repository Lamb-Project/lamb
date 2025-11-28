"""
Weather Tool for LAMB Assistants

This is a proof-of-concept tool that demonstrates how to provide
function calling capabilities to LLM-powered assistants.

For the POC, this uses a free weather API (Open-Meteo) that doesn't require an API key.
"""

import httpx
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# OpenAI Function Calling specification for the weather tool
WEATHER_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current temperature for a specified city. Returns temperature in Celsius.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city to get weather for (e.g., 'Paris', 'London', 'New York')"
                }
            },
            "required": ["city"]
        }
    }
}

# City coordinates for the weather API (Open-Meteo uses lat/lon)
CITY_COORDINATES = {
    "paris": {"lat": 48.8566, "lon": 2.3522, "name": "Paris, France"},
    "london": {"lat": 51.5074, "lon": -0.1278, "name": "London, UK"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "name": "New York, USA"},
    "tokyo": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo, Japan"},
    "sydney": {"lat": -33.8688, "lon": 151.2093, "name": "Sydney, Australia"},
    "berlin": {"lat": 52.5200, "lon": 13.4050, "name": "Berlin, Germany"},
    "madrid": {"lat": 40.4168, "lon": -3.7038, "name": "Madrid, Spain"},
    "rome": {"lat": 41.9028, "lon": 12.4964, "name": "Rome, Italy"},
    "amsterdam": {"lat": 52.3676, "lon": 4.9041, "name": "Amsterdam, Netherlands"},
    "singapore": {"lat": 1.3521, "lon": 103.8198, "name": "Singapore"},
}


async def get_weather(city: str) -> str:
    """
    Get the current temperature for a city using Open-Meteo API.
    
    Args:
        city: Name of the city (case-insensitive)
        
    Returns:
        JSON string with temperature information or error message
    """
    city_lower = city.lower().strip()
    
    # Find city coordinates
    if city_lower not in CITY_COORDINATES:
        # Default to Paris if city not found (for the POC)
        logger.warning(f"City '{city}' not found in database, defaulting to Paris")
        city_lower = "paris"
    
    coords = CITY_COORDINATES[city_lower]
    
    try:
        # Open-Meteo API - free, no API key required
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={coords['lat']}"
            f"&longitude={coords['lon']}"
            f"&current=temperature_2m,weather_code"
            f"&timezone=auto"
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            current = data.get("current", {})
            temperature = current.get("temperature_2m")
            weather_code = current.get("weather_code", 0)
            
            # Convert weather code to description
            weather_descriptions = {
                0: "clear sky",
                1: "mainly clear", 2: "partly cloudy", 3: "overcast",
                45: "foggy", 48: "depositing rime fog",
                51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
                61: "slight rain", 63: "moderate rain", 65: "heavy rain",
                71: "slight snow", 73: "moderate snow", 75: "heavy snow",
                80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
                95: "thunderstorm",
            }
            weather_desc = weather_descriptions.get(weather_code, "unknown conditions")
            
            result = {
                "city": coords["name"],
                "temperature_celsius": temperature,
                "conditions": weather_desc,
                "success": True
            }
            
            logger.info(f"Weather for {coords['name']}: {temperature}°C, {weather_desc}")
            return json.dumps(result)
            
    except httpx.TimeoutException:
        error_result = {
            "city": coords["name"],
            "error": "Weather service timeout",
            "success": False
        }
        logger.error(f"Timeout getting weather for {city}")
        return json.dumps(error_result)
        
    except Exception as e:
        error_result = {
            "city": coords["name"],
            "error": str(e),
            "success": False
        }
        logger.error(f"Error getting weather for {city}: {e}")
        return json.dumps(error_result)


def get_weather_sync(city: str) -> str:
    """
    Synchronous version of get_weather for non-async contexts.
    """
    import asyncio
    return asyncio.run(get_weather(city))
