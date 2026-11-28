"""Creator codes: self-service onboarding for instructors who arrive by LTI without a LAMB account.

Requirement in #467, build in #562. An organization admin creates a code. An instructor who
launches an activity from the LMS and has no LAMB Creator account enters it and becomes a
creator (never an admin) in that one organization.

Eligibility is the boundary. A code can be redeemed only from the page a verified launch
returned: that page carries a ticket, signed by LAMB, with the identity and the instructor
role the LMS asserted. The ticket lives fifteen minutes, serves one launch and one purpose.
Holding the code grants nothing; neither does a student launch, a setup or dashboard token,
or the organization's signup key, which belongs to the web sign-up form and is never accepted
here.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from lamb import auth as lamb_auth, lti_access
from lamb.logging_config import get_logger
from lamb.lti13 import is_scoped

logger = get_logger(__name__, component="LTI")

TICKET_TYPE = "onboarding"
TICKET_LIFETIME = timedelta(minutes=15)
ATTEMPT_WINDOW_SECONDS = 15 * 60
# After a launch from the LMS, an instructor may move between the activity and LAMB Creator,
# add an organization and switch organization for this long (Marc, 14 November 2026: four hours).
ACTIVITY_SESSION_SECONDS = 4 * 3600
RETURN_TYPE = "return"
MAX_FAILED_ATTEMPTS = 5
# No 0/O and no 1/I: the code is read aloud and typed by hand.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
PAGE_TEXT_LIMIT = 4000
LABEL_LIMIT = 120
CONFIG_KEY = "lti_onboarding"
DEFAULT_PAGE_TEXT = (
    "Your institution lets teachers create their own LAMB Creator account with a creator code.\n"
    "If you have a code, enter it below. If you do not, ask the person who manages LAMB at your "
    "institution for one."
)

MESSAGES = {
    "invalid": "That code is not valid. Check it and try again.",
    "disabled": "This code is no longer active.",
    "expired": "This code has expired.",
    "used_up": "This code has reached its limit of uses.",
    "rate_limited": "Too many attempts. Wait a few minutes, then open the activity from your LMS again.",
    "not_allowed": "This code belongs to an organization that your LMS is not connected to.",
    "account_disabled": "Your LAMB account in this organization is disabled.",
    "already_member": "You already have an account in this organization. Go back and choose it.",
    "other_lms": "An account for this LMS user already exists in this organization, obtained from another LMS. Ask your LAMB administrator.",
    "failed": "The account could not be created. Open the activity from your LMS again, or contact your LAMB administrator.",
    "replayed": "This launch has already been used. Open the activity from your LMS again.",
}
# Outcomes that tell the instructor to talk to someone: the organization's own text follows them.
SHOW_ORGANIZATION_TEXT = {"disabled", "expired", "used_up", "not_allowed", "account_disabled", "other_lms"}


def migrate(cursor, prefix):
    for sql in (
        '''CREATE TABLE IF NOT EXISTS {p}lti_creator_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL UNIQUE, hint TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1, expires_at INTEGER, max_uses INTEGER,
            use_count INTEGER NOT NULL DEFAULT 0, created_by INTEGER,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
            FOREIGN KEY(organization_id) REFERENCES {p}organizations(id))''',
        '''CREATE INDEX IF NOT EXISTS {p}lti_creator_codes_org ON {p}lti_creator_codes(organization_id)''',
        '''CREATE TABLE IF NOT EXISTS {p}lti_creator_code_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code_id INTEGER NOT NULL,
            creator_user_id INTEGER NOT NULL, identity_hash TEXT NOT NULL,
            launch_id TEXT NOT NULL UNIQUE, protocol TEXT NOT NULL, redeemed_at INTEGER NOT NULL,
            lms_instance TEXT NOT NULL DEFAULT '', lms_email TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(code_id) REFERENCES {p}lti_creator_codes(id))''',
        '''CREATE TABLE IF NOT EXISTS {p}lti_onboarding_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, identity_hash TEXT NOT NULL,
            launch_id TEXT NOT NULL, outcome TEXT NOT NULL, attempted_at INTEGER NOT NULL)''',
        '''CREATE INDEX IF NOT EXISTS {p}lti_onboarding_attempts_identity
            ON {p}lti_onboarding_attempts(identity_hash, attempted_at)''',
    ):
        cursor.execute(sql.format(p=prefix))
    # Databases that ran an earlier build of this migration lack the two identity columns.
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({prefix}lti_creator_code_redemptions)").fetchall()}
    for column in ("lms_instance", "lms_email"):
        if column not in columns:
            cursor.execute(f"ALTER TABLE {prefix}lti_creator_code_redemptions ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")


# ---------------------------------------------------------------------------
# Codes
# ---------------------------------------------------------------------------

def normalize(code: str) -> str:
    """What the instructor typed, without spaces, hyphens or case."""
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())


def _hash(code: str) -> str:
    return hmac.new(lamb_auth._get_jwt_secret().encode(), normalize(code).encode(), hashlib.sha256).hexdigest()


def _new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(raw[i:i + 4] for i in range(0, CODE_LENGTH, 4))


def _status(row: Dict[str, Any], now: Optional[int] = None) -> str:
    now = now or int(time.time())
    if not row["enabled"]:
        return "disabled"
    if row["expires_at"] is not None and row["expires_at"] <= now:
        return "expired"
    if row["max_uses"] is not None and row["use_count"] >= row["max_uses"]:
        return "used_up"
    return "active"


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": row["id"], "label": row["label"], "hint": row["hint"], "enabled": bool(row["enabled"]),
            "expires_at": row["expires_at"], "max_uses": row["max_uses"], "use_count": row["use_count"],
            "created_at": row["created_at"], "status": _status(row)}


def _rows(db, sql: str, params=()) -> List[Dict[str, Any]]:
    connection = db.get_connection()
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql.format(p=db.table_prefix), params).fetchall()]
    finally:
        connection.close()


def _write(db, sql: str, params=()) -> sqlite3.Cursor:
    connection = db.get_connection()
    try:
        with connection:
            return connection.execute(sql.format(p=db.table_prefix), params)
    finally:
        connection.close()


def create_code(db, organization_id: int, label: str = "", expires_at: Optional[int] = None,
                max_uses: Optional[int] = None, created_by: Optional[int] = None) -> Dict[str, Any]:
    """Create a code for one organization. The clear value is returned once and never stored."""
    organization = db.get_organization_by_id(organization_id)
    if not organization:
        raise ValueError("Organization not found")
    # The system organization may have codes: it can be the only organization of a small
    # installation (Marc, 18 November 2026). Its members by code are plain users.
    if organization.get("status") == "suspended":
        raise ValueError("This organization is suspended.")
    now = int(time.time())
    if expires_at is not None and int(expires_at) <= now:
        raise ValueError("The expiry date must be in the future")
    if max_uses is not None and int(max_uses) < 1:
        raise ValueError("The use limit must be at least 1")
    code = _new_code()
    cursor = _write(db, '''INSERT INTO {p}lti_creator_codes
        (organization_id, code_hash, hint, label, enabled, expires_at, max_uses, use_count, created_by, created_at, updated_at)
        VALUES (?,?,?,?,1,?,?,0,?,?,?)''',
        (organization_id, _hash(code), code[-4:], (label or "").strip()[:LABEL_LIMIT],
         int(expires_at) if expires_at is not None else None, int(max_uses) if max_uses is not None else None,
         created_by, now, now))
    logger.info(f"Creator code {cursor.lastrowid} created for organization {organization_id}")
    row = _rows(db, "SELECT * FROM {p}lti_creator_codes WHERE id=?", (cursor.lastrowid,))[0]
    return {**_public(row), "code": code}


def list_codes(db, organization_id: int) -> List[Dict[str, Any]]:
    return [_public(row) for row in _rows(
        db, "SELECT * FROM {p}lti_creator_codes WHERE organization_id=? ORDER BY created_at DESC, id DESC",
        (organization_id,))]


def set_enabled(db, organization_id: int, code_id: int, enabled: bool) -> Optional[Dict[str, Any]]:
    """Enable or disable a code of this organization. None when the code is not this organization's."""
    cursor = _write(db, "UPDATE {p}lti_creator_codes SET enabled=?, updated_at=? WHERE id=? AND organization_id=?",
                    (1 if enabled else 0, int(time.time()), code_id, organization_id))
    if cursor.rowcount != 1:
        return None
    logger.info(f"Creator code {code_id} {'enabled' if enabled else 'disabled'} in organization {organization_id}")
    return _public(_rows(db, "SELECT * FROM {p}lti_creator_codes WHERE id=?", (code_id,))[0])


