"""Assistant management commands — lamb assistant *."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success

app = typer.Typer(help="Manage assistants.")

ASSISTANT_LIST_COLUMNS = [
    ("assistant_id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("publish_status", "Published"),
]

ASSISTANT_DETAIL_FIELDS = [
    ("assistant_id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("system_prompt", "System Prompt"),
    ("publish_status", "Published"),
    ("owner", "Owner"),
    ("rag_top_k", "RAG Top-K"),
    ("rag_collection_names", "RAG Collections"),
]


@app.command("list")
def list_assistants(
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List all assistants."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/assistant/get_assistants", params={"limit": limit, "offset": offset})
    assistants = resp.get("assistants", [])
    format_output(assistants, ASSISTANT_LIST_COLUMNS, fmt)


@app.command("get")
def get_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a single assistant."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/get_assistant/{assistant_id}")
    format_output(data, ASSISTANT_LIST_COLUMNS, fmt, detail_fields=ASSISTANT_DETAIL_FIELDS)


@app.command("create")
def create_assistant(
    name: str = typer.Argument(..., help="Assistant name."),
    description: str = typer.Option("", "--description", "-d", help="Assistant description."),
    system_prompt: str = typer.Option("", "--system-prompt", "-s", help="System prompt text."),
    system_prompt_file: Optional[Path] = typer.Option(
        None, "--system-prompt-file", help="Read system prompt from file."
    ),
    rag_top_k: Optional[int] = typer.Option(None, "--rag-top-k", help="Number of RAG chunks."),
    rag_collections: Optional[str] = typer.Option(
        None, "--rag-collections", help="Comma-separated RAG collection names."
    ),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new assistant."""
    fmt = output or get_output_format()
    prompt = system_prompt
    if system_prompt_file:
        prompt = system_prompt_file.read_text(encoding="utf-8")

    body: dict = {"name": name, "description": description, "system_prompt": prompt}
    if rag_top_k is not None:
        body["rag_top_k"] = rag_top_k
    if rag_collections:
        body["rag_collection_names"] = [c.strip() for c in rag_collections.split(",")]

    with get_client() as client:
        data = client.post("/creator/assistant/create_assistant", json=body)
    print_success(f"Assistant created: {data.get('assistant_id', '')}")
    format_output(data, ASSISTANT_LIST_COLUMNS, fmt)


@app.command("update")
def update_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
    system_prompt: Optional[str] = typer.Option(None, "--system-prompt", "-s", help="New system prompt."),
    rag_top_k: Optional[int] = typer.Option(None, "--rag-top-k", help="Number of RAG chunks."),
    rag_collections: Optional[str] = typer.Option(
        None, "--rag-collections", help="Comma-separated RAG collection names."
    ),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Update an existing assistant."""
    fmt = output or get_output_format()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if system_prompt is not None:
        body["system_prompt"] = system_prompt
    if rag_top_k is not None:
        body["rag_top_k"] = rag_top_k
    if rag_collections is not None:
        body["rag_collection_names"] = [c.strip() for c in rag_collections.split(",")]

    if not body:
        print_error("No fields to update. Provide at least one option.")
        raise typer.Exit(1)

    with get_client() as client:
        data = client.put(f"/creator/assistant/update_assistant/{assistant_id}", json=body)
    print_success(data.get("message", "Assistant updated."))


@app.command("delete")
def delete_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete an assistant."""
    if not confirm:
        typer.confirm(f"Delete assistant {assistant_id}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/assistant/delete_assistant/{assistant_id}")
    print_success(data.get("message", "Assistant deleted."))


@app.command("publish")
def publish_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
) -> None:
    """Publish an assistant (make it available to end-users)."""
    with get_client() as client:
        data = client.put(
            f"/creator/assistant/publish/{assistant_id}", json={"publish_status": True}
        )
    print_success(f"Assistant {assistant_id} published.")


@app.command("unpublish")
def unpublish_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
) -> None:
    """Unpublish an assistant (hide from end-users)."""
    with get_client() as client:
        data = client.put(
            f"/creator/assistant/publish/{assistant_id}", json={"publish_status": False}
        )
    print_success(f"Assistant {assistant_id} unpublished.")


@app.command("export")
def export_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file", "-f", help="Write export to file instead of stdout."
    ),
) -> None:
    """Export an assistant configuration as JSON."""
    with get_client() as client:
        data = client.get(f"/creator/assistant/export/{assistant_id}")

    json_str = json.dumps(data, indent=2, default=str)
    if output_file:
        output_file.write_text(json_str, encoding="utf-8")
        print_success(f"Exported to {output_file}")
    else:
        sys.stdout.write(json_str + "\n")
