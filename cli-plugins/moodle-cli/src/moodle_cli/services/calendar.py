"""Calendar service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class CalendarEvent(BaseModel):
    id: int
    name: str = ""
    description: str = ""
    eventtype: str = ""
    courseid: int = 0
    timestart: int = 0
    timeduration: int = 0


class CalendarService(BaseService):
    def get_events(self, course_ids: list[int] | None = None) -> list[CalendarEvent]:
        events: dict[str, Any] = {}
        options: dict[str, Any] = {"userevents": 1, "siteevents": 1}
        if course_ids:
            events["courseids"] = course_ids
        data = self.call(
            "core_calendar_get_calendar_events",
            events=events,
            options=options,
        )
        return [CalendarEvent(**e) for e in data.get("events", [])]

    def create_event(
        self,
        name: str,
        eventtype: str = "user",
        timestart: int = 0,
        timeduration: int = 0,
        description: str = "",
        courseid: int = 0,
    ) -> CalendarEvent:
        event_data: dict[str, Any] = {
            "name": name,
            "eventtype": eventtype,
            "timestart": timestart,
            "timeduration": timeduration,
            "description": description,
        }
        if courseid:
            event_data["courseid"] = courseid
        data = self.call("core_calendar_create_calendar_events", events=[event_data])
        return CalendarEvent(**data["events"][0])
