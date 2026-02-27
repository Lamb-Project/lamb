from lamb.modules.base import ActivityModule, SetupField, LTIContext
from lamb.modules.chat.service import ChatModuleService
from fastapi.responses import RedirectResponse
from fastapi import HTTPException
from lamb.database_manager import LambDatabaseManager
import os


class ChatModule(ActivityModule):
    name = "chat"
    display_name = "AI Chat Activity"
    description = "Students interact with AI assistants in a chat interface."

    def __init__(self):
        self.service = ChatModuleService()
        self.db_manager = LambDatabaseManager()

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
        """Called when an instructor finishes the setup form."""
        self.service.configure_activity(activity_id, setup_data)

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

        # Get OWI redirect URL
        import config
        owi_public = (os.getenv("OWI_PUBLIC_BASE_URL")
                      or os.getenv("OWI_BASE_URL")
                      or config.OWI_PUBLIC_BASE_URL)
        redirect_url = f"{owi_public}/api/v1/auths/complete?token={owi_token}"
        
        return RedirectResponse(url=redirect_url, status_code=303)


    def on_instructor_launch(self, ctx: LTIContext):
        """Called when an instructor launches an activity of this type."""
        from lamb.lti_router import _create_token, DASHBOARD_TOKEN_TTL
        activity = self.db_manager.get_lti_activity_by_resource_link(ctx.resource_link_id)
        if not activity:
             raise HTTPException(status_code=404, detail="Activity not found")
        
        is_owner = (ctx.lms_email and ctx.lms_email == activity.get('owner_email'))
        
        # We need the request base url. While not in context directly, it's safer to use the env var
        public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:8000") 

        dashboard_token = _create_token({
            "type": "dashboard",
            "resource_link_id": ctx.resource_link_id,
            "lms_user_id": ctx.lms_user_id,
            "lms_email": ctx.lms_email,
            "username": ctx.username,
            "display_name": ctx.display_name,
            "is_owner": is_owner,
        }, ttl=DASHBOARD_TOKEN_TTL)
        
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/dashboard?resource_link_id={ctx.resource_link_id}&token={dashboard_token}",
            status_code=303
        )

    def get_frontend_build_path(self):
        return None

module = ChatModule()
