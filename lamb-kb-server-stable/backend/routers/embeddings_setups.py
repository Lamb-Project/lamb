"""
Router for embeddings setup management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from database.connection import get_db, get_embedding_function_by_params
from database.models import Organization, EmbeddingsSetup, Collection
from schemas.embeddings_setup import (
    EmbeddingsSetupCreate,
    EmbeddingsSetupResponse,
    EmbeddingsSetupAvailable,
    EmbeddingsSetupUpdate
)
from dependencies import verify_token
from utils.encryption import encrypt_api_key, decrypt_api_key

router = APIRouter(tags=["Embeddings Setups"])


@router.get("/organizations/{org_external_id}/embeddings-setups", response_model=List[EmbeddingsSetupResponse], dependencies=[Depends(verify_token)])
async def list_embeddings_setups(org_external_id: str, db: Session = Depends(get_db)):
    """List all embeddings setups for an organization."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    setups = db.query(EmbeddingsSetup).filter(EmbeddingsSetup.organization_id == org.id).all()

    results = []
    for setup in setups:
        collections_count = db.query(Collection).filter(Collection.embeddings_setup_id == setup.id).count()
        results.append(EmbeddingsSetupResponse(
            id=setup.id,
            name=setup.name,
            setup_key=setup.setup_key,
            vendor=setup.vendor,
            model_name=setup.model_name,
            embedding_dimensions=setup.embedding_dimensions,
            is_default=setup.is_default,
            is_active=setup.is_active,
            api_key_configured=bool(setup.api_key),
            collections_count=collections_count
        ))

    return results


@router.get("/organizations/{org_external_id}/embeddings-setups/available", response_model=List[EmbeddingsSetupAvailable], dependencies=[Depends(verify_token)])
async def get_available_setups(org_external_id: str, db: Session = Depends(get_db)):
    """Get active embeddings setups available for collection creation."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    setups = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.is_active == True
    ).all()

    return [
        EmbeddingsSetupAvailable(
            setup_key=setup.setup_key,
            name=setup.name,
            description=setup.description,
            model_name=setup.model_name,
            embedding_dimensions=setup.embedding_dimensions,
            is_default=setup.is_default
        )
        for setup in setups
    ]


@router.get("/organizations/{org_external_id}/embeddings-setups/{setup_key}", response_model=EmbeddingsSetupResponse, dependencies=[Depends(verify_token)])
async def get_embeddings_setup(org_external_id: str, setup_key: str, db: Session = Depends(get_db)):
    """Get a specific embeddings setup by key."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    setup = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Embeddings setup not found")

    collections_count = db.query(Collection).filter(Collection.embeddings_setup_id == setup.id).count()
    return EmbeddingsSetupResponse(
        id=setup.id,
        name=setup.name,
        setup_key=setup.setup_key,
        vendor=setup.vendor,
        model_name=setup.model_name,
        embedding_dimensions=setup.embedding_dimensions,
        is_default=setup.is_default,
        is_active=setup.is_active,
        api_key_configured=bool(setup.api_key),
        collections_count=collections_count
    )


