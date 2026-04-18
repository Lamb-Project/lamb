"""Quiz service."""

from __future__ import annotations

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class Quiz(BaseModel):
    id: int
    course: int = 0
    coursemodule: int = 0
    name: str = ""
    timeopen: int = 0
    timeclose: int = 0
    grade: float = 0


class QuizAttempt(BaseModel):
    id: int
    quiz: int = 0
    userid: int = 0
    attempt: int = 0
    state: str = ""
    grade: float | None = None
    timestart: int = 0
    timefinish: int = 0


class QuizService(BaseService):
    def list_quizzes(self, course_id: int) -> list[Quiz]:
        data = self.call("mod_quiz_get_quizzes_by_courses", courseids=[course_id])
        return [Quiz(**q) for q in data.get("quizzes", [])]

    def get_attempts(self, quiz_id: int, user_id: int | None = None) -> list[QuizAttempt]:
        params = {"quizid": quiz_id, "status": "all"}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("mod_quiz_get_user_attempts", **params)
        return [QuizAttempt(**a) for a in data.get("attempts", [])]
