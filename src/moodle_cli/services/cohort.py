"""Cohort service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class Cohort(BaseModel):
    id: int
    name: str = ""
    idnumber: str = ""
    description: str = ""
    visible: bool = True


class CohortService(BaseService):
    def list_cohorts(self) -> list[Cohort]:
        data = self.call("core_cohort_get_cohorts")
        return [Cohort(**c) for c in data]

    def create_cohort(
        self,
        name: str,
        categorytype_type: str = "system",
        categorytype_value: str = "",
        idnumber: str = "",
        description: str = "",
    ) -> Cohort:
        cohort_data: dict[str, Any] = {
            "categorytype": {"type": categorytype_type, "value": categorytype_value},
            "name": name,
            "idnumber": idnumber,
            "description": description,
        }
        data = self.call("core_cohort_create_cohorts", cohorts=[cohort_data])
        return Cohort(**data[0])

    def delete_cohorts(self, cohort_ids: list[int]) -> None:
        self.call("core_cohort_delete_cohorts", cohortids=cohort_ids)

    def add_members(self, cohort_id: int, user_ids: list[int]) -> None:
        members = [{"cohortid": cohort_id, "userid": uid} for uid in user_ids]
        self.call("core_cohort_add_cohort_members", members=members)

    def remove_members(self, cohort_id: int, user_ids: list[int]) -> None:
        members = [{"cohortid": cohort_id, "userid": uid} for uid in user_ids]
        self.call("core_cohort_delete_cohort_members", members=members)
