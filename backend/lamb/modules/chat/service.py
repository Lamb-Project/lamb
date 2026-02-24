from typing import Dict, Any, List, Optional, Tuple
import time
import re
import os

from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.owi_bridge.owi_groups import OwiGroupManager
from lamb.owi_bridge.owi_database import OwiDatabaseManager, OWIModel
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="CHAT_MODULE_SERVICE")

class ChatModuleService:
    """
    Handles the Open WebUI (OWI) specific logic for the Chat module.
    Extracted from the generic LtiActivityManager.
    """
    def __init__(self):
        self.db_manager = LambDatabaseManager()
        self.owi_user_manager = OwiUserManager()
        self.owi_group_manager = OwiGroupManager()

    def configure_activity(self, activity_id: int, setup_data: Dict[str, Any]) -> None:
        """
        Creates the OWI group and adds/removes assistant models.
        Called after the activity is created in LAMB's DB.
        """
        resource_link_id = setup_data['resource_link_id']
        assistant_ids = setup_data['assistant_ids']
        configured_by_email = setup_data['configured_by_email']
        activity_name = setup_data.get('activity_name', resource_link_id)

        group_name = f"lti_activity_{resource_link_id}"

        # Get an OWI admin user to own the group
        owi_user = self.owi_user_manager.get_user_by_email(configured_by_email)
        if not owi_user:
            logger.error(f"No OWI user found for {configured_by_email}")
            raise Exception(f"Configuration failed: Instructor {configured_by_email} not found in OWI")

        # Create OWI group
        owi_group = self.owi_group_manager.create_group(
            name=group_name,
            user_id=owi_user['id'],
            description=f"LTI Activity: {activity_name}"
        )
        if not owi_group:
            logger.error(f"Failed to create OWI group for activity {resource_link_id}")
            raise Exception(f"Configuration failed: Could not create OWI group")

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

        # Update LAMB DB activity record with the OWI details
        self.db_manager.execute_query(
            "UPDATE lti_activities SET owi_group_id = ?, owi_group_name = ? WHERE id = ?",
            (owi_group_id, group_name, activity_id)
        )

    def reconfigure_activity(self, activity_id: int, activity_data: Dict[str, Any], new_assistant_ids: List[int]) -> bool:
         """Reconfigure an existing activity's assistant selection."""
         owi_group_id = activity_data['owi_group_id']

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
         
         return True


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
        Handle a student (or instructor-as-user) launch into a configured chat activity.
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

        # Capture OWI user ID for dashboard chat queries
        owi_user_id = owi_user.get('id', '') if owi_user else ''

        # Add to activity's OWI group
        add_result = self.owi_group_manager.add_user_to_group_by_email(
            group_id=activity['owi_group_id'],
            user_email=email
        )
        if add_result.get("status") == "error" and "already a member" not in add_result.get("error", "").lower():
            logger.warning(f"Could not add {email} to group: {add_result.get('error')}")

        # Record in LAMB DB (also updates access tracking)
        self.db_manager.create_lti_activity_user(
            activity_id=activity['id'],
            user_email=email,
            user_name=username,
            user_display_name=display_name,
            lms_user_id=lms_user_id,
            owi_user_id=owi_user_id
        )

        # Get auth token
        token = self.owi_user_manager.get_auth_token(email, display_name)
        if not token:
            logger.error(f"Failed to get auth token for {email}")
            return None

        return token

    # =========================================================================
    # Dashboard Data
    # =========================================================================

    def get_dashboard_stats(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary statistics for the instructor dashboard."""
        activity_id = activity['id']

        # Student stats from LAMB DB
        student_data = self.db_manager.get_activity_students(activity_id, page=1, per_page=1)
        total_students = student_data['total']

        # Active in last 7 days
        seven_days_ago = int(time.time()) - (7 * 86400)
        all_students = self.db_manager.get_activity_students(activity_id, page=1, per_page=10000)
        active_7d = sum(1 for s in all_students['students']
                        if s.get('last_access_at') and s['last_access_at'] >= seven_days_ago)

        # Chat stats from OWI DB
        assistants = self.db_manager.get_activity_assistants(activity_id)
        owi_user_ids = self.db_manager.get_all_activity_user_owi_ids(activity_id)
        total_chats = 0
        total_messages = 0
        assistant_stats = []

        owi_db = OwiDatabaseManager()
        for asst in assistants:
            model_pattern = f'lamb_assistant.{asst["id"]}'
            chats, msgs = self._count_chats_for_model(owi_db, model_pattern, owi_user_ids)
            total_chats += chats
            total_messages += msgs
            assistant_stats.append({
                "id": asst["id"],
                "name": asst["name"],
                "owner": asst.get("owner", ""),
                "chat_count": chats,
                "message_count": msgs,
            })

        return {
            "total_students": total_students,
            "total_chats": total_chats,
            "total_messages": total_messages,
            "active_last_7d": active_7d,
            "assistants": assistant_stats,
        }

    def get_dashboard_chats(self, activity: Dict[str, Any],
                             assistant_id: int = None,
                             page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        Get anonymized chat list for the dashboard.
        Only works if chat_visibility_enabled is true.
        """
        if not activity.get('chat_visibility_enabled'):
            return {"chats": [], "total": 0, "error": "Chat visibility not enabled"}

        activity_id = activity['id']
        assistants = self.db_manager.get_activity_assistants(activity_id)
        owi_user_ids = self.db_manager.get_all_activity_user_owi_ids(activity_id)
        if not owi_user_ids:
            return {"chats": [], "total": 0}

        # Build student anonymization map (by created_at order)
        anon_map = self._build_anonymization_map(activity_id)

        # Build assistant name map
        asst_map = {f'lamb_assistant.{a["id"]}': a["name"] for a in assistants}

        # Filter to specific assistant if requested
        if assistant_id:
            target_models = [f'lamb_assistant.{assistant_id}']
        else:
            target_models = list(asst_map.keys())

        owi_db = OwiDatabaseManager()
        chats = self._query_activity_chats(owi_db, target_models, owi_user_ids,
                                            page, per_page, anon_map, asst_map)
        total = self._count_activity_chats(owi_db, target_models, owi_user_ids)

        return {"chats": chats, "total": total}

    def get_dashboard_chat_detail(self, activity: Dict[str, Any],
                                   chat_id: str) -> Optional[Dict[str, Any]]:
        """Get a single chat's full transcript, anonymized."""
        if not activity.get('chat_visibility_enabled'):
            return None

        activity_id = activity['id']
        owi_user_ids = self.db_manager.get_all_activity_user_owi_ids(activity_id)
        anon_map = self._build_anonymization_map(activity_id)
        assistants = self.db_manager.get_activity_assistants(activity_id)
        asst_map = {f'lamb_assistant.{a["id"]}': a["name"] for a in assistants}

        owi_db = OwiDatabaseManager()
        return self._query_chat_detail(owi_db, chat_id, owi_user_ids, anon_map, asst_map)

    # =========================================================================
    # OWI Chat Query Helpers (private)
    # =========================================================================

    def _build_anonymization_map(self, activity_id: int) -> Dict[str, str]:
        """Build a map from owi_user_id to 'Student N' (ordered by created_at)."""
        all_data = self.db_manager.get_activity_students(activity_id, page=1, per_page=100000)
        anon = {}
        for i, student in enumerate(all_data['students']):
            owi_uid = student.get('owi_user_id')
            if owi_uid:
                anon[owi_uid] = f"Student {i + 1}"
        return anon

    @staticmethod
    def _count_chats_for_model(owi_db, model_pattern: str,
                                owi_user_ids: List[str]) -> Tuple[int, int]:
        """Count chats and messages for a model, filtered by user IDs."""
        if not owi_user_ids:
            return 0, 0
        try:
            placeholders = ",".join("?" for _ in owi_user_ids)
            query = f"""
                SELECT c.chat FROM chat c
                WHERE json_extract(c.chat, '$.models') LIKE ?
                AND c.user_id IN ({placeholders})
            """
            import json as json_mod
            rows = owi_db.execute_query(query, (f'%{model_pattern}%', *owi_user_ids))
            if not rows:
                return 0, 0
            chat_count = len(rows)
            msg_count = 0
            for row in rows:
                try:
                    chat_data = json_mod.loads(row[0]) if isinstance(row[0], str) else row[0]
                    messages = chat_data.get('history', {}).get('messages', {})
                    if isinstance(messages, dict):
                        msg_count += len(messages)
                    elif isinstance(messages, list):
                        msg_count += len(messages)
                except (json_mod.JSONDecodeError, AttributeError):
                    pass
            return chat_count, msg_count
        except Exception as e:
            logger.error(f"Error counting chats for model {model_pattern}: {e}")
            return 0, 0

    @staticmethod
    def _count_activity_chats(owi_db, model_patterns: List[str],
                               owi_user_ids: List[str]) -> int:
        """Count total chats across models for activity users."""
        if not owi_user_ids or not model_patterns:
            return 0
        try:
            user_ph = ",".join("?" for _ in owi_user_ids)
            model_conditions = " OR ".join(
                "json_extract(c.chat, '$.models') LIKE ?" for _ in model_patterns
            )
            query = f"""
                SELECT COUNT(*) FROM chat c
                WHERE ({model_conditions})
                AND c.user_id IN ({user_ph})
            """
            params = [f'%{m}%' for m in model_patterns] + list(owi_user_ids)
            result = owi_db.execute_query(query, tuple(params), fetch_one=True)
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error counting activity chats: {e}")
            return 0

    @staticmethod
    def _query_activity_chats(owi_db, model_patterns: List[str],
                               owi_user_ids: List[str],
                               page: int, per_page: int,
                               anon_map: Dict[str, str],
                               asst_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Query paginated chat list for dashboard."""
        if not owi_user_ids or not model_patterns:
            return []
        try:
            import json as json_mod
            user_ph = ",".join("?" for _ in owi_user_ids)
            model_conditions = " OR ".join(
                "json_extract(c.chat, '$.models') LIKE ?" for _ in model_patterns
            )
            offset = (page - 1) * per_page
            query = f"""
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at, c.chat
                FROM chat c
                WHERE ({model_conditions})
                AND c.user_id IN ({user_ph})
                ORDER BY c.updated_at DESC
                LIMIT ? OFFSET ?
            """
            params = [f'%{m}%' for m in model_patterns] + list(owi_user_ids) + [per_page, offset]
            rows = owi_db.execute_query(query, tuple(params))
            if not rows:
                return []

            chats = []
            for row in rows:
                chat_id, user_id, title, created_at, updated_at, chat_json = row
                anon_name = anon_map.get(user_id, "Unknown Student")
                # Count messages
                msg_count = 0
                assistant_name = "Unknown"
                try:
                    chat_data = json_mod.loads(chat_json) if isinstance(chat_json, str) else chat_json
                    messages = chat_data.get('history', {}).get('messages', {})
                    msg_count = len(messages) if isinstance(messages, (dict, list)) else 0
                    models = chat_data.get('models', [])
                    for m in models:
                        if m in asst_map:
                            assistant_name = asst_map[m]
                            break
                except (Exception,):
                    pass

                chats.append({
                    "chat_id": chat_id,
                    "anonymous_student": anon_name,
                    "assistant_name": assistant_name,
                    "title": title or "(untitled)",
                    "message_count": msg_count,
                    "created_at": created_at,
                    "updated_at": updated_at,
                })
            return chats
        except Exception as e:
            logger.error(f"Error querying activity chats: {e}")
            return []

    @staticmethod
    def _query_chat_detail(owi_db, chat_id: str,
                            owi_user_ids: List[str],
                            anon_map: Dict[str, str],
                            asst_map: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Get full chat transcript, anonymized."""
        if not owi_user_ids:
            return None
        try:
            import json as json_mod
            user_ph = ",".join("?" for _ in owi_user_ids)
            query = f"""
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at, c.chat
                FROM chat c
                WHERE c.id = ? AND c.user_id IN ({user_ph})
            """
            row = owi_db.execute_query(query, (chat_id, *owi_user_ids), fetch_one=True)
            if not row:
                return None

            chat_id_val, user_id, title, created_at, updated_at, chat_json = row
            anon_name = anon_map.get(user_id, "Unknown Student")
            chat_data = json_mod.loads(chat_json) if isinstance(chat_json, str) else chat_json

            # Extract messages in order
            messages_raw = chat_data.get('history', {}).get('messages', {})
            messages = []
            if isinstance(messages_raw, dict):
                # Sort by timestamp or order
                sorted_msgs = sorted(messages_raw.values(),
                                      key=lambda m: m.get('timestamp', 0))
                for msg in sorted_msgs:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    messages.append({
                        "role": role,
                        "speaker": anon_name if role == 'user' else _get_assistant_display(msg, asst_map),
                        "content": content,
                        "timestamp": msg.get('timestamp'),
                    })
            elif isinstance(messages_raw, list):
                for msg in messages_raw:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    messages.append({
                        "role": role,
                        "speaker": anon_name if role == 'user' else _get_assistant_display(msg, asst_map),
                        "content": content,
                        "timestamp": msg.get('timestamp'),
                    })

            # Determine assistant name from models
            models = chat_data.get('models', [])
            assistant_name = "Unknown"
            for m in models:
                if m in asst_map:
                    assistant_name = asst_map[m]
                    break

            return {
                "chat_id": chat_id_val,
                "anonymous_student": anon_name,
                "assistant_name": assistant_name,
                "title": title or "(untitled)",
                "message_count": len(messages),
                "created_at": created_at,
                "updated_at": updated_at,
                "messages": messages,
            }
        except Exception as e:
            logger.error(f"Error querying chat detail: {e}")
            return None

def _get_assistant_display(msg: dict, asst_map: Dict[str, str]) -> str:
    """Get display name for an assistant message."""
    model = msg.get('model', msg.get('modelId', ''))
    if model in asst_map:
        return asst_map[model]
    # Try matching partial
    for key, name in asst_map.items():
        if key in model or model in key:
            return name
    return "Assistant"
