"""Session-scoped fixtures for LAMB CLI E2E tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

from helpers.cli_runner import LambCLI

# Load .env from testing/cli/
load_dotenv(Path(__file__).parent / ".env")

ADMIN_EMAIL = os.getenv("LOGIN_EMAIL", "admin@owi.com")
ADMIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "admin")
SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")


def login_as(email: str, password: str) -> str:
    """Log in via HTTP and return a JWT token."""
    with httpx.Client(base_url=SERVER_URL, timeout=30, follow_redirects=True) as c:
        resp = c.post(
            "/creator/login",
            data={"email": email, "password": password},
        )
        resp.raise_for_status()
        body = resp.json()
        assert body.get("success"), f"Login failed for {email}: {body}"
        return body["data"]["token"]


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Authenticate as admin once and return the JWT token."""
    return login_as(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def cli(admin_token: str) -> LambCLI:
    """Authenticated CLI runner (admin)."""
    return LambCLI(server_url=SERVER_URL, token=admin_token)


@pytest.fixture(scope="session")
def unauthenticated_cli() -> LambCLI:
    """CLI runner with no token."""
    return LambCLI(server_url=SERVER_URL, token=None)


@pytest.fixture(scope="session")
def timestamp() -> str:
    """Unique timestamp string for tagging test resources."""
    return str(int(time.time() * 1000))


@pytest.fixture(scope="session")
def fixture_file_path() -> Path:
    """Path to the ikasiker_fixture.txt test file."""
    p = Path(__file__).resolve().parent.parent / "playwright" / "fixtures" / "ikasiker_fixture.txt"
    assert p.exists(), f"Fixture file not found: {p}"
    return p


@pytest.fixture(scope="session")
def server_url() -> str:
    return SERVER_URL


@pytest.fixture(scope="session", autouse=True)
def session_cleanup(cli: LambCLI, timestamp: str):
    """Best-effort cleanup of leaked resources after all tests."""
    yield
    # Cleanup any KBs tagged with our timestamp
    result = cli.run_json("kb", "list")
    if result.success:
        kbs = result.json
        if isinstance(kbs, dict):
            kbs = kbs.get("knowledge_bases", [])
        for kb in kbs:
            name = kb.get("name", "")
            if timestamp in name:
                cli.run("kb", "delete", str(kb["id"]), "--confirm")

    # Cleanup any assistants tagged with our timestamp
    result = cli.run_json("assistant", "list")
    if result.success:
        assistants = result.json
        if isinstance(assistants, dict):
            assistants = assistants.get("assistants", [])
        for a in assistants:
            name = a.get("name", "")
            if timestamp in name:
                aid = str(a.get("id") or a.get("assistant_id", ""))
                if aid:
                    cli.run("assistant", "delete", aid, "--confirm")

    # Cleanup any orgs tagged with our timestamp
    result = cli.run_json("org", "list")
    if result.success:
        orgs = result.json
        if isinstance(orgs, list):
            for org in orgs:
                slug = org.get("slug", "")
                if timestamp in slug:
                    cli.run("org", "delete", slug, "--confirm")
