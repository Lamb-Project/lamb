"""Command registry: maps CLI commands to Creator Interface HTTP endpoints.

Each handler receives (ctx, args, kwargs) where ctx is a CommandContext
with an async http client (AsyncLambClient), user_email, organization_id, etc.
HTTP handlers are async. Local handlers (docs.*, help) are sync.

HTTP commands call /creator/* endpoints via ASGI transport — same code path
as the frontend and lamb-cli. No TCP, no deadlock with single-worker uvicorn.

Authorization (auto/ask/never) is handled by the agent loop, not here.
"""

from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING

from lamb.logging_config import get_logger

if TYPE_CHECKING:
    from lamb.aac.liteshell.shell import CommandContext

logger = get_logger(__name__, component="AAC")

Handler = Callable[["CommandContext", list[str], dict[str, Any]], Any]
COMMAND_REGISTRY: dict[str, Handler] = {}
LOCAL_COMMANDS: set[str] = set()  # sync-only commands (file reads, no HTTP)


def register(name: str, local: bool = False):
    """Decorator to register a command handler.

    Args:
        name: Command key (e.g., "assistant.list")
        local: If True, handler is sync (file reads). Otherwise async (HTTP).
    """
    def decorator(func: Handler) -> Handler:
        COMMAND_REGISTRY[name] = func
        if local:
            LOCAL_COMMANDS.add(name)
        return func
    return decorator


def _unwrap(response: Any) -> Any:
    """Unwrap API responses that use a data envelope."""
    if isinstance(response, dict) and "data" in response and len(response) <= 3:
        return response["data"]
    return response


# ---------------------------------------------------------------------------
# Assistant commands (async HTTP → /creator/assistant/*)
# ---------------------------------------------------------------------------

@register("assistant.list")
async def assistant_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List all assistants for the current user."""
    return _unwrap(await ctx.http.get("/creator/assistant/get_assistants", params={"limit": 100}))


@register("assistant.get")
async def assistant_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get assistant details by ID."""
    if not args:
        raise ValueError("Usage: lamb assistant get <id>")
    return _unwrap(await ctx.http.get(f"/creator/assistant/get_assistant/{args[0]}"))


@register("assistant.config")
async def assistant_config(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Show available connectors, models, and processors."""
    return _unwrap(await ctx.http.get("/creator/assistant/defaults"))


@register("assistant.debug")
async def assistant_debug(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Run a message through an assistant's full pipeline without calling the LLM. Shows what the LLM would see."""
    if not args:
        raise ValueError("Usage: lamb assistant debug <id> --message \"text\"")
    assistant_id = args[0]
    message = kwargs.get("message", kwargs.get("m", ""))
    if not message:
        raise ValueError("Provide --message or -m with the test input")
    return _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/tests/run",
        json={"message": message, "debug_bypass": True},
    ))