# ---------------------------------------------------------------------------
# The page text an institution writes
# ---------------------------------------------------------------------------

def own_page_text(organization: Optional[Dict[str, Any]]) -> str:
    config = (organization or {}).get("config") or {}
    return str((config.get(CONFIG_KEY) or {}).get("page_text") or "").strip()


def page_text(db, organization_ids=()) -> str:
    """Text shown to an instructor with no account.

    The organization's own text when the launch points at exactly one organization, else the
    system organization's (the deployment's), else the text that ships with LAMB.
    """
    if len(organization_ids) == 1:
        text = own_page_text(db.get_organization_by_id(organization_ids[0]))
        if text:
            return text
    system = db.get_organization_by_slug("lamb") if hasattr(db, "get_organization_by_slug") else None
    return own_page_text(system) or DEFAULT_PAGE_TEXT


def set_page_text(db, organization: Dict[str, Any], text: str) -> str:
    text = str(text or "").strip()
    if len(text) > PAGE_TEXT_LIMIT:
        raise ValueError(f"The text is longer than {PAGE_TEXT_LIMIT} characters")
    config = dict(organization.get("config") or {})
    if text:
        config[CONFIG_KEY] = {**(config.get(CONFIG_KEY) or {}), "page_text": text}
    else:
        config.pop(CONFIG_KEY, None)
    if not db.update_organization_config(organization["id"], config):
        raise ValueError("The text could not be saved")
    return text


