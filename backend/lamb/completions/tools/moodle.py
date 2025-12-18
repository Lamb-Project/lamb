"""
Moodle Tool for LAMB Assistants

This tool provides integration with Moodle LMS to retrieve user course information
via Moodle Web Services (`core_enrol_get_users_courses`).
"""

import json
import logging
import os
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# OpenAI Function Calling specification for the Moodle tool
MOODLE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "get_moodle_courses",
        "description": "Get the list of courses a user is enrolled in from Moodle LMS",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The Moodle user identifier (username or ID)"
                }
            },
            "required": ["user_id"]
        }
    }
}

async def get_moodle_courses(user_id: str) -> str:
    """
    Get courses for a Moodle user.

    Requires `MOODLE_API_URL` and `MOODLE_TOKEN` to be configured.
    Args:
        user_id: The Moodle user identifier (username or ID)
        
    Returns:
        JSON string with course information or error message
    """
    # Get Moodle config from environment
    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not moodle_url or not moodle_token:
        logger.error("MOODLE_API_URL and/or MOODLE_TOKEN environment variable not set")
        return json.dumps({
            "user_id": user_id,
            "courses": [],
            "error": "MOODLE_API_URL and/or MOODLE_TOKEN not configured",
            "success": False,
        })

    return await get_moodle_courses_real(user_id=user_id, moodle_url=moodle_url, token=moodle_token)


async def get_moodle_courses_real(user_id: str, moodle_url: str, token: str) -> str:
    """
    Get courses for a Moodle user using the actual Moodle Web Services API.

    Uses the `core_enrol_get_users_courses` web service function.
    Args:
        user_id: The Moodle user identifier
        moodle_url: The Moodle instance URL
        token: The Moodle Web Services token
        
    Returns:
        JSON string with course information or error message
    """
    try:
        # Moodle Web Services endpoint
        # Support either a full server.php URL or a base Moodle URL.
        if "server.php" in moodle_url:
            ws_url = moodle_url
        else:
            ws_url = f"{moodle_url.rstrip('/')}/webservice/rest/server.php"
        
        params = {
            "wstoken": token,
            "wsfunction": "core_enrol_get_users_courses",
            "moodlewsrestformat": "json",
            "userid": user_id
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(ws_url, params=params, timeout=10.0)
            response.raise_for_status()
            
            courses_data = response.json()
            
            # Check for Moodle error response
            if isinstance(courses_data, dict) and "exception" in courses_data:
                return json.dumps({
                    "user_id": user_id,
                    "error": courses_data.get("message", "Moodle API error"),
                    "success": False
                })
            
            # Format courses
            courses = [
                {
                    "id": course.get("id"),
                    "name": course.get("fullname"),
                    "shortname": course.get("shortname"),
                    "category": course.get("categoryname", "")
                }
                for course in courses_data
            ]
            
            return json.dumps({
                "user_id": user_id,
                "courses": courses,
                "course_count": len(courses),
                "success": True,
                "source": "moodle_api"
            })
            
    except httpx.TimeoutException:
        logger.error(f"Timeout connecting to Moodle for user {user_id}")
        return json.dumps({
            "user_id": user_id,
            "error": "Moodle service timeout",
            "success": False
        })
    except Exception as e:
        logger.error(f"Error getting Moodle courses for {user_id}: {e}")
        return json.dumps({
            "user_id": user_id,
            "error": str(e),
            "success": False
        })


def get_moodle_courses_sync(user_id: str) -> str:
    """
    Synchronous version of get_moodle_courses for non-async contexts.
    """
    import asyncio
    return asyncio.run(get_moodle_courses(user_id))
