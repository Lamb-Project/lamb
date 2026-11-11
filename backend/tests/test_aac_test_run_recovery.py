"""Exact run request IDs and persisted distinction between agent and human judgments."""
import sqlite3
import uuid
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from lamb.services import test_router as api
from lamb.services.test_service import TestService as Service


@pytest.mark.asyncio
async def test_run_request_replay_does_not_dispatch_again(monkeypatch, tmp_path):
    from lamb.aac import turn_lock
    monkeypatch.setattr(turn_lock, 'LOCK_ROOT', tmp_path / 'locks')
    saved = {}
    async def run(**kwargs):
        result = {'id': kwargs['request_id'], 'assistant_id': kwargs['assistant_id'], 'scenario_id': kwargs['scenario_id']}
        saved[result['id']] = result
        return result
    service = N(get_scenario=lambda identifier: {'assistant_id': 7, 'messages': []},
                get_run=saved.get, run_scenario=AsyncMock(side_effect=run))
    monkeypatch.setattr(api, 'TestService', lambda: service)
    auth = N(user={'email': 'teacher@example.test'}, require_assistant_access=lambda *a, **k: None)
    identifier = str(uuid.uuid4())
    body = {'scenario_id': 'case1', 'request_id': identifier}
    request = N(headers={'content-type': 'application/json'}, json=AsyncMock(return_value=body))
    first = await api.run_tests(7, request, auth)
    assert await api.run_tests(7, request, auth) == first
    assert service.run_scenario.await_count == 1
    body['scenario_id'] = 'different-case'
    with pytest.raises(HTTPException) as error:
        await api.run_tests(7, request, auth)
    assert error.value.status_code == 409
    assert service.run_scenario.await_count == 1


@pytest.mark.asyncio
async def test_evaluator_provenance_is_stored_without_human_confirmation(monkeypatch, tmp_path):
    path = tmp_path / 'evaluations.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE T_assistant_test_evaluations (id TEXT, test_run_id TEXT, evaluator TEXT, verdict TEXT, notes TEXT, dimensions TEXT, confirmed_by_user INTEGER, created_at TEXT)')
    service = Service.__new__(Service)
    service._prefix = 'T_'
    service.db = N(get_connection=lambda: sqlite3.connect(path))
    service.get_run = lambda identifier: {'assistant_id': 7}
    monkeypatch.setattr(api, 'TestService', lambda: service)
    auth = N(require_assistant_access=lambda *a, **k: None)
    for evaluator in ('legatus', 'user'):
        await api.evaluate_run(7, 'run', N(json=AsyncMock(return_value={'verdict': 'good', 'evaluator': evaluator})), auth)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT evaluator,confirmed_by_user FROM T_assistant_test_evaluations').fetchall() == [('legatus', None), ('user', 1)]
