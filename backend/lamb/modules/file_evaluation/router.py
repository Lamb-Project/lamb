"""
API router for the file_evaluation module.

Mounted at ``/lamb/v1/modules/file_evaluation/`` by the module system.
JWT auth uses the same ``lamb.auth`` tokens issued by ``lti_router.py``.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import os
import json
import sqlite3

from lamb import auth as lamb_auth
from lamb.logging_config import get_logger

from .service import FileEvalService
from .grade_service import GradeService
from .evaluation_service import EvaluationService
from .lti_passback import LTIGradePassback
from .schemas import (
    GradeUpdate,
    GroupCodeSubmission,
    StartEvaluationRequest,
)

logger = get_logger(__name__, component="FILE_EVAL")

router = APIRouter(tags=["file_evaluation"])

_service = FileEvalService()
_grade_svc = GradeService()
_eval_svc = EvaluationService()


# ── JWT dependency ────────────────────────────────────────────────────────

def _decode_jwt(request: Request, token: Optional[str] = None) -> dict:
    """Extract and validate a LAMB JWT from Authorization header or query param."""
    raw_token = token
    if not raw_token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            raw_token = auth[7:]
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing token")

    payload = lamb_auth.decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def _require_instructor(payload: dict):
    if not payload.get("is_instructor") and payload.get("lti_type") not in ("dashboard", "setup"):
        raise HTTPException(status_code=403, detail="Instructor access required")


# ── Activity view (for student or instructor) ─────────────────────────────

@router.get("/activities/{activity_id}/view")
async def get_activity_view(activity_id: int, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    tid = payload.get("lti_activity_id")
    if tid is not None and int(tid) != int(activity_id):
        raise HTTPException(status_code=403, detail="Activity does not match token")
    student_id = payload.get("lti_user_email", "")
    is_instructor = payload.get("is_instructor") or payload.get("lti_type") in ("dashboard",)

    cfg = _service.get_setup_config(activity_id)
    activity_info = _service.get_activity_info(activity_id)

    if is_instructor:
        subs = _service.get_submissions_by_activity(activity_id)
        stats = _service.get_dashboard_stats(activity_id)
        return {"activity_id": activity_id, "setup_config": cfg, "activity_info": activity_info, "submissions": subs, "stats": stats}

    sub = _service.get_student_submission(activity_id, student_id)
    return {"activity_id": activity_id, "setup_config": cfg, "activity_info": activity_info, "submission": sub, "can_submit": sub is None}


@router.put("/activities/{activity_id}/setup-config")
async def update_setup_config(
    activity_id: int,
    request: Request,
    body: dict,
    token: str = "",
):
    """Update setup_config for an activity (evaluator_id, deadline, submission_type, etc.)."""
    payload = _decode_jwt(request, token)
    _require_instructor(payload)

    tid = payload.get("lti_activity_id")
    if tid is not None and int(tid) != int(activity_id):
        raise HTTPException(status_code=403, detail="Activity does not match token")

    # Allowed fields to update
    allowed_fields = {"evaluator_id", "deadline", "submission_type", "max_group_size", "language"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    conn = _service.db.get_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        tbl = f"{_service.db.table_prefix}lti_activities"

        # Get current setup_config
        row = conn.execute(f"SELECT setup_config FROM {tbl} WHERE id = ?", (activity_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Activity not found")

        current_cfg = row.get("setup_config")
        if isinstance(current_cfg, (bytes, bytearray, memoryview)):
            current_cfg = bytes(current_cfg).decode("utf-8", errors="replace")
        if isinstance(current_cfg, str):
            try:
                current_cfg = json.loads(current_cfg) if current_cfg else {}
            except (json.JSONDecodeError, TypeError):
                current_cfg = {}
        if not isinstance(current_cfg, dict):
            current_cfg = {}

        # Merge updates
        current_cfg.update(updates)

        conn.execute(
            f"UPDATE {tbl} SET setup_config = ? WHERE id = ?",
            (json.dumps(current_cfg), activity_id),
        )
        conn.commit()

        return {"success": True, "setup_config": current_cfg}
    finally:
        conn.close()


# ── Submissions ───────────────────────────────────────────────────────────

@router.post("/activities/{activity_id}/submissions")
async def upload_submission(
    activity_id: int,
    request: Request,
    file: UploadFile = File(...),
    student_note: Optional[str] = Form(None),
    token: str = Form(""),
):
    payload = _decode_jwt(request, token)
    student_id = payload.get("lti_user_email", "")
    lis_sourcedid = payload.get("lis_result_sourcedid")

    # Path param must match the activity embedded in the JWT (numeric lti_activities.id).
    tid = payload.get("lti_activity_id")
    if tid is not None and int(tid) != int(activity_id):
        raise HTTPException(status_code=403, detail="Activity does not match token")

    content = await file.read()
    try:
        result = _service.create_submission(
            activity_id=activity_id,
            student_id=student_id,
            file_name=file.filename or "upload",
            file_bytes=content,
            file_type=file.content_type or "application/octet-stream",
            lis_result_sourcedid=lis_sourcedid,
            student_note=student_note,
        )
    except ValueError as e:
        msg = str(e)
        code = 404 if "not found" in msg.lower() else 409
        raise HTTPException(status_code=code, detail=msg) from e
    except sqlite3.IntegrityError as e:
        logger.warning("file_eval submission constraint: %s", e)
        raise HTTPException(
            status_code=409,
            detail="Could not save submission (duplicate or invalid data).",
        ) from e
    except sqlite3.OperationalError as e:
        logger.exception("file_eval DB operational error on submission")
        raise HTTPException(status_code=503, detail=str(e)) from e
    except OSError as e:
        logger.exception("file_eval file store error")
        raise HTTPException(status_code=500, detail=f"Could not store file: {e}") from e
    except Exception:
        logger.exception("file_eval unexpected error on submission")
        raise
    return {"success": True, "submission": result}


@router.get("/activities/{activity_id}/submissions")
async def list_submissions(activity_id: int, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)
    return _service.get_submissions_by_activity(activity_id)


@router.get("/submissions/me")
async def my_submission(request: Request, token: str = "", activity_id: int = Query(...)):
    payload = _decode_jwt(request, token)
    student_id = payload.get("lti_user_email", "")
    sub = _service.get_student_submission(activity_id, student_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No submission found")
    return sub


@router.post("/submissions/join")
async def join_group(request: Request, body: GroupCodeSubmission, token: str = "", activity_id: int = Query(...)):
    payload = _decode_jwt(request, token)
    student_id = payload.get("lti_user_email", "")
    lis_sourcedid = payload.get("lis_result_sourcedid")
    result = _service.join_group(
        activity_id=activity_id,
        group_code=body.group_code,
        student_id=student_id,
        lis_result_sourcedid=lis_sourcedid,
    )
    return {"success": True, "submission": result}


@router.get("/submissions/{file_submission_id}/members")
async def get_members(file_submission_id: str, request: Request, token: str = ""):
    _decode_jwt(request, token)
    return _service.get_group_members(file_submission_id)


@router.get("/submissions/my-file/download")
async def download_file(request: Request, token: str = "", activity_id: int = Query(...)):
    payload = _decode_jwt(request, token)
    student_id = payload.get("lti_user_email", "")
    sub = _service.get_student_submission(activity_id, student_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No submission")

    file_path = sub["file_submission"]["file_path"]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_name = sub["file_submission"]["file_name"]

    def iterfile():
        with open(file_path, "rb") as fh:
            yield from iter(lambda: fh.read(65536), b"")

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/submissions/{file_submission_id}/download")
async def download_submission_by_id(file_submission_id: str, request: Request, token: str = ""):
    """Download a specific submission file by file_submission_id (for instructors)."""
    payload = _decode_jwt(request, token)
    _require_instructor(payload)

    conn = _service.db.get_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        tbl = f"{_service.db.table_prefix}mod_file_eval_submissions"
        fs = conn.execute(f"SELECT * FROM {tbl} WHERE id = ?", (file_submission_id,)).fetchone()
        if not fs:
            raise HTTPException(status_code=404, detail="Submission not found")

        file_path = fs["file_path"]
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")

        file_name = fs["file_name"]

        def iterfile():
            with open(file_path, "rb") as fh:
                yield from iter(lambda: fh.read(65536), b"")

        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )
    finally:
        conn.close()


# ── Evaluation ────────────────────────────────────────────────────────────

@router.post("/activities/{activity_id}/evaluate")
async def start_evaluation(
    activity_id: int,
    body: StartEvaluationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    token: str = "",
):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)

    cfg = _service.get_setup_config(activity_id)
    evaluator_id = cfg.get("evaluator_id")
    if not evaluator_id:
        raise HTTPException(status_code=400, detail="No evaluator configured for this activity")

    start_result = _eval_svc.start_evaluation(activity_id, body.file_submission_ids)
    if not start_result.get("success"):
        raise HTTPException(status_code=400, detail=start_result.get("message", "Failed"))

    queued_ids = start_result.get("queued_ids", [])
    if queued_ids:
        background_tasks.add_task(_eval_svc.process_evaluation_batch, activity_id, queued_ids, evaluator_id)

    return start_result


@router.get("/activities/{activity_id}/evaluation-status")
async def evaluation_status(activity_id: int, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)
    return _eval_svc.get_evaluation_status(activity_id)


# ── Grades ────────────────────────────────────────────────────────────────

@router.post("/grades/{file_submission_id}")
async def update_grade(file_submission_id: str, body: GradeUpdate, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)
    grade = _grade_svc.create_or_update_grade(file_submission_id, body.score, body.comment)
    return {"success": True, "grade": grade}


@router.post("/grades/activity/{activity_id}/accept-ai-grades")
async def accept_ai_grades(activity_id: int, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)
    count = _grade_svc.accept_ai_grades_for_activity(activity_id)
    return {"success": True, "accepted": count}


# ── Grade sync to Moodle ─────────────────────────────────────────────────

@router.post("/activities/{activity_id}/grades/sync")
async def sync_grades(activity_id: int, request: Request, token: str = ""):
    payload = _decode_jwt(request, token)
    _require_instructor(payload)
    result = LTIGradePassback.send_activity_grades(activity_id)
    return result
