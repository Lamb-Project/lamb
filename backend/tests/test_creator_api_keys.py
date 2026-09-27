"""Creator API keys for the OpenAI-compatible facade (#519)."""
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import main
from config import API_KEY

KEY = 'lamb_ak_fixture-only-key'


def request(token=None):
    return SimpleNamespace(headers={'Authorization': f'Bearer {token}'} if token is not None else {})


def fake_db(status='active', expires_at=None, api_access=True, enabled=True, found=True):
    db = MagicMock()
    db.get_api_key_by_hash.side_effect = lambda h: ({'id': 3, 'creator_user_id': 8, 'organization_id': 2, 'status': status,
        'expires_at': expires_at} if found and h == hashlib.sha256(KEY.encode()).hexdigest() else None)
    db.get_organization_by_id.return_value = {'id': 2, 'config': {'features': {'api_access': api_access}}}
    db.get_creator_user_by_id.return_value = {'id': 8, 'user_email': 'a1@example.invalid'}
    db.get_creator_user_by_email.return_value = {'id': 8, 'enabled': enabled}
    db.get_published_assistants_for_org_user.return_value = [{'id': 25}, {'id': 30}]
    return db


def resolve(token, **state):
    db = fake_db(**state)
    with patch.object(main, 'LambDatabaseManager', return_value=db):
        return main._resolve_facade_identity(request(token)), db


def test_system_token_is_system():
    assert resolve(API_KEY)[0] == {'kind': 'system'}


def test_valid_creator_key_resolves_to_its_creator_and_is_touched():
    identity, db = resolve(KEY)
    assert identity == {'kind': 'creator', 'user_id': 8, 'organization_id': 2, 'email': 'a1@example.invalid'}
    db.touch_api_key.assert_called_once_with(3)


@pytest.mark.parametrize('state', [
    {'status': 'revoked'}, {'expires_at': int(time.time()) - 1}, {'api_access': False},
    {'enabled': False}, {'found': False}])
def test_invalid_creator_keys_resolve_to_nothing(state):
    identity, db = resolve(KEY, **state)
    assert identity is None
    db.touch_api_key.assert_not_called()


@pytest.mark.parametrize('token', [None, '', 'wrong', 'tést'])
def test_missing_or_wrong_credentials_resolve_to_nothing(token):
    assert resolve(token)[0] is None


def test_models_list_requires_a_credential():
    with patch.object(main, 'LambDatabaseManager', return_value=fake_db()), \
         patch.object(main, 'helper_get_all_assistants', return_value=[{'id': 25}, {'id': 30}, {'id': 99}]):
        import asyncio
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.get_models(request()))
        assert exc.value.status_code == 401


def test_models_list_is_scoped_for_a_creator_key_and_full_for_the_system_token():
    import asyncio, json
    assistants = [{'id': 25}, {'id': 30}, {'id': 99}]
    with patch.object(main, 'LambDatabaseManager', return_value=fake_db()), \
         patch.object(main, 'helper_get_all_assistants', return_value=assistants), \
         patch.object(main, '_get_assistant_capabilities', return_value={}):
        creator = json.loads(asyncio.run(main.get_models(request(KEY))).body)
        system = json.loads(asyncio.run(main.get_models(request(API_KEY))).body)
    assert [m['id'] for m in creator['data']] == ['lamb_assistant.25', 'lamb_assistant.30']
    assert len(system['data']) == 3
