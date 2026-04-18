"""Rich table rendering utilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rich.table import Table

from moodle_cli.output.console import console


def render_table(
    rows: Sequence[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Render a list of dicts as a Rich table."""
    if not rows:
        console.print("[dim]No results.[/dim]")
        return

    if columns is None:
        columns = list(rows[0].keys())

    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col, overflow="fold")

    for row in rows:
        table.add_row(*(str(row.get(col, "")) for col in columns))

    console.print(table)
