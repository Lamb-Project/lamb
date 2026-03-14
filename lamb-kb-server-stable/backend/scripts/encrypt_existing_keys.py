#!/usr/bin/env python3
"""
Script to encrypt existing plaintext API keys in the database.

This script is idempotent - it will only encrypt values that aren't already encrypted.
Encrypted values are prefixed with 'enc::' for identification.

Usage:
    # Dry run (default) - shows what would be encrypted
    python scripts/encrypt_existing_keys.py
    
    # Execute encryption
    python scripts/encrypt_existing_keys.py --execute

Prerequisites:
    - Set ENCRYPTION_KEY environment variable
    - Activate the backend virtual environment
"""

import sys
import os
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import KnowledgeStoreSetup
from utils.encryption import encrypt_api_key, is_encrypted, is_encryption_enabled


def encrypt_existing_keys(execute: bool = False) -> dict:
    """
    Encrypt existing plaintext API keys in knowledge_store_setups table.

    Handles both legacy api_key column and api_key inside plugin_config JSON.

    Args:
        execute: If True, perform actual encryption. If False, dry run only.

    Returns:
        Dictionary with results summary
    """
    import json

    results = {
        "total_setups": 0,
        "already_encrypted": 0,
        "to_encrypt": 0,
        "encrypted": 0,
        "no_key": 0,
        "errors": []
    }

    if not is_encryption_enabled():
        print("ERROR: Encryption key not configured.")
        print("Set ENCRYPTION_KEY environment variable first.")
        print("\nGenerate a key with:")
        print("  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return results

    db: Session = SessionLocal()

    try:
        setups = db.query(KnowledgeStoreSetup).all()
        results["total_setups"] = len(setups)

        print(f"\nFound {len(setups)} knowledge store setups")
        print("=" * 60)

        for setup in setups:
            setup_desc = f"[{setup.id}] {setup.name} (org_id={setup.organization_id})"
            encrypted_any = False

            # Check legacy api_key column
            if setup.api_key:
                if is_encrypted(setup.api_key):
                    results["already_encrypted"] += 1
                    print(f"  SKIP (legacy key already encrypted): {setup_desc}")
                else:
                    results["to_encrypt"] += 1
                    if execute:
                        try:
                            setup.api_key = encrypt_api_key(setup.api_key)
                            encrypted_any = True
                            results["encrypted"] += 1
                            print(f"  ENCRYPTED (legacy): {setup_desc}")
                        except Exception as e:
                            results["errors"].append(f"{setup_desc} (legacy): {str(e)}")
                            print(f"  ERROR (legacy): {setup_desc} - {e}")
                    else:
                        key_preview = setup.api_key[:4] + "..." if len(setup.api_key) > 4 else "***"
                        print(f"  WOULD ENCRYPT (legacy): {setup_desc} (key starts with: {key_preview})")

            # Check api_key inside plugin_config
            plugin_config = setup.plugin_config
            if plugin_config:
                if isinstance(plugin_config, str):
                    try:
                        plugin_config = json.loads(plugin_config)
                    except (json.JSONDecodeError, TypeError):
                        plugin_config = None

                if plugin_config and plugin_config.get("api_key"):
                    pc_key = plugin_config["api_key"]
                    if is_encrypted(pc_key):
                        print(f"  SKIP (plugin_config key already encrypted): {setup_desc}")
                    else:
                        results["to_encrypt"] += 1
                        if execute:
                            try:
                                plugin_config["api_key"] = encrypt_api_key(pc_key)
                                setup.plugin_config = json.dumps(plugin_config)
                                encrypted_any = True
                                results["encrypted"] += 1
                                print(f"  ENCRYPTED (plugin_config): {setup_desc}")
                            except Exception as e:
                                results["errors"].append(f"{setup_desc} (plugin_config): {str(e)}")
                                print(f"  ERROR (plugin_config): {setup_desc} - {e}")
                        else:
                            key_preview = pc_key[:4] + "..." if len(pc_key) > 4 else "***"
                            print(f"  WOULD ENCRYPT (plugin_config): {setup_desc} (key starts with: {key_preview})")

            if not setup.api_key and not (plugin_config and plugin_config.get("api_key")):
                results["no_key"] += 1
                print(f"  SKIP (no key): {setup_desc}")

        if execute and results["encrypted"] > 0:
            db.commit()
            print(f"\n✓ Committed {results['encrypted']} encryption(s) to database")

    except Exception as e:
        results["errors"].append(f"Database error: {str(e)}")
        print(f"\nERROR: {e}")
        db.rollback()
    finally:
        db.close()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Encrypt existing plaintext API keys in the database"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the encryption (default is dry run)"
    )
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("API Key Encryption Script")
    print("=" * 60)
    
    if args.execute:
        print("MODE: EXECUTE - Will encrypt API keys")
    else:
        print("MODE: DRY RUN - No changes will be made")
        print("(Use --execute to perform actual encryption)")
    
    results = encrypt_existing_keys(execute=args.execute)
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"  Total setups:       {results['total_setups']}")
    print(f"  No API key:         {results['no_key']}")
    print(f"  Already encrypted:  {results['already_encrypted']}")
    print(f"  To encrypt:         {results['to_encrypt']}")
    if args.execute:
        print(f"  Successfully encrypted: {results['encrypted']}")
    if results["errors"]:
        print(f"  Errors:             {len(results['errors'])}")
        for err in results["errors"]:
            print(f"    - {err}")
    
    if not args.execute and results["to_encrypt"] > 0:
        print(f"\n⚠️  {results['to_encrypt']} key(s) need encryption.")
        print("Run with --execute to encrypt them.")
    
    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
