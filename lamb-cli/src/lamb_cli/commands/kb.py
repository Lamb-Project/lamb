"""Knowledge base management commands — lamb kb *."""

from __future__ import annotations

import os
from typing import Optional

import typer
from rich.progress import BarColumn, Progress, TextColumn

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success

app = typer.Typer(help="Manage knowledge bases.")

KB_LIST_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("is_owner", "Owner"),
    ("is_shared", "Shared"),
]

KB_DETAIL_FIELDS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("is_owner", "Owner"),
    ("is_shared", "Shared"),
    ("can_modify", "Can Modify"),
    ("owner", "Owner User"),
    ("files", "Files"),
]

FILE_COLUMNS = [
    ("id", "ID"),
    ("filename", "Filename"),
    ("size", "Size"),
    ("content_type", "Content Type"),
]

QUERY_RESULT_COLUMNS = [
    ("similarity", "Similarity"),
    ("data", "Data"),
]

PLUGIN_COLUMNS = [
    ("name", "Name"),
    ("description", "Description"),
    ("kind", "Kind"),
]


@app.command("list")
def list_kbs(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List your knowledge bases."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/knowledgebases/user")
    kbs = resp.get("knowledge_bases", [])
    format_output(kbs, KB_LIST_COLUMNS, fmt)


@app.command("list-shared")
def list_shared_kbs(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List shared knowledge bases."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/knowledgebases/shared")
    kbs = resp.get("knowledge_bases", [])
    format_output(kbs, KB_LIST_COLUMNS, fmt)


@app.command("get")
def get_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a knowledge base."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/knowledgebases/kb/{kb_id}")
    # For table display, show file count instead of full list
    if fmt != "json" and isinstance(data.get("files"), list):
        display = {**data, "files": len(data["files"])}
    else:
        display = data
    format_output(display, KB_LIST_COLUMNS, fmt, detail_fields=KB_DETAIL_FIELDS)


