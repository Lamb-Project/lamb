"""File service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class MoodleFile(BaseModel):
    filename: str = ""
    filepath: str = ""
    filesize: int = 0
    fileurl: str = ""
    timecreated: int = 0
    timemodified: int = 0
    mimetype: str = ""


class FileService(BaseService):
    def list_files(
        self,
        contextid: int,
        component: str = "user",
        filearea: str = "private",
        itemid: int = 0,
        filepath: str = "/",
    ) -> list[MoodleFile]:
        data = self.call(
            "core_files_get_files",
            contextid=contextid,
            component=component,
            filearea=filearea,
            itemid=itemid,
            filepath=filepath,
        )
        return [MoodleFile(**f) for f in data.get("files", [])]

    def upload(
        self,
        file_path: str,
        component: str = "user",
        filearea: str = "draft",
        itemid: int = 0,
    ) -> dict[str, Any]:
        """Upload a file to Moodle's draft area.

        Note: This uses a separate upload endpoint, not the REST API.
        """
        import httpx

        url = f"{self.client.base_url}/webservice/upload.php"
        with open(file_path, "rb") as f:
            resp = httpx.post(
                url,
                data={
                    "token": self.client.token,
                    "component": component,
                    "filearea": filearea,
                    "itemid": str(itemid),
                },
                files={"file_1": f},
                timeout=60.0,
            )
        resp.raise_for_status()
        return resp.json()
