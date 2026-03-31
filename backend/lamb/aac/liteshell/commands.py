"""Command registry: maps CLI commands to LAMB service function calls.

Each handler receives (ctx, args, kwargs) where ctx is a CommandContext
with user_email, organization_id, and user_id. Handlers return structured data.

All commands execute directly. Authorization (auto/ask/never) is handled
by the agent loop, not here — commands are only called when authorized.
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


def register(name: str):
    """Decorator to register a command handler."""
    def decorator(func: Handler) -> Handler:
        COMMAND_REGISTRY[name] = func
        return func
    return decorator


# ---------------------------------------------------------------------------
# Assistant READ commands
# ---------------------------------------------------------------------------

@register("assistant.list")
def assistant_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List all assistants for the current user."""
    from lamb.services.assistant_service import AssistantService
    svc = AssistantService()
    return svc.get_assistants_by_owner(ctx.user_email)


@register("assistant.get")
def assistant_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Get assistant details by ID."""
    if not args:
        raise ValueError("Usage: lamb assistant get <id>")
    from lamb.services.assistant_service import AssistantService
    svc = AssistantService()
    assistant = svc.get_assistant_with_publication_dict(int(args[0]))
    if not assistant:
        raise ValueError(f"Assistant {args[0]} not found")
    return assistant


@register("assistant.config")
def assistant_config(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Show available connectors, models, and processors."""
    from lamb.completions.main import load_plugins
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    import importlib

    pps = load_plugins('pps')
    connectors = load_plugins('connectors')
    rag_processors = load_plugins('rag')

    connector_models = {}
    for connector_name in connectors:
        module = importlib.import_module(f"lamb.completions.connectors.{connector_name}")
        if hasattr(module, 'get_available_llms'):
            try:
                connector_models[connector_name] = module.get_available_llms(ctx.user_email)
            except Exception:
                connector_models[connector_name] = []
        else:
            connector_models[connector_name] = []

    resolver = OrganizationConfigResolver(ctx.user_email)
    global_default = resolver.get_global_default_model_config()

    return {
        "prompt_processors": list(pps.keys()),
        "connectors": connector_models,
        "rag_processors": list(rag_processors.keys()),
        "defaults": {"global_default_model": global_default},
    }


# ---------------------------------------------------------------------------
# Assistant WRITE commands (execute directly, authorization is external)
# ---------------------------------------------------------------------------