@register("assistant.create")
async def assistant_create(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Create a new assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant create <name> [--system-prompt ...] [--llm ...]")
    name = args[0]

    metadata: dict[str, Any] = {}
    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            metadata[key] = kwargs[key]

    body: dict[str, Any] = {"name": name}
    if kwargs.get("system_prompt"):
        body["system_prompt"] = kwargs["system_prompt"]
    if kwargs.get("description") or kwargs.get("d"):
        body["description"] = kwargs.get("description", kwargs.get("d", ""))
    if kwargs.get("prompt_template"):
        body["prompt_template"] = kwargs["prompt_template"]
    if kwargs.get("rag_top_k"):
        body["RAG_Top_k"] = int(kwargs["rag_top_k"])
    if kwargs.get("rag_collections"):
        body["RAG_collections"] = kwargs["rag_collections"]
    if metadata:
        body["metadata"] = json.dumps(metadata)

    return _unwrap(await ctx.http.post("/creator/assistant/create_assistant", json=body))


@register("assistant.update")
async def assistant_update(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Update an assistant (fetch-and-merge handled by Creator Interface)."""
    if not args:
        raise ValueError("Usage: lamb assistant update <id> [--name ...] [--system-prompt ...]")
    assistant_id = args[0]

    body: dict[str, Any] = {}
    if "name" in kwargs or "n" in kwargs:
        body["name"] = kwargs.get("name", kwargs.get("n"))
    if "system_prompt" in kwargs:
        body["system_prompt"] = kwargs["system_prompt"]
    if "description" in kwargs or "d" in kwargs:
        body["description"] = kwargs.get("description", kwargs.get("d"))
    if "prompt_template" in kwargs:
        body["prompt_template"] = kwargs["prompt_template"]

    metadata: dict[str, Any] = {}
    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            metadata[key] = kwargs[key]
    if metadata:
        body["metadata"] = json.dumps(metadata)

    if not body:
        raise ValueError("No fields to update. Use --name, --system-prompt, --llm, etc.")

    return _unwrap(await ctx.http.put(f"/creator/assistant/update_assistant/{assistant_id}", json=body))


@register("assistant.delete")
async def assistant_delete(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Delete (soft-delete) an assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant delete <id>")
    return _unwrap(await ctx.http.delete(f"/creator/assistant/delete_assistant/{args[0]}"))


# ---------------------------------------------------------------------------
# Rubric commands (async HTTP → /creator/rubrics/*)
# ---------------------------------------------------------------------------

@register("rubric.list")
async def rubric_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List your rubrics."""
    result = _unwrap(await ctx.http.get("/creator/rubrics", params={"limit": 100}))
    if isinstance(result, dict) and "rubrics" in result:
        return result["rubrics"]
    return result


@register("rubric.list-public")
async def rubric_list_public(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List public rubrics (templates)."""
    result = _unwrap(await ctx.http.get("/creator/rubrics/public", params={"limit": 100}))
    if isinstance(result, dict) and "rubrics" in result:
        return result["rubrics"]
    return result


@register("rubric.get")
async def rubric_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get rubric details by UUID."""
    if not args:
        raise ValueError("Usage: lamb rubric get <rubric_id>")
    return _unwrap(await ctx.http.get(f"/creator/rubrics/{args[0]}"))


@register("rubric.export")
async def rubric_export(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Export a rubric as JSON or markdown."""
    if not args:
        raise ValueError("Usage: lamb rubric export <rubric_id> [--format json|md]")
    fmt = kwargs.get("format", kwargs.get("f", "json"))
    if fmt in ("md", "markdown"):
        return await ctx.http.get(f"/creator/rubrics/{args[0]}/export/markdown")
    return await ctx.http.get(f"/creator/rubrics/{args[0]}/export/json")


# ---------------------------------------------------------------------------
# Knowledge Base commands (async HTTP → /creator/knowledgebases/*)
# ---------------------------------------------------------------------------

@register("kb.list")
async def kb_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List your knowledge bases."""
    return _unwrap(await ctx.http.get("/creator/knowledgebases/user"))


@register("kb.get")
async def kb_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get KB details by ID."""
    if not args:
        raise ValueError("Usage: lamb kb get <id>")
    return _unwrap(await ctx.http.get(f"/creator/knowledgebases/kb/{args[0]}"))


# ---------------------------------------------------------------------------
# Template commands (async HTTP → /creator/prompt-templates/*)
# ---------------------------------------------------------------------------

@register("template.list")
async def template_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List your prompt templates."""
    return _unwrap(await ctx.http.get("/creator/prompt-templates/list"))


@register("template.get")
async def template_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get template details by ID."""
    if not args:
        raise ValueError("Usage: lamb template get <id>")
    return _unwrap(await ctx.http.get(f"/creator/prompt-templates/{args[0]}"))


# ---------------------------------------------------------------------------
# Model commands (async HTTP → /creator/models)
# ---------------------------------------------------------------------------

@register("model.list")
async def model_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List available models for the user's organization."""
    return _unwrap(await ctx.http.get("/creator/models"))


# ---------------------------------------------------------------------------
# Test commands (async HTTP → /creator/assistant/{id}/tests/*)
# ---------------------------------------------------------------------------

@register("test.scenarios")
async def test_scenarios(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List test scenarios for an assistant."""
    if not args:
        raise ValueError("Usage: lamb test scenarios <assistant_id>")
    return _unwrap(await ctx.http.get(f"/creator/assistant/{args[0]}/tests/scenarios"))


@register("test.add")
async def test_add(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Add a test scenario to an assistant."""
    if not args:
        raise ValueError("Usage: lamb test add <assistant_id> <title> --message \"text\"")
    assistant_id = args[0]
    title = args[1] if len(args) > 1 else kwargs.get("title", "Test scenario")
    message = kwargs.get("message", kwargs.get("m", ""))
    if not message:
        raise ValueError("Provide --message with the test input")
    return _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/tests/scenarios",
        json={
            "title": title,
            "message": message,
            "description": kwargs.get("description", ""),
            "scenario_type": kwargs.get("type", kwargs.get("t", "single_turn")),
            "expected_behavior": kwargs.get("expected", kwargs.get("e", "")),
        },
    ))


@register("test.run")
async def test_run(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Run test scenarios through the real completion pipeline."""
    if not args:
        raise ValueError("Usage: lamb test run <assistant_id> [--scenario <id>] [--bypass]")
    assistant_id = args[0]
    bypass = kwargs.get("bypass", kwargs.get("b", False))
    body: dict[str, Any] = {
        "debug_bypass": bypass is True or bypass == "true",
    }
    scenario_id = kwargs.get("scenario", kwargs.get("s"))
    if scenario_id:
        body["scenario_id"] = scenario_id
    return _unwrap(await ctx.http.post(f"/creator/assistant/{assistant_id}/tests/run", json=body))


@register("test.runs")
async def test_runs(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List test runs for an assistant."""
    if not args:
        raise ValueError("Usage: lamb test runs <assistant_id>")
    return _unwrap(await ctx.http.get(f"/creator/assistant/{args[0]}/tests/runs"))


@register("test.run-detail")
async def test_run_detail(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get full details of a test run."""
    if not args:
        raise ValueError("Usage: lamb test run-detail <run_id> <assistant_id>")
    assistant_id = args[1] if len(args) > 1 else kwargs.get("assistant", kwargs.get("a", ""))
    if not assistant_id:
        raise ValueError("Usage: lamb test run-detail <run_id> <assistant_id>")
    return _unwrap(await ctx.http.get(f"/creator/assistant/{assistant_id}/tests/runs/{args[0]}"))


@register("test.evaluate")
async def test_evaluate(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Record an evaluation for a test run."""
    if len(args) < 2:
        raise ValueError("Usage: lamb test evaluate <run_id> <verdict: good|bad|mixed> [<assistant_id>]")
    run_id = args[0]
    verdict = args[1]
    if verdict not in ("good", "bad", "mixed"):
        raise ValueError("Verdict must be 'good', 'bad', or 'mixed'")
    assistant_id = args[2] if len(args) > 2 else kwargs.get("assistant", kwargs.get("a", ""))
    if not assistant_id:
        raise ValueError("Usage: lamb test evaluate <run_id> <verdict> <assistant_id>")
    return _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/tests/runs/{run_id}/evaluate",
        json={
            "verdict": verdict,
            "notes": kwargs.get("notes", kwargs.get("n", "")),
        },
    ))


# ---------------------------------------------------------------------------
# Documentation commands (LOCAL — sync, read files, no HTTP)
# ---------------------------------------------------------------------------

_DOCS_DIR = None


def _get_docs_dir():
    """Resolve the aac_docs directory path (lazy, cached)."""
    global _DOCS_DIR
    if _DOCS_DIR is None:
        from pathlib import Path
        _DOCS_DIR = Path(__file__).parents[1] / "docs"
    return _DOCS_DIR


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse YAML front matter from a markdown file. Returns (metadata, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    import yaml
    try:
        meta = yaml.safe_load(text[3:end]) or {}
    except Exception:
        meta = {}
    body = text[end + 3:].lstrip("\n")
    return meta, body


@register("docs.index", local=True)
def docs_index(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """List available LAMB documentation topics with summaries."""
    docs_dir = _get_docs_dir()
    index_file = docs_dir / "index.md"
    if not index_file.exists():
        raise ValueError("Documentation index not found")

    meta, body = _parse_front_matter(index_file.read_text(encoding="utf-8"))

    sections = []
    for md_file in sorted(docs_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue
        file_meta, _ = _parse_front_matter(md_file.read_text(encoding="utf-8"))
        if not file_meta.get("topic"):
            continue
        sections.append({
            "topic": file_meta["topic"],
            "file": md_file.name,
            "covers": file_meta.get("covers", []),
            "answers": file_meta.get("answers", []),
        })

    return {
        "version": meta.get("version", "unknown"),
        "topics": [s["topic"] for s in sections],
        "sections": sections,
    }


@register("docs.read", local=True)
def docs_read(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Read a specific LAMB documentation topic. Use --section to read only a subsection."""
    if not args:
        raise ValueError(
            "Usage: lamb docs read <topic> [--section \"heading\"]\n"
            "Use 'lamb docs index' to see available topics."
        )
    topic = args[0]
    section = kwargs.get("section")

    docs_dir = _get_docs_dir()
    candidates = [docs_dir / topic, docs_dir / f"{topic}.md"]
    doc_file = None
    for c in candidates:
        if c.exists() and c.is_file():
            doc_file = c
            break

    if not doc_file:
        available = [f.stem for f in docs_dir.glob("*.md") if f.name != "index.md"]
        raise ValueError(f"Topic '{topic}' not found. Available: {available}")

    meta, body = _parse_front_matter(doc_file.read_text(encoding="utf-8"))

    if section:
        lines = body.split("\n")
        section_lower = section.lower().strip()
        in_section = False
        section_lines = []
        for line in lines:
            if line.startswith("## "):
                if in_section:
                    break
                heading = line[3:].strip().lower()
                if section_lower in heading:
                    in_section = True
                    section_lines.append(line)
            elif line.startswith("# ") and in_section:
                break
            elif in_section:
                section_lines.append(line)

        if not section_lines:
            headings = [l[3:].strip() for l in lines if l.startswith("## ")]
            raise ValueError(
                f"Section '{section}' not found in '{topic}'. "
                f"Available sections: {headings}"
            )
        body = "\n".join(section_lines).strip()

    return {
        "topic": meta.get("topic", topic),
        "file": doc_file.name,
        "content": body,
    }


# ---------------------------------------------------------------------------
# Utility commands (LOCAL — sync)
# ---------------------------------------------------------------------------

@register("help", local=True)
def help_cmd(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict[str, str]:
    """Show available commands."""
    result = {}
    for key, func in sorted(COMMAND_REGISTRY.items()):
        doc = func.__doc__ or ""
        result[f"lamb {key.replace('.', ' ')}"] = doc.split("\n")[0].strip()
    return result
