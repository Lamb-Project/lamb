"""Authenticated learning scenario API; documents are never served directly."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictInt
from lamb.auth_context import AuthContext, get_auth_context
from lamb.aac.learning_scenarios import ScenarioStore

router = APIRouter()

class Create(BaseModel):
    title: str
    content: str = ''
    links: dict | None = None

class Update(BaseModel):
    revision: StrictInt
    title: str | None = None
    content: str | None = None
    links: dict | None = None

class Selection(BaseModel):
    scenario_id: str | None = None

@router.get('/learning-scenarios')
def list_scenarios(auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).list()

@router.post('/learning-scenarios')
def create(body: Create, auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).create(body.title, body.content, body.links)

@router.put('/learning-scenarios/default')
def default(body: Selection, auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).default(body.scenario_id)

@router.get('/learning-scenarios/{key}')
def get(key: str, auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).get(key)

@router.put('/learning-scenarios/{key}')
def update(key: str, body: Update, auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).update(key, body.revision, **{k:v for k,v in body.model_dump().items() if k != 'revision' and v is not None})

@router.delete('/learning-scenarios/{key}')
def remove(key: str, revision: int, auth: AuthContext = Depends(get_auth_context)):
    return ScenarioStore(auth).update(key, revision, archived=True)

@router.post('/learning-scenarios/{key}/duplicate')
def duplicate(key: str, body: Create, auth: AuthContext = Depends(get_auth_context)):
    store = ScenarioStore(auth)
    source = store.get(key)
    return store.create(body.title, source['content'], source.get('links', {}))

@router.get('/sessions/{session_id}/learning-scenario')
def selected(session_id: str, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.session_manager import AACSessionManager
    session = AACSessionManager().get_session(session_id, auth.user['email'])
    if not session or session['organization_id'] != auth.organization['id']:
        raise HTTPException(404, 'Session not found')
    key = (session.get('skill_info') or {}).get('learning_scenario_id')
    item = None
    if key:
        try: item = ScenarioStore(auth).get(key)
        except HTTPException as exc:
            if exc.status_code != 404: raise
    return {'scenario_id': key, 'scenario': item, 'unavailable': bool(key and not item)}

@router.put('/sessions/{session_id}/learning-scenario')
def select(session_id: str, body: Selection, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.session_manager import AACSessionManager
    from lamb.aac.turn_lock import TurnLock
    selected(session_id, auth)
    with TurnLock(session_id):
        mgr = AACSessionManager()
        session = mgr.get_session(session_id, auth.user['email'])
        if session.get('pending_action'):
            raise HTTPException(409, 'Resolve the pending action before changing the learning scenario')
        state = session.get('skill_info') or {}
        state['learning_scenario_id'] = ScenarioStore(auth).selection(body.scenario_id)
        mgr.update_conversation(session_id, auth.user['email'], session['conversation'],
            pending_action=session.get('pending_action'), skill_info=state, tool_audit=session.get('tool_audit'))
    return selected(session_id, auth)
