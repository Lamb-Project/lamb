"""Knowledge Store management commands — lamb ks *.

Targets the new KB Server (port 9092) via the LAMB Creator Interface at
``/creator/knowledge-stores/...``. The legacy ``lamb kb *`` commands keep
serving the stable KB Server (port 9090) and are not modified.

Both ``lamb ks`` (primary, short) and ``lamb knowledge-store`` (alias) are
registered in ``main.py`` and resolve to this same command group.
"""

from __future__ import annotations

import time
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success, print_warning

app = typer.Typer(help="Manage Knowledge Stores (new KB Server).")


# ----------------------------------------------------------------------
# Output column / detail definitions
# ----------------------------------------------------------------------


KS_LIST_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("chunking_strategy", "Chunking"),
    ("embedding_vendor", "Vendor"),
    ("embedding_model", "Model"),
    ("vector_db_backend", "Backend"),
    ("is_shared", "Shared"),
    ("content_count", "Content"),
]

KS_DETAIL_FIELDS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("chunking_strategy", "Chunking Strategy"),
    ("chunking_params", "Chunking Params"),
    ("embedding_vendor", "Embedding Vendor"),
    ("embedding_model", "Embedding Model"),
    ("embedding_endpoint", "Embedding Endpoint"),
    ("vector_db_backend", "Vector DB"),
    ("is_shared", "Shared"),
    ("is_owner", "Is Owner"),
    ("server_status", "Server Status"),
    ("document_count", "Documents"),
    ("chunk_count", "Chunks"),
    ("owner_email", "Owner"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

CONTENT_LINK_COLUMNS = [
    ("library_item_id", "Item ID"),
    ("item_title", "Title"),
    ("library_name", "Library"),
    ("item_source_type", "Source"),
    ("status", "Status"),
    ("chunks_created", "Chunks"),
    ("kb_job_id", "Job"),
]

QUERY_RESULT_COLUMNS = [
    ("score", "Score"),
    ("source_title", "Title"),
    ("source_item_id", "Item"),
    ("snippet", "Snippet"),
]


# ----------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------


@app.command("options")
def show_options(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show the chunking strategies, embedding vendors / models, and vector
    DB backends available to your organization."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/knowledge-stores/options")
    format_output(data, [], fmt)


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------


@app.command("create")
def create_knowledge_store(
    name: str = typer.Argument(..., help="Knowledge Store name."),
    chunking: str = typer.Option(..., "--chunking", help="Chunking strategy (e.g. 'simple', 'hierarchical', 'by_page', 'by_section')."),
    embedding_vendor: str = typer.Option(..., "--embedding-vendor", help="Embedding vendor (e.g. 'openai', 'ollama')."),
    embedding_model: str = typer.Option(..., "--embedding-model", help="Embedding model identifier."),
    vector_db: str = typer.Option(..., "--vector-db", help="Vector DB backend (e.g. 'chromadb', 'qdrant')."),
    description: str = typer.Option("", "--description", "-d", help="Optional description."),
    embedding_endpoint: Optional[str] = typer.Option(None, "--embedding-endpoint", help="Optional override for the vendor API base URL."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new Knowledge Store.

    The chunking strategy, embedding vendor / model, embedding endpoint, and
    vector DB backend are LOCKED at creation time — only ``name`` and
    ``description`` can change later.
    """
    fmt = output or get_output_format()
    body: dict = {
        "name": name,
        "description": description,
        "chunking_strategy": chunking,
        "embedding_vendor": embedding_vendor,
        "embedding_model": embedding_model,
        "vector_db_backend": vector_db,
    }
    if embedding_endpoint:
        body["embedding_endpoint"] = embedding_endpoint
    with get_client() as client:
        data = client.post("/creator/knowledge-stores", json=body)
    print_success(f"Knowledge Store created: {data.get('id', '')}")
    format_output(data, KS_LIST_COLUMNS, fmt, detail_fields=KS_DETAIL_FIELDS)


@app.command("list")
def list_knowledge_stores(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List Knowledge Stores accessible to you (owned + shared)."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/knowledge-stores")
    items = resp.get("knowledge_stores", []) if isinstance(resp, dict) else resp
    format_output(items, KS_LIST_COLUMNS, fmt)


@app.command("get")
def get_knowledge_store(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a Knowledge Store including its locked configuration."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/knowledge-stores/{ks_id}")
    format_output(data, KS_LIST_COLUMNS, fmt, detail_fields=KS_DETAIL_FIELDS)


@app.command("update")
def update_knowledge_store(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    name: Optional[str] = typer.Option(None, "--name", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
) -> None:
    """Update name and/or description (the only mutable fields)."""
    if name is None and description is None:
        print_error("Specify --name or --description (or both).")
        raise typer.Exit(1)
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    with get_client() as client:
        client.put(f"/creator/knowledge-stores/{ks_id}", json=body)
    print_success(f"Knowledge Store {ks_id} updated.")


@app.command("delete")
def delete_knowledge_store(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a Knowledge Store and all its vectors."""
    if not confirm:
        typer.confirm(f"Delete Knowledge Store {ks_id}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/knowledge-stores/{ks_id}")
    msg = (
        data.get("message", "Knowledge Store deleted.")
        if isinstance(data, dict)
        else "Knowledge Store deleted."
    )
    print_success(msg)


@app.command("share")
def share_knowledge_store(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable sharing."),
) -> None:
    """Enable or disable organization-wide sharing."""
    if enable is None:
        print_error("Specify --enable or --disable.")
        raise typer.Exit(1)
    with get_client() as client:
        client.put(f"/creator/knowledge-stores/{ks_id}/share", json={"is_shared": enable})
    state = "enabled" if enable else "disabled"
    print_success(f"Sharing {state} for Knowledge Store {ks_id}.")


# ----------------------------------------------------------------------
# Content (library item -> KS)
# ----------------------------------------------------------------------


@app.command("add-content")
def add_content(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    library_id: str = typer.Option(..., "--library", "-l", help="Source library ID."),
    items: str = typer.Option(..., "--items", "-i", help="Comma-separated library item IDs."),
    wait: bool = typer.Option(False, "--wait", help="Block until ingestion completes."),
) -> None:
    """Ingest one or more library items into a Knowledge Store."""
    item_ids = [s.strip() for s in items.split(",") if s.strip()]
    if not item_ids:
        print_error("No item IDs provided.")
        raise typer.Exit(1)
    body = {"library_id": library_id, "item_ids": item_ids}
    with get_client(timeout=120.0) as client:
        data = client.post(f"/creator/knowledge-stores/{ks_id}/content", json=body)

    job_id = data.get("job_id") if isinstance(data, dict) else None
    if isinstance(data, dict) and data.get("status") == "noop":
        print_warning(data.get("message", "No new items linked."))
        return

    print_success(
        f"Ingestion queued for {len(item_ids)} item(s) "
        f"(job: {job_id or '<unknown>'})."
    )

    if wait:
        _wait_for_items(ks_id, item_ids)


@app.command("list-content")
def list_content(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List linked library items for a Knowledge Store."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get(f"/creator/knowledge-stores/{ks_id}/content")
    links = resp.get("content", []) if isinstance(resp, dict) else resp
    format_output(links, CONTENT_LINK_COLUMNS, fmt)


@app.command("remove-content")
def remove_content(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    library_item_id: str = typer.Argument(..., help="Library item ID to remove from this KS."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Remove a library item's vectors from a Knowledge Store.

    Does not affect the library item itself — only its presence in this KS.
    """
    if not confirm:
        typer.confirm(f"Remove item {library_item_id} from Knowledge Store {ks_id}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/knowledge-stores/{ks_id}/content/{library_item_id}")
    msg = (
        data.get("message", "Content removed.")
        if isinstance(data, dict)
        else "Content removed."
    )
    print_success(msg)


# ----------------------------------------------------------------------
# Status / polling
# ----------------------------------------------------------------------


def _poll_link_status(ks_id: str, library_item_id: str) -> dict:
    """Single-shot status fetch for one (KS, library item) pair."""
    with get_client(timeout=60.0) as client:
        return client.get(f"/creator/knowledge-stores/{ks_id}/content/{library_item_id}")


def _wait_for_items(ks_id: str, library_item_ids: list[str],
                    max_wait_seconds: int = 600) -> None:
    """Poll each item with exponential backoff until ready/failed.

    Backoff schedule: 1s, 2s, 4s, 8s, 16s, then capped at 16s. This avoids
    Marc's #336 finding (#19) about flaky 15s hard budgets while staying
    responsive on quick jobs.
    """
    pending = set(library_item_ids)
    deadline = time.time() + max_wait_seconds
    delay = 1.0
    while pending and time.time() < deadline:
        for item_id in list(pending):
            try:
                status_data = _poll_link_status(ks_id, item_id)
            except Exception as e:
                print_warning(f"  {item_id}: poll error — {e}")
                continue
            status = status_data.get("status") if isinstance(status_data, dict) else None
            if status in ("ready", "failed"):
                pending.discard(item_id)
                if status == "ready":
                    chunks = status_data.get("chunks_created", "?")
                    print_success(f"  {item_id}: ready ({chunks} chunks)")
                else:
                    print_error(
                        f"  {item_id}: failed — {status_data.get('error_message', 'unknown')}"
                    )
        if pending:
            time.sleep(delay)
            delay = min(delay * 2, 16.0)
    if pending:
        print_warning(
            f"Timed out waiting on {len(pending)} item(s); they remain in flight."
        )


@app.command("status")
def status(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    item: Optional[str] = typer.Option(None, "--item", "-i", help="Single library item ID to inspect."),
    wait: bool = typer.Option(False, "--wait", help="Block until ready/failed (single item only)."),
    max_wait: int = typer.Option(600, "--max-wait", help="Maximum seconds to wait."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show ingestion status for a single linked item or for the whole KS."""
    fmt = output or get_output_format()
    if item:
        if wait:
            _wait_for_items(ks_id, [item], max_wait_seconds=max_wait)
        data = _poll_link_status(ks_id, item)
        format_output(data, CONTENT_LINK_COLUMNS, fmt, detail_fields=CONTENT_LINK_COLUMNS)
    else:
        with get_client() as client:
            resp = client.get(f"/creator/knowledge-stores/{ks_id}/content")
        links = resp.get("content", []) if isinstance(resp, dict) else resp
        format_output(links, CONTENT_LINK_COLUMNS, fmt)


# ----------------------------------------------------------------------
# Query
# ----------------------------------------------------------------------


@app.command("query")
def query(
    ks_id: str = typer.Argument(..., help="Knowledge Store ID."),
    query_text: str = typer.Argument(..., help="Query text."),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Maximum chunks to return."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Run a similarity search against a Knowledge Store.

    Returns chunks with permalink-bearing metadata so citations resolve via
    LAMB's /docs/ proxy.
    """
    fmt = output or get_output_format()
    body = {"query_text": query_text, "top_k": top_k}
    with get_client(timeout=60.0) as client:
        data = client.post(f"/creator/knowledge-stores/{ks_id}/query", json=body)

    results = data.get("results", []) if isinstance(data, dict) else []
    flattened = []
    for r in results:
        meta = r.get("metadata", {}) or {}
        snippet = (r.get("text") or "").replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        flattened.append({
            "score": round(r.get("score", 0), 4),
            "source_title": meta.get("source_title") or meta.get("title", "?"),
            "source_item_id": meta.get("source_item_id", "?"),
            "snippet": snippet,
        })
    format_output(flattened, QUERY_RESULT_COLUMNS, fmt)
