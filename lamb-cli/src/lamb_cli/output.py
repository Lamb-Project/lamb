"""Output formatting utilities for LAMB CLI.

All user-facing data goes to stdout; status/error messages go to stderr.
Supports table, json, and plain output formats.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Sequence

from rich.console import Console
from rich.table import Table

stderr_console = Console(stderr=True)
stdout_console = Console()


def print_error(msg: str) -> None:
    """Print an error message to stderr in red."""
    stderr_console.print(f"[red]Error:[/red] {msg}")


def print_success(msg: str) -> None:
    """Print a success message to stderr in green."""
    stderr_console.print(f"[green]{msg}[/green]")


def print_warning(msg: str) -> None:
    """Print a warning message to stderr in yellow."""
    stderr_console.print(f"[yellow]{msg}[/yellow]")


def print_table(data: list[dict], columns: list[tuple[str, str]], title: str | None = None) -> None:
    """Render a Rich table to stdout.

    Args:
        data: List of row dicts.
        columns: List of (key, header_label) tuples.
        title: Optional table title.
    """
    table = Table(title=title, show_header=True, header_style="bold")
    for _key, header in columns:
        table.add_column(header)
    for row in data:
        table.add_row(*(str(row.get(k, "")) for k, _ in columns))
    stdout_console.print(table)


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")


def print_plain(data: list[dict], columns: list[tuple[str, str]]) -> None:
    """Print data as tab-separated values to stdout."""
    for row in data:
        values = [str(row.get(k, "")) for k, _ in columns]
        sys.stdout.write("\t".join(values) + "\n")


def print_detail(data: dict, fields: Sequence[tuple[str, str]]) -> None:
    """Print a single object as key-value pairs to stdout."""
    max_label = max(len(label) for _, label in fields) if fields else 0
    for key, label in fields:
        value = data.get(key, "")
        sys.stdout.write(f"{label:<{max_label}}  {value}\n")


def format_output(
    data: Any,
    columns: list[tuple[str, str]],
    fmt: str,
    detail_fields: Sequence[tuple[str, str]] | None = None,
) -> None:
    """Dispatch output to the correct formatter.

    Args:
        data: A list of dicts (table) or a single dict (detail).
        columns: Column definitions for table/plain output.
        fmt: One of 'table', 'json', 'plain'.
        detail_fields: If set and data is a single dict, use detail layout.
    """
    if fmt == "json":
        print_json(data)
        return

    if isinstance(data, dict):
        if fmt == "plain":
            fields = detail_fields or columns
            for key, _label in fields:
                sys.stdout.write(f"{data.get(key, '')}\n")
        else:
            print_detail(data, detail_fields or columns)
        return

    if fmt == "plain":
        print_plain(data, columns)
    else:
        print_table(data, columns)
