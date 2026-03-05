#!/usr/bin/env python3
"""
Migration script to convert OLD MODE collections to NEW MODE.

OLD MODE: Collections with inline embeddings_model JSON config
NEW MODE: Collections referencing organization + embeddings_setup

This script:
1. Finds collections with embeddings_model but no embeddings_setup_id
2. Creates matching EmbeddingsSetup records per org/vendor/model combo
3. Links collections to the appropriate setups
4. Optionally clears the old embeddings_model field

Usage:
    # Dry run (default)
    python scripts/migrate_collections_to_new_mode.py
    
    # Execute migration
    python scripts/migrate_collections_to_new_mode.py --execute
    
    # Keep embeddings_model field after migration (for rollback safety)
    python scripts/migrate_collections_to_new_mode.py --execute --keep-old
"""

import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Collection, Organization, EmbeddingsSetup
from utils.encryption import encrypt_api_key


# Default organization for collections without one
SYSTEM_ORG_EXTERNAL_ID = "system"
SYSTEM_ORG_NAME = "System Organization"


def get_or_create_system_org(db: Session) -> Organization:
    """Get or create the system organization."""
    org = db.query(Organization).filter(
        Organization.external_id == SYSTEM_ORG_EXTERNAL_ID
    ).first()
    
    if not org:
        org = Organization(
            external_id=SYSTEM_ORG_EXTERNAL_ID,
            name=SYSTEM_ORG_NAME
        )
        db.add(org)
        db.flush()
        print(f"  Created system organization: {org.id}")
    
    return org


def generate_setup_key(vendor: str, model: str) -> str:
    """Generate a unique setup key from vendor and model."""
    # Normalize: lowercase, replace special chars
    key = f"{vendor}_{model}".lower()
    key = key.replace("/", "_").replace("-", "_").replace(" ", "_")
    # Limit length
    return key[:80]


def parse_embeddings_model(collection: Collection) -> Optional[Dict[str, Any]]:
    """Parse the embeddings_model JSON from a collection."""
    if not collection.embeddings_model:
        return None
    
    try:
        if isinstance(collection.embeddings_model, str):
            return json.loads(collection.embeddings_model)
        return collection.embeddings_model
    except (json.JSONDecodeError, TypeError):
        return None


def find_or_create_setup(
    db: Session,
    org: Organization,
    vendor: str,
    model: str,
    api_key: Optional[str],
    api_endpoint: Optional[str],
    dimensions: int = 1536
) -> Tuple[EmbeddingsSetup, bool]:
    """
    Find existing setup or create new one.
    
    Returns:
        Tuple of (setup, was_created)
    """
    setup_key = generate_setup_key(vendor, model)
    
    # Look for existing setup with same key
    existing = db.query(EmbeddingsSetup).filter(
        EmbeddingsSetup.organization_id == org.id,
        EmbeddingsSetup.setup_key == setup_key
    ).first()
    
    if existing:
        return existing, False
    
    # Create new setup
    new_setup = EmbeddingsSetup(
        organization_id=org.id,
        name=f"{vendor.title()} - {model}",
        setup_key=setup_key,
        description=f"Migrated from inline config",
        vendor=vendor,
        model_name=model,
        api_endpoint=api_endpoint,
        api_key=encrypt_api_key(api_key) if api_key else None,
        embedding_dimensions=dimensions,
        is_default=False,
        is_active=True
    )
    db.add(new_setup)
    db.flush()
    
    return new_setup, True


