"""Organization-admin API for creator codes (#467, #562).

An organization admin creates, lists, enables and disables the codes of their own
organization and writes the text an instructor without an account reads. A system admin
does the same for the organization named in `org`; the system organization has no codes,
and its text is the deployment's default.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, StrictBool

from lamb import lti_onboarding, lti_access
from lamb.auth_context import AuthContext, get_auth_context
from .organization_router import db_manager, verify_organization_admin_access

router = APIRouter()


class LmsWhitelist(BaseModel):
    whitelist_enabled: StrictBool = False
    allowed_instances: list[str] = Field(default_factory=list, max_length=lti_access.LIMIT)


class OrganizationLock(BaseModel):
    locked_instances: list[str] = Field(default_factory=list, max_length=lti_access.LIMIT)


@router.get('/lti-access', tags=['Admin - LTI'])
async def get_lms_whitelist(auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    return {**lti_access.global_settings(db_manager), 'seen_instances': lti_access.seen_instances(db_manager)}


@router.put('/lti-access', tags=['Admin - LTI'])
async def set_lms_whitelist(body: LmsWhitelist, auth: AuthContext = Depends(get_auth_context)):
    auth.require_system_admin()
    try:
        settings = lti_access.validate_global(body.model_dump())
        system = db_manager.get_organization_by_slug('lamb')
        if not system:
            raise ValueError('System organization not found.')
        lti_access.save_settings(db_manager, system['id'], settings)
        return {**settings, 'seen_instances': lti_access.seen_instances(db_manager)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _lock_view(organization, auth):
    """What the lock screen shows: the lock, the installation this administrator came in
    from, and the ones already seen launching into the organization. Only a system
    administrator may type an identifier that is neither."""
    return {'locked_instances': lti_access.locked_instances(organization),
            'my_instance': lti_access.session_instance(auth.token_payload),
            'seen_instances': lti_access.seen_instances(db_manager, organization['id']),
            'can_type': bool(auth.is_system_admin),
            **lti_access.global_settings(db_manager)}


@router.get('/org-admin/settings/lti-access', tags=['Organization Admin - Settings'])
async def get_organization_lock(request: Request, org: Optional[str] = None,
                                auth: AuthContext = Depends(get_auth_context)):
    _, organization = await _organization(request, org)
    return _lock_view(organization, auth)


@router.put('/org-admin/settings/lti-access', tags=['Organization Admin - Settings'])
async def set_organization_lock(request: Request, body: OrganizationLock, org: Optional[str] = None,
                                auth: AuthContext = Depends(get_auth_context)):
    _, organization = await _organization(request, org)
    try:
        wanted = lti_access.validate_instances(body.locked_instances)
        view = _lock_view(organization, auth)
        known = view['locked_instances'] + view['seen_instances'] + [view['my_instance']]
        if not auth.is_system_admin and any(v not in known for v in wanted):
            raise ValueError('Choose the LMS you opened LAMB from, or one already used with this organization.')
        if wanted and view['my_instance'] and view['my_instance'] not in wanted:
            raise ValueError('Keep the LMS you are connected from in the list, or you would lock yourself out.')
        lti_access.save_settings(db_manager, organization['id'], {'locked_instances': wanted})
        return _lock_view(db_manager.get_organization_by_id(organization['id']), auth)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class NewCreatorCode(BaseModel):
    label: str = Field("", max_length=lti_onboarding.LABEL_LIMIT, description="What the code is for, e.g. a term or a faculty")
    expires_at: Optional[int] = Field(None, description="Unix time after which the code stops working; null for no expiry")
    max_uses: Optional[int] = Field(None, ge=1, description="How many instructors may use it; null for no limit")


class CreatorCodeState(BaseModel):
    enabled: bool


class OnboardingPageText(BaseModel):
    page_text: str = Field("", max_length=lti_onboarding.PAGE_TEXT_LIMIT)


async def _organization(request: Request, org: Optional[str]):
    target = None
    if org:
        target_organization = db_manager.get_organization_by_slug(org)
        if not target_organization:
            raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")
        target = target_organization['id']
    admin = await verify_organization_admin_access(request, target)
    organization = db_manager.get_organization_by_id(admin['organization_id'])
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return admin, organization


@router.get("/org-admin/settings/creator-codes", tags=["Organization Admin - Settings"],
            summary="List the organization's creator codes and its onboarding text")
async def list_creator_codes(request: Request, org: Optional[str] = None):
    _, organization = await _organization(request, org)
    return {
        "codes": lti_onboarding.list_codes(db_manager, organization["id"]),
        "codes_available": True,
        "page_text": lti_onboarding.own_page_text(organization),
        "effective_page_text": lti_onboarding.page_text(db_manager, [organization["id"]]),
        "default_page_text": lti_onboarding.DEFAULT_PAGE_TEXT,
        "page_text_limit": lti_onboarding.PAGE_TEXT_LIMIT,
    }


@router.post("/org-admin/settings/creator-codes", tags=["Organization Admin - Settings"],
             summary="Create a creator code; the code itself is returned only in this response")
async def create_creator_code(request: Request, body: NewCreatorCode, org: Optional[str] = None):
    admin, organization = await _organization(request, org)
    try:
        return lti_onboarding.create_code(db_manager, organization["id"], body.label, body.expires_at,
                                          body.max_uses, admin.get("user_id"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/org-admin/settings/creator-codes/page-text", tags=["Organization Admin - Settings"],
            summary="Set the text an instructor without an account reads; empty restores the default")
async def update_onboarding_page_text(request: Request, body: OnboardingPageText, org: Optional[str] = None):
    _, organization = await _organization(request, org)
    try:
        text = lti_onboarding.set_page_text(db_manager, organization, body.page_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"page_text": text, "effective_page_text": lti_onboarding.page_text(db_manager, [organization["id"]])}


@router.put("/org-admin/settings/creator-codes/{code_id}", tags=["Organization Admin - Settings"],
            summary="Enable or disable one of the organization's creator codes")
async def update_creator_code(request: Request, code_id: int, body: CreatorCodeState, org: Optional[str] = None):
    _, organization = await _organization(request, org)
    code = lti_onboarding.set_enabled(db_manager, organization["id"], code_id, body.enabled)
    if code is None:
        raise HTTPException(status_code=404, detail="Creator code not found in this organization")
    return code
