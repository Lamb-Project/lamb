import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# API key from env. Backwards-compatible: fall back to the historical default
# so existing installs keep working, but warn loudly — it must be overridden in
# production (#413).
import sys
API_KEY = os.getenv("LAMB_API_KEY")
if not API_KEY:
    API_KEY = "0p3n-w3bu!"
    print(
        "WARNING [kb-server]: LAMB_API_KEY not set; using the insecure default token. "
        "Set LAMB_API_KEY to a strong value in production.",
        file=sys.stderr,
    )

# Security scheme
security = HTTPBearer(
    scheme_name="Bearer Authentication",
    description="Enter the API token as a Bearer token",
    auto_error=True,
)

# Authentication dependency with detailed docstring
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the provided Bearer token against the API key.
    
    Args:
        credentials: The HTTP Authorization credentials containing the Bearer token
        
    Returns:
        The validated token string
        
    Raises:
        HTTPException: If the token is invalid or missing
    """
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials 