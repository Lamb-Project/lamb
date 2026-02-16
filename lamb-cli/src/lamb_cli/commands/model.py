"""Model commands — lamb model *."""

from __future__ import annotations

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output

app = typer.Typer(help="Manage models.")

MODEL_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("owned_by", "Owned By"),
]


@app.command("list")
def list_models(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List available models."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/models")
    models = resp.get("data", []) if isinstance(resp, dict) else resp
    format_output(models, MODEL_COLUMNS, fmt)