# ---------------------------------------------------------------------------
# The ticket a verified instructor launch hands to its own page
# ---------------------------------------------------------------------------

def issue_ticket(*, lms_user_id: str, lms_email: str, display_name: str, resource_link_id: str,
                 context_id: str = "", context_title: str = "", protocol: str, lms_instance: str = "",
                 username: str = "", launched_at: Optional[int] = None) -> str:
    """Sign what the LMS asserted in this launch. Call only after the launch was verified
    and only for a launch that carries the instructor role."""
    return lamb_auth.create_token({
        "lti_type": TICKET_TYPE,
        "lti_instructor": True,
        "lti_protocol": protocol,
        "lti_launch_id": secrets.token_hex(16),
        "lti_lms_user_id": lms_user_id,
        "lti_lms_email": lms_email or "",
        "lti_lms_instance": lms_instance or "",
        "lti_launched_at": int(launched_at or time.time()),
        "lti_username": username or "",
        "lti_display_name": display_name or "",
        "lti_resource_link_id": resource_link_id,
        "lti_context_id": context_id or "",
        "lti_context_title": context_title or "",
    }, expires_delta=TICKET_LIFETIME)


def read_ticket(token: str) -> Optional[Dict[str, Any]]:
    payload = lamb_auth.decode_token(token) if token else None
    if not payload or payload.get("lti_type") != TICKET_TYPE or payload.get("lti_instructor") is not True:
        return None
    if not payload.get("lti_lms_user_id") or not payload.get("lti_launch_id") or not payload.get("lti_resource_link_id"):
        return None
    if payload.get("lti_protocol") not in ("1.1", "1.3"):
        return None
    # An LTI 1.3 launch carries the handle of its registration as its instance; an LTI 1.1
    # launch never does. The user is the LMS's own identifier in both.
    if is_scoped(payload.get("lti_lms_instance")) != (payload["lti_protocol"] == "1.3") or is_scoped(payload["lti_lms_user_id"]):
        return None
    return payload


