"""Creator-only connection endpoints. Secret inputs never enter AAC conversation."""
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, SecretStr, StrictBool
from lamb.auth_context import AuthContext, get_auth_context
from .connection import establish_connection, public_connection, MoodleConnectionError
from .policy import MoodleConfigurationError
from .secrets import TokenCipher
from .store import ConnectionStore, ConnectionConflict

router = APIRouter(prefix='/moodle', tags=['Moodle connector'])
PRIVACY_NOTICE = ('Student names, posts and grades reach the AAC driver model, the organization’s configured provider. '
                  'On a local provider they stay on premises; on a hosted one they leave.')

@lru_cache(maxsize=1)
def database():
    from lamb.database_manager import LambDatabaseManager
    return LambDatabaseManager()


def store_for(auth: AuthContext = Depends(get_auth_context)):
    return ConnectionStore(database(), auth.organization['id'], auth.user['id'])


class ConnectBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: SecretStr | None = None
    passport: SecretStr | None = None


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool = False
    base_url: str = ''
    mode: str = 'readonly'
    write_groups: list[str] = []
    allow_grade_write: StrictBool = False


def translate_error(exc):
    if isinstance(exc, MoodleConfigurationError): code = 503
    elif isinstance(exc, PermissionError): code = 403
    elif isinstance(exc, ConnectionConflict): code = 409
    elif isinstance(exc, MoodleConnectionError): code = 400
    else: code = 503
    detail = str(exc) if code != 503 or isinstance(exc, MoodleConfigurationError) else 'Moodle connection storage is unavailable'
    raise HTTPException(code, detail) from None


def settings_view(policy):
    return {'enabled': policy.enabled, 'base_url': policy.base_url, 'mode': policy.mode,
            'write_groups': sorted(policy.write_groups), 'allow_grade_write': policy.allow_grade_write}


@router.get('/connection')
def connection_status(auth: AuthContext = Depends(get_auth_context), store=Depends(store_for)):
    try:
        snap = store.snapshot()
        policy, record = snap['policy'], snap['record']
        connected = bool(policy.enabled and record and record.get('base_url') == policy.base_url)
        setup = (auth.organization.get('config') or {}).get('setups', {}).get('default', {})
        driver = setup.get('aac', {}) or setup.get('global_default_model', {})
        return {'connected': connected, 'connection': public_connection(record) if record else None,
                'settings': settings_view(policy), 'can_configure': bool(auth.is_system_admin or auth.is_org_admin),
                'configured_driver': {k:driver.get(k, '') for k in ('provider', 'model')},
                'privacy_notice': PRIVACY_NOTICE}
    except (MoodleConfigurationError, PermissionError, RuntimeError) as exc:
        translate_error(exc)


@router.post('/connection')
def connect(body: ConnectBody, store=Depends(store_for)):
    try:
        token = body.token.get_secret_value() if body.token is not None else None
        passport = body.passport.get_secret_value() if body.passport is not None else None
        if any(value and len(value) > 8192 for value in (token, passport)):
            raise MoodleConnectionError('Moodle credential input is too long')
        snap = store.snapshot()
        cipher = TokenCipher()
        record = establish_connection(snap['policy'], cipher, organization_id=store.organization_id,
                                      owner_id=store.owner_id, token=token, passport=passport)
        public = store.save(record, expected_generation=snap['generation'], expected_policy=snap['policy'])
        return {'connected': True, 'connection': public}
    except (MoodleConfigurationError, MoodleConnectionError, PermissionError, RuntimeError) as exc:
        translate_error(exc)


@router.delete('/connection')
def disconnect(store=Depends(store_for)):
    try:
        store.disconnect()
        return {'connected': False}
    except (MoodleConfigurationError, PermissionError, RuntimeError) as exc:
        translate_error(exc)


@router.put('/settings')
def configure(body: SettingsBody, auth: AuthContext = Depends(get_auth_context), store=Depends(store_for)):
    if not (auth.is_system_admin or auth.is_org_admin):
        raise HTTPException(403, 'Organization administrator required')
    try:
        # Invalid proposed configuration is a request error; stored invalid configuration is 503.
        return {'settings': store.configure(body.model_dump()), 'privacy_notice': PRIVACY_NOTICE}
    except MoodleConfigurationError as exc:
        raise HTTPException(400, str(exc)) from None
    except (PermissionError, RuntimeError) as exc:
        translate_error(exc)
