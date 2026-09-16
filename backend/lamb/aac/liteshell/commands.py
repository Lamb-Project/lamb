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


async def _resolve_kb_ids(ctx: "CommandContext", collections: str) -> str:
    """Resolve KB names to numeric IDs. Numeric IDs pass through unchanged."""
    if not collections or not collections.strip():
        return collections

    items = [item.strip() for item in collections.split(",")]
    if all(item.isdigit() for item in items):
        return collections

    # Fetch KB list and build name→id map, falling back to pass-through on error
    try:
        kbs = _unwrap(await ctx.http.get("/creator/knowledgebases/user"))
        kbs = kbs if isinstance(kbs, list) else kbs.get("knowledge_bases", [])
    except Exception:
        return collections

    kb_map = {kb["name"].lower(): str(kb["id"]) for kb in kbs if kb.get("id") is not None and kb.get("name")}
    resolved = [kb_map.get(item.lower(), item) for item in items]
    return ",".join(resolved)


# ---------------------------------------------------------------------------
# Assistant commands (async HTTP → /creator/assistant/*)
# ---------------------------------------------------------------------------

def _list_params(kwargs, limit=50, **extra):
    params = {"limit": int(kwargs.get("limit", kwargs.get("l", limit))), "offset": int(kwargs.get("offset", 0)), **extra}
    if params['limit'] < 1 or params['offset'] < 0:
        raise ValueError("limit must be positive and offset nonnegative")
    for key, alias in (("search", "s"), ("subject", "subject")):
        if key in kwargs or alias in kwargs:
            params[key] = kwargs.get(key, kwargs.get(alias))
    return params


@register("assistant.list")
async def assistant_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List all assistants for the current user."""
    return _unwrap(await ctx.http.get("/creator/assistant/get_assistants", params=_list_params(kwargs)))


@register("assistant.list-shared")
async def assistant_list_shared(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List assistants shared with you by other users."""
    return _unwrap(await ctx.http.get("/creator/lamb/assistant-sharing/shared-with-me"))


@register("assistant.get")
async def assistant_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get assistant details by ID or name."""
    if not args:
        raise ValueError("Usage: lamb assistant get <id_or_name>")
    identifier = args[0]

    # If it's a number, get by ID
    if identifier.isdigit():
        return _unwrap(await ctx.http.get(f"/creator/assistant/get_assistant/{identifier}"))

    # Otherwise, search by name in owned + shared assistants
    owned = _unwrap(await ctx.http.get("/creator/assistant/get_assistants", params={"limit": 100}))
    assistants = owned.get("assistants", owned) if isinstance(owned, dict) else owned
    if isinstance(assistants, list):
        for a in assistants:
            name = a.get("name", "")
            # Match exact or without user prefix (e.g., "1_rock_the_60s" matches "rock_the_60s")
            bare_name = name.split("_", 1)[1] if "_" in name and name.split("_")[0].isdigit() else name
            if name == identifier or bare_name == identifier:
                aid = a.get("id") or a.get("assistant_id")
                return _unwrap(await ctx.http.get(f"/creator/assistant/get_assistant/{aid}"))

    # Try shared assistants too
    try:
        shared = _unwrap(await ctx.http.get("/creator/lamb/assistant-sharing/shared-with-me"))
        shared_list = shared if isinstance(shared, list) else shared.get("assistants", [])
        for a in shared_list:
            name = a.get("name", "")
            bare_name = name.split("_", 1)[1] if "_" in name and name.split("_")[0].isdigit() else name
            if name == identifier or bare_name == identifier:
                aid = a.get("id") or a.get("assistant_id")
                return _unwrap(await ctx.http.get(f"/creator/assistant/get_assistant/{aid}"))
    except Exception:
        pass

    raise ValueError(f"Assistant '{identifier}' not found by name. Use numeric ID or exact name.")


@register("assistant.config")
async def assistant_config(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Show available connectors, models, and processors."""
    capabilities = _unwrap(await ctx.http.get("/creator/assistant/capabilities"))
    raw = _unwrap(await ctx.http.get("/creator/assistant/defaults"))
    form_defaults = raw.get("config", raw)
    return {"capabilities": capabilities,
            "defaults": {**form_defaults, **capabilities.get("model_defaults", {"connector": "", "llm": ""})},
            "form_defaults": form_defaults,
            "global_default_model": capabilities.get("global_default_model", {}),
            "global_default_available": capabilities.get("global_default_available", False)}