def allowed_organizations(db, ticket: Dict[str, Any]) -> Optional[List[int]]:
    """Organizations this launch may enter: those of its LTI 1.3 registration, or None (any) for LTI 1.1."""
    registration = lti_access.registration_of(db, ticket.get("lti_lms_instance"))
    return None if registration is None else list(registration["organization_ids"])


# ---------------------------------------------------------------------------
# Who a launch is
# ---------------------------------------------------------------------------

def _identity(lms_user_id: str) -> str:
    """The key of an LMS user in the records of codes and attempts. A person is the same on
    LTI 1.1 and on LTI 1.3 (#579); the "1.1:" inside is how these keys were first written."""
    return hashlib.sha256(f"1.1:{lms_user_id}".encode()).hexdigest()


def instances_of(db, lms_user_id: str) -> Dict[int, set]:
    """For an LMS user id: the LMS installations each account was obtained from with a creator
    code, {creator_user_id: {instance, ...}}. An account that is not there was not obtained
    with a code."""
    obtained: Dict[int, set] = {}
    for row in _rows(db, "SELECT creator_user_id, lms_instance FROM {p}lti_creator_code_redemptions WHERE identity_hash=?",
                     (_identity(lms_user_id),)):
        obtained.setdefault(row["creator_user_id"], set()).add(row["lms_instance"])
    return obtained


def accounts_of_instance(db, accounts: List[Dict[str, Any]], lms_user_id: str, lms_instance: str) -> List[Dict[str, Any]]:
    """Of the LTI creator accounts tied to an LMS user id, those a launch from this LMS
    installation may act as (Marc, 15 November 2026: identity is the organization, the LMS
    user and the LMS instance, never the email), on LTI 1.1 and on LTI 1.3 alike (#579).

    A user id is only that LMS's own number: an account obtained with a creator code belongs
    to the installation it was obtained from. An account made by the organization's own LTI
    Creator tool carries no record of an installation and is recognised by the user id. The
    installation is compared as the LMS names itself. An account of an organization this
    launch may not enter is left out: on LTI 1.3 the organizations of the registration, on
    LTI 1.1 the whitelist and the organization lock where an administrator enabled them.
    ValueError when the registration of an LTI 1.3 session is no longer enabled.
    """
    from lamb.lti13.store import installation_of
    here = installation_of(lms_instance, db)
    obtained = instances_of(db, lms_user_id)
    return [account for account in accounts
            if lti_access.organization_allowed(db, account["organization_id"], lms_instance)
            and (account["id"] not in obtained
                 or any(lti_access.same_instance(v, here) for v in obtained[account["id"]]))]


# ---------------------------------------------------------------------------
# Redemption
# ---------------------------------------------------------------------------

@dataclass
class Redemption:
    ok: bool
    reason: str = ""
    creator_user: Optional[Dict[str, Any]] = None
    organization: Optional[Dict[str, Any]] = None
    first_account: bool = False   # the person had no LAMB account before this code

    @property
    def message(self) -> str:
        return MESSAGES.get(self.reason, MESSAGES["failed"])


def _identity_hash(ticket: Dict[str, Any]) -> str:
    return _identity(ticket['lti_lms_user_id'])


def _instance(claims: Dict[str, Any]) -> str:
    return str(claims.get("lti_lms_instance") or "").strip()


def _email(claims: Dict[str, Any]) -> str:
    return str(claims.get("lti_lms_email") or "").strip().lower()


