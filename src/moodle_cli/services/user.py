"""User service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class User(BaseModel):
    id: int
    username: str = ""
    fullname: str = ""
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    department: str = ""
    institution: str = ""
    profileimageurl: str = ""


class UserService(BaseService):
    def get_me(self) -> User:
        data = self.call("core_webservice_get_site_info")
        return User(
            id=data["userid"],
            username=data["username"],
            fullname=data["fullname"],
            firstname=data.get("firstname", ""),
            lastname=data.get("lastname", ""),
        )

    def list_users(self, key: str = "email", value: str = "") -> list[User]:
        data = self.call(
            "core_user_get_users",
            criteria=[{"key": key, "value": value}],
        )
        return [User(**u) for u in data.get("users", [])]

    def get_user(self, user_id: int) -> User:
        data = self.call(
            "core_user_get_users_by_field",
            field="id",
            values=[str(user_id)],
        )
        return User(**data[0])

    def create_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
        **kwargs: Any,
    ) -> User:
        user_data = {
            "username": username,
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "password": password,
            **kwargs,
        }
        data = self.call("core_user_create_users", users=[user_data])
        return User(**data[0])

    def update_user(self, user_id: int, **kwargs: Any) -> None:
        user_data = {"id": user_id, **kwargs}
        self.call("core_user_update_users", users=[user_data])

    def delete_users(self, user_ids: list[int]) -> None:
        self.call("core_user_delete_users", userids=user_ids)
