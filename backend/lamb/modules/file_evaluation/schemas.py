"""
Pydantic schemas for the file_evaluation module API.

Only module-specific models live here. Core LAMB models (users, activities,
organisations) are defined elsewhere.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, field_validator, model_validator


# ── Grades ─────────────────────────────────────────────────────────────────

class GradeRequest(BaseModel):
    file_submission_id: str
    score: float
    comment: Optional[str] = None

class GradeUpdate(BaseModel):
    score: float
    comment: Optional[str] = None

class GradeResponse(BaseModel):
    id: str
    file_submission_id: str
    ai_score: Optional[float] = None
    ai_comment: Optional[str] = None
    ai_evaluated_at: Optional[int] = None
    score: Optional[float] = None
    comment: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


# ── File Submissions ───────────────────────────────────────────────────────

class FileSubmissionResponse(BaseModel):
    id: str
    activity_id: int
    file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    uploaded_by: str
    uploaded_at: Optional[int] = None
    group_code: Optional[str] = None
    group_display_name: Optional[str] = None
    max_group_members: int = 1
    student_note: Optional[str] = None
    evaluation_status: Optional[str] = None
    evaluation_started_at: Optional[int] = None
    evaluation_error: Optional[str] = None
    grade: Optional[GradeResponse] = None


# ── Student Submissions ────────────────────────────────────────────────────

class StudentSubmissionResponse(BaseModel):
    id: str
    file_submission_id: str
    student_id: str
    activity_id: int
    lis_result_sourcedid: Optional[str] = None
    joined_at: Optional[int] = None
    sent_to_moodle: bool = False
    sent_to_moodle_at: Optional[int] = None


# ── Combined views ─────────────────────────────────────────────────────────

class SubmissionView(BaseModel):
    file_submission: FileSubmissionResponse
    student_submission: StudentSubmissionResponse
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    is_group_leader: bool = False
    group_member_count: Optional[int] = None


# ── Group join flow ────────────────────────────────────────────────────────

class GroupCodeSubmission(BaseModel):
    group_code: str

class GroupCodeResponse(BaseModel):
    success: bool
    message: str
    submission: Optional[SubmissionView] = None


# ── Activity setup config (stored in lti_activities.setup_config JSON) ─────

class FileEvalSetupConfig(BaseModel):
    evaluator_id: Optional[str] = None
    submission_type: Literal["individual", "group"] = "individual"
    max_group_size: Optional[int] = None
    deadline: Optional[str] = None
    language: str = "en"

    @model_validator(mode='before')
    @classmethod
    def legacy_submission_type(cls, data):
        if isinstance(data, dict) and data.get('submission_type') is None and 'activity_type' in data:
            return {**data, 'submission_type': data.get('activity_type') or 'individual'}
        return data

    @field_validator('language', mode='before')
    @classmethod
    def normalize_language(cls, v):
        if isinstance(v, str):
            v = v.lower()
            if v not in ('en', 'es', 'ca', 'eu'):
                return 'en'
        return v


# ── Evaluation control ─────────────────────────────────────────────────────

class StartEvaluationRequest(BaseModel):
    file_submission_ids: List[str]

class EvaluationStatusResponse(BaseModel):
    overall_status: str
    counts: dict
    submissions: list


# ── Activity view (student portal) ────────────────────────────────────────

class StudentActivityViewResponse(BaseModel):
    activity_id: int
    activity_name: Optional[str] = None
    setup_config: Optional[FileEvalSetupConfig] = None
    submission: Optional[SubmissionView] = None
    can_submit: bool = True
