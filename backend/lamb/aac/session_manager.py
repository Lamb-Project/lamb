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
            # Support both old format (plain list) and new format (envelope with pending_action)
            if isinstance(raw, dict) and "messages" in raw:
                session["conversation"] = raw["messages"]
                session["pending_action"] = raw.get("pending_action")
            else:
                session["conversation"] = raw
                session["pending_action"] = None
            return session
        finally:
            conn.close()

    def list_sessions(self, user_email: str) -> list[dict]:
        """List all sessions for a user."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT id, assistant_id, status, created_at, updated_at
                   FROM {self._table} WHERE user_email = ?
                   ORDER BY updated_at DESC""",
                (user_email,),
            )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_conversation(
        self,
        session_id: str,
        user_email: str,
        conversation: list[dict],
        assistant_id: Optional[int] = None,
        pending_action: Optional[dict] = None,
    ) -> None:
        """Update the conversation history and pending action for a session.

        The pending_action is serialized into the conversation JSON as a
        special envelope so it survives across stateless request boundaries.
        """
        now = datetime.utcnow().isoformat()
        # Pack pending_action into the stored blob
        stored = {
            "messages": conversation,
            "pending_action": pending_action,
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