@register("assistant.debug")
async def assistant_debug(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Inspect this input through prompt assembly without saving a test or chat."""
    if not args:
        raise ValueError("Usage: lamb assistant debug <id> --message \"text\"")
    assistant_id = args[0]
    message = kwargs.get("message", kwargs.get("m", ""))
    if not message:
        raise ValueError("Provide --message or -m with the test input")
    response = _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/chat/completions",
        json={"messages": [{"role": "user", "content": message}],
              "debug_bypass": True, "stream": False, "persist_chat": False},
    ))
    try:
        if response.get("model") != "debug-bypass":
            raise ValueError("not a bypass response")
        content = response["choices"][0]["message"]["content"]
        if not content.startswith("Messages:\n"):
            raise ValueError("missing assembled messages")
        messages, _ = json.JSONDecoder().raw_decode(content[len("Messages:\n"):])
        if not isinstance(messages, list) or not messages or not all(
            isinstance(m, dict) and "role" in m and "content" in m for m in messages
        ):
            raise ValueError("invalid assembled messages")
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("Debug inspection failed: no valid assembled input returned. "
                         "Do not claim retrieval was verified; no saved test was run.") from exc
    return {"evidence_type": "assistant_pipeline_debug", "assistant_id": assistant_id,
            "input_message": message, "assembled_messages": messages,
            "saved_test_run": False, "persisted_chat": False,
            "limitations": "Shows assembled input for this new invocation, not a trace of an earlier answer. "
                           "Bypasses the final answer model; preprocessing may still use models. "
                           "Does not evaluate answer quality or expose ranks/scores of omitted chunks."}



@register("assistant.create")
async def assistant_create(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Create a new assistant."""
    if not args:
        raise ValueError("Usage: lamb assistant create <name> [--system-prompt ...] [--llm ...]")
    name = args[0]
    if kwargs.get("rubric_id"):
        await ctx.http.get(f"/creator/rubrics/{kwargs['rubric_id']}")

    metadata: dict[str, Any] = {}
    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            metadata[key] = kwargs[key]

    _capabilities(metadata, kwargs)
    body: dict[str, Any] = {"name": name}
    if kwargs.get("system_prompt"):
        body["system_prompt"] = kwargs["system_prompt"]
    if kwargs.get("description") or kwargs.get("d"):
        body["description"] = kwargs.get("description", kwargs.get("d", ""))
    if "prompt_template" in kwargs:
        body["prompt_template"] = kwargs["prompt_template"]
    if kwargs.get("rag_top_k"):
        body["RAG_Top_k"] = int(kwargs["rag_top_k"])
    if kwargs.get("rag_collections"):
        body["RAG_collections"] = await _resolve_kb_ids(ctx, kwargs["rag_collections"])
    if metadata:
        body["metadata"] = json.dumps(metadata)

    return _unwrap(await ctx.http.post("/creator/assistant/create_assistant", json=body))


@register("assistant.update")
async def assistant_update(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Update an assistant. Fetches current state and merges your changes."""
    if not args:
        raise ValueError("Usage: lamb assistant update <id> [--name ...] [--system-prompt ...]")
    assistant_id = args[0]
    if kwargs.get("rubric_id"):
        await ctx.http.get(f"/creator/rubrics/{kwargs['rubric_id']}")

    # Fetch current assistant to merge with
    current = _unwrap(await ctx.http.get(f"/creator/assistant/get_assistant/{assistant_id}"))
    if not current or not isinstance(current, dict):
        raise ValueError(f"Assistant {assistant_id} not found")

    # Build body from current + overrides
    body: dict[str, Any] = {
        "name": current.get("name", ""),
        "description": current.get("description", ""),
        "system_prompt": current.get("system_prompt", ""),
        "prompt_template": current.get("prompt_template", ""),
        "RAG_Top_k": current.get("RAG_Top_k", 3),
        "RAG_collections": current.get("RAG_collections", ""),
    }

    # Apply overrides from kwargs
    if "name" in kwargs or "n" in kwargs:
        body["name"] = kwargs.get("name", kwargs.get("n"))
    if "system_prompt" in kwargs:
        body["system_prompt"] = kwargs["system_prompt"]
    if "description" in kwargs or "d" in kwargs:
        body["description"] = kwargs.get("description", kwargs.get("d"))
    if "prompt_template" in kwargs:
        body["prompt_template"] = kwargs["prompt_template"]
    if "rag_top_k" in kwargs:
        body["RAG_Top_k"] = int(kwargs["rag_top_k"])
    if "rag_collections" in kwargs:
        body["RAG_collections"] = await _resolve_kb_ids(ctx, kwargs["rag_collections"])

    # Merge metadata: start from current, overlay changes
    existing_meta = {}
    raw_meta = current.get("metadata") or current.get("api_callback") or "{}"
    if isinstance(raw_meta, str):
        try:
            existing_meta = json.loads(raw_meta)
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(raw_meta, dict):
        existing_meta = raw_meta

    for key in ("llm", "connector", "prompt_processor", "rag_processor",
                "rubric_id", "rubric_format"):
        if key in kwargs:
            existing_meta[key] = kwargs[key]
    _capabilities(existing_meta, kwargs)
    body["metadata"] = json.dumps(existing_meta)

    return _unwrap(await ctx.http.put(f"/creator/assistant/update_assistant/{assistant_id}", json=body))


async def _publish_assistant(ctx, args, published):
    data = _unwrap(await ctx.http.put(f"/creator/assistant/publish/{args[0]}", json={"publish_status": published}))
    if isinstance(data, dict) and data.get("success") is False:
        raise ValueError(data.get("error", "Publication failed"))
    return {"id": args[0], "published": published, "response": data}


@register("assistant.publish")
async def assistant_publish(ctx, args, kwargs):
    """Publish an owned assistant in LAMB; does not configure an external LMS."""
    return await _publish_assistant(ctx, args, True)


@register("assistant.unpublish")
async def assistant_unpublish(ctx, args, kwargs):
    """Unpublish an owned assistant in LAMB."""
    return await _publish_assistant(ctx, args, False)


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
    result = _unwrap(await ctx.http.get("/creator/rubrics", params=_list_params(kwargs, tab="my")))
    if isinstance(result, dict) and "rubrics" in result:
        return result["rubrics"]
    return result


@register("rubric.list-public")
async def rubric_list_public(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List public rubrics (templates)."""
    result = _unwrap(await ctx.http.get("/creator/rubrics", params=_list_params(kwargs, tab="templates")))
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
    return _unwrap(await ctx.http.get("/creator/prompt-templates/list", params=_list_params(kwargs)))


@register("template.get")
async def template_get(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Get template details by ID."""
    if not args:
        raise ValueError("Usage: lamb template get <id>")
    return _unwrap(await ctx.http.get(f"/creator/prompt-templates/{args[0]}"))


# ---------------------------------------------------------------------------
# Model commands (async HTTP → /creator/models)
# ---------------------------------------------------------------------------

@register("assistant.list-published")
async def assistant_list_published(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List published assistants (registered as LTI models)."""
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
    if not message and "messages" not in kwargs:
        raise ValueError("Provide --message or --messages with the test input")
    return _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/tests/scenarios",
        json={
            "title": title,
            "messages": _messages(kwargs),
            "description": kwargs.get("description", kwargs.get("d", "")),
            "scenario_type": kwargs.get("type", kwargs.get("t", "single_turn")),
            "expected_behavior": kwargs.get("expected", kwargs.get("e", "")),
        },
    ))


@register("test.update")
async def test_update(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Patch explicitly supplied scenario fields; keep scenario identity and history."""
    body = {}
    for field, names in {"title":("title",), "description":("description","d"),
                         "expected_behavior":("expected","e"), "scenario_type":("type","t")}.items():
        for name in names:
            if name in kwargs:
                body[field] = kwargs[name]
                break
    if "message" in kwargs or "m" in kwargs:
        body["messages"] = [{"role":"user","content":kwargs.get("message",kwargs.get("m"))}]
    if not body:
        raise ValueError("Provide at least one field to update")
    return _unwrap(await ctx.http.put(
        f"/creator/assistant/{args[0]}/tests/scenarios/{args[1]}", json=body))


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
    import asyncio
    try:
        return _unwrap(await asyncio.wait_for(ctx.http.post(f"/creator/assistant/{assistant_id}/tests/run", json=body), float(kwargs.get('timeout', 900))))
    except asyncio.TimeoutError as exc:
        raise ValueError('Test batch timed out; inspect saved test runs before retrying. Some runs may already have completed.') from exc


@register("test.runs")
async def test_runs(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List test runs for an assistant."""
    if not args:
        raise ValueError("Usage: lamb test runs <assistant_id>")
    return _unwrap(await ctx.http.get(f"/creator/assistant/{args[0]}/tests/runs", params={"limit": _list_params(kwargs, limit=20)["limit"]}))


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
        raise ValueError("Usage: lamb test evaluate <run_id> <assistant_id> <verdict: good|bad|mixed>")
    run_id = args[0]
    # Canonical CLI order is RUN_ID ASSISTANT_ID VERDICT. Retain the old
    # AAC order for already-saved recipes and conversations.
    canonical = len(args) == 3 and args[2] in ("good", "bad", "mixed")
    verdict = args[2] if canonical else args[1]
    if verdict not in ("good", "bad", "mixed"):
        raise ValueError("Verdict must be 'good', 'bad', or 'mixed'")
    assistant_id = args[1] if canonical else (args[2] if len(args) > 2 else kwargs.get("assistant", kwargs.get("a", "")))
    if not assistant_id:
        raise ValueError("Usage: lamb test evaluate <run_id> <assistant_id> <verdict>")
    return _unwrap(await ctx.http.post(
        f"/creator/assistant/{assistant_id}/tests/runs/{run_id}/evaluate",
        json={
            "verdict": verdict,
            "notes": kwargs.get("notes", kwargs.get("n", "")),
        },
    ))


# ---------------------------------------------------------------------------
# Chat command (async HTTP — direct inference on an assistant)
# ---------------------------------------------------------------------------

@register("assistant.chat")
async def assistant_chat(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Send a message to an assistant and get a real response. Usage: lamb assistant chat <id> --message "text"."""
    if not args:
        raise ValueError("Usage: lamb assistant chat <assistant_id> --message \"text\"")
    assistant_id = args[0]
    message = kwargs.get("message", kwargs.get("m", ""))
    if not message:
        raise ValueError("Provide --message or -m with the text to send")

    body: dict[str, Any] = {
        "messages": [{"role": "user", "content": message}],
        "stream": False,
        "persist_chat": kwargs.get("persist") in (True, "true"),
    }
    if kwargs.get("chat_id"):
        body["chat_id"] = kwargs["chat_id"]
    bypass = kwargs.get("bypass", kwargs.get("b", False))
    if bypass is True or bypass == "true":
        body["debug_bypass"] = True

    result = await ctx.http.post(
        f"/creator/assistant/{assistant_id}/chat/completions",
        json=body,
    )
    # Extract the response text from the completions format
    if isinstance(result, dict):
        choices = result.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return {"response": content, "model": result.get("model", ""), "usage": result.get("usage", {}), "chat_id": result.get("chat_id")}
    return result


# ---------------------------------------------------------------------------
# Session commands (async HTTP)
# ---------------------------------------------------------------------------

@register("session.rename")
async def session_rename(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """Rename the current session. The agent should do this when it learns the user's intent or target assistant name."""
    if not args:
        raise ValueError("Usage: lamb session rename \"New title\"")
    # Agent calls this INSIDE a session — it needs to know the current session id.
    # We pass the session id via kwargs since the liteshell doesn't know about the AAC session.
    session_id = kwargs.get("session", kwargs.get("s", ""))
    if not session_id:
        # Fallback: the AgentLoop will inject the current session_id before executing
        raise ValueError("session.rename requires --session <id> (injected by agent loop)")
    title = " ".join(args).strip()
    if not title:
        raise ValueError("Title cannot be empty")
    return await ctx.http.put(
        f"/creator/aac/sessions/{session_id}/title",
        json={"title": title},
    )


# ---------------------------------------------------------------------------
# Skill commands (LOCAL — sync, read files, no HTTP)
# ---------------------------------------------------------------------------

@register("skill.list", local=True)
def skill_list(ctx: "CommandContext", args: list[str], kwargs: dict) -> Any:
    """List available AAC skills with descriptions and requirements."""
    from lamb.aac.skill_loader import list_skills
    pack = ctx.knowledge.get('pack')
    if not pack:
        return list_skills()
    from lamb.aac.pack_loader import allowed_skills
    allowed = allowed_skills(pack, ctx.knowledge['brief']['layers'])
    return [s for s in list_skills(pack.skills_dir) if s['id'] in allowed]


@register("skill.load", local=True)
def skill_load(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Load a skill into the current session. The skill prompt and startup data are returned for injection."""
    if not args:
        raise ValueError("Usage: lamb skill load <skill-id> [--assistant <id>] [--language <lang>]")
    from lamb.aac.skill_loader import load_skill

    skill_id = args[0]
    context: dict[str, Any] = {}
    if "assistant" in kwargs or "a" in kwargs:
        context["assistant_id"] = kwargs.get("assistant", kwargs.get("a"))
    if "language" in kwargs:
        context["language"] = kwargs["language"]

    pack = ctx.knowledge.get('pack')
    if pack:
        from lamb.aac.pack_loader import allowed_skills
        if skill_id not in allowed_skills(pack, ctx.knowledge['brief']['layers']):
            raise ValueError('This workflow is outside your role; ask the appropriate administrator')
    skill = load_skill(skill_id, context, pack.skills_dir if pack else None)
    return {
        "skill_id": skill_id,
        "name": skill["metadata"].get("name", skill_id),
        "prompt": skill["prompt"],
    }


# ---------------------------------------------------------------------------
# Documentation commands (LOCAL — sync, read files, no HTTP)
# ---------------------------------------------------------------------------

@register("docs.index", local=True)
def docs_index(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """List documentation topics, language-neutral anchors and locale coverage."""
    from lamb.aac.documentation import manifest
    data = manifest()
    language = ctx.knowledge.get('brief', {}).get('session_language', 'en')
    return {'version':data['version'], 'topics':list(data['topics']), 'sections':data['topics'],
            'language':language, 'coverage':data['coverage'][language]}


@register("docs.read", local=True)
def docs_read(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Read a documentation topic, optionally --section ANCHOR_ID, in the session language."""
    from lamb.aac.documentation import read_topic
    language = ctx.knowledge.get('brief', {}).get('session_language', 'en')
    result = read_topic(args[0], language, kwargs.get('section'))
    # Keep proof of an actual missing section for the translation escape hatch.
    if result['fallback_sections'] and ctx.knowledge.get('state') is not None:
        ctx.knowledge['state']['documentation_fallback'] = {
            'topic':args[0], 'sections':result['fallback_sections'], 'language':language}
        ctx.knowledge['state'].setdefault('documentation_notices', {})[args[0]] = result['fallback_sections']
    return result


@register("glossary", local=True)
def glossary_lookup(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Look up a domain term in the pinned session glossary: lamb glossary TERM."""
    from lamb.aac.glossary import lookup
    glossary = ctx.knowledge.get('brief', {}).get('glossary', {})
    entries = lookup(glossary, args[0])
    return {'term':args[0], 'entries':entries, 'language':glossary.get('language','en'),
            'source':'pinned_pack_glossary', 'machine_translation':False}


@register("translate")
async def translate_text(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict:
    """Translate an unknown blocking term or missing documentation section through the configured utility model."""
    from lamb.aac.translation import translate
    return await translate(ctx.knowledge, ctx.user_email, args[0] if args else '', kwargs)


# Existing CLI analytics vocabulary; the API remains the authorization boundary.
def _analytics_params(kwargs, defaults=None):
    params = dict(defaults or {})
    for key in ("page", "per_page", "user_id", "start_date", "end_date", "period"):
        if key in kwargs:
            params[key] = kwargs[key]
    if "search" in kwargs:
        params["search_content"] = kwargs["search"]
    for key in ("page", "per_page"):
        if key in params:
            params[key] = int(params[key])
            if params[key] < 1:
                raise ValueError(f"{key} must be positive")
    if "period" in params and params["period"] not in {"day", "week", "month"}:
        raise ValueError("period must be day, week or month")
    return params


@register("analytics.chats")
async def analytics_chats(ctx, args, kwargs):
    """List assistant chats with CLI-compatible filters."""
    data = await ctx.http.get(f"/creator/analytics/assistant/{args[0]}/chats",
                             params=_analytics_params(kwargs, {"page": 1, "per_page": 20}))
    return data.get("chats", [])


@register("analytics.chat-detail")
async def analytics_chat_detail(ctx, args, kwargs):
    """Get an authorized assistant chat and its messages."""
    from urllib.parse import quote
    return await ctx.http.get(f"/creator/analytics/assistant/{args[0]}/chats/{quote(args[1], safe='')}")


@register("analytics.stats")
async def analytics_stats(ctx, args, kwargs):
    """Get assistant chat statistics."""
    return await ctx.http.get(f"/creator/analytics/assistant/{args[0]}/stats",
                             params=_analytics_params(kwargs))


@register("analytics.timeline")
async def analytics_timeline(ctx, args, kwargs):
    """Get assistant activity by day, week or month."""
    return await ctx.http.get(f"/creator/analytics/assistant/{args[0]}/timeline",
                             params=_analytics_params(kwargs, {"period": "day"}))


# ---------------------------------------------------------------------------
# Utility commands (LOCAL — sync)
# ---------------------------------------------------------------------------

@register("help", local=True)
def help_cmd(ctx: "CommandContext", args: list[str], kwargs: dict) -> dict[str, str]:
    """Show available commands."""
    result = {}
    pack = ctx.knowledge.get('pack')
    allowed = None
    if pack:
        from lamb.aac.pack_loader import allowed_commands
        allowed = allowed_commands(pack, ctx.knowledge['brief']['layers'])
    for key, func in sorted(COMMAND_REGISTRY.items()):
        if allowed is not None and key not in allowed:
            continue
        doc = func.__doc__ or ""
        result[f"lamb {key.replace('.', ' ')}"] = doc.split("\n")[0].strip()
    return result


@register("kb.create")
async def kb_create(ctx, args, kwargs):
    """Create a knowledge base: kb create NAME [--description TEXT]."""
    return _unwrap(await ctx.http.post('/creator/knowledgebases', json={
        'name': args[0], 'description': kwargs.get('description', kwargs.get('d', '')), **_fields(kwargs, ('access_control',))}))


@register("kb.query")
async def kb_query(ctx, args, kwargs):
    """Query actual KB content: kb query KB_ID TEXT [--top-k N] [--threshold N] [--plugin NAME]."""
    body = {'query_text': args[1]}
    params = {}
    top = kwargs.get('top_k', kwargs.get('k'))
    if top is not None:
        top = int(top)
        if top < 1: raise ValueError('top-k must be positive')
        params['top_k'] = top
    threshold = kwargs.get('threshold', kwargs.get('t'))
    if threshold is not None:
        import math
        threshold = float(threshold)
        if not math.isfinite(threshold): raise ValueError('threshold must be finite')
        params['threshold'] = threshold
    if params: body['plugin_params'] = params
    if kwargs.get('plugin', kwargs.get('p')): body['plugin_name'] = kwargs.get('plugin', kwargs.get('p'))
    result = _unwrap(await ctx.http.post(f'/creator/knowledgebases/kb/{args[0]}/query', json=body))
    evidence = {"type": "direct_kb_query", "query": body,
                "limitations": "Separate KB probe, not proof of an assistant's injected context. "
                               "Only returned chunks have observed ranks/scores. Absence does not establish "
                               "an omitted chunk's score, language-related cause, or that a larger top-k fixes it."}
    return {**result, "evidence": evidence} if isinstance(result, dict) else {"result": result, "evidence": evidence}


@register("test.evaluations")
async def test_evaluations(ctx, args, kwargs):
    """Read stored evaluations before reporting test outcomes: test evaluations ASSISTANT_ID."""
    return _unwrap(await ctx.http.get(f'/creator/assistant/{args[0]}/tests/evaluations'))


def _apply_weights(criteria, value):
    """Change named weights without asking an agent to reproduce criteria/level IDs."""
    import copy
    import math
    weights = json.loads(value)
    if not isinstance(weights, dict) or not weights:
        raise ValueError('weights must be a nonempty JSON object of exact criterion names and percentages')
    result = copy.deepcopy(criteria)
    for name, weight in weights.items():
        matches = [c for c in result if c.get('name') == name]
        if len(matches) != 1:
            raise ValueError(f'Criterion name must match exactly one existing criterion: {name}')
        if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 100:
            raise ValueError('Weights must be finite numbers between 0 and 100')
        matches[0]['weight'] = weight
    all_weights = [c.get('weight', 0) for c in result]
    if any(type(w) not in (int, float) or not math.isfinite(w) or not 0 <= w <= 100 for w in all_weights):
        raise ValueError('Every resulting weight must be a finite percentage')
    original_total = sum(c.get('weight', 0) for c in criteria)
    incremental_repair = len(weights) == 1 and len(criteria) > 1 and not math.isclose(original_total, 100, abs_tol=0.000001)
    if not incremental_repair and not math.isclose(sum(all_weights), 100, abs_tol=0.000001):
        raise ValueError('Resulting criterion weights must total 100; provide all changed weights together')
    return result


def _rubric_form(current, changes):
    current = current.get('rubric', current)
    raw = current.get('rubric_data', current)
    raw = json.loads(raw) if isinstance(raw, str) else raw
    metadata = raw.get('metadata', {})
    form = {'title': raw.get('title', current.get('title', '')),
            'description': raw.get('description', ''), 'subject': metadata.get('subject', ''),
            'gradeLevel': metadata.get('gradeLevel', ''), 'scoringType': raw.get('scoringType', 'points'),
            'maxScore': raw.get('maxScore', 10), 'criteria': raw.get('criteria', [])}
    mapping = {'grade_level':'gradeLevel', 'scoring_type':'scoringType', 'max_score':'maxScore'}
    for key, value in changes.items():
        if key not in {'o', 'output', 'weights'}: form[mapping.get(key, key)] = value
    criteria = form['criteria']
    if isinstance(criteria, str): criteria = json.loads(criteria)
    if not isinstance(criteria, list) or not criteria or not all(isinstance(c, dict) for c in criteria):
        raise ValueError('criteria must be a nonempty JSON array of criterion objects')
    if 'weights' in changes:
        if 'criteria' in changes: raise ValueError('Use either --weights or --criteria, not both')
        criteria = _apply_weights(criteria, changes['weights'])
    if not form['title'].strip(): raise ValueError('Rubric title is required')
    form['criteria'] = json.dumps(criteria, ensure_ascii=False)
    return form


@register("rubric.create")
async def rubric_create(ctx, args, kwargs):
    """Create rubric: rubric create TITLE --criteria JSON [--description TEXT] [--max-score N]. Server validates criteria/levels/weights."""
    return await ctx.http.post('/creator/rubrics', data=_rubric_form({}, {**kwargs, 'title':args[0]}))


@register("rubric.update")
async def rubric_update(ctx, args, kwargs):
    """Edit rubric: rubric update ID [--title TEXT] [--criteria JSON]. Unspecified fields and criteria are preserved."""
    if not set(kwargs) - {'o', 'output'}: raise ValueError('Provide at least one rubric field to update')
    current = await ctx.http.get(f'/creator/rubrics/{args[0]}')
    return await ctx.http.put(f'/creator/rubrics/{args[0]}', data=_rubric_form(current, kwargs))


@register("kb.jobs")
async def kb_jobs(ctx, args, kwargs):
    """List ingestion jobs, terminal status and errors: kb jobs KB_ID."""
    return await ctx.http.get(f'/creator/knowledgebases/kb/{args[0]}/ingestion-jobs')


@register("kb.status")
async def kb_status(ctx, args, kwargs):
    """Inspect ingestion status and failures: kb status KB_ID."""
    return await ctx.http.get(f'/creator/knowledgebases/kb/{args[0]}/ingestion-status')


@register("frontend-manage.current")
async def frontend_current(ctx, args, kwargs):
    """Read the connected browser's current workspace; unavailable without a frontend turn."""
    if ctx.frontend is None:
        raise ValueError('No connected frontend for this turn. Guide the user; do not claim navigation.')
    return await ctx.frontend({'operation': 'current'})


@register("frontend-manage.open")
async def frontend_open(ctx, args, kwargs):
    """Open assistants, assistant-create, assistant ID --tab properties|tests|chat|activity|edit, kb ID --tab files|ingest|query, or rubric UUID. Waits for the browser."""
    from lamb.aac.frontend import destination
    target = destination(args, kwargs)
    if ctx.frontend is None:
        raise ValueError('No connected frontend for this turn. Guide the user; do not claim navigation.')
    paths = {'assistant': '/creator/assistant/get_assistant/', 'kb': '/creator/knowledgebases/kb/', 'rubric': '/creator/rubrics/'}
    if target['resource'] in paths:
        await ctx.http.get(paths[target['resource']] + target['id'])  # normal caller resource permissions, before emitting an action
    return await ctx.frontend({'operation': 'open', **target})


# Educator operations use the same authenticated Creator endpoints as lamb-cli.
def _fields(kwargs, names):
    return {name: kwargs[name] for name in names if name in kwargs}


def _switch(kwargs):
    if ('enable' in kwargs) == ('disable' in kwargs):
        raise ValueError('Specify exactly one of --enable or --disable')
    return ('enable' in kwargs) == (kwargs.get('enable', kwargs.get('disable')) not in (False, 'false'))


def _capabilities(metadata, kwargs):
    values = dict(metadata.get('capabilities') or {})
    for name in ('vision', 'image_generation'):
        if name in kwargs or 'no_' + name in kwargs:
            values[name] = name in kwargs and kwargs[name] not in (False, 'false')
    if values:
        metadata['capabilities'] = values


def _messages(kwargs):
    if 'messages' in kwargs:
        if 'message' in kwargs or 'm' in kwargs:
            raise ValueError('Use either --messages JSON or --message TEXT')
        messages = json.loads(kwargs['messages'])
        if not isinstance(messages, list) or not messages or not all(
            isinstance(m, dict) and m.get('role') in {'user', 'assistant', 'system'}
            and isinstance(m.get('content'), str) and m['content'].strip() for m in messages):
            raise ValueError('messages must be a nonempty JSON array of role/content messages')
        return messages
    message = kwargs.get('message', kwargs.get('m', ''))
    if not message:
        raise ValueError('Provide --message TEXT or --messages JSON')
    return [{'role': 'user', 'content': message}]


@register("whoami")
async def whoami(ctx, args, kwargs):
    """Show the authenticated user and permissions."""
    return _unwrap(await ctx.http.get('/creator/user/current'))


@register("assistant.export")
async def assistant_export(ctx, args, kwargs):
    """Export assistant configuration as JSON: assistant export ID."""
    return _unwrap(await ctx.http.get(f'/creator/assistant/export/{args[0]}'))


@register("kb.list-shared")
async def kb_list_shared(ctx, args, kwargs):
    """List shared knowledge bases."""
    return _unwrap(await ctx.http.get('/creator/knowledgebases/shared'))


@register("kb.plugins")
async def kb_plugins(ctx, args, kwargs):
    """List ingestion plugins before selecting a non-file ingestion workflow."""
    return _unwrap(await ctx.http.get('/creator/knowledgebases/ingestion-plugins'))


@register("kb.query-plugins")
async def kb_query_plugins(ctx, args, kwargs):
    """List available query plugins."""
    return _unwrap(await ctx.http.get('/creator/knowledgebases/query-plugins'))


@register("job.get")
async def job_get(ctx, args, kwargs):
    """Read an ingestion job: job get KB_ID JOB_ID."""
    return _unwrap(await ctx.http.get(f'/creator/knowledgebases/kb/{args[0]}/ingestion-jobs/{args[1]}'))


@register("test.scenario-detail")
async def test_scenario_detail(ctx, args, kwargs):
    """Read a saved scenario: test scenario-detail SCENARIO_ID ASSISTANT_ID."""
    return _unwrap(await ctx.http.get(f'/creator/assistant/{args[1]}/tests/scenarios/{args[0]}'))


@register("kb.delete")
async def kb_delete(ctx, args, kwargs):
    """Delete a knowledge base: kb delete KB_ID."""
    return _unwrap(await ctx.http.delete(f'/creator/knowledgebases/kb/{args[0]}'))


@register("kb.delete-file")
async def kb_delete_file(ctx, args, kwargs):
    """Delete an ingested KB file by ID: kb delete-file KB_ID FILE_ID."""
    return _unwrap(await ctx.http.delete(f'/creator/knowledgebases/kb/{args[0]}/files/{args[1]}'))


@register("rubric.delete")
async def rubric_delete(ctx, args, kwargs):
    """Delete a rubric: rubric delete ID."""
    return _unwrap(await ctx.http.delete(f'/creator/rubrics/{args[0]}'))


@register("template.delete")
async def template_delete(ctx, args, kwargs):
    """Delete a prompt template: template delete ID."""
    return _unwrap(await ctx.http.delete(f'/creator/prompt-templates/{args[0]}'))


@register("test.delete-scenario")
async def test_delete_scenario(ctx, args, kwargs):
    """Delete a saved scenario: test delete-scenario SCENARIO_ID ASSISTANT_ID."""
    return _unwrap(await ctx.http.delete(f'/creator/assistant/{args[1]}/tests/scenarios/{args[0]}'))


@register("job.retry")
async def job_retry(ctx, args, kwargs):
    """Retry an ingestion job: job retry KB_ID JOB_ID."""
    return _unwrap(await ctx.http.post(f'/creator/knowledgebases/kb/{args[0]}/ingestion-jobs/{args[1]}/retry'))


@register("job.cancel")
async def job_cancel(ctx, args, kwargs):
    """Cancel an ingestion job: job cancel KB_ID JOB_ID."""
    return _unwrap(await ctx.http.post(f'/creator/knowledgebases/kb/{args[0]}/ingestion-jobs/{args[1]}/cancel'))


@register("kb.update")
async def kb_update(ctx, args, kwargs):
    """Update selected KB fields: kb update ID --name TEXT --description TEXT --access-control private|public."""
    body = _fields(kwargs, ('name', 'description', 'access_control'))
    if not body: raise ValueError('Provide at least one field to update')
    return _unwrap(await ctx.http.patch(f'/creator/knowledgebases/kb/{args[0]}', json=body))


@register("kb.share")
async def kb_share(ctx, args, kwargs):
    """Change organization sharing: kb share ID --enable|--disable."""
    return _unwrap(await ctx.http.put(f'/creator/knowledgebases/kb/{args[0]}/share', json={'is_shared': _switch(kwargs)}))


@register("template.share")
async def template_share(ctx, args, kwargs):
    """Change organization sharing: template share ID --enable|--disable."""
    return _unwrap(await ctx.http.put(f'/creator/prompt-templates/{args[0]}/share', json={'is_shared': _switch(kwargs)}))


@register("rubric.share")
async def rubric_share(ctx, args, kwargs):
    """Change rubric public visibility: rubric share ID --enable|--disable."""
    return _unwrap(await ctx.http.put(f'/creator/rubrics/{args[0]}/visibility', data={'is_public': str(_switch(kwargs)).lower()}))


@register("rubric.duplicate")
async def rubric_duplicate(ctx, args, kwargs):
    """Duplicate an accessible rubric: rubric duplicate ID."""
    return _unwrap(await ctx.http.post(f'/creator/rubrics/{args[0]}/duplicate'))


@register("rubric.generate")
async def rubric_generate(ctx, args, kwargs):
    """Generate an unsaved rubric preview: rubric generate PROMPT --language en|es|ca|eu [--model NAME]."""
    body = {'prompt': args[0], 'language': kwargs.get('language', kwargs.get('lang', 'en'))}
    if body['language'] not in {'en', 'es', 'ca', 'eu'}: raise ValueError('Unsupported language')
    if kwargs.get('model', kwargs.get('m')): body['model'] = kwargs.get('model', kwargs.get('m'))
    data = _unwrap(await ctx.http.post('/creator/rubrics/ai-generate', json=body))
    if not isinstance(data, dict) or not data.get('success'): raise ValueError(data.get('error', 'Rubric generation failed') if isinstance(data, dict) else 'Invalid generation response')
    return data.get('rubric', {})


@register("template.list-shared")
async def template_list_shared(ctx, args, kwargs):
    """List shared prompt templates."""
    return _unwrap(await ctx.http.get('/creator/prompt-templates/shared', params=_list_params(kwargs)))


@register("template.create")
async def template_create(ctx, args, kwargs):
    """Create a prompt template: template create NAME [--description TEXT] [--system-prompt TEXT] [--prompt-template TEXT] [--shared]."""
    body = {'name': args[0], 'is_shared': kwargs.get('shared', False) not in (False, 'false')}
    body.update(_fields(kwargs, ('description', 'system_prompt', 'prompt_template')))
    return _unwrap(await ctx.http.post('/creator/prompt-templates/create', json=body))


@register("template.update")
async def template_update(ctx, args, kwargs):
    """Edit selected template fields: template update ID --name TEXT --description TEXT --system-prompt TEXT --prompt-template TEXT."""
    body = _fields(kwargs, ('name', 'description', 'system_prompt', 'prompt_template'))
    if not body: raise ValueError('Provide at least one field to update')
    return _unwrap(await ctx.http.put(f'/creator/prompt-templates/{args[0]}', json=body))


@register("template.duplicate")
async def template_duplicate(ctx, args, kwargs):
    """Duplicate a template: template duplicate ID [--new-name NAME]."""
    body = _fields(kwargs, ('new_name',))
    return _unwrap(await ctx.http.post(f'/creator/prompt-templates/{args[0]}/duplicate', json=body))


@register("template.export")
async def template_export(ctx, args, kwargs):
    """Return template JSON without writing a file: template export ID [ID ...]."""
    return _unwrap(await ctx.http.post('/creator/prompt-templates/export', json={'template_ids': [int(x) for x in args]}))


@register("kb.ingest")
async def kb_ingest(ctx, args, kwargs):
    """Run non-file ingestion: kb ingest KB_ID --plugin NAME [--url URL] [--youtube URL] [--param key=value ...]."""
    params = {}
    if kwargs.get('url'): params['url'] = kwargs['url']
    if kwargs.get('youtube'): params['video_url'] = kwargs['youtube']
    for value in kwargs.get('param', []):
        if '=' not in value: raise ValueError('Use --param key=value')
        key, value = value.split('=', 1)
        params[key] = value
    body = {'plugin_name': kwargs.get('plugin', kwargs.get('p'))}
    if not body['plugin_name']: raise ValueError('Provide --plugin NAME')
    catalogue = _unwrap(await ctx.http.get('/creator/knowledgebases/ingestion-plugins'))
    plugins = catalogue if isinstance(catalogue, list) else catalogue.get('plugins', [])
    selected = next((plugin for plugin in plugins if plugin.get('name') == body['plugin_name']), None)
    if not selected: raise ValueError('Ingestion plugin is not available; inspect lamb kb plugins')
    if selected.get('kind') not in {'base-ingest', 'remote-ingest'}:
        from lamb.aac.liteshell.shell import FILESYSTEM_MESSAGE
        raise ValueError(FILESYSTEM_MESSAGE)
    if params: body['parameters'] = params
    return _unwrap(await ctx.http.post(f'/creator/knowledgebases/kb/{args[0]}/plugin-ingest-base', json=body))
