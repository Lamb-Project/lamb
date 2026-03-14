"""
Router for knowledge store setup management endpoints.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from database.connection import get_db
from database.models import Organization, KnowledgeStoreSetup, Collection
from schemas.knowledge_store_setup import (
    KnowledgeStoreSetupCreate,
    KnowledgeStoreSetupResponse,
    KnowledgeStoreSetupAvailable,
    KnowledgeStoreSetupUpdate
)
from dependencies import verify_token
from utils.encryption import encrypt_api_key
from knowledge_store import get_knowledge_store, list_knowledge_store_plugins

router = APIRouter(tags=["Knowledge Store Setups"])


def _build_plugin_config(setup: KnowledgeStoreSetupCreate) -> dict:
    """Build plugin_config from either explicit plugin_config or legacy shorthand fields."""
    if setup.plugin_config:
        return setup.plugin_config
    # Build from legacy fields (chromadb shorthand)
    config = {}
    if setup.vendor:
        config["vendor"] = setup.vendor
    if setup.model_name:
        config["model"] = setup.model_name
    if setup.api_key:
        config["api_key"] = setup.api_key
    if setup.api_endpoint:
        config["api_endpoint"] = setup.api_endpoint
    if setup.embedding_dimensions:
        config["embedding_dimensions"] = setup.embedding_dimensions
    return config


def _safe_config_summary(plugin_config) -> dict:
    """Return plugin_config with sensitive fields masked."""
    if not plugin_config:
        return {}
    cfg = plugin_config if isinstance(plugin_config, dict) else json.loads(plugin_config)
    safe = {k: v for k, v in cfg.items() if k != "api_key"}
    safe["api_key_configured"] = bool(cfg.get("api_key"))
    return safe


def _to_response(setup: KnowledgeStoreSetup, collections_count: int) -> KnowledgeStoreSetupResponse:
    cfg = setup.plugin_config
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    return KnowledgeStoreSetupResponse(
        id=setup.id,
        name=setup.name,
        setup_key=setup.setup_key,
        plugin_type=setup.plugin_type,
        plugin_config_summary=_safe_config_summary(cfg),
        is_default=setup.is_default,
        is_active=setup.is_active,
        api_key_configured=bool(cfg.get("api_key")) if cfg else False,
        collections_count=collections_count
    )


@router.get(
    "/organizations/{org_external_id}/knowledge-store-setups",
    response_model=List[KnowledgeStoreSetupResponse],
    dependencies=[Depends(verify_token)]
)
async def list_knowledge_store_setups(org_external_id: str, db: Session = Depends(get_db)):
    """List all knowledge store setups for an organization."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        return []

    setups = db.query(KnowledgeStoreSetup).filter(KnowledgeStoreSetup.organization_id == org.id).all()
    return [
        _to_response(s, db.query(Collection).filter(Collection.knowledge_store_setup_id == s.id).count())
        for s in setups
    ]


@router.get(
    "/organizations/{org_external_id}/knowledge-store-setups/available",
    response_model=List[KnowledgeStoreSetupAvailable],
    dependencies=[Depends(verify_token)]
)
async def get_available_setups(org_external_id: str, db: Session = Depends(get_db)):
    """Get active setups available for collection creation."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        return []

    setups = db.query(KnowledgeStoreSetup).filter(
        KnowledgeStoreSetup.organization_id == org.id,
        KnowledgeStoreSetup.is_active == True
    ).all()
    return [
        KnowledgeStoreSetupAvailable(
            setup_key=s.setup_key, name=s.name, description=s.description,
            plugin_type=s.plugin_type, is_default=s.is_default
        )
        for s in setups
    ]


@router.get(
    "/organizations/{org_external_id}/knowledge-store-setups/{setup_key}",
    response_model=KnowledgeStoreSetupResponse,
    dependencies=[Depends(verify_token)]
)
async def get_knowledge_store_setup(org_external_id: str, setup_key: str, db: Session = Depends(get_db)):
    """Get a specific setup by key."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    setup = db.query(KnowledgeStoreSetup).filter(
        KnowledgeStoreSetup.organization_id == org.id,
        KnowledgeStoreSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Setup not found")
    count = db.query(Collection).filter(Collection.knowledge_store_setup_id == setup.id).count()
    return _to_response(setup, count)


