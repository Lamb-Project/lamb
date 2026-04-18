"""Site information service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class SiteInfo(BaseModel):
    sitename: str
    siteurl: str
    username: str
    fullname: str
    userid: int
    lang: str
    release: str
    version: str
    functions: list[dict[str, Any]] = []


class SiteFunction(BaseModel):
    name: str
    version: str = ""


class SiteService(BaseService):
    def get_site_info(self) -> SiteInfo:
        data = self.call("core_webservice_get_site_info")
        return SiteInfo(**data)

    def get_functions(self) -> list[SiteFunction]:
        info = self.call("core_webservice_get_site_info")
        return [SiteFunction(**f) for f in info.get("functions", [])]
