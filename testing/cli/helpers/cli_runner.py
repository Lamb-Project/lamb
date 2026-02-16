"""Subprocess wrapper for invoking the ``lamb`` CLI in tests."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CLIResult:
    """Parsed result of a CLI invocation."""

    returncode: int
    stdout: str
    stderr: str
    _json: Any = field(default=None, repr=False)

    @property
    def success(self) -> bool:
        return self.returncode == 0

    @property
    def json(self) -> Any:
        if self._json is None:
            self._json = json.loads(self.stdout)
        return self._json

    # -- assertion helpers ---------------------------------------------------

    def assert_success(self) -> "CLIResult":
        assert self.returncode == 0, (
            f"Expected exit 0, got {self.returncode}.\n"
            f"stdout: {self.stdout[:500]}\nstderr: {self.stderr[:500]}"
        )
        return self

    def assert_failure(self, expected_code: int | None = None) -> "CLIResult":
        if expected_code is not None:
            assert self.returncode == expected_code, (
                f"Expected exit {expected_code}, got {self.returncode}.\n"
                f"stderr: {self.stderr[:500]}"
            )
        else:
            assert self.returncode != 0, (
                f"Expected non-zero exit, got 0.\nstdout: {self.stdout[:500]}"
            )
        return self

    def assert_stdout_contains(self, text: str) -> "CLIResult":
        assert text in self.stdout, (
            f"Expected stdout to contain {text!r}.\nstdout: {self.stdout[:500]}"
        )
        return self

    def assert_stderr_contains(self, text: str) -> "CLIResult":
        assert text.lower() in self.stderr.lower(), (
            f"Expected stderr to contain {text!r}.\nstderr: {self.stderr[:500]}"
        )
        return self

    def assert_json_key(self, key: str, expected: Any = ...) -> "CLIResult":
        val = self.json
        # Navigate dotted paths like "data.token"
        for part in key.split("."):
            if isinstance(val, dict):
                assert part in val, f"Key {part!r} not found in {list(val.keys())}"
                val = val[part]
            elif isinstance(val, list) and part.isdigit():
                val = val[int(part)]
            else:
                raise AssertionError(f"Cannot navigate {part!r} in {type(val)}")
        if expected is not ...:
            assert val == expected, f"Expected {key}={expected!r}, got {val!r}"
        return self


class LambCLI:
    """Wraps ``subprocess.run()`` calls to the ``lamb`` binary."""

    def __init__(self, server_url: str, token: str | None = None):
        self._server_url = server_url
        self._token = token
        self._lamb_bin = shutil.which("lamb") or self._find_lamb()
        if not self._lamb_bin:
            raise RuntimeError(
                "lamb binary not found on PATH. "
                "Install with: pip install -e /path/to/lamb-cli"
            )
        # An empty temp dir used as HOME for unauthenticated runs so the CLI
        # doesn't pick up credentials from ~/.config/lamb/credentials.toml.
        self._empty_config_dir = tempfile.mkdtemp(prefix="lamb_cli_test_")

    @staticmethod
    def _find_lamb() -> str | None:
        """Locate the lamb binary next to the running Python interpreter."""
        import sys
        candidate = os.path.join(os.path.dirname(sys.executable), "lamb")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        return None

    @property
    def token(self) -> str | None:
        return self._token

    def set_token(self, token: str | None) -> None:
        self._token = token

    def clear_token(self) -> None:
        self._token = None

    def _env(self) -> dict[str, str]:
        env = {**os.environ}
        env["LAMB_SERVER_URL"] = self._server_url
        env["TERM"] = "dumb"  # suppress ANSI escape codes
        env.pop("LAMB_TOKEN", None)
        if self._token:
            env["LAMB_TOKEN"] = self._token
        else:
            # Point HOME to an empty temp dir so the CLI doesn't
            # pick up credentials from ~/.config/lamb/credentials.toml
            env["HOME"] = self._empty_config_dir
        return env

    def run(self, *args: str, timeout: int = 60) -> CLIResult:
        """Run ``lamb <args>`` and return a CLIResult."""
        cmd = [self._lamb_bin, *args]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._env(),
        )
        return CLIResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def run_json(self, *args: str, timeout: int = 60) -> CLIResult:
        """Run ``lamb <args> --output json`` and return a CLIResult with parsed JSON."""
        return self.run(*args, "--output", "json", timeout=timeout)