@app.command("create")
def create_kb(
    name: str = typer.Argument(..., help="Knowledge base name."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    access_control: Optional[str] = typer.Option(None, "--access-control", help="Access control JSON."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new knowledge base."""
    fmt = output or get_output_format()
    body: dict = {"name": name, "description": description}
    if access_control is not None:
        body["access_control"] = access_control
    with get_client() as client:
        data = client.post("/creator/knowledgebases", json=body)
    print_success(f"Knowledge base created: {data.get('id', '')}")
    format_output(data, KB_LIST_COLUMNS, fmt)


@app.command("update")
def update_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
    access_control: Optional[str] = typer.Option(None, "--access-control", help="Access control JSON."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Update a knowledge base."""
    fmt = output or get_output_format()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if access_control is not None:
        body["access_control"] = access_control
    if not body:
        print_error("No fields to update. Provide at least one option.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.patch(f"/creator/knowledgebases/kb/{kb_id}", json=body)
    print_success(data.get("message", "Knowledge base updated.") if isinstance(data, dict) else "Knowledge base updated.")


@app.command("delete")
def delete_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a knowledge base."""
    if not confirm:
        typer.confirm(f"Delete knowledge base {kb_id}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/knowledgebases/kb/{kb_id}")
    msg = data.get("message", "Knowledge base deleted.") if isinstance(data, dict) else "Knowledge base deleted."
    print_success(msg)


@app.command("share")
def share_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable sharing."),
) -> None:
    """Enable or disable sharing for a knowledge base."""
    if enable is None:
        print_error("Specify --enable or --disable.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(f"/creator/knowledgebases/kb/{kb_id}/share", json={"is_shared": enable})
    state = "enabled" if enable else "disabled"
    print_success(f"Sharing {state} for knowledge base {kb_id}.")


@app.command("upload")
def upload_files_cmd(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    files: list[str] = typer.Argument(..., help="File paths to upload."),
) -> None:
    """Upload files to a knowledge base."""
    # Validate files exist
    for fp in files:
        if not os.path.isfile(fp):
            print_error(f"File not found: {fp}")
            raise typer.Exit(1)

    with get_client() as client:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Uploading files", total=len(files))
            data = client.upload_files(
                f"/creator/knowledgebases/kb/{kb_id}/files",
                file_paths=files,
            )
            progress.update(task, completed=len(files))
    count = len(files)
    print_success(f"Uploaded {count} file{'s' if count != 1 else ''} to knowledge base {kb_id}.")


@app.command("ingest")
def ingest_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    plugin: str = typer.Option(..., "--plugin", "-p", help="Ingestion plugin name."),
    url: Optional[str] = typer.Option(None, "--url", help="URL to ingest."),
    youtube: Optional[str] = typer.Option(None, "--youtube", help="YouTube URL to ingest."),
    param: Optional[list[str]] = typer.Option(None, "--param", help="Plugin parameter as key=value."),
) -> None:
    """Ingest content into a knowledge base via a plugin."""
    body: dict = {"plugin_name": plugin}
    plugin_params: dict = {}

    if url:
        plugin_params["url"] = url
    if youtube:
        plugin_params["youtube_url"] = youtube
    if param:
        for p in param:
            if "=" not in p:
                print_error(f"Invalid parameter format: {p}. Use key=value.")
                raise typer.Exit(1)
            key, value = p.split("=", 1)
            plugin_params[key] = value

    if plugin_params:
        body["plugin_params"] = plugin_params

    with get_client() as client:
        data = client.post(f"/creator/knowledgebases/kb/{kb_id}/plugin-ingest-base", json=body)
    if isinstance(data, dict) and data.get("job_id"):
        print_success(f"Ingestion started. Job ID: {data['job_id']}")
    else:
        print_success("Ingestion request submitted.")


@app.command("query")
def query_kb(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    query_text: str = typer.Argument(..., help="Query text."),
    plugin: Optional[str] = typer.Option(None, "--plugin", "-p", help="Query plugin name."),
    top_k: Optional[int] = typer.Option(None, "--top-k", "-k", help="Number of results."),
    threshold: Optional[float] = typer.Option(None, "--threshold", "-t", help="Similarity threshold."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Query a knowledge base."""
    fmt = output or get_output_format()
    body: dict = {"query_text": query_text}
    plugin_params: dict = {}

    if plugin:
        body["plugin_name"] = plugin
    if top_k is not None:
        plugin_params["top_k"] = top_k
    if threshold is not None:
        plugin_params["threshold"] = threshold
    if plugin_params:
        body["plugin_params"] = plugin_params

    with get_client() as client:
        data = client.post(f"/creator/knowledgebases/kb/{kb_id}/query", json=body)

    results = data if isinstance(data, list) else data.get("results", [])

    # Truncate data field for table display
    if fmt != "json":
        for r in results:
            if isinstance(r.get("data"), str) and len(r["data"]) > 80:
                r["data"] = r["data"][:77] + "..."

    format_output(results, QUERY_RESULT_COLUMNS, fmt)


@app.command("delete-file")
def delete_file(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    file_id: str = typer.Argument(..., help="File ID to delete."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a file from a knowledge base."""
    if not confirm:
        typer.confirm(f"Delete file {file_id} from knowledge base {kb_id}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/knowledgebases/kb/{kb_id}/files/{file_id}")
    msg = data.get("message", "File deleted.") if isinstance(data, dict) else "File deleted."
    print_success(msg)


@app.command("plugins")
def list_plugins(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List available ingestion plugins."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/knowledgebases/ingestion-plugins")
    plugins = data if isinstance(data, list) else data.get("plugins", [])
    format_output(plugins, PLUGIN_COLUMNS, fmt)


@app.command("query-plugins")
def list_query_plugins(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List available query plugins."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/knowledgebases/query-plugins")
    plugins = data if isinstance(data, list) else data.get("plugins", [])
    format_output(plugins, PLUGIN_COLUMNS, fmt)
