"""Tests for site service."""

from __future__ import annotations

import respx
from httpx import Response

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.services.site import SiteService
from tests.conftest import BASE_URL, TOKEN, load_fixture


class TestSiteService:
    @respx.mock
    def test_get_site_info(self) -> None:
        fixture = load_fixture("site_info")
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=fixture)
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = SiteService(client)
        info = svc.get_site_info()

        assert info.sitename == "Test Moodle"
        assert info.username == "admin"
        assert info.userid == 2
        assert info.release.startswith("4.3")

    @respx.mock
    def test_get_functions(self) -> None:
        fixture = load_fixture("site_info")
        respx.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=fixture)
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = SiteService(client)
        funcs = svc.get_functions()

        assert len(funcs) == 3
        assert funcs[0].name == "core_webservice_get_site_info"
