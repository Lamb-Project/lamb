"""Tests for course service."""

from __future__ import annotations

import respx
from httpx import Response

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.services.course import CourseService
from tests.conftest import BASE_URL, TOKEN, load_fixture


class TestCourseService:
    @respx.mock
    def test_list_courses(self) -> None:
        fixture = load_fixture("courses")
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=fixture)
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        courses = svc.list_courses()

        assert len(courses) == 2
        assert courses[1].shortname == "MATH101"
        assert courses[1].fullname == "Introduction to Mathematics"

    @respx.mock
    def test_get_course(self) -> None:
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=[{
                "id": 2,
                "shortname": "MATH101",
                "fullname": "Introduction to Mathematics",
                "categoryid": 1,
            }])
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        course = svc.get_course(2)

        assert course.id == 2
        assert course.shortname == "MATH101"

    @respx.mock
    def test_search_courses(self) -> None:
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json={
                "courses": [{
                    "id": 2,
                    "shortname": "MATH101",
                    "fullname": "Introduction to Mathematics",
                    "categoryid": 1,
                }],
                "total": 1,
            })
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        results = svc.search_courses("math")

        assert len(results) == 1
        assert results[0].shortname == "MATH101"