def _record(db, ticket: Dict[str, Any], outcome: str) -> None:
    _write(db, "INSERT INTO {p}lti_onboarding_attempts (identity_hash, launch_id, outcome, attempted_at) VALUES (?,?,?,?)",
           (_identity_hash(ticket), ticket["lti_launch_id"], outcome, int(time.time())))


def _refuse(db, ticket, reason: str, organization=None, code_id=None) -> Redemption:
    _record(db, ticket, reason)
    # The code itself is never logged: its id when it matched, nothing when it did not.
    logger.warning(f"Creator code refused ({reason}) for launch identity {_identity_hash(ticket)[:12]}"
                   + (f", code {code_id}" if code_id else ""))
    return Redemption(False, reason, organization=organization)


def _generated_email(organization: Dict[str, Any], lms_user_id: str) -> str:
    # Same address the LMS-to-Creator entry gives the same person in the same organization.
    from lamb.lti_creator_router import sanitize_lti_user_id
    return f"lti_creator_{organization['slug']}_{sanitize_lti_user_id(lms_user_id)}@lamb-lti.local"


def redeem(db, manager, ticket: Dict[str, Any], code: str) -> Redemption:
    """Turn a valid code into a creator account for the instructor of this ticket.

    `ticket` comes from read_ticket(). Nothing is written before every check has passed,
    except the record of the attempt.
    """
    now = int(time.time())
    identity = _identity_hash(ticket)
    failed = _rows(db, '''SELECT COUNT(*) AS n FROM {p}lti_onboarding_attempts
        WHERE identity_hash=? AND attempted_at>? AND outcome NOT IN ('ok','claimed') ''', (identity, now - ATTEMPT_WINDOW_SECONDS))[0]["n"]
    if failed >= MAX_FAILED_ATTEMPTS:
        logger.warning(f"Creator code attempts limited for launch identity {identity[:12]}")
        return Redemption(False, "rate_limited")
    if not normalize(code):
        return _refuse(db, ticket, "invalid")

    rows = _rows(db, "SELECT * FROM {p}lti_creator_codes WHERE code_hash=?", (_hash(code),))
    if not rows:
        return _refuse(db, ticket, "invalid")
    row = rows[0]
    organization = db.get_organization_by_id(row["organization_id"])
    if not organization:
        return _refuse(db, ticket, "invalid", code_id=row["id"])
    status = _status(row, now)
    if status != "active":
        return _refuse(db, ticket, status, organization, row["id"])
    try:
        # LTI 1.1: the optional whitelist and organization lock. LTI 1.3: the organizations
        # of the registration.
        lti_access.require_organization(db, organization, _instance(ticket))
        from lamb.lti13.store import installation_of
        installation = installation_of(_instance(ticket), db)
    except ValueError:
        return _refuse(db, ticket, "not_allowed", organization, row["id"])

    lms_user_id = ticket["lti_lms_user_id"]
    existing = db.get_creator_user_by_lti(organization["id"], lms_user_id)
    if existing and not existing.get("enabled", True):
        return _refuse(db, ticket, "account_disabled", organization, row["id"])
    # The LTI creator accounts this launch already is, in any organization. Never two in one
    # organization. The email decides nothing here: a password account with the same address
    # is another matter, and does not stand in the way.
    try:
        known = manager.identify_instructor(lms_user_id=lms_user_id, lms_instance=_instance(ticket))
    except ValueError:
        known = []
    if any(account["organization_id"] == organization["id"] for account in known):
        return _refuse(db, ticket, "already_member", organization, row["id"])
    if existing and instances_of(db, lms_user_id).get(existing["id"]):
        # The account of this user id in this organization was obtained from another LMS
        # instance: the same number there is another person. A code does not hand it over.
        return _refuse(db, ticket, "other_lms", organization, row["id"])
    # `existing` without being known and without a record of an instance: an account made by
    # the organization's LTI Creator tool, or one whose link went missing. The code links it
    # and takes no use; from now on it belongs to this instance.

    # One atomic database statement claims the launch before any provisioning.
    # Other workers see the claim even while the OWI account call is in progress.
    claimed = _write(db, '''INSERT INTO {p}lti_onboarding_attempts
        (identity_hash, launch_id, outcome, attempted_at)
        SELECT ?, ?, 'claimed', ?
        WHERE NOT EXISTS (SELECT 1 FROM {p}lti_onboarding_attempts WHERE launch_id=? AND outcome='claimed')
          AND NOT EXISTS (SELECT 1 FROM {p}lti_creator_code_redemptions WHERE launch_id=?)''',
        (identity, ticket["lti_launch_id"], now, ticket["lti_launch_id"], ticket["lti_launch_id"]))
    if claimed.rowcount != 1:
        return _refuse(db, ticket, "replayed")
    creator_id = existing["id"] if existing else None
    if not existing:
        # Take one use only if the code is still active at this instant; two instructors
        # racing for the last use cannot both get it.
        taken = _write(db, '''UPDATE {p}lti_creator_codes SET use_count=use_count+1, updated_at=?
            WHERE id=? AND enabled=1 AND (expires_at IS NULL OR expires_at>?)
              AND (max_uses IS NULL OR use_count<max_uses)''', (now, row["id"], now))
        if taken.rowcount != 1:
            fresh = _rows(db, "SELECT * FROM {p}lti_creator_codes WHERE id=?", (row["id"],))[0]
            return _refuse(db, ticket, _status(fresh, now) if _status(fresh, now) != "active" else "used_up",
                           organization, row["id"])
        creator_id = db.create_lti_creator_user(
            organization_id=organization["id"], lti_user_id=lms_user_id,
            user_email=_generated_email(organization, lms_user_id),
            user_name=ticket.get("lti_display_name") or "LTI User", allow_system=True)
        if not creator_id:
            _write(db, "UPDATE {p}lti_creator_codes SET use_count=use_count-1 WHERE id=? AND use_count>0", (row["id"],))
            return _refuse(db, ticket, "failed", organization, row["id"])
    try:
        manager.link_identity(lms_user_id=lms_user_id, creator_user_id=creator_id,
                              lms_email=ticket.get("lti_lms_email") or None)
    except ValueError:
        return _refuse(db, ticket, "not_allowed", organization, row["id"])

    _write(db, '''INSERT INTO {p}lti_creator_code_redemptions
        (code_id, creator_user_id, identity_hash, launch_id, protocol, redeemed_at, lms_instance, lms_email)
        VALUES (?,?,?,?,?,?,?,?)''',
        (row["id"], creator_id, identity, ticket["lti_launch_id"], ticket["lti_protocol"], now,
         installation, _email(ticket)))
    _record(db, ticket, "ok")
    creator = db.get_creator_user_by_id(creator_id)
    logger.info(f"Creator code {row['id']} redeemed: creator user {creator_id} in organization {organization['id']}")
    return Redemption(True, "ok", creator_user={
        "id": creator_id, "organization_id": organization["id"],
        "user_email": creator.get("user_email") or creator.get("email"),
        "user_name": creator.get("user_name") or creator.get("name"),
    }, organization=organization, first_account=not known)


# ---------------------------------------------------------------------------
# Between the activity and LAMB Creator
# ---------------------------------------------------------------------------

def launched_at(claims: Dict[str, Any]) -> Optional[int]:
    """When the LMS launch behind these claims happened (carried from token to token), else when the token was issued."""
    value = claims.get("lti_launched_at") or claims.get("iat")
    return int(value) if isinstance(value, (int, float)) else None


def within_session(claims: Dict[str, Any]) -> bool:
    start = launched_at(claims)
    return start is not None and 0 <= time.time() - start <= ACTIVITY_SESSION_SECONDS


def creator_access(db, manager, claims: Dict[str, Any]) -> List[Dict[str, Any]]:
    """LTI creator accounts this instructor may enter LAMB Creator as, or switch to.

    An LTI creator has no password and enters LAMB only through the LMS (Marc, 14 November
    2026). Offered: every account the launch identifies (LtiActivityManager.identify_instructor:
    the LMS user and the LMS installation), within four hours of the launch, whatever
    email the launch carries: the same LMS user enters any of their organizations (Marc,
    15 November 2026). `claims`: a setup, dashboard or return token, or the identity kept in a
    Creator session. Regular creators sign in on the login page and are never offered here.
    """
    if not within_session(claims):
        return []
    lms_user_id = claims.get("lti_lms_user_id") or ""
    if not lms_user_id:
        return []
    try:
        identified = manager.identify_instructor(lms_user_id=lms_user_id, lms_instance=_instance(claims))
    except ValueError:
        return []
    accounts = []
    for account in identified:
        organization = db.get_organization_by_id(account["organization_id"]) or {}
        accounts.append({"creator_user_id": account["id"], "organization_id": account["organization_id"],
                         "organization_name": organization.get("name") or "",
                         "user_name": account.get("user_name") or account.get("name") or ""})
    return sorted(accounts, key=lambda a: (a["organization_name"].lower(), a["creator_user_id"]))


