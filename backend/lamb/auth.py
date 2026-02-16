"""
LAMB Native Authentication Module

Provides password hashing and JWT token management for LAMB's own auth,
independent of Open WebUI. Uses the same bcrypt configuration as the OWI
bridge for hash compatibility during the migration period.
"""

import os
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from lamb.logging_config import get_logger

# Suppress the specific passlib warning about bcrypt version
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

logger = get_logger(__name__, component="AUTH")

# Password hashing — same config as owi_users.py for hash compatibility
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=12,
)

# Default token lifetime
DEFAULT_TOKEN_EXPIRY = timedelta(days=7)


def _get_jwt_secret() -> str:
    """Return JWT signing secret, raising at call time (not import time).

    Resolution order: LAMB_JWT_SECRET → WEBUI_SECRET_KEY (from config.py).
    """
    import config
    secret = config.LAMB_JWT_SECRET
    if not secret:
        raise RuntimeError(
            "No JWT secret available. Set LAMB_JWT_SECRET or WEBUI_SECRET_KEY "
            "in backend/.env"
        )
    return secret


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT.

    Args:
        data: Payload dict — should include 'sub' (user id), 'email', 'role'.
        expires_delta: Optional custom expiry. Defaults to 7 days.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or DEFAULT_TOKEN_EXPIRY)
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a LAMB JWT.

    Returns:
        Decoded payload dict, or None if the token is invalid/expired.
    """
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return None
