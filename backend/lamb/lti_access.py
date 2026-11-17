"""LTI platform admission and organization-to-Moodle binding.

Only consume platform claims after protocol authentication. LTI 1.1 authenticates
the signed launch with its configured secret; deployments sharing that secret
also share trust in the instance claims. HTTP Origin/Referer are never identity.
"""
import json
import re
from urllib.parse import urlsplit, urlunsplit

KEY = "lti_access"


def normalize_url(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Enter the Moodle installation's full URL.")
    value = value.strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Invalid Moodle URL.")
    try:
        parts = urlsplit(value)
        if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment):
            raise ValueError()
        host = parts.hostname.encode("idna").decode("ascii").lower()
        if not re.fullmatch(r"[a-z0-9.-]+", host) or any(not x or x.startswith('-') or x.endswith('-') for x in host.split('.')):
            raise ValueError()
        port = parts.port
        if port == 0:
            raise ValueError()
        authority = host + (f":{port}" if port and (parts.scheme, port) not in (("https", 443), ("http", 80)) else "")
        path = parts.path.rstrip("/")
        if any(p in (".", "..") for p in path.split('/')) or '%' in path or '//' in path:
            raise ValueError()
        return urlunsplit((parts.scheme, authority, path, "", ""))
    except (ValueError, UnicodeError):
        raise ValueError("Use a full Moodle URL without credentials, query parameters or fragments.") from None


def instance_url(value):
    """Compatibility with the hostname GUID carried by older signed Moodle launches."""
    return normalize_url(value if "://" in str(value) else "https://" + str(value or ""))


def lti11_origin(parameters):
    supplied = parameters.get("tool_consumer_instance_url")
    return normalize_url(supplied) if supplied else instance_url(parameters.get("tool_consumer_instance_guid"))


def global_settings(db):
    system = db.get_organization_by_slug("lamb")
    if not system:
        raise ValueError("System LTI settings are unavailable.")
    settings = (system.get("config") or {}).get(KEY) or {}
    return validate_global(settings)


def validate_global(settings):
    enabled = settings.get("whitelist_enabled", False)
    origins = settings.get("allowed_origins", [])
    if type(enabled) is not bool or not isinstance(origins, list) or len(origins) > 100:
        raise ValueError("Use a whitelist switch and at most 100 LMS installation URLs.")
    return {"whitelist_enabled": enabled, "allowed_origins": list(dict.fromkeys(normalize_url(url) for url in origins))}


def require_global(db, origin):
    origin = normalize_url(origin)
    policy = global_settings(db)
    if policy["whitelist_enabled"] and origin not in policy["allowed_origins"]:
        raise ValueError("This LMS is not allowed by the LAMB administrator.")
    return origin


def organization_url(organization):
    raw = ((organization or {}).get("config") or {}).get(KEY, {}).get("moodle_url", "")
    return normalize_url(raw) if raw else ""


def require_organization(db, organization, origin):
    origin = require_global(db, origin)
    if not organization or organization.get("is_system") or organization.get("status", "active") != "active":
        raise ValueError("This organization does not accept LTI access.")
    expected = organization_url(organization)
    if not expected:
        raise ValueError("The organization administrator must configure its Moodle installation before LTI access.")
    if origin != expected:
        raise ValueError("This LMS is not connected to the organization.")
    return origin


def organization_allowed(db, organization_id, origin):
    try:
        require_organization(db, db.get_organization_by_id(organization_id), origin)
        return True
    except ValueError:
        return False


def identity_origin(db, user_id, instance):
    from lamb.lti13 import is_scoped
    if is_scoped(user_id):
        from lamb.lti13.store import Store
        store = Store(db)
        user = store.object(user_id, "user")
        return normalize_url(store.registration(user["registration_id"], user["deployment_id"])["issuer"])
    return instance_url(instance)


def save_settings(db, organization_id, settings):
    """Patch only this feature under a write lock, preserving unrelated settings."""
    connection = db.get_connection()
    if connection is None:
        raise ValueError("Organization settings storage is unavailable.")
    try:
        connection.execute("BEGIN IMMEDIATE")
        table = f"{db.table_prefix}organizations"
        row = connection.execute(f"SELECT config FROM {table} WHERE id=?", (organization_id,)).fetchone()
        if not row:
            raise ValueError("Organization not found.")
        config = json.loads(row[0] or '{}')
        config[KEY] = settings
        connection.execute(f"UPDATE {table} SET config=? WHERE id=?", (json.dumps(config), organization_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
