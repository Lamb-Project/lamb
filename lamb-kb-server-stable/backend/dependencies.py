import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Get API key from environment variable (required; no insecure default) (#413)
API_KEY = os.getenv("LAMB_API_KEY")
if not API_KEY:
    raise RuntimeError("LAMB_API_KEY environment variable is required")

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