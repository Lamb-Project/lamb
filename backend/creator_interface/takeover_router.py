"""Administrators acting as a creator for support (#523)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lamb.auth_context import AuthContext, get_auth_context
from lamb.services import takeover

router = APIRouter()


class AckBody(BaseModel):
    ids: List[str]


def _claim(auth: AuthContext):
    claim = auth.token_payload.get("takeover")
    return claim if isinstance(claim, dict) else None


@router.post("/admin/users/{user_id}/takeover", tags=["Takeover"],
             summary="Act as a creator (system or organization administrator)")
async def start_takeover(user_id: int, auth: AuthContext = Depends(get_auth_context)):
    try:
        return takeover.start(auth, user_id)
    except takeover.TakeoverRefused as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/takeover/current", tags=["Takeover"], summary="The takeover this session belongs to, if any")
async def current_takeover(auth: AuthContext = Depends(get_auth_context)):
    claim = _claim(auth)
    if not claim:
        return {"active": False}
    return {"active": True, "takeover_id": claim.get("id"), "expires_at": claim.get("expires_at"),
            "actor": claim.get("actor"),
            "user": {"id": auth.user.get("id"), "name": auth.user.get("name"), "email": auth.user.get("email")}}


@router.post("/takeover/end", tags=["Takeover"], summary="End the takeover this session belongs to")
async def end_takeover(auth: AuthContext = Depends(get_auth_context)):
    claim = _claim(auth)
    if not claim:
        raise HTTPException(status_code=400, detail="This session is not a takeover.")
    return {"ended": takeover.end(claim, "ended")}


@router.get("/user/takeover-notices", tags=["Takeover"],
            summary="Administrators who acted on your account, not yet dismissed")
async def takeover_notices(auth: AuthContext = Depends(get_auth_context)):
    if _claim(auth):
        return {"notices": []}  # shown to the creator, not to the administrator acting as them
    return {"notices": takeover.notices(auth.user["id"])}


@router.post("/user/takeover-notices/ack", tags=["Takeover"], summary="Dismiss takeover notices")
async def acknowledge_notices(body: AckBody, auth: AuthContext = Depends(get_auth_context)):
    if _claim(auth):
        raise HTTPException(status_code=403, detail="Notices can be dismissed only by the account owner.")
    return {"acknowledged": takeover.acknowledge(auth.user["id"], body.ids)}
