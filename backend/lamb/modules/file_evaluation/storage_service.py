"""
File storage service for the file_evaluation module.

Files are stored under ``{BACKEND_DIR}/uploads/file-eval/{activity_id}/``.
"""
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Optional
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
UPLOADS_ROOT = os.path.join(_BACKEND_DIR, "uploads", "file-eval")


class FileStorageService:
    """Manage the uploads directory for file-eval submissions."""

    @classmethod
    def ensure_uploads_root(cls) -> str:
        os.makedirs(UPLOADS_ROOT, exist_ok=True)
        return UPLOADS_ROOT

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
        """Persist a file and return its *absolute* path (stored in DB)."""
        activity_dir = cls.ensure_activity_directory(activity_id)

        if previous_file_path:
            cls.delete_path(previous_file_path)

        sanitized = cls._sanitize_filename(file_name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_name = f"{submission_id}_{ts}_{sanitized}"
        dest_path = os.path.join(activity_dir, dest_name)

        with open(dest_path, "wb") as fh:
            fh.write(file_bytes)

        return dest_path

    @classmethod
    def is_within_uploads(cls, path: str) -> bool:
        root = cls.ensure_uploads_root()
        try:
            return os.path.commonpath([os.path.abspath(path), root]) == root
        except ValueError:
            return False

    @classmethod
    def delete_path(cls, path: str) -> None:
        if not path:
            return
        abs_path = os.path.abspath(path)
        if not cls.is_within_uploads(abs_path):
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
