"""Role assignment service."""

from __future__ import annotations

from moodle_cli.services.base import BaseService


class RoleService(BaseService):
    def assign_role(self, role_id: int, user_id: int, context_id: int) -> None:
        self.call(
            "core_role_assign_roles",
            assignments=[
                {"roleid": role_id, "userid": user_id, "contextid": context_id}
            ],
        )

    def unassign_role(self, role_id: int, user_id: int, context_id: int) -> None:
        self.call(
            "core_role_unassign_roles",
            unassignments=[
                {"roleid": role_id, "userid": user_id, "contextid": context_id}
            ],
        )
