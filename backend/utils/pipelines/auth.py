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


def get_current_active_user(
    token: str = Depends(get_current_user),
) -> str:
    """
    Validate that the current user exists and is enabled.
    Returns the user email from the token.
    Raises HTTPException 403 if user is disabled or doesn't exist.
    """
    # Decode token to get user email
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    user_email = payload.get("email")
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Check if user exists and is enabled
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    
    user = db.get_creator_user_by_email(user_email)
    
    # User doesn't exist (deleted)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account no longer exists. Please contact your administrator.",
            headers={"X-Account-Status": "deleted"}
        )
    
    # User is disabled
    if not user.get('enabled', True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled. Please contact your administrator.",
            headers={"X-Account-Status": "disabled"}
        )
    
    return user_email
