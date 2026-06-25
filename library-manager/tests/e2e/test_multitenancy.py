"""E2E multi-tenancy: the org filter isolates libraries between organizations.

``GET /libraries?organization_id=<org>`` is the tenant boundary — LAMB always
scopes by org. Libraries created under org A must never appear in org B's list
and vice versa.
"""

from __future__ import annotations

import httpx
import pytest
from _helpers import library_payload, unique_id

pytestmark = pytest.mark.slow


def test_org_filter_isolates_libraries(http: httpx.Client) -> None:
    """Libraries are listed only under their own organization, never another's."""
    org_a = unique_id("orgA")
    org_b = unique_id("orgB")

    lib_a = library_payload(organization_id=org_a)
    lib_b = library_payload(organization_id=org_b)
    assert http.post("/libraries", json=lib_a).status_code == 201
    assert http.post("/libraries", json=lib_b).status_code == 201

    resp_a = http.get("/libraries", params={"organization_id": org_a})
    assert resp_a.status_code == 200, resp_a.text
    ids_a = {lib["id"] for lib in resp_a.json()["libraries"]}
    assert lib_a["id"] in ids_a
    assert lib_b["id"] not in ids_a

    resp_b = http.get("/libraries", params={"organization_id": org_b})
    assert resp_b.status_code == 200, resp_b.text
    ids_b = {lib["id"] for lib in resp_b.json()["libraries"]}
    assert lib_b["id"] in ids_b
    assert lib_a["id"] not in ids_b


def test_org_a_library_absent_from_org_b(http: httpx.Client) -> None:
    """A library created under org A is not visible in org B's list at all."""
    org_a = unique_id("orgA")
    org_b = unique_id("orgB")
    lib_a = library_payload(organization_id=org_a)
    assert http.post("/libraries", json=lib_a).status_code == 201

    resp_b = http.get("/libraries", params={"organization_id": org_b})
    assert resp_b.status_code == 200, resp_b.text
    body = resp_b.json()
    assert all(lib["id"] != lib_a["id"] for lib in body["libraries"]), body
