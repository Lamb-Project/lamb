"""
LTI Activity Manager

Business logic for the unified LTI activity endpoint.
Handles credential resolution, instructor identification,
activity configuration, and student launch.
"""

import os
import re
import time
import hmac
import hashlib
import base64
import urllib.parse
from typing import Optional, Dict, List, Any, Tuple

from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.owi_bridge.owi_group import OwiGroupManager
from lamb.owi_bridge.owi_model import OWIModel
from lamb.owi_bridge.owi_database import OwiDatabaseManager
from lamb.logging_config import get_logger
from lamb.auth_context import validate_user_enabled
from fastapi import HTTPException

logger = get_logger(__name__, component="LTI_ACTIVITY")


class LtiActivityManager:
    """Manages the unified LTI activity lifecycle."""

    def __init__(self):
        self.db_manager = LambDatabaseManager()

    # =========================================================================
    # Credential Resolution
    # =========================================================================

    def get_lti_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get global LTI consumer key and secret.
        DB overrides .env.
        """
        db_config = self.db_manager.get_lti_global_config()
        if db_config:
            return db_config['oauth_consumer_key'], db_config['oauth_consumer_secret']

        key = os.getenv('LTI_GLOBAL_CONSUMER_KEY', 'lamb')
        secret = os.getenv('LTI_GLOBAL_SECRET') or os.getenv('LTI_SECRET')
        if secret:
            return key, secret
        return None, None

    # =========================================================================
    # OAuth 1.0 Signature
    # =========================================================================

    def validate_oauth_signature(self, post_data: dict, http_method: str,
                                  base_url: str) -> bool:
        """
        Validate OAuth 1.0 HMAC-SHA1 signature using global LTI credentials.
        Returns True if signature is valid.
        """
        _, consumer_secret = self.get_lti_credentials()
        if not consumer_secret:
            logger.error("No LTI secret configured (neither DB nor .env)")
            return False

        computed = self._compute_oauth_signature(post_data, http_method,
                                                  base_url, consumer_secret)
        received = post_data.get("oauth_signature", "")

        if computed != received:
            logger.error(f"OAuth signature mismatch. Computed: {computed}, Received: {received}")
            return False

        logger.debug("OAuth signature validated successfully")
        return True

    @staticmethod
    def _compute_oauth_signature(params: dict, http_method: str,
                                  base_url: str, consumer_secret: str,
                                  token_secret: str = "") -> str:
        """Compute OAuth 1.0 HMAC-SHA1 signature."""
        params_copy = {k: v for k, v in params.items() if k != "oauth_signature"}
        sorted_params = sorted(params_copy.items())
        encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

        base_string = "&".join([
            http_method.upper(),
            urllib.parse.quote(base_url, safe=''),
            urllib.parse.quote(encoded_params, safe='')
        ])

        signing_key = f"{consumer_secret}&{token_secret}"
        hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
        return base64.b64encode(hashed.digest()).decode()

    # =========================================================================
    # Role Detection
    # =========================================================================

    @staticmethod
    def is_instructor(roles_str: str) -> bool:
        """Check if the LTI roles string indicates an instructor."""
        if not roles_str:
            return False
        roles_lower = roles_str.lower()
        instructor_indicators = [
            'instructor', 'teacher', 'contentdeveloper',
            'administrator', 'teachingassistant',
            'urn:lti:role:ims/lis/instructor',
            'urn:lti:instrole:ims/lis/instructor',
        ]
        return any(indicator in roles_lower for indicator in instructor_indicators)

    # =========================================================================
    # Instructor Identification
    # =========================================================================

    def identify_instructor(self, lms_user_id: str,
                             lms_email: str = None) -> List[Dict[str, Any]]:
        """
        Identify LAMB Creator users matching an LMS identity.
        Uses waterfall: email match → lti_user_id match → identity links.
        Returns list of Creator user dicts (may span multiple orgs).
        """
        return self.db_manager.get_creator_users_by_lms_identity(
            lms_user_id=lms_user_id,
            lms_email=lms_email
        )

    def link_identity(self, lms_user_id: str, creator_user_id: int,
                       lms_email: str = None) -> Optional[int]:
        """Store a link between an LMS identity and a Creator user."""
        return self.db_manager.create_lti_identity_link(
            lms_user_id=lms_user_id,
            creator_user_id=creator_user_id,
            lms_email=lms_email
        )

    def verify_creator_credentials(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify Creator user credentials for the identity-linking flow.
        Returns a normalized Creator user dict if valid, None otherwise.
        Keys: id, organization_id, user_email, user_name, user_type, enabled
        """
        # Check password via OWI
        verified = self.owi_user_manager.verify_user(email, password)
        if not verified:
            return None
        
        # Verify user exists and is enabled (delegates to AuthContext validation)
        try:
            creator_user = validate_user_enabled(email)
        except HTTPException:
            # User doesn't exist or is disabled
            return None
        
        # Normalize field names (get_creator_user_by_email uses 'email'/'name',
        # but the rest of the LTI code uses 'user_email'/'user_name')
        return {
            'id': creator_user['id'],
            'organization_id': creator_user['organization_id'],
            'user_email': creator_user.get('email') or creator_user.get('user_email'),
            'user_name': creator_user.get('name') or creator_user.get('user_name'),
            'user_type': creator_user.get('user_type', 'creator'),
            'enabled': creator_user.get('enabled', True),
        }

    # =========================================================================
    # Published Assistants
    # =========================================================================

    def get_published_assistants_for_instructor(
        self, creator_users: List[Dict], organization_id: int = None
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Get published assistants grouped by organization.
        If organization_id is given, filter to that org only.
        Returns: {org_id: [assistant_dict, ...]}
        """
        result = {}
        for cu in creator_users:
            org_id = cu['organization_id']
            if organization_id and org_id != organization_id:
                continue
            assistants = self.db_manager.get_published_assistants_for_org_user(
                organization_id=org_id,
                creator_user_id=cu['id'],
                creator_user_email=cu['user_email']
            )
            if assistants:
                if org_id not in result:
                    result[org_id] = []
                result[org_id].extend(assistants)
        return result

    # =========================================================================
    # Activity Configuration
    # =========================================================================

    def configure_activity(
        self,
        resource_link_id: str,
        organization_id: int,
        assistant_ids: List[int],
        configured_by_email: str,
        configured_by_name: str = None,
        context_id: str = None,
        context_title: str = None,
        activity_name: str = None,
        chat_visibility_enabled: bool = False,
        activity_type: str = "chat",
    ) -> Optional[Dict[str, Any]]:
        """
        Configure a new LTI activity:
        1. Store the activity and its assistant list in LAMB DB
        Returns the activity dict or None on failure.
        """
        # Store in LAMB DB
        activity_id = self.db_manager.create_lti_activity(
            resource_link_id=resource_link_id,
            organization_id=organization_id,
            owi_group_id="",
            owi_group_name="",
            configured_by_email=configured_by_email,
            configured_by_name=configured_by_name,
            context_id=context_id,
            context_title=context_title,
            activity_name=activity_name,
            chat_visibility_enabled=chat_visibility_enabled,
            activity_type=activity_type
        )
        if not activity_id:
            logger.error(f"Failed to create LTI activity record for {resource_link_id}")
            return None

        # Store assistant links
        self.db_manager.add_assistants_to_activity(activity_id, assistant_ids)

        return self.db_manager.get_lti_activity_by_resource_link(resource_link_id)

    def reconfigure_activity(
        self,
        activity: Dict[str, Any],
        new_assistant_ids: List[int]
    ) -> bool:
        """
        Reconfigure an existing activity's assistant selection in LAMB db.
        """
        activity_id = activity['id']

        current_assistants = self.db_manager.get_activity_assistants(activity_id)
        current_ids = {a['id'] for a in current_assistants}
        new_ids = set(new_assistant_ids)

        to_add = new_ids - current_ids
        to_remove = current_ids - new_ids

        # Update DB
        if to_remove:
            self.db_manager.remove_assistants_from_activity(activity_id, list(to_remove))
        if to_add:
            self.db_manager.add_assistants_to_activity(activity_id, list(to_add))

        self.db_manager.update_lti_activity(activity_id, status='active')
        return True

    # =========================================================================
    # Student / User Launch
    # =========================================================================

    @staticmethod
    def sanitize_for_email(value: str, max_length: int = 80) -> str:
        """Sanitize a string for use in email local-part."""
        sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
        return sanitized[:max_length] if sanitized else "user"

    def generate_student_email(self, username: str, resource_link_id: str) -> str:
        """Generate synthetic email for a student in an activity."""
        safe_user = self.sanitize_for_email(username)
        safe_rlid = self.sanitize_for_email(resource_link_id, max_length=60)
        return f"{safe_user}_{safe_rlid}@lamb-lti.local"

    # =========================================================================
    # URL helpers
    # =========================================================================

    @staticmethod
    def build_base_url(request) -> str:
        """Build the base URL for OAuth signature from request headers."""
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("Host", request.url.hostname)
        prefix = request.headers.get("X-Forwarded-Prefix", "")
        return f"{proto}://{host}{prefix}{request.url.path}"

    @staticmethod
    def get_owi_redirect_url(token: str) -> str:
        """Build the OWI redirect URL with token."""
        import config
        owi_public = (os.getenv("OWI_PUBLIC_BASE_URL")
                      or os.getenv("OWI_BASE_URL")
                      or config.OWI_PUBLIC_BASE_URL)
        return f"{owi_public}/api/v1/auths/complete?token={token}"

    @staticmethod
    def get_public_base_url(request) -> str:
        """Get the public-facing base URL for LAMB."""
        public = os.getenv("LAMB_PUBLIC_BASE_URL")
        if public:
            return public
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("Host", request.url.hostname)
        prefix = request.headers.get("X-Forwarded-Prefix", "")
        return f"{proto}://{host}{prefix}"

    # =========================================================================
    # Consent
    # =========================================================================

    def check_student_consent(self, activity: Dict[str, Any], user_email: str) -> bool:
        """
        Check if a student needs to give consent for chat visibility.
        Returns True if consent is needed (chat_visibility enabled + no consent yet).
        """
        if not activity.get('chat_visibility_enabled'):
            return False
        user_record = self.db_manager.get_activity_user(activity['id'], user_email)
        if not user_record:
            return True  # New user, consent needed
        return user_record.get('consent_given_at') is None

    def record_consent(self, activity_id: int, user_email: str) -> bool:
        """Record student consent for chat visibility."""
        return self.db_manager.record_student_consent(activity_id, user_email)

    # =========================================================================
    # =========================================================================
    # Dashboard Data Base
    # =========================================================================

    def get_dashboard_students(self, activity_id: int, page: int = 1,
                                per_page: int = 20) -> Dict[str, Any]:
        """Get anonymized student list for the dashboard."""
        data = self.db_manager.get_activity_students(activity_id, page, per_page)
        offset = (page - 1) * per_page
        anonymized = []
        for i, student in enumerate(data['students']):
            anonymized.append({
                "anonymous_id": f"Student {offset + i + 1}",
                "first_access": student['created_at'],
                "last_access": student.get('last_access_at') or student['created_at'],
                "access_count": student.get('access_count', 0),
                "has_consented": student.get('consent_given_at') is not None,
            })
        return {"students": anonymized, "total": data['total']}
