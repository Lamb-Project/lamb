"""
Sandbox execution tool stub — secure Python sandbox.

Always refuses: no flag or setting enables execution. The definition is kept so
the wizard can show the tool as unavailable. A real sandbox was deliberately
not built (decision D7, see Documentation/workshop-design.md §5).
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