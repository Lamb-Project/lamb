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
from starlette.background import BackgroundTask
from openai import AsyncOpenAI

from lamb.auth_context import AuthContext, get_auth_context
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.aac.authorization import ActionAuthorizer
from lamb.aac.session_manager import AACSessionManager
from lamb.aac.turn_lock import TurnLock
from lamb.aac.session_logger import SessionLogger
from lamb.aac.skill_loader import load_skill, list_skills
from lamb.aac.liteshell.shell import LiteShell
from lamb.aac.agent.loop import AgentLoop
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

router = APIRouter(prefix="/aac", tags=["AAC"])

from lamb.aac.skill_loader import SKILLS_DIR
from lamb.aac.scenario_router import router as scenario_router
router.include_router(scenario_router)

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
    from lamb.aac.language import validate_ui_language, LANGUAGES
    try:
        validate_ui_language(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    ui_language = body.get('ui_language', 'en')
    assistant_id = body.get("assistant_id")
    skill_id = body.get("skill")
    skill_context = body.get("context", {})
    if not isinstance(skill_context, dict):
        raise HTTPException(status_code=400, detail="Skill context must be an object.")

    if ui_language:
        skill_context['language'] = LANGUAGES[ui_language]

    # If skill provides assistant_id in context, use it
    if "assistant_id" in skill_context and not assistant_id:
        assistant_id = skill_context["assistant_id"]
    # And vice versa
    if assistant_id and "assistant_id" not in skill_context:
        skill_context["assistant_id"] = assistant_id

    from lamb.aac.skill_routing import normalize_context
    skill_context = normalize_context(skill_context)

    if skill_id:
        _validate_skill_selection(skill_id, skill_context)

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

    # Situation and registry facts are computed once, before the first model turn.
    from lamb.aac.learning_scenarios import ScenarioStore
    selected_scenario = ScenarioStore(auth).selection(body.get("learning_scenario_id"))
    state = {"learning_scenario_id": selected_scenario, "skill_id": skill_id, "context": skill_context, "started": False, "ui_language":ui_language}
    try:
        state = await _initialize_session_knowledge(auth, state, request.app.routes, validate_selection=True)
    except ValueError as exc:
        raise HTTPException(503, f'LAMB AGENT knowledge configuration is unavailable: {exc}')

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

    mgr.update_conversation(session_id=session['id'], user_email=auth.user['email'], conversation=[], skill_info=state)
    result.update(brief=state['brief'], response_language_policy=state['response_language_policy'])

    return result


@router.get('/policy')
async def get_agent_policy(language: str = 'en', auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.preferences import response_policy, language_code
    try:
        language_code(language)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    try:
        return response_policy(OrganizationConfigResolver(auth.user['email']), language)
    except ValueError as exc:
        raise HTTPException(503, str(exc))


@router.get("/skills")
async def get_available_skills(auth: AuthContext = Depends(get_auth_context)):
    """List only workflows in this user's role layers."""
    from lamb.aac.pack_loader import load_pack, allowed_skills
    from lamb.aac.preferences import agent_settings
    from lamb.aac.brief import role_axes
    pack = load_pack(agent_settings(auth.organization.get('config', {})))
    allowed = allowed_skills(pack, role_axes(auth)['layers'])
    return [s for s in list_skills(pack.skills_dir) if s['id'] in allowed]


@router.get("/sessions")
async def list_sessions(auth: AuthContext = Depends(get_auth_context)):
    """List the current user's AAC sessions."""
    mgr = AACSessionManager()
    return mgr.list_sessions(auth.user["email"])


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    auth: AuthContext = Depends(get_auth_context),
    diagnostics: bool = False,
):
    """Get session details including conversation history."""
    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    from lamb.aac.session_guidance import browser_session
    return session if diagnostics else browser_session(session)


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


async def _read_user_message(request):
    body = await request.json()
    user_message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(user_message, str) or not user_message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    from lamb.aac.language import validate_ui_language
    try:
        validate_ui_language(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return user_message.strip()


def _lock_owned_session(session_id, auth):
    # Authorize before returning a busy response; reload under the lock in the
    # handler so a turn completed between this read and lock acquisition is seen.
    if not AACSessionManager().get_session(session_id, auth.user["email"]):
        raise HTTPException(status_code=404, detail="Session not found")
    return TurnLock(session_id)


@router.post("/sessions/{session_id}/frontend/{action_id}/claim")
async def frontend_claim(session_id: str, action_id: str, request: Request, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.frontend import get_mailbox
    body = await request.json()
    channel = body.get('channel', '') if isinstance(body, dict) else ''
    if not isinstance(channel, str) or not get_mailbox().claim(action_id, session_id, auth.user['email'], channel):
        raise HTTPException(409, 'Expired, duplicate or mismatched frontend action')
    return {'success': True, 'valid_for_ms': 5000}


@router.post("/sessions/{session_id}/frontend/{action_id}")
async def frontend_ack(session_id: str, action_id: str, request: Request, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.frontend import get_mailbox
    body = await request.json()
    if not isinstance(body, dict) or body.get('status') not in ('opened', 'current', 'blocked', 'failed'):
        raise HTTPException(400, 'Invalid frontend acknowledgement')
    # Only bounded, known fields enter tool results. Never ingest page HTML or form values.
    result = {k: str(body[k])[:300] for k in ('status', 'reason', 'route', 'resource', 'id', 'tab') if k in body}
    if not get_mailbox().acknowledge(action_id, session_id, auth.user['email'], str(body.get('channel', '')), result):
        raise HTTPException(409, 'Expired, duplicate or mismatched frontend action')
    return {'success': True}


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, request: Request, auth: AuthContext = Depends(get_auth_context)):
    message = await _read_user_message(request)
    with _lock_owned_session(session_id, auth):
        return await _send_message(session_id, request, auth, message)


@router.post("/sessions/{session_id}/message/stream")
async def send_message_stream(session_id: str, request: Request, auth: AuthContext = Depends(get_auth_context)):
    message = await _read_user_message(request)
    lock = _lock_owned_session(session_id, auth)
    try:
        response = await _send_message_stream(session_id, request, auth, message)
    except BaseException:
        lock.close()
        raise
    original = response.body_iterator
    async def guarded():
        try:
            async for chunk in original:
                yield chunk
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    await original.aclose()
            finally:
                lock.close()
    response.body_iterator = guarded()
    async def finish_stream():
        # Starlette may stop consuming while guarded is suspended at yield.
        # Finalize persistence before making the session available again.
        with anyio.CancelScope(shield=True):
            try:
                await response.body_iterator.aclose()
                await original.aclose()
            finally:
                lock.close()
    response.background = BackgroundTask(finish_stream)
    return response


async def _send_message(
    session_id: str,
    request: Request,
    auth: AuthContext,
    user_message: str,
):
    """Send a message to the AAC agent and get a response.

    Request body: {"message": "text"}
    Response: {"response": "agent text", "stats": {...}}

    The response shape is always the same. Authorization for write commands
    is handled internally — if confirmation is needed, the agent's response
    will ask the user, and the user's next message resolves it.
    """

    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract bearer token from request for liteshell HTTP calls
    auth_header = request.headers.get("authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer") else ""

    # Build agent — handle skill startup if needed
    agent, user_message, skill_info = await _prepare_agent_and_message(auth, session, user_message, token=bearer_token, ui_language=(await request.json()).get('ui_language'))

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
        "response": ((getattr(agent, "scenario_notice", None) or "") + "\n\n" + response_text).lstrip(),
        "stats": stats,
    }


async def _send_message_stream(
    session_id: str,
    request: Request,
    auth: AuthContext,
    user_message: str,
):
    """Send a message and stream the response via SSE.

    Request body: {"message": "text"}
    Response: text/event-stream with chunks, ending with [DONE]
    """

    mgr = AACSessionManager()
    session = mgr.get_session(session_id, auth.user["email"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    auth_header = request.headers.get("authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer") else ""
    agent, user_message, skill_info = await _prepare_agent_and_message(auth, session, user_message, token=bearer_token, ui_language=(await request.json()).get('ui_language'))

    from lamb.aac.frontend import FrontendBridge
    body = await request.json()
    bridge = None
    if body.get('frontend_channel'):
        try:
            bridge = FrontendBridge(session_id, auth.user['email'], body['frontend_channel'])
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, 'Invalid frontend channel')
        agent.shell.frontend = bridge.request

    async def generate():
        policy = (getattr(agent, 'skill_state', None) or {}).get('response_language_policy')
        if policy:
            yield f"data: {json.dumps({'status': 'policy', 'policy': policy})}\n\n"
        from lamb.aac.frontend import stream_with_frontend
        events = stream_with_frontend(agent.chat_stream(user_message), bridge)
        try:
            notice = getattr(agent, "scenario_notice", None)
            if isinstance(notice, str) and notice:
                yield f"data: {json.dumps({'content': notice + chr(10) + chr(10)})}\n\n"
            async for event in events:
                if isinstance(event, dict):
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"data: {json.dumps({'content': event})}\n\n"
        except Exception as e:
            logger.error(f"Stream error in session {session_id}: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await events.aclose()
                finally:
                    try:
                        if bridge:
                            bridge.close()
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


async def _initialize_session_knowledge(auth, state, routes=(), validate_selection=False):
    from lamb.aac.pack_loader import load_pack
    from lamb.aac.preferences import agent_settings, response_policy
    from lamb.aac.brief import capability_map, session_brief
    from lamb.aac.documentation import coverage
    selected = load_pack(agent_settings(auth.organization.get('config', {})))
    language = state.get('ui_language', 'en')
    if not state.get('brief'):
        state['brief'] = session_brief(auth, language, await capability_map(auth, routes), coverage(language), selected)
    from lamb.aac.pack_loader import allowed_skills
    if validate_selection and state.get('skill_id') and state['skill_id'] not in allowed_skills(selected, state['brief']['layers']):
        raise HTTPException(403, 'This workflow is outside your role')
    state.setdefault('pack_version', selected.version)
    state.setdefault('pack_hash', selected.fingerprint)
    state['response_language_policy'] = response_policy(OrganizationConfigResolver(auth.user['email']), language)
    return state


async def _apply_language_policy(agent, auth, requested):
    from lamb.aac.language import apply_ui_language
    from lamb.aac.preferences import response_policy, apply_policy
    apply_ui_language(agent, requested)
    try:
        policy = response_policy(OrganizationConfigResolver(auth.user['email']), agent.skill_state.get('ui_language', 'en'))
        apply_policy(agent, policy)
    except ValueError as exc:
        await agent.shell.close()
        await agent.llm_client.close()
        raise HTTPException(503, f'Invalid LAMB AGENT settings; ask the organization administrator: {exc}')


async def _finish_turn(mgr, agent, session_id, user_email, skill_info):
    """Persist completed tool effects even when output fails or the client leaves."""
    skill_info = getattr(agent, "skill_state", None) or skill_info
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


def _validate_skill_selection(skill_id, context):
    """Reject invalid selections before persisting a session or allocating clients."""
    from lamb.aac.skill_loader import load_skill
    if not isinstance(skill_id, str) or not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="Skill must be a name and context must be an object.")
    try:
        load_skill(skill_id, dict(context))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid skill selection: {exc}. Choose an available skill with its required context, or start a free-form session.") from exc


async def _prepare_agent_and_message(
    auth: AuthContext, session: dict, user_message: str, token: str = "", ui_language: str | None = None,
) -> tuple:
    """Build the right agent and adjust the message for skill startup.

    Returns: (agent, message, skill_info)
    """
    if not (session.get('skill_info') or {}).get('brief'):
        state = dict(session.get('skill_info') or {})
        from lamb.aac.language import LANGUAGES
        legacy_language = state.get('context', {}).get('language', '')
        inherited_locale = next((code for code,name in LANGUAGES.items() if name.casefold()==str(legacy_language).casefold()), 'en')
        state.setdefault('ui_language', ui_language or inherited_locale)
        try:
            session = dict(session, skill_info=await _initialize_session_knowledge(auth, state))
        except ValueError as exc:
            raise HTTPException(503, f'LAMB AGENT knowledge configuration is unavailable: {exc}')
    try:
        agent = _build_agent(auth, session, token=token)
    except ValueError as exc:
        raise HTTPException(503, f'LAMB AGENT knowledge configuration is unavailable: {exc}') from exc
    await _apply_language_policy(agent, auth, ui_language)
    state = agent.skill_state
    try:
        if state.get("skill_id") and not state.get("active_snapshot") and not agent.pending_action:
            instructions = agent.activate_skill(state["skill_id"], state.get("context"), reason="session_selection")
            agent.conversation.append({"role": "user", "content": "[System: Workflow instructions]\n" + instructions})
        elif not agent.pending_action:
            from lamb.aac.skill_routing import select_workflow
            selected = select_workflow(user_message, state, agent.pack)
            if selected:
                instructions = agent.activate_skill(*selected, reason="user_turn")
                agent.conversation.append({"role": "user", "content": "[System: Workflow instructions]\n" + instructions})
    except ValueError as exc:
        # An existing session must survive a retired or renamed recipe. New
        # invalid selections are still rejected by the creation endpoint.
        logger.warning("Recovering unavailable saved AAC workflow: %s", exc)
        state['skill_id'] = None
        state.pop('active_snapshot', None)
        from lamb.aac.session_guidance import guidance_notice
        agent.conversation.append({'role': 'assistant', 'content': guidance_notice(state, 'unavailable')})
    return agent, user_message, state


def _resolve_agent_llm(user_email: str):
    """Use the organization's selected provider for both plain and skill AAC."""
    resolver = OrganizationConfigResolver(user_email)
    from lamb.aac.preferences import agent_settings
    try:
        settings = agent_settings(resolver.organization.get('config', {}))
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    explicit = bool(settings.get('provider') or settings.get('model'))
    default = settings if explicit else resolver.get_global_default_model_config()
    if explicit and (not settings.get('model') or settings.get('provider') not in {'openai', 'ollama'}):
        raise HTTPException(503, 'Invalid LAMB AGENT model configuration; ask the organization administrator to correct it')
    provider = default.get("provider") or "openai"
    if provider not in {"openai", "ollama"}:
        try:
            default = resolver.resolve_model_for_completion(
                default.get("model"), provider, available_providers={"openai", "ollama"})
            provider = default["provider"]
        except ValueError:
            raise HTTPException(503, "AAC needs an enabled OpenAI-compatible or Ollama provider in this organization")
    config = resolver.get_provider_config(provider)
    if not config or config.get("enabled") is False:
        raise HTTPException(status_code=503, detail=f"No enabled {provider} provider configured for this organization")
    model = default.get("model") or config.get("default_model")
    base_url = config.get("base_url")
    if provider == "ollama":
        if not base_url or not model:
            raise HTTPException(status_code=503, detail="AAC requires an Ollama base URL and default model")
        # Ollama's compatible endpoint accepts tools through the existing legacy loop.
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        api_key = config.get("api_key") or "ollama"
    else:
        api_key = config.get("api_key")
        if not api_key:
            raise HTTPException(status_code=503, detail="No OpenAI API key configured for this organization")
        if not model:
            raise HTTPException(503, "AAC requires a configured default model; ask the organization administrator")
    return AsyncOpenAI(api_key=api_key, base_url=base_url), model


def _build_agent(auth: AuthContext, session: dict, token: str = "") -> AgentLoop:
    """Build an AgentLoop from auth context and session state."""
    user_email = auth.user["email"]
    org_id = auth.organization["id"]
    user_id = auth.user.get("id", 0)

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

    agent = AgentLoop(
        shell=shell,
        llm_client=None,
        model="",
        authorizer=authorizer,
        session_logger=slog,
        session_id=session["id"],
    )

    # Pin the rendered prefix for this session. Skill transitions append to history.
    state = dict(session.get("skill_info") or {})
    from lamb.aac.session_guidance import refresh_guidance
    from lamb.aac.pack_loader import load_pack, allowed_commands
    from lamb.aac.preferences import agent_settings
    # Never change the interpretation of an action already awaiting confirmation.
    if session.get('pending_action') and state.get('pack_version'):
        selected = load_pack(version=state['pack_version'])
    else:
        selected = load_pack(agent_settings(auth.organization.get('config', {})))
    agent.pack = selected
    shell.knowledge = {'pack':selected, 'brief':state.get('brief', {}), 'state':state}
    shell.allowed_commands = allowed_commands(selected, state.get('brief', {}).get('layers', ['creator']))
    notice = refresh_guidance(agent, state, session, SKILLS_DIR)
    shell.knowledge['brief'] = state.get('brief', {})
    state.setdefault("context", {})
    if session.get("assistant_id"):
        state["context"].setdefault("assistant_id", session["assistant_id"])
    from lamb.aac.skill_routing import normalize_context
    state['context'] = normalize_context(state.get('context'))
    agent.system_prompt = state["system_prompt"]
    agent.skill_state = state

    # Restore state from session
    agent.conversation = list(session.get("conversation", []))
    if notice:
        agent.conversation.append({"role": "assistant", "content": notice})
    agent.pending_action = session.get("pending_action")
    agent.tool_audit = session.get("tool_audit", [])
    from lamb.aac.learning_scenarios import apply_scenario
    apply_scenario(agent, auth)

    # Pure pack and prefix validation must finish before allocating an HTTP client.
    agent.llm_client, agent.model = _resolve_agent_llm(user_email)
    slog.log_session_start(assistant_id=session.get("assistant_id"), model=agent.model)

    return agent


async def _build_agent_with_skill(
    auth: AuthContext,
    session: dict,
    skill_id: str,
    context: dict,
    token: str = "",
) -> AgentLoop:
    """Compatibility entry point using the same persistent, append-only routing."""
    agent = _build_agent(auth, session, token=token)
    instructions = agent.activate_skill(skill_id, context, reason="session_selection")
    agent.conversation.append({"role": "user", "content": "[System: Workflow instructions]\n" + instructions})
    return agent


def _truncate_json(data: Any, max_len: int = 3000) -> str:
    """Serialize data to JSON, truncating if too long."""
    import json
    text = json.dumps(data, default=str, ensure_ascii=False, indent=2)
    if len(text) > max_len:
        return text[:max_len] + "\n... (truncated)"
    return text