@register("assistant.create")
def assistant_create(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Create a new assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant create <name> [--system-prompt ...] [--llm ...]")

    from lamb.services.assistant_service import AssistantService
    from lamb.lamb_classes import Assistant
    from creator_interface.assistant_router import sanitize_assistant_name_with_prefix

    svc = AssistantService()
    name = args[0]

    # Sanitize name with user prefix (same logic as creator interface)
    def check_exists(prefixed_name: str) -> bool:
        existing = svc.get_assistant_by_name(prefixed_name, ctx.user_email)
        return existing is not None

    sanitized_name, _, _ = sanitize_assistant_name_with_prefix(
        user_name=name,
        user_id=ctx.user_id,
        check_exists_fn=check_exists,
        max_length=50,
    )

    metadata: dict[str, Any] = {}
    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            metadata[key] = kwargs[key]
    metadata_json = json.dumps(metadata) if metadata else "{}"

    assistant_obj = Assistant(
        name=sanitized_name,
        description=kwargs.get("description", kwargs.get("d", "")),
        owner=ctx.user_email,
        api_callback=metadata_json,
        system_prompt=kwargs.get("system_prompt", ""),
        prompt_template=kwargs.get("prompt_template", ""),
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=int(kwargs.get("rag_top_k", 3)),
        RAG_collections=kwargs.get("rag_collections", ""),
        organization_id=ctx.organization_id,
    )

    assistant_id = svc.create_assistant(assistant_obj)
    if not assistant_id:
        raise ValueError(f"Failed to create assistant '{name}' — name may already exist")

    return {"assistant_id": assistant_id, "name": sanitized_name, "message": "Assistant created"}


@register("assistant.update")
def assistant_update(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Update an assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant update <id> [--name ...] [--system-prompt ...]")

    from lamb.services.assistant_service import AssistantService
    from lamb.lamb_classes import Assistant

    svc = AssistantService()
    assistant_id = int(args[0])

    current = svc.get_assistant_by_id(assistant_id)
    if not current:
        raise ValueError(f"Assistant {assistant_id} not found")
    if current.owner != ctx.user_email:
        raise ValueError(f"You don't own assistant {assistant_id}")

    # Build updated fields, merging with current
    name = kwargs.get("name", kwargs.get("n", current.name))
    system_prompt = kwargs.get("system_prompt", current.system_prompt)
    description = kwargs.get("description", kwargs.get("d", current.description or ""))
    prompt_template = kwargs.get("prompt_template", current.prompt_template or "")

    # Merge metadata
    existing_meta = {}
    if current.api_callback:
        try:
            existing_meta = json.loads(current.api_callback)
        except (json.JSONDecodeError, TypeError):
            pass
    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            existing_meta[key] = kwargs[key]
    metadata_json = json.dumps(existing_meta)

    updated_obj = Assistant(
        name=name,
        description=description,
        owner=current.owner,
        api_callback=metadata_json,
        system_prompt=system_prompt,
        prompt_template=prompt_template,
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=current.RAG_Top_k or 3,
        RAG_collections=current.RAG_collections or "",
        organization_id=ctx.organization_id,
    )

    success = svc.update_assistant(assistant_id, updated_obj)
    if not success:
        raise ValueError(f"Failed to update assistant {assistant_id}")

    return {"assistant_id": assistant_id, "message": "Assistant updated"}


@register("assistant.delete")
def assistant_delete(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Delete (soft-delete) an assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant delete <id>")

    from lamb.services.assistant_service import AssistantService

    svc = AssistantService()
    assistant_id = int(args[0])

    current = svc.get_assistant_by_id(assistant_id)
    if not current:
        raise ValueError(f"Assistant {assistant_id} not found")
    if current.owner != ctx.user_email:
        raise ValueError(f"You don't own assistant {assistant_id}")

    result = svc.soft_delete_assistant_by_id(assistant_id)
    return result


# ---------------------------------------------------------------------------
# Rubric READ commands
# ---------------------------------------------------------------------------

@register("rubric.list")
def rubric_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List your rubrics."""
    from lamb.evaluaitor import rubric_service
    result = rubric_service.list_rubrics_logic(
        user_email=ctx.user_email,
        organization_id=ctx.organization_id,
    )
    return result.get("rubrics", []) if isinstance(result, dict) else result


@register("rubric.list-public")
def rubric_list_public(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List public rubrics (templates)."""
    from lamb.evaluaitor import rubric_service
    result = rubric_service.list_public_rubrics_logic(
        organization_id=ctx.organization_id,
    )
    return result.get("rubrics", []) if isinstance(result, dict) else result


@register("rubric.get")
def rubric_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Get rubric details by UUID."""
    if not args:
        raise ValueError("Usage: lamb rubric get <rubric_id>")
    from lamb.evaluaitor import rubric_service
    result = rubric_service.get_rubric_logic(
        rubric_id=args[0],
        user_email=ctx.user_email,
    )
    if not result:
        raise ValueError(f"Rubric {args[0]} not found")
    return result


@register("rubric.export")
def rubric_export(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Export a rubric as JSON or markdown."""
    if not args:
        raise ValueError("Usage: lamb rubric export <rubric_id> [--format json|md]")
    from lamb.evaluaitor import rubric_service
    fmt = kwargs.get("format", kwargs.get("f", "json"))
    if fmt in ("md", "markdown"):
        content, filename = rubric_service.export_rubric_markdown_logic(
            rubric_id=args[0], user_email=ctx.user_email,
        )
        return content
    content, filename = rubric_service.export_rubric_json_logic(
        rubric_id=args[0], user_email=ctx.user_email,
    )
    return content


# ---------------------------------------------------------------------------
# Knowledge Base READ commands
# ---------------------------------------------------------------------------

@register("kb.list")
def kb_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List your knowledge bases."""
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    return db.get_owned_kbs(ctx.user_id, ctx.organization_id)


@register("kb.get")
def kb_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Get KB details by ID."""
    if not args:
        raise ValueError("Usage: lamb kb get <id>")
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    kb = db.get_kb_registry_entry(args[0])
    if not kb:
        raise ValueError(f"KB {args[0]} not found")
    can_access, _ = db.user_can_access_kb(args[0], ctx.user_id)
    if not can_access:
        raise ValueError(f"Access denied to KB {args[0]}")
    return kb


# ---------------------------------------------------------------------------
# Template READ commands
# ---------------------------------------------------------------------------

@register("template.list")
def template_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List your prompt templates."""
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    return db.get_user_prompt_templates(ctx.user_email, ctx.organization_id) or []


@register("template.get")
def template_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Get template details by ID."""
    if not args:
        raise ValueError("Usage: lamb template get <id>")
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    tpl = db.get_prompt_template_by_id(int(args[0]), ctx.user_email)
    if not tpl:
        raise ValueError(f"Template {args[0]} not found")
    return tpl


# ---------------------------------------------------------------------------
# Model READ commands
# ---------------------------------------------------------------------------

@register("model.list")
def model_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> list[dict]:
    """List available models for the user's organization."""
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    resolver = OrganizationConfigResolver(ctx.user_email)
    result = []
    org_config = resolver.organization.get("config", {})
    setups = org_config.get("setups", {}).get("default", {})
    providers = setups.get("providers", {})
    for provider_name, prov_config in providers.items():
        if prov_config.get("enabled", True):
            for model in prov_config.get("models", []):
                result.append({
                    "provider": provider_name,
                    "model": model,
                    "is_default": model == prov_config.get("default_model"),
                })
    return result


# ---------------------------------------------------------------------------
# Utility commands
# ---------------------------------------------------------------------------

@register("help")
def help_cmd(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict[str, str]:
    """Show available commands."""
    result = {}
    for key, func in sorted(COMMAND_REGISTRY.items()):
        doc = func.__doc__ or ""
        result[f"lamb {key.replace('.', ' ')}"] = doc.split("\n")[0].strip()
    return result
