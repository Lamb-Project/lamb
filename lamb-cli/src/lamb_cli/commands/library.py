"""Library management commands — lamb library *."""

from __future__ import annotations

import json
import os
import time
from typing import Optional

import typer
from rich.progress import BarColumn, Progress, TextColumn

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.errors import ApiError
from lamb_cli.output import format_output, print_error, print_success, print_warning


def _render_fr10_conflict(exc: ApiError) -> None:
    """Surface FR-10 deletion conflicts (409) with the blocking KS list.

    The backend returns a body shaped:
        {"detail": "...", "blocking_knowledge_stores": [{"id": ..., "name": ...}, ...]}
    We print the human-readable list before re-raising so callers see WHICH
    Knowledge Stores are holding the item rather than a bare 'API error (409)'.
    """
    blocking = exc.body.get("blocking_knowledge_stores") if exc.body else None
    if not blocking:
        return
    print_error(exc.body.get("detail", "Resource is in use by Knowledge Stores."))
    print_error("Blocking Knowledge Stores:")
    for ks in blocking:
        ks_id = ks.get("id", "?") if isinstance(ks, dict) else str(ks)
        ks_name = ks.get("name", "") if isinstance(ks, dict) else ""
        suffix = f" — {ks_name}" if ks_name else ""
        print_error(f"  - {ks_id}{suffix}")
    print_error(
        "Run 'lamb ks remove-content <ks_id> <item_id>' for each, then retry."
    )


# lifecycle verification 2026-05-03 (#337): library item polling helper.
# Mirrors knowledge_store._wait_for_items but targets the
# /creator/libraries/{lib}/items/{item} endpoint where status is one of
# pending | processing | ready | failed.
_TERMINAL_ITEM_STATES = {"ready", "failed", "completed"}


def _poll_library_item(library_id: str, item_id: str) -> dict:
    """Single-shot status fetch for one (library, item) pair."""
    with get_client(timeout=60.0) as client:
        return client.get(f"/creator/libraries/{library_id}/items/{item_id}")


def _wait_for_library_items(
    library_id: str,
    item_ids: list[str],
    max_wait_seconds: int = 600,
) -> None:
    """Poll each library item with exponential backoff until ready/failed.

    Backoff schedule: 1s, 2s, 4s, 8s, 16s, then capped at 16s.
    """
    pending = set(item_ids)
    deadline = time.time() + max_wait_seconds
    delay = 1.0
    while pending and time.time() < deadline:
        for item_id in list(pending):
            try:
                data = _poll_library_item(library_id, item_id)
            except Exception as e:  # noqa: BLE001 - report and keep polling
                print_warning(f"  {item_id}: poll error — {e}")
                continue
            status = data.get("status") if isinstance(data, dict) else None
            if status in _TERMINAL_ITEM_STATES:
                pending.discard(item_id)
                if status == "failed":
                    err = data.get("error_message") or data.get("error") or "unknown"
                    print_error(f"  {item_id}: failed — {err}")
                else:
                    pages = data.get("page_count", "?")
                    print_success(f"  {item_id}: {status} ({pages} pages)")
        if pending:
            time.sleep(delay)
            delay = min(delay * 2, 16.0)
    if pending:
        print_warning(
            f"Timed out waiting on {len(pending)} item(s); they remain in flight."
        )

app = typer.Typer(help="Manage document libraries.")

LIBRARY_LIST_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("item_count", "Items"),
    ("is_shared", "Shared"),
]

LIBRARY_DETAIL_FIELDS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("item_count", "Items"),
    ("is_shared", "Shared"),
    ("owner", "Owner"),
    ("created_at", "Created"),
]

ITEM_LIST_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("source_type", "Source"),
    ("import_plugin", "Plugin"),
    ("status", "Status"),
    ("page_count", "Pages"),
    ("image_count", "Images"),
    ("created_at", "Created"),
]

