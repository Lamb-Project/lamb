"""Forum service."""

from __future__ import annotations

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class Forum(BaseModel):
    id: int
    course: int = 0
    name: str = ""
    type: str = ""
    intro: str = ""


class Discussion(BaseModel):
    id: int
    name: str = ""
    subject: str = ""
    message: str = ""
    userid: int = 0
    userfullname: str = ""
    timemodified: int = 0


class ForumService(BaseService):
    def list_forums(self, course_id: int) -> list[Forum]:
        data = self.call("mod_forum_get_forums_by_courses", courseids=[course_id])
        return [Forum(**f) for f in data]

    def get_discussions(self, forum_id: int) -> list[Discussion]:
        data = self.call("mod_forum_get_forum_discussions", forumid=forum_id)
        return [Discussion(**d) for d in data.get("discussions", [])]

    def add_discussion(
        self, forum_id: int, subject: str, message: str
    ) -> int:
        data = self.call(
            "mod_forum_add_discussion",
            forumid=forum_id,
            subject=subject,
            message=message,
        )
        return data["discussionid"]