@router.post("/organizations/{org_external_id}/embeddings-setups", response_model=EmbeddingsSetupResponse, dependencies=[Depends(verify_token)])
async def create_embeddings_setup(org_external_id: str, setup: EmbeddingsSetupCreate, db: Session = Depends(get_db)):
    """Create a new embeddings setup for an organization."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    # Check for duplicate setup_key
    existing = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.setup_key == setup.setup_key
    ).first()
    if existing:
        raise HTTPException(409, "Setup key already exists for this organization")

    # Validate embeddings config by testing it
    try:
        emb_func = get_embedding_function_by_params(
            vendor=setup.vendor,
            model_name=setup.model_name,
            api_key=setup.api_key or "",
            api_endpoint=setup.api_endpoint or ""
        )
        test_emb = emb_func(["test"])
        actual_dims = len(test_emb[0])
        if actual_dims != setup.embedding_dimensions:
            raise HTTPException(400, f"Dimension mismatch: expected {setup.embedding_dimensions}, got {actual_dims}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Invalid embeddings configuration: {str(e)}")

    # Create new setup with encrypted API key
    new_setup = EmbeddingsSetup(
        organization_id=org.id,
        name=setup.name,
        setup_key=setup.setup_key,
        description=setup.description,
        vendor=setup.vendor,
        api_endpoint=setup.api_endpoint,
        api_key=encrypt_api_key(setup.api_key),  # Encrypt before storing
        model_name=setup.model_name,
        embedding_dimensions=setup.embedding_dimensions,
        is_default=setup.is_default,
        is_active=True
    )
    db.add(new_setup)
    
    # SINGLE-DEFAULT ENFORCEMENT: If new setup is default, clear is_default on all others
    if setup.is_default:
        db.query(EmbeddingsSetup).filter(
            EmbeddingsSetup.organization_id == org.id,
            EmbeddingsSetup.setup_key != setup.setup_key
        ).update({"is_default": False})
    
    db.commit()
    db.refresh(new_setup)

    return EmbeddingsSetupResponse(
        id=new_setup.id,
        name=new_setup.name,
        setup_key=new_setup.setup_key,
        vendor=new_setup.vendor,
        model_name=new_setup.model_name,
        embedding_dimensions=new_setup.embedding_dimensions,
        is_default=new_setup.is_default,
        is_active=new_setup.is_active,
        api_key_configured=bool(new_setup.api_key),
        collections_count=0
    )


@router.put("/organizations/{org_external_id}/embeddings-setups/{setup_key}", response_model=EmbeddingsSetupResponse, dependencies=[Depends(verify_token)])
async def update_embeddings_setup(
    org_external_id: str,
    setup_key: str,
    update: EmbeddingsSetupUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an embeddings setup.

    Supports API key rotation and provider migration.
    CRITICAL: Embedding dimensions cannot be changed (would invalidate existing collections).
    """
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    setup = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Setup not found")

    # If changing vendor/model/endpoint, validate that dimensions don't change
    if update.vendor or update.model_name or update.api_endpoint:
        test_vendor = update.vendor or setup.vendor
        test_model = update.model_name or setup.model_name
        test_endpoint = update.api_endpoint or setup.api_endpoint
        test_key = update.api_key or setup.api_key

        try:
            emb_func = get_embedding_function_by_params(
                test_vendor,
                test_model,
                test_key or "",
                test_endpoint or ""
            )
            test_emb = emb_func(["test"])
            new_dims = len(test_emb[0])
            if new_dims != setup.embedding_dimensions:
                raise HTTPException(
                    400,
                    f"Dimension mismatch: setup has {setup.embedding_dimensions} dimensions, "
                    f"new configuration produces {new_dims} dimensions. Cannot change dimensions."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Invalid new configuration: {str(e)}")

    # Apply updates
    if update.name:
        setup.name = update.name
    if update.description is not None:
        setup.description = update.description
    if update.api_key:
        setup.api_key = encrypt_api_key(update.api_key)  # Encrypt before storing
    if update.api_endpoint is not None:
        setup.api_endpoint = update.api_endpoint
    if update.vendor:
        setup.vendor = update.vendor
    if update.model_name:
        setup.model_name = update.model_name
    if update.is_active is not None:
        setup.is_active = update.is_active
    
    # SINGLE-DEFAULT ENFORCEMENT: Handle is_default updates
    if update.is_default is not None:
        if update.is_default:
            # Clear is_default on all other setups in this org
            db.query(EmbeddingsSetup).filter(
                EmbeddingsSetup.organization_id == org.id,
                EmbeddingsSetup.id != setup.id
            ).update({"is_default": False})
        setup.is_default = update.is_default

    db.commit()
    db.refresh(setup)

    collections_count = db.query(Collection).filter(Collection.embeddings_setup_id == setup.id).count()

    return EmbeddingsSetupResponse(
        id=setup.id,
        name=setup.name,
        setup_key=setup.setup_key,
        vendor=setup.vendor,
        model_name=setup.model_name,
        embedding_dimensions=setup.embedding_dimensions,
        is_default=setup.is_default,
        is_active=setup.is_active,
        api_key_configured=bool(setup.api_key),
        collections_count=collections_count
    )


@router.delete("/organizations/{org_external_id}/embeddings-setups/{setup_key}", dependencies=[Depends(verify_token)])
async def delete_embeddings_setup(
    org_external_id: str,
    setup_key: str,
    force: bool = Query(False, description="Force deletion even if collections are using this setup"),
    replacement_setup_key: str = Query(None, description="Migration target setup key (requires force=true)"),
    db: Session = Depends(get_db)
):
    """
    Delete an embeddings setup.

    By default, fails if collections are using this setup.
    With force=true, can optionally migrate collections to a replacement setup.
    """
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    setup = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Setup not found")

    collections_count = db.query(Collection).filter(Collection.embeddings_setup_id == setup.id).count()

    # Check if setup is in use
    if collections_count > 0 and not force:
        raise HTTPException(
            409,
            {
                "error": "setup_in_use",
                "collections_count": collections_count,
                "message": f"Cannot delete setup with {collections_count} active collection(s). Use force=true to override."
            }
        )

    # If force deletion with replacement, migrate collections
    if force and replacement_setup_key:
        replacement = db.query(EmbeddingsSetup).filter(
            EmbeddingsSetup.organization_id == org.id,
            EmbeddingsSetup.setup_key == replacement_setup_key
        ).first()
        if not replacement:
            raise HTTPException(404, f"Replacement setup '{replacement_setup_key}' not found")

        # Verify dimension compatibility
        if replacement.embedding_dimensions != setup.embedding_dimensions:
            raise HTTPException(
                400,
                f"Replacement setup must have same dimensions ({setup.embedding_dimensions}), "
                f"but has {replacement.embedding_dimensions}"
            )

        # Migrate collections
        db.query(Collection).filter(Collection.embeddings_setup_id == setup.id).update(
            {"embeddings_setup_id": replacement.id}
        )

    # Delete setup
    db.delete(setup)
    db.commit()

    return {
        "status": "deleted",
        "collections_migrated": collections_count if (force and replacement_setup_key) else 0
    }