def migrate_collections(execute: bool = False, keep_old: bool = False) -> dict:
    """
    Migrate OLD MODE collections to NEW MODE.
    
    Args:
        execute: If True, perform actual migration. If False, dry run.
        keep_old: If True, don't clear embeddings_model after migration.
        
    Returns:
        Dictionary with migration results
    """
    results = {
        "total_collections": 0,
        "already_new_mode": 0,
        "to_migrate": 0,
        "migrated": 0,
        "setups_created": 0,
        "setups_reused": 0,
        "errors": [],
        "migration_log": []
    }
    
    db: Session = SessionLocal()
    
    try:
        # Find collections that need migration (OLD MODE = has embeddings_model, no setup_id)
        all_collections = db.query(Collection).all()
        results["total_collections"] = len(all_collections)
        
        print(f"\nFound {len(all_collections)} total collections")
        print("=" * 70)
        
        for collection in all_collections:
            coll_desc = f"[{collection.id}] {collection.name} (owner: {collection.owner})"
            
            # Check if already using NEW MODE
            if collection.embeddings_setup_id:
                results["already_new_mode"] += 1
                print(f"  SKIP (already NEW MODE): {coll_desc}")
                continue
            
            # Parse old config
            config = parse_embeddings_model(collection)
            if not config:
                results["errors"].append(f"{coll_desc}: No valid embeddings_model config")
                print(f"  SKIP (no config): {coll_desc}")
                continue
            
            results["to_migrate"] += 1
            
            # Extract config values
            vendor = config.get("vendor", "local")
            model = config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
            api_key = config.get("apikey")
            api_endpoint = config.get("api_endpoint") or config.get("endpoint")
            
            # Determine dimensions (default varies by vendor)
            if vendor.lower() == "openai":
                dimensions = 1536
            elif vendor.lower() in ("ollama", "local"):
                dimensions = 768
            else:
                dimensions = 384
            
            if execute:
                try:
                    # Get or create organization
                    if collection.organization_id:
                        org = db.query(Organization).filter(
                            Organization.id == collection.organization_id
                        ).first()
                        if not org:
                            org = get_or_create_system_org(db)
                    else:
                        org = get_or_create_system_org(db)
                    
                    # Find or create setup
                    setup, was_created = find_or_create_setup(
                        db, org, vendor, model, api_key, api_endpoint, dimensions
                    )
                    
                    if was_created:
                        results["setups_created"] += 1
                    else:
                        results["setups_reused"] += 1
                    
                    # Update collection
                    collection.organization_id = org.id
                    collection.embeddings_setup_id = setup.id
                    collection.embedding_dimensions = dimensions
                    
                    if not keep_old:
                        collection.embeddings_model = None
                    
                    results["migrated"] += 1
                    results["migration_log"].append({
                        "collection_id": collection.id,
                        "collection_name": collection.name,
                        "org_id": org.id,
                        "setup_id": setup.id,
                        "setup_key": setup.setup_key
                    })
                    
                    action = "created" if was_created else "reused"
                    print(f"  MIGRATED: {coll_desc} -> setup:{setup.setup_key} ({action})")
                    
                except Exception as e:
                    results["errors"].append(f"{coll_desc}: {str(e)}")
                    print(f"  ERROR: {coll_desc} - {e}")
            else:
                setup_key = generate_setup_key(vendor, model)
                print(f"  WOULD MIGRATE: {coll_desc}")
                print(f"    vendor={vendor}, model={model} -> setup_key={setup_key}")
        
        if execute and results["migrated"] > 0:
            db.commit()
            print(f"\n✓ Committed {results['migrated']} migration(s) to database")
            
            # Save migration log for potential rollback
            log_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            try:
                with open(log_path, 'w') as f:
                    json.dump(results["migration_log"], f, indent=2)
                print(f"✓ Migration log saved to: {log_path}")
            except Exception as e:
                print(f"⚠️  Could not save migration log: {e}")
        
    except Exception as e:
        results["errors"].append(f"Database error: {str(e)}")
        print(f"\nERROR: {e}")
        db.rollback()
    finally:
        db.close()
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Migrate OLD MODE collections to NEW MODE with embeddings setups"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration (default is dry run)"
    )
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Keep embeddings_model field after migration (for rollback safety)"
    )
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("Collection Migration Script: OLD MODE -> NEW MODE")
    print("=" * 70)
    
    if args.execute:
        print("MODE: EXECUTE - Will migrate collections")
        if args.keep_old:
            print("      (keeping old embeddings_model field)")
    else:
        print("MODE: DRY RUN - No changes will be made")
        print("(Use --execute to perform actual migration)")
    
    results = migrate_collections(execute=args.execute, keep_old=args.keep_old)
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"  Total collections:    {results['total_collections']}")
    print(f"  Already NEW MODE:     {results['already_new_mode']}")
    print(f"  To migrate:           {results['to_migrate']}")
    if args.execute:
        print(f"  Successfully migrated: {results['migrated']}")
        print(f"  Setups created:       {results['setups_created']}")
        print(f"  Setups reused:        {results['setups_reused']}")
    if results["errors"]:
        print(f"  Errors:               {len(results['errors'])}")
        for err in results["errors"][:5]:  # Show first 5 errors
            print(f"    - {err}")
        if len(results["errors"]) > 5:
            print(f"    ... and {len(results['errors']) - 5} more")
    
    if not args.execute and results["to_migrate"] > 0:
        print(f"\n⚠️  {results['to_migrate']} collection(s) need migration.")
        print("Run with --execute to migrate them.")
    
    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
