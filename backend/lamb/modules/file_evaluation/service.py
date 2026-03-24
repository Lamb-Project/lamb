"""
Submission & group service for the file_evaluation module.

Handles file uploads, group join flow, and query views.
Activity config lives in ``lti_activities.setup_config`` JSON.
"""
import uuid
import secrets
import string
import time as _time
import json
from typing import Optional, Dict, Any, List
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger
from .storage_service import FileStorageService
from .grade_service import GradeService

logger = get_logger(__name__, component="FILE_EVAL")

GROUP_PREFIX_MAP = {
    'en': 'GROUP',
    'es': 'GRUPO',
    'ca': 'GRUP',
    'eu': 'TALDEA',
}


def _now() -> int:
    return int(_time.time())


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _parse_setup_config(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Return setup_config as a dict; tolerate bytes, NULL, or already-parsed dict."""
    raw = activity.get("setup_config")
    if raw is None:
        raw = "{}"
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).decode("utf-8", errors="replace")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class FileEvalService:
    def __init__(self):
        self.db = LambDatabaseManager()
        self.grade_svc = GradeService()

    # ── Setup config helpers ──────────────────────────────────────────────

    def get_setup_config(self, activity_id: int) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            return {}
        try:
            conn.row_factory = _dict_factory
            tbl = f"{self.db.table_prefix}lti_activities"
            row = conn.execute(f"SELECT setup_config FROM {tbl} WHERE id = ?", (activity_id,)).fetchone()
            if not row:
                return {}
            return _parse_setup_config(row)
        finally:
            conn.close()

    # ── Create submission ─────────────────────────────────────────────────

    def create_submission(
        self,
        activity_id: int,
        student_id: str,
        file_name: str,
        file_bytes: bytes,
        file_type: str,
        lis_result_sourcedid: Optional[str] = None,
        student_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            raise RuntimeError("No DB connection")
        try:
            conn.row_factory = _dict_factory

            tbl = f"{self.db.table_prefix}lti_activities"
            activity = conn.execute(f"SELECT * FROM {tbl} WHERE id = ?", (activity_id,)).fetchone()
            if not activity:
                raise ValueError("Activity not found")

            cfg = _parse_setup_config(activity)
            submission_type = cfg.get("submission_type") or cfg.get("activity_type", "individual")
            max_group_size = cfg.get("max_group_size") or 1
            language = cfg.get("language", "en")

            file_size = len(file_bytes)

            existing_ss = conn.execute(
                "SELECT * FROM mod_file_eval_student_submissions WHERE student_id = ? AND activity_id = ?",
                (student_id, activity_id),
            ).fetchone()

            if existing_ss:
                fs = conn.execute(
                    "SELECT * FROM mod_file_eval_submissions WHERE id = ?",
                    (existing_ss["file_submission_id"],),
                ).fetchone()
                if fs and fs["uploaded_by"] == student_id:
                    file_path = FileStorageService.save_submission_file(
                        activity_id=activity_id,
                        submission_id=fs["id"],
                        file_name=file_name,
                        file_bytes=file_bytes,
                        previous_file_path=fs["file_path"],
                    )
                    conn.execute(
                        """UPDATE mod_file_eval_submissions
                           SET file_name=?, file_path=?, file_size=?, file_type=?, uploaded_at=?,
                               student_note=?, evaluation_status=NULL, evaluation_error=NULL
                         WHERE id=?""",
                        (file_name, file_path, file_size, file_type, _now(),
                         (student_note or "").strip() or None, fs["id"]),
                    )
                    if lis_result_sourcedid:
                        conn.execute(
                            "UPDATE mod_file_eval_student_submissions SET lis_result_sourcedid=?, joined_at=? WHERE id=?",
                            (lis_result_sourcedid, _now(), existing_ss["id"]),
                        )
                    conn.commit()
                    return self._build_submission_view(conn, fs["id"], existing_ss["id"])

            # New submission
            fs_id = str(uuid.uuid4())
            ss_id = str(uuid.uuid4())
            group_code = None
            group_display_name = None

            if submission_type == "group":
                group_code = self._generate_group_code(conn)
                group_display_name = self._generate_group_display_name(conn, activity_id, language)

            file_path = FileStorageService.save_submission_file(
                activity_id=activity_id,
                submission_id=fs_id,
                file_name=file_name,
                file_bytes=file_bytes,
            )

            conn.execute(
                """INSERT INTO mod_file_eval_submissions
                   (id, activity_id, file_name, file_path, file_size, file_type,
                    uploaded_by, uploaded_at, group_code, group_display_name,
                    max_group_members, student_note)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (fs_id, activity_id, file_name, file_path, file_size, file_type,
                 student_id, _now(), group_code, group_display_name,
                 max_group_size if submission_type == "group" else 1,
                 (student_note or "").strip() or None),
            )

            conn.execute(
                """INSERT INTO mod_file_eval_student_submissions
                   (id, file_submission_id, student_id, activity_id,
                    lis_result_sourcedid, joined_at)
                   VALUES (?,?,?,?,?,?)""",
                (ss_id, fs_id, student_id, activity_id, lis_result_sourcedid, _now()),
            )

            conn.commit()
            return self._build_submission_view(conn, fs_id, ss_id)
        finally:
            conn.close()

    # ── Join group ────────────────────────────────────────────────────────

    def join_group(
        self,
        activity_id: int,
        group_code: str,
        student_id: str,
        lis_result_sourcedid: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            raise RuntimeError("No DB")
        try:
            conn.row_factory = _dict_factory

            fs = conn.execute(
                "SELECT * FROM mod_file_eval_submissions WHERE group_code = ? AND activity_id = ?",
                (group_code, activity_id),
            ).fetchone()
            if not fs:
                raise ValueError("Invalid group code")

            members = conn.execute(
                "SELECT COUNT(*) AS c FROM mod_file_eval_student_submissions WHERE file_submission_id = ?",
                (fs["id"],),
            ).fetchone()["c"]
            if members >= fs["max_group_members"]:
                raise ValueError("Group is full")

            existing = conn.execute(
                "SELECT id, file_submission_id FROM mod_file_eval_student_submissions WHERE student_id = ? AND activity_id = ?",
                (student_id, activity_id),
            ).fetchone()
            if existing:
                if existing["file_submission_id"] == fs["id"]:
                    raise ValueError("Already a member of this group")
                raise ValueError("Already submitted to this activity")

            ss_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO mod_file_eval_student_submissions
                   (id, file_submission_id, student_id, activity_id, lis_result_sourcedid, joined_at)
                   VALUES (?,?,?,?,?,?)""",
                (ss_id, fs["id"], student_id, activity_id, lis_result_sourcedid, _now()),
            )
            conn.commit()
            return self._build_submission_view(conn, fs["id"], ss_id)
        finally:
            conn.close()

    # ── Queries ───────────────────────────────────────────────────────────

    def get_student_submission(self, activity_id: int, student_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return None
        try:
            conn.row_factory = _dict_factory
            ss = conn.execute(
                "SELECT * FROM mod_file_eval_student_submissions WHERE activity_id = ? AND student_id = ?",
                (activity_id, student_id),
            ).fetchone()
            if not ss:
                return None
            return self._build_submission_view(conn, ss["file_submission_id"], ss["id"])
        finally:
            conn.close()

    def get_submissions_by_activity(self, activity_id: int) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return []
        try:
            conn.row_factory = _dict_factory
            file_subs = conn.execute(
                "SELECT * FROM mod_file_eval_submissions WHERE activity_id = ? ORDER BY uploaded_at DESC",
                (activity_id,),
            ).fetchall()

            result = []
            for fs in file_subs:
                grade = self.grade_svc.get_grade_by_submission(fs["id"])
                members = conn.execute(
                    "SELECT * FROM mod_file_eval_student_submissions WHERE file_submission_id = ?",
                    (fs["id"],),
                ).fetchall()
                result.append({
                    "file_submission": fs,
                    "grade": grade,
                    "members": members,
                    "member_count": len(members),
                })
            return result
        finally:
            conn.close()

    def get_group_members(self, file_submission_id: str) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return []
        try:
            conn.row_factory = _dict_factory
            return conn.execute(
                "SELECT * FROM mod_file_eval_student_submissions WHERE file_submission_id = ?",
                (file_submission_id,),
            ).fetchall()
        finally:
            conn.close()

    # ── Dashboard stats ───────────────────────────────────────────────────

    def get_dashboard_stats(self, activity_id: int) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            return {}
        try:
            conn.row_factory = _dict_factory
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM mod_file_eval_submissions WHERE activity_id = ?",
                (activity_id,),
            ).fetchone()["c"]

            evaluated = conn.execute(
                "SELECT COUNT(*) AS c FROM mod_file_eval_submissions WHERE activity_id = ? AND evaluation_status = 'completed'",
                (activity_id,),
            ).fetchone()["c"]

            graded = conn.execute(
                """SELECT COUNT(*) AS c FROM mod_file_eval_grades g
                   JOIN mod_file_eval_submissions fs ON g.file_submission_id = fs.id
                   WHERE fs.activity_id = ? AND g.score IS NOT NULL""",
                (activity_id,),
            ).fetchone()["c"]

            sent = conn.execute(
                "SELECT COUNT(*) AS c FROM mod_file_eval_student_submissions WHERE activity_id = ? AND sent_to_moodle = 1",
                (activity_id,),
            ).fetchone()["c"]

            return {"total_submissions": total, "evaluated": evaluated, "graded": graded, "sent_to_moodle": sent}
        finally:
            conn.close()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _build_submission_view(self, conn, fs_id: str, ss_id: str) -> Dict[str, Any]:
        fs = conn.execute("SELECT * FROM mod_file_eval_submissions WHERE id = ?", (fs_id,)).fetchone()
        ss = conn.execute("SELECT * FROM mod_file_eval_student_submissions WHERE id = ?", (ss_id,)).fetchone()
        grade = self.grade_svc.get_grade_by_submission(fs_id)
        member_count = conn.execute(
            "SELECT COUNT(*) AS c FROM mod_file_eval_student_submissions WHERE file_submission_id = ?",
            (fs_id,),
        ).fetchone()["c"]
        is_leader = (fs["uploaded_by"] == ss["student_id"]) and fs.get("group_code") is not None
        return {
            "file_submission": fs,
            "student_submission": ss,
            "grade": grade,
            "is_group_leader": is_leader,
            "member_count": member_count,
        }

    @staticmethod
    def _generate_group_code(conn) -> str:
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            exists = conn.execute(
                "SELECT 1 FROM mod_file_eval_submissions WHERE group_code = ?", (code,),
            ).fetchone()
            if not exists:
                return code

    @staticmethod
    def _generate_group_display_name(conn, activity_id: int, language: str) -> str:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM mod_file_eval_submissions WHERE activity_id = ? AND group_code IS NOT NULL",
            (activity_id,),
        ).fetchone()
        number = (row["c"] if isinstance(row, dict) else row[0]) + 1
        prefix = GROUP_PREFIX_MAP.get(language, "GROUP")
        return f"{prefix}_{number}"
