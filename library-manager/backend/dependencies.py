"""FastAPI dependencies for request-level concerns.

The Library Manager trusts requests from LAMB unconditionally when the
bearer token matches. There is no user-level auth here — LAMB handles
that and passes pre-authorized requests.
"""

import hmac

from config import LAMB_API_TOKEN
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """Validate that the request carries the correct LAMB service token.

    Uses ``hmac.compare_digest`` for timing-safe comparison to prevent
    timing attacks that could reveal the token character by character.
    Operands are encoded to bytes first because ``hmac.compare_digest``
    raises ``TypeError`` on ``str`` inputs containing non-ASCII characters;
    comparing bytes keeps the comparison timing-safe while ensuring any
    invalid token (including non-ASCII) is rejected with 401 rather than
    crashing with a 500.

    Args:
        credentials: The Authorization header parsed by HTTPBearer.

    Returns:
        The verified token string.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    if not hmac.compare_digest(
        credentials.credentials.encode("utf-8"), LAMB_API_TOKEN.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token.",
        )
    return credentials.credentials
