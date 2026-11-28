"""Optional LMS admission for LTI 1.1 launches.

Off by default (Marc, 18 November 2026): with no whitelist and no organization lock LAMB
does not compare the installation a launch names, and launches behave as they did in 0.8.
A system administrator may restrict LAMB to a whitelist of installations; an organization
administrator may lock the organization to the installations it is used from.

LTI 1.1 authenticates a launch with a shared secret, and the installation identifier is a
claim signed with it. These checks keep honest installations that share credentials apart;
they do not stop an operator who holds the secret. An LTI 1.3 launch is governed by its
registration: its session carries a handle in place of the installation's name, and the
organizations it may enter are those of the registration, not the whitelist or the lock.
Identifiers are compared as the LMS sends them: nothing is parsed, so an LMS that names
itself with a site id or a free text works like any other.

For LAMB an installation is the same one on both versions (#579): what is stored and
compared is always what the LMS calls itself. Since LTI 1.1 stays open for an installation
that also uses LTI 1.3, the limit of the shared secret applies to that installation too.
"""
import json
import sqlite3

KEY = "lti_access"
LIMIT = 100
MAX_LENGTH = 255
LEGACY_KEYS = ("moodle_url", "allowed_origins")  # URL settings of the 17 November dev build; never read


def instance_id(parameters) -> str:
    """What an LTI 1.1 launch calls its installation; empty when the LMS does not say.
    A name shaped like the handle of an LTI 1.3 session is refused."""
    from lamb.lti13 import is_scoped
    value = str(parameters.get("tool_consumer_instance_guid") or "").strip()
    if is_scoped(value):
        raise ValueError("Reserved LTI identifier")
    return value


def registration_of(db, instance):
    """The LTI 1.3 registration a session came through, or None for an LTI 1.1 session.
    ValueError when the registration or its deployment is no longer enabled."""
    from lamb.lti13 import is_scoped
    if not is_scoped(instance):
        return None
    from lamb.lti13.store import Store
    return Store(db).instance(instance)[1]


def same_instance(one, other) -> bool:
    """Whether two identifiers name the same installation. Dev builds of 17 and 18 November
    2026 stored and signed 'https://<identifier>'; those records and sessions still match."""
    one, other = str(one or "").strip(), str(other or "").strip()
    if one == other:
        return True
    return bool(one and other) and (one.lower() == "https://" + other.lower() or other.lower() == "https://" + one.lower())


def _listed(instance, instances) -> bool:
    return any(same_instance(instance, entry) for entry in instances)


def _stored(values):
    return [v.strip() for v in values if isinstance(v, str) and v.strip()] if isinstance(values, list) else []


def validate_instances(values):
    if not isinstance(values, list) or len(values) > LIMIT:
        raise ValueError(f"Use at most {LIMIT} LMS installations.")
    cleaned = []
    for value in values:
        if (not isinstance(value, str) or not value.strip() or len(value) > MAX_LENGTH
                or any(ord(c) < 32 for c in value)):
            raise ValueError("Invalid LMS installation identifier.")
        cleaned.append(value.strip())
    return list(dict.fromkeys(cleaned))


# -- the system whitelist -------------------------------------------------------------

def global_settings(db):
    system = db.get_organization_by_slug("lamb")
    settings = ((system or {}).get("config") or {}).get(KEY) or {}
    return {"whitelist_enabled": settings.get("whitelist_enabled") is True and "allowed_instances" in settings,
            "allowed_instances": _stored(settings.get("allowed_instances"))}


def validate_global(settings):
    enabled = settings.get("whitelist_enabled", False)
    if type(enabled) is not bool:
        raise ValueError("Use a whitelist switch and a list of LMS installations.")
    return {"whitelist_enabled": enabled, "allowed_instances": validate_instances(settings.get("allowed_instances", []))}


def require_global(db, instance):
    policy = global_settings(db)
    if policy["whitelist_enabled"] and not _listed(instance, policy["allowed_instances"]):
        raise ValueError("This LMS is not allowed by the LAMB administrator.")
    return instance


# -- the organization lock ------------------------------------------------------------

def locked_instances(organization):
    return _stored((((organization or {}).get("config") or {}).get(KEY) or {}).get("locked_instances"))


def require_organization(db, organization, instance):
    """Refuse a launch into this organization: on LTI 1.3 when its registration does not list
    the organization, on LTI 1.1 only where an administrator asked for it."""
    registration = registration_of(db, instance)
    if registration is not None:
        if not organization:
            raise ValueError("Organization not found.")
        if organization.get("status") == "suspended":
            raise ValueError("This organization is suspended.")
        if organization["id"] not in registration["organization_ids"]:
            raise ValueError("Organization is not allowed for this LMS registration")
        return instance
    require_global(db, instance)
    if not organization:
        raise ValueError("Organization not found.")
    if organization.get("status") == "suspended":
        raise ValueError("This organization is suspended.")
    lock = locked_instances(organization)
    if lock and not _listed(instance, lock):
        raise ValueError("This LMS is not connected to the organization.")
    return instance


def organization_allowed(db, organization_id, instance):
    try:
        require_organization(db, db.get_organization_by_id(organization_id), instance)
        return True
    except ValueError:
        return False


# -- what an administrator can choose from ----------------------------------------------

def session_instance(token_payload) -> str:
    """The installation an LTI 1.1 Creator session was opened from; empty for a password
    session, an LTI 1.3 session, or an LMS that does not name itself. The lock an organization
    administrator sets with it applies to LTI 1.1 launches only."""
    from lamb.lti13 import is_scoped
    identity = (token_payload or {}).get("lti_identity")
    if (not isinstance(identity, dict) or not identity.get("lms_user_id")
            or is_scoped(identity["lms_user_id"]) or is_scoped(identity.get("lms_instance"))):
        return ""
    instance = str(identity.get("lms_instance") or "").strip()
    return "" if "://" in instance else instance  # a session of the 17 November dev build


def seen_instances(db, organization_id=None):
    """Installations whose verified LTI 1.1 launches reached this organization (or any): the
    ones recorded on its activities and on the accounts obtained with its creator codes."""
    p = db.table_prefix
    org = (organization_id,) if organization_id is not None else ()
    queries = (
        (f"SELECT DISTINCT lms_origin FROM {p}lti_activities WHERE lms_scope LIKE '[\"1.1\"%'"
         + (" AND organization_id=?" if org else ""), org),
        (f"SELECT DISTINCT r.lms_instance FROM {p}lti_creator_code_redemptions r "
         f"JOIN {p}lti_creator_codes c ON c.id=r.code_id WHERE r.protocol='1.1'"
         + (" AND c.organization_id=?" if org else ""), org))
    found = set()
    connection = db.get_connection()
    if connection is None:
        return []
    try:
        for sql, params in queries:
            try:
                found.update(str(row[0] or "").strip() for row in connection.execute(sql, params))
            except sqlite3.Error:
                continue  # a table of a later migration
    finally:
        connection.close()
    return sorted(v for v in found if v and "://" not in v)[:LIMIT]


def save_settings(db, organization_id, settings):
    """Patch only this feature's keys under a write lock, preserving every other setting."""
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
        current = config.get(KEY) if isinstance(config.get(KEY), dict) else {}
        config[KEY] = {k: v for k, v in {**current, **settings}.items() if k not in LEGACY_KEYS}
        connection.execute(f"UPDATE {table} SET config=? WHERE id=?", (json.dumps(config), organization_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
