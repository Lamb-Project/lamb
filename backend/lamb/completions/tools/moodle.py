"""
Moodle Tool for LAMB Assistants

This tool provides integration with Moodle LMS to retrieve user course information
via the Moodle Web Service API (core_enrol_get_users_courses). The function
`get_moodle_courses(user_id)` calls the configured Moodle instance using
environment variables `MOODLE_API_URL` and `MOODLE_TOKEN`.
"""

import json
import logging
import os
from typing import Optional

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

# Note: We now use the Moodle Webservice API via `core_enrol_get_users_courses`.
# This file no longer provides mock data; it uses the configured
# `MOODLE_API_URL` and `MOODLE_TOKEN` environment variables.


async def get_moodle_courses(user_id: str) -> str:
    """
    Get courses for a Moodle user.
    
    Phase 1: Return mocked data based on user_id
    Phase 2: Call actual Moodle Web Services API
    
    Args:
        user_id: The Moodle user identifier (username or ID)
        
    Returns:
        JSON string with course information or error message
    """
    # Get Moodle config from environment
    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not moodle_url or not moodle_token:
        logger.error("MOODLE_API_URL or MOODLE_TOKEN environment variable not set.")
        return json.dumps({
            "user_id": user_id,
            "error": "MOODLE_API_URL or MOODLE_TOKEN not configured",
            "success": False
        })

    # If the caller passes a non-numeric user_id (e.g. email), try to resolve it to a Moodle numeric ID
    # using the Moodle core_user_get_users_by_field API. If resolution fails, assume user_id is already an ID.
    numeric_user_id = user_id
    if not str(user_id).isdigit():
        import httpx
        try:
            params = {
                "wstoken": moodle_token,
                "wsfunction": "core_user_get_users_by_field",
                "moodlewsrestformat": "json",
                "field": "email",
                "values[0]": user_id
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(moodle_url, params=params, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list) and len(data) > 0 and "id" in data[0]:
                    numeric_user_id = str(data[0]["id"])
                    logger.info(f"Resolved Moodle user by email to id={numeric_user_id} for {user_id}")
        except Exception:
            # Fall through and leave numeric_user_id as passed; the core_enrol_get_users_courses call will fail
            logger.debug(f"Unable to resolve Moodle user from '{user_id}', attempting as-is")

    # Call the real Moodle API
    return await get_moodle_courses_real(numeric_user_id, moodle_url, moodle_token)


async def get_moodle_courses_real(user_id: str, moodle_url: str, token: str) -> str:
    """
    Get courses for a Moodle user using the actual Moodle Web Services API.
    
    This is a placeholder for Phase 2 implementation.
    Will use the core_enrol_get_users_courses web service function.
    
    Args:
        user_id: The Moodle user identifier
        moodle_url: The Moodle instance URL
        token: The Moodle Web Services token
        
    Returns:
        JSON string with course information or error message
    """
    import httpx
    
    try:
        # Moodle Web Services endpoint - assume `moodle_url` is already the full server.php ws URL
        ws_url = moodle_url
        
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
