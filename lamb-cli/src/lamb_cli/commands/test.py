"""Test scenario and evaluation commands — lamb test *."""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_json, print_success

app = typer.Typer(help="Test scenarios, run tests, and evaluate assistants.")

console = Console()
err_console = Console(stderr=True)

SCENARIO_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("scenario_type", "Type"),
    ("_msg_count", "Messages"),
    ("created_by", "Created By"),
    ("created_at", "Created"),
]

RUN_COLUMNS = [
    ("id", "Run ID"),
    ("scenario_id", "Scenario"),
    ("model_used", "Model"),
    ("_response_preview", "Response"),
    ("_tokens", "Tokens"),
    ("elapsed_ms", "Time (ms)"),
    ("created_at", "Created"),
]

EVAL_COLUMNS = [
    ("id", "Eval ID"),
    ("test_run_id", "Run ID"),
    ("evaluator", "By"),
    ("verdict", "Verdict"),
    ("notes", "Notes"),
    ("created_at", "Created"),
]


def _enrich_scenario(s: dict) -> dict:
    s["_msg_count"] = len(s.get("messages", []))
    return s


def _enrich_run(r: dict) -> dict:
    resp = r.get("response", "")
    r["_response_preview"] = (resp[:80] + "...") if len(resp) > 80 else resp
    usage = r.get("token_usage", {})
    r["_tokens"] = usage.get("total_tokens", "")
    return r


# ------------------------------------------------------------------
# Scenarios
# ------------------------------------------------------------------

@app.command("scenarios")
def list_scenarios(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """List test scenarios for an assistant."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/{assistant_id}/tests/scenarios")
    scenarios = data if isinstance(data, list) else []
    if fmt == "json":
        print_json(scenarios)
    else:
        format_output([_enrich_scenario(s) for s in scenarios], SCENARIO_COLUMNS, fmt)


@app.command("add")
def add_scenario(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    title: str = typer.Argument(..., help="Scenario title."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Single user message (for single-turn)."),
    messages_file: Optional[str] = typer.Option(None, "--messages-file", "-f", help="JSON file with messages array."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
    expected: Optional[str] = typer.Option(None, "--expected", "-e", help="Expected behavior."),
    scenario_type: str = typer.Option("single_turn", "--type", "-t", help="Type: single_turn, multi_turn, adversarial."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """Add a test scenario."""
    fmt = output or get_output_format()

    if messages_file:
        import pathlib
        raw = pathlib.Path(messages_file).read_text()
        messages = json.loads(raw)
    elif message:
        messages = [{"role": "user", "content": message}]
    else:
        print_error("Provide --message or --messages-file.")
        raise typer.Exit(1)

    body: dict = {
        "title": title,
        "messages": messages,
        "scenario_type": scenario_type,
    }
    if description:
        body["description"] = description
    if expected:
        body["expected_behavior"] = expected

    with get_client() as client:
        data = client.post(f"/creator/assistant/{assistant_id}/tests/scenarios", json=body)
    print_success(f"Scenario created: {data.get('id', '')}")
    if fmt == "json":
        print_json(data)


@app.command("scenario-detail")
def get_scenario(
    scenario_id: str = typer.Argument(..., help="Scenario ID."),
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """Get scenario details."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/{assistant_id}/tests/scenarios/{scenario_id}")
    if fmt == "json":
        print_json(data)
    else:
        console.print(f"[bold]{data.get('title', '')}[/bold] ({data.get('scenario_type', '')})")
        if data.get("description"):
            console.print(f"  {data['description']}")
        if data.get("expected_behavior"):
            console.print(f"  [dim]Expected: {data['expected_behavior']}[/dim]")
        console.print()
        for msg in data.get("messages", []):
            role = msg.get("role", "?")
            console.print(f"  [{role}] {msg.get('content', '')}")


@app.command("delete-scenario")
def delete_scenario(
    scenario_id: str = typer.Argument(..., help="Scenario ID."),
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation."),
) -> None:
    """Delete a test scenario."""
    if not confirm:
        typer.confirm(f"Delete scenario {scenario_id}?", abort=True)
    with get_client() as client:
        client.delete(f"/creator/assistant/{assistant_id}/tests/scenarios/{scenario_id}")
    print_success(f"Scenario {scenario_id} deleted.")


# ------------------------------------------------------------------
# Run tests
# ------------------------------------------------------------------

