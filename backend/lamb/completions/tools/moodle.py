"""Moodle tools for LAMB assistants.

Provides Moodle LMS integrations via Moodle Web Services.

- `get_moodle_courses`: enrolled courses for a user
- `get_moodle_assignments_status`: assignment completion/due/missed status
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


def _moodle_ws_url(moodle_url: str) -> str:
    if "server.php" in moodle_url:
        return moodle_url
    return f"{moodle_url.rstrip('/')}/webservice/rest/server.php"


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


async def _moodle_ws_get(
    ws_url: str,
    token: str,
    wsfunction: str,
    extra_params: List[Tuple[str, Any]],
    timeout_s: float = 15.0,
) -> Any:
    params: List[Tuple[str, Any]] = [
        ("wstoken", token),
        ("wsfunction", wsfunction),
        ("moodlewsrestformat", "json"),
    ]
    params.extend(extra_params)

    async with httpx.AsyncClient() as client:
        response = await client.get(ws_url, params=params, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()

    # Moodle error response shape
    if isinstance(data, dict) and "exception" in data:
        raise RuntimeError(data.get("message") or data.get("errorcode") or "Moodle API error")

    return data

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


MOODLE_ASSIGNMENTS_STATUS_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "get_moodle_assignments_status",
        "description": "Get Moodle assignment completion and due status for a user (completed, due, missed)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The Moodle user identifier (numeric ID)",
                },
                "days_past": {
                    "type": "integer",
                    "description": "How many days back to look for recently-due assignments (default 30)",
                    "minimum": 0,
                },
                "days_future": {
                    "type": "integer",
                    "description": "How many days ahead to look for upcoming assignments (default 30)",
                    "minimum": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of assignments to check submission status for (default 40)",
                    "minimum": 1,
                },
            },
            "required": ["user_id"],
        },
    },
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
    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not moodle_url or not moodle_token:
        logger.error("MOODLE_API_URL and/or MOODLE_TOKEN environment variable not set")
        return json.dumps(
            {
                "user_id": user_id,
                "courses": [],
                "error": "MOODLE_API_URL and/or MOODLE_TOKEN not configured",
                "success": False,
            }
        )

    return await get_moodle_courses_real(user_id=str(user_id).strip(), moodle_url=moodle_url, token=moodle_token)


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
        ws_url = _moodle_ws_url(moodle_url)

        courses_data = await _moodle_ws_get(
            ws_url,
            token,
            "core_enrol_get_users_courses",
            [("userid", user_id)],
            timeout_s=10.0,
        )

        courses = [
            {
                "id": course.get("id"),
                "name": course.get("fullname"),
                "shortname": course.get("shortname"),
                "category": course.get("categoryname", ""),
            }
            for course in (courses_data or [])
        ]

        return json.dumps(
            {
                "user_id": user_id,
                "courses": courses,
                "course_count": len(courses),
                "success": True,
                "source": "moodle_api",
            }
        )

    except httpx.TimeoutException:
        logger.error(f"Timeout connecting to Moodle for user {user_id}")
        return json.dumps({"user_id": user_id, "error": "Moodle service timeout", "success": False})
    except Exception as e:
        logger.error(f"Error getting Moodle courses for {user_id}: {e}")
        return json.dumps({"user_id": user_id, "error": str(e), "success": False})


def get_moodle_courses_sync(user_id: str) -> str:
    """
    Synchronous version of get_moodle_courses for non-async contexts.
    """
    return asyncio.run(get_moodle_courses(user_id))


async def get_moodle_assignments_status(
    user_id: str,
    days_past: int = 30,
    days_future: int = 30,
    limit: int = 40,
) -> str:
    """Return assignment completion/due/missed status for a user.

    Requires Moodle Web Services + a token that can call:
    - core_enrol_get_users_courses
    - mod_assign_get_assignments
    - mod_assign_get_submission_status
    """

    moodle_url = os.getenv("MOODLE_API_URL")
    moodle_token = os.getenv("MOODLE_TOKEN")

    if not moodle_url or not moodle_token:
        logger.error("MOODLE_API_URL and/or MOODLE_TOKEN environment variable not set")
        return json.dumps(
            {
                "user_id": user_id,
                "error": "MOODLE_API_URL and/or MOODLE_TOKEN not configured",
                "success": False,
            }
        )

    ws_url = _moodle_ws_url(moodle_url)
    resolved_user_id = str(user_id).strip()

    now_ts = _now_ts()
    window_start = now_ts - int(max(days_past, 0)) * 86400
    window_end = now_ts + int(max(days_future, 0)) * 86400

    try:
        courses_data = await _moodle_ws_get(
            ws_url,
            moodle_token,
            "core_enrol_get_users_courses",
            [("userid", resolved_user_id)],
            timeout_s=10.0,
        )

        course_ids: List[int] = [int(c.get("id")) for c in (courses_data or []) if c.get("id") is not None]
        course_lookup: Dict[int, Dict[str, Any]] = {
            int(c.get("id")): {
                "id": int(c.get("id")),
                "name": c.get("fullname"),
                "shortname": c.get("shortname"),
            }
            for c in (courses_data or [])
            if c.get("id") is not None
        }

        if not course_ids:
            return json.dumps(
                {
                    "user_id": user_id,
                    "resolved_user_id": resolved_user_id,
                    "success": True,
                    "source": "moodle_api",
                    "counts": {"completed": 0, "due": 0, "missed": 0},
                    "completed": [],
                    "due": [],
                    "missed": [],
                    "note": "No enrolled courses found for user",
                }
            )

        # Moodle expects params like courseids[0]=1&courseids[1]=2
        course_params = [(f"courseids[{i}]", cid) for i, cid in enumerate(course_ids)]
        assignments_payload = await _moodle_ws_get(
            ws_url,
            moodle_token,
            "mod_assign_get_assignments",
            course_params,
            timeout_s=20.0,
        )

        assignments: List[Dict[str, Any]] = []
        for course in (assignments_payload or {}).get("courses", []):
            cid = course.get("id")
            for a in course.get("assignments", []) or []:
                duedate = a.get("duedate") or 0
                if duedate and (int(duedate) < window_start or int(duedate) > window_end):
                    continue
                assignments.append(
                    {
                        "assignment_id": a.get("id"),
                        "assignment_name": a.get("name"),
                        "course_id": cid,
                        "due_ts": int(duedate) if duedate else None,
                        "due": _ts_to_iso(int(duedate)) if duedate else None,
                        "cutoff_ts": int(a.get("cutoffdate")) if a.get("cutoffdate") else None,
                        "cutoff": _ts_to_iso(int(a.get("cutoffdate"))) if a.get("cutoffdate") else None,
                    }
                )

        # Prioritize by due date proximity.
        def sort_key(item: Dict[str, Any]) -> Tuple[int, int]:
            due_ts = item.get("due_ts")
            if due_ts is None:
                return (1, 0)
            return (0, abs(int(due_ts) - now_ts))

        assignments.sort(key=sort_key)
        max_to_check = int(limit) if limit else 40
        max_to_check = max(1, min(max_to_check, int(os.getenv("MOODLE_ASSIGNMENTS_LIMIT", str(max_to_check)))))
        assignments_to_check = assignments[:max_to_check]

        semaphore = asyncio.Semaphore(int(os.getenv("MOODLE_ASSIGNMENTS_CONCURRENCY", "8")))

        async def fetch_submission_status(assignment_id: Any) -> Dict[str, Any]:
            async with semaphore:
                return await _moodle_ws_get(
                    ws_url,
                    moodle_token,
                    "mod_assign_get_submission_status",
                    [("assignid", assignment_id), ("userid", resolved_user_id)],
                    timeout_s=15.0,
                )

        submission_results = await asyncio.gather(
            *[fetch_submission_status(a["assignment_id"]) for a in assignments_to_check],
            return_exceptions=True,
        )

        completed: List[Dict[str, Any]] = []
        due: List[Dict[str, Any]] = []
        missed: List[Dict[str, Any]] = []
        errors: List[str] = []

        for assignment, submission in zip(assignments_to_check, submission_results):
            course_info = course_lookup.get(int(assignment.get("course_id") or 0), {})
            item = {
                **assignment,
                "course": course_info or None,
            }

            if isinstance(submission, BaseException):
                errors.append(f"assignid={assignment.get('assignment_id')}: {submission}")
                continue

            submission_dict: Dict[str, Any] = submission or {}
            submissionstatus = submission_dict.get("submissionstatus")
            graded = submission_dict.get("graded")
            is_completed = False
            if isinstance(submissionstatus, str):
                is_completed = submissionstatus.lower() in {"submitted", "graded"}
            if graded is True:
                is_completed = True

            due_ts = assignment.get("due_ts")
            if is_completed:
                completed.append({**item, "submissionstatus": submissionstatus})
            else:
                if due_ts is None:
                    due.append({**item, "submissionstatus": submissionstatus, "note": "No due date"})
                elif int(due_ts) < now_ts:
                    missed.append({**item, "submissionstatus": submissionstatus})
                else:
                    due.append({**item, "submissionstatus": submissionstatus})

        return json.dumps(
            {
                "user_id": user_id,
                "resolved_user_id": resolved_user_id,
                "success": True,
                "source": "moodle_api",
                "window": {
                    "now": _ts_to_iso(now_ts),
                    "days_past": int(days_past),
                    "days_future": int(days_future),
                    "limit": max_to_check,
                },
                "counts": {
                    "completed": len(completed),
                    "due": len(due),
                    "missed": len(missed),
                },
                "completed": completed,
                "due": due,
                "missed": missed,
                "errors": errors,
            }
        )

    except httpx.TimeoutException:
        logger.error(f"Timeout connecting to Moodle for user {user_id}")
        return json.dumps({"user_id": user_id, "error": "Moodle service timeout", "success": False})
    except Exception as e:
        logger.error(f"Error getting Moodle assignments for {user_id}: {e}")
        return json.dumps({"user_id": user_id, "error": str(e), "success": False})
