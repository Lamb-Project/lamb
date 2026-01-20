"""
Shared pytest configuration and fixtures for all tests.

This module provides:
- Common pytest markers for test categorization
- Shared utilities used by both unit and live tests
"""

import pytest


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", 
        "unit: marks test as unit test (fast, in-process)"
    )
    config.addinivalue_line(
        "markers", 
        "live: marks test as live server test (requires running server)"
    )


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--live-server",
        action="store",
        default="http://localhost:9090",
        help="Base URL of the live server for live tests"
    )
    parser.addoption(
        "--api-key",
        action="store",
        default="0p3n-w3bu!",
        help="API key for authentication"
    )


@pytest.fixture(scope="session")
def live_server_url(request):
    """Get the live server URL from command line."""
    return request.config.getoption("--live-server")


@pytest.fixture(scope="session")
def api_key(request):
    """Get the API key from command line."""
    return request.config.getoption("--api-key")
