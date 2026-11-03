"""Real SQLite restore conflicts and current authorization on stored artifacts."""
import copy
import sqlite3
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException, Response
from lamb.aac import execution_router as api
from lamb.aac.auto_work import signature


class Auth:
    user = {'email': 'teacher@example.test'}
    organization = {'id': 1}
    denied = False
    def require_assistant_access(self, identifier, level='any'):
        if self.denied or identifier != 7:
            raise HTTPException(403, 'No access')
    def require_kb_access(self, identifier, level='any'):
        if self.denied:
            raise HTTPException(403, 'No access')


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path/'journal.db'
    old = dict(zip(api.FIELDS, ('7_prova_carles', '', 'teacher@example.test', '{}', 'Previous prompt', '', 3, '')))
    new = {**old, 'system_prompt': 'Changed prompt'}
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE T_assistants (id INTEGER PRIMARY KEY, ' + ','.join(k + (' INTEGER' if k == 'RAG_Top_k' else ' TEXT') for k in api.FIELDS) + ')')
        c.execute('INSERT INTO T_assistants VALUES ('+','.join('?' for _ in range(1+len(api.FIELDS)))+')', [7, *new.values()])
    class DB:
        table_prefix = 'T_'
        def get_connection(self): return sqlite3.connect(path)
    monkeypatch.setattr(api, 'LambDatabaseManager', DB)
    entry = {'id': 'change_1', 'command': 'lamb assistant update 7 --system-prompt "Changed prompt"', 'status': 'completed', 'created_at': 1,
             'before': {'fields': old, 'revision': signature(old)}, 'after': {'fields': new, 'revision': signature(new)}}
    session = {'id': 'session_1', 'organization_id': 1, 'conversation': [],
               'skill_info': {'execution': {'journal': [entry], 'reports': [
                   {'id': 'report_1', 'title': 'Saved report', 'destination': {'resource': 'assistant', 'id': '7', 'tab': 'tests'}}]}}}
    class Sessions:
        def get_session(self, identifier, email):
            return session if identifier == 'session_1' and email == Auth.user['email'] else None
    monkeypatch.setattr(api, 'AACSessionManager', Sessions)
    return path, session, old, new


@pytest.mark.asyncio
async def test_restore_uses_retained_data_and_preserves_owner(store):
    path, session, old, _ = store
    request = N(json=AsyncMock(return_value={'session_id': 'session_1', 'change_id': 'change_1'}))
    result = await api.restore_assistant(7, request, Auth())
    assert result['after']['fields'] == old
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT system_prompt,owner FROM T_assistants WHERE id=7').fetchone() == ('Previous prompt', 'teacher@example.test')


@pytest.mark.asyncio
async def test_intervening_edit_prevents_restore(store):
    path, _, _, _ = store
    with sqlite3.connect(path) as c:
        c.execute('UPDATE T_assistants SET description=? WHERE id=7', ('Someone else edited this',))
    with pytest.raises(HTTPException) as error:
        await api.restore_assistant(7, N(json=AsyncMock(return_value={'session_id': 'session_1', 'change_id': 'change_1'})), Auth())
    assert error.value.status_code == 409
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT system_prompt FROM T_assistants WHERE id=7').fetchone()[0] == 'Changed prompt'


@pytest.mark.asyncio
async def test_client_cannot_supply_restore_values(store):
    with pytest.raises(HTTPException) as error:
        await api.restore_assistant(7, N(json=AsyncMock(return_value={'session_id': 'session_1', 'change_id': 'change_1', 'before': {'system_prompt': 'Injected'}})), Auth())
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_report_rechecks_current_access_and_org(store):
    auth = Auth()
    assert (await api.read_report('session_1', 'report_1', Response(), auth))['title'] == 'Saved report'
    auth.denied = True
    with pytest.raises(HTTPException) as error:
        await api.read_report('session_1', 'report_1', Response(), auth)
    assert error.value.status_code == 403
    auth.denied = False
    auth.organization = {'id': 2}
    with pytest.raises(HTTPException) as error:
        await api.read_report('session_1', 'report_1', Response(), auth)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_change_history_hides_values_after_revocation(store):
    auth = Auth()
    assert len(await api.read_changes('session_1', Response(), auth)) == 1
    auth.denied = True
    assert await api.read_changes('session_1', Response(), auth) == []


@pytest.mark.asyncio
async def test_snapshot_requires_owner_access(store):
    auth = Auth()
    result = await api.assistant_snapshot(7, Response(), auth)
    assert result['revision'] == signature(result['fields'])
    auth.denied = True
    with pytest.raises(HTTPException):
        await api.assistant_snapshot(7, Response(), auth)
