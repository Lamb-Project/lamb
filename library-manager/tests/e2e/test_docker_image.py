"""E2E Docker smoke: the real shipping image boots, serves, and runs non-root.

Builds ``library-manager/Dockerfile`` once, runs the container, and validates
the actual deployment artifact end-to-end: health, plugin listing, non-root
user, and one real import over the mapped host port. Skips cleanly when no
Docker daemon is available.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from _helpers import AUTH_HEADERS, library_payload, poll_until_ready_sync, text_file

from ._docker import Container, build_image, docker_available

pytestmark = [pytest.mark.slow, pytest.mark.needs_docker]

if not docker_available():
    pytest.skip("Docker daemon not available", allow_module_level=True)

_EXPECTED_PLUGINS = {
    "simple_import",
    "markitdown_import",
    "markitdown_plus_import",
    "url_import",
    "youtube_transcript_import",
}


@pytest.fixture(scope="module")
def container() -> Iterator[Container]:
    """Build the real image and run it once for the module."""
    build_image(timeout=900.0)
    c = Container.run("lamb-library-manager-e2e")
    try:
        c.wait_healthy(timeout=90.0)
        yield c
    finally:
        c.stop()


def test_health_over_mapped_port(container: Container) -> None:
    """GET /health on the mapped host port → 200 with status ok."""
    r = httpx.get(f"{container.base_url}/health", timeout=10.0)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok", r.text


def test_plugins_listed_in_container(container: Container) -> None:
    """The containerized service lists all five import plugins."""
    r = httpx.get(
        f"{container.base_url}/plugins", headers=AUTH_HEADERS, timeout=10.0
    )
    assert r.status_code == 200, r.text
    names = {p["name"] for p in r.json()["plugins"]}
    assert names >= _EXPECTED_PLUGINS, names


def test_runs_as_non_root(container: Container) -> None:
    """The container process runs as the unprivileged 'appuser', not root."""
    result = container.exec("whoami")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "appuser", result.stdout


def test_real_import_in_container(container: Container) -> None:
    """A real simple_import inside the container reaches 'ready' over HTTP."""
    with httpx.Client(
        base_url=container.base_url, headers=AUTH_HEADERS, timeout=30.0
    ) as c:
        lib = library_payload()
        assert c.post("/libraries", json=lib).status_code == 201
        resp = c.post(
            f"/libraries/{lib['id']}/import/file",
            files=text_file("# Docker\n\ncontainer import body", "docker.md"),
            data={"plugin_name": "simple_import", "title": "Docker Doc"},
        )
        assert resp.status_code == 202, resp.text
        item_id = resp.json()["item_id"]
        status = poll_until_ready_sync(c, lib["id"], item_id, timeout=40)
    assert status == "ready", status
