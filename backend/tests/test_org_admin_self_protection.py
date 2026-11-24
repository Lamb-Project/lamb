"""An organization admin cannot disable or delete their own account.

These go through the real ``verify_organization_admin_access``: the guards compare the target
with what that function returns, and they once read a key it does not return.
"""
import asyncio
from types import SimpleNamespace as N
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from creator_interface import organization_router as r

ORG = {'id': 7, 'slug': 'school', 'is_system': False}
SYSTEM = {'id': 1, 'slug': 'lamb', 'is_system': True}
USERS = {
    1: {'id': 1, 'user_email': 'root@lamb.example', 'organization_id': 1},
    11: {'id': 11, 'user_email': 'admin@school.example', 'organization_id': 7},
    12: {'id': 12, 'user_email': 'teacher@school.example', 'organization_id': 7},
}


def _auth(system_admin=False):
    if system_admin:  # acts in the system organization unless another one is named
        return N(user={'id': 1, 'email': 'root@lamb.example', 'name': 'Root'}, is_system_admin=True,
                 is_org_admin=True, organization=SYSTEM, organization_role='admin')
    return N(user={'id': 11, 'email': 'admin@school.example', 'name': 'Admin'}, is_system_admin=False,
             is_org_admin=True, organization=ORG, organization_role='admin')


def _call(endpoint, *args, system_admin=False, **kwargs):
    db = Mock()
    db.get_creator_user_by_id.side_effect = USERS.get
    db.get_organization_by_id.side_effect = {1: SYSTEM, 7: ORG}.get
    db.get_user_organization_role.side_effect = lambda user_id, org_id: 'admin' if user_id == 11 else 'member'
    db.delete_creator_user.return_value = True
    owi = Mock()
    owi.update_user_status.return_value = True
    owi.delete_user.return_value = True
    request = N(headers={'Authorization': 'Bearer token'})
    with patch.object(r, '_build_auth_context', return_value=_auth(system_admin)), \
            patch.object(r, 'db_manager', db), patch.object(r, 'OwiUserManager', return_value=owi):
        try:
            return asyncio.run(endpoint(request, *args, **kwargs)), db, owi
        except HTTPException as refused:
            return refused, db, owi


def _update(user_id, enabled, **kwargs):
    return _call(r.update_organization_user, user_id, r.OrgAdminUserUpdate(enabled=enabled), **kwargs)


@pytest.mark.parametrize('system_admin, own_id', [(False, 11), (True, 1)])
def test_an_admin_cannot_disable_their_own_account(system_admin, own_id):
    refused, _, owi = _update(own_id, False, system_admin=system_admin)

    assert isinstance(refused, HTTPException) and refused.status_code == 403
    assert 'cannot disable your own account' in refused.detail
    owi.update_user_status.assert_not_called()


def test_an_admin_can_disable_another_user_and_enable_themselves():
    result, _, owi = _update(12, False)
    assert result == {'message': 'User updated successfully'}
    owi.update_user_status.assert_called_once_with('teacher@school.example', False)

    result, _, owi = _update(11, True)
    assert result == {'message': 'User updated successfully'}
    owi.update_user_status.assert_called_once_with('admin@school.example', True)


def test_an_admin_cannot_delete_their_own_account():
    refused, db, owi = _call(r.delete_organization_user, 11)

    assert isinstance(refused, HTTPException) and refused.status_code == 403
    assert 'cannot delete your own account' in refused.detail
    db.delete_creator_user.assert_not_called()
    owi.delete_user.assert_not_called()


def test_an_admin_can_delete_a_member():
    result, db, owi = _call(r.delete_organization_user, 12)

    assert result == {'message': 'User teacher@school.example has been permanently deleted'}
    db.delete_creator_user.assert_called_once_with(12)
    owi.delete_user.assert_called_once_with('teacher@school.example')
