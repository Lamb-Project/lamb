"""Assignment service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class Assignment(BaseModel):
    id: int
    cmid: int = 0
    course: int = 0
    name: str = ""
    duedate: int = 0
    grade: float = 0


class Submission(BaseModel):
    id: int
    userid: int = 0
    status: str = ""
    timemodified: int = 0
    gradingstatus: str = ""


class AssignService(BaseService):
    def list_assignments(self, course_ids: list[int] | None = None) -> list[Assignment]:
        params: dict[str, Any] = {}
        if course_ids:
            params["courseids"] = course_ids
        data = self.call("mod_assign_get_assignments", **params)
        assignments = []
        for course_data in data.get("courses", []):
            for a in course_data.get("assignments", []):
                assignments.append(Assignment(**a))
        return assignments

    def get_submissions(self, assignment_ids: list[int]) -> list[Submission]:
        data = self.call(
            "mod_assign_get_submissions", assignmentids=assignment_ids
        )
        submissions = []
        for a in data.get("assignments", []):
            for s in a.get("submissions", []):
                submissions.append(Submission(**s))
        return submissions

    def grade_submission(
        self,
        assignment_id: int,
        user_id: int,
        grade: float,
        feedback: str = "",
    ) -> None:
        self.call(
            "mod_assign_save_grade",
            assignmentid=assignment_id,
            userid=user_id,
            grade=grade,
            attemptnumber=-1,
            addattempt=0,
            workflowstate="graded",
            plugindata={"assignfeedbackcomments_editor": {"text": feedback, "format": 1}},
        )
