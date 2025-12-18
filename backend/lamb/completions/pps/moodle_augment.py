"""
Moodle Augment Prompt Processor
This prompt processor extends simple_augment to support Moodle-aware placeholders:

- {moodle_user}: best-effort user identifier (prefers Moodle numeric ID when resolvable)
- {moodle_info_for_user}: formatted Moodle course context

User ID Extraction Priority:
1. request.__openwebui_headers__.x-openwebui-user-email (attempt to resolve to Moodle ID)
2. request.__openwebui_headers__.x-openwebui-user-id
3. request.metadata.user_id
4. request.metadata.lti_user_id
5. request.metadata.lis_person_sourcedid
6. request.metadata.email
7. "default" (fallback)
"""

from typing import Any, Dict, List, Optional

import json
import logging
import os

import httpx

from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)


def _moodle_ws_url(moodle_url: str) -> str:
    if "server.php" in moodle_url:
        return moodle_url
    return f"{moodle_url.rstrip('/')}/webservice/rest/server.php"


def _resolve_moodle_user_id_from_email(email: str) -> Optional[str]:
    """Best-effort mapping from email to Moodle numeric user ID."""
    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not (moodle_url and moodle_token):
        return None

    ws_url = _moodle_ws_url(moodle_url)
    params = {
        "wstoken": moodle_token,
        "wsfunction": "core_user_get_users_by_field",
        "moodlewsrestformat": "json",
        "field": "email",
        "values[0]": email,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(ws_url, params=params)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list) and data and isinstance(data[0], dict) and "id" in data[0]:
            return str(data[0]["id"])
    except Exception as e:
        logger.warning(f"Unable to resolve Moodle user ID for email '{email}': {e}")

    return None


def _has_vision_capability(assistant: Assistant) -> bool:
    """
    Check if the assistant has vision capabilities enabled.

    Args:
        assistant: Assistant object with metadata

    Returns:
        bool: True if vision is enabled, False otherwise
    """
    if not assistant:
        return False

    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    if not metadata_str:
        return False

    try:
        metadata = json.loads(metadata_str)
        capabilities = metadata.get('capabilities', {})
        return capabilities.get('vision', False)
    except (json.JSONDecodeError, AttributeError):
        return False


def _extract_user_id(request: Dict[str, Any]) -> str:
    """
    Extract user ID from request headers/metadata.

    Returns:
        str: User ID or "default" if not found
    """
    openwebui_headers = request.get("__openwebui_headers__", {}) or {}

    email = openwebui_headers.get("x-openwebui-user-email") or openwebui_headers.get("X-OpenWebUI-User-Email")
    if email:
        resolved = _resolve_moodle_user_id_from_email(str(email))
        if resolved:
            return resolved
        return str(email)

    owui_user_id = openwebui_headers.get("x-openwebui-user-id") or openwebui_headers.get("X-OpenWebUI-User-Id")
    if owui_user_id:
        return str(owui_user_id)

    metadata = request.get("metadata", {}) or {}
    # Try various user identification fields
    user_id = (
        metadata.get('user_id') or
        metadata.get('lti_user_id') or
        metadata.get('lis_person_sourcedid') or
        metadata.get('email') or
        metadata.get('user') or
        None
    )

    if user_id:
        return str(user_id)

    return "default"


