"""Pytest configuration for the backend test suite.

The `test_*` files listed below are NOT pytest tests — they are manually-run
helper scripts (token minting for the workshop E2E flow) that execute side
effects at import time. Exclude them here so a bare `pytest` run does not
import or collect them.
"""
collect_ignore = [
    "test_mint_edge.py",
    "test_mint_e2e.py",
]