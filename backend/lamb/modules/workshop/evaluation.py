"""Formative evaluation for workshop submissions.

Serializes a student's whole build process (build decisions + conversation
including the tool trace + reflection) into a transcript, runs it through the
reusable rubric evaluation engine via an async, org-aware LLM call, and stores
the resulting criterion-by-criterion feedback.

The score produced here is a *suggestion*: the final grade is always decided
by the teacher. Feedback is never written into a gradebook.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from lamb.completions.small_fast_model_helper import invoke_small_fast_model
from lamb.database_manager import LambDatabaseManager
from lamb.evaluaitor.rubric_database import RubricDatabaseManager
from lamb.evaluaitor.rubric_service import generate_rubric_evaluation_json

logger = logging.getLogger(__name__)

_db_manager = LambDatabaseManager()
_rubric_db = RubricDatabaseManager()


# ─────────────────────────────────────────────────────────────────────────────
# Transcript serialization
# ─────────────────────────────────────────────────────────────────────────────

def _as_dict(value: Any) -> Dict[str, Any]:
    """Best-effort parse of a JSON string / dict into a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _as_list(value: Any) -> List[Any]:
    """Best-effort parse of a JSON string / list into a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _render_tool_calls(tool_calls: Any) -> List[str]:
    """Render OpenAI-style ``tool_calls`` entries as human-readable lines."""
    lines: List[str] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        name = fn.get("name") or "tool"
        args = fn.get("arguments")
        if isinstance(args, str):
            rendered_args = args
        elif args is None:
            rendered_args = ""
        else:
            try:
                rendered_args = json.dumps(args, ensure_ascii=False)
            except (TypeError, ValueError):
                rendered_args = str(args)
        lines.append(f"[tool call: {name}({rendered_args})]")
    return lines


def build_transcript(session: Dict[str, Any]) -> str:
    """Render build decisions + chat (incl. tool trace) + reflection into text.

    The output is handed to the LLM as the student's work. Tool exchanges are
    preserved even when the frontend marked them ``hidden`` (hidden only means
    "don't render in the chat UI"), so the rubric can judge whether the student
    understood when tools were triggered.
    """
    session = session or {}
    build_state = _as_dict(session.get("build_state"))

    lines: List[str] = []
    lines.append("=== BUILD DECISIONS ===")

    instructions = (build_state.get("instructions") or "").strip()
    lines.append(
        "Assistant instructions:\n" + (instructions or "(none provided)"))

    file_meta = _as_dict(build_state.get("attachedFileMeta"))
    document_name = (
        file_meta.get("name")
        or build_state.get("documentName")
        or session.get("document_name")
        or "(none)"
    )
    lines.append(f"Attached document: {document_name}")

    kb = (
        build_state.get("kbCollection")
        or build_state.get("selectedKbId")
        or session.get("kb_id")
        or "(none)"
    )
    lines.append(f"Knowledge base collection: {kb}")

    tools = build_state.get("selectedTools")
    if isinstance(tools, (list, tuple)) and tools:
        lines.append(f"Selected tools: {', '.join(str(t) for t in tools)}")
    else:
        lines.append("Selected tools: (none)")

    # ── Conversation ──
    lines.append("")
    lines.append("=== CONVERSATION ===")
    messages = _as_list(session.get("saved_chat"))
    if not messages:
        lines.append("(no conversation)")

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []
        hidden = bool(message.get("hidden"))

        # Tool calls are always kept (part of the observable tool trace).
        lines.extend(_render_tool_calls(tool_calls))

        if role == "tool":
            name = message.get("name") or "tool"
            lines.append(f"[tool result ({name})]: {content}")
            continue

        # Hidden non-tool entries are conversation plumbing — skip rendering.
        if hidden and not tool_calls:
            continue

        if content:
            speaker = {
                "user": "Student",
                "assistant": "Assistant",
            }.get(role, role or "Message")
            lines.append(f"{speaker}: {content}")

    # ── Reflection ──
    lines.append("")
    lines.append("=== STUDENT REFLECTION ===")
    reflection = (session.get("reflection") or "").strip()
    lines.append(reflection or "(none provided)")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# LLM response handling
# ─────────────────────────────────────────────────────────────────────────────

def extract_llm_content(response: Any) -> str:
    """Pull the assistant text out of the many shapes a connector may return."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices")
        if choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            return (message.get("content") or first.get("text") or "")
        return response.get("content") or ""
    # Pydantic / SDK objects
    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if message is not None:
            return getattr(message, "content", "") or ""
        return getattr(first, "text", "") or ""
    return str(response)


