"""Workshop module — an AI-building activity for students.

Contract-aligned with the #277 ActivityModule design so it can be migrated
into the module framework once that lands. Implements its own minimal
activity_type dispatch on the current main/dev branch.
"""

from fastapi import APIRouter


class WorkshopModule:
    name = "workshop"
    display_name = "AI Workshop"

    # ── Contract (aligned with #277 ActivityModule) ──
    def get_migrations(self):
        """Return migrations owned by this module (Phase 4 may register)."""
        return []

    def get_routers(self) -> list:
        """Return the module's FastAPI routers."""
        from .routers import router
        return [router]

    def get_setup_fields(self):
        return []

    def on_activity_configured(self, ctx):
        """Called when an activity is configured as workshop."""
        pass

    def on_activity_reconfigured(self, ctx):
        """Called when an activity is reconfigured as workshop."""
        pass

    def on_student_launch(self, ctx):
        """Student launches into the build wizard — create restricted workspace."""
        from .service import initialize_workshop_workspace
        return initialize_workshop_workspace(ctx)

    def on_instructor_launch(self, ctx):
        """Instructor launches into teacher dashboard."""
        from .dashboard import workshop_dashboard_stats
        return workshop_dashboard_stats(ctx)

    def launch_user(self, ctx):
        """Launch a user into the workshop (Phase 4)."""
        from .service import initialize_workshop_workspace
        return initialize_workshop_workspace(ctx)

    def get_dashboard_stats(self, activity):
        from .dashboard import workshop_dashboard_stats
        return workshop_dashboard_stats(activity)

    def get_frontend_build_path(self):
        """Frontend SPA mount path (Phase 4)."""
        return "/m/workshop/"


module = WorkshopModule()
