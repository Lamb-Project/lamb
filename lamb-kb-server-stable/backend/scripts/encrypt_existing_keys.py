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
from database.models import EmbeddingsSetup
from utils.encryption import encrypt_api_key, is_encrypted, is_encryption_enabled


def encrypt_existing_keys(execute: bool = False) -> dict:
    """
    Encrypt existing plaintext API keys in embeddings_setups table.
    
    Args:
        execute: If True, perform actual encryption. If False, dry run only.
        
    Returns:
        Dictionary with results summary
    """
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
        setups = db.query(EmbeddingsSetup).all()
        results["total_setups"] = len(setups)
        
        print(f"\nFound {len(setups)} embeddings setups")
        print("=" * 60)
        
        for setup in setups:
            setup_desc = f"[{setup.id}] {setup.name} (org_id={setup.organization_id})"
            
            if not setup.api_key:
                results["no_key"] += 1
                print(f"  SKIP (no key): {setup_desc}")
                continue
            
            if is_encrypted(setup.api_key):
                results["already_encrypted"] += 1
                print(f"  SKIP (already encrypted): {setup_desc}")
                continue
            
            results["to_encrypt"] += 1
            
            if execute:
                try:
                    encrypted_key = encrypt_api_key(setup.api_key)
                    setup.api_key = encrypted_key
                    results["encrypted"] += 1
                    print(f"  ENCRYPTED: {setup_desc}")
                except Exception as e:
                    results["errors"].append(f"{setup_desc}: {str(e)}")
                    print(f"  ERROR: {setup_desc} - {e}")
            else:
                # Key preview (first 4 chars only for security)
                key_preview = setup.api_key[:4] + "..." if len(setup.api_key) > 4 else "***"
                print(f"  WOULD ENCRYPT: {setup_desc} (key starts with: {key_preview})")
        
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
