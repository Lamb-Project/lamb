"""JSON output renderer."""

from __future__ import annotations

import json as _json
from typing import Any

from moodle_cli.output.console import console


def render_json(data: Any) -> None:
    """Pretty-print data as JSON."""
    console.print_json(_json.dumps(data, default=str))
