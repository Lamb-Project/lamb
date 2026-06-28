"""Helpers for bringing the e2e docker-compose stack up/down.

Supports both the modern ``docker compose`` plugin and the legacy
``docker-compose`` binary, picking whichever is on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_KB_ROOT = Path(__file__).resolve().parent.parent.parent
_COMPOSE_FILE = _KB_ROOT / "docker-compose.test.yml"


def _compose_cmd() -> list[str]:
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


def _run(args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    full_env.update(env)
    return subprocess.run(
        args,
        env=full_env,
        cwd=str(_KB_ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def compose_up(env: dict) -> None:
    _run(
        _compose_cmd() + [
            "-f",
            str(_COMPOSE_FILE),
            "up",
            "-d",
            "--wait",
        ],
        env=env,
    )


def compose_down(env: dict) -> None:
    _run(
        _compose_cmd() + [
            "-f",
            str(_COMPOSE_FILE),
            "down",
            "-v",
        ],
        env=env,
        check=False,
    )
