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

    # ── Structured design questions (D5) ──
    lines.extend(_render_design_questions(build_state))

    # ── Observability snapshots (D2/D3) ──
    lines.extend(_render_observability_snapshots(build_state))

    return "\n".join(lines)


# The three reflection questions, mirroring REFLECTION_QUESTIONS in the wizard
# (frontend/svelte-app .../workshopFormState.svelte.js). Kept here so the
# transcript labels the answers instead of pasting an unlabelled blob.
DESIGN_QUESTIONS = (
    ("q1", "What did you ask your assistant to do, and why?"),
    ("q2", "What did the assistant actually receive?"),
    ("q3", "What would you change in your design after testing it?"),
)

# How many A/B turns are worth sending. The rubric only needs enough to judge
# whether the student understood grounding; a whole lesson's transcript would
# bury it (and cost tokens).
MAX_TRANSCRIPT_SNAPSHOTS = 6

# Prompt budget for the evaluation transcript, in characters (~1 000 tokens).
# Chosen against the measured reality of a small-context deployment: the rubric
# instructions are ~4 900 chars and Ollama's default window is 2 048 tokens, so
# the prompt has to leave the answer room. The full transcript is still shown to
# the teacher on the dashboard — this bounds only what is sent to the model.
MAX_EVALUATION_TRANSCRIPT_CHARS = 4000


def clamp_for_prompt(text: str, max_chars: int = MAX_EVALUATION_TRANSCRIPT_CHARS) -> str:
    """Trim an over-long prompt transcript, keeping both ends.

    The head carries the build decisions and the tail carries the reflection and
    the observation snapshots — the parts the rubric actually grades. The middle
    (a long conversation) is what gets dropped, with an explicit marker so the
    model knows the transcript was shortened rather than assuming the student
    submitted very little.
    """
    text = text or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    marker = "\n\n[... conversation shortened for length ...]\n\n"
    head_budget = int((max_chars - len(marker)) * 0.4)
    tail_budget = max_chars - len(marker) - head_budget
    return text[:head_budget].rstrip() + marker + text[-tail_budget:].lstrip()


def _render_design_questions(build_state: Dict[str, Any]) -> List[str]:
    """Render the structured reflection answers as their own section.

    Students who answered the three fixed questions get them laid out
    question → answer, which is far easier for the rubric to judge than one
    free-text blob. Legacy submissions (free text only) fall back to the
    reflection section above and say so, rather than duplicating it.
    """
    answers = build_state.get("reflectionAnswers")
    lines = ["", "=== DESIGN QUESTIONS ==="]

    if not isinstance(answers, dict) or not any(
            (answers.get(key) or "").strip() for key, _ in DESIGN_QUESTIONS):
        lines.append("(not answered — this submission predates the guided "
                     "reflection; see STUDENT REFLECTION above)")
        return lines

    for key, heading in DESIGN_QUESTIONS:
        answer = (answers.get(key) or "").strip()
        lines.append(f"Q: {heading}")
        lines.append(f"A: {answer or '(not answered)'}")
    return lines


