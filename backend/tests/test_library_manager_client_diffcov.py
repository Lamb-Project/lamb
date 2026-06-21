"""Unit tests for ``creator_interface.library_manager_client.LibraryManagerClient``.

Covers the thin async proxy methods that resolve org config and delegate to
``_request`` / ``_fetch_bytes``. Both internals are mocked (via AsyncMock and a
stubbed ``_get_library_config``) so nothing leaves the process.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from creator_interface.library_manager_client import LibraryManagerClient


def run(coro):
    return asyncio.run(coro)


def _cfg(**over):
    base = {"url": "http://lib", "token": "tok", "allowed_plugins": [],
            "external_keys": {}}
    base.update(over)
    return base


@pytest.fixture
def client(monkeypatch):
    c = LibraryManagerClient()
    monkeypatch.setattr(c, "_get_library_config", lambda creator_user=None: _cfg())
    c._request = AsyncMock(return_value={"ok": True})
    c._fetch_bytes = AsyncMock(return_value="raw-response")
    return c


def _last_request(c):
    args, kwargs = c._request.call_args
    return args, kwargs


def _last_fetch(c):
    args, kwargs = c._fetch_bytes.call_args
    return args, kwargs


class _FakeUploadFile:
    def __init__(self, filename="f.txt", content=b"data", content_type="text/plain"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self.seek_calls = []

    async def read(self):
        return self._content

    async def seek(self, pos):
        self.seek_calls.append(pos)


# ---------------------------------------------------------------------------
# import_file  (lines 215-216 — folder_id present branch)
# ---------------------------------------------------------------------------


def test_import_file_with_folder_id(client):
    f = _FakeUploadFile()
    run(client.import_file("lib1", f, "simple", "Title",
                           plugin_params={"a": 1}, api_keys={"k": "v"},
                           folder_id="fold1"))
    args, kwargs = _last_request(client)
    assert args[0] == "POST"
    assert args[1] == "/libraries/lib1/import/file"
    assert kwargs["data"]["folder_id"] == "fold1"
    assert "file" in kwargs["files"]
    assert f.seek_calls == [0]


def test_import_file_without_folder_id(client):
    f = _FakeUploadFile()
    run(client.import_file("lib1", f, "simple", "Title"))
    _, kwargs = _last_request(client)
    assert "folder_id" not in kwargs["data"]


# ---------------------------------------------------------------------------
# import_youtube  (lines 251-252, 255)
# ---------------------------------------------------------------------------


def test_import_youtube_default_language(client):
    run(client.import_youtube("lib1", "http://yt", "youtube", "Title"))
    args, kwargs = _last_request(client)
    assert args[1] == "/libraries/lib1/import/youtube"
    assert kwargs["json"]["plugin_params"]["language"] == "en"
    assert kwargs["json"]["language"] == "en"


def test_import_youtube_plugin_params_language_wins(client):
    run(client.import_youtube("lib1", "http://yt", "youtube", "Title",
                              language="en", plugin_params={"language": "es"}))
    _, kwargs = _last_request(client)
    assert kwargs["json"]["plugin_params"]["language"] == "es"
    assert kwargs["json"]["language"] == "es"


# ---------------------------------------------------------------------------
# get_tree  (273-274)
# ---------------------------------------------------------------------------


def test_get_tree(client):
    run(client.get_tree("lib1"))
    args, _ = _last_request(client)
    assert (args[0], args[1]) == ("GET", "/libraries/lib1/tree")


# ---------------------------------------------------------------------------
# folder ops (279-280, 287-288, 296-297, 304-305) + move_items (312-313)
# ---------------------------------------------------------------------------


def test_create_folder(client):
    run(client.create_folder("lib1", "New", parent_folder_id="p1"))
    args, kwargs = _last_request(client)
    assert (args[0], args[1]) == ("POST", "/libraries/lib1/folders")
    assert kwargs["json"] == {"name": "New", "parent_folder_id": "p1"}


def test_rename_folder(client):
    run(client.rename_folder("lib1", "fold1", "Renamed"))
    args, kwargs = _last_request(client)
    assert (args[0], args[1]) == ("PUT", "/libraries/lib1/folders/fold1")
    assert kwargs["json"] == {"name": "Renamed"}


def test_move_folder(client):
    run(client.move_folder("lib1", "fold1", "parent2"))
    args, kwargs = _last_request(client)
    assert (args[0], args[1]) == ("PUT", "/libraries/lib1/folders/fold1/move")
    assert kwargs["json"] == {"parent_folder_id": "parent2"}


def test_delete_folder(client):
    run(client.delete_folder("lib1", "fold1"))
    args, _ = _last_request(client)
    assert (args[0], args[1]) == ("DELETE", "/libraries/lib1/folders/fold1")


def test_move_items(client):
    run(client.move_items("lib1", ["i1", "i2"], "fold1"))
    args, kwargs = _last_request(client)
    assert (args[0], args[1]) == ("POST", "/libraries/lib1/items/move")
    assert kwargs["json"] == {"item_ids": ["i1", "i2"], "folder_id": "fold1"}


# ---------------------------------------------------------------------------
# capabilities (367-368, 373-374) + item content (388-389)
# ---------------------------------------------------------------------------


def test_get_capabilities(client):
    run(client.get_capabilities())
    args, _ = _last_request(client)
    assert (args[0], args[1]) == ("GET", "/capabilities")


def test_get_item_capabilities(client):
    run(client.get_item_capabilities("lib1", "item1"))
    args, _ = _last_request(client)
    assert args[0] == "GET"
    assert args[1] == "/libraries/lib1/items/item1/capabilities"


def test_get_item_content(client):
    out = run(client.get_item_content("lib1", "item1", "audio"))
    args, _ = _last_fetch(client)
    assert args[0] == "GET"
    assert args[1] == "/libraries/lib1/items/item1/content/audio"
    assert out == "raw-response"
