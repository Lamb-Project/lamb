"""Fernet-based encryption for integration credentials at rest.

Reads a 32-byte urlsafe-base64 key from env var `LAMB_INTEGRATIONS_KEY`.
Generate one with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class IntegrationsCryptoError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.environ.get("LAMB_INTEGRATIONS_KEY")
    if not key:
        raise IntegrationsCryptoError(
            "LAMB_INTEGRATIONS_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())" '
            "and add it to backend/.env."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise IntegrationsCryptoError(
            f"LAMB_INTEGRATIONS_KEY is not a valid Fernet key: {exc}"
        ) from exc


def encrypt_config(config: dict[str, Any]) -> str:
    """Serialize a dict to encrypted ciphertext (str)."""
    plaintext = json.dumps(config, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(plaintext).decode("ascii")


def decrypt_config(ciphertext: str) -> dict[str, Any]:
    """Decrypt ciphertext back to a dict. Raises on bad key or tamper."""
    try:
        plaintext = _fernet().decrypt(ciphertext.encode("ascii"))
    except InvalidToken as exc:
        raise IntegrationsCryptoError(
            "Failed to decrypt integration config — wrong key or corrupted ciphertext."
        ) from exc
    return json.loads(plaintext.decode("utf-8"))