@app.command("run")
def run_tests(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    scenario_id: Optional[str] = typer.Option(None, "--scenario", "-s", help="Run a specific scenario."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """Run test scenarios against an assistant."""
    fmt = output or get_output_format()
    body: dict = {}
    if scenario_id:
        body["scenario_id"] = scenario_id

    err_console.print("[dim]Running tests...[/dim]")
    with get_client() as client:
        data = client.post(f"/creator/assistant/{assistant_id}/tests/run", json=body)

    if fmt == "json":
        print_json(data)
        return

    # Single run or batch
    if "runs" in data:
        runs = data["runs"]
        print_success(f"{data.get('count', len(runs))} test(s) completed.")
        for r in runs:
            if "error" in r:
                console.print(f"  [red]FAIL[/red] {r.get('title', r.get('scenario_id', '?'))}: {r['error']}")
            else:
                usage = r.get("token_usage", {})
                tokens = usage.get("total_tokens", "?")
                console.print(
                    f"  [green]OK[/green] {r.get('scenario_id', '?')[:8]}... "
                    f"({r.get('model_used', '?')}, {tokens} tokens, {r.get('elapsed_ms', 0):.0f}ms)"
                )
                resp = r.get("response", "")
                if resp:
                    console.print(f"    {resp[:120]}{'...' if len(resp) > 120 else ''}")
    else:
        # Single run
        usage = data.get("token_usage", {})
        print_success(
            f"Test completed: {data.get('model_used', '?')}, "
            f"{usage.get('total_tokens', '?')} tokens, {data.get('elapsed_ms', 0):.0f}ms"
        )
        console.print()
        console.print(Markdown(data.get("response", "")))


@app.command("runs")
def list_runs(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    limit: int = typer.Option(20, "--limit", "-l", help="Max runs to show."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """List test runs for an assistant."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/{assistant_id}/tests/runs", params={"limit": limit})
    runs = data if isinstance(data, list) else []
    if fmt == "json":
        print_json(runs)
    else:
        format_output([_enrich_run(r) for r in runs], RUN_COLUMNS, fmt)


@app.command("run-detail")
def get_run_detail(
    run_id: str = typer.Argument(..., help="Test run ID."),
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """Show full test run details (input, output, snapshot)."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/{assistant_id}/tests/runs/{run_id}")
    if fmt == "json":
        print_json(data)
        return

    console.print(f"[bold]Test Run[/bold] {data.get('id', '')[:12]}...")
    console.print(f"  Model: {data.get('model_used', '?')}")
    console.print(f"  Time: {data.get('elapsed_ms', 0):.0f}ms")
    usage = data.get("token_usage", {})
    if usage:
        console.print(f"  Tokens: {usage.get('prompt_tokens', '?')}→{usage.get('completion_tokens', '?')} ({usage.get('total_tokens', '?')} total)")

    console.print("\n[bold]Input:[/bold]")
    for msg in data.get("input_messages", []):
        console.print(f"  [{msg.get('role', '?')}] {msg.get('content', '')}")

    console.print("\n[bold]Output:[/bold]")
    output_data = data.get("output", {})
    choices = output_data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
        console.print(Markdown(content))

    snapshot = data.get("assistant_snapshot", {})
    if snapshot:
        console.print(f"\n[dim]Snapshot: llm={snapshot.get('llm')}, rag={snapshot.get('rag_processor')}[/dim]")


# ------------------------------------------------------------------
# Evaluations
# ------------------------------------------------------------------

@app.command("evaluate")
def evaluate_run(
    run_id: str = typer.Argument(..., help="Test run ID to evaluate."),
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    verdict: str = typer.Argument(..., help="Verdict: good, bad, or mixed."),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Evaluation notes."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """Submit an evaluation for a test run."""
    fmt = output or get_output_format()
    if verdict not in ("good", "bad", "mixed"):
        print_error("Verdict must be 'good', 'bad', or 'mixed'.")
        raise typer.Exit(1)

    body: dict = {"verdict": verdict}
    if notes:
        body["notes"] = notes

    with get_client() as client:
        data = client.post(
            f"/creator/assistant/{assistant_id}/tests/runs/{run_id}/evaluate",
            json=body,
        )
    print_success(f"Evaluation recorded: {verdict}")
    if fmt == "json":
        print_json(data)


@app.command("evaluations")
def list_evaluations(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """List evaluations for an assistant's test runs."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/assistant/{assistant_id}/tests/evaluations")
    evals = data if isinstance(data, list) else []
    if fmt == "json":
        print_json(evals)
    else:
        format_output(evals, EVAL_COLUMNS, fmt)
