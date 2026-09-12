"""AAC API router — /creator/aac/ endpoints.

Provides session management and agent interaction for the
Agent-Assisted Creator.
"""

from __future__ import annotations

import json
import anyio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from lamb.auth_context import AuthContext, get_auth_context
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.aac.authorization import ActionAuthorizer
from lamb.aac.session_manager import AACSessionManager
from lamb.aac.session_logger import SessionLogger
from lamb.aac.skill_loader import load_skill, list_skills
from lamb.aac.liteshell.shell import LiteShell
from lamb.aac.agent.loop import AgentLoop
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

router = APIRouter(prefix="/aac", tags=["AAC"])

SKILLS_DIR = Path(__file__).parent / "skills"

# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------


@router.post("/files")
async def attach_file(file: UploadFile = File(...), auth: AuthContext = Depends(get_auth_context)):
    """Stage an actual user-selected file and return an owned reference for AAC tools."""
    from uuid import uuid4
    from lamb.aac.files import ROOT, MAX_BYTES
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".json", ".pdf"}:
        raise HTTPException(400, "Supported attachment types: txt, md, json, pdf")
    content = await file.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(413, "Attachment must be nonempty and at most 10 MiB")
    if suffix != ".pdf":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Text attachments must be UTF-8")
    folder = ROOT / str(auth.user["id"])
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise HTTPException(400, "Invalid upload directory")
    path = folder / ("aac_" + uuid4().hex + suffix)
    path.write_bytes(content)
    return {"path": str(path.relative_to(ROOT)), "name": Path(file.filename).name, "size": len(content)}


