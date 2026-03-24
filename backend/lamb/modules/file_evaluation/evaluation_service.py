"""
Background evaluation service for the file_evaluation module.

Manages evaluation status, queues, batch processing, and timeout handling.
"""
import time as _time
from typing import List, Dict, Any
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")

STATUS_PENDING = 'pending'
STATUS_PROCESSING = 'processing'
STATUS_COMPLETED = 'completed'
STATUS_ERROR = 'error'

EVALUATION_TIMEOUT_SECONDS = 300  # 5 minutes


def _now() -> int:
    return int(_time.time())


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class EvaluationService:

    def __init__(self):
        self.db = LambDatabaseManager()

    # ── Status ────────────────────────────────────────────────────────────

    def get_evaluation_status(self, activity_id: int) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            return {"overall_status": "error", "counts": {}, "submissions": []}
        try:
            conn.row_factory = _dict_factory
            subs = conn.execute(
                "SELECT id, group_code, group_display_name, file_name, evaluation_status, evaluation_started_at, evaluation_error "
                "FROM mod_file_eval_submissions WHERE activity_id = ?",
                (activity_id,),
            ).fetchall()

            counts = {"total": len(subs), "pending": 0, "processing": 0, "completed": 0, "error": 0, "not_started": 0}
            items = []
            threshold = _now() - EVALUATION_TIMEOUT_SECONDS

            for s in subs:
                status = s["evaluation_status"] or "not_started"
                if status == STATUS_PROCESSING and s.get("evaluation_started_at") and s["evaluation_started_at"] < threshold:
                    status = "timeout"

                bucket = status if status in counts else ("error" if status == "timeout" else "not_started")
                counts[bucket] = counts.get(bucket, 0) + 1

                items.append({
                    "file_submission_id": s["id"],
                    "file_name": s["file_name"],
                    "group_code": s.get("group_code"),
                    "group_display_name": s.get("group_display_name"),
                    "status": status,
                    "error": s.get("evaluation_error"),
                    "started_at": s.get("evaluation_started_at"),
                })

            if counts["processing"] > 0 or counts["pending"] > 0:
                overall = "in_progress"
            elif counts["error"] > 0:
                overall = "completed_with_errors"
            elif counts["completed"] > 0:
                overall = "completed"
            else:
                overall = "idle"

            return {"overall_status": overall, "counts": counts, "submissions": items}
        finally:
            conn.close()

    # ── Start (mark as pending) ───────────────────────────────────────────

    def start_evaluation(self, activity_id: int, file_submission_ids: List[str]) -> Dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            return {"success": False, "message": "No DB", "queued": 0}
        try:
            conn.row_factory = _dict_factory
            placeholders = ",".join("?" for _ in file_submission_ids)
            subs = conn.execute(
                f"SELECT id, evaluation_status, evaluation_started_at FROM mod_file_eval_submissions "
                f"WHERE id IN ({placeholders}) AND activity_id = ?",
                (*file_submission_ids, activity_id),
            ).fetchall()

            if not subs:
                return {"success": False, "message": "No submissions found", "queued": 0}

            threshold = _now() - EVALUATION_TIMEOUT_SECONDS
            to_queue, already = [], []

            for s in subs:
                st = s["evaluation_status"]
                if st in (STATUS_PENDING, STATUS_PROCESSING):
                    if st == STATUS_PROCESSING and s.get("evaluation_started_at") and s["evaluation_started_at"] < threshold:
                        to_queue.append(s["id"])
                    else:
                        already.append(s["id"])
                else:
                    to_queue.append(s["id"])

            now = _now()
            for sid in to_queue:
                conn.execute(
                    "UPDATE mod_file_eval_submissions SET evaluation_status = ?, evaluation_started_at = ?, evaluation_error = NULL WHERE id = ?",
                    (STATUS_PENDING, now, sid),
                )
            conn.commit()

            return {"success": True, "message": f"{len(to_queue)} queued", "queued": len(to_queue),
                    "queued_ids": to_queue, "already_processing": already}
        except Exception as exc:
            logger.error(f"start_evaluation error: {exc}")
            return {"success": False, "message": str(exc), "queued": 0}
        finally:
            conn.close()

    # ── Process batch (runs in BackgroundTasks) ───────────────────────────

    async def process_evaluation_batch(
        self,
        activity_id: int,
        file_submission_ids: List[str],
        evaluator_id: str,
    ) -> Dict[str, Any]:
        from .evaluator_client import EvaluatorClient
        from .document_extractor import DocumentExtractor
        from .grade_service import GradeService

        grade_svc = GradeService()
        results: Dict[str, Any] = {"created": 0, "updated": 0, "errors": []}

        for fsid in file_submission_ids:
            conn = self.db.get_connection()
            if not conn:
                results["errors"].append({"id": fsid, "error": "No DB"})
                continue

            try:
                conn.row_factory = _dict_factory
                sub = conn.execute("SELECT * FROM mod_file_eval_submissions WHERE id = ?", (fsid,)).fetchone()
                if not sub:
                    results["errors"].append({"id": fsid, "error": "Not found"})
                    continue

                conn.execute(
                    "UPDATE mod_file_eval_submissions SET evaluation_status = ?, evaluation_started_at = ? WHERE id = ?",
                    (STATUS_PROCESSING, _now(), fsid),
                )
                conn.commit()
            finally:
                conn.close()

            # Extract text
            try:
                text = DocumentExtractor.extract_text_from_file(sub["file_path"])
                if not text or not text.strip():
                    self._mark_error(fsid, "Could not extract text from document")
                    results["errors"].append({"id": fsid, "error": "Empty text"})
                    continue
            except Exception as exc:
                self._mark_error(fsid, f"Text extraction: {exc}")
                results["errors"].append({"id": fsid, "error": str(exc)})
                continue

            # Call evaluator
            try:
                eval_result = await EvaluatorClient.evaluate_text(text, int(evaluator_id))
            except Exception as exc:
                self._mark_error(fsid, f"Evaluator: {exc}")
                results["errors"].append({"id": fsid, "error": str(exc)})
                continue

            if not eval_result.get("success"):
                self._mark_error(fsid, eval_result.get("error", "Unknown"))
                results["errors"].append({"id": fsid, "error": eval_result.get("error")})
                continue

            parsed = EvaluatorClient.parse_evaluation_response(eval_result)
            if not parsed.get("success"):
                self._mark_error(fsid, parsed.get("error", "Parse failure"))
                results["errors"].append({"id": fsid, "error": parsed.get("error")})
                continue

            ai_score = parsed.get("score")
            ai_comment = parsed.get("comment", "")

            existing = grade_svc.get_grade_by_submission(fsid)
            grade_svc.upsert_ai_grade(fsid, ai_score, ai_comment)
            if existing:
                results["updated"] += 1
            else:
                results["created"] += 1

            self._mark_completed(fsid)

        return results

    # ── Reset stuck ───────────────────────────────────────────────────────

    def reset_stuck(self, activity_id: int) -> int:
        conn = self.db.get_connection()
        if not conn:
            return 0
        try:
            threshold = _now() - EVALUATION_TIMEOUT_SECONDS
            cur = conn.execute(
                "UPDATE mod_file_eval_submissions SET evaluation_status = ?, evaluation_error = 'Timed out' "
                "WHERE activity_id = ? AND evaluation_status = ? AND evaluation_started_at < ?",
                (STATUS_ERROR, activity_id, STATUS_PROCESSING, threshold),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _mark_error(self, fsid: str, error: str):
        conn = self.db.get_connection()
        if not conn:
            return
        try:
            conn.execute(
                "UPDATE mod_file_eval_submissions SET evaluation_status = ?, evaluation_error = ? WHERE id = ?",
                (STATUS_ERROR, error, fsid),
            )
            conn.commit()
        finally:
            conn.close()

    def _mark_completed(self, fsid: str):
        conn = self.db.get_connection()
        if not conn:
            return
        try:
            conn.execute(
                "UPDATE mod_file_eval_submissions SET evaluation_status = ?, evaluation_error = NULL WHERE id = ?",
                (STATUS_COMPLETED, fsid),
            )
            conn.commit()
        finally:
            conn.close()
