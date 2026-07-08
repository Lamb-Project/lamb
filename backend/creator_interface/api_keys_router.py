"""Creator API keys — issuance, listing and revocation.

A creator user can mint personal API keys that expose *their own* published
assistants through the OpenAI-compatible facade (`/v1/models`,
`/v1/chat/completions`). The capability is gated per organization by the
`api_access` feature flag.

The plaintext key is shown exactly once, at creation. Only its SHA-256 hash
is stored; listing returns metadata (prefix, label, status, timestamps),
never the key.
"""

import hashlib
import secrets
import time
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from lamb.auth_context import AuthContext, get_auth_context
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__)
security = HTTPBearer()
router = APIRouter()
db = LambDatabaseManager()

KEY_PREFIX = "lamb_ak_"


class CreateKeyBody(BaseModel):
    label: Optional[str] = None
    expires_in_days: Optional[int] = None


class CreatedKey(BaseModel):
    id: int
    api_key: str          # full key — shown ONCE
    key_prefix: str
    label: Optional[str]
    expires_at: Optional[int]


class KeyInfo(BaseModel):
    id: int
    key_prefix: str
    label: Optional[str]
    status: str
    created_at: int
    last_used_at: Optional[int]
    expires_at: Optional[int]


def _require_api_access(auth: AuthContext) -> None:
    if not auth.features.get("api_access"):
        raise HTTPException(
            status_code=403,
            detail="API access is not enabled for this organization.",
        )


@router.post("", response_model=CreatedKey, status_code=201,
             dependencies=[Depends(security)])
async def create_key(body: CreateKeyBody,
                     auth: AuthContext = Depends(get_auth_context)):
    """Mint a new API key for the current creator user."""
    _require_api_access(auth)

    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:16]

    expires_at = None
    if body.expires_in_days and body.expires_in_days > 0:
        expires_at = int(time.time()) + body.expires_in_days * 86400

    key_id = db.create_api_key(
        key_hash=key_hash,
        key_prefix=key_prefix,
        creator_user_id=auth.user["id"],
        organization_id=auth.organization["id"],
        label=body.label,
        expires_at=expires_at,
    )
    if key_id is None:
        raise HTTPException(status_code=500, detail="Could not create API key.")

    logger.info(f"API key {key_id} created for user {auth.user.get('email')}")
    return CreatedKey(id=key_id, api_key=raw, key_prefix=key_prefix,
                      label=body.label, expires_at=expires_at)


@router.get("", response_model=List[KeyInfo], dependencies=[Depends(security)])
async def list_keys(auth: AuthContext = Depends(get_auth_context)):
    """List the current user's API keys (metadata only)."""
    _require_api_access(auth)
    return db.list_api_keys_for_user(auth.user["id"])


@router.delete("/{key_id}", status_code=204, dependencies=[Depends(security)])
async def revoke_key(key_id: int, auth: AuthContext = Depends(get_auth_context)):
    """Revoke one of the current user's API keys."""
    _require_api_access(auth)
    if not db.revoke_api_key(key_id, auth.user["id"]):
        raise HTTPException(status_code=404, detail="Key not found.")
    return None
