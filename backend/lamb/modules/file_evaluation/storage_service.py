"""
File storage service for the file_evaluation module.

Files are stored under ``{LAMB_DB_PATH}/uploads/file-eval/{activity_id}/``, next
to the database that references them, so they live in the same persistent volume
and the same backup.

The database keeps the path *relative* to that root (``{activity_id}/{file}``).
Rows written before this layout hold an absolute path under
``.../uploads/file-eval/``; ``resolve_path`` maps those onto the current root.
"""
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Optional

import config
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")

_UPLOADS_SUBDIR = ("uploads", "file-eval")
_LEGACY_MARKER = "/uploads/file-eval/"


def uploads_root() -> str:
    return os.path.abspath(os.path.join(config.LAMB_DB_PATH, *_UPLOADS_SUBDIR))


class FileStorageService:
    """Manage the uploads directory for file-eval submissions."""

    @classmethod
    def ensure_uploads_root(cls) -> str:
        root = uploads_root()
        os.makedirs(root, exist_ok=True)
        return root

    @classmethod
    def ensure_activity_directory(cls, activity_id: int) -> str:
        d = os.path.join(cls.ensure_uploads_root(), str(activity_id))
        os.makedirs(d, exist_ok=True)
        return d

    @classmethod
    def save_submission_file(
        cls,
        *,
        activity_id: int,
        submission_id: str,
        file_name: str,
        file_bytes: bytes,
        previous_file_path: Optional[str] = None,
    ) -> str:
        """Persist a file and return its path relative to the uploads root (stored in DB)."""
        activity_dir = cls.ensure_activity_directory(activity_id)

        if previous_file_path:
            cls.delete_path(previous_file_path)

        sanitized = cls._sanitize_filename(file_name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_name = f"{submission_id}_{ts}_{sanitized}"

        with open(os.path.join(activity_dir, dest_name), "wb") as fh:
            fh.write(file_bytes)

        return f"{activity_id}/{dest_name}"

    @classmethod
    def resolve_path(cls, stored_path: Optional[str]) -> Optional[str]:
        """Absolute path for a ``file_path`` value from the DB, or None if it
        does not point inside the uploads root."""
        if not stored_path:
            return None
        root = uploads_root()
        normalized = stored_path.replace("\\", "/")
        if os.path.isabs(stored_path) or _LEGACY_MARKER in normalized:
            # Legacy absolute path: keep only what follows .../uploads/file-eval/
            _, found, tail = normalized.rpartition(_LEGACY_MARKER)
            if not found:
                return None
            normalized = tail
        candidate = os.path.abspath(os.path.join(root, *normalized.split("/")))
        try:
            if candidate == root or os.path.commonpath([candidate, root]) != root:
                return None
        except ValueError:
            return None
        return candidate

    @classmethod
    def delete_path(cls, stored_path: Optional[str]) -> None:
        abs_path = cls.resolve_path(stored_path)
        if not abs_path:
            return
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path, ignore_errors=True)
        elif os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass

    @staticmethod
    def _sanitize_filename(file_name: str) -> str:
        base = os.path.basename(file_name or "")
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
        return cleaned or "submission"
