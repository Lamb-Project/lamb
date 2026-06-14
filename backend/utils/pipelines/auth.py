from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status, Depends

from pydantic import BaseModel
from typing import Union, Optional


from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import logging
import os
import warnings

# passlib 1.7.4 + bcrypt 4.x: bcrypt removed __about__ module, passlib can't read version.
# This is harmless — passlib falls back gracefully. Suppress the noise.
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

import requests
import uuid

# No insecure fallback: signing without a configured secret must fail closed.
SESSION_SECRET = os.getenv("SESSION_SECRET")
ALGORITHM = "HS256"

##############
# Auth Utils
##############

bearer_security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return (
        pwd_context.verify(plain_password, hashed_password) if hashed_password else None
    )


def get_password_hash(password):
    return pwd_context.hash(password)


def create_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    if not SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET environment variable is required to sign tokens")
    payload = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    if not SESSION_SECRET:
        return None
    try:
        decoded = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        return decoded
    except Exception as e:
        return None


def extract_token_from_auth_header(auth_header: str):
    return auth_header[len("Bearer ") :]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_security),
) -> str:
    """Validate the bearer token against the system API key.

    Previously this returned the token unconditionally, so any
    ``Authorization: Bearer <anything>`` header was accepted. The
    endpoints that depend on this (legacy LTI-users routes, the
    pipelines reload endpoint) are system/admin surfaces and require
    the LAMB system token. (#410)
    """
    import config

    token = credentials.credentials
    if not token or token != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
        )
    return token
