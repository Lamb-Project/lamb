"""
DEPRECATED (2026-02-17): This module is no longer used in the codebase.

All authentication now goes through lamb.auth_context.AuthContext for centralized
validation including the 'enabled' field check.

Migration guide:
- For crypto functions (hash_password, create_token): Use lamb/auth.py
- For authentication dependencies: Use lamb/auth_context.py (get_auth_context)
- For enabled/deleted user checks: Handled automatically by AuthContext

This file is kept for backward compatibility with external integrations (if any).
DO NOT use get_current_active_user() in new code - it duplicates logic that
AuthContext already provides.

Last usage removed: 2026-02-17 (lti_users_router.py migrated to AuthContext)
"""

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status, Depends

from pydantic import BaseModel
from typing import Union, Optional


from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import logging
import os

import requests
import uuid

SESSION_SECRET = os.getenv("SESSION_SECRET", " ")
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
    payload = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        decoded = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        return decoded
    except Exception as e:
        return None


def extract_token_from_auth_header(auth_header: str):
    return auth_header[len("Bearer ") :]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_security),
) -> Optional[dict]:
    token = credentials.credentials
    return token
