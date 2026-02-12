"""Assistant management commands — lamb assistant *."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success, print_warning, stderr_console

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
    ("connector", "Connector"),
    ("llm", "LLM"),
    ("prompt_processor", "Prompt Processor"),
    ("rag_processor", "RAG Processor"),
    ("rag_top_k", "RAG Top-K"),
    ("rag_collection_names", "RAG Collections"),
]


def _parse_metadata(data: dict) -> dict:
    """Extract metadata fields into top-level keys for display."""
    metadata_str = data.get("metadata") or data.get("api_callback") or ""
    if isinstance(metadata_str, str) and metadata_str:
        try:
            md = json.loads(metadata_str)
            data.setdefault("connector", md.get("connector", ""))
            data.setdefault("llm", md.get("llm", ""))
            data.setdefault("prompt_processor", md.get("prompt_processor", ""))
            data.setdefault("rag_processor", md.get("rag_processor", ""))
        except (json.JSONDecodeError, AttributeError):
            pass
    elif isinstance(metadata_str, dict):
        data.setdefault("connector", metadata_str.get("connector", ""))
        data.setdefault("llm", metadata_str.get("llm", ""))
        data.setdefault("prompt_processor", metadata_str.get("prompt_processor", ""))
        data.setdefault("rag_processor", metadata_str.get("rag_processor", ""))
    return data


def _fetch_capabilities(client) -> dict:
    """Fetch system capabilities (connectors, models, processors)."""
    try:
        return client.get("/lamb/v1/completions/list")
    except Exception:
        return {}


def _fetch_defaults(client) -> dict:
    """Fetch organization assistant defaults."""
    try:
        resp = client.get("/creator/assistant/defaults")
        if isinstance(resp, dict):
            return resp.get("config", resp)
        return {}
    except Exception:
        return {}


def _build_metadata(
    connector: str,
    llm: str,
    prompt_processor: str,
    rag_processor: str,
    vision: bool = False,
    image_generation: bool = False,
) -> str:
    """Build the metadata JSON string for the assistant."""
    md = {
        "prompt_processor": prompt_processor,
        "connector": connector,
        "llm": llm,
        "rag_processor": rag_processor,
        "capabilities": {
            "vision": vision,
            "image_generation": image_generation,
        },
    }
    return json.dumps(md)


def _choose_from_list(prompt_text: str, options: list[str], default: str = "") -> str:
    """Interactive chooser: display numbered options and let user pick."""
    stderr_console.print(f"\n[bold]{prompt_text}[/bold]")
    for i, opt in enumerate(options, 1):
        marker = " [green](default)[/green]" if opt == default else ""
        stderr_console.print(f"  {i}. {opt}{marker}")

    while True:
        choice = typer.prompt("Choose", default=default if default in options else "")
        # Accept number or exact name
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        elif choice in options:
            return choice
        stderr_console.print(f"[yellow]Enter a number 1-{len(options)} or an exact name.[/yellow]")


def _interactive_wizard(client) -> dict:
    """Run the interactive assistant configuration wizard.

    Returns a dict with: connector, llm, prompt_processor, rag_processor, vision, image_generation.
    """
    capabilities = _fetch_capabilities(client)
    defaults = _fetch_defaults(client)

    # Extract available options
    connectors_data = capabilities.get("connectors", {})
    connector_names = list(connectors_data.keys()) if connectors_data else ["openai"]
    prompt_processors = capabilities.get("prompt_processors", ["simple_augment"])
    rag_processors = capabilities.get("rag_processors", ["no_rag"])

    default_connector = defaults.get("connector", connector_names[0] if connector_names else "openai")
    default_llm = defaults.get("llm", "")
    default_pp = defaults.get("prompt_processor", prompt_processors[0] if prompt_processors else "simple_augment")
    default_rag = defaults.get("rag_processor", "no_rag")

    stderr_console.print("\n[bold cyan]--- Assistant Configuration Wizard ---[/bold cyan]")

    # 1. Connector
    connector = _choose_from_list("Select a connector:", connector_names, default_connector)

    # 2. LLM (depends on connector)
    connector_info = connectors_data.get(connector, {})
    available_llms = connector_info.get("available_llms", [])
    if not available_llms:
        available_llms = [default_llm] if default_llm else ["gpt-4o-mini"]
    llm = _choose_from_list("Select an LLM model:", available_llms, default_llm)

    # 3. Prompt Processor
    pp = _choose_from_list("Select a prompt processor:", prompt_processors, default_pp)

    # 4. RAG Processor
    rag = _choose_from_list("Select a RAG processor:", rag_processors, default_rag)

    # 5. Capabilities
    vision = typer.confirm("Enable vision?", default=False)
    image_gen = typer.confirm("Enable image generation?", default=False)

    stderr_console.print("\n[bold cyan]--- Configuration Summary ---[/bold cyan]")
    stderr_console.print(f"  Connector:        {connector}")
    stderr_console.print(f"  LLM:              {llm}")
    stderr_console.print(f"  Prompt Processor: {pp}")
    stderr_console.print(f"  RAG Processor:    {rag}")
    stderr_console.print(f"  Vision:           {vision}")
    stderr_console.print(f"  Image Generation: {image_gen}")
    stderr_console.print("")

    return {
        "connector": connector,
        "llm": llm,
        "prompt_processor": pp,
        "rag_processor": rag,
        "vision": vision,
        "image_generation": image_gen,
    }


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
    data = _parse_metadata(data)
    format_output(data, ASSISTANT_LIST_COLUMNS, fmt, detail_fields=ASSISTANT_DETAIL_FIELDS)


@app.command("create")
def create_assistant(
    name: str = typer.Argument(..., help="Assistant name."),
    description: str = typer.Option("", "--description", "-d", help="Assistant description."),
    system_prompt: str = typer.Option("", "--system-prompt", "-s", help="System prompt text."),
    system_prompt_file: Optional[Path] = typer.Option(
        None, "--system-prompt-file", help="Read system prompt from file."
    ),
    connector: Optional[str] = typer.Option(None, "--connector", help="LLM connector (e.g. openai, ollama)."),
    llm: Optional[str] = typer.Option(None, "--llm", help="LLM model name (e.g. gpt-4o-mini)."),
    prompt_processor: Optional[str] = typer.Option(None, "--prompt-processor", help="Prompt processor plugin."),
    rag_processor: Optional[str] = typer.Option(None, "--rag-processor", help="RAG processor plugin."),
    vision: bool = typer.Option(False, "--vision/--no-vision", help="Enable vision capability."),
    image_generation: bool = typer.Option(False, "--image-generation/--no-image-generation", help="Enable image generation."),
    rag_top_k: Optional[int] = typer.Option(None, "--rag-top-k", help="Number of RAG chunks."),
    rag_collections: Optional[str] = typer.Option(
        None, "--rag-collections", help="Comma-separated RAG collection names."
    ),
    prompt_template: Optional[str] = typer.Option(None, "--prompt-template", help="Prompt template text."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run interactive configuration wizard."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new assistant.

    Use --interactive/-i for a guided wizard that shows available connectors,
    models, and processors. Or use flags (--connector, --llm, etc.) for scripting.
    If no configuration flags are provided and stdin is a TTY, the wizard runs
    automatically.
    """
    fmt = output or get_output_format()
    prompt = system_prompt
    if system_prompt_file:
        prompt = system_prompt_file.read_text(encoding="utf-8")

    body: dict = {"name": name, "description": description, "system_prompt": prompt}
    if prompt_template is not None:
        body["prompt_template"] = prompt_template
    if rag_top_k is not None:
        body["RAG_Top_k"] = rag_top_k
    if rag_collections:
        body["RAG_collections"] = rag_collections

    has_config_flags = any(v is not None for v in [connector, llm, prompt_processor, rag_processor])
    is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()

    with get_client() as client:
        if has_config_flags:
            # Scripting mode: use explicit flags, fill missing from server defaults
            if not all([connector, llm]):
                defaults = _fetch_defaults(client)
                connector = connector or defaults.get("connector", "openai")
                llm = llm or defaults.get("llm", "gpt-4o-mini")
                prompt_processor = prompt_processor or defaults.get("prompt_processor", "simple_augment")
                rag_processor = rag_processor or defaults.get("rag_processor", "no_rag")
            body["metadata"] = _build_metadata(
                connector=connector,
                llm=llm,
                prompt_processor=prompt_processor or "simple_augment",
                rag_processor=rag_processor or "no_rag",
                vision=vision,
                image_generation=image_generation,
            )
        elif interactive or is_tty:
            # Interactive wizard
            config = _interactive_wizard(client)
            body["metadata"] = _build_metadata(**config)
        # else: no metadata — server will use its defaults

        data = client.post("/creator/assistant/create_assistant", json=body)
    print_success(f"Assistant created: {data.get('assistant_id', '')}")
    format_output(data, ASSISTANT_LIST_COLUMNS, fmt)


