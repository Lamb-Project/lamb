from lamb.modules.base import ActivityModule, SetupField, LTIContext
from lamb.modules.file_evaluation.service import FileEvalService
from . import migrations as _fe_migrations
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, HTTPException
from lamb.database_manager import LambDatabaseManager
from lamb import auth as lamb_auth
from lamb.logging_config import get_logger
from lamb.lti_activity_manager import LtiActivityManager
from typing import Dict, Any, List, Optional
from datetime import timedelta
import os
import json

logger = get_logger(__name__, component="FILE_EVAL_MODULE")


class FileEvalModule(ActivityModule):
    name = "file_evaluation"
    display_name = "File Evaluation"
    description = "Students submit files; AI evaluates them; instructor reviews and sends grades to the LMS."

    def __init__(self):
        self.service = FileEvalService()
        self.db_manager = LambDatabaseManager()

    def _create_file_eval_jwt(self, activity: Dict[str, Any], user_email: str,
                               display_name: str, lms_user_id: str,
                               is_instructor: bool, lis_result_sourcedid: str = None) -> str:
        data = {
            "lti_type": "file_eval",
            "lti_resource_link_id": activity["resource_link_id"],
            "lti_activity_id": activity["id"],
            "lti_user_email": user_email,
            "lti_display_name": display_name,
            "lti_lms_user_id": lms_user_id,
            "is_instructor": is_instructor,
        }
        if lis_result_sourcedid:
            data["lis_result_sourcedid"] = lis_result_sourcedid
        return lamb_auth.create_token(data, expires_delta=timedelta(days=7))

    def get_migrations(self):
        # Fresh read: prefix must match LambDatabaseManager (same env as core DB schema).
        p = LambDatabaseManager().table_prefix
        return [s.format(table_prefix=p) for s in _fe_migrations.MIGRATION_SQL]

    def get_routers(self):
        from lamb.modules.file_evaluation.router import router
        return [router]

    def get_setup_fields(self):
        return [
            SetupField(
                name="evaluator_id",
                label="Evaluator assistant ID",
                field_type="text",
                required=False,
            ),
            SetupField(
                name="submission_type",
                label="Submission type",
                field_type="select",
                required=True,
                options=[
                    {"value": "individual", "label": "Individual"},
                    {"value": "group", "label": "Group"},
                ],
            ),
            SetupField(
                name="max_group_size",
                label="Max group size",
                field_type="number",
                required=False,
            ),
            SetupField(
                name="deadline",
                label="Deadline",
                field_type="datetime",
                required=False,
            ),
            SetupField(
                name="language",
                label="Language",
                field_type="select",
                required=False,
                options=[
                    {"value": "en", "label": "English"},
                    {"value": "es", "label": "Español"},
                    {"value": "ca", "label": "Català"},
                    {"value": "eu", "label": "Euskara"},
                ],
            ),
        ]

    def on_activity_configured(self, activity_id, setup_data):
        """Called after the router saves the activity DB record.
        Persists module-specific fields into lti_activities.setup_config JSON.
        """
        ev = setup_data.get("evaluator_id")
        aids = setup_data.get("assistant_ids") or []
        if not ev and aids:
            ev = str(aids[0])
        module_fields = {
            "evaluator_id": ev,
            "submission_type": setup_data.get("submission_type", "individual"),
            "max_group_size": setup_data.get("max_group_size"),
            "deadline": setup_data.get("deadline"),
            "language": setup_data.get("language", "en"),
        }

        conn = self.db_manager.get_connection()
        if not conn:
            return
        pfx = self.db_manager.table_prefix
        tbl = f"{pfx}lti_activities"
        try:
            existing_raw = conn.execute(
                f"SELECT setup_config FROM {tbl} WHERE id = ?", (activity_id,)
            ).fetchone()
            existing = {}
            if existing_raw and existing_raw[0]:
                try:
                    existing = json.loads(existing_raw[0])
                except (json.JSONDecodeError, TypeError):
                    pass
            existing.update(module_fields)
            conn.execute(
                f"UPDATE {tbl} SET setup_config = ? WHERE id = ?",
                (json.dumps(existing), activity_id),
            )
            conn.commit()
            logger.info(f"Saved setup_config for activity {activity_id}")
        finally:
            conn.close()

    def on_activity_reconfigured(self, activity, added_ids, removed_ids):
        pass

    def on_student_launch(self, ctx: LTIContext):
        """Called when a student launches an activity of this type."""
        activity = self.db_manager.get_lti_activity_by_resource_link(ctx.resource_link_id)
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        manager = LtiActivityManager()
        student_email = manager.generate_student_email(ctx.username, ctx.resource_link_id)

        token = self._create_file_eval_jwt(
            activity, student_email, ctx.display_name,
            ctx.lms_user_id, is_instructor=False,
        )

        public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:9099")
        # Numeric activity_id is required by /lamb/v1/modules/file_evaluation/... path params;
        # resource_link_id alone is a UUID and cannot be used as activity_id.
        url = (
            f"{public_base}/m/file-eval/upload"
            f"?activity_id={activity['id']}&resource_link_id={ctx.resource_link_id}&token={token}"
        )
        return RedirectResponse(url=url, status_code=303)

    def on_instructor_launch(self, ctx: LTIContext):
        """Called when an instructor launches an activity of this type."""
        activity = self.db_manager.get_lti_activity_by_resource_link(ctx.resource_link_id)
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        logger.info(f"FileEvalModule.on_instructor_launch called for activity {ctx.resource_link_id}")
        logger.info(f"  Instructor: {ctx.display_name} ({ctx.lms_email})")

        manager = LtiActivityManager()
        instructor_email = manager.generate_student_email(ctx.username, ctx.resource_link_id)

        token = self._create_file_eval_jwt(
            activity, instructor_email, ctx.display_name,
            ctx.lms_user_id, is_instructor=True,
        )

        public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:9099")
        redirect_url = (
            f"{public_base}/m/file-eval/grading"
            f"?activity_id={activity['id']}&resource_link_id={ctx.resource_link_id}&token={token}"
        )
        logger.info(f"Redirecting to grading: {redirect_url}")

        return RedirectResponse(url=redirect_url, status_code=303)

    def launch_user(self, activity, username, display_name, lms_user_id,
                     is_instructor=False):
        """Launch a user into this activity. Returns redirect URL or None."""
        manager = LtiActivityManager()
        user_email = manager.generate_student_email(username, activity["resource_link_id"])
        token = self._create_file_eval_jwt(
            activity, user_email, display_name, lms_user_id, is_instructor,
        )
        public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:9099")
        page = "grading" if is_instructor else "upload"
        return (
            f"{public_base}/m/file-eval/{page}"
            f"?activity_id={activity['id']}&resource_link_id={activity['resource_link_id']}&token={token}"
        )

    def get_dashboard_stats(self, activity):
        return self.service.get_dashboard_stats(activity["id"])

    def get_dashboard_chats(self, activity, assistant_id=None, page=1, per_page=20):
        return {"chats": [], "total": 0}

    def get_dashboard_chat_detail(self, activity, chat_id):
        return None

    def get_frontend_build_path(self):
        return None

module = FileEvalModule()