_JSON_OUTPUT_DIRECTIVE = (
    "\n\nIMPORTANT: Respond with ONLY one valid JSON object and nothing else. "
    "Do not use markdown, code fences, or prose. Use exactly these keys: "
    '{"criteria": [{"criterion": string, "level": string, "score": number, '
    '"weight": number, "feedback": string}], "total_score": number, '
    '"max_score": number, "overall_feedback": string}. '
    "criteria must contain one entry per rubric criterion."
)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```\s*$", "", stripped)
    return stripped.strip()


def parse_evaluation_json(raw: str) -> Dict[str, Any]:
    """Parse the LLM's evaluation JSON, tolerating markdown fences / prose.

    Raises ``ValueError`` when no parseable JSON object can be found.
    """
    text = _strip_code_fences(raw or "")
    if not text:
        raise ValueError("Empty LLM response")

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
    else:
        candidate = text

    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Could not parse evaluation JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise ValueError("Evaluation JSON is not an object")
    return parsed


def _first_present(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _normalize_criterion(entry: Any) -> Optional[Dict[str, Any]]:
    """Normalize one criterion evaluation into a stable shape."""
    if isinstance(entry, str):
        return {"criterion": entry, "level": None, "score": None,
                "weight": None, "feedback": None}
    if not isinstance(entry, dict):
        return None

    name = _first_present(entry, "criterion", "name", "criterion_name",
                          "criterionName", "title")
    level = _first_present(entry, "level", "selected_level", "level_label",
                           "levelLabel", "performance_level")
    score = _first_present(entry, "score", "level_score", "levelScore",
                           "points", "value")
    weight = _first_present(entry, "weight", "criterion_weight")
    feedback = _first_present(entry, "feedback", "justification", "comments",
                              "comment", "rationale")
    return {
        "criterion": name,
        "level": level,
        "score": score,
        "weight": weight,
        "feedback": feedback,
    }


def normalize_evaluation(
    data: Dict[str, Any], rubric_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Map the LLM output onto our stable evaluation shape."""
    raw_criteria = _first_present(
        data, "criteria", "criterion_evaluations", "criterionEvaluations",
        "evaluations", "criterion_evaluation") or []
    if isinstance(raw_criteria, dict):
        raw_criteria = [
            {"criterion": k, **(v if isinstance(v, dict) else {"feedback": v})}
            for k, v in raw_criteria.items()
        ]
    if not isinstance(raw_criteria, list):
        raw_criteria = []

    criteria = [
        normalized
        for normalized in (_normalize_criterion(c) for c in raw_criteria)
        if normalized is not None
    ]

    overall = _first_present(
        data, "overall_feedback", "overallFeedback", "overall", "feedback",
        "summary")
    total = _first_present(
        data, "total_score", "totalScore", "score", "final_score",
        "finalScore")
    max_score = _first_present(data, "max_score", "maxScore")
    if max_score is None:
        max_score = rubric_data.get("maxScore")

    return {
        "criteria": criteria,
        "overall_feedback": overall,
        "total_score": total,
        "max_score": max_score,
    }


def _coerce_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation service
# ─────────────────────────────────────────────────────────────────────────────

async def evaluate_session(
    session: Dict[str, Any],
    activity: Dict[str, Any],
    rubric_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run rubric-based formative evaluation via an async LLM call.

    Returns a structured result:
        ``{"configured": False}`` when no rubric is attached, otherwise
        ``{"configured": True, "status", "criteria", "overall_feedback", ...}``.

    Failure modes (missing rubric → ``configured: False``; LLM/parse failure →
    ``status: "failed"`` + ``error_message``) are returned rather than raised,
    so a submit never 500s because feedback could not be generated.
    """
    activity = activity or {}
    session = session or {}
    rubric_id = rubric_id or activity.get("rubric_id")
    if not rubric_id:
        return {"configured": False}

    owner_email = (
        activity.get("owner_email")
        or activity.get("configured_by_email")
        or ""
    )
    if not owner_email:
        return {"configured": False, "error_message": "Activity has no owner"}

    rubric = _rubric_db.get_rubric_by_id(rubric_id, owner_email)
    if not rubric:
        return {"configured": False, "error_message": "Rubric not accessible"}

    rubric_data = rubric.get("rubric_data") or {}
    instructions = generate_rubric_evaluation_json(rubric_data)
    transcript = build_transcript(session)

    messages = [
        {"role": "system", "content": instructions + _JSON_OUTPUT_DIRECTIVE},
        {"role": "user", "content": transcript},
    ]

    session_id = session.get("id")
    activity_id = session.get("activity_id") or activity.get("id")

    try:
        response = await invoke_small_fast_model(
            messages=messages,
            assistant_owner=owner_email,
            stream=False,
        )
    except Exception as e:  # connector/config failure
        logger.error(f"Workshop evaluation LLM call failed: {e}")
        _persist(
            session_id, activity_id, rubric_id, status="failed",
            error_message=str(e),
        )
        return {
            "configured": True,
            "status": "failed",
            "rubric_id": rubric_id,
            "criteria": [],
            "overall_feedback": None,
            "total_score": None,
            "max_score": rubric_data.get("maxScore"),
            "error_message": str(e),
        }

    raw = extract_llm_content(response)
    model_used = response.get("model") if isinstance(response, dict) else None

    try:
        parsed = parse_evaluation_json(raw)
        normalized = normalize_evaluation(parsed, rubric_data)
        status = "completed"
        error_message = None
    except ValueError as e:
        logger.warning(f"Workshop evaluation malformed JSON: {e}")
        normalized = {
            "criteria": [],
            "overall_feedback": None,
            "total_score": None,
            "max_score": rubric_data.get("maxScore"),
        }
        status = "failed"
        error_message = str(e)

    total_score = _coerce_number(normalized.get("total_score"))
    max_score = _coerce_number(normalized.get("max_score"))

    _persist(
        session_id,
        activity_id,
        rubric_id,
        criteria=normalized.get("criteria"),
        overall_feedback=normalized.get("overall_feedback"),
        total_score=total_score,
        max_score=max_score,
        model_used=model_used,
        status=status,
        raw_response=raw,
        error_message=error_message,
    )

    return {
        "configured": True,
        "status": status,
        "rubric_id": rubric_id,
        "criteria": normalized.get("criteria") or [],
        "overall_feedback": normalized.get("overall_feedback"),
        "total_score": total_score,
        "max_score": max_score,
        "model_used": model_used,
        "error_message": error_message,
    }


def _persist(
    session_id: Optional[str],
    activity_id: Optional[int],
    rubric_id: Optional[str],
    *,
    criteria: Optional[List[Dict[str, Any]]] = None,
    overall_feedback: Optional[str] = None,
    total_score: Optional[float] = None,
    max_score: Optional[float] = None,
    model_used: Optional[str] = None,
    status: str = "completed",
    raw_response: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Best-effort persistence; evaluation failures must not break the flow."""
    if not session_id or not activity_id:
        logger.warning("Cannot persist workshop evaluation without session/activity")
        return
    try:
        _db_manager.upsert_workshop_evaluation(
            session_id=session_id,
            activity_id=activity_id,
            rubric_id=rubric_id,
            criteria=criteria or [],
            overall_feedback=overall_feedback,
            total_score=total_score,
            max_score=max_score,
            model_used=model_used,
            status=status,
            raw_response=raw_response,
            error_message=error_message,
        )
    except Exception as e:
        logger.error(f"Failed to persist workshop evaluation: {e}")