ITEM_DETAIL_FIELDS = [
    ("id", "ID"),
    ("title", "Title"),
    ("source_type", "Source"),
    ("original_filename", "Filename"),
    ("content_type", "Type"),
    ("file_size", "Size"),
    ("import_plugin", "Plugin"),
    ("status", "Status"),
    ("page_count", "Pages"),
    ("image_count", "Images"),
    ("permalink_base", "Permalink"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

PLUGIN_COLUMNS = [
    ("name", "Name"),
    ("description", "Description"),
    ("supported_source_types", "Sources"),
]


@app.command("list")
def list_libraries(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List libraries in the current organization."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/libraries")
    libraries = resp.get("libraries", []) if isinstance(resp, dict) else resp
    format_output(libraries, LIBRARY_LIST_COLUMNS, fmt)


@app.command("create")
def create_library(
    name: str = typer.Argument(..., help="Library name."),
    description: str = typer.Option("", "--description", "-d", help="Library description."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new library."""
    fmt = output or get_output_format()
    body: dict = {"name": name}
    if description:
        body["description"] = description
    with get_client() as client:
        data = client.post("/creator/libraries", json=body)
    print_success(f"Library created: {data.get('id', '')}")
    format_output(data, LIBRARY_LIST_COLUMNS, fmt, detail_fields=LIBRARY_DETAIL_FIELDS)


@app.command("get")
def get_library(
    library_id: str = typer.Argument(..., help="Library ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a library."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/libraries/{library_id}")
    format_output(data, LIBRARY_LIST_COLUMNS, fmt, detail_fields=LIBRARY_DETAIL_FIELDS)


@app.command("delete")
def delete_library(
    library_id: str = typer.Argument(..., help="Library ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a library and all its content."""
    if not confirm:
        typer.confirm(f"Delete library {library_id}?", abort=True)
    try:
        with get_client() as client:
            data = client.delete(f"/creator/libraries/{library_id}")
    except ApiError as exc:
        if exc.status_code == 409:
            _render_fr10_conflict(exc)
        raise
    msg = data.get("message", "Library deleted.") if isinstance(data, dict) else "Library deleted."
    print_success(msg)


@app.command("share")
def share_library(
    library_id: str = typer.Argument(..., help="Library ID."),
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable sharing."),
) -> None:
    """Enable or disable organization-wide sharing for a library."""
    if enable is None:
        print_error("Specify --enable or --disable.")
        raise typer.Exit(1)
    with get_client() as client:
        client.put(f"/creator/libraries/{library_id}/share", json={"is_shared": enable})
    state = "enabled" if enable else "disabled"
    print_success(f"Sharing {state} for library {library_id}.")


@app.command("upload")
def upload_files(
    library_id: str = typer.Argument(..., help="Library ID."),
    files: list[str] = typer.Argument(..., help="File paths to upload."),
    plugin: Optional[str] = typer.Option(None, "--plugin", "-p", help="Import plugin name."),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Document title (default: filename)."),
    # lifecycle verification 2026-05-03 (#337): allow blocking until import
    # finishes so scripts/CI can act on the produced item without manually polling.
    wait: bool = typer.Option(False, "--wait", help="Block until import finishes (ready/failed)."),
    max_wait: int = typer.Option(600, "--max-wait", help="Maximum seconds to wait when --wait is set."),
) -> None:
    """Upload files to a library for import."""
    for fp in files:
        if not os.path.isfile(fp):
            print_error(f"File not found: {fp}")
            raise typer.Exit(1)

    item_ids: list[str] = []
    with get_client(timeout=120.0) as client:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Uploading files", total=len(files))
            for fp in files:
                file_title = title or os.path.basename(fp)
                data: dict = {"title": file_title}
                if plugin:
                    data["plugin_name"] = plugin
                resp = client.post_multipart_form(
                    f"/creator/libraries/{library_id}/upload",
                    file_path=fp,
                    field_name="file",
                    data=data,
                )
                item_id = resp.get("item_id", "?") if isinstance(resp, dict) else "?"
                if isinstance(resp, dict) and resp.get("item_id"):
                    item_ids.append(resp["item_id"])
                progress.update(task, advance=1)
                print_success(f"  {os.path.basename(fp)} → item {item_id}")

    count = len(files)
    print_success(f"Uploaded {count} file{'s' if count != 1 else ''} to library {library_id}.")

    if wait and item_ids:
        print_success("Waiting for items to finish importing...")
        _wait_for_library_items(library_id, item_ids, max_wait_seconds=max_wait)


@app.command("import-url")
def import_url(
    library_id: str = typer.Argument(..., help="Library ID."),
    url: str = typer.Option(..., "--url", help="URL to import."),
    plugin: str = typer.Option("url_import", "--plugin", "-p", help="Import plugin name."),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Document title."),
    depth: Optional[int] = typer.Option(None, "--depth", help="Max crawl depth."),
    # lifecycle verification 2026-05-03 (#337)
    wait: bool = typer.Option(False, "--wait", help="Block until import finishes (ready/failed)."),
    max_wait: int = typer.Option(600, "--max-wait", help="Maximum seconds to wait when --wait is set."),
) -> None:
    """Import content from a URL."""
    body: dict = {
        "url": url,
        "plugin_name": plugin,
        "title": title or url,
    }
    if depth is not None:
        body["plugin_params"] = {"max_discovery_depth": depth}
    with get_client(timeout=120.0) as client:
        data = client.post(f"/creator/libraries/{library_id}/import-url", json=body)
    item_id = data.get("item_id") if isinstance(data, dict) else None
    if item_id:
        print_success(f"Import started. Item ID: {item_id}")
    else:
        print_success("Import request submitted.")
    if wait and item_id:
        print_success("Waiting for item to finish importing...")
        _wait_for_library_items(library_id, [item_id], max_wait_seconds=max_wait)


@app.command("import-youtube")
def import_youtube(
    library_id: str = typer.Argument(..., help="Library ID."),
    url: str = typer.Option(..., "--url", help="YouTube video URL."),
    language: str = typer.Option("en", "--language", "-l", help="Transcript language (ISO 639-1)."),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Document title."),
    # lifecycle verification 2026-05-03 (#337)
    wait: bool = typer.Option(False, "--wait", help="Block until import finishes (ready/failed)."),
    max_wait: int = typer.Option(600, "--max-wait", help="Maximum seconds to wait when --wait is set."),
) -> None:
    """Import a YouTube video transcript."""
    body: dict = {
        "video_url": url,
        "language": language,
        "plugin_name": "youtube_transcript_import",
        "title": title or url,
    }
    with get_client(timeout=120.0) as client:
        data = client.post(f"/creator/libraries/{library_id}/import-youtube", json=body)
    item_id = data.get("item_id") if isinstance(data, dict) else None
    if item_id:
        print_success(f"Import started. Item ID: {item_id}")
    else:
        print_success("Import request submitted.")
    if wait and item_id:
        print_success("Waiting for item to finish importing...")
        _wait_for_library_items(library_id, [item_id], max_wait_seconds=max_wait)


@app.command("items")
def list_items(
    library_id: str = typer.Argument(..., help="Library ID."),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status."),
    limit: int = typer.Option(20, "--limit", help="Max results."),
    offset: int = typer.Option(0, "--offset", help="Skip count."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List imported items in a library."""
    fmt = output or get_output_format()
    params: dict = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    with get_client() as client:
        resp = client.get(f"/creator/libraries/{library_id}/items", params=params)
    items = resp.get("items", []) if isinstance(resp, dict) else resp
    format_output(items, ITEM_LIST_COLUMNS, fmt)


@app.command("item")
def get_item(
    library_id: str = typer.Argument(..., help="Library ID."),
    item_id: str = typer.Argument(..., help="Item ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of an imported item."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/libraries/{library_id}/items/{item_id}")
    format_output(data, ITEM_LIST_COLUMNS, fmt, detail_fields=ITEM_DETAIL_FIELDS)


@app.command("delete-item")
def delete_item(
    library_id: str = typer.Argument(..., help="Library ID."),
    item_id: str = typer.Argument(..., help="Item ID to delete."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete an imported item from a library."""
    if not confirm:
        typer.confirm(f"Delete item {item_id} from library {library_id}?", abort=True)
    try:
        with get_client() as client:
            data = client.delete(f"/creator/libraries/{library_id}/items/{item_id}")
    except ApiError as exc:
        if exc.status_code == 409:
            _render_fr10_conflict(exc)
        raise
    msg = data.get("message", "Item deleted.") if isinstance(data, dict) else "Item deleted."
    print_success(msg)


@app.command("plugins")
def list_plugins(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List available import plugins."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/libraries/plugins")
    plugins = data.get("plugins", []) if isinstance(data, dict) else data
    format_output(plugins, PLUGIN_COLUMNS, fmt)


@app.command("import-config")
def show_import_config(
    library_id: str = typer.Argument(..., help="Library ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show the import configuration for a library."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/libraries/{library_id}/import-config")
    format_output(data, [], fmt)


@app.command("set-import-config")
def set_import_config(
    library_id: str = typer.Argument(..., help="Library ID."),
    image_descriptions: Optional[str] = typer.Option(None, "--image-descriptions", help="basic or llm."),
    crawl_depth: Optional[int] = typer.Option(None, "--crawl-depth", help="Max URL crawl depth."),
) -> None:
    """Update the import configuration for a library."""
    config: dict = {}
    if image_descriptions is not None:
        config["image_descriptions"] = image_descriptions
    if crawl_depth is not None:
        config["max_discovery_depth"] = crawl_depth
    if not config:
        print_error("No config options specified.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(f"/creator/libraries/{library_id}/import-config", json=config)
    warning = data.get("warning", "") if isinstance(data, dict) else ""
    if warning:
        print_warning(warning)
    print_success("Import configuration updated.")


@app.command("export")
def export_library(
    library_id: str = typer.Argument(..., help="Library ID."),
    output_file: str = typer.Option(None, "--output-file", "-f", help="Output ZIP path."),
) -> None:
    """Export a library as a ZIP file."""
    if not output_file:
        output_file = f"library-{library_id[:8]}.zip"
    with get_client(timeout=300.0) as client:
        resp = client._http.request("GET", f"/creator/libraries/{library_id}/export")
        if not resp.is_success:
            print_error(f"Export failed: HTTP {resp.status_code}")
            raise typer.Exit(2)
        with open(output_file, "wb") as f:
            f.write(resp.content)
    print_success(f"Library exported to {output_file}")


@app.command("import")
def import_library(
    file_path: str = typer.Argument(..., help="ZIP file to import."),
) -> None:
    """Import a library from a ZIP file."""
    if not os.path.isfile(file_path):
        print_error(f"File not found: {file_path}")
        raise typer.Exit(1)
    with get_client(timeout=300.0) as client:
        data = client.upload_file(f"/creator/libraries/import", file_path=file_path, field_name="file")
    if isinstance(data, dict):
        print_success(
            f"Library imported: {data.get('library_name', '?')} "
            f"({data.get('item_count', 0)} items, ID: {data.get('library_id', '?')})"
        )
    else:
        print_success("Library imported.")
