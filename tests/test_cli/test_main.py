"""Tests for the main CLI group."""

from __future__ import annotations

from click.testing import CliRunner

from moodle_cli.cli.main import cli


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "moodle-cli" in result.output
    assert "Marc Alier" in result.output
    assert "Juanan Pereira" in result.output
    assert "GPL-3.0" in result.output
    assert "auth" in result.output
    assert "course" in result.output
    assert "site" in result.output


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_all_groups_present() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    expected = [
        "auth", "site", "course", "user", "enrol", "grade",
        "assign", "forum", "quiz", "calendar", "message",
        "completion", "file", "cohort", "role", "call",
    ]
    for group in expected:
        assert group in result.output, f"Missing command group: {group}"


def test_auth_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "--help"])
    assert result.exit_code == 0
    assert "login" in result.output
    assert "logout" in result.output
    assert "status" in result.output
    assert "profiles" in result.output


def test_course_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["course", "--help"])
    assert result.exit_code == 0
    for cmd in ["list", "get", "search", "contents", "create", "update", "delete"]:
        assert cmd in result.output, f"Missing course subcommand: {cmd}"
