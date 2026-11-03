"""Owner-scoped execution controls, result readback and revision-checked restoration."""
import json
from contextlib import closing
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from lamb.auth_context import AuthContext, get_auth_context
from lamb.aac.session_manager import AACSessionManager
from lamb.aac.turn_lock import TurnLock
from lamb.aac.auto_work import task_state, signature
from lamb.database_manager import LambDatabaseManager

router = APIRouter()
FIELDS = ('name', 'description', 'owner', 'api_callback', 'system_prompt', 'prompt_template', 'RAG_Top_k', 'RAG_collections')


def session_for(auth, identifier):
    session = AACSessionManager().get_session(identifier, auth.user['email'])
    if not session or session['organization_id'] != auth.organization['id']:
        raise HTTPException(404, 'Session not found')
    return session


def state_for(session):
    return task_state(session.setdefault('skill_info', {}) or _empty_state(session))


def _empty_state(session):
    session['skill_info'] = {}
    return session['skill_info']


def persist(session, auth):
    AACSessionManager().update_conversation(session['id'], auth.user['email'], session['conversation'],
        pending_action=session.get('pending_action'), skill_info=session['skill_info'], tool_audit=session.get('tool_audit'))


@router.put('/sessions/{session_id}/execution')
async def set_execution(session_id: str, request: Request, auth: AuthContext = Depends(get_auth_context)):
    session_for(auth, session_id)
    body = await request.json()
    if not isinstance(body, dict) or set(body) - {'mode', 'new_task'}:
        raise HTTPException(400, 'Use mode or new_task')
    if 'mode' in body and body['mode'] not in {'auto', 'guided'}:
        raise HTTPException(400, 'Mode must be auto or guided')
    if 'new_task' in body and type(body['new_task']) is not bool:
        raise HTTPException(400, 'new_task must be boolean')
    with TurnLock(session_id):
        session = session_for(auth, session_id)
        state = state_for(session)
        if session.get('pending_action'):
            raise HTTPException(409, 'Resolve the prepared approval before changing execution mode or starting another task')
        plan = state['task'].get('plan') or {}
        if plan.get('status') in {'approved', 'running', 'uncertain'}:
            raise HTTPException(409, 'Finish or reconcile the active plan first')
        if body.get('new_task'):
            state.setdefault('previous_tasks', []).append(state.pop('task'))
            task_state(session['skill_info'])
        if 'mode' in body:
            state['mode'] = body['mode']
        persist(session, auth)
    return {'mode': state['mode'], 'task_id': state['task']['id']}


@router.get('/sessions/{session_id}/reports/{report_id}')
async def read_report(session_id: str, report_id: str, response: Response, auth: AuthContext = Depends(get_auth_context)):
    session = session_for(auth, session_id)
    report = next((r for r in state_for(session)['reports'] if r['id'] == report_id), None)
    if not report:
        raise HTTPException(404, 'Report not found')
    auth.require_assistant_access(int(report['destination']['id']))
    if report.get('kind') == 'activity-analysis':
        from creator_interface.analytics_router import require_analysis_access
        from lamb.services.activity_analysis import AnalysisStore
        require_analysis_access(auth, int(report['assistant_id']))
        report = AnalysisStore().get(auth, int(report['assistant_id']), report['id'])
    response.headers['Cache-Control'] = 'private, no-store'
    return report


@router.get('/sessions/{session_id}/changes')
async def read_changes(session_id: str, response: Response, auth: AuthContext = Depends(get_auth_context)):
    from lamb.aac.liteshell.shell import prepare_command
    session = session_for(auth, session_id)
    result = []
    for entry in state_for(session)['journal']:
        key, args, _, _ = prepare_command(entry['command'])
        # Historical assistant values remain subject to current resource authority.
        if key == 'assistant.update':
            try:
                auth.require_assistant_access(int(args[0]), level='owner')
            except HTTPException:
                continue
        if key == 'kb.update':
            try:
                auth.require_kb_access(args[0])
            except HTTPException:
                continue
        if key.startswith('test.') and args:
            try:
                target = args[1] if key == 'test.evaluate' else args[0]
                auth.require_assistant_access(int(target))
            except (HTTPException, ValueError):
                continue
        result.append({k: entry.get(k) for k in ('id', 'status', 'created_at', 'before', 'after')} | {
            'action': key, 'restorable': key == 'assistant.update' and entry['status'] == 'completed'
            and bool(entry.get('before') and entry.get('after'))})
    response.headers['Cache-Control'] = 'private, no-store'
    return result


def snapshot(connection, table, identifier):
    row = connection.execute(f'SELECT {", ".join(FIELDS)} FROM {table} WHERE id=?', (identifier,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Assistant not found')
    fields = dict(zip(FIELDS, row))
    return {'fields': fields, 'revision': signature(fields)}


@router.get('/assistants/{assistant_id}/snapshot')
async def assistant_snapshot(assistant_id: int, response: Response, auth: AuthContext = Depends(get_auth_context)):
    auth.require_assistant_access(assistant_id, level='owner')
    db = LambDatabaseManager()
    with closing(db.get_connection()) as c:
        result = snapshot(c, f'{db.table_prefix}assistants', assistant_id)
    response.headers['Cache-Control'] = 'private, no-store'
    return result


@router.post('/assistants/{assistant_id}/restore')
async def restore_assistant(assistant_id: int, request: Request, auth: AuthContext = Depends(get_auth_context)):
    auth.require_assistant_access(assistant_id, level='owner')
    body = await request.json()
    if not isinstance(body, dict) or set(body) != {'session_id', 'change_id'}:
        raise HTTPException(400, 'Provide session_id and change_id')
    session = session_for(auth, body['session_id'])
    entry = next((e for e in state_for(session)['journal'] if e['id'] == body['change_id']), None)
    if not entry or entry.get('status') != 'completed' or not entry.get('before') or not entry.get('after'):
        raise HTTPException(404, 'Restorable change not found')
    from lamb.aac.liteshell.shell import prepare_command
    key, args, _, _ = prepare_command(entry['command'])
    if key != 'assistant.update' or int(args[0]) != assistant_id:
        raise HTTPException(400, 'Change does not belong to this assistant')
    old = entry['before']['fields']
    # Use server-retained historical values, never a client-supplied snapshot.
    if set(old) != set(FIELDS):
        raise HTTPException(409, 'Historical snapshot is incomplete')
    from lamb.uploaded_files import validate_file_binding
    validate_file_binding(old['api_callback'], old['owner'])
    db = LambDatabaseManager()
    table = f'{db.table_prefix}assistants'
    with closing(db.get_connection()) as c, c:
        c.execute('BEGIN IMMEDIATE')
        current = snapshot(c, table, assistant_id)
        if current['revision'] != entry['after']['revision']:
            raise HTTPException(409, 'Assistant changed after this edit. Compare the current version before restoring.')
        fields = [name for name in FIELDS if name != 'owner']
        c.execute(f'UPDATE {table} SET {", ".join(name+"=?" for name in fields)} WHERE id=?',
                  [old[name] for name in fields] + [assistant_id])
        restored = snapshot(c, table, assistant_id)
    return {'assistant_id': assistant_id, 'restored_change': entry['id'], 'before': current, 'after': restored}