def _get_moodle_courses_sync(user_id: str) -> str:
    """Synchronous Moodle course lookup used by the prompt processor."""
    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not moodle_url or not moodle_token:
        return json.dumps({
            "user_id": user_id,
            "courses": [],
            "error": "MOODLE_API_URL and/or MOODLE_TOKEN not configured",
            "success": False,
        })

    ws_url = _moodle_ws_url(moodle_url)
    params = {
        "wstoken": moodle_token,
        "wsfunction": "core_enrol_get_users_courses",
        "moodlewsrestformat": "json",
        "userid": user_id,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(ws_url, params=params)
            response.raise_for_status()
            courses_data = response.json()

        if isinstance(courses_data, dict) and "exception" in courses_data:
            return json.dumps({
                "user_id": user_id,
                "error": courses_data.get("message", "Moodle API error"),
                "success": False,
            })

        courses = [
            {
                "id": course.get("id"),
                "name": course.get("fullname"),
                "shortname": course.get("shortname"),
                "category": course.get("categoryname", ""),
            }
            for course in (courses_data or [])
            if isinstance(course, dict)
        ]

        return json.dumps({
            "user_id": user_id,
            "courses": courses,
            "course_count": len(courses),
            "success": True,
            "source": "moodle_api",
        })
    except Exception as e:
        logger.error(f"Error getting Moodle courses for {user_id}: {e}")
        return json.dumps({
            "user_id": user_id,
            "courses": [],
            "error": str(e),
            "success": False,
        })

def _format_moodle_context(moodle_json: str) -> str:
    """
    Format Moodle course data into a human-readable string for the LLM.

    Args:
        moodle_json: JSON string from the Moodle tool

    Returns:
        Formatted string describing the user's courses
    """
    try:
        data = json.loads(moodle_json)

        if not data.get('success', False):
            error = data.get('error', 'Unknown error')
            return f"(Unable to retrieve course information: {error})"

        courses = data.get('courses', [])

        if not courses:
            return "(No enrolled courses found)"

        # Format course list
        course_lines = []
        for course in courses:
            name = course.get('name', 'Unknown Course')
            shortname = course.get('shortname', '')
            category = course.get('category', '')
            role = course.get('role', 'student')

            line = f"- {name}"
            if shortname:
                line += f" ({shortname})"
            if category:
                line += f" - {category}"
            if role and role != 'student':
                line += f" [Role: {role}]"

            course_lines.append(line)

        course_count = len(courses)
        header = f"Enrolled in {course_count} course{'s' if course_count != 1 else ''}:"

        return header + "\n" + "\n".join(course_lines)

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Moodle JSON: {e}")
        return "(Error parsing course information)"


def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Moodle-aware prompt processor that extends simple_augment.

    Supports all placeholders from simple_augment plus:
    - {moodle_user}
    - {moodle_info_for_user}
    """
    logger.debug("moodle_augment: Starting prompt processing")

    messages = request.get("messages", [])
    if not messages:
        return messages

    last_message = messages[-1]["content"]
    processed_messages: List[Dict[str, str]] = []

    if not assistant:
        return messages

    if assistant.system_prompt:
        processed_messages.append({"role": "system", "content": assistant.system_prompt})

    processed_messages.extend(messages[:-1])

    if not assistant.prompt_template:
        processed_messages.append(messages[-1])
        return processed_messages

    template = assistant.prompt_template
    uses_moodle_user = "{moodle_user}" in template
    uses_moodle_info = "{moodle_info_for_user}" in template

    moodle_user = ""
    moodle_context = ""
    if uses_moodle_user or uses_moodle_info:
        moodle_user = _extract_user_id(request)
        if uses_moodle_info:
            moodle_json = _get_moodle_courses_sync(moodle_user)
            moodle_context = _format_moodle_context(moodle_json)

    has_vision = _has_vision_capability(assistant)

    if isinstance(last_message, list) and has_vision:
        augmented_content = []
        text_parts = [item.get("text", "") for item in last_message if item.get("type") == "text"]
        user_input_text = " ".join(text_parts)

        augmented_text = template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")
        if uses_moodle_user:
            augmented_text = augmented_text.replace("{moodle_user}", moodle_user)
        if uses_moodle_info:
            augmented_text = augmented_text.replace("{moodle_info_for_user}", moodle_context)

        if rag_context:
            context = json.dumps(rag_context)
            augmented_text = augmented_text.replace("{context}", "\n\n" + context + "\n\n")
        else:
            augmented_text = augmented_text.replace("{context}", "")

        augmented_content.append({"type": "text", "text": augmented_text})
        for item in last_message:
            if item.get("type") != "text":
                augmented_content.append(item)

        processed_messages.append({"role": messages[-1]["role"], "content": augmented_content})
        logger.debug("moodle_augment: Prompt processing complete")
        return processed_messages

    if isinstance(last_message, list):
        user_input_text = " ".join(
            [item.get("text", "") for item in last_message if item.get("type") == "text"]
        )
    else:
        user_input_text = str(last_message)

    prompt = template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")
    if uses_moodle_user:
        prompt = prompt.replace("{moodle_user}", moodle_user)
    if uses_moodle_info:
        prompt = prompt.replace("{moodle_info_for_user}", moodle_context)

    if rag_context:
        context = json.dumps(rag_context)
        prompt = prompt.replace("{context}", "\n\n" + context + "\n\n")
    else:
        prompt = prompt.replace("{context}", "")

    processed_messages.append({"role": messages[-1]["role"], "content": prompt})
    logger.debug("moodle_augment: Prompt processing complete")
    return processed_messages
