"""
Encryption utilities for API key protection.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Encryption key must be provided via ENCRYPTION_KEY environment variable.

Usage:
    from utils.encryption import encrypt_api_key, decrypt_api_key
    
    # Encrypt before storing
    encrypted = encrypt_api_key("sk-abc123...")
    
    # Decrypt when needed
    plaintext = decrypt_api_key(encrypted)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Encryption key from environment
_ENCRYPTION_KEY: Optional[str] = os.getenv('ENCRYPTION_KEY')

# Lazy-loaded Fernet instance
_fernet = None

# Prefix to identify encrypted values
ENCRYPTED_PREFIX = "enc::"


def _get_fernet():
    """Get or create Fernet instance with the configured key."""
    global _fernet
    
    if _fernet is not None:
        return _fernet
    
    if not _ENCRYPTION_KEY:
        return None
    
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)
        return _fernet
    except Exception as e:
        logger.error(f"Failed to initialize Fernet encryption: {e}")
        return None


def is_encryption_enabled() -> bool:
    """Check if encryption is properly configured."""
    return _get_fernet() is not None


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be already encrypted."""
    if not value:
        return False
    return value.startswith(ENCRYPTED_PREFIX)


def encrypt_api_key(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypt an API key for storage.
    
    Args:
        plaintext: The API key to encrypt
        
    Returns:
        Encrypted string prefixed with 'enc::' or original if encryption disabled
    """
    if not plaintext:
        return plaintext
    
    # Skip if already encrypted
    if is_encrypted(plaintext):
        return plaintext
    
    fernet = _get_fernet()
    if not fernet:
        logger.warning("Encryption not configured - storing API key in plaintext")
        return plaintext
    
    try:
        encrypted_bytes = fernet.encrypt(plaintext.encode('utf-8'))
        return ENCRYPTED_PREFIX + encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt API key: {e}")
        # Return plaintext rather than failing - allows graceful degradation
        return plaintext


def decrypt_api_key(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypt an API key for use.
    
    Args:
        ciphertext: The encrypted API key (with 'enc::' prefix)
        
    Returns:
        Decrypted plaintext API key, or original if not encrypted
    """
    if not ciphertext:
        return ciphertext
    
    # If not encrypted, return as-is (backward compatibility)
    if not is_encrypted(ciphertext):
        return ciphertext
    
    fernet = _get_fernet()
    if not fernet:
        logger.error("Cannot decrypt - encryption key not configured")
        raise ValueError("Encryption key not configured but encrypted value found")
    
    try:
        # Remove prefix and decrypt
        encrypted_part = ciphertext[len(ENCRYPTED_PREFIX):]
        decrypted_bytes = fernet.decrypt(encrypted_part.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        raise ValueError(f"Failed to decrypt API key: {e}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded 32-byte key suitable for ENCRYPTION_KEY env var
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode('utf-8')


# Utility for CLI
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "generate-key":
        print(f"ENCRYPTION_KEY={generate_encryption_key()}")
    else:
        print("Usage: python encryption.py generate-key")
        print(f"Encryption enabled: {is_encryption_enabled()}")
