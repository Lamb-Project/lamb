"""Rubric management commands — lamb rubric *."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_json, print_success, print_warning, stderr_console

app = typer.Typer(help="Manage rubrics (EvaluAItor).")

RUBRIC_LIST_COLUMNS = [
    ("rubric_id", "Rubric ID"),
    ("title", "Title"),
    ("description", "Description"),
    ("_criteria_count", "Criteria"),
    ("_max_score", "Max Score"),
    ("is_public", "Public"),
]

RUBRIC_DETAIL_FIELDS = [
    ("rubric_id", "Rubric ID"),
    ("title", "Title"),
    ("description", "Description"),
    ("_subject", "Subject"),
    ("_grade_level", "Grade Level"),
    ("_scoring_type", "Scoring Type"),
    ("_max_score", "Max Score"),
    ("_criteria_summary", "Criteria"),
    ("is_public", "Public"),
    ("is_showcase", "Showcase"),
    ("owner_email", "Owner"),
    ("organization_slug", "Organization"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]


def _enrich_rubric(r: dict) -> dict:
    """Add computed display fields from rubric_data."""
    rd = r.get("rubric_data") or {}
    meta = rd.get("metadata") or {}
    criteria = rd.get("criteria") or []
    r["_criteria_count"] = len(criteria)
    r["_max_score"] = rd.get("maxScore", "")
    r["_scoring_type"] = rd.get("scoringType", "")
    r["_subject"] = meta.get("subject", "")
    r["_grade_level"] = meta.get("gradeLevel", "")
    # Build criteria summary: "Name (weight%) | Name (weight%) | ..."
    parts = []
    for c in criteria:
        parts.append(f"{c['name']} ({c.get('weight', '')}%)")
    r["_criteria_summary"] = " | ".join(parts)
    return r


def _enrich_list(rubrics: list[dict]) -> list[dict]:
    """Enrich a list of rubrics with computed fields."""
    return [_enrich_rubric(r) for r in rubrics]


@app.command("list")
def list_rubrics(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of rubrics."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search by title or description."),
    subject: Optional[str] = typer.Option(None, "--subject", help="Filter by subject."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List your rubrics."""
    fmt = output or get_output_format()
    params: dict = {"tab": "my", "limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if subject:
        params["subject"] = subject
    with get_client() as client:
        resp = client.get("/creator/rubrics", params=params)
    rubrics = resp.get("rubrics", []) if isinstance(resp, dict) else []
    if fmt == "json":
        print_json(rubrics)
    else:
        format_output(_enrich_list(rubrics), RUBRIC_LIST_COLUMNS, fmt)


@app.command("list-public")
def list_public_rubrics(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of rubrics."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search by title or description."),
    subject: Optional[str] = typer.Option(None, "--subject", help="Filter by subject."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List public rubrics (templates)."""
    fmt = output or get_output_format()
    params: dict = {"tab": "templates", "limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if subject:
        params["subject"] = subject
    with get_client() as client:
        resp = client.get("/creator/rubrics", params=params)
    rubrics = resp.get("rubrics", []) if isinstance(resp, dict) else []
    if fmt == "json":
        print_json(rubrics)
    else:
        format_output(_enrich_list(rubrics), RUBRIC_LIST_COLUMNS, fmt)


@app.command("get")
def get_rubric(
    rubric_id: str = typer.Argument(..., help="Rubric UUID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a rubric."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/rubrics/{rubric_id}")
    if fmt == "json":
        print_json(data)
    else:
        format_output(_enrich_rubric(data), RUBRIC_LIST_COLUMNS, fmt, detail_fields=RUBRIC_DETAIL_FIELDS)


@app.command("delete")
def delete_rubric(
    rubric_id: str = typer.Argument(..., help="Rubric UUID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a rubric."""
    if not confirm:
        typer.confirm(f"Delete rubric {rubric_id}?", abort=True)
    with get_client() as client:
        client.delete(f"/creator/rubrics/{rubric_id}")
    print_success(f"Rubric {rubric_id} deleted.")


@app.command("duplicate")
def duplicate_rubric(
    rubric_id: str = typer.Argument(..., help="Rubric UUID to duplicate."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Duplicate a rubric."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.post(f"/creator/rubrics/{rubric_id}/duplicate")
    new_id = data.get("rubric_id", "") if isinstance(data, dict) else ""
    print_success(f"Rubric duplicated: {new_id}")
    if isinstance(data, dict):
        if fmt == "json":
            print_json(data)
        else:
            format_output(_enrich_rubric(data), RUBRIC_LIST_COLUMNS, fmt, detail_fields=RUBRIC_DETAIL_FIELDS)


@app.command("export")
def export_rubric(
    rubric_id: str = typer.Argument(..., help="Rubric UUID to export."),
    format_: str = typer.Option("json", "--format", "-f", help="Export format: json or md (markdown)."),
    file: Optional[Path] = typer.Option(None, "--file", help="Write to file instead of stdout."),
) -> None:
    """Export a rubric as JSON or markdown."""
    if format_ not in ("json", "md", "markdown"):
        print_error("Format must be 'json' or 'md'.")
        raise typer.Exit(1)
    endpoint = "markdown" if format_ in ("md", "markdown") else "json"
    with get_client() as client:
        data = client.get(f"/creator/rubrics/{rubric_id}/export/{endpoint}")
    if endpoint == "json":
        text = json.dumps(data, indent=2, default=str, ensure_ascii=False)
    else:
        text = data if isinstance(data, str) else str(data)
    if file:
        file.write_text(text + "\n", encoding="utf-8")
        print_success(f"Exported rubric to {file}.")
    else:
        sys.stdout.write(text + "\n")


@app.command("import")
def import_rubric(
    file: Path = typer.Argument(..., help="JSON file to import."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Import a rubric from a JSON file."""
    if not file.exists():
        print_error(f"File not found: {file}")
        raise typer.Exit(1)
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.upload_file("/creator/rubrics/import", str(file))
    # API returns {"success": true, "rubric": {...}} — unwrap
    rubric = data.get("rubric", data) if isinstance(data, dict) else data
    new_id = rubric.get("rubric_id", "") if isinstance(rubric, dict) else ""
    print_success(f"Rubric imported: {new_id}")
    if isinstance(rubric, dict):
        if fmt == "json":
            print_json(rubric)
        else:
            format_output(_enrich_rubric(rubric), RUBRIC_LIST_COLUMNS, fmt, detail_fields=RUBRIC_DETAIL_FIELDS)


@app.command("share")
def share_rubric(
    rubric_id: str = typer.Argument(..., help="Rubric UUID."),
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable public visibility."),
) -> None:
    """Enable or disable public visibility for a rubric."""
    if enable is None:
        print_error("Specify --enable or --disable.")
        raise typer.Exit(1)
    with get_client() as client:
        client.put(f"/creator/rubrics/{rubric_id}/visibility", data={"is_public": str(enable).lower()})
    state = "public" if enable else "private"
    print_success(f"Rubric {rubric_id} is now {state}.")


@app.command("generate")
def generate_rubric(
    prompt: str = typer.Argument(..., help="Natural language description of the rubric to generate."),
    language: str = typer.Option("en", "--language", "--lang", help="Language: en, es, eu, ca."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model override."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
    save_to: Optional[Path] = typer.Option(None, "--save-to", help="Save generated rubric JSON to file."),
) -> None:
    """Generate a rubric using AI (preview only, does not save).

    The generated rubric is returned as a preview. Use --save-to to write
    the rubric JSON to a file, which can then be imported with 'lamb rubric import'.
    """
    fmt = output or get_output_format()
    body: dict = {"prompt": prompt, "language": language}
    if model:
        body["model"] = model
    with get_client() as client:
        data = client.post("/creator/rubrics/ai-generate", json=body)
    if not isinstance(data, dict):
        print_error("Unexpected response from server.")
        raise typer.Exit(2)
    if not data.get("success"):
        print_error(data.get("error", "AI generation failed."))
        if data.get("raw_response"):
            stderr_console.print(f"[dim]Raw response: {data['raw_response'][:500]}[/dim]")
        raise typer.Exit(2)
    if data.get("explanation"):
        stderr_console.print(f"[dim]{data['explanation']}[/dim]")
    rubric = data.get("rubric", {})
    if save_to:
        # Add rubricId if missing so the file can be imported directly
        if "rubricId" not in rubric:
            rubric["rubricId"] = str(uuid.uuid4())
        save_to.write_text(
            json.dumps(rubric, indent=2, default=str, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print_success(f"Rubric saved to {save_to} (importable with 'lamb rubric import').")
    if fmt == "json":
        print_json(rubric)
    else:
        # Show the markdown preview if available, otherwise show structured data
        md = data.get("markdown")
        if md and fmt != "plain":
            sys.stdout.write(md + "\n")
        elif rubric:
            # Wrap rubric in the same shape as a full rubric record for display
            display = {"rubric_data": rubric, "rubric_id": rubric.get("rubricId", "")}
            format_output(_enrich_rubric(display), RUBRIC_LIST_COLUMNS, fmt, detail_fields=RUBRIC_DETAIL_FIELDS)
