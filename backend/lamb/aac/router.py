"""AAC API router — /creator/aac/ endpoints.

Provides session management and agent interaction for the
Agent-Assisted Creator.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import AsyncOpenAI

from lamb.auth_context import AuthContext, get_auth_context
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.aac.authorization import ActionAuthorizer
from lamb.aac.session_manager import AACSessionManager
from lamb.aac.session_logger import SessionLogger
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
    """Start a new AAC design session."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    assistant_id = body.get("assistant_id")

    mgr = AACSessionManager()
    session = mgr.create_session(
        user_email=auth.user["email"],
        organization_id=auth.organization["id"],
        assistant_id=assistant_id,
    )
    return session


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

    # Load skills
    if SKILLS_DIR.is_dir():
        agent.load_skills(SKILLS_DIR)

    # Restore state from session
    agent.conversation = session.get("conversation", [])
    agent.pending_action = session.get("pending_action")

    return agent
