"""Creator-only connection endpoints. Secret inputs never enter AAC conversation."""
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr, StrictBool
from lamb.auth_context import AuthContext, get_auth_context
from .connection import establish_connection, public_connection, MoodleConnectionError
from .policy import MoodleConfigurationError
from .secrets import TokenCipher
from .store import ConnectionStore, ConnectionConflict

router = APIRouter(prefix='/moodle', tags=['Moodle connector'])


class TaskBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command: str


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


def effective_driver(auth):
    from lamb.aac.driver import resolve_driver, public_driver
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    try:
        return public_driver(resolve_driver(OrganizationConfigResolver(auth.user['email'])))
    except HTTPException as exc:
        # Users must still be able to disconnect or repair connector settings.
        return {'provider': '', 'model': '', 'error': exc.detail}


@router.get('/connection')
def connection_status(auth: AuthContext = Depends(get_auth_context), store=Depends(store_for)):
    try:
        snap = store.snapshot()
        policy, record = snap['policy'], snap['record']
        connected = bool(policy.enabled and record and record.get('base_url') == policy.base_url)
        driver = effective_driver(auth)
        return {'connected': connected, 'connection': public_connection(record) if record else None,
                'settings': settings_view(policy), 'can_configure': bool(auth.is_system_admin or auth.is_org_admin),
                'effective_driver': driver,
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


@router.post('/connection/qr-image')
async def connect_qr_image(request: Request, store=Depends(store_for)):
    # Raw body avoids multipart temporary-file spooling. Authentication runs first.
    from starlette.concurrency import run_in_threadpool
    from .qr_image import MAX_IMAGE_BYTES, decode_passport
    data = bytearray()
    try:
        snap = store.snapshot()
        snap['policy'].require_connection_url(snap['policy'].base_url)
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_IMAGE_BYTES:
                raise HTTPException(413, 'Select a QR image smaller than 5 MiB.')
            data.extend(chunk)
        passport = await run_in_threadpool(decode_passport, bytes(data))
        # Reuse site/identity verification, encrypted persistence and generation guard.
        return await run_in_threadpool(connect, ConnectBody(passport=passport), store)
    except (MoodleConfigurationError, MoodleConnectionError, PermissionError, RuntimeError) as exc:
        translate_error(exc)
    finally:
        data.clear()


@router.post('/tasks')
def run_task(body: TaskBody, store=Depends(store_for)):
    from .contract import prepare_moodle
    from .task_contract import task_specs
    from .runtime import MoodleRuntime
    try:
        if len(body.command) > 4096:
            raise ValueError('Moodle task command is too long')
        spec, params = prepare_moodle(body.command)
        if spec.key not in task_specs():
            raise ValueError('This endpoint accepts Moodle news, continue, runs and evidence tasks only')
        return MoodleRuntime(store).execute(spec.key, params)
    except ValueError as exc:
        if isinstance(exc, MoodleConfigurationError): translate_error(exc)
        raise HTTPException(400, str(exc)) from None
    except PermissionError as exc:
        translate_error(exc)
    except Exception:
        raise HTTPException(503, 'Moodle task could not finish. Check the connection and retry.') from None


@router.get('/results/{result_id}')
def task_result(result_id: str, store=Depends(store_for)):
    from .runtime import MoodleRuntime
    try:
        return MoodleRuntime(store).task('evidence', {'result_id': result_id}, full=True)
    except PermissionError as exc:
        raise HTTPException(404, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Moodle evidence cannot be verified now. Try again later.') from None
