"""Ingestion job management commands — lamb job *."""

from __future__ import annotations

import sys
import time
from typing import Optional

import typer
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success

app = typer.Typer(help="Manage ingestion jobs.")

JOB_LIST_COLUMNS = [
    ("id", "ID"),
    ("original_filename", "Filename"),
    ("status", "Status"),
    ("percentage", "Progress"),
    ("created_at", "Created At"),
]

JOB_DETAIL_FIELDS = [
    ("id", "ID"),
    ("original_filename", "Filename"),
    ("status", "Status"),
    ("percentage", "Progress"),
    ("created_at", "Created At"),
    ("plugin_name", "Plugin"),
    ("document_count", "Documents"),
    ("error_message", "Error"),
    ("processing_duration_seconds", "Duration (s)"),
]

STATUS_COLUMNS = [
    ("total_jobs", "Total Jobs"),
    ("currently_processing", "Currently Processing"),
]

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _flatten_job(job: dict) -> dict:
    """Flatten progress.percentage into top-level percentage field."""
    flat = dict(job)
    progress = job.get("progress")
    if isinstance(progress, dict):
        flat["percentage"] = progress.get("percentage", "")
    elif "percentage" not in flat:
        flat["percentage"] = ""
    return flat


@app.command("list")
def list_jobs(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    sort_by: Optional[str] = typer.Option(None, "--sort-by", help="Sort field."),
    sort_order: Optional[str] = typer.Option(None, "--sort-order", help="Sort order: asc or desc."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List ingestion jobs for a knowledge base."""
    fmt = output or get_output_format()
    params: dict = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if sort_by:
        params["sort_by"] = sort_by
    if sort_order:
        params["sort_order"] = sort_order

    with get_client() as client:
        resp = client.get(f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs", params=params)
    items = resp.get("items", [])
    items = [_flatten_job(j) for j in items]
    format_output(items, JOB_LIST_COLUMNS, fmt)


@app.command("get")
def get_job(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    job_id: str = typer.Argument(..., help="Job ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of an ingestion job."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}")
    flat = _flatten_job(data)
    format_output(flat, JOB_LIST_COLUMNS, fmt, detail_fields=JOB_DETAIL_FIELDS)


@app.command("retry")
def retry_job(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    job_id: str = typer.Argument(..., help="Job ID."),
) -> None:
    """Retry a failed ingestion job."""
    with get_client() as client:
        data = client.post(f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/retry")
    print_success(f"Job {job_id} retry requested.")


@app.command("cancel")
def cancel_job(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    job_id: str = typer.Argument(..., help="Job ID."),
) -> None:
    """Cancel a running ingestion job."""
    with get_client() as client:
        data = client.post(f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}/cancel")
    print_success(f"Job {job_id} cancellation requested.")


@app.command("watch")
def watch_job(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    job_id: str = typer.Argument(..., help="Job ID."),
    interval: float = typer.Option(3.0, "--interval", "-i", help="Poll interval in seconds."),
) -> None:
    """Watch an ingestion job with live progress updates."""
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    with get_client() as client:
        if not is_tty:
            # Non-interactive: single poll, print status line
            data = client.get(f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}")
            flat = _flatten_job(data)
            sys.stdout.write(
                f"{flat.get('id', '')} {flat.get('status', '')} {flat.get('percentage', '')}%\n"
            )
            return

        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TextColumn("{task.fields[status]}"),
        )
        task = progress.add_task("Ingestion", total=100, status="pending")

        with Live(progress, refresh_per_second=2):
            while True:
                data = client.get(
                    f"/creator/knowledgebases/kb/{kb_id}/ingestion-jobs/{job_id}"
                )
                flat = _flatten_job(data)
                job_status = flat.get("status", "unknown")
                pct = flat.get("percentage", 0)
                if not isinstance(pct, (int, float)):
                    pct = 0
                filename = flat.get("original_filename", "")
                desc = filename if filename else "Ingestion"
                progress.update(task, completed=pct, description=desc, status=job_status)

                if job_status in TERMINAL_STATUSES:
                    break
                time.sleep(interval)

    if job_status == "completed":
        print_success(f"Job {job_id} completed.")
    elif job_status == "failed":
        err = flat.get("error_message", "")
        print_error(f"Job {job_id} failed: {err}" if err else f"Job {job_id} failed.")
    elif job_status == "cancelled":
        print_success(f"Job {job_id} was cancelled.")


@app.command("status")
def job_status_cmd(
    kb_id: str = typer.Argument(..., help="Knowledge base ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show ingestion status summary for a knowledge base."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/knowledgebases/kb/{kb_id}/ingestion-status")

    if fmt == "json":
        format_output(data, STATUS_COLUMNS, fmt)
        return

    # Flatten by_status into the display dict for detail view
    display = dict(data)
    by_status = data.get("by_status", {})
    fields = list(STATUS_COLUMNS)
    for status_key, count in by_status.items():
        field_key = f"status_{status_key}"
        display[field_key] = count
        fields.append((field_key, f"  {status_key}"))

    recent = data.get("recent_failures", [])
    display["recent_failures"] = len(recent)
    fields.append(("recent_failures", "Recent Failures"))

    format_output(display, STATUS_COLUMNS, fmt, detail_fields=fields)
