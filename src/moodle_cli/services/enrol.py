"""Enrolment service."""

from __future__ import annotations

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class EnrolledCourse(BaseModel):
    id: int
    shortname: str
    fullname: str
    enrolledusercount: int = 0
    visible: int = 1


class EnrolledUser(BaseModel):
    id: int
    username: str = ""
    fullname: str = ""
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    roles: list[dict[str, object]] = []


class EnrolService(BaseService):
    def get_my_courses(self, userid: int | None = None) -> list[EnrolledCourse]:
        params = {}
        if userid is not None:
            params["userid"] = userid
        data = self.call("core_enrol_get_users_courses", **params)
        return [EnrolledCourse(**c) for c in data]

    def list_enrolled_users(self, course_id: int) -> list[EnrolledUser]:
        data = self.call("core_enrol_get_enrolled_users", courseid=course_id)
        return [EnrolledUser(**u) for u in data]
