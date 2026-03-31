"""AAC API router — /creator/aac/ endpoints.

Provides session management and agent interaction for the
Agent-Assisted Creator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
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

    # Generate session title
    title = ""
    if skill_id:
        try:
            skill_meta = load_skill(skill_id, skill_context)["metadata"]
            skill_name = skill_meta.get("name", skill_id)
        except Exception:
            skill_name = skill_id
        # Try to get assistant name for the title
        if assistant_id:
            try:
                from lamb.services.assistant_service import AssistantService
                svc = AssistantService()
                assistant = svc.get_assistant_by_id(assistant_id)
                if assistant:
                    title = f"{skill_name}: {assistant.name}"
            except Exception:
                pass
        if not title:
            title = skill_name
    else:
        title = f"Session"

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

    # If a skill is set, run the startup sequence
    if skill_id:
        try:
            agent = _build_agent_with_skill(auth, session, skill_id, skill_context)
            # Run agent's first turn with a synthetic startup message
            first_message = await agent.chat(
                "[System: Skill launched. Run your startup analysis and greet the user.]"
            )
            # Persist conversation
            mgr.update_conversation(
                session_id=session["id"],
                user_email=auth.user["email"],
                conversation=agent.conversation,
                pending_action=agent.pending_action,
            )
            result["first_message"] = first_message
            result["stats"] = agent.get_stats()
        except Exception as e:
            logger.error(f"Skill startup failed for '{skill_id}': {e}")
            result["first_message"] = None
            result["error"] = f"Skill startup failed: {str(e)}"

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
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build agent with restored state
    agent = _build_agent(auth, session)

    # Run agent loop (handles pending actions, authorization, tool calls)
    try:
        response_text = await agent.chat(user_message)
    except Exception as e:
        logger.error(f"Agent error in session {session_id}: {e}")
        if agent.session_logger:
            agent.session_logger.log_error(str(e), context="agent_chat")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Persist conversation + pending action
    mgr.update_conversation(
        session_id=session_id,
        user_email=auth.user["email"],
        conversation=agent.conversation,
        pending_action=agent.pending_action,
    )

    stats = agent.get_stats()
    if agent.session_logger:
        agent.session_logger.log("turn_complete", stats)

    return {
        "response": response_text,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_agent(auth: AuthContext, session: dict) -> AgentLoop:
    """Build an AgentLoop from auth context and session state."""
    user_email = auth.user["email"]
    org_id = auth.organization["id"]
    user_id = auth.user.get("id", 0)

    # Resolve LLM config from organization
    resolver = OrganizationConfigResolver(user_email)
    openai_config = resolver.get_provider_config("openai")

    if not openai_config or not openai_config.get("api_key"):
        raise HTTPException(
            status_code=500,
            detail="No OpenAI provider configured for this organization",
        )

    llm_client = AsyncOpenAI(
        api_key=openai_config["api_key"],
        base_url=openai_config.get("base_url"),
    )

    # Use global default model, or fall back to provider default
    global_default = resolver.get_global_default_model_config()
    model = global_default.get("model") or openai_config.get("default_model", "gpt-4o-mini")

    # Build components
    shell = LiteShell(user_email=user_email, organization_id=org_id, user_id=user_id)
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
    )

    # Load generic skills (for non-skill sessions)
    if SKILLS_DIR.is_dir():
        agent.load_skills(SKILLS_DIR)

    # Restore state from session
    agent.conversation = session.get("conversation", [])
    agent.pending_action = session.get("pending_action")

    return agent


def _build_agent_with_skill(
    auth: AuthContext,
    session: dict,
    skill_id: str,
    context: dict,
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

    # Resolve LLM config
    resolver = OrganizationConfigResolver(user_email)
    openai_config = resolver.get_provider_config("openai")
    if not openai_config or not openai_config.get("api_key"):
        raise HTTPException(
            status_code=500,
            detail="No OpenAI provider configured for this organization",
        )

    llm_client = AsyncOpenAI(
        api_key=openai_config["api_key"],
        base_url=openai_config.get("base_url"),
    )

    global_default = resolver.get_global_default_model_config()
    model = global_default.get("model") or openai_config.get("default_model", "gpt-4o-mini")

    # Build components
    shell = LiteShell(user_email=user_email, organization_id=org_id, user_id=user_id)
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
    )

    # Execute startup actions via liteshell
    for action in skill["startup_actions"]:
        result = shell.execute(action)
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
