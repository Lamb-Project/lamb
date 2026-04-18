"""Grade service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class GradeItem(BaseModel):
    itemname: str | None = None
    grade: str | None = None
    grademax: float = 0
    grademin: float = 0
    feedback: str = ""


class GradeReport(BaseModel):
    usergrades: list[dict[str, Any]] = []


class GradeService(BaseService):
    def get_grades(self, course_id: int, user_id: int | None = None) -> list[GradeItem]:
        params: dict[str, Any] = {"courseid": course_id}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("gradereport_user_get_grade_items", **params)
        items = []
        for ug in data.get("usergrades", []):
            for gi in ug.get("gradeitems", []):
                items.append(GradeItem(**gi))
        return items

    def get_report(self, course_id: int, user_id: int | None = None) -> GradeReport:
        params: dict[str, Any] = {"courseid": course_id}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("gradereport_user_get_grade_items", **params)
        return GradeReport(**data)
