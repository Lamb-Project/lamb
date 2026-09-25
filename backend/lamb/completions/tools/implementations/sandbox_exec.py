"""
Sandbox execution tool stub — secure Python sandbox.

DEFAULT DISABLED. Only available when `features.sandbox_enabled` is true.
Requires separate security hardening before production use.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_sandbox_exec(args: dict) -> dict:
    """Execute Python code in a secure sandbox.

    Expected args:
        code (str): Python code to execute.

    Returns:
        dict with success bool and either output (str) or error (str).
    """
    code = (args.get("code") or "").strip()
    if not code:
        return {"success": False, "error": "No code provided"}

    # Stub: refuse all execution. Real implementation behind feature flag.
    logger.warning("sandbox_exec called but is DISABLED by default")
    return {
        "success": False,
        "error": "Sandbox execution is not enabled. Contact your administrator.",
    }