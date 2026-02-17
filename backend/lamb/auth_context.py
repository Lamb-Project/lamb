"""
LAMB AuthContext — Centralized Authentication and Authorization Manager

Provides a single AuthContext dataclass that is built once per request via
FastAPI ``Depends()``, replacing the scattered auth-check patterns throughout
the codebase.

Usage in route handlers::

    from lamb.auth_context import get_auth_context, get_optional_auth_context, require_admin, AuthContext

    # Standard auth (most endpoints)
    async def my_endpoint(auth: AuthContext = Depends(get_auth_context)):
        ...

    # Optional auth (e.g. /completions/list)
    async def list_stuff(auth: Optional[AuthContext] = Depends(get_optional_auth_context)):
        ...

    # Admin-only shortcut
    async def admin_endpoint(auth: AuthContext = Depends(require_admin)):
        ...
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AUTH_CTX")

# Shared DB manager instance
_db = LambDatabaseManager()


# ---------------------------------------------------------------------------
# AuthContext dataclass
# ---------------------------------------------------------------------------

@dataclass
class AuthContext:
    """Complete authentication and authorization context for a request.

    Built once per request by ``get_auth_context`` / ``get_optional_auth_context``.
    Route handlers receive this instead of a raw user dict and can use its
    typed properties and on-demand resource checkers.
    """

    # --- Identity (always loaded) ---
    user: Dict[str, Any]
    """Creator_users row (id, email, name, user_type, user_config, …)."""

    token_payload: Dict[str, Any]
    """Raw JWT claims (sub, email, role, exp, iat)."""

    # --- Roles (always loaded) ---
    is_system_admin: bool = False
    """True when the JWT ``role`` claim is ``"admin"``."""

    organization_role: Optional[str] = None
    """``"owner"`` | ``"admin"`` | ``"member"`` | ``None``."""

    is_org_admin: bool = False
    """True when ``organization_role`` is ``"owner"`` or ``"admin"``."""

    # --- Organization (always loaded) ---
    organization: Dict[str, Any] = field(default_factory=dict)
    """Full org dict (id, name, slug, is_system, config, …)."""

    # --- Org Features (always loaded, from org config) ---
    features: Dict[str, Any] = field(default_factory=dict)
    """Feature flags from ``organization.config.features``."""

    # ------------------------------------------------------------------
    # Resource-level access checkers (on-demand, query DB per call)
    # ------------------------------------------------------------------

    def can_access_assistant(self, assistant_id: int) -> str:
        """Check user's access level for an assistant.

        Returns:
            ``"owner"`` | ``"org_admin"`` | ``"shared"`` | ``"none"``
        """
        assistant = _db.get_assistant_by_id_with_publication(assistant_id)
        if not assistant:
            return "none"

        # Owner check
        if assistant.get("owner") == self.user.get("email"):
            return "owner"

        # System admin can access anything
        if self.is_system_admin:
            return "org_admin"

        # Org admin for the assistant's organization
        if self.is_org_admin and assistant.get("organization_id") == self.organization.get("id"):
            return "org_admin"

        # Shared with user
        user_id = self.user.get("id")
        if user_id and _db.is_assistant_shared_with_user(assistant_id, user_id):
            return "shared"

        # Same organization (for usage/chat, not modification)
        if assistant.get("organization_id") == self.organization.get("id"):
            return "shared"

        return "none"

    def can_modify_assistant(self, assistant_id: int) -> bool:
        """True if the user is the assistant owner or a system admin."""
        level = self.can_access_assistant(assistant_id)
        return level in ("owner",) or self.is_system_admin

    def can_delete_assistant(self, assistant_id: int) -> bool:
        """True if the user is the assistant owner or a system admin."""
        return self.can_modify_assistant(assistant_id)

    def can_access_kb(self, kb_id: str) -> str:
        """Check user's access level for a knowledge base.

        Returns:
            ``"owner"`` | ``"shared"`` | ``"none"``
        """
        user_id = self.user.get("id")
        if not user_id:
            return "none"

        can_access, access_type = _db.user_can_access_kb(kb_id, user_id)
        if can_access:
            return access_type

        # System admin override
        if self.is_system_admin:
            return "owner"

        return "none"

    # ------------------------------------------------------------------
    # Guard methods (raise HTTPException on denial)
    # ------------------------------------------------------------------

    def require_system_admin(self) -> None:
        """Raise ``HTTPException(403)`` if not a system admin."""
        if not self.is_system_admin:
            logger.warning(
                f"System admin required — denied for user {self.user.get('email')} "
                f"(role={self.token_payload.get('role')})"
            )
            raise HTTPException(status_code=403, detail="System administrator privileges required")

    def require_org_admin(self) -> None:
        """Raise ``HTTPException(403)`` if not org admin or system admin."""
        if not self.is_org_admin and not self.is_system_admin:
            logger.warning(
                f"Org admin required — denied for user {self.user.get('email')} "
                f"(org_role={self.organization_role})"
            )
            raise HTTPException(
                status_code=403,
                detail="Organization administrator privileges required",
            )

    def require_assistant_access(self, assistant_id: int, level: str = "any") -> str:
        """Raise ``HTTPException(403/404)`` if access is insufficient.

        Args:
            assistant_id: The assistant to check.
            level: Required level — ``"any"``, ``"owner_or_admin"``, ``"owner"``.

        Returns:
            The actual access level string so callers can branch if needed.
        """
        access = self.can_access_assistant(assistant_id)

        if access == "none":
            # Use 404 to avoid leaking existence information
            raise HTTPException(status_code=404, detail="Assistant not found")

        if level == "owner" and access != "owner" and not self.is_system_admin:
            raise HTTPException(status_code=403, detail="Only the assistant owner can perform this action")

        if level == "owner_or_admin" and access not in ("owner", "org_admin"):
            raise HTTPException(status_code=403, detail="Insufficient permissions for this assistant")

        return access

    def require_kb_access(self, kb_id: str, level: str = "any") -> str:
        """Raise ``HTTPException(403/404)`` if KB access is insufficient.

        Args:
            kb_id: The knowledge base UUID to check.
            level: Required level — ``"any"``, ``"owner"``.

        Returns:
            The actual access level string.
        """
        access = self.can_access_kb(kb_id)

        if access == "none":
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if level == "owner" and access != "owner":
            raise HTTPException(status_code=403, detail="Only the knowledge base owner can perform this action")

        return access

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable permissions summary (for logging/debugging)."""
        return {
            "user": {
                "id": self.user.get("id"),
                "email": self.user.get("email"),
                "name": self.user.get("name"),
                "user_type": self.user.get("user_type"),
            },
            "roles": {
                "is_system_admin": self.is_system_admin,
                "organization_role": self.organization_role,
                "is_org_admin": self.is_org_admin,
            },
            "organization": {
                "id": self.organization.get("id"),
                "name": self.organization.get("name"),
                "slug": self.organization.get("slug"),
                "is_system": self.organization.get("is_system", False),
            },
            "features": self.features,
        }


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

