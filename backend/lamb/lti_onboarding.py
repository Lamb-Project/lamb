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

from lamb import auth as lamb_auth
from lamb.logging_config import get_logger
from lamb.lti13 import is_scoped

logger = get_logger(__name__, component="LTI")

TICKET_TYPE = "onboarding"
TICKET_LIFETIME = timedelta(minutes=15)
ATTEMPT_WINDOW_SECONDS = 15 * 60
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
    "failed": "The account could not be created. Open the activity from your LMS again, or contact your LAMB administrator.",
}
# Outcomes that tell the instructor to talk to someone: the organization's own text follows them.
SHOW_ORGANIZATION_TEXT = {"disabled", "expired", "used_up", "not_allowed", "account_disabled"}


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
            FOREIGN KEY(code_id) REFERENCES {p}lti_creator_codes(id))''',
        '''CREATE TABLE IF NOT EXISTS {p}lti_onboarding_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, identity_hash TEXT NOT NULL,
            launch_id TEXT NOT NULL, outcome TEXT NOT NULL, attempted_at INTEGER NOT NULL)''',
        '''CREATE INDEX IF NOT EXISTS {p}lti_onboarding_attempts_identity
            ON {p}lti_onboarding_attempts(identity_hash, attempted_at)''',
    ):
        cursor.execute(sql.format(p=prefix))


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
    if organization.get("is_system"):
        raise ValueError("Creator codes cannot be created for the system organization")
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
                 context_id: str = "", context_title: str = "", protocol: str) -> str:
    """Sign what the LMS asserted in this launch. Call only after the launch was verified
    and only for a launch that carries the instructor role."""
    return lamb_auth.create_token({
        "lti_type": TICKET_TYPE,
        "lti_instructor": True,
        "lti_protocol": protocol,
        "lti_launch_id": secrets.token_hex(16),
        "lti_lms_user_id": lms_user_id,
        "lti_lms_email": lms_email or "",
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
    # A 1.3 identity is LAMB's scoped identifier, a 1.1 identity never is.
    if is_scoped(payload["lti_lms_user_id"]) != (payload["lti_protocol"] == "1.3"):
        return None
    return payload


def allowed_organizations(db, ticket: Dict[str, Any]) -> Optional[List[int]]:
    """Organizations this launch may enter: those of its LTI 1.3 registration, or None (any) for LTI 1.1."""
    if ticket["lti_protocol"] != "1.3":
        return None
    from lamb.lti13.store import Store
    store = Store(db)
    user = store.object(ticket["lti_lms_user_id"], "user")
    return list(store.registration(user["registration_id"], user["deployment_id"])["organization_ids"])


# ---------------------------------------------------------------------------
# Redemption
# ---------------------------------------------------------------------------

@dataclass
class Redemption:
    ok: bool
    reason: str = ""
    creator_user: Optional[Dict[str, Any]] = None
    organization: Optional[Dict[str, Any]] = None

    @property
    def message(self) -> str:
        return MESSAGES.get(self.reason, MESSAGES["failed"])


def _identity_hash(ticket: Dict[str, Any]) -> str:
    return hashlib.sha256(f"{ticket['lti_protocol']}:{ticket['lti_lms_user_id']}".encode()).hexdigest()


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
        WHERE identity_hash=? AND attempted_at>? AND outcome!='ok' ''', (identity, now - ATTEMPT_WINDOW_SECONDS))[0]["n"]
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
    if not organization or organization.get("is_system"):
        return _refuse(db, ticket, "invalid", code_id=row["id"])
    status = _status(row, now)
    if status != "active":
        return _refuse(db, ticket, status, organization, row["id"])
    try:
        allowed = allowed_organizations(db, ticket)
    except ValueError:
        return _refuse(db, ticket, "not_allowed", organization, row["id"])
    if allowed is not None and organization["id"] not in allowed:
        return _refuse(db, ticket, "not_allowed", organization, row["id"])

    lms_user_id = ticket["lti_lms_user_id"]
    existing = db.get_creator_user_by_lti(organization["id"], lms_user_id)
    if existing and not existing.get("enabled", True):
        return _refuse(db, ticket, "account_disabled", organization, row["id"])

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
            user_name=ticket.get("lti_display_name") or "LTI User")
        if not creator_id:
            _write(db, "UPDATE {p}lti_creator_codes SET use_count=use_count-1 WHERE id=? AND use_count>0", (row["id"],))
            return _refuse(db, ticket, "failed", organization, row["id"])
    try:
        manager.link_identity(lms_user_id=lms_user_id, creator_user_id=creator_id,
                              lms_email=ticket.get("lti_lms_email") or None)
    except ValueError:
        return _refuse(db, ticket, "not_allowed", organization, row["id"])

    _write(db, '''INSERT OR IGNORE INTO {p}lti_creator_code_redemptions
        (code_id, creator_user_id, identity_hash, launch_id, protocol, redeemed_at) VALUES (?,?,?,?,?,?)''',
        (row["id"], creator_id, identity, ticket["lti_launch_id"], ticket["lti_protocol"], now))
    _record(db, ticket, "ok")
    creator = db.get_creator_user_by_id(creator_id)
    logger.info(f"Creator code {row['id']} redeemed: creator user {creator_id} in organization {organization['id']}")
    return Redemption(True, "ok", creator_user={
        "id": creator_id, "organization_id": organization["id"],
        "user_email": creator.get("user_email") or creator.get("email"),
        "user_name": creator.get("user_name") or creator.get("name"),
    }, organization=organization)
