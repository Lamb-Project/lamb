"""
Grade CRUD service for the file_evaluation module.

All database operations use raw SQL via ``LambDatabaseManager.get_connection()``.
Dual grading model: AI proposes (ai_score/ai_comment), professor finalises (score/comment).
"""
import uuid
import time
from typing import Optional, Dict, Any
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")


def _now() -> int:
    return int(time.time())


class GradeService:
    def __init__(self):
        self.db = LambDatabaseManager()

    # ── Read ──────────────────────────────────────────────────────────────

    def get_grade_by_submission(self, file_submission_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return None
        try:
            conn.row_factory = _dict_factory
            row = conn.execute(
                "SELECT * FROM mod_file_eval_grades WHERE file_submission_id = ?",
                (file_submission_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    # ── Create / Update professor grade ───────────────────────────────────

    def create_or_update_grade(
        self,
        file_submission_id: str,
        score: float,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            raise RuntimeError("No DB connection")
        try:
            conn.row_factory = _dict_factory
            existing = conn.execute(
                "SELECT id FROM mod_file_eval_grades WHERE file_submission_id = ?",
                (file_submission_id,),
            ).fetchone()

            now = _now()
            if existing:
                conn.execute(
                    """UPDATE mod_file_eval_grades
                       SET score = ?, comment = ?, updated_at = ?
                     WHERE file_submission_id = ?""",
                    (score, comment, now, file_submission_id),
                )
                conn.commit()
                return self.get_grade_by_submission(file_submission_id)  # type: ignore

            grade_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO mod_file_eval_grades
                   (id, file_submission_id, score, comment, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (grade_id, file_submission_id, score, comment, now, now),
            )
            conn.commit()
            return self.get_grade_by_submission(file_submission_id)  # type: ignore
        finally:
            conn.close()

    # ── Create / Update AI grade ──────────────────────────────────────────

    def upsert_ai_grade(
        self,
        file_submission_id: str,
        ai_score: Optional[float],
        ai_comment: Optional[str],
    ) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            raise RuntimeError("No DB connection")
        try:
            conn.row_factory = _dict_factory
            existing = conn.execute(
                "SELECT id FROM mod_file_eval_grades WHERE file_submission_id = ?",
                (file_submission_id,),
            ).fetchone()

            now = _now()
            if existing:
                conn.execute(
                    """UPDATE mod_file_eval_grades
                       SET ai_score = ?, ai_comment = ?, ai_evaluated_at = ?, updated_at = ?
                     WHERE file_submission_id = ?""",
                    (ai_score, ai_comment, now, now, file_submission_id),
                )
            else:
                grade_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO mod_file_eval_grades
                       (id, file_submission_id, ai_score, ai_comment, ai_evaluated_at, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (grade_id, file_submission_id, ai_score, ai_comment, now, now, now),
                )
            conn.commit()
            return self.get_grade_by_submission(file_submission_id)  # type: ignore
        finally:
            conn.close()

    # ── Bulk: accept all AI grades as final ───────────────────────────────

    def accept_ai_grades_for_activity(self, activity_id: int) -> int:
        conn = self.db.get_connection()
        if not conn:
            return 0
        try:
            now = _now()
            cur = conn.execute(
                """UPDATE mod_file_eval_grades
                      SET score = ai_score, comment = ai_comment, updated_at = ?
                    WHERE ai_score IS NOT NULL
                      AND file_submission_id IN (
                          SELECT id FROM mod_file_eval_submissions WHERE activity_id = ?
                      )""",
                (now, activity_id),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