def _render_observability_snapshots(build_state: Dict[str, Any]) -> List[str]:
    """Render what the student observed while building (D2/D3).

    Two kinds of evidence, deliberately kept distinct:

    * the **document facts** (how many chunks the upload became) and the
      **retrieval probes** are deterministic observations of the build;
    * the **A/B turns** record the knowledge-base mode per turn, which is what
      lets the rubric see whether the student actually ran the comparison.

    Everything is limited (``MAX_TRANSCRIPT_SNAPSHOTS``) so a long session does
    not drown the rubric in raw frames.
    """
    lines = ["", "=== OBSERVABILITY SNAPSHOTS ==="]

    observations = _as_list(build_state.get("observations"))
    document_lines = []
    probe_lines = []
    for entry in observations:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        data = _as_dict(entry.get("data"))
        if kind == "document":
            for file in _as_list(data.get("files")):
                file = _as_dict(file)
                params = _as_dict(file.get("plugin_params"))
                document_lines.append(
                    "Document chunking: {name} → {chunks} chunk(s) "
                    "(chunk_size={size}, overlap={overlap}, status={status})".format(
                        name=file.get("original_filename")
                        or file.get("filename") or "(unnamed)",
                        chunks=file.get("document_count", 0),
                        size=params.get("chunk_size", "?"),
                        overlap=params.get("chunk_overlap", "?"),
                        status=file.get("status", "?")))
        elif kind == "probe":
            probe_lines.append(
                "Retrieval probe {query!r}: {count} excerpt(s)".format(
                    query=(data.get("query") or "")[:120],
                    count=data.get("count", len(_as_list(data.get("results"))))))

    if document_lines or probe_lines:
        lines.extend(document_lines)
        lines.extend(probe_lines)
    else:
        lines.append("(no build-time observations recorded)")

    history = _as_list(build_state.get("obsHistory"))
    if history:
        lines.append("")
        lines.append(
            f"Knowledge-base comparison (last {MAX_TRANSCRIPT_SNAPSHOTS} turn(s)):")
        for run in history[-MAX_TRANSCRIPT_SNAPSHOTS:]:
            run = _as_dict(run)
            mode = "ON" if (run.get("ragMode") or "on") != "off" else "OFF"
            lines.append(
                "- [knowledge base {mode}] Q: {q} | excerpts sent: {n} | A: {a}".format(
                    mode=mode,
                    q=(run.get("question") or "")[:160],
                    n=len(_as_list(run.get("sources"))),
                    a=(run.get("answer") or "")[:400]))
    else:
        lines.append("(the student did not run the knowledge-base comparison)")

    return lines


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
    "criteria must contain one entry per rubric criterion. "
    # Small-context models (a 2048-token Ollama model is a realistic deployment)
    # share their window between the prompt and the answer: this prompt is
    # ~1500 tokens, so a verbose answer is what gets cut off mid-JSON. Asking
    # for short feedback is what keeps the whole object inside the window.
    "Keep every \"feedback\" to at most two short sentences and the whole JSON "
    "compact, with no line breaks inside string values."
)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```\s*$", "", stripped)
    return stripped.strip()


def _repair_truncated_json(text: str) -> str:
    """Close a JSON object the model stopped writing in the middle of.

    A model running out of context/output budget leaves the object unterminated
    — typically missing the trailing `}` of the envelope, sometimes cut inside a
    string. Everything before the cut is valid, so closing it recovers a
    complete evaluation instead of throwing away a usable one.

    The cut string is terminated with an ellipsis so a reader can see the
    sentence was clipped rather than assume it ended there.
    """
    out: List[str] = []
    stack: List[str] = []
    in_string = False
    escape = False

    for ch in text:
        out.append(ch)
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if stack:
                stack.pop()

    repaired = "".join(out)
    if escape:  # a dangling backslash cannot end a string
        repaired = repaired[:-1]
    if in_string:
        repaired += '…"'
    # A trailing comma would make the appended closers invalid.
    repaired = re.sub(r",\s*$", "", repaired.rstrip())
    for opener in reversed(stack):
        repaired += "]" if opener == "[" else "}"
    return repaired


def _load_json_object(candidate: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object, tolerating the defects LLMs actually produce."""
    attempts = [candidate]
    # Trailing commas before a closer are the most common small-model slip.
    attempts.append(re.sub(r",(\s*[}\]])", r"\1", candidate))
    # …and a response cut off mid-object needs its brackets closed first.
    repaired = _repair_truncated_json(candidate)
    attempts.extend([repaired, re.sub(r",(\s*[}\]])", r"\1", repaired)])

    for attempt in attempts:
        try:
            parsed = json.loads(attempt)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_evaluation_json_detailed(raw: str) -> "tuple[Dict[str, Any], Optional[str]]":
    """Parse the LLM's evaluation JSON and say whether it had to be repaired.

    Returns ``(data, note)``; ``note`` is None for a clean response and a short
    human-readable explanation when the payload was truncated or malformed and
    the parser recovered what it could. Raises ``ValueError`` when no object can
    be recovered at all.
    """
    text = _strip_code_fences(raw or "")
    if not text:
        raise ValueError("Empty LLM response")

    start = text.find("{")
    candidate = text[start:] if start != -1 else text

    parsed = _load_json_object(candidate)
    if parsed is not None:
        # A response that never closed its envelope was cut short, even if the
        # recovered fragment parsed cleanly.
        balanced = _repair_truncated_json(candidate) == candidate.rstrip()
        note = None if balanced else (
            "The model's response was cut off before the JSON was complete; "
            "the fields it did produce are shown.")
        return parsed, note

    # Nothing parseable from the first brace: fall back to the last balanced
    # slice, which is what an object followed by prose looks like.
    end = text.rfind("}")
    if start != -1 and end > start:
        parsed = _load_json_object(text[start:end + 1])
        if parsed is not None:
            return parsed, None

    try:
        json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Could not parse evaluation JSON: {e}") from e
    raise ValueError("Evaluation JSON is not an object")


def parse_evaluation_json(raw: str) -> Dict[str, Any]:
    """Parse the LLM's evaluation JSON, tolerating markdown fences / prose.

    Raises ``ValueError`` when no parseable JSON object can be found.
    """
    return parse_evaluation_json_detailed(raw)[0]


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
    # The rubric instructions alone are ~5 000 characters (≈1 250 tokens) and a
    # small-context model shares its window between prompt and answer, so the
    # transcript is bounded for the *prompt* only: the teacher dashboard still
    # shows the full transcript, and a lesson-length conversation cannot push
    # the model past its window and truncate the answer mid-JSON.
    transcript = clamp_for_prompt(transcript, MAX_EVALUATION_TRANSCRIPT_CHARS)

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

    parse_note = None
    try:
        parsed, parse_note = parse_evaluation_json_detailed(raw)
        normalized = normalize_evaluation(parsed, rubric_data)
        status = "completed"
        error_message = None
        if parse_note:
            # The feedback is real but was cut short; say so instead of either
            # discarding it (status failed) or pretending it is complete.
            logger.warning(
                "Workshop evaluation truncated for session %s (%s criteria "
                "recovered from %d chars)",
                session_id, len(normalized.get("criteria") or []), len(raw))
            error_message = parse_note
    except ValueError as e:
        logger.warning(
            "Workshop evaluation malformed JSON for session %s: %s "
            "(prompt=%d chars, response=%d chars)",
            session_id, e, len(instructions) + len(transcript), len(raw))
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
