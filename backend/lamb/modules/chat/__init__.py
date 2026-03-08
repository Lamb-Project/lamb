from lamb.modules.base import ActivityModule, SetupField, LTIContext
from lamb.modules.chat.service import ChatModuleService
from fastapi.responses import RedirectResponse
from fastapi import HTTPException
from lamb.database_manager import LambDatabaseManager
from typing import Dict, Any, List, Optional
import os


class ChatModule(ActivityModule):
    name = "chat"
    display_name = "AI Chat Activity"
    description = "Students interact with AI assistants in a chat interface."

    def __init__(self):
        self.service = ChatModuleService()
        self.db_manager = LambDatabaseManager()

    def _get_owi_redirect_url(self, owi_token: str) -> str:
        """Build the OWI redirect URL with token."""
        import config
        owi_public = (os.getenv("OWI_PUBLIC_BASE_URL")
                      or os.getenv("OWI_BASE_URL")
                      or config.OWI_PUBLIC_BASE_URL)
        return f"{owi_public}/api/v1/auths/complete?token={owi_token}"

    def get_migrations(self):
        return []

    def get_routers(self):
        return []

    def get_setup_fields(self):
        return [
            SetupField(
                name="chat_visibility_enabled",
                label="Allow instructors to review anonymized chat transcripts",
                field_type="checkbox",
                required=False
            )
        ]

    def on_activity_configured(self, activity_id, setup_data):
        """Called after the router saves the activity DB record.
        Creates the OWI group and adds assistant model permissions.
        """
        self.service.configure_activity(activity_id, setup_data)

    def on_activity_reconfigured(self, activity, added_ids, removed_ids):
        """Update OWI model permissions when assistants change."""
        from lamb.owi_bridge.owi_database import OwiDatabaseManager
        from lamb.owi_bridge.owi_model import OWIModel

        owi_group_id = activity['owi_group_id']
        owi_db = OwiDatabaseManager()
        owi_model = OWIModel(owi_db)

        for aid in added_ids:
            owi_model.add_group_to_model(f"lamb_assistant.{aid}", owi_group_id, "read")
        for aid in removed_ids:
            owi_model.remove_group_from_model(f"lamb_assistant.{aid}", owi_group_id, "read")

    def on_student_launch(self, ctx: LTIContext):
        """Called when a student launches an activity of this type."""
        activity = self.db_manager.get_lti_activity_by_resource_link(ctx.resource_link_id)
        if not activity:
             raise HTTPException(status_code=404, detail="Activity not found")

        owi_token = self.service.handle_student_launch(
            activity=activity,
            username=ctx.username,
            display_name=ctx.display_name,
            lms_user_id=ctx.lms_user_id
        )
        if not owi_token:
            raise HTTPException(status_code=500, detail="Failed to process chat launch")

        return RedirectResponse(url=self._get_owi_redirect_url(owi_token), status_code=303)

    def on_instructor_launch(self, ctx: LTIContext):
        """Called when an instructor launches an activity of this type."""
        from lamb.lti_router import _create_dashboard_jwt
        from lamb.lti_activity_manager import LtiActivityManager

        activity = self.db_manager.get_lti_activity_by_resource_link(ctx.resource_link_id)
        if not activity:
             raise HTTPException(status_code=404, detail="Activity not found")

        lti_manager = LtiActivityManager()
        instructor_email = lti_manager.generate_student_email(ctx.username, ctx.resource_link_id)
        instructor_user = {"email": instructor_email, "display_name": ctx.display_name}

        public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:8000") 

        dashboard_token = _create_dashboard_jwt(
            activity, instructor_user,
            lms_user_id=ctx.lms_user_id,
            lms_email=ctx.lms_email,
            username=ctx.username
        )
        
        return RedirectResponse(
            url=f"{public_base}/m/chat/dashboard?resource_link_id={ctx.resource_link_id}&token={dashboard_token}",
            status_code=303
        )

    def launch_user(self, activity, username, display_name, lms_user_id,
                     is_instructor=False):
        """Launch a user into OWI. Returns redirect URL or None."""
        owi_token = self.service.handle_student_launch(
            activity=activity,
            username=username,
            display_name=display_name,
            lms_user_id=lms_user_id,
            is_instructor=is_instructor,
        )
        if not owi_token:
            return None
        return self._get_owi_redirect_url(owi_token)

    def get_dashboard_stats(self, activity):
        return self.service.get_dashboard_stats(activity)

    def get_dashboard_chats(self, activity, assistant_id=None, page=1, per_page=20):
        return self.service.get_dashboard_chats(activity, assistant_id, page, per_page)

    def get_dashboard_chat_detail(self, activity, chat_id):
        return self.service.get_dashboard_chat_detail(activity, chat_id)

    def get_frontend_build_path(self):
        return None

module = ChatModule()
