"""Public OIDC/key endpoints and system-admin-only registration management."""
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lamb.auth_context import AuthContext, get_auth_context
from .keys import KeyRing
from .network import checked_url, origin
from .protocol import begin_login, target_url
from .store import Store

router = APIRouter()


class Registration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=2048)
    client_id: str = Field(min_length=1, max_length=255)
    authorization_url: str
    token_url: str
    jwks_url: str
    deployment_ids: list[str] = Field(min_length=1, max_length=100)
    organization_ids: list[int] = Field(min_length=1, max_length=100)
    service_origins: list[str] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @field_validator('issuer', 'authorization_url', 'token_url', 'jwks_url')
    @classmethod
    def valid_url(cls, value):
        return checked_url(value)

    @field_validator('issuer')
    @classmethod
    def issuer_url(cls, value):
        if urlsplit(value).query:
            raise ValueError('Issuer must not contain a query')
        return value

    @field_validator('deployment_ids')
    @classmethod
    def valid_deployments(cls, values):
        if any(not value or len(value) > 1024 for value in values) or len(values) != len(set(values)):
            raise ValueError('Deployment IDs must be nonempty and unique')
        return values

    @field_validator('organization_ids')
    @classmethod
    def valid_orgs(cls, values):
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError('Organization IDs must be positive and unique')
        return values

    @field_validator('service_origins')
    @classmethod
    def valid_origins(cls, values):
        for value in values:
            if value != origin(value):
                raise ValueError('Service origins must contain only scheme, host and optional port')
        return list(dict.fromkeys(values))


class IdentityLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    deployment_id: str = Field(min_length=1, max_length=1024)
    subject: str = Field(min_length=1, max_length=255)
    creator_user_id: int = Field(gt=0)


@router.api_route('/login', methods=['GET', 'POST'])
async def login(request: Request):
    params = request.query_params if request.method == 'GET' else await request.form()
    if any(len(params.getlist(key)) != 1 for key in params):
        raise HTTPException(400, 'Duplicate OIDC login parameter')
    try:
        return begin_login(dict(params))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/jwks')
def jwks():
    return JSONResponse(KeyRing().public(), headers={'Cache-Control': 'public, max-age=300'})


@router.get('/registration-info')
async def registration_info():
    try:
        launch = target_url()
    except ValueError as exc:
        raise HTTPException(503, 'Configure an HTTPS LAMB_PUBLIC_BASE_URL for LTI 1.3') from exc
    base = launch.rsplit('/', 1)[0]
    return {'version': '1.3.0', 'login_url': base + '/login', 'launch_url': launch,
            'redirect_uris': [launch], 'jwks_url': base + '/jwks',
            'services': ['AGS score'], 'registration': 'manual'}


@router.get('/registrations')
async def registrations(auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    return Store().registrations()


def save(body, registration_id=None):
    store = Store()
    for org_id in body.organization_ids:
        if not store.db.get_organization_by_id(org_id):
            raise HTTPException(422, 'Unknown organization ID')
    try:
        return {'id': store.save_registration(body.model_dump(), registration_id)}
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(409, 'Registration conflicts with existing data' if isinstance(exc, sqlite3.IntegrityError)
                            else str(exc)) from exc


@router.post('/registrations', status_code=201)
async def create_registration(body: Registration, auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    return save(body)


@router.put('/registrations/{registration_id}')
async def update_registration(registration_id: int, body: Registration,
                              auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    return save(body, registration_id)


@router.post('/registrations/{registration_id}/identity-links', status_code=201)
async def link_identity(registration_id: int, body: IdentityLink,
                        auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    store = Store()
    try:
        reg = store.registration(registration_id, body.deployment_id)
        creator = store.db.get_creator_user_by_id(body.creator_user_id)
        if not creator or not creator.get('enabled', True) or creator['organization_id'] not in reg['organization_ids']:
            raise ValueError('Creator account is not allowed for this LMS registration')
        user = store.object_id(registration_id, body.deployment_id, 'user', body.subject)
        store.link_creator(user, body.creator_user_id)
        return {'user_id': user, 'creator_user_id': body.creator_user_id}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/keys/rotate')
async def rotate_keys(auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    return {'kid': KeyRing().rotate(), 'previous_public_key_retention_seconds': 86400}
