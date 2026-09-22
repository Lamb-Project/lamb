"""Authenticated metadata-only storage management; never serve private blobs."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import Literal
from lamb.auth_context import AuthContext, get_auth_context
from lamb.storage_lifecycle import OwnerStorage

router = APIRouter(prefix='/private-storage', tags=['Private storage'])


def owner_storage(auth: AuthContext = Depends(get_auth_context),
                  organization_id: int | None = Query(default=None, gt=0),
                  owner_id: int | None = Query(default=None, gt=0)):
    organization_id = organization_id or int(auth.organization['id'])
    owner_id = owner_id or int(auth.user['id'])
    if (organization_id, owner_id) != (int(auth.organization['id']), int(auth.user['id'])) and not auth.is_system_admin:
        # Org administrators cannot use lifecycle management as a side door into
        # another creator's course evidence. System admins can manage orphans.
        raise HTTPException(403, 'Only system administrators may manage another storage owner')
    try:
        return OwnerStorage(organization_id, owner_id)
    except (OSError, ValueError):
        raise HTTPException(503, 'Private storage is unavailable; check its configured persistent path') from None


def perform(operation):
    try:
        return operation()
    except PermissionError:
        raise HTTPException(404, 'Private storage handle is unavailable') from None
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, 'Storage is busy, protected or requires administrator inspection; no unsafe cleanup was attempted') from None
    except OSError:
        raise HTTPException(503, 'Private storage is unavailable') from None


@router.get('')
def inspect_storage(storage=Depends(owner_storage)):
    return perform(storage.inspect)


@router.post('/cleanup')
def cleanup_storage(storage=Depends(owner_storage)):
    return perform(storage.clean)


@router.delete('/reviews/{review_id}')
def discard_review(review_id: str, storage=Depends(owner_storage)):
    return perform(lambda: storage.discard_review(review_id))


class PurgeOriginalsBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: Literal['purge-private-originals']


@router.post('/imports/{import_id}/purge-originals')
def purge_originals(import_id: str, body: PurgeOriginalsBody, storage=Depends(owner_storage)):
    return perform(lambda: storage.purge_originals(import_id))
