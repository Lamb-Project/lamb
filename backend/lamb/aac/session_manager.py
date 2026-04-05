"""AAC session management.

Sessions track the conversation between a user and the AAC agent,
along with the assistant being designed and any test results.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


class AACSessionManager:
    """Manage AAC design sessions."""

    def __init__(self):
        self.db = LambDatabaseManager()
        self._table = f"{self.db.table_prefix}aac_sessions"

    def create_session(
        self,
        user_email: str,
        organization_id: int,
        assistant_id: Optional[int] = None,
        title: str = "",
    ) -> dict:
        """Create a new design session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO {self._table}
                   (id, assistant_id, user_email, organization_id, status, conversation, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', '[]', ?, ?, ?)""",
                (session_id, assistant_id, user_email, organization_id, title, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "id": session_id,
            "assistant_id": assistant_id,
            "title": title,
            "status": "active",
            "created_at": now,
        }

    def get_session(self, session_id: str, user_email: str) -> Optional[dict]:
        """Get a session by ID (scoped to user)."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self._table} WHERE id = ? AND user_email = ?",
                (session_id, user_email),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            session = dict(zip(columns, row))
            raw = json.loads(session.get("conversation", "[]"))
            # Support both old format (plain list) and new format (envelope)
            if isinstance(raw, dict) and "messages" in raw:
                session["conversation"] = raw["messages"]
                session["pending_action"] = raw.get("pending_action")
                session["skill_info"] = raw.get("skill_info")
                session["tool_audit"] = raw.get("tool_audit", [])
            else:
                session["conversation"] = raw
                session["pending_action"] = None
                session["skill_info"] = None
                session["tool_audit"] = []
            return session
        finally:
            conn.close()

    def list_sessions(self, user_email: str) -> list[dict]:
        """List all sessions for a user with tool stats."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT id, assistant_id, status, title, created_at, updated_at, conversation
                   FROM {self._table} WHERE user_email = ?
                   ORDER BY updated_at DESC""",
                (user_email,),
            )
            columns = [desc[0] for desc in cursor.description]
            sessions = []
            for row in cursor.fetchall():
                s = dict(zip(columns, row))
                # Extract stats from conversation envelope
                tool_calls = 0
                tool_errors = 0
                turn_count = 0
                skill_id = None
                try:
                    raw = json.loads(s.get("conversation") or "[]")
                    if isinstance(raw, dict):
                        messages = raw.get("messages", [])
                        audit = raw.get("tool_audit", [])
                        skill_info = raw.get("skill_info") or {}
                        skill_id = skill_info.get("skill_id")
                        tool_calls = len(audit)
                        tool_errors = sum(1 for e in audit if not e.get("success"))
                    else:
                        messages = raw
                    turn_count = sum(1 for m in messages if m.get("role") == "user")
                except Exception:
                    pass
                s.pop("conversation", None)  # don't send full conversation in list
                s["tool_calls"] = tool_calls
                s["tool_errors"] = tool_errors
                s["turn_count"] = turn_count
                s["skill_id"] = skill_id
                sessions.append(s)
            return sessions
        finally:
            conn.close()

    def update_conversation(
        self,
        session_id: str,
        user_email: str,
        conversation: list[dict],
        assistant_id: Optional[int] = None,
        pending_action: Optional[dict] = None,
        skill_info: Optional[dict] = None,
        tool_audit: Optional[list] = None,
    ) -> None:
        """Update the conversation history and all session state.

        All state is serialized into the conversation JSON envelope so it
        survives across stateless request boundaries.
        """
        now = datetime.utcnow().isoformat()
        stored = {
            "messages": conversation,
            "pending_action": pending_action,
            "skill_info": skill_info,
            "tool_audit": tool_audit or [],
        }
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            update_fields = "conversation = ?, updated_at = ?"
            params: list[Any] = [json.dumps(stored, default=str, ensure_ascii=False), now]
            if assistant_id is not None:
                update_fields += ", assistant_id = ?"
                params.append(assistant_id)
            params.extend([session_id, user_email])
            cursor.execute(
                f"UPDATE {self._table} SET {update_fields} WHERE id = ? AND user_email = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()

    def delete_session(self, session_id: str, user_email: str) -> bool:
        """Delete (archive) a session."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {self._table} SET status = 'archived', updated_at = ? WHERE id = ? AND user_email = ?",
                (datetime.utcnow().isoformat(), session_id, user_email),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
