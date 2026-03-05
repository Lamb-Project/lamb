"""
Router for organization management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Organization, EmbeddingsSetup, Collection
from schemas.organization import OrganizationCreate, OrganizationResponse
from dependencies import verify_token

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("/", response_model=OrganizationResponse, dependencies=[Depends(verify_token)])
async def create_or_update_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    """
    Create or update organization (upsert).

    If an organization with the given external_id exists, it will be updated.
    Otherwise, a new organization will be created.
    """
    existing = db.query(Organization).filter(Organization.external_id == org.external_id).first()

    if existing:
        existing.name = org.name
        db.commit()
        db.refresh(existing)

        # Count setups and collections
        setups_count = db.query(EmbeddingsSetup).filter(EmbeddingsSetup.organization_id == existing.id).count()
        collections_count = db.query(Collection).filter(Collection.organization_id == existing.id).count()

        return OrganizationResponse(
            id=existing.id,
            external_id=existing.external_id,
            name=existing.name,
            created_at=existing.created_at,
            setups_count=setups_count,
            collections_count=collections_count
        )

    new_org = Organization(external_id=org.external_id, name=org.name)
    db.add(new_org)
    db.commit()
    db.refresh(new_org)

    return OrganizationResponse(
        id=new_org.id,
        external_id=new_org.external_id,
        name=new_org.name,
        created_at=new_org.created_at,
        setups_count=0,
        collections_count=0
    )


@router.get("/{external_id}", response_model=OrganizationResponse, dependencies=[Depends(verify_token)])
async def get_organization(external_id: str, db: Session = Depends(get_db)):
    """Get organization by external_id."""
    org = db.query(Organization).filter(Organization.external_id == external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    # Count setups and collections
    setups_count = db.query(EmbeddingsSetup).filter(EmbeddingsSetup.organization_id == org.id).count()
    collections_count = db.query(Collection).filter(Collection.organization_id == org.id).count()

    return OrganizationResponse(
        id=org.id,
        external_id=org.external_id,
        name=org.name,
        created_at=org.created_at,
        setups_count=setups_count,
        collections_count=collections_count
    )