@app.command("update")
def update_assistant(
    assistant_id: str = typer.Argument(..., help="Assistant ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
    system_prompt: Optional[str] = typer.Option(None, "--system-prompt", "-s", help="New system prompt."),
    connector: Optional[str] = typer.Option(None, "--connector", help="LLM connector."),
    llm: Optional[str] = typer.Option(None, "--llm", help="LLM model name."),
    prompt_processor: Optional[str] = typer.Option(None, "--prompt-processor", help="Prompt processor plugin."),
    rag_processor: Optional[str] = typer.Option(None, "--rag-processor", help="RAG processor plugin."),
    vision: Optional[bool] = typer.Option(None, "--vision/--no-vision", help="Enable/disable vision."),
    image_generation: Optional[bool] = typer.Option(None, "--image-generation/--no-image-generation", help="Enable/disable image generation."),
    rag_top_k: Optional[int] = typer.Option(None, "--rag-top-k", help="Number of RAG chunks."),
    rag_collections: Optional[str] = typer.Option(
        None, "--rag-collections", help="Comma-separated RAG collection names."
    ),
    prompt_template: Optional[str] = typer.Option(None, "--prompt-template", help="Prompt template text."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run interactive configuration wizard."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Update an existing assistant.

    Use --interactive/-i to re-configure the assistant with the wizard.
    Or pass individual flags to change specific settings.
    """
    fmt = output or get_output_format()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if system_prompt is not None:
        body["system_prompt"] = system_prompt
    if prompt_template is not None:
        body["prompt_template"] = prompt_template
    if rag_top_k is not None:
        body["RAG_Top_k"] = rag_top_k
    if rag_collections is not None:
        body["RAG_collections"] = rag_collections

    has_config_flags = any(v is not None for v in [connector, llm, prompt_processor, rag_processor, vision, image_generation])

    with get_client() as client:
        if interactive:
            config = _interactive_wizard(client)
            body["metadata"] = _build_metadata(**config)
        elif has_config_flags:
            # Fetch current metadata to merge changes
            current = client.get(f"/creator/assistant/get_assistant/{assistant_id}")
            current_md = {}
            md_str = current.get("metadata") or current.get("api_callback") or "{}"
            if isinstance(md_str, str):
                try:
                    current_md = json.loads(md_str)
                except (json.JSONDecodeError, AttributeError):
                    pass
            elif isinstance(md_str, dict):
                current_md = md_str

            body["metadata"] = _build_metadata(
                connector=connector or current_md.get("connector", "openai"),
                llm=llm or current_md.get("llm", "gpt-4o-mini"),
                prompt_processor=prompt_processor or current_md.get("prompt_processor", "simple_augment"),
                rag_processor=rag_processor or current_md.get("rag_processor", "no_rag"),
                vision=vision if vision is not None else current_md.get("capabilities", {}).get("vision", False),
                image_generation=image_generation if image_generation is not None else current_md.get("capabilities", {}).get("image_generation", False),
            )

        if not body:
            print_error("No fields to update. Provide at least one option.")
            raise typer.Exit(1)

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


@app.command("config")
def show_config(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show available connectors, models, and processors.

    Queries the server for the current system capabilities and organization
    defaults, so you know what values to use with --connector, --llm, etc.
    """
    fmt = output or get_output_format()
    with get_client() as client:
        capabilities = _fetch_capabilities(client)
        defaults = _fetch_defaults(client)

    if fmt == "json":
        from lamb_cli.output import print_json

        print_json({"capabilities": capabilities, "defaults": defaults})
        return

    stderr_console.print("\n[bold]Connectors & Models[/bold]")
    connectors = capabilities.get("connectors", {})
    for name, info in connectors.items():
        models = info.get("available_llms", [])
        stderr_console.print(f"  [cyan]{name}[/cyan]: {', '.join(models) if models else '(no models)'}")

    stderr_console.print("\n[bold]Prompt Processors[/bold]")
    for pp in capabilities.get("prompt_processors", []):
        stderr_console.print(f"  {pp}")

    stderr_console.print("\n[bold]RAG Processors[/bold]")
    for rp in capabilities.get("rag_processors", []):
        stderr_console.print(f"  {rp}")

    if defaults:
        stderr_console.print("\n[bold]Organization Defaults[/bold]")
        for key in ("connector", "llm", "prompt_processor", "rag_processor"):
            val = defaults.get(key, "")
            if val:
                stderr_console.print(f"  {key}: {val}")
    stderr_console.print("")