def _build_auth_context(token: str) -> Optional[AuthContext]:
    """Authenticate user from a Bearer token and build a full AuthContext.

    Tries LAMB native JWT first; falls back to OWI token validation for
    pre-migration tokens.

    Returns:
        An ``AuthContext`` instance, or ``None`` if the token is invalid.
    """
    # --- 1. Decode token (LAMB JWT first, OWI fallback) ---
    from lamb.auth import decode_token as lamb_decode

    payload = lamb_decode(token)
    jwt_role: Optional[str] = None

    if payload:
        user_email = payload.get("email", "")
        jwt_role = payload.get("role")
        if not user_email:
            logger.error("No email in LAMB JWT payload")
            return None
        logger.debug(f"LAMB JWT authenticated: {user_email}")
    else:
        # OWI fallback
        try:
            from lamb.owi_bridge.owi_users import OwiUserManager
            owi = OwiUserManager()
            owi_user = owi.get_user_auth(token)
            if not owi_user:
                logger.debug("Both LAMB JWT and OWI token validation failed")
                return None
            user_email = owi_user.get("email", "")
            jwt_role = owi_user.get("role")
            if not user_email:
                logger.error("No email in OWI token response")
                return None
            # Construct a minimal payload dict for consistency
            payload = {"email": user_email, "role": jwt_role, "sub": owi_user.get("id")}
            logger.debug(f"OWI token authenticated: {user_email}")
        except Exception as e:
            logger.error(f"OWI fallback failed: {e}")
            return None

    # --- 2. Load creator user from DB ---
    creator_user = _db.get_creator_user_by_email(user_email)
    if not creator_user:
        logger.error(f"No creator user found for email: {user_email}")
        return None

    if not creator_user.get('enabled', True):
        logger.warning(f"Disabled user {user_email} attempted API access")
        raise HTTPException(
            status_code=403,
            detail="Account has been disabled. Please contact your administrator.",
            headers={"X-Account-Status": "disabled"}
        )
        
    # Use JWT role as authoritative; fall back to DB role
    effective_role = jwt_role or creator_user.get("role", "user")
    creator_user["role"] = effective_role

    is_system_admin = effective_role == "admin"

    # --- 3. Load organization ---
    organization_id = creator_user.get("organization_id")
    organization: Dict[str, Any] = {}
    if organization_id:
        organization = _db.get_organization_by_id(organization_id) or {}
        if not organization:
            logger.warning(f"Organization {organization_id} not found for user {user_email}")
    else:
        logger.warning(f"No organization_id for user {user_email}")

    # Attach organization to user dict for backward compatibility
    creator_user["organization"] = organization

    # --- 4. Load organization role ---
    org_role: Optional[str] = None
    user_id = creator_user.get("id")
    if user_id and organization_id:
        org_role = _db.get_user_organization_role(user_id, organization_id)

    is_org_admin = org_role in ("owner", "admin")

    # --- 5. Extract feature flags from org config ---
    org_config = organization.get("config", {})
    if isinstance(org_config, str):
        try:
            org_config = json.loads(org_config)
        except (json.JSONDecodeError, TypeError):
            org_config = {}
    features = org_config.get("features", {})

    # --- 6. Build and return ---
    return AuthContext(
        user=creator_user,
        token_payload=payload,
        is_system_admin=is_system_admin,
        organization_role=org_role,
        is_org_admin=is_org_admin,
        organization=organization,
        features=features,
    )


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------

_bearer = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthContext:
    """Standard auth dependency — most endpoints.

    Raises ``HTTPException(401)`` if the token is missing or invalid.
    """
    ctx = _build_auth_context(credentials.credentials)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
    return ctx


async def get_optional_auth_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[AuthContext]:
    """Optional auth dependency — endpoints that work with or without auth.

    Returns ``AuthContext`` if a valid token is provided, ``None`` otherwise.
    """
    if credentials is None:
        return None

    ctx = _build_auth_context(credentials.credentials)
    if ctx is None:
        # Token was provided but invalid — log but don't block
        logger.warning("Invalid token provided to optional-auth endpoint")
        return None
    return ctx


async def require_admin(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Admin-only shortcut dependency.

    Raises ``HTTPException(403)`` if the authenticated user is not a system admin.
    """
    auth.require_system_admin()
    return auth
