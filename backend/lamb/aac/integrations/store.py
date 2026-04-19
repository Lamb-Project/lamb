"""Per-user integrations store — DB CRUD with encryption at rest.

The `user_integrations` table holds one row per (user_id, integration_id).
The config (URL, token, service, etc.) is Fernet-encrypted in `config_json`.
Only `configured`, `healthy`, and `last_verified_at` are ever exposed through
the liteshell API — plaintext credentials never leave this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from lamb.aac.integrations.crypto import decrypt_config, encrypt_config
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntegrationsStore:
    """CRUD for rows in LAMB_user_integrations."""

    def __init__(self) -> None:
        self.db = LambDatabaseManager()
        self._table = f"{self.db.table_prefix}user_integrations"

    # --- internal helpers ------------------------------------------------

    def _row_to_safe_dict(self, row: tuple, columns: list[str]) -> dict[str, Any]:
        """Return a row without the encrypted config_json field."""
        d = dict(zip(columns, row))
        d.pop("config_json", None)
        return d

    # --- read ------------------------------------------------------------

    def get_config(self, user_id: int, integration_id: str) -> Optional[dict[str, Any]]:
        """Return the decrypted config dict, or None if no integration is saved."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT config_json FROM {self._table} "
                f"WHERE user_id = ? AND integration_id = ?",
                (user_id, integration_id),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return decrypt_config(row[0])

    def list(self, user_id: int) -> list[dict[str, Any]]:
        """List integrations for a user (no credentials — just metadata)."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT integration_id, healthy, last_verified_at, "
                f"       created_at, updated_at "
                f"FROM {self._table} WHERE user_id = ? "
                f"ORDER BY integration_id",
                (user_id,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
        for r in rows:
            r["configured"] = True
            r["healthy"] = bool(r.get("healthy"))
        return rows

    # --- write -----------------------------------------------------------

    def save(
        self, user_id: int, integration_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Upsert an integration for a user. Encrypts config at rest."""
        ciphertext = encrypt_config(config)
        now = _now_iso()
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id FROM {self._table} "
                f"WHERE user_id = ? AND integration_id = ?",
                (user_id, integration_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    f"UPDATE {self._table} SET config_json = ?, updated_at = ?, "
                    f"    healthy = 0, last_verified_at = NULL "
                    f"WHERE id = ?",
                    (ciphertext, now, existing[0]),
                )
            else:
                cur.execute(
                    f"INSERT INTO {self._table} "
                    f"(user_id, integration_id, config_json, healthy, "
                    f" created_at, updated_at) "
                    f"VALUES (?, ?, ?, 0, ?, ?)",
                    (user_id, integration_id, ciphertext, now, now),
                )
            conn.commit()
        finally:
            conn.close()
        return {
            "integration_id": integration_id,
            "configured": True,
            "healthy": False,
            "last_verified_at": None,
            "updated_at": now,
        }

    def remove(self, user_id: int, integration_id: str) -> bool:
        """Delete an integration. Returns True if a row was deleted."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM {self._table} "
                f"WHERE user_id = ? AND integration_id = ?",
                (user_id, integration_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def set_health(
        self, user_id: int, integration_id: str, healthy: bool
    ) -> Optional[dict[str, Any]]:
        """Update the health flag and verified timestamp. None if row missing."""
        now = _now_iso()
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {self._table} SET healthy = ?, last_verified_at = ?, "
                f"    updated_at = ? "
                f"WHERE user_id = ? AND integration_id = ?",
                (1 if healthy else 0, now, now, user_id, integration_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        finally:
            conn.close()
        return {
            "integration_id": integration_id,
            "healthy": healthy,
            "last_verified_at": now,
        }