def creator_session(db, manager, claims: Dict[str, Any], creator_user_id: int) -> Optional[str]:
    """A LAMB Creator session for one of the accounts creator_access() offers, or None.

    The session remembers the LMS identity and the time of the launch, so that the person can
    switch organization from inside LAMB Creator for the rest of the four hours.
    """
    if not any(account["creator_user_id"] == creator_user_id for account in creator_access(db, manager, claims)):
        logger.warning(f"Creator entry refused for creator user {creator_user_id}")
        return None
    user = db.get_creator_user_by_id(creator_user_id)
    logger.info(f"Creator entry from the LMS: creator user {creator_user_id}")
    return lamb_auth.create_token({
        "sub": str(creator_user_id), "email": user.get("user_email") or user.get("email"), "role": user.get("role") or "user",
        "lti_identity": {"lms_user_id": claims.get("lti_lms_user_id"), "lms_email": _email(claims),
                         "lms_instance": _instance(claims), "launched_at": launched_at(claims)}})


def session_identity(session: Dict[str, Any]) -> Dict[str, Any]:
    """The launch claims a Creator session carries, in the shape creator_access() reads; {} for a session
    that did not come from the LMS."""
    identity = session.get("lti_identity") if isinstance(session, dict) else None
    if not isinstance(identity, dict) or not identity.get("lms_user_id"):
        return {}
    return {"lti_lms_user_id": identity.get("lms_user_id"), "lti_lms_email": identity.get("lms_email") or "",
            "lti_lms_instance": identity.get("lms_instance") or "", "lti_launched_at": identity.get("launched_at")}


RETURN_CLAIMS = ("lti_resource_link_id", "lti_context_id", "lti_context_title", "lti_lms_user_id", "lti_lms_email",
                 "lti_lms_instance", "lti_username", "lti_display_name")


def issue_return(claims: Dict[str, Any]) -> str:
    """The way back to the activity a person came from, for the rest of the four hours. LAMB Creator
    keeps it per browser tab: another activity opened in another tab has its own."""
    start = launched_at(claims) or int(time.time())
    remaining = max(1, start + ACTIVITY_SESSION_SECONDS - int(time.time()))
    return lamb_auth.create_token({"lti_type": RETURN_TYPE, "lti_launched_at": start,
                                   **{key: claims.get(key) or "" for key in RETURN_CLAIMS}},
                                  expires_delta=timedelta(seconds=remaining))


def read_return(token: str) -> Optional[Dict[str, Any]]:
    payload = lamb_auth.decode_token(token) if token else None
    if not payload or payload.get("lti_type") != RETURN_TYPE or not within_session(payload):
        return None
    if not payload.get("lti_resource_link_id") or not payload.get("lti_lms_user_id"):
        return None
    return payload
