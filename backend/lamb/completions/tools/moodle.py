"""
Moodle Tool for LAMB Assistants

This tool provides integration with Moodle LMS to retrieve user course information.
Currently implements mock data; future versions will integrate with actual Moodle Web Services API.

Phase 1: Mock data implementation
Phase 2: Real Moodle Web Services API integration (using core_enrol_get_users_courses)
"""

import json
import logging
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

# Mock course data for different users (Phase 1)
MOCK_USER_COURSES = {
    "student1": [
        {"id": 101, "name": "Introduction to Programming", "shortname": "CS101", "category": "Computer Science"},
        {"id": 102, "name": "Data Structures", "shortname": "CS201", "category": "Computer Science"},
        {"id": 103, "name": "Web Development", "shortname": "WEB101", "category": "Computer Science"}
    ],
    "admin@owi.com": [
        {"id": 201, "name": "Calculus I", "shortname": "MATH101", "category": "Mathematics"},
        {"id": 202, "name": "Linear Algebra", "shortname": "MATH201", "category": "Mathematics"},
        {"id": 103, "name": "Web Development", "shortname": "WEB101", "category": "Computer Science"}
    ],
    "instructor1": [
        {"id": 101, "name": "Introduction to Programming", "shortname": "CS101", "category": "Computer Science", "role": "instructor"},
        {"id": 301, "name": "Advanced Algorithms", "shortname": "CS401", "category": "Computer Science", "role": "instructor"}
    ],
    # Default courses for unknown users
    "default": [
        {"id": 101, "name": "Introduction to Programming", "shortname": "CS101", "category": "Computer Science"},
        {"id": 102, "name": "Data Structures", "shortname": "CS201", "category": "Computer Science"},
        {"id": 103, "name": "Web Development", "shortname": "WEB101", "category": "Computer Science"}
    ]
}


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
    user_id_lower = user_id.lower().strip()
    
    # Get courses for user (or default if not found)
    courses = MOCK_USER_COURSES.get(user_id_lower, MOCK_USER_COURSES["default"])
    
    result = {
        "user_id": user_id,
        "courses": courses,
        "course_count": len(courses),
        "success": True,
        "source": "mock"  # Indicates this is mock data
    }
    
    logger.info(f"Retrieved {len(courses)} courses for Moodle user '{user_id}'")
    return json.dumps(result)


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
        # Moodle Web Services endpoint
        ws_url = f"{moodle_url}/webservice/rest/server.php"
        
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
