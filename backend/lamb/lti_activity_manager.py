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

logger = get_logger(__name__, component="LTI_ACTIVITY")


class LtiActivityManager:
    """Manages the unified LTI activity lifecycle."""

    def __init__(self):
        self.db_manager = LambDatabaseManager()
        self.owi_user_manager = OwiUserManager()
        self.owi_group_manager = OwiGroupManager()

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
        # Get the Creator user from LAMB DB
        creator_user = self.db_manager.get_creator_user_by_email(email)
        if not creator_user:
            return None
        if not creator_user.get('enabled', True):
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
    ) -> Optional[Dict[str, Any]]:
        """
        Configure a new LTI activity:
        1. Create OWI group for the activity
        2. Add the group to each selected assistant model's access control
        3. Store the activity and its assistant list in LAMB DB
        Returns the activity dict or None on failure.
        """
        group_name = f"lti_activity_{resource_link_id}"

        # Get an OWI admin user to own the group
        # Use the instructor's OWI account
        owi_user = self.owi_user_manager.get_user_by_email(configured_by_email)
        if not owi_user:
            logger.error(f"No OWI user found for {configured_by_email}")
            return None

        # Create OWI group
        owi_group = self.owi_group_manager.create_group(
            name=group_name,
            user_id=owi_user['id'],
            description=f"LTI Activity: {activity_name or resource_link_id}"
        )
        if not owi_group:
            logger.error(f"Failed to create OWI group for activity {resource_link_id}")
            return None

        owi_group_id = owi_group['id']
        logger.info(f"Created OWI group {owi_group_id} for activity {resource_link_id}")

        # Add activity group to each selected assistant model's read access
        owi_db = OwiDatabaseManager()
        owi_model = OWIModel(owi_db)
        for aid in assistant_ids:
            model_id = f"lamb_assistant.{aid}"
            success = owi_model.add_group_to_model(
                model_id=model_id,
                group_id=owi_group_id,
                permission_type="read"
            )
            if success:
                logger.info(f"Added activity group to model {model_id}")
            else:
                logger.warning(f"Failed to add activity group to model {model_id}")

        # Store in LAMB DB
        activity_id = self.db_manager.create_lti_activity(
            resource_link_id=resource_link_id,
            organization_id=organization_id,
            owi_group_id=owi_group_id,
            owi_group_name=group_name,
            configured_by_email=configured_by_email,
            configured_by_name=configured_by_name,
            context_id=context_id,
            context_title=context_title,
            activity_name=activity_name
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
        Reconfigure an existing activity's assistant selection.
        Adds group to new models, removes from old ones.
        """
        activity_id = activity['id']
        owi_group_id = activity['owi_group_id']

        current_assistants = self.db_manager.get_activity_assistants(activity_id)
        current_ids = {a['id'] for a in current_assistants}
        new_ids = set(new_assistant_ids)

        to_add = new_ids - current_ids
        to_remove = current_ids - new_ids

        owi_db = OwiDatabaseManager()
        owi_model = OWIModel(owi_db)

        # Add group to new models
        for aid in to_add:
            owi_model.add_group_to_model(f"lamb_assistant.{aid}", owi_group_id, "read")

        # Remove group from old models
        for aid in to_remove:
            owi_model.remove_group_from_model(f"lamb_assistant.{aid}", owi_group_id, "read")

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

    def handle_student_launch(
        self,
        activity: Dict[str, Any],
        username: str,
        display_name: str,
        lms_user_id: str = None,
    ) -> Optional[str]:
        """
        Handle a student (or instructor-as-user) launch into a configured activity.
        1. Generate synthetic email
        2. Get/create OWI user
        3. Add to activity's OWI group
        4. Record in lti_activity_users
        5. Get auth token
        Returns the OWI auth token or None on failure.
        """
        email = self.generate_student_email(username, activity['resource_link_id'])
        logger.info(f"Student launch: {email} for activity {activity['resource_link_id']}")

        # Get or create OWI user
        owi_user = self.owi_user_manager.get_user_by_email(email)
        if not owi_user:
            logger.info(f"Creating new OWI user for {email}")
            owi_user = self.owi_user_manager.create_user(
                name=display_name,
                email=email,
                password=f"lti_activity_{activity['id']}",
                role="user"
            )
            if not owi_user:
                logger.error(f"Failed to create OWI user for {email}")
                return None

        # Add to activity's OWI group
        add_result = self.owi_group_manager.add_user_to_group_by_email(
            group_id=activity['owi_group_id'],
            user_email=email
        )
        if add_result.get("status") == "error" and "already a member" not in add_result.get("error", "").lower():
            logger.warning(f"Could not add {email} to group: {add_result.get('error')}")

        # Record in LAMB DB
        self.db_manager.create_lti_activity_user(
            activity_id=activity['id'],
            user_email=email,
            user_name=username,
            user_display_name=display_name,
            lms_user_id=lms_user_id
        )

        # Get auth token
        token = self.owi_user_manager.get_auth_token(email, display_name)
        if not token:
            logger.error(f"Failed to get auth token for {email}")
            return None

        return token

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
