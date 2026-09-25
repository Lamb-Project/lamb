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
        """Return migrations owned by this module (may register later)."""
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
        """Instructor launches into the workshop teacher dashboard.

        Returns a redirect target when ``ctx`` carries a ``public_base`` /
        ``dashboard_token`` (the LTI launch path); otherwise returns the raw
        stats for contract consumers that only want data.
        """
        from .dashboard import instructor_launch_redirect, workshop_dashboard_stats
        if ctx and (ctx.get("dashboard_token") or ctx.get("public_base")):
            return instructor_launch_redirect(ctx)
        return workshop_dashboard_stats(ctx or {})

    def launch_user(self, ctx):
        """Launch a user into the workshop."""
        from .service import initialize_workshop_workspace
        return initialize_workshop_workspace(ctx)

    def get_dashboard_stats(self, activity):
        from .dashboard import workshop_dashboard_stats
        return workshop_dashboard_stats(activity)

    def get_frontend_build_path(self):
        """Frontend SPA mount path."""
        return "/m/workshop/"


module = WorkshopModule()