@router.get("/files/validate")
async def validate_file(reference: str, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.files import owned_file
    try:
        path = owned_file(reference, auth.user["id"])
        if path.suffix.lower() not in {".txt", ".md", ".json"}:
            raise ValueError("Single-file RAG requires a UTF-8 text file; ingest PDFs into a KB")
        path.read_text(encoding="utf-8")
    except (ValueError, UnicodeError) as e:
        raise HTTPException(400, str(e))
    return {"path": reference, "valid": True}


@router.post("/sessions")
async def create_session(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Start a new AAC design session.

    Body (optional):
        {
            "assistant_id": 4,                          # existing assistant to work on
            "skill": "improve-assistant",               # skill to launch
            "context": {"language": "Catalan", ...}     # extra context for the skill
        }

    If a skill is provided, the agent runs its startup sequence and the
    response includes the agent's first message. The user doesn't need
    to send a message first — the agent leads.
    """
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    assistant_id = body.get("assistant_id")
    skill_id = body.get("skill")
    skill_context = body.get("context", {})

    # If skill provides assistant_id in context, use it
    if "assistant_id" in skill_context and not assistant_id:
        assistant_id = skill_context["assistant_id"]
    # And vice versa
    if assistant_id and "assistant_id" not in skill_context:
        skill_context["assistant_id"] = assistant_id

    # Generate session title — friendly format: "<SkillVerb>: <assistant_name>"
    title = ""
    _skill_titles = {
        "about-lamb": "LAMB Helper",
        "create-assistant": "Create: (new)",
        "improve-assistant": "Improve",
        "explain-assistant": "Explain",
        "test-and-evaluate": "Test",
        "test-lti-tools": "LTI Setup",
    }
    if skill_id:
        base = _skill_titles.get(skill_id, skill_id)
        # Resolve assistant name (strip user prefix like "1_")
        if assistant_id and skill_id in ("improve-assistant", "explain-assistant", "test-and-evaluate"):
            try:
                from lamb.services.assistant_service import AssistantService
                svc = AssistantService()
                assistant = svc.get_assistant_by_id(assistant_id)
                if assistant:
                    name = assistant.name
                    # Strip leading user_id prefix: "1_name" → "name"
                    if "_" in name and name.split("_")[0].isdigit():
                        name = name.split("_", 1)[1]
                    title = f"{base}: {name}"
            except Exception:
                pass
        if not title:
            title = base
    else:
        title = "Free-form chat"

    mgr = AACSessionManager()
    session = mgr.create_session(
        user_email=auth.user["email"],
        organization_id=auth.organization["id"],
        assistant_id=assistant_id,
        title=title,
    )

    result = {
        "id": session["id"],
        "assistant_id": assistant_id,
        "title": title,
        "status": "active",
        "skill": skill_id,
        "created_at": session["created_at"],
    }

    # If skill, store skill_info so the first message triggers startup
    if skill_id:
        mgr.update_conversation(
            session_id=session["id"],
            user_email=auth.user["email"],
            conversation=[],
            skill_info={"skill_id": skill_id, "context": skill_context, "started": False},
        )

    return result


@router.get("/skills")
async def get_available_skills(auth: AuthContext = Depends(get_auth_context)):
    """List available AAC skills."""
    return list_skills()


@router.get("/sessions")
async def list_sessions(auth: AuthContext = Depends(get_auth_context)):
    """List the current user's AAC sessions."""
    mgr = AACSessionManager()
    return mgr.list_sessions(auth.user["email"])


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get session details including conversation history."""
    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive a session."""
    mgr = AACSessionManager()
    if not mgr.delete_session(session_id, auth.user["email"]):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@router.put("/sessions/{session_id}/title")
async def rename_session(
    session_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Rename a session (update its title)."""
    body = await request.json()
    title = body.get("title", "")
    mgr = AACSessionManager()
    if not mgr.rename_session(session_id, auth.user["email"], title):
        raise HTTPException(status_code=404, detail="Session not found or invalid title")
    return {"success": True, "title": title.strip()[:200]}


# ---------------------------------------------------------------------------
# Agent interaction
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Send a message to the AAC agent and get a response.

    Request body: {"message": "text"}
    Response: {"response": "agent text", "stats": {...}}

    The response shape is always the same. Authorization for write commands
    is handled internally — if confirmation is needed, the agent's response
    will ask the user, and the user's next message resolves it.
    """
    body = await request.json()
    user_message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(user_message, str) or not user_message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    user_message = user_message.strip()

    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract bearer token from request for liteshell HTTP calls
    auth_header = request.headers.get("authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer") else ""

    # Build agent — handle skill startup if needed
    agent, user_message, skill_info = await _prepare_agent_and_message(auth, session, user_message, token=bearer_token)

    # Run agent loop
    try:
        response_text = await agent.chat(user_message)
    except Exception as e:
        logger.error(f"Agent error in session {session_id}: {e}")
        if agent.session_logger:
            agent.session_logger.log_error(str(e), context="agent_chat")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    finally:
        await _finish_turn(mgr, agent, session_id, auth.user["email"], skill_info)



    stats = agent.get_stats()
    if agent.session_logger:
        agent.session_logger.log("turn_complete", stats)

    return {
        "response": response_text,
        "stats": stats,
    }


@router.post("/sessions/{session_id}/message/stream")
async def send_message_stream(
    session_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Send a message and stream the response via SSE.

    Request body: {"message": "text"}
    Response: text/event-stream with chunks, ending with [DONE]
    """
    body = await request.json()
    user_message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(user_message, str) or not user_message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    user_message = user_message.strip()

    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    auth_header = request.headers.get("authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer") else ""
    agent, user_message, skill_info = await _prepare_agent_and_message(auth, session, user_message, token=bearer_token)

    async def generate():
        try:
            async for event in agent.chat_stream(user_message):
                if isinstance(event, dict):
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"data: {json.dumps({'content': event})}\n\n"
        except Exception as e:
            logger.error(f"Stream error in session {session_id}: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            await _finish_turn(mgr, agent, session_id, auth.user["email"], skill_info)
        stats = agent.get_stats()
        if agent.session_logger:
            agent.session_logger.log("turn_complete", stats)
        yield f"data: {json.dumps({'done': True, 'stats': stats})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _finish_turn(mgr, agent, session_id, user_email, skill_info):
    """Persist completed tool effects even when output fails or the client leaves."""
    if skill_info:
        skill_info["started"] = True
    try:
        mgr.update_conversation(session_id=session_id, user_email=user_email,
            conversation=agent.conversation, pending_action=agent.pending_action,
            skill_info=skill_info, tool_audit=agent.tool_audit)
    finally:
        # Starlette cancels the response scope on disconnect; close clients inside a shield.
        with anyio.CancelScope(shield=True):
            try:
                await agent.shell.close()
            finally:
                await agent.llm_client.close()


async def _prepare_agent_and_message(
    auth: AuthContext, session: dict, user_message: str, token: str = "",
) -> tuple:
    """Build the right agent and adjust the message for skill startup.

    Returns: (agent, message, skill_info)
    """
    skill_info = session.get("skill_info")

    if skill_info and not skill_info.get("started"):
        # First message in a skill session — build with skill and use startup trigger
        agent = await _build_agent_with_skill(
            auth, session,
            skill_info["skill_id"],
            skill_info.get("context", {}),
            token=token,
        )
        # The user message becomes the startup trigger; prepend the actual message if any
        if user_message and not user_message.startswith("[System:"):
            startup_msg = f"[System: Skill launched. Greet the user and present your initial analysis.]\nUser's first message: {user_message}"
        else:
            startup_msg = "[System: Skill launched. Greet the user and present your initial analysis.]"
        return agent, startup_msg, skill_info
    else:
        agent = _build_agent(auth, session, token=token)
        return agent, user_message, skill_info


def _resolve_agent_llm(user_email: str):
    """Use the organization's selected provider for both plain and skill AAC."""
    resolver = OrganizationConfigResolver(user_email)
    default = resolver.get_global_default_model_config()
    provider = default.get("provider") or "openai"
    if provider not in {"openai", "ollama"}:
        raise HTTPException(status_code=400, detail=f"AAC does not support provider '{provider}'")
    config = resolver.get_provider_config(provider)
    if not config or config.get("enabled") is False:
        raise HTTPException(status_code=400, detail=f"No enabled {provider} provider configured for this organization")
    model = default.get("model") or config.get("default_model")
    base_url = config.get("base_url")
    if provider == "ollama":
        if not base_url or not model:
            raise HTTPException(status_code=400, detail="AAC requires an Ollama base URL and default model")
        # Ollama's compatible endpoint accepts tools through the existing legacy loop.
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        api_key = config.get("api_key") or "ollama"
    else:
        api_key = config.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="No OpenAI API key configured for this organization")
        model = model or "gpt-4o-mini"
    return AsyncOpenAI(api_key=api_key, base_url=base_url), model


def _build_agent(auth: AuthContext, session: dict, token: str = "") -> AgentLoop:
    """Build an AgentLoop from auth context and session state."""
    user_email = auth.user["email"]
    org_id = auth.organization["id"]
    user_id = auth.user.get("id", 0)

    llm_client, model = _resolve_agent_llm(user_email)

    # Build components — liteshell uses LambClient via HTTP (same path as CLI/frontend)
    import os
    server_url = os.environ.get("LAMB_LITESHELL_URL", "http://localhost:9099")
    shell = LiteShell(
        server_url=server_url,
        token=token,
        user_email=user_email,
        organization_id=org_id,
        user_id=user_id,
    )
    authorizer = ActionAuthorizer()

    slog = SessionLogger(
        session_id=session["id"],
        user_email=user_email,
        user_id=user_id,
    )
    slog.log_session_start(assistant_id=session.get("assistant_id"), model=model)

    agent = AgentLoop(
        shell=shell,
        llm_client=llm_client,
        model=model,
        authorizer=authorizer,
        session_logger=slog,
        session_id=session["id"],
    )

    # Load generic skills (for non-skill sessions)
    if SKILLS_DIR.is_dir():
        agent.load_skills(SKILLS_DIR)

    # Restore state from session
    agent.conversation = session.get("conversation", [])
    agent.pending_action = session.get("pending_action")
    agent.tool_audit = session.get("tool_audit", [])

    return agent


async def _build_agent_with_skill(
    auth: AuthContext,
    session: dict,
    skill_id: str,
    context: dict,
    token: str = "",
) -> AgentLoop:
    """Build an AgentLoop configured for a specific skill.

    The skill's prompt replaces the generic skills. Startup actions
    are executed before the agent's first turn.
    """
    user_email = auth.user["email"]
    org_id = auth.organization["id"]
    user_id = auth.user.get("id", 0)

    # Load and resolve the skill
    skill = load_skill(skill_id, context)

    llm_client, model = _resolve_agent_llm(user_email)

    # Build components — liteshell uses LambClient via HTTP
    import os
    server_url = os.environ.get("LAMB_LITESHELL_URL", "http://localhost:9099")
    shell = LiteShell(
        server_url=server_url,
        token=token,
        user_email=user_email,
        organization_id=org_id,
        user_id=user_id,
    )
    authorizer = ActionAuthorizer()

    slog = SessionLogger(
        session_id=session["id"],
        user_email=user_email,
        user_id=user_id,
    )
    slog.log_session_start(
        assistant_id=session.get("assistant_id"),
        model=model,
    )
    slog.log("skill_loaded", {"skill_id": skill_id, "context": context})

    # Build agent with skill prompt instead of generic skills
    from lamb.aac.agent.loop import DEFAULT_SYSTEM_PROMPT
    system_prompt = DEFAULT_SYSTEM_PROMPT + "\n\n# Active Skill\n" + skill["prompt"]

    agent = AgentLoop(
        shell=shell,
        llm_client=llm_client,
        model=model,
        authorizer=authorizer,
        system_prompt=system_prompt,
        session_logger=slog,
        session_id=session["id"],
    )

    # Execute startup actions via liteshell
    from lamb.aac.agent.loop import _parse_action_key, _extract_artifacts
    for action in skill["startup_actions"]:
        if authorizer.check(authorizer.resolve_action_key(action) or "") != "auto":
            agent.conversation.append({"role": "user", "content":
                f"[System: Startup action skipped because it requires authorization: {action}]"})
            continue
        result = await shell.execute(action)
        # Record in tool audit
        action_key = _parse_action_key(action)
        agent._record_audit(action, action_key, result.success, result.elapsed_ms, result)
        if result.success:
            agent.conversation.append({
                "role": "user",
                "content": f"[System: Startup data from `{action}`]\n{_truncate_json(result.data)}",
            })
            slog.log_tool_call(
                command=action,
                success=True,
                elapsed_ms=result.elapsed_ms,
                data=result.data,
            )
        else:
            logger.warning(f"Skill startup action failed: {action} → {result.error}")
            slog.log_tool_call(
                command=action,
                success=False,
                elapsed_ms=result.elapsed_ms,
                error=result.error,
            )

    return agent


def _truncate_json(data: Any, max_len: int = 3000) -> str:
    """Serialize data to JSON, truncating if too long."""
    import json
    text = json.dumps(data, default=str, ensure_ascii=False, indent=2)
    if len(text) > max_len:
        return text[:max_len] + "\n... (truncated)"
    return text