@router.post(
    "/organizations/{org_external_id}/knowledge-store-setups",
    response_model=KnowledgeStoreSetupResponse,
    dependencies=[Depends(verify_token)]
)
async def create_knowledge_store_setup(
    org_external_id: str,
    setup: KnowledgeStoreSetupCreate,
    db: Session = Depends(get_db)
):
    """Create a new knowledge store setup."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    existing = db.query(KnowledgeStoreSetup).filter(
        KnowledgeStoreSetup.organization_id == org.id,
        KnowledgeStoreSetup.setup_key == setup.setup_key
    ).first()
    if existing:
        raise HTTPException(409, "Setup key already exists for this organization")

    plugin_config = _build_plugin_config(setup)

    # Validate via plugin
    try:
        plugin = get_knowledge_store(setup.plugin_type)
        validation = plugin.validate_plugin_config(plugin_config)
        if not validation["valid"]:
            raise HTTPException(400, f"Invalid plugin config: {'; '.join(validation['errors'])}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Plugin validation failed: {str(e)}")

    # Encrypt api_key before storing
    stored_config = {**plugin_config}
    if stored_config.get("api_key"):
        stored_config["api_key"] = encrypt_api_key(stored_config["api_key"])

    new_setup = KnowledgeStoreSetup(
        organization_id=org.id,
        name=setup.name,
        setup_key=setup.setup_key,
        description=setup.description,
        plugin_type=setup.plugin_type,
        plugin_config=json.dumps(stored_config),
        is_default=setup.is_default,
        is_active=True
    )
    db.add(new_setup)

    if setup.is_default:
        db.query(KnowledgeStoreSetup).filter(
            KnowledgeStoreSetup.organization_id == org.id,
            KnowledgeStoreSetup.setup_key != setup.setup_key
        ).update({"is_default": False})

    db.commit()
    db.refresh(new_setup)
    return _to_response(new_setup, 0)


@router.put(
    "/organizations/{org_external_id}/knowledge-store-setups/{setup_key}",
    response_model=KnowledgeStoreSetupResponse,
    dependencies=[Depends(verify_token)]
)
async def update_knowledge_store_setup(
    org_external_id: str,
    setup_key: str,
    update: KnowledgeStoreSetupUpdate,
    db: Session = Depends(get_db)
):
    """Update a knowledge store setup."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    setup = db.query(KnowledgeStoreSetup).filter(
        KnowledgeStoreSetup.organization_id == org.id,
        KnowledgeStoreSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Setup not found")

    # Merge plugin_config updates
    current_config = setup.plugin_config
    if isinstance(current_config, str):
        current_config = json.loads(current_config)
    current_config = current_config or {}

    if update.plugin_config:
        current_config.update(update.plugin_config)
    # Apply legacy field overrides
    if update.vendor:
        current_config["vendor"] = update.vendor
    if update.model_name:
        current_config["model"] = update.model_name
    if update.api_endpoint is not None:
        current_config["api_endpoint"] = update.api_endpoint
    if update.api_key:
        current_config["api_key"] = encrypt_api_key(update.api_key)

    # Validate the merged config
    try:
        plugin = get_knowledge_store(setup.plugin_type)
        validation = plugin.validate_plugin_config(current_config)
        if not validation["valid"]:
            raise HTTPException(400, f"Invalid config after update: {'; '.join(validation['errors'])}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Validation failed: {str(e)}")

    setup.plugin_config = json.dumps(current_config)
    if update.name:
        setup.name = update.name
    if update.description is not None:
        setup.description = update.description
    if update.is_active is not None:
        setup.is_active = update.is_active
    if update.is_default is not None:
        if update.is_default:
            db.query(KnowledgeStoreSetup).filter(
                KnowledgeStoreSetup.organization_id == org.id,
                KnowledgeStoreSetup.id != setup.id
            ).update({"is_default": False})
        setup.is_default = update.is_default

    db.commit()
    db.refresh(setup)
    count = db.query(Collection).filter(Collection.knowledge_store_setup_id == setup.id).count()
    return _to_response(setup, count)


@router.delete(
    "/organizations/{org_external_id}/knowledge-store-setups/{setup_key}",
    dependencies=[Depends(verify_token)]
)
async def delete_knowledge_store_setup(
    org_external_id: str,
    setup_key: str,
    force: bool = Query(False),
    replacement_setup_key: str = Query(None),
    db: Session = Depends(get_db)
):
    """Delete a knowledge store setup."""
    org = db.query(Organization).filter(Organization.external_id == org_external_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    setup = db.query(KnowledgeStoreSetup).filter(
        KnowledgeStoreSetup.organization_id == org.id,
        KnowledgeStoreSetup.setup_key == setup_key
    ).first()
    if not setup:
        raise HTTPException(404, "Setup not found")

    count = db.query(Collection).filter(Collection.knowledge_store_setup_id == setup.id).count()

    if count > 0 and not force:
        raise HTTPException(409, {
            "error": "setup_in_use",
            "collections_count": count,
            "message": f"Cannot delete setup with {count} active collection(s). Use force=true."
        })

    if force and replacement_setup_key:
        replacement = db.query(KnowledgeStoreSetup).filter(
            KnowledgeStoreSetup.organization_id == org.id,
            KnowledgeStoreSetup.setup_key == replacement_setup_key
        ).first()
        if not replacement:
            raise HTTPException(404, f"Replacement setup '{replacement_setup_key}' not found")
        db.query(Collection).filter(Collection.knowledge_store_setup_id == setup.id).update(
            {"knowledge_store_setup_id": replacement.id}
        )

    db.delete(setup)
    db.commit()
    return {"status": "deleted", "collections_migrated": count if (force and replacement_setup_key) else 0}


# ── Plugin discovery endpoints ──

@router.get("/knowledge-store-plugins", dependencies=[Depends(verify_token)])
async def list_plugins():
    """List all available knowledge store plugin types."""
    return {"plugins": list_knowledge_store_plugins()}


@router.post("/knowledge-store-plugins/{plugin_type}/validate-config", dependencies=[Depends(verify_token)])
async def validate_plugin_config(plugin_type: str, body: dict):
    """Validate a plugin configuration without creating a setup."""
    try:
        plugin = get_knowledge_store(plugin_type)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return plugin.validate_plugin_config(body.get("plugin_config", body))